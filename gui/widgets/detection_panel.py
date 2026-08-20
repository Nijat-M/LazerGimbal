# -*- coding: utf-8 -*-
"""
Yetenek 6 分类结果面板 (Hedef Sınıflandırma Paneli)

竞赛规范能力 6 要求"在用户界面上展示"分类结果，这个面板就是给裁判看的：
    HEDEF TİPİ (目标类型) / GÜVEN (置信度) / MESAFE (距离)

注意：这里是 Qt 控件，土耳其字符 (Füze / İHA) 由 Qt 自己渲染，不存在乱码问题。
画面里叠加的文字才需要 PIL（见 s4_detector.ciz()），因为 cv2.putText 画不出来。
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

# 每类一个固定颜色，和画面上的框颜色保持一致 (s4_detector.RENK 是 BGR，这里用 RGB)
SINIF_RENK = {
    "F16":            QColor(60, 200, 60),
    "HELIKOPTER":     QColor(235, 190, 60),
    "BALISTIK_FUZE":  QColor(240, 90, 70),
    "FUZE":           QColor(240, 90, 70),
    "MINI_IHA":       QColor(60, 170, 235),
    "IHA":            QColor(60, 170, 235),
    "RED BALLOON":    QColor(255, 70, 70),
    "BLUE BALLOON":   QColor(56, 189, 248),
}


class DetectionPanel(QGroupBox):
    """Real-time Target Classification & IFF Panel (Rock-Solid & Flicker-Free)"""

    def __init__(self, parent=None):
        super().__init__("Capability 6 — Target Classification & IFF", parent)
        self._last_iff_style = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 12, 8, 8)

        # 顶部：检测数量统计栏（固定高度，彻底杜绝折行抽动）
        self.lbl_summary = QLabel("TOTAL: 0  |  🔴 ENEMY: 0  |  🔵 FRIENDLY: 0  |  ⚪ UNKNOWN: 0")
        self.lbl_summary.setFixedHeight(34)
        self.lbl_summary.setStyleSheet("""
            background-color: #0f172a;
            color: #38bdf8;
            font-weight: bold;
            font-family: Consolas, "Segoe UI", monospace;
            font-size: 11px;
            padding: 4px 6px;
            border-radius: 4px;
            border: 1px solid #1e3a8a;
        """)
        self.lbl_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_summary)

        # ---- Yetenek 7: 火控开火授权/友军保护状态条（固定高度，防抖） ----
        self.lbl_iff = QLabel("STANDBY  --  NO TARGET IN SECTOR")
        self.lbl_iff.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_iff.setFixedHeight(46)
        self._set_iff_style("#64748b", "#0f172a")
        layout.addWidget(self.lbl_iff)

        # 分类结果表 (4列: Target Type | Affiliation (IFF) | Confidence | Distance)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Target Type", "Affiliation (IFF)", "Confidence", "Distance"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setFixedHeight(170)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        f = QFont("Segoe UI", 9)
        f.setBold(True)
        self.table.setFont(f)
        layout.addWidget(self.table)

        self.lbl_hint = QLabel(
            "Note: Red targets are marked ENEMY, Blue targets are marked FRIENDLY."
        )
        self.lbl_hint.setStyleSheet("color: #64748b; font-size: 10px; padding: 2px;")
        self.lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_hint)

    # ------------------------------------------------------------------
    def _set_iff_style(self, fg: str, bg: str):
        """样式缓存：仅在样式变化时更新，彻底杜绝 60FPS 重绘抽动"""
        style_key = f"{fg}_{bg}"
        if style_key == self._last_iff_style:
            return
        self._last_iff_style = style_key
        self.lbl_iff.setStyleSheet(
            f"background-color: {bg}; color: {fg}; font-weight: bold;"
            f"font-family: Consolas, monospace; font-size: 12px;"
            f"padding: 4px; border-radius: 4px; border: 2px solid {fg};"
        )

    def set_model_status(self, ok: bool, message: str):
        """模型加载状态指示"""
        if not ok:
            self.table.setRowCount(0)
            self.lbl_summary.setText("MODEL NOT LOADED")
            self._set_iff_style("#64748b", "#0f172a")

    def update_detections(self, dets: list):
        """
        每帧极速无抖动更新 (Atomic 60FPS Refresh)
        """
        def is_enemy(d):
            t = str(d.get("taraf", "")).upper()
            return t == "ENEMY" or "RED" in t or "KIRMIZI" in t

        def is_friendly(d):
            t = str(d.get("taraf", "")).upper()
            return t == "FRIENDLY" or "BLUE" in t or "MAVI" in t

        red_c = sum(1 for d in dets if is_enemy(d))
        blue_c = sum(1 for d in dets if is_friendly(d))
        neutral_c = len(dets) - red_c - blue_c

        # 1. 单行固定宽度统计，绝不换行抽动
        summary_text = f"TOTAL: {len(dets)}  |  🔴 ENEMY: {red_c}  |  🔵 FRIENDLY: {blue_c}  |  ⚪ UNKNOWN: {neutral_c}"
        if self.lbl_summary.text() != summary_text:
            self.lbl_summary.setText(summary_text)

        # 2. Yetenek 7 火控状态条判定
        if red_c > 0:
            enemy_names = ", ".join([d.get("gorunen", d.get("sinif", "ENEMY")) for d in dets if is_enemy(d)])
            txt = f"🔥 FIRE AUTHORIZED >> {enemy_names}"
            if blue_c > 0:
                txt += chr(10) + f"🛡️ PROTECTED: {blue_c} FRIENDLY (BLUE) - DO NOT FIRE"
            self._set_iff_style("#ef4444", "#2a0808")
        elif blue_c > 0:
            txt = f"🛑 HOLD FIRE -- ALL {blue_c} FRIENDLY UNITS SAFE\n🛡️ PROTECTED: {blue_c} FRIENDLY (BLUE) - DO NOT FIRE"
            self._set_iff_style("#38bdf8", "#081a2e")
        else:
            txt = "STANDBY  --  NO TARGET IN SECTOR"
            self._set_iff_style("#64748b", "#0f172a")

        if self.lbl_iff.text() != txt:
            self.lbl_iff.setText(txt)

        # 3. 表格内容高效平滑刷新
        if self.table.rowCount() != len(dets):
            self.table.setRowCount(len(dets))

        for row, d in enumerate(dets):
            # Target Type
            raw_cls = str(d.get("sinif", "")).upper()
            disp_name = d.get("gorunen", d.get("sinif", "?"))
            it_name = self.table.item(row, 0)
            if it_name is None:
                it_name = QTableWidgetItem(disp_name)
                it_name.setForeground(SINIF_RENK.get(raw_cls, QColor(220, 220, 220)))
                self.table.setItem(row, 0, it_name)
            else:
                if it_name.text() != disp_name:
                    it_name.setText(disp_name)
                    it_name.setForeground(SINIF_RENK.get(raw_cls, QColor(220, 220, 220)))

            # Affiliation
            if is_enemy(d):
                aff_txt = "🔴 ENEMY (RED)"
                aff_col = QColor(255, 60, 60)
            elif is_friendly(d):
                aff_txt = "🔵 FRIENDLY (BLUE)"
                aff_col = QColor(56, 189, 248)
            else:
                aff_txt = "⚪ UNKNOWN"
                aff_col = QColor(180, 180, 180)

            it_aff = self.table.item(row, 1)
            if it_aff is None:
                it_aff = QTableWidgetItem(aff_txt)
                it_aff.setForeground(aff_col)
                it_aff.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 1, it_aff)
            else:
                if it_aff.text() != aff_txt:
                    it_aff.setText(aff_txt)
                    it_aff.setForeground(aff_col)

            # Confidence
            conf_val = float(d.get("guven", 0.0))
            conf_txt = f"{conf_val * 100:.0f}%"
            it_conf = self.table.item(row, 2)
            if it_conf is None:
                it_conf = QTableWidgetItem(conf_txt)
                it_conf.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 2, it_conf)
            else:
                if it_conf.text() != conf_txt:
                    it_conf.setText(conf_txt)

            # Distance
            m = d.get("mesafe_m")
            dist_txt = f"{m:.1f} m" if m else "~10.0 m"
            it_dist = self.table.item(row, 3)
            if it_dist is None:
                it_dist = QTableWidgetItem(dist_txt)
                it_dist.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 3, it_dist)
            else:
                if it_dist.text() != dist_txt:
                    it_dist.setText(dist_txt)

    def update_iff(self, info: dict):
        """兼容保留接口，已整合至 update_detections 避免冲突"""
        pass

    def set_emergency_stop_visual(self):
        """急停状态下的醒目指示"""
        self.lbl_iff.setText("🛑 EMERGENCY STOP ENGAGED\nWEAPON SYSTEM SAFE - ALL CEASE FIRE")
        self._set_iff_style("#ef4444", "#3f1010")

    def clear_detections(self):
        """离开模式时清空表格"""
        self.table.setRowCount(0)
        self.lbl_iff.setText("STANDBY")
        self._set_iff_style("#64748b", "#0f172a")
        self.lbl_summary.setText("STANDBY")
