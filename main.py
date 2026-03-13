# -*- coding: utf-8 -*-
import os
import sys

# 关键修复：在 Windows 下，由于 PyQt6 和 PyTorch (CUDA) 可能存在 DLL (如 c10.dll, OpenMP等) 冲突，
# 必须在导入 PyQt6 之前优先导入 torch，以保证底层库正确初始化。
import torch

# 抑制OpenCV警告和错误信息（在导入cv2之前设置）
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'

from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from utils.logger import Logger

logger = Logger("System")

# 尝试导入主题（可选）
try:
    import qdarktheme
    HAS_DARK_THEME = True
except ImportError:
    HAS_DARK_THEME = False
    logger.info("[SYSTEM] 提示: 安装 pyqtdarktheme 以启用暗色主题")

def main():
    """
    程序入口 (Program Entry Point)
    """
    # 0. 配置标准输出缓冲 (Debug)
    # 强制 stdout 立即刷新，防止 crash 时日志丢失
    sys.stdout.reconfigure(encoding='utf-8')
    
    logger.info("[SYSTEM] 程序启动...")
    logger.info("[SYSTEM] 初始化 Application...")

    # 1. 创建应用程序对象
    app = QApplication(sys.argv)
    
    # 2. 应用现代暗色主题 (可选)
    if HAS_DARK_THEME:
        app.setStyleSheet(qdarktheme.load_stylesheet())
        logger.info("[SYSTEM] 已应用暗色主题")
    else:
        logger.info("[SYSTEM] 使用默认主题")
    
    # 3. 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 4. 进入事件循环
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
