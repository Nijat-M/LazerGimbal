# -*- coding: utf-8 -*-
"""
异步串口通讯传输层 (Asynchronous Serial Transport Layer)
================================================================================
本模块为上位机 (PC) 与下位机 (STM32F401) 之间的核心数据总线。负责：
1. 异步非阻塞串口通信：收发完全分离于独立工作线程，严禁因串口阻塞拖慢 GUI 与控制循环；
2. 双队列 + 最新帧覆盖丢弃策略 (Dual Queue with Latest-Wins Policy)：
   - 紧急插队队列 (urgent_queue)：急停 (!STOP) 与复位 (!CENTER) 具备最高抢占权；
   - 顺序配置队列 (write_queue)：PID 调参、激光功率等配置指令保序按序发送；
   - 高频伺服最新覆盖 (latest_realtime_command)：60Hz 实时控制偏差帧只发最新一帧，
     来不及发送的历史旧帧自动丢弃，彻底消除通信队列堆积引起的控制滞后 (Lag) 与发散自激；
3. 通用轻量级 Signal 机制：兼容 PyQt6 信号槽接口 (.connect / .emit)，同时在无 Qt 依赖的
   纯 Python 单元测试和后台环境中均可零依赖透明运行；
4. 断帧拼包协议解析：基于换行符 '\\n' 严格处理 USB CDC 虚拟串口的分包与粘包。
================================================================================
"""

import queue
import sys
import threading
import time
from typing import Callable, List, Optional

import serial

try:
    from config import cfg
except ImportError:
    sys.path.append("..")
    from config import cfg
from utils.logger import Logger

logger = Logger("SerialThread")


class Signal:
    """
    通用轻量级信号类 (Universal Pure-Python Signal)

    设计目的:
        提供与 PyQt6 pyqtSignal 完全一致的 .connect() 与 .emit() 调用接口，
        使得 SerialThread 既能无缝连接 Qt GUI 槽函数，又能在纯 Python 单元测试
        或独立控制台模式下脱离 Qt 运行时正常工作。
    """
    def __init__(self):
        self._slots: List[Callable] = []

    def connect(self, slot: Callable) -> None:
        """注册回调槽函数"""
        if slot not in self._slots:
            self._slots.append(slot)

    def disconnect(self, slot: Callable) -> None:
        """注销回调槽函数"""
        if slot in self._slots:
            self._slots.remove(slot)

    def emit(self, *args, **kwargs) -> None:
        """广播触发所有已注册的槽函数（单槽异常不中断其余槽函数的派发）"""
        for slot in list(self._slots):
            try:
                slot(*args, **kwargs)
            except Exception as e:
                logger.error(f"[SIGNAL ERROR] Callback {slot} failed: {e}")


