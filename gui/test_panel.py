
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
        
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        self.btn_left = QPushButton("◀")
        self.btn_right = QPushButton("▶")
        
        # 按钮样式
        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right]:
            btn.setFixedSize(50, 50)
            btn.setStyleSheet("font-size: 20px; font-weight: bold;")

        # 连接信号
        # 注意: 这里只发射信号，不直接控制串口或修改配置
        self.btn_up.clicked.connect(lambda: self.request_move_signal.emit('y', -1))
        self.btn_down.clicked.connect(lambda: self.request_move_signal.emit('y', 1))
        self.btn_left.clicked.connect(lambda: self.request_move_signal.emit('x', 1)) 
        self.btn_right.clicked.connect(lambda: self.request_move_signal.emit('x', -1))

        # 布局
        layout.addWidget(self.btn_up, 0, 1)
        layout.addWidget(self.btn_left, 1, 0)
        layout.addWidget(self.btn_right, 1, 2)
        layout.addWidget(self.btn_down, 1, 1)
        
        self.setLayout(layout)

    def handle_key_event(self, event):
        """
        处理键盘事件 (被 MainWindow 调用)
        :return: True if handled, False otherwise
        """
        if not self.isVisible():
            return False

        key = event.key()
        if key == Qt.Key.Key_Up:
            self.request_move_signal.emit('y', -1)
            return True
        elif key == Qt.Key.Key_Down:
            self.request_move_signal.emit('y', 1)
            return True
        elif key == Qt.Key.Key_Left:
            self.request_move_signal.emit('x', 1)
            return True
        elif key == Qt.Key.Key_Right:
            self.request_move_signal.emit('x', -1)
            return True
        
        return False
