# -*- coding: utf-8 -*-
"""
IFF — Dost/Dusman Tanima (Identification Friend or Foe)
敌我识别：靠颜色区分红=敌 / 蓝=友

Sartname dayanagi / 规范依据:
  5.4 HEDEF BILGILERI (s.15):
    "Asama-3'de dusman ve dost ayrimi hedef maketlerinin renkleri uzerinden
     yapilacaktir. Dost hedef MAVI, dusman hedef KIRMIZI renkli olacaktir."
    第三阶段的敌我区分靠靶标颜色：友军=蓝，敌军=红。

  2.4.4.1 Yetenek 7 (s.11):
    1 kirmizi(dusman) + 2 mavi(dost) yerlestirilir. Sistem otonom modda
    dusmani imha eder; bu sure icinde DOST UNSURLARA ATES ETMEDIGI gorulur.
    放 1 红 + 2 蓝，系统自主摧毁敌方，期间必须看到【没有对友军开火】。

Bu yuzden buradaki en onemli kural:
  EMIN DEGILSEN "NEUTRAL" DE.  Yanlis "ENEMY" = dost unsura ates = gorev basarisiz.
  最重要的原则：不确定就返回 NEUTRAL。误判成 ENEMY 就等于朝友军开火，任务直接失败。
"""

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

# Renk kaniti ROI'nin bu oranindan azsa NEUTRAL / 颜色证据低于该占比就判中立
MIN_RENK_ORANI = 0.035
# Baskin renk digerinin bu katindan fazla olmali / 主色须超过次色的这个倍数
BASKINLIK = 1.15

ENEMY, FRIENDLY, NEUTRAL = "ENEMY", "FRIENDLY", "NEUTRAL"

# BGR — ekranda cizim rengi / 屏幕绘制颜色
IFF_BGR = {
    ENEMY:    (40, 40, 240),     # kirmizi (Red / Hostile)
    FRIENDLY: (240, 180, 40),    # mavi (Blue / Friendly)
    NEUTRAL:  (170, 170, 170),   # gri (Neutral / Unknown)
}
IFF_ETIKET = {
    ENEMY:    "ENEMY (RED)",
    FRIENDLY: "FRIENDLY (BLUE)",
    NEUTRAL:  "UNKNOWN",
}


def iff_analiz(frame_bgr, box):
    """
    Kutu icindeki canli kirmizi/mavi piksel oranindan taraf belirler.
    返回 (taraf, kirmizi_sayisi, mavi_sayisi, oran)

    优化：适配10米室内/室外光照下的红蓝靶标检测，
    防止高饱和度门控漏检靶标。
    """
    if cv2 is None or frame_bgr is None or box is None:
        return NEUTRAL, 0, 0, 0.0

    x1, y1, x2, y2 = [int(v) for v in box]
    h, w = frame_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if (x2 - x1) < 6 or (y2 - y1) < 6:
        return NEUTRAL, 0, 0, 0.0

    # 裁掉外圈 8%，保留靶标主要面积
    mx, my = int((x2 - x1) * 0.08), int((y2 - y1) * 0.08)
    roi = frame_bgr[y1 + my:y2 - my, x1 + mx:x2 - mx]
    if roi.size == 0:
        return NEUTRAL, 0, 0, 0.0

    try:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    except Exception:
        return NEUTRAL, 0, 0, 0.0

    H = hsv[:, :, 0].astype(np.int32)
    S = hsv[:, :, 1].astype(np.int32)
    V = hsv[:, :, 2].astype(np.int32)

    # 真实光照条件下的有效色彩阈值
    vivid = (S >= 45) & (V >= 35) & (V <= 255)
    kirmizi = int(np.count_nonzero(vivid & ((H <= 14) | (H >= 165))))
    mavi = int(np.count_nonzero(vivid & (H >= 88) & (H <= 142)))

    total = max(roi.shape[0] * roi.shape[1], 1)
    max_color = max(kirmizi, mavi)
    oran = max_color / total

    # 判定规则
    if max_color < 8 or oran < MIN_RENK_ORANI:
        return NEUTRAL, kirmizi, mavi, oran

    if mavi >= 8 and (mavi > kirmizi * BASKINLIK or kirmizi < 6):
        return FRIENDLY, kirmizi, mavi, oran
    if kirmizi >= 8 and (kirmizi > mavi * BASKINLIK or mavi < 6):
        return ENEMY, kirmizi, mavi, oran

    if mavi > kirmizi:
        return FRIENDLY, kirmizi, mavi, oran
    elif kirmizi > mavi:
        return ENEMY, kirmizi, mavi, oran

    return NEUTRAL, kirmizi, mavi, oran


class IFFKarari:
    """
    Zaman icinde kararli taraf karari.
    时序稳定的敌我判定 —— 结合短期时序滤波提高抗抖动性。
    """

    def __init__(self, pencere=5, esik=0.5):
        self.pencere = pencere
        self.esik = esik
        self._gecmis = {}

    def guncelle(self, key, taraf):
        h = self._gecmis.setdefault(key, [])
        h.append(taraf)
        if len(h) > self.pencere:
            h.pop(0)
        if not h:
            return NEUTRAL
        for t in (ENEMY, FRIENDLY):
            if h.count(t) / len(h) >= self.esik:
                return t
        return h[-1] if h else NEUTRAL

    def temizle(self):
        self._gecmis.clear()
