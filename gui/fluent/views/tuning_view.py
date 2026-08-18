# -*- coding: utf-8 -*-
"""
PID 参数调优与运动诊断视图 (Tuning & Diagnostics View) - 像素级对齐版

布局设计：
- 独立的现代 Fluent CardWidget：
  1. PID 闭环控制参数卡片 (Kp, Ki, Kd, Deadzone, 轴反转, 保存/重置)
  2. 手动阶跃与云台校准卡片 (D-Pad 方向微调与键盘直控开关)
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QScrollArea
)
from qfluentwidgets import (
    CardWidget, Slider, DoubleSpinBox, SpinBox, SwitchButton,
    PushButton, PrimaryPushButton, FluentIcon,
    StrongBodyLabel, CaptionLabel, BodyLabel, InfoBar, InfoBarPosition
)

from gui.fluent.common.event_filters import apply_wheel_protection


class TuningView(QWidget):
    """PID 调优与诊断视图"""

    # 信号
    pid_changed = pyqtSignal(float, float, float)     # (kp, ki, kd)
    invert_changed = pyqtSignal(bool, bool)           # (invert_x, invert_y)
    deadzone_changed = pyqtSignal(int)
    save_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    # 运动诊断信号
    start_continuous_signal = pyqtSignal(str, int)    # axis, dir
    stop_continuous_signal = pyqtSignal()
    keyboard_control_toggled = pyqtSignal(bool)

    def __init__(self, initial_kp=0.60, initial_ki=0.16, initial_kd=0.50,
                 initial_deadzone=5, invert_x=False, invert_y=True, parent=None):
        super().__init__(parent)
        self.setObjectName("TuningView")

        self._kp = initial_kp
        self._ki = initial_ki
        self._kd = initial_kd
        self._deadzone = initial_deadzone
        self._invert_x = invert_x
        self._invert_y = invert_y

        self._is_updating = False
        self.init_ui()
        apply_wheel_protection(self)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        cards_layout = QVBoxLayout(content_widget)
        cards_layout.setContentsMargins(0, 0, 10, 0)
        cards_layout.setSpacing(16)

        # ----------------------------------
        # 卡片 1: PID 闭环控制参数 (CardWidget)
        # ----------------------------------
        pid_card = CardWidget()
        pid_layout = QVBoxLayout(pid_card)
        pid_layout.setContentsMargins(22, 20, 22, 22)
        pid_layout.setSpacing(16)

        card_title_1 = StrongBodyLabel("⚙️ PID 闭环追踪参数 (Real-Time Control Loop)")
        card_title_1.setStyleSheet("font-size: 15px; font-weight: bold; margin-bottom: 4px;")
        pid_layout.addWidget(card_title_1)

        # 比例增益 Kp
        self.kp_slider, self.kp_spin = self._create_param_row(
            pid_layout, "比例增益 (Kp - 响应速度):", 0.0, 5.0, self._kp, 0.01, 2
        )
        self.kp_slider.valueChanged.connect(self._on_kp_slider_changed)
        self.kp_spin.valueChanged.connect(self._on_kp_spin_changed)

        # 积分增益 Ki
        self.ki_slider, self.ki_spin = self._create_param_row(
            pid_layout, "积分增益 (Ki - 消除静差):", 0.0, 1.0, self._ki, 0.01, 3
        )
        self.ki_slider.valueChanged.connect(self._on_ki_slider_changed)
        self.ki_spin.valueChanged.connect(self._on_ki_spin_changed)

        # 微分增益 Kd
        self.kd_slider, self.kd_spin = self._create_param_row(
            pid_layout, "微分增益 (Kd - 抑制震荡):", 0.0, 2.0, self._kd, 0.01, 2
        )
        self.kd_slider.valueChanged.connect(self._on_kd_slider_changed)
        self.kd_spin.valueChanged.connect(self._on_kd_spin_changed)

        # 死区 Deadzone
        dz_layout = QHBoxLayout()
        dz_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        dz_label = BodyLabel("目标死区 (Deadzone px):")
        self.dz_spin = SpinBox()
        self.dz_spin.setFixedHeight(32)
        self.dz_spin.setRange(0, 50)
        self.dz_spin.setValue(self._deadzone)
        self.dz_spin.valueChanged.connect(self._on_deadzone_changed)
        self.dz_spin.setFixedWidth(110)
        dz_layout.addWidget(dz_label)
        dz_layout.addStretch()
        dz_layout.addWidget(self.dz_spin)
        pid_layout.addLayout(dz_layout)

        # 轴向反转 (Invert X / Y)
        invert_layout = QHBoxLayout()
        invert_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        inv_x_label = BodyLabel("X 轴反向:")
        self.switch_inv_x = SwitchButton()
        self.switch_inv_x.setFixedHeight(32)
        self.switch_inv_x.setChecked(self._invert_x)
        self.switch_inv_x.checkedChanged.connect(self._on_invert_changed)

        inv_y_label = BodyLabel("Y 轴反向:")
        self.switch_inv_y = SwitchButton()
        self.switch_inv_y.setFixedHeight(32)
        self.switch_inv_y.setChecked(self._invert_y)
        self.switch_inv_y.checkedChanged.connect(self._on_invert_changed)

        invert_layout.addWidget(inv_x_label)
        invert_layout.addWidget(self.switch_inv_x)
        invert_layout.addSpacing(28)
        invert_layout.addWidget(inv_y_label)
        invert_layout.addWidget(self.switch_inv_y)
        invert_layout.addStretch()
        pid_layout.addLayout(invert_layout)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        btn_layout.setSpacing(12)

        self.btn_save = PrimaryPushButton(FluentIcon.SAVE, "保存参数配置")
        self.btn_save.setFixedHeight(36)
        self.btn_save.clicked.connect(self._on_save_clicked)

        self.btn_reset = PushButton(FluentIcon.SYNC, "恢复出厂预设")
        self.btn_reset.setFixedHeight(36)
        self.btn_reset.clicked.connect(self._on_reset_clicked)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_reset)
        pid_layout.addLayout(btn_layout)

        cards_layout.addWidget(pid_card)

        # ----------------------------------
        # 卡片 2: 手动阶跃与运动测试 (CardWidget)
        # ----------------------------------
        manual_card = CardWidget()
        manual_layout = QVBoxLayout(manual_card)
        manual_layout.setContentsMargins(22, 20, 22, 22)
        manual_layout.setSpacing(16)

        card_title_2 = StrongBodyLabel("🎮 云台运动诊断与方向测试 (Manual Diagnostics)")
        card_title_2.setStyleSheet("font-size: 15px; font-weight: bold; margin-bottom: 4px;")
        manual_layout.addWidget(card_title_2)

        # D-Pad 方向键
        dpad_container = QHBoxLayout()
        dpad_grid = QGridLayout()
        dpad_grid.setSpacing(8)

        self.btn_up = PushButton("▲")
        self.btn_down = PushButton("▼")
        self.btn_left = PushButton("◀")
        self.btn_right = PushButton("▶")

        for btn in (self.btn_up, self.btn_down, self.btn_left, self.btn_right):
            btn.setFixedSize(54, 42)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.btn_up.pressed.connect(lambda: self.start_continuous_signal.emit('y', 1))
        self.btn_up.released.connect(self.stop_continuous_signal.emit)

        self.btn_down.pressed.connect(lambda: self.start_continuous_signal.emit('y', -1))
        self.btn_down.released.connect(self.stop_continuous_signal.emit)

        self.btn_left.pressed.connect(lambda: self.start_continuous_signal.emit('x', -1))
        self.btn_left.released.connect(self.stop_continuous_signal.emit)

        self.btn_right.pressed.connect(lambda: self.start_continuous_signal.emit('x', 1))
        self.btn_right.released.connect(self.stop_continuous_signal.emit)

        dpad_grid.addWidget(self.btn_up, 0, 1)
        dpad_grid.addWidget(self.btn_left, 1, 0)
        dpad_grid.addWidget(self.btn_right, 1, 2)
        dpad_grid.addWidget(self.btn_down, 1, 1)

        dpad_container.addStretch()
        dpad_container.addLayout(dpad_grid)
        dpad_container.addStretch()
        manual_layout.addLayout(dpad_container)

        # 键盘全局直控说明与开关
        kb_box = QHBoxLayout()
        kb_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        kb_label = BodyLabel("全局键盘直控 (WASD / 方向键):")
        self.switch_keyboard = SwitchButton()
        self.switch_keyboard.setFixedHeight(32)
        self.switch_keyboard.setChecked(True)
        self.switch_keyboard.checkedChanged.connect(self.keyboard_control_toggled.emit)
        kb_box.addWidget(kb_label)
        kb_box.addStretch()
        kb_box.addWidget(self.switch_keyboard)
        manual_layout.addLayout(kb_box)

        cards_layout.addWidget(manual_card)
        cards_layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def _create_param_row(self, layout, title, min_val, max_val, init_val, step, decimals):
        vbox = QVBoxLayout()
        vbox.setSpacing(6)

        header = QHBoxLayout()
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        label = BodyLabel(title)
        spin = DoubleSpinBox()
        spin.setFixedHeight(32)
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setValue(init_val)
        spin.setFixedWidth(110)

        header.addWidget(label)
        header.addStretch()
        header.addWidget(spin)
        vbox.addLayout(header)

        slider = Slider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(26)
        slider.setRange(int(min_val * 100), int(max_val * 100))
        slider.setValue(int(init_val * 100))
        slider.setSingleStep(int(step * 100))
        vbox.addWidget(slider)

        layout.addLayout(vbox)
        return slider, spin

    def _on_kp_slider_changed(self, val):
        if self._is_updating:
            return
        self._is_updating = True
        self._kp = val / 100.0
        self.kp_spin.setValue(self._kp)
        self._is_updating = False
        self._emit_pid()

    def _on_kp_spin_changed(self, val):
        if self._is_updating:
            return
        self._is_updating = True
        self._kp = val
        self.kp_slider.setValue(int(val * 100))
        self._is_updating = False
        self._emit_pid()

    def _on_ki_slider_changed(self, val):
        if self._is_updating:
            return
        self._is_updating = True
        self._ki = val / 100.0
        self.ki_spin.setValue(self._ki)
        self._is_updating = False
        self._emit_pid()

    def _on_ki_spin_changed(self, val):
        if self._is_updating:
            return
        self._is_updating = True
        self._ki = val
        self.ki_slider.setValue(int(val * 100))
        self._is_updating = False
        self._emit_pid()

    def _on_kd_slider_changed(self, val):
        if self._is_updating:
            return
        self._is_updating = True
        self._kd = val / 100.0
        self.kd_spin.setValue(self._kd)
        self._is_updating = False
        self._emit_pid()

    def _on_kd_spin_changed(self, val):
        if self._is_updating:
            return
        self._is_updating = True
        self._kd = val
        self.kd_slider.setValue(int(val * 100))
        self._is_updating = False
        self._emit_pid()

    def _on_deadzone_changed(self, val):
        self._deadzone = val
        self.deadzone_changed.emit(val)

    def _on_invert_changed(self):
        inv_x = self.switch_inv_x.isChecked()
        inv_y = self.switch_inv_y.isChecked()
        self.invert_changed.emit(inv_x, inv_y)

    def _emit_pid(self):
        self.pid_changed.emit(self._kp, self._ki, self._kd)

    def _on_save_clicked(self):
        self.save_requested.emit()
        InfoBar.success(
            title="配置已保存",
            content="PID 参数与反转设置已成功持久化保存到配置文件。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def _on_reset_clicked(self):
        self.reset_requested.emit()
        InfoBar.info(
            title="参数已重置",
            content="已恢复为默认 PID 参数预设值。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def set_pid_values(self, kp, ki, kd, invert_x=None, invert_y=None, deadzone=None):
        """外部同步设置参数"""
        self._is_updating = True
        self._kp = kp
        self._ki = ki
        self._kd = kd
        self.kp_spin.setValue(kp)
        self.kp_slider.setValue(int(kp * 100))
        self.ki_spin.setValue(ki)
        self.ki_slider.setValue(int(ki * 100))
        self.kd_spin.setValue(kd)
        self.kd_slider.setValue(int(kd * 100))

        if invert_x is not None:
            self.switch_inv_x.setChecked(invert_x)
        if invert_y is not None:
            self.switch_inv_y.setChecked(invert_y)
        if deadzone is not None:
            self.dz_spin.setValue(deadzone)
        self._is_updating = False
