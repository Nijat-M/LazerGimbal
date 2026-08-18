# -*- coding: utf-8 -*-
import os
import unittest
from typing import ClassVar

_ = os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from gui.fluent.app_window import FluentAppWindow
from gui.fluent.views.console_view import ConsoleView
from gui.fluent.views.tuning_view import TuningView
from gui.fluent.views.settings_view import SettingsView


class FluentUITests(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        instance = QApplication.instance()
        cls.app = instance if isinstance(instance, QApplication) else QApplication([])

    def test_views_initialization(self) -> None:
        console = ConsoleView()
        self.assertIsNotNone(console.camera_view)
        self.assertIsNotNone(console.mode_combo)
        self.assertIsNotNone(console.btn_track)

        tuning = TuningView()
        self.assertIsNotNone(tuning.kp_slider)
        self.assertIsNotNone(tuning.btn_save)

        settings = SettingsView()
        self.assertIsNotNone(settings.combo_port)
        self.assertIsNotNone(settings.combo_camera)

    def test_fluent_app_window_navigation(self) -> None:
        window = FluentAppWindow()
        self.assertIsNotNone(window.console_view)
        self.assertIsNotNone(window.tuning_view)
        self.assertIsNotNone(window.settings_view)

        # 切换各页面测试
        window.switchTo(window.tuning_view)
        window.switchTo(window.settings_view)
        window.switchTo(window.console_view)


if __name__ == "__main__":
    _ = unittest.main()
