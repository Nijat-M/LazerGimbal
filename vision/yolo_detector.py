from ultralytics import YOLO
import cv2
import numpy as np
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
    def __init__(self, model_path="vision/models/yolov8n.pt"):
        self.model = YOLO(model_path)
        
    def detect_target(self, frame: np.ndarray, target_class=None) -> YOLODetectionResult:
        """
        Detects multiple targets. Returns all targets and selects one main target (highest confidence) for tracking.
        """
        results = self.model(frame, verbose=False)
        
        best_conf = 0
        best_target = None
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
                    
                    # 也可以在这里改成计算“离画面中心最近”的作为 best_target
                    if conf > best_conf:
                        best_conf = conf
                        best_target = target
                        
        if best_target is not None:
            return YOLODetectionResult(
                detected=True,
                position=best_target.position,
                box=best_target.box,
                class_id=best_target.class_id,
                confidence=best_target.confidence,
                all_targets=all_targets
            )
            
        return YOLODetectionResult(detected=False, all_targets=[])
