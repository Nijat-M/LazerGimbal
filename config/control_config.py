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
    DEADZONE: int = 3  # 拦截死区（像素），极窄死区确保准星直接打进目标中心红心

    # FPS 风格鼠标手动瞄准
    MOUSE_SENSITIVITY: float = 0.08      # 每个鼠标计数对应的虚拟角度（度）
    MOUSE_ERROR_PER_DEGREE: float = 50.0 # 虚拟角度增量→模拟误差转换系数
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

    # 追踪误差缩放与准星防过冲阻尼参数
    TRACKING_SCALE_X: float = 1.25       # X 轴基准追踪误差缩放系数
    TRACKING_SCALE_Y: float = 0.90       # Y 轴基准追踪误差缩放系数 (提高 Y 轴克服云台重力，直推目标中心)
    TRACKING_MAX_ERROR_X: int = 130      # X 轴单周期最大追踪误差
    TRACKING_MAX_ERROR_Y: int = 90       # Y 轴单周期最大追踪误差
    
    SETTLE_ZONE_X: int = 35              # X 轴准星中心平滑减速过渡区（像素）
    SETTLE_ZONE_Y: int = 18              # Y 轴准星中心平滑减速过渡区（像素）
    EDGE_COMPRESS_THRESHOLD_X: int = 100 # X 轴屏幕边缘软饱和压缩起点（像素）
    EDGE_COMPRESS_THRESHOLD_Y: int = 100 # Y 轴屏幕边缘软饱和压缩起点（像素）

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
