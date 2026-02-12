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
    QGroupBox, QFormLayout, QComboBox, QPushButton, QLabel
)
from PyQt6.QtCore import pyqtSignal, QTimer
import cv2


class CameraPanel(QGroupBox):
    """摄像头选择面板"""
    
    # 信号：摄像头切换
    camera_changed = pyqtSignal(int, int, int)  # (camera_id, width, height)
    
    def __init__(self, default_id=0, parent=None):
        super().__init__("摄像头设置 (Camera Settings)", parent)
        self.available_cameras = []
        self.init_ui(default_id)
        # 延迟检测，不阻塞 UI 启动
        QTimer.singleShot(500, self.detect_cameras)
    
    def init_ui(self, default_id):
        """初始化UI"""
        layout = QFormLayout(self)
        
        # 摄像头选择下拉框
        self.combo_camera = QComboBox()
        self.combo_camera.setToolTip("选择要使用的摄像头设备")
        
        # 分辨率选择
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems([
            "320x240 (低分辨率-高速)",
            "640x480 (标准-推荐)",
            "800x600 (中等)",
            "1280x720 (高清)",
            "1920x1080 (全高清)"
        ])
        self.combo_resolution.setCurrentIndex(1)  # 默认640x480
        self.combo_resolution.setToolTip("分辨率越高，细节越清晰，但处理速度越慢")
        
        # 应用按钮（仅用于手动切换）
        self.btn_apply = QPushButton("切换摄像头 (Switch)")
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_apply.setStyleSheet("background-color: #5cb85c; color: white;")
        self.btn_apply.setToolTip("切换到其他摄像头或分辨率")
        
        # 重新检测按钮
        self.btn_refresh = QPushButton("🔄 重新检测")
        self.btn_refresh.clicked.connect(self.detect_cameras)
        self.btn_refresh.setToolTip("重新扫描可用摄像头")
        
        # 状态标签
        self.lbl_status = QLabel("未检测到摄像头")
        self.lbl_status.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_status.setWordWrap(True)
        
        layout.addRow("摄像头:", self.combo_camera)
        layout.addRow("分辨率:", self.combo_resolution)
        layout.addRow(self.btn_apply)
        layout.addRow(self.btn_refresh)
        layout.addRow(self.lbl_status)
    
    def detect_cameras(self):
        """检测可用摄像头"""
        self.lbl_status.setText("正在检测摄像头...")
        self.lbl_status.setStyleSheet("color: orange; font-size: 10px;")
        
        # 延迟执行，避免阻塞UI
        QTimer.singleShot(100, self._detect_cameras_task)
    
    def _detect_cameras_task(self):
        """实际检测任务 - 智能快速版"""
        self.available_cameras = []
        self.combo_camera.clear()
        
        # 先检测 Camera 0
        if self._try_open_camera(0):
            # 成功，检查是否还有 Camera 1（笔记本+USB场景）
            self._try_open_camera(1)
            # 如果有两个了，大概率不会有更多，跳过 Camera 2
        else:
            # Camera 0 失败，尝试 Camera 1（可能只插了USB摄像头）
            if self._try_open_camera(1):
                # 找到了，停止检测
                pass
            else:
                # 都没有，再试试 Camera 2
                self._try_open_camera(2)
        
        # 更新状态并智能应用
        if self.available_cameras:
            num_cameras = len(self.available_cameras)
            
            if num_cameras == 1:
                # 只有一个摄像头，自动应用
                camera_id = self.available_cameras[0]
                self.combo_camera.setCurrentIndex(0)
                msg = f"✓ 已自动选择 Camera {camera_id}"
                self.lbl_status.setText(msg)
                self.lbl_status.setStyleSheet("color: green; font-size: 10px;")
                
                # 自动应用默认分辨率
                QTimer.singleShot(100, self._auto_apply_single_camera)
                
            else:
                # 多个摄像头，优先选择USB摄像头（Camera 1）
                if 1 in self.available_cameras:
                    self.combo_camera.setCurrentIndex(self.available_cameras.index(1))
                    selected = 1
                else:
                    selected = self.available_cameras[0]
                
                msg = f"检测到 {num_cameras} 个摄像头，已选择 Camera {selected}"
                self.lbl_status.setText(msg)
                self.lbl_status.setStyleSheet("color: green; font-size: 10px;")
                
                # 多摄像头也自动应用（智能选择后）
                QTimer.singleShot(100, self._auto_apply_single_camera)
        else:
            msg = "未检测到摄像头！请检查设备连接"
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("color: red; font-size: 10px;")
    
    def _auto_apply_single_camera(self):
        """自动应用摄像头设置"""
        if not self.available_cameras:
            return
        
        camera_index = self.combo_camera.currentIndex()
        if camera_index < 0 or camera_index >= len(self.available_cameras):
            return
        
        camera_id = self.available_cameras[camera_index]
        resolution_text = self.combo_resolution.currentText()
        width, height = self._parse_resolution(resolution_text)
        
        # 发射信号
        self.camera_changed.emit(camera_id, width, height)
        
        # 更新状态
        if len(self.available_cameras) == 1:
            msg = f"✓ Camera {camera_id} 已就绪 ({width}x{height})"
        else:
            msg = f"✓ 已应用 Camera {camera_id} ({width}x{height})"
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet("color: green; font-size: 10px;")
    
    
    def _try_open_camera(self, camera_id):
        """尝试打开指定摄像头"""
        try:
            cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            
            if cap.isOpened():
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
    
    def _auto_apply_single_camera(self):
        """自动应用摄像头设置"""
        if not self.available_cameras:
            return
        
        camera_index = self.combo_camera.currentIndex()
        if camera_index < 0 or camera_index >= len(self.available_cameras):
            return
        
        camera_id = self.available_cameras[camera_index]
        resolution_text = self.combo_resolution.currentText()
        width, height = self._parse_resolution(resolution_text)
        
        # 发射信号
        self.camera_changed.emit(camera_id, width, height)
        
        # 更新状态
        if len(self.available_cameras) == 1:
            msg = f"✓ Camera {camera_id} 已就绪 ({width}x{height})"
        else:
            msg = f"✓ 已应用 Camera {camera_id} ({width}x{height})"
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet("color: green; font-size: 10px;")
    
    def _on_apply_clicked(self):
        """应用设置按钮点击（手动切换）"""
        if not self.available_cameras:
            self.lbl_status.setText("没有可用摄像头！")
            self.lbl_status.setStyleSheet("color: red; font-size: 10px;")
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
        self.lbl_status.setText(f"✓ 已切换到 Camera {camera_id} ({width}x{height})")
        self.lbl_status.setStyleSheet("color: green; font-size: 10px;")
    
    def _parse_resolution(self, text):
        """解析分辨率字符串 '640x480' -> (640, 480)"""
        try:
            res_part = text.split()[0]  # "640x480"
            width, height = res_part.split('x')
            return int(width), int(height)
        except:
            return 640, 480  # 默认值
    
    def get_current_camera_id(self):
        """获取当前选择的摄像头ID"""
        camera_index = self.combo_camera.currentIndex()
        if camera_index >= 0 and camera_index < len(self.available_cameras):
            return self.available_cameras[camera_index]
        return 0
