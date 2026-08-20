import os
import sys
import unittest
from typing import ClassVar

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_ = os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from gui.widgets.mode_panel import ModePanel


class ModePanelTests(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        instance = QApplication.instance()
        cls.app = instance if isinstance(instance, QApplication) else QApplication([])

    def test_laser_tracking_mode_is_not_available(self) -> None:
        panel = ModePanel()
        labels = [button.text() for button in panel.mode_group.buttons()]

        self.assertFalse(hasattr(panel, "rb_tracking"))
        self.assertFalse(any("激光追踪" in label for label in labels))
        self.assertFalse(any("Laser Tracking" in label for label in labels))

    def test_blue_tracking_mode_remains_available(self) -> None:
        panel = ModePanel()
        panel.set_mode("BLUE_TRACKING")

        self.assertEqual(panel.get_current_mode(), "BLUE_TRACKING")


if __name__ == "__main__":
    _ = unittest.main()
