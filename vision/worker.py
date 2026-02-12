# -*- coding: utf-8 -*-
import os
import sys

# 抑制OpenCV警告
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'

import cv2
import numpy as np
import time
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage

# 尝试导入 Config
try:
    from config import cfg
except ImportError:
    sys.path.append("..")
    from config import cfg

class VisionWorker(QThread):
    """
    视觉处理线程 (Vision Processing Thread)
    
    [原理 Principle]
    视觉处理通过 OpenCV 读取每一帧图像，进行一系列过滤和计算，
    最终得出"误差" (Error)，即目标偏离中心的距离。
    
    这个误差被发送给 Main Window 的控制循环 (PID Controller) 来驱动舵机。
    
    我们将视觉处理单独放在一个线程中，是因为图像处理是计算密集型任务。
    如果放在主线程，会严重卡顿界面。
    """
    
    # [信号 Signals]
    frame_signal = pyqtSignal(QImage)           # 发送处理后的画面给 UI 显示
    mask_signal = pyqtSignal(QImage)            # 发送二值化蒙版 (Mask) 给 UI 调试
    control_signal = pyqtSignal(int, int)       # 发送误差信号 (Error X, Error Y)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.frame_count = 0
        self.mode = "IDLE"  # 模式: "IDLE" (待机), "TRACKING" (追踪)
        self.cap = None
        self.camera_id = cfg.CAMERA_ID
        self.frame_width = cfg.FRAME_WIDTH
        self.frame_height = cfg.FRAME_HEIGHT
        self.camera_ready = False  # 摄像头是否就绪
        self.blue_object_detected = False  # 蓝色物体检测状态（避免刷屏）        self.laser_tracking_status = None  # 激光追踪状态: "both", "blue_only", "none"
    def set_mode(self, mode):
        """ 设置工作模式 """
        self.mode = mode
        print(f"[VISION] 视觉线程模式: {mode}")
    
    def switch_camera(self, camera_id, width, height):
        """
        动态切换摄像头 (Dynamic Camera Switching)
        :param camera_id: 摄像头ID
        :param width: 分辨率宽度
        :param height: 分辨率高度
        """
        print(f"[VISION] 切换摄像头: ID={camera_id}, {width}x{height}")
        
        # 保存新参数
        self.camera_id = camera_id
        self.frame_width = width
        self.frame_height = height
        
        # 释放旧摄像头
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            time.sleep(0.5)  # 等待摄像头完全释放
        
        # 打开新摄像头
        self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
        
        if not self.cap.isOpened():
            print(f"[VISION] DSHOW后端失败，尝试默认后端...")
            self.cap = cv2.VideoCapture(self.camera_id)
        
        if not self.cap.isOpened():
            print(f"[VISION ERROR] 无法打开摄像头 ID={camera_id}")
            self.camera_ready = False
            return
        
        # 设置参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        self.cap.set(cv2.CAP_PROP_FPS, 60)  # 尝试60fps
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 禁用缓冲
        
        # 等待摄像头稳定
        time.sleep(0.3)
        
        # 读取几帧预热
        for _ in range(5):
            self.cap.read()
        
        # 获取实际设置的参数
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        print(f"[VISION] ✓ 摄像头就绪: {actual_width}x{actual_height} @ {actual_fps}fps")
        
        # 标记摄像头已就绪
        self.camera_ready = True

    def run(self):
        """
        线程主循环 (Thread Main Loop)
        不断的读取摄像头 -> 处理 -> 发送结果
        """
        print(f"[VISION] 视觉线程已启动，等待摄像头初始化...")
        
        # 等待摄像头就绪（通过switch_camera或用户点击应用设置触发）
        while self.is_running and not self.camera_ready:
            time.sleep(0.1)
        
        if not self.is_running:
            print("[VISION] 线程退出")
            return
        
        print(f"[VISION] 摄像头初始化完成，开始处理画面")
        
        frame_count = 0
        error_count = 0  # 连续错误计数

        while self.is_running:
            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                continue
            
            ret, frame = self.cap.read()
            
            if not ret or frame is None:
                error_count += 1
                # 只在前5次错误时打印，避免刷屏
                if error_count <= 5:
                    print(f"[VISION ERROR] 读取帧失败 ({error_count}/5)")
                elif error_count == 100:
                    print(f"[VISION ERROR] 持续读取失败，请检查摄像头连接")
                    error_count = 0  # 重置计数
                time.sleep(0.1)
                continue
            
            # 读取成功，重置错误计数
            error_count = 0
            frame_count += 1

            # 核心处理逻辑
            try:
                if self.mode == "TRACKING":
                    self.process_tracking(frame)
                elif self.mode == "BLUE_TRACKING":
                    self.process_blue_tracking(frame)
                else:
                    # IDLE 模式，只显示原图，不进行复杂计算
                    self.send_image(frame)
            except Exception as e:
                print(f"[VISION ERROR] 模式 {self.mode} 处理出错: {e}")
                import traceback
                traceback.print_exc()

            # 帧率控制优化：减少不必要的延迟
            # 视觉处理越快，控制延迟越小
            time.sleep(0.01)  # 10ms，避免CPU占用过高

        print("[VISION] 线程退出，释放摄像头")
        if self.cap is not None:
            self.cap.release()

    def process_tracking(self, frame):
        """
        [算法核心] 视觉追踪 Visual Tracking
        
        流程 Pipeline:
        1. BGR -> HSV: 转换颜色空间，HSV 对光照变化更鲁棒。
        2. inRange: 根据阈值提取特定颜色的像素，得到二值图 (Mask)。
        3. Morphology: 形态学操作(开运算/闭运算) 去除噪点。
        4. findContours: 寻找连通区域(轮廓)。
        5. minEnclosingCircle/Moments: 计算轮廓中心。
        6. Error calc: 计算目标中心与画面中心的偏差。
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 形态学核 (Kernel)
        kernel = np.ones((5, 5), np.uint8)

        # === 蓝色物体追踪模式 (Blue Object Tracking) ===
        # 目标: 控制红色激光点 (Red Laser) 去追踪 蓝色物体 (Blue Target)
        # 误差 = 蓝色目标位置 - 红色激光位置
        
        # 1. 寻找蓝色物体
        mask_blue = cv2.inRange(hsv, cfg.HSV_BLUE_LOWER, cfg.HSV_BLUE_UPPER)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_OPEN, kernel)  # 去噪
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel) # 填孔
        
        # 2. 寻找红色激光点 (激光点可能很小/亮)
        mask_red1 = cv2.inRange(hsv, cfg.HSV_RED_LOWER1, cfg.HSV_RED_UPPER1)
        mask_red2 = cv2.inRange(hsv, cfg.HSV_RED_LOWER2, cfg.HSV_RED_UPPER2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_OPEN, kernel)
        
        # 调试显示: 合并显示两个 Mask
        debug_mask = cv2.bitwise_or(mask_blue, mask_red)

        # 寻找轮廓
        cnts_blue, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts_red, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        blue_pos = None
        red_pos = None
        
        # 获取蓝色最大轮廓
        if cnts_blue:
            c_b = max(cnts_blue, key=cv2.contourArea)
            if cv2.contourArea(c_b) > 100: # 面积过滤
                ((bx, by), br) = cv2.minEnclosingCircle(c_b)
                blue_pos = (int(bx), int(by))
                # 在原图画圈标记
                cv2.circle(frame, blue_pos, int(br), (255, 0, 0), 2)
                cv2.putText(frame, "Target", (blue_pos[0]-10, blue_pos[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 2)

        # 获取红色最大轮廓
        if cnts_red:
            c_r = max(cnts_red, key=cv2.contourArea)
            if cv2.contourArea(c_r) > 5: # 激光点很小，阈值要低
                ((rx, ry), rr) = cv2.minEnclosingCircle(c_r)
                red_pos = (int(rx), int(ry))
                cv2.circle(frame, red_pos, 5, (0, 0, 255), -1)

        # [计算控制信号]
        if blue_pos and red_pos:
            # 只有当两个都找到时，才能计算相对误差
            # 目标：让红色激光(Laser)移动到蓝色目标(Target)位置
            # Error = Target - Laser
            error_x = blue_pos[0] - red_pos[0]
            error_y = blue_pos[1] - red_pos[1]
            
            # 画出误差向量线（绿色箭头）
            cv2.arrowedLine(frame, red_pos, blue_pos, (0, 255, 0), 2)
            
            # 发送控制信号
            self.control_signal.emit(error_x, error_y)
            
            # 状态变化时打印
            if self.laser_tracking_status != "both":
                print("[VISION] ✓ 同时检测到蓝色目标和红色激光")
                self.laser_tracking_status = "both"
            
        elif blue_pos and not red_pos:
            # 看到蓝色目标但没看到激光
            # 只在状态变化时打印
            if self.laser_tracking_status != "blue_only":
                print("[VISION] 找到蓝色目标，但红色激光丢失")
                self.laser_tracking_status = "blue_only"
        else:
            # 两者都没找到或只找到激光
            if self.laser_tracking_status != "none" and self.laser_tracking_status is not None:
                print("[VISION] 未检测到目标")
                self.laser_tracking_status = "none"
        
        # 发送调试画面
        self.send_mask(debug_mask)
        self.send_image(frame)

    def process_blue_tracking(self, frame):
        """
        [新功能] 蓝色物体居中追踪模式 (Blue Object Centering Mode)
        
        流程 Pipeline:
        1. 检测蓝色物体
        2. 计算蓝色物体中心相对于画面中心的偏差
        3. 发送误差信号给控制器，让云台移动使蓝色物体居中
        
        与 TRACKING 模式的区别:
        - TRACKING: 红色激光追踪蓝色物体（误差 = 蓝色位置 - 红色位置）
        - BLUE_TRACKING: 蓝色物体居中（误差 = 蓝色位置 - 画面中心）
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 形态学核
        kernel = np.ones((5, 5), np.uint8)
        
        # 检测蓝色物体
        mask_blue = cv2.inRange(hsv, cfg.HSV_BLUE_LOWER, cfg.HSV_BLUE_UPPER)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_OPEN, kernel)  # 去噪
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel) # 填孔
        
        # 寻找轮廓
        cnts_blue, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 画面中心点
        center_x = self.frame_width // 2
        center_y = self.frame_height // 2
        
        # 在画面上画中心十字线（用于调试）
        cv2.line(frame, (center_x - 20, center_y), (center_x + 20, center_y), (0, 255, 255), 1)
        cv2.line(frame, (center_x, center_y - 20), (center_x, center_y + 20), (0, 255, 255), 1)
        cv2.circle(frame, (center_x, center_y), 5, (0, 255, 255), 2)
        
        blue_pos = None
        
        # 获取蓝色最大轮廓
        if cnts_blue:
            c_b = max(cnts_blue, key=cv2.contourArea)
            if cv2.contourArea(c_b) > 100:  # 面积过滤
                ((bx, by), br) = cv2.minEnclosingCircle(c_b)
                blue_pos = (int(bx), int(by))
                
                # 在原图画圈标记蓝色目标
                cv2.circle(frame, blue_pos, int(br), (255, 0, 0), 2)
                cv2.putText(frame, "Target", (blue_pos[0]-20, blue_pos[1]-30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                
                # 计算原始误差：目标位置 - 画面中心
                raw_error_x = blue_pos[0] - center_x
                raw_error_y = blue_pos[1] - center_y
                
                # [关键优化] 死区处理 - 在视觉层面过滤小误差
                # 当目标已经足够接近中心时，不发送控制信号
                deadzone = 30  # 像素死区（可根据实际调整）
                
                if abs(raw_error_x) < deadzone and abs(raw_error_y) < deadzone:
                    # 在死区内，认为已对准
                    cv2.putText(frame, "LOCKED", (center_x - 30, center_y - 40), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    error_x = 0
                    error_y = 0
                else:
                    # [误差缩放] 降低灵敏度，避免过度反应
                    # 自适应缩放：远距离缩放更小，近距离缩放正常
                    error_mag = (raw_error_x**2 + raw_error_y**2)**0.5
                    if error_mag > 150:
                        # 远距离：大幅降低灵敏度
                        scale_factor = 0.4
                    elif error_mag > 80:
                        # 中距离：中等缩放
                        scale_factor = 0.55
                    else:
                        # 近距离：正常缩放
                        scale_factor = 0.65
                    
                    error_x = int(raw_error_x * scale_factor)
                    error_y = int(raw_error_y * scale_factor)
                
                # 画出误差向量线（从中心指向目标，绿色箭头）
                cv2.arrowedLine(frame, (center_x, center_y), blue_pos, (0, 255, 0), 2)
                
                # 显示误差值（原始值和缩放后的值）
                error_text = f"Error: X={raw_error_x}({error_x}), Y={raw_error_y}({error_y})"
                cv2.putText(frame, error_text, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # 发送控制信号
                self.control_signal.emit(error_x, error_y)
                
                # 状态变化时打印（找到了）
                if not self.blue_object_detected:
                    print("[VISION] ✓ 找到蓝色目标")
                    self.blue_object_detected = True
        else:
            # 没找到蓝色目标
            # 只在状态变化时打印一次
            if self.blue_object_detected:
                print("[VISION] ✗ 未找到蓝色目标")
                self.blue_object_detected = False
        
        # 发送调试画面
        self.send_mask(mask_blue)
        self.send_image(frame)



    def send_image(self, frame):
        """ 工具函数: 将 OpenCV (BGR) 图像转换为 Qt (RGB) 图像以便显示 """
        try:
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            # copy() 是必须的，因为 OpenCV 复用内存，而 Qt 需要独立内存，否则会崩溃
            q_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            self.frame_signal.emit(q_image)
        except Exception as e:
            print(f"[VISION ERROR] send_image failed: {e}")

    def send_mask(self, mask):
        """ 工具函数: 发送单通道 Mask """
        try:
            h, w = mask.shape
            bytes_per_line = w
            q_image = QImage(mask.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8).copy()
            self.mask_signal.emit(q_image)
        except Exception as e:
            print(f"[VISION ERROR] send_mask failed: {e}")

    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()
