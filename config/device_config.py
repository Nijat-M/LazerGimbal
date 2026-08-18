# -*- coding: utf-8 -*-
"""
设备与连接持久化配置 (Device & Connection Persistence Configuration)
自动保存用户选择的摄像头 ID、分辨率、画面方向以及 STM32 串口端口号，启动时自动预加载。
"""

import os
import json
from utils.logger import Logger

logger = Logger("DeviceConfig")
DEVICE_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "device_settings.json")


class DeviceConfig:
    """保存摄像头设置与 STM32 串口连接偏好"""
    
    # 摄像头偏好
    CAMERA_ID: int = 1
    RESOLUTION_WIDTH: int = 1920
    RESOLUTION_HEIGHT: int = 1080
    FLIP_MODE: str = "NONE"
    AUTO_OPEN_CAMERA: bool = True

    # STM32 串口偏好
    SERIAL_PORT: str = "COM5"
    SERIAL_BAUDRATE: int = 115200
    AUTO_CONNECT_SERIAL: bool = True

    @classmethod
    def load(cls) -> bool:
        """从 JSON 加载配置，若不存在则创建默认配置"""
        if not os.path.exists(DEVICE_SETTINGS_FILE):
            cls.save()
            return False

        try:
            with open(DEVICE_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            cam = data.get("camera", {})
            cls.CAMERA_ID = int(cam.get("camera_id", cls.CAMERA_ID))
            cls.RESOLUTION_WIDTH = int(cam.get("resolution_width", cls.RESOLUTION_WIDTH))
            cls.RESOLUTION_HEIGHT = int(cam.get("resolution_height", cls.RESOLUTION_HEIGHT))
            cls.FLIP_MODE = str(cam.get("flip_mode", cls.FLIP_MODE))
            cls.AUTO_OPEN_CAMERA = bool(cam.get("auto_open", cls.AUTO_OPEN_CAMERA))

            ser = data.get("serial", {})
            cls.SERIAL_PORT = str(ser.get("port", cls.SERIAL_PORT))
            cls.SERIAL_BAUDRATE = int(ser.get("baudrate", cls.SERIAL_BAUDRATE))
            cls.AUTO_CONNECT_SERIAL = bool(ser.get("auto_connect", cls.AUTO_CONNECT_SERIAL))

            logger.info(
                f"[DEVICE CONFIG] ✓ Loaded saved device settings: "
                f"Camera={cls.CAMERA_ID} ({cls.RESOLUTION_WIDTH}x{cls.RESOLUTION_HEIGHT}, flip={cls.FLIP_MODE}), "
                f"Port={cls.SERIAL_PORT}"
            )
            return True
        except Exception as e:
            logger.error(f"[DEVICE CONFIG ERROR] Failed to load device_settings.json: {e}")
            return False

    @classmethod
    def save(cls) -> bool:
        """保存当前设备与连接设置到 JSON 文件"""
        data = {
            "camera": {
                "camera_id": cls.CAMERA_ID,
                "resolution_width": cls.RESOLUTION_WIDTH,
                "resolution_height": cls.RESOLUTION_HEIGHT,
                "flip_mode": cls.FLIP_MODE,
                "auto_open": cls.AUTO_OPEN_CAMERA
            },
            "serial": {
                "port": cls.SERIAL_PORT,
                "baudrate": cls.SERIAL_BAUDRATE,
                "auto_connect": cls.AUTO_CONNECT_SERIAL
            }
        }
        try:
            with open(DEVICE_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"[DEVICE CONFIG] ✓ Saved device settings to {DEVICE_SETTINGS_FILE}")
            return True
        except Exception as e:
            logger.error(f"[DEVICE CONFIG ERROR] Failed to save device_settings.json: {e}")
            return False


# 模块导入时自动加载
DeviceConfig.load()
