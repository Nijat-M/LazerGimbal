# -*- coding: utf-8 -*-
"""
目标检测器 (Target Detector)

职责（单一职责原则）：
- 接收 BGR 图像帧
- 检测目标（蓝色物体 / 红色激光点）
- 返回目标的位置信息

不包含：
- 控制逻辑
- 误差计算
- 死区判断
- 误差缩放
- 任何发送信号的代码
"""

import cv2
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass, field

from config.vision_config import VisionConfig


@dataclass
class DetectionResult:
    """
    单目标检测结果

    Attrs:
        detected : 是否检测到目标
        position : 目标中心坐标 (x, y)，未检测到时为 None
        radius   : 最小外接圆半径，未检测到时为 None
        area     : 轮廓面积，未检测到时为 None
    """
    detected: bool = False
    position: Optional[Tuple[int, int]] = None
    radius: Optional[float] = None
    area: Optional[float] = None


class TargetDetector:
    """
    目标检测器

    使用 HSV 颜色空间检测蓝色物体和红色激光点，
    所有颜色阈值均从 VisionConfig 读取，无硬编码。
    """

    def __init__(self):
        """初始化检测器，预建形态学核"""
        size = VisionConfig.MORPHOLOGY_KERNEL_SIZE
        self.kernel = np.ones((size, size), np.uint8)

    def detect_blue_object(self, frame: np.ndarray) -> DetectionResult:
        """
        检测蓝色物体

        Args:
            frame: BGR 格式图像帧

        Returns:
            DetectionResult: 蓝色物体的检测结果
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, VisionConfig.HSV_BLUE_LOWER, VisionConfig.HSV_BLUE_UPPER)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel)
        return self._find_largest_contour(mask, min_area=VisionConfig.MIN_CONTOUR_AREA)

    def detect_laser_and_blue(
        self, frame: np.ndarray
    ) -> Tuple[DetectionResult, DetectionResult]:
        """
        同时检测红色激光点和蓝色物体

        Args:
            frame: BGR 格式图像帧

        Returns:
            (laser_result, blue_result): 激光点和蓝色物体各自的检测结果
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 蓝色物体
        mask_blue = cv2.inRange(hsv, VisionConfig.HSV_BLUE_LOWER, VisionConfig.HSV_BLUE_UPPER)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_OPEN, self.kernel)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, self.kernel)

        # 红色激光点（红色在 HSV 色轮两端，需要两个范围）
        mask_red1 = cv2.inRange(hsv, VisionConfig.HSV_RED_LOWER1, VisionConfig.HSV_RED_UPPER1)
        mask_red2 = cv2.inRange(hsv, VisionConfig.HSV_RED_LOWER2, VisionConfig.HSV_RED_UPPER2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_OPEN, self.kernel)

        blue_result = self._find_largest_contour(mask_blue, min_area=100)
        laser_result = self._find_largest_contour(mask_red, min_area=5)  # 激光点很小

        return laser_result, blue_result

    def get_debug_mask(self, frame: np.ndarray) -> np.ndarray:
        """
        返回合并的调试蒙版（红+蓝合并，用于 UI 调试显示）

        Args:
            frame: BGR 格式图像帧

        Returns:
            单通道二值化蒙版
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        mask_blue = cv2.inRange(hsv, VisionConfig.HSV_BLUE_LOWER, VisionConfig.HSV_BLUE_UPPER)
        mask_red1 = cv2.inRange(hsv, VisionConfig.HSV_RED_LOWER1, VisionConfig.HSV_RED_UPPER1)
        mask_red2 = cv2.inRange(hsv, VisionConfig.HSV_RED_LOWER2, VisionConfig.HSV_RED_UPPER2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)

        return cv2.bitwise_or(mask_blue, mask_red)

    # --------------------------------------------------
    # 内部工具
    # --------------------------------------------------

    def _find_largest_contour(
        self, mask: np.ndarray, min_area: float
    ) -> DetectionResult:
        """
        在给定蒙版中找出最大轮廓并返回其中心

        Args:
            mask    : 单通道二值化蒙版
            min_area: 最小面积阈值（过滤噪点）

        Returns:
            DetectionResult
        """
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return DetectionResult(detected=False)

        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        if area < min_area:
            return DetectionResult(detected=False)

        (x, y), radius = cv2.minEnclosingCircle(largest)

        return DetectionResult(
            detected=True,
            position=(int(x), int(y)),
            radius=float(radius),
            area=float(area),
        )
