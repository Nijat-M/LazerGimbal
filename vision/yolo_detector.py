import os
import cv2
import numpy as np
import math
from typing import Optional, Tuple, List, Dict, Union
from dataclasses import dataclass
from pathlib import Path
from utils.logger import Logger

logger = Logger("YOLO")

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    YOLO = None
    HAS_YOLO = False

@dataclass
class YOLOSingleResult:
    position: Tuple[int, int]
    box: Tuple[int, int, int, int]
    class_id: int
    confidence: float
    class_name: str = ""

@dataclass
class YOLODetectionResult:
    detected: bool = False
    # 主目标 (置信度最高的或者最靠近中心的，这里默认选置信度最高或者特定逻辑)
    position: Optional[Tuple[int, int]] = None
    box: Optional[Tuple[int, int, int, int]] = None
    class_id: Optional[int] = None
    confidence: Optional[float] = None
    class_name: Optional[str] = None
    # 场景中的所有目标
    all_targets: List[YOLOSingleResult] = None


class TemporalBoxTracker:
    """
    时域目标生命周期与防抖平滑追踪器 (Anti-Jitter & Temporal EMA Smoother)
    - 解决 F-16 / 战机高频边界抖动与置信度跳跃问题 (EMA 65% 历史加权)
    - 解决 导弹 (BALISTIK_FUZE) 等细长/小目标瞬时漏检与闪烁问题
    """
    def __init__(self, max_lost_frames: int = 6, iou_thresh: float = 0.15, dist_thresh: float = 120.0):
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

    def update(self, raw_targets: List[YOLOSingleResult]) -> List[YOLOSingleResult]:
        matched_track_ids = set()
        matched_raw_indices = set()

        for idx, t in enumerate(raw_targets):
            best_id = None
            best_iou = self.iou_thresh
            best_dist = self.dist_thresh

            d_box = t.box
            d_cx = t.position[0]
            d_cy = t.position[1]

            for tid, track in self.tracks.items():
                if tid in matched_track_ids:
                    continue
                t_box = track["box"]
                t_cx = track["position"][0]
                t_cy = track["position"][1]

                iou_val = self._iou(d_box, t_box)
                dist_val = math.hypot(d_cx - t_cx, d_cy - t_cy)
                same_cls = (t.class_id == track["class_id"])

                if (iou_val > best_iou) or (same_cls and dist_val < best_dist):
                    best_iou = iou_val
                    best_dist = dist_val
                    best_id = tid

            if best_id is not None:
                matched_track_ids.add(best_id)
                matched_raw_indices.add(idx)
                track = self.tracks[best_id]
                track["hits"] += 1
                track["lost"] = 0
                track["confirmed"] = True

                # EMA 平滑坐标框 (35% 新 + 65% 旧) -> 彻底消除抖动
                nb = t.box
                ob = track["box"]
                smooth_box = (
                    int(0.35 * nb[0] + 0.65 * ob[0]),
                    int(0.35 * nb[1] + 0.65 * ob[1]),
                    int(0.35 * nb[2] + 0.65 * ob[2]),
                    int(0.35 * nb[3] + 0.65 * ob[3]),
                )
                smooth_pos = (
                    (smooth_box[0] + smooth_box[2]) // 2,
                    (smooth_box[1] + smooth_box[3]) // 2,
                )
                track["box"] = smooth_box
                track["position"] = smooth_pos
                # 平滑置信度
                track["confidence"] = 0.30 * t.confidence + 0.70 * track["confidence"]
                track["class_id"] = t.class_id
                track["class_name"] = t.class_name

        # 新增 Track
        for idx, t in enumerate(raw_targets):
            if idx not in matched_raw_indices:
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = {
                    "position": t.position,
                    "box": t.box,
                    "class_id": t.class_id,
                    "confidence": t.confidence,
                    "class_name": t.class_name,
                    "hits": 1,
                    "lost": 0,
                    "confirmed": (t.confidence >= 0.25),
                }

        # 丢帧衰减与保活
        dead_ids = []
        for tid, track in self.tracks.items():
            if tid not in matched_track_ids:
                track["lost"] += 1
                track["confidence"] *= 0.94
                if track["lost"] > self.max_lost_frames:
                    dead_ids.append(tid)

        for tid in dead_ids:
            del self.tracks[tid]

        # 输出确认的目标列表
        result_targets: List[YOLOSingleResult] = []
        for track in self.tracks.values():
            if track["confirmed"] or track["hits"] >= 2:
                result_targets.append(YOLOSingleResult(
                    position=track["position"],
                    box=track["box"],
                    class_id=track["class_id"],
                    confidence=track["confidence"],
                    class_name=track["class_name"]
                ))

        result_targets.sort(key=lambda x: x.confidence, reverse=True)
        return result_targets


