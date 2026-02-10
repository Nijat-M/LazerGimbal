# -*- coding: utf-8 -*-
"""
串口连接面板 (Serial Connection Panel)

功能：
- 选择串口号
- 连接/断开串口
"""

from PyQt6.QtWidgets import (
    QGroupBox, QFormLayout, QComboBox, QPushButton
)
from PyQt6.QtCore import pyqtSignal


class SerialPanel(QGroupBox):
    """串口连接面板"""
    
    # 信号：连接状态改变
    connection_toggled = pyqtSignal(bool, str)  # (checked, port_name)
    
    def __init__(self, default_port="COM3", parent=None):
        super().__init__("通信连接 (Serial Connection)", parent)
        self.init_ui(default_port)
    
    def init_ui(self, default_port):
        """初始化UI"""
        layout = QFormLayout(self)
        
        # 端口选择
        self.combo_port = QComboBox()
        self.combo_port.addItems([
            "COM1", "COM2", "COM3", "COM4", "COM5",
            "COM6", "COM7", "COM8", "COM9", "COM10"
        ])
        self.combo_port.setCurrentText(default_port)
        
        # 连接按钮
        self.btn_connect = QPushButton("连接 (Connect)")
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        
        layout.addRow("端口 (Port):", self.combo_port)
        layout.addRow(self.btn_connect)
    
    def _on_connect_clicked(self):
        """连接按钮点击处理"""
        port = self.combo_port.currentText()
        checked = self.btn_connect.isChecked()
        
        if checked:
            self.btn_connect.setText("断开 (Disconnect)")
        else:
            self.btn_connect.setText("连接 (Connect)")
        
        # 发射信号
        self.connection_toggled.emit(checked, port)
    
    def set_connection_status(self, success, message):
        """
        设置连接状态
        :param success: 是否成功
        :param message: 状态消息
        """
        if not success:
            # 连接失败，重置按钮
            self.btn_connect.setChecked(False)
            self.btn_connect.setText("连接 (Connect)")
