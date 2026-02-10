# -*- coding: utf-8 -*-
"""
控制按钮面板 (Control Panel)

包含：
- 开始/停止控制
- 重置位置
- 测试蜂鸣器
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal


class ControlPanel(QWidget):
    """控制按钮面板"""
    
    # 信号
    control_toggled = pyqtSignal(bool)  # 控制开关
    reset_requested = pyqtSignal()      # 重置位置
    buzzer_requested = pyqtSignal()     # 测试蜂鸣器
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)
        
        # 开始/停止按钮
        self.btn_control = QPushButton("开始控制 (Start)")
        self.btn_control.setCheckable(True)
        self.btn_control.setStyleSheet(
            "background-color: #444; color: white; padding: 8px;"
        )
        self.btn_control.toggled.connect(self._on_control_toggled)
        layout.addWidget(self.btn_control)
        
        # 重置位置按钮
        self.btn_reset = QPushButton("重置位置 (Reset)")
        self.btn_reset.setToolTip("重置软件坐标为中位 (90°, 90°)")
        self.btn_reset.clicked.connect(self.reset_requested.emit)
        layout.addWidget(self.btn_reset)
        
        # 蜂鸣器按钮
        self.btn_buzzer = QPushButton("测试蜂鸣器")
        self.btn_buzzer.clicked.connect(self.buzzer_requested.emit)
        layout.addWidget(self.btn_buzzer)
    
    def _on_control_toggled(self, checked):
        """控制开关切换"""
        if checked:
            self.btn_control.setText("停止控制 (Stop)")
            self.btn_control.setStyleSheet(
                "background-color: #d9534f; color: white; "
                "font-weight: bold; padding: 8px;"
            )
        else:
            self.btn_control.setText("开始控制 (Start)")
            self.btn_control.setStyleSheet(
                "background-color: #444; color: white; padding: 8px;"
            )
        
        self.control_toggled.emit(checked)
