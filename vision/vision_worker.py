# -*- coding: utf-8 -*-
"""
视觉处理线程 (Vision Worker Thread)

职责（单一职责原则）：
1. 管理摄像头（打开/关闭/切换）
2. 采集图像帧
3. 调用 TargetDetector 检测目标
4. 绘制可视化信息（标记框、箭头、十字线）
5. 发送原始坐标或误差信号给控制器

不包含：
- 死区判断
- 误差缩放
- 任何PID/控制相关逻辑
"""

import os
import sys
import threading
import math
import time
from datetime import datetime
from collections import deque

# 抑制 OpenCV 警告
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'

# 核心修改：在 Windows 下，必须先加载 torch（YOLO 会加载）再加载 cv2，否则可能导致 c10.dll 初始化失败
from vision.yolo_detector import AsyncYOLODetector, YOLODetector

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt6.QtGui import QImage

from config.vision_config import VisionConfig
from vision.detector import TargetDetector
from vision.iff import iff_analiz, IFF_BGR, IFF_ETIKET, ENEMY, FRIENDLY, NEUTRAL
from utils.logger import Logger

logger = Logger("VisionWorker")


class VisionWorker(QThread):
    """
    视觉处理线程

    信号说明：
        frame_signal      : 发送处理后的画面（给 UI 显示）
        mask_signal       : 发送调试蒙版（给 UI 调试显示）
        target_pos_signal : 发送目标位置 (pos_x, pos_y)（物体居中追踪）
        stats_signal      : 发送实时统计数据 (fps, width, height)
    """

    frame_signal = pyqtSignal(QImage)       # 处理后的画面
    mask_signal = pyqtSignal(QImage)        # 调试蒙版
    target_pos_signal = pyqtSignal(int, int)  # 物体追踪原始坐标
    stats_signal = pyqtSignal(float, int, int) # (fps, width, height)
    camera_state_signal = pyqtSignal(int, bool, str) # (request generation, ready, message)
    iff_signal = pyqtSignal(dict)   # Yetenek 7: dost/dusman durumu / 敌我态势
    detections_signal = pyqtSignal(list) # Yetenek 6/7: 完整检测目标列表 (给裁判UI表格展示)
    recording_status_signal = pyqtSignal(str, str, int) # (state: 'IDLE'/'RECORDING'/'PAUSED', file_path, elapsed_seconds)
    laser_fire_request_signal = pyqtSignal(bool, int)   # (firing: bool, power: int) 自动打击开火请求

    def __init__(self):
        super().__init__()
        self.is_running: bool = True
        self.mode: str = "IDLE"
        self.balloon_firing: bool = False
        self._active_balloon_pos: tuple[int, int] | None = None
        self._active_balloon_missing_count: int = 0
        self._eliminated_balloon_count: int = 0
        self._balloon_tracks: dict = {}
        self._next_balloon_id: int = 1
        self.cap = None
        self.camera_id: int = VisionConfig.CAMERA_ID
        self.frame_width: int = VisionConfig.FRAME_WIDTH
        self.frame_height: int = VisionConfig.FRAME_HEIGHT
        self.camera_ready: bool = False

        # 第二屏幕：准星画中画局部放大镜 (PiP Digital Zoom Reticle Scope)
        self.pip_enabled: bool = True
        self.pip_zoom: float = 3.0          # 默认放大倍数 3.0x (可调 1.5x ~ 6.0x)

        # 屏幕/视频录制系统 (Record / Pause / Stop System)
        self.recording_state: str = "IDLE"  # "IDLE", "RECORDING", "PAUSED"
        self.video_writer = None
        self.recording_start_time: float = 0.0
        self.recording_paused_time: float = 0.0
        self.recording_total_paused_sec: float = 0.0
        self.writer_w: int = 0
        self.writer_h: int = 0
        self._rec_lock = threading.Lock()
        self._last_rec_sec: int = -1
        self._recording_fps: float = 30.0
        self._recording_frames_written: int = 0

        # 麦克风录音系统 (Microphone Audio Capture)
        self._audio_stream = None
        self._audio_wave_file = None
        self._audio_temp_path: str = ""
        self._video_temp_path: str = ""
        self._audio_samplerate: int = 44100
        self._audio_channels: int = 1

        # 电机与激光状态遥测（用于录制视频 HUD 水印叠加，全英文）
        self.telemetry_pan: float = 0.0
        self.telemetry_tilt: float = 0.0
        self.telemetry_laser_armed: bool = False
        self.telemetry_laser_firing: bool = False
        self.telemetry_laser_pwr: int = 100
        self.speed_gear: int = 2

        # 检测器（纯视觉，无控制逻辑）
        self.detector = TargetDetector()
        
        # YOLO检测器与配置
        self.yolo_detector = None
        self.yolo_model_path: str = getattr(VisionConfig, "DEFAULT_YOLO_MODEL", "vision/models/savunma_yolo26.pt")
        self.yolo_target_class = getattr(VisionConfig, "YOLO_TARGET_CLASS", None)
        self.yolo_conf_threshold: float = getattr(VisionConfig, "YOLO_CONF_THRESHOLD", 0.35)

        # ---- Yetenek 7: dost/dusman (IFF) ----
        from vision.iff import IFFKarari
        self.iff_enabled: bool = True
        self._iff = IFFKarari()

        # 状态跟踪（避免重复打印）
        self.blue_object_detected = False   # 蓝色物体检测状态
        self.flip_mode: str = getattr(VisionConfig, "FLIP_MODE", "NONE")

        # FPS 计算相关
        self.prev_time = time.time()
        self.fps_queue = deque(maxlen=20)  # 平滑 FPS
        self.current_fps = 0

        # 线程安全标志，用于异步打开摄像头
        self._camera_request_lock = threading.Lock()
        self._camera_request_generation = 0
        self._need_reconnect = False
        self._need_close = False
        self._pending_id = -1
        self._pending_w = 640
        self._pending_h = 480

    def update_telemetry_pos(self, pan: float, tilt: float) -> None:
        """更新云台当前角度数据 (Pan, Tilt in degrees)"""
        self.telemetry_pan = float(pan)
        self.telemetry_tilt = float(tilt)

    def update_telemetry_laser(self, armed: bool, firing: bool, pwr: int = 100) -> None:
        """更新激光武器状态 (Armed, Firing, Power %)"""
        self.telemetry_laser_armed = bool(armed)
        self.telemetry_laser_firing = bool(firing)
        self.telemetry_laser_pwr = int(pwr)

    def set_speed_gear(self, gear: int) -> None:
        """设置电机速度档位 (1: 0.3x, 2: 1.0x, 3: 2.2x)"""
        self.speed_gear = max(1, min(3, int(gear)))

    def is_recording(self) -> bool:
        """是否正在录像或暂停中"""
        return self.recording_state in ("RECORDING", "PAUSED")

    # --------------------------------------------------
    # 公共接口
    # --------------------------------------------------

    def set_flip_mode(self, flip_mode: str) -> None:
        """设置画面翻转模式: 'NONE'(正常), '180'(180°倒装翻转), 'V'(垂直翻转), 'H'(水平镜像)"""
        self.flip_mode = flip_mode
        VisionConfig.FLIP_MODE = flip_mode
        logger.info(f"[VISION] 画面翻转模式更新为: {flip_mode}")

    def set_mode(self, mode: str) -> None:
        """设置工作模式"""
        if self.mode == "BALLOON_HUNT" and mode != "BALLOON_HUNT":
            if self.balloon_firing:
                self.balloon_firing = False
                self.laser_fire_request_signal.emit(False, 0)
        self.mode = mode
        if mode == "BALLOON_HUNT":
            self._active_balloon_pos = None
            self._active_balloon_missing_count = 0
            self._eliminated_balloon_count = 0
        if mode == "YOLO_TRACKING" and self.yolo_detector is None:
            logger.info(f"[VISION] 正在初始化 YOLO 异步深度学习引擎 (模型: {self.yolo_model_path})...")
            self.yolo_detector = AsyncYOLODetector(
                self.yolo_model_path, 
                conf_threshold=self.yolo_conf_threshold
            )
            self.yolo_detector.set_target_class(self.yolo_target_class)
            logger.info("[VISION] YOLO 异步引擎初始化完成。")
        self._iff.temizle()
        logger.info(f"[VISION] 视觉线程模式: {mode}")

    def set_yolo_model(self, model_path: str) -> None:
        """动态切换 YOLO 模型"""
        self.yolo_model_path = model_path
        if self.yolo_detector is not None:
            logger.info(f"[VISION] 正在热切换 YOLO 模型至: {model_path}")
            self.yolo_detector.set_model(model_path)

    def set_yolo_target_class(self, target_class) -> None:
        """设置 YOLO 追踪的目标类别过滤 (None 为追踪所有目标)"""
        self.yolo_target_class = target_class
        if self.yolo_detector is not None:
            self.yolo_detector.set_target_class(target_class)
            logger.info(f"[VISION] YOLO 目标过滤类别已更新为: {target_class}")

    def set_yolo_conf_threshold(self, conf: float) -> None:
        """设置 YOLO 检测置信度阈值"""
        self.yolo_conf_threshold = conf
        if self.yolo_detector is not None:
            self.yolo_detector.set_conf_threshold(conf)
            logger.info(f"[VISION] YOLO 置信度阈值已更新为: {conf:.2f}")

    def set_pip_zoom(self, zoom: float) -> None:
        """设置第二屏幕准星放大倍数 (1.5x ~ 6.0x)"""
        self.pip_zoom = max(1.5, min(6.0, float(zoom)))
        logger.info(f"[VISION] 准星画中画放大倍数已设定为: {self.pip_zoom:.1f}x")

    def set_pip_enabled(self, enabled: bool) -> None:
        """开启/关闭左上角第二屏幕画中画"""
        self.pip_enabled = bool(enabled)
        logger.info(f"[VISION] 准星画中画状态: {'开启' if self.pip_enabled else '关闭'}")

    def start_recording(self, output_dir: str = "recordings") -> bool:
        """开始录制屏幕视频"""
        with self._rec_lock:
            if self.recording_state != "IDLE":
                return True
            try:
                os.makedirs(output_dir, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                fps = max(15.0, min(60.0, float(self.current_fps or 30.0)))
                w = self.frame_width if self.frame_width > 0 else 640
                h = self.frame_height if self.frame_height > 0 else 480
                w = w if (w % 2 == 0) else w - 1
                h = h if (h % 2 == 0) else h - 1
                self.writer_w = w
                self.writer_h = h

                self.recording_path = os.path.join(output_dir, f"rec_{timestamp}.mp4")
                self._video_temp_path = os.path.join(output_dir, f"temp_v_{timestamp}.mp4")
                self._audio_temp_path = os.path.join(output_dir, f"temp_a_{timestamp}.wav")

                self._recording_fps = 30.0
                self._recording_frames_written = 0

                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                self.video_writer = cv2.VideoWriter(self._video_temp_path, fourcc, self._recording_fps, (w, h))
                if not self.video_writer.isOpened():
                    fourcc = cv2.VideoWriter_fourcc(*'avc1')
                    self.video_writer = cv2.VideoWriter(self._video_temp_path, fourcc, self._recording_fps, (w, h))
                if not self.video_writer.isOpened():
                    self._video_temp_path = os.path.join(output_dir, f"temp_v_{timestamp}.avi")
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    self.video_writer = cv2.VideoWriter(self._video_temp_path, fourcc, self._recording_fps, (w, h))

                # 启动麦克风录音 (Microphone Stream)
                try:
                    import sounddevice as sd
                    import wave
                    self._audio_wave_file = wave.open(self._audio_temp_path, 'wb')
                    self._audio_wave_file.setnchannels(self._audio_channels)
                    self._audio_wave_file.setsampwidth(2) # 16-bit PCM
                    self._audio_wave_file.setframerate(self._audio_samplerate)

                    def _audio_callback(indata, frames, time_info, status):
                        if self.recording_state == "RECORDING" and self._audio_wave_file is not None:
                            try:
                                self._audio_wave_file.writeframes(indata)
                            except Exception:
                                pass

                    self._audio_stream = sd.InputStream(
                        samplerate=self._audio_samplerate,
                        channels=self._audio_channels,
                        dtype='int16',
                        callback=_audio_callback
                    )
                    self._audio_stream.start()
                    logger.info("[VISION] 🎙️ 麦克风环境声音录制已成功启动")
                except Exception as audio_err:
                    logger.warning(f"[VISION] 麦克风录音初始化跳过: {audio_err}")
                    self._audio_stream = None
                    self._audio_wave_file = None

                self.recording_state = "RECORDING"
                self.recording_start_time = time.time()
                self.recording_paused_time = 0.0
                self.recording_total_paused_sec = 0.0
                self._last_rec_sec = -1
                logger.info(f"[VISION] 🔴 开始录制视音频: {self.recording_path} ({w}x{h} @ {fps:.1f}fps)")
                self.recording_status_signal.emit("RECORDING", self.recording_path, 0)
                return True
            except Exception as e:
                logger.error(f"[VISION ERROR] 启动录像失败: {e}")
                self.is_recording = False
                return False

    def pause_recording(self) -> bool:
        """暂停 / 继续录制屏幕视频"""
        with self._rec_lock:
            now = time.time()
            if self.recording_state == "RECORDING":
                self.recording_state = "PAUSED"
                self.recording_paused_time = now
                elapsed = max(0, int(now - self.recording_start_time - self.recording_total_paused_sec))
                logger.info(f"[VISION] ⏸ 视频录制已暂停 (时长: {elapsed}s)")
                self.recording_status_signal.emit("PAUSED", self.recording_path, elapsed)
                return True
            elif self.recording_state == "PAUSED":
                self.recording_state = "RECORDING"
                if self.recording_paused_time > 0:
                    self.recording_total_paused_sec += (now - self.recording_paused_time)
                self.recording_paused_time = 0.0
                elapsed = max(0, int(now - self.recording_start_time - self.recording_total_paused_sec))
                logger.info(f"[VISION] ▶ 视频录制已继续...")
                self.recording_status_signal.emit("RECORDING", self.recording_path, elapsed)
                return True
            return False

    def stop_recording(self) -> str:
        """停止录制屏幕视频并保存"""
        with self._rec_lock:
            if self.recording_state == "IDLE":
                return ""
            now = time.time()
            if self.recording_state == "PAUSED" and self.recording_paused_time > 0:
                self.recording_total_paused_sec += (now - self.recording_paused_time)

            elapsed = max(0, int(now - self.recording_start_time - self.recording_total_paused_sec))
            self.recording_state = "IDLE"
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None

            # 停止麦克风音频流并关闭文件
            has_audio = False
            if self._audio_stream is not None:
                try:
                    self._audio_stream.stop()
                    self._audio_stream.close()
                except Exception:
                    pass
                self._audio_stream = None

            if self._audio_wave_file is not None:
                try:
                    self._audio_wave_file.close()
                    if os.path.exists(self._audio_temp_path) and os.path.getsize(self._audio_temp_path) > 1024:
                        has_audio = True
                except Exception:
                    pass
                self._audio_wave_file = None

            path = self.recording_path
            v_tmp = self._video_temp_path
            a_tmp = self._audio_temp_path

            def _mux_worker(v_file, a_file, out_file, with_audio):
                try:
                    if with_audio and os.path.exists(v_file) and os.path.exists(a_file):
                        import imageio_ffmpeg
                        import subprocess
                        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                        cmd = [
                            ffmpeg_exe, '-y',
                            '-i', v_file,
                            '-i', a_file,
                            '-c:v', 'copy',
                            '-c:a', 'aac',
                            '-b:a', '128k',
                            '-shortest',
                            out_file
                        ]
                        res = subprocess.run(cmd, capture_output=True, text=True)
                        if res.returncode == 0 and os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                            if os.path.exists(v_file): os.remove(v_file)
                            if os.path.exists(a_file): os.remove(a_file)
                            logger.info(f"[VISION] 🎬 麦克风环境声音与录像已成功合并输出: {out_file}")
                            return
                    if os.path.exists(v_file):
                        if os.path.exists(out_file):
                            os.remove(out_file)
                        os.rename(v_file, out_file)
                    if os.path.exists(a_file):
                        os.remove(a_file)
                except Exception as e:
                    logger.error(f"[VISION] 混音处理异常: {e}")

            threading.Thread(target=_mux_worker, args=(v_tmp, a_tmp, path, has_audio), daemon=True).start()

            logger.info(f"[VISION] ⏹ 录制结束并保存至: {path} (时长: {elapsed}s)")
            self.recording_status_signal.emit("IDLE", path, elapsed)
            return path


    def open_camera_settings(self) -> None:
        """打开 Windows DirectShow 原生相机属性设置面板 (调节全局快门曝光/增益等)"""
        if self.cap is not None and self.cap.isOpened():
            try:
                logger.info("[VISION] 正在打开 DirectShow 相机属性调节面板...")
                self.cap.set(cv2.CAP_PROP_SETTINGS, 1)
            except Exception as e:
                logger.error(f"[VISION ERROR] 打开相机设置面板失败: {e}")

    def switch_camera(self, camera_id: int, width: int, height: int) -> None:
        """Queue a generation-tagged camera-open request for the worker thread."""
        with self._camera_request_lock:
            self._camera_request_generation += 1
            generation = self._camera_request_generation
            self._pending_id = camera_id
            self._pending_w = width
            self._pending_h = height
            self._need_reconnect = True
            self._need_close = False
        self.camera_ready = False
        self.camera_state_signal.emit(generation, False, "正在打开摄像头...")

    def close_camera(self) -> None:
        """Request closure; only the vision thread may touch VideoCapture."""
        logger.info("[VISION] 正在关闭摄像头...")
        with self._camera_request_lock:
            self._camera_request_generation += 1
            generation = self._camera_request_generation
            self._need_close = True
            self._need_reconnect = False
        self.camera_ready = False
        self.camera_state_signal.emit(generation, False, "摄像头已关闭")

    def stop(self, timeout_ms: int = 5000) -> bool:
        """Request worker-owned cleanup and report whether the thread exited."""
        with self._camera_request_lock:
            self._camera_request_generation += 1
            generation = self._camera_request_generation
            self._need_close = True
            self._need_reconnect = False
        self.is_running = False
        self.camera_state_signal.emit(generation, False, "视觉线程已停止")
        self.quit()
        if not self.isRunning():
            return True
        return self.wait(timeout_ms)

    def _take_camera_request(self):
        with self._camera_request_lock:
            generation = self._camera_request_generation
            if self._need_close:
                self._need_close = False
                return ("close", generation, -1, 0, 0)
            if self._need_reconnect:
                self._need_reconnect = False
                return (
                    "open",
                    generation,
                    self._pending_id,
                    self._pending_w,
                    self._pending_h,
                )
        return None

    def _is_camera_request_current(self, generation: int) -> bool:
        with self._camera_request_lock:
            return self.is_running and generation == self._camera_request_generation

    def _do_switch_camera(
        self, generation: int, camera_id: int, width: int, height: int
    ) -> None:
        """Open and warm a candidate camera before atomically publishing it."""
        logger.info(f"[VISION] 正在后台打开摄像头: ID={camera_id}, {width}x{height}")
        self._close_camera_in_worker(emit_frame=False)

        candidate = None
        for attempt in range(3):
            if not self._is_camera_request_current(generation):
                return
            candidate = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            if candidate.isOpened():
                break
            candidate.release()
            time.sleep(0.15)

        if candidate is None or not candidate.isOpened():
            logger.info("[VISION] DSHOW后端未就绪，尝试默认后端...")
            candidate = cv2.VideoCapture(camera_id)

        if not candidate.isOpened():
            message = f"无法打开摄像头 ID={camera_id}"
            logger.error(f"[VISION ERROR] {message}")
            candidate.release()
            if self._is_camera_request_current(generation):
                self.camera_state_signal.emit(generation, False, message)
            return

        # 核心优化：先设置 FOURCC 为 MJPG 硬件压缩，再协商分辨率与高帧率
        target_fps = getattr(VisionConfig, "TARGET_FPS", 60)
        candidate.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        candidate.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        candidate.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        candidate.set(cv2.CAP_PROP_FPS, target_fps)
        candidate.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        valid_warmup_frames = 0
        for _ in range(15):
            if not self._is_camera_request_current(generation):
                candidate.release()
                return
            ret, frame = candidate.read()
            if ret and frame is not None:
                valid_warmup_frames += 1

        if valid_warmup_frames == 0:
            message = f"摄像头 ID={camera_id} 未返回有效画面"
            logger.error(f"[VISION ERROR] {message}")
            candidate.release()
            if self._is_camera_request_current(generation):
                self.camera_state_signal.emit(generation, False, message)
            return

        actual_w = int(candidate.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(candidate.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(candidate.get(cv2.CAP_PROP_FPS))
        actual_fourcc = int(candidate.get(cv2.CAP_PROP_FOURCC))
        f_str = (
            "".join(chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4))
            if actual_fourcc > 0
            else "DEFAULT"
        )

        if not self._is_camera_request_current(generation):
            candidate.release()
            return

        self.cap = candidate
        self.frame_width = actual_w
        self.frame_height = actual_h
        VisionConfig.FRAME_WIDTH = actual_w
        VisionConfig.FRAME_HEIGHT = actual_h
        VisionConfig.CENTER_X = actual_w // 2
        VisionConfig.CENTER_Y = actual_h // 2

        logger.info(
            f"[VISION] ✓ 摄像头就绪: {actual_w}x{actual_h} "
            f"@ {actual_fps}fps, 编码: {f_str}"
        )
        if 0 < actual_fps < VisionConfig.TARGET_FPS:
            logger.warning(f"[VISION] 环境光照可能不足，实际帧率: {actual_fps}")

        self.camera_ready = True
        self.camera_state_signal.emit(
            generation,
            True,
            f"摄像头就绪: {actual_w}x{actual_h} @ {actual_fps}fps",
        )

    def _close_camera_in_worker(self, emit_frame: bool = True) -> None:
        self.camera_ready = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if emit_frame:
            black_frame = QImage(
                self.frame_width,
                self.frame_height,
                QImage.Format.Format_RGB888,
            )
            black_frame.fill(0)
            self.frame_signal.emit(black_frame)
        logger.info("[VISION] 摄像头已关闭")

    # --------------------------------------------------
    # 主循环
    # --------------------------------------------------

    def run(self) -> None:
        """线程主循环"""
        logger.info("[VISION] 视觉线程已启动，等待指令...")
        error_count = 0

        while self.is_running:
            request = self._take_camera_request()
            if request is not None:
                action, generation, camera_id, width, height = request
                if action == "close":
                    self._close_camera_in_worker()
                else:
                    self._do_switch_camera(
                        generation, camera_id, width, height
                    )
                continue

            if not self.camera_ready or self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()

            # Boresight "crop" modu: lazerin vurdugu nokta merkeze gelsin.
            # crop 模式：先把画面裁到激光落点居中，之后全流程自动一致。
            if ret and frame is not None:
                frame = self._boresight_crop(frame)

            if not ret or frame is None:
                error_count += 1
                if error_count <= 5:
                    logger.error(f"[VISION ERROR] 读取帧失败 ({error_count}/5)")
                    if error_count == 5:
                        self.camera_ready = False
                        with self._camera_request_lock:
                            generation = self._camera_request_generation
                        self.camera_state_signal.emit(
                            generation, False, "摄像头画面中断"
                        )
                elif error_count == 100:
                    logger.error("[VISION ERROR] 持续读取失败，请检查摄像头连接")
                    error_count = 0
                time.sleep(0.1)
                continue

            error_count = 0

            # 画面方向翻转（在所有检测算法与绘制之前处理）
            if self.flip_mode == "180":
                frame = cv2.flip(frame, -1)
            elif self.flip_mode == "V":
                frame = cv2.flip(frame, 0)
            elif self.flip_mode == "H":
                frame = cv2.flip(frame, 1)

            try:
                # 计算 FPS (在处理模式前计算，确保 stats_signal 发送的是当前帧的FPS)
                curr_time = time.time()
                dt = curr_time - self.prev_time
                self.prev_time = curr_time
                if dt > 0:
                    self.fps_queue.append(1.0 / dt)
                    self.current_fps = sum(self.fps_queue) / len(self.fps_queue)

                if self.mode == "BLUE_TRACKING":
                    self._process_blue_tracking(frame)
                elif self.mode == "YOLO_TRACKING":
                    self._process_yolo_tracking(frame)
                elif self.mode == "BALLOON_HUNT":
                    self._process_balloon_hunt(frame)
                elif self.mode in ("STAGE3_BALLOONS", "STAGE3_BALLOON_DEFENSE"):
                    self._process_stage3_balloon_defense(frame)
                
                # 统一发送实时状态统计
                self.stats_signal.emit(self.current_fps, self.frame_width, self.frame_height)
                self._draw_overlay(frame) # _draw_overlay现在只计算FPS，不绘图
                self._send_image(frame)
            except Exception as e:
                logger.error(f"模式 {self.mode} 处理出错: {e}")
                import traceback
                traceback.print_exc()

            # (原有的 time.sleep(0.01) 已被删除，因为 cap.read() 自身就是硬件阻塞的)
            # 通过依赖 OpenCV 底层帧数阻塞，这解决了画面延迟和操作响应慢的根本问题。

        logger.info("[VISION] 线程退出，释放摄像头")
        self._close_camera_in_worker(emit_frame=False)

    # --------------------------------------------------
    # 处理逻辑（纯视觉，不含任何控制决策）
    # --------------------------------------------------


    def _process_blue_tracking(self, frame: cv2.Mat) -> None:
        """
        BLUE_TRACKING 模式：蓝色物体居中追踪

        发送蓝色目标的原始像素坐标（不是误差），
        由 GimbalController.handle_target_position 计算误差并处理。
        """
        blue_result, mask_blue = self.detector.detect_blue_object(frame)

        # 画面中心十字线
        # Nisangah = lazerin GERCEK vurus noktasi (boresight kalibrasyonu uygulanmis).
        # 十字线画在【激光实际落点】上 —— 所见即所打。
        _h, _w = frame.shape[:2]          # kirpilmis olabilir / 可能已被裁剪
        VisionConfig.CENTER_X = _w // 2
        VisionConfig.CENTER_Y = _h // 2
        cx, cy = VisionConfig.aim_point(VisionConfig.AKTIF_MESAFE_M)
        cv2.line(frame, (cx - 20, cy), (cx + 20, cy), (0, 255, 255), 1)
        cv2.line(frame, (cx, cy - 20), (cx, cy + 20), (0, 255, 255), 1)
        cv2.circle(frame, (cx, cy), 5, (0, 255, 255), 2)

        if blue_result.detected:
            pos = blue_result.position
            # 绘制目标标记
            cv2.circle(frame, pos, int(blue_result.radius), (255, 0, 0), 2)
            cv2.putText(frame, "Target",
                        (pos[0] - 20, pos[1] - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            cv2.arrowedLine(frame, (cx, cy), pos, (0, 255, 0), 2)

            # 发送原始坐标（不是误差！）→ handle_target_position
            self.target_pos_signal.emit(pos[0], pos[1])

            if not self.blue_object_detected:
                logger.info("[VISION] ✓ 找到蓝色目标")
                self.blue_object_detected = True
        else:
            if self.blue_object_detected:
                logger.info("[VISION] ✗ 未找到蓝色目标")
                self.blue_object_detected = False

        # 发送单次计算的高速调试蒙版
        self._send_mask(mask_blue)

    def _process_balloon_hunt(self, frame: cv2.Mat) -> None:
        """
        BALLOON_HUNT 模式：橙色气球打击与爆破模式 (Orange Balloon Hunt & Pop Mode)
        - 实时分割并追踪橙色气球 (Orange Balloon)
        - 准星一旦触碰到气球主体范围 (is_touching): 自动发射 100% 功率高能激光打爆气球
        - 若准星偏离/未触及气球: 持续追踪伺服修正，并在偏离时自动停火保护
        - 循环执行直至气球爆炸/画面中无橙色气球为止 (自动安全停火)
        """
        _h, _w = frame.shape[:2]
        VisionConfig.CENTER_X = _w // 2
        VisionConfig.CENTER_Y = _h // 2
        aim_x, aim_y = VisionConfig.aim_point(VisionConfig.AKTIF_MESAFE_M)

        # 1. 橙色高精度色彩与物理通道联合分割
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        b = frame[:, :, 0].astype(np.float32)
        g = frame[:, :, 1].astype(np.float32)
        r = frame[:, :, 2].astype(np.float32)

        # 橙色特征：H在[5, 24]区间，高饱和度S>=75（排除米色/木质桌面/皮肤），亮度V>=50，且R通道显著高于G和B
        hsv_mask = cv2.inRange(hsv, (5, 75, 50), (24, 255, 255))
        bgr_mask = (r > g + 22) & (r > b + 45) & (r >= 105)
        mask_orange = hsv_mask & (bgr_mask.astype(np.uint8) * 255)

        # 形态学滤波：使用椭圆结构元平滑气球边缘并断开细长线缆杂斑
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
        mask_clean = cv2.morphologyEx(mask_orange, cv2.MORPH_OPEN, kernel_open)
        mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, kernel_close)

        contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 2. 严苛几何形态学过滤：只识别气球形状的椭圆/圆形饱满凸面体
        valid_balloons = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 500: # 过滤杂散小噪点
                continue
            
            perimeter = cv2.arcLength(c, True)
            if perimeter <= 0:
                continue
            
            # (1) 圆度/紧凑度 (Circularity = 4 * pi * Area / P^2): 气球>=0.45，排除细长电线/杂乱多边形
            circularity = 4.0 * math.pi * area / (perimeter * perimeter)
            
            # (2) 凸包实心度 (Solidity = Area / ConvexHullArea): 气球为饱满无凹坑曲面>=0.82，排除手指/凹凸杂物
            hull = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull)
            solidity = area / float(max(hull_area, 1.0))
            
            # (3) 边界框宽高比: 气球呈椭球或球形，长宽比在 0.45 ~ 2.2 之间，排除条状横木/线管
            (cx_b, cy_b), radius = cv2.minEnclosingCircle(c)
            x_b, y_b, w_b, h_b = cv2.boundingRect(c)
            aspect_ratio = float(w_b) / float(max(h_b, 1))
            
            # 排除天花板顶角边缘的消防警报灯/指示灯
            if cy_b < _h * 0.25 or y_b < _h * 0.15:
                continue

            # (4) 最小外接圆覆盖率 (Extent)
            circle_extent = area / float(max(math.pi * (radius ** 2), 1.0))

            # (5) 椭圆拟合几何校验
            ellipse_valid = True
            ellipse_ratio = 1.0
            if len(c) >= 5:
                (ex, ey), (d1, d2), e_angle = cv2.fitEllipse(c)
                ellipse_ratio = min(d1, d2) / max(d1, d2) if max(d1, d2) > 0 else 0
                if ellipse_ratio < 0.35: # 过于扁平则非气球
                    ellipse_valid = False

            # 综合判定：必须同时满足气球的椭圆/圆形几何特征
            if (circularity >= 0.45 and solidity >= 0.82 and 
                0.45 <= aspect_ratio <= 2.2 and circle_extent >= 0.45 and ellipse_valid):
                # 气球几何质量评分
                score = circularity * solidity * circle_extent * ellipse_ratio * math.sqrt(area)
                valid_balloons.append((c, score, area, (cx_b, cy_b), radius))

        # 3. 多目标连续打击锁相匹配 (Target Persistence & Sequential Kill Chain)
        # 若视野中有多个气球，死死咬住当前正在锁定的第1个气球，打爆后再无缝切换第2个气球
        active_item = None
        queued_items = []

        if valid_balloons:
            # (A) 若已有正在锁定的气球，通过空间欧氏距离优先匹配同一个目标，绝不左右跳变摇摆
            if self._active_balloon_pos is not None:
                closest = min(valid_balloons, key=lambda item: math.hypot(item[3][0] - self._active_balloon_pos[0], item[3][1] - self._active_balloon_pos[1]))
                dist = math.hypot(closest[3][0] - self._active_balloon_pos[0], closest[3][1] - self._active_balloon_pos[1])
                if dist <= 160: # 160像素内认为是同一个平稳运动的气球
                    active_item = closest
                    self._active_balloon_pos = (int(closest[3][0]), int(closest[3][1]))
                    self._active_balloon_missing_count = 0
                    queued_items = [b for b in valid_balloons if b is not closest]
                else:
                    self._active_balloon_missing_count += 1
                    if self._active_balloon_missing_count >= 3:
                        # 确认当前第1个目标已打爆消失，准备切下一个
                        self._eliminated_balloon_count += 1
                        logger.info(f"[BALLOON HUNT] 💥 气球 #{self._eliminated_balloon_count} 已被打爆歼灭！自动锁定下一个气球...")
                        self._active_balloon_pos = None
                        self._active_balloon_missing_count = 0

            # (B) 若当前无锁定目标（刚开机或上一个已歼灭），从候选列表中锁定最优目标
            if self._active_balloon_pos is None:
                def _target_priority(item):
                    dist_reticle = math.hypot(aim_x - item[3][0], aim_y - item[3][1])
                    return item[1] - (dist_reticle * 0.15)
                active_item = max(valid_balloons, key=_target_priority)
                self._active_balloon_pos = (int(active_item[3][0]), int(active_item[3][1]))
                self._active_balloon_missing_count = 0
                queued_items = [b for b in valid_balloons if b is not active_item]
        else:
            if self._active_balloon_pos is not None:
                self._active_balloon_missing_count += 1
                if self._active_balloon_missing_count >= 3:
                    self._eliminated_balloon_count += 1
                    logger.info(f"[BALLOON HUNT] 💥 气球 #{self._eliminated_balloon_count} 已被打爆歼灭！")
                    self._active_balloon_pos = None
                    self._active_balloon_missing_count = 0

        # 4. 绘制排队待打的气球（黄色虚线圈提示）
        for q_idx, q_b in enumerate(queued_items, start=2):
            q_c, q_score, q_area, (q_cx, q_cy), q_r = q_b
            cv2.circle(frame, (int(q_cx), int(q_cy)), int(q_r), (255, 200, 0), 2)
            cv2.putText(frame, f"[QUEUED #{q_idx}]", (int(q_cx) - 40, int(q_cy) - int(q_r) - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 200, 0), 1, cv2.LINE_AA)

        is_touching = False

        if active_item is not None:
            c_max, best_score, area, (cx_b, cy_b), radius = active_item
            M = cv2.moments(c_max)
            if M['m00'] > 0:
                bx = int(M['m10'] / M['m00'])
                by = int(M['m01'] / M['m00'])
            else:
                bx, by = int(cx_b), int(cy_b)

            # 准星是否触碰/位于当前锁定气球轮廓内部或包络圆内
            is_inside_poly = cv2.pointPolygonTest(c_max, (float(aim_x), float(aim_y)), False) >= 0
            dist_to_center = math.hypot(aim_x - bx, aim_y - by)
            is_touching = is_inside_poly or (dist_to_center <= max(12.0, radius * 0.92))

            # 发送目标坐标驱动云台只追踪当前目标
            self.target_pos_signal.emit(bx, by)

            # 绘制当前主打击气球（鲜明红色/橙色轮廓）
            cv2.drawContours(frame, [c_max], -1, (0, 140, 255), 2)
            cv2.circle(frame, (int(cx_b), int(cy_b)), int(radius), (0, 165, 255), 2)
            cv2.circle(frame, (bx, by), 6, (0, 215, 255), -1)
            cv2.putText(frame, "[ENGAGING #1]", (int(cx_b) - 50, int(cy_b) - int(radius) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 215, 255), 2, cv2.LINE_AA)

            # 绘制从激光准星到气球质心的导引箭头
            line_color = (0, 0, 255) if is_touching else (0, 255, 255)
            cv2.arrowedLine(frame, (aim_x, aim_y), (bx, by), line_color, 2, tipLength=0.15)

            if is_touching:
                # 准星已触碰气球：自动触发 100% 激光发射！
                if not self.balloon_firing:
                    self.balloon_firing = True
                    self.laser_fire_request_signal.emit(True, 100)
                    logger.info(f"[BALLOON HUNT] 🔥 准星触碰当前目标气球 (Dist={dist_to_center:.1f}px) -> 触发 100% 激光打爆！")

                # 绘制高亮开火告警 HUD
                hud_text = f"🔥 [LOCKED ON TARGET] 100% LASER FIRING! (Popped: {self._eliminated_balloon_count})"
                cv2.rectangle(frame, (10, _h - 75), (560, _h - 35), (0, 0, 160), -1)
                cv2.rectangle(frame, (10, _h - 75), (560, _h - 35), (0, 0, 255), 2)
                cv2.putText(frame, hud_text, (20, _h - 48),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            else:
                # 准星偏离/未触及气球：激光停火，继续伺服对准
                if self.balloon_firing:
                    self.balloon_firing = False
                    self.laser_fire_request_signal.emit(False, 0)
                    logger.info("[BALLOON HUNT] 准星偏离当前气球 -> 激光停火并继续追踪")

                hud_text = f"🎈 [ENGAGING #1] Tracking (Dist: {dist_to_center:.1f}px | Queued: {len(queued_items)})"
                cv2.rectangle(frame, (10, _h - 75), (530, _h - 35), (20, 20, 20), -1)
                cv2.rectangle(frame, (10, _h - 75), (530, _h - 35), (0, 165, 255), 2)
                cv2.putText(frame, hud_text, (20, _h - 48),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 215, 255), 2)
        else:
            # 画面中没有橙色气球（全部气球已爆炸或未出现）：立即关闭激光，保持安全搜索
            if self.balloon_firing:
                self.balloon_firing = False
                self.laser_fire_request_signal.emit(False, 0)
                logger.info("[BALLOON HUNT] ✓ 全部橙色气球已爆炸/消失 -> 激光安全关闭")

            hud_text = f"🎈 [ALL BALLOONS CLEARED] Total Popped: {self._eliminated_balloon_count}"
            cv2.rectangle(frame, (10, _h - 75), (510, _h - 35), (20, 20, 20), -1)
            cv2.rectangle(frame, (10, _h - 75), (510, _h - 35), (52, 211, 153), 2)
            cv2.putText(frame, hud_text, (20, _h - 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (52, 211, 153), 2)

        # 画面准星绘制 (触碰时准星变红闪烁，未触碰时为亮黄色)
        reticle_color = (0, 0, 255) if is_touching else (0, 255, 255)
        cv2.line(frame, (aim_x - 22, aim_y), (aim_x + 22, aim_y), reticle_color, 2)
        cv2.line(frame, (aim_x, aim_y - 22), (aim_x, aim_y + 22), reticle_color, 2)
        cv2.circle(frame, (aim_x, aim_y), 6, reticle_color, 2)

        # 发送调试蒙版
        self._send_mask(mask_clean)

    def _process_stage3_balloon_defense(self, frame: cv2.Mat) -> None:
        """
        Stage 3 Balloon Defense Mode (Stage 3 竞赛三气球防空模式):
        - Red Balloon (Center) -> ENEMY (HOSTILE) -> Slew & Laser Engagement
        - Blue / Cyan Balloons (Left & Right) -> FRIENDLY (PROTECTED) -> Strictly Protected (Zero Friendly Fire)
        - 100% English HUD & Stage 3 Timeline signals
        """
        _h, _w = frame.shape[:2]
        VisionConfig.CENTER_X = _w // 2
        VisionConfig.CENTER_Y = _h // 2
        aim_x, aim_y = VisionConfig.aim_point(VisionConfig.AKTIF_MESAFE_M)

        # 1. 色彩分割 (HSV + BGR 通道差分，适应走廊阴影与漫反射)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        b = frame[:, :, 0].astype(np.float32)
        g = frame[:, :, 1].astype(np.float32)
        r = frame[:, :, 2].astype(np.float32)

        # 红色气球判据 (ENEMY HOSTILE)
        mask_red = (
            (cv2.inRange(hsv, (0, 60, 40), (18, 255, 255)) | cv2.inRange(hsv, (165, 60, 40), (180, 255, 255))) &
            (((r > g + 20) & (r > b + 32) & (r >= 95)).astype(np.uint8) * 255)
        )

        # 蓝色/青色气球判据 (FRIENDLY PROTECTED - 增强阴影区提取)
        mask_blue = (
            cv2.inRange(hsv, (30, 18, 25), (150, 255, 255)) &
            (((g > r + 1) | (b > r + 2)) & ((g + b) >= 2 * r + 2) & (g >= 50)).astype(np.uint8) * 255
        )

        # 2. 几何形态学与椭球体提取
        def _extract_raw_candidates(mask, side_type):
            k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
            m_clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_open)
            m_clean = cv2.morphologyEx(m_clean, cv2.MORPH_CLOSE, k_close)
            cnts, _ = cv2.findContours(m_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            res = []
            for c in cnts:
                area = cv2.contourArea(c)
                if area < 150:
                    continue
                peri = cv2.arcLength(c, True)
                if peri <= 0:
                    continue
                circ = 4.0 * math.pi * area / (peri * peri)
                hull = cv2.convexHull(c)
                solid = area / float(max(cv2.contourArea(hull), 1.0))
                (cx, cy), radius = cv2.minEnclosingCircle(c)
                xb, yb, wb, hb = cv2.boundingRect(c)
                ar = float(wb) / float(max(hb, 1))

                # 排除天花板及墙体高处纸飞机裁片 (地面气球在视野中下部 cy >= 0.40 * _h)
                if cy < _h * 0.40 or yb < _h * 0.30:
                    continue

                if circ >= 0.35 and solid >= 0.70 and 0.40 <= ar <= 2.40 and radius >= 8.0:
                    dist_m = max(1.0, (0.22 * 1200.0) / float(max(wb, hb, 1)))
                    res.append({
                        "contour": c,
                        "center": (int(round(cx)), int(round(cy))),
                        "radius": radius,
                        "box": [float(xb), float(yb), float(xb + wb), float(yb + hb)],
                        "area": area,
                        "taraf": side_type,
                        "mesafe_m": dist_m,
                    })
            return res

        raw_reds = _extract_raw_candidates(mask_red, "ENEMY")
        raw_blues = _extract_raw_candidates(mask_blue, "FRIENDLY")
        
        # 候选框空间去重 (Candidate Spatial De-duplication)
        def _dedup_candidates(cands):
            cands_sorted = sorted(cands, key=lambda item: item["area"], reverse=True)
            kept = []
            for c in cands_sorted:
                if not any(math.hypot(c["center"][0] - k["center"][0], c["center"][1] - k["center"][1]) < 45.0 for k in kept):
                    kept.append(c)
            return kept

        raw_reds = _dedup_candidates(raw_reds)
        raw_blues = _dedup_candidates(raw_blues)
        raw_all = raw_reds + raw_blues

        # 3. 空间多目标时序追踪与零闪烁保持 (Multi-Object Spatial Tracker & Holdover)
        if not hasattr(self, "_balloon_tracks"):
            self._balloon_tracks = {}
            self._next_balloon_id = 1

        unmatched = list(range(len(raw_all)))
        matched_ids = set()

        for tid, t in list(self._balloon_tracks.items()):
            best_d = 75.0
            best_idx = -1
            for idx in unmatched:
                cand = raw_all[idx]
                if cand["taraf"] == t["taraf"]:
                    d = math.hypot(t["center"][0] - cand["center"][0], t["center"][1] - cand["center"][1])
                    if d < best_d:
                        best_d = d
                        best_idx = idx
            if best_idx >= 0:
                cand = raw_all[best_idx]
                # EMA 平滑平抑噪声抖动
                for i in range(4):
                    t["box"][i] = 0.70 * cand["box"][i] + 0.30 * t["box"][i]
                t["center"] = (int((t["box"][0] + t["box"][2]) / 2.0), int((t["box"][1] + t["box"][3]) / 2.0))
                t["radius"] = float(cand["radius"])
                t["area"] = float(cand["area"])
                t["contour"] = cand["contour"]
                t["mesafe_m"] = cand["mesafe_m"]
                t["missing"] = 0
                matched_ids.add(tid)
                unmatched.remove(best_idx)
            else:
                t["missing"] += 1
                if t["missing"] > 4: # 超过 4 帧丢失才移除
                    del self._balloon_tracks[tid]

        for idx in unmatched:
            cand = raw_all[idx]
            # 检查是否与已有活跃轨迹重叠，杜绝在同一气球上派生双重轨迹
            if any(math.hypot(cand["center"][0] - ex["center"][0], cand["center"][1] - ex["center"][1]) < 55.0 for ex in self._balloon_tracks.values() if ex["taraf"] == cand["taraf"]):
                continue
            nid = self._next_balloon_id
            self._next_balloon_id += 1
            self._balloon_tracks[nid] = {
                "id": nid,
                "box": list(cand["box"]),
                "center": cand["center"],
                "radius": cand["radius"],
                "area": cand["area"],
                "contour": cand.get("contour"),
                "taraf": cand["taraf"],
                "mesafe_m": cand["mesafe_m"],
                "missing": 0,
            }

        # 4. 轨迹层空间非极大值抑制 (Track-Level Spatial NMS)，绝对防止同一气球出现两个重叠框
        track_list = sorted(self._balloon_tracks.values(), key=lambda t: (t["missing"] == 0, t["area"]), reverse=True)
        kept_tracks = {}
        for t in track_list:
            overlap = False
            for k_id, k_t in kept_tracks.items():
                if t["taraf"] == k_t["taraf"]:
                    d = math.hypot(t["center"][0] - k_t["center"][0], t["center"][1] - k_t["center"][1])
                    if d < 55.0:
                        overlap = True
                        break
            if not overlap:
                kept_tracks[t["id"]] = t
        self._balloon_tracks = kept_tracks

        # 5. 生成规范且左右固定的检测列表 (按左右 X 坐标稳定排序)
        active_tracks = list(self._balloon_tracks.values())
        red_tracks = [t for t in active_tracks if t["taraf"] == "ENEMY"]
        blue_tracks = sorted([t for t in active_tracks if t["taraf"] == "FRIENDLY"], key=lambda t: t["center"][0])

        all_detections = []
        for r_obj in red_tracks:
            rx1, ry1, rx2, ry2 = [int(v) for v in r_obj["box"]]
            cx, cy = r_obj["center"]
            all_detections.append({
                "contour": r_obj.get("contour"),
                "center": (cx, cy),
                "position": (cx, cy),
                "radius": r_obj["radius"],
                "box": (rx1, ry1, rx2, ry2),
                "area": r_obj["area"],
                "taraf": "ENEMY",
                "renk": "RED",
                "raw_name": "Red Balloon",
                "sinif": "RED BALLOON",
                "gorunen": "Red Balloon (Hostile)",
                "guven": 0.96 if r_obj["missing"] == 0 else 0.85,
                "mesafe_m": r_obj["mesafe_m"],
            })

        for b_idx, b_obj in enumerate(blue_tracks, 1):
            bx1, by1, bx2, by2 = [int(v) for v in b_obj["box"]]
            cx, cy = b_obj["center"]
            pos_label = "Left" if b_idx == 1 and len(blue_tracks) >= 2 else ("Right" if b_idx == 2 else f"#{b_idx}")
            all_detections.append({
                "contour": b_obj.get("contour"),
                "center": (cx, cy),
                "position": (cx, cy),
                "radius": b_obj["radius"],
                "box": (bx1, by1, bx2, by2),
                "area": b_obj["area"],
                "taraf": "FRIENDLY",
                "renk": "BLUE",
                "raw_name": f"Blue Balloon ({pos_label})",
                "sinif": "BLUE BALLOON",
                "gorunen": f"Blue Balloon ({pos_label})",
                "guven": 0.94 if b_obj["missing"] == 0 else 0.82,
                "mesafe_m": b_obj["mesafe_m"],
            })

        self.detections_signal.emit(all_detections)

        # 5. 敌方红色气球锁定与交战
        is_touching = False
        target_red = None
        if red_tracks:
            target_red = max(red_tracks, key=lambda item: item["area"] - math.hypot(aim_x - item["center"][0], aim_y - item["center"][1]) * 0.2)
            bx, by = target_red["center"]
            rx1, ry1, rx2, ry2 = [int(v) for v in target_red["box"]]
            radius = target_red["radius"]

            if target_red.get("contour") is not None:
                is_inside = cv2.pointPolygonTest(target_red["contour"], (float(aim_x), float(aim_y)), False) >= 0
            else:
                is_inside = (rx1 <= aim_x <= rx2 and ry1 <= aim_y <= ry2)
            dist_to_center = math.hypot(aim_x - bx, aim_y - by)
            is_touching = is_inside or (dist_to_center <= max(14.0, radius * 0.90))

            # 发送云台伺服跟踪目标
            self.target_pos_signal.emit(bx, by)

            # 绘制红色敌军战术框 (Bold Red)
            cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (30, 30, 255), 2)
            cl = max(6, int(min(rx2 - rx1, ry2 - ry1) * 0.22))
            cv2.line(frame, (rx1, ry1), (rx1 + cl, ry1), (0, 0, 255), 3)
            cv2.line(frame, (rx1, ry1), (rx1, ry1 + cl), (0, 0, 255), 3)
            cv2.line(frame, (rx2, ry1), (rx2 - cl, ry1), (0, 0, 255), 3)
            cv2.line(frame, (rx2, ry1), (rx2, ry1 + cl), (0, 0, 255), 3)
            cv2.line(frame, (rx1, ry2), (rx1 + cl, ry2), (0, 0, 255), 3)
            cv2.line(frame, (rx1, ry2), (rx1, ry2 - cl), (0, 0, 255), 3)
            cv2.line(frame, (rx2, ry2), (rx2 - cl, ry2), (0, 0, 255), 3)
            cv2.line(frame, (rx2, ry2), (rx2, ry2 - cl), (0, 0, 255), 3)

            # 中心红点与导引线
            cv2.circle(frame, (bx, by), 5, (0, 0, 255), -1)
            line_color = (0, 0, 255) if is_touching else (0, 200, 255)
            cv2.arrowedLine(frame, (aim_x, aim_y), (bx, by), line_color, 2, tipLength=0.15)

            # 战术文字标识 (100% English)
            conf_val = 96 if target_red["missing"] == 0 else 85
            tag_top = f"[HOSTILE LOCKED] Red Balloon ({conf_val}%)"
            tag_sub = f"FIRE >> ENEMY (RED) | {target_red['mesafe_m']:.1f}m"

            (tw, th), _ = cv2.getTextSize(tag_top, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
            cv2.rectangle(frame, (rx1, max(0, ry1 - 32)), (rx1 + tw + 10, ry1), (0, 0, 0), -1)
            cv2.putText(frame, tag_top, (rx1 + 4, ry1 - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 80, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, tag_sub, (rx1 + 4, ry1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 255), 1, cv2.LINE_AA)

        # 6. 绘制蓝色友军保护标识 (Cyan Blue Box & PROTECTED Text)
        for b_idx, b_obj in enumerate(blue_tracks, 1):
            bx1, by1, bx2, by2 = [int(v) for v in b_obj["box"]]
            bcx, bcy = b_obj["center"]
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (255, 200, 0), 2)
            cv2.circle(frame, (bcx, bcy), 4, (255, 200, 0), -1)

            conf_val = 94 if b_obj["missing"] == 0 else 82
            pos_label = "Left" if b_idx == 1 and len(blue_tracks) >= 2 else ("Right" if b_idx == 2 else f"#{b_idx}")
            tag_blue = f"[FRIENDLY] Blue Balloon ({pos_label}) ({conf_val}%)"
            sub_blue = "PROTECTED -- DO NOT FIRE"
            (bw_t, bh_t), _ = cv2.getTextSize(tag_blue, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
            cv2.rectangle(frame, (bx1, max(0, by1 - 32)), (bx1 + bw_t + 10, by1), (0, 0, 0), -1)
            cv2.putText(frame, tag_blue, (bx1 + 4, by1 - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1, cv2.LINE_AA)
            cv2.putText(frame, sub_blue, (bx1 + 4, by1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 120), 1, cv2.LINE_AA)

        # 7. 准星绘制 (触碰红色目标变红，否则保持明亮准星)
        reticle_color = (0, 0, 255) if is_touching else (0, 255, 255)
        cv2.line(frame, (aim_x - 22, aim_y), (aim_x + 22, aim_y), reticle_color, 2)
        cv2.line(frame, (aim_x, aim_y - 22), (aim_x, aim_y + 22), reticle_color, 2)
        cv2.circle(frame, (aim_x, aim_y), 6, reticle_color, 2)

        # 8. 发送 IFF 状态信号
        self.iff_signal.emit({
            "enemy": len(red_tracks),
            "friendly": len(blue_tracks),
            "neutral": 0,
            "locked": "Red Balloon" if target_red else None,
            "fire": is_touching if target_red else False
        })

        # 9. 画面左上方战术态势表格 (On-Screen Tactical Table)
        cv2.rectangle(frame, (10, 10), (330, 80), (15, 23, 42), -1)
        cv2.rectangle(frame, (10, 10), (330, 80), (2, 132, 199), 1)
        cv2.putText(frame, "STAGE 3 BALLOON IFF SUMMARY", (18, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (56, 189, 248), 1, cv2.LINE_AA)
        cv2.putText(frame, f"RED (HOSTILE)   : {len(red_tracks)} TARGET [LOCKED]", (18, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 70, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"BLUE (FRIENDLY) : {len(blue_tracks)} PROTECTED [SAFE]", (18, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 200, 0), 1, cv2.LINE_AA)

        # 发送调试蒙版
        self._send_mask(mask_red | mask_blue)


    def _boresight_crop(self, frame):
        """
        Goruntuyu, lazerin vurdugu nokta MERKEZ olacak sekilde kirpar.
        裁剪画面，让激光实际落点成为新画面的中心。

        Boylece nisangah ekranin tam ortasinda kalir ve alt katmanlarin
        (tespit, hata hesabi, cizim) kaymadan haberi olmasina gerek kalmaz —
        hepsi otomatik olarak dogru referansa gore calisir.
        这样十字线就在正中，而且下游（检测/误差/绘制）完全不需要知道偏移，
        自动就以正确基准工作。

        BEDELI / 代价: yatayda 2*|ox|, dikeyde 2*|oy| piksel FOV kaybi.
        损失 2*|ox| 宽、2*|oy| 高的视场。
        """
        if VisionConfig.BORESIGHT_MODE != "crop" or frame is None:
            return frame
        ox, oy = VisionConfig.raw_offset(VisionConfig.AKTIF_MESAFE_M)
        if ox == 0 and oy == 0:
            return frame
        h, w = frame.shape[:2]
        px, py = w // 2 + ox, h // 2 + oy
        # merkez disari tasmissa kirpma anlamsiz -> dokunma
        if not (0 < px < w and 0 < py < h):
            return frame
        hw = min(px, w - px)
        hh = min(py, h - py)
        if hw < 32 or hh < 32:
            return frame
        return frame[py - hh:py + hh, px - hw:px + hw]

    def _process_yolo_tracking(self, frame: cv2.Mat) -> None:
        """
        YOLO_TRACKING 模式：YOLO 目标检测与敌我识别 (IFF) 自主追踪
        
        核心火控规则：
        1. 严格只瞄准并摧毁红色敌方目标 (ENEMY / RED)；
        2. 绝对不对蓝色友军 (FRIENDLY / BLUE) 发送云台追踪或开火指令，蓝色友军全程受安全门保护；
        3. 画面清晰区分敌我：敌方红框锁定引导、友军蓝框高亮保护 (DO NOT FIRE)；
        4. 全程向 UI 实时推送 4 列详细检测列表与态势判定，为裁判提供最直接的视觉与表格证据。
        """
        if self.yolo_detector is None:
            return

        result = self.yolo_detector.detect_target(frame)

        # 画面中心十字准星与战术瞄准环
        # Nisangah = lazerin GERCEK vurus noktasi (boresight kalibrasyonu uygulanmis).
        # 十字线画在【激光实际落点】上 —— 所见即所打。
        _h, _w = frame.shape[:2]          # kirpilmis olabilir / 可能已被裁剪
        VisionConfig.CENTER_X = _w // 2
        VisionConfig.CENTER_Y = _h // 2
        cx, cy = VisionConfig.aim_point(VisionConfig.AKTIF_MESAFE_M)
        cv2.line(frame, (cx - 25, cy), (cx + 25, cy), (0, 255, 255), 1)
        cv2.line(frame, (cx, cy - 25), (cx, cy + 25), (0, 255, 255), 1)
        cv2.circle(frame, (cx, cy), 6, (0, 255, 255), 1)
        cv2.circle(frame, (cx, cy), 40, (0, 180, 255), 1)

        # 1. 收集所有检测到的目标（双重严格校验置信度门限）
        conf_gate = self.yolo_conf_threshold if self.yolo_conf_threshold is not None else 0.30
        raw_targets = []
        if hasattr(result, 'all_targets') and result.all_targets:
            raw_targets = [t for t in result.all_targets if (t.confidence or 0.0) >= conf_gate]
        elif result.detected and (result.confidence or 0.0) >= conf_gate:
            from vision.yolo_detector import YOLOSingleResult
            raw_targets = [YOLOSingleResult(
                position=result.position,
                box=result.box,
                class_id=result.class_id,
                confidence=result.confidence,
                class_name=result.class_name
            )]

        # 2. 空间质心多目标时序滤波与多空间 IFF 敌我识别 (彻底消除闪烁与跳变)
        if self.iff_enabled:
            analyzed_targets = self._iff.update_frame(frame, raw_targets)
        else:
            analyzed_targets = []
            for t in raw_targets:
                raw_cname = t.class_name if t.class_name else f"Cls_{t.class_id}"
                x1, y1, x2, y2 = [int(v) for v in t.box]
                analyzed_targets.append({
                    "track_id": 0,
                    "raw_name": raw_cname,
                    "sinif": raw_cname,
                    "guven": float(t.confidence or 0.0),
                    "box": (x1, y1, x2, y2),
                    "position": (int((x1 + x2) / 2), int((y1 + y2) / 2)),
                    "taraf": ENEMY,
                    "renk": ENEMY,
                    "missing": 0,
                })

        for d in analyzed_targets:
            raw_cname = d["raw_name"]
            display_name = VisionConfig.get_class_display_name(raw_cname)
            d["display_name"] = display_name
            d["gorunen"] = display_name
            bw = max(d["box"][2] - d["box"][0], 1)
            mesafe_m = (self.frame_width * 0.45) / (2.0 * bw * math.tan(math.radians(30.0)))
            d["mesafe_m"] = max(1.0, min(30.0, mesafe_m))

        # 分类统计
        enemy_list = [d for d in analyzed_targets if d["taraf"] == ENEMY]
        friendly_list = [d for d in analyzed_targets if d["taraf"] == FRIENDLY]
        neutral_list = [d for d in analyzed_targets if d["taraf"] == NEUTRAL]

        # 3. 目标火控锁定逻辑：严格只锁定敌方目标 (ENEMY)
        locked_enemy = None
        atis_izni = False

        if enemy_list:
            # 优先选择最靠近十字中心或置信度最高的敌方目标
            def _enemy_priority(d):
                dx = d["position"][0] - cx
                dy = d["position"][1] - cy
                dist_center = math.hypot(dx, dy)
                return d["guven"] * 100.0 - (dist_center * 0.05)
            
            enemy_list.sort(key=_enemy_priority, reverse=True)
            locked_enemy = enemy_list[0]
            atis_izni = True

        # 4. 画面战术 HUD 绘制 (高对比度暗色半透明底衬 + 鲜明军规配色)
        for d in analyzed_targets:
            x1, y1, x2, y2 = d["box"]
            pos = d["position"]
            conf_pct = int(d["guven"] * 100)
            disp_name = d["display_name"]
            taraf = d["taraf"]

            if locked_enemy and d == locked_enemy:
                # ====== 当前主锁定敌方目标 (RED HOSTILE - PRIMARY ENGAGEMENT) ======
                c_color = (30, 30, 255) # 鲜明正红
                line_len = min(22, (x2 - x1) // 3, (y2 - y1) // 3)
                # 四角战术包角
                cv2.line(frame, (x1, y1), (x1 + line_len, y1), c_color, 3)
                cv2.line(frame, (x1, y1), (x1, y1 + line_len), c_color, 3)
                cv2.line(frame, (x2, y1), (x2 - line_len, y1), c_color, 3)
                cv2.line(frame, (x2, y1), (x2, y1 + line_len), c_color, 3)
                cv2.line(frame, (x1, y2), (x1 + line_len, y2), c_color, 3)
                cv2.line(frame, (x1, y2), (x1, y2 - line_len), c_color, 3)
                cv2.line(frame, (x2, y2), (x2 - line_len, y2), c_color, 3)
                cv2.line(frame, (x2, y2), (x2, y2 - line_len), c_color, 3)
                cv2.rectangle(frame, (x1, y1), (x2, y2), c_color, 1)

                # 中心红点与红色追踪引导箭头
                cv2.circle(frame, pos, 5, c_color, -1)
                cv2.arrowedLine(frame, (cx, cy), pos, c_color, 2, tipLength=0.15)

                # 顶部标签与深色背景框（消除与背景光晕混淆）
                tag_y = max(38, y1 - 8)
                cv2.rectangle(frame, (x1 - 1, tag_y - 30), (x1 + 260, tag_y), (15, 15, 25), -1)
                cv2.rectangle(frame, (x1 - 1, tag_y - 30), (x1 + 260, tag_y), c_color, 1)
                cv2.putText(frame, f"[HOSTILE LOCKED] {disp_name} ({conf_pct}%)",
                            (x1 + 4, tag_y - 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"FIRE >> ENEMY (RED) | {d['mesafe_m']:.1f}m",
                            (x1 + 4, tag_y - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.40, (50, 100, 255), 1, cv2.LINE_AA)

            elif taraf == ENEMY:
                # ====== 次要敌方目标 (RED HOSTILE - QUEUED / STANDBY) ======
                c_color = (30, 30, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), c_color, 2)
                cv2.circle(frame, pos, 3, c_color, -1)

                tag_y = max(38, y1 - 8)
                cv2.rectangle(frame, (x1 - 1, tag_y - 30), (x1 + 220, tag_y), (15, 15, 25), -1)
                cv2.rectangle(frame, (x1 - 1, tag_y - 30), (x1 + 220, tag_y), c_color, 1)
                cv2.putText(frame, f"[HOSTILE] {disp_name} ({conf_pct}%)",
                            (x1 + 4, tag_y - 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"ENEMY QUEUED | {d['mesafe_m']:.1f}m",
                            (x1 + 4, tag_y - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.40, (50, 100, 255), 1, cv2.LINE_AA)

            elif taraf == FRIENDLY:
                # ====== 友军保护目标 (BLUE FRIENDLY - PROTECTED) ======
                c_color = (255, 200, 0) # 高对比度鲜明青蓝 (Cyan-Blue)
                cv2.rectangle(frame, (x1, y1), (x2, y2), c_color, 2)
                cv2.circle(frame, pos, 3, c_color, -1)

                tag_y = max(38, y1 - 8)
                cv2.rectangle(frame, (x1 - 1, tag_y - 30), (x1 + 240, tag_y), (15, 25, 20), -1)
                cv2.rectangle(frame, (x1 - 1, tag_y - 30), (x1 + 240, tag_y), c_color, 1)
                cv2.putText(frame, f"[FRIENDLY] {disp_name} ({conf_pct}%)",
                            (x1 + 4, tag_y - 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, "PROTECTED -- DO NOT FIRE",
                            (x1 + 4, tag_y - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.40, (100, 240, 255), 1, cv2.LINE_AA)

            else:
                # ====== 未定中立目标 (NEUTRAL / ANALYZING) ======
                c_color = (0, 180, 255) # 亮琥珀黄
                cv2.rectangle(frame, (x1, y1), (x2, y2), c_color, 1)
                cv2.circle(frame, pos, 3, c_color, -1)

                tag_y = max(24, y1 - 6)
                cv2.rectangle(frame, (x1 - 1, tag_y - 18), (x1 + 180, tag_y), (20, 20, 20), -1)
                cv2.putText(frame, f"[IFF?] {disp_name} ({conf_pct}%)",
                            (x1 + 4, tag_y - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 210, 255), 1, cv2.LINE_AA)

        # 5. 云台驱动控制
        if atis_izni and locked_enemy:
            pos = locked_enemy["position"]
            self.target_pos_signal.emit(pos[0], pos[1])
            if not self.blue_object_detected:
                logger.info(f"[VISION] ✓ YOLO 锁定敌方目标: {locked_enemy['display_name']} (置信度: {int(locked_enemy['guven']*100)}%)")
                self.blue_object_detected = True
        else:
            if self.blue_object_detected:
                logger.info("[VISION] ✗ YOLO: 无敌方目标或已消灭，停止火控追踪并保护友军")
                self.blue_object_detected = False

        # 6. 向 UI 广播 IFF 态势和完整 4 列检测表格数据
        if self.iff_enabled:
            self.iff_signal.emit({
                "enemy": len(enemy_list),
                "friendly": len(friendly_list),
                "neutral": len(neutral_list),
                "locked": locked_enemy["display_name"] if locked_enemy else None,
                "fire": atis_izni,
            })
            self.detections_signal.emit(analyzed_targets)

        mask_black = np.zeros(frame.shape[:2], dtype=np.uint8)
        self._send_mask(mask_black)


    # --------------------------------------------------
    # 渲染与发送工具 (PiP Scope 画中画 & 录像)
    # --------------------------------------------------

    def _render_pip_scope(self, frame: cv2.Mat, aim_x: int, aim_y: int) -> cv2.Mat:
        """
        在主画面左上角绘制第二屏幕：纯光学准星区域局部放大镜 (PiP Pure Zoom Scope)
        放大中心绝对锚定在大准星实际所指的像素位置 (aim_x, aim_y)！
        包含中心微型准头。
        """
        fh, fw = frame.shape[:2]
        pip_w = 260 if fw >= 1280 else 200
        pip_h = 195 if fw >= 1280 else 150
        pad_x, pad_y = 14, 14

        # 计算在原图上裁切的局部窗口尺寸
        crop_w = max(16, int(pip_w / self.pip_zoom))
        crop_h = max(12, int(pip_h / self.pip_zoom))

        # 确保以大准星实际落点 (aim_x, aim_y) 为中心进行裁切
        x1 = max(0, min(aim_x - crop_w // 2, fw - crop_w))
        y1 = max(0, min(aim_y - crop_h // 2, fh - crop_h))
        x2 = x1 + crop_w
        y2 = y1 + crop_h

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return frame

        scope_img = cv2.resize(crop, (pip_w, pip_h), interpolation=cv2.INTER_LINEAR)

        # 小屏幕中心微型战术准头 (PiP Micro Center Reticle)
        sc_cx, sc_cy = pip_w // 2, pip_h // 2
        reticle_color = (56, 189, 248) # Neon Cyan
        cv2.circle(scope_img, (sc_cx, sc_cy), 2, reticle_color, -1)
        cv2.line(scope_img, (sc_cx - 8, sc_cy), (sc_cx - 3, sc_cy), reticle_color, 1)
        cv2.line(scope_img, (sc_cx + 3, sc_cy), (sc_cx + 8, sc_cy), reticle_color, 1)
        cv2.line(scope_img, (sc_cx, sc_cy - 8), (sc_cx, sc_cy - 3), reticle_color, 1)
        cv2.line(scope_img, (sc_cx, sc_cy + 3), (sc_cx, sc_cy + 8), reticle_color, 1)

        # 战术放大倍数角标 (左上角小文字)
        cv2.putText(scope_img, f"ZOOM {self.pip_zoom:.1f}X", (8, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (56, 189, 248), 1)

        # 外边框
        cv2.rectangle(scope_img, (0, 0), (pip_w - 1, pip_h - 1), (56, 189, 248), 2)

        # 贴合在主画面左上角
        frame[pad_y:pad_y + pip_h, pad_x:pad_x + pip_w] = scope_img
        return frame

    def _draw_overlay(self, frame: cv2.Mat) -> None:
        """不再向画面直接绘图，改为通过 stats_signal 更新 UI"""
        pass

    def _send_image(self, frame: cv2.Mat) -> None:
        """渲染画中画与录像，并将 BGR 帧转为 QImage 发送给 UI"""
        try:
            fh, fw = frame.shape[:2]

            # 1. 计算大准星在当前帧上的实际像素坐标 (对齐 Crop 与 Offset 模式)
            aim_x, aim_y = VisionConfig.get_calibrated_aim_coords(fw, fh)

            # 2. 绘制主画面左上角第二屏幕：大准星区域局部放大镜
            if self.pip_enabled:
                self._render_pip_scope(frame, aim_x, aim_y)

            # 2.1 绘制电机速度档位实时战术角标 (Speed Gear Badge)
            gear_label = "G1 (SLOW 0.3x)" if self.speed_gear == 1 else ("G2 (NORM 1.0x)" if self.speed_gear == 2 else "G3 (FAST 2.2x)")
            gear_color = (52, 211, 153) if self.speed_gear == 1 else ((56, 189, 248) if self.speed_gear == 2 else (0, 165, 255))
            pip_w = 260 if fw >= 1280 else 200
            pip_h = 195 if fw >= 1280 else 150
            pad_x, pad_y = 14, 14
            badge_y = (pad_y + pip_h + 18) if self.pip_enabled else 28
            cv2.putText(frame, f"⚡ SPEED: {gear_label}", (pad_x, badge_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(frame, f"⚡ SPEED: {gear_label}", (pad_x, badge_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, gear_color, 1, cv2.LINE_AA)

            # 3. 画面底部常驻全英文战术遥测 HUD 仪表条 (All-Time Live Screen & Recorded Video OSD)
            now = time.time()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            pan_tilt_str = f"PAN: {self.telemetry_pan:+.2f} deg   TILT: {self.telemetry_tilt:+.2f} deg"
            
            tgt_name = str(self.yolo_target_class) if self.yolo_target_class is not None else "ALL"
            range_val = getattr(VisionConfig, "AKTIF_MESAFE_M", None)
            range_str = f"{range_val:.0f}m" if range_val else "FIX"
            laser_str = "FIRE ⚡" if self.telemetry_laser_firing else ("ARMED" if self.telemetry_laser_armed else "SAFE")
            sys_info_str = f"SYS: {self.mode} | TGT: {tgt_name} | RNG: {range_str} | SPD: {gear_label} | LASER: {laser_str}"

            hud_h = 68
            hud_y = fh - hud_h
            if hud_y > 0:
                sub_img = frame[hud_y:fh, 0:fw]
                black_rect = np.zeros_like(sub_img)
                cv2.addWeighted(sub_img, 0.40, black_rect, 0.60, 0, sub_img)
                frame[hud_y:fh, 0:fw] = sub_img

                cv2.putText(frame, f"TIME: {now_str}", (14, hud_y + 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"GIMBAL: {pan_tilt_str}", (14, hud_y + 38),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (56, 189, 248), 1, cv2.LINE_AA)
                cv2.putText(frame, sys_info_str, (14, hud_y + 58),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (52, 211, 153), 1, cv2.LINE_AA)

            # 4. 视频录像安全写入与 REC / PAUSE 状态角标 (基于真实物理挂钟时间消除跳帧与快进)
            with self._rec_lock:
                if self.recording_state != "IDLE" and self.video_writer is not None:
                    try:
                        if self.recording_state == "RECORDING":
                            if fw != self.writer_w or fh != self.writer_h:
                                frame_to_write = cv2.resize(frame, (self.writer_w, self.writer_h))
                            else:
                                frame_to_write = frame

                            # 计算自录制开始以来的实际真实物理时间所应输出的帧数
                            elapsed_actual = max(0.0, now - self.recording_start_time - self.recording_total_paused_sec)
                            target_frames = int(round(elapsed_actual * self._recording_fps))
                            frames_needed = max(1, target_frames - self._recording_frames_written)
                            # 限制单次突发写入上限，平滑负载
                            frames_needed = min(frames_needed, 6)

                            contiguous_frame = np.ascontiguousarray(frame_to_write)
                            for _ in range(frames_needed):
                                self.video_writer.write(contiguous_frame)
                                self._recording_frames_written += 1

                            elapsed_s = int(elapsed_actual)
                            m, s = divmod(elapsed_s, 60)
                            blink = int(now * 2) % 2 == 0
                            rec_color = (40, 40, 240) if blink else (100, 100, 255)
                            cv2.circle(frame, (fw - 145, 26), 7, rec_color, -1)
                            cv2.putText(frame, f"REC {m:02d}:{s:02d}", (fw - 130, 32),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                            if elapsed_s != self._last_rec_sec:
                                self._last_rec_sec = elapsed_s
                                self.recording_status_signal.emit("RECORDING", self.recording_path, elapsed_s)
                        elif self.recording_state == "PAUSED":
                            elapsed_s = max(0, int(self.recording_paused_time - self.recording_start_time - self.recording_total_paused_sec))
                            m, s = divmod(elapsed_s, 60)
                            cv2.putText(frame, f"PAUSED {m:02d}:{s:02d}", (fw - 165, 32),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 215, 255), 2)
                            if elapsed_s != self._last_rec_sec:
                                self._last_rec_sec = elapsed_s
                                self.recording_status_signal.emit("PAUSED", self.recording_path, elapsed_s)
                    except Exception as e:
                        logger.error(f"[VISION ERROR] 视频流写入异常: {e}")

            frame_cont = np.ascontiguousarray(frame)
            h, w, ch = frame_cont.shape
            q_image = QImage(frame_cont.data, w, h, ch * w,
                             QImage.Format.Format_BGR888).copy()
            self.frame_signal.emit(q_image)
        except Exception as e:
            logger.error(f"[VISION ERROR] send_image failed: {e}")

    def _send_mask(self, mask: cv2.Mat) -> None:
        """将单通道蒙版发送给 UI（调试用）"""
        try:
            h, w = mask.shape
            q_image = QImage(mask.data, w, h, w,
                             QImage.Format.Format_Grayscale8).copy()
            self.mask_signal.emit(q_image)
        except Exception as e:
            logger.error(f"[VISION ERROR] send_mask failed: {e}")