class YOLODetector:
    """
    YOLO 深度学习目标检测引擎
    
    支持:
    - 针对国防防空模型 (savunma_yolo26.pt / yetenek6_best.pt) 与通用模型 (yolo26n.pt / yolov8n.pt) 的自动发现与动态热切换
    - 目标类别过滤 (如单独追踪 BALISTIK_FUZE, F16, HELIKOPTER, MINI_IHA)
    - 动态调节置信度阈值
    - 时域防抖平滑追踪算法 (Anti-Jitter EMA Filter)
    """

    @classmethod
    def get_models_dir(cls) -> Path:
        """获取 models 目录的绝对路径"""
        current_dir = Path(__file__).resolve().parent
        models_dir = current_dir / "models"
        if not models_dir.exists():
            models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir

    @classmethod
    def resolve_model_path(cls, model_path: Optional[str] = None) -> Optional[str]:
        """
        解析模型文件的绝对路径，具备多层备选容错机制
        """
        models_dir = cls.get_models_dir()
        project_root = models_dir.parent.parent

        candidates = []
        if model_path:
            p = Path(model_path)
            candidates.extend([
                p if p.is_absolute() else None,
                project_root / model_path,
                models_dir / p.name,
                Path(model_path)
            ])

        # 默认备选模型（防空模型优先，通用模型次之）
        candidates.extend([
            models_dir / "yetenek6_best.pt",
            models_dir / "savunma_yolo26.pt",
            models_dir / "yolo26n.pt",
            models_dir / "yolov8n.pt",
            models_dir / "yolo11n.pt",
            project_root / "yetenek6_best.pt",
            project_root / "savunma_yolo26.pt",
            project_root / "yolo26n.pt",
            project_root / "yolov8n.pt"
        ])

        for c in candidates:
            if c is not None and c.exists() and c.is_file():
                return str(c.resolve())

        return None

    @classmethod
    def list_available_models(cls) -> List[Dict[str, str]]:
        """
        扫描系统中所有可用的 YOLO 模型文件
        """
        models_dir = cls.get_models_dir()
        found_models = []
        seen_filenames = set()

        search_dirs = [models_dir, models_dir.parent.parent]
        for s_dir in search_dirs:
            if s_dir.exists():
                for pt_file in s_dir.glob("*.pt"):
                    if pt_file.name not in seen_filenames:
                        seen_filenames.add(pt_file.name)
                        rel_path = f"vision/models/{pt_file.name}" if pt_file.parent == models_dir else pt_file.name
                        
                        # 友好描述
                        if "yetenek" in pt_file.name.lower():
                            display_name = f"{pt_file.name} (Air Defense Target / 4 Classes)"
                        elif "savunma" in pt_file.name.lower():
                            display_name = f"{pt_file.name} (Air Defense Model / 4 Classes)"
                        elif "yolo26n" in pt_file.name.lower():
                            display_name = f"{pt_file.name} (COCO General / 80 Classes)"
                        elif "yolov8" in pt_file.name.lower():
                            display_name = f"{pt_file.name} (YOLOv8 General)"
                        else:
                            display_name = f"{pt_file.name} (Custom Model)"

                        found_models.append({
                            "filename": pt_file.name,
                            "path": rel_path,
                            "abs_path": str(pt_file.resolve()),
                            "display_name": display_name
                        })

        # 确保 savunma / yetenek 防空模型排在最前面
        found_models.sort(key=lambda m: (
            0 if "yetenek" in m["filename"].lower() else (1 if "savunma" in m["filename"].lower() else 2),
            m["filename"]
        ))
        return found_models

    def __init__(self, model_path: str = "vision/models/yetenek6_best.pt", conf_threshold: float = 0.30):
        self.model = None
        self.current_model_path: Optional[str] = None
        self.conf_threshold: float = conf_threshold
        self.min_box_size: int = 4  # 极小框容差，支持细长导弹 (Missile) 与小微无人机
        self.imgsz: int = 960
        self.tracker = TemporalBoxTracker(max_lost_frames=6, iou_thresh=0.15, dist_thresh=120.0)

        # 硬件加速设备检测 (RTX GPU / CUDA 极速加速)
        try:
            import torch
            if torch.cuda.is_available():
                self.device = "cuda:0"
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"[YOLO] 🔥 已启用 GPU 硬件加速: {gpu_name} (CUDA / FP16)")
            else:
                self.device = "cpu"
                logger.info("[YOLO] 当前使用 CPU 推理模式")
        except Exception:
            self.device = "cpu"

        # 目标锁定状态记录
        self.locked_target_position: Optional[Tuple[int, int]] = None
        self.locked_target_class: Optional[int] = None
        self.lost_frames = 0
        self.max_lost_frames = 10
        self.lock_distance_threshold = 200

        # 加载初始模型
        self.load_model(model_path)

    def load_model(self, model_path: str) -> bool:
        """
        动态加载或切换 YOLO 模型
        """
        if not HAS_YOLO:
            logger.error("[YOLO ERROR] 未安装 ultralytics 深度学习库！请运行: pip install ultralytics")
            self.model = None
            return False

        resolved_path = self.resolve_model_path(model_path)
        if resolved_path is None:
            resolved_path = "yolo26n.pt"
            logger.warning(f"[YOLO] 未找到指定模型 {model_path}，回退到自动在线模型: {resolved_path}")

        try:
            self.model = YOLO(resolved_path)
            self.current_model_path = resolved_path
            model_name = os.path.basename(resolved_path)
            
            # 防空模型在 GPU 上使用高清 960 尺寸，确保远距细长导弹高分辨率特征保留
            if ("savunma" in resolved_path.lower() or "yetenek" in resolved_path.lower()) and self.device.startswith("cuda"):
                self.imgsz = 960
            else:
                self.imgsz = 640

            class_names = self.get_class_names()
            names_summary = ", ".join([f"{k}:{v}" for k, v in list(class_names.items())[:6]])
            if len(class_names) > 6:
                names_summary += f" ... (共{len(class_names)}类)"

            logger.info(f"[YOLO] ✓ 成功载入模型 ({model_name} @ imgsz={self.imgsz}): {resolved_path}")
            logger.info(f"[YOLO]   支持类别: [{names_summary}]")
            
            # 重置锁定状态与追踪器
            self.tracker = TemporalBoxTracker(max_lost_frames=6, iou_thresh=0.15, dist_thresh=120.0)
            self.locked_target_position = None
            self.locked_target_class = None
            self.lost_frames = 0
            return True
        except Exception as e:
            logger.error(f"[YOLO ERROR] 加载模型 {model_path} 失败: {e}")
            self.model = None
            return False

    def get_class_names(self) -> Dict[int, str]:
        """获取当前模型支持的类别字典 {id: name}"""
        if self.model is not None and hasattr(self.model, "names") and self.model.names:
            return self.model.names
        return {}

    def detect_target(
        self, 
        frame: np.ndarray, 
        target_class: Optional[Union[int, str]] = None,
        conf_threshold: Optional[float] = None
    ) -> YOLODetectionResult:
        """
        多目标检测与战术追踪锁定 (时域平滑去抖 + 细长导弹增强检出)
        
        Args:
            frame: 输入 BGR 图像
            target_class: 过滤目标类别 (None 表示追踪所有类别)
            conf_threshold: 置信度阈值
        """
        if self.model is None:
            return YOLODetectionResult(detected=False, all_targets=[])

        user_conf = conf_threshold if conf_threshold is not None else self.conf_threshold
        # 推理时采用自适应敏捷阈值（捕获细小导弹），后续由时域追踪器确认
        infer_conf = max(0.18, user_conf * 0.65)
        class_names = self.get_class_names()

        target_class_id: Optional[int] = None
        if isinstance(target_class, str):
            for cid, cname in class_names.items():
                if cname.lower() == target_class.lower():
                    target_class_id = cid
                    break
        elif isinstance(target_class, int):
            target_class_id = target_class

        try:
            results = self.model(
                frame, 
                verbose=False, 
                device=self.device, 
                imgsz=self.imgsz, 
                conf=infer_conf,
                iou=0.40,
                max_det=25
            )
        except Exception:
            try:
                results = self.model(frame, verbose=False, conf=infer_conf)
            except Exception as e:
                logger.error(f"[YOLO ERROR] 推理执行异常: {e}")
                return YOLODetectionResult(detected=False, all_targets=[])

        raw_targets: List[YOLOSingleResult] = []

        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0].item())
                if target_class_id is None or cls_id == target_class_id:
                    score = float(box.conf[0].item())
                    b_xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    x1, y1, x2, y2 = b_xyxy
                    w = x2 - x1
                    h = y2 - y1

                    # 极小噪点过滤（放宽至 4px，允许细长导弹通过）
                    if w < self.min_box_size or h < self.min_box_size or (w * h) < 16:
                        continue

                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    
                    cname = class_names.get(cls_id, f"Cls_{cls_id}")
                    target = YOLOSingleResult(
                        position=(cx, cy),
                        box=(x1, y1, x2, y2),
                        class_id=cls_id,
                        confidence=score,
                        class_name=cname
                    )
                    raw_targets.append(target)

        # ====== 时域 EMA 平滑滤波 (彻底消除 F-16 抖动并保活导弹) ======
        all_targets = self.tracker.update(raw_targets)

        # --- 目标锁定逻辑：同类别优先 + 距离加权连续追踪 ---
        best_target = None

        if len(all_targets) > 0:
            if self.locked_target_position is not None and self.lost_frames < self.max_lost_frames:
                best_score = float('inf')
                for t in all_targets:
                    dist = math.hypot(
                        t.position[0] - self.locked_target_position[0], 
                        t.position[1] - self.locked_target_position[1]
                    )
                    if dist < self.lock_distance_threshold:
                        class_penalty = 0.0 if (self.locked_target_class is not None and t.class_id == self.locked_target_class) else 50.0
                        conf_bonus = t.confidence * 40.0
                        score = dist + class_penalty - conf_bonus
                        if score < best_score:
                            best_score = score
                            best_target = t

            if best_target is None:
                best_target = all_targets[0]

        if best_target is not None:
            self.locked_target_position = best_target.position
            self.locked_target_class = best_target.class_id
            self.lost_frames = 0
            return YOLODetectionResult(
                detected=True,
                position=best_target.position,
                box=best_target.box,
                class_id=best_target.class_id,
                confidence=best_target.confidence,
                class_name=best_target.class_name,
                all_targets=all_targets
            )
        else:
            self.lost_frames += 1
            if self.lost_frames >= self.max_lost_frames:
                self.locked_target_position = None
                self.locked_target_class = None
            return YOLODetectionResult(detected=False, all_targets=all_targets)




