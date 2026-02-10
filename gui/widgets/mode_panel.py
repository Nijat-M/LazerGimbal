# -*- coding: utf-8 -*-
"""
模式选择面板 (Mode Selection Panel)

三种模式：
1. 待机 (IDLE) - 只显示画面
2. 视觉追踪 (TRACKING) - 自动追踪目标
3. 测试模式 (TEST) - 手动控制
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
        
        # 三个单选框
        self.rb_idle = QRadioButton("待机 (IDLE)")
        self.rb_tracking = QRadioButton("视觉追踪 (Tracking)")
        self.rb_test = QRadioButton("测试模式 (Test Mode)")
        
        self.rb_idle.setChecked(True)
        
        self.mode_group.addButton(self.rb_idle, 0)
        self.mode_group.addButton(self.rb_tracking, 1)
        self.mode_group.addButton(self.rb_test, 3)
        
        # 连接信号
        self.mode_group.idToggled.connect(self._on_mode_toggled)
        
        layout.addWidget(self.rb_idle)
        layout.addWidget(self.rb_tracking)
        layout.addWidget(self.rb_test)
    
    def _on_mode_toggled(self, btn_id, checked):
        """模式切换处理"""
        if not checked:
            return
        
        mode_map = {0: "IDLE", 1: "TRACKING", 3: "TEST"}
        mode = mode_map.get(btn_id, "IDLE")
        
        # 测试模式需要确认
        if mode == "TEST":
            reply = QMessageBox.question(
                self,
                "确认进入测试模式",
                "进入测试模式将允许手动控制舵机大幅度移动。\n\n"
                "请确认：\n"
                "1. 云台周围无障碍物\n"
                "2. 舵机软限位已校准\n\n"
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
    
    def get_current_mode(self):
        """获取当前模式"""
        if self.rb_tracking.isChecked():
            return "TRACKING"
        elif self.rb_test.isChecked():
            return "TEST"
        else:
            return "IDLE"
