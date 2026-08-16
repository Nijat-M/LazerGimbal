# -*- coding: utf-8 -*-
"""
模式选择面板 (Mode Selection Panel)

工作模式：待机、蓝色物体追踪、YOLO 追踪、按钮测试和 FPS 风格鼠标瞄准。
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QRadioButton, 
    QButtonGroup, QMessageBox
)
from PyQt6.QtCore import pyqtSignal


class ModePanel(QGroupBox):
    """模式选择面板"""
    
    # 信号：模式改变
    mode_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__("Mode", parent)
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 按钮组
        self.mode_group = QButtonGroup(self)
        
        # 工作模式单选框
        self.rb_idle = QRadioButton("IDLE")
        self.rb_blue_tracking = QRadioButton("Blue Object Tracking")
        self.rb_yolo_tracking = QRadioButton("YOLO Tracking")
        self.rb_test = QRadioButton("Test Mode")
        self.rb_mouse_manual = QRadioButton("Mouse Aim")
        
        self.rb_idle.setChecked(True)
        
        # 设置提示文本
        self.rb_blue_tracking.setToolTip("Center blue object")
        self.rb_yolo_tracking.setToolTip("Center human using YOLO")
        self.rb_mouse_manual.setToolTip("Click live view to capture mouse for manual aiming")
        
        self.mode_group.addButton(self.rb_idle, 0)
        self.mode_group.addButton(self.rb_blue_tracking, 1)
        self.mode_group.addButton(self.rb_yolo_tracking, 2)
        self.mode_group.addButton(self.rb_test, 3)
        self.mode_group.addButton(self.rb_mouse_manual, 4)
        
        # 连接信号
        self.mode_group.idToggled.connect(self._on_mode_toggled)
        
        layout.addWidget(self.rb_idle)
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
            1: "BLUE_TRACKING",
            2: "YOLO_TRACKING",
            3: "TEST",
            4: "MANUAL_MOUSE",
        }
        mode = mode_map.get(btn_id, "IDLE")
        
        # 手动模式需要确认
        if mode in ("TEST", "MANUAL_MOUSE"):
            mode_name = "鼠标手动瞄准" if mode == "MANUAL_MOUSE" else "测试模式"
            reply = QMessageBox.question(
                self,
                f"确认进入{mode_name}",
                f"进入{mode_name}将允许手动控制云台。\n\n"
                "Please confirm:\n"
                "1. No obstacles around gimbal\n"
                "2. Servo soft limits calibrated\n"
                "3. Ready to press Esc to stop immediately\n\n"
                "Continue?",
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
            1: "BLUE_TRACKING",
            2: "YOLO_TRACKING",
            3: "TEST",
            4: "MANUAL_MOUSE",
        }
        return mode_map.get(btn_id, "IDLE")

    def set_mode(self, mode: str):
        """通过代码切换当前选中的模式"""
        if mode == "BLUE_TRACKING":
            self.rb_blue_tracking.setChecked(True)
        elif mode == "YOLO_TRACKING":
            self.rb_yolo_tracking.setChecked(True)
        elif mode == "TEST":
            self.rb_test.setChecked(True)
        elif mode == "MANUAL_MOUSE":
            self.rb_mouse_manual.setChecked(True)
        else:
            self.rb_idle.setChecked(True)

