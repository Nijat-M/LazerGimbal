from PyQt6.QtWidgets import QGroupBox, QGridLayout, QVBoxLayout, QPushButton, QCheckBox
from PyQt6.QtCore import pyqtSignal, Qt
from utils.logger import Logger
logger = Logger("TestPanel")


class TestModePanel(QGroupBox):
    """
    手动电机与键盘操控面板 (Manual Motor & Keyboard Control)
    - 屏幕方向键：按住连续旋转，松开即停
    - 键盘 WASD / 方向键：随时快捷操控电机
    - 结合 1/2/3 档位调节速度
    """
    request_move_signal = pyqtSignal(str, int)          # 单步微调
    start_continuous_signal = pyqtSignal(str, int)      # 按住开始连续转动
    stop_continuous_signal = pyqtSignal()               # 松开停止
    keyboard_control_toggled = pyqtSignal(bool)         # 键盘控制开关

    def __init__(self, parent=None):
        super().__init__("🎮 Manual Motor & Keyboard Control", parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(6)
        
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        self.btn_left = QPushButton("◀")
        self.btn_right = QPushButton("▶")
        
        # 按钮现代化暗色战术样式
        btn_style = """
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
                border-color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #0369a1;
                color: #f1f5f9;
            }
        """
        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right]:
            btn.setFixedSize(44, 36)
            btn.setStyleSheet(btn_style)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # 绑定按住开始与松开停止
        self.btn_up.pressed.connect(lambda: self._emit_start('y', 1, 'Up'))
        self.btn_up.released.connect(self._emit_stop)

        self.btn_down.pressed.connect(lambda: self._emit_start('y', -1, 'Down'))
        self.btn_down.released.connect(self._emit_stop)

        self.btn_left.pressed.connect(lambda: self._emit_start('x', -1, 'Left'))
        self.btn_left.released.connect(self._emit_stop)

        self.btn_right.pressed.connect(lambda: self._emit_start('x', 1, 'Right'))
        self.btn_right.released.connect(self._emit_stop)

        # 布局方向键
        grid_layout.addWidget(self.btn_up, 0, 1)
        grid_layout.addWidget(self.btn_left, 1, 0)
        grid_layout.addWidget(self.btn_right, 1, 2)
        grid_layout.addWidget(self.btn_down, 1, 1)
        main_layout.addLayout(grid_layout)

        # 键盘控制开关选项（默认开启）
        self.cb_keyboard = QCheckBox("⌨ Enable Keyboard Control (WASD / Arrows)")
        self.cb_keyboard.setChecked(True)
        self.cb_keyboard.setStyleSheet("color: #38bdf8; font-weight: 500; font-size: 11px;")
        self.cb_keyboard.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cb_keyboard.toggled.connect(self.keyboard_control_toggled.emit)
        main_layout.addWidget(self.cb_keyboard)
    
    def _emit_start(self, axis, direction, name):
        self.start_continuous_signal.emit(axis, direction)

    def _emit_stop(self):
        self.stop_continuous_signal.emit()


