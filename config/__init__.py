# -*- coding: utf-8 -*-
"""
配置模块统一接口 (Configuration Module)

[使用方法 Usage]
原来:
    from config import cfg
    cfg.PID_KP = 0.5

现在:
    from config import cfg, PIDConfig, VisionConfig, HardwareConfig
    
    # 方式1: 使用旧接口（兼容性）
    cfg.PID_KP = 0.5
    
    # 方式2: 使用新接口（推荐）
    PIDConfig.KP = 0.5
    VisionConfig.CAMERA_ID = 0
    HardwareConfig.SERIAL_PORT = "COM3"

[优点]
1. 参数分类清晰，容易找到
2. 每个配置文件独立，便于调试
3. 向下兼容旧代码
"""

import json
import os
from .pid_config import PIDConfig
from .vision_config import VisionConfig
from .hardware_config import HardwareConfig


class ConfigManager:
    """
    配置管理器 (Configuration Manager)
    提供统一的配置加载/保存接口
    """
    
    CONFIG_FILE = "gimbal_config.json"
    
    def __init__(self):
        """
        初始化配置（兼容旧代码的属性映射）
        """
        # 自动加载配置
        self.load_config()
    
    # ==========================
    # 兼容性属性（映射到新配置类）
    # ==========================
    # PID 参数
    @property
    def PID_KP(self): return PIDConfig.KP
    @PID_KP.setter
    def PID_KP(self, value): PIDConfig.KP = value
    
    @property
    def PID_KI(self): return PIDConfig.KI
    @PID_KI.setter
    def PID_KI(self, value): PIDConfig.KI = value
    
    @property
    def PID_KD(self): return PIDConfig.KD
    @PID_KD.setter
    def PID_KD(self, value): PIDConfig.KD = value
    
    @property
    def MAX_STEP(self): return PIDConfig.MAX_STEP
    @MAX_STEP.setter
    def MAX_STEP(self, value): PIDConfig.MAX_STEP = value
    
    @property
    def DEADZONE(self): return PIDConfig.DEADZONE
    @DEADZONE.setter
    def DEADZONE(self, value): PIDConfig.DEADZONE = value
    
    @property
    def INVERT_X(self): return PIDConfig.INVERT_X
    @INVERT_X.setter
    def INVERT_X(self, value): PIDConfig.INVERT_X = value
    
    @property
    def INVERT_Y(self): return PIDConfig.INVERT_Y
    @INVERT_Y.setter
    def INVERT_Y(self, value): PIDConfig.INVERT_Y = value
    
    @property
    def SERVO_SOFTWARE_STEP_SCALE(self): return PIDConfig.SERVO_STEP_TO_DEGREE
    
    # 视觉参数
    @property
    def CAMERA_ID(self): return VisionConfig.CAMERA_ID
    @CAMERA_ID.setter
    def CAMERA_ID(self, value): VisionConfig.CAMERA_ID = value
    
    @property
    def FRAME_WIDTH(self): return VisionConfig.FRAME_WIDTH
    @property
    def FRAME_HEIGHT(self): return VisionConfig.FRAME_HEIGHT
    @property
    def CENTER_X(self): return VisionConfig.CENTER_X
    @property
    def CENTER_Y(self): return VisionConfig.CENTER_Y
    @property
    def PIXELS_PER_DEGREE(self): return VisionConfig.PIXELS_PER_DEGREE
    
    @property
    def HSV_RED_LOWER1(self): return VisionConfig.HSV_RED_LOWER1
    @property
    def HSV_RED_UPPER1(self): return VisionConfig.HSV_RED_UPPER1
    @property
    def HSV_RED_LOWER2(self): return VisionConfig.HSV_RED_LOWER2
    @property
    def HSV_RED_UPPER2(self): return VisionConfig.HSV_RED_UPPER2
    @property
    def HSV_BLUE_LOWER(self): return VisionConfig.HSV_BLUE_LOWER
    @property
    def HSV_BLUE_UPPER(self): return VisionConfig.HSV_BLUE_UPPER
    
    # 硬件参数
    @property
    def SERIAL_PORT(self): return HardwareConfig.SERIAL_PORT
    @SERIAL_PORT.setter
    def SERIAL_PORT(self, value): HardwareConfig.SERIAL_PORT = value
    
    @property
    def BAUD_RATE(self): return HardwareConfig.BAUD_RATE
    @property
    def TIMEOUT(self): return HardwareConfig.TIMEOUT
    @property
    def SERVO_MIN_LIMIT(self): return HardwareConfig.SERVO_MIN_LIMIT
    @property
    def SERVO_MAX_LIMIT(self): return HardwareConfig.SERVO_MAX_LIMIT
    @property
    def MANUAL_STEP(self): return HardwareConfig.MANUAL_STEP
    @property
    def DEGREE_TO_PULSE(self): return HardwareConfig.DEGREE_TO_PULSE
    
    # CONFIG_FILE 已在类级别定义，无需 property
    
    # ==========================
    # 配置保存/加载
    # ==========================
    def load_config(self):
        """
        从 JSON 文件加载配置
        Load configuration from file
        """
        config_file = ConfigManager.CONFIG_FILE
        if not os.path.exists(config_file):
            print("[CONFIG] 配置文件不存在，使用默认值")
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 加载 PID 参数
            if 'PID' in data:
                PIDConfig.update_from_dict(data['PID'])
            
            # 向下兼容旧格式
            else:
                PIDConfig.KP = data.get('PID_KP', PIDConfig.KP)
                PIDConfig.KI = data.get('PID_KI', PIDConfig.KI)
                PIDConfig.KD = data.get('PID_KD', PIDConfig.KD)
                PIDConfig.MAX_STEP = data.get('MAX_STEP', PIDConfig.MAX_STEP)
                PIDConfig.DEADZONE = data.get('DEADZONE', PIDConfig.DEADZONE)
            
            print(f"[CONFIG] ✓ 已加载配置: {config_file}")
            print(f"[CONFIG]   PID: Kp={PIDConfig.KP:.2f}, Ki={PIDConfig.KI:.3f}, Kd={PIDConfig.KD:.2f}")
            
        except Exception as e:
            print(f"[CONFIG] ✗ 加载失败: {e}")
    
    def save_config(self):
        """
        保存当前配置到 JSON 文件
        Save configuration to file
        """
        config_file = ConfigManager.CONFIG_FILE
        data = {
            'PID': PIDConfig.get_tuning_dict(),
            'version': '2.0',  # 新版本标记
            'last_updated': self._get_timestamp()
        }
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[CONFIG] ✓ 已保存配置: {config_file}")
        except Exception as e:
            print(f"[CONFIG] ✗ 保存失败: {e}")
    
    def _get_timestamp(self):
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==========================
# 全局单例（兼容旧代码）
# ==========================
cfg = ConfigManager()

# 导出所有配置类
__all__ = [
    'cfg',              # 兼容旧代码
    'PIDConfig',        # PID 参数
    'VisionConfig',     # 视觉参数
    'HardwareConfig',   # 硬件参数
    'ConfigManager'     # 配置管理器
]
