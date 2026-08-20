# -*- coding: utf-8 -*-
"""
Yetenek 6 检测器桥接层 (Bridge to yetenek6/scripts/s4_detector.py)

为什么需要这个文件：
    s4_detector.py 放在 yetenek6/scripts/ 下，不在 Python 的 import 路径里。
    这里负责把那个目录加进 sys.path，然后把 HedefDedektoru 转出来，
    这样主程序就能直接 `from vision.yetenek6_detector import ...`。

    好处是 s4_detector.py 保持原样不动 —— 它是框架无关的，
    以后想单独跑 `python s4_detector.py --weights best.pt --source 0` 也照样能跑。

用法：
    from vision.yetenek6_detector import create_detector
    det, err = create_detector()          # 权重找不到时 det=None, err=原因
    dets = det.tespit(frame)              # [{'sinif','gorunen','guven','box','mesafe_m'}, ...]
    vis  = det.ciz(frame, dets)           # 画好框的画面（土耳其字符用 PIL 绘制）
"""

import os
import sys

from config.yetenek6_config import Yetenek6Config

# yetenek6/scripts 加入 import 路径
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_ROOT, "yetenek6", "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

try:
    from s4_detector import HedefDedektoru, GORUNEN_AD, RENK
    HAS_YETENEK6 = True
    _IMPORT_ERROR = None
except Exception as e:          # noqa: BLE001 - 启动期不能因为它崩掉整个界面
    HedefDedektoru = None
    GORUNEN_AD, RENK = {}, {}
    HAS_YETENEK6 = False
    _IMPORT_ERROR = e


def create_detector(weights=None, conf=None, imgsz=None, device=None,
                    hfov_deg=None, hedef_genislik_m=None):
    """
    按 Yetenek6Config 构造检测器。

    返回 (detector, error_message)：
        成功 -> (HedefDedektoru 实例, None)
        失败 -> (None, "给用户看的中文原因")
    调用方不需要 try/except，看 error_message 是不是 None 就行。
    """
    if not HAS_YETENEK6:
        return None, f"无法导入 s4_detector.py: {_IMPORT_ERROR}"

    cfg = Yetenek6Config
    w = weights or cfg.find_weights()
    if w is None:
        tried = "\n  ".join(cfg.WEIGHTS_CANDIDATES)
        return None, ("找不到训练好的权重 best.pt。请先跑 s3_train.py 训练。\n"
                      f"已尝试的路径:\n  {tried}")

    try:
        det = HedefDedektoru(
            w,
            conf=cfg.CONF if conf is None else conf,
            iou=cfg.IOU,
            imgsz=cfg.IMGSZ if imgsz is None else imgsz,
            device=cfg.DEVICE if device is None else device,
            hfov_deg=cfg.HFOV_DEG if hfov_deg is None else hfov_deg,
            hedef_genislik_m=(cfg.HEDEF_GENISLIK_M if hedef_genislik_m is None
                              else hedef_genislik_m),
        )
    except Exception as e:      # noqa: BLE001
        return None, f"加载模型失败: {e}"

    return det, None
