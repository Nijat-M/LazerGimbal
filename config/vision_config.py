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

    # ==========================================================================
    # 激光-相机 光轴视差校准模型 (Laser-Camera Boresight Parallax Calibration)
    # ==========================================================================
    # 【物理与光学视差原理 (Optical Parallax Mechanics)】
    # 相机镜头安装在高功率激光发射管的正上方，两者光轴在物理空间中存在间距（基线 Baseline），
    # 并非共轴系统。因此，激光光斑在相机画面上的实际像素落点绝对不会恰好落在画面正中 (Width/2, Height/2)。
    #
    # 任意目标距离 d (米) 下，激光在画面上的总像素偏移量由两大物理分量叠加而成:
    #   offset(d) = CENTER_OFFSET + PARALLAX_AT_1M / d
    #
    #   1. 固定角度倾斜分量 (CENTER_OFFSET):
    #      由相机支架与激光管的微小机械倾角误差导致，与目标距离 d 无关，属于常数偏移项 (像素 px)；
    #   2. 物理光轴视差分量 (PARALLAX_AT_1M / d):
    #      由相机与激光管的物理中心距基线产生，与目标交战距离 d 成严格反比（距离越远视差越小，无限远趋向于 0）。
    #
    # 【双距离快速校准法 (Dual-Distance Calibration)】
    #   若仅在固定单一距离下射击，保持 PARALLAX_AT_1M = 0 即可；
    #   若需要在 5m、10m、15m 多级交战距离下均实现直打红心，只需在两个距离测出实际偏移，
    #   调用 solve_parallax(d1, off1, d2, off2) 即可自动联立解析出精准的机械倾角与视差基线！
    CENTER_OFFSET_X = 0      # X 轴固定机械倾角偏移量 (像素 px)
    CENTER_OFFSET_Y = 0      # Y 轴固定机械倾角偏移量 (像素 px)
    PARALLAX_X_AT_1M = 0.0   # 1 米标准基准距离下的 X 轴物理视差量 (像素 px)
    PARALLAX_Y_AT_1M = 0.0   # 1 米标准基准距离下的 Y 轴物理视差量 (像素 px)
    CALIB_PATH = "config/crosshair_calibration.json"

    # 当前比赛/测试设定的交战距离 (单位: 米)。
    # 视差修正函数将依据此距离动态微调落点。若为 None 则退化为仅使用固定偏移模式。
    # 竞赛中交战距离已知固定（如 5m / 10m / 15m），可在 GUI 界面直接一键选择。
    AKTIF_MESAFE_M = None

    # 光轴校准视场补偿模式 (Boresight Correction Mode):
    #   "offset" (准星偏移模式): 
    #       保持摄像头完整原始视场 (Full FOV)，将瞄准十字准星动态平移到激光真实击打落点。
    #       优点: 零裁剪、视场最大、目标丢失率最低。
    #   "crop" (对称裁剪居中模式): 
    #       以激光真实落点为对称中心，对输入画面进行裁切，使十字准星依然呈现在视窗正中央。
    #       代价: 损失边缘部分视场 (水平损失 2*|ox| 像素，垂直损失 2*|oy| 像素)。
    BORESIGHT_MODE = "offset"

    @classmethod
    def get_calibrated_aim_coords(cls, frame_w: int, frame_h: int) -> tuple[int, int]:
        """
        获取在指定分辨率画面 (frame_w, frame_h) 下激光实际瞄准点的绝对像素坐标 (aim_x, aim_y)

        无论是 Crop 模式还是 Offset 模式，均确保大屏准星与画中画局部放大镜完全共轴对齐。

        Args:
            frame_w: 当前帧图像宽度（像素）
            frame_h: 当前帧图像高度（像素）

        Returns:
            tuple[int, int]: 激光落点绝对坐标 (aim_x, aim_y)
        """
        if cls.BORESIGHT_MODE == "crop":
            return int(frame_w // 2), int(frame_h // 2)
        ox, oy = cls.raw_offset(cls.AKTIF_MESAFE_M)
        aim_x = max(0, min(frame_w - 1, frame_w // 2 + ox))
        aim_y = max(0, min(frame_h - 1, frame_h // 2 + oy))
        return int(aim_x), int(aim_y)

    @classmethod
    def aim_point(cls, mesafe_m=None) -> tuple[int, int]:
        """
        获取当前距离下激光物理光斑在 640x480 参考画面中的实际落点

        控制原理:
            云台自动闭环追踪的根本目标是将目标驱动到【此落点】，而非画面的几何中心！

        Args:
            mesafe_m: 当前目标距离 (米)，若为 None 则读取全局 AKTIF_MESAFE_M

        Returns:
            tuple[int, int]: 激光落点在参考坐标系下的坐标 (aim_x, aim_y)
        """
        if cls.BORESIGHT_MODE == "crop":
            return int(cls.CENTER_X), int(cls.CENTER_Y)
        ox, oy = cls.CENTER_OFFSET_X, cls.CENTER_OFFSET_Y
        if mesafe_m and mesafe_m > 0.2:
            ox += cls.PARALLAX_X_AT_1M / mesafe_m
            oy += cls.PARALLAX_Y_AT_1M / mesafe_m
        return int(round(cls.CENTER_X + ox)), int(round(cls.CENTER_Y + oy))

    @classmethod
    def raw_offset(cls, mesafe_m=None) -> tuple[int, int]:
        """
        计算相对于画面中心的原始视差偏差矢量 (ox, oy)（单位: 像素 px）

        Args:
            mesafe_m: 当前目标物理距离（米）

        Returns:
            tuple[int, int]: 偏移量分量 (ox, oy)
        """
        ox, oy = float(cls.CENTER_OFFSET_X), float(cls.CENTER_OFFSET_Y)
        if mesafe_m and mesafe_m > 0.2:
            ox += cls.PARALLAX_X_AT_1M / mesafe_m
            oy += cls.PARALLAX_Y_AT_1M / mesafe_m
        return int(round(ox)), int(round(oy))

    @classmethod
    def set_center_offset(cls, ox: int, oy: int) -> tuple[int, int]:
        """设置固定机械倾角偏移分量 (ox, oy)"""
        cls.CENTER_OFFSET_X, cls.CENTER_OFFSET_Y = int(ox), int(oy)
        return cls.CENTER_OFFSET_X, cls.CENTER_OFFSET_Y

    @classmethod
    def adjust_center_offset(cls, dx: int, dy: int) -> tuple[int, int]:
        """在当前固定倾角偏移基础上进行增量微调"""
        return cls.set_center_offset(cls.CENTER_OFFSET_X + dx,
                                     cls.CENTER_OFFSET_Y + dy)

    @classmethod
    def reset_center_offset(cls) -> tuple[int, int]:
        """重置所有光轴校准参数至初始零位"""
        cls.PARALLAX_X_AT_1M = cls.PARALLAX_Y_AT_1M = 0.0
        return cls.set_center_offset(0, 0)

    @classmethod
    def solve_parallax(cls, d1: float, off1: tuple[int, int], d2: float, off2: tuple[int, int]):
        """
        双距离实测偏移联立求解机械倾角固定分量 (C) 与物理视差基线分量 (P)

        数学推导原理:
            已知在距离 d1 处测得偏移 o1，在距离 d2 处测得偏移 o2:
                o1 = C + P / d1
                o2 = C + P / d2
            两式相减消除常数 C:
                o1 - o2 = P * (1/d1 - 1/d2)
            从而解出:
                P = (o1 - o2) / (1/d1 - 1/d2)
                C = o1 - P / d1

        使用范例:
            # 5 米处实测偏移 (-40, -55)，15 米处实测偏移 (-18, -25)
            solve_parallax(5.0, (-40, -55), 15.0, (-18, -25))

        Args:
            d1: 第一个测量距离（米）
            off1: 第一个距离下的实测像素偏移 (dx1, dy1)
            d2: 第二个测量距离（米）
            off2: 第二个距离下的实测像素偏移 (dx2, dy2)

        Returns:
            tuple: (CENTER_OFFSET_X, CENTER_OFFSET_Y, PARALLAX_X_AT_1M, PARALLAX_Y_AT_1M)
        """
        for i, (o1, o2) in enumerate(zip(off1, off2)):
            denom = (1.0 / d1) - (1.0 / d2)
            P = (o1 - o2) / denom if abs(denom) > 1e-9 else 0.0
            C = o1 - P / d1
            if i == 0:
                cls.PARALLAX_X_AT_1M, cls.CENTER_OFFSET_X = P, int(round(C))
            else:
                cls.PARALLAX_Y_AT_1M, cls.CENTER_OFFSET_Y = P, int(round(C))
        return (cls.CENTER_OFFSET_X, cls.CENTER_OFFSET_Y,
                cls.PARALLAX_X_AT_1M, cls.PARALLAX_Y_AT_1M)

    # --------------------------------------------------------------------------
    # 快捷访问与持久化接口 (供 CalibrationPanel 调校面板调用)
    # --------------------------------------------------------------------------
    @classmethod
    def get_center_x(cls) -> int:
        """获取当前距离下带偏移修正的准星 X 像素坐标"""
        return cls.aim_point(cls.AKTIF_MESAFE_M)[0]

    @classmethod
    def get_center_y(cls) -> int:
        """获取当前距离下带偏移修正的准星 Y 像素坐标"""
        return cls.aim_point(cls.AKTIF_MESAFE_M)[1]

    @classmethod
    def save_calibration(cls):
        try:
            return cls.save_crosshair_calibration()
        except Exception:
            return False

    @classmethod
    def load_crosshair_calibration(cls):
        import json, os
        try:
            if os.path.exists(cls.CALIB_PATH):
                with open(cls.CALIB_PATH, "r", encoding="utf-8") as f:
                    d = json.load(f)
                cls.CENTER_OFFSET_X = int(d.get("offset_x", 0))
                cls.CENTER_OFFSET_Y = int(d.get("offset_y", 0))
                cls.PARALLAX_X_AT_1M = float(d.get("parallax_x_at_1m", 0.0))
                cls.PARALLAX_Y_AT_1M = float(d.get("parallax_y_at_1m", 0.0))
                cls.BORESIGHT_MODE = str(d.get("boresight_mode", "offset"))
                rng = d.get("range_m", None)
                cls.AKTIF_MESAFE_M = float(rng) if rng is not None else None
                return True
        except Exception as e:
            pass
        return False

    @classmethod
    def save_crosshair_calibration(cls):
        import json, os
        try:
            os.makedirs(os.path.dirname(cls.CALIB_PATH) or ".", exist_ok=True)
            payload = {
                "offset_x": int(cls.CENTER_OFFSET_X),
                "offset_y": int(cls.CENTER_OFFSET_Y),
                "parallax_x_at_1m": float(cls.PARALLAX_X_AT_1M),
                "parallax_y_at_1m": float(cls.PARALLAX_Y_AT_1M),
                "boresight_mode": str(cls.BORESIGHT_MODE),
                "range_m": float(cls.AKTIF_MESAFE_M) if cls.AKTIF_MESAFE_M is not None else None,
                "description": "Laser-camera boresight calibration configuration",
            }
            with open(cls.CALIB_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False
    PIXELS_PER_DEGREE = 20  # 像素到角度转换系数（估算值）
    
    # ==========================
    # 颜色阈值 - 蓝色物体 (基础 HSV 模式)
    # ==========================
    # 蓝色在 100-140 度
    # 提高V下限(30->60)和S下限(100->140)，避免黑色物体和阴影被误判为蓝色
    HSV_BLUE_LOWER = np.array([100, 140, 60])
    HSV_BLUE_UPPER = np.array([140, 255, 255])
    
    # ==========================
    # 敌我识别 (IFF) 光照与多色彩空间自适应参数
    # ==========================
    # 走廊/复杂光照自适应参数
    IFF_LIGHTING_MODE = "AUTO"             # "AUTO", "HALLWAY_WARM", "STANDARD"
    IFF_MIN_FOREGROUND_RATIO = 0.05        # 目标前景区域中颜色有效像素最低占比 (5%)
    IFF_DOMINANCE_RATIO = 1.25             # 主导色彩与竞争色彩的比值门限 (1.25x)
    IFF_MIN_VALID_PIXELS = 6               # 最小有效色彩像素数
    
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


