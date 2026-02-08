# -*- coding: utf-8 -*-
import sys
import time
import serial
import queue
from PyQt6.QtCore import QThread, pyqtSignal

# 尝试导入 Config
try:
    from config import cfg
except ImportError:
    sys.path.append("..")
    from config import cfg

class SerialThread(QThread):
    """
    串口通信线程 (Serial Communication Thread)
    
    [原理 Principle]
    GUI 界面运行在主线程 (Main Thread)。如果在主线程中直接进行串口读写 (特别是读取)，
    可能会因为等待数据而阻塞 (Block) 界面，导致界面“假死”。
    
    解决方案: 使用 QThread 创建一个子线程，专门负责串口 I/O。
    子线程与主线程之间通过 信号(Signal) 和 槽(Slot) 机制进行安全通信。
    """
    
    # [信号定义 Signals]
    # 用于向主线程发送通知，这是线程安全的通信方式。
    connection_state_signal = pyqtSignal(bool, str)  # 连接状态变更 (成功/失败, 消息)
    data_received_signal = pyqtSignal(str)           # 收到串口数据

    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.is_running = True
        
        # [线程安全队列 Thread-Safe Queue]
        # 主线程调用 send_command 时，只是把指令放入队列。
        # 子线程在 run() 循环中取出指令发送。
        # 这就是 "生产者-消费者" (Producer-Consumer) 模式。
        self.write_queue = queue.Queue()

    def connect_serial(self, port_name, baud_rate):
        """
        连接串口
        """
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()

            # 初始化 PySerial 对象
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                timeout=cfg.TIMEOUT
            )
            
            if self.serial_port.is_open:
                msg = f"已连接至 {port_name}"
                print(f"[SERIAL] {msg}")
                self.connection_state_signal.emit(True, msg)
                return True
        except serial.SerialException as e:
            error_msg = f"连接失败: {str(e)}"
            print(f"[SERIAL ERROR] {error_msg}")
            self.connection_state_signal.emit(False, error_msg)
            return False
        return False

    def disconnect_serial(self):
        """
        断开串口
        """
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.connection_state_signal.emit(False, "串口已断开")

    def send_command(self, command: str):
        """
        发送指令 (生产者)
        将指令放入队列，立即返回，不阻塞 GUI。
        """
        if not command.endswith('\n'):
            command += '\n'
        self.write_queue.put(command)

    def run(self):
        """
        线程主循环 (消费者)
        不断检查:
        1. 发送队列是否有新指令? -> 发送
        2. 串口是否有新数据? -> 接收
        """
        while self.is_running:
            if self.serial_port and self.serial_port.is_open:
                # 1. 处理发送队列 (Sending)
                while not self.write_queue.empty():
                    try:
                        cmd = self.write_queue.get_nowait()
                        self.serial_port.write(cmd.encode('utf-8'))
                        # print(f"[SERIAL TX] '{cmd.strip()}'")  # Disabled for performance (latency)
                    except Exception as e:
                        print(f"[SERIAL TX ERROR] {e}")

                # 2. 处理接收数据 (Receiving)
                try:
                    if self.serial_port.in_waiting > 0:
                        # readline() 会读取直到 '\n'，由于设置了 timeout，不会无限阻塞
                        data = self.serial_port.readline().decode('utf-8').strip()
                        if data:
                            print(f"[SERIAL RX] '{data}'") 
                            self.data_received_signal.emit(data)
                except Exception as e:
                    print(f"接收错误: {e}")

            # 避免 CPU 占用过高 (Yield CPU)
            # 10ms 的休眠足以让 OS 调度其他任务
            time.sleep(0.01)

    def stop(self):
        """ 停止线程 """
        self.is_running = False
        self.wait()
