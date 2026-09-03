# -*- coding: utf-8 -*-
"""
LazerGimbal SADIR 1798-K — 系统主入口 (System Main Entry Point)
================================================================================
本程序为 2 轴闭环激光跟踪与防空云台系统的总入口。负责：
1. Windows 底层 DLL (CUDA/PyTorch vs PyQt6) 动态加载顺序保护；
2. 图像采集底层 (OpenCV MSMF / DirectShow) 环境变量抑制与调优；
3. 标准输入输出缓冲与 UTF-8 编码重定向；
4. PyQt6 高清 DPI 自适应渲染与现代暗色主题 (qdarktheme) 加载；
5. 主仪表盘窗口 (MainWindow) 的实例化与事件主循环启动。
================================================================================
"""
import os
import sys

# 【Windows 底层 DLL 冲突防护守卫 (DLL Load Guard)】
# 在 Windows 下，PyQt6 与 PyTorch (CUDA / OpenMP / c10.dll) 并存时极易发生加载符号冲突。
# 必须严格在导入 PyQt6 之前优先导入 torch，确保底层 CUDA 运行时正确绑定。
try:
    import torch
except ImportError:
    pass

# 抑制 OpenCV 底层非必要警告信息并关闭 MSMF 后端卡死问题
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
