# -*- coding: utf-8 -*-
"""
LaserGimbal Fluent Ground Station - 现代 UI 启动入口
"""

import os
import sys

# 关键修复：优先导入 torch 初始化底层 CUDA/OpenMP DLL
try:
    import torch
except ImportError:
    pass

# 抑制 OpenCV 日志噪音
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from gui.fluent.app_window import FluentAppWindow
from utils.logger import Logger

logger = Logger("FluentLauncher")


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    logger.info("[SYSTEM] 启动 LaserGimbal Fluent Ground Station...")

    # 启用高 DPI 缩放
    app = QApplication(sys.argv)

    window = FluentAppWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
