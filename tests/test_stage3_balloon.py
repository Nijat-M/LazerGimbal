# -*- coding: utf-8 -*-
"""
Unit tests for Stage 3 Balloon Defense Mode & IFF Separation
"""

import sys
import os
import unittest
import numpy as np
import cv2

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

from core.stage3_mission_director import Stage3MissionDirector, Stage3MissionState
from vision.vision_worker import VisionWorker


class Stage3BalloonDefenseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.wall_color_bgr = (120, 165, 185)

    def test_synthetic_hallway_three_balloons(self):
        """
        Test synthetic frame with 1 Red Balloon in center and 2 Blue Balloons on sides.
        """
        frame = np.full((480, 640, 3), self.wall_color_bgr, dtype=np.uint8)
        frame[250:, :] = (90, 120, 140) # Floor

        # Left Blue Balloon (Cyan BGR: 210, 200, 50)
        cv2.circle(frame, (200, 320), 22, (210, 200, 50), -1)
        # Center Red Balloon (Red BGR: 30, 45, 220)
        cv2.circle(frame, (320, 320), 22, (30, 45, 220), -1)
        # Right Blue Balloon (Cyan BGR: 210, 200, 50)
        cv2.circle(frame, (440, 320), 22, (210, 200, 50), -1)

        worker = VisionWorker()
        worker.mode = "STAGE3_BALLOONS"

        received_dets = []
        worker.detections_signal.connect(lambda dets: received_dets.extend(dets))

        worker._process_stage3_balloon_defense(frame)

        red_dets = [d for d in received_dets if d["taraf"] == "ENEMY"]
        blue_dets = [d for d in received_dets if d["taraf"] == "FRIENDLY"]

        self.assertEqual(len(red_dets), 1, f"Expected 1 Red Enemy balloon, got {len(red_dets)}")
        self.assertEqual(len(blue_dets), 2, f"Expected 2 Blue Friendly balloons, got {len(blue_dets)}")
        self.assertTrue(red_dets[0]["raw_name"].startswith("Red Balloon"))
        self.assertTrue(blue_dets[0]["raw_name"].startswith("Blue Balloon"))

    def test_real_user_uploaded_image(self):
        """
        Test on real photo uploaded by the user from the hallway.
        """
        img_path = os.path.join(PROJECT_ROOT, "scratch", "media_1787162313810.jpg")
        alt_path = r"C:\Users\BYC TURK\.gemini\antigravity-ide\brain\7e1c18de-de49-40cf-a017-5dd5bf8670ed\.user_uploaded\media_1787162313810.jpg"
        if not os.path.exists(img_path) and os.path.exists(alt_path):
            img_path = alt_path

        if os.path.exists(img_path):
            frame = cv2.imread(img_path)
            worker = VisionWorker()
            worker.mode = "STAGE3_BALLOONS"

            received_dets = []
            worker.detections_signal.connect(lambda dets: received_dets.extend(dets))

            worker._process_stage3_balloon_defense(frame)

            red_dets = [d for d in received_dets if d["taraf"] == "ENEMY"]
            blue_dets = [d for d in received_dets if d["taraf"] == "FRIENDLY"]

            self.assertEqual(len(red_dets), 1, f"Expected 1 Red Enemy balloon in real photo, got {len(red_dets)}")
            self.assertGreaterEqual(len(blue_dets), 1, f"Expected at least 1 Blue Friendly balloon in real photo, got {len(blue_dets)}")

    def test_stage3_director_state_machine_with_balloons(self):
        """
        Test Stage 3 Director progressing through timeline with Red Balloon target.
        """
        director = Stage3MissionDirector()
        states_recorded = []
        director.state_changed.connect(lambda s, m: states_recorded.append(s))

        # Start mission
        started = director.start_mission()
        self.assertTrue(started)
        self.assertEqual(director.state, Stage3MissionState.ACQUIRING)

        from config.vision_config import VisionConfig
        aim_x, aim_y = VisionConfig.aim_point(VisionConfig.AKTIF_MESAFE_M)

        # Feed detections: 1 Red Enemy + 2 Blue Friendly (with Red right at aim point)
        fake_dets = [
            {"raw_name": "Red Balloon", "taraf": "ENEMY", "box": (aim_x - 20, aim_y - 20, aim_x + 20, aim_y + 20), "position": (aim_x, aim_y)},
            {"raw_name": "Blue Balloon", "taraf": "FRIENDLY", "box": (aim_x - 120, aim_y - 20, aim_x - 80, aim_y + 20), "position": (aim_x - 100, aim_y)},
            {"raw_name": "Blue Balloon", "taraf": "FRIENDLY", "box": (aim_x + 80, aim_y - 20, aim_x + 120, aim_y + 20), "position": (aim_x + 100, aim_y)},
        ]
        director.on_detections_update(fake_dets)

        self.assertEqual(director.state, Stage3MissionState.ENGAGING)
        self.assertEqual(director.friendly_count, 2)
        self.assertEqual(director.friendly_fired_count, 0)
        self.assertEqual(director.enemy_count, 1)

        # Manually confirm destruction
        director.confirm_destruction()
        self.assertEqual(director.state, Stage3MissionState.WAIT_POST_FIRE)

        # Fast forward phase finished
        director._on_phase_finished()
        self.assertEqual(director.state, Stage3MissionState.EMERGENCY_STOP)


if __name__ == "__main__":
    unittest.main()
