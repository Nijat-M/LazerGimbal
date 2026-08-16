# -*- coding: utf-8 -*-
"""
串口连接面板 (Serial Connection Panel)

功能：
- 专注于 STM32 原生 USB CDC (VID:0483 PID:5740)
- 彻底过滤并屏蔽 Windows 蓝牙虚拟串口残留 (BTHENUM / Bluetooth SPP)
- 紧凑美观的响应式 UI 布局，无任何文字截断
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt
import serial.tools.list_ports


class SerialPanel(QGroupBox):
    """串口连接面板"""
    
    # 信号：连接状态改变 (checked, port_name)
    connection_toggled = pyqtSignal(bool, str)
    
    def __init__(self, default_port=None, parent=None):
        super().__init__("USB Communication", parent)
        self.is_connected = False
        self.init_ui(default_port)
    
    def init_ui(self, default_port):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 12, 10, 10)
        
        # 1. 端口选择行 (水平布局)
        port_row = QHBoxLayout()
        port_label = QLabel("Port:")
        port_label.setStyleSheet("font-weight: bold; min-width: 75px;")
        
        # 自动检测可用端口 ComboBox (彻底过滤蓝牙)
        class SmartRefreshComboBox(QComboBox):
            def showPopup(sub_self):
                sub_self.refresh_ports()
                super().showPopup()

            def refresh_ports(sub_self):
                current_selected = sub_self.currentData()
                sub_self.clear()
                all_ports = list(serial.tools.list_ports.comports())
                
                # 过滤掉蓝牙虚拟串口残留 (BTHENUM / Bluetooth / 蓝牙)
                valid_ports = []
                for p in all_ports:
                    is_bluetooth = ("BTHENUM" in str(p.hwid)) or ("蓝牙" in str(p.description)) or ("Bluetooth" in str(p.description))
                    if not is_bluetooth:
                        valid_ports.append(p)
                
                if not valid_ports:
                    sub_self.addItem("No USB Device (No Port)", None)
                    return

                usb_found_index = -1
                for idx, p in enumerate(valid_ports):
                    is_stm32_usb = (p.vid == 0x0483 and p.pid == 0x5740) or ("STMicroelectronics" in str(p.description)) or ("0483:5740" in str(p.hwid))
                    
                    if is_stm32_usb:
                        label = f"{p.device} (⚡ STM32 Native USB)"
                        if usb_found_index == -1:
                            usb_found_index = idx
                    else:
                        clean_desc = str(p.description).split("(")[0].strip()
                        label = f"{p.device} ({clean_desc[:16]})"
                    
                    sub_self.addItem(label, p.device)
                
                if current_selected is not None:
                    found_idx = sub_self.findData(current_selected)
                    if found_idx >= 0:
                        sub_self.setCurrentIndex(found_idx)
                    elif usb_found_index >= 0:
                        sub_self.setCurrentIndex(usb_found_index)
                elif usb_found_index >= 0:
                    sub_self.setCurrentIndex(usb_found_index)

        self.combo_port = SmartRefreshComboBox()
        self.combo_port.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                border-radius: 4px;
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #475569;
            }
            QComboBox:hover {
                border: 1px solid #38bdf8;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: #f8fafc;
                selection-background-color: #0284c7;
            }
        """)
        self.combo_port.refresh_ports()
        
        port_row.addWidget(port_label)
        port_row.addWidget(self.combo_port, 1)
        main_layout.addLayout(port_row)
        
        # 2. 状态信息指示卡片 (紧凑型，自适应换行)
        self.status_card = QFrame()
        self.status_card.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 6px 8px;
            }
        """)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(2, 2, 2, 2)
        status_layout.setSpacing(0)
        
        self.lbl_channel_type = QLabel("Channel: Detecting...")
        self.lbl_channel_type.setWordWrap(True)
        self.lbl_channel_type.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        status_layout.addWidget(self.lbl_channel_type)
        
        main_layout.addWidget(self.status_card)
        self._update_channel_badge()
        self.combo_port.currentIndexChanged.connect(self._update_channel_badge)

        # 3. 连接控制按钮
        self.btn_connect = QPushButton("⚡ Connect")
        self.btn_connect.setCheckable(True)
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:checked {
                background-color: #dc2626;
            }
            QPushButton:checked:hover {
                background-color: #b91c1c;
            }
        """)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        main_layout.addWidget(self.btn_connect)
    
    def _update_channel_badge(self):
        """更新当前选中端口的通道类型徽章"""
        if self.is_connected:
            return
            
        current_text = self.combo_port.currentText()
        if "⚡ STM32" in current_text:
            self.lbl_channel_type.setText("⚡ STM32 Native USB (12 Mbps Full Speed)")
            self.lbl_channel_type.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 12px;")
        elif "未检测到" in current_text:
            self.lbl_channel_type.setText("⚠️ No STM32 USB connection detected")
            self.lbl_channel_type.setStyleSheet("color: #f87171; font-weight: bold; font-size: 12px;")
        else:
            self.lbl_channel_type.setText("🔌 Standard USB Serial Port")
            self.lbl_channel_type.setStyleSheet("color: #94a3b8; font-size: 12px;")

    def _on_connect_clicked(self):
        """连接按钮点击处理"""
        port = self.combo_port.currentData()
        if not port:
            port = self.combo_port.currentText().split()[0]
        checked = self.btn_connect.isChecked()
        
        if checked:
            self.btn_connect.setText("⏳ Establishing connection...")
        else:
            self.btn_connect.setText("⚡ Connect")
            self.is_connected = False
            self._update_channel_badge()
        
        # 发射信号
        self.connection_toggled.emit(checked, port)
    
    def set_connection_status(self, success, message):
        """设置连接状态回调"""
        self.is_connected = success
        if success:
            self.btn_connect.setChecked(True)
            self.btn_connect.setText("🔌 Disconnect")
            port_name = self.combo_port.currentData() or ""
            self.lbl_channel_type.setText(f"✓ Connected {port_name} (12 Mbps 全速传输中)")
            self.lbl_channel_type.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 12px;")
        else:
            self.btn_connect.setChecked(False)
            self.btn_connect.setText("⚡ Connect")
            self._update_channel_badge()
