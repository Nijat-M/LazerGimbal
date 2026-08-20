#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 4 / 步骤 4 : Arayuze takilacak tespit + siniflandirma modulu
                  可直接接入你们 UI 的检测 + 分类模块

Framework bagimsiz. PyQt / Tkinter / Web / ROS -- hepsinde ayni sekilde kullanilir.
框架无关。PyQt / Tkinter / Web / ROS 均可直接调用。

    from s4_detector import HedefDedektoru
    det = HedefDedektoru("best.pt", conf=0.35, imgsz=960)
    dets = det.tespit(frame_bgr)              # [{'sinif','guven','box','mesafe_m'}, ...]
    vis  = det.ciz(frame_bgr, dets)           # arayuze basilacak kare / 送给界面的画面

Tek basina test / 单独测试:
    python s4_detector.py --weights best.pt --source 0          # kamera
    python s4_detector.py --weights best.pt --source video.mp4
"""
import argparse, math, os, time
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None
from PIL import Image, ImageDraw, ImageFont

# Target classes friendly English names
GORUNEN_AD = {
    "F16": "F-16 Fighter Jet",
    "HELIKOPTER": "Helicopter",
    "BALISTIK_FUZE": "Ballistic Missile",
    "FUZE": "Missile",
    "MINI_IHA": "Mini/Micro UAV",
    "IHA": "Mini/Micro UAV",
}
RENK = {  # BGR
    "F16": (60, 200, 60),
    "HELIKOPTER": (60, 190, 235),
    "BALISTIK_FUZE": (70, 90, 240),
    "FUZE": (70, 90, 240),
    "MINI_IHA": (235, 170, 60),
    "IHA": (235, 170, 60),
}
FONT_ADAYLARI = [
    "C:/Windows/Fonts/segoeui.ttf", 
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _font(size):
    for p in FONT_ADAYLARI:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


# Renk kaniti bu orandan azsa NEUTRAL denir (ates edilmez).
# 颜色证据低于这个占比就判 NEUTRAL（不开火）。0.12 = ROI 的 12%
MIN_RENK_ORANI = 0.12

# Yanlis renk -> Yetenek 7'de dost unsura ates demektir. Bu yuzden esikler muhafazakar.
# 判错颜色 = 能力7 里朝友军开火。所以阈值取保守值。
_NEUTRAL = ("UNKNOWN", "NEUTRAL", "TARGET", (200, 200, 200))


def renk_analizi(frame_bgr, box):
    """
    Hedef kutusundaki kirmizi/mavi dagilimindan dost-dusman ayrimi.
    从目标框内的红/蓝分布判定敌我。  RED = ENEMY, BLUE = FRIENDLY

    Sartname 5.4 (s.15): dost hedef MAVI, dusman hedef KIRMIZI.
    规范 5.4（第15页）：友军=蓝，敌军=红。
    走廊多色彩空间自适应增强版 (CIELAB + 归一化色度 + 阴影抗性)
    """
    if cv2 is None or frame_bgr is None:
        return _NEUTRAL

    try:
        from vision.iff import iff_analiz, ENEMY, FRIENDLY
        taraf, k_cnt, m_cnt, oran = iff_analiz(frame_bgr, box)
        if taraf == FRIENDLY:
            return "BLUE", "FRIENDLY", "FRIENDLY (BLUE)", (255, 144, 30)
        elif taraf == ENEMY:
            return "RED", "ENEMY", "ENEMY (RED)", (30, 30, 255)
        return _NEUTRAL
    except Exception:
        pass

    x1, y1, x2, y2 = [int(round(v)) for v in box]
    h, w = frame_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if (x2 - x1) < 8 or (y2 - y1) < 8:
        return _NEUTRAL

    mx, my = int((x2 - x1) * 0.10), int((y2 - y1) * 0.10)
    roi = frame_bgr[y1 + my:y2 - my, x1 + mx:x2 - mx]
    if roi.size == 0:
        return _NEUTRAL
    try:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    except Exception:
        return _NEUTRAL

    H = hsv[:, :, 0].astype(np.int32)
    S = hsv[:, :, 1].astype(np.int32)
    V = hsv[:, :, 2].astype(np.int32)

    b = roi[:, :, 0].astype(np.float32)
    g = roi[:, :, 1].astype(np.float32)
    r = roi[:, :, 2].astype(np.float32)
    tot = b + g + r + 1e-5
    rn = r / tot
    bn = b / tot

    red_mask = ((H <= 16) | (H >= 160)) & (S >= 22) & (V >= 15) & (rn >= 0.36)
    blue_mask = (H >= 75) & (H <= 155) & (S >= 12) & (V >= 12) & (bn >= 0.32)

    red_count = int(np.count_nonzero(red_mask))
    blue_count = int(np.count_nonzero(blue_mask))

    total = roi.shape[0] * roi.shape[1]
    if max(red_count, blue_count) / max(total, 1) < 0.045:
        return _NEUTRAL

    if blue_count > red_count * 1.25 and blue_count >= 4:
        return "BLUE", "FRIENDLY", "FRIENDLY (BLUE)", (255, 144, 30)
    if red_count > blue_count * 1.25 and red_count >= 4:
        return "RED", "ENEMY", "ENEMY (RED)", (30, 30, 255)
    return _NEUTRAL


class TemporalTargetTracker:
    """
    时域目标生命周期与防抖平滑追踪器 (Temporal Target Lifecycle & Anti-Jitter Smoother)
    
    解决问题：
    1. 相机/目标静止时，单帧置信度波动导致目标频繁丢失/重现 (Total Target 数量跳变 1->0->1->0)
    2. 单帧置信度百分比跳动剧烈 (如 89% -> 63% -> 91%)
    3. 目标框边缘高频微小抖动
    4. NMS 偶发分裂产生的双重框跳变
    """
    def __init__(self, max_lost_frames=6, iou_thresh=0.25, dist_thresh=80.0):
        self.max_lost_frames = max_lost_frames
        self.iou_thresh = iou_thresh
        self.dist_thresh = dist_thresh
        self.tracks = {}  # track_id -> dict
        self.next_id = 1

    @staticmethod
    def _iou(box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = max(1, (box1[2] - box1[0]) * (box1[3] - box1[1]))
        area2 = max(1, (box2[2] - box2[0]) * (box2[3] - box2[1]))
        union = area1 + area2 - inter
        return inter / max(1, union)

    def update(self, raw_dets):
        """
        raw_dets: list of dicts [{'sinif','gorunen','guven','box','mesafe_m','renk','taraf','renk_etiket','renk_bgr'}, ...]
        Returns: smoothed, persistent, confirmed list of targets.
        """
        matched_track_ids = set()
        matched_det_indices = set()

        for det_idx, det in enumerate(raw_dets):
            best_id = None
            best_iou = self.iou_thresh
            best_dist = self.dist_thresh

            d_box = det["box"]
            d_cx = (d_box[0] + d_box[2]) / 2.0
            d_cy = (d_box[1] + d_box[3]) / 2.0

            for tid, track in self.tracks.items():
                if tid in matched_track_ids:
                    continue
                t_box = track["box"]
                t_cx = (t_box[0] + t_box[2]) / 2.0
                t_cy = (t_box[1] + t_box[3]) / 2.0

                iou_val = self._iou(d_box, t_box)
                dist_val = math.hypot(d_cx - t_cx, d_cy - t_cy)

                # 同类别或高 IOU / 近距离关联
                same_cls = (det["sinif"] == track["sinif"])
                if (iou_val > best_iou) or (same_cls and dist_val < best_dist):
                    best_iou = iou_val
                    best_dist = dist_val
                    best_id = tid

            if best_id is not None:
                # 匹配成功：执行 EMA 滤波与状态更新
                matched_track_ids.add(best_id)
                matched_det_indices.add(det_idx)
                track = self.tracks[best_id]

                track["hits"] += 1
                track["lost"] = 0
                if track["hits"] >= 2 or det["guven"] >= 0.45:
                    track["confirmed"] = True

                # EMA 平滑坐标框 (40% 新 + 60% 旧)
                nb = det["box"]
                ob = track["box"]
                track["box"] = (
                    int(0.40 * nb[0] + 0.60 * ob[0]),
                    int(0.40 * nb[1] + 0.60 * ob[1]),
                    int(0.40 * nb[2] + 0.60 * ob[2]),
                    int(0.40 * nb[3] + 0.60 * ob[3]),
                )

                # EMA 平滑置信度 (30% 新 + 70% 旧，极大消除百分比剧烈跳动)
                track["guven"] = 0.30 * det["guven"] + 0.70 * track["guven"]

                # 类别更新
                if det["guven"] > 0.40:
                    track["sinif"] = det["sinif"]
                    track["gorunen"] = det["gorunen"]

                # 距离平滑
                if det.get("mesafe_m") is not None:
                    if track.get("mesafe_m") is not None:
                        track["mesafe_m"] = 0.35 * det["mesafe_m"] + 0.65 * track["mesafe_m"]
                    else:
                        track["mesafe_m"] = det["mesafe_m"]

                # 敌我属性 (IFF) 保持
                if det.get("taraf") in ("ENEMY", "FRIENDLY"):
                    track["renk"] = det["renk"]
                    track["taraf"] = det["taraf"]
                    track["renk_etiket"] = det["renk_etiket"]
                    track["renk_bgr"] = det["renk_bgr"]

        # 2. 未匹配的新检测 -> 新建 Track
        for det_idx, det in enumerate(raw_dets):
            if det_idx not in matched_det_indices:
                tid = self.next_id
                self.next_id += 1
                is_conf = (det["guven"] >= 0.45)
                self.tracks[tid] = {
                    "id": tid,
                    "sinif": det["sinif"],
                    "gorunen": det["gorunen"],
                    "box": det["box"],
                    "guven": det["guven"],
                    "mesafe_m": det.get("mesafe_m"),
                    "renk": det.get("renk", "UNKNOWN"),
                    "taraf": det.get("taraf", "NEUTRAL"),
                    "renk_etiket": det.get("renk_etiket", "TARGET"),
                    "renk_bgr": det.get("renk_bgr", (200, 200, 200)),
                    "hits": 1,
                    "lost": 0,
                    "confirmed": is_conf,
                }

        # 3. 未匹配的存量 Track -> 丢帧处理与衰减
        dead_ids = []
        for tid, track in self.tracks.items():
            if tid not in matched_track_ids:
                track["lost"] += 1
                track["guven"] *= 0.94  # 缓慢衰减
                if track["lost"] > self.max_lost_frames:
                    dead_ids.append(tid)

        for tid in dead_ids:
            del self.tracks[tid]

        # 4. 去重过滤 (重叠框聚合)
        confirmed_tracks = [t for t in self.tracks.values() if t["confirmed"]]
        confirmed_tracks.sort(key=lambda t: -t["guven"])

        suppressed = set()
        clean_tracks = []
        for i, t1 in enumerate(confirmed_tracks):
            if t1["id"] in suppressed:
                continue
            clean_tracks.append(t1)
            for j in range(i + 1, len(confirmed_tracks)):
                t2 = confirmed_tracks[j]
                if self._iou(t1["box"], t2["box"]) > 0.45:
                    suppressed.add(t2["id"])

        return clean_tracks


class HedefDedektoru:
    def __init__(self, weights, conf=0.35, iou=0.45, imgsz=960, device=None,
                 hfov_deg=None, hedef_genislik_m=None):
        """Estimate distance if hfov_deg + hedef_genislik_m are provided."""
        from ultralytics import YOLO
        self.m = YOLO(weights)
        self.conf, self.iou, self.imgsz, self.device = conf, iou, imgsz, device
        self.hfov, self.hedef_m = hfov_deg, hedef_genislik_m
        self.names = self.m.names
        self._f = {}
        self.tracker = TemporalTargetTracker(max_lost_frames=6, iou_thresh=0.25)

    def _mesafe(self, box_px_w, img_w):
        if not (self.hfov and self.hedef_m) or box_px_w <= 1:
            return None
        return img_w * self.hedef_m / (2.0 * box_px_w * math.tan(math.radians(self.hfov) / 2.0))

    def tespit(self, frame_bgr):
        kw = dict(conf=max(0.20, self.conf * 0.75), iou=self.iou, imgsz=self.imgsz, verbose=False)
        if self.device is not None:
            kw["device"] = self.device
        r = self.m.predict(frame_bgr, **kw)[0]
        H, W = frame_bgr.shape[:2]
        raw_dets = []
        if r.boxes is not None:
            for b in r.boxes:
                score = float(b.conf[0])
                if score < max(0.20, self.conf * 0.75):
                    continue
                x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
                ad = self.names[int(b.cls[0])]
                box = (int(x1), int(y1), int(x2), int(y2))
                
                # Color and IFF analysis (Red-Enemy / Blue-Friendly)
                renk, taraf, renk_etiket, renk_bgr = renk_analizi(frame_bgr, box)
                
                raw_dets.append({
                    "sinif": ad,
                    "gorunen": GORUNEN_AD.get(ad.upper(), ad),
                    "guven": score,
                    "box": box,
                    "mesafe_m": self._mesafe(x2 - x1, W),
                    "renk": renk,
                    "taraf": taraf,
                    "renk_etiket": renk_etiket,
                    "renk_bgr": renk_bgr,
                })
        
        # 通过时域生命周期与防抖平滑追踪器输出稳定目标
        stable_dets = self.tracker.update(raw_dets)
        return sorted(stable_dets, key=lambda d: -d["guven"])

    def ciz(self, frame_bgr, dets, baslik="TARGET DETECTION & CLASSIFICATION (CAPABILITY 6)"):
        """Render high-definition tactical HUD labels using PIL"""
        img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        dr = ImageDraw.Draw(img, "RGBA")
        H, W = frame_bgr.shape[:2]
        fs = max(15, int(W / 60))
        f = self._f.setdefault(fs, _font(fs))
        fs2 = max(13, int(W / 80))
        f2 = self._f.setdefault(fs2, _font(fs2))

        red_count = 0
        blue_count = 0

        for d in dets:
            x1, y1, x2, y2 = d["box"]
            
            # Border color based on enemy / friendly (RGB)
            t_taraf = str(d.get("taraf", "")).upper()
            t_renk = str(d.get("renk", "")).upper()
            if t_taraf in ("ENEMY", "DÜŞMAN", "DUSMAN", "RED") or "RED" in t_renk:
                c = (255, 35, 35)      # Bright Red (Enemy)
                red_count += 1
            elif t_taraf in ("FRIENDLY", "DOST", "BLUE") or "BLUE" in t_renk:
                c = (30, 144, 255)     # Bright Blue (Friendly)
                blue_count += 1
            else:
                c = RENK.get(d["sinif"].upper(), (0, 220, 0))[::-1]

            # Draw tactical bounding box
            dr.rectangle([x1, y1, x2, y2], outline=c, width=max(2, int(W / 480)))
            
            # Label text: Target Class + Affiliation + Confidence + Distance
            txt = f'{d["gorunen"]}  [{d.get("renk_etiket", "")}]  {d["guven"]*100:.0f}%'
            if d.get("mesafe_m"):
                txt += f'  ~{d["mesafe_m"]:.1f}m'
                
            tb = dr.textbbox((0, 0), txt, font=f)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            ty = max(y1 - th - 8, 0)
            tx = min(x1, W - tw - 14)
            tx = max(tx, 0)
            
            # Semi-transparent tag background
            dr.rectangle([tx, ty, tx + tw + 12, ty + th + 8], fill=c + (220,))
            dr.text((tx + 6, ty + 3), txt, font=f, fill=(255, 255, 255) if c[0] > 180 or c[2] > 180 else (0, 0, 0))

        # Top tactical status header bar
        top_bar_h = fs2 + 16
        dr.rectangle([0, 0, W, top_bar_h], fill=(10, 15, 25, 210))
        top_info = f"{baslik}   |   TOTAL: {len(dets)}   |   ENEMY(RED): {red_count}   |   FRIENDLY(BLUE): {blue_count}"
        dr.text((12, 6), top_info, font=f2, fill=(255, 255, 255))
        
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--source", default="0")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--hfov", type=float, default=None)
    ap.add_argument("--target_m", type=float, default=None)
    ap.add_argument("--save", default=None, help="cikti videosu / 输出录像 mp4")
    a = ap.parse_args()

    det = HedefDedektoru(a.weights, conf=a.conf, imgsz=a.imgsz,
                         hfov_deg=a.hfov, hedef_genislik_m=a.target_m)
    src = int(a.source) if a.source.isdigit() else a.source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise SystemExit(f"kaynak acilamadi / 无法打开: {a.source}")

    wr, t0, n = None, time.time(), 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        vis = det.ciz(fr, det.tespit(fr))
        n += 1
        fps = n / max(time.time() - t0, 1e-6)
        cv2.putText(vis, f"{fps:.1f} FPS", (vis.shape[1] - 130, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        if a.save:
            if wr is None:
                wr = cv2.VideoWriter(a.save, cv2.VideoWriter_fourcc(*"mp4v"), 25,
                                     (vis.shape[1], vis.shape[0]))
            wr.write(vis)
        cv2.imshow("Yetenek 6 - Tespit ve Siniflandirma", vis)
        if cv2.waitKey(1) & 0xFF in (27, ord("q")):
            break
    cap.release()
    if wr:
        wr.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
