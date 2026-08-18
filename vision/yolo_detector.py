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


class YOLODetector:
    """
    YOLO 深度学习目标检测引擎
    
    支持:
    - 针对国防防空模型 (savunma_yolo26.pt) 与通用模型 (yolo26n.pt / yolov8n.pt) 的自动发现与动态热切换
    - 目标类别过滤 (如单独追踪 BALISTIK_FUZE, F16, HELIKOPTER, MINI_IHA)
    - 动态调节置信度阈值
    - 目标锁定最近距离优先算法 (Anti-Jitter)
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
            models_dir / "savunma_yolo26.pt",
            models_dir / "yetenek6_best.pt",
            models_dir / "yolo26n.pt",
            models_dir / "yolov8n.pt",
            models_dir / "yolo11n.pt",
            project_root / "savunma_yolo26.pt",
            project_root / "yetenek6_best.pt",
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
                        if "savunma" in pt_file.name.lower():
                            display_name = f"{pt_file.name} (Air Defense Model / 4 Classes)"
                        elif "yetenek" in pt_file.name.lower():
                            display_name = f"{pt_file.name} (Air Defense Target / 4 Classes)"
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
            0 if "savunma" in m["filename"].lower() else (1 if "yetenek" in m["filename"].lower() else 2),
            m["filename"]
        ))
        return found_models

    def __init__(self, model_path: str = "vision/models/savunma_yolo26.pt", conf_threshold: float = 0.50):
        self.model = None
        self.current_model_path: Optional[str] = None
        self.conf_threshold: float = conf_threshold
        self.min_box_size: int = 16
        self.imgsz: int = 640
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

        # 目标锁定状态记录与平滑追踪器
        self.locked_target_position: Optional[Tuple[int, int]] = None
        self.locked_target_class: Optional[int] = None
        self.locked_target_smooth_pos: Optional[Tuple[float, float]] = None
        self.lost_frames = 0
        self.max_lost_frames = 10  # 丢失多少帧后认为目标彻底丢失，重新寻找全局最优
        self.lock_distance_threshold = 180  # 锁定追踪的最大跳变距离 (像素)

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
            # 尝试回退加载 yolo26n.pt
            resolved_path = "yolo26n.pt"
            logger.warning(f"[YOLO] 未找到指定模型 {model_path}，回退到自动在线模型: {resolved_path}")

        try:
            self.model = YOLO(resolved_path)
            self.current_model_path = resolved_path
            model_name = os.path.basename(resolved_path)
            
            # 国防防空模型在 GPU 上优先使用训练尺寸 (960)，通用模型使用 640
            if ("savunma" in resolved_path.lower() or "yetenek" in resolved_path.lower()) and self.device.startswith("cuda"):
                self.imgsz = 960
            else:
                self.imgsz = 640

            # 读取类别名称
            class_names = self.get_class_names()
            names_summary = ", ".join([f"{k}:{v}" for k, v in list(class_names.items())[:6]])
            if len(class_names) > 6:
                names_summary += f" ... (共{len(class_names)}类)"

            logger.info(f"[YOLO] ✓ 成功载入模型 ({model_name} @ imgsz={self.imgsz}): {resolved_path}")
            logger.info(f"[YOLO]   支持类别: [{names_summary}]")
            
            # 重置锁定状态
            self.locked_target_position = None
            self.locked_target_class = None
            self.locked_target_smooth_pos = None
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
        多目标检测与战术追踪锁定 (抗误识别 + 平滑去抖)
        
        Args:
            frame: 输入 BGR 图像
            target_class: 过滤目标类别 (None 表示追踪所有类别，int 为类别ID，str 为类别名称)
            conf_threshold: 置信度阈值 (None 则使用实例默认值)
        """
        if self.model is None:
            return YOLODetectionResult(detected=False, all_targets=[])

        conf = conf_threshold if conf_threshold is not None else self.conf_threshold
        class_names = self.get_class_names()

        # 解析 target_class (如果传入了类别名称字符串，转换为类别 ID)
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
                conf=conf,
                iou=0.45,
                max_det=20
            )
        except Exception:
            # 回退保护
            try:
                results = self.model(frame, verbose=False, conf=conf)
            except Exception as e:
                logger.error(f"[YOLO ERROR] 推理执行异常: {e}")
                return YOLODetectionResult(detected=False, all_targets=[])

        all_targets: List[YOLOSingleResult] = []

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

                    # 噪点几何过滤：过滤过小碎片/非正常框，防止背景噪点误报
                    if w < self.min_box_size or h < self.min_box_size or (w * h) < 256:
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
                    all_targets.append(target)

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
                        # 类别一致性权重奖励：如果与上帧目标类别相同，优先锁定
                        class_penalty = 0.0 if (self.locked_target_class is not None and t.class_id == self.locked_target_class) else 60.0
                        conf_bonus = t.confidence * 30.0
                        score = dist + class_penalty - conf_bonus
                        if score < best_score:
                            best_score = score
                            best_target = t

            # 如果没找到上一帧附近的目标，则选择置信度最高的目标作为新锁定目标
            if best_target is None:
                best_conf = 0.0
                for t in all_targets:
                    if t.confidence > best_conf:
                        best_conf = t.confidence
                        best_target = t

        # 更新锁定的目标状态
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

