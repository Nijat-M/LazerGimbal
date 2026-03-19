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
    KP: float = 0.4    # 比例系数 (与STM32上电安全值同步)
    KI: float = 0.16   # 积分系数 (与STM32上电安全值同步)
    KD: float = 0.5    # 微分系数 (与STM32上电安全值同步)
    DEADZONE: int = 5  # 拦截死区（像素），在此死区内强制认定为误差0

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
