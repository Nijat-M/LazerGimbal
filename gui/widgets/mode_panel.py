# -*- coding: utf-8 -*-
"""
模式选择面板 (Mode Selection Panel)

工作模式：待机、自动追踪、按钮测试和 FPS 风格鼠标瞄准。
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QRadioButton, 
    QButtonGroup, QMessageBox
)
from PyQt6.QtCore import pyqtSignal


class ModePanel(QGroupBox):
    """模式选择面板"""
    
    # 信号：模式改变
    mode_changed = pyqtSignal(str)  # "IDLE", "TRACKING", "TEST"
    
    def __init__(self, parent=None):
        super().__init__("工作模式 (Mode)", parent)
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 按钮组
        self.mode_group = QButtonGroup(self)
        
        # 工作模式单选框
        self.rb_idle = QRadioButton("待机 (IDLE)")
        self.rb_tracking = QRadioButton("激光追踪 (Laser Tracking)")
        self.rb_blue_tracking = QRadioButton("蓝色物体追踪 (Blue Object)")
        self.rb_yolo_tracking = QRadioButton("YOLO 人体追踪 (YOLO Tracking)")
        self.rb_test = QRadioButton("测试模式 (Test Mode)")
        self.rb_mouse_manual = QRadioButton("鼠标手动瞄准 (Mouse Aim)")
        
        self.rb_idle.setChecked(True)
        
        # 设置提示文本
        self.rb_tracking.setToolTip("红色激光追踪蓝色物体")
        self.rb_blue_tracking.setToolTip("让蓝色物体居中在画面中央")
        self.rb_yolo_tracking.setToolTip("使用 YOLO26 端到端深度学习模型使得人体居中在画面中央")
        self.rb_mouse_manual.setToolTip("点击实时画面捕获鼠标，像 FPS 游戏一样手动瞄准")
        
        self.mode_group.addButton(self.rb_idle, 0)
        self.mode_group.addButton(self.rb_tracking, 1)
        self.mode_group.addButton(self.rb_blue_tracking, 2)
        self.mode_group.addButton(self.rb_yolo_tracking, 4)
        self.mode_group.addButton(self.rb_test, 3)
        self.mode_group.addButton(self.rb_mouse_manual, 5)
        
        # 连接信号
        self.mode_group.idToggled.connect(self._on_mode_toggled)
        
        layout.addWidget(self.rb_idle)
        layout.addWidget(self.rb_tracking)
        layout.addWidget(self.rb_blue_tracking)
        layout.addWidget(self.rb_yolo_tracking)
        layout.addWidget(self.rb_test)
        layout.addWidget(self.rb_mouse_manual)
    
    def _on_mode_toggled(self, btn_id, checked):
        """模式切换处理"""
        if not checked:
            return
        
        mode_map = {
            0: "IDLE",
            1: "TRACKING",
            2: "BLUE_TRACKING",
            3: "TEST",
            4: "YOLO_TRACKING",
            5: "MANUAL_MOUSE",
        }
        mode = mode_map.get(btn_id, "IDLE")
        
        # 手动模式需要确认
        if mode in ("TEST", "MANUAL_MOUSE"):
            mode_name = "鼠标手动瞄准" if mode == "MANUAL_MOUSE" else "测试模式"
            reply = QMessageBox.question(
                self,
                f"确认进入{mode_name}",
                f"进入{mode_name}将允许手动控制云台。\n\n"
                "请确认：\n"
                "1. 云台周围无障碍物\n"
                "2. 舵机软限位已校准\n"
                "3. 已准备好使用 Esc 立即停止\n\n"
                "是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                # 取消，回到待机模式
                self.rb_idle.setChecked(True)
                return
        
        # 发射信号
        self.mode_changed.emit(mode)
    
    def get_current_mode(self) -> str:
        """获取当前选中的模式字符串"""
        btn_id = self.mode_group.checkedId()
        mode_map = {
            0: "IDLE",
            1: "TRACKING",
            2: "BLUE_TRACKING",
            3: "TEST",
            4: "YOLO_TRACKING",
            5: "MANUAL_MOUSE",
        }
        return mode_map.get(btn_id, "IDLE")

    def set_mode(self, mode: str):
        """通过代码切换当前选中的模式"""
        if mode == "TRACKING":
            self.rb_tracking.setChecked(True)
        elif mode == "BLUE_TRACKING":
            self.rb_blue_tracking.setChecked(True)
        elif mode == "YOLO_TRACKING":
            self.rb_yolo_tracking.setChecked(True)
        elif mode == "TEST":
            self.rb_test.setChecked(True)
        elif mode == "MANUAL_MOUSE":
            self.rb_mouse_manual.setChecked(True)
        else:
            self.rb_idle.setChecked(True)

