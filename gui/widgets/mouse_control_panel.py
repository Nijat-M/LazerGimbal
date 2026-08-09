# -*- coding: utf-8 -*-
"""Status and tuning controls for FPS-style mouse aiming."""

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)


class MouseControlPanel(QGroupBox):
    sensitivity_changed = pyqtSignal(float)

    def __init__(self, initial_sensitivity: float, parent=None) -> None:
        super().__init__("鼠标瞄准 (Mouse Aim)", parent)
        self._init_ui(initial_sensitivity)

    def _init_ui(self, initial_sensitivity: float) -> None:
        layout = QVBoxLayout(self)

        self.status_label = QLabel("未捕获：点击实时画面开始控制")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.target_label = QLabel("虚拟目标：Yaw +0.00° | Pitch +0.00°")
        layout.addWidget(self.target_label)

        form = QFormLayout()
        self.sensitivity_spin = QDoubleSpinBox()
        self.sensitivity_spin.setRange(0.01, 1.00)
        self.sensitivity_spin.setSingleStep(0.01)
        self.sensitivity_spin.setDecimals(2)
        self.sensitivity_spin.setSuffix(" °/count")
        self.sensitivity_spin.setValue(initial_sensitivity)
        self.sensitivity_spin.valueChanged.connect(self.sensitivity_changed.emit)
        form.addRow("灵敏度", self.sensitivity_spin)
        layout.addLayout(form)

        instructions = QLabel(
            "点击实时画面捕获鼠标；移动鼠标控制云台；Esc、窗口失焦或切换模式会立即停止。"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: gray;")
        layout.addWidget(instructions)

    @pyqtSlot(bool)
    def set_capture_state(self, captured: bool) -> None:
        if captured:
            self.status_label.setText("已捕获：Esc 释放并停止")
            self.status_label.setStyleSheet("color: #00aa55; font-weight: bold;")
        else:
            self.status_label.setText("未捕获：点击实时画面开始控制")
            self.status_label.setStyleSheet("color: #cc8800;")

    @pyqtSlot(float, float)
    def update_target(self, yaw: float, pitch: float) -> None:
        self.target_label.setText(
            f"虚拟目标：Yaw {yaw:+.2f}° | Pitch {pitch:+.2f}°"
        )
