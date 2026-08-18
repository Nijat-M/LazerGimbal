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

    def test_geometric_shape_filtering(self):
        # 1. Round Balloon
        m_round = np.zeros((300, 300), dtype=np.uint8)
        cv2.circle(m_round, (150, 150), 70, 255, -1)
        c_round = max(cv2.findContours(m_round, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
        area_r = cv2.contourArea(c_round)
        perim_r = cv2.arcLength(c_round, True)
        circ_r = 4.0 * math.pi * area_r / (perim_r ** 2)
        solid_r = area_r / float(cv2.contourArea(cv2.convexHull(c_round)))
        self.assertGreaterEqual(circ_r, 0.45)
        self.assertGreaterEqual(solid_r, 0.82)

        # 2. Long Thin Wire (Should be rejected)
        m_wire = np.zeros((300, 300), dtype=np.uint8)
        cv2.line(m_wire, (150, 20), (150, 280), 255, 6)
        c_wire = max(cv2.findContours(m_wire, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
        area_w = cv2.contourArea(c_wire)
        perim_w = cv2.arcLength(c_wire, True)
        circ_w = 4.0 * math.pi * area_w / (perim_w ** 2)
        self.assertLess(circ_w, 0.45, "Long wire should be rejected by circularity")

if __name__ == '__main__':
    unittest.main()
