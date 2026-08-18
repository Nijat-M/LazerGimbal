# -*- coding: utf-8 -*-
"""
实时监控与主作战操控台 (Console View)

布局特点：
1. 沉浸式大视窗：主视频流 + 准星 HUD + FPS 鼠标操控。
2. 顶部遥测状态栏 (Telemetry Header)：显示串口、帧率、激光状态、目标坐标等关键指标。
3. 底部快捷动作条 (Quick Action Bar)：模式切换、激光安全锁、击发、一键回中、急停。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
)
from qfluentwidgets import (
    CardWidget, SimpleCardWidget, PushButton, PrimaryPushButton,
    TogglePushButton, SwitchButton, ComboBox, Slider,
    FluentIcon, InfoBar, InfoBarPosition,
    StrongBodyLabel, CaptionLabel
)

from gui.widgets.camera_view import CameraView
from gui.fluent.common.event_filters import apply_wheel_protection


class ConsoleView(QWidget):
    """主作战操控台视图"""

    # 控制信号
    control_toggled = pyqtSignal(bool)
    mode_changed = pyqtSignal(str)
    reset_requested = pyqtSignal()
    emergency_stop_requested = pyqtSignal()
    
    # 激光信号
    laser_armed_toggled = pyqtSignal(bool)
    laser_fire_changed = pyqtSignal(bool)
    laser_power_changed = pyqtSignal(int)
    
    # YOLO 扩展信号
    yolo_model_changed = pyqtSignal(str)
    yolo_class_changed = pyqtSignal(object)
    yolo_conf_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConsoleView")
        self.laser_armed = False
        self.laser_firing = False
        self.init_ui()
        apply_wheel_protection(self)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # ==========================
        # 1. 顶部遥测与状态药丸条 (Telemetry Bar)
        # ==========================
        telemetry_card = SimpleCardWidget()
        telemetry_layout = QHBoxLayout(telemetry_card)
        telemetry_layout.setContentsMargins(16, 8, 16, 8)
        telemetry_layout.setSpacing(14)

        # 串口状态胶囊
        self.serial_badge = QLabel("● 串口: 未连接")
        self.serial_badge.setStyleSheet("""
            QLabel {
                background-color: #334155;
                color: #94a3b8;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 12px;
            }
        """)
        telemetry_layout.addWidget(self.serial_badge)

        telemetry_layout.addSpacing(6)

        # 帧率与视觉状态
        self.fps_label = CaptionLabel("FPS: -- | Res: ---")
        self.fps_label.setStyleSheet("color: #94a3b8; font-family: monospace; font-size: 12px;")
        telemetry_layout.addWidget(self.fps_label)

        telemetry_layout.addSpacing(6)

        # 目标相对偏差
        self.target_label = CaptionLabel("Target Δ: [0.0°, 0.0°]")
        self.target_label.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 12px;")
        telemetry_layout.addWidget(self.target_label)

        telemetry_layout.addStretch()

        # 激光安全状态胶囊
        self.laser_badge = QLabel("LASER SAFE")
        self.laser_badge.setStyleSheet("""
            QLabel {
                background-color: #065f46;
                color: #34d399;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
                border-radius: 12px;
            }
        """)
        telemetry_layout.addWidget(self.laser_badge)

        main_layout.addWidget(telemetry_card)

        # ==========================
        # 2. 核心大视窗：视频流与 HUD (Camera View)
        # ==========================
        self.camera_view = CameraView()
        self.camera_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.camera_view, 1)

        # ==========================
        # 3. 底部快捷动作条 (Quick Action Bar)
        # ==========================
        action_card = CardWidget()
        action_layout = QHBoxLayout(action_card)
        action_layout.setContentsMargins(14, 10, 14, 10)
        action_layout.setSpacing(12)

        # --- 模式选择器 ---
        mode_box = QVBoxLayout()
        mode_box.setSpacing(2)
        mode_title = CaptionLabel("工作模式 / Mode")
        self.mode_combo = ComboBox()
        self.mode_combo.addItems([
            "待机 (IDLE)",
            "蓝色物体追踪 (Color)",
            "YOLO 国防追踪 (Defense YOLO)",
            "FPS 鼠标手动瞄准 (Mouse Aim)",
            "测试与仿真 (Test Mode)"
        ])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        self.mode_combo.setMinimumWidth(180)
        mode_box.addWidget(mode_title)
        mode_box.addWidget(self.mode_combo)
        action_layout.addLayout(mode_box)

        action_layout.addSpacing(6)

        # --- 追踪使能按钮 ---
        self.btn_track = TogglePushButton(FluentIcon.PLAY, "开始追踪 / Track")
        self.btn_track.setMinimumHeight(38)
        self.btn_track.toggled.connect(self._on_track_toggled)
        action_layout.addWidget(self.btn_track)

        # --- 激光保险解锁开关 ---
        arm_box = QVBoxLayout()
        arm_box.setSpacing(2)
        arm_title = CaptionLabel("激光保险 / Arm")
        arm_h = QHBoxLayout()
        self.switch_arm = SwitchButton()
        self.switch_arm.setOnText("ARMED")
        self.switch_arm.setOffText("SAFE")
        self.switch_arm.checkedChanged.connect(self._on_arm_toggled)
        arm_h.addWidget(self.switch_arm)
        arm_box.addWidget(arm_title)
        arm_box.addLayout(arm_h)
        action_layout.addLayout(arm_box)

        # --- 激光点射按钮 ---
        self.btn_fire = PrimaryPushButton(FluentIcon.MESSAGE, "击发 (Space)")
        self.btn_fire.setMinimumHeight(38)
        self.btn_fire.setEnabled(False)
        self.btn_fire.setStyleSheet("""
            PrimaryPushButton {
                background-color: #f43f5e;
                border: 1px solid #e11d48;
            }
            PrimaryPushButton:hover {
                background-color: #e11d48;
            }
            PrimaryPushButton:pressed {
                background-color: #be123c;
            }
            PrimaryPushButton:disabled {
                background-color: #475569;
                border: 1px solid #334155;
            }
        """)
        self.btn_fire.pressed.connect(lambda: self.laser_fire_changed.emit(True))
        self.btn_fire.released.connect(lambda: self.laser_fire_changed.emit(False))
        action_layout.addWidget(self.btn_fire)

        # --- 激光功率调节 (PWM 0~100%) ---
        pwr_box = QVBoxLayout()
        pwr_box.setSpacing(2)
        self.pwr_label = CaptionLabel("激光功率: 100%")
        self.pwr_slider = Slider(Qt.Orientation.Horizontal)
        self.pwr_slider.setRange(0, 100)
        self.pwr_slider.setValue(100)
        self.pwr_slider.setFixedWidth(110)
        self.pwr_slider.valueChanged.connect(self._on_power_slider_changed)
        pwr_box.addWidget(self.pwr_label)
        pwr_box.addWidget(self.pwr_slider)
        action_layout.addLayout(pwr_box)

        action_layout.addSpacing(6)

        # --- 一键回中 ---
        self.btn_center = PushButton(FluentIcon.SYNC, "回中 / Center")
        self.btn_center.setMinimumHeight(38)
        self.btn_center.clicked.connect(self.reset_requested.emit)
        action_layout.addWidget(self.btn_center)

        # --- 紧急停止 (E-STOP) ---
        self.btn_estop = PrimaryPushButton(FluentIcon.CANCEL, "🛑 急停 (ESC)")
        self.btn_estop.setMinimumHeight(38)
        self.btn_estop.setStyleSheet("""
            PrimaryPushButton {
                background-color: #b91c1c;
                border: 1px solid #991b1b;
                font-weight: bold;
            }
            PrimaryPushButton:hover {
                background-color: #dc2626;
            }
            PrimaryPushButton:pressed {
                background-color: #991b1b;
            }
        """)
        self.btn_estop.clicked.connect(self.emergency_stop_requested.emit)
        action_layout.addWidget(self.btn_estop)

        main_layout.addWidget(action_card)

    def _on_mode_combo_changed(self, index: int):
        mode_keys = ["IDLE", "BLUE_OBJECT", "YOLO_DEFENSE", "MOUSE_MANUAL", "TEST"]
        if 0 <= index < len(mode_keys):
            target_mode = mode_keys[index]
            self.mode_changed.emit(target_mode)
            if target_mode == "MOUSE_MANUAL":
                InfoBar.info(
                    title="鼠标手控模式已就绪",
                    content="直接点击主视频区域即可锁定鼠标，按 ESC 释放捕获。",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3500,
                    parent=self
                )

    def _on_track_toggled(self, checked: bool):
        if checked:
            self.btn_track.setText("停止追踪 / Stop")
            self.btn_track.setIcon(FluentIcon.PAUSE)
        else:
            self.btn_track.setText("开始追踪 / Track")
            self.btn_track.setIcon(FluentIcon.PLAY)
        self.control_toggled.emit(checked)

    def _on_arm_toggled(self, checked: bool):
        self.laser_armed = checked
        self.btn_fire.setEnabled(checked)
        if checked:
            self.laser_badge.setText("LASER ARMED")
            self.laser_badge.setStyleSheet("""
                background-color: #991b1b;
                color: #fca5a5;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
                border-radius: 12px;
            """)
        else:
            self.laser_badge.setText("LASER SAFE")
            self.laser_badge.setStyleSheet("""
                background-color: #065f46;
                color: #34d399;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
                border-radius: 12px;
            """)
        self.laser_armed_toggled.emit(checked)

    def _on_power_slider_changed(self, value: int):
        self.pwr_label.setText(f"激光功率: {value}%")
        self.laser_power_changed.emit(value)

    def set_laser_firing_visual(self, firing: bool):
        """设置开火高亮状态"""
        self.laser_firing = firing
        if firing:
            self.laser_badge.setText("⚡ FIRING ⚡")
            self.laser_badge.setStyleSheet("""
                background-color: #d97706;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
                border-radius: 12px;
            """)
        elif self.laser_armed:
            self.laser_badge.setText("LASER ARMED")
            self.laser_badge.setStyleSheet("""
                background-color: #991b1b;
                color: #fca5a5;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
                border-radius: 12px;
            """)
        else:
            self.laser_badge.setText("LASER SAFE")
            self.laser_badge.setStyleSheet("""
                background-color: #065f46;
                color: #34d399;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
                border-radius: 12px;
            """)

    def update_serial_status(self, connected: bool, message: str):
        if connected:
            self.serial_badge.setText(f"● 串口: 已连接 ({message})")
            self.serial_badge.setStyleSheet("""
                background-color: #14532d;
                color: #86efac;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 12px;
            """)
        else:
            self.serial_badge.setText("● 串口: 未连接")
            self.serial_badge.setStyleSheet("""
                background-color: #334155;
                color: #94a3b8;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 12px;
            """)

    def update_telemetry(self, fps: float, res_str: str, target_dx: float = 0.0, target_dy: float = 0.0):
        self.fps_label.setText(f"FPS: {fps:.1f} | Res: {res_str}")
        self.target_label.setText(f"Target Δ: [{target_dx:+.1f}°, {target_dy:+.1f}°]")

    def handle_emergency_reset(self):
        """急停复位本视图各开关"""
        self.switch_arm.setChecked(False)
        self.btn_track.setChecked(False)
        self._on_arm_toggled(False)
        self._on_track_toggled(False)
