# -*- coding: utf-8 -*-
"""
摄像头显示组件 (Camera View Widget)

显示两个画面：
1. 摄像头实时画面
2. 调试蒙版 (Debug Mask)
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap


class CameraView(QWidget):
    """摄像头显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_camera_active = False
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 主摄像头画面
        layout.addWidget(QLabel("<h2>实时监控 (Live View)</h2>"))
        
        self.lbl_camera = QLabel("摄像头画面未启动")
        self.lbl_camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_camera.setStyleSheet("background-color: black; border: 2px solid #333;")
        self.lbl_camera.setMinimumSize(480, 360)
        layout.addWidget(self.lbl_camera, 2)
        
        # 调试蒙版
        layout.addWidget(QLabel("<h3>算法调试 (Debug Mask)</h3>"))
        
        self.lbl_mask = QLabel("Mask 蒙版 (调试)")
        self.lbl_mask.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mask.setStyleSheet("background-color: #222; border: 1px dashed #555;")
        self.lbl_mask.setMinimumSize(320, 240)
        self.lbl_mask.setMaximumHeight(300)
        layout.addWidget(self.lbl_mask, 1)

    def set_camera_active(self, active: bool):
        """设置相机激活状态"""
        self.is_camera_active = active
    
    @pyqtSlot(QImage)
    def update_camera_feed(self, qt_img):
        """更新摄像头画面"""
        if not self.is_camera_active:
            return
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(
            self.lbl_camera.size(), 
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self.lbl_camera.setPixmap(scaled)
    
    @pyqtSlot(QImage)
    def update_mask_feed(self, qt_img):
        """更新调试蒙版"""
        if not self.is_camera_active:
            return
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(
            self.lbl_mask.size(), 
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self.lbl_mask.setPixmap(scaled)

    def show_blank_screen(self, text="相机未运行 (Camera Not Running)"):
        """清空画面，显示黑屏与提示文字"""
        self.is_camera_active = False
        self.lbl_camera.clear()
        self.lbl_camera.setText(f"<font color='#888888'><h3>📷 {text}</h3></font>")
        self.lbl_mask.clear()
        self.lbl_mask.setText("<font color='#666666'>Mask 蒙版 (已停止)</font>")
