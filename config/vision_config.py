# -*- coding: utf-8 -*-
"""
视觉参数配置 (Vision Configuration)

[颜色检测原理]
使用 HSV 颜色空间，比 RGB 更适合光照变化的场景。
H (Hue 色调): 0-180，表示颜色种类
S (Saturation 饱和度): 0-255，鲜艳程度
V (Value 明度): 0-255，明暗程度

[调参工具]
可以使用 HSV 颜色拾取器在线调节：https://colorizer.org/
或者运行程序后，在 Debug Mask 窗口查看效果
"""

import numpy as np

class VisionConfig:
    """视觉处理参数 (Vision Processing Parameters)"""
    
    # ==========================
    # 摄像头设置
    # ==========================
    CAMERA_ID = 1           # 摄像头设备ID（0=笔记本内置，1=USB摄像头）
    
    # [分辨率和帧率选择指南]
    # 低分辨率 (320x240): 
    #   优点: CPU占用低，帧率高(60+fps)，系统响应快
    #   缺点: 远距离目标难以识别，图像粗糙
    #   适用: 近距离追踪(<2米)，追求极致响应速度
    #
    # 标准分辨率 (640x480): ★推荐★
    #   优点: 平衡性能与精度，CPU占用适中
    #   缺点: 无明显缺点
    #   适用: 大多数场景(2-5米)，最佳性价比选择
    #
    # 高分辨率 (1280x720, 1920x1080):
    #   优点: 目标细节清晰，远距离识别好
    #   缺点: CPU占用高，帧率可能下降到15-30fps
    #   适用: 远距离追踪(>5米)，电脑性能好
    #
    # [推荐配置]
    # - 追求速度: 640x480 @ 60fps
    # - 追求精度: 1280x720 @ 30fps (需要较好的CPU)
    # - 一般使用: 640x480 @ 30-60fps (最佳平衡)
    # 
    # 注意: 某些摄像头不支持高帧率，系统会自动调整
    
    FRAME_WIDTH = 640       # 图像宽度（推荐: 640 或 1280）
    FRAME_HEIGHT = 480      # 图像高度（推荐: 480 或 720）
    TARGET_FPS = 60         # 目标帧率（实际帧率取决于摄像头硬件）
    
    # ==========================
    # 坐标系统
    # ==========================
    CENTER_X = 320          # 画面中心X（一般是宽度/2）
    CENTER_Y = 240          # 画面中心Y（一般是高度/2）
    PIXELS_PER_DEGREE = 20  # 像素到角度转换系数（估算值）
    
    # ==========================
    # 颜色阈值 - 红色激光点
    # ==========================
    # 红色在 HSV 色轮两端（0° 和 180°），需要两个范围
    # Range 1: 0-10 度（深红）
    HSV_RED_LOWER1 = np.array([0, 100, 100])
    HSV_RED_UPPER1 = np.array([10, 255, 255])
    
    # Range 2: 160-180 度（品红）
    HSV_RED_LOWER2 = np.array([160, 100, 100])
    HSV_RED_UPPER2 = np.array([180, 255, 255])
    
    # ==========================
    # 颜色阈值 - 蓝色物体
    # ==========================
    # 蓝色在 100-140 度
    # 暗光环境优化：降低V下限(50->30)，降低S下限(150->100)
    HSV_BLUE_LOWER = np.array([100, 100, 30])
    HSV_BLUE_UPPER = np.array([140, 255, 255])
    
    # ==========================
    # 形态学参数
    # ==========================
    MORPHOLOGY_KERNEL_SIZE = 5      # 形态学操作核大小
    MIN_CONTOUR_AREA = 50           # 最小轮廓面积（过滤噪点）
    
    @classmethod
    def get_red_ranges(cls):
        """
        返回红色检测的两个 HSV 范围
        Returns tuple of red HSV ranges for cv2.inRange
        """
        return (
            (cls.HSV_RED_LOWER1, cls.HSV_RED_UPPER1),
            (cls.HSV_RED_LOWER2, cls.HSV_RED_UPPER2)
        )
    
    @classmethod
    def get_blue_range(cls):
        """
        返回蓝色检测的 HSV 范围
        Returns blue HSV range for cv2.inRange
        """
        return (cls.HSV_BLUE_LOWER, cls.HSV_BLUE_UPPER)
