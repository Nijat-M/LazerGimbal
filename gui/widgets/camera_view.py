# -*- coding: utf-8 -*-
"""Camera display with optional FPS-style relative mouse capture."""

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint, QSize
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

    def set_current_frame_size(self, w: int, h: int) -> None:
        """更新底层视频帧分辨率，用于精准无偏坐标映射"""
        self.frame_w = w
        self.frame_h = h
        self.update()

    def paintEvent(self, a0) -> None:
        super().paintEvent(a0)
        if not self._show_crosshair and not self.laser_armed:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 获取当前实际帧分辨率
        fw = getattr(self, "frame_w", getattr(VisionConfig, "FRAME_WIDTH", 640))
        fh = getattr(self, "frame_h", getattr(VisionConfig, "FRAME_HEIGHT", 480))

        # 真实激光瞄准点（支持 Crop 与 Offset 模式，与画中画 100% 绝对对齐）
        aim_x, aim_y = VisionConfig.get_calibrated_aim_coords(fw, fh)

        pix = self.pixmap()
        if pix and not pix.isNull() and fw > 0 and fh > 0:
            pw = pix.width()
            ph = pix.height()
            lw = self.width()
            lh = self.height()
            pad_x = (lw - pw) // 2
            pad_y = (lh - ph) // 2

            center_x = int(pad_x + (aim_x / float(fw)) * pw)
            center_y = int(pad_y + (aim_y / float(fh)) * ph)
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
    record_start_requested = pyqtSignal()
    record_pause_requested = pyqtSignal()
    record_stop_requested = pyqtSignal()
    speed_gear_changed = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.is_camera_active = False
        self._mouse_mode_enabled = False
        self.is_fullscreen = False
        self.recording_state = "IDLE"
        self.current_zoom = 3.0
        self.current_gear = 2
        self.init_ui()

    def set_laser_status(self, armed: bool, firing: bool) -> None:
        """同步激光武器状态至画面准星 HUD"""
        self.lbl_camera.set_laser_status(armed, firing)

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 1. 顶部操作工具栏 (Live View 标题 + 速度档位 + 画中画放大 + 3键录像 + 掩码 + 全屏)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(6)

        self.lbl_title = QLabel("<h2>📷 Live Camera Feed</h2>")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        # 1.0 电机三档速度选择 (Speed Gear 1 / 2 / 3, Shortcut: 1, 2, 3)
        gear_box = QWidget()
        gear_layout = QHBoxLayout(gear_box)
        gear_layout.setContentsMargins(0, 0, 0, 0)
        gear_layout.setSpacing(2)

        lbl_spd = QLabel("⚡")
        lbl_spd.setStyleSheet("color: #38bdf8; font-size: 12px;")
        gear_layout.addWidget(lbl_spd)

        self.btn_gear1 = QPushButton("1: 0.3x")
        self.btn_gear1.setToolTip("Gear 1: Precision Slow 0.3x (防远距离震动, 快捷键: 1)")
        self.btn_gear1.setCheckable(True)
        self.btn_gear1.clicked.connect(lambda: self.speed_gear_changed.emit(1))
        gear_layout.addWidget(self.btn_gear1)

        self.btn_gear2 = QPushButton("2: 1.0x")
        self.btn_gear2.setToolTip("Gear 2: Normal Cruise 1.0x (标准速度, 快捷键: 2)")
        self.btn_gear2.setCheckable(True)
        self.btn_gear2.setChecked(True)
        self.btn_gear2.clicked.connect(lambda: self.speed_gear_changed.emit(2))
        gear_layout.addWidget(self.btn_gear2)

        self.btn_gear3 = QPushButton("3: 2.2x")
        self.btn_gear3.setToolTip("Gear 3: Fast Turbo 2.2x (高速追击, 快捷键: 3)")
        self.btn_gear3.setCheckable(True)
        self.btn_gear3.clicked.connect(lambda: self.speed_gear_changed.emit(3))
        gear_layout.addWidget(self.btn_gear3)

        self._update_gear_button_styles()
        header_layout.addWidget(gear_box)

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

        # 1.2 屏幕录像三按键组 (Record / Pause / Stop)
        rec_box = QWidget()
        rec_layout = QHBoxLayout(rec_box)
        rec_layout.setContentsMargins(0, 0, 0, 0)
        rec_layout.setSpacing(3)

        self.btn_rec_start = QPushButton("⏺ Record")
        self.btn_rec_start.setToolTip("Start video recording to recordings/ (开始录屏)")
        self.btn_rec_start.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f87171;
                border: 1px solid #dc2626;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #991b1b;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #0f172a;
                color: #475569;
                border: 1px solid #1e293b;
            }
        """)
        self.btn_rec_start.clicked.connect(self.record_start_requested.emit)
        rec_layout.addWidget(self.btn_rec_start)

        self.btn_rec_pause = QPushButton("⏸ Pause")
        self.btn_rec_pause.setToolTip("Pause / Resume recording (暂停/继续)")
        self.btn_rec_pause.setEnabled(False)
        self.btn_rec_pause.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #fbbf24;
                border: 1px solid #d97706;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #b45309;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #0f172a;
                color: #475569;
                border: 1px solid #1e293b;
            }
        """)
        self.btn_rec_pause.clicked.connect(self.record_pause_requested.emit)
        rec_layout.addWidget(self.btn_rec_pause)

        self.btn_rec_stop = QPushButton("⏹ Stop")
        self.btn_rec_stop.setToolTip("Stop and save video to recordings/ (停止并保存)")
        self.btn_rec_stop.setEnabled(False)
        self.btn_rec_stop.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #475569;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #dc2626;
                color: #ffffff;
                border-color: #ef4444;
            }
            QPushButton:disabled {
                background-color: #0f172a;
                color: #475569;
                border: 1px solid #1e293b;
            }
        """)
        self.btn_rec_stop.clicked.connect(self.record_stop_requested.emit)
        rec_layout.addWidget(self.btn_rec_stop)

        self.lbl_rec_status = QLabel("")
        self.lbl_rec_status.setVisible(False)
        rec_layout.addWidget(self.lbl_rec_status)

        header_layout.addWidget(rec_box)

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

    def _update_gear_button_styles(self):
        """更新速度档位按钮高亮样式"""
        style_inactive = """
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f1f5f9;
            }
        """
        style_g1 = """
            QPushButton {
                background-color: #065f46;
                color: #34d399;
                border: 1px solid #059669;
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: bold;
            }
        """
        style_g2 = """
            QPushButton {
                background-color: #0369a1;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: bold;
            }
        """
        style_g3 = """
            QPushButton {
                background-color: #9a3412;
                color: #fb923c;
                border: 1px solid #ea580c;
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: bold;
            }
        """
        self.btn_gear1.setStyleSheet(style_g1 if self.current_gear == 1 else style_inactive)
        self.btn_gear2.setStyleSheet(style_g2 if self.current_gear == 2 else style_inactive)
        self.btn_gear3.setStyleSheet(style_g3 if self.current_gear == 3 else style_inactive)

    def set_speed_gear_visual(self, gear: int):
        """外部（如快捷键/控制器）更新档位时同步按钮视觉"""
        self.current_gear = max(1, min(3, int(gear)))
        self.btn_gear1.setChecked(self.current_gear == 1)
        self.btn_gear2.setChecked(self.current_gear == 2)
        self.btn_gear3.setChecked(self.current_gear == 3)
        self._update_gear_button_styles()

    def zoom_in(self):
        """Zoom In 0.5x (Shortcut: ] or +)"""
        new_val = min(60, self.slider_zoom.value() + 5)
        self.slider_zoom.setValue(new_val)

    def zoom_out(self):
        """Zoom Out 0.5x (Shortcut: [ or -)"""
        new_val = max(15, self.slider_zoom.value() - 5)
        self.slider_zoom.setValue(new_val)

    def set_recording_status(self, state: str, path: str, elapsed_seconds: int):
        """更新录像三按键状态 (IDLE / RECORDING / PAUSED)"""
        self.recording_state = state
        m, s = divmod(elapsed_seconds, 60)
        if state == "IDLE":
            self.btn_rec_start.setEnabled(True)
            self.btn_rec_pause.setEnabled(False)
            self.btn_rec_pause.setText("⏸ Pause")
            self.btn_rec_stop.setEnabled(False)
            self.lbl_rec_status.setVisible(False)
        elif state == "RECORDING":
            self.btn_rec_start.setEnabled(False)
            self.btn_rec_pause.setEnabled(True)
            self.btn_rec_pause.setText("⏸ Pause")
            self.btn_rec_stop.setEnabled(True)
            self.lbl_rec_status.setVisible(True)
            self.lbl_rec_status.setText(f"🔴 {m:02d}:{s:02d}")
            self.lbl_rec_status.setStyleSheet("color: #ef4444; font-weight: bold; font-family: Consolas, monospace; font-size: 11px;")
        elif state == "PAUSED":
            self.btn_rec_start.setEnabled(False)
            self.btn_rec_pause.setEnabled(True)
            self.btn_rec_pause.setText("▶ Resume")
            self.btn_rec_stop.setEnabled(True)
            self.lbl_rec_status.setVisible(True)
            self.lbl_rec_status.setText(f"⏸ {m:02d}:{s:02d}")
            self.lbl_rec_status.setStyleSheet("color: #f59e0b; font-weight: bold; font-family: Consolas, monospace; font-size: 11px;")

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
        if qt_img is None or qt_img.isNull() or qt_img.width() <= 0:
            return
        if not self.is_camera_active:
            self.is_camera_active = True
            self._update_mouse_input_state()
        self.lbl_camera.set_current_frame_size(qt_img.width(), qt_img.height())
        pixmap = QPixmap.fromImage(qt_img)
        lbl_sz = self.lbl_camera.size()
        if lbl_sz.width() < 100 or lbl_sz.height() < 100:
            lbl_sz = QSize(max(480, self.width()), max(360, self.height()))
        scaled = pixmap.scaled(
            lbl_sz, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
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
