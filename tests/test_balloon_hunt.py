# -*- coding: utf-8 -*-
import unittest
import cv2
import numpy as np
import math

class TestBalloonHunt(unittest.TestCase):
    def setUp(self):
        # Create test frame with orange balloon
        self.frame = np.full((480, 640, 3), (85, 205, 215), dtype=np.uint8) # Yellow wall background
        # Draw user's orange balloon (BGR: 66, 118, 200)
        cv2.circle(self.frame, (320, 240), 80, (66, 118, 200), -1)

    def test_orange_balloon_segmentation(self):
        hsv = cv2.cvtColor(self.frame, cv2.COLOR_BGR2HSV)
        b = self.frame[:, :, 0].astype(np.float32)
        g = self.frame[:, :, 1].astype(np.float32)
        r = self.frame[:, :, 2].astype(np.float32)

        hsv_mask = cv2.inRange(hsv, (5, 65, 55), (25, 255, 255))
        bgr_mask = (r > g + 25) & (r > b + 45) & (r >= 95)
        mask_orange = hsv_mask & (bgr_mask.astype(np.uint8) * 255)

        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        mask_clean = cv2.morphologyEx(mask_orange, cv2.MORPH_OPEN, kernel_open)
        mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, kernel_close)

        contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid = [c for c in contours if cv2.contourArea(c) >= 350]
        self.assertGreater(len(valid), 0, "Failed to segment orange balloon")

        c_max = max(valid, key=cv2.contourArea)
        M = cv2.moments(c_max)
        bx = int(M['m10'] / M['m00'])
        by = int(M['m01'] / M['m00'])
        (cx_b, cy_b), radius = cv2.minEnclosingCircle(c_max)

        self.assertAlmostEqual(bx, 320, delta=5)
        self.assertAlmostEqual(by, 240, delta=5)
        self.assertAlmostEqual(radius, 80, delta=5)

        # Test Aim Point Touch
        aim_touch = (310, 235)
        aim_miss = (100, 100)

        is_touch = cv2.pointPolygonTest(c_max, aim_touch, False) >= 0 or math.hypot(aim_touch[0]-bx, aim_touch[1]-by) <= radius
        is_miss = cv2.pointPolygonTest(c_max, aim_miss, False) >= 0 or math.hypot(aim_miss[0]-bx, aim_miss[1]-by) <= radius

        self.assertTrue(is_touch, "Aim point inside balloon should trigger touch")
        self.assertFalse(is_miss, "Aim point far away should not trigger touch")

if __name__ == '__main__':
    unittest.main()
