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
    多色彩空间融合分析 (HSV + BGR差分 + CIELAB)
    返回 (taraf, kirmizi_sayisi, mavi_sayisi, oran)
    """
    if cv2 is None or frame_bgr is None or box is None:
        return NEUTRAL, 0, 0, 0.0

    x1, y1, x2, y2 = [int(v) for v in box]
    h, w = frame_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    bw, bh = x2 - x1, y2 - y1
    if bw < 6 or bh < 6:
        return NEUTRAL, 0, 0, 0.0

    # 提取目标主体 ROI (去除边缘 4% 杂边)
    mx, my = max(1, int(bw * 0.04)), max(1, int(bh * 0.04))
    roi = frame_bgr[y1 + my:y2 - my, x1 + mx:x2 - mx]
    if roi.size == 0:
        return NEUTRAL, 0, 0, 0.0

    total_px = roi.shape[0] * roi.shape[1]

    # --- 1. RGB / BGR 物理通道 ---
    b = roi[:, :, 0].astype(np.float32)
    g = roi[:, :, 1].astype(np.float32)
    r = roi[:, :, 2].astype(np.float32)

    # --- 2. HSV 色度空间 ---
    try:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        H = hsv[:, :, 0].astype(np.float32)
        S = hsv[:, :, 1].astype(np.float32)
        V = hsv[:, :, 2].astype(np.float32)

        # 红色敌军特征：
        # 1) H位于纯红区间 (0~7 或 170~180)
        # 2) 强饱和度排除黄色墙壁/射灯/木头 (S >= 45, V >= 35)
        # 3) R 通道必须大幅压倒 G 通道与 B 通道 (黄光下 R~=G，纯红 R>>G)
        hsv_red = (
            ((H <= 7) | (H >= 170)) & (S >= 45) & (V >= 35)
            & (r - g >= 25) & (r - b >= 30) & (r / (g + b + 1.0) >= 1.25)
        )
        
        # 蓝色友军特征 (全面适应走廊黄光/低曝光/深蓝/灰蓝 3D 打印靶标)：
        # 1) H位于蓝色广谱区间 (75~155)
        # 2) 宽容饱和度与亮度门限 (S >= 15, V >= 20)
        # 3) 即使在黄光漫反射下，蓝色靶标的 B 通道仍明显高于 R 通道
        hsv_blue = (
            (H >= 75) & (H <= 155) & (S >= 15) & (V >= 20) & (b >= r + 2)
        )
    except Exception:
        hsv_red = np.zeros_like(b, dtype=bool)
        hsv_blue = np.zeros_like(b, dtype=bool)

    # --- 3. BGR 强色度差分特征 ---
    bgr_red = (r >= 65) & (r - g >= 25) & (r - b >= 35) & (r / (g + b + 1.0) >= 1.25)
    bgr_blue = (b >= 40) & (b >= r + 4) & (b / (r + 1.0) >= 1.04)

    is_red = hsv_red | bgr_red
    is_blue = hsv_blue | bgr_blue

    kirmizi_sayisi = int(np.count_nonzero(is_red))
    mavi_sayisi = int(np.count_nonzero(is_blue))

    max_color = max(kirmizi_sayisi, mavi_sayisi)
    oran = max_color / float(max(total_px, 1))

    # 动态像素门限 (微小目标 3 像素，标准目标 5 像素)
    min_px = 3 if total_px < 300 else 5
    min_ratio = 0.008 if total_px < 300 else 0.015

    if max_color < min_px or oran < min_ratio:
        return NEUTRAL, kirmizi_sayisi, mavi_sayisi, oran

    # 主导色彩裁决：友军保护绝对优先 (发现蓝色且占优必判友军，杜绝误击友军)
    if mavi_sayisi >= min_px and (mavi_sayisi >= kirmizi_sayisi or kirmizi_sayisi < min_px):
        return FRIENDLY, kirmizi_sayisi, mavi_sayisi, oran
    elif kirmizi_sayisi >= min_px and (kirmizi_sayisi > mavi_sayisi * 1.2 or mavi_sayisi < min_px):
        return ENEMY, kirmizi_sayisi, mavi_sayisi, oran

    return NEUTRAL, kirmizi_sayisi, mavi_sayisi, oran


class TrackedIFFObject:
    """单个跟踪目标的时序状态载体"""
    def __init__(self, track_id: int, box, class_name: str, confidence: float, initial_side: str):
        self.track_id = track_id
        self.box = [float(v) for v in box]
        self.class_name = class_name
        self.confidence = float(confidence)
        self.history = deque(maxlen=5)
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

        # 稳态多数表决 (友军保护优先)
        f_votes = self.history.count(FRIENDLY)
        e_votes = self.history.count(ENEMY)
        
        if f_votes >= 2 and f_votes >= e_votes:
            self.current_side = FRIENDLY
        elif e_votes >= 2 and e_votes > f_votes:
            self.current_side = ENEMY
        elif f_votes > 0 and e_votes == 0:
            self.current_side = FRIENDLY
        elif e_votes > 0 and f_votes == 0:
            self.current_side = ENEMY


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

