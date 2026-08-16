# -*- coding: utf-8 -*-
"""
控制系统配置 (Control System Configuration)

集中管理所有控制相关参数：
- PID/FF 参数
- 死区设置
- 安全限制
"""

class ControlConfig:
    """控制系统参数（类变量作为全局单例）"""

    # ==========================================
    # 控制参数 (Control Parameters)
    # ==========================================
    CONTROL_LOOP_HZ: float = 60.0 # 控制循环频率 (60Hz，与60FPS相机帧率完美同步)
    KP: float = 0.60   # 比例系数 (敏捷跟手，平稳无过冲)
    KI: float = 0.16   # 积分系数 (消除稳态静差)
    KD: float = 0.50   # 微分系数 (高速阻尼，抑制摆动)
    DEADZONE: int = 5  # 拦截死区（像素），在此死区内强制认定为误差0

    # FPS 风格鼠标手动瞄准
    MOUSE_SENSITIVITY: float = 0.08      # 每个鼠标计数对应的虚拟角度（度）
    MOUSE_ERROR_PER_DEGREE: float = 50.0 # 旧舵机协议的角度增量→模拟误差转换
    MOUSE_MAX_ERROR: int = 120           # 单个控制周期的最大模拟误差
    MOUSE_YAW_MIN: float = -80.0
    MOUSE_YAW_MAX: float = 80.0
    MOUSE_PITCH_MIN: float = -45.0
    MOUSE_PITCH_MAX: float = 45.0

    # ==========================================
    # 安全限制与追踪参数 (Safety Limits & Tracking Tunings)
    # ==========================================
    VISION_WATCHDOG_TIMEOUT: float = 0.25  # 目标坐标超过250ms未更新时立即停止

    # 轴向反转（默认：X轴不反转，Y轴反转）
    # 视觉坐标中，目标在右侧(+X)需向右转(+err)，故X轴默认不反转；
    # 目标在上方(-Y)需向上抬头(+err)，故Y轴默认取反。
    INVERT_X: bool = False
    INVERT_Y: bool = True

    # 追踪误差缩放与安全限幅（针对新电机与机械俯仰行程优化）
    TRACKING_SCALE_X: float = 1.20       # X 轴追踪误差缩放系数（配合下位机直接速度闭环）
    TRACKING_SCALE_Y: float = 0.45       # Y 轴追踪误差缩放系数（保持平稳，防过冲保护限位）
    TRACKING_MAX_ERROR_X: int = 360      # X 轴单周期最大追踪误差（匹配 1600 steps/s 高转速）
    TRACKING_MAX_ERROR_Y: int = 50       # Y 轴单周期最大追踪误差

    # 舵机软件限位（度）
    SERVO_MIN_LIMIT: int = 0
    SERVO_MAX_LIMIT: int = 180
    SERVO_CENTER: int = 90
    SERVO_STEP_TO_DEGREE: float = 0.1  # 每步对应的角度数

    # ==========================================
    # 辅助方法 (Helper Methods)
    # ==========================================
    @classmethod
    def get_tuning_dict(cls) -> dict:
        """返回可调参数字典（用于GUI显示和JSON保存）"""
        return {
            'KP': cls.KP,
            'KI': cls.KI,
            'KD': cls.KD,
            'DEADZONE': cls.DEADZONE,
        }

    @classmethod
    def update_from_dict(cls, data: dict) -> None:
        """从字典更新设定参数（用于加载配置文件）"""
        cls.KP = data.get('KP', cls.KP)
        cls.KI = data.get('KI', cls.KI)
        cls.KD = data.get('KD', cls.KD)
        cls.DEADZONE = data.get('DEADZONE', cls.DEADZONE)
