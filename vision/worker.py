# -*- coding: utf-8 -*-
import cv2
import numpy as np
import time
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage
import sys

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

    def set_mode(self, mode):
        """ 设置工作模式 """
        self.mode = mode
        print(f"[VISION] 视觉线程模式: {mode}")

    def run(self):
        """
        线程主循环 (Thread Main Loop)
        不断的读取摄像头 -> 处理 -> 发送结果
        """
        # 打开摄像头 (ID 0 通常是默认摄像头)
        self.cap = cv2.VideoCapture(cfg.CAMERA_ID)
        
        # 设置分辨率 (降低分辨率可以提高处理速度 fps)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.FRAME_HEIGHT)

        if not self.cap.isOpened():
            print("无法打开摄像头")
            return

        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # 核心处理逻辑
            try:
                if self.mode == "TRACKING":
                    self.process_tracking(frame)
                else:
                    # IDLE 模式，只显示原图，不进行复杂就算
                    self.send_image(frame)
            except Exception as e:
                print(f"[VISION ERROR] 模式 {self.mode} 处理出错: {e}")
                import traceback
                traceback.print_exc()

            # 帧率控制优化：减少不必要的延迟
            # 视觉处理越快，控制延迟越小
            time.sleep(0.001)  # 1ms，保持CPU友好的同时减少延迟

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
            
        elif blue_pos and not red_pos:
            # 看到蓝色目标但没看到激光
            # 可能是激光跑出画面或被遮挡
            if self.frame_count % 60 == 0:
                print("[VISION] 找到蓝色目标，但红色激光丢失")
        else:
            # 两者都没找到或只找到激光
            pass
        
        # 发送调试画面
        self.send_mask(debug_mask)
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
