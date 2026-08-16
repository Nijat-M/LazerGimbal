# -*- coding: utf-8 -*-
"""
Laser Gimbal (HSS) - Futuristic WebUI Backend Server (FastAPI)
Provides:
- Blue Color (HSV) Object Detector (TargetDetector) + YOLO Target Detector
- Real-time WebSockets for Telemetry and 3D Model Synchronization
- Low-latency MJPEG video streaming (/video_feed)
- REST API for Configuration, Serial Ports, and PID parameters
- Static SPA hosting of the React/Three.js WebUI
"""

import os
import sys
import time
import json
import asyncio
import argparse
import threading
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
import serial
import serial.tools.list_ports

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from utils.logger import Logger
from config.control_config import ControlConfig
from config.vision_config import VisionConfig
from vision.detector import TargetDetector, DetectionResult
from vision.yolo_detector import YOLODetector
from core.control.error_processor import ErrorProcessor
from core.web_bridge import WebBridge

logger = Logger("WebServer")

app = FastAPI(title="Lazer Gimbal HSS C2 Server", version="2.0.0")

# Enable CORS for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
bridge = WebBridge()
target_detector = TargetDetector()
error_processor = ErrorProcessor()
yolo_detector: Optional[YOLODetector] = None


def get_yolo_detector() -> Optional[YOLODetector]:
    global yolo_detector
    if yolo_detector is None:
        try:
            logger.info("[YOLO] Initializing YOLO Detector...")
            yolo_detector = YOLODetector()
        except Exception as e:
            logger.error(f"[YOLO ERROR] Could not initialize YOLO: {e}")
    return yolo_detector


# Video & Camera State
cap: Optional[cv2.VideoCapture] = None
camera_lock = threading.Lock()
current_camera_id: int = VisionConfig.CAMERA_ID
latest_frame_bytes: Optional[bytes] = None
is_camera_live: bool = False


def init_camera(preferred_id: int = 0) -> bool:
    """Initialize physical camera device"""
    global cap, is_camera_live, current_camera_id
    with camera_lock:
        if cap is not None and cap.isOpened():
            cap.release()

        # If user explicitly picks simulation (-1), switch to simulation
        if preferred_id == -1:
            cap = None
            is_camera_live = False
            current_camera_id = -1
            bridge.camera_id = -1
            bridge.is_camera_live = False
            logger.info("[CAMERA] Switched to High-Tech Simulation Feed Mode.")
            return True

        for cam_id in [preferred_id, 0, 1, 2]:
            try:
                test_cap = cv2.VideoCapture(cam_id)
                if test_cap.isOpened():
                    test_cap.set(cv2.CAP_PROP_FRAME_WIDTH, VisionConfig.FRAME_WIDTH)
                    test_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VisionConfig.FRAME_HEIGHT)
                    test_cap.set(cv2.CAP_PROP_FPS, VisionConfig.TARGET_FPS)
                    
                    ret, test_frame = test_cap.read()
                    if ret and test_frame is not None:
                        cap = test_cap
                        current_camera_id = cam_id
                        is_camera_live = True
                        bridge.camera_id = cam_id
                        bridge.is_camera_live = True
                        logger.info(f"[CAMERA] ✓ Successfully opened Camera ID: {cam_id}")
                        return True
                    test_cap.release()
            except Exception as e:
                logger.warning(f"[CAMERA] Could not open camera {cam_id}: {e}")

        cap = None
        is_camera_live = False
        bridge.is_camera_live = False
        logger.warning("[CAMERA] No physical camera found. Using high-tech simulation mode.")
        return False

# Register callback with WebBridge
bridge.on_switch_camera_cb = init_camera



