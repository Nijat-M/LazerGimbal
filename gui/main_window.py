# -*- coding: utf-8 -*-
"""
主窗口 - 重构版 v3.0 (Main Window - Refactored)

[架构改进 Architecture Improvement]
原来 423 行代码全在一个文件 → 现在拆分成模块化组件

[新结构 New Structure]
- 主窗口只负责组装组件和协调通信
- 每个功能区域都是独立的组件（camera_view, pid_tuner等）
- 代码清晰，易于维护和调试

[文件大小对比]
- 旧版: 423 行
- 新版: ~150 行（减少 65%）
"""

import sys
import time

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QMessageBox, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QKeyEvent

from utils.logger import Logger
logger = Logger("GUI")


# 导入核心模块
try:
    from config import cfg
    from config.control_config import ControlConfig
    from core.serial_thread import SerialThread
    from core.gimbal_controller import GimbalController
    from vision.vision_worker import VisionWorker
    from gui.test_panel import TestModePanel
    from gui.widgets import (
        CameraView, CameraPanel, SerialPanel, ModePanel,
        PIDTuner, ControlPanel, MouseControlPanel
    )
except ImportError:
    sys.path.append("..")
    from config import cfg
    from config.control_config import ControlConfig
    from core.serial_thread import SerialThread
    from core.gimbal_controller import GimbalController
    from vision.vision_worker import VisionWorker
    from gui.test_panel import TestModePanel
    from gui.widgets import (
        CameraView, CameraPanel, SerialPanel, ModePanel,
        PIDTuner, ControlPanel, MouseControlPanel
    )

