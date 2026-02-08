# -*- coding: utf-8 -*-
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QGroupBox, 
    QSlider, QFormLayout, QRadioButton, QButtonGroup,
    QMessageBox, QCheckBox, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QImage, QPixmap, QAction
import qdarktheme

# 导入核心模块
# 确保路径正确
try:
    from config import cfg
    from config import cfg
    from core.serial_thread import SerialThread
    from vision.worker import VisionWorker
    from core.pid import PIDController
    from gui.test_panel import TestModePanel
except ImportError:
    sys.path.append("..")
    from config import cfg
    from core.serial_thread import SerialThread
    from vision.worker import VisionWorker
    from core.pid import PIDController
    from gui.test_panel import TestModePanel

class MainWindow(QMainWindow):
    """
    主窗口类 (Main GUI Window)
    
    [架构 Architecture]
    这是一个基于 PyQt6 的图形界面程序。它充当整个系统的"指挥中心"。
    它主要负责:
    1. 启动和管理子线程 (SerialThread, VisionWorker)。
    2. 显示实时视频流和调试蒙版。
    3. 提供用户交互 (按钮, 滑块)。
    4. 运行控制循环 (Control Loop)，执行 PID 算法。
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LaserGimbal_Pro - 激光云台控制系统")
        self.resize(1000, 700)

        # [线程实例化]
        self.serial_thread = SerialThread()
        self.vision_thread = VisionWorker()

        # 初始化UI布局
        self.init_ui()
        self.init_signals() # 连接信号与槽

        # 启动视觉线程 (默认开启摄像头预览)
        self.vision_thread.start()

        # [状态变量]
        # 舵机当前角度估算 (Software Position Estimate)
        # 我们假设初始位置在 90 度 (物理中位)。
        # 之后所有的移动指令 (x+1, x-1) 都会更新这个变量，以便我们在软件上知道云台大概在哪。
        self.servo_x = 90
        self.servo_y = 90

        # 当前视觉误差 (由 VisionWorker 更新)
        self.current_error_x = 0
        self.current_error_y = 0
        # self.last_error_x/y 移除，PID 类内部管理

        # [PID 控制器实例]
        self.pid_x = PIDController(cfg.PID_KP, cfg.PID_KI, cfg.PID_KD, cfg.MAX_STEP)
        self.pid_y = PIDController(cfg.PID_KP, cfg.PID_KI, cfg.PID_KD, cfg.MAX_STEP)

        # [控制循环 Timer]
        # 我们使用独立定时器 (20Hz = 50ms) 来运行 PID 控制循环。
        # 这样做的好处是将 "视觉识别频率" 和 "舵机控制频率" 解耦 (Decouple)。
        # 视觉可能只有 15fps，但我们可以以 20Hz 稳定的频率发送控制指令。
        self.control_timer = QTimer()
        self.control_timer.timeout.connect(self.control_loop)
        self.control_timer.start(50) # 50ms

    def init_ui(self):
        """ 初始化界面布局 (Layouts & Widgets) """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局: 水平 (左侧视频, 右侧控制)
        main_layout = QHBoxLayout(central_widget)

        # ==========================
        # 左侧: 视频显示区
        # ==========================
        left_layout = QVBoxLayout()
        
        # 摄像头画面 QLabel
        self.lbl_camera = QLabel("摄像头画面未启动")
        self.lbl_camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_camera.setStyleSheet("background-color: black; border: 2px solid #333;")
        self.lbl_camera.setMinimumSize(480, 360)
        
        # Mask 蒙版 (调试用) QLabel
        self.lbl_mask = QLabel("Mask 蒙版 (调试)")
        self.lbl_mask.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mask.setStyleSheet("background-color: #222; border: 1px dashed #555;")
        self.lbl_mask.setMinimumSize(320, 240)
        self.lbl_mask.setMaximumHeight(300) 

        left_layout.addWidget(QLabel("<h2>实时监控 (Live View)</h2>"))
        left_layout.addWidget(self.lbl_camera, 2)
        left_layout.addWidget(QLabel("<h3>算法调试 (Debug Mask)</h3>"))
        left_layout.addWidget(self.lbl_mask, 1)   
        
        main_layout.addLayout(left_layout, 2) # 左侧占 2/3

        # ==========================
        # 右侧: 控制面板
        # ==========================
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)

        # 1. 串口连接设置
        grp_serial = QGroupBox("通信连接 (Serial Connection)")
        serial_layout = QFormLayout()
        
        self.combo_port = QComboBox()
        self.combo_port.addItems(["COM1", "COM2", "COM3", "COM4", "COM5"]) 
        self.combo_port.setCurrentText(cfg.SERIAL_PORT)
        
        self.btn_connect = QPushButton("连接 (Connect)")
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self.toggle_connection)
        
        serial_layout.addRow("端口 (Port):", self.combo_port)
        serial_layout.addRow(self.btn_connect)
        grp_serial.setLayout(serial_layout)
        right_layout.addWidget(grp_serial)

        # 2. 模式选择
        grp_mode = QGroupBox("工作模式 (Mode)")
        mode_layout = QVBoxLayout()
        self.mode_group = QButtonGroup()
        
        self.rb_idle = QRadioButton("待机 (IDLE)")
        self.rb_tracking = QRadioButton("视觉追踪 (Tracking)")
        self.rb_test = QRadioButton("测试模式 (Test Mode - Manual)")
        
        self.rb_idle.setChecked(True)
        self.mode_group.addButton(self.rb_idle, 0)
        self.mode_group.addButton(self.rb_tracking, 1)
        self.mode_group.addButton(self.rb_test, 3) # ID 3 for Test Mode
        
        self.mode_group.idToggled.connect(self.change_mode)
        
        mode_layout.addWidget(self.rb_idle)
        mode_layout.addWidget(self.rb_tracking)
        mode_layout.addWidget(self.rb_test)
        grp_mode.setLayout(mode_layout)
        right_layout.addWidget(grp_mode)

        # 追踪目标选择
        grp_target = QGroupBox("追踪目标 (Target)")
        target_layout = QHBoxLayout()
        self.bg_target = QButtonGroup()
        
        self.rb_target_red = QRadioButton("红色激光 (Red Center)")
        self.rb_target_blue = QRadioButton("蓝色物体 (Blue Chase)")
        
        self.bg_target.addButton(self.rb_target_red, 0)
        self.bg_target.addButton(self.rb_target_blue, 1)
        
        if getattr(cfg, 'DEFAULT_TRACK_COLOR', 'RED') == 'BLUE':
            self.rb_target_blue.setChecked(True)
        else:
            self.rb_target_red.setChecked(True)
            
        self.bg_target.idToggled.connect(self.change_target_color)
        
        target_layout.addWidget(self.rb_target_red)
        target_layout.addWidget(self.rb_target_blue)
        grp_target.setLayout(target_layout)
        right_layout.addWidget(grp_target)

        # 3. PID 参数调整
        pid_layout = QVBoxLayout()
        pid_layout.addWidget(QLabel("PID 参数微调"))
        
        # Kp Slider
        kp_layout = QHBoxLayout()
        self.label_kp_val = QLabel(f"{cfg.PID_KP:.2f}") 
        self.slider_kp = QSlider(Qt.Orientation.Horizontal)
        self.slider_kp.setRange(0, 100)
        self.slider_kp.setValue(int(cfg.PID_KP * 100))
        self.slider_kp.valueChanged.connect(self.update_pid)
        kp_layout.addWidget(QLabel("Kp:"))
        kp_layout.addWidget(self.slider_kp)
        kp_layout.addWidget(self.label_kp_val) 
        pid_layout.addLayout(kp_layout)
 
        # Ki Slider
        ki_layout = QHBoxLayout()
        self.label_ki_val = QLabel(f"{cfg.PID_KI:.2f}")
        self.slider_ki = QSlider(Qt.Orientation.Horizontal)
        self.slider_ki.setRange(0, 100)
        self.slider_ki.setValue(int(cfg.PID_KI * 100))
        self.slider_ki.valueChanged.connect(self.update_pid)
        ki_layout.addWidget(QLabel("Ki:"))
        ki_layout.addWidget(self.slider_ki)
        ki_layout.addWidget(self.label_ki_val)
        pid_layout.addLayout(ki_layout)

        # Kd Slider
        kd_layout = QHBoxLayout()
        self.label_kd_val = QLabel(f"{cfg.PID_KD:.2f}")
        self.slider_kd = QSlider(Qt.Orientation.Horizontal)
        self.slider_kd.setRange(0, 100)
        self.slider_kd.setValue(int(cfg.PID_KD * 100))
        self.slider_kd.valueChanged.connect(self.update_pid)
        kd_layout.addWidget(QLabel("Kd:"))
        kd_layout.addWidget(self.slider_kd)
        kd_layout.addWidget(self.label_kd_val)
        pid_layout.addLayout(kd_layout)

        # Save & Reset Buttons
        self.btn_save_config = QPushButton("保存配置 (Save Config)")
        self.btn_save_config.clicked.connect(self.save_configuration)
        pid_layout.addWidget(self.btn_save_config)

        check_layout = QHBoxLayout()
        self.chk_invert_x = QCheckBox("反转 X 轴 (Invert X)")
        self.chk_invert_y = QCheckBox("反转 Y 轴 (Invert Y)")
        self.chk_invert_x.setChecked(True) # 默认选中，根据 Config 实际加载
        self.chk_invert_y.setChecked(True)
        check_layout.addWidget(self.chk_invert_x)
        check_layout.addWidget(self.chk_invert_y)
        pid_layout.addLayout(check_layout)
        
        self.btn_reset_pid = QPushButton("重置默认 PID")
        self.btn_reset_pid.clicked.connect(self.reset_pid_default)
        pid_layout.addWidget(self.btn_reset_pid)

        right_layout.addLayout(pid_layout)

        # 4. 其它控制
        ctrl_layout = QHBoxLayout()
        
        self.btn_servo_power = QPushButton("开始控制 (Start)")
        self.btn_servo_power.setCheckable(True)
        self.btn_servo_power.setStyleSheet("background-color: #444; color: white;")
        self.btn_servo_power.toggled.connect(self.toggle_servo_power)
        
        self.btn_sync = QPushButton("重置位置 (Reset)")
        self.btn_sync.setToolTip("重置软件坐标为 90, 90")
        self.btn_sync.clicked.connect(self.sync_position)
        
        self.btn_buzzer = QPushButton("测试蜂鸣器 (Buzzer)")
        ctrl_layout.addWidget(self.btn_buzzer)
        right_layout.addLayout(ctrl_layout)

        # 5. 测试模式控制面板 (Test Mode Controls) - 默认隐藏
        # 5. 测试模式控制面板 (Refactored)
        self.grp_test = TestModePanel()
        self.grp_test.request_move_signal.connect(self.manual_move)
        
        self.grp_test.setVisible(False) # Hidden by default
        right_layout.addWidget(self.grp_test)

        # 状态栏
        self.status_label = QLabel("系统就绪")
        self.status_label.setStyleSheet("color: gray;")
        right_layout.addWidget(self.status_label)
        
        right_layout.addStretch() 
        main_layout.addLayout(right_layout, 1)

    def init_signals(self):
        """ 连接信号与槽 (Signals & Slots) """
        # 视觉线程信号
        self.vision_thread.frame_signal.connect(self.update_camera_feed)
        self.vision_thread.mask_signal.connect(self.update_mask_feed)
        self.vision_thread.control_signal.connect(self.handle_control_signal)
        
        # 串口线程信号
        self.serial_thread.connection_state_signal.connect(self.update_connection_status)
        self.serial_thread.data_received_signal.connect(self.update_log)

    # ==========================
    # 槽函数 (Slots)
    # ==========================
    
    @pyqtSlot(QImage)
    def update_camera_feed(self, qt_img):
        """ 更新摄像头画面，保持比例缩放 """
        pixmap = QPixmap.fromImage(qt_img)
        scaled_pixmap = pixmap.scaled(self.lbl_camera.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.lbl_camera.setPixmap(scaled_pixmap)

    @pyqtSlot(QImage)
    def update_mask_feed(self, qt_img):
        """ 更新 Mask 画面 """
        pixmap = QPixmap.fromImage(qt_img)
        scaled_pixmap = pixmap.scaled(self.lbl_mask.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.lbl_mask.setPixmap(scaled_pixmap)

    @pyqtSlot(bool)
    def toggle_servo_power(self, checked):
        if checked:
            print("[GUI ACTION] 点击开始控制 (Start)")
            self.btn_servo_power.setText("停止控制 (Stop)")
            self.btn_servo_power.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold;")
        else:
            print("[GUI ACTION] 点击停止控制 (Stop)")
            self.btn_servo_power.setText("开始控制 (Start)")
            self.btn_servo_power.setStyleSheet("background-color: #5cb85c; color: white; font-weight: bold;")

    @pyqtSlot(int, int)
    def handle_control_signal(self, err_x, err_y):
        """ 
        [轻量化] 视觉线程只负责更新 Error 变量
        不在这里进行 PID 计算，以防止阻塞视觉线程或被视觉帧率限制。
        """
        import time
        self.last_vision_time = time.time() # 记录时间，用于 Watchdog
        self.current_error_x = err_x
        self.current_error_y = err_y

    def control_loop(self):
        """
        [PID 控制核心] Control Loop
        独立于视觉帧率，专门负责计算 PID 并发送指令。
        频率: 20Hz (由 QTimer 控制)
        """
        try:
            # 1. 检查开关状态
            if not self.btn_servo_power.isChecked():
                return
            
            # 2. 检查串口连接 - Safety Check
            if not self.serial_thread.serial_port or not self.serial_thread.serial_port.is_open:
                # 限制警告频率，防止刷屏
                if not hasattr(self, 'last_warn_time') or time.time() - self.last_warn_time > 2.0:
                    print("[WARNING] Serial Not Connected! Please click 'Connect' first.")
                    self.last_warn_time = time.time()
                return
            
            # 3. [看门狗 Watchdog] 安全检测
            # 如果超过 1.0 秒没有收到视觉信号，说明可能丢了目标或摄像头卡死。
            # 此时必须停止舵机，防止失控乱转。
            import time
            if not hasattr(self, 'last_vision_time'):
                self.last_vision_time = time.time()
            
            if time.time() - self.last_vision_time > 1.0:
                if self.current_error_x != 0 or self.current_error_y != 0:
                     print(f"[SAFETY] Vision Signal Lost > 1.0s (Last: {self.last_vision_time:.2f}). Stopping...")
                     self.current_error_x = 0
                     self.current_error_y = 0
                return

            # 获取当前误差
            err_x = self.current_error_x
            err_y = self.current_error_y
            
            # 4. [死区 Deadzone]
            # 如果误差很小，就认为已经对准了，不发送指令。
            # 这可以消除舵机在目标附近的细微抖动。
            deadzone = getattr(cfg, 'DEADZONE', 20)
            if abs(err_x) < deadzone and abs(err_y) < deadzone:
                return

            # --- [PID 算法核心] (Refactored) ---
            
            # 使用提取出的 PIDController 类计算
            # Update Tunings (如果有实时修改需求，可在 update_pid 中设置，这里确保同步)
            # self.pid_x.set_tunings(...) # 其实不需要每次调用，slider 动了会调用 update_pid
            
            # 5. 反转处理 (Invert) - 需在计算前反转误差，或者计算后反转输出？
            # 旧逻辑是反转误差: if invert: err = -err
            if self.chk_invert_x.isChecked(): err_x = -err_x
            if self.chk_invert_y.isChecked(): err_y = -err_y

            delta_x = self.pid_x.update(err_x)
            delta_y = self.pid_y.update(err_y)


            # 如果没有动作，直接返回
            if delta_x == 0 and delta_y == 0:
                return

            # --- 7. 坐标更新与发送 ---
            
            # 更新软件坐标 (用于限位判断)
            soft_delta_x = delta_x * cfg.SERVO_SOFTWARE_STEP_SCALE
            soft_delta_y = delta_y * cfg.SERVO_SOFTWARE_STEP_SCALE

            next_x = self.servo_x + soft_delta_x
            next_y = self.servo_y + soft_delta_y

            # [软件限位 Software Limits]
            # 防止撞墙
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

            # 发送串口指令
            if abs(delta_x) > 0: 
                self.servo_x = next_x # 更新位置
                cmd_x = f"x{'+' if delta_x >= 0 else ''}{delta_x}"
                self.serial_thread.send_command(f"{cmd_x}\n")
            
            if abs(delta_y) > 0:
                self.servo_y = next_y
                cmd_y = f"y{'+' if delta_y >= 0 else ''}{delta_y}"
                self.serial_thread.send_command(f"{cmd_y}\n")
                
            # 更新状态栏显示
            self.status_label.setText(f"Servo Pos: X={self.servo_x:.1f}, Y={self.servo_y:.1f}")

        except Exception as e:
            print(f"[CONTROL CRASH PROTECT] Error in loop: {e}")
            import traceback
            traceback.print_exc()

    def sync_position(self):
        """ 重置软件坐标 (用于手动校准) """
        print("[GUI ACTION] 点击重置位置 (Reset)")
        self.servo_x = 90
        self.servo_y = 90
        QMessageBox.information(self, "重置完成", "软件坐标已重置为 90, 90。\n(请确保云台当前物理位置也大致在中间，此操作不发送指令)")



    @pyqtSlot()
    def toggle_connection(self):
        """ 连接/断开串口 """
        if self.btn_connect.isChecked():
            port = self.combo_port.currentText()
            print(f"[GUI ACTION] 尝试连接端口: {port}")
            self.servo_x = 90
            self.servo_y = 90
            self.status_label.setText(f"重置舵机位置: X=90, Y=90")
            
            self.serial_thread.connect_serial(port, cfg.BAUD_RATE)
            self.serial_thread.start()
            self.btn_connect.setText("断开 (Disconnect)")
        else:
            print("[GUI ACTION] 断开连接")
            self.serial_thread.stop()
            self.serial_thread.disconnect_serial()
            self.btn_connect.setText("连接 (Connect)")

    @pyqtSlot(bool, str)
    def update_connection_status(self, success, msg):
        print(f"[GUI STATUS] {msg}")
        self.status_label.setText(msg)
        if success:
            self.status_label.setStyleSheet("color: #00ff00;")
        else:
            self.status_label.setStyleSheet("color: red;")
            self.btn_connect.setChecked(False)
            self.btn_connect.setText("连接 (Connect)")

    @pyqtSlot(int, bool)
    def change_mode(self, btn_id, checked):
        if not checked: return
        mode_map = {0: "IDLE", 1: "TRACKING", 3: "TEST"}
        mode = mode_map.get(btn_id, "IDLE")
        
        # [Safety Confirmation for Test Mode]
        if mode == "TEST":
            reply = QMessageBox.question(
                self, 
                "确认进入测试模式", 
                "进入测试模式将允许手动控制舵机大幅度移动 (30度/次)。\n\n请确认：\n1. 云台周围无障碍物。\n2. 舵机软限位已校准 (当前软件位置正确)。\n\n是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.rb_idle.setChecked(True) # Revert to IDLE
                return

        print(f"[GUI ACTION] 切换模式: {mode}")
        
        # Update UI visibility
        self.grp_test.setVisible(mode == "TEST")
        
        # Disable Vision Thread processing in Test Mode (Treat as IDLE for vision)
        vision_mode = "IDLE" if mode == "TEST" else mode
        self.vision_thread.set_mode(vision_mode)
        
        self.status_label.setText(f"模式已切换: {mode}")

    @pyqtSlot(int, bool)
    def change_target_color(self, btn_id, checked):
        if not checked: return
        color = "BLUE" if btn_id == 1 else "RED"
        cfg.DEFAULT_TRACK_COLOR = color
        print(f"[GUI ACTION] 切换追踪目标: {color}")
        self.status_label.setText(f"追踪目标已切换: {color}")

    def manual_move(self, axis, direction):
        """
        手动移动舵机 (Test Mode)
        axis: 'x' or 'y'
        direction: 1 or -1
        """
        if not self.serial_thread.serial_port or not self.serial_thread.serial_port.is_open:
            QMessageBox.warning(self, "错误", "串口未连接！")
            return
            
        step_deg = 30 # 每次移动 30 度
        # Calculate steps: 30 deg / 0.2 scale = 150 steps
        # But wait, send_command sends RAW steps.
        # If scale is 0.2, it means 1 raw step = 0.2 degrees.
        # So 30 degrees = 30 / 0.2 = 150 raw steps.
        raw_steps = int(step_deg / cfg.SERVO_SOFTWARE_STEP_SCALE) * direction
        
        # Invert Check
        if axis == 'x' and self.chk_invert_x.isChecked(): raw_steps = -raw_steps
        if axis == 'y' and self.chk_invert_y.isChecked(): raw_steps = -raw_steps

        # Prediction & Limit Check
        # Current pos
        curr = self.servo_x if axis == 'x' else self.servo_y
        
        # Calculate next software position (Degree)
        # delta_deg = raw_steps * scale
        delta_deg = raw_steps * cfg.SERVO_SOFTWARE_STEP_SCALE
        next_pos = curr + delta_deg
        
        # [Safety Limit Check]
        if next_pos < cfg.SERVO_MIN_LIMIT or next_pos > cfg.SERVO_MAX_LIMIT:
            print(f"[SAFETY] Manual Move Blocked: Target {next_pos:.1f} out of bounds (0-180)")
            self.status_label.setText(f"⛔ 移动被阻止: 目标角度 {next_pos:.1f} 超出范围!")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            return
            
        # Send Command
        # The protocol: x+150 or x-150
        cmd = f"{axis}{'+' if raw_steps >= 0 else ''}{raw_steps}"
        self.serial_thread.send_command(f"{cmd}\n")
        
        # Update Software State
        if axis == 'x': self.servo_x = next_pos
        else: self.servo_y = next_pos
        
        self.status_label.setText(f"Manual Move: {axis.upper()} {delta_deg:+.1f}° -> {next_pos:.1f}")
        self.status_label.setStyleSheet("color: blue;")

    def keyPressEvent(self, event):
        """ 键盘控制 (Arrow Keys) - Refactored """
        # 优先让测试面板处理
        if self.grp_test.handle_key_event(event):
            return # Handled
            
        super().keyPressEvent(event)

    def update_pid(self):
        """ 滑块调整 PID 参数 """
        # ... (Existing logic for updating Config)
        cfg.PID_KP = self.slider_kp.value() / 100.0
        cfg.PID_KI = self.slider_ki.value() / 100.0
        cfg.PID_KD = self.slider_kd.value() / 100.0
        
        self.label_kp_val.setText(f"{cfg.PID_KP:.2f}")
        self.label_ki_val.setText(f"{cfg.PID_KI:.2f}")
        self.label_kd_val.setText(f"{cfg.PID_KD:.2f}")
        
        # 同步更新 PID 控制器实例
        self.pid_x.set_tunings(cfg.PID_KP, cfg.PID_KI, cfg.PID_KD)
        self.pid_y.set_tunings(cfg.PID_KP, cfg.PID_KI, cfg.PID_KD)
        print(f"[PID TUNING] Kp={cfg.PID_KP}, Ki={cfg.PID_KI}, Kd={cfg.PID_KD}")

    def closeEvent(self, event):
        if not checked: return
        color = "BLUE" if btn_id == 1 else "RED"
        cfg.DEFAULT_TRACK_COLOR = color
        print(f"[GUI ACTION] 切换追踪目标: {color}")
        self.status_label.setText(f"追踪目标已切换: {color}")

    def update_pid(self):
        """ 更新 PID 参数 """
        cfg.PID_KP = self.slider_kp.value() / 100.0
        cfg.PID_KI = self.slider_ki.value() / 100.0
        cfg.PID_KD = self.slider_kd.value() / 100.0
        
        self.label_kp_val.setText(f"{cfg.PID_KP:.2f}")
        self.label_ki_val.setText(f"{cfg.PID_KI:.2f}")
        self.label_kd_val.setText(f"{cfg.PID_KD:.2f}")
        print(f"[PID SET] Kp={cfg.PID_KP}, Ki={cfg.PID_KI}, Kd={cfg.PID_KD}")
        
    def save_configuration(self):
        """ 保存当前配置到文件 """
        cfg.save_config()
        self.status_label.setText(f"配置已保存 (Saved to {cfg.CONFIG_FILE})")
        print("[GUI] Configuration Saved.")
        QMessageBox.information(self, "保存成功", f"配置已保存到 {cfg.CONFIG_FILE}")

    def reset_pid_default(self):
        """ 重置为默认 PID 参数 """
        # Factory Defaults (Updated to new Tuned values)
        default_kp = 0.5
        default_ki = 0.0
        default_kd = 0.1
        
        self.slider_kp.setValue(int(default_kp * 100))
        self.slider_ki.setValue(int(default_ki * 100))
        self.slider_kd.setValue(int(default_kd * 100))
        print("[GUI] PID 参数已重置")

    def update_log(self, data):
        pass


