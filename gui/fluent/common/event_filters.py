# -*- coding: utf-8 -*-
"""
全局事件过滤器与交互优化模块 (Event Filters & Interaction Enhancements)

功能：
1. GlobalKeyFilter: 全局拦截方向键(↑↓←→)、WASD、空格键(开火)、Esc(急停/退出)，无论焦点在哪个按钮，均可直接控制云台。
2. WheelAntiAccidentFilter: 阻止 SpinBox / Slider / ComboBox 在非主动聚焦时被滚轮意外修改。
"""

from PyQt6.QtCore import QObject, QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QWidget, QLineEdit, QTextEdit, QPlainTextEdit,
    QAbstractSpinBox, QSlider, QComboBox
)


class GlobalKeyFilter(QObject):
    """
    全局键盘快捷键拦截器
    
    保证在整个应用中，只要用户没有在文本框中输入文字：
    - W/A/S/D 与 ↑/↓/←/→ 均能平滑控制云台转动
    - Space 按住即发射激光 (在 Armed 状态下)
    - Esc 退出全屏 / 释放鼠标 / 触发急停
    """
    
    # 快捷键事件信号
    manual_move_press = pyqtSignal(str, int)   # axis ('x'/'y'), direction (1/-1)
    manual_move_release = pyqtSignal()         # 停止平移
    laser_fire_press = pyqtSignal()            # 触发开火
    laser_fire_release = pyqtSignal()          # 停止开火
    emergency_stop_triggered = pyqtSignal()    # 触发急停
    fullscreen_toggle = pyqtSignal()           # 切换全屏

    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyboard_control_enabled = True   # 默认开启键盘直控

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            if key_event.isAutoRepeat():
                return False
            
            # 如果当前聚焦的是输入框，则不拦截正常文字输入
            if isinstance(watched, (QLineEdit, QTextEdit, QPlainTextEdit)):
                return False

            key = key_event.key()

            # F11: 切换全屏
            if key == Qt.Key.Key_F11:
                self.fullscreen_toggle.emit()
                return True

            # Esc: 急停 / 退出
            if key == Qt.Key.Key_Escape:
                self.emergency_stop_triggered.emit()
                return True

            # Space: 激光击发
            if key == Qt.Key.Key_Space:
                self.laser_fire_press.emit()
                return True

            # 方向键与 WASD 控制云台
            if self.keyboard_control_enabled:
                if key in (Qt.Key.Key_Up, Qt.Key.Key_W):
                    self.manual_move_press.emit('y', 1)
                    return True
                elif key in (Qt.Key.Key_Down, Qt.Key.Key_S):
                    self.manual_move_press.emit('y', -1)
                    return True
                elif key in (Qt.Key.Key_Left, Qt.Key.Key_A):
                    self.manual_move_press.emit('x', -1)
                    return True
                elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
                    self.manual_move_press.emit('x', 1)
                    return True

        elif event.type() == QEvent.Type.KeyRelease:
            key_event: QKeyEvent = event
            if key_event.isAutoRepeat():
                return False

            if isinstance(watched, (QLineEdit, QTextEdit, QPlainTextEdit)):
                return False

            key = key_event.key()

            # 松开空格: 停止发射
            if key == Qt.Key.Key_Space:
                self.laser_fire_release.emit()
                return True

            # 松开方向键: 刹车
            if self.keyboard_control_enabled:
                if key in (Qt.Key.Key_Up, Qt.Key.Key_W, Qt.Key.Key_Down, Qt.Key.Key_S,
                           Qt.Key.Key_Left, Qt.Key.Key_A, Qt.Key.Key_Right, Qt.Key.Key_D):
                    self.manual_move_release.emit()
                    return True

        return super().eventFilter(watched, event)


class WheelAntiAccidentFilter(QObject):
    """
    滚轮防误触过滤器
    
    安装在 SpinBox, Slider, ComboBox 或其容器上：
    当控件未获得焦点时，滚轮事件被忽略并向上传递给 ScrollArea，防止滑动页面时意外修改参数。
    """
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel:
            if isinstance(watched, (QAbstractSpinBox, QSlider, QComboBox)):
                if not watched.hasFocus():
                    event.ignore()
                    return True
        return super().eventFilter(watched, event)


def apply_wheel_protection(widget: QWidget):
    """递归为组件内所有的 SpinBox、Slider、ComboBox 安装滚轮防误触保护"""
    filter_inst = WheelAntiAccidentFilter(widget)
    for child in widget.findChildren((QAbstractSpinBox, QSlider, QComboBox)):
        child.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        child.installEventFilter(filter_inst)
