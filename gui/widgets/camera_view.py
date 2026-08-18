# -*- coding: utf-8 -*-
"""Camera display with optional FPS-style relative mouse capture."""

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint
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
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QSlider, QFrame
from config.vision_config import VisionConfig


class MouseAimLabel(QLabel):
    """Video label that emits relative mouse deltas while captured."""

    mouse_delta_signal = pyqtSignal(int, int)
    capture_changed_signal = pyqtSignal(bool)
    double_clicked_signal = pyqtSignal()

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self._mouse_control_enabled = False
        self._captured = False
        self._show_crosshair = False
        self.laser_armed = False
        self.laser_firing = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    def set_laser_status(self, armed: bool, firing: bool) -> None:
        """更新激光武器视觉状态"""
        self.laser_armed = armed
        self.laser_firing = firing
        self.update()

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
        if not self._show_crosshair and not self.laser_armed:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 真实激光瞄准点（支持 Crop 与 Offset 模式，与画中画完全对齐）
        raw_cx, raw_cy = VisionConfig.aim_point(VisionConfig.AKTIF_MESAFE_M)
        fw = getattr(VisionConfig, "FRAME_WIDTH", 640)
        fh = getattr(VisionConfig, "FRAME_HEIGHT", 480)

        pix = self.pixmap()
        if pix and not pix.isNull() and fw > 0 and fh > 0:
            pw = pix.width()
            ph = pix.height()
            lw = self.width()
            lh = self.height()
            pad_x = (lw - pw) // 2
            pad_y = (lh - ph) // 2

            norm_x = max(0.0, min(1.0, raw_cx / float(fw)))
            norm_y = max(0.0, min(1.0, raw_cy / float(fh)))
            center_x = int(pad_x + norm_x * pw)
            center_y = int(pad_y + norm_y * ph)
            center = QPoint(center_x, center_y)
        else:
            center = self.rect().center()

        # 根据激光发射/保险状态切换准星颜色与光效
        if self.laser_firing:
            # 正在发射：激光红光打击光环 + 强红准星
            strike_pen = QPen(QColor(255, 0, 0, 180), 3)
            painter.setPen(strike_pen)
            painter.drawEllipse(center, 18, 18)
            painter.drawEllipse(center, 36, 36)

            aim_color = QColor(255, 50, 50, 255)
            outline_color = QColor(0, 0, 0, 220)
        elif self.laser_armed:
            # 武器就绪 (ARMED)：战术亮橙红准星
            aim_color = QColor(255, 100, 50, 240)
            outline_color = QColor(0, 0, 0, 200)
        else:
            # 待机或普通瞄准：极光青白准星
            aim_color = QColor(56, 189, 248, 235)
            outline_color = QColor(0, 0, 0, 200)

        outline_pen = QPen(outline_color, 4)
        aim_pen = QPen(aim_color, 2)

        for pen in (outline_pen, aim_pen):
            painter.setPen(pen)
            painter.drawLine(center.x() - 24, center.y(), center.x() - 7, center.y())
            painter.drawLine(center.x() + 7, center.y(), center.x() + 24, center.y())
            painter.drawLine(center.x(), center.y() - 24, center.x(), center.y() - 7)
            painter.drawLine(center.x(), center.y() + 7, center.x(), center.y() + 24)
            painter.drawEllipse(center, 3, 3)

        # 战术状态角标
        if self.laser_firing:
            painter.setPen(QPen(QColor(255, 50, 50, 255)))
            painter.drawText(center.x() + 15, center.y() - 15, "⚡ LASER FIRE")
        elif self.laser_armed:
            painter.setPen(QPen(QColor(255, 120, 50, 220)))
            painter.drawText(center.x() + 15, center.y() - 15, "ARMED")

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

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        """双击画面触发全屏切换"""
        self.double_clicked_signal.emit()


