# -*- coding: utf-8 -*-
"""
结构化日志工具 (Structured Logger)

[功能]
- 统一的日志格式
- 不同级别的日志（DEBUG, INFO, WARNING, ERROR）
- 同时输出到控制台和文件

[使用方法]
from utils.logger import Logger

logger = Logger("GimbalController")
logger.info("云台初始化完成")
logger.warning("视觉信号丢失", timeout=2.0)
logger.error("串口连接失败", port="COM3")
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


class Logger:
    """结构化日志器"""
    
    # 全局设置
    _initialized = False
    _log_dir = Path("logs")
    
    def __init__(self, name, log_to_file=True):
        """
        初始化日志器
        :param name: 模块名称
        :param log_to_file: 是否同时写入文件
        """
        self.logger = logging.getLogger(name)
        
        # 避免重复初始化
        if not Logger._initialized:
            Logger._setup_logging(log_to_file)
            Logger._initialized = True
    
    @staticmethod
    def _setup_logging(log_to_file):
        """设置全局日志配置"""
        # 创建日志目录
        Logger._log_dir.mkdir(exist_ok=True)
        
        # 日志格式
        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # 根日志器配置
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(console_handler)
        
        # 文件处理器（可选）
        if log_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = Logger._log_dir / f"system_{timestamp}.log"
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
            print(f"[LOGGER] 📝 日志文件: {log_file}")
    
    def debug(self, message, **kwargs):
        """调试信息"""
        self.logger.debug(self._format_message(message, kwargs))
    
    def info(self, message, **kwargs):
        """一般信息"""
        self.logger.info(self._format_message(message, kwargs))
    
    def warning(self, message, **kwargs):
        """警告信息"""
        self.logger.warning(self._format_message(message, kwargs))
    
    def error(self, message, **kwargs):
        """错误信息"""
        self.logger.error(self._format_message(message, kwargs))
    
    def critical(self, message, **kwargs):
        """严重错误"""
        self.logger.critical(self._format_message(message, kwargs))
    
    @staticmethod
    def _format_message(message, kwargs):
        """格式化消息（添加键值对参数）"""
        if not kwargs:
            return message
        
        params = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        return f"{message} ({params})"


# 快捷方式（全局日志器）
_global_logger = Logger("System")

def debug(message, **kwargs):
    _global_logger.debug(message, **kwargs)

def info(message, **kwargs):
    _global_logger.info(message, **kwargs)

def warning(message, **kwargs):
    _global_logger.warning(message, **kwargs)

def error(message, **kwargs):
    _global_logger.error(message, **kwargs)

def critical(message, **kwargs):
    _global_logger.critical(message, **kwargs)


# ==========================
# 使用示例
# ==========================
if __name__ == "__main__":
    # 示例1: 模块日志器
    logger = Logger("TestModule")
    logger.info("模块启动")
    logger.debug("调试信息", x=10, y=20)
    logger.warning("可能的问题", code=404)
    logger.error("发生错误", reason="连接超时")
    
    # 示例2: 全局日志器
    info("使用全局日志器")
    warning("这是警告", level=3)
