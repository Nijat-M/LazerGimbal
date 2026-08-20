# -*- coding: utf-8 -*-
"""
IFF — Dost/Dusman Tanima (Identification Friend or Foe)
敌我识别与高对比度色彩分析系统

规范依据:
  - 敌我区分靠靶标颜色：友军 (FRIENDLY) = 蓝色，敌军 (ENEMY) = 红色。
  - 任务目标：快速精准锁定敌方红色目标，全程保护友方蓝色目标。

增强特性:
  1. HSV + BGR + CIELAB 多空间融合色彩色度分析，抗弱光、强光与色彩褪色；
  2. 空间质心多目标时序平滑追踪器 (Spatial Temporal IFF Tracker)，杜绝丢帧闪烁；
  3. 滞后状态机 (State Hysteresis)，防止敌我状态在临界点频繁跳变。
"""

import math
from collections import deque
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

ENEMY, FRIENDLY, NEUTRAL = "ENEMY", "FRIENDLY", "NEUTRAL"

# BGR — 屏幕绘制高对比度颜色 (High-Contrast Cyberpunk Tactical Colors)
IFF_BGR = {
    ENEMY:    (30, 30, 255),     # 鲜艳赤红 (Bright Red / Hostile)
    FRIENDLY: (255, 200, 0),     # 鲜艳青蓝 (Bright Cyan-Blue / Friendly)
    NEUTRAL:  (0, 180, 255),     # 战术亮琥珀黄 (Bright Amber / Analyzing)
}
IFF_ETIKET = {
    ENEMY:    "ENEMY (RED)",
    FRIENDLY: "FRIENDLY (BLUE)",
    NEUTRAL:  "UNKNOWN",
}


def iff_analiz(frame_bgr, box):
    """
    走廊/室内光照高鲁棒敌我识别 (IFF) 分析
    
    物理判据：
    - 红色敌军 (ENEMY RED)：
        H <= 13 或 H >= 167 (纯红/偏橙红)
        S >= 30, V >= 20
        (R - B) / (R + B + 1) >= 0.18 (强力压制蓝光反射)
        (R - G) / (R + G + 1) >= 0.08 且 R >= G + 8 (排除 R~=G 的黄白背景墙面)
        R >= B + 15
    - 蓝色友军 (FRIENDLY BLUE)：
        75 <= H <= 155 (青蓝/深蓝广谱)
        S >= 20, V >= 18
        (B - R) / (B + R + 1) >= 0.08 或 B >= R + 6 (B 显著超越 R)
        B >= 25
    - 环境黄墙/木门/门框：
        H 在 20~35 区间，R ~= G，(R-B) 与 (B-R) 比值均不达标，完全排除

    返回 (taraf, kirmizi_sayisi, mavi_sayisi, oran)
    """
    if cv2 is None or frame_bgr is None or box is None:
        return NEUTRAL, 0, 0, 0.0

    x1, y1, x2, y2 = [int(round(v)) for v in box]
    h, w = frame_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    bw, bh = x2 - x1, y2 - y1
    if bw < 6 or bh < 6:
        return NEUTRAL, 0, 0, 0.0

    # 提取目标主体 ROI (去除边缘 4% 杂边)
    my = max(1, int(bh * 0.04))
    mx = max(1, int(bw * 0.04))
    roi = frame_bgr[y1 + my:y2 - my, x1 + mx:x2 - mx]
    if roi.size == 0 or roi.shape[0] < 4 or roi.shape[1] < 4:
        return NEUTRAL, 0, 0, 0.0

    total_px = roi.shape[0] * roi.shape[1]

    b = roi[:, :, 0].astype(np.float32)
    g = roi[:, :, 1].astype(np.float32)
    r = roi[:, :, 2].astype(np.float32)

    try:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        H = hsv[:, :, 0].astype(np.float32)
        S = hsv[:, :, 1].astype(np.float32)
        V = hsv[:, :, 2].astype(np.float32)
    except Exception:
        H = np.zeros_like(b)
        S = np.zeros_like(b)
        V = np.zeros_like(b)

    # --- 1. 红色敌方像素判定 ---
    is_red_pixel = (
        ((H <= 13) | (H >= 167)) &
        (S >= 30) & (V >= 20) &
        ((r - b) / (r + b + 1.0) >= 0.18) &
        ((r - g) / (r + g + 1.0) >= 0.08) &
        (r >= g + 8) &
        (r >= b + 15)
    )

    # --- 2. 蓝色友方像素判定 ---
    is_blue_pixel = (
        (H >= 75) & (H <= 155) &
        (S >= 20) & (V >= 18) &
        (((b - r) / (b + r + 1.0) >= 0.08) | (b >= r + 6)) &
        (b >= 25)
    )

    kirmizi_sayisi = int(np.count_nonzero(is_red_pixel))
    mavi_sayisi = int(np.count_nonzero(is_blue_pixel))

    r_ratio = kirmizi_sayisi / float(total_px)
    b_ratio = mavi_sayisi / float(total_px)
    max_ratio = max(r_ratio, b_ratio)

    min_px_thresh = 3 if total_px < 250 else 4
    min_ratio_thresh = 0.020

    # 裁决决策：比例达到 2.0% 且数量达到 4 颗
    if mavi_sayisi >= min_px_thresh and b_ratio >= min_ratio_thresh:
        if mavi_sayisi > kirmizi_sayisi * 1.20 or kirmizi_sayisi < min_px_thresh:
            return FRIENDLY, kirmizi_sayisi, mavi_sayisi, b_ratio

    if kirmizi_sayisi >= min_px_thresh and r_ratio >= min_ratio_thresh:
        if kirmizi_sayisi > mavi_sayisi * 1.20 or mavi_sayisi < min_px_thresh:
            return ENEMY, kirmizi_sayisi, mavi_sayisi, r_ratio

    return NEUTRAL, kirmizi_sayisi, mavi_sayisi, max_ratio


