
from PyQt6.QtWidgets import QGroupBox, QGridLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt

class TestModePanel(QGroupBox):
    """
    测试模式控制面板 (Test Mode Control Panel)
    分离 UI 逻辑，负责接收用户输入 (按钮/键盘) 并发送信号。
    """
    # 信号: 请求移动舵机 (轴 'x'/'y', 方向 1/-1)
    request_move_signal = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__("手动测试 (Manual Control)", parent)
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout()
        layout.setContentsMargins(5, 5, 5, 5)  # 减小边距
        layout.setSpacing(5)  # 减小间距
        
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        self.btn_left = QPushButton("◀")
        self.btn_right = QPushButton("▶")
        
        # 按钮样式 - 更紧凑
        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right]:
            btn.setFixedSize(40, 40)  # 从50x50改为40x40
            btn.setStyleSheet("font-size: 18px; font-weight: bold;")

        # 连接信号（添加调试输出）
        self.btn_up.clicked.connect(lambda: self._emit_move('y', -1, '上'))
        self.btn_down.clicked.connect(lambda: self._emit_move('y', 1, '下'))
        self.btn_left.clicked.connect(lambda: self._emit_move('x', 1, '左'))
        self.btn_right.clicked.connect(lambda: self._emit_move('x', -1, '右'))

        # 布局
        layout.addWidget(self.btn_up, 0, 1)
        layout.addWidget(self.btn_left, 1, 0)
        layout.addWidget(self.btn_right, 1, 2)
        layout.addWidget(self.btn_down, 1, 1)
        
        self.setLayout(layout)
    
    def _emit_move(self, axis, direction, name):
        """发射移动信号（带调试信息）"""
        print(f"[TEST_PANEL] 按钮点击: {name} (轴={axis}, 方向={direction})")
        self.request_move_signal.emit(axis, direction)
