# -*- coding: utf-8 -*-
"""
硬件参数配置 (Hardware Configuration)

[串口通信说明]
与 STM32 下位机通信使用串口 UART。
数据格式: "X{angle}Y{angle}\n" (例如: "X90Y90\n")

[舵机说明]
MG996R 参数：
- 工作电压: 4.8V - 7.2V
- 工作电流: 100mA (空载), 2.5A (堵转)
- 转速: 0.17s/60° (6V)
- 扭矩: 9.4 kg·cm (4.8V), 11 kg·cm (6V)
- 转动角度: 0° - 180°
"""

class HardwareConfig:
    """硬件相关参数 (Hardware Parameters)"""
    
    # ==========================
    # 串口配置
    # ==========================
    SERIAL_PORT = "COM3"    # 串口号（根据实际情况修改）
    BAUD_RATE = 9600        # 波特率（需与 STM32 程序一致）
    TIMEOUT = 1             # 读取超时时间（秒）
    
    # ==========================
    # 舵机限位
    # ==========================
    SERVO_MIN_LIMIT = 0     # 舵机最小角度（度）
    SERVO_MAX_LIMIT = 180   # 舵机最大角度（度）
    SERVO_CENTER = 90       # 舵机中位（度）
    
    # ==========================
    # 舵机 PWM 参数（与 STM32 匹配）
    # ==========================
    # STM32 PWM 脉冲范围：600-2400 对应 0-180°
    # 每 1° = (2400-600)/180 = 10 个脉冲单位
    #
    # ⚙️ 调试说明：如果手动模式移动太小/太大，调整此参数
    # - 移动太小：增大此值（如 15, 20）
    # - 移动太大：减小此值（如 8, 5）
    # - 理论值：10（根据 PWM 配置计算）
    DEGREE_TO_PULSE = 10    # 角度到 PWM 脉冲的转换系数
    
    # 注意：追踪模式使用 PID 输出（已经是脉冲单位），不受此参数影响
    # 此参数仅影响手动测试模式
    
    # ==========================
    # 手动控制
    # ==========================
    # 手动模式每次移动步长（度）
    # 建议值：5-15°（太小看不清，太大容易超限位）
    MANUAL_STEP = 10        # 每次按方向键移动的角度
    
    # ==========================
    # 安全保护
    # ==========================
    WATCHDOG_TIMEOUT = 2.0  # 看门狗超时时间（秒）
    # 如果超过此时间没收到视觉数据，自动回中
    
    @classmethod
    def get_serial_config(cls):
        """
        返回串口配置字典
        Returns serial configuration as dict
        """
        return {
            'port': cls.SERIAL_PORT,
            'baudrate': cls.BAUD_RATE,
            'timeout': cls.TIMEOUT
        }
    
    @classmethod
    def is_angle_valid(cls, angle):
        """
        检查角度是否在有效范围内
        Check if angle is within valid range
        """
        return cls.SERVO_MIN_LIMIT <= angle <= cls.SERVO_MAX_LIMIT
    
    @classmethod
    def clamp_angle(cls, angle):
        """
        限制角度在有效范围内
        Clamp angle to valid range
        """
        return max(cls.SERVO_MIN_LIMIT, min(cls.SERVO_MAX_LIMIT, angle))
