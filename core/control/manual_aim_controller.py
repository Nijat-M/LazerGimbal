# -*- coding: utf-8 -*-
"""
FPS 风格鼠标手动瞄准控制器 (FPS Manual Mouse Aim Controller)
================================================================================
本模块实现将高频 Windows 鼠标相对位移事件平滑映射为云台虚实姿态角的算法核心。

【核心设计原理 (Core Design Mechanics)】
1. 异步生产者-消费者模型 (Producer-Consumer Decoupling):
   - 生产者 (GUI 线程): 响应 Windows 鼠标事件 (高达 1000Hz 轮询)，通过 add_mouse_delta
     快速累加位移到增量缓冲区 (_pending_yaw_delta)，绝对不在 UI 线程发起网络或串口通信；
   - 消费者 (控制线程): 以稳定的 60Hz 采样周期，通过 consume_angle_delta 按批量、带限幅地
     抽取并发送至 STM32 下位机，彻底避免串口阻塞和指令积压。
2. 软限位与边界钳位 (Software Angular Limits):
   - 实时根据 ControlConfig 设定的物理安全行程 (Yaw/Pitch Limits) 限制虚拟准星，
     防止由于鼠标大幅度拖拽导致云台线缆缠绕或机械结构碰撞。
3. 容错与同步回滚机制 (Synchronized Rollback):
   - 在串口异常断开或紧急制动时，通过 discard_pending 将累积未发出的增量从虚拟姿态中回滚，
     确保虚拟十字准星与物理云台的当前实际姿态绝对同步。
================================================================================
"""

from __future__ import annotations

import threading


class ManualAimController:
    """
    线程安全的 FPS 风格鼠标瞄准状态管理器
    """

    def __init__(
        self,
        sensitivity: float,
        yaw_limits: tuple[float, float],
        pitch_limits: tuple[float, float],
    ) -> None:
        """
        初始化鼠标手动瞄准控制器

        Args:
            sensitivity: 鼠标灵敏度 (每个鼠标位移像素所代表的旋转度数 deg/px)
            yaw_limits: 水平偏航轴角度软限位区间 (min_yaw_deg, max_yaw_deg)
            pitch_limits: 垂直俯仰轴角度软限位区间 (min_pitch_deg, max_pitch_deg)
        """
        self._lock = threading.Lock()
        self._sensitivity = sensitivity
        self._yaw_limits = yaw_limits
        self._pitch_limits = pitch_limits
        
        # 当前瞄准空间绝对虚拟角度 (单位: 度)
        self._target_yaw = 0.0
        self._target_pitch = 0.0
        
        # 累积待发送给下位机的未消费角位移增量 (单位: 度)
        self._pending_yaw_delta = 0.0
        self._pending_pitch_delta = 0.0

    def set_sensitivity(self, sensitivity: float) -> None:
        """动态设置鼠标灵敏度系数"""
        if sensitivity <= 0:
            raise ValueError("Mouse sensitivity must be positive")
        with self._lock:
            self._sensitivity = sensitivity

    def get_sensitivity(self) -> float:
        """获取当前设置的鼠标灵敏度系数"""
        with self._lock:
            return self._sensitivity

    def add_mouse_delta(self, dx: int, dy: int) -> tuple[float, float]:
        """
        处理高频鼠标相对位移事件（由 GUI 控件在捕获模式下高速调用）

        Args:
            dx: 鼠标 X 轴像素位移（向右为正）
            dy: 鼠标 Y 轴像素位移（向下为正）

        Returns:
            tuple[float, float]: 钳位限幅后的最新目标绝对角度 (target_yaw, target_pitch)
        """
        with self._lock:
            # 鼠标向右推 -> Yaw 向右转增加；鼠标向上推 (dy<0) -> Pitch 抬头增加
            requested_yaw = self._target_yaw + dx * self._sensitivity
            requested_pitch = self._target_pitch - dy * self._sensitivity

            new_yaw = self._clamp(requested_yaw, self._yaw_limits)
            new_pitch = self._clamp(requested_pitch, self._pitch_limits)

            # 仅累加在有效行程范围内的增量
            self._pending_yaw_delta += new_yaw - self._target_yaw
            self._pending_pitch_delta += new_pitch - self._target_pitch
            self._target_yaw = new_yaw
            self._target_pitch = new_pitch
            return self._target_yaw, self._target_pitch

    def consume_angle_delta(
        self,
        max_abs_delta: float,
        min_abs_delta: float,
    ) -> tuple[float, float]:
        """
        以定频控制周期按配额消费累积角位移增量

        设计考量:
            1. 限幅抑制 (max_abs_delta): 避免因鼠标瞬间剧烈晃动导致云台瞬间以破坏性加速度飞车；
            2. 死区抑制 (min_abs_delta): 过滤手部微颤引起的亚像素死区抖动；
            3. 残余保持: 本周期未发完的增量继续保留在待发缓冲区中，后续周期平滑补发。

        Args:
            max_abs_delta: 单周期允许消费的最大绝对角度增量
            min_abs_delta: 启动运动所需的最小阈值角度（死区门限）

        Returns:
            tuple[float, float]: 本周期实际消费并应下发的角位移增量 (yaw_delta, pitch_delta)
        """
        if max_abs_delta <= 0 or min_abs_delta <= 0:
            raise ValueError("Delta limits must be positive")
        with self._lock:
            yaw_delta = self._select_delta(
                self._pending_yaw_delta, max_abs_delta, min_abs_delta
            )
            pitch_delta = self._select_delta(
                self._pending_pitch_delta, max_abs_delta, min_abs_delta
            )
            self._pending_yaw_delta -= yaw_delta
            self._pending_pitch_delta -= pitch_delta
            return yaw_delta, pitch_delta

    def discard_pending(self) -> tuple[float, float]:
        """
        清空并回滚所有未消费增量，保持虚拟准星与物理云台真实位置一致

        在触发急停 (E-STOP) 或串口通讯中断时调用，防止恢复通信后突然猛冲补发。

        Returns:
            tuple[float, float]: 回滚后的真实同步目标角 (target_yaw, target_pitch)
        """
        with self._lock:
            self._target_yaw = self._clamp(
                self._target_yaw - self._pending_yaw_delta, self._yaw_limits
            )
            self._target_pitch = self._clamp(
                self._target_pitch - self._pending_pitch_delta, self._pitch_limits
            )
            self._pending_yaw_delta = 0.0
            self._pending_pitch_delta = 0.0
            return self._target_yaw, self._target_pitch

    def reset_target(self) -> tuple[float, float]:
        """重置瞄准目标姿态至绝对中心原点 (0.0°, 0.0°)"""
        with self._lock:
            self._target_yaw = 0.0
            self._target_pitch = 0.0
            self._pending_yaw_delta = 0.0
            self._pending_pitch_delta = 0.0
            return self._target_yaw, self._target_pitch

    def get_target(self) -> tuple[float, float]:
        """获取当前设定的虚拟瞄准目标角 (target_yaw, target_pitch)"""
        with self._lock:
            return self._target_yaw, self._target_pitch

    @staticmethod
    def _select_delta(value: float, maximum: float, minimum: float) -> float:
        """带死区与上限截断的数值选择器"""
        bounded = max(-maximum, min(maximum, value))
        return bounded if abs(bounded) >= minimum else 0.0

    @staticmethod
    def _clamp(value: float, limits: tuple[float, float]) -> float:
        """区间截断辅助函数"""
        return max(limits[0], min(limits[1], value))
