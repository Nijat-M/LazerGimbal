from PyQt6.QtWidgets import QGroupBox, QGridLayout, QVBoxLayout, QPushButton, QCheckBox
from PyQt6.QtCore import pyqtSignal, Qt
from utils.logger import Logger
logger = Logger("TestPanel")


class TestModePanel(QGroupBox):
    """
    测试模式控制面板 (Test Mode Control Panel)
    支持：
    1. 点击单步微调
    2. 长按连续移动，松开即停
    3. 键盘控制独立开关 (WASD / 方向键)
    """
    request_move_signal = pyqtSignal(str, int)          # 单步微调
    start_continuous_signal = pyqtSignal(str, int)      # 按住开始连续转动
    stop_continuous_signal = pyqtSignal()               # 松开停止
    keyboard_control_toggled = pyqtSignal(bool)         # 键盘控制开关

    def __init__(self, parent=None):
        super().__init__("Manual Control", parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(6)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(5)
        
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        self.btn_left = QPushButton("◀")
        self.btn_right = QPushButton("▶")
        
        # 按钮样式
        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right]:
            btn.setFixedSize(40, 40)
            btn.setStyleSheet("font-size: 18px; font-weight: bold;")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus) # 避免抢占焦点

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

        # 键盘控制开关选项（默认关闭，需要勾选才激活）
        self.cb_keyboard = QCheckBox("🎮 Enable Keyboard Control (WASD/Arrows)")
        self.cb_keyboard.setChecked(False)
        self.cb_keyboard.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cb_keyboard.toggled.connect(self.keyboard_control_toggled.emit)
        main_layout.addWidget(self.cb_keyboard)
    
    def _emit_start(self, axis, direction, name):
        logger.info(f"[TEST_PANEL] Button pressed: {name} (axis={axis}, dir={direction})")
        self.start_continuous_signal.emit(axis, direction)

    def _emit_stop(self):
        logger.info("[TEST_PANEL] Button released, stopping")
        self.stop_continuous_signal.emit()


