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

    def __init__(self):
        super().__init__()
        self.is_running: bool = True
        self.mode: str = "IDLE"
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
        self.recording_path: str = ""
        self.writer_w: int = 0
        self.writer_h: int = 0
        self._rec_lock = threading.Lock()

        # 电机与激光状态遥测（用于录制视频 HUD 水印叠加，全英文）
        self.telemetry_pan: float = 0.0
        self.telemetry_tilt: float = 0.0
        self.telemetry_laser_armed: bool = False
        self.telemetry_laser_firing: bool = False
        self.telemetry_laser_pwr: int = 100

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
        self.mode = mode
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
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                self.video_writer = cv2.VideoWriter(self.recording_path, fourcc, fps, (w, h))
                if not self.video_writer.isOpened():
                    self.recording_path = os.path.join(output_dir, f"rec_{timestamp}.avi")
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    self.video_writer = cv2.VideoWriter(self.recording_path, fourcc, fps, (w, h))

                self.recording_state = "RECORDING"
                self.recording_start_time = time.time()
                self.recording_paused_time = 0.0
                self.recording_total_paused_sec = 0.0
                logger.info(f"[VISION] 🔴 开始录制视频: {self.recording_path} ({w}x{h} @ {fps:.1f}fps)")
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
            path = self.recording_path
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

        candidate = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        if not candidate.isOpened():
            candidate.release()
            logger.info("[VISION] DSHOW后端失败，尝试默认后端...")
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

        # 2. 遍历所有目标进行 IFF 敌我识别与测距
        analyzed_targets = []
        for t in raw_targets:
            raw_cname = t.class_name if t.class_name else f"Cls_{t.class_id}"
            display_name = VisionConfig.get_class_display_name(raw_cname)
            
            # IFF 颜色识别
            taraf = NEUTRAL
            if self.iff_enabled:
                taraf_raw, _, _, _ = iff_analiz(frame, t.box)
                t_key = f"{raw_cname}_{t.box[0]//30}_{t.box[1]//30}"
                taraf = self._iff.guncelle(t_key, taraf_raw)

            # 光学测距估算 (~10m 标准比赛场景)
            bw = max(t.box[2] - t.box[0], 1)
            mesafe_m = (self.frame_width * 0.45) / (2.0 * bw * math.tan(math.radians(30.0)))
            mesafe_m = max(1.0, min(30.0, mesafe_m))

            analyzed_targets.append({
                "target": t,
                "raw_name": raw_cname,
                "display_name": display_name,
                "sinif": raw_cname,
                "gorunen": display_name,
                "guven": float(t.confidence or 0.0),
                "box": t.box,
                "position": t.position,
                "mesafe_m": mesafe_m,
                "taraf": taraf,
                "renk": taraf,
            })

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

        # 4. 画面战术 HUD 绘制
        for d in analyzed_targets:
            x1, y1, x2, y2 = d["box"]
            pos = d["position"]
            conf_pct = int(d["guven"] * 100)
            disp_name = d["display_name"]
            taraf = d["taraf"]

            if locked_enemy and d == locked_enemy:
                # ====== 当前主锁定敌方目标 (RED HOSTILE - PRIMARY ENGAGEMENT) ======
                c_color = (40, 40, 240) # BGR Red
                # 绘制四角加厚瞄准角框
                line_len = min(22, (x2 - x1) // 3, (y2 - y1) // 3)
                cv2.line(frame, (x1, y1), (x1 + line_len, y1), c_color, 2)
                cv2.line(frame, (x1, y1), (x1, y1 + line_len), c_color, 2)
                cv2.line(frame, (x2, y1), (x2 - line_len, y1), c_color, 2)
                cv2.line(frame, (x2, y1), (x2, y1 + line_len), c_color, 2)
                cv2.line(frame, (x1, y2), (x1 + line_len, y2), c_color, 2)
                cv2.line(frame, (x1, y2), (x1, y2 - line_len), c_color, 2)
                cv2.line(frame, (x2, y2), (x2 - line_len, y2), c_color, 2)
                cv2.line(frame, (x2, y2), (x2, y2 - line_len), c_color, 2)
                cv2.rectangle(frame, (x1, y1), (x2, y2), c_color, 1)

                # 中心红点与红色追踪引导箭头 (仅指向当前交战的主敌方)
                cv2.circle(frame, pos, 5, c_color, -1)
                cv2.arrowedLine(frame, (cx, cy), pos, c_color, 2, tipLength=0.15)

                # 顶部标签
                cv2.putText(frame, f"[HOSTILE LOCKED] {disp_name} ({conf_pct}%)",
                            (x1, max(20, y1 - 22)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, c_color, 2)
                cv2.putText(frame, f"FIRE AUTHORIZED >> ENEMY | {d['mesafe_m']:.1f}m",
                            (x1, max(36, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (60, 60, 255), 1)

            elif taraf == ENEMY:
                # ====== 次要敌方目标 (RED HOSTILE - QUEUED / STANDBY) ======
                c_color = (40, 40, 240) # BGR Red（全部敌方标红）
                cv2.rectangle(frame, (x1, y1), (x2, y2), c_color, 2)
                cv2.circle(frame, pos, 3, c_color, -1)
                cv2.putText(frame, f"[HOSTILE] {disp_name} ({conf_pct}%)",
                            (x1, max(20, y1 - 22)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, c_color, 2)
                cv2.putText(frame, f"ENEMY QUEUED | {d['mesafe_m']:.1f}m",
                            (x1, max(36, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (60, 60, 255), 1)

            elif taraf == FRIENDLY:
                # ====== 友军保护目标 (BLUE FRIENDLY - PROTECTED) ======
                c_color = (240, 180, 40) # BGR Blue / Cyan
                cv2.rectangle(frame, (x1, y1), (x2, y2), c_color, 2)
                cv2.circle(frame, pos, 3, c_color, -1)
                
                # 顶部标签：明确标明 FRIENDLY - DO NOT FIRE
                cv2.putText(frame, f"[FRIENDLY] {disp_name} ({conf_pct}%)",
                            (x1, max(20, y1 - 22)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, c_color, 2)
                cv2.putText(frame, "PROTECTED -- DO NOT FIRE",
                            (x1, max(36, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (100, 230, 255), 1)

            else:
                # ====== 未定中立目标 (NEUTRAL / UNKNOWN) ======
                c_color = (170, 170, 170)
                cv2.rectangle(frame, (x1, y1), (x2, y2), c_color, 1)
                cv2.circle(frame, pos, 3, c_color, -1)
                cv2.putText(frame, f"{disp_name} ({conf_pct}%)",
                            (x1, max(20, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, c_color, 1)

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

            # 3. 录屏视频流写入与 REC / PAUSE 状态角标及全英文遥测 OSD 叠加
            if self.recording_state != "IDLE" and self.video_writer is not None:
                now = time.time()
                # 录制画面 OSD 战术水印与数据叠加 (全英文 HUD)
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                pan_tilt_str = f"PAN: {self.telemetry_pan:+.2f} deg   TILT: {self.telemetry_tilt:+.2f} deg"
                
                tgt_name = str(self.yolo_target_class) if self.yolo_target_class is not None else "ALL"
                range_val = getattr(VisionConfig, "AKTIF_MESAFE_M", None)
                range_str = f"{range_val:.0f}m" if range_val else "FIX"
                laser_str = "FIRE ⚡" if self.telemetry_laser_firing else ("ARMED" if self.telemetry_laser_armed else "SAFE")
                sys_info_str = f"SYS: {self.mode} | TGT: {tgt_name} | RNG: {range_str} | LASER: {laser_str}"

                hud_h = 68
                hud_y = fh - hud_h
                if hud_y > 0:
                    sub_img = frame[hud_y:fh, 0:fw]
                    black_rect = np.zeros_like(sub_img)
                    cv2.addWeighted(sub_img, 0.45, black_rect, 0.55, 0, sub_img)
                    frame[hud_y:fh, 0:fw] = sub_img

                    cv2.putText(frame, f"TIME: {now_str}", (14, hud_y + 18),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
                    cv2.putText(frame, f"GIMBAL: {pan_tilt_str}", (14, hud_y + 38),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (56, 189, 248), 1, cv2.LINE_AA)
                    cv2.putText(frame, sys_info_str, (14, hud_y + 58),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (52, 211, 153), 1, cv2.LINE_AA)

                if self.recording_state == "RECORDING":
                    if fw != self.writer_w or fh != self.writer_h:
                        frame_to_write = cv2.resize(frame, (self.writer_w, self.writer_h))
                    else:
                        frame_to_write = frame
                    self.video_writer.write(frame_to_write)

                    elapsed_s = max(0, int(now - self.recording_start_time - self.recording_total_paused_sec))
                    m, s = divmod(elapsed_s, 60)
                    blink = int(now * 2) % 2 == 0
                    rec_color = (40, 40, 240) if blink else (100, 100, 255)
                    cv2.circle(frame, (fw - 145, 26), 7, rec_color, -1)
                    cv2.putText(frame, f"REC {m:02d}:{s:02d}", (fw - 130, 32),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                    self.recording_status_signal.emit("RECORDING", self.recording_path, elapsed_s)
                elif self.recording_state == "PAUSED":
                    elapsed_s = max(0, int(self.recording_paused_time - self.recording_start_time - self.recording_total_paused_sec))
                    m, s = divmod(elapsed_s, 60)
                    cv2.putText(frame, f"PAUSED {m:02d}:{s:02d}", (fw - 165, 32),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 215, 255), 2)
                    self.recording_status_signal.emit("PAUSED", self.recording_path, elapsed_s)

            h, w, ch = frame.shape
            q_image = QImage(frame.data, w, h, ch * w,
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
