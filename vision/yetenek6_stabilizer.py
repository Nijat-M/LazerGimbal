# -*- coding: utf-8 -*-
"""
Yetenek 6 时序稳定器 (Temporal Stabilizer)

解决的问题：
    目标不动、相机不动，但界面上的检测数量和置信度一直跳。

根因：
    检测是【每帧独立】做的，没有任何跨帧记忆。
    真实画面每帧都不一样（传感器噪声、自动曝光呼吸、灯光闪烁、
    轻微失焦），置信度就在阈值上下摆动，于是目标忽有忽无。
    这不是 YOLO 的 bug —— 同一张图输入 100 次，输出完全一致。

做法（标准目标跟踪思路）：
    1. 跨帧匹配   用 IoU 把这一帧的框和已有轨迹配对
    2. 迟滞判定   连续命中 min_hits 次才显示；丢失 max_age 帧后才移除
                  （出现难、消失也难 -> 数字不再跳）
    3. 平滑       框坐标和置信度用指数滑动平均，视觉上不再抖
    4. 类别投票   用最近若干帧的多数票定类别，防止 F16/Füze 来回切

对界面的效果：
    TOPLAM 数字稳定，置信度平滑变化，框不再闪烁。
"""

from collections import deque, Counter


def _iou(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(ix1 - ix0, 0), max(iy1 - iy0, 0)
    inter = iw * ih
    ua = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / ua if ua > 0 else 0.0


class _Track:
    __slots__ = ("box", "conf", "hits", "misses", "cls_votes", "sinif", "gorunen", "mesafe")

    def __init__(self, d):
        self.box = list(d["box"])
        self.conf = d["guven"]
        self.hits = 1
        self.misses = 0
        self.cls_votes = deque([d["sinif"]], maxlen=15)
        self.sinif = d["sinif"]
        self.gorunen = d["gorunen"]
        self.mesafe = d["mesafe_m"]

    def update(self, d, alpha):
        for i in range(4):
            self.box[i] = alpha * d["box"][i] + (1 - alpha) * self.box[i]
        self.conf = alpha * d["guven"] + (1 - alpha) * self.conf
        if d["mesafe_m"] is not None:
            self.mesafe = (alpha * d["mesafe_m"] + (1 - alpha) * self.mesafe
                           if self.mesafe else d["mesafe_m"])
        self.cls_votes.append(d["sinif"])
        # 多数票定类别，防止两类之间来回跳
        win = Counter(self.cls_votes).most_common(1)[0][0]
        if win != self.sinif:
            self.sinif = win
            self.gorunen = d["gorunen"] if d["sinif"] == win else self.gorunen
        self.hits += 1
        self.misses = 0


class DetectionStabilizer:
    """
    参数含义：
        iou_thr   跨帧认定"同一个目标"的最小 IoU
        min_hits  连续命中几次才对外显示（防止一闪而过的误检）
        max_age   丢失几帧后才真正删除（防止偶尔漏检导致数字掉下去）
        alpha     平滑系数，越小越平滑但响应越慢
    """

    def __init__(self, iou_thr=0.30, min_hits=3, max_age=8, alpha=0.45):
        self.iou_thr = iou_thr
        self.min_hits = min_hits
        self.max_age = max_age
        self.alpha = alpha
        self.tracks = []

    def reset(self):
        self.tracks = []

    def update(self, dets):
        """喂入本帧原始检测，返回稳定后的检测列表（结构与输入一致）。"""
        used = set()
        # 1) 已有轨迹找最佳匹配
        for t in self.tracks:
            best, best_iou = -1, self.iou_thr
            for i, d in enumerate(dets):
                if i in used:
                    continue
                v = _iou(t.box, d["box"])
                if v > best_iou:
                    best, best_iou = i, v
            if best >= 0:
                t.update(dets[best], self.alpha)
                used.add(best)
            else:
                t.misses += 1
                # 命中数必须【可减】：否则一个只在 15% 帧出现的背景误检
                # （门框、消防箱…）也会靠日积月累攒够 min_hits 被确认，
                # 然后一直粘在画面上。递减让它永远达不到确认线。
                t.hits = max(t.hits - 1, 0)

        # 2) 未匹配的检测 -> 新轨迹
        for i, d in enumerate(dets):
            if i not in used:
                self.tracks.append(_Track(d))

        # 3) 老化淘汰
        self.tracks = [t for t in self.tracks if t.misses <= self.max_age]

        # 4) 只输出已确认的轨迹
        out = []
        for t in self.tracks:
            if t.hits < self.min_hits:
                continue
            out.append({
                "sinif": t.sinif,
                "gorunen": t.gorunen,
                "guven": t.conf,
                "box": tuple(int(v) for v in t.box),
                "mesafe_m": t.mesafe,
            })
        return sorted(out, key=lambda d: -d["guven"])
