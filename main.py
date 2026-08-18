# -*- coding: utf-8 -*-
import os
import sys

# 关键修复：在 Windows 下，由于 PyQt6 和 PyTorch (CUDA) 可能存在 DLL (如 c10.dll, OpenMP等) 冲突，
# 若安装了 PyTorch，在导入 PyQt6 之前优先导入 torch，以保证底层库正确初始化。
try:
    import torch
except ImportError:
    pass


# 抑制OpenCV警告和错误信息（在导入cv2之前设置）
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'

import argparse
from PyQt6.QtWidgets import QApplication
from utils.logger import Logger

logger = Logger("System")

# 导入 UI 模式
try:
    from gui.fluent.app_window import FluentAppWindow
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False

from gui.main_window import MainWindow

# 尝试导入主题（可选，用于老版 UI）
try:
    import qdarktheme
    HAS_DARK_THEME = True
except ImportError:
    HAS_DARK_THEME = False


def main():
    """
    程序入口 (Program Entry Point)
    """
    parser = argparse.ArgumentParser(description="LaserGimbal Ground Station")
    parser.add_argument("--classic", action="store_true", help="Launch classic PyQt6 UI instead of Fluent UI")
    args, _ = parser.parse_known_args()

    # 0. 配置标准输出缓冲 (Debug)
    sys.stdout.reconfigure(encoding='utf-8')
    
    # 1. 创建应用程序对象
    app = QApplication(sys.argv)
    
    # 2. 根据参数选择启动 Fluent UI 还是 Classic UI
    if not args.classic and HAS_FLUENT:
        logger.info("[SYSTEM] 正在启动现代 Fluent UI 地面站...")
        window = FluentAppWindow()
    else:
        logger.info("[SYSTEM] 正在启动经典版 UI...")
        if HAS_DARK_THEME:
            app.setStyleSheet(qdarktheme.load_stylesheet())
        window = MainWindow()

    # 3. 显示主窗口
    window.show()
    
    # 4. 进入事件循环
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
