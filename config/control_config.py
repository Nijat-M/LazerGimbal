# -*- coding: utf-8 -*-
"""
控制系统配置 (Control System Configuration)

集中管理所有控制相关参数：
- PID参数
- 速度分级
- 死区设置
- 误差缩放参数
- 安全限制
"""

from typing import List, Dict, Any


class ControlConfig:
    """控制系统参数（类变量作为全局单例）"""

    # ==========================================
    # PID 参数 (PID Parameters)
    # ==========================================
    KP: float = 0.3    # 比例系数 (Proportional Gain) - 稳定优先
    KI: float = 0.0    # 积分系数 (Integral Gain)    - 云台系统通常为0
    KD: float = 0.25   # 微分系数 (Derivative Gain)  - 增加阻尼，减少震荡
    MAX_INTEGRAL: int = 100  # 积分上限（防止积分饱和）

    # ==========================================
    # 速度分级 (Speed Levels)
    # 按阈值从大到小排列（列表，顺序明确，不用dict避免迭代歧义）
    # ==========================================
    SPEED_LEVELS: List[Dict[str, Any]] = [
        {'threshold': 150, 'max_step': 15},  # 超远距离 (>150px)
        {'threshold': 100, 'max_step': 12},  # 远距离   (100-150px)
        {'threshold': 60,  'max_step': 9},   # 中距离   (60-100px)
        {'threshold': 0,   'max_step': 6},   # 近距离   (<60px, 兜底)
    ]

    # ==========================================
    # 自适应死区 (Adaptive Deadzone)
    # 按误差从小到大排列（近点死区稍大防震荡，远点死区小快响应）
    # ==========================================
    CONTROL_DEADZONE_LEVELS: List[Dict[str, Any]] = [
        {'threshold': 20,  'deadzone': 12},  # 极小误差区域，小死区容忍微小跳动
        {'threshold': 50,  'deadzone': 8},   # 中低误差区域，进一步缩小死区使PID介入
        {'threshold': 999, 'deadzone': 5},   # 大误差区域，极小死区提供最快响应
    ]

    # ==========================================
    # 误差缩放 (Error Scaling)
    # 按距离从大到小排列（降低灵敏度，避免过度反应）
    # ==========================================
    ERROR_SCALING: List[Dict[str, Any]] = [
        {'threshold': 150, 'scale': 0.40},  # >150px  → 40% (大幅降低)
        {'threshold': 80,  'scale': 0.55},  # 80-150px → 55%
        {'threshold': 0,   'scale': 0.65},  # <80px   → 65% (兜底)
    ]

    # ==========================================
    # 误差滤波 (Error Filter)
    # ==========================================
    ERROR_FILTER_LENGTH: int = 3  # 移动平均滤波器长度（帧数）

    # ==========================================
    # 安全限制 (Safety Limits)
    # ==========================================
    VISION_WATCHDOG_TIMEOUT: float = 1.0  # 视觉信号看门狗超时（秒）

    # 轴向反转（摄像头方向与云台方向相反时设为True）
    INVERT_X: bool = True
    INVERT_Y: bool = True

    # 舵机软件限位（度）
    SERVO_MIN_LIMIT: int = 0
    SERVO_MAX_LIMIT: int = 180
    SERVO_CENTER: int = 90
    SERVO_STEP_TO_DEGREE: float = 0.1  # 每步对应的角度数

    # ==========================================
    # 辅助方法 (Helper Methods)
    # ==========================================

    @classmethod
    def get_speed_for_error(cls, error_magnitude: float) -> int:
        """
        根据误差大小返回最大步数（从大阈值向小阈值依次判断）

        Args:
            error_magnitude: 误差的欧几里得距离（像素）

        Returns:
            适合的最大步数
        """
        for level in cls.SPEED_LEVELS:
            if error_magnitude > level['threshold']:
                return level['max_step']
        return cls.SPEED_LEVELS[-1]['max_step']  # 兜底返回最慢速度

    @classmethod
    def get_deadzone_for_error(cls, error_magnitude: float) -> int:
        """
        根据误差大小返回死区大小（从小阈值向大阈值依次判断）

        Args:
            error_magnitude: 误差的欧几里得距离（像素）

        Returns:
            适合的死区大小（像素）
        """
        for level in cls.CONTROL_DEADZONE_LEVELS:
            if error_magnitude < level['threshold']:
                return level['deadzone']
        return 10  # 兜底

    @classmethod
    def get_scale_for_error(cls, error_magnitude: float) -> float:
        """
        根据误差大小返回缩放系数（从大阈值向小阈值依次判断）

        Args:
            error_magnitude: 误差的欧几里得距离（像素）

        Returns:
            缩放系数 (0.0-1.0)
        """
        for level in cls.ERROR_SCALING:
            if error_magnitude > level['threshold']:
                return level['scale']
        return cls.ERROR_SCALING[-1]['scale']  # 兜底返回最大缩放

    @classmethod
    def get_tuning_dict(cls) -> dict:
        """返回可调参数字典（用于GUI显示和JSON保存）"""
        return {
            'KP': cls.KP,
            'KI': cls.KI,
            'KD': cls.KD,
            'MAX_STEP': cls.SPEED_LEVELS[0]['max_step'],
            'DEADZONE': cls.CONTROL_DEADZONE_LEVELS[0]['deadzone'],
        }

    @classmethod
    def update_from_dict(cls, data: dict) -> None:
        """从字典更新PID参数（用于加载配置文件）"""
        cls.KP = data.get('KP', cls.KP)
        cls.KI = data.get('KI', cls.KI)
        cls.KD = data.get('KD', cls.KD)
