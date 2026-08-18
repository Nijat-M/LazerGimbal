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
}


class DetectionPanel(QGroupBox):
    """Real-time Target Classification & IFF Panel"""

    def __init__(self, parent=None):
        super().__init__("Capability 6 — Target Classification & IFF", parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # 顶部：检测数量 + 模型状态
        self.lbl_summary = QLabel("Model Not Loaded")
        self.lbl_summary.setStyleSheet("""
            background-color: #1a1a1a;
            color: #888;
            font-weight: bold;
            font-family: Consolas, "Segoe UI", monospace;
            padding: 6px;
            border-radius: 4px;
            border: 1px solid #333;
        """)
        self.lbl_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_summary.setWordWrap(True)
        layout.addWidget(self.lbl_summary)

        # ---- Yetenek 7: ATES IZNI / FIRE AUTHORIZATION ----
        # Sartname 2.4.4.1 Yetenek 7: sistem dusman (kirmizi) unsuru imha edecek,
        # dost (mavi) unsurlara ATES ETMEYECEK. Hakem bunu ekranda gormeli.
        # 规范能力7：系统摧毁红色敌方，且【不得】对蓝色友军开火。
        # 裁判必须能在屏幕上看到这个判定 —— 所以单独做一个醒目状态条。
        self.lbl_iff = QLabel("NO TARGET")
        self.lbl_iff.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_iff.setWordWrap(True)
        self.lbl_iff.setMinimumHeight(38)
        self._set_iff_style("#64748b", "#0f172a")
        layout.addWidget(self.lbl_iff)

        # 分类结果表 (4列: Target Type | Affiliation (IFF) | Confidence | Distance)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Target Type", "Affiliation (IFF)", "Confidence", "Distance"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(180)

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
            "Note: Place targets at 5 m / 10 m / 15 m distances.\n"
            "🔴 Red targets are identified as ENEMY, 🔵 Blue targets as FRIENDLY."
        )
        self.lbl_hint.setStyleSheet("color: #94a3b8; font-size: 10px; padding: 2px;")
        self.lbl_hint.setWordWrap(True)
        layout.addWidget(self.lbl_hint)

    # ------------------------------------------------------------------
    def _set_iff_style(self, fg: str, bg: str):
        self.lbl_iff.setStyleSheet(
            f"background-color: {bg}; color: {fg}; font-weight: bold;"
            f"font-family: Consolas, monospace; font-size: 12px;"
            f"padding: 6px; border-radius: 4px; border: 2px solid {fg};"
        )

    def set_model_status(self, ok: bool, message: str):
        """Update top status bar on model load status"""
        color = "#00ff00" if ok else "#ff5555"
        self.lbl_summary.setText(message)
        self.lbl_summary.setStyleSheet(f"""
            background-color: #1a1a1a;
            color: {color};
            font-weight: bold;
            font-family: Consolas, "Segoe UI", monospace;
            padding: 6px;
            border-radius: 4px;
            border: 1px solid #333;
        """)
        if not ok:
            self.table.setRowCount(0)

    def update_detections(self, dets: list):
        """
        Refresh table and IFF status every frame.
        dets: [{'sinif','gorunen','guven','box','mesafe_m','renk','taraf'}, ...]
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

        self.lbl_summary.setText(f"TOTAL TARGETS: {len(dets)}   |   🔴 ENEMY: {red_c}   |   🔵 FRIENDLY: {blue_c}   |   ⚪ UNKNOWN: {neutral_c}")

        # ---- Yetenek 7: 开火授权与友军保护判定 ----
        if red_c > 0:
            enemy_names = ", ".join([d.get("gorunen", d.get("sinif", "ENEMY")) for d in dets if is_enemy(d)])
            txt = f"🔥 FIRE AUTHORIZED  >>  {enemy_names}"
            if blue_c > 0:
                txt += chr(10) + f"🛡️ PROTECTED: {blue_c} FRIENDLY (BLUE) - DO NOT FIRE"
            self._set_iff_style("#ef4444", "#2a0808")
        elif blue_c > 0:
            txt = f"🛑 HOLD FIRE  --  ALL {blue_c} FRIENDLY UNITS SAFE"
            txt += chr(10) + f"🛡️ PROTECTED: {blue_c} FRIENDLY (BLUE) - DO NOT FIRE"
            self._set_iff_style("#38bdf8", "#081a2e")
        else:
            txt = "STANDBY  --  NO TARGET IN SECTOR"
            self._set_iff_style("#64748b", "#0f172a")

        self.lbl_iff.setText(txt)
        self.lbl_summary.setStyleSheet("""
            background-color: #0f172a;
            color: #38bdf8;
            font-weight: bold;
            font-family: Consolas, "Segoe UI", monospace;
            padding: 6px;
            border-radius: 4px;
            border: 1px solid #1e3a8a;
        """)

        # 刷新 4 列详细表格
        self.table.setRowCount(len(dets))
        for row, d in enumerate(dets):
            # 1. Target Type
            raw_cls = str(d.get("sinif", "")).upper()
            display_name = d.get("gorunen", d.get("sinif", "?"))
            item_ad = QTableWidgetItem(display_name)
            item_ad.setForeground(SINIF_RENK.get(raw_cls, QColor(220, 220, 220)))
            self.table.setItem(row, 0, item_ad)

            # 2. Affiliation (IFF)
            if is_enemy(d):
                item_taraf = QTableWidgetItem("🔴 ENEMY (RED)")
                item_taraf.setForeground(QColor(255, 60, 60))
            elif is_friendly(d):
                item_taraf = QTableWidgetItem("🔵 FRIENDLY (BLUE)")
                item_taraf.setForeground(QColor(56, 189, 248))
            else:
                item_taraf = QTableWidgetItem("⚪ UNKNOWN")
                item_taraf.setForeground(QColor(180, 180, 180))
            item_taraf.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, item_taraf)

            # 3. Confidence
            guven_val = float(d.get("guven", 0.0))
            item_conf = QTableWidgetItem(f"{guven_val * 100:.0f}%")
            item_conf.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, item_conf)

            # 4. Distance
            m = d.get("mesafe_m")
            item_m = QTableWidgetItem(f"{m:.1f} m" if m else "~10.0 m")
            item_m.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, item_m)

    def update_iff(self, info: dict):
        """
        Yetenek 7 快速状态同步
        """
        e = int(info.get("enemy", 0))
        f = int(info.get("friendly", 0))
        n = int(info.get("neutral", 0))
        self.lbl_summary.setText(f"ENEMY: {e}   FRIENDLY: {f}   UNKNOWN: {n}")

        if info.get("fire"):
            self.lbl_iff.setText(
                f"🔥 FIRE AUTHORIZED  >>  {info.get('locked') or 'ENEMY (RED)'}"
                + (chr(10) + f"🛡️ PROTECTED: {f} FRIENDLY (BLUE) - DO NOT FIRE" if f else ""))
            self._set_iff_style("#ef4444", "#2a0808")
        elif f > 0:
            self.lbl_iff.setText(
                f"🛑 HOLD FIRE  --  ALL {f} FRIENDLY UNITS SAFE"
                + (chr(10) + f"🛡️ PROTECTED: {f} FRIENDLY (BLUE) - DO NOT FIRE"))
            self._set_iff_style("#38bdf8", "#081a2e")
        elif e > 0:
            self.lbl_iff.setText(f"🎯 ENEMY DETECTED ({e}) - ACQUIRING LOCK")
            self._set_iff_style("#f59e0b", "#2a1f0a")
        else:
            self.lbl_iff.setText("STANDBY  --  NO TARGET IN SECTOR")
            self._set_iff_style("#64748b", "#0f172a")

    def set_emergency_stop_visual(self):
        """急停状态下的醒目指示"""
        self.lbl_iff.setText("🛑 EMERGENCY STOP ENGAGED\nWEAPON SYSTEM SAFE - ALL CEASE FIRE")
        self._set_iff_style("#ef4444", "#3f1010")

    def clear_detections(self):
        """离开模式时清空表格"""
        self.table.setRowCount(0)
        self.lbl_iff.setText("STANDBY")
        self._set_iff_style("#64748b", "#0f172a")
        self.lbl_summary.setText("Standby")
        self.lbl_summary.setStyleSheet("""
            background-color: #1a1a1a;
            color: #888;
            font-weight: bold;
            font-family: Consolas, monospace;
            padding: 5px;
            border-radius: 3px;
            border: 1px solid #333;
        """)
