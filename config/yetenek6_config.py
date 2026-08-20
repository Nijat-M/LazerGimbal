# -*- coding: utf-8 -*-
"""
Yetenek 6 配置 —— 目标探测与分类 (Hedef Tespit ve Sınıflandırma)

TEKNOFEST 2026 Çelikkubbe 能力 6：
    在 5m / 10m / 15m 三个距离上探测并分类
    F16 / Mini-Micro İHA / Füze / Helikopter，并在界面上展示。

[你可能需要改的只有这几个数]
    HFOV_DEG        : 相机水平视场角，由 s0_kamera.py 实测得出
    HEDEF_GENISLIK_M: 打印靶标的实际宽度（米）
    CONF            : 置信度阈值，检不到就调低，误检多就调高
"""

import os

# 项目根目录 (LazerGimbal/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Yetenek6Config:
    """能力 6 检测参数"""

    # ==========================
    # 模型权重
    # ==========================
    # s3_train.py 训练完会把权重写到 runs/detect/yetenek6/weights/best.pt。
    # 训练时的工作目录可能是 scripts/ 也可能是 yetenek6/，所以这里按顺序找。
    # 注意：ultralytics 有个全局 settings 记着 runs_dir，实测它会把权重写到
    # Desktop\Hava savunma\LazerGimbal\runs\... （外层那个副本），
    # 而不是本项目目录。所以这里把两边都列上，谁存在用谁。
    _SIBLING = os.path.join(os.path.dirname(os.path.dirname(_ROOT)), "LazerGimbal")
    WEIGHTS_CANDIDATES = [
        r"C:\Users\BYC TURK\Desktop\Hava savunma\YETENEK6_TASINABILIR\yetenek6_best.pt",  # 用户指定的新模型优先
        r"C:\Users\BYC TURK\Desktop\YETENEK6_TASINABILIR\yetenek6_best.pt",  # 兼容旧路径
        os.path.join(_ROOT, "vision", "models", "yetenek6_best.pt"),   # 手动放置优先
        os.path.join(_ROOT, "vision", "models", "savunma_yolo26.pt"),
        os.path.join(_ROOT, "yetenek6", "scripts", "runs", "detect", "yetenek6", "weights", "best.pt"),
        os.path.join(_ROOT, "yetenek6", "runs", "detect", "yetenek6", "weights", "best.pt"),
        os.path.join(_ROOT, "runs", "detect", "yetenek6", "weights", "best.pt"),
        os.path.join(_SIBLING, "runs", "detect", "yetenek6", "weights", "best.pt"),
    ]

    # ==========================
    # 推理参数
    # ==========================
    CONF = 0.35             # 置信度阈值
    IOU = 0.45              # NMS 阈值

    # ★ 关键参数：绝对不要改成 640 ★
    # 15 米处靶标只有约 45-60 像素，640 输入下会被压到 15-20 像素，
    # 小目标召回率会断崖式下跌。960 是显存与精度的平衡点。
    # RTX 4050 只有 6GB 显存，1280 容易爆显存。
    IMGSZ = 960

    DEVICE = 0              # 0 = 第一块 GPU；CPU 用 "cpu"

    # ==========================
    # 距离估算（可选，加分项）
    # ==========================
    # 规范只要求"在这三个距离上完成探测和分类并通过界面展示"，
    # 距离是布置条件，不是界面必须输出的数值。
    # 给了这两个值就顺带显示距离；设为 None 则界面显示 "-"。
    # AR0234 全局快门 1920x1200, 像元 3.0um -> 感光面宽 5.76mm
    # 8mm 镜头: HFOV = 2*atan(5.76/16) = 39.6 度
    #   （换 6mm 改成 51.3；换 12mm 改成 27.0）
    # 建议用 s0_kamera.py 实测后校正这个值。
    HFOV_DEG = 39.6

    # 官方 3MF 里各模型的实际尺寸不同，这里填一个"代表值"仅用于距离估算。
    # 距离估算是可选的加分项，规范并不要求，误差几十厘米无所谓。
    # 各类实际宽度: F16 0.50 / HELIKOPTER 0.583 / BALISTIK_FUZE 0.50 / MINI_IHA 0.375
    HEDEF_GENISLIK_M = 0.50

    # ==========================
    # 竞赛要求的三个距离（仅用于界面提示）
    # ==========================
    MESAFELER_M = (5, 10, 15)

    @classmethod
    def find_weights(cls):
        """返回第一个存在的权重路径；都不存在返回 None。"""
        for p in cls.WEIGHTS_CANDIDATES:
            if os.path.exists(p):
                return p
        return None
