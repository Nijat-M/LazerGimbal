# -*- coding: utf-8 -*-
"""
云台控制器核心模块 (Gimbal Controller Core)

[职责 Responsibility]
1. PID控制循环（固定频率 40Hz）
2. 舵机位置状态管理（软件坐标估算）
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

    def __init__(self, serial_thread):
        """
        初始化控制器

        Args:
            serial_thread: 串口通信线程实例
        """
        super().__init__()

        self.serial_thread = serial_thread

        # [舵机位置状态] 软件坐标估算（假设初始中位90度）
        self.servo_x: float = 90.0
        self.servo_y: float = 90.0

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

        # [控制循环线程] 40Hz (25ms) 替代 QTimer
        self.is_running = True
        self.control_thread = threading.Thread(target=self._run_control_loop, daemon=True)
        self.control_thread.start()

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
                self.status_update_signal.emit("鼠标模式下不能启动自动控制")
                return False
            if enabled and not self.visual_input_enabled:
                self.status_update_signal.emit("摄像头尚未就绪，不能启动自动控制")
                return False

            self.control_enabled = enabled
            if not enabled:
                self.stop_motion()
        status = "控制已启动" if enabled else "控制已停止"
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
            self.status_update_signal.emit("鼠标瞄准就绪：点击实时画面开始")

    def set_mouse_capture_active(self, active: bool) -> None:
        """Arm mouse motion only while the video widget owns the cursor."""
        with self._motion_lock:
            active = active and self.manual_mouse_enabled
            if self.mouse_capture_active == active:
                return
            self.mouse_capture_active = active
            if not active:
                self.stop_motion()
        status = "鼠标已捕获，Esc 停止" if active else "鼠标已释放，运动已停止"
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
        if not self.visual_input_enabled:
            return

        # 计算相对于画面中心的原始误差
        raw_error_x = target_x - VisionConfig_center_x()
        raw_error_y = target_y - VisionConfig_center_y()

        # [分辨率归一化] 核心改进：
        # 将不同分辨率下的误差（像素）统一缩放到 640x480 空间。
        # 这样 PID 参数和 SPEED_LEVELS 就不需要根据分辨率重新调整。
        norm_x, norm_y = self._normalize_error(raw_error_x, raw_error_y)

        # 通过 ErrorProcessor 缩放 + 滤波
        processed_x, processed_y = self.error_processor.process(norm_x, norm_y)

        self.current_error_x = processed_x
        self.current_error_y = processed_y
        self.last_vision_time = time.monotonic()

    def handle_vision_error(self, err_x: int, err_y: int) -> None:
        """
        接收视觉线程的误差信号（兼容旧接口）

        此接口保留用于 TRACKING 模式（激光追蓝色目标），
        该模式下 worker 直接计算两点间误差，无需再做原始坐标转换。

        Args:
            err_x: X 轴误差（像素）
            err_y: Y 轴误差（像素）
        """
        if not self.visual_input_enabled:
            return
        self.last_vision_time = time.monotonic()

        # [分辨率归一化]
        norm_x, norm_y = self._normalize_error(err_x, err_y)

        # 通过 ErrorProcessor 缩放 + 滤波
        processed_x, processed_y = self.error_processor.process(norm_x, norm_y)

        self.current_error_x = processed_x
        self.current_error_y = processed_y

    # --------------------------------------------------
    # 核心控制循环
    # --------------------------------------------------

    def _run_control_loop(self) -> None:
        """
        运行在独立线程中的控制主循环。
        通过精确睡眠维持指定的控制频率（如40Hz），彻底与 GUI 事件循环解耦。
        """
        target_dt = 1.0 / 40.0  # 40Hz -> 0.025s
        
        while self.is_running:
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

        if self.invert_x:
            err_x = -err_x
        if self.invert_y:
            err_y = -err_y

        self.serial_thread.send_realtime_command(f"<{err_x},{err_y},0>\n")

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

        self.serial_thread.send_realtime_command(f"<{err_x},{err_y},0>\n")
        self.manual_motion_active = True

    def _is_serial_connected(self) -> bool:
        return bool(self.serial_thread and self.serial_thread.is_connected())

    def _warn_serial_disconnected(self) -> None:
        now = time.monotonic()
        if now - self.last_warn_time > 2.0:
            logger.warning("[WARNING] 串口未连接！请先点击'连接'按钮。")
            self.status_update_signal.emit("警告: 串口未连接")
            self.last_warn_time = now

    # --------------------------------------------------
    # 手动控制（测试模式）
    # --------------------------------------------------

    def manual_move(self, axis: str, direction: int) -> None:
        """Send one short, bounded movement for the legacy button test panel."""
        logger.info(f"[MANUAL] 手动移动请求: 轴={axis}, 方向={direction}")
        if not self._is_serial_connected():
            self.status_update_signal.emit("⚠️ 警告: 串口未连接")
            return
        if axis not in ("x", "y") or direction not in (-1, 1):
            logger.warning("[MANUAL] 忽略无效的手动移动参数")
            return

        degree_step = cfg.MANUAL_STEP * direction
        if axis == "x" and self.invert_x:
            degree_step = -degree_step
        elif axis == "y" and self.invert_y:
            degree_step = -degree_step

        simulated_error = -70 if degree_step > 0 else 70
        command = (
            f"<{simulated_error},0,0>\n"
            if axis == "x"
            else f"<0,{simulated_error},0>\n"
        )
        self.serial_thread.send_realtime_command(command)
        threading.Timer(0.05, self.serial_thread.send_stop_command).start()
        self.status_update_signal.emit(f"手动移动 {axis.upper()}")

    def sync_position(self) -> bool:
        """Physically center the legacy servos and reset the virtual aim origin."""
        if not self._is_serial_connected():
            self.status_update_signal.emit("⚠️ 串口未连接，无法执行归中")
            return False

        with self._motion_lock:
            self.current_error_x = 0
            self.current_error_y = 0
            self.error_processor.reset()
            self.manual_motion_active = False
            self.serial_thread.send_center_command()
            self.servo_x = float(ControlConfig.SERVO_CENTER)
            self.servo_y = float(ControlConfig.SERVO_CENTER)
            target = self.manual_aim.reset_target()

        self.manual_target_update_signal.emit(*target)
        self.position_update_signal.emit(self.servo_x, self.servo_y)
        self.status_update_signal.emit("云台已发送归中命令 (90, 90)")
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

def VisionConfig_center_x() -> int:
    """懒加载 VisionConfig.CENTER_X"""
    from config.vision_config import VisionConfig
    return VisionConfig.CENTER_X


def VisionConfig_center_y() -> int:
    """懒加载 VisionConfig.CENTER_Y"""
    from config.vision_config import VisionConfig
    return VisionConfig.CENTER_Y
