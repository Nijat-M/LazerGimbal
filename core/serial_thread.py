# -*- coding: utf-8 -*-
"""
Asynchronous serial transport with priority stop and latest-wins motion.
Supports PyQt6 GUI signals and pure-Python threaded environments.
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
    """Universal Signal supporting .connect() and .emit() for any callable."""
    def __init__(self):
        self._slots: List[Callable] = []

    def connect(self, slot: Callable) -> None:
        if slot not in self._slots:
            self._slots.append(slot)

    def disconnect(self, slot: Callable) -> None:
        if slot in self._slots:
            self._slots.remove(slot)

    def emit(self, *args, **kwargs) -> None:
        for slot in list(self._slots):
            try:
                slot(*args, **kwargs)
            except Exception as e:
                logger.error(f"[SIGNAL ERROR] Callback {slot} failed: {e}")


class SerialThread(threading.Thread):
    """
    High-performance Asynchronous Serial Thread.
    Compatible with PyQt6 QThread interface (isRunning, start, stop, wait).
    """

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.connection_state_signal = Signal()
        self.data_received_signal = Signal()

        self.serial_port: Optional[serial.Serial] = None
        self.is_running = True
        self.write_queue = queue.Queue()
        self.urgent_queue = queue.Queue()
        self._latest_lock = threading.Lock()
        self._latest_realtime_command = None
        self._read_buffer = ""

    def isRunning(self) -> bool:
        """QThread compatibility helper"""
        return self.is_alive()

    def wait(self, timeout_ms: int = 1000) -> bool:
        """QThread compatibility helper"""
        self.join(timeout=timeout_ms / 1000.0)
        return not self.is_alive()

    def connect_serial(self, port_name: str, baud_rate: int = 115200) -> bool:
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
        self.clear_pending_commands()
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.connection_state_signal.emit(False, "串口已断开")

    def is_connected(self) -> bool:
        return bool(self.serial_port and self.serial_port.is_open)

    def send_command(self, command: str) -> None:
        """Queue a discrete command such as tuning or configuration."""
        self.write_queue.put(self._normalize_command(command))

    def send_realtime_command(self, command: str) -> None:
        """Replace any unsent motion command with the newest command."""
        with self._latest_lock:
            self._latest_realtime_command = self._normalize_command(command)

    def send_stop_command(self) -> None:
        """Discard unsent motion and prioritize an explicit firmware STOP."""
        self._send_urgent_motion_command("!STOP\n")

    def send_center_command(self) -> None:
        """Discard pending motion and reset the firmware motion state."""
        self._send_urgent_motion_command("!CENTER\n")

    def _send_urgent_motion_command(self, command: str) -> None:
        with self._latest_lock:
            self._latest_realtime_command = None
        self._clear_queue(self.urgent_queue)
        self.urgent_queue.put(command)

    def clear_pending_commands(self) -> None:
        with self._latest_lock:
            self._latest_realtime_command = None
        self._clear_queue(self.urgent_queue)
        self._clear_queue(self.write_queue)

    def run(self) -> None:
        while self.is_running:
            if not self.is_connected():
                time.sleep(0.05)
                continue

            try:
                self._drain_queue(self.urgent_queue)
                self._drain_queue(self.write_queue, limit=8)

                with self._latest_lock:
                    realtime_command = self._latest_realtime_command
                    self._latest_realtime_command = None
                if realtime_command is not None:
                    self._write(realtime_command)

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
        self.is_running = False
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass

    def _drain_queue(self, command_queue: queue.Queue, limit=None) -> None:
        sent = 0
        while limit is None or sent < limit:
            try:
                command = command_queue.get_nowait()
            except queue.Empty:
                break
            self._write(command)
            sent += 1

    def _write(self, command: str) -> None:
        port = self.serial_port
        if port is None or not port.is_open:
            raise serial.SerialException("Serial port is not connected")
        port.write(command.encode("utf-8"))

    def _handle_received_chunk(self, chunk: str) -> None:
        self._read_buffer += chunk.replace("\r", "\n")
        while "\n" in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split("\n", 1)
            line = line.strip()
            if line:
                logger.info(f"[SERIAL RX] '{line}'")
                self.data_received_signal.emit(line)

    @staticmethod
    def _normalize_command(command: str) -> str:
        return command if command.endswith("\n") else command + "\n"

    @staticmethod
    def _clear_queue(command_queue: queue.Queue) -> None:
        while True:
            try:
                command_queue.get_nowait()
            except queue.Empty:
                return
