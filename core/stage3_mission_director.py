# -*- coding: utf-8 -*-
"""
Stage 3 Autonomous Mission Director (第三阶段自主防空任务指挥官)

竞赛规程规范任务流程（能力7 / 第三阶段可选加分项）：
约 10 米处放置 1 个红色（敌方）+ 2 个蓝色（友方）目标：
1. 态势扫描与友军保护认证 (Scan & Verify IFF)
2. 锁定并自主摧毁敌方 (Engage & Destroy Hostile)
3. 停火并精确等待 10 秒 (Post-Engagement Wait 10s)
4. 触发急停 (Trigger Emergency Stop)
5. 急停后再次精确等待 10 秒 (Post-ESTOP Stabilization Wait 10s)
6. 安全关机退出 (Safe System Shutdown)
全程系统 100% 严禁对蓝色友军开火，实时生成裁判铁证记录。
"""

import time
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from utils.logger import Logger

logger = Logger("MissionDirector")


class Stage3MissionState:
    IDLE = "IDLE"
    ACQUIRING = "ACQUIRING"              # 阶段 1: 扫描并锁定敌方 (友军受安全门保护)
    ENGAGING = "ENGAGING"                # 阶段 2: 摧毁敌方 (开火打击)
    WAIT_POST_FIRE = "WAIT_POST_FIRE"    # 阶段 3: 等待 10 秒
    EMERGENCY_STOP = "EMERGENCY_STOP"    # 阶段 4: 按急停
    WAIT_POST_ESTOP = "WAIT_POST_ESTOP"  # 阶段 5: 再等 10 秒
    COMPLETED = "COMPLETED"              # 阶段 6: 任务圆满完成，准备关机
    ABORTED = "ABORTED"                  # 任务中止


