# -*- coding: utf-8 -*-
import sys
import qdarktheme
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    """
    程序入口 (Program Entry Point)
    """
    # 0. 配置标准输出缓冲 (Debug)
    # 强制 stdout 立即刷新，防止 crash 时日志丢失
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("[SYSTEM] 程序启动...")
    print("[SYSTEM] 初始化 Application...")

    # 1. 创建应用程序对象
    app = QApplication(sys.argv)
    
    # 2. 应用现代暗色主题 (Apply Modern Dark Theme)
    app.setStyleSheet(qdarktheme.load_stylesheet())
    
    # 3. 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 4. 进入事件循环
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
