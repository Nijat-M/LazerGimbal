# -*- coding: utf-8 -*-
"""
设备连接与系统设置视图 (Settings View)

模块包含：
1. STM32 原生 USB 串口通信管理卡片
2. 工业摄像头采集与画面翻转配置卡片
3. 手控鼠标瞄准灵敏度卡片
4. 现代主题外观 (暗黑/亮色/毛玻璃) 与系统偏好卡片
"""

import os
import serial.tools.list_ports
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea
)
from qfluentwidgets import (
    HeaderCardWidget, PushButton, PrimaryPushButton,
    ComboBox, Slider, DoubleSpinBox, SwitchButton,
    FluentIcon, BodyLabel, CaptionLabel, InfoBar, InfoBarPosition,
    setTheme, Theme, isDarkTheme
)

from config import cfg
from config.vision_config import VisionConfig
from config.control_config import ControlConfig
from gui.fluent.common.event_filters import apply_wheel_protection


class SettingsView(QWidget):
    """设备与系统设置视图"""

    # 串口信号
    serial_connection_toggled = pyqtSignal(bool, str)    # (checked, port_name)

    # 相机信号
    camera_changed = pyqtSignal(int, int, int)           # (cam_id, w, h)
    camera_toggled = pyqtSignal(bool)                    # 开关
    flip_changed = pyqtSignal(str)                       # NONE/180/V/H
    open_camera_settings_requested = pyqtSignal()        # DirectShow 对话框

    # 鼠标手控信号
    mouse_sensitivity_changed = pyqtSignal(float)

    def __init__(self, default_port=None, default_cam_id=0, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsView")
        self.default_port = default_port or cfg.SERIAL_PORT
        self.default_cam_id = default_cam_id
        self.is_serial_connected = False
        self.is_camera_running = False

        self.init_ui()
        apply_wheel_protection(self)

        # 延迟异步刷新可用端口和相机
        QTimer.singleShot(300, self.refresh_serial_ports)
        QTimer.singleShot(600, self.detect_cameras)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        cards_layout = QVBoxLayout(content)
        cards_layout.setContentsMargins(0, 0, 10, 0)
        cards_layout.setSpacing(16)

        # ==========================================
        # 卡片 1: STM32 USB 串口通信 (CardWidget)
        # ==========================================
        serial_card = HeaderCardWidget(self)
        serial_card.setTitle("🔌 STM32 USB 硬件通信 (Serial & CDC)")
        serial_layout = QVBoxLayout(serial_card)
        serial_layout.setContentsMargins(16, 14, 16, 16)
        serial_layout.setSpacing(12)

        # 端口选择
        port_h = QHBoxLayout()
        port_label = BodyLabel("通信端口 (COM Port):", self)
        self.combo_port = ComboBox(self)
        self.combo_port.setMinimumWidth(260)
        self.btn_refresh_ports = PushButton(FluentIcon.SYNC, "刷新", self)
        self.btn_refresh_ports.clicked.connect(self.refresh_serial_ports)

        port_h.addWidget(port_label)
        port_h.addStretch()
        port_h.addWidget(self.combo_port)
        port_h.addWidget(self.btn_refresh_ports)
        serial_layout.addLayout(port_h)

        # 波特率
        baud_h = QHBoxLayout()
        baud_label = BodyLabel("波特率 (Baud Rate):", self)
        self.combo_baud = ComboBox(self)
        self.combo_baud.addItems(["115200", "921600", "460800", "230400", "57600"])
        self.combo_baud.setCurrentText(str(cfg.BAUD_RATE))
        self.combo_baud.setMinimumWidth(160)
        baud_h.addWidget(baud_label)
        baud_h.addStretch()
        baud_h.addWidget(self.combo_baud)
        serial_layout.addLayout(baud_h)

        # 串口连接按钮
        conn_h = QHBoxLayout()
        self.serial_status_desc = CaptionLabel("状态: 未连接", self)
        self.btn_serial_connect = PrimaryPushButton(FluentIcon.CONNECT, "连接串口", self)
        self.btn_serial_connect.clicked.connect(self._on_serial_connect_clicked)
        conn_h.addWidget(self.serial_status_desc)
        conn_h.addStretch()
        conn_h.addWidget(self.btn_serial_connect)
        serial_layout.addLayout(conn_h)

        cards_layout.addWidget(serial_card)

        # ==========================================
        # 卡片 2: 工业摄像头与视觉采集 (CardWidget)
        # ==========================================
        cam_card = HeaderCardWidget(self)
        cam_card.setTitle("📷 工业摄像头与图像采集 (Vision Pipeline)")
        cam_layout = QVBoxLayout(cam_card)
        cam_layout.setContentsMargins(16, 14, 16, 16)
        cam_layout.setSpacing(12)

        # 摄像头选择
        cam_sel_h = QHBoxLayout()
        cam_sel_label = BodyLabel("视频设备 (Camera ID):", self)
        self.combo_camera = ComboBox(self)
        self.combo_camera.setMinimumWidth(220)
        self.btn_detect_cams = PushButton(FluentIcon.SYNC, "检测", self)
        self.btn_detect_cams.clicked.connect(self.detect_cameras)
        cam_sel_h.addWidget(cam_sel_label)
        cam_sel_h.addStretch()
        cam_sel_h.addWidget(self.combo_camera)
        cam_sel_h.addWidget(self.btn_detect_cams)
        cam_layout.addLayout(cam_sel_h)

        # 分辨率与帧率
        res_h = QHBoxLayout()
        res_label = BodyLabel("采集分辨率与帧率预设:", self)
        self.combo_resolution = ComboBox(self)
        self.combo_resolution.addItems([
            "640x480 (60 FPS - 极致低延迟)",
            "1280x720 (60 FPS - 高清 HD)",
            "1920x1080 (60 FPS - 全高清 FHD)"
        ])
        self.combo_resolution.setCurrentIndex(0)
        self.combo_resolution.setMinimumWidth(260)
        res_h.addWidget(res_label)
        res_h.addStretch()
        res_h.addWidget(self.combo_resolution)
        cam_layout.addLayout(res_h)

        # 画面镜像与翻转
        flip_h = QHBoxLayout()
        flip_label = BodyLabel("画面方向 / 镜像反转:", self)
        self.combo_flip = ComboBox(self)
        self.combo_flip.addItem("正常 (Normal 0°)", "NONE")
        self.combo_flip.addItem("180° 旋转 (Inverted)", "180")
        self.combo_flip.addItem("垂直翻转 (Vertical)", "V")
        self.combo_flip.addItem("水平镜像 (Horizontal)", "H")
        self.combo_flip.currentIndexChanged.connect(self._on_flip_changed)
        self.combo_flip.setMinimumWidth(200)
        flip_h.addWidget(flip_label)
        flip_h.addStretch()
        flip_h.addWidget(self.combo_flip)
        cam_layout.addLayout(flip_h)

        # 摄像头操作按钮
        cam_btns_h = QHBoxLayout()
        self.btn_cam_toggle = PushButton(FluentIcon.PLAY, "启动视频流", self)
        self.btn_cam_toggle.clicked.connect(self._on_cam_toggle_clicked)

        self.btn_cam_apply = PrimaryPushButton(FluentIcon.ACCEPT, "应用分辨率与设置", self)
        self.btn_cam_apply.clicked.connect(self._on_cam_apply_clicked)

        self.btn_cam_hw_settings = PushButton(FluentIcon.SETTING, "相机曝光/增益驱动面板", self)
        self.btn_cam_hw_settings.clicked.connect(self.open_camera_settings_requested.emit)

        cam_btns_h.addWidget(self.btn_cam_toggle)
        cam_btns_h.addWidget(self.btn_cam_apply)
        cam_btns_h.addWidget(self.btn_cam_hw_settings)
        cam_layout.addLayout(cam_btns_h)

        cards_layout.addWidget(cam_card)

        # ==========================================
        # 卡片 3: 手控鼠标瞄准与输入灵敏度 (CardWidget)
        # ==========================================
        input_card = HeaderCardWidget(self)
        input_card.setTitle("🎯 手控瞄准灵敏度与输入偏好 (Control & Sensitivity)")
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(16, 14, 16, 16)
        input_layout.setSpacing(12)

        sens_v = QVBoxLayout()
        sens_header = QHBoxLayout()
        sens_label = BodyLabel("FPS 鼠标手控相对灵敏度 (Sensitivity):", self)
        self.sens_spin = DoubleSpinBox(self)
        self.sens_spin.setRange(0.01, 1.0)
        self.sens_spin.setSingleStep(0.01)
        self.sens_spin.setDecimals(3)
        self.sens_spin.setValue(ControlConfig.MOUSE_SENSITIVITY)
        self.sens_spin.setFixedWidth(100)
        sens_header.addWidget(sens_label)
        sens_header.addStretch()
        sens_header.addWidget(self.sens_spin)
        sens_v.addLayout(sens_header)

        self.sens_slider = Slider(Qt.Orientation.Horizontal, self)
        self.sens_slider.setRange(1, 100)
        self.sens_slider.setValue(int(ControlConfig.MOUSE_SENSITIVITY * 100))
        self.sens_slider.valueChanged.connect(self._on_sens_slider_changed)
        self.sens_spin.valueChanged.connect(self._on_sens_spin_changed)
        sens_v.addWidget(self.sens_slider)
        input_layout.addLayout(sens_v)

        cards_layout.addWidget(input_card)

        # ==========================================
        # 卡片 4: 现代 UI 主题与系统外观 (CardWidget)
        # ==========================================
        theme_card = HeaderCardWidget(self)
        theme_card.setTitle("🎨 系统外观与主题 (Appearance & Theme)")
        theme_layout = QVBoxLayout(theme_card)
        theme_layout.setContentsMargins(16, 14, 16, 16)
        theme_layout.setSpacing(12)

        theme_h = QHBoxLayout()
        theme_label = BodyLabel("界面色彩主题:", self)
        self.combo_theme = ComboBox(self)
        self.combo_theme.addItems(["暗黑模式 (Dark Mode)", "明亮模式 (Light Mode)", "跟随系统 (Auto)"])
        self.combo_theme.setCurrentIndex(0)
        self.combo_theme.currentIndexChanged.connect(self._on_theme_changed)
        self.combo_theme.setMinimumWidth(200)
        theme_h.addWidget(theme_label)
        theme_h.addStretch()
        theme_h.addWidget(self.combo_theme)
        theme_layout.addLayout(theme_h)

        cards_layout.addWidget(theme_card)
        cards_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def refresh_serial_ports(self):
        """刷新非蓝牙串口列表"""
        current_data = self.combo_port.currentData()
        self.combo_port.clear()

        all_ports = list(serial.tools.list_ports.comports())
        valid_ports = []
        for p in all_ports:
            is_bt = ("BTHENUM" in str(p.hwid)) or ("蓝牙" in str(p.description)) or ("Bluetooth" in str(p.description))
            if not is_bt:
                valid_ports.append(p)

        if not valid_ports:
            self.combo_port.addItem("未检测到有效 USB 设备", None)
            return

        stm32_idx = -1
        for idx, p in enumerate(valid_ports):
            is_stm32 = (p.vid == 0x0483 and p.pid == 0x5740) or ("STMicroelectronics" in str(p.description)) or ("0483:5740" in str(p.hwid))
            if is_stm32:
                label = f"{p.device} (⚡ STM32 USB CDC)"
                if stm32_idx == -1:
                    stm32_idx = idx
            else:
                desc = str(p.description).split("(")[0].strip()
                label = f"{p.device} ({desc[:18]})"
            self.combo_port.addItem(label, p.device)

        if current_data is not None:
            found = self.combo_port.findData(current_data)
            if found >= 0:
                self.combo_port.setCurrentIndex(found)
            elif stm32_idx >= 0:
                self.combo_port.setCurrentIndex(stm32_idx)
        elif stm32_idx >= 0:
            self.combo_port.setCurrentIndex(stm32_idx)

    def detect_cameras(self):
        """检测可用摄像头"""
        import cv2
        self.combo_camera.clear()
        found_any = False
        for idx in range(4):
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                self.combo_camera.addItem(f"Camera #{idx} (DirectShow)", idx)
                cap.release()
                found_any = True
        if not found_any:
            self.combo_camera.addItem("Default Camera #0", 0)

    def _on_serial_connect_clicked(self):
        port = self.combo_port.currentData()
        if not port:
            InfoBar.warning(
                title="无法连接",
                content="请选择有效的串口设备！",
                position=InfoBarPosition.TOP,
                parent=self
            )
            return

        target_state = not self.is_serial_connected
        self.serial_connection_toggled.emit(target_state, port)

    def set_serial_status(self, connected: bool, message: str):
        self.is_serial_connected = connected
        if connected:
            self.btn_serial_connect.setText("断开串口")
            self.btn_serial_connect.setIcon(FluentIcon.CLOSE)
            self.serial_status_desc.setText(f"状态: 已连接 ({message})")
            self.serial_status_desc.setStyleSheet("color: #4ade80;")
        else:
            self.btn_serial_connect.setText("连接串口")
            self.btn_serial_connect.setIcon(FluentIcon.CONNECT)
            self.serial_status_desc.setText(f"状态: 未连接 ({message})")
            self.serial_status_desc.setStyleSheet("color: #94a3b8;")

    def _on_cam_toggle_clicked(self):
        target = not self.is_camera_running
        self.camera_toggled.emit(target)

    def set_camera_running_status(self, running: bool):
        self.is_camera_running = running
        if running:
            self.btn_cam_toggle.setText("停止视频流")
            self.btn_cam_toggle.setIcon(FluentIcon.PAUSE)
        else:
            self.btn_cam_toggle.setText("启动视频流")
            self.btn_cam_toggle.setIcon(FluentIcon.PLAY)

    def _on_cam_apply_clicked(self):
        cam_id = self.combo_camera.currentData()
        if cam_id is None:
            cam_id = 0
        res_idx = self.combo_resolution.currentIndex()
        resolutions = [(640, 480), (1280, 720), (1920, 1080)]
        w, h = resolutions[res_idx] if 0 <= res_idx < len(resolutions) else (640, 480)
        self.camera_changed.emit(cam_id, w, h)
        InfoBar.success(
            title="摄像头设置已应用",
            content=f"已切换至 Camera #{cam_id} @ {w}x{h}",
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def _on_flip_changed(self, index: int):
        flip_mode = self.combo_flip.itemData(index) or "NONE"
        self.flip_changed.emit(flip_mode)

    def _on_sens_slider_changed(self, val: int):
        sens = val / 100.0
        self.sens_spin.setValue(sens)
        self.mouse_sensitivity_changed.emit(sens)

    def _on_sens_spin_changed(self, val: float):
        self.sens_slider.setValue(int(val * 100))
        self.mouse_sensitivity_changed.emit(val)

    def _on_theme_changed(self, index: int):
        if index == 0:
            setTheme(Theme.DARK)
        elif index == 1:
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.AUTO)
