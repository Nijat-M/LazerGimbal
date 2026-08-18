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
    QLabel, QMessageBox, QScrollArea, QSplitter
)
from PyQt6.QtCore import Qt, QTimer
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
    from core.stage3_mission_director import Stage3MissionDirector
    from gui.widgets import (
        CameraView, CameraPanel, SerialPanel, ModePanel,
        PIDTuner, ControlPanel, MouseControlPanel, DetectionPanel, CrosshairCalibrationPanel,
        Stage3MissionPanel
    )
except ImportError:
    sys.path.append("..")
    from config import cfg
    from config.control_config import ControlConfig
    from core.serial_thread import SerialThread
    from core.gimbal_controller import GimbalController
    from vision.vision_worker import VisionWorker
    from gui.test_panel import TestModePanel
    from core.stage3_mission_director import Stage3MissionDirector
    from gui.widgets import (
        CameraView, CameraPanel, SerialPanel, ModePanel,
        PIDTuner, ControlPanel, MouseControlPanel, DetectionPanel, CrosshairCalibrationPanel,
        Stage3MissionPanel
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
        self.setWindowTitle("LaserGimbal Pro Ground Station")
        self.resize(1260, 820)
        self.setMinimumSize(960, 640)
        self.is_camera_fullscreen = False

        # Kayitli boresight kalibrasyonunu yukle (lazer-kamera es eksenli degil)
        # 启动时加载保存的光轴校准（相机和激光不同轴，必须补偿）
        from config.vision_config import VisionConfig
        VisionConfig.load_crosshair_calibration()

        # [核心线程和控制器]
        self.serial_thread = SerialThread()
        self.vision_thread = VisionWorker()
        self.controller = GimbalController(self.serial_thread)
        self.camera_request_generation = -1
        self.keyboard_control_enabled = True

        # [初始化]
        self.init_ui()
        self.init_signals()

        # 启动视觉线程
        self.vision_thread.start()
        
        # 启动时自动尝试连接保存的 STM32 端口
        QTimer.singleShot(700, self._auto_connect_serial)

    def _auto_connect_serial(self):
        """自动连接保存的 STM32 串口"""
        from config.device_config import DeviceConfig
        if getattr(DeviceConfig, "AUTO_CONNECT_SERIAL", True):
            port = self.serial_panel.combo_port.currentData()
            if port and not self.serial_panel.is_connected:
                logger.info(f"[GUI] Auto-connecting to saved serial port: {port}...")
                self.serial_panel.btn_connect.setChecked(True)
                self.serial_panel._on_connect_clicked()

    def init_ui(self):
        """初始化界面 - 使用响应式水平分割布局 (QSplitter)"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # 创建主响应式水平分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #1e293b;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background-color: #0284c7;
            }
        """)

        # ==========================
        # 左侧：摄像头显示区
        # ==========================
        self.camera_view = CameraView()
        self.camera_view.setMinimumWidth(480)
        self.splitter.addWidget(self.camera_view)

        # ==========================
        # 右侧：控制面板（添加滚动区域）
        # ==========================
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setMinimumWidth(380)
        
        # 设置滚动条样式，使其美观且不遮挡内容
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #1e293b;
                border-radius: 6px;
                background-color: #0b0f19;
            }
            QScrollBar:vertical {
                width: 10px;
                background: #0f172a;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                border-radius: 5px;
                min-height: 25px;
            }
            QScrollBar::handle:vertical:hover {
                background: #0284c7;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建内容组件
        scroll_content = QWidget()
        right_layout = QVBoxLayout(scroll_content)
        right_layout.setSpacing(8)
        right_layout.setContentsMargins(8, 8, 8, 8)

        # 1. 串口连接面板
        self.serial_panel = SerialPanel(default_port=cfg.SERIAL_PORT)
        right_layout.addWidget(self.serial_panel)
        
        # 2. 摄像头选择面板（新增）
        self.camera_panel = CameraPanel(default_id=cfg.CAMERA_ID)
        right_layout.addWidget(self.camera_panel)

        # 3. 模式选择面板
        self.mode_panel = ModePanel()
        right_layout.addWidget(self.mode_panel)

        # Yetenek 7: dost/dusman + ates izni paneli
        # 能力7：敌我识别 + 开火授权面板（只在 YOLO Defense Tracking 下显示）
        self.detection_panel = DetectionPanel()
        self.detection_panel.setVisible(False)
        right_layout.addWidget(self.detection_panel)

        # Stage 3 Autonomous Mission Panel (第三阶段自主防空竞赛加分流程)
        self.stage3_director = Stage3MissionDirector(main_window=self)
        self.stage3_mission_panel = Stage3MissionPanel(director=self.stage3_director)
        self.stage3_mission_panel.setVisible(False)
        right_layout.addWidget(self.stage3_mission_panel)

        # Lazer-Kamera boresight kalibrasyon paneli
        # 激光-相机光轴校准面板
        self.calibration_panel = CrosshairCalibrationPanel()
        right_layout.addWidget(self.calibration_panel)

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

        # 6. 手动电机与键盘控制面板 (常驻主界面，随时可直接操控)
        self.test_panel = TestModePanel()
        self.test_panel.setVisible(True)
        self.test_panel.setMaximumHeight(160)
        right_layout.addWidget(self.test_panel)

        # 7. 鼠标手动瞄准面板（默认隐藏）
        self.mouse_control_panel = MouseControlPanel(
            initial_sensitivity=ControlConfig.MOUSE_SENSITIVITY
        )
        self.mouse_control_panel.setVisible(False)
        right_layout.addWidget(self.mouse_control_panel)

        # 状态栏
        self.status_label = QLabel("System Ready")
        self.status_label.setStyleSheet("color: #94a3b8; padding: 4px; font-size: 11px;")
        self.status_label.setWordWrap(True) # 允许长文本换行，防止撑大窗口
        right_layout.addWidget(self.status_label)
        
        right_layout.addStretch()
        
        # 将内容设置到滚动区域
        self.scroll_area.setWidget(scroll_content)
        self.splitter.addWidget(self.scroll_area)
        
        # 设置左右初始分配比例 ~ 65% : 35%
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([780, 440])

        main_layout.addWidget(self.splitter)

    def init_signals(self):
        """连接信号与槽 - 协调各组件通信"""
        # ===== 视觉线程 =====
        # 视觉 -> 摄像头显示组件
        self.vision_thread.frame_signal.connect(self.camera_view.update_camera_feed)
        self.vision_thread.mask_signal.connect(self.camera_view.update_mask_feed)
        # 实时信息更新
        self.vision_thread.stats_signal.connect(self.camera_panel.update_vision_stats)
        self.vision_thread.camera_state_signal.connect(self.on_camera_state_changed)
        self.vision_thread.iff_signal.connect(self.on_iff_update)
        self.calibration_panel.offset_changed.connect(self.on_crosshair_offset)
        self.vision_thread.detections_signal.connect(self.detection_panel.update_detections)
        self.vision_thread.detections_signal.connect(self.stage3_director.on_detections_update)
        self.vision_thread.laser_fire_request_signal.connect(self.on_laser_fire_request)
        # 物体追踪模式发送目标原始坐标，误差由控制器计算
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
        if hasattr(self.serial_thread, "data_sent_signal"):
            self.serial_thread.data_sent_signal.connect(self.serial_panel.log_tx)
        if hasattr(self.serial_thread, "data_received_signal"):
            self.serial_thread.data_received_signal.connect(self.serial_panel.log_rx)
        
        # ===== 摄像头面板 =====
        self.camera_panel.camera_changed.connect(self.on_camera_changed)
        self.camera_panel.camera_toggled.connect(self.on_camera_toggled)
        self.camera_panel.flip_changed.connect(self.vision_thread.set_flip_mode)
        self.camera_panel.open_settings_requested.connect(self.vision_thread.open_camera_settings)
        
        # ===== 控制器 =====
        self.controller.status_update_signal.connect(self.update_status)
        self.controller.position_update_signal.connect(self.update_status)
        self.controller.position_update_signal.connect(self.vision_thread.update_telemetry_pos)
        self.controller.laser_state_signal.connect(self.vision_thread.update_telemetry_laser)
        self.controller.speed_gear_changed_signal.connect(
            lambda gear, mult: self.camera_view.set_speed_gear_visual(gear)
        )
        self.controller.speed_gear_changed_signal.connect(
            lambda gear, mult: self.vision_thread.set_speed_gear(gear)
        )
        
        # ===== GUI 组件 =====
        # 串口面板
        self.serial_panel.connection_toggled.connect(self.on_serial_connection_toggled)
        
        # 模式面板
        self.mode_panel.mode_changed.connect(self.on_mode_changed)
        self.mode_panel.mode_changed.connect(self.vision_thread.set_mode)
        self.mode_panel.yolo_model_changed.connect(self.vision_thread.set_yolo_model)
        self.mode_panel.yolo_class_changed.connect(self.vision_thread.set_yolo_target_class)
        self.mode_panel.yolo_conf_changed.connect(self.vision_thread.set_yolo_conf_threshold)
        
        # PID 调参面板
        self.pid_tuner.pid_changed.connect(self.on_pid_changed)
        self.pid_tuner.deadzone_changed.connect(self.on_deadzone_changed)
        self.pid_tuner.invert_changed.connect(self.on_invert_changed)
        self.pid_tuner.save_requested.connect(self.on_save_config)
        self.pid_tuner.reset_requested.connect(self.on_reset_pid)
        
        # 控制面板与激光武器
        self.control_panel.control_toggled.connect(self.on_control_toggled)
        self.control_panel.reset_requested.connect(self.on_reset_position)
        self.control_panel.emergency_stop_requested.connect(self.on_emergency_stop)
        self.control_panel.laser_armed_toggled.connect(self.controller.set_laser_armed)
        self.control_panel.laser_fire_changed.connect(self.controller.set_laser_firing)
        self.control_panel.laser_power_changed.connect(self.controller.set_laser_power)

        # 激光状态 -> 画面准星 HUD
        self.controller.laser_state_signal.connect(
            lambda armed, firing, pwr: self.camera_view.set_laser_status(armed, firing)
        )
        self.controller.laser_state_signal.connect(
            lambda armed, firing, pwr: self.control_panel.set_laser_firing_visual(firing)
        )
        
        # 摄像头全屏、准星画中画缩放、3 档速度与 3 键录屏信号
        self.camera_view.fullscreen_requested.connect(self.toggle_fullscreen_mode)
        self.camera_view.pip_zoom_changed.connect(self.vision_thread.set_pip_zoom)
        self.camera_view.speed_gear_changed.connect(self.controller.set_speed_gear)
        self.camera_view.speed_gear_changed.connect(self.vision_thread.set_speed_gear)
        self.camera_view.record_start_requested.connect(self.on_start_recording)
        self.camera_view.record_pause_requested.connect(self.on_pause_recording)
        self.camera_view.record_stop_requested.connect(self.on_stop_recording)
        self.vision_thread.recording_status_signal.connect(self.camera_view.set_recording_status)

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
    
    def toggle_fullscreen_mode(self):
        """全屏/窗口化模式切换"""
        self.is_camera_fullscreen = not self.is_camera_fullscreen
        if self.is_camera_fullscreen:
            # 隐藏右侧控制栏，主窗口全屏化
            self.scroll_area.setVisible(False)
            self.showFullScreen()
            self.camera_view.set_fullscreen_state(True)
            self.status_label.setText("⛶ Fullscreen Monitor Mode (Press Esc or F11 to exit)")
        else:
            # 恢复正常窗口并展示右侧控制栏
            self.scroll_area.setVisible(True)
            self.showNormal()
            self.camera_view.set_fullscreen_state(False)
            self.splitter.setSizes([780, 440])
            self.status_label.setText("Exited Fullscreen Mode")

    def on_serial_connection_toggled(self, checked, port):
        """串口连接切换"""
        if checked:
            logger.info(f"[GUI] Connecting serial: {port}")
            self.serial_thread.connect_serial(port, cfg.BAUD_RATE)
            if not self.serial_thread.isRunning():
                self.serial_thread.start()
        else:
            logger.info("[GUI] Disconnect serial request")
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
            self.controller.stop_motion("Serial connection lost, motion stopped")
            self.status_label.setStyleSheet("color: red; padding: 5px;")
            self.serial_panel.set_connection_status(False, message)
    def on_camera_changed(self, camera_id, width, height):
        """摄像头切换"""
        logger.info(f"[GUI] Camera switched: ID={camera_id}, Resolution={width}x{height}")
        self.vision_thread.switch_camera(camera_id, width, height)
        self.status_label.setText(f"Opening Camera {camera_id} @ {width}x{height}")

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
            self.controller.stop_motion(f"{message}，motion stopped")
        self.status_label.setText(message)

    def on_camera_toggled(self, is_open: bool):
        """摄像头开关触发"""
        if not is_open:
            logger.info("[GUI] User triggered close camera")
            self.camera_view.release_mouse_control()
            self.controller.stop_motion("Camera closed，motion stopped")
            self.vision_thread.close_camera()
            self.camera_view.show_blank_screen("Camera Not Running")
            self.status_label.setText("Camera closed")
        else:
            logger.info("[GUI] User triggered open camera")
            cam_id = self.camera_panel.get_current_camera_id()
            w, h = self.camera_panel.get_selected_resolution()
            self.vision_thread.switch_camera(cam_id, w, h)
    
    def on_mode_changed(self, mode):
        """Switch modes while keeping automatic and manual motion exclusive."""
        logger.info(f"[GUI] Mode switched: {mode}")

        self.detection_panel.setVisible(mode == "YOLO_TRACKING")
        self.stage3_mission_panel.setVisible(mode == "YOLO_TRACKING")
        if mode != "YOLO_TRACKING":
            self.detection_panel.clear_detections()
            if hasattr(self, "stage3_director") and self.stage3_director.is_running:
                self.stage3_director.abort_mission("Mode Switched Away")
        is_mouse = mode == "MANUAL_MOUSE"
        self.test_panel.setVisible(True) # 手动控制面板始终常驻显示
        self.mouse_control_panel.setVisible(is_mouse)

        # Every mode transition first disarms the previous motion source.
        self.camera_view.release_mouse_control()
        self.control_panel.set_control_enabled(False)
        self.controller.set_manual_mouse_mode(is_mouse)
        self.camera_view.set_mouse_control_enabled(is_mouse)

        # Manual modes still display live video but do not run target detection.
        vision_mode = "IDLE" if mode in ("TEST", "MANUAL_MOUSE") else mode
        self.vision_thread.set_mode(vision_mode)
        
        if mode == "BALLOON_HUNT":
            self.control_panel.set_control_enabled(True)
            self.on_control_toggled(True)
            self.status_label.setText("🎈 Orange Balloon Pop Mode: Auto-tracking & 100% Laser Active")
        else:
            self.controller.set_laser_firing(False)
            self.status_label.setText(
                "Mouse Aim: Click live view to start, Esc to stop"
                if is_mouse
                else f"Mode: {mode}"
            )
    
    def on_laser_fire_request(self, firing: bool, power: int = 100):
        """来自视觉线程（如橙色气球打击模式）的自动开火请求"""
        if firing:
            if not self.controller.laser_armed:
                self.controller.set_laser_armed(True)
                self.control_panel.btn_laser_arm.setChecked(True)
            if self.controller.laser_power != power:
                self.controller.set_laser_power(power)
                self.control_panel.slider_power.setValue(power)
            if not self.controller.laser_firing:
                self.controller.set_laser_firing(True)
        else:
            if self.controller.laser_firing:
                self.controller.set_laser_firing(False)
    
    def on_crosshair_offset(self, ox: int, oy: int):
        """Boresight offset degisti -> hem cizim hem nisan alma bundan etkilenir."""
        logger.info(f"[GUI] Boresight offset: dX={ox:+d} dY={oy:+d}")
        self.status_label.setText(f"Boresight: dX={ox:+d}  dY={oy:+d}")

    def on_iff_update(self, info: dict):
        """Yetenek 7: vision thread'den gelen dost/dusman durumu -> panel"""
        self.detection_panel.update_iff(info)

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
        logger.info(f"[GUI] Deadzone updated to: {deadzone}px")
    
    def on_invert_changed(self, invert_x, invert_y):
        """反转设置改变"""
        self.controller.set_invert(invert_x, invert_y)
    
    def on_save_config(self):
        """保存配置"""
        cfg.save_config()
        self.status_label.setText("✓ Config saved")
    
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
                self.status_label.setText("⚠️ Serial not connected, please connect first!")
                self.control_panel.set_control_enabled(False)
                return
            if not self.controller.visual_input_enabled:
                self.status_label.setText("⚠️ Camera not ready, please open camera first!")
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
            status = "🟢 Auto tracking started" if checked else "⚪ Auto tracking stopped"
            self.status_label.setText(status)
    
    def on_reset_position(self):
        """停止电机并重置相对原点。"""
        if not self.controller.sync_position():
            return
        QMessageBox.information(
            self, 
            "Reset Complete",
            "Motors stopped. Current position has been set as software relative origin."
        )
    
    def on_start_recording(self):
        """开始录屏"""
        success = self.vision_thread.start_recording()
        if success:
            self.status_label.setText("🔴 正在录制全屏超清视频流...")
            self.status_label.setStyleSheet("color: #ef4444; font-weight: bold; padding: 5px;")

    def on_pause_recording(self):
        """暂停/继续录屏"""
        self.vision_thread.pause_recording()

    def on_stop_recording(self):
        """停止并保存录屏"""
        saved_file = self.vision_thread.stop_recording()
        if saved_file:
            self.status_label.setText(f"✓ 录屏已完成并保存至: {saved_file}")
            self.status_label.setStyleSheet("color: #38bdf8; font-weight: bold; padding: 5px;")

    def on_manual_move(self, axis, direction):
        """手动移动（测试模式）"""
        print(f"[GUI] Received manual move request: axis={axis}, dir={direction}")
        self.controller.manual_move(axis, direction)

    def on_keyboard_control_toggled(self, enabled: bool):
        """键盘操控开关切换"""
        self.keyboard_control_enabled = enabled
        if not enabled:
            self.controller.stop_manual_continuous()
        status = "🎮 Keyboard control ON (WASD/Arrows)" if enabled else "Keyboard control OFF"
        self.status_label.setText(status)

    def update_status(self, *args):
        """更新状态栏"""
        if len(args) == 1:
            # 字符串消息
            self.status_label.setText(str(args[0]))
        elif len(args) == 2:
            # 位置信息 (x, y)
            x, y = args
            self.status_label.setText(f"Relative origin: X={x:.1f}°, Y={y:.1f}°")

    def on_emergency_stop(self):
        """急停处理：立即切断激光、停止电机并重置所有使能"""
        logger.warning("[GUI] 收到急停请求 (EMERGENCY STOP)！")
        self.camera_view.release_mouse_control()
        self.control_panel.set_control_enabled(False)
        self.control_panel.btn_arm.setChecked(False)
        self.controller.set_laser_armed(False)
        self.controller.stop_motion("🛑 Emergency Stop Triggered")
        self.status_label.setText("🛑 EMERGENCY STOP TRIGGERED")
        self.status_label.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
        self.detection_panel.set_emergency_stop_visual()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """全局快捷键：F11 全屏切换、空格键发射激光、Esc 退出全屏/急停、[ ] / + - 准星画中画缩放、R 录屏、方向键/WASD 手动点动"""
        if event.isAutoRepeat():
            return

        key = event.key()

        # F11 键：切换全屏模式
        if key == Qt.Key.Key_F11:
            self.toggle_fullscreen_mode()
            event.accept()
            return

        # Esc 键：优先退出全屏，其次释放鼠标捕获，最后触发急停
        if key == Qt.Key.Key_Escape:
            if self.is_camera_fullscreen:
                self.toggle_fullscreen_mode()
                event.accept()
                return
            if self.controller.mouse_capture_active:
                self.camera_view.release_mouse_control()
                event.accept()
                return
            self.on_emergency_stop()
            event.accept()
            return

        # 空格键：在激光处于 ARMED 状态下按住发射
        if key == Qt.Key.Key_Space:
            if self.controller.laser_armed:
                self.control_panel.set_laser_firing_visual(True)
                self.controller.set_laser_firing(True)
                event.accept()
                return

        # 准星放大镜快捷键：] 或 + 或 = 放大 / [ 或 - 缩小
        if key in (Qt.Key.Key_BracketRight, Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.camera_view.zoom_in()
            event.accept()
            return
        elif key in (Qt.Key.Key_BracketLeft, Qt.Key.Key_Minus):
            self.camera_view.zoom_out()
            event.accept()
            return

        # 数字键 1, 2, 3: 快速切换电机速度档位 (Gear 1: 0.3x, Gear 2: 1.0x, Gear 3: 2.2x)
        if key == Qt.Key.Key_1:
            self.controller.set_speed_gear(1)
            event.accept()
            return
        elif key == Qt.Key.Key_2:
            self.controller.set_speed_gear(2)
            event.accept()
            return
        elif key == Qt.Key.Key_3:
            self.controller.set_speed_gear(3)
            event.accept()
            return

        # R 键：快捷录屏 (若空闲则开始录制，若正在录制则暂停/继续)
        if key == Qt.Key.Key_R:
            if self.vision_thread.recording_state == "IDLE":
                self.on_start_recording()
            else:
                self.on_pause_recording()
            event.accept()
            return

        # 键盘方向键 (↑/↓/←/→) 与 (W/S/A/D) 快捷操控云台（长按连续旋转，松开即停）
        if getattr(self, "keyboard_control_enabled", True):
            if key in (Qt.Key.Key_Up, Qt.Key.Key_W):
                if not event.isAutoRepeat():
                    self.controller.start_manual_continuous('y', 1)
                event.accept()
                return
            elif key in (Qt.Key.Key_Down, Qt.Key.Key_S):
                if not event.isAutoRepeat():
                    self.controller.start_manual_continuous('y', -1)
                event.accept()
                return
            elif key in (Qt.Key.Key_Left, Qt.Key.Key_A):
                if not event.isAutoRepeat():
                    self.controller.start_manual_continuous('x', -1)
                event.accept()
                return
            elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
                if not event.isAutoRepeat():
                    self.controller.start_manual_continuous('x', 1)
                event.accept()
                return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """松开按键处理：松开空格停火、松开方向键平稳刹车"""
        if event.isAutoRepeat():
            return

        key = event.key()

        # 松开空格键：停止激光发射
        if key == Qt.Key.Key_Space:
            self.control_panel.set_laser_firing_visual(False)
            self.controller.set_laser_firing(False)
            event.accept()
            return

        if getattr(self, "keyboard_control_enabled", False):
            if key in (Qt.Key.Key_Up, Qt.Key.Key_W, Qt.Key.Key_Down, Qt.Key.Key_S,
                       Qt.Key.Key_Left, Qt.Key.Key_A, Qt.Key.Key_Right, Qt.Key.Key_D):
                self.controller.stop_manual_continuous()
                event.accept()
                return

        super().keyReleaseEvent(event)


    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Release input, stop motion, and terminate background workers."""
        logger.info("[GUI] Closing window, stopping threads...")
        self.camera_view.release_mouse_control()
        self.controller.stop()

        if self.serial_thread.isRunning():
            # Give the priority STOP a short opportunity to leave the queue.
            time.sleep(0.03)
            self.serial_thread.stop()
        else:
            self.serial_thread.disconnect_serial()

        if self.vision_thread.isRunning() and not self.vision_thread.stop(5000):
            logger.error("[GUI] Vision thread failed to exit in 5s, aborting close")
            QMessageBox.warning(
                self,
                "Close Incomplete",
                "Camera thread is still releasing resources. Window close aborted. Try again.",
            )
            if a0 is not None:
                a0.ignore()
            return

        if a0 is not None:
            a0.accept()