def generate_simulated_frame(pitch: float, yaw: float, is_laser_firing: bool, mode: str):
    """Generate realistic sci-fi tactical EO/IR video feed when physical camera is offline"""
    w, h = VisionConfig.FRAME_WIDTH, VisionConfig.FRAME_HEIGHT
    frame = np.zeros((h, w, 3), dtype=np.uint8)

    # Dark tactical thermal background
    frame[:] = (16, 12, 8)

    # Draw grid lines
    for x in range(0, w, 40):
        cv2.line(frame, (x, 0), (x, h), (30, 24, 16), 1)
    for y in range(0, h, 40):
        cv2.line(frame, (0, y), (w, y), (30, 24, 16), 1)

    t = time.time()

    # If in COLOR_TRACKING / BLUE_TRACKING mode, draw a blue simulated target object
    if mode in ("COLOR_TRACKING", "BLUE_TRACKING"):
        blue_x = int(w / 2 + np.sin(t * 1.0) * 130 - (yaw * 2.5))
        blue_y = int(h / 2 + np.cos(t * 1.3) * 70 + (pitch * 2.5))
        radius = 22

        # Draw real blue circle in BGR: (255, 100, 20) -> (B, G, R)
        cv2.circle(frame, (blue_x, blue_y), radius, (255, 120, 20), -1)
        cv2.circle(frame, (blue_x, blue_y), radius + 2, (255, 200, 50), 2)

        # Run actual TargetDetector to verify detector algorithm!
        blue_res, _ = target_detector.detect_blue_object(frame)
        if blue_res.detected and blue_res.position:
            pos = blue_res.position
            # Draw tracking overlay
            cv2.circle(frame, pos, int(blue_res.radius or radius), (0, 240, 255), 2)
            cv2.putText(frame, "BLUE TARGET", (pos[0] - 35, pos[1] - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 240, 255), 1)
            cv2.arrowedLine(frame, (w // 2, h // 2), pos, (0, 255, 100), 1)

            err_x = pos[0] - (w // 2)
            err_y = pos[1] - (h // 2)
            bridge.error_x = err_x
            bridge.error_y = err_y

            is_locked = abs(err_x) < 25 and abs(err_y) < 25
            bridge.detections = [
                {
                    "label": "BLUE TARGET",
                    "confidence": 0.98,
                    "bbox": [pos[0], pos[1], (blue_res.radius or radius) * 2, (blue_res.radius or radius) * 2],
                    "is_locked": is_locked or is_laser_firing,
                    "distance_m": 12.4,
                }
            ]
        else:
            bridge.detections = []
            bridge.error_x = 0
            bridge.error_y = 0

    else:
        # Generic Simulated Drone Target
        drone_x = int(w / 2 + np.sin(t * 1.2) * 120 - (yaw * 3))
        drone_y = int(h / 2 + np.cos(t * 1.5) * 60 + (pitch * 3))

        bridge.error_x = drone_x - (w // 2)
        bridge.error_y = drone_y - (h // 2)

        is_locked = abs(bridge.error_x) < 25 and abs(bridge.error_y) < 25
        bridge.detections = [
            {
                "label": "TARGET DRONE-X1",
                "confidence": 0.94 + np.sin(t * 3) * 0.04,
                "bbox": [drone_x, drone_y, 70, 45],
                "is_locked": is_locked or is_laser_firing,
                "distance_m": 18.5,
            }
        ]

        # Draw Drone Silhouette
        cv2.circle(frame, (drone_x, drone_y), 18, (0, 240, 255), 2)
        cv2.line(frame, (drone_x - 30, drone_y), (drone_x + 30, drone_y), (0, 240, 255), 2)
        cv2.line(frame, (drone_x, drone_y - 12), (drone_x, drone_y + 12), (0, 240, 255), 2)

    # Laser strike point if firing
    if is_laser_firing and bridge.detections:
        target_pos = (bridge.detections[0]["bbox"][0], bridge.detections[0]["bbox"][1])
        cv2.line(frame, (w // 2, h // 2), target_pos, (0, 0, 255), 3)
        cv2.circle(frame, target_pos, 24, (0, 50, 255), -1)

    # Encode to JPEG
    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return jpeg.tobytes()


def process_camera_frame(frame: np.ndarray) -> bytes:
    """Process physical camera frame with Blue Object Detection or YOLO"""
    h, w = frame.shape[:2]
    cx = w // 2
    cy = h // 2

    mode = bridge.tracking_mode

    # Flip mode handling
    flip_mode = getattr(VisionConfig, "FLIP_MODE", "NONE")
    if flip_mode == "180":
        frame = cv2.flip(frame, -1)
    elif flip_mode == "V":
        frame = cv2.flip(frame, 0)
    elif flip_mode == "H":
        frame = cv2.flip(frame, 1)

    # 1. BLUE OBJECT DETECTION (TargetDetector)
    if mode in ("COLOR_TRACKING", "BLUE_TRACKING"):
        blue_result, _ = target_detector.detect_blue_object(frame)

        if blue_result.detected and blue_result.position:
            pos = blue_result.position
            rad = int(blue_result.radius or 20)

            # Draw blue target marker and tracking vector
            cv2.circle(frame, pos, rad, (255, 0, 0), 2)
            cv2.circle(frame, pos, 4, (0, 255, 255), -1)
            cv2.putText(
                frame,
                f"BLUE TARGET [{pos[0]},{pos[1]}]",
                (pos[0] - 40, pos[1] - rad - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 240, 255),
                1,
            )
            cv2.arrowedLine(frame, (cx, cy), pos, (0, 255, 0), 2)

            raw_err_x = pos[0] - cx
            raw_err_y = pos[1] - cy

            proc_x, proc_y = error_processor.process(raw_err_x, raw_err_y)
            bridge.error_x = proc_x
            bridge.error_y = proc_y

            is_locked = abs(proc_x) < 20 and abs(proc_y) < 20

            bridge.detections = [
                {
                    "label": "BLUE TARGET",
                    "confidence": 0.98,
                    "bbox": [pos[0], pos[1], rad * 2, rad * 2],
                    "is_locked": is_locked or bridge.laser_firing,
                    "distance_m": 10.0,
                }
            ]

            # Send automated motion command to gimbal if tracking enabled
            if bridge.system_state in ("TRACKING", "LOCKED"):
                scale_x = getattr(ControlConfig, "TRACKING_SCALE_X", 1.2)
                scale_y = getattr(ControlConfig, "TRACKING_SCALE_Y", 0.45)
                invert_y = getattr(ControlConfig, "INVERT_Y", True)
                
                cmd_y = -proc_y if invert_y else proc_y
                motion_cmd = f"<{int(proc_x * scale_x)},{int(cmd_y * scale_y)},0>\n"
                if bridge.serial_thread and bridge.serial_thread.is_connected():
                    bridge.serial_thread.send_realtime_command(motion_cmd)
        else:
            bridge.detections = []
            bridge.error_x = 0
            bridge.error_y = 0
            error_processor.reset()

    # 2. YOLO AI DEEP LEARNING TARGET DETECTION
    elif mode == "YOLO_TRACKING":
        yd = get_yolo_detector()
        if yd is not None:
            yolo_res = yd.detect_target(frame)
            if yolo_res.detected and yolo_res.position:
                pos = yolo_res.position
                x1, y1, x2, y2 = yolo_res.box or (pos[0] - 25, pos[1] - 25, pos[0] + 25, pos[1] + 25)
                bw = max(20, x2 - x1)
                bh = max(20, y2 - y1)

                label_name = "TARGET"
                if hasattr(yd, "model") and yd.model and hasattr(yd.model, "names") and yolo_res.class_id is not None:
                    label_name = yd.model.names.get(yolo_res.class_id, f"CLS_{yolo_res.class_id}")

                conf = float(yolo_res.confidence or 0.92)

                # Draw YOLO bounding box & label
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.circle(frame, pos, 4, (0, 255, 255), -1)
                cv2.putText(
                    frame,
                    f"{label_name.upper()} {conf:.2f}",
                    (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    2,
                )
                cv2.arrowedLine(frame, (cx, cy), pos, (0, 255, 100), 2)

                raw_err_x = pos[0] - cx
                raw_err_y = pos[1] - cy

                proc_x, proc_y = error_processor.process(raw_err_x, raw_err_y)
                bridge.error_x = proc_x
                bridge.error_y = proc_y

                is_locked = abs(proc_x) < 25 and abs(proc_y) < 25

                bridge.detections = [
                    {
                        "label": label_name.upper(),
                        "confidence": conf,
                        "bbox": [pos[0], pos[1], bw, bh],
                        "is_locked": is_locked or bridge.laser_firing,
                        "distance_m": 15.0,
                    }
                ]

                # Send automated motion command to gimbal if tracking enabled
                if bridge.system_state in ("TRACKING", "LOCKED"):
                    scale_x = getattr(ControlConfig, "TRACKING_SCALE_X", 1.2)
                    scale_y = getattr(ControlConfig, "TRACKING_SCALE_Y", 0.45)
                    invert_y = getattr(ControlConfig, "INVERT_Y", True)
                    
                    cmd_y = -proc_y if invert_y else proc_y
                    motion_cmd = f"<{int(proc_x * scale_x)},{int(cmd_y * scale_y)},0>\n"
                    if bridge.serial_thread and bridge.serial_thread.is_connected():
                        bridge.serial_thread.send_realtime_command(motion_cmd)
            else:
                bridge.detections = []
                bridge.error_x = 0
                bridge.error_y = 0
                error_processor.reset()
        else:
            bridge.detections = []
            bridge.error_x = 0
            bridge.error_y = 0

    # Draw Laser Strike on Camera Feed if firing

    if bridge.laser_firing and bridge.detections:
        target_pos = (bridge.detections[0]["bbox"][0], bridge.detections[0]["bbox"][1])
        cv2.line(frame, (cx, cy), target_pos, (0, 0, 255), 3)
        cv2.circle(frame, target_pos, 20, (0, 0, 255), -1)

    # Encode to JPEG
    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return jpeg.tobytes()


def video_stream_generator():
    """Generator for MJPEG stream (/video_feed)"""
    global cap, is_camera_live
    prev_time = time.time()

    while True:
        frame_bytes = None
        if is_camera_live and cap is not None and cap.isOpened():
            with camera_lock:
                ret, frame = cap.read()
            if ret and frame is not None:
                frame_bytes = process_camera_frame(frame)
            else:
                is_camera_live = False

        if frame_bytes is None:
            # Simulation stream with Blue Target detection demo
            frame_bytes = generate_simulated_frame(
                pitch=bridge.pitch,
                yaw=bridge.yaw,
                is_laser_firing=bridge.laser_firing,
                mode=bridge.tracking_mode,
            )

        # Calculate FPS
        curr_time = time.time()
        dt = curr_time - prev_time
        prev_time = curr_time
        if dt > 0:
            bridge.fps = 1.0 / dt

        # Yield frame in multipart MJPEG format
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
        )

        time.sleep(0.030)  # ~33 FPS


@app.get("/video_feed")
def video_feed():
    """MJPEG Video stream endpoint for WebUI"""
    return StreamingResponse(
        video_stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """WebSocket for bidirectional real-time telemetry and command control"""
    await bridge.connect_client(websocket)
    try:
        while True:
            # Receive client commands
            data_text = await websocket.receive_text()
            try:
                cmd_data = json.loads(data_text)
                bridge.handle_command(cmd_data)
            except Exception as e:
                logger.error(f"[WS ERROR] Command parse failed: {e}")
    except WebSocketDisconnect:
        bridge.disconnect_client(websocket)
    except Exception as e:
        logger.error(f"[WS ERROR] Connection exception: {e}")
        bridge.disconnect_client(websocket)


async def telemetry_broadcast_loop():
    """Background task to broadcast telemetry to WebSockets at 30Hz"""
    while True:
        try:
            await bridge.broadcast_telemetry()
        except Exception as e:
            logger.error(f"[TELEMETRY ERROR] Broadcast failure: {e}")
        await asyncio.sleep(0.033)


@app.on_event("startup")
async def startup_event():
    logger.info("[SERVER] Initializing Camera and Vision Systems...")
    init_camera(VisionConfig.CAMERA_ID)
    logger.info("[SERVER] Starting background telemetry broadcaster...")
    asyncio.create_task(telemetry_broadcast_loop())


@app.get("/api/status")
def get_status():
    return bridge.get_telemetry_dict()


@app.get("/api/ports")
def list_serial_ports():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    return {"ports": ports}


@app.post("/api/camera/switch")
def switch_camera(camera_id: int):
    success = init_camera(camera_id)
    return {"success": success, "camera_id": camera_id, "live": is_camera_live}


# Serve React SPA static build if exists
webui_dist_path = os.path.join(os.path.dirname(__file__), "webui", "dist")
if os.path.exists(webui_dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(webui_dist_path, "assets")), name="assets")

    @app.get("/")
    def serve_spa():
        return FileResponse(os.path.join(webui_dist_path, "index.html"))


def main():
    parser = argparse.ArgumentParser(description="Lazer Gimbal WebUI Backend Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--cam", type=int, default=0, help="Camera ID (default: 0)")
    args = parser.parse_args()

    VisionConfig.CAMERA_ID = args.cam

    print(f"\n=======================================================")
    print(f"🎯 LAZER GIMBAL // TEKNOFEST HSS C2 COMMAND SERVER")
    print(f"📡 Backend & WebUI URL: http://localhost:{args.port}")
    print(f"👁️ Mavi Renk & Hedef Tanıma (TargetDetector): AKTİF")
    print(f"=======================================================\n")

    uvicorn.run("web_server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