class MainWindow(QMainWindow):
    """
    主窗口 - 重构版 (Main Window - Refactored)
    
    [职责 Responsibilities]
    1. 组装 GUI 组件
    2. 协调组件之间的通信
    3. 管理核心线程（串口、视觉、控制器）
    
    业务逻辑在: core/gimbal_controller.py
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LaserGimbal - 激光云台 v0.4.0")
        self.resize(1000, 700)

        # [核心线程和控制器]
        self.serial_thread = SerialThread()
        self.vision_thread = VisionWorker()
        self.controller = GimbalController(self.serial_thread)
        self.camera_request_generation = -1

        # [初始化]
        self.init_ui()
        self.init_signals()

        # 启动视觉线程
        self.vision_thread.start()
        
        # 摄像头会通过 camera_panel 自动检测并应用，无需手动初始化

    def init_ui(self):
        """初始化界面 - 使用组件化设计"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局：左侧视频，右侧控制
        main_layout = QHBoxLayout(central_widget)

        # ==========================
        # 左侧：摄像头显示区
        # ==========================
        self.camera_view = CameraView()
        main_layout.addWidget(self.camera_view, 2)

        # ==========================
        # 右侧：控制面板（添加滚动区域）
        # ==========================
        # 创建滚动区域容器
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setMinimumWidth(420)  # 设置最小宽度
        scroll_area.setMaximumWidth(480)  # 增加最大宽度，留出滚动条空间
        
        # 设置滚动条样式，使其更加美观且不挡住内容
        scroll_area.setStyleSheet("""
            QScrollBar:vertical {
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建内容组件
        scroll_content = QWidget()
        right_layout = QVBoxLayout(scroll_content)
        right_layout.setSpacing(10)  # 减小间距，节省空间
        right_layout.setContentsMargins(10, 10, 15, 10)  # 右侧留出更多空间给滚动条

        # 1. 串口连接面板
        self.serial_panel = SerialPanel(default_port=cfg.SERIAL_PORT)
        right_layout.addWidget(self.serial_panel)
        
        # 2. 摄像头选择面板（新增）
        self.camera_panel = CameraPanel(default_id=cfg.CAMERA_ID)
        right_layout.addWidget(self.camera_panel)

        # 3. 模式选择面板
        self.mode_panel = ModePanel()
        right_layout.addWidget(self.mode_panel)

        # 4. PID 调参面板
        self.pid_tuner = PIDTuner(
            initial_kp=cfg.PID_KP,
            initial_ki=cfg.PID_KI,
            initial_kd=cfg.PID_KD,
            invert_x=cfg.INVERT_X,
            invert_y=cfg.INVERT_Y
        )
        right_layout.addWidget(self.pid_tuner)

        # 5. 控制按钮面板
        self.control_panel = ControlPanel()
        right_layout.addWidget(self.control_panel)

        # 6. 测试模式面板（默认隐藏）
        self.test_panel = TestModePanel()
        self.test_panel.setVisible(False)
        self.test_panel.setMaximumHeight(150)  # 限制最大高度
        right_layout.addWidget(self.test_panel)

        # 7. 鼠标手动瞄准面板（默认隐藏）
        self.mouse_control_panel = MouseControlPanel(
            initial_sensitivity=ControlConfig.MOUSE_SENSITIVITY
        )
        self.mouse_control_panel.setVisible(False)
        right_layout.addWidget(self.mouse_control_panel)

        # 状态栏
        self.status_label = QLabel("系统就绪")
        self.status_label.setStyleSheet("color: gray; padding: 5px;")
        self.status_label.setWordWrap(True) # 允许长文本换行，防止撑大窗口
        right_layout.addWidget(self.status_label)
        
        right_layout.addStretch()
        
        # 将内容设置到滚动区域
        scroll_area.setWidget(scroll_content)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area, 1)

    def init_signals(self):
        """连接信号与槽 - 协调各组件通信"""
        # ===== 视觉线程 =====
        # 视觉 -> 摄像头显示组件
        self.vision_thread.frame_signal.connect(self.camera_view.update_camera_feed)
        self.vision_thread.mask_signal.connect(self.camera_view.update_mask_feed)
        # 实时信息更新
        self.vision_thread.stats_signal.connect(self.camera_panel.update_vision_stats)
        self.vision_thread.camera_state_signal.connect(self.on_camera_state_changed)
        # 视觉 -> 控制器（两条信号路径）
        # TRACKING 模式：发送两点误差（激光 vs 蓝色目标）
        self.vision_thread.control_signal.connect(self.controller.handle_vision_error)
        # BLUE_TRACKING 模式：发送蓝色目标原始坐标（误差由控制器计算）
        self.vision_thread.target_pos_signal.connect(self.controller.handle_target_position)

        # 实时画面 -> FPS 鼠标瞄准控制器
        self.camera_view.mouse_delta_signal.connect(self.controller.handle_mouse_delta)
        self.camera_view.mouse_capture_changed_signal.connect(
            self.controller.set_mouse_capture_active
        )
        self.camera_view.mouse_capture_changed_signal.connect(
            self.mouse_control_panel.set_capture_state
        )
        self.controller.manual_target_update_signal.connect(
            self.mouse_control_panel.update_target
        )
        self.mouse_control_panel.sensitivity_changed.connect(
            self.controller.update_mouse_sensitivity
        )
        
        # ===== 串口线程 =====
        self.serial_thread.connection_state_signal.connect(self.on_connection_status_changed)
        
        # ===== 摄像头面板 =====
        self.camera_panel.camera_changed.connect(self.on_camera_changed)
        self.camera_panel.camera_toggled.connect(self.on_camera_toggled)
        self.camera_panel.flip_changed.connect(self.vision_thread.set_flip_mode)
        self.camera_panel.open_settings_requested.connect(self.vision_thread.open_camera_settings)
        
        # ===== 控制器 =====
        self.controller.status_update_signal.connect(self.update_status)
        self.controller.position_update_signal.connect(self.update_status)
        
        # ===== GUI 组件 =====
        # 串口面板
        self.serial_panel.connection_toggled.connect(self.on_serial_connection_toggled)
        
        # 模式面板
        self.mode_panel.mode_changed.connect(self.on_mode_changed)
        
        # PID 调参面板
        self.pid_tuner.pid_changed.connect(self.on_pid_changed)
        self.pid_tuner.deadzone_changed.connect(self.on_deadzone_changed)
        self.pid_tuner.invert_changed.connect(self.on_invert_changed)
        self.pid_tuner.save_requested.connect(self.on_save_config)
        self.pid_tuner.reset_requested.connect(self.on_reset_pid)
        
        # 控制面板
        self.control_panel.control_toggled.connect(self.on_control_toggled)
        self.control_panel.reset_requested.connect(self.on_reset_position)
        
        # 手动测试面板（支持单步微调、长按连续移动、独立键盘开关）
        self.test_panel.request_move_signal.connect(self.on_manual_move)
        self.test_panel.start_continuous_signal.connect(self.controller.start_manual_continuous)
        self.test_panel.stop_continuous_signal.connect(self.controller.stop_manual_continuous)
        self.test_panel.keyboard_control_toggled.connect(self.on_keyboard_control_toggled)
        
        # 激活键盘焦点
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


    # ==========================
    # 槽函数 (Slots) - 简化版
    # ==========================
    
    def on_serial_connection_toggled(self, checked, port):
        """串口连接切换"""
        if checked:
            logger.info(f"[GUI] 连接串口: {port}")
            self.serial_thread.connect_serial(port, cfg.BAUD_RATE)
            if not self.serial_thread.isRunning():
                self.serial_thread.start()
        else:
            logger.info("[GUI] 断开串口请求")
            self.serial_thread.disconnect_serial()
            # 注意：不建议在此直接 stop()，因为线程内部可能还在处理最后的读取/写入。
            # 依靠 disconnect_serial 关闭串口后，线程循环会自动跳过。
            # 真正的停止建议在 closeEvent。
    
    def on_connection_status_changed(self, success, message):
        """串口连接状态改变"""
        logger.info(f"[GUI] {message}")
        self.status_label.setText(message)
        # 同步更新串口面板的按钮状态
        self.serial_panel.set_connection_status(success, message)
        
        if success:
            self.status_label.setStyleSheet("color: #00ff00; padding: 5px;")
        else:
            self.camera_view.release_mouse_control()
            self.controller.stop_motion("串口连接丢失，运动已停止")
            self.status_label.setStyleSheet("color: red; padding: 5px;")
            self.serial_panel.set_connection_status(False, message)
    def on_camera_changed(self, camera_id, width, height):
        """摄像头切换"""
        logger.info(f"[GUI] 摄像头切换: ID={camera_id}, Resolution={width}x{height}")
        self.vision_thread.switch_camera(camera_id, width, height)
        self.status_label.setText(f"正在打开 Camera {camera_id} @ {width}x{height}")

    def on_camera_state_changed(
        self, generation: int, ready: bool, message: str
    ) -> None:
        """Ignore stale camera results and arm mouse input only for live frames."""
        if generation < self.camera_request_generation:
            return
        self.camera_request_generation = generation
        self.camera_view.set_camera_active(ready)
        self.controller.set_visual_input_enabled(ready)
        if not ready:
            self.control_panel.set_control_enabled(False)
            self.camera_view.release_mouse_control()
            self.controller.stop_motion(f"{message}，运动已停止")
        self.status_label.setText(message)

    def on_camera_toggled(self, is_open: bool):
        """摄像头开关触发"""
        if not is_open:
            logger.info("[GUI] 用户触发关闭摄像头")
            self.camera_view.release_mouse_control()
            self.controller.stop_motion("摄像头已关闭，运动已停止")
            self.vision_thread.close_camera()
            self.camera_view.show_blank_screen("相机未运行 (Camera Not Running)")
            self.status_label.setText("摄像头已关闭")
        else:
            logger.info("[GUI] 用户触发开启摄像头")
            self.camera_view.set_camera_active(False)
            cam_id = self.camera_panel.get_current_camera_id()
            w, h = self.camera_panel.get_selected_resolution()
            self.vision_thread.switch_camera(cam_id, w, h)
    
    def on_mode_changed(self, mode):
        """Switch modes while keeping automatic and manual motion exclusive."""
        logger.info(f"[GUI] 工作模式切换: {mode}")

        is_test = mode == "TEST"
        is_mouse = mode == "MANUAL_MOUSE"
        self.test_panel.setVisible(is_test)
        self.mouse_control_panel.setVisible(is_mouse)

        # Every mode transition first disarms the previous motion source.
        self.camera_view.release_mouse_control()
        self.control_panel.set_control_enabled(False)
        self.controller.set_manual_mouse_mode(is_mouse)
        self.camera_view.set_mouse_control_enabled(is_mouse)

        # Manual modes still display live video but do not run target detection.
        vision_mode = "IDLE" if mode in ("TEST", "MANUAL_MOUSE") else mode
        self.vision_thread.set_mode(vision_mode)
        self.status_label.setText(
            "鼠标瞄准：点击实时画面开始，Esc 停止"
            if is_mouse
            else f"模式: {mode}"
        )
    
    def on_pid_changed(self, kp, ki, kd):
        """PID 参数改变"""
        cfg.PID_KP = kp
        cfg.PID_KI = ki
        cfg.PID_KD = kd
        self.controller.update_pid_tunings(kp, ki, kd)
        
    def on_deadzone_changed(self, deadzone):
        """死区参数改变"""
        # 修改 ControlConfig 中死区设定
        ControlConfig.DEADZONE = deadzone
        logger.info(f"[GUI] 死区已统一更新为: {deadzone}px")
    
    def on_invert_changed(self, invert_x, invert_y):
        """反转设置改变"""
        self.controller.set_invert(invert_x, invert_y)
    
    def on_save_config(self):
        """保存配置"""
        cfg.save_config()
        self.status_label.setText("✓ 配置已保存")
    
    def on_reset_pid(self):
        """重置 PID（恢复 ControlConfig 默认值）"""
        from config.control_config import ControlConfig
        default_kp = ControlConfig.KP
        default_ki = ControlConfig.KI
        default_kd = ControlConfig.KD

        # 更新控制器
        self.controller.update_pid_tunings(default_kp, default_ki, default_kd)
        # 同步更新 GUI 滑块显示
        self.pid_tuner.set_pid_values(default_kp, default_ki, default_kd)
    
    def on_control_toggled(self, checked):
        """控制开关（开启/关闭自动目标追踪）"""
        if checked:
            if not self.serial_thread.is_connected():
                self.status_label.setText("⚠️ 串口未连接，请先点击'连接'串口！")
                self.control_panel.set_control_enabled(False)
                return
            if not self.controller.visual_input_enabled:
                self.status_label.setText("⚠️ 摄像头未就绪，请先开启摄像头！")
                self.control_panel.set_control_enabled(False)
                return

            # 如果当前还是 IDLE 待机模式，自动帮用户切换为蓝色目标追踪模式
            if self.mode_panel.get_current_mode() in ("IDLE", "TEST"):
                self.mode_panel.set_mode("BLUE_TRACKING")
                self.vision_thread.set_mode("BLUE_TRACKING")

        accepted = self.controller.set_control_enabled(checked)
        if checked and not accepted:
            self.control_panel.set_control_enabled(False)
        else:
            status = "🟢 自动追踪控制已启动" if checked else "⚪ 自动控制已停止"
            self.status_label.setText(status)
    
    def on_reset_position(self):
        """重置位置"""
        if not self.controller.sync_position():
            return
        QMessageBox.information(
            self, 
            "重置完成", 
            "已向 STM32 发送物理归中命令 (90°, 90°)"
        )
    
    def on_manual_move(self, axis, direction):
        """手动移动（测试模式）"""
        print(f"[GUI] 收到手动移动请求: 轴={axis}, 方向={direction}")
        self.controller.manual_move(axis, direction)

    def on_keyboard_control_toggled(self, enabled: bool):
        """键盘操控开关切换"""
        self.keyboard_control_enabled = enabled
        if not enabled:
            self.controller.stop_manual_continuous()
        status = "🎮 键盘操控已开启 (可用 WASD / 方向键)" if enabled else "键盘操控已关闭"
        self.status_label.setText(status)
    
    def update_status(self, *args):
        """更新状态栏"""
        if len(args) == 1:
            # 字符串消息
            self.status_label.setText(args[0])
        elif len(args) == 2:
            # 位置信息 (x, y)
            x, y = args
            self.status_label.setText(f"Servo: X={x:.1f}°, Y={y:.1f}°")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """键盘方向键 (↑/↓/←/→) 与 (W/S/A/D) 快捷操控云台（仅在勾选开启时生效）"""
        if not getattr(self, "keyboard_control_enabled", False):
            super().keyPressEvent(event)
            return

        if event.isAutoRepeat():
            return

        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_W):
            self.controller.start_manual_continuous('y', -1)
            event.accept()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_S):
            self.controller.start_manual_continuous('y', 1)
            event.accept()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_A):
            self.controller.start_manual_continuous('x', 1)
            event.accept()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
            self.controller.start_manual_continuous('x', -1)
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """松开键盘按键时立即平稳刹车"""
        if not getattr(self, "keyboard_control_enabled", False):
            super().keyReleaseEvent(event)
            return

        if event.isAutoRepeat():
            return

        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_W, Qt.Key.Key_Down, Qt.Key.Key_S,
                   Qt.Key.Key_Left, Qt.Key.Key_A, Qt.Key.Key_Right, Qt.Key.Key_D):
            self.controller.stop_manual_continuous()
            event.accept()
        else:
            super().keyReleaseEvent(event)


    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Release input, stop motion, and terminate background workers."""
        logger.info("[GUI] 关闭窗口，停止线程...")
        self.camera_view.release_mouse_control()
        self.controller.stop()

        if self.serial_thread.isRunning():
            # Give the priority STOP a short opportunity to leave the queue.
            time.sleep(0.03)
            self.serial_thread.stop()
        else:
            self.serial_thread.disconnect_serial()

        if self.vision_thread.isRunning() and not self.vision_thread.stop(5000):
            logger.error("[GUI] 视觉线程未能在 5 秒内退出，取消窗口销毁")
            QMessageBox.warning(
                self,
                "关闭尚未完成",
                "摄像头线程仍在释放资源，窗口暂时不会销毁。请稍后重试。",
            )
            if a0 is not None:
                a0.ignore()
            return

        if a0 is not None:
            a0.accept()


