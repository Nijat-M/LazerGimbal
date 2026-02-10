# -*- coding: utf-8 -*-
import numpy as np

class Config:
    """
    单例配置类 (Singleton Configuration Class)
    用于存储全局配置参数，如串口设置、PID参数、视觉阈值等。
    Singleton Pattern ensures only one instance of Config exists.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """
        初始化默认参数
        Initialize default system parameters.
        """
        # ==========================
        # 1. 串口配置 (Serial Configuration)
        # ==========================
        # 通信端口和波特率，用于连接 STM32 下位机
        self.SERIAL_PORT = "COM3"
        self.BAUD_RATE = 9600
        self.TIMEOUT = 1               # 读取超时时间 (秒)

        # ==========================
        # 2. PID 控制参数 (PID Control Parameters)
        # ==========================
        # Proportional (P): 比例项，主要动力。
        # 越大响应越快，但容易震荡。
        self.PID_KP = 0.4   # 温和：稳定优先，避免过冲
        
        # Integral (I): 积分项，消除稳态误差。
        # 用于修正"差一点点"的情况。
        self.PID_KI = 0.0   # 云台系统通常不需要积分项
        
        # Derivative (D): 微分项，阻尼作用。
        # 用于抑制震荡，相当于"刹车"。
        self.PID_KD = 0.2   # 平衡：良好的阻尼效果
        
        # ==========================
        # 3. 运动限制 (Motion Limits)
        # ==========================
        # 反转设置: 如果摄像头看到的移动方向和云台实际方向相反，设置为True
        self.INVERT_X = True
        self.INVERT_Y = True
        
        # MAX_STEP: 每次循环最大移动步数。
        # 限制最大速度，防止舵机动作过大/过快。
        # 注意：代码中使用智能速度控制，根据距离动态调整
        self.MAX_STEP = 20         # 基础最大速度（温和）
        self.MAX_STEP_FAST = 25    # 远距离快速接近（降低避免扭到头）
        self.MAX_STEP_MEDIUM = 15  # 中距离平稳移动
        self.MAX_STEP_SLOW = 8     # 近距离精确定位
        
        # DEADZONE: 死区 (Pixels)。
        # 当误差小于此像素值时，不发送指令，防止在目标附近抖动。
        # 注意：代码中实际使用自适应死区(5-25像素)
        self.DEADZONE = 15

        # ==========================
        # 4. 图像参数 (Computer Vision)
        # ==========================
        self.CAMERA_ID = 0      # 摄像头ID (默认0)
        self.FRAME_WIDTH = 640  # 原始分辨率 (Resolution)
        self.FRAME_HEIGHT = 480
        self.CENTER_X = 320     # 画面中心点 (Target Center)
        self.CENTER_Y = 240
        self.PIXELS_PER_DEGREE = 20 # 估算值: 多少像素对应 1 度

        # ==========================
        # 5. 颜色阈值 (Color Thresholds - HSV)
        # ==========================
        # HSV (Hue, Saturation, Value) 颜色空间比 RGB 更适合颜色识别
        
        # 红色激光点 (Red Laser)
        # 红色在 HSV 色轮的 0 度和 180 度附近，所以需要两个范围
        self.HSV_RED_LOWER1 = np.array([0, 100, 100])
        self.HSV_RED_UPPER1 = np.array([10, 255, 255])
        self.HSV_RED_LOWER2 = np.array([160, 100, 100])
        self.HSV_RED_UPPER2 = np.array([180, 255, 255])
        
        # 蓝色物体 (Blue Object)
        self.HSV_BLUE_LOWER = np.array([100, 150, 50])
        self.HSV_BLUE_UPPER = np.array([140, 255, 255])

        # ==========================
        # 6. 软限位与比例 (Software Limits)
        # ==========================
        # 软件位置估算系数。防止软件坐标跑得比物理舵机快，导致早早撞到虚拟墙。
        # [Calibration] Hardware moves ~0.1 deg per step.
        self.SERVO_SOFTWARE_STEP_SCALE = 0.1
        
        self.SERVO_MIN_LIMIT = 0   # 最小角度
        self.SERVO_MAX_LIMIT = 180 # 最大角度
        
        # 手动模式单次移动步长（度）
        self.MANUAL_STEP = 5  # 每次按方向键移动5度

        # ==========================
        # 7. 配置文件 (Configuration)
        # ==========================
        self.CONFIG_FILE = "gimbal_config.json"

    def load_config(self):
        """ 
        从 JSON 文件加载配置 (Load Configuration)
        Persist settings across restarts.
        """
        import json
        import os
        if not os.path.exists(self.CONFIG_FILE):
             return
        try:
            with open(self.CONFIG_FILE, 'r') as f:
                data = json.load(f)
                # Load PID
                self.PID_KP = data.get('PID_KP', self.PID_KP)
                self.PID_KI = data.get('PID_KI', self.PID_KI)
                self.PID_KD = data.get('PID_KD', self.PID_KD)
                # Load Limits
                self.MAX_STEP = data.get('MAX_STEP', self.MAX_STEP)
                self.DEADZONE = data.get('DEADZONE', self.DEADZONE)
                print(f"[CONFIG] Loaded settings from {self.CONFIG_FILE}")
        except Exception as e:
            print(f"[CONFIG] Error loading: {e}")

    def save_config(self):
        """ 
        保存当前配置到 JSON 文件 (Save Configuration)
        """
        import json
        data = {
            'PID_KP': self.PID_KP,
            'PID_KI': self.PID_KI,
            'PID_KD': self.PID_KD,
            'MAX_STEP': self.MAX_STEP,
            'DEADZONE': self.DEADZONE
        }
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"[CONFIG] Saved settings to {self.CONFIG_FILE}")
        except Exception as e:
            print(f"[CONFIG] Error saving: {e}")

# 全局单例实例
cfg = Config()
