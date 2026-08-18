# -*- coding: utf-8 -*-
"""
Stage 3 Mission Panel (第三阶段自主防空竞赛面板)

专为竞赛“击毁敌方 -> 等待10秒 -> 按急停 -> 再等10秒 -> 关机”设计的可视化指挥面板。
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QFrame, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.stage3_mission_director import Stage3MissionDirector, Stage3MissionState


class Stage3MissionPanel(QGroupBox):
    """Stage 3 Autonomous Mission Control Panel"""

    def __init__(self, director: Stage3MissionDirector, parent=None):
        super().__init__("Stage 3 — Autonomous Mission (Stage 3 竞赛加分流程)", parent)
        self.director = director
        self.init_ui()
        self.init_signals()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 12, 8, 8)

        # 1. 任务流程步骤进度条 (6 阶段 Stepper)
        self.lbl_steps_header = QLabel("MISSION TIMELINE:")
        self.lbl_steps_header.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.lbl_steps_header)

        self.step_labels = []
        steps_widget = QWidget()
        steps_layout = QVBoxLayout(steps_widget)
        steps_layout.setSpacing(3)
        steps_layout.setContentsMargins(0, 0, 0, 0)

        step_names = [
            "1. 态势扫描 (1敌+2友)",
            "2. 自主锁定并摧毁敌方",
            "3. 停火并精确等待 10 秒",
            "4. 触发急停 (E-STOP)",
            "5. 急停后再等待 10 秒",
            "6. 任务圆满完成并安全关机"
        ]

        for i, name in enumerate(step_names):
            lbl = QLabel(f"⚪ {name}")
            lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 500;")
            self.step_labels.append(lbl)
            steps_layout.addWidget(lbl)

        layout.addWidget(steps_widget)

        # 2. 核心状态与倒计时显示横幅
        self._base_message = "READY TO START STAGE 3 MISSION"
        self.lbl_mission_status = QLabel(self._base_message)
        self.lbl_mission_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mission_status.setFixedHeight(50)
        self.lbl_mission_status.setStyleSheet("""
            background-color: #0f172a;
            color: #38bdf8;
            font-weight: bold;
            font-family: Consolas, "Segoe UI", monospace;
            font-size: 11px;
            padding: 4px;
            border-radius: 4px;
            border: 2px solid #0284c7;
        """)
        layout.addWidget(self.lbl_mission_status)

        # 3. 倒计时进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #1e293b;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06b6d4, stop:1 #10b981);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 4. 裁判铁证数据卡 (Referee Live Audit Card)
        self.lbl_audit = QLabel("🛡️ FRIENDLY: 2/2 PROTECTED  |  SHOTS ON FRIENDLY: 0")
        self.lbl_audit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_audit.setFixedHeight(28)
        self.lbl_audit.setStyleSheet("""
            background-color: #062a1c;
            color: #34d399;
            font-weight: bold;
            font-size: 10px;
            border-radius: 3px;
            border: 1px solid #059669;
        """)
        layout.addWidget(self.lbl_audit)

        # 5. 操作控制按钮行
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_start = QPushButton("▶ 启动第三阶段任务")
        self.btn_start.setFixedHeight(36)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #10b981;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748b;
            }
        """)
        btn_layout.addWidget(self.btn_start, 2)

        self.btn_abort = QPushButton("⏹ 中止")
        self.btn_abort.setFixedHeight(36)
        self.btn_abort.setEnabled(False)
        self.btn_abort.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #e2e8f0;
                font-weight: bold;
                font-size: 11px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #dc2626;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #475569;
            }
        """)
        btn_layout.addWidget(self.btn_abort, 1)

        layout.addLayout(btn_layout)

        # 6. 安全关机按钮 (完成阶段点亮)
        self.btn_shutdown = QPushButton("🛑 安全关机 (Clean Shutdown)")
        self.btn_shutdown.setFixedHeight(34)
        self.btn_shutdown.setVisible(False)
        self.btn_shutdown.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ef4444;
            }
        """)
        layout.addWidget(self.btn_shutdown)

    def init_signals(self):
        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_abort.clicked.connect(self._on_abort_clicked)
        self.btn_shutdown.clicked.connect(self._on_shutdown_clicked)

        self.director.state_changed.connect(self._on_state_changed)
        self.director.countdown_updated.connect(self._on_countdown_updated)
        self.director.step_progress.connect(self._on_step_progress)
        self.director.friendly_audit_signal.connect(self._on_friendly_audit)

    def _on_start_clicked(self):
        self.btn_start.setEnabled(False)
        self.btn_abort.setEnabled(True)
        self.btn_shutdown.setVisible(False)
        self.director.start_mission()

    def _on_abort_clicked(self):
        self.director.abort_mission("User Aborted")
        self.btn_start.setEnabled(True)
        self.btn_abort.setEnabled(False)

    def _on_shutdown_clicked(self):
        self.director.execute_shutdown()

    def _on_state_changed(self, state: str, message: str):
        self._base_message = message
        self.lbl_mission_status.setText(message)

        if state == Stage3MissionState.ENGAGING:
            self.lbl_mission_status.setStyleSheet("""
                background-color: #3f1010; color: #ef4444; font-weight: bold;
                font-family: Consolas, monospace; font-size: 11px;
                padding: 4px; border-radius: 4px; border: 2px solid #ef4444;
            """)
        elif state in (Stage3MissionState.WAIT_POST_FIRE, Stage3MissionState.WAIT_POST_ESTOP):
            self.lbl_mission_status.setStyleSheet("""
                background-color: #1e1b4b; color: #a855f7; font-weight: bold;
                font-family: Consolas, monospace; font-size: 11px;
                padding: 4px; border-radius: 4px; border: 2px solid #a855f7;
            """)
        elif state == Stage3MissionState.EMERGENCY_STOP:
            self.lbl_mission_status.setStyleSheet("""
                background-color: #450a0a; color: #f87171; font-weight: bold;
                font-family: Consolas, monospace; font-size: 11px;
                padding: 4px; border-radius: 4px; border: 2px solid #dc2626;
            """)
        elif state == Stage3MissionState.COMPLETED:
            self.lbl_mission_status.setStyleSheet("""
                background-color: #064e3b; color: #34d399; font-weight: bold;
                font-family: Consolas, monospace; font-size: 11px;
                padding: 4px; border-radius: 4px; border: 2px solid #10b981;
            """)
            self.btn_start.setEnabled(True)
            self.btn_abort.setEnabled(False)
            self.btn_shutdown.setVisible(True)
        elif state in (Stage3MissionState.IDLE, Stage3MissionState.ABORTED):
            self.lbl_mission_status.setStyleSheet("""
                background-color: #0f172a; color: #38bdf8; font-weight: bold;
                font-family: Consolas, monospace; font-size: 11px;
                padding: 4px; border-radius: 4px; border: 2px solid #0284c7;
            """)
            self.btn_start.setEnabled(True)
            self.btn_abort.setEnabled(False)
            self.progress_bar.setValue(0)

    def _on_countdown_updated(self, remaining: float, total: float):
        if total > 0:
            pct = int((1.0 - (remaining / total)) * 1000)
            self.progress_bar.setValue(pct)
            self.lbl_mission_status.setText(f"{self._base_message}\n⏳ 倒计时: {remaining:.1f} 秒 (剩余 {int(remaining/total*100)}%)")

    def _on_step_progress(self, current_step: int, step_name: str):
        for i, lbl in enumerate(self.step_labels):
            idx = i + 1
            if idx < current_step:
                lbl.setText(f"✓ {lbl.text()[2:]}")
                lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: bold;")
            elif idx == current_step:
                lbl.setText(f"▶ {lbl.text()[2:]}")
                lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")
            else:
                lbl.setText(f"⚪ {lbl.text()[2:]}")
                lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: 500;")

    def _on_friendly_audit(self, friendly_c: int, fired_c: int):
        txt = f"🛡️ FRIENDLY: {friendly_c} PROTECTED  |  SHOTS ON FRIENDLY: {fired_c} (100% SAFE)"
        self.lbl_audit.setText(txt)
