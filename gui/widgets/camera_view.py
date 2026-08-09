# -*- coding: utf-8 -*-
"""Camera display with optional FPS-style relative mouse capture."""

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MouseAimLabel(QLabel):
    """Video label that emits relative mouse deltas while captured."""

    mouse_delta_signal = pyqtSignal(int, int)
    capture_changed_signal = pyqtSignal(bool)

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self._mouse_control_enabled = False
        self._captured = False
        self._show_crosshair = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    def set_mouse_control_enabled(self, enabled: bool) -> None:
        self._mouse_control_enabled = enabled
        self._show_crosshair = enabled
        if not enabled:
            self.release_capture()
        self.update()

    def release_capture(self) -> None:
        if not self._captured:
            return
        self._captured = False
        self.releaseMouse()
        self.unsetCursor()
        self.capture_changed_signal.emit(False)
        self.update()

    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        if ev is None:
            return
        if (
            self._mouse_control_enabled
            and ev.button() == Qt.MouseButton.LeftButton
        ):
            self._capture_mouse()
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent | None) -> None:
        if ev is None:
            return
        if not self._captured:
            super().mouseMoveEvent(ev)
            return

        center_global = self.mapToGlobal(self.rect().center())
        cursor_global = ev.globalPosition().toPoint()
        dx = cursor_global.x() - center_global.x()
        dy = cursor_global.y() - center_global.y()
        if dx or dy:
            self.mouse_delta_signal.emit(dx, dy)
            QCursor.setPos(center_global)
        ev.accept()

    def keyPressEvent(self, ev: QKeyEvent | None) -> None:
        if ev is None:
            return
        if ev.key() == Qt.Key.Key_Escape and self._captured:
            self.release_capture()
            ev.accept()
            return
        super().keyPressEvent(ev)

    def focusOutEvent(self, ev) -> None:
        self.release_capture()
        super().focusOutEvent(ev)

    def hideEvent(self, a0) -> None:
        self.release_capture()
        super().hideEvent(a0)

    def paintEvent(self, a0) -> None:
        super().paintEvent(a0)
        if not self._show_crosshair:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()

        outline_pen = QPen(QColor(0, 0, 0, 210), 4)
        aim_pen = QPen(QColor(255, 255, 255, 235), 2)
        for pen in (outline_pen, aim_pen):
            painter.setPen(pen)
            painter.drawLine(center.x() - 24, center.y(), center.x() - 7, center.y())
            painter.drawLine(center.x() + 7, center.y(), center.x() + 24, center.y())
            painter.drawLine(center.x(), center.y() - 24, center.x(), center.y() - 7)
            painter.drawLine(center.x(), center.y() + 7, center.x(), center.y() + 24)
            painter.drawEllipse(center, 3, 3)

    def _capture_mouse(self) -> None:
        if self._captured:
            return
        self._captured = True
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.grabMouse()
        QCursor.setPos(self.mapToGlobal(self.rect().center()))
        self.capture_changed_signal.emit(True)
        self.update()


class CameraView(QWidget):
    """Display live video and expose safe relative mouse-control signals."""

    mouse_delta_signal = pyqtSignal(int, int)
    mouse_capture_changed_signal = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.is_camera_active = False
        self._mouse_mode_enabled = False
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>实时监控 (Live View)</h2>"))

        self.lbl_camera = MouseAimLabel("摄像头画面未启动")
        self.lbl_camera.setStyleSheet("background-color: black; border: 2px solid #333;")
        self.lbl_camera.setMinimumSize(480, 360)
        self.lbl_camera.mouse_delta_signal.connect(self.mouse_delta_signal.emit)
        self.lbl_camera.capture_changed_signal.connect(
            self.mouse_capture_changed_signal.emit
        )
        layout.addWidget(self.lbl_camera, 2)

        layout.addWidget(QLabel("<h3>算法调试 (Debug Mask)</h3>"))

        self.lbl_mask = QLabel("Mask 蒙版 (调试)")
        self.lbl_mask.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mask.setStyleSheet("background-color: #222; border: 1px dashed #555;")
        self.lbl_mask.setMinimumSize(320, 240)
        self.lbl_mask.setMaximumHeight(300)
        layout.addWidget(self.lbl_mask, 1)

    def set_camera_active(self, active: bool) -> None:
        self.is_camera_active = active
        self._update_mouse_input_state()

    def set_mouse_control_enabled(self, enabled: bool) -> None:
        self._mouse_mode_enabled = enabled
        self._update_mouse_input_state()

    def release_mouse_control(self) -> None:
        self.lbl_camera.release_capture()

    def _update_mouse_input_state(self) -> None:
        self.lbl_camera.set_mouse_control_enabled(
            self._mouse_mode_enabled and self.is_camera_active
        )

    @pyqtSlot(QImage)
    def update_camera_feed(self, qt_img: QImage) -> None:
        if not self.is_camera_active:
            return
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(
            self.lbl_camera.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        self.lbl_camera.setPixmap(scaled)

    @pyqtSlot(QImage)
    def update_mask_feed(self, qt_img: QImage) -> None:
        if not self.is_camera_active:
            return
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(
            self.lbl_mask.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        self.lbl_mask.setPixmap(scaled)

    def show_blank_screen(self, text: str = "相机未运行 (Camera Not Running)") -> None:
        self.is_camera_active = False
        self._update_mouse_input_state()
        self.lbl_camera.clear()
        self.lbl_camera.setText(f"<font color='#888888'><h3>📷 {text}</h3></font>")
        self.lbl_mask.clear()
        self.lbl_mask.setText("<font color='#666666'>Mask 蒙版 (已停止)</font>")
