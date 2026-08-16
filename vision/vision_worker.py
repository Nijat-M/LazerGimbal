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

# 抑制 OpenCV 警告
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'

# 核心修改：在 Windows 下，必须先加载 torch（YOLO 会加载）再加载 cv2，否则可能导致 c10.dll 初始化失败
from vision.yolo_detector import AsyncYOLODetector, YOLODetector

import cv2
import time
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt6.QtGui import QImage
from collections import deque

from config.vision_config import VisionConfig
from vision.detector import TargetDetector
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

    def __init__(self):
        super().__init__()
        self.is_running: bool = True
        self.mode: str = "IDLE"
        self.cap = None
        self.camera_id: int = VisionConfig.CAMERA_ID
        self.frame_width: int = VisionConfig.FRAME_WIDTH
        self.frame_height: int = VisionConfig.FRAME_HEIGHT
        self.camera_ready: bool = False

        # 检测器（纯视觉，无控制逻辑）
        self.detector = TargetDetector()
        
        # YOLO检测器 (按需初始化，或在这里先初始化)
        self.yolo_detector = None


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
            logger.info("[VISION] 正在初始化 YOLO26 异步深度学习引擎...")
            self.yolo_detector = AsyncYOLODetector("vision/models/yolo26n.pt")
            logger.info("[VISION] YOLO26 异步引擎初始化完成。")
        logger.info(f"[VISION] 视觉线程模式: {mode}")

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
        cx = self.frame_width // 2
        cy = self.frame_height // 2
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


    def _process_yolo_tracking(self, frame: cv2.Mat) -> None:
        """
        YOLO_TRACKING 模式：YOLO 物体居中追踪
        
        发送目标的原始像素坐标，由 GimbalController 计算误差。
        采用后台异步并发架构，主视觉线程零阻塞，保证相机以 60 FPS 满速流畅采集与显示。
        """
        if self.yolo_detector is None:
            return

        # 非阻塞提交并获取最新目标锁定结果（主线程耗时 <0.01ms）
        result = self.yolo_detector.detect_target(frame, target_class=None)

        # 画面中心十字线
        cx = self.frame_width // 2
        cy = self.frame_height // 2
        cv2.line(frame, (cx - 20, cy), (cx + 20, cy), (0, 255, 255), 1)
        cv2.line(frame, (cx, cy - 20), (cx, cy + 20), (0, 255, 255), 1)
        cv2.circle(frame, (cx, cy), 5, (0, 255, 255), 2)

        # 1. 遍历并画出视野里发现的所有目标
        if hasattr(result, 'all_targets') and result.all_targets:
            for t in result.all_targets:
                tx1, ty1, tx2, ty2 = t.box
                t_pos = t.position
                
                # 绘制所有检测到的物体为黄色框和圆点（BGR: (0, 255, 255) 是黄色），代表“雷达探测到但未锁定”
                cv2.rectangle(frame, (tx1, ty1), (tx2, ty2), (0, 255, 255), 1)
                cv2.circle(frame, t_pos, 3, (0, 255, 255), -1)
                
                label_name = self.yolo_detector.model.names.get(t.class_id, f"Cls_{t.class_id}")
                cv2.putText(frame, f"{label_name} {t.confidence:.2f}",
                            (tx1, ty1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        # 2. 特别高亮画出被“锁定”要追踪的那一个主目标
        if result.detected:
            pos = result.position
            x1, y1, x2, y2 = result.box
            
            # 覆写主目标的颜色为粗的红色框及醒目的提示
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.circle(frame, pos, 5, (0, 0, 255), -1)
            
            label_name = self.yolo_detector.model.names.get(result.class_id, f"Cls_{result.class_id}") if result.class_id is not None else "Target"
            cv2.putText(frame, f"[LOCKED] {label_name}",
                        (x1, y1 - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.arrowedLine(frame, (cx, cy), pos, (0, 255, 0), 2)

            self.target_pos_signal.emit(pos[0], pos[1])

            if not self.blue_object_detected:
                logger.info("[VISION] ✓ YOLO: 找到目标")
                self.blue_object_detected = True
        else:
            if self.blue_object_detected:
                logger.info("[VISION] ✗ YOLO: 未找到目标")
                self.blue_object_detected = False

        # 对于YOLO我们不需要发送特定的掩码蒙版，直接填黑
        mask_black = np.zeros(frame.shape[:2], dtype=np.uint8)
        self._send_mask(mask_black)


    # --------------------------------------------------
    # 渲染与发送工具
    # --------------------------------------------------

    def _draw_overlay(self, frame: cv2.Mat) -> None:
        """不再向画面直接绘图，改为通过 stats_signal 更新 UI"""
        # FPS 计算已移至 run() 循环开始处，确保 stats_signal 发送的是最新值
        pass # 清空绘图逻辑

    def _send_image(self, frame: cv2.Mat) -> None:
        """将 BGR 帧转为 QImage 发送给 UI (原生 Format_BGR888 避免红蓝反转)"""
        try:
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
