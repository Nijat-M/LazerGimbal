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


class CameraPanel(QGroupBox):
    """摄像头选择面板"""
    
    # 信号：摄像头切换和关闭
    camera_changed = pyqtSignal(int, int, int)  # (camera_id, width, height)
    camera_toggled = pyqtSignal(bool)           # 开启/关闭信号
    flip_changed = pyqtSignal(str)              # 画面翻转信号 ("NONE", "180", "V", "H")
    open_settings_requested = pyqtSignal()      # 请求打开 DirectShow 相机硬件属性面板

    def __init__(self, default_id=0, parent=None):
        super().__init__("摄像头设置 (Camera Settings)", parent)
        self.available_cameras = []
        self.is_camera_open = False
        self.init_ui(default_id)
        # 延迟检测，不阻塞 UI 启动
        QTimer.singleShot(500, self.detect_cameras)
    
    def init_ui(self, default_id):
        """初始化UI"""
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # 1. 摄像头选择下拉框
        self.combo_camera = QComboBox()
        self.combo_camera.setToolTip("选择要使用的摄像头设备")
        
        # 2. 分辨率选择（聚焦于工业级最稳妥的 60 FPS 档位）
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems([
            "640x480 (标清推荐 - 60 FPS 极速响应)",
            "1280x720 (高清平衡 - 60 FPS 视野更宽)",
            "1920x1080 (全高清 - 60 FPS 细节丰富)"
        ])
        self.combo_resolution.setCurrentIndex(0)  # 默认 640x480
        self.combo_resolution.setToolTip("选择工作分辨率（640x480 延迟最低、PID 闭环响应最快）")
        
        # 3. 画面方向/翻转选择 (即时热切换)
        self.combo_flip = QComboBox()
        self.combo_flip.addItem("正常 (Normal)", "NONE")
        self.combo_flip.addItem("180° 翻转 (倒装安装)", "180")
        self.combo_flip.addItem("垂直翻转 (Vertical)", "V")
        self.combo_flip.addItem("水平镜像 (Horizontal)", "H")
        initial_flip_idx = self.combo_flip.findData(getattr(VisionConfig, "FLIP_MODE", "NONE"))
        if initial_flip_idx >= 0:
            self.combo_flip.setCurrentIndex(initial_flip_idx)
        self.combo_flip.currentIndexChanged.connect(self._on_flip_changed)
        self.combo_flip.setToolTip("选择后立即生效，无需重启摄像头")

        # 4. 主操作按钮组
        self.btn_toggle = QPushButton("开启摄像头 (Open)")
        self.btn_toggle.clicked.connect(self._on_toggle_clicked)
        self.btn_toggle.setStyleSheet("background-color: #007bff; color: white; padding: 5px;")
        self.btn_toggle.setToolTip("打开或关闭摄像头的读取线程")

        self.btn_apply = QPushButton("切换设置 (Apply)")
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_apply.setStyleSheet("background-color: #5cb85c; color: white; padding: 5px;")
        self.btn_apply.setToolTip("切换分辨率或摄像头设备后点击生效")
        
        btn_main_layout = QHBoxLayout()
        btn_main_layout.addWidget(self.btn_toggle)
        btn_main_layout.addWidget(self.btn_apply)

        # 5. 硬件与辅助工具按钮组
        self.btn_settings = QPushButton("⚙️ 曝光/增益调参")
        self.btn_settings.clicked.connect(self._on_settings_clicked)
        self.btn_settings.setStyleSheet("background-color: #495057; color: white; padding: 4px;")
        self.btn_settings.setToolTip("打开 DirectShow / 工业相机原生驱动面板，微调曝光时间与增益")

        self.btn_refresh = QPushButton("🔄 刷新设备")
        self.btn_refresh.clicked.connect(self.detect_cameras)
        self.btn_refresh.setStyleSheet("padding: 4px;")
        self.btn_refresh.setToolTip("重新扫描连接的 USB 摄像头")
        
        btn_tool_layout = QHBoxLayout()
        btn_tool_layout.addWidget(self.btn_settings)
        btn_tool_layout.addWidget(self.btn_refresh)

        # 6. 状态标签
        self.lbl_status = QLabel("未开启 - 请点击开启摄像头")
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

        layout.addRow("实时状态:", self.lbl_vision_stats)
        layout.addRow("设备:", self.combo_camera)
        layout.addRow("分辨率:", self.combo_resolution)
        layout.addRow("画面方向:", self.combo_flip)
        layout.addRow(btn_main_layout)
        layout.addRow(btn_tool_layout)
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
                # 只有一个摄像头，自动选择
                self.combo_camera.setCurrentIndex(0)
                msg = f"✓ 已检测到 Camera {self.available_cameras[0]}"
            else:
                msg = f"✓ 已检测到 {num_cameras} 个摄像头"
            
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("color: green; font-size: 10px;")
        else:
            msg = "未检测到摄像头！请检查设备连接"
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("color: red; font-size: 10px;")
    
    def _on_toggle_clicked(self):
        """开启或关闭摄像头"""
        if not self.available_cameras:
            self.lbl_status.setText("没有可用的摄像头！请重试")
            self.lbl_status.setStyleSheet("color: red; font-size: 10px;")
            return
            
        self.is_camera_open = not self.is_camera_open
        
        if self.is_camera_open:
            self.btn_toggle.setText("关闭摄像头 (Close)")
            self.btn_toggle.setStyleSheet("background-color: #dc3545; color: white;")
            self.camera_toggled.emit(True)
            self._on_apply_clicked()  # 触发发送 camera_changed
        else:
            self.btn_toggle.setText("开启摄像头 (Open)")
            self.btn_toggle.setStyleSheet("background-color: #007bff; color: white;")
            self.camera_toggled.emit(False)
            self.lbl_status.setText("摄像头已关闭")
            self.lbl_status.setStyleSheet("color: gray; font-size: 10px;")

    def _on_flip_changed(self, index: int):
        """画面翻转下拉框选择改变"""
        mode = self.combo_flip.currentData()
        if mode:
            self.flip_changed.emit(mode)

    def _on_settings_clicked(self):
        """点击打开 DirectShow 原生工业相机调参面板"""
        if not self.is_camera_open:
            self.lbl_status.setText("请先开启摄像头再调节硬件参数！")
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
            self.lbl_status.setText("没有可用摄像头！")
            self.lbl_status.setStyleSheet("color: red; font-size: 10px;")
            return
            
        if not self.is_camera_open:
            self.lbl_status.setText("请先开启摄像头再切换设置")
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
