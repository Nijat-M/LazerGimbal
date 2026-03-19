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
from typing import Tuple
from PyQt6.QtCore import QObject, pyqtSignal

from config import cfg
from config.control_config import ControlConfig
from core.control.error_processor import ErrorProcessor
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
        self.last_vision_time: float = time.time()

        # [控制开关]
        self.control_enabled: bool = False

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
        """停止控制线程，通常在退出应用时调用"""
        self.is_running = False
        if self.control_thread.is_alive():
            self.control_thread.join(timeout=1.0)

    # --------------------------------------------------
    # 公共接口（GUI 调用）
    # --------------------------------------------------

    def set_control_enabled(self, enabled: bool) -> None:
        """启用/禁用 PID 自动控制"""
        self.control_enabled = enabled
        status = "控制已启动" if enabled else "控制已停止"
        self.status_update_signal.emit(status)
        logger.info(f"[CONTROLLER] {status}")

    def set_invert(self, invert_x: bool, invert_y: bool) -> None:
        """设置轴向反转"""
        self.invert_x = invert_x
        self.invert_y = invert_y
        ControlConfig.INVERT_X = invert_x
        ControlConfig.INVERT_Y = invert_y

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
        self.last_vision_time = time.time()

    def handle_vision_error(self, err_x: int, err_y: int) -> None:
        """
        接收视觉线程的误差信号（兼容旧接口）

        此接口保留用于 TRACKING 模式（激光追蓝色目标），
        该模式下 worker 直接计算两点间误差，无需再做原始坐标转换。

        Args:
            err_x: X 轴误差（像素）
            err_y: Y 轴误差（像素）
        """
        self.last_vision_time = time.time()

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
        """
        [核心] PID 控制单次计算与指令下发


        所有参数均从 ControlConfig 读取，无硬编码数字。
        """
        try:
            # 1. 检查控制开关
            if not self.control_enabled:
                return

            # 2. 检查串口连接
            if not self.serial_thread.serial_port or \
               not self.serial_thread.serial_port.is_open:
                now = time.time()
                if now - self.last_warn_time > 2.0:
                    logger.warning("[WARNING] 串口未连接！请先点击'连接'按钮。")
                    self.status_update_signal.emit("警告: 串口未连接")
                    self.last_warn_time = now
                return

            # 3. [安全看门狗] 超时停止控制，防止失控
            time_since_last_vision = time.time() - self.last_vision_time
            if time_since_last_vision > ControlConfig.VISION_WATCHDOG_TIMEOUT:
                if self.current_error_x != 0 or self.current_error_y != 0:
                    logger.warning(f"视觉信号丢失，停止控制 (超时: {time_since_last_vision:.2f}s)")
                    self.current_error_x = 0
                    self.current_error_y = 0
                    # 发送停止指令
                    if self.serial_thread and self.serial_thread.serial_port and self.serial_thread.serial_port.is_open:
                        self.serial_thread.send_command("<0,0,0>\n")
                return

            # 4. 获取当前误差
            err_x = self.current_error_x
            err_y = self.current_error_y

            # 5. [PID 上位机死区拦截] 死区可由用户界面调整，默认为 5 px 左右
            # 将X和Y轴的死区判断【独立分开】，防止Y轴运动时带动原本已经停稳的X轴震荡！
            if abs(err_x) < ControlConfig.DEADZONE:
                err_x = 0
            
            if abs(err_y) < ControlConfig.DEADZONE:
                err_y = 0

            # 6. 处理轴向反转
            if self.invert_x:
                err_x = -err_x
            if self.invert_y:
                err_y = -err_y

            # 7. 打包成指令发送
            # 协议格式：<Error_X, Error_Y, 0>
            # 第三个参数 0 预留给未来的前馈速度 Vel_X (Phase 3)
            cmd = f"<{err_x},{err_y},0>\n"
            self.serial_thread.send_command(cmd)

        except Exception as e:
            logger.error(f"[CONTROLLER ERROR] 控制循环异常: {e}")
            import traceback
            traceback.print_exc()

    # --------------------------------------------------
    # 手动控制（测试模式）
    # --------------------------------------------------

    def manual_move(self, axis: str, direction: int) -> None:
        """
        手动移动舵机（测试模式）

        Args:
            axis: 'x' 或 'y'
            direction: 1（正向）或 -1（反向）
        """
        logger.info(f"[MANUAL] 手动移动请求: 轴={axis}, 方向={direction}")

        if not self.serial_thread.serial_port or \
           not self.serial_thread.serial_port.is_open:
            logger.warning("[WARNING] 串口未连接，无法手动移动")
            self.status_update_signal.emit("⚠️ 警告: 串口未连接")
            return

        degree_step = cfg.MANUAL_STEP * direction

        # 应用反转设置
        if axis == 'x' and self.invert_x:
            degree_step = -degree_step
            logger.info("[MANUAL] X轴已反转（INVERT_X=True）")
        elif axis == 'y' and self.invert_y:
            degree_step = -degree_step
            logger.info("[MANUAL] Y轴已反转（INVERT_Y=True）")

        # 角度 → PWM 脉冲
        pulse_step = int(degree_step * cfg.DEGREE_TO_PULSE)
        logger.info(f"[MANUAL] 角度步长: {degree_step}°, PWM脉冲步长: {pulse_step}")

        if axis == 'x':
            next_pos = self.servo_x + degree_step
            if ControlConfig.SERVO_MIN_LIMIT <= next_pos <= ControlConfig.SERVO_MAX_LIMIT:
                self.servo_x = next_pos
                cmd = f"x{'+' if pulse_step >= 0 else ''}{pulse_step}"
                logger.info(f"[MANUAL] 发送 X 轴命令: {cmd} (新位置={self.servo_x:.1f}°)")
                self.serial_thread.send_command(f"{cmd}\n")
                self.position_update_signal.emit(self.servo_x, self.servo_y)
                self.status_update_signal.emit(f"手动移动 X: {self.servo_x:.1f}°")
            else:
                logger.warning(f"[LIMIT] X轴已到达限位: {next_pos:.1f}°")
                self.status_update_signal.emit(f"⚠️ X轴限位: {next_pos:.1f}°")

        elif axis == 'y':
            next_pos = self.servo_y + degree_step
            if ControlConfig.SERVO_MIN_LIMIT <= next_pos <= ControlConfig.SERVO_MAX_LIMIT:
                self.servo_y = next_pos
                cmd = f"y{'+' if pulse_step >= 0 else ''}{pulse_step}"
                logger.info(f"[MANUAL] 发送 Y 轴命令: {cmd} (新位置={self.servo_y:.1f}°)")
                self.serial_thread.send_command(f"{cmd}\n")
                self.position_update_signal.emit(self.servo_x, self.servo_y)
                self.status_update_signal.emit(f"手动移动 Y: {self.servo_y:.1f}°")
            else:
                logger.warning(f"[LIMIT] Y轴已到达限位: {next_pos:.1f}°")
                self.status_update_signal.emit(f"⚠️ Y轴限位: {next_pos:.1f}°")

    def sync_position(self) -> None:
        """
        重置软件坐标估算为中位（90度）

        用于校准或在失步后重新同步。
        """
        self.servo_x = float(ControlConfig.SERVO_CENTER)
        self.servo_y = float(ControlConfig.SERVO_CENTER)
        self.error_processor.reset()
        self.position_update_signal.emit(self.servo_x, self.servo_y)
        self.status_update_signal.emit("位置已重置为中位 (90, 90)")
    def _normalize_error(self, err_x: int, err_y: int) -> Tuple[int, int]:
        """将不同分辨率下的误差像素归一化到 640 宽度的基准空间"""
        from config.vision_config import VisionConfig
        actual_w = VisionConfig.FRAME_WIDTH
        if actual_w <= 0:
            return err_x, err_y
        
        # 计算缩放比 (例如 1920 -> 640, scale = 0.333)
        # 确保 10% 屏宽的误差在任何分辨率下都对应相同的数值
        scale = 640.0 / actual_w
        return int(err_x * scale), int(err_y * scale)

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
