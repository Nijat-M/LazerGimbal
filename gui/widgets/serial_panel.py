# -*- coding: utf-8 -*-
"""
串口连接面板 (Serial Connection Panel)

功能：
- 专注于 STM32 原生 USB CDC (VID:0483 PID:5740)
- 彻底过滤并屏蔽 Windows 蓝牙虚拟串口残留 (BTHENUM / Bluetooth SPP)
- 紧凑美观的响应式 UI 布局，无任何文字截断
"""

from datetime import datetime
from collections import deque
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel, QFrame, QPlainTextEdit
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
import serial.tools.list_ports
from config.device_config import DeviceConfig


class SerialPanel(QGroupBox):
    """串口连接面板"""
    
    # 信号：连接状态改变 (checked, port_name)
    connection_toggled = pyqtSignal(bool, str)
    
    def __init__(self, default_port=None, parent=None):
        super().__init__("USB Communication", parent)
        self.is_connected = False
        self.init_ui(default_port or DeviceConfig.SERIAL_PORT)
    
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
                current_selected = sub_self.currentData() or DeviceConfig.SERIAL_PORT
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
                saved_port_index = -1
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
                    if p.device == DeviceConfig.SERIAL_PORT:
                        saved_port_index = idx
                
                if saved_port_index >= 0:
                    sub_self.setCurrentIndex(saved_port_index)
                elif current_selected is not None:
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

        # 4. STM32 实时通信监视器 (TX / RX Serial Console)
        monitor_header = QHBoxLayout()
        lbl_mon = QLabel("<b>📡 Live Port Monitor (TX / RX)</b>")
        lbl_mon.setStyleSheet("color: #94a3b8; font-size: 11px;")
        monitor_header.addWidget(lbl_mon)
        monitor_header.addStretch()

        self.btn_clear_log = QPushButton("Clear")
        self.btn_clear_log.setFixedSize(45, 20)
        self.btn_clear_log.setStyleSheet("""
            QPushButton { background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 3px; font-size: 10px; }
            QPushButton:hover { background-color: #334155; color: #f1f5f9; }
        """)
        self.btn_clear_log.clicked.connect(self._clear_monitor)
        monitor_header.addWidget(self.btn_clear_log)
        main_layout.addLayout(monitor_header)

        self.txt_monitor = QPlainTextEdit()
        self.txt_monitor.setReadOnly(True)
        self.txt_monitor.setMaximumBlockCount(150)
        self.txt_monitor.setMinimumHeight(100)
        self.txt_monitor.setMaximumHeight(140)
        self.txt_monitor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #090d16;
                color: #38bdf8;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10px;
                border: 1px solid #1e293b;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        main_layout.addWidget(self.txt_monitor)
        
        # 批量日志刷新定时器 (10Hz)，避免高频运动时 QTextDocument 跨线程崩溃
        self._log_queue = deque(maxlen=200)
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_logs)
        self._flush_timer.start(100)
    
    def _clear_monitor(self):
        self._log_queue.clear()
        self.txt_monitor.clear()

    def log_tx(self, msg: str):
        """记录发送给 STM32 的数据 (TX ➜)"""
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._log_queue.append(f"[{now}] ⬆ TX ➜ {msg}")

    def log_rx(self, msg: str):
        """记录从 STM32 接收到的数据 (RX ⬅)"""
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._log_queue.append(f"[{now}] ⬇ RX ⬅ {msg}")

    def _flush_logs(self):
        if not self._log_queue:
            return
        lines = []
        while self._log_queue:
            lines.append(self._log_queue.popleft())
        if lines:
            text = "\n".join(lines)
            self.txt_monitor.appendPlainText(text)
            self.txt_monitor.ensureCursorVisible()

    def _update_channel_badge(self):
        """更新当前选中端口的通道类型徽章"""
        if self.is_connected:
            return
            
        current_text = self.combo_port.currentText()
        if "⚡ STM32" in current_text:
            self.lbl_channel_type.setText("⚡ STM32 Native USB (12 Mbps Full Speed)")
            self.lbl_channel_type.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 12px;")
        elif "No USB" in current_text or "No Port" in current_text or "未检测到" in current_text:
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
        """设置连接状态回调并持久化端口"""
        self.is_connected = success
        if success:
            self.btn_connect.setChecked(True)
            self.btn_connect.setText("🔌 Disconnect")
            port_name = self.combo_port.currentData() or ""
            self.lbl_channel_type.setText(f"✓ Connected {port_name} (12 Mbps Full Speed)")
            self.lbl_channel_type.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 12px;")
            if port_name:
                DeviceConfig.SERIAL_PORT = port_name
                DeviceConfig.save()
        else:
            self.btn_connect.setChecked(False)
            self.btn_connect.setText("⚡ Connect")
            self._update_channel_badge()
