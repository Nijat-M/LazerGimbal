# -*- coding: utf-8 -*-
"""
云台控制器核心模块 (Gimbal Controller Core)

[职责 Responsibility]
1. PID控制循环（固定频率 40Hz）
2. 步进电机相对原点状态管理
3. 视觉误差接收与处理（通过 ErrorProcessor）
4. 安全保护机制（看门狗、死区、软限位）

[架构设计 Architecture]
- Controller 层不包含任何 UI 代码
- GUI 调用 Controller 的方法
- Controller 通过 SerialThread 发送指令
- Controller 通过 Qt 信号通知 GUI 更新状态
- 所有控制参数统一从 ControlConfig 读取，无硬编码魔法数字
"""

import time
import math
import threading
from PyQt6.QtCore import QObject, pyqtSignal

from config import cfg
from config.control_config import ControlConfig
from core.control.error_processor import ErrorProcessor
from core.control.manual_aim_controller import ManualAimController
from utils.logger import Logger

logger = Logger("GimbalController")


class GimbalController(QObject):
    """
    云台控制器 (Gimbal Controller)

    负责所有控制逻辑，与 GUI 解耦。
    """

    # Qt 信号：通知 GUI 更新状态显示
    status_update_signal = pyqtSignal(str)        # 状态文本
    position_update_signal = pyqtSignal(float, float)  # X, Y 位置（度）
    manual_target_update_signal = pyqtSignal(float, float)  # 相对中心的 yaw/pitch
    laser_state_signal = pyqtSignal(bool, bool, int)  # 激光状态 (armed, firing, power)
    speed_gear_changed_signal = pyqtSignal(int, float)  # (gear: 1/2/3, multiplier: 0.3/1.0/2.2)

    def __init__(self, serial_thread):
        """
        初始化控制器

        Args:
            serial_thread: 串口通信线程实例
        """
        super().__init__()

        self.serial_thread = serial_thread

        # 3 级速度档位系统 (1: 微调/远距离防震 0.3x, 2: 标准 1.0x, 3: 高速 2.2x)
        self.speed_gear: int = 2
        self.speed_multiplier: float = 1.0

        # 当前硬件软件相对原点与动态角度估算 (单位: 度)
        self.servo_x: float = 0.0
        self.servo_y: float = 0.0

        # 接收 STM32 硬件遥测反馈
        if hasattr(self.serial_thread, "data_received_signal"):
            self.serial_thread.data_received_signal.connect(self._handle_serial_rx)

        # [激光武器控制状态]
        self.laser_armed: bool = False
        self.laser_firing: bool = False
        self.laser_power: int = 100

        # [误差处理器] 负责缩放和滤波（统一从 ControlConfig 读取参数）
        self.error_processor = ErrorProcessor()

        # [处理后的误差] 由视觉线程发来的坐标处理后存储在此
        self.current_error_x: int = 0
        self.current_error_y: int = 0
        self.last_vision_time: float = time.monotonic()

        # [控制开关]
        self.control_enabled: bool = False
        self.visual_input_enabled: bool = False

        # [FPS 鼠标瞄准]
        self.manual_aim = ManualAimController(
            sensitivity=ControlConfig.MOUSE_SENSITIVITY,
            yaw_limits=(ControlConfig.MOUSE_YAW_MIN, ControlConfig.MOUSE_YAW_MAX),
            pitch_limits=(ControlConfig.MOUSE_PITCH_MIN, ControlConfig.MOUSE_PITCH_MAX),
        )
        self.manual_mouse_enabled: bool = False
        self.mouse_capture_active: bool = False
        self.manual_motion_active: bool = False
        self._motion_lock = threading.RLock()

        # [反转设置] 从 ControlConfig 读取默认值
        self.invert_x: bool = ControlConfig.INVERT_X
        self.invert_y: bool = ControlConfig.INVERT_Y

        # 警告时间戳（防止刷屏）
        self.last_warn_time: float = 0.0

        # [手动连续移动控制 (按住连续动/键盘控制)]
        self._manual_jog_active: bool = False
        self._manual_jog_axis: str = 'x'
        self._manual_jog_dir: int = 0

        # [控制循环线程] 40Hz (25ms) 替代 QTimer
        self.is_running = True
        self.control_thread = threading.Thread(target=self._run_control_loop, daemon=True)
        self.control_thread.start()

    def set_speed_gear(self, gear: int) -> None:
        """设置电机速度档位 (1: 微调/远距离防震 0.3x, 2: 标准 1.0x, 3: 高速 2.2x)"""
        gear = max(1, min(3, int(gear)))
        self.speed_gear = gear
        if gear == 1:
            self.speed_multiplier = 0.30
            gear_name = "GEAR 1 (SLOW / PRECISION 0.3x)"
        elif gear == 2:
            self.speed_multiplier = 1.00
            gear_name = "GEAR 2 (NORMAL 1.0x)"
        else:
            self.speed_multiplier = 2.20
            gear_name = "GEAR 3 (FAST / TURBO 2.2x)"

        self.speed_gear_changed_signal.emit(self.speed_gear, self.speed_multiplier)
        self.status_update_signal.emit(f"⚡ 电机速度已切换为: {gear_name}")
        logger.info(f"[CONTROLLER] 电机速度档位更新: {gear_name}")

    def _handle_serial_rx(self, line: str) -> None:
        """解析 STM32 上报的遥测角度或状态 (e.g. 'P: 12.3, -4.5' or 'POS: <12.3, -4.5>')"""
        try:
            clean = line.strip()
            if ("P:" in clean or "POS:" in clean) and "," in clean:
                parts = clean.replace("POS:", "").replace("P:", "").replace("<", "").replace(">", "").split(",")
                if len(parts) >= 2:
                    px = float(parts[0].strip())
                    py = float(parts[1].strip())
                    self.servo_x = px
                    self.servo_y = py
                    self.position_update_signal.emit(self.servo_x, self.servo_y)
        except Exception:
            pass

    def set_laser_armed(self, armed: bool) -> None:
        """设置激光保险状态 (ARM / SAFE)"""
        self.laser_armed = armed
        if not armed and self.laser_firing:
            self.laser_firing = False
            if self._is_serial_connected():
                self.serial_thread.send_command("!LASER:0\n")
        self.laser_state_signal.emit(self.laser_armed, self.laser_firing, self.laser_power)
        logger.info(f"[LASER] 激光保险状态: {'🔴 ARMED' if armed else '🟢 SAFE'}")

    def set_laser_firing(self, firing: bool) -> None:
        """设置激光发射状态"""
        if not self.laser_armed:
            if firing:
                logger.warning("[LASER] 激光未解锁 (SAFE)，无法发射！")
            return
        self.laser_firing = firing
        if self._is_serial_connected():
            cmd = "!LASER:1\n" if firing else "!LASER:0\n"
            self.serial_thread.send_command(cmd)
        self.laser_state_signal.emit(self.laser_armed, self.laser_firing, self.laser_power)
        logger.info(f"[LASER] 激光发射状态: {'⚡ FIRING' if firing else 'STOPPED'}")

    def set_laser_power(self, power: int) -> None:
        """设置激光 PWM 输出功率 (0 ~ 100%)"""
        self.laser_power = max(0, min(100, int(power)))
        if self._is_serial_connected():
            self.serial_thread.send_command(f"!POWER:{self.laser_power}\n")
        self.laser_state_signal.emit(self.laser_armed, self.laser_firing, self.laser_power)
        logger.info(f"[LASER] 激光功率设定: {self.laser_power}%")


    def stop(self) -> None:
        """Stop motion and terminate the control thread."""
        with self._motion_lock:
            self.is_running = False
            self.control_enabled = False
            self.manual_mouse_enabled = False
            self.mouse_capture_active = False
            self.stop_motion()
        if self.control_thread.is_alive():
            self.control_thread.join(timeout=1.0)

    # --------------------------------------------------
    # 公共接口（GUI 调用）
    # --------------------------------------------------

    def set_control_enabled(self, enabled: bool) -> bool:
        """Enable or disable automatic visual tracking and report acceptance."""
        with self._motion_lock:
            if enabled and self.manual_mouse_enabled:
                self.status_update_signal.emit("Cannot start auto tracking in Mouse Aim mode")
                return False
            if enabled and not self.visual_input_enabled:
                self.status_update_signal.emit("Camera is not ready, cannot start tracking")
                return False

            self.control_enabled = enabled
            if not enabled:
                self.stop_motion()
        status = "Tracking Started" if enabled else "Tracking Stopped"
        self.status_update_signal.emit(status)
        logger.info(f"[CONTROLLER] {status}")
        return True

    def set_visual_input_enabled(self, enabled: bool) -> None:
        """Accept vision samples only while the current camera is confirmed live."""
        with self._motion_lock:
            self.visual_input_enabled = enabled
            if not enabled:
                self.stop_motion()

    def set_invert(self, invert_x: bool, invert_y: bool) -> None:
        """设置轴向反转"""
        self.invert_x = invert_x
        self.invert_y = invert_y
        ControlConfig.INVERT_X = invert_x
        ControlConfig.INVERT_Y = invert_y

    def set_manual_mouse_mode(self, enabled: bool) -> None:
        """Switch the controller between visual tracking and mouse aiming."""
        with self._motion_lock:
            was_enabled = self.manual_mouse_enabled
            self.manual_mouse_enabled = enabled
            self.mouse_capture_active = False
            self.manual_motion_active = False

            if enabled:
                self.control_enabled = False
                self.stop_motion()
            elif was_enabled:
                self.stop_motion()
            target = self.manual_aim.get_target()

        self.manual_target_update_signal.emit(*target)
        if enabled:
            self.status_update_signal.emit("Mouse Aim Ready: Click live view to start")

    def set_mouse_capture_active(self, active: bool) -> None:
        """Arm mouse motion only while the video widget owns the cursor."""
        with self._motion_lock:
            active = active and self.manual_mouse_enabled
            if self.mouse_capture_active == active:
                return
            self.mouse_capture_active = active
            if not active:
                self.stop_motion()
        status = "Mouse Captured (Press Esc to release)" if active else "Mouse Released (Motion Stopped)"
        self.status_update_signal.emit(status)

    def handle_mouse_delta(self, dx: int, dy: int) -> None:
        """Accumulate high-rate GUI mouse events without sending serial data."""
        with self._motion_lock:
            if not self.manual_mouse_enabled or not self.mouse_capture_active:
                return
            yaw, pitch = self.manual_aim.add_mouse_delta(dx, dy)
        self.manual_target_update_signal.emit(yaw, pitch)

    def update_mouse_sensitivity(self, sensitivity: float) -> None:
        self.manual_aim.set_sensitivity(sensitivity)
        ControlConfig.MOUSE_SENSITIVITY = sensitivity

    def stop_motion(self, reason: str | None = None) -> None:
        """Clear pending state and send a prioritized, explicit firmware STOP."""
        with self._motion_lock:
            self.current_error_x = 0
            self.current_error_y = 0
            self.error_processor.reset()
            target = self.manual_aim.discard_pending()
            self.manual_motion_active = False
            if self.serial_thread:
                self.serial_thread.send_stop_command()
        self.manual_target_update_signal.emit(*target)
        if reason:
            logger.warning(reason)
            self.status_update_signal.emit(reason)

    def update_pid_tunings(self, kp: float, ki: float, kd: float) -> None:
        """动态更新 PID 参数（调参时由 GUI 调用）"""
        ControlConfig.KP = kp
        ControlConfig.KI = ki
        ControlConfig.KD = kd
        
        # 将 PID 参数直接发送给下位机 (STM32)
        if self.serial_thread and self.serial_thread.serial_port and self.serial_thread.serial_port.is_open:
            cmd = f"{{{kp},{ki},{kd}}}\n"
            self.serial_thread.send_command(cmd)

        logger.info(f"[CONTROLLER] PID参数已更新并发送至下位机: Kp={kp:.2f}, Ki={ki:.3f}, Kd={kd:.2f}")

    def handle_target_position(self, target_x: int, target_y: int) -> None:
        """
        接收视觉线程的目标位置（原始像素坐标）

        视觉层只负责检测目标位置，误差计算和处理在此完成。

        Args:
            target_x: 目标在画面中的 X 坐标（像素）
            target_y: 目标在画面中的 Y 坐标（像素）
        """
        with self._motion_lock:
            if not self.visual_input_enabled:
                return

            # Hedefi ekran MERKEZINE degil, lazerin GERCEK vurus noktasina suruyoruz.
            # 误差要相对【激光实际落点】算，不是画面正中 ——
            # 相机装在激光上方，两者不同轴；用正中算的话激光永远打偏。
            aim_x, aim_y = VisionConfig_aim_point()
            raw_error_x = target_x - aim_x
            raw_error_y = target_y - aim_y

            # 将不同分辨率下的误差统一缩放到 640x480 空间。
            norm_x, norm_y = self._normalize_error(raw_error_x, raw_error_y)
            processed_x, processed_y = self.error_processor.process(norm_x, norm_y)

            # X/Y 与时间戳作为同一个视觉样本原子提交。
            self.current_error_x = processed_x
            self.current_error_y = processed_y
            self.last_vision_time = time.monotonic()


    # --------------------------------------------------
    # 核心控制循环
    # --------------------------------------------------

    def _run_control_loop(self) -> None:
        """
        运行在独立线程中的控制主循环。
        通过精确睡眠维持 60Hz 实时控制频率，与 60 FPS 视觉帧率严格同步。
        """
        while self.is_running:
            loop_hz = float(getattr(ControlConfig, "CONTROL_LOOP_HZ", 60.0))
            target_dt = 1.0 / max(10.0, loop_hz)
            start_time = time.perf_counter()
            
            # 执行单次计算和发送
            self.control_loop()
            
            # 精确时间补偿睡眠
            elapsed = time.perf_counter() - start_time
            sleep_time = target_dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def control_loop(self) -> None:
        """Run one fixed-rate automatic or mouse-control update."""
        try:
            with self._motion_lock:
                self._control_loop_locked()
        except Exception as exc:
            logger.error(f"[CONTROLLER ERROR] 控制循环异常: {exc}")
            import traceback
            traceback.print_exc()

    def _control_loop_locked(self) -> None:
        if not self.is_running:
            return

        # 优先响应手动连续点动/键盘操控
        if self._manual_jog_active:
            if not self._is_serial_connected():
                self._manual_jog_active = False
                self._warn_serial_disconnected()
                return
            axis = self._manual_jog_axis
            direction = self._manual_jog_dir
            # 根据速度档位缩放连续运动速度
            base_speed = 260 if axis == "x" else 180
            simulated_error = int(round(base_speed * direction * self.speed_multiplier))

            command = f"<{simulated_error},0,0>\n" if axis == "x" else f"<0,{simulated_error},0>\n"
            self.serial_thread.send_realtime_command(command)

            # 动态积分估算当前电机相对角度
            d_ang = (18.0 * self.speed_multiplier * 0.025) * direction
            if axis == "x":
                self.servo_x = max(-180.0, min(180.0, self.servo_x + d_ang))
            else:
                self.servo_y = max(-45.0, min(45.0, self.servo_y + d_ang))
            self.position_update_signal.emit(self.servo_x, self.servo_y)
            return

        if self.manual_mouse_enabled:
            self._manual_mouse_control_loop()
            return

        if not self.control_enabled or not self.visual_input_enabled:
            return

        if not self._is_serial_connected():
            self._warn_serial_disconnected()
            return

        time_since_last_vision = time.monotonic() - self.last_vision_time
        if time_since_last_vision > ControlConfig.VISION_WATCHDOG_TIMEOUT:
            if self.current_error_x != 0 or self.current_error_y != 0:
                self.stop_motion(
                    f"视觉信号丢失，停止控制 (超时: {time_since_last_vision:.2f}s)"
                )
            return

        err_x = self.current_error_x
        err_y = self.current_error_y

        if abs(err_x) < ControlConfig.DEADZONE:
            err_x = 0
        if abs(err_y) < ControlConfig.DEADZONE:
            err_y = 0

        # 反转设置 (视觉坐标系下: X轴默认不变，Y轴图像向下为正因而取反)
        if self.invert_x:
            err_x = -err_x
        if self.invert_y:
            err_y = -err_y

        # 应用 X/Y 轴独立追踪缩放（针对机械特性进行差分动态分配）
        scale_x = getattr(ControlConfig, "TRACKING_SCALE_X", 1.20)
        scale_y = getattr(ControlConfig, "TRACKING_SCALE_Y", 0.45)
        max_err_x = getattr(ControlConfig, "TRACKING_MAX_ERROR_X", 120)
        max_err_y = getattr(ControlConfig, "TRACKING_MAX_ERROR_Y", 50)

        # ----------------------------------------------------
        # 核心防过冲与边缘防飞车算法 (3-Zone Kinematic Servoing Profile)
        # 1. 准星核心区 (< settle_zone 像素): 渐进比例平滑减速，消除过冲与回摆
        # 2. 正常视野区 (settle_zone ~ edge_threshold 像素): 线性敏捷响应
        # 3. 屏幕最边缘区 (> edge_threshold 像素): 亚线性软饱和压缩，防止超大速度远距离冲过头
        # ----------------------------------------------------
        abs_x = abs(err_x)
        settle_zone_x = getattr(ControlConfig, "SETTLE_ZONE_X", 45)
        edge_thresh_x = getattr(ControlConfig, "EDGE_COMPRESS_THRESHOLD_X", 100)

        if 0 < abs_x < settle_zone_x:
            factor_x = 0.50 + 0.50 * (abs_x / float(settle_zone_x))
            err_x_computed = abs_x * scale_x * factor_x
        elif abs_x > edge_thresh_x:
            excess_x = abs_x - edge_thresh_x
            compressed_x = edge_thresh_x + (excess_x ** 0.55) * 1.2
            err_x_computed = compressed_x * scale_x
        else:
            err_x_computed = abs_x * scale_x

        abs_y = abs(err_y)
        settle_zone_y = getattr(ControlConfig, "SETTLE_ZONE_Y", 25)
        edge_thresh_y = getattr(ControlConfig, "EDGE_COMPRESS_THRESHOLD_Y", 100)

        if 0 < abs_y < settle_zone_y:
            factor_y = 0.50 + 0.50 * (abs_y / float(settle_zone_y))
            err_y_computed = abs_y * scale_y * factor_y
        elif abs_y > edge_thresh_y:
            excess_y = abs_y - edge_thresh_y
            compressed_y = edge_thresh_y + (excess_y ** 0.55) * 1.2
            err_y_computed = compressed_y * scale_y
        else:
            err_y_computed = abs_y * scale_y

        # 恢复符号并取整，同时叠加当前速度档位倍率
        err_x = round(math.copysign(err_x_computed * self.speed_multiplier, err_x)) if err_x != 0 else 0
        err_y = round(math.copysign(err_y_computed * self.speed_multiplier, err_y)) if err_y != 0 else 0

        # 幅值安全截断保护
        err_x = max(-max_err_x, min(max_err_x, err_x))
        err_y = max(-max_err_y, min(max_err_y, err_y))

        # 动态估算电机角度
        if err_x != 0 or err_y != 0:
            d_pan = -(err_x / 640.0) * (30.0 * self.speed_multiplier) * 0.025
            d_tilt = -(err_y / 480.0) * (20.0 * self.speed_multiplier) * 0.025
            self.servo_x = max(-180.0, min(180.0, self.servo_x + d_pan))
            self.servo_y = max(-45.0, min(45.0, self.servo_y + d_tilt))
            self.position_update_signal.emit(self.servo_x, self.servo_y)

        fire_val = 1 if (self.laser_armed and self.laser_firing) else 0
        self.serial_thread.send_realtime_command(f"<{err_x},{err_y},{fire_val}>\n")




    def _manual_mouse_control_loop(self) -> None:
        """Consume accumulated mouse movement at 40 Hz without queue buildup."""
        if not self.mouse_capture_active:
            return
        if not self._is_serial_connected():
            target = self.manual_aim.discard_pending()
            self.manual_target_update_signal.emit(*target)
            self.manual_motion_active = False
            self._warn_serial_disconnected()
            return

        gain = ControlConfig.MOUSE_ERROR_PER_DEGREE
        max_error = ControlConfig.MOUSE_MAX_ERROR
        yaw_delta, pitch_delta = self.manual_aim.consume_angle_delta(
            max_abs_delta=max_error / gain,
            min_abs_delta=1.0 / gain,
        )
        if abs(yaw_delta) < 1e-6 and abs(pitch_delta) < 1e-6:
            if self.manual_motion_active:
                self.serial_thread.send_stop_command()
                self.manual_motion_active = False
            return

        err_x = round(yaw_delta * gain)
        err_y = round(-pitch_delta * gain)
        err_x = max(-max_error, min(max_error, err_x))
        err_y = max(-max_error, min(max_error, err_y))

        if self.invert_x:
            err_x = -err_x
        if self.invert_y:
            err_y = -err_y

        fire_val = 1 if (self.laser_armed and self.laser_firing) else 0
        self.serial_thread.send_realtime_command(f"<{err_x},{err_y},{fire_val}>\n")
        self.manual_motion_active = True

    def _is_serial_connected(self) -> bool:
        return bool(self.serial_thread and self.serial_thread.is_connected())

    def _warn_serial_disconnected(self) -> None:
        now = time.monotonic()
        if now - self.last_warn_time > 2.0:
            logger.warning("[WARNING] Serial port not connected! Please click 'Connect'.")
            self.status_update_signal.emit("Warning: Serial port not connected")
            self.last_warn_time = now

    # --------------------------------------------------
    # 手动控制（测试模式与连续点动）
    # --------------------------------------------------

    def manual_move(self, axis: str, direction: int) -> None:
        """Send one single distinct jog step scaled by speed gear."""
        logger.info(f"[MANUAL] 手动点动微调: 轴={axis}, 方向={direction}, 档位=G{self.speed_gear} ({self.speed_multiplier:.1f}x)")
        if not self._is_serial_connected():
            self.status_update_signal.emit("⚠️ 警告: 串口未连接，无法控制电机")
            return
        if axis not in ("x", "y") or direction not in (-1, 1):
            logger.warning("[MANUAL] 忽略无效的手动移动参数")
            return

        base_error = 240 if axis == "x" else 160
        step_error = max(35, int(round(base_error * self.speed_multiplier)))
        simulated_error = step_error * direction

        command = (
            f"<{simulated_error},0,0>\n"
            if axis == "x"
            else f"<0,{simulated_error},0>\n"
        )
        self.serial_thread.send_realtime_command(command)
        stop_delay = 0.12 if axis == "x" else 0.10
        threading.Timer(stop_delay, self.serial_thread.send_stop_command).start()

        d_ang = (1.5 * self.speed_multiplier) * direction
        if axis == "x":
            self.servo_x = max(-180.0, min(180.0, self.servo_x + d_ang))
        else:
            self.servo_y = max(-45.0, min(45.0, self.servo_y + d_ang))
        self.position_update_signal.emit(self.servo_x, self.servo_y)
        self.status_update_signal.emit(f"手动点动 {axis.upper()} (方向 {direction:+d}, 档位 G{self.speed_gear})")

    def start_manual_continuous(self, axis: str, direction: int) -> None:
        """按住按钮或按下键盘方向键时：启动连续平滑运动"""
        if not self._is_serial_connected():
            self.status_update_signal.emit("⚠️ 警告: 串口未连接，无法控制电机")
            return
        if axis not in ("x", "y") or direction not in (-1, 1):
            return

        with self._motion_lock:
            self._manual_jog_axis = axis
            self._manual_jog_dir = direction
            self._manual_jog_active = True

        self.status_update_signal.emit(f"连续移动中: {axis.upper()} (方向 {direction:+d})")

    def stop_manual_continuous(self) -> None:
        """松开按钮或松开键盘时：立即刹车停止"""
        with self._motion_lock:
            if not self._manual_jog_active:
                return
            self._manual_jog_active = False
            self._manual_jog_axis = 'x'
            self._manual_jog_dir = 0
            if self.serial_thread:
                self.serial_thread.send_stop_command()
        self.status_update_signal.emit("移动已停止")



    def sync_position(self) -> bool:
        """Stop both motors and treat the current pose as the relative origin."""
        if not self._is_serial_connected():
            self.status_update_signal.emit("⚠️ 串口未连接，无法重置控制状态")
            return False

        with self._motion_lock:
            self.current_error_x = 0
            self.current_error_y = 0
            self.error_processor.reset()
            self.manual_motion_active = False
            self.serial_thread.send_center_command()
            self.servo_x = 0.0
            self.servo_y = 0.0
            target = self.manual_aim.reset_target()

        self.manual_target_update_signal.emit(*target)
        self.position_update_signal.emit(self.servo_x, self.servo_y)
        self.status_update_signal.emit("电机已停止，当前位置已设为相对原点")
        return True

    def _normalize_error(self, err_x: int, err_y: int) -> tuple[int, int]:
        """Normalize X and Y independently to the 640x480 reference frame."""
        from config.vision_config import VisionConfig

        actual_w = VisionConfig.FRAME_WIDTH
        actual_h = VisionConfig.FRAME_HEIGHT
        if actual_w <= 0 or actual_h <= 0:
            return err_x, err_y

        scale_x = 640.0 / actual_w
        scale_y = 480.0 / actual_h
        return int(err_x * scale_x), int(err_y * scale_y)

# --------------------------------------------------
# 辅助函数（避免循环导入，延迟读取 VisionConfig）
# --------------------------------------------------

def VisionConfig_aim_point():
    """Lazerin gercek vurus noktasi (boresight kalibrasyonu uygulanmis).
       激光实际落点（已应用光轴校准）。"""
    from config.vision_config import VisionConfig
    return VisionConfig.aim_point(VisionConfig.AKTIF_MESAFE_M)


def VisionConfig_center_x() -> int:
    """懒加载 VisionConfig.CENTER_X"""
    from config.vision_config import VisionConfig
    return VisionConfig.CENTER_X


def VisionConfig_center_y() -> int:
    """懒加载 VisionConfig.CENTER_Y"""
    from config.vision_config import VisionConfig
    return VisionConfig.CENTER_Y
