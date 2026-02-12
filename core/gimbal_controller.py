# -*- coding: utf-8 -*-
"""
云台控制器核心模块 (Gimbal Controller Core)

[职责 Responsibility]
这个类负责云台的所有控制逻辑，包括：
1. PID控制循环
2. 舵机位置状态管理
3. 视觉误差处理
4. 安全保护机制（看门狗、死区、限位）

[架构设计 Architecture]
Controller 层 - 不包含任何UI代码，只负责业务逻辑
- GUI调用Controller的方法
- Controller通过SerialThread发送指令
- Controller通过信号通知GUI更新显示
"""

import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

try:
    from config import cfg
    from core.pid import PIDController
except ImportError:
    import sys
    sys.path.append("..")
    from config import cfg
    from core.pid import PIDController


class GimbalController(QObject):
    """
    云台控制器 (Gimbal Controller)
    
    负责所有控制逻辑，与GUI解耦
    """
    
    # 信号：通知GUI更新状态显示
    status_update_signal = pyqtSignal(str)  # 状态文本
    position_update_signal = pyqtSignal(float, float)  # X, Y位置
    
    def __init__(self, serial_thread):
        """
        初始化控制器
        :param serial_thread: 串口通信线程实例
        """
        super().__init__()
        
        # 串口通信实例
        self.serial_thread = serial_thread
        
        # [舵机位置状态] Software Position Estimate
        # 假设初始位置在中位 (90度)
        self.servo_x = 90.0
        self.servo_y = 90.0
        
        # [视觉误差] 由视觉线程更新
        self.current_error_x = 0
        self.current_error_y = 0
        self.last_vision_time = time.time()
        
        # [误差滤波] 移动平均滤波器，减少噪声导致的抖动
        self.error_history_x = [0] * 3  # 保存最近3帧的误差
        self.error_history_y = [0] * 3
        self.history_index = 0
        
        # [PID控制器实例]
        # 注意：max_step 会在控制循环中动态调整
        self.pid_x = PIDController(cfg.PID_KP, cfg.PID_KI, cfg.PID_KD, cfg.MAX_STEP)
        self.pid_y = PIDController(cfg.PID_KP, cfg.PID_KI, cfg.PID_KD, cfg.MAX_STEP)
        
        # [控制开关]
        self.control_enabled = False
        
        # [反转设置] - 从GUI获取或使用配置
        self.invert_x = cfg.INVERT_X
        self.invert_y = cfg.INVERT_Y
        
        # [控制循环定时器]
        # 40Hz (25ms) 控制频率，更快的响应速度
        # 提高频率可以减少延迟，改善追踪性能
        self.control_timer = QTimer()
        self.control_timer.timeout.connect(self.control_loop)
        self.control_timer.start(25)  # 25ms = 40Hz
        
        # 警告时间戳（防止刷屏）
        self.last_warn_time = 0
    
    def set_control_enabled(self, enabled):
        """
        启用/禁用控制
        :param enabled: True=启动控制, False=停止控制
        """
        self.control_enabled = enabled
        status = "控制已启动" if enabled else "控制已停止"
        self.status_update_signal.emit(status)
        print(f"[CONTROLLER] {status}")
    
    def set_invert(self, invert_x, invert_y):
        """
        设置轴反转
        :param invert_x: X轴是否反转
        :param invert_y: Y轴是否反转
        """
        self.invert_x = invert_x
        self.invert_y = invert_y
        cfg.INVERT_X = invert_x
        cfg.INVERT_Y = invert_y
    
    def update_pid_tunings(self, kp, ki, kd):
        """
        动态更新PID参数
        :param kp: 比例系数
        :param ki: 积分系数
        :param kd: 微分系数
        """
        self.pid_x.set_tunings(kp, ki, kd)
        self.pid_y.set_tunings(kp, ki, kd)
        print(f"[CONTROLLER] PID参数已更新: Kp={kp:.2f}, Ki={ki:.2f}, Kd={kd:.2f}")
    
    def handle_vision_error(self, err_x, err_y):
        """
        接收视觉线程的误差信号
        :param err_x: X轴误差（像素）
        :param err_y: Y轴误差（像素）
        """
        self.last_vision_time = time.time()
        
        # 更新误差历史，用于移动平均滤波
        self.error_history_x[self.history_index] = err_x
        self.error_history_y[self.history_index] = err_y
        self.history_index = (self.history_index + 1) % 3
        
        # 计算移动平均值，减少噪声
        self.current_error_x = sum(self.error_history_x) // 3
        self.current_error_y = sum(self.error_history_y) // 3
    
    def control_loop(self):
        """
        [核心] PID控制循环
        
        独立于视觉帧率，以固定频率(20Hz)运行
        执行PID计算并发送串口指令
        """
        try:
            # 1. 检查控制开关
            if not self.control_enabled:
                return
            
            # 2. 检查串口连接状态
            if not self.serial_thread.serial_port or not self.serial_thread.serial_port.is_open:
                if time.time() - self.last_warn_time > 2.0:
                    print("[WARNING] 串口未连接！请先点击'连接'按钮。")
                    self.status_update_signal.emit("警告: 串口未连接")
                    self.last_warn_time = time.time()
                return
            
            # 3. [安全看门狗] Vision Signal Watchdog
            # 如果超过1秒未收到视觉信号，停止控制防止失控
            watchdog_timeout = 1.0
            if time.time() - self.last_vision_time > watchdog_timeout:
                if self.current_error_x != 0 or self.current_error_y != 0:
                    print(f"[SAFETY] 视觉信号丢失 > {watchdog_timeout}s，停止控制")
                    self.current_error_x = 0
                    self.current_error_y = 0
                return
            
            # 4. 获取当前误差
            err_x = self.current_error_x
            err_y = self.current_error_y
            
            # 5. [自适应死区处理] Adaptive Deadzone
            # 越接近目标，死区越大，防止震荡
            # 远离目标时死区小，提高响应速度
            error_magnitude = (err_x**2 + err_y**2)**0.5
            
            # 动态死区：5-30像素，根据误差大小调整
            if error_magnitude < 40:
                # 接近目标，使用较大死区防止震荡
                adaptive_deadzone = 30
            elif error_magnitude < 80:
                # 中等距离，使用中等死区
                adaptive_deadzone = 20
            else:
                # 远离目标，使用较小死区提高响应
                adaptive_deadzone = 10
            
            if abs(err_x) < adaptive_deadzone and abs(err_y) < adaptive_deadzone:
                return
            
            # 6. [反转处理] Invert
            if self.invert_x:
                err_x = -err_x
            if self.invert_y:
                err_y = -err_y
            
            # 7. [智能速度控制] Speed Adaptation - 更平滑的速度过渡
            # 根据误差大小动态调整最大步数，远快近慢
            # 增加速度档位，让过渡更平滑
            if error_magnitude > 150:
                # 超远距离：中等速度（避免太快飞出）
                adaptive_max_step = getattr(cfg, 'MAX_STEP_VERY_FAST', 15)
            elif error_magnitude > 100:
                # 远距离：平稳移动
                adaptive_max_step = getattr(cfg, 'MAX_STEP_FAST', 12)
            elif error_magnitude > 60:
                # 中距离：稳定移动
                adaptive_max_step = getattr(cfg, 'MAX_STEP_MEDIUM', 9)
            else:
                # 近距离：精确定位
                adaptive_max_step = getattr(cfg, 'MAX_STEP_SLOW', 6)
            
            # 动态更新PID的速度限制
            self.pid_x.max_step = adaptive_max_step
            self.pid_y.max_step = adaptive_max_step
            
            # 8. [PID计算]
            delta_x = self.pid_x.update(err_x)
            delta_y = self.pid_y.update(err_y)
            
            # 如果没有动作，直接返回
            if delta_x == 0 and delta_y == 0:
                return
            
            # 9. [软件坐标更新与限位]
            soft_delta_x = delta_x * cfg.SERVO_SOFTWARE_STEP_SCALE
            soft_delta_y = delta_y * cfg.SERVO_SOFTWARE_STEP_SCALE
            
            next_x = self.servo_x + soft_delta_x
            next_y = self.servo_y + soft_delta_y
            
            # 软件限位检查
            if next_x > cfg.SERVO_MAX_LIMIT:
                next_x = cfg.SERVO_MAX_LIMIT
                delta_x = 0
            elif next_x < cfg.SERVO_MIN_LIMIT:
                next_x = cfg.SERVO_MIN_LIMIT
                delta_x = 0
            
            if next_y > cfg.SERVO_MAX_LIMIT:
                next_y = cfg.SERVO_MAX_LIMIT
                delta_y = 0
            elif next_y < cfg.SERVO_MIN_LIMIT:
                next_y = cfg.SERVO_MIN_LIMIT
                delta_y = 0
            
            # 10. [发送串口指令]
            if abs(delta_x) > 0:
                self.servo_x = next_x
                cmd_x = f"x{'+' if delta_x >= 0 else ''}{delta_x}"
                self.serial_thread.send_command(f"{cmd_x}\n")
            
            if abs(delta_y) > 0:
                self.servo_y = next_y
                cmd_y = f"y{'+' if delta_y >= 0 else ''}{delta_y}"
                self.serial_thread.send_command(f"{cmd_y}\n")
            
            # 11. [更新GUI显示]
            self.position_update_signal.emit(self.servo_x, self.servo_y)
            
        except Exception as e:
            print(f"[CONTROLLER ERROR] 控制循环异常: {e}")
            import traceback
            traceback.print_exc()
    
    def manual_move(self, axis, direction):
        """
        手动移动舵机（测试模式）
        :param axis: 'x' 或 'y'
        :param direction: 1 或 -1
        """
        print(f"[MANUAL] 手动移动请求: 轴={axis}, 方向={direction}")
        
        if not self.serial_thread.serial_port or not self.serial_thread.serial_port.is_open:
            print("[WARNING] 串口未连接，无法手动移动")
            self.status_update_signal.emit("⚠️ 警告: 串口未连接")
            return
        
        # 手动控制步长（角度）
        degree_step = cfg.MANUAL_STEP * direction
        
        # !!! 关键修复1：应用反转设置 !!!
        # 追踪模式中有反转处理，手动模式也需要
        if axis == 'x' and self.invert_x:
            degree_step = -degree_step
            print(f"[MANUAL] X轴已反转（INVERT_X=True）")
        elif axis == 'y' and self.invert_y:
            degree_step = -degree_step
            print(f"[MANUAL] Y轴已反转（INVERT_Y=True）")
        
        # !!! 关键修复2：角度到PWM脉冲转换 !!!
        # STM32 PWM 配置：600-2400 对应 0-180°
        # 每 1° = (2400-600)/180 = 10 个脉冲单位
        # 所以需要将角度步长转换为脉冲步长
        pulse_step = int(degree_step * cfg.DEGREE_TO_PULSE)
        
        print(f"[MANUAL] 角度步长: {degree_step}°, PWM脉冲步长: {pulse_step}")
        
        if axis == 'x':
            next_pos = self.servo_x + degree_step
            if cfg.SERVO_MIN_LIMIT <= next_pos <= cfg.SERVO_MAX_LIMIT:
                self.servo_x = next_pos
                cmd = f"x{'+' if pulse_step >= 0 else ''}{pulse_step}"
                print(f"[MANUAL] 发送 X 轴命令: {cmd} (新位置={self.servo_x:.1f}°)")
                self.serial_thread.send_command(f"{cmd}\n")
                self.position_update_signal.emit(self.servo_x, self.servo_y)
                self.status_update_signal.emit(f"手动移动 X: {self.servo_x:.1f}°")
            else:
                print(f"[LIMIT] X轴已到达限位: {next_pos:.1f}° (限制: {cfg.SERVO_MIN_LIMIT}-{cfg.SERVO_MAX_LIMIT})")
                self.status_update_signal.emit(f"⚠️ X轴限位: {next_pos:.1f}°")
        
        elif axis == 'y':
            next_pos = self.servo_y + degree_step
            if cfg.SERVO_MIN_LIMIT <= next_pos <= cfg.SERVO_MAX_LIMIT:
                self.servo_y = next_pos
                cmd = f"y{'+' if pulse_step >= 0 else ''}{pulse_step}"
                print(f"[MANUAL] 发送 Y 轴命令: {cmd} (新位置={self.servo_y:.1f}°)")
                self.serial_thread.send_command(f"{cmd}\n")
                self.position_update_signal.emit(self.servo_x, self.servo_y)
                self.status_update_signal.emit(f"手动移动 Y: {self.servo_y:.1f}°")
            else:
                print(f"[LIMIT] Y轴已到达限位: {next_pos:.1f}° (限制: {cfg.SERVO_MIN_LIMIT}-{cfg.SERVO_MAX_LIMIT})")
                self.status_update_signal.emit(f"⚠️ Y轴限位: {next_pos:.1f}°")
    
    def sync_position(self):
        """
        重置软件位置估算为中位（90度）
        用于校准或在失步后重新同步
        """
        self.servo_x = 90.0
        self.servo_y = 90.0
        self.pid_x.reset()
        self.pid_y.reset()
        self.position_update_signal.emit(self.servo_x, self.servo_y)
        self.status_update_signal.emit("位置已重置为中位 (90, 90)")
        print("[CONTROLLER] 位置已同步重置")
