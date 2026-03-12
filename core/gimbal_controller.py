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
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from config import cfg
from config.control_config import ControlConfig
from core.pid import PIDController
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

        # [PID 控制器] 参数从 ControlConfig 读取
        self.pid_x = PIDController(ControlConfig.KP, ControlConfig.KI,
                                   ControlConfig.KD, ControlConfig.SPEED_LEVELS[0]['max_step'])
        self.pid_y = PIDController(ControlConfig.KP, ControlConfig.KI,
                                   ControlConfig.KD, ControlConfig.SPEED_LEVELS[0]['max_step'])

        # [控制开关]
        self.control_enabled: bool = False

        # [反转设置] 从 ControlConfig 读取默认值
        self.invert_x: bool = ControlConfig.INVERT_X
        self.invert_y: bool = ControlConfig.INVERT_Y

        # [控制循环定时器] 40Hz (25ms)
        self.control_timer = QTimer()
        self.control_timer.timeout.connect(self.control_loop)
        self.control_timer.start(25)

        # 警告时间戳（防止刷屏）
        self.last_warn_time: float = 0.0

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
        self.pid_x.set_tunings(kp, ki, kd)
        self.pid_y.set_tunings(kp, ki, kd)
        ControlConfig.KP = kp
        ControlConfig.KI = ki
        ControlConfig.KD = kd
        logger.info(f"[CONTROLLER] PID参数已更新: Kp={kp:.2f}, Ki={ki:.3f}, Kd={kd:.2f}")

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

    def control_loop(self) -> None:
        """
        [核心] PID 控制循环（40Hz 固定频率）

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
            if time.time() - self.last_vision_time > ControlConfig.VISION_WATCHDOG_TIMEOUT:
                if self.current_error_x != 0 or self.current_error_y != 0:
                    logger.warning("视觉信号丢失，停止控制",
                                   timeout=ControlConfig.VISION_WATCHDOG_TIMEOUT)
                    self.current_error_x = 0
                    self.current_error_y = 0
                return

            # 4. 获取当前误差
            err_x = self.current_error_x
            err_y = self.current_error_y

            # 5. [自适应死区] 从 ControlConfig 统一读取，无硬编码
            error_magnitude = ErrorProcessor.get_magnitude(err_x, err_y)
            deadzone = ControlConfig.get_deadzone_for_error(error_magnitude)

            if abs(err_x) < deadzone and abs(err_y) < deadzone:
                return  # 在死区内，不发送指令

            # 6. [轴向反转]
            if self.invert_x:
                err_x = -err_x
            if self.invert_y:
                err_y = -err_y

            # 7. [自适应速度] 从 ControlConfig 统一读取，无硬编码
            max_step = ControlConfig.get_speed_for_error(error_magnitude)
            self.pid_x.max_step = max_step
            self.pid_y.max_step = max_step

            # 8. [PID 计算]
            delta_x = self.pid_x.update(err_x)
            delta_y = self.pid_y.update(err_y)

            if delta_x == 0 and delta_y == 0:
                return

            # 9. [软件坐标更新与限位]
            scale = ControlConfig.SERVO_STEP_TO_DEGREE
            next_x = self.servo_x + delta_x * scale
            next_y = self.servo_y + delta_y * scale

            # 软件限位
            if next_x > ControlConfig.SERVO_MAX_LIMIT:
                next_x = ControlConfig.SERVO_MAX_LIMIT
                delta_x = 0
            elif next_x < ControlConfig.SERVO_MIN_LIMIT:
                next_x = ControlConfig.SERVO_MIN_LIMIT
                delta_x = 0

            if next_y > ControlConfig.SERVO_MAX_LIMIT:
                next_y = ControlConfig.SERVO_MAX_LIMIT
                delta_y = 0
            elif next_y < ControlConfig.SERVO_MIN_LIMIT:
                next_y = ControlConfig.SERVO_MIN_LIMIT
                delta_y = 0

            # 10. [发送串口指令]
            if abs(delta_x) > 0:
                self.servo_x = next_x
                cmd_x = f"x{'+' if delta_x >= 0 else ''}{delta_x}"
                self.serial_thread.send_command(f"{cmd_x}\n")

            if abs(delta_y) > 0:
                self.servo_y = next_y
                cmd_y = f"y{'+' if delta_y >= 0 else ''}{delta_y}"
                self.serial_thread.send_command(f"{cmd_y}\n")

            # 11. [更新 GUI 显示]
            self.position_update_signal.emit(self.servo_x, self.servo_y)

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
        self.pid_x.reset()
        self.pid_y.reset()
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
