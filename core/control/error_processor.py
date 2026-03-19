# -*- coding: utf-8 -*-
"""
误差处理器 (Error Processor)

职责（单一职责原则）：
1. 接收原始视觉误差
2. 执行基础的限幅与异常值拦截（防止剧烈抖动导致云台瞬间疯转）
3. 提供处理后的纯净误差给控制器使用

[优化]
- 移除了拖后腿的移动平均滤波（deque），确保 0 帧滞后，将抗抖动任务完全交给新版 YOLO26 的 NMS-Free 与后续卡尔曼滤波。
"""

from typing import Tuple

class ErrorProcessor:
    """
    零延迟误差处理器
    """

    def __init__(self, max_pixel_jump: int = 300):
        """
        初始化误差处理器

        Args:
            max_pixel_jump: 允许的单帧最大像素跳变（防异常框）
        """
        self.max_pixel_jump = max_pixel_jump
        self.last_x = 0
        self.last_y = 0

    def process(self, raw_x: int, raw_y: int) -> Tuple[int, int]:
        """
        处理原始误差（零延迟直通 + 异常突变拦截）
        
        Args:
            raw_x: 原始X轴误差（像素）
            raw_y: 原始Y轴误差（像素）
            
        Returns:
            (processed_x, processed_y): 处理后的误差（像素）
        """
        # 突变拦截逻辑：如果两帧之间目标误差瞬间跳变极大（比如YOLO出Bug闪了一下）
        # 则强制限制最大跳变步长，防止微分项(Kd)瞬间爆炸
        if abs(raw_x - self.last_x) > self.max_pixel_jump:
            raw_x = self.last_x + (self.max_pixel_jump if raw_x > self.last_x else -self.max_pixel_jump)
            
        if abs(raw_y - self.last_y) > self.max_pixel_jump:
            raw_y = self.last_y + (self.max_pixel_jump if raw_y > self.last_y else -self.max_pixel_jump)

        self.last_x = raw_x
        self.last_y = raw_y

        return raw_x, raw_y

    def reset(self) -> None:
        """重置状态（模式切换或重新连接时调用）"""
        self.last_x = 0
        self.last_y = 0

    @staticmethod
    def get_magnitude(error_x: int, error_y: int) -> float:
        """计算误差的欧几里得距离（像素）"""
        return (error_x ** 2 + error_y ** 2) ** 0.5
