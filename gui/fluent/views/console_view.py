# -*- coding: utf-8 -*-
"""
实时监控与主作战操控台 (Console View) - 极致对齐与现代美化版

布局特点：
1. 沉浸式大视窗：主视频流 + 准星 HUD + FPS 鼠标操控。
2. 顶部遥测状态栏 (Telemetry Header)：所有状态胶囊水平绝对居中对齐，杜绝错位。
3. 底部统一基准动作条 (Standardized Action Bar)：每列均采用统一规格标签 + 统一 36px 高度控件，所有按钮坐落在同一水平基准线。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QFrame
)
from qfluentwidgets import (
    CardWidget, SimpleCardWidget, PushButton, PrimaryPushButton,
    TogglePushButton, SwitchButton, ComboBox, Slider,
    FluentIcon, InfoBar, InfoBarPosition,
    CaptionLabel, StrongBodyLabel
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
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # ==========================================
        # 1. 顶部遥测与状态药丸条 (Telemetry Header)
        # ==========================================
        telemetry_card = SimpleCardWidget()
        telemetry_layout = QHBoxLayout(telemetry_card)
        telemetry_layout.setContentsMargins(16, 6, 16, 6)
        telemetry_layout.setSpacing(14)
        telemetry_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 串口状态胶囊
        self.serial_badge = QLabel("● 串口: 未连接")
        self.serial_badge.setFixedHeight(26)
        self.serial_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.serial_badge.setStyleSheet("""
            QLabel {
                background-color: #334155;
                color: #94a3b8;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 12px;
                border-radius: 13px;
            }
        """)
        telemetry_layout.addWidget(self.serial_badge)

        telemetry_layout.addSpacing(6)

        # 帧率与视觉状态
        self.fps_label = QLabel("FPS: -- | Res: ---")
        self.fps_label.setFixedHeight(26)
        self.fps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fps_label.setStyleSheet("color: #94a3b8; font-family: 'Segoe UI', monospace; font-size: 12px; font-weight: 500;")
        telemetry_layout.addWidget(self.fps_label)

        telemetry_layout.addSpacing(6)

        # 目标相对偏差
        self.target_label = QLabel("Target Δ: [0.0°, 0.0°]")
        self.target_label.setFixedHeight(26)
        self.target_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.target_label.setStyleSheet("color: #38bdf8; font-family: 'Segoe UI', monospace; font-size: 12px; font-weight: 600;")
        telemetry_layout.addWidget(self.target_label)

        telemetry_layout.addStretch()

        # 激光安全状态胶囊
        self.laser_badge = QLabel("LASER SAFE")
        self.laser_badge.setFixedHeight(26)
        self.laser_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.laser_badge.setStyleSheet("""
            QLabel {
                background-color: #065f46;
                color: #34d399;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 14px;
                border-radius: 13px;
            }
        """)
        telemetry_layout.addWidget(self.laser_badge)

        main_layout.addWidget(telemetry_card)

        # ==========================================
        # 2. 核心大视窗：视频流与 HUD (Camera View)
        # ==========================================
        self.camera_view = CameraView()
        self.camera_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.camera_view, 1)

        # ==========================================
        # 3. 底部统一基线控制架 (Quick Action Control Rack)
        # ==========================================
        action_card = CardWidget()
        action_layout = QHBoxLayout(action_card)
        action_layout.setContentsMargins(16, 12, 16, 12)
        action_layout.setSpacing(16)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # --- 列 1: 模式选择器 ---
        col_mode = self._create_control_column("工作模式 / Mode")
        self.mode_combo = ComboBox()
        self.mode_combo.setFixedHeight(36)
        self.mode_combo.setMinimumWidth(170)
        self.mode_combo.addItems([
            "待机 (IDLE)",
            "蓝色物体追踪 (Color)",
            "YOLO 国防追踪 (Defense YOLO)",
            "FPS 鼠标手动瞄准 (Mouse Aim)",
            "测试与仿真 (Test Mode)"
        ])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        col_mode.addWidget(self.mode_combo)
        action_layout.addLayout(col_mode)

        # --- 列 2: 追踪使能按钮 ---
        col_track = self._create_control_column("自动追踪 / Track")
        self.btn_track = TogglePushButton(FluentIcon.PLAY, "开始追踪")
        self.btn_track.setFixedHeight(36)
        self.btn_track.setMinimumWidth(110)
        self.btn_track.toggled.connect(self._on_track_toggled)
        col_track.addWidget(self.btn_track)
        action_layout.addLayout(col_track)

        # --- 分隔线 ---
        action_layout.addWidget(self._create_v_separator())

        # --- 列 3: 激光保险解锁开关 ---
        col_arm = self._create_control_column("激光保险 / Arm")
        self.switch_arm = SwitchButton()
        self.switch_arm.setFixedHeight(36)
        self.switch_arm.setOnText("ARMED")
        self.switch_arm.setOffText("SAFE")
        self.switch_arm.checkedChanged.connect(self._on_arm_toggled)
        col_arm.addWidget(self.switch_arm)
        action_layout.addLayout(col_arm)

        # --- 列 4: 激光点射按钮 ---
        col_fire = self._create_control_column("激光击发 / Fire")
        self.btn_fire = PrimaryPushButton(FluentIcon.MESSAGE, "击发 (Space)")
        self.btn_fire.setFixedHeight(36)
        self.btn_fire.setMinimumWidth(115)
        self.btn_fire.setEnabled(False)
        self.btn_fire.setStyleSheet("""
            PrimaryPushButton {
                background-color: #f43f5e;
                border: 1px solid #e11d48;
                font-weight: bold;
            }
            PrimaryPushButton:hover {
                background-color: #e11d48;
            }
            PrimaryPushButton:pressed {
                background-color: #be123c;
            }
            PrimaryPushButton:disabled {
                background-color: #334155;
                color: #64748b;
                border: 1px solid #1e293b;
            }
        """)
        self.btn_fire.pressed.connect(lambda: self.laser_fire_changed.emit(True))
        self.btn_fire.released.connect(lambda: self.laser_fire_changed.emit(False))
        col_fire.addWidget(self.btn_fire)
        action_layout.addLayout(col_fire)

        # --- 列 5: 激光 PWM 功率 ---
        col_pwr = self._create_control_column("功率 / PWM: 100%")
        self.pwr_label = col_pwr.itemAt(0).widget()  # 获取刚才生成的标签用于动态更新
        self.pwr_slider = Slider(Qt.Orientation.Horizontal)
        self.pwr_slider.setFixedHeight(36)
        self.pwr_slider.setRange(0, 100)
        self.pwr_slider.setValue(100)
        self.pwr_slider.setFixedWidth(100)
        self.pwr_slider.valueChanged.connect(self._on_power_slider_changed)
        col_pwr.addWidget(self.pwr_slider)
        action_layout.addLayout(col_pwr)

        # --- 分隔线 ---
        action_layout.addWidget(self._create_v_separator())

        # --- 列 6: 一键回中 ---
        col_center = self._create_control_column("云台动作 / Origin")
        self.btn_center = PushButton(FluentIcon.SYNC, "坐标回中")
        self.btn_center.setFixedHeight(36)
        self.btn_center.setMinimumWidth(100)
        self.btn_center.clicked.connect(self.reset_requested.emit)
        col_center.addWidget(self.btn_center)
        action_layout.addLayout(col_center)

        # --- 列 7: 紧急停止 (E-STOP) ---
        col_estop = self._create_control_column("紧急停机 / Safe")
        self.btn_estop = PrimaryPushButton(FluentIcon.CANCEL, "🛑 急停 (ESC)")
        self.btn_estop.setFixedHeight(36)
        self.btn_estop.setMinimumWidth(125)
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
        col_estop.addWidget(self.btn_estop)
        action_layout.addLayout(col_estop)

        main_layout.addWidget(action_card)

    def _create_control_column(self, label_text: str) -> QVBoxLayout:
        """创建统一高度与对齐方式的标准控制列"""
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl = CaptionLabel(label_text)
        lbl.setFixedHeight(16)
        lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")
        vbox.addWidget(lbl)
        return vbox

    def _create_v_separator(self) -> QFrame:
        """创建垂直分隔线"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #334155; max-height: 40px; margin-top: 10px;")
        return line

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
            self.btn_track.setText("停止追踪")
            self.btn_track.setIcon(FluentIcon.PAUSE)
        else:
            self.btn_track.setText("开始追踪")
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
                padding: 2px 14px;
                border-radius: 13px;
            """)
        else:
            self.laser_badge.setText("LASER SAFE")
            self.laser_badge.setStyleSheet("""
                background-color: #065f46;
                color: #34d399;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 14px;
                border-radius: 13px;
            """)
        self.laser_armed_toggled.emit(checked)

    def _on_power_slider_changed(self, value: int):
        if hasattr(self, 'pwr_label') and isinstance(self.pwr_label, QLabel):
            self.pwr_label.setText(f"功率 / PWM: {value}%")
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
                padding: 2px 14px;
                border-radius: 13px;
            """)
        elif self.laser_armed:
            self.laser_badge.setText("LASER ARMED")
            self.laser_badge.setStyleSheet("""
                background-color: #991b1b;
                color: #fca5a5;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 14px;
                border-radius: 13px;
            """)
        else:
            self.laser_badge.setText("LASER SAFE")
            self.laser_badge.setStyleSheet("""
                background-color: #065f46;
                color: #34d399;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 14px;
                border-radius: 13px;
            """)

    def update_serial_status(self, connected: bool, message: str):
        if connected:
            self.serial_badge.setText(f"● 串口: 已连接 ({message})")
            self.serial_badge.setStyleSheet("""
                background-color: #14532d;
                color: #86efac;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 12px;
                border-radius: 13px;
            """)
        else:
            self.serial_badge.setText("● 串口: 未连接")
            self.serial_badge.setStyleSheet("""
                background-color: #334155;
                color: #94a3b8;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 12px;
                border-radius: 13px;
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
