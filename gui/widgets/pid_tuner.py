# -*- coding: utf-8 -*-
"""
PID 调参面板 (PID Tuning Panel)

⭐ 这是调试 PID 的核心组件！

[功能]
1. 实时调整 Kp、Ki、Kd 参数
2. 反转轴向设置
3. 保存/重置配置

[使用技巧]
- 拖动滑块实时调参，观察效果
- 勾选"反转"改变运动方向
- 找到最佳参数后点击"保存配置"
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSlider, QPushButton, QCheckBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation
from PyQt6.QtGui import QCursor


class PIDTuner(QWidget):
    """PID 调参面板"""
    
    # 信号：PID 参数改变
    pid_changed = pyqtSignal(float, float, float)  # (kp, ki, kd)
    
    # 信号：反转设置改变
    invert_changed = pyqtSignal(bool, bool)  # (invert_x, invert_y)
    
    # 信号：保存配置
    save_requested = pyqtSignal()
    
    # 信号：重置PID
    reset_requested = pyqtSignal()
    
    def __init__(self, initial_kp=0.4, initial_ki=0.0, initial_kd=0.2, 
                 invert_x=True, invert_y=True, parent=None):
        super().__init__(parent)
        
        self.kp = initial_kp
        self.ki = initial_ki
        self.kd = initial_kd
        self.is_expanded = False  # 默认折叠
        
        self.init_ui(invert_x, invert_y)
        self.update_sliders()
        # 初始状态设为折叠
        self.content_frame.setVisible(self.is_expanded)
    
    def init_ui(self, invert_x, invert_y):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ==========================
        # 标题栏（可点击折叠/展开）
        # ==========================
        title_frame = QFrame()
        title_frame.setObjectName("pidTunerTitle")
        title_frame.setStyleSheet("""
            QFrame#pidTunerTitle {
                border: 1px solid palette(mid);
                border-radius: 5px;
                padding: 8px;
                background-color: palette(dark);
            }
            QFrame#pidTunerTitle:hover {
                background-color: palette(mid);
            }
        """)
        title_frame.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_label = QLabel("▶ ⚙️ PID 参数调节 (点击展开)")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        
        # 让标题栏可点击
        title_frame.mousePressEvent = lambda event: self.toggle_content()
        
        layout.addWidget(title_frame)
        
        # ==========================
        # 内容框架（可折叠）
        # ==========================
        self.content_frame = QFrame()
        self.content_frame.setObjectName("pidTunerContent")
        self.content_frame.setStyleSheet("""
            QFrame#pidTunerContent {
                border: 1px solid palette(mid);
                border-top: none;
                border-radius: 0 0 5px 5px;
                padding: 10px;
            }
        """)
        
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setSpacing(8)
        
        # ==========================
        # Kp 滑块
        # ==========================
        kp_layout = QHBoxLayout()
        kp_layout.addWidget(QLabel("Kp:"))
        
        self.slider_kp = QSlider(Qt.Orientation.Horizontal)
        self.slider_kp.setRange(0, 200)  # 0.00 - 2.00
        self.slider_kp.valueChanged.connect(self._on_slider_changed)
        kp_layout.addWidget(self.slider_kp)
        
        self.label_kp_val = QLabel("0.40")
        self.label_kp_val.setMinimumWidth(50)
        self.label_kp_val.setStyleSheet("color: #FFA726; font-weight: bold;")
        kp_layout.addWidget(self.label_kp_val)
        
        content_layout.addLayout(kp_layout)
        
        # Kp 说明
        kp_hint = QLabel("↑ 比例项：响应速度（过大会震荡）")
        kp_hint.setStyleSheet("color: gray; font-size: 10px;")
        content_layout.addWidget(kp_hint)
        
        # ==========================
        # Ki 滑块
        # ==========================
        ki_layout = QHBoxLayout()
        ki_layout.addWidget(QLabel("Ki:"))
        
        self.slider_ki = QSlider(Qt.Orientation.Horizontal)
        self.slider_ki.setRange(0, 100)  # 0.000 - 1.000
        self.slider_ki.valueChanged.connect(self._on_slider_changed)
        ki_layout.addWidget(self.slider_ki)
        
        self.label_ki_val = QLabel("0.000")
        self.label_ki_val.setMinimumWidth(50)
        self.label_ki_val.setStyleSheet("color: #66BB6A; font-weight: bold;")
        ki_layout.addWidget(self.label_ki_val)
        
        content_layout.addLayout(ki_layout)
        
        # Ki 说明
        ki_hint = QLabel("↑ 积分项：消除稳态误差（通常很小）")
        ki_hint.setStyleSheet("color: gray; font-size: 10px;")
        content_layout.addWidget(ki_hint)
        
        # ==========================
        # Kd 滑块
        # ==========================
        kd_layout = QHBoxLayout()
        kd_layout.addWidget(QLabel("Kd:"))
        
        self.slider_kd = QSlider(Qt.Orientation.Horizontal)
        self.slider_kd.setRange(0, 100)  # 0.00 - 1.00
        self.slider_kd.valueChanged.connect(self._on_slider_changed)
        kd_layout.addWidget(self.slider_kd)
        
        self.label_kd_val = QLabel("0.20")
        self.label_kd_val.setMinimumWidth(50)
        self.label_kd_val.setStyleSheet("color: #42A5F5; font-weight: bold;")
        kd_layout.addWidget(self.label_kd_val)
        
        content_layout.addLayout(kd_layout)
        
        # Kd 说明
        kd_hint = QLabel("↑ 微分项：阻尼作用（抑制震荡）")
        kd_hint.setStyleSheet("color: gray; font-size: 10px;")
        content_layout.addWidget(kd_hint)
        
        content_layout.addSpacing(10)
        
        # ==========================
        # 反转设置
        # ==========================
        check_layout = QHBoxLayout()
        
        self.chk_invert_x = QCheckBox("反转 X 轴")
        self.chk_invert_x.setChecked(invert_x)
        self.chk_invert_x.stateChanged.connect(self._on_invert_changed)
        
        self.chk_invert_y = QCheckBox("反转 Y 轴")
        self.chk_invert_y.setChecked(invert_y)
        self.chk_invert_y.stateChanged.connect(self._on_invert_changed)
        
        check_layout.addWidget(self.chk_invert_x)
        check_layout.addWidget(self.chk_invert_y)
        content_layout.addLayout(check_layout)
        
        content_layout.addSpacing(10)
        
        # ==========================
        # 按钮
        # ==========================
        self.btn_save = QPushButton("💾 保存配置")
        self.btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_save.clicked.connect(self._on_save_clicked)
        content_layout.addWidget(self.btn_save)
        
        self.btn_reset = QPushButton("🔄 重置默认 PID")
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        content_layout.addWidget(self.btn_reset)
        
        # 将内容框架添加到主布局
        layout.addWidget(self.content_frame)
    
    def toggle_content(self):
        """切换折叠/展开状态"""
        self.is_expanded = not self.is_expanded
        self.content_frame.setVisible(self.is_expanded)
        
        # 更新标题文字
        if self.is_expanded:
            self.title_label.setText("▼ ⚙️ PID 参数调节 (点击折叠)")
        else:
            self.title_label.setText("▶ ⚙️ PID 参数调节 (点击展开)")
    
    def update_sliders(self):
        """更新滑块位置和显示"""
        # 阻止信号，避免setValue触发valueChanged导致值被覆盖
        self.slider_kp.blockSignals(True)
        self.slider_ki.blockSignals(True)
        self.slider_kd.blockSignals(True)
        
        self.slider_kp.setValue(int(self.kp * 100))
        self.slider_ki.setValue(int(self.ki * 100))
        self.slider_kd.setValue(int(self.kd * 100))
        
        self.slider_kp.blockSignals(False)
        self.slider_ki.blockSignals(False)
        self.slider_kd.blockSignals(False)
        
        # 更新显示标签
        self.label_kp_val.setText(f"{self.kp:.2f}")
        self.label_ki_val.setText(f"{self.ki:.3f}")
        self.label_kd_val.setText(f"{self.kd:.2f}")
    
    def _on_slider_changed(self):
        """滑块值改变"""
        self.kp = self.slider_kp.value() / 100.0
        self.ki = self.slider_ki.value() / 100.0
        self.kd = self.slider_kd.value() / 100.0
        
        # 更新显示
        self.label_kp_val.setText(f"{self.kp:.2f}")
        self.label_ki_val.setText(f"{self.ki:.3f}")
        self.label_kd_val.setText(f"{self.kd:.2f}")
        
        # 发射信号
        self.pid_changed.emit(self.kp, self.ki, self.kd)
    
    def _on_invert_changed(self):
        """反转设置改变"""
        invert_x = self.chk_invert_x.isChecked()
        invert_y = self.chk_invert_y.isChecked()
        self.invert_changed.emit(invert_x, invert_y)
    
    def _on_save_clicked(self):
        """保存按钮点击"""
        self.save_requested.emit()
        QMessageBox.information(
            self, 
            "保存成功", 
            f"PID 参数已保存！\n\nKp={self.kp:.2f}, Ki={self.ki:.3f}, Kd={self.kd:.2f}"
        )
    
    def _on_reset_clicked(self):
        """重置按钮点击（恢复 ControlConfig 默认值）"""
        from config.control_config import ControlConfig
        default_kp = ControlConfig.KP
        default_ki = ControlConfig.KI
        default_kd = ControlConfig.KD

        reply = QMessageBox.question(
            self,
            "确认重置",
            f"是否重置为默认 PID 参数？\n\nKp={default_kp:.2f}, Ki={default_ki:.3f}, Kd={default_kd:.2f}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.kp = default_kp
            self.ki = default_ki
            self.kd = default_kd
            self.update_sliders()
            self.reset_requested.emit()
    
    def set_pid_values(self, kp, ki, kd):
        """外部设置 PID 值"""
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.update_sliders()
