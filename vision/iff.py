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
    敌我识别核心颜色分析函数 (Identification Friend or Foe Analysis)

    【竞赛识别规则与物理挑战】
    1. 阵营定义:
       - 友军目标 (FRIENDLY): 蓝色涂装 / 蓝色靶标；
       - 敌军目标 (ENEMY): 红色涂装 / 红色靶标；
       - 中立未知 (NEUTRAL): 尚未确认为明确敌我的目标（禁止盲目开火）。
    2. 恶劣环境干扰挑战:
       - 走廊室内暖光灯照射、反光白墙、原木黄色门框经常导致 HSV 色相 H 产生偏移；
       - 蓝光激光反射或强光过曝导致单颜色空间（单纯 HSV 或 RGB）严重失效。

    【多空间融合色度判据数学原理】
    - 红色敌方判定 (ENEMY RED):
        1. 环形色相双区间: (H <= 13) 或 (H >= 167)，覆盖 HSV 8 位空间两端（0~26° 与 334°~360°）；
        2. 色彩饱和度与明度门限: S >= 30, V >= 20；
        3. 归一化红蓝对比比值: (R - B) / (R + B + 1.0) >= 0.18，强力压制高功率蓝光激光的反光干扰；
        4. 排除黄色木门/黄墙: (R - G) / (R + G + 1.0) >= 0.08 且 R >= G + 8。
           (黄色在 RGB 空间中 R 约等于 G，此比值能将环境黄墙与木质靶架彻底剔除，绝不误判为红色敌军)；
        5. 绝对红通道优势: R >= B + 15。
    - 蓝色友方判定 (FRIENDLY BLUE):
        1. 广谱色相区间: 75 <= H <= 155，覆盖深青、浅蓝、海军蓝；
        2. 归一化蓝红对比比值: (B - R) / (B + R + 1.0) >= 0.08 或 B >= R + 6；
        3. 绝对蓝通道底限: B >= 25。

    Args:
        frame_bgr: 原始 BGR 彩色图像帧 (numpy.ndarray)
        box: 目标边界框 [x1, y1, x2, y2]

    Returns:
        tuple: (taraf, kirmizi_sayisi, mavi_sayisi, oran)
               - taraf: 判定结果 ("ENEMY", "FRIENDLY", "NEUTRAL")
               - kirmizi_sayisi: 框内红色有效像素数
               - mavi_sayisi: 框内蓝色有效像素数
               - oran: 优势颜色像素占有效 ROI 的比例 (0.0 ~ 1.0)
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

    # 【提取核心 ROI：内缩 4% 消除边缘杂色】
    # 目标检测框边缘常包含 2~5 像素的环境背景（如红墙、地毯）。
    # 内缩 4% 可以确保只对靶标本身的中心材质进行采样分析，彻底排除背景误导。
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

    # 1. 红色敌方像素判定掩码
    is_red_pixel = (
        ((H <= 13) | (H >= 167)) &
        (S >= 30) & (V >= 20) &
        ((r - b) / (r + b + 1.0) >= 0.18) &
        ((r - g) / (r + g + 1.0) >= 0.08) &
        (r >= g + 8) &
        (r >= b + 15)
    )

    # 2. 蓝色友方像素判定掩码
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

    # 最小绝对像素数阈值（小目标至少 3 颗，标准目标至少 4 颗，防止孤立噪点误触发）
    min_px_thresh = 3 if total_px < 250 else 4
    min_ratio_thresh = 0.020  # 最低占比门限 2.0%

    # 3. 最终优势阵营综合决策 (引入 20% 优势容限)
    if mavi_sayisi >= min_px_thresh and b_ratio >= min_ratio_thresh:
        if mavi_sayisi > kirmizi_sayisi * 1.20 or kirmizi_sayisi < min_px_thresh:
            return FRIENDLY, kirmizi_sayisi, mavi_sayisi, b_ratio

    if kirmizi_sayisi >= min_px_thresh and r_ratio >= min_ratio_thresh:
        if kirmizi_sayisi > mavi_sayisi * 1.20 or mavi_sayisi < min_px_thresh:
            return ENEMY, kirmizi_sayisi, mavi_sayisi, r_ratio

    return NEUTRAL, kirmizi_sayisi, mavi_sayisi, max_ratio


