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

import cv2
import time
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from config.vision_config import VisionConfig
from vision.detector import TargetDetector


class VisionWorker(QThread):
    """
    视觉处理线程

    信号说明：
        frame_signal      : 发送处理后的画面（给 UI 显示）
        mask_signal       : 发送调试蒙版（给 UI 调试显示）
        control_signal    : 发送误差 (err_x, err_y)（TRACKING 模式，激光追蓝色）
        target_pos_signal : 发送目标位置 (pos_x, pos_y)（BLUE_TRACKING 模式，居中追踪）
    """

    frame_signal = pyqtSignal(QImage)       # 处理后的画面
    mask_signal = pyqtSignal(QImage)        # 调试蒙版
    control_signal = pyqtSignal(int, int)   # 误差信号 (TRACKING 模式)
    target_pos_signal = pyqtSignal(int, int)  # 原始坐标 (BLUE_TRACKING 模式)

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

        # 状态跟踪（避免重复打印）
        self.blue_object_detected: bool = False
        self.laser_tracking_status = None  # "both" | "blue_only" | "none"

    # --------------------------------------------------
    # 公共接口
    # --------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """设置工作模式"""
        self.mode = mode
        print(f"[VISION] 视觉线程模式: {mode}")

    def switch_camera(self, camera_id: int, width: int, height: int) -> None:
        """动态切换摄像头"""
        print(f"[VISION] 切换摄像头: ID={camera_id}, {width}x{height}")

        self.camera_id = camera_id
        self.frame_width = width
        self.frame_height = height

        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            time.sleep(0.5)

        self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            print("[VISION] DSHOW后端失败，尝试默认后端...")
            self.cap = cv2.VideoCapture(self.camera_id)

        if not self.cap.isOpened():
            print(f"[VISION ERROR] 无法打开摄像头 ID={camera_id}")
            self.camera_ready = False
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        self.cap.set(cv2.CAP_PROP_FPS, VisionConfig.TARGET_FPS)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        time.sleep(0.3)
        for _ in range(5):
            self.cap.read()  # 预热

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        print(f"[VISION] ✓ 摄像头就绪: {actual_w}x{actual_h} @ {actual_fps}fps")

        self.camera_ready = True

    def stop(self) -> None:
        """停止线程"""
        self.is_running = False
        self.quit()
        self.wait()

    # --------------------------------------------------
    # 主循环
    # --------------------------------------------------

    def run(self) -> None:
        """线程主循环"""
        print("[VISION] 视觉线程已启动，等待摄像头初始化...")

        while self.is_running and not self.camera_ready:
            time.sleep(0.1)

        if not self.is_running:
            print("[VISION] 线程退出")
            return

        print("[VISION] 摄像头初始化完成，开始处理画面")
        error_count = 0

        while self.is_running:
            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()

            if not ret or frame is None:
                error_count += 1
                if error_count <= 5:
                    print(f"[VISION ERROR] 读取帧失败 ({error_count}/5)")
                elif error_count == 100:
                    print("[VISION ERROR] 持续读取失败，请检查摄像头连接")
                    error_count = 0
                time.sleep(0.1)
                continue

            error_count = 0

            try:
                if self.mode == "TRACKING":
                    self._process_tracking(frame)
                elif self.mode == "BLUE_TRACKING":
                    self._process_blue_tracking(frame)
                else:
                    self._send_image(frame)  # IDLE：只显示原图
            except Exception as e:
                print(f"[VISION ERROR] 模式 {self.mode} 处理出错: {e}")
                import traceback
                traceback.print_exc()

            time.sleep(0.01)  # 10ms，避免CPU占用过高

        print("[VISION] 线程退出，释放摄像头")
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
                print("[VISION] ✓ 同时检测到蓝色目标和红色激光")
                self.laser_tracking_status = "both"

        elif blue_result.detected and not laser_result.detected:
            if self.laser_tracking_status != "blue_only":
                print("[VISION] 找到蓝色目标，但红色激光丢失")
                self.laser_tracking_status = "blue_only"
        else:
            if self.laser_tracking_status not in (None, "none"):
                print("[VISION] 未检测到目标")
                self.laser_tracking_status = "none"

        # 调试蒙版
        debug_mask = self.detector.get_debug_mask(frame)
        self._send_mask(debug_mask)
        self._send_image(frame)

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

            # 显示坐标信息（调试用）
            raw_ex = pos[0] - cx
            raw_ey = pos[1] - cy
            cv2.putText(frame, f"Pos: ({pos[0]}, {pos[1]}) Err: ({raw_ex}, {raw_ey})",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            # 发送原始坐标（不是误差！）→ handle_target_position
            self.target_pos_signal.emit(pos[0], pos[1])

            if not self.blue_object_detected:
                print("[VISION] ✓ 找到蓝色目标")
                self.blue_object_detected = True
        else:
            if self.blue_object_detected:
                print("[VISION] ✗ 未找到蓝色目标")
                self.blue_object_detected = False

        # 调试蒙版（蓝色检测范围）
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask_blue = cv2.inRange(hsv, VisionConfig.HSV_BLUE_LOWER, VisionConfig.HSV_BLUE_UPPER)
        self._send_mask(mask_blue)
        self._send_image(frame)

    # --------------------------------------------------
    # 图像发送工具
    # --------------------------------------------------

    def _send_image(self, frame: cv2.Mat) -> None:
        """将 BGR 帧转为 QImage 发送给 UI"""
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            q_image = QImage(rgb.data, w, h, ch * w,
                             QImage.Format.Format_RGB888).copy()
            self.frame_signal.emit(q_image)
        except Exception as e:
            print(f"[VISION ERROR] send_image failed: {e}")

    def _send_mask(self, mask: cv2.Mat) -> None:
        """将单通道蒙版发送给 UI（调试用）"""
        try:
            h, w = mask.shape
            q_image = QImage(mask.data, w, h, w,
                             QImage.Format.Format_Grayscale8).copy()
            self.mask_signal.emit(q_image)
        except Exception as e:
            print(f"[VISION ERROR] send_mask failed: {e}")