class CameraView(QWidget):
    """Display live video, PiP Reticle Scope, and Video Recording with Fullscreen capability."""

    mouse_delta_signal = pyqtSignal(int, int)
    mouse_capture_changed_signal = pyqtSignal(bool)
    fullscreen_requested = pyqtSignal()
    pip_zoom_changed = pyqtSignal(float)
    record_toggle_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.is_camera_active = False
        self._mouse_mode_enabled = False
        self.is_fullscreen = False
        self.is_recording = False
        self.current_zoom = 3.0
        self.init_ui()

    def set_laser_status(self, armed: bool, firing: bool) -> None:
        """同步激光武器状态至画面准星 HUD"""
        self.lbl_camera.set_laser_status(armed, firing)

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 1. 顶部操作工具栏 (Live View 标题 + 画中画放大 + 录屏 + 掩码 + 全屏)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(6)

        self.lbl_title = QLabel("<h2>📷 Live Camera Feed</h2>")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        # 1.1 准星画中画局部放大倍数调节 (PiP Reticle Scope Zoom)
        zoom_box = QWidget()
        zoom_layout = QHBoxLayout(zoom_box)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.setSpacing(3)

        self.btn_zoom_out = QPushButton("➖")
        self.btn_zoom_out.setToolTip("Zoom Out Reticle Scope (Shortcut: [ or -)")
        self.btn_zoom_out.setFixedSize(26, 26)
        self.btn_zoom_out.setStyleSheet("""
            QPushButton { background-color: #1e293b; color: #38bdf8; font-weight: bold; border: 1px solid #334155; border-radius: 3px; font-size: 11px; }
            QPushButton:hover { background-color: #0284c7; color: white; }
        """)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(self.btn_zoom_out)

        self.lbl_zoom = QLabel("🔍 3.0x")
        self.lbl_zoom.setStyleSheet("color: #38bdf8; font-weight: bold; font-family: Consolas, monospace; font-size: 11px; min-width: 44px;")
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zoom_layout.addWidget(self.lbl_zoom)

        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(15, 60) # 1.5x ~ 6.0x
        self.slider_zoom.setValue(30)     # 3.0x
        self.slider_zoom.setFixedWidth(75)
        self.slider_zoom.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #334155; border-radius: 2px; }
            QSlider::handle:horizontal { background: #38bdf8; width: 10px; margin: -3px 0; border-radius: 5px; }
        """)
        self.slider_zoom.valueChanged.connect(self._on_slider_zoom_changed)
        zoom_layout.addWidget(self.slider_zoom)

        self.btn_zoom_in = QPushButton("➕")
        self.btn_zoom_in.setToolTip("Zoom In Reticle Scope (Shortcut: ] or +)")
        self.btn_zoom_in.setFixedSize(26, 26)
        self.btn_zoom_in.setStyleSheet("""
            QPushButton { background-color: #1e293b; color: #38bdf8; font-weight: bold; border: 1px solid #334155; border-radius: 3px; font-size: 11px; }
            QPushButton:hover { background-color: #0284c7; color: white; }
        """)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(self.btn_zoom_in)

        header_layout.addWidget(zoom_box)

        # 1.2 屏幕录像按键 (Screen Video Recording)
        self.btn_record = QPushButton("⏺ Record")
        self.btn_record.setToolTip("Start / Stop Video Recording to recordings/ (Shortcut: R)")
        self.btn_record.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f87171;
                border: 1px solid #dc2626;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #991b1b;
                color: #ffffff;
            }
        """)
        self.btn_record.clicked.connect(self.record_toggle_requested.emit)
        header_layout.addWidget(self.btn_record)

        # 掩码显示/折叠切换按钮
        self.btn_toggle_mask = QPushButton("👁 Debug Mask")
        self.btn_toggle_mask.setCheckable(True)
        self.btn_toggle_mask.setChecked(True)
        self.btn_toggle_mask.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #0369a1;
                color: #ffffff;
                border: 1px solid #38bdf8;
            }
        """)
        self.btn_toggle_mask.toggled.connect(self._on_toggle_mask)
        header_layout.addWidget(self.btn_toggle_mask)

        # 全屏切换按钮
        self.btn_fullscreen = QPushButton("⛶ Fullscreen (F11)")
        self.btn_fullscreen.setToolTip("Toggle Fullscreen Live View (Double click feed or press F11)")
        self.btn_fullscreen.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.btn_fullscreen.clicked.connect(self.fullscreen_requested.emit)
        header_layout.addWidget(self.btn_fullscreen)

        layout.addLayout(header_layout)

        # 2. 摄像头主显示标签
        self.lbl_camera = MouseAimLabel("Camera not started")
        self.lbl_camera.setStyleSheet("background-color: black; border: 2px solid #333; border-radius: 4px;")
        self.lbl_camera.setMinimumSize(480, 360)
        self.lbl_camera.mouse_delta_signal.connect(self.mouse_delta_signal.emit)
        self.lbl_camera.capture_changed_signal.connect(
            self.mouse_capture_changed_signal.emit
        )
        self.lbl_camera.double_clicked_signal.connect(self.fullscreen_requested.emit)
        layout.addWidget(self.lbl_camera, 3)

        # 3. 调试掩码区域
        self.mask_container = QWidget()
        mask_layout = QVBoxLayout(self.mask_container)
        mask_layout.setContentsMargins(0, 4, 0, 0)
        mask_layout.setSpacing(2)

        lbl_mask_title = QLabel("<b>Debug Vision Mask</b>")
        lbl_mask_title.setStyleSheet("color: #64748b; font-size: 11px;")
        mask_layout.addWidget(lbl_mask_title)

        self.lbl_mask = QLabel("Debug Mask")
        self.lbl_mask.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mask.setStyleSheet("background-color: #18181b; border: 1px dashed #3f3f46; border-radius: 4px;")
        self.lbl_mask.setMinimumSize(320, 160)
        self.lbl_mask.setMaximumHeight(240)
        mask_layout.addWidget(self.lbl_mask)

        layout.addWidget(self.mask_container, 1)

    def _on_toggle_mask(self, checked: bool):
        """显示/隐藏调试掩码区域，给主摄像头腾出更多纵向空间"""
        self.mask_container.setVisible(checked)

    def set_fullscreen_state(self, is_fullscreen: bool):
        """同步全屏按钮状态与文本"""
        self.is_fullscreen = is_fullscreen
        if is_fullscreen:
            self.btn_fullscreen.setText("🗗 Exit Fullscreen (Esc/F11)")
            self.btn_fullscreen.setStyleSheet("""
                QPushButton {
                    background-color: #e11d48;
                    color: #ffffff;
                    font-weight: bold;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #be123c;
                }
            """)
            # 全屏下默认隐藏调试掩码，呈现最纯粹大屏画面
            self.mask_container.setVisible(False)
        else:
            self.btn_fullscreen.setText("⛶ Fullscreen (F11)")
            self.btn_fullscreen.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    font-weight: bold;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
            """)
            self.mask_container.setVisible(self.btn_toggle_mask.isChecked())

    def _on_slider_zoom_changed(self, val: int):
        factor = val / 10.0
        self.current_zoom = factor
        self.lbl_zoom.setText(f"🔍 {factor:.1f}x")
        self.pip_zoom_changed.emit(factor)

    def zoom_in(self):
        """Zoom In 0.5x (Shortcut: ] or +)"""
        new_val = min(60, self.slider_zoom.value() + 5)
        self.slider_zoom.setValue(new_val)

    def zoom_out(self):
        """Zoom Out 0.5x (Shortcut: [ or -)"""
        new_val = max(15, self.slider_zoom.value() - 5)
        self.slider_zoom.setValue(new_val)

    def set_recording_status(self, is_recording: bool, path: str, elapsed_seconds: int):
        """更新录像按键状态"""
        self.is_recording = is_recording
        if is_recording:
            m, s = divmod(elapsed_seconds, 60)
            self.btn_record.setText(f"⏹ Stop [{m:02d}:{s:02d}]")
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #dc2626;
                    color: #ffffff;
                    border: 1px solid #ef4444;
                    font-weight: bold;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #b91c1c;
                }
            """)
        else:
            self.btn_record.setText("⏺ Record")
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #f87171;
                    border: 1px solid #dc2626;
                    font-weight: bold;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #991b1b;
                    color: #ffffff;
                }
            """)

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
            self.lbl_camera.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_camera.setPixmap(scaled)

    @pyqtSlot(QImage)
    def update_mask_feed(self, qt_img: QImage) -> None:
        if not self.is_camera_active or not self.mask_container.isVisible():
            return
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(
            self.lbl_mask.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_mask.setPixmap(scaled)

    def show_blank_screen(self, text: str = "Camera Not Running") -> None:
        self.is_camera_active = False
        self._update_mouse_input_state()
        self.lbl_camera.clear()
        self.lbl_camera.setText(f"<font color='#888888'><h3>📷 {text}</h3></font>")
        self.lbl_mask.clear()
        self.lbl_mask.setText("<font color='#666666'>Debug Mask (Stopped)</font>")
