from ultralytics import YOLO
import cv2
import numpy as np
import math
from typing import Optional, Tuple, List
from dataclasses import dataclass

@dataclass
class YOLOSingleResult:
    position: Tuple[int, int]
    box: Tuple[int, int, int, int]
    class_id: int
    confidence: float

@dataclass
class YOLODetectionResult:
    detected: bool = False
    # 主目标 (置信度最高的或者最靠近中心的，这里默认选置信度最高或者特定逻辑)
    position: Optional[Tuple[int, int]] = None
    box: Optional[Tuple[int, int, int, int]] = None
    class_id: Optional[int] = None
    confidence: Optional[float] = None
    # 场景中的所有目标
    all_targets: List[YOLOSingleResult] = None


class YOLODetector:
    def __init__(self, model_path="vision/models/yolo26n.pt"):
        self.model = YOLO(model_path)
        # 目标锁定状态记录
        self.locked_target_position: Optional[Tuple[int, int]] = None
        self.lost_frames = 0
        self.max_lost_frames = 10  # 丢失多少帧后认为目标彻底丢失，重新寻找全局最优
        self.lock_distance_threshold = 150  # 锁定追踪的最大跳变距离 (像素)
        
    def detect_target(self, frame: np.ndarray, target_class=None) -> YOLODetectionResult:
        """
        Detects multiple targets. Returns all targets and selects one main target for tracking.
        改进：优先选择距离上一帧被锁定目标最近的候选者，防止追踪目标在不同人/物体间横跳。
        """
        results = self.model(frame, verbose=False)
        
        all_targets = []
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls_id = int(box.cls[0].item())
                if target_class is None or cls_id == target_class:
                    conf = box.conf[0].item()
                    b_xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    x1, y1, x2, y2 = b_xyxy
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    
                    target = YOLOSingleResult(
                        position=(cx, cy),
                        box=(x1, y1, x2, y2),
                        class_id=cls_id,
                        confidence=conf
                    )
                    all_targets.append(target)
                    
        # --- 工业级目标锁定逻辑：中心距最近优先 ---
        best_target = None
        
        if len(all_targets) > 0:
            if self.locked_target_position is not None and self.lost_frames < self.max_lost_frames:
                # 寻找距离上一帧锁定目标最近的候选者
                min_dist = float('inf')
                for t in all_targets:
                    # 计算欧氏距离
                    dist = math.hypot(t.position[0] - self.locked_target_position[0], 
                                      t.position[1] - self.locked_target_position[1])
                    if dist < min_dist and dist < self.lock_distance_threshold:
                        min_dist = dist
                        best_target = t
            
            # 如果没找到附近的目标，或者之前没有锁定过目标，则回退到"最高置信度"作为新目标
            if best_target is None:
                best_conf = 0.0
                for t in all_targets:
                    if t.confidence > best_conf:
                        best_conf = t.confidence
                        best_target = t

        # 更新锁定的目标状态
        if best_target is not None:
            self.locked_target_position = best_target.position
            self.lost_frames = 0
            return YOLODetectionResult(
                detected=True,
                position=best_target.position,
                box=best_target.box,
                class_id=best_target.class_id,
                confidence=best_target.confidence,
                all_targets=all_targets
            )
        else:
            self.lost_frames += 1
            return YOLODetectionResult(detected=False, all_targets=all_targets)
