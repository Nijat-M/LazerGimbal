# -*- coding: utf-8 -*-
"""
现代化 Fluent 主地面站窗口 (LaserGimbal Fluent Ground Station)

架构特色：
1. FluentWindow 侧边栏/顶部自适应导航栏
2. 三大核心子系统页面：作战操控台 (Console)、PID 调参诊断 (Tuning)、硬件与系统设置 (Settings)
3. 全局键盘无冲突拦截器 (GlobalKeyFilter)：WASD/方向键直接控云台、空格击发、Esc 急停
4. 滚轮防误触机制：页面滑动不窜改任何参数
"""

import sys
import time
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon, QCloseEvent
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon,
    setTheme, Theme, InfoBar, InfoBarPosition
)

from utils.logger import Logger
logger = Logger("FluentApp")

from config import cfg
from config.control_config import ControlConfig
from core.serial_thread import SerialThread
from core.gimbal_controller import GimbalController
from vision.vision_worker import VisionWorker

from gui.fluent.views.console_view import ConsoleView
from gui.fluent.views.tuning_view import TuningView
from gui.fluent.views.settings_view import SettingsView
from gui.fluent.common.event_filters import GlobalKeyFilter


class FluentAppWindow(FluentWindow):
    """现代化 Fluent 地面站主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LaserGimbal Pro - Fluent Ground Station")
        self.setMinimumSize(920, 580)

        # 智能适应屏幕尺寸 (默认 1200x720 黄金比例，防止在笔记本或小屏幕上超屏)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            w = min(1200, max(920, geo.width() - 80))
            h = min(720, max(580, geo.height() - 80))
            self.resize(w, h)
            self.move((geo.width() - w) // 2, (geo.height() - h) // 2)
        else:
            self.resize(1180, 700)

        self.camera_request_generation = -1

        # 默认暗黑主题
        setTheme(Theme.DARK)

        # 1. 初始化底层核心线程与控制器
        self.serial_thread = SerialThread()
        self.vision_thread = VisionWorker()
        self.controller = GimbalController(self.serial_thread)

        # 2. 创建子系统视图
        self.console_view = ConsoleView(self)
        self.tuning_view = TuningView(
            initial_kp=cfg.PID_KP,
            initial_ki=cfg.PID_KI,
            initial_kd=cfg.PID_KD,
            initial_deadzone=cfg.DEADZONE,
            invert_x=cfg.INVERT_X,
            invert_y=cfg.INVERT_Y,
            parent=self
        )
        self.settings_view = SettingsView(
            default_port=cfg.SERIAL_PORT,
            default_cam_id=cfg.CAMERA_ID,
            parent=self
        )

        # 3. 添加到 FluentWindow 导航栏
        self.init_navigation()

        # 4. 信号槽绑定与数据通信协调
        self.init_signals()

        # 5. 安装全局无死角按键拦截器
        self.init_global_hotkeys()

        # 6. 启动视觉线程
        self.vision_thread.start()
        self.settings_view.set_camera_running_status(True)

    def init_navigation(self):
        """配置侧边导航栏"""
        # 1. 实时作战操控台
        self.addSubInterface(
            self.console_view,
            FluentIcon.CAMERA,
            "作战操控台 (Console)"
        )

        # 2. PID 调优与运动测试
        self.addSubInterface(
            self.tuning_view,
            FluentIcon.DEVELOPER_TOOLS,
            "PID 调优 (Tuning)"
        )

        # 3. 硬件与系统设置 (置于底部)
        self.addSubInterface(
            self.settings_view,
            FluentIcon.SETTING,
            "设备与设置 (Settings)",
            NavigationItemPosition.BOTTOM
        )

    def init_signals(self):
        """连接所有核心信号与槽"""
        # ==========================
        # 1. 视觉线程 (VisionWorker)
        # ==========================
        self.vision_thread.frame_signal.connect(self.console_view.camera_view.update_camera_feed)
        self.vision_thread.mask_signal.connect(self.console_view.camera_view.update_mask_feed)
        self.vision_thread.stats_signal.connect(self._on_vision_stats)
        self.vision_thread.camera_state_signal.connect(self._on_camera_state_changed)
        self.vision_thread.target_pos_signal.connect(self.controller.handle_target_position)

        # ==========================
        # 2. 鼠标手控交互 (FPS Mouse Aim)
        # ==========================
        self.console_view.camera_view.mouse_delta_signal.connect(
            self.controller.handle_mouse_delta
        )
        self.console_view.camera_view.mouse_capture_changed_signal.connect(
            self.controller.set_mouse_capture_active
        )
        self.settings_view.mouse_sensitivity_changed.connect(
            self.controller.update_mouse_sensitivity
        )

        # ==========================
        # 3. 串口与控制器遥测 (Serial & Controller)
        # ==========================
        self.serial_thread.connection_state_signal.connect(self._on_serial_status_changed)
        self.controller.status_update_signal.connect(self._on_controller_status)
        self.controller.position_update_signal.connect(self._on_position_update)

        # ==========================
        # 4. 操控台信号 (ConsoleView)
        # ==========================
        self.console_view.control_toggled.connect(self._on_control_toggled)
        self.console_view.mode_changed.connect(self._on_mode_changed)
        self.console_view.reset_requested.connect(self.controller.sync_position)
        self.console_view.emergency_stop_requested.connect(self.trigger_emergency_stop)
        self.console_view.camera_toggled.connect(self._on_camera_toggled)

        self.console_view.laser_armed_toggled.connect(self.controller.set_laser_armed)
        self.console_view.laser_fire_changed.connect(self.controller.set_laser_firing)
        self.console_view.laser_power_changed.connect(self.controller.set_laser_power)

        # 激光状态反馈 -> 视频准星 HUD & 控制台
        self.controller.laser_state_signal.connect(
            lambda armed, firing, pwr: self.console_view.camera_view.set_laser_status(armed, firing)
        )
        self.controller.laser_state_signal.connect(
            lambda armed, firing, pwr: self.console_view.set_laser_firing_visual(firing)
        )

        # ==========================
        # 5. PID 调参信号 (TuningView)
        # ==========================
        self.tuning_view.pid_changed.connect(self._on_pid_changed)
        self.tuning_view.invert_changed.connect(self.controller.set_invert)
        self.tuning_view.deadzone_changed.connect(self._on_deadzone_changed)
        self.tuning_view.save_requested.connect(self._on_save_config)
        self.tuning_view.reset_requested.connect(self._on_reset_pid)

        self.tuning_view.start_continuous_signal.connect(self.controller.start_manual_continuous)
        self.tuning_view.stop_continuous_signal.connect(self.controller.stop_manual_continuous)
        self.tuning_view.keyboard_control_toggled.connect(self._on_keyboard_control_toggled)

        # ==========================
        # 6. 设置面板信号 (SettingsView)
        # ==========================
        self.settings_view.serial_connection_toggled.connect(self._on_serial_toggle)
        self.settings_view.camera_changed.connect(self._on_camera_device_changed)
        self.settings_view.camera_toggled.connect(self._on_camera_toggled)
        self.settings_view.flip_changed.connect(self.vision_thread.set_flip_mode)
        self.settings_view.open_camera_settings_requested.connect(
            self.vision_thread.open_camera_settings
        )

    def init_global_hotkeys(self):
        """安装全局键盘直控事件过滤器"""
        self.key_filter = GlobalKeyFilter(self)
        self.key_filter.manual_move_press.connect(self.controller.start_manual_continuous)
        self.key_filter.manual_move_release.connect(self.controller.stop_manual_continuous)
        self.key_filter.laser_fire_press.connect(self._on_hotkey_fire_press)
        self.key_filter.laser_fire_release.connect(self._on_hotkey_fire_release)
        self.key_filter.emergency_stop_triggered.connect(self.trigger_emergency_stop)

        # 全局安装到应用实例，无视子控件焦点直接生效
        app = QApplication.instance()
        if app:
            app.installEventFilter(self.key_filter)

    # ==========================
    # 槽函数实现 (Slots)
    # ==========================

    def _on_hotkey_fire_press(self):
        if self.controller.laser_armed:
            self.controller.set_laser_firing(True)

    def _on_hotkey_fire_release(self):
        self.controller.set_laser_firing(False)

    def _on_keyboard_control_toggled(self, enabled: bool):
        self.key_filter.keyboard_control_enabled = enabled

    def _on_control_toggled(self, checked: bool):
        if checked:
            if not self.serial_thread.is_connected():
                InfoBar.warning(
                    title="串口未连接",
                    content="请先在设置页或顶部连接 STM32 串口！",
                    position=InfoBarPosition.TOP,
                    parent=self.console_view
                )
                self.console_view.btn_track.setChecked(False)
                return
            if not self.controller.visual_input_enabled:
                InfoBar.warning(
                    title="摄像头未就绪",
                    content="视频流尚未就绪，请先确认摄像头已启动！",
                    position=InfoBarPosition.TOP,
                    parent=self.console_view
                )
                self.console_view.btn_track.setChecked(False)
                return
            accepted = self.controller.set_control_enabled(True)
            if not accepted:
                self.console_view.btn_track.setChecked(False)
        else:
            self.controller.set_control_enabled(False)

    def _on_camera_state_changed(self, generation: int, ready: bool, message: str):
        if generation < self.camera_request_generation:
            return
        self.camera_request_generation = generation
        self.console_view.camera_view.set_camera_active(ready)
        self.controller.set_visual_input_enabled(ready)
        if not ready:
            self.console_view.btn_track.setChecked(False)
            self.console_view.camera_view.release_mouse_control()
            self.controller.stop_motion(f"{message}，motion stopped")

    def _on_mode_changed(self, mode_str: str):
        logger.info(f"[GUI] Mode switched to: {mode_str}")
        is_mouse = mode_str == "MOUSE_MANUAL"
        self.console_view.camera_view.release_mouse_control()
        self.console_view.btn_track.setChecked(False)
        self.controller.set_manual_mouse_mode(is_mouse)
        self.console_view.camera_view.set_mouse_control_enabled(is_mouse)

        vision_mode = "IDLE" if mode_str in ("TEST", "MOUSE_MANUAL") else mode_str
        self.vision_thread.set_mode(vision_mode)

    def _on_pid_changed(self, kp: float, ki: float, kd: float):
        cfg.PID_KP = kp
        cfg.PID_KI = ki
        cfg.PID_KD = kd
        self.controller.update_pid_tunings(kp, ki, kd)

    def _on_deadzone_changed(self, deadzone: int):
        ControlConfig.DEADZONE = deadzone
        logger.info(f"[GUI] Deadzone updated to: {deadzone}px")

    def _on_serial_toggle(self, checked: bool, port: str):
        if checked:
            logger.info(f"[GUI] Connecting serial: {port}")
            self.serial_thread.connect_serial(port, cfg.BAUD_RATE)
            if not self.serial_thread.isRunning():
                self.serial_thread.start()
        else:
            logger.info("[GUI] Disconnecting serial")
            self.serial_thread.disconnect_serial()

    def _on_serial_status_changed(self, success: bool, message: str):
        self.console_view.update_serial_status(success, message)
        self.settings_view.set_serial_status(success, message)
        if not success:
            self.console_view.camera_view.release_mouse_control()
            self.controller.stop_motion("Serial connection lost")

    def _on_vision_stats(self, fps: float, res_str: str):
        self.console_view.update_telemetry(fps, res_str)

    def _on_controller_status(self, *args):
        pass

    def _on_position_update(self, x: float, y: float):
        pass

    def _on_camera_device_changed(self, cam_id: int, w: int, h: int):
        self.vision_thread.switch_camera(cam_id, w, h)

    def _on_camera_state_changed(self, generation: int, ready: bool, message: str):
        self.camera_request_generation = generation
        self.controller.set_visual_input_enabled(ready)
        self.settings_view.set_camera_running_status(ready)
        self.console_view.set_camera_running_status(ready)
        if not ready and self.controller.control_enabled:
            self.console_view.btn_track.setChecked(False)

    def _on_camera_toggled(self, running: bool):
        if running:
            cam_id = self.settings_view.combo_camera.currentData()
            if cam_id is None:
                cam_id = cfg.CAMERA_ID
            res_idx = self.settings_view.combo_resolution.currentIndex()
            resolutions = [(640, 480), (1280, 720), (1920, 1080)]
            w, h = resolutions[res_idx] if 0 <= res_idx < len(resolutions) else (640, 480)
            self.vision_thread.switch_camera(cam_id, w, h)
        else:
            self.vision_thread.close_camera()
        self.settings_view.set_camera_running_status(running)
        self.console_view.set_camera_running_status(running)

    def _on_save_config(self):
        cfg.PID_KP = self.tuning_view._kp
        cfg.PID_KI = self.tuning_view._ki
        cfg.PID_KD = self.tuning_view._kd
        cfg.DEADZONE = self.tuning_view._deadzone
        cfg.INVERT_X = self.tuning_view.switch_inv_x.isChecked()
        cfg.INVERT_Y = self.tuning_view.switch_inv_y.isChecked()
        cfg.save_config()

    def _on_reset_pid(self):
        default_kp = ControlConfig.KP
        default_ki = ControlConfig.KI
        default_kd = ControlConfig.KD
        self.tuning_view.set_pid_values(default_kp, default_ki, default_kd, False, True, 5)
        self.controller.update_pid_tunings(default_kp, default_ki, default_kd)
        self.controller.set_invert(False, True)

    def trigger_emergency_stop(self):
        """全局急停"""
        logger.warning("[GUI] 🛑 急停已触发 (EMERGENCY STOP)！")
        self.console_view.camera_view.release_mouse_control()
        self.console_view.handle_emergency_reset()
        self.controller.set_laser_armed(False)
        self.controller.stop_motion("🛑 Emergency Stop Triggered")

        InfoBar.error(
            title="🛑 紧急停机已触发",
            content="电机驱动已切断，激光硬件已强制锁定并断电！",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=4000,
            parent=self.console_view
        )

    def closeEvent(self, event: QCloseEvent | None):
        """安全关闭各后台线程"""
        logger.info("[GUI] Exiting Fluent Application...")
        self.console_view.camera_view.release_mouse_control()
        self.controller.stop()

        if self.serial_thread.isRunning():
            time.sleep(0.03)
            self.serial_thread.stop()
        else:
            self.serial_thread.disconnect_serial()

        if self.vision_thread.isRunning():
            self.vision_thread.stop(3000)

        if event:
            event.accept()
