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
        super().__init__("Mouse Aim Control", parent)
        self._init_ui(initial_sensitivity)

    def _init_ui(self, initial_sensitivity: float) -> None:
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Uncaptured: Click live view to start")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.target_label = QLabel("Virtual Target: Yaw +0.00° | Pitch +0.00°")
        layout.addWidget(self.target_label)

        form = QFormLayout()
        self.sensitivity_spin = QDoubleSpinBox()
        self.sensitivity_spin.setRange(0.01, 1.00)
        self.sensitivity_spin.setSingleStep(0.01)
        self.sensitivity_spin.setDecimals(2)
        self.sensitivity_spin.setSuffix(" °/count")
        self.sensitivity_spin.setValue(initial_sensitivity)
        self.sensitivity_spin.valueChanged.connect(self.sensitivity_changed.emit)
        form.addRow("Sensitivity", self.sensitivity_spin)
        layout.addLayout(form)

        instructions = QLabel(
            "Click live camera feed to capture mouse; move cursor to aim; Esc, window blur or mode change stops motion immediately."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: gray;")
        layout.addWidget(instructions)

    @pyqtSlot(bool)
    def set_capture_state(self, captured: bool) -> None:
        if captured:
            self.status_label.setText("Captured: Esc to release and stop")
            self.status_label.setStyleSheet("color: #00aa55; font-weight: bold;")
        else:
            self.status_label.setText("Uncaptured: Click live view to start")
            self.status_label.setStyleSheet("color: #cc8800;")

    @pyqtSlot(float, float)
    def update_target(self, yaw: float, pitch: float) -> None:
        self.target_label.setText(
            f"Virtual Target: Yaw {yaw:+.2f}° | Pitch {pitch:+.2f}°"
        )