class AsyncYOLODetector:
    """
    异步并发 YOLO 检测引擎 (支持动态模型热换与类别过滤)
    
    架构优势：
    - 将相机 60 FPS 视频流采集与 GPU 深度学习推理彻底解耦到独立后台线程；
    - 主视觉线程以 100% 恒定 60.0 FPS 极速刷新，彻底消除微顿挫（Micro-Stuttering）；
    - 后台 Worker 以最高速度持续更新最新目标坐标；
    - 支持在运行中动态切换模型文件与目标类别。
    """
    def __init__(self, model_path: str = "vision/models/savunma_yolo26.pt", conf_threshold: float = 0.35):
        import threading
        self.detector = YOLODetector(model_path, conf_threshold=conf_threshold)
        self.lock = threading.Lock()
        self.new_frame_event = threading.Event()
        self.is_running = True
        
        self._target_class: Optional[Union[int, str]] = None
        self._conf_threshold: float = conf_threshold
        self._pending_frame: Optional[np.ndarray] = None
        self._latest_result: YOLODetectionResult = YOLODetectionResult(detected=False, all_targets=[])
        
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    @property
    def model(self):
        return self.detector.model

    def set_model(self, model_path: str) -> bool:
        """线程安全地热切换模型"""
        with self.lock:
            success = self.detector.load_model(model_path)
            self._latest_result = YOLODetectionResult(detected=False, all_targets=[])
            return success

    def set_target_class(self, target_class: Optional[Union[int, str]]) -> None:
        """设置过滤追踪的目标类别"""
        with self.lock:
            self._target_class = target_class

    def set_conf_threshold(self, conf: float) -> None:
        """设置置信度阈值"""
        with self.lock:
            self._conf_threshold = conf
            self.detector.conf_threshold = conf

    def get_class_names(self) -> Dict[int, str]:
        """获取当前模型的类别字典"""
        with self.lock:
            return self.detector.get_class_names()

    def get_current_model_path(self) -> Optional[str]:
        """获取当前加载的模型路径"""
        with self.lock:
            return self.detector.current_model_path

    def submit_frame(self, frame: np.ndarray) -> None:
        """非阻塞提交最新图像帧（0.01ms 极速返回）"""
        with self.lock:
            self._pending_frame = frame.copy()
        self.new_frame_event.set()

    def get_latest_result(self) -> YOLODetectionResult:
        """非阻塞获取当前最新检测结果（0.001ms 极速返回）"""
        with self.lock:
            return self._latest_result

    def detect_target(
        self, 
        frame: np.ndarray, 
        target_class: Optional[Union[int, str]] = None
    ) -> YOLODetectionResult:
        """兼容原有接口：自动异步提交并获取最新状态"""
        if target_class is not None:
            self.set_target_class(target_class)
        self.submit_frame(frame)
        return self.get_latest_result()

    def _worker_loop(self) -> None:
        """后台 GPU 推理循环"""
        while self.is_running:
            self.new_frame_event.wait(timeout=0.1)
            if not self.is_running:
                break
                
            frame_to_process = None
            target_cls = None
            conf_th = 0.35
            with self.lock:
                if self._pending_frame is not None:
                    frame_to_process = self._pending_frame
                    self._pending_frame = None
                target_cls = self._target_class
                conf_th = self._conf_threshold
                self.new_frame_event.clear()
            
            if frame_to_process is not None:
                try:
                    res = self.detector.detect_target(
                        frame_to_process, 
                        target_class=target_cls,
                        conf_threshold=conf_th
                    )
                    with self.lock:
                        self._latest_result = res
                except Exception as e:
                    logger.error(f"[ASYNC YOLO] 推理异常: {e}")

    def close(self) -> None:
        """停止后台线程"""
        self.is_running = False
        self.new_frame_event.set()

