#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 5 / 步骤 5 : Mevcut PyQt arayuzunuze 20 satirda entegrasyon ornegi
                  20 行接入你们现有 PyQt 界面的示例

Sizin arayuzunuzde zaten kamera->QLabel akisi VAR. Yapmaniz gereken tek sey:
你们界面里相机→QLabel 的链路已经通了，唯一要做的是：

    ESKI / 原来:   self.label.setPixmap(self.mat2pix(frame))
    YENI / 改成:   dets = self.det.tespit(frame)
                   self.label.setPixmap(self.mat2pix(self.det.ciz(frame, dets)))
                   self.tablo_guncelle(dets)      # <- hakem icin sinif listesi / 给裁判看的分类列表

Tek basina calistirmak icin / 单独运行:
    python s5_ui_pyqt.py --weights best.pt --source 0
"""
import argparse, sys
import cv2
from s4_detector import HedefDedektoru

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
except ImportError:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
    except ImportError:
        sys.exit("pip install PyQt5")


def mat2pix(bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    return QtGui.QPixmap.fromImage(QtGui.QImage(rgb.data, w, h, 3 * w,
                                                QtGui.QImage.Format_RGB888).copy())


class Panel(QtWidgets.QWidget):
    """Yetenek 6 gosterim paneli / 能力 6 展示面板"""

    def __init__(self, weights, source, conf, imgsz, hfov, target_m):
        super().__init__()
        self.setWindowTitle("Yetenek 6 - Hedef Tespit ve Siniflandirma")
        self.det = HedefDedektoru(weights, conf=conf, imgsz=imgsz,
                                  hfov_deg=hfov, hedef_genislik_m=target_m)
        self.cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)

        self.video = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.video.setMinimumSize(960, 540)
        self.video.setStyleSheet("background:#111;")

        self.tablo = QtWidgets.QTableWidget(0, 3)
        self.tablo.setHorizontalHeaderLabels(["HEDEF TIPI", "GUVEN", "MESAFE"])
        self.tablo.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch)
        self.tablo.setMaximumWidth(360)
        self.tablo.setStyleSheet(
            "QTableWidget{background:#1b1f24;color:#e6edf3;gridline-color:#30363d;"
            "font-size:15px;} QHeaderView::section{background:#22272e;color:#9fb0c0;"
            "padding:6px;border:0;font-weight:600;}")

        self.durum = QtWidgets.QLabel("HAZIR")
        self.durum.setStyleSheet("color:#9fb0c0;padding:4px;font-size:13px;")

        sag = QtWidgets.QVBoxLayout()
        sag.addWidget(QtWidgets.QLabel("<b style='color:#e6edf3'>SINIFLANDIRMA</b>"))
        sag.addWidget(self.tablo)
        sag.addWidget(self.durum)

        lay = QtWidgets.QHBoxLayout(self)
        lay.addWidget(self.video, 1)
        lay.addLayout(sag)
        self.setStyleSheet("background:#0d1117;")

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)

    def tick(self):
        ok, fr = self.cap.read()
        if not ok:
            return
        dets = self.det.tespit(fr)
        vis = self.det.ciz(fr, dets)
        self.video.setPixmap(mat2pix(vis).scaled(
            self.video.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.tablo.setRowCount(len(dets))
        for i, d in enumerate(dets):
            self.tablo.setItem(i, 0, QtWidgets.QTableWidgetItem(d["gorunen"]))
            self.tablo.setItem(i, 1, QtWidgets.QTableWidgetItem(f'%{d["guven"]*100:.0f}'))
            self.tablo.setItem(i, 2, QtWidgets.QTableWidgetItem(
                f'{d["mesafe_m"]:.1f} m' if d["mesafe_m"] else "-"))
        self.durum.setText(f"Tespit edilen hedef sayisi: {len(dets)}")

    def closeEvent(self, e):
        self.cap.release()
        e.accept()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--source", default="0")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--hfov", type=float, default=None)
    ap.add_argument("--target_m", type=float, default=None)
    a = ap.parse_args()
    app = QtWidgets.QApplication(sys.argv)
    w = Panel(a.weights, a.source, a.conf, a.imgsz, a.hfov, a.target_m)
    w.resize(1400, 620)
    w.show()
    sys.exit(app.exec_())
