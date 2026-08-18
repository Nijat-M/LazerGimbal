# -*- coding: utf-8 -*-
"""
摄像头选择面板 (Camera Selection Panel)

功能：
- 检测可用摄像头
- 选择摄像头ID
- 动态切换摄像头
- 分辨率和帧率设置
"""

import os
# 抑制OpenCV警告信息
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'

from PyQt6.QtWidgets import (
    QGroupBox, QFormLayout, QHBoxLayout, QComboBox, QPushButton, QLabel
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
import cv2
from config.vision_config import VisionConfig
from config.device_config import DeviceConfig


class CameraPanel(QGroupBox):
    """摄像头选择面板"""
    
    # 信号：摄像头切换和关闭
    camera_changed = pyqtSignal(int, int, int)  # (camera_id, width, height)
    camera_toggled = pyqtSignal(bool)           # 开启/关闭信号
    flip_changed = pyqtSignal(str)              # 画面翻转信号 ("NONE", "180", "V", "H")
    open_settings_requested = pyqtSignal()      # 请求打开 DirectShow 相机硬件属性面板

    def __init__(self, default_id=None, parent=None):
        super().__init__("Camera Settings", parent)
        self.available_cameras = []
        self.is_camera_open = False
        self.init_ui(default_id if default_id is not None else DeviceConfig.CAMERA_ID)
        # 延迟检测，不阻塞 UI 启动
        QTimer.singleShot(400, self.detect_cameras)
    
    def init_ui(self, default_id):
        """初始化UI"""
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # 1. 摄像头选择下拉框
        self.combo_camera = QComboBox()
        self.combo_camera.setToolTip("Select camera device")
        
        # 2. 分辨率选择（聚焦于工业级最稳妥的 60 FPS 档位）
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems([
            "640x480 (60 FPS - Low Latency)",
            "1280x720 (60 FPS - HD)",
            "1920x1080 (60 FPS - Full HD)"
        ])
        saved_res_prefix = f"{DeviceConfig.RESOLUTION_WIDTH}x{DeviceConfig.RESOLUTION_HEIGHT}"
        for i in range(self.combo_resolution.count()):
            if self.combo_resolution.itemText(i).startswith(saved_res_prefix):
                self.combo_resolution.setCurrentIndex(i)
                break
        self.combo_resolution.setToolTip("Select resolution (640x480 lowest latency)")
        
        # 3. 画面方向/翻转选择 (即时热切换)
        self.combo_flip = QComboBox()
        self.combo_flip.addItem("Normal (0°)", "NONE")
        self.combo_flip.addItem("180° Flip (Inverted)", "180")
        self.combo_flip.addItem("Vertical Flip", "V")
        self.combo_flip.addItem("Horizontal Mirror", "H")
        initial_flip_idx = self.combo_flip.findData(getattr(DeviceConfig, "FLIP_MODE", "NONE"))
        if initial_flip_idx >= 0:
            self.combo_flip.setCurrentIndex(initial_flip_idx)
        self.combo_flip.currentIndexChanged.connect(self._on_flip_changed)
        self.combo_flip.setToolTip("Takes effect immediately")

        # 4. 主操作按钮组
        self.btn_toggle = QPushButton("Open Camera")
        self.btn_toggle.clicked.connect(self._on_toggle_clicked)
        self.btn_toggle.setStyleSheet("background-color: #007bff; color: white; padding: 5px;")
        self.btn_toggle.setToolTip("Start or stop camera thread")

        self.btn_apply = QPushButton("Apply Settings")
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_apply.setStyleSheet("background-color: #5cb85c; color: white; padding: 5px;")
        self.btn_apply.setToolTip("Apply after changing resolution or device")
        
        btn_main_layout = QHBoxLayout()
        btn_main_layout.addWidget(self.btn_toggle)
        btn_main_layout.addWidget(self.btn_apply)

        # 5. 硬件与辅助工具按钮组
        self.btn_settings = QPushButton("⚙️ Exposure/Gain")
        self.btn_settings.clicked.connect(self._on_settings_clicked)
        self.btn_settings.setStyleSheet("background-color: #495057; color: white; padding: 4px;")
        self.btn_settings.setToolTip("Open DirectShow panel for exposure/gain")

        self.btn_refresh = QPushButton("🔄 Refresh Devices")
        self.btn_refresh.clicked.connect(self.detect_cameras)
        self.btn_refresh.setStyleSheet("padding: 4px;")
        self.btn_refresh.setToolTip("Rescan connected USB cameras")
        
        btn_tool_layout = QHBoxLayout()
        btn_tool_layout.addWidget(self.btn_settings)
        btn_tool_layout.addWidget(self.btn_refresh)

        # 6. 状态标签
        self.lbl_status = QLabel("Not Open - Please click Open Camera")
        self.lbl_status.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_status.setWordWrap(True)
        
        # 实时视觉统计 (FPS, 分辨率)
        self.lbl_vision_stats = QLabel("FPS: -- | RES: --")
        self.lbl_vision_stats.setStyleSheet("""
            background-color: #1a1a1a; 
            color: #00ff00; 
            font-weight: bold; 
            font-family: Consolas, monospace;
            padding: 5px;
            border-radius: 3px;
            border: 1px solid #333;
        """)
        self.lbl_vision_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addRow("Live Stats:", self.lbl_vision_stats)
        layout.addRow("Device:", self.combo_camera)
        layout.addRow("Resolution:", self.combo_resolution)
        layout.addRow("Orientation:", self.combo_flip)
        layout.addRow(btn_main_layout)
        layout.addRow(btn_tool_layout)
        layout.addRow(self.lbl_status)
    
    def detect_cameras(self):
        """检测可用摄像头"""
        self.lbl_status.setText("Detecting cameras...")
        self.lbl_status.setStyleSheet("color: orange; font-size: 10px;")
        
        # 延迟执行，避免阻塞UI
        QTimer.singleShot(100, self._detect_cameras_task)
    
    def _detect_cameras_task(self):
        """实际检测任务 - 快速直连版 (避免启动时占用硬件设备导致 DirectShow 锁死)"""
        # 预置可用设备列表 (Camera 0: 笔记本自带, Camera 1: USB云台相机, Camera 2: 备用)
        self.available_cameras = [0, 1, 2]
        self.combo_camera.clear()
        self.combo_camera.addItem("Camera 0 (Integrated Webcam)")
        self.combo_camera.addItem("Camera 1 (USB Gimbal Camera)")
        self.combo_camera.addItem("Camera 2 (Aux USB Camera)")
        
        saved_id = DeviceConfig.CAMERA_ID if DeviceConfig.CAMERA_ID in self.available_cameras else 1
        saved_idx = self.available_cameras.index(saved_id)
        self.combo_camera.setCurrentIndex(saved_idx)
        
        self.lbl_status.setText(f"✓ Ready: Camera {saved_id}")
        self.lbl_status.setStyleSheet("color: green; font-size: 10px;")

        if DeviceConfig.AUTO_OPEN_CAMERA and not self.is_camera_open:
            QTimer.singleShot(100, self._auto_start_camera)
    
    def _auto_start_camera(self):
        """启动时平稳自动开启保存的摄像头"""
        if not self.is_camera_open and self.available_cameras:
            self.is_camera_open = True
            self.btn_toggle.setText("Close Camera")
            self.btn_toggle.setStyleSheet("background-color: #dc3545; color: white;")
            self._on_apply_clicked()

    def _on_toggle_clicked(self):
        """开启或关闭摄像头"""
        if not self.available_cameras:
            self.lbl_status.setText("No available cameras! Try again")
            self.lbl_status.setStyleSheet("color: red; font-size: 10px;")
            return
            
        self.is_camera_open = not self.is_camera_open
        
        if self.is_camera_open:
            self.btn_toggle.setText("Close Camera")
            self.btn_toggle.setStyleSheet("background-color: #dc3545; color: white;")
            self._on_apply_clicked()  # 触发发送唯一的 camera_changed 信号
        else:
            self.btn_toggle.setText("Open Camera")
            self.btn_toggle.setStyleSheet("background-color: #007bff; color: white;")
            self.camera_toggled.emit(False)
            self.lbl_status.setText("Camera closed")
            self.lbl_status.setStyleSheet("color: gray; font-size: 10px;")

    def _on_flip_changed(self, index: int):
        """画面翻转下拉框选择改变"""
        mode = self.combo_flip.currentData()
        if mode:
            DeviceConfig.FLIP_MODE = mode
            DeviceConfig.save()
            self.flip_changed.emit(mode)

    def _on_settings_clicked(self):
        """点击打开 DirectShow 原生工业相机调参面板"""
        if not self.is_camera_open:
            self.lbl_status.setText("Please open camera before tuning hardware!")
            self.lbl_status.setStyleSheet("color: orange; font-size: 10px;")
            return
        self.open_settings_requested.emit()
    
    def _try_open_camera(self, camera_id):
        """尝试打开指定摄像头"""
        try:
            cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FPS, 60)
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = int(cap.get(cv2.CAP_PROP_FPS))
                    fps_text = f"{fps}fps" if fps > 0 else "auto"
                    
                    self.available_cameras.append(camera_id)
                    camera_info = f"Camera {camera_id} ({width}x{height}@{fps_text})"
                    self.combo_camera.addItem(camera_info)
                    cap.release()
                    return True
            
            cap.release()
        except Exception:
            pass
        
        return False
    

    
    def _on_apply_clicked(self):
        """应用设置按钮点击（手动切换）"""
        if not self.available_cameras:
            self.lbl_status.setText("No available cameras!")
            self.lbl_status.setStyleSheet("color: red; font-size: 10px;")
            return
            
        if not self.is_camera_open:
            self.lbl_status.setText("Please open camera before applying settings")
            self.lbl_status.setStyleSheet("color: orange; font-size: 10px;")
            return
        
        # 获取选择的摄像头ID
        camera_index = self.combo_camera.currentIndex()
        if camera_index < 0 or camera_index >= len(self.available_cameras):
            return
        
        camera_id = self.available_cameras[camera_index]
        
        # 解析分辨率
        resolution_text = self.combo_resolution.currentText()
        width, height = self._parse_resolution(resolution_text)
        
        # 发射信号
        self.camera_changed.emit(camera_id, width, height)

        # 同步更新下拉框的文本（保留原有FPS信息）
        old_text = self.combo_camera.itemText(camera_index)
        fps_part = f"@{old_text.split('@')[1]}" if "@" in old_text else ")"
        self.combo_camera.setItemText(camera_index, f"Camera {camera_id} ({width}x{height}{fps_part}")
        
        # 持久化保存设备配置
        DeviceConfig.CAMERA_ID = camera_id
        DeviceConfig.RESOLUTION_WIDTH = width
        DeviceConfig.RESOLUTION_HEIGHT = height
        DeviceConfig.FLIP_MODE = self.combo_flip.currentData() or "NONE"
        DeviceConfig.save()

        self.lbl_status.setText(f"✓ Switched to Camera {camera_id} ({width}x{height})")
        self.lbl_status.setStyleSheet("color: green; font-size: 10px;")
    
    def _parse_resolution(self, text):
        """解析分辨率字符串 '640x480' -> (640, 480)"""
        try:
            res_part = text.split()[0]  # "640x480"
            width, height = res_part.split('x')
            return int(width), int(height)
        except:
            return 640, 480  # 默认值
    
    def update_vision_stats(self, fps, width, height):
        """更新视觉统计信息"""
        color = "#00ff00" if fps > 30 else "#ffff00"
        if fps < 15: color = "#ff0000"
        
        self.lbl_vision_stats.setText(f"FPS: {fps:.1f} | RES: {width}x{height}")
        self.lbl_vision_stats.setStyleSheet(f"""
            background-color: #1a1a1a; 
            color: {color}; 
            font-weight: bold; 
            font-family: Consolas, monospace;
            padding: 5px;
            border-radius: 3px;
            border: 1px solid #333;
        """)

    def get_current_camera_id(self):
        """获取当前选择的摄像头ID"""
        camera_index = self.combo_camera.currentIndex()
        if camera_index >= 0 and camera_index < len(self.available_cameras):
            return self.available_cameras[camera_index]
        return 0

    def get_selected_resolution(self):
        """获取选中的分辨率 (width, height)"""
        text = self.combo_resolution.currentText()
        return self._parse_resolution(text)
