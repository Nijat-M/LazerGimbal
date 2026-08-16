# -*- coding: utf-8 -*-
"""
误差处理器 (Error Processor) - 动态超前预测与零滞后去抖

职责：
1. 异常突变滤波（防超大跳变破坏云台）
2. 动态自适应速度超前补偿 (Lead Anticipation):
   - 当目标高速运动或迅速逼近准星时，自动补偿视觉回路约 40~50ms 固有延迟，实现零超调提前制动！
   - 彻底消除因视觉滞后引发的“起步迟钝、冲过目标、来回摆动”现象。
"""

import time
import math
from typing import Tuple, Optional


class ErrorProcessor:
    """
    零滞后动态超前预测误差处理器
    """

    def __init__(self, max_pixel_jump: int = 350, max_pixel_jump_y: int = 120):
        self.max_pixel_jump_x = max_pixel_jump
        self.max_pixel_jump_y = max_pixel_jump_y
        self.last_x: Optional[float] = None
        self.last_y: Optional[float] = None
        self.last_time: float = 0.0
        self.vel_x: float = 0.0
        self.vel_y: float = 0.0
        self.lead_time: float = 0.045  # 45ms 视觉管线固有延迟超前补偿

    def process(self, raw_x: int, raw_y: int) -> Tuple[int, int]:
        """
        处理原始误差（突变拦截 + 动态速度超前预测）
        
        Args:
            raw_x: 原始X轴误差（像素）
            raw_y: 原始Y轴误差（像素）
            
        Returns:
            (processed_x, processed_y): 处理后的误差（像素）
        """
        now = time.monotonic()
        
        if self.last_x is None or self.last_y is None:
            self.last_x = float(raw_x)
            self.last_y = float(raw_y)
            self.last_time = now
            self.vel_x = 0.0
            self.vel_y = 0.0
            return raw_x, raw_y

        dt = now - self.last_time
        if dt <= 0.001:
            dt = 0.016  # 默认 60 FPS 间隔

        # 1. 突变拦截
        fx = float(raw_x)
        fy = float(raw_y)
        if abs(fx - self.last_x) > self.max_pixel_jump_x:
            fx = self.last_x + (self.max_pixel_jump_x if fx > self.last_x else -self.max_pixel_jump_x)
        if abs(fy - self.last_y) > self.max_pixel_jump_y:
            fy = self.last_y + (self.max_pixel_jump_y if fy > self.last_y else -self.max_pixel_jump_y)

        # 2. 估计目标相对误差变化速率 (px/s)
        diff_x = fx - self.last_x
        diff_y = fy - self.last_y

        # 【核心：果冻效应消除门限】
        # 摄像头传感器与检测框微小离散抖动 (< 1.2px) 直接判定为静止，切断高频导数噪声
        inst_vel_x = (diff_x / dt) if abs(diff_x) >= 1.2 else 0.0
        inst_vel_y = (diff_y / dt) if abs(diff_y) >= 1.2 else 0.0

        # 对速度估计进行低通滤波（Y轴加重滤波，彻底消除俯仰高频微震与果冻效应）
        self.vel_x = 0.55 * inst_vel_x + 0.45 * self.vel_x
        self.vel_y = 0.35 * inst_vel_y + 0.65 * self.vel_y

        self.last_x = fx
        self.last_y = fy
        self.last_time = now

        # 3. 非对称动态超前预测 (Asymmetric Lead Braking Compensator):
        # - 当目标快速冲向准星中心 (fx 与 vel_x 异号): 属于急刹阶段，加大超前时间 (65ms) 提前减速，彻底消除远距离大速度过冲与回摆！
        # - 当目标加速远离准星 (fx 与 vel_x 同号): 属于追击阶段，使用 35ms 超前时间，极速跟手不迟钝！
        if fx * self.vel_x < 0:
            lead_time_x = 0.065  # 远距离逼近强效提前刹车 (65ms)
        else:
            lead_time_x = 0.035  # 加速追击零延迟跟手 (35ms)

        if fy * self.vel_y < 0:
            lead_time_y = 0.055
        else:
            lead_time_y = 0.025  # Y 轴小范围柔和响应，杜绝果冻

        pred_x = fx + lead_time_x * self.vel_x
        pred_y = fy + lead_time_y * self.vel_y

        # 如果跨越了 0 点（意味着已完美制动到达中心），避免符号反转产生抖动
        if fx * pred_x < 0:
            pred_x = 0.0
        if fy * pred_y < 0:
            pred_y = 0.0

        return int(round(pred_x)), int(round(pred_y))


    def reset(self) -> None:
        """重置状态（模式切换或重新连接时调用）"""
        self.last_x = None
        self.last_y = None
        self.last_time = 0.0
        self.vel_x = 0.0
        self.vel_y = 0.0

    @staticmethod
    def get_magnitude(error_x: int, error_y: int) -> float:
        """计算误差的欧几里得距离（像素）"""
        return (error_x ** 2 + error_y ** 2) ** 0.5


