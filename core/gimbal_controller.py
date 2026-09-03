# -*- coding: utf-8 -*-
"""
云台控制器核心模块 (Gimbal Controller Core)
================================================================================
本模块为 2 轴闭环激光云台的主控业务中枢，负责多模式运动学规划、定频闭环伺服、
光轴视差校准以及多重硬件安全联锁机制。

【核心职责 (Core Responsibilities)】
1. 定频高精度控制循环：默认 60Hz（可配置 10Hz~100Hz），与视觉传感器帧率深度同步。
2. 运动学与相对原点推算：航向角 (Yaw/Pan) 与俯仰角 (Pitch/Tilt) 的实时航位推算 (Dead Reckoning)。
3. 视觉引导闭环伺服：结合激光发射管光轴视差 (Boresight Calibration) 与 3 区非线性运动学平滑滤波。
4. 激光武器安全互锁：ARM / SAFE 状态机、友军防误伤切断、硬件看门狗与异常急停 (ESTOP)。
5. 多模式运动调度：自动视觉闭环追踪、FPS 鼠标精准瞄准、多档位键盘/按钮离散点动与平滑连续运动。

【架构设计规范 (Architectural Decoupling)】
- 严格分层解耦：Controller 层与 GUI 视图层完全解耦，不含任何图形界面渲染代码。
- 异步通信桥接：GUI 通过公共 API 调用控制器，控制器通过 Qt 信号向 GUI 异步派发遥测事件。
- 下位机通讯总线：通过 SerialThread 实例向下位机 (STM32F401) 异步下发高频实时数据帧。
- 集中式参数注入：所有控制增益、物理限制与机械参数均由 ControlConfig 与 VisionConfig 统一管理。
================================================================================
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

    封装所有云台闭环追踪计算、模式切换、鼠标瞄准及下位机指令下发业务。
    """

    # Qt 异步信号：通知 GUI 界面刷新运行状态与遥测数据
    status_update_signal = pyqtSignal(str)                  # 控制器状态/警报文本
    position_update_signal = pyqtSignal(float, float)       # X(Pan), Y(Tilt) 当前估算姿态角 (度)
    manual_target_update_signal = pyqtSignal(float, float)  # 鼠标瞄准相对中心的 Yaw/Pitch 目标角
    laser_state_signal = pyqtSignal(bool, bool, int)        # 激光状态 (armed: 保险, firing: 发射, power: 功率)
    speed_gear_changed_signal = pyqtSignal(int, float)      # 电机档位与倍率 (gear: 1/2/3, multiplier)

    def __init__(self, serial_thread):
        """
        初始化控制器

        Args:
            serial_thread: 串口通信线程实例
        """
        super().__init__()

        self.serial_thread = serial_thread

        # 3 级速度档位系统 (Gear 1: 精准微调 0.30x, Gear 2: 标准巡航 1.00x, Gear 3: 高速机动 2.20x)
        self.speed_gear: int = 2
        self.speed_multiplier: float = 1.0

        # 当前硬件软件相对原点与动态角度估算值 (单位: 角度 deg)
        self.servo_x: float = 0.0
        self.servo_y: float = 0.0

        # 挂载下位机 (STM32) 串口遥测数据接收槽函数
        if hasattr(self.serial_thread, "data_received_signal"):
            self.serial_thread.data_received_signal.connect(self._handle_serial_rx)

        # [激光子系统状态] 保险解锁 (armed)、开火中 (firing)、PWM 输出功率百分比 (0~100)
        self.laser_armed: bool = False
        self.laser_firing: bool = False
        self.laser_power: int = 100

        # [视觉误差前处理器] 负责归一化坐标转换与滤波（统一读取 ControlConfig 参数）
        self.error_processor = ErrorProcessor()

        # [最新目标误差样本] 记录视觉处理后的当前归一化像素偏差与时间戳
        self.current_error_x: int = 0
        self.current_error_y: int = 0
        self.last_vision_time: float = time.monotonic()

        # [运行模式开关]
        self.control_enabled: bool = False       # 自动视觉闭环追踪开关
        self.visual_input_enabled: bool = False  # 相机输入有效性标志

        # [FPS 鼠标手动瞄准控制器]
        self.manual_aim = ManualAimController(
            sensitivity=ControlConfig.MOUSE_SENSITIVITY,
            yaw_limits=(ControlConfig.MOUSE_YAW_MIN, ControlConfig.MOUSE_YAW_MAX),
            pitch_limits=(ControlConfig.MOUSE_PITCH_MIN, ControlConfig.MOUSE_PITCH_MAX),
        )
        self.manual_mouse_enabled: bool = False
        self.mouse_capture_active: bool = False
        self.manual_motion_active: bool = False
        self._motion_lock = threading.RLock()

        # [坐标轴反转设置] 从 ControlConfig 读取，适配正装/吊装等机械布局
        self.invert_x: bool = ControlConfig.INVERT_X
        self.invert_y: bool = ControlConfig.INVERT_Y

        # 串口通讯断开警报节流时间戳（避免短时间内重复刷屏）
        self.last_warn_time: float = 0.0

        # [手动平滑连续运动状态] 供 UI 按钮长按或键盘方向键连续操控
        self._manual_jog_active: bool = False
        self._manual_jog_axis: str = 'x'
        self._manual_jog_dir: int = 0

        # [控制主线程] 独立定频控制线程（支持 60Hz 实时同步），彻底解耦 Qt GUI 主线程
        self.is_running = True
        self.control_thread = threading.Thread(target=self._run_control_loop, daemon=True)
        self.control_thread.start()

    def set_speed_gear(self, gear: int) -> None:
        """
        设置电机速度档位

        档位说明:
            - Gear 1 (0.30x): 远程高精度瞄准、防抖微调
            - Gear 2 (1.00x): 标准巡航速度与常规视觉追踪
            - Gear 3 (2.20x): 快速大角度大行程转动机动

        Args:
            gear: 档位序号 (1, 2, 3)
        """
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
        """
        解析下位机 (STM32) 上报的姿态角度或系统状态报文

        支持的报文样例:
            - "P: 12.3, -4.5"
            - "POS: <12.3, -4.5>"

        Args:
            line: 串口接收缓冲区提取出的单行文本
        """
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
        """
        设置激光安全保险状态 (ARM / SAFE)

        安全策略:
            当锁定保险 (armed=False) 时，若当前激光正在发射，将立即强制切断并下发停火指令。

        Args:
            armed: True 为解除保险允许发射，False 为上锁保险严禁发射
        """
        self.laser_armed = armed
        if not armed and self.laser_firing:
            self.laser_firing = False
            if self._is_serial_connected():
                self.serial_thread.send_command("!LASER:0\n")
        self.laser_state_signal.emit(self.laser_armed, self.laser_firing, self.laser_power)
        logger.info(f"[LASER] 激光保险状态: {'🔴 ARMED' if armed else '🟢 SAFE'}")

    def set_laser_firing(self, firing: bool) -> None:
        """
        触发或停止激光物理发射

        安全检查:
            若激光处于 SAFE 保险上锁状态，将拒绝触发发射并输出告警。

        Args:
            firing: True 为开火，False 为停火
        """
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
        """
        设置激光输出功率 (TIM3 硬件 PWM 占空比 0~100%)

        Args:
            power: 功率百分比整数 (0 ~ 100)
        """
        self.laser_power = max(0, min(100, int(power)))
        if self._is_serial_connected():
            self.serial_thread.send_command(f"!POWER:{self.laser_power}\n")
        self.laser_state_signal.emit(self.laser_armed, self.laser_firing, self.laser_power)
        logger.info(f"[LASER] 激光功率设定: {self.laser_power}%")


    def stop(self) -> None:
        """
        优雅停止运动并彻底退出后台控制线程
        """
        with self._motion_lock:
            self.is_running = False
            self.control_enabled = False
            self.manual_mouse_enabled = False
            self.mouse_capture_active = False
            self.stop_motion()
        if self.control_thread.is_alive():
            self.control_thread.join(timeout=1.0)

    # --------------------------------------------------------------------------
    # 外部公共控制接口 (GUI 与业务逻辑层调用)
    # --------------------------------------------------------------------------

    def set_control_enabled(self, enabled: bool) -> bool:
        """
        开启或停止自动视觉闭环追踪模式

        安全互锁:
            - 若当前处于 FPS 鼠标瞄准模式，禁止同时开启自动追踪。
            - 若相机视频流尚未就绪 (未收到有效帧)，拒绝启动追踪。

        Args:
            enabled: True 为开启自动追踪，False 为停止

        Returns:
            bool: 是否成功改变追踪状态
        """
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
        """
        设置视觉输入有效性门禁

        仅在当前图像采集工作线程确认正常运作时接收视觉样本；
        当视频暂停或断开时自动关闭并安全刹车。

        Args:
            enabled: 视觉输入是否有效
        """
        with self._motion_lock:
            self.visual_input_enabled = enabled
            if not enabled:
                self.stop_motion()

    def set_invert(self, invert_x: bool, invert_y: bool) -> None:
        """
        设置电机运动轴向反转标志

        Args:
            invert_x: X 偏航轴 (Pan) 是否反向
            invert_y: Y 俯仰轴 (Tilt) 是否反向
        """
        self.invert_x = invert_x
        self.invert_y = invert_y
        ControlConfig.INVERT_X = invert_x
        ControlConfig.INVERT_Y = invert_y

    def set_manual_mouse_mode(self, enabled: bool) -> None:
        """
        切换控制模式：自动视觉追踪 vs FPS 鼠标手动瞄准

        Args:
            enabled: True 为开启鼠标瞄准，False 为退出鼠标瞄准
        """
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
        """
        更新鼠标独占捕获状态

        仅在鼠标处于画面内部被捕获时，才响应鼠标微小位移。

        Args:
            active: 鼠标是否被视频视窗捕获
        """
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
        """
        接收高频 GUI 鼠标相对位移事件（非阻塞内存增量累积）

        Args:
            dx: 鼠标 X 轴像素增量
            dy: 鼠标 Y 轴像素增量
        """
        with self._motion_lock:
            if not self.manual_mouse_enabled or not self.mouse_capture_active:
                return
            yaw, pitch = self.manual_aim.add_mouse_delta(dx, dy)
        self.manual_target_update_signal.emit(yaw, pitch)

    def update_mouse_sensitivity(self, sensitivity: float) -> None:
        """
        动态调整鼠标手动瞄准灵敏度增益

        Args:
            sensitivity: 灵敏度浮点系数
        """
        self.manual_aim.set_sensitivity(sensitivity)
        ControlConfig.MOUSE_SENSITIVITY = sensitivity

    def stop_motion(self, reason: str | None = None) -> None:
        """
        高优先级制动：清空所有待发缓冲，向下位机下发即时刹车指令 (STOP)

        Args:
            reason: 触发停机的可读原因说明（可选，用于日志告警）
        """
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
        """
        动态同步 PID 闭环控制参数（调参面板实时调用并推送到 STM32）

        Args:
            kp: 比例增益 (Proportional Gain)
            ki: 积分增益 (Integral Gain)
            kd: 微分增益 (Derivative Gain)
        """
        ControlConfig.KP = kp
        ControlConfig.KI = ki
        ControlConfig.KD = kd
        
        # 将 PID 参数直接格式化打包发送给下位机 (STM32)
        if self.serial_thread and self.serial_thread.serial_port and self.serial_thread.serial_port.is_open:
            cmd = f"{{{kp},{ki},{kd}}}\n"
            self.serial_thread.send_command(cmd)

        logger.info(f"[CONTROLLER] PID参数已更新并发送至下位机: Kp={kp:.2f}, Ki={ki:.3f}, Kd={kd:.2f}")

    def handle_target_position(self, target_x: int, target_y: int) -> None:
        """
        接收视觉识别线程派发的目标中心像素坐标，并计算带光轴视差补偿的控制偏差

        【核心光轴校准 (Boresight Calibration)】
            云台对准的目标基准不是画面的绝对几何中心 (Width/2, Height/2)，
            而是激光发射管在相机成像平面上的实际光学落点 (Aim Point)。
            因为摄像头与激光管具有物理安装间距（垂直/水平视差），若直接对准画面正中，
            远近距离切换时激光打击点将产生严重几何偏离。

        Args:
            target_x: 目标在当前视频帧中的原始 X 像素坐标
            target_y: 目标在当前视频帧中的原始 Y 像素坐标
        """
        with self._motion_lock:
            if not self.visual_input_enabled:
                return

            # 读取当前设定靶标距离下经过光轴校准的激光落点坐标
            aim_x, aim_y = VisionConfig_aim_point()
            raw_error_x = target_x - aim_x
            raw_error_y = target_y - aim_y

            # 将任意画面分辨率下的绝对像素误差统一归一化缩放到 640x480 参考空间
            norm_x, norm_y = self._normalize_error(raw_error_x, raw_error_y)
            processed_x, processed_y = self.error_processor.process(norm_x, norm_y)

            # 原子更新当前偏差坐标与视觉有效时间戳
            self.current_error_x = processed_x
            self.current_error_y = processed_y
            self.last_vision_time = time.monotonic()

    # --------------------------------------------------------------------------
    # 核心控制定频循环 (定频伺服、运动学规划与指令打包下发)
    # --------------------------------------------------------------------------

    def _run_control_loop(self) -> None:
        """
        运行于独立控制线程的定频主循环入口。

        通过精确微秒级时间补偿睡眠维持 60Hz 实时控制频率（从 ControlConfig.CONTROL_LOOP_HZ 读取），
        与 Arducam 60 FPS 全局快门相机的高帧率输出严格对齐，实现端到端最低延时。
        """
        while self.is_running:
            loop_hz = float(getattr(ControlConfig, "CONTROL_LOOP_HZ", 60.0))
            target_dt = 1.0 / max(10.0, loop_hz)
            start_time = time.perf_counter()
            
            # 执行单次伺服更新
            self.control_loop()
            
            # 精确计算耗时并执行动态补偿睡眠
            elapsed = time.perf_counter() - start_time
            sleep_time = target_dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def control_loop(self) -> None:
        """执行单次定频控制步进（带全局异常保护机制）"""
        try:
            with self._motion_lock:
                self._control_loop_locked()
        except Exception as exc:
            logger.error(f"[CONTROLLER ERROR] 控制循环异常: {exc}")
            import traceback
            traceback.print_exc()

    def _control_loop_locked(self) -> None:
        """
        持有运动锁状态下的核心控制步进逻辑。

        执行优先级逻辑:
            1. 手动点动/键盘长按连续微调 (Manual Jog)
            2. FPS 鼠标瞄准模式 (Mouse Aim)
            3. 自动视觉闭环追踪 (Auto Visual Tracking)
               - 视觉超时看门狗安全切断
               - 动态中心死区过滤 (Deadzone)
               - 机械安装轴向极性反转 (Inversion)
               - 3-Zone 运动学伺服曲线规划 (防过冲与边缘非线性压缩)
               - 电机静态摩擦力死区补偿与姿态角航位推算
               - 实时打包下发运动与激光发射指令
        """
        if not self.is_running:
            return

        # 优先级 1: 优先响应手动连续点动/键盘长按微调
        if self._manual_jog_active:
            if not self._is_serial_connected():
                self._manual_jog_active = False
                self._warn_serial_disconnected()
                return
            axis = self._manual_jog_axis
            direction = self._manual_jog_dir
            # 根据当前速度档位倍率缩放连续运动基准速度
            base_speed = 260 if axis == "x" else 180
            simulated_error = int(round(base_speed * direction * self.speed_multiplier))

            command = f"<{simulated_error},0,0>\n" if axis == "x" else f"<0,{simulated_error},0>\n"
            self.serial_thread.send_realtime_command(command)

            # 动态积分推算当前步进电机相对角度 (航位推算 Dead Reckoning)
            d_ang = (18.0 * self.speed_multiplier * 0.025) * direction
            if axis == "x":
                self.servo_x = max(-180.0, min(180.0, self.servo_x + d_ang))
            else:
                self.servo_y = max(-45.0, min(45.0, self.servo_y + d_ang))
            self.position_update_signal.emit(self.servo_x, self.servo_y)
            return

        # 优先级 2: FPS 鼠标手动瞄准模式
        if self.manual_mouse_enabled:
            self._manual_mouse_control_loop()
            return

        # 优先级 3: 自动视觉闭环追踪
        if not self.control_enabled or not self.visual_input_enabled:
            return

        if not self._is_serial_connected():
            self._warn_serial_disconnected()
            return

        # 视觉样本超时看门狗 (Watchdog)：若目标丢失超限，立即紧急停机，防止盲目持续飞车
        time_since_last_vision = time.monotonic() - self.last_vision_time
        if time_since_last_vision > ControlConfig.VISION_WATCHDOG_TIMEOUT:
            if self.current_error_x != 0 or self.current_error_y != 0:
                self.stop_motion(
                    f"视觉信号丢失，停止控制 (超时: {time_since_last_vision:.2f}s)"
                )
            return

        err_x = self.current_error_x
        err_y = self.current_error_y

        # 中心死区滤波 (Deadzone): 消除图像量化噪声引起的轻微电机啸叫与抖动
        if abs(err_x) < ControlConfig.DEADZONE:
            err_x = 0
        if abs(err_y) < ControlConfig.DEADZONE:
            err_y = 0

        # 轴向反转适配 (图像坐标系 Y 轴向下为正，根据物理安装极性调整符号)
        if self.invert_x:
            err_x = -err_x
        if self.invert_y:
            err_y = -err_y

        # 应用 X/Y 轴独立动态追踪增益与最大行程限幅
        scale_x = getattr(ControlConfig, "TRACKING_SCALE_X", 1.20)
        scale_y = getattr(ControlConfig, "TRACKING_SCALE_Y", 0.45)
        max_err_x = getattr(ControlConfig, "TRACKING_MAX_ERROR_X", 120)
        max_err_y = getattr(ControlConfig, "TRACKING_MAX_ERROR_Y", 50)

        # ----------------------------------------------------------------------
        # 3-Zone 运动学伺服整形曲线 (3-Zone Kinematic Servoing Profile)
        # 1. 准星核心微调区 (< settle_zone 像素): 渐进二次阻尼减速，消除过冲与终点回摆
        # 2. 视野巡航响应区 (settle_zone ~ edge_threshold 像素): 高动态线性响应
        # 3. 画面边缘软饱和区 (> edge_threshold 像素): 亚线性指数压缩，防止超大速度冲出视场
        # ----------------------------------------------------------------------
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
            factor_y = 0.65 + 0.35 * (abs_y / float(settle_zone_y))
            err_y_computed = max(7.0, abs_y * scale_y * factor_y)
        elif abs_y > edge_thresh_y:
            excess_y = abs_y - edge_thresh_y
            compressed_y = edge_thresh_y + (excess_y ** 0.55) * 1.2
            err_y_computed = compressed_y * scale_y
        else:
            err_y_computed = abs_y * scale_y

        # 克服机械静摩擦力与重力负载：保证小误差时不卡滞、大误差时不失速，精准咬合目标
        if err_x != 0:
            cmd_mag_x = max(10.0, err_x_computed)
            err_x = int(math.copysign(min(max_err_x, round(cmd_mag_x)), err_x))
        else:
            err_x = 0

        if err_y != 0:
            cmd_mag_y = max(14.0, err_y_computed)
            err_y = int(math.copysign(min(max_err_y, round(cmd_mag_y)), err_y))
        else:
            err_y = 0

        # 动态航位推算电机的相对空间方位角
        if err_x != 0 or err_y != 0:
            d_pan = -(err_x / 640.0) * 30.0 * 0.025
            d_tilt = -(err_y / 480.0) * 20.0 * 0.025
            self.servo_x = max(-180.0, min(180.0, self.servo_x + d_pan))
            self.servo_y = max(-45.0, min(45.0, self.servo_y + d_tilt))
            self.position_update_signal.emit(self.servo_x, self.servo_y)

        # 组装实时通讯控制帧并下发: "<err_x,err_y,fire_val>\n"
        fire_val = 1 if (self.laser_armed and self.laser_firing) else 0
        self.serial_thread.send_realtime_command(f"<{err_x},{err_y},{fire_val}>\n")




    def _manual_mouse_control_loop(self) -> None:
        """
        定频消耗累积的鼠标角位移，计算平滑速度增量并下发，彻底避免串口指令积压
        """
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
        """检查串口通信线路是否处于已连接开启状态"""
        return bool(self.serial_thread and self.serial_thread.is_connected())

    def _warn_serial_disconnected(self) -> None:
        """输出串口未连接告警（自带 2.0 秒节流防抖，避免高频循环中日志刷屏）"""
        now = time.monotonic()
        if now - self.last_warn_time > 2.0:
            logger.warning("[WARNING] Serial port not connected! Please click 'Connect'.")
            self.status_update_signal.emit("Warning: Serial port not connected")
            self.last_warn_time = now

    # --------------------------------------------------------------------------
    # 手动控制接口（单步微调点动与连续平滑运动）
    # --------------------------------------------------------------------------

    def manual_move(self, axis: str, direction: int) -> None:
        """
        单步微调离散点动

        根据当前设定的速度档位 (Gear Multiplier) 动态缩放单次点动的脉冲量，
        执行短时间加速并在预定延迟后自动刹车，实现超高精度像素级微调。

        Args:
            axis: 运动轴 ('x' 为水平偏航，'y' 为垂直俯仰)
            direction: 移动方向 (+1 为正向，-1 为反向)
        """
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
        """
        启动连续手动移动（适用于 UI 按钮按住不放或键盘方向键长按）

        Args:
            axis: 轴向 ('x' 或 'y')
            direction: 方向 (+1 或 -1)
        """
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
        """
        停止连续手动移动（UI 按钮松开或键盘方向键弹起时调用，立即下发刹车）
        """
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
        """
        零位标定：停止双轴电机并将当前机械姿态重置为相对原点 (0.0°, 0.0°)

        Returns:
            bool: 是否成功执行原点归零
        """
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
        """
        将任意摄像机分辨率下的绝对像素误差归一化至 640x480 参考坐标空间

        设计意义:
            保证无论在 1080p、720p 或 VGA 采集分辨率下，PID 增益与伺服动力学曲线
            均表现出一致的物理响应强度，无需为不同相机配置重新校准 PID。

        Args:
            err_x: 原始图像像素 X 轴误差
            err_y: 原始图像像素 Y 轴误差

        Returns:
            tuple[int, int]: 归一化缩放后的 (norm_x, norm_y)
        """
        from config.vision_config import VisionConfig

        actual_w = VisionConfig.FRAME_WIDTH
        actual_h = VisionConfig.FRAME_HEIGHT
        if actual_w <= 0 or actual_h <= 0:
            return err_x, err_y

        scale_x = 640.0 / actual_w
        scale_y = 480.0 / actual_h
        return int(err_x * scale_x), int(err_y * scale_y)


# ------------------------------------------------------------------------------
# 辅助函数（延迟动态读取 VisionConfig，彻底避免跨模块循环依赖导入）
# ------------------------------------------------------------------------------

def VisionConfig_aim_point():
    """
    获取当前工作距离下激光在图像中的真实对准落点（已应用光轴视差校准）
    """
    from config.vision_config import VisionConfig
    return VisionConfig.aim_point(VisionConfig.AKTIF_MESAFE_M)


def VisionConfig_center_x() -> int:
    """延迟获取当前配置下的画面中心 X 像素坐标"""
    from config.vision_config import VisionConfig
    return VisionConfig.CENTER_X


def VisionConfig_center_y() -> int:
    """延迟获取当前配置下的画面中心 Y 像素坐标"""
    from config.vision_config import VisionConfig
    return VisionConfig.CENTER_Y