class TrackedIFFObject:
    """
    单个跟踪目标的时序状态载体 (平滑防抖与敏捷判定)

    核心功能:
    1. 空间坐标 EMA 指数移动平均平滑，消除目标框像素级颤抖；
    2. 滑动历史窗口 (maxlen=6) 表决，避免目标闪烁时阵营频繁交替变更。
    """
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
    def center(self) -> tuple[float, float]:
        """获取目标框的几何中心点 (center_x, center_y)"""
        return ((self.box[0] + self.box[2]) / 2.0, (self.box[1] + self.box[3]) / 2.0)

    def update(self, new_box, class_name: str, confidence: float, raw_side: str) -> None:
        """
        使用当前帧的实测数据更新该目标状态

        Args:
            new_box: 当前帧检测到的新坐标 [x1, y1, x2, y2]
            class_name: 类别名称
            confidence: 检测置信度
            raw_side: 本帧色彩单帧初判结果 ("ENEMY" / "FRIENDLY" / "NEUTRAL")
        """
        # 指数移动平均 (EMA) 平滑目标框，alpha=0.70 兼顾极低延迟与平稳去抖
        alpha = 0.70
        for i in range(4):
            self.box[i] = alpha * float(new_box[i]) + (1.0 - alpha) * self.box[i]
        self.class_name = class_name
        self.confidence = float(confidence)
        self.missing_frames = 0
        self.history.append(raw_side)

        # 敏捷时序滞后表决 (Agile Temporal Hysteresis):
        # 只要有一方表决数占优且至少达到 1 票即更新判定，防止阵营死锁
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
    空间质心多目标时序跟踪器 (Spatial Centroid Multi-Object IFF Stabilizer)
    
    【核心设计优势】
    1. 欧氏几何质心匹配: 使用空间欧氏距离关联检测框，彻底消除字符串哈希带来的 ID 错乱；
    2. 漏检记忆保持 (Hold-over): 允许目标在画面中瞬时漏检最多 5 帧，平滑插值保持呈现，杜绝 UI 闪烁；
    3. 稳定输出封装: 统一输出格式兼容 Stage 3 任务决策与裁判端多目标表格。
    """

    def __init__(self, max_distance: float = 75.0, max_missing: int = 5):
        """
        初始化时序跟踪器

        Args:
            max_distance: 帧间质心关联匹配的最大欧氏距离门限（像素，默认 75px）
            max_missing: 允许连续丢失的最大帧数（超过此帧数彻底注销该轨迹，默认 5 帧）
        """
        self.max_distance = max_distance
        self.max_missing = max_missing
        self.tracks = {}
        self.next_track_id = 1

    def update_frame(self, frame_bgr, raw_targets: list) -> list:
        """
        处理当前视频帧中的全部原始目标，执行阵营识别、质心匹配与平滑跟踪

        Args:
            frame_bgr: 原始 BGR 彩色图像帧
            raw_targets: YOLO 或其他检测器返回的原始目标对象列表

        Returns:
            list[dict]: 平滑稳定后的目标信息字典列表 (包含 track_id, box, taraf 等)
        """
        # 1. 对输入的目标逐一提取中心点并执行单帧色彩色度分析
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

        # 2. 基于欧氏几何距离贪心关联当前帧与历史轨迹
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
                # 匹配成功：更新目标状态
                det = detections[best_det_idx]
                track.update(det["box"], det["class_name"], det["confidence"], det["side_raw"])
                matched_track_ids.add(track_id)
                unmatched_detections.remove(best_det_idx)
            else:
                # 匹配失败：累加丢失帧数，超时注销
                track.missing_frames += 1
                if track.missing_frames > self.max_missing:
                    del self.tracks[track_id]

        # 3. 为画面中新出现的检测目标分配全新的自增 Track ID
        for d_idx in unmatched_detections:
            det = detections[d_idx]
            new_id = self.next_track_id
            self.next_track_id += 1
            self.tracks[new_id] = TrackedIFFObject(
                new_id, det["box"], det["class_name"], det["confidence"], det["side_raw"]
            )

        # 4. 构建输出结果字典列表（若当前帧临时漏检，适度衰减置信度并保持输出，防止画面闪烁）
        results = []
        for track_id, track in self.tracks.items():
            if track.missing_frames > 0:
                # 漏检状态置信度平滑衰减
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

    def temizle(self) -> None:
        """重置并排空所有正在追踪的历史轨迹"""
        self.tracks.clear()
        self.next_track_id = 1

