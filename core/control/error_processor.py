# -*- coding: utf-8 -*-
"""
误差处理器 (Error Processor)

职责（单一职责原则）：
1. 接收原始视觉误差
2. 自适应缩放（降低灵敏度）
3. 移动平均滤波（减少噪声抖动）
4. 提供处理后的误差给控制器使用

不包含：
- 死区处理（由 GimbalController 统一处理）
- 控制指令发送
- 任何UI相关逻辑
"""

from typing import Tuple
from collections import deque
from config.control_config import ControlConfig


class ErrorProcessor:
    """
    误差处理器

    功能：
    - 自适应误差缩放（远距离降低灵敏度）
    - 移动平均滤波（平滑误差信号）
    """

    def __init__(self, filter_length: int = None):
        """
        初始化误差处理器

        Args:
            filter_length: 滤波器长度（帧数），None 则使用配置值
        """
        self.filter_length: int = filter_length or ControlConfig.ERROR_FILTER_LENGTH

        # 使用 deque 实现移动窗口（自动丢弃旧数据）
        self.history_x: deque = deque(maxlen=self.filter_length)
        self.history_y: deque = deque(maxlen=self.filter_length)

        # 初始化历史为0，避免启动时滤波输出偏大
        for _ in range(self.filter_length):
            self.history_x.append(0)
            self.history_y.append(0)

    def process(self, raw_x: int, raw_y: int) -> Tuple[int, int]:
        """
        处理原始误差

        工作流程：
        1. 计算误差大小（欧几里得距离）
        2. 自适应缩放（从 ControlConfig 读取参数）
        3. 移动平均滤波

        Args:
            raw_x: 原始X轴误差（像素）
            raw_y: 原始Y轴误差（像素）

        Returns:
            (processed_x, processed_y): 处理后的误差（像素）
        """
        # 1. 计算误差大小
        magnitude = self.get_magnitude(raw_x, raw_y)

        # 2. 自适应缩放（参数统一从 ControlConfig 读取）
        scale = ControlConfig.get_scale_for_error(magnitude)
        scaled_x = int(raw_x * scale)
        scaled_y = int(raw_y * scale)

        # 3. 移动平均滤波
        self.history_x.append(scaled_x)
        self.history_y.append(scaled_y)

        filtered_x = sum(self.history_x) // self.filter_length
        filtered_y = sum(self.history_y) // self.filter_length

        return filtered_x, filtered_y

    def reset(self) -> None:
        """重置滤波器历史（模式切换或重新连接时调用）"""
        self.history_x.clear()
        self.history_y.clear()
        for _ in range(self.filter_length):
            self.history_x.append(0)
            self.history_y.append(0)

    @staticmethod
    def get_magnitude(error_x: int, error_y: int) -> float:
        """计算误差的欧几里得距离（像素）"""
        return (error_x ** 2 + error_y ** 2) ** 0.5
