# -*- coding: utf-8 -*-
"""
PID 控制参数配置 (PID Control Configuration)

[调参指南 Tuning Guide]
- Kp (比例): 主要动力，越大响应越快，但容易震荡
- Ki (积分): 消除稳态误差，一般设很小或为0
- Kd (微分): 阻尼作用，抑制震荡，相当于"刹车"

[调参流程]
1. 先调 Kp: 从小到大，直到出现轻微震荡
2. 再加 Kd: 消除震荡，平滑响应
3. 最后调 Ki: 如果有稳态误差才加，通常保持0

[MG996R 舵机建议值]
- 快速响应: Kp=0.8, Ki=0, Kd=0.15
- 平滑稳定: Kp=0.5, Ki=0, Kd=0.1
- 慢速精准: Kp=0.3, Ki=0.01, Kd=0.05
"""

class PIDConfig:
    """PID 控制参数 (PID Control Parameters)"""
    
    # ==========================
    # PID 三要素 (温和版：稳定优先，避免过冲)
    # ==========================
    KP = 0.3    # 比例系数 (Proportional Gain) - 降低响应速度，提高稳定性
    KI = 0.0    # 积分系数 (Integral Gain) - 云台系统通常不需要积分
    KD = 0.25   # 微分系数 (Derivative Gain) - 增加阻尼，减少震荡
    
    # ==========================
    # 运动限制 (保守版 - 稳定优先，多档位速度)
    # ==========================
    MAX_STEP = 12           # 基础最大步数
    MAX_STEP_VERY_FAST = 15 # 超远距离时的速度（新增）
    MAX_STEP_FAST = 12      # 远距离时的速度
    MAX_STEP_MEDIUM = 9     # 中距离时的速度
    MAX_STEP_SLOW = 6       # 接近目标时的速度
    DEADZONE = 20           # 基础死区（像素）
    MAX_INTEGRAL = 100      # 积分上限（防止积分饱和）
    
    # ==========================
    # 轴向反转
    # ==========================
    # 如果摄像头看到的移动方向和云台实际方向相反，设置为 True
    INVERT_X = True
    INVERT_Y = True
    
    # ==========================
    # 舵机参数
    # ==========================
    # 软件位置估算系数（度/步）
    # MG996R 舵机约 0.1 度/步
    SERVO_STEP_TO_DEGREE = 0.1
    
    @classmethod
    def get_tuning_dict(cls):
        """
        返回可调参数字典（用于GUI显示和保存）
        Returns tunable parameters as dict
        """
        return {
            'KP': cls.KP,
            'KI': cls.KI,
            'KD': cls.KD,
            'MAX_STEP': cls.MAX_STEP,
            'DEADZONE': cls.DEADZONE
        }
    
    @classmethod
    def update_from_dict(cls, data):
        """
        从字典更新参数（用于加载配置）
        Update parameters from dict
        """
        cls.KP = data.get('KP', cls.KP)
        cls.KI = data.get('KI', cls.KI)
        cls.KD = data.get('KD', cls.KD)
        cls.MAX_STEP = data.get('MAX_STEP', cls.MAX_STEP)
        cls.DEADZONE = data.get('DEADZONE', cls.DEADZONE)
