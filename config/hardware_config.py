# -*- coding: utf-8 -*-
"""
硬件参数配置 (Hardware Configuration)

[通信架构说明]
- STM32F401 采用原生 USB CDC 虚拟串口 (12 Mbps Full-Speed)。
- 协议格式:
  - 实时运动指令: "<error_x,error_y,fire>\\n" (例如: "<12, -8, 0>\\n")
  - 参数整定指令: "{Kp,Ki,Kd}\\n" (例如: "{0.60,0.16,0.50}\\n")
  - 紧急制动指令: "!STOP\\n"
  - 复位中位指令: "!CENTER\\n"
  - 激光武器指令: "!LASERON\\n", "!LASEROFF\\n", "!LASER:100\\n"

[执行机构说明]
- 电机类型: MKS SERVO42C 闭环步进电机 (Closed-Loop Stepper Engine)
- 底层调度: STM32 TIM2 10kHz DDA 步进脉冲发生器
- 速度上限: 9000 steps/s (高达 ~1000°/s 高速响应)
- 加速度上限: 10000 steps/s² (毫秒级起步与高强度制动)
- 激光模组: TIM3 PWM 1kHz 硬件调光 (PB0 / PA7)
"""

class HardwareConfig:
    """硬件相关参数 (Hardware Parameters)"""
    
    # ==========================
    # USB CDC / 串口配置
    # ==========================
    SERIAL_PORT = "COM5"    # 默认 USB 虚拟串口号 (STMicroelectronics Virtual COM)
    BAUD_RATE = 115200      # 传输波特率 (USB CDC 模式下虚拟波特率)
    TIMEOUT = 1             # 读取超时时间（秒）
    
    # ==========================
    # 步进电机与运动控制参数
    # ==========================
    STEP_TIMER_HZ = 10000.0         # TIM2 步进脉冲调度时基 (10kHz DDA)
    MAX_STEP_RATE = 9000.0          # 最大步进频率 (steps/s)
    MAX_STEP_ACCEL = 10000.0        # 最大加速度 (steps/s²)
    FRICTION_BREAKAWAY_RATE_X = 120.0 # X 轴克服静摩擦起步前馈 (steps/s)
    
    # 手动模式点动步长 (像素当量)
    MANUAL_STEP = 10
    DEGREE_TO_PULSE = 10            # 兼容保留字段
    
    # ==========================
    # 激光武器子系统 (Laser Subsystem)
    # ==========================
    LASER_PWM_FREQ_HZ = 1000        # TIM3 硬件 PWM 频率 (1kHz)
    DEFAULT_LASER_POWER = 100       # 默认激光功率 (0-100%)
    
    # ==========================
    # 安全保护机制
    # ==========================
    WATCHDOG_TIMEOUT = 0.25         # 视觉看门狗超时时间（秒，250ms未收到坐标自动急停）
    
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