class SerialThread(threading.Thread):
    """
    高性能异步串口收发主线程 (High-Performance Asynchronous Serial Thread)
    
    接口特性:
        完全兼容 PyQt6 的 QThread 生命周期语义 (isRunning, start, stop, wait)。
    """

    def __init__(self) -> None:
        super().__init__(daemon=True)
        # 状态与遥测信号
        self.connection_state_signal = Signal()  # 串口连接状态变化信号 (is_connected: bool, message: str)
        self.data_received_signal = Signal()     # 接收到 STM32 完整单行文本帧信号 (line: str)
        self.data_sent_signal = Signal()         # 成功向 STM32 物理输出指令帧信号 (command: str)

        self.serial_port: Optional[serial.Serial] = None
        self.is_running = True
        
        # 指令发送通道：
        # 1. 普通保序队列：参数整定、激光功率等离散配置指令
        self.write_queue = queue.Queue()
        # 2. 紧急最高优先级队列：急停 !STOP、复位 !CENTER
        self.urgent_queue = queue.Queue()
        # 3. 实时运动指令单槽：存储最新运动控制帧，最新覆盖旧值
        self._latest_lock = threading.Lock()
        self._latest_realtime_command = None
        
        # 串口拼包接收缓冲区（解决 USB CDC 底层分包与粘包）
        self._read_buffer = ""

    def isRunning(self) -> bool:
        """兼容 QThread.isRunning() 接口"""
        return self.is_alive()

    def wait(self, timeout_ms: int = 1000) -> bool:
        """兼容 QThread.wait() 接口"""
        self.join(timeout=timeout_ms / 1000.0)
        return not self.is_alive()

    def connect_serial(self, port_name: str, baud_rate: int = 115200) -> bool:
        """
        打开指定的物理串口或 USB 虚拟串口设备

        Args:
            port_name: 串口号 (例如: "COM5", "/dev/ttyUSB0")
            baud_rate: 通信波特率 (默认 115200)

        Returns:
            bool: 是否成功建立连接
        """
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()

            timeout = getattr(cfg, "TIMEOUT", 0.5)
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                timeout=timeout,
                write_timeout=0.2,
            )

            if self.serial_port.is_open:
                msg = f"已连接至 {port_name} ({baud_rate} bps)"
                logger.info(f"[SERIAL] {msg}")
                self.connection_state_signal.emit(True, msg)
                return True
        except serial.SerialException as exc:
            error_msg = f"连接失败 ({port_name}): {exc}"
            logger.error(f"[SERIAL ERROR] {error_msg}")
            self.connection_state_signal.emit(False, error_msg)
        except Exception as exc:
            error_msg = f"未知异常 ({port_name}): {exc}"
            logger.error(f"[SERIAL ERROR] {error_msg}")
            self.connection_state_signal.emit(False, error_msg)
        return False

    def disconnect_serial(self) -> None:
        """主动断开当前串口连接并清空待发指令队列"""
        self.clear_pending_commands()
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.connection_state_signal.emit(False, "串口已断开")

    def is_connected(self) -> bool:
        """检查串口对象是否有效且处于已打开通信状态"""
        return bool(self.serial_port and self.serial_port.is_open)

    def send_command(self, command: str) -> None:
        """
        压入离散保序配置指令（如 PID 参数整定、激光功率调整）

        Args:
            command: 待发文本指令（自动补齐换行符）
        """
        self.write_queue.put(self._normalize_command(command))

    def send_realtime_command(self, command: str) -> None:
        """
        更新高频实时运动控制帧（采用【最新覆盖丢弃】策略）

        原理:
            视觉闭环控制具有强烈的时效性，历史位置指令若堆积会导致云台严重滞后甚至振荡。
            本方法在持有轻量锁的情况下直接覆盖上一帧未发指令，确保下位机始终执行最新姿态！

        Args:
            command: 实时运动指令帧 (例如: "<12,-5,1>\\n")
        """
        with self._latest_lock:
            self._latest_realtime_command = self._normalize_command(command)

    def send_stop_command(self) -> None:
        """
        紧急制动：清空未发运动指令，以最高紧急优先级抢先发送 '!STOP\\n' 指令
        """
        self._send_urgent_motion_command("!STOP\n")

    def send_center_command(self) -> None:
        """
        原点复位：清空待发运动指令，以最高紧急优先级抢先发送 '!CENTER\\n' 指令
        """
        self._send_urgent_motion_command("!CENTER\n")

    def _send_urgent_motion_command(self, command: str) -> None:
        """清除过时待发帧，并将最高优先级指令送入 urgent_queue 队列"""
        with self._latest_lock:
            self._latest_realtime_command = None
        self._clear_queue(self.urgent_queue)
        self.urgent_queue.put(command)

    def clear_pending_commands(self) -> None:
        """排空所有普通配置队列、紧急队列与实时最新指令槽"""
        with self._latest_lock:
            self._latest_realtime_command = None
        self._clear_queue(self.urgent_queue)
        self._clear_queue(self.write_queue)

    def run(self) -> None:
        """
        串口异步 I/O 工作线程主执行循环

        调度优先级:
            1. 优先完全排空紧急队列 (urgent_queue: !STOP / !CENTER)；
            2. 批量消耗普通配置队列 (write_queue: 每次上限 8 条，防止饿死实时控制)；
            3. 提取并下发最新实时运动帧 (latest_realtime_command: 最新的闭环位置帧)；
            4. 非阻塞读取下位机回传遥测数据并执行断包拼包切分；
            5. 空闲时微秒级休眠 (2ms)，避免 CPU 空转并保持最低往返时延。
        """
        while self.is_running:
            if not self.is_connected():
                time.sleep(0.05)
                continue

            try:
                # 1. 最高优先级：处理紧急刹车与复位指令
                self._drain_queue(self.urgent_queue)
                
                # 2. 次高优先级：处理参数配置指令（带配额限制，防止突发多条堵塞主通道）
                self._drain_queue(self.write_queue, limit=8)

                # 3. 实时控制通道：仅提取最新单帧下发，旧帧自动清空
                with self._latest_lock:
                    realtime_command = self._latest_realtime_command
                    self._latest_realtime_command = None
                if realtime_command is not None:
                    self._write(realtime_command)

                # 4. 接收通道：非阻塞读取 STM32 上报的遥测角度与状态
                port = self.serial_port
                if port is None or not port.is_open:
                    continue
                waiting = port.in_waiting
                if waiting > 0:
                    chunk = port.read(waiting).decode(
                        "utf-8", errors="ignore"
                    )
                    self._handle_received_chunk(chunk)
                else:
                    # 串口静默状态下让出时间片，保持 500Hz 轮询响应能力
                    time.sleep(0.002)

            except (serial.SerialException, OSError) as exc:
                error_msg = f"检测到物理断开或硬件异常: {exc}"
                logger.error(f"[SERIAL ERROR] {error_msg}")
                if self.serial_port:
                    try:
                        self.serial_port.close()
                    except Exception:
                        pass
                self.clear_pending_commands()
                self.connection_state_signal.emit(False, error_msg)
            except Exception as exc:
                logger.error(f"[SERIAL UNKNOWN ERROR] {exc}")

    def stop(self) -> None:
        """安全终止串口后台工作线程并关闭硬件端口"""
        self.is_running = False
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass

    def _drain_queue(self, command_queue: queue.Queue, limit=None) -> None:
        """非阻塞批量排空并发送队列中的指令"""
        sent = 0
        while limit is None or sent < limit:
            try:
                command = command_queue.get_nowait()
            except queue.Empty:
                break
            self._write(command)
            sent += 1

    def _write(self, command: str) -> None:
        """向串口硬件底层写入经过 UTF-8 编码的字节流，并广播 data_sent_signal"""
        port = self.serial_port
        if port is None or not port.is_open:
            raise serial.SerialException("Serial port is not connected")
        port.write(command.encode("utf-8"))
        stripped = command.strip()
        if stripped:
            self.data_sent_signal.emit(stripped)

    def _handle_received_chunk(self, chunk: str) -> None:
        """
        基于换行符 '\\n' 实现串口流式数据的行切分拼包 (Line-Buffered Framer)

        设计考量:
            USB CDC 传输是以数据包 (USB Packet) 为单位的，一行报文可能被拆散在两个包中，
            或者一个包中包含多行报文。使用缓冲区进行累积并以 '\\n' 切分，保证每次只抛出完整帧。
        """
        self._read_buffer += chunk.replace("\r", "\n")
        while "\n" in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split("\n", 1)
            line = line.strip()
            if line:
                logger.info(f"[SERIAL RX] '{line}'")
                self.data_received_signal.emit(line)

    @staticmethod
    def _normalize_command(command: str) -> str:
        """规范化指令文本：确保以换行符结尾"""
        return command if command.endswith("\n") else command + "\n"

    @staticmethod
    def _clear_queue(command_queue: queue.Queue) -> None:
        """清空指定的线程安全队列"""
        while True:
            try:
                command_queue.get_nowait()
            except queue.Empty:
                return
