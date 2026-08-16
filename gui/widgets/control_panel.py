# -*- coding: utf-8 -*-
"""
控制与激光武器面板 (Control & Laser Weapon Panel)

包含：
- 云台追踪启动/停止控制
- 相对原点重置与急停
- 激光保险解锁 (ARM / SAFE)
- 激光发射触发 (按住发射 / 空格快捷键)
- 激光 PWM 功率无级调节 (0% ~ 100%) 与快速预设
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QGroupBox, QSlider, QLabel, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt


class ControlPanel(QWidget):
    """控制与激光武器系统面板"""
    
    # 系统控制信号
    control_toggled = pyqtSignal(bool)       # 自动追踪开关
    reset_requested = pyqtSignal()           # 归中/原点重置
    emergency_stop_requested = pyqtSignal()  # 急停信号
    
    # 激光武器控制信号
    laser_armed_toggled = pyqtSignal(bool)   # 激光保险 (ARM/SAFE)
    laser_fire_changed = pyqtSignal(bool)    # 激光击发 (True=开火, False=停火)
    laser_power_changed = pyqtSignal(int)    # 激光 PWM 功率 (0~100%)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.laser_armed = False
        self.laser_firing = False
        self.laser_power = 100
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # ==========================
        # 1. 云台控制按钮组 (水平)
        # ==========================
        control_group = QGroupBox("Gimbal Motion Control")
        control_layout = QHBoxLayout(control_group)
        control_layout.setContentsMargins(10, 10, 10, 10)
        control_layout.setSpacing(8)
        
        # 开始/停止追踪按钮
        self.btn_control = QPushButton("▶ Start Tracking")
        self.btn_control.setCheckable(True)
        self.btn_control.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: bold;
                padding: 8px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.btn_control.toggled.connect(self._on_control_toggled)
        control_layout.addWidget(self.btn_control, 2)
        
        # 停止电机并将当前位置设为软件相对原点
        self.btn_reset = QPushButton("⟲ Reset Origin")
        self.btn_reset.setToolTip("Stop motors and set current position as relative origin")
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #f8fafc;
                padding: 8px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.btn_reset.clicked.connect(self.reset_requested.emit)
        control_layout.addWidget(self.btn_reset, 1)

        # 急停按钮
        self.btn_estop = QPushButton("🛑 E-STOP")
        self.btn_estop.setToolTip("Instant Hardware Stop & Cut Laser")
        self.btn_estop.setStyleSheet("""
            QPushButton {
                background-color: #991b1b;
                color: #fee2e2;
                font-weight: bold;
                padding: 8px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        self.btn_estop.clicked.connect(self.emergency_stop_requested.emit)
        control_layout.addWidget(self.btn_estop, 1)
        
        main_layout.addWidget(control_group)

        # ==========================
        # 2. 激光武器控制系统组
        # ==========================
        laser_group = QGroupBox("Laser Weapon System (PB0 PWM + PA7 EN)")
        laser_layout = QVBoxLayout(laser_group)
        laser_layout.setContentsMargins(10, 10, 10, 10)
        laser_layout.setSpacing(8)

        # 2.1 保险与发射按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        # 保险切换按钮 (ARM / SAFE)
        self.btn_arm = QPushButton("🛡️ SAFE (LOCKED)")
        self.btn_arm.setCheckable(True)
        self.btn_arm.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                font-weight: bold;
                padding: 9px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0f172a;
            }
        """)
        self.btn_arm.toggled.connect(self._on_arm_toggled)
        btn_row.addWidget(self.btn_arm, 1)

        # 发射按键 (按住发射，松开停火)
        self.btn_fire = QPushButton("🔥 HOLD TO FIRE")
        self.btn_fire.setEnabled(False)
        self.btn_fire.setToolTip("Press and hold to fire (or hold Spacebar)")
        self.btn_fire.setStyleSheet("""
            QPushButton {
                background-color: #3f1515;
                color: #7f1d1d;
                border: 1px solid #7f1d1d;
                font-weight: bold;
                padding: 9px;
                border-radius: 4px;
            }
        """)
        self.btn_fire.pressed.connect(self._on_fire_pressed)
        self.btn_fire.released.connect(self._on_fire_released)
        btn_row.addWidget(self.btn_fire, 1)

        laser_layout.addLayout(btn_row)

        # 2.2 激光 PWM 功率无级调节滑块
        power_box = QFrame()
        power_box.setStyleSheet("background-color: #0f172a; border-radius: 4px; padding: 6px;")
        power_layout = QVBoxLayout(power_box)
        power_layout.setContentsMargins(6, 6, 6, 6)
        power_layout.setSpacing(4)

        # 标题与当前百分比显示
        title_row = QHBoxLayout()
        lbl_power_title = QLabel("⚡ PWM Power Output (PB0):")
        lbl_power_title.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        self.lbl_power_val = QLabel("100%")
        self.lbl_power_val.setStyleSheet("color: #f59e0b; font-size: 12px; font-weight: bold;")
        title_row.addWidget(lbl_power_title)
        title_row.addStretch()
        title_row.addWidget(self.lbl_power_val)
        power_layout.addLayout(title_row)

        # 滑动条
        self.slider_power = QSlider(Qt.Orientation.Horizontal)
        self.slider_power.setRange(0, 100)
        self.slider_power.setValue(100)
        self.slider_power.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #f59e0b;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #fbbf24;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
        """)
        self.slider_power.valueChanged.connect(self._on_slider_power_changed)
        power_layout.addWidget(self.slider_power)

        # 快速挡位按钮
        presets_row = QHBoxLayout()
        presets_row.setSpacing(4)

        btn_preset_10 = QPushButton("10% Aim")
        btn_preset_10.setToolTip("Low power aiming pointer")
        btn_preset_10.setStyleSheet("font-size: 10px; padding: 2px 4px;")
        btn_preset_10.clicked.connect(lambda: self.set_laser_power(10))
        presets_row.addWidget(btn_preset_10)

        btn_preset_50 = QPushButton("50% Test")
        btn_preset_50.setToolTip("Medium power alignment")
        btn_preset_50.setStyleSheet("font-size: 10px; padding: 2px 4px;")
        btn_preset_50.clicked.connect(lambda: self.set_laser_power(50))
        presets_row.addWidget(btn_preset_50)

        btn_preset_100 = QPushButton("100% Strike")
        btn_preset_100.setToolTip("Full power destruction")
        btn_preset_100.setStyleSheet("font-size: 10px; padding: 2px 4px; font-weight: bold; color: #ef4444;")
        btn_preset_100.clicked.connect(lambda: self.set_laser_power(100))
        presets_row.addWidget(btn_preset_100)

        power_layout.addLayout(presets_row)
        laser_layout.addWidget(power_box)

        # 底部操作提示
        tip_label = QLabel("Tip: Hold Spacebar anywhere to fire while Armed")
        tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip_label.setStyleSheet("color: #64748b; font-size: 10px;")
        laser_layout.addWidget(tip_label)

        main_layout.addWidget(laser_group)
    
    # --------------------------------------------------
    # 槽函数与控制逻辑
    # --------------------------------------------------

    def _on_control_toggled(self, checked):
        """控制开关切换"""
        if checked:
            self.btn_control.setText("⏹ Stop Tracking")
            self.btn_control.setStyleSheet("""
                QPushButton {
                    background-color: #dc2626;
                    color: white;
                    font-weight: bold;
                    padding: 8px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #b91c1c;
                }
            """)
        else:
            self.btn_control.setText("▶ Start Tracking")
            self.btn_control.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    font-weight: bold;
                    padding: 8px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
            """)
        self.control_toggled.emit(checked)

    def set_control_enabled(self, enabled: bool) -> None:
        """从外部同步追踪开关状态"""
        self.btn_control.setChecked(enabled)

    def _on_arm_toggled(self, armed: bool):
        """激光保险切换"""
        self.laser_armed = armed
        if armed:
            self.btn_arm.setText("🔥 ARMED (READY)")
            self.btn_arm.setStyleSheet("""
                QPushButton {
                    background-color: #7f1d1d;
                    color: #fca5a5;
                    border: 1px solid #ef4444;
                    font-weight: bold;
                    padding: 9px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #991b1b;
                }
            """)
            self.btn_fire.setEnabled(True)
            self.btn_fire.setStyleSheet("""
                QPushButton {
                    background-color: #991b1b;
                    color: #ffffff;
                    border: 1px solid #ef4444;
                    font-weight: bold;
                    padding: 9px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """)
        else:
            self.btn_arm.setText("🛡️ SAFE (LOCKED)")
            self.btn_arm.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #38bdf8;
                    border: 1px solid #0284c7;
                    font-weight: bold;
                    padding: 9px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #0f172a;
                }
            """)
            self.btn_fire.setEnabled(False)
            self.btn_fire.setText("🔥 HOLD TO FIRE")
            self.btn_fire.setStyleSheet("""
                QPushButton {
                    background-color: #3f1515;
                    color: #7f1d1d;
                    border: 1px solid #7f1d1d;
                    font-weight: bold;
                    padding: 9px;
                    border-radius: 4px;
                }
            """)
        self.laser_armed_toggled.emit(armed)

    def _on_fire_pressed(self):
        """按下发射"""
        if not self.laser_armed:
            return
        self.laser_firing = True
        self.btn_fire.setText("⚡ FIRING...")
        self.btn_fire.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                border: 2px solid #ffffff;
                font-weight: bold;
                padding: 9px;
                border-radius: 4px;
            }
        """)
        self.laser_fire_changed.emit(True)

    def _on_fire_released(self):
        """松开发射"""
        self.laser_firing = False
        if self.laser_armed:
            self.btn_fire.setText("🔥 HOLD TO FIRE")
            self.btn_fire.setStyleSheet("""
                QPushButton {
                    background-color: #991b1b;
                    color: #ffffff;
                    border: 1px solid #ef4444;
                    font-weight: bold;
                    padding: 9px;
                    border-radius: 4px;
                }
            """)
        self.laser_fire_changed.emit(False)

    def set_laser_firing_visual(self, firing: bool):
        """供键盘/外部同步更新开火按钮视觉"""
        if firing:
            self.btn_fire.setText("⚡ FIRING...")
            self.btn_fire.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: #ffffff;
                    border: 2px solid #ffffff;
                    font-weight: bold;
                    padding: 9px;
                    border-radius: 4px;
                }
            """)
        else:
            if self.laser_armed:
                self.btn_fire.setText("🔥 HOLD TO FIRE")
                self.btn_fire.setStyleSheet("""
                    QPushButton {
                        background-color: #991b1b;
                        color: #ffffff;
                        border: 1px solid #ef4444;
                        font-weight: bold;
                        padding: 9px;
                        border-radius: 4px;
                    }
                """)

    def _on_slider_power_changed(self, val: int):
        """滑动条功率改变"""
        self.laser_power = val
        self.lbl_power_val.setText(f"{val}%")
        self.laser_power_changed.emit(val)

    def set_laser_power(self, power: int):
        """设置功率值并同步更新滑动条与显示"""
        clamped = max(0, min(100, int(power)))
        self.slider_power.setValue(clamped)