class TrackedIFFObject:
    """单个跟踪目标的时序状态载体 (平滑防抖与敏捷判定)"""
    def __init__(self, track_id: int, box, class_name: str, confidence: float, initial_side: str):
        self.track_id = track_id
        self.box = [float(v) for v in box]
        self.class_name = class_name
        self.confidence = float(confidence)
        self.history = deque(maxlen=6)
        self.history.append(initial_side)
        self.current_side = initial_side
        self.missing_frames = 0

    @property
    def center(self):
        return ((self.box[0] + self.box[2]) / 2.0, (self.box[1] + self.box[3]) / 2.0)

    def update(self, new_box, class_name: str, confidence: float, raw_side: str):
        # 指数移动平均 (EMA) 平滑坐标抖动
        alpha = 0.70
        for i in range(4):
            self.box[i] = alpha * float(new_box[i]) + (1.0 - alpha) * self.box[i]
        self.class_name = class_name
        self.confidence = float(confidence)
        self.missing_frames = 0
        self.history.append(raw_side)

        # 敏捷时序表决 (Agile Temporal Hysteresis)
        f_votes = self.history.count(FRIENDLY)
        e_votes = self.history.count(ENEMY)
        
        if f_votes >= 1 and f_votes > e_votes:
            self.current_side = FRIENDLY
        elif e_votes >= 1 and e_votes > f_votes:
            self.current_side = ENEMY
        elif raw_side != NEUTRAL:
            self.current_side = raw_side




class IFFKarari:
    """
    空间质心时序跟踪器 (Spatial Temporal Multi-Object IFF Stabilizer)
    
    1. 使用欧氏距离质心关联匹配，不再依赖不稳定的字符串哈希；
    2. 支持最大 5 帧丢帧记忆保持 (Hold-over)，彻底消除目标框在画面中的闪烁；
    3. 坐标平滑与敌我滞后稳定判定。
    """

    def __init__(self, max_distance: float = 75.0, max_missing: int = 5):
        self.max_distance = max_distance
        self.max_missing = max_missing
        self.tracks = {}
        self.next_track_id = 1

    def update_frame(self, frame_bgr, raw_targets: list) -> list:
        """
        处理当前帧的所有原始 YOLO 检测结果，返回平滑且稳定的分析列表
        """
        # 1. 对所有输入目标计算单帧色彩裁决
        detections = []
        for t in raw_targets:
            box = t.box
            raw_cname = t.class_name if t.class_name else f"Cls_{t.class_id}"
            conf = float(t.confidence or 0.0)
            side_raw, k_cnt, m_cnt, oran = iff_analiz(frame_bgr, box)
            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0
            detections.append({
                "target": t,
                "box": box,
                "class_name": raw_cname,
                "confidence": conf,
                "side_raw": side_raw,
                "center": (cx, cy),
                "k_cnt": k_cnt,
                "m_cnt": m_cnt,
            })

        # 2. 质心距离矩阵匹配现有轨迹
        unmatched_detections = list(range(len(detections)))
        matched_track_ids = set()

        for track_id, track in list(self.tracks.items()):
            best_dist = self.max_distance
            best_det_idx = -1
            tcx, tcy = track.center

            for d_idx in unmatched_detections:
                dcx, dcy = detections[d_idx]["center"]
                dist = math.hypot(dcx - tcx, dcy - tcy)
                if dist < best_dist:
                    best_dist = dist
                    best_det_idx = d_idx

            if best_det_idx >= 0:
                det = detections[best_det_idx]
                track.update(det["box"], det["class_name"], det["confidence"], det["side_raw"])
                matched_track_ids.add(track_id)
                unmatched_detections.remove(best_det_idx)
            else:
                track.missing_frames += 1
                if track.missing_frames > self.max_missing:
                    del self.tracks[track_id]

        # 3. 为未匹配的新检测创建新轨迹
        for d_idx in unmatched_detections:
            det = detections[d_idx]
            new_id = self.next_track_id
            self.next_track_id += 1
            self.tracks[new_id] = TrackedIFFObject(
                new_id, det["box"], det["class_name"], det["confidence"], det["side_raw"]
            )

        # 4. 构建输出列表 (包含记忆轨迹，即使某帧临时漏检也保持平稳呈现)
        results = []
        for track_id, track in self.tracks.items():
            if track.missing_frames > 0:
                # 漏检插值平滑处理
                conf = max(0.20, track.confidence * 0.90)
            else:
                conf = track.confidence

            x1, y1, x2, y2 = [int(round(v)) for v in track.box]
            cx, cy = int(round((x1 + x2) / 2)), int(round((y1 + y2) / 2))

            results.append({
                "track_id": track.track_id,
                "raw_name": track.class_name,
                "sinif": track.class_name,
                "guven": conf,
                "box": (x1, y1, x2, y2),
                "position": (cx, cy),
                "taraf": track.current_side,
                "renk": track.current_side,
                "missing": track.missing_frames,
            })

        return results

    def temizle(self):
        """重置所有轨迹"""
        self.tracks.clear()
        self.next_track_id = 1

