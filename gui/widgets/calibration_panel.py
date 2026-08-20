# -*- coding: utf-8 -*-
"""
激光落点 / 准星零位校准面板 (Laser Crosshair Calibration Panel)

功能：
- 解决摄像头光轴与物理激光发射点之间的机械安装视差 (Parallax Offset)
- 支持按键微调 (Ctrl+方向键 / IJKL)、步长调节 (1px / 5px / 10px)
- 支持在画面上直接 Ctrl + 鼠标左键点击激光光斑完成快速吸附对齐
- 实时同步至 PID 闭环跟踪目标点与 HUD 瞄准准星
- 支持保存至 JSON 配置文件，下次启动自动加载
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from config.vision_config import VisionConfig


class CrosshairCalibrationPanel(QGroupBox):
    """激光准星校准控制面板"""

    offset_changed = pyqtSignal(int, int)  # (offset_x, offset_y)

    def __init__(self, parent=None):
        super().__init__("🎯 Laser Boresight Crosshair", parent)
        self.init_ui()
        self.update_display()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 1. 实时偏移状态指示器
        self.lbl_status = QLabel("Offset: ΔX = 0 px | ΔY = 0 px")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("""
            background-color: #0f172a;
            color: #38bdf8;
            font-family: Consolas, "Segoe UI", monospace;
            font-weight: bold;
            font-size: 11px;
            padding: 5px;
            border-radius: 4px;
            border: 1px solid #1e3a8a;
        """)
        layout.addWidget(self.lbl_status)

        # 2. 步长选择与快捷重置/保存栏
        ctrl_top = QHBoxLayout()
        ctrl_top.setSpacing(6)

        lbl_step = QLabel("Step:")
        lbl_step.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ctrl_top.addWidget(lbl_step)

        self.combo_step = QComboBox()
        self.combo_step.addItems(["1 px (Fine)", "5 px (Med)", "10 px (Fast)"])
        self.combo_step.setCurrentIndex(0)
        self.combo_step.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #f1f5f9;
                border: 1px solid #334155;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 11px;
            }
        """)
        ctrl_top.addWidget(self.combo_step, 1)

        self.btn_reset = QPushButton("🎯 Center (0,0)")
        self.btn_reset.setToolTip("Reset crosshair back to geometric center (Ctrl + R)")
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #e2e8f0;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        ctrl_top.addWidget(self.btn_reset)

        self.btn_save = QPushButton("💾 Save")
        self.btn_save.setToolTip("Save calibration offset to disk (Ctrl + S)")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: bold;
                padding: 3px 10px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #10b981;
            }
        """)
        self.btn_save.clicked.connect(self.on_save_clicked)
        ctrl_top.addWidget(self.btn_save)

        layout.addLayout(ctrl_top)

        # ==========================================================
        # Boresight modu + atis mesafesi / 光轴补偿方式 + 交战距离
        # ==========================================================
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)

        lbl_m = QLabel("Mode:")
        lbl_m.setStyleSheet("color:#94a3b8; font-size:11px;")
        mode_row.addWidget(lbl_m)

        self.combo_mode = QComboBox()
        # offset = nisangahi lazerin vurdugu yere tasi (tam FOV korunur)
        # crop   = goruntuyu kirp, nisangah ekran ortasinda kalsin
        # offset = 十字线移到激光落点（保留全视场）
        # crop   = 裁剪画面让十字线居中（损失约 2 倍偏移的视场）
        self.combo_mode.addItem("Offset  (keep full FOV)", "offset")
        self.combo_mode.addItem("Crop    (centered reticle)", "crop")
        self.combo_mode.setStyleSheet("font-size:11px; padding:2px;")
        idx = self.combo_mode.findData(getattr(VisionConfig, "BORESIGHT_MODE", "offset"))
        self.combo_mode.setCurrentIndex(max(idx, 0))
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.combo_mode, 1)

        lbl_d = QLabel("Range:")
        lbl_d.setStyleSheet("color:#94a3b8; font-size:11px;")
        mode_row.addWidget(lbl_d)

        self.combo_range = QComboBox()
        # Kamera lazerin USTUNDE -> paralaks mesafeyle TERS orantili.
        # Tek mesafede yapilan kalibrasyon 5 m ile 15 m'de ayni sonucu vermez.
        # 相机在激光上方，视差与距离成反比；单一标定在 5m 和 15m 不通用。
        self.combo_range.addItem("Fixed (no parallax)", None)
        for _d in (5, 10, 15, 20):
            self.combo_range.addItem(f"{_d} m", float(_d))
        self.combo_range.setStyleSheet("font-size:11px; padding:2px;")
        _cur = getattr(VisionConfig, "AKTIF_MESAFE_M", None)
        _ri = self.combo_range.findData(float(_cur) if _cur else None)
        self.combo_range.setCurrentIndex(max(_ri, 0))
        self.combo_range.currentIndexChanged.connect(self._on_range_changed)
        mode_row.addWidget(self.combo_range, 1)

        layout.addLayout(mode_row)

        # 3. 方向十字键 (D-Pad 微调)
        dpad_layout = QGridLayout()
        dpad_layout.setSpacing(4)

        btn_style = """
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px;
                min-width: 32px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
                border-color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #0369a1;
            }
        """

        self.btn_up = QPushButton("▲")
        self.btn_up.setStyleSheet(btn_style)
        self.btn_up.setToolTip("Move crosshair UP")
        self.btn_up.clicked.connect(lambda: self.adjust_offset(0, -self.get_step_size()))
        dpad_layout.addWidget(self.btn_up, 0, 1)

        self.btn_left = QPushButton("◀")
        self.btn_left.setStyleSheet(btn_style)
        self.btn_left.setToolTip("Move crosshair LEFT")
        self.btn_left.clicked.connect(lambda: self.adjust_offset(-self.get_step_size(), 0))
        dpad_layout.addWidget(self.btn_left, 1, 0)

        self.btn_dot = QPushButton("🎯")
        self.btn_dot.setStyleSheet(btn_style)
        self.btn_dot.setToolTip("Reset to Center")
        self.btn_dot.clicked.connect(self.on_reset_clicked)
        dpad_layout.addWidget(self.btn_dot, 1, 1)

        self.btn_right = QPushButton("▶")
        self.btn_right.setStyleSheet(btn_style)
        self.btn_right.setToolTip("Move crosshair RIGHT")
        self.btn_right.clicked.connect(lambda: self.adjust_offset(self.get_step_size(), 0))
        dpad_layout.addWidget(self.btn_right, 1, 2)

        self.btn_down = QPushButton("▼")
        self.btn_down.setStyleSheet(btn_style)
        self.btn_down.setToolTip("Move crosshair DOWN")
        self.btn_down.clicked.connect(lambda: self.adjust_offset(0, self.get_step_size()))
        dpad_layout.addWidget(self.btn_down, 2, 1)

        layout.addLayout(dpad_layout)

        # 4. 操作提示与快捷键说明
        lbl_hint = QLabel(
            "💡 <b>Calibration Tips:</b><br>"
            "• <b>Ctrl + Arrow Keys</b>: Nudge crosshair (Hold Shift for +5px)<br>"
            "• <b>Ctrl + Click</b> on live camera: Snap crosshair to laser dot<br>"
            "• <b>Ctrl+R</b>: Reset | <b>Ctrl+S</b>: Save"
        )
        lbl_hint.setStyleSheet("color: #64748b; font-size: 10px; padding: 2px;")
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)

    def get_step_size(self) -> int:
        idx = self.combo_step.currentIndex()
        if idx == 0:
            return 1
        elif idx == 1:
            return 5
        elif idx == 2:
            return 10
        return 1

    def adjust_offset(self, dx: int, dy: int):
        ox, oy = VisionConfig.adjust_center_offset(dx, dy)
        self.update_display()
        self.offset_changed.emit(ox, oy)

    def set_offset(self, ox: int, oy: int):
        VisionConfig.set_center_offset(ox, oy)
        self.update_display()
        self.offset_changed.emit(ox, oy)

    def on_reset_clicked(self):
        VisionConfig.reset_center_offset()
        self.update_display()
        self.offset_changed.emit(0, 0)

    def on_save_clicked(self):
        ok = VisionConfig.save_calibration()
        mode = getattr(VisionConfig, "BORESIGHT_MODE", "offset")
        if ok:
            self.lbl_status.setText(f"✓ Saved! [ΔX={VisionConfig.CENTER_OFFSET_X:+d}, ΔY={VisionConfig.CENTER_OFFSET_Y:+d}, {mode}]")
            self.lbl_status.setStyleSheet("""
                background-color: #064e3b;
                color: #34d399;
                font-family: Consolas, "Segoe UI", monospace;
                font-weight: bold;
                font-size: 11px;
                padding: 5px;
                border-radius: 4px;
                border: 1px solid #059669;
            """)
        else:
            self.lbl_status.setText("✗ Save Failed")

    def _on_mode_changed(self, _idx):
        """offset <-> crop. 其它模块都从 VisionConfig 读。"""
        VisionConfig.BORESIGHT_MODE = self.combo_mode.currentData() or "offset"
        self.update_display()
        self.offset_changed.emit(VisionConfig.CENTER_OFFSET_X,
                                 VisionConfig.CENTER_OFFSET_Y)

    def _on_range_changed(self, _idx):
        """视差修正用的交战距离"""
        VisionConfig.AKTIF_MESAFE_M = self.combo_range.currentData()
        self.update_display()
        self.offset_changed.emit(VisionConfig.CENTER_OFFSET_X,
                                 VisionConfig.CENTER_OFFSET_Y)

    def update_display(self):
        ox = VisionConfig.CENTER_OFFSET_X
        oy = VisionConfig.CENTER_OFFSET_Y
        cx = VisionConfig.get_center_x()
        cy = VisionConfig.get_center_y()
        mode = getattr(VisionConfig, "BORESIGHT_MODE", "offset")
        rng = getattr(VisionConfig, "AKTIF_MESAFE_M", None)
        rtxt = f"{rng:.0f}m" if rng else "fixed"

        # 动态同步下拉菜单选择项
        if hasattr(self, 'combo_mode') and hasattr(self, 'combo_range'):
            self.combo_mode.blockSignals(True)
            self.combo_range.blockSignals(True)
            idx_m = self.combo_mode.findData(mode)
            if idx_m >= 0:
                self.combo_mode.setCurrentIndex(idx_m)
            idx_r = self.combo_range.findData(float(rng) if rng else None)
            if idx_r >= 0:
                self.combo_range.setCurrentIndex(idx_r)
            self.combo_mode.blockSignals(False)
            self.combo_range.blockSignals(False)

        # crop 模式画面被裁，顺便显示视场损失
        extra = f"  FOV -{abs(ox)*2}x{abs(oy)*2}px" if (mode == "crop" and (ox or oy)) else ""
        self.lbl_status.setText(
            f"Offset: dX={ox:+d}px  dY={oy:+d}px" + chr(10)
            + f"[{mode}] range {rtxt}{extra}   (Aim: {cx}, {cy})")
        self.lbl_status.setStyleSheet("""
            background-color: #0f172a;
            color: #38bdf8;
            font-family: Consolas, "Segoe UI", monospace;
            font-weight: bold;
            font-size: 11px;
            padding: 5px;
            border-radius: 4px;
            border: 1px solid #1e3a8a;
        """)
