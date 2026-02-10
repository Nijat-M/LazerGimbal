# -*- coding: utf-8 -*-
"""
主窗口 - 重构版 (Main Window - Refactored)

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
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QMessageBox
)
from PyQt6.QtCore import pyqtSlot

# 导入核心模块
try:
    from config import cfg
    from core.serial_thread import SerialThread
    from core.gimbal_controller import GimbalController
    from vision.worker import VisionWorker
    from gui.test_panel import TestModePanel
    from gui.widgets import (
        CameraView, SerialPanel, ModePanel, 
        PIDTuner, ControlPanel
    )
except ImportError:
    sys.path.append("..")
    from config import cfg
    from core.serial_thread import SerialThread
    from core.gimbal_controller import GimbalController
    from vision.worker import VisionWorker
    from gui.test_panel import TestModePanel
    from gui.widgets import (
        CameraView, SerialPanel, ModePanel, 
        PIDTuner, ControlPanel
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
        self.setWindowTitle("LaserGimbal Pro - 激光云台控制系统 v2.0")
        self.resize(1000, 700)

        # [核心线程和控制器]
        self.serial_thread = SerialThread()
        self.vision_thread = VisionWorker()
        self.controller = GimbalController(self.serial_thread)

        # [初始化]
        self.init_ui()
        self.init_signals()

        # 启动视觉线程
        self.vision_thread.start()

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
        # 右侧：控制面板
        # ==========================
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)

        # 1. 串口连接面板
        self.serial_panel = SerialPanel(default_port=cfg.SERIAL_PORT)
        right_layout.addWidget(self.serial_panel)

        # 2. 模式选择面板
        self.mode_panel = ModePanel()
        right_layout.addWidget(self.mode_panel)

        # 3. PID 调参面板
        self.pid_tuner = PIDTuner(
            initial_kp=cfg.PID_KP,
            initial_ki=cfg.PID_KI,
            initial_kd=cfg.PID_KD,
            invert_x=cfg.INVERT_X,
            invert_y=cfg.INVERT_Y
        )
        right_layout.addWidget(self.pid_tuner)

        # 4. 控制按钮面板
        self.control_panel = ControlPanel()
        right_layout.addWidget(self.control_panel)

        # 5. 测试模式面板（默认隐藏）
        self.test_panel = TestModePanel()
        self.test_panel.setVisible(False)
        right_layout.addWidget(self.test_panel)

        # 状态栏
        self.status_label = QLabel("系统就绪")
        self.status_label.setStyleSheet("color: gray; padding: 5px;")
        right_layout.addWidget(self.status_label)
        
        right_layout.addStretch()
        main_layout.addLayout(right_layout, 1)

    def init_signals(self):
        """连接信号与槽 - 协调各组件通信"""
        # ===== 视觉线程 =====
        # 视觉 -> 摄像头显示组件
        self.vision_thread.frame_signal.connect(self.camera_view.update_camera_feed)
        self.vision_thread.mask_signal.connect(self.camera_view.update_mask_feed)
        # 视觉 -> 控制器
        self.vision_thread.control_signal.connect(self.controller.handle_vision_error)
        
        # ===== 串口线程 =====
        self.serial_thread.connection_state_signal.connect(self.on_connection_status_changed)
        
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
        self.pid_tuner.invert_changed.connect(self.on_invert_changed)
        self.pid_tuner.save_requested.connect(self.on_save_config)
        self.pid_tuner.reset_requested.connect(self.on_reset_pid)
        
        # 控制面板
        self.control_panel.control_toggled.connect(self.on_control_toggled)
        self.control_panel.reset_requested.connect(self.on_reset_position)
        
        # 测试面板
        self.test_panel.request_move_signal.connect(self.on_manual_move)

    # ==========================
    # 槽函数 (Slots) - 简化版
    # ==========================
    
    def on_serial_connection_toggled(self, checked, port):
        """串口连接切换"""
        if checked:
            print(f"[GUI] 连接串口: {port}")
            self.controller.sync_position()
            self.serial_thread.connect_serial(port, cfg.BAUD_RATE)
            self.serial_thread.start()
        else:
            print("[GUI] 断开串口")
            self.serial_thread.stop()
            self.serial_thread.disconnect_serial()
    
    def on_connection_status_changed(self, success, message):
        """串口连接状态改变"""
        print(f"[GUI] {message}")
        self.status_label.setText(message)
        
        if success:
            self.status_label.setStyleSheet("color: #00ff00; padding: 5px;")
        else:
            self.status_label.setStyleSheet("color: red; padding: 5px;")
            self.serial_panel.set_connection_status(False, message)
    
    def on_mode_changed(self, mode):
        """模式切换"""
        print(f"[GUI] 工作模式切换: {mode}")
        
        # 更新 UI 可见性
        self.test_panel.setVisible(mode == "TEST")
        
        # 视觉线程：测试模式下不需要视觉处理，设为 IDLE
        vision_mode = "IDLE" if mode == "TEST" else mode
        if mode == "TEST":
            print(f"[GUI] 视觉线程已暂停（TEST 模式下不需要视觉追踪）")
        else:
            print(f"[GUI] 视觉线程模式: {vision_mode}")
        
        self.vision_thread.set_mode(vision_mode)
        self.status_label.setText(f"模式: {mode}")
    
    def on_pid_changed(self, kp, ki, kd):
        """PID 参数改变"""
        cfg.PID_KP = kp
        cfg.PID_KI = ki
        cfg.PID_KD = kd
        self.controller.update_pid_tunings(kp, ki, kd)
    
    def on_invert_changed(self, invert_x, invert_y):
        """反转设置改变"""
        self.controller.set_invert(invert_x, invert_y)
    
    def on_save_config(self):
        """保存配置"""
        cfg.save_config()
        self.status_label.setText("✓ 配置已保存")
    
    def on_reset_pid(self):
        """重置 PID"""
        # 更新为新的默认值
        self.controller.update_pid_tunings(0.4, 0.0, 0.2)
        # 同步更新GUI滑块显示
        self.pid_tuner.set_pid_values(0.4, 0.0, 0.2)
    
    def on_control_toggled(self, checked):
        """控制开关"""
        self.controller.set_control_enabled(checked)
    
    def on_reset_position(self):
        """重置位置"""
        self.controller.sync_position()
        QMessageBox.information(
            self, 
            "重置完成", 
            "软件坐标已重置为中位 (90°, 90°)"
        )
    
    def on_manual_move(self, axis, direction):
        """手动移动（测试模式）"""
        print(f"[GUI] 收到手动移动请求: 轴={axis}, 方向={direction}")
        self.controller.manual_move(axis, direction)
    
    def update_status(self, *args):
        """更新状态栏"""
        if len(args) == 1:
            # 字符串消息
            self.status_label.setText(args[0])
        elif len(args) == 2:
            # 位置信息 (x, y)
            x, y = args
            self.status_label.setText(f"Servo: X={x:.1f}°, Y={y:.1f}°")

    def closeEvent(self, event):
        """关闭窗口时清理资源"""
        print("[GUI] 关闭窗口，停止线程...")
        
        # 停止视觉线程
        self.vision_thread.is_running = False
        self.vision_thread.wait()
        
        # 停止串口线程
        if self.serial_thread.isRunning():
            self.serial_thread.stop()
            self.serial_thread.wait()
        
        event.accept()

