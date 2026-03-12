# -*- coding: utf-8 -*-
"""
配置模块统一接口 (Configuration Module)

[使用方法 Usage]
推荐方式（直接导入配置类）：
    from config import ControlConfig, VisionConfig, HardwareConfig
    ControlConfig.KP = 0.5
    VisionConfig.CAMERA_ID = 1

兼容方式（旧代码）：
    from config import cfg
    cfg.PID_KP  # 通过 cfg 访问（兼容旧接口）

[配置文件职责]
- control_config.py : PID参数、速度分级、死区、误差缩放（控制相关全在这里）
- vision_config.py  : 摄像头、颜色阈值、图像参数
- hardware_config.py: 串口、舵机PWM、手动控制参数
"""

import json
import os
from datetime import datetime

from .control_config import ControlConfig
from .vision_config import VisionConfig
from .hardware_config import HardwareConfig
from utils.logger import Logger
logger = Logger("Config")



class ConfigManager:
    """
    配置管理器（简化版）

    职责：统一提供配置的保存/加载接口。
    不再包含冗余的属性映射，直接使用各配置类。
    """

    CONFIG_FILE = "gimbal_config.json"

    def __init__(self):
        """初始化时自动加载配置文件（若存在）"""
        self.load_config()

    # --------------------------------------------------
    # 兼容旧代码的属性（最小集合，避免大规模改动旧代码）
    # --------------------------------------------------
    @property
    def PID_KP(self) -> float: return ControlConfig.KP
    @PID_KP.setter
    def PID_KP(self, v: float): ControlConfig.KP = v

    @property
    def PID_KI(self) -> float: return ControlConfig.KI
    @PID_KI.setter
    def PID_KI(self, v: float): ControlConfig.KI = v

    @property
    def PID_KD(self) -> float: return ControlConfig.KD
    @PID_KD.setter
    def PID_KD(self, v: float): ControlConfig.KD = v

    @property
    def INVERT_X(self) -> bool: return ControlConfig.INVERT_X
    @INVERT_X.setter
    def INVERT_X(self, v: bool): ControlConfig.INVERT_X = v

    @property
    def INVERT_Y(self) -> bool: return ControlConfig.INVERT_Y
    @INVERT_Y.setter
    def INVERT_Y(self, v: bool): ControlConfig.INVERT_Y = v

    @property
    def SERVO_SOFTWARE_STEP_SCALE(self) -> float: return ControlConfig.SERVO_STEP_TO_DEGREE

    @property
    def SERVO_MIN_LIMIT(self) -> int: return ControlConfig.SERVO_MIN_LIMIT

    @property
    def SERVO_MAX_LIMIT(self) -> int: return ControlConfig.SERVO_MAX_LIMIT

    # 以下从各子配置类透出（只读，旧代码使用）
    @property
    def CAMERA_ID(self) -> int: return VisionConfig.CAMERA_ID
    @CAMERA_ID.setter
    def CAMERA_ID(self, v: int): VisionConfig.CAMERA_ID = v

    @property
    def FRAME_WIDTH(self) -> int: return VisionConfig.FRAME_WIDTH

    @property
    def FRAME_HEIGHT(self) -> int: return VisionConfig.FRAME_HEIGHT

    @property
    def CENTER_X(self) -> int: return VisionConfig.CENTER_X

    @property
    def CENTER_Y(self) -> int: return VisionConfig.CENTER_Y

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

    @property
    def SERIAL_PORT(self) -> str: return HardwareConfig.SERIAL_PORT
    @SERIAL_PORT.setter
    def SERIAL_PORT(self, v: str): HardwareConfig.SERIAL_PORT = v

    @property
    def BAUD_RATE(self) -> int: return HardwareConfig.BAUD_RATE

    @property
    def TIMEOUT(self) -> int: return HardwareConfig.TIMEOUT

    @property
    def MANUAL_STEP(self) -> int: return HardwareConfig.MANUAL_STEP

    @property
    def DEGREE_TO_PULSE(self) -> int: return HardwareConfig.DEGREE_TO_PULSE

    # --------------------------------------------------
    # 配置保存 / 加载
    # --------------------------------------------------
    def load_config(self) -> None:
        """从 JSON 文件加载配置"""
        if not os.path.exists(self.CONFIG_FILE):
            logger.info("[CONFIG] 配置文件不存在，使用默认值")
            return

        try:
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 新格式
            if 'PID' in data:
                ControlConfig.update_from_dict(data['PID'])
            # 兼容旧格式
            else:
                ControlConfig.KP = data.get('PID_KP', ControlConfig.KP)
                ControlConfig.KI = data.get('PID_KI', ControlConfig.KI)
                ControlConfig.KD = data.get('PID_KD', ControlConfig.KD)

            logger.info(f"[CONFIG] ✓ 已加载配置: {self.CONFIG_FILE}")
            print(f"[CONFIG]   PID: Kp={ControlConfig.KP:.2f}, "
                  f"Ki={ControlConfig.KI:.3f}, Kd={ControlConfig.KD:.2f}")

        except Exception as e:
            logger.info(f"[CONFIG] ✗ 加载失败: {e}")

    def save_config(self) -> None:
        """保存当前配置到 JSON 文件"""
        data = {
            'PID': ControlConfig.get_tuning_dict(),
            'version': '3.0',
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info(f"[CONFIG] ✓ 已保存配置: {self.CONFIG_FILE}")
        except Exception as e:
            logger.info(f"[CONFIG] ✗ 保存失败: {e}")


# ==========================
# 全局单例（兼容旧代码 `from config import cfg`）
# ==========================
cfg = ConfigManager()

# 推荐直接使用配置类
__all__ = [
    'cfg',           # 兼容旧代码
    'ControlConfig', # 控制参数（PID/速度/死区/缩放）
    'VisionConfig',  # 视觉参数（颜色/摄像头）
    'HardwareConfig', # 硬件参数（串口/舵机）
    'ConfigManager',
]
