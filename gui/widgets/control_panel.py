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
        
        # 停止电机并将当前位置设为软件相对原点
        self.btn_reset = QPushButton("重置原点 (Reset)")
        self.btn_reset.setToolTip("停止电机并将当前位置设为相对原点，不执行物理归中")
        self.btn_reset.clicked.connect(self.reset_requested.emit)
        layout.addWidget(self.btn_reset)
    
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

    def set_control_enabled(self, enabled: bool) -> None:
        """Synchronize the toggle button with an externally selected mode."""
        self.btn_control.setChecked(enabled)