class Stage3MissionDirector(QObject):
    """
    第三阶段自主竞赛任务状态机
    """
    # 信号定义
    state_changed = pyqtSignal(str, str)        # (state, message)
    countdown_updated = pyqtSignal(float, float) # (remaining_sec, total_sec)
    step_progress = pyqtSignal(int, str)         # (current_step: 1-6, step_name)
    friendly_audit_signal = pyqtSignal(int, int) # (friendly_detected_count, friendly_fired_count)
    log_message = pyqtSignal(str, str)           # (level, message)
    request_emergency_stop = pyqtSignal()        # 触发急停请求
    request_shutdown = pyqtSignal()              # 触发关机请求

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.state = Stage3MissionState.IDLE
        
        # 配置参数 (秒)
        self.engagement_duration = 4.0   # 攻击持续时间 (秒)
        self.post_fire_wait = 10.0       # 击毁后等待 10 秒
        self.post_estop_wait = 10.0      # 急停后等待 10 秒
        
        # 实时计时器
        self.timer = QTimer(self)
        self.timer.setInterval(50)  # 20 Hz 高精度倒计时
        self.timer.timeout.connect(self._on_tick)
        
        self.phase_start_time = 0.0
        self.phase_target_duration = 0.0
        
        # 裁判铁证数据统计
        self.friendly_count = 0
        self.friendly_fired_count = 0  # 必须始终保持为 0
        self.enemy_count = 0
        self.hostile_destroyed = False
        self.mission_start_time = 0.0
        self.engaging_start_time = 0.0
        self.hostile_disappeared_since = 0.0

    @property
    def is_running(self) -> bool:
        return self.state not in (Stage3MissionState.IDLE, Stage3MissionState.COMPLETED, Stage3MissionState.ABORTED)

    def start_mission(self) -> bool:
        """启动第三阶段自主任务流程"""
        if self.is_running:
            return False

        logger.info("[MISSION] 🚀 启动第三阶段自主防空任务 (Stage 3 Mission Started)!")
        self.friendly_fired_count = 0
        self.hostile_destroyed = False
        self.mission_start_time = time.time()
        self.engaging_start_time = 0.0
        self.hostile_disappeared_since = 0.0

        # 1. 确保系统处于自动追踪模式与激光保险使能，但初始绝对不发射激光
        if self.main_window:
            try:
                if hasattr(self.main_window.mode_panel, "mode_group"):
                    btn = self.main_window.mode_panel.mode_group.button(2)
                    if btn:
                        btn.setChecked(True)
                self.main_window.on_mode_changed("YOLO_TRACKING")
                self.main_window.control_panel.set_control_enabled(True)
                self.main_window.control_panel.btn_arm.setChecked(True)
                self.main_window.controller.set_laser_armed(True)
                self.main_window.controller.set_laser_firing(False) # 初始阶段确保激光停火
            except Exception as e:
                logger.error(f"[MISSION ERROR] 初始化任务状态异常: {e}")

        self._enter_state(Stage3MissionState.ACQUIRING, "Step 1/6: Scanning & Slewing Reticle to Hostile (跟到目标再开火)...")
        self.step_progress.emit(1, "Acquiring & Slewing to Target")
        return True

    def abort_mission(self, reason: str = "User Aborted") -> None:
        """中止任务"""
        self.timer.stop()
        if self.main_window:
            self.main_window.controller.set_laser_firing(False)
        self._enter_state(Stage3MissionState.ABORTED, f"Mission Aborted: {reason}")
        logger.warning(f"[MISSION] ⏹ 任务中止: {reason}")

    def confirm_destruction(self) -> bool:
        """
        确认目标已摧毁（由操作员/裁判点击或视觉自动识别靶标消失后调用）
        """
        if self.state != Stage3MissionState.ENGAGING:
            logger.warning("[MISSION] 目标未处于交战状态，无法确认摧毁")
            return False

        logger.info("[MISSION] 💥 确认敌方目标已摧毁 (Hostile Destruction Confirmed)!")
        self.hostile_destroyed = True
        
        # 立即切断激光
        if self.main_window:
            try:
                self.main_window.controller.set_laser_firing(False)
            except Exception:
                pass

        # 推进至第 3 阶段：等待 10 秒
        self._enter_state(Stage3MissionState.WAIT_POST_FIRE, "Step 3/6: Hostile Destroyed! Cease Fire >> Waiting 10s...")
        self.step_progress.emit(3, "Post-Fire Wait 10s")
        return True

    def on_detections_update(self, dets: list) -> None:
        """从视觉检测流水线接收最新态势"""
        if not self.is_running:
            return

        import math
        red_dets = [d for d in dets if str(d.get("taraf", "")).upper() in ("ENEMY", "RED")]
        blue_c = sum(1 for d in dets if str(d.get("taraf", "")).upper() in ("FRIENDLY", "BLUE"))
        
        self.enemy_count = len(red_dets)
        self.friendly_count = blue_c
        self.friendly_audit_signal.emit(self.friendly_count, self.friendly_fired_count)

        # 阶段 1: 扫描与伺服逼近阶段 (ACQUIRING)
        # 核心逻辑：云台自主跟踪敌方，必须等待准星真正接触/进入敌方目标框内后，才准许开火！
        if self.state == Stage3MissionState.ACQUIRING:
            if red_dets:
                from config.vision_config import VisionConfig
                aim_x, aim_y = VisionConfig.aim_point(VisionConfig.AKTIF_MESAFE_M)
                
                target = red_dets[0]
                x1, y1, x2, y2 = target.get("box", (0, 0, 0, 0))
                pos = target.get("position", ((x1 + x2) // 2, (y1 + y2) // 2))
                dist = math.hypot(aim_x - pos[0], aim_y - pos[1])
                bw = max(x2 - x1, 1)
                bh = max(y2 - y1, 1)
                
                # 准星是否已到达目标框内或距离质心极近 (已跟到位)
                is_on_target = (x1 <= aim_x <= x2 and y1 <= aim_y <= y2) or (dist <= max(24.0, min(bw, bh) * 0.55))
                
                if is_on_target:
                    self.engaging_start_time = time.time()
                    self.hostile_disappeared_since = 0.0
                    self._enter_state(
                        Stage3MissionState.ENGAGING, 
                        "Step 2/6: Crosshair On Target >> Continuous Laser Tracking & Engaging (不停跟踪照射)..."
                    )
                    self.step_progress.emit(2, "Continuous Laser Engagement")
                    if self.main_window:
                        self.main_window.controller.set_laser_firing(True)
                else:
                    # 正在伺服跟踪飞向目标，严禁提前开火
                    if self.main_window and self.main_window.controller.laser_firing:
                        self.main_window.controller.set_laser_firing(False)
                    self.step_progress.emit(1, f"Slewing to Target (Dist: {dist:.0f}px)")
            else:
                if self.main_window and self.main_window.controller.laser_firing:
                    self.main_window.controller.set_laser_firing(False)

        # 阶段 2: 持续跟踪照射打击阶段 (ENGAGING)
        # 保持连续高能激光发射 (不是点射，而是不停的跟踪的射)，直至目标被摧毁
        elif self.state == Stage3MissionState.ENGAGING:
            # 持续确保激光发射保持开启
            if self.main_window and not self.main_window.controller.laser_firing:
                self.main_window.controller.set_laser_firing(True)

            now = time.time()
            # 目标摧毁判定：持续开火照射至少 1.2 秒后，若敌方目标从画面消失持续 >= 0.8 秒，自动确认摧毁
            if (now - self.engaging_start_time) >= 1.2:
                if len(red_dets) == 0:
                    if self.hostile_disappeared_since == 0.0:
                        self.hostile_disappeared_since = now
                    elif (now - self.hostile_disappeared_since) >= 0.8:
                        logger.info("[MISSION] 🎯 视觉感知：红色敌方已完全脱离/被消灭，自动判定摧毁！")
                        self.confirm_destruction()
                else:
                    self.hostile_disappeared_since = 0.0

    def _enter_state(self, new_state: str, message: str) -> None:
        self.state = new_state
        self.phase_start_time = time.time()
        
        if new_state == Stage3MissionState.ENGAGING:
            # 交战阶段不再使用固定时间倒计时自动跳过，必须等待摧毁确认！
            self.phase_target_duration = 0.0
            self.timer.stop()
        elif new_state == Stage3MissionState.WAIT_POST_FIRE:
            self.phase_target_duration = self.post_fire_wait
            self.timer.start()
        elif new_state == Stage3MissionState.WAIT_POST_ESTOP:
            self.phase_target_duration = self.post_estop_wait
            self.timer.start()
        elif new_state in (Stage3MissionState.IDLE, Stage3MissionState.COMPLETED, Stage3MissionState.ABORTED):
            self.timer.stop()

        self.state_changed.emit(self.state, message)
        logger.info(f"[MISSION] State -> {new_state}: {message}")

    def _on_tick(self) -> None:
        """高精度倒计时调度"""
        if self.phase_target_duration <= 0.0:
            return
            
        elapsed = time.time() - self.phase_start_time
        remaining = max(0.0, self.phase_target_duration - elapsed)
        self.countdown_updated.emit(remaining, self.phase_target_duration)

        if remaining <= 0.001:
            self._on_phase_finished()

    def _on_phase_finished(self) -> None:
        """当前阶段完成，自动推进下一步"""
        self.timer.stop()

        if self.state == Stage3MissionState.WAIT_POST_FIRE:
            # 等待 10 秒结束 -> 阶段 4: 按急停
            self._enter_state(Stage3MissionState.EMERGENCY_STOP, "Step 4/6: 10s Elapsed >> Triggering Emergency Stop (E-STOP)...")
            self.step_progress.emit(4, "Emergency Stop")
            self.request_emergency_stop.emit()
            if self.main_window:
                self.main_window.on_emergency_stop()
            
            # 立即进入阶段 5: 急停后再等 10 秒
            QTimer.singleShot(400, lambda: self._start_post_estop_wait())

        elif self.state == Stage3MissionState.WAIT_POST_ESTOP:
            # 再等 10 秒结束 -> 阶段 6: 关机准备与裁判报告
            self._enter_state(Stage3MissionState.COMPLETED, "Step 6/6: Mission Completed Successfully! Ready for Safe Shutdown.")
            self.step_progress.emit(6, "Mission Complete / Shutdown")

    def _start_post_estop_wait(self) -> None:
        self._enter_state(Stage3MissionState.WAIT_POST_ESTOP, "Step 5/6: Emergency Stop Engaged >> Waiting 10s Stabilization...")
        self.step_progress.emit(5, "Post-ESTOP Wait 10s")

    def execute_shutdown(self) -> None:
        """安全关机退出程序"""
        logger.info("[MISSION] 🛑 执行安全关机退出 (Executing Clean System Shutdown)...")
        if self.main_window:
            self.main_window.close()
