# -*- coding: utf-8 -*-
"""
数据记录器 (Data Recorder)

⭐ PID 调试神器！

[功能]
- 实时记录误差、输出、位置等数据
- 自动保存为 CSV 文件
- 方便用 Excel 或 Python 绘图分析

[使用方法]
recorder = DataRecorder("pid_test_1")
recorder.log(error_x=50, error_y=-30, output_x=5, output_y=-3, pos_x=95, pos_y=87)
...
recorder.save()  # 保存到 logs/pid_test_1_20260210_143052.csv
"""

import csv
import time
from pathlib import Path
from datetime import datetime


class DataRecorder:
    """数据记录器"""
    
    def __init__(self, session_name="pid_debug", auto_save_interval=100):
        """
        初始化记录器
        :param session_name: 会话名称（用于文件命名）
        :param auto_save_interval: 自动保存间隔（记录条数）
        """
        self.session_name = session_name
        self.auto_save_interval = auto_save_interval
        
        # 数据缓冲区
        self.buffer = []
        self.record_count = 0
        
        # 开始时间
        self.start_time = time.time()
        
        # 确保日志目录存在
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = self.log_dir / f"{session_name}_{timestamp}.csv"
        
        # CSV 列定义
        self.fieldnames = [
            'timestamp',     # 时间戳（秒）
            'error_x',       # X 轴误差（像素）
            'error_y',       # Y 轴误差
            'output_x',      # X 轴 PID 输出（步数）
            'output_y',      # Y 轴 PID 输出
            'pos_x',         # X 轴舵机位置（度）
            'pos_y',         # Y 轴舵机位置
            'kp',            # 当前 Kp 值
            'ki',            # 当前 Ki 值
            'kd'             # 当前 Kd 值
        ]
        
        print(f"[RECORDER] 📊 数据记录器已启动")
        print(f"[RECORDER]    文件: {self.filename}")
    
    def log(self, error_x=0, error_y=0, output_x=0, output_y=0, 
            pos_x=0, pos_y=0, kp=0, ki=0, kd=0):
        """
        记录一条数据
        """
        timestamp = time.time() - self.start_time
        
        record = {
            'timestamp': f"{timestamp:.3f}",
            'error_x': error_x,
            'error_y': error_y,
            'output_x': output_x,
            'output_y': output_y,
            'pos_x': f"{pos_x:.2f}",
            'pos_y': f"{pos_y:.2f}",
            'kp': f"{kp:.3f}",
            'ki': f"{ki:.3f}",
            'kd': f"{kd:.3f}"
        }
        
        self.buffer.append(record)
        self.record_count += 1
        
        # 自动保存
        if self.record_count % self.auto_save_interval == 0:
            self.save()
    
    def save(self):
        """保存缓冲区数据到文件"""
        if not self.buffer:
            return
        
        # 判断文件是否存在（决定是否写表头）
        file_exists = self.filename.exists()
        
        try:
            with open(self.filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                
                # 第一次写入时添加表头
                if not file_exists:
                    writer.writeheader()
                
                # 写入数据
                writer.writerows(self.buffer)
            
            print(f"[RECORDER] ✓ 已保存 {len(self.buffer)} 条记录 (总计 {self.record_count})")
            self.buffer.clear()
            
        except Exception as e:
            print(f"[RECORDER] ✗ 保存失败: {e}")
    
    def close(self):
        """关闭记录器（保存剩余数据）"""
        self.save()
        duration = time.time() - self.start_time
        print(f"[RECORDER] 📊 记录完成！")
        print(f"[RECORDER]    总记录: {self.record_count} 条")
        print(f"[RECORDER]    时长: {duration:.1f} 秒")
        print(f"[RECORDER]    文件: {self.filename}")
    
    def __enter__(self):
        """支持 with 语句"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时自动保存"""
        self.close()


class QuickPlotter:
    """
    快速绘图工具（需要 matplotlib）
    
    [使用方法]
    QuickPlotter.plot_csv("logs/pid_test_1_20260210_143052.csv")
    """
    
    @staticmethod
    def plot_csv(csv_file, show_plot=True, save_fig=True):
        """
        从 CSV 文件绘制 PID 曲线
        :param csv_file: CSV 文件路径
        :param show_plot: 是否显示图形
        :param save_fig: 是否保存图片
        """
        try:
            import pandas as pd
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('TkAgg')  # 使用 TkAgg 后端（适合 Windows）
            
        except ImportError:
            print("[PLOTTER] ✗ 需要安装: pip install pandas matplotlib")
            return
        
        # 读取数据
        df = pd.read_csv(csv_file)
        
        # 创建图形
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        fig.suptitle(f'PID 调试数据分析 - {Path(csv_file).name}', fontsize=14)
        
        # 子图1: 误差曲线
        axes[0].plot(df['timestamp'], df['error_x'], label='Error X', color='red', alpha=0.7)
        axes[0].plot(df['timestamp'], df['error_y'], label='Error Y', color='blue', alpha=0.7)
        axes[0].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        axes[0].set_ylabel('误差 (像素)')
        axes[0].set_title('误差曲线 (Error)')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # 子图2: 输出曲线
        axes[1].plot(df['timestamp'], df['output_x'], label='Output X', color='orange', alpha=0.7)
        axes[1].plot(df['timestamp'], df['output_y'], label='Output Y', color='green', alpha=0.7)
        axes[1].axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        axes[1].set_ylabel('输出 (步数)')
        axes[1].set_title('PID 输出曲线 (Output)')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        # 子图3: 位置曲线
        axes[2].plot(df['timestamp'], df['pos_x'], label='Position X', color='purple', alpha=0.7)
        axes[2].plot(df['timestamp'], df['pos_y'], label='Position Y', color='brown', alpha=0.7)
        axes[2].axhline(y=90, color='gray', linestyle='--', alpha=0.5, label='中位 (90°)')
        axes[2].set_xlabel('时间 (秒)')
        axes[2].set_ylabel('位置 (度)')
        axes[2].set_title('舵机位置曲线 (Position)')
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 保存图片
        if save_fig:
            img_file = Path(csv_file).with_suffix('.png')
            plt.savefig(img_file, dpi=150)
            print(f"[PLOTTER] ✓ 图表已保存: {img_file}")
        
        # 显示图形
        if show_plot:
            plt.show()
        
        return fig


# ==========================
# 使用示例
# ==========================
if __name__ == "__main__":
    # 示例1: 记录数据
    print("=== 数据记录示例 ===")
    
    with DataRecorder("test_session") as recorder:
        # 模拟记录100条数据
        for i in range(100):
            recorder.log(
                error_x=50 - i * 0.5,
                error_y=-30 + i * 0.3,
                output_x=5,
                output_y=-3,
                pos_x=90 + i * 0.1,
                pos_y=90 - i * 0.05,
                kp=0.5, ki=0.0, kd=0.1
            )
            time.sleep(0.01)
    
    # 示例2: 绘图（如果有数据文件）
    print("\n=== 绘图示例 ===")
    log_dir = Path("logs")
    if log_dir.exists():
        csv_files = list(log_dir.glob("*.csv"))
        if csv_files:
            print(f"找到 {len(csv_files)} 个日志文件")
            # QuickPlotter.plot_csv(csv_files[-1])  # 取消注释以绘图
