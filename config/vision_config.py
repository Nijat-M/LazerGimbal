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
    FLIP_MODE = "NONE"      # 画面翻转模式: "NONE"(正常), "180"(180°倒装翻转), "V"(垂直翻转), "H"(水平镜像)
    
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

    # ==========================
    # Lazer-Kamera Boresight Kalibrasyonu / 激光-相机 光轴校准
    # ==========================
    # Kamera lazer cikisinin USTUNDE duruyor -> ikisi es eksenli DEGIL.
    # Bu yuzden lazerin gercek vurus noktasi ekran merkezine denk gelmez.
    # 相机装在激光出口【上方】，两者不同轴，所以激光实际落点不在画面正中。
    #
    # Toplam kayma iki bilesenden olusur / 总偏移由两部分组成:
    #   1) SABIT (mekanik egiklik): mesafeden bagimsiz, piksel cinsinden sabit
    #      固定分量（机械倾斜）：与距离无关，像素值恒定
    #   2) PARALAKS (baz mesafesi): mesafeyle TERS orantili, uzakta kuculur
    #      视差分量（基线）：与距离成反比，越远越小
    #
    #   kayma(d) = CENTER_OFFSET + PARALLAX_AT_1M / d
    #
    # Tek mesafede kalibre ederseniz PARALLAX_AT_1M = 0 birakin;
    # 5/10/15 m'nin ucunde de vurmak istiyorsaniz iki mesafede olcup doldurun.
    # 只在一个距离校准就把 PARALLAX 留 0；要在 5/10/15 米都打准就测两个距离。
    CENTER_OFFSET_X = 0      # sabit bilesen (px) / 固定分量
    CENTER_OFFSET_Y = 0
    PARALLAX_X_AT_1M = 0.0   # 1 m'deki paralaks (px) / 1米处的视差量
    PARALLAX_Y_AT_1M = 0.0
    CALIB_PATH = "config/crosshair_calibration.json"

    # Aktif atis mesafesi (m). Paralaks duzeltmesi bunu kullanir.
    # 当前交战距离(米)，视差修正用它。None = 只用固定偏移。
    # Yarismada mesafe bilindigi icin (5/10/15 m) arayuzden secilir.
    # 比赛里距离是已知的，界面上直接选。
    AKTIF_MESAFE_M = None

    @classmethod
    def aim_point(cls, mesafe_m=None):
        """Lazerin GERCEKTEN vuracagi ekran noktasi.
           激光【实际】会打到的屏幕点。云台要把目标驱动到这里，而不是画面正中。"""
        ox, oy = cls.CENTER_OFFSET_X, cls.CENTER_OFFSET_Y
        if mesafe_m and mesafe_m > 0.2:
            ox += cls.PARALLAX_X_AT_1M / mesafe_m
            oy += cls.PARALLAX_Y_AT_1M / mesafe_m
        return int(round(cls.CENTER_X + ox)), int(round(cls.CENTER_Y + oy))

    @classmethod
    def set_center_offset(cls, ox: int, oy: int):
        cls.CENTER_OFFSET_X, cls.CENTER_OFFSET_Y = int(ox), int(oy)
        return cls.CENTER_OFFSET_X, cls.CENTER_OFFSET_Y

    @classmethod
    def adjust_center_offset(cls, dx: int, dy: int):
        return cls.set_center_offset(cls.CENTER_OFFSET_X + dx,
                                     cls.CENTER_OFFSET_Y + dy)

    @classmethod
    def reset_center_offset(cls):
        cls.PARALLAX_X_AT_1M = cls.PARALLAX_Y_AT_1M = 0.0
        return cls.set_center_offset(0, 0)

    @classmethod
    def solve_parallax(cls, d1, off1, d2, off2):
        """Iki mesafedeki olcumden sabit + paralaks bilesenlerini cozer.
           由两个距离的实测偏移解出【固定分量】和【视差分量】。
           off = (dx, dy) piksel. Ornek / 例: solve_parallax(5,(-40,-55), 15,(-18,-25))"""
        for i, (o1, o2) in enumerate(zip(off1, off2)):
            # o = C + P/d  ->  P = (o1-o2)/(1/d1 - 1/d2),  C = o1 - P/d1
            denom = (1.0 / d1) - (1.0 / d2)
            P = (o1 - o2) / denom if abs(denom) > 1e-9 else 0.0
            C = o1 - P / d1
            if i == 0:
                cls.PARALLAX_X_AT_1M, cls.CENTER_OFFSET_X = P, int(round(C))
            else:
                cls.PARALLAX_Y_AT_1M, cls.CENTER_OFFSET_Y = P, int(round(C))
        return (cls.CENTER_OFFSET_X, cls.CENTER_OFFSET_Y,
                cls.PARALLAX_X_AT_1M, cls.PARALLAX_Y_AT_1M)

    # calibration_panel.py'nin bekledigi kisa adlar / 面板期望的简写接口
    @classmethod
    def get_center_x(cls):
        """Nisangahin ekrandaki X'i (offset uygulanmis) / 十字线屏幕 X（含偏移）"""
        return cls.aim_point(cls.AKTIF_MESAFE_M)[0]

    @classmethod
    def get_center_y(cls):
        return cls.aim_point(cls.AKTIF_MESAFE_M)[1]

    @classmethod
    def save_calibration(cls):
        try:
            cls.save_crosshair_calibration()
            return True
        except Exception:
            return False

    @classmethod
    def load_crosshair_calibration(cls):
        import json, os
        try:
            if os.path.exists(cls.CALIB_PATH):
                d = json.load(open(cls.CALIB_PATH, encoding="utf-8"))
                cls.CENTER_OFFSET_X = int(d.get("offset_x", 0))
                cls.CENTER_OFFSET_Y = int(d.get("offset_y", 0))
                cls.PARALLAX_X_AT_1M = float(d.get("parallax_x_at_1m", 0.0))
                cls.PARALLAX_Y_AT_1M = float(d.get("parallax_y_at_1m", 0.0))
                return True
        except Exception:
            pass
        return False

    @classmethod
    def save_crosshair_calibration(cls):
        import json, os
        os.makedirs(os.path.dirname(cls.CALIB_PATH) or ".", exist_ok=True)
        json.dump({
            "offset_x": cls.CENTER_OFFSET_X,
            "offset_y": cls.CENTER_OFFSET_Y,
            "parallax_x_at_1m": cls.PARALLAX_X_AT_1M,
            "parallax_y_at_1m": cls.PARALLAX_Y_AT_1M,
            "description": "Laser-camera boresight. aim = center + offset + parallax/distance_m",
        }, open(cls.CALIB_PATH, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
        return cls.CALIB_PATH
    PIXELS_PER_DEGREE = 20  # 像素到角度转换系数（估算值）
    
    # ==========================
    # 颜色阈值 - 蓝色物体
    # ==========================
    # 蓝色在 100-140 度
    # 提高V下限(30->60)和S下限(100->140)，避免黑色物体和阴影被误判为蓝色
    HSV_BLUE_LOWER = np.array([100, 140, 60])
    HSV_BLUE_UPPER = np.array([140, 255, 255])
    
    # ==========================
    # 形态学参数
    # ==========================
    MORPHOLOGY_KERNEL_SIZE = 5      # 形态学操作核大小
    MIN_CONTOUR_AREA = 50           # 最小轮廓面积（过滤噪点）

    # ==========================
    # YOLO 目标检测模型设置
    # ==========================
    DEFAULT_YOLO_MODEL = "vision/models/yetenek6_best.pt"  # 默认使用最新训练的防空国防目标模型
    YOLO_CONF_THRESHOLD = 0.30                             # 敏捷置信度阈值 0.30，有效捕获细长导弹与远距无人机
    YOLO_TARGET_CLASS = None                               # 默认追踪目标类别 (None: 视野内全部目标)
    YOLO_MIN_BOX_SIZE = 4                                  # 最小有效目标框边长（允许细长导弹通过）

    # Military / Defense targets and standard COCO class friendly labels (100% English)
    CLASS_LABELS_EN = {
        "BALISTIK_FUZE": "Ballistic Missile",
        "F16": "F-16 Fighter Jet",
        "HELIKOPTER": "Helicopter",
        "MINI_IHA": "Mini UAV / Drone",
        "person": "Person",
        "airplane": "Airplane",
        "drone": "UAV / Drone",
        "car": "Vehicle / Car"
    }
    
    @classmethod
    def get_blue_range(cls):
        """
        Returns blue HSV range for cv2.inRange
        """
        return (cls.HSV_BLUE_LOWER, cls.HSV_BLUE_UPPER)

    @classmethod
    def get_class_display_name(cls, class_name: str) -> str:
        """Get friendly English display name for class"""
        return cls.CLASS_LABELS_EN.get(class_name, class_name)

