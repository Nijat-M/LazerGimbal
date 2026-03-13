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

# 抑制 OpenCV 警告
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'

# 核心修改：在 Windows 下，必须先加载 torch（YOLO 会加载）再加载 cv2，否则可能导致 c10.dll 初始化失败
from vision.yolo_detector import YOLODetector

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
        control_signal    : 发送误差 (err_x, err_y)（TRACKING 模式，激光追蓝色）
        target_pos_signal : 发送目标位置 (pos_x, pos_y)（BLUE_TRACKING 模式，居中追踪）
        stats_signal      : 发送实时统计数据 (fps, width, height)
    """

    frame_signal = pyqtSignal(QImage)       # 处理后的画面
    mask_signal = pyqtSignal(QImage)        # 调试蒙版
    control_signal = pyqtSignal(int, int)   # 误差信号 (TRACKING 模式)
    target_pos_signal = pyqtSignal(int, int)  # 原始坐标 (BLUE_TRACKING 模式)
    stats_signal = pyqtSignal(float, int, int) # (fps, width, height)

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
        self.laser_tracking_status = None  # 记录当前追踪状态

        # FPS 计算相关
        self.prev_time = time.time()
        self.fps_queue = deque(maxlen=20)  # 平滑 FPS
        self.current_fps = 0

        # 线程安全标志，用于异步打开摄像头
        self._need_reconnect = False
        self._pending_id = -1
        self._pending_w = 640
        self._pending_h = 480

    # --------------------------------------------------
    # 公共接口
    # --------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """设置工作模式"""
        self.mode = mode
        if mode == "YOLO_TRACKING" and self.yolo_detector is None:
            logger.info("[VISION] 正在初始化 YOLOv8 模型...")
            self.yolo_detector = YOLODetector("vision/models/yolov8n.pt")  # 从新的规范路径加载
            logger.info("[VISION] YOLOv8 模型初始化完成。")
        logger.info(f"[VISION] 视觉线程模式: {mode}")

    def switch_camera(self, camera_id: int, width: int, height: int) -> None:
        """异步请求切换摄像头"""
        self._pending_id = camera_id
        self._pending_w = width
        self._pending_h = height
        self._need_reconnect = True
        self.camera_ready = False  # 暂时停止处理逻辑

    def _do_switch_camera(self) -> None:
        """在后台线程中实际执行打开操作"""
        camera_id = self._pending_id
        width = self._pending_w
        height = self._pending_h
        
        logger.info(f"[VISION] 正在后台打开摄像头: ID={camera_id}, {width}x{height}")

        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.cap = None
            time.sleep(0.3)

        self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            logger.info("[VISION] DSHOW后端失败，尝试默认后端...")
            self.cap = cv2.VideoCapture(camera_id)

        if not self.cap.isOpened():
            logger.error(f"[VISION ERROR] 无法打开摄像头 ID={camera_id}")
            self.camera_ready = False
            return

        if self.cap.isOpened():
            # [核心逻辑] 先设分辨率 -> 强制设 MJPG -> 再次确认分辨率
            # 这种“补刀”式设置能防止驱动自动重置回慢速模式。
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # 强制开启 MJPG
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            # [确认]
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, 60)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 暖机时间延长，让驱动有足够时间匹配模式
        time.sleep(1.0) 
        for _ in range(15):
            self.cap.read() 

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        actual_fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
        
        # 解码 FourCC 编码
        f_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)]) if actual_fourcc > 0 else "DEFAULT"

        self.frame_width = actual_w
        self.frame_height = actual_h

        logger.info(f"[VISION] 优化模式就绪: {actual_w}x{actual_h} @ {actual_fps}fps, 编码: {f_str}")

        self.frame_width = actual_w
        self.frame_height = actual_h

        logger.info(f"[VISION] 硬件实际反馈: {actual_w}x{actual_h} @ {actual_fps}fps, 编码: {f_str}")

        # 动态更新全局配置
        VisionConfig.FRAME_WIDTH = actual_w
        VisionConfig.FRAME_HEIGHT = actual_h
        VisionConfig.CENTER_X = actual_w // 2
        VisionConfig.CENTER_Y = actual_h // 2

        logger.info(f"[VISION] ✓ 摄像头就绪: {actual_w}x{actual_h} @ {actual_fps}fps")

        if 0 < actual_fps < VisionConfig.TARGET_FPS:
            logger.warning(f"[VISION] 环境光照可能不足，实际帧率: {actual_fps}")

        self.camera_ready = True

    def stop(self) -> None:
        """停止线程"""
        self.is_running = False
        self.quit()
        self.wait()

    def close_camera(self) -> None:
        """手动关闭摄像头"""
        logger.info("[VISION] 正在关闭摄像头...")
        self.camera_ready = False
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.cap = None
        
        # 发送一张黑屏蒙版告知UI已关闭
        black_frame = QImage(self.frame_width, self.frame_height, QImage.Format.Format_RGB888)
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
            # 检查是否需要（重）连摄像头 -> 异步操作防止UI卡死
            if self._need_reconnect:
                self._do_switch_camera()
                self._need_reconnect = False
                continue

            if not self.camera_ready or self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()

            if not ret or frame is None:
                error_count += 1
                if error_count <= 5:
                    logger.error(f"[VISION ERROR] 读取帧失败 ({error_count}/5)")
                elif error_count == 100:
                    logger.error("[VISION ERROR] 持续读取失败，请检查摄像头连接")
                    error_count = 0
                time.sleep(0.1)
                continue

            error_count = 0

            try:
                # 计算 FPS (在处理模式前计算，确保 stats_signal 发送的是当前帧的FPS)
                curr_time = time.time()
                dt = curr_time - self.prev_time
                self.prev_time = curr_time
                if dt > 0:
                    self.fps_queue.append(1.0 / dt)
                    self.current_fps = sum(self.fps_queue) / len(self.fps_queue)

                if self.mode == "TRACKING":
                    self._process_tracking(frame)
                elif self.mode == "BLUE_TRACKING":
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
        if self.cap is not None:
            self.cap.release()

    # --------------------------------------------------
    # 处理逻辑（纯视觉，不含任何控制决策）
    # --------------------------------------------------

    def _process_tracking(self, frame: cv2.Mat) -> None:
        """
        TRACKING 模式：激光点追踪蓝色目标

        误差 = 蓝色目标位置 - 红色激光位置（两点相对误差）
        直接发送误差，由 GimbalController.handle_vision_error 处理。
        """
        laser_result, blue_result = self.detector.detect_laser_and_blue(frame)

        # 绘制检测结果
        if blue_result.detected:
            cv2.circle(frame, blue_result.position, int(blue_result.radius),
                       (255, 0, 0), 2)
            cv2.putText(frame, "Target",
                        (blue_result.position[0] - 10, blue_result.position[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        if laser_result.detected:
            cv2.circle(frame, laser_result.position, 5, (0, 0, 255), -1)

        # 计算并发送误差（原始两点差，不做任何缩放/死区处理）
        if blue_result.detected and laser_result.detected:
            error_x = blue_result.position[0] - laser_result.position[0]
            error_y = blue_result.position[1] - laser_result.position[1]
            cv2.arrowedLine(frame, laser_result.position, blue_result.position,
                            (0, 255, 0), 2)
            self.control_signal.emit(error_x, error_y)  # → handle_vision_error

            if self.laser_tracking_status != "both":
                logger.info("[VISION] ✓ 同时检测到蓝色目标和红色激光")
                self.laser_tracking_status = "both"

        elif blue_result.detected and not laser_result.detected:
            if self.laser_tracking_status != "blue_only":
                logger.info("[VISION] 找到蓝色目标，但红色激光丢失")
                self.laser_tracking_status = "blue_only"
        else:
            if self.laser_tracking_status not in (None, "none"):
                logger.info("[VISION] 未检测到目标")
                self.laser_tracking_status = "none"

        # 调试蒙版
        debug_mask = self.detector.get_debug_mask(frame)
        self._send_mask(debug_mask)
        # self._send_image(frame)  # 已经在 run() 统一发送了


    def _process_blue_tracking(self, frame: cv2.Mat) -> None:
        """
        BLUE_TRACKING 模式：蓝色物体居中追踪

        发送蓝色目标的原始像素坐标（不是误差），
        由 GimbalController.handle_target_position 计算误差并处理。
        """
        blue_result = self.detector.detect_blue_object(frame)

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

            # 显示坐标信息（已移至全局 Overlay 或精简）
            pass

            # 发送原始坐标（不是误差！）→ handle_target_position
            self.target_pos_signal.emit(pos[0], pos[1])

            if not self.blue_object_detected:
                logger.info("[VISION] ✓ 找到蓝色目标")
                self.blue_object_detected = True
        else:
            if self.blue_object_detected:
                logger.info("[VISION] ✗ 未找到蓝色目标")
                self.blue_object_detected = False

        # 调试蒙版（蓝色检测范围）
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask_blue = cv2.inRange(hsv, VisionConfig.HSV_BLUE_LOWER, VisionConfig.HSV_BLUE_UPPER)
        self._send_mask(mask_blue)


    def _process_yolo_tracking(self, frame: cv2.Mat) -> None:
        """
        YOLO_TRACKING 模式：YOLO 物体居中追踪
        
        发送目标的原始像素坐标，由 GimbalController 计算误差。
        """
        if self.yolo_detector is None:
            return
            
        # 设置目标类别为 None（不限制类别），这样就可以框出猫、手机等所有COCO类别物体了
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
        """将 BGR 帧转为 QImage 发送给 UI"""
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            q_image = QImage(rgb.data, w, h, ch * w,
                             QImage.Format.Format_RGB888).copy()
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
