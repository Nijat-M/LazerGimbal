# -*- coding: utf-8 -*-
"""
Web Bridge Module for Laser Gimbal (HSS)
Connects GimbalController, VisionWorker, and SerialThread with FastAPI WebSocket server.
"""

import time
import asyncio
import json
from typing import Dict, Any, List, Set, Optional
from fastapi import WebSocket
import numpy as np

from utils.logger import Logger
from config.control_config import ControlConfig
from config.vision_config import VisionConfig
from core.serial_thread import SerialThread

logger = Logger("WebBridge")


class WebBridge:
    def __init__(self, gimbal_controller=None, vision_worker=None, serial_thread: Optional[SerialThread] = None):
        self.gimbal_controller = gimbal_controller
        self.vision_worker = vision_worker
        self.serial_thread = serial_thread

        # Connected WebSocket clients
        self.active_connections: Set[WebSocket] = set()

        # Telemetry State
        self.pitch: float = 0.0
        self.yaw: float = 0.0
        self.roll: float = 0.0
        self.error_x: int = 0
        self.error_y: int = 0
        self.tracking_mode: str = "IDLE"
        self.laser_armed: bool = False
        self.laser_firing: bool = False
        self.laser_power: int = 100
        self.fps: float = 0.0
        self.latency_ms: float = 8.0
        self.voltage_v: float = 12.4
        self.temperature_c: float = 38.2
        self.system_state: str = "READY"
        self.detections: List[Dict[str, Any]] = []
        
        # Camera & Vision State
        self.camera_id: int = getattr(VisionConfig, "CAMERA_ID", 0)
        self.frame_width: int = getattr(VisionConfig, "FRAME_WIDTH", 640)
        self.frame_height: int = getattr(VisionConfig, "FRAME_HEIGHT", 480)
        self.target_fps: int = getattr(VisionConfig, "TARGET_FPS", 60)
        self.is_camera_live: bool = False
        self.flip_mode: str = getattr(VisionConfig, "FLIP_MODE", "NONE")
        self.available_cameras: List[Dict[str, Any]] = []
        self.available_ports: List[Dict[str, Any]] = []

        # Callbacks
        self.on_switch_camera_cb = None
        self.on_scan_cameras_cb = None
        self.on_scan_ports_cb = None

        self.last_broadcast_time = time.monotonic()
        self._setup_signals()

    def _setup_signals(self):
        """Hook into PyQt / Controller signals if available"""
        if self.gimbal_controller:
            try:
                self.gimbal_controller.position_update_signal.connect(self._on_position_update)
            except Exception:
                pass

    def _on_position_update(self, x: float, y: float):
        self.yaw = x
        self.pitch = y

    def get_telemetry_dict(self) -> Dict[str, Any]:
        connected = False
        port = "DISCONNECTED"
        if self.serial_thread:
            connected = self.serial_thread.is_connected()
            if self.serial_thread.serial_port and self.serial_thread.serial_port.port:
                port = str(self.serial_thread.serial_port.port)

        # Pull latest values from gimbal controller if present
        if self.gimbal_controller:
            self.error_x = getattr(self.gimbal_controller, "current_error_x", 0)
            self.error_y = getattr(self.gimbal_controller, "current_error_y", 0)
            self.yaw = getattr(self.gimbal_controller, "servo_x", self.yaw)
            self.pitch = getattr(self.gimbal_controller, "servo_y", self.pitch)

        if self.vision_worker:
            self.fps = getattr(self.vision_worker, "current_fps", self.fps)
            self.tracking_mode = getattr(self.vision_worker, "mode", self.tracking_mode)

        # Calculate system state
        if self.laser_firing:
            self.system_state = "LOCKED"
        elif self.tracking_mode in ("YOLO_TRACKING", "COLOR_TRACKING", "BLUE_TRACKING"):
            if abs(self.error_x) > 0 or abs(self.error_y) > 0:
                self.system_state = "TRACKING"
            else:
                self.system_state = "SEARCHING"
        else:
            self.system_state = "READY"

        return {
            "timestamp": int(time.time() * 1000),
            "connected": connected,
            "port": port,
            "pitch": round(self.pitch, 2),
            "yaw": round(self.yaw, 2),
            "roll": round(self.roll, 2),
            "error_x": self.error_x,
            "error_y": self.error_y,
            "tracking_mode": self.tracking_mode,
            "laser_armed": self.laser_armed,
            "laser_firing": self.laser_firing,
            "laser_power": self.laser_power,
            "fps": round(self.fps, 1),
            "target_fps": self.target_fps,
            "resolution": f"{self.frame_width}x{self.frame_height}",
            "latency_ms": round(self.latency_ms, 1),
            "temperature_c": round(self.temperature_c, 1),
            "voltage_v": round(self.voltage_v, 1),
            "system_state": self.system_state,
            "detections": self.detections,
            "camera_id": self.camera_id,
            "is_camera_live": self.is_camera_live,
            "flip_mode": self.flip_mode,
            "available_cameras": self.available_cameras,
            "available_ports": self.available_ports,
            "pid": {
                "kp": getattr(ControlConfig, "KP", 0.60),
                "ki": getattr(ControlConfig, "KI", 0.16),
                "kd": getattr(ControlConfig, "KD", 0.50),
            },
        }

    async def connect_client(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"[WEB] New client connected. Total clients: {len(self.active_connections)}")
        # Send instant telemetry upon connection
        try:
            payload = json.dumps(self.get_telemetry_dict())
            await websocket.send_text(payload)
        except Exception:
            pass

    def disconnect_client(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"[WEB] Client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast_telemetry(self):
        """Broadcast current telemetry snapshot to all connected clients"""
        if not self.active_connections:
            return

        def _json_default(obj):
            if isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float32, np.float64)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return str(obj)

        payload = json.dumps(self.get_telemetry_dict(), default=_json_default)
        dead_connections = set()

        for ws in self.active_connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.add(ws)

        for ws in dead_connections:
            self.active_connections.discard(ws)

    def handle_command(self, cmd_data: Dict[str, Any]):
        """Execute commands received from the WebUI"""
        action = cmd_data.get("action")
        payload = cmd_data.get("payload", {})

        logger.info(f"[WEB CMD] Action: {action}, Payload: {payload}")

        if action == "SET_MODE":
            mode = payload.get("mode", "IDLE")
            self.tracking_mode = mode
            if self.vision_worker:
                self.vision_worker.set_mode(mode)
            if self.gimbal_controller:
                is_tracking = mode in ("YOLO_TRACKING", "COLOR_TRACKING")
                self.gimbal_controller.set_control_enabled(is_tracking)

        elif action == "ARM_LASER":
            armed = payload.get("armed", False)
            self.laser_armed = armed
            if not armed and self.laser_firing:
                self.laser_firing = False
                self._send_laser_command(False)

        elif action == "FIRE_LASER":
            if self.laser_armed:
                self.laser_firing = True
                self._send_laser_command(True)

        elif action == "STOP_LASER":
            self.laser_firing = False
            self._send_laser_command(False)

        elif action == "MANUAL_JOG":
            axis = payload.get("axis", "x")
            direction = payload.get("dir", 0)
            step = payload.get("step", 5)

            if axis == "x":
                self.yaw += direction * step
                if self.gimbal_controller:
                    self.gimbal_controller.servo_x = self.yaw
            elif axis == "y":
                self.pitch += direction * step
                if self.gimbal_controller:
                    self.gimbal_controller.servo_y = self.pitch

            # Send jog motion to serial
            if self.serial_thread and self.serial_thread.is_connected():
                speed = 260 if axis == "x" else 40
                sim_err = speed * direction
                cmd = f"<{sim_err},0,0>\n" if axis == "x" else f"<0,{sim_err},0>\n"
                self.serial_thread.send_realtime_command(cmd)

        elif action == "CENTER":
            self.yaw = 0.0
            self.pitch = 0.0
            if self.gimbal_controller:
                self.gimbal_controller.servo_x = 0.0
                self.gimbal_controller.servo_y = 0.0
            if self.serial_thread and self.serial_thread.is_connected():
                self.serial_thread.send_center_command()

        elif action == "EMERGENCY_STOP":
            self.laser_firing = False
            self.laser_armed = False
            self._send_laser_command(False)
            if self.gimbal_controller:
                self.gimbal_controller.stop_motion("WebUI Emergency Stop Triggered")
            elif self.serial_thread and self.serial_thread.is_connected():
                self.serial_thread.send_stop_command()

        elif action == "UPDATE_PID":
            kp = float(payload.get("kp", 0.60))
            ki = float(payload.get("ki", 0.16))
            kd = float(payload.get("kd", 0.50))
            if self.gimbal_controller:
                self.gimbal_controller.update_pid_tunings(kp, ki, kd)
            else:
                ControlConfig.KP = kp
                ControlConfig.KI = ki
                ControlConfig.KD = kd

        elif action == "CONNECT_SERIAL":
            port = payload.get("port")
            baud = int(payload.get("baud", 115200))
            if not port and self.available_ports:
                # Pick first available or STM32 port
                stm32_ports = [p["device"] for p in self.available_ports if p.get("is_stm32")]
                port = stm32_ports[0] if stm32_ports else self.available_ports[0]["device"]
            
            if port and self.serial_thread:
                logger.info(f"[WEB] Connecting to serial port: {port} @ {baud} bps")
                self.serial_thread.connect_serial(port, baud)

        elif action == "DISCONNECT_SERIAL":
            if self.serial_thread:
                logger.info("[WEB] Disconnecting serial port...")
                self.serial_thread.disconnect_serial()

        elif action == "SCAN_PORTS":
            if self.on_scan_ports_cb:
                self.available_ports = self.on_scan_ports_cb()

        elif action == "SET_CAMERA":
            cam_id = int(payload.get("camera_id", 0))
            width = int(payload.get("width", self.frame_width))
            height = int(payload.get("height", self.frame_height))
            fps = int(payload.get("fps", self.target_fps))
            self.camera_id = cam_id
            if self.on_switch_camera_cb:
                self.on_switch_camera_cb(cam_id, width, height, fps)

        elif action == "SET_RESOLUTION":
            width = int(payload.get("width", 640))
            height = int(payload.get("height", 480))
            fps = int(payload.get("fps", 60))
            self.frame_width = width
            self.frame_height = height
            self.target_fps = fps
            VisionConfig.FRAME_WIDTH = width
            VisionConfig.FRAME_HEIGHT = height
            VisionConfig.TARGET_FPS = fps
            if self.on_switch_camera_cb:
                self.on_switch_camera_cb(self.camera_id, width, height, fps)

        elif action == "SCAN_CAMERAS":
            if getattr(self, "on_scan_cameras_cb", None):
                self.available_cameras = self.on_scan_cameras_cb()

        elif action == "SET_FLIP_MODE":
            flip = payload.get("flip_mode", "NONE")
            self.flip_mode = flip
            VisionConfig.FLIP_MODE = flip
            if self.vision_worker:
                self.vision_worker.set_flip_mode(flip)

    def _send_laser_command(self, fire: bool):
        if self.serial_thread and self.serial_thread.is_connected():
            cmd = "!LASER:1\n" if fire else "!LASER:0\n"
            self.serial_thread.send_command(cmd)
