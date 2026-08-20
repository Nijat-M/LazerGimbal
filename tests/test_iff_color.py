import os
import sys
import unittest
import numpy as np
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vision.iff import iff_analiz, IFFKarari, ENEMY, FRIENDLY, NEUTRAL


class IFFHallwayLightingTests(unittest.TestCase):
    """测试在走廊暖光、阴影暗处及边缘背景干扰下的红蓝敌我识别"""

    def setUp(self):
        # 走廊米黄/暖白墙壁背景色彩 (Warm hallway wall: High R, moderate G, lower B)
        self.wall_color_bgr = np.array([120, 165, 185], dtype=np.uint8)

    def test_shadow_dim_red_target(self):
        """
        场景 1: 左侧红色飞机剪纸处在走廊弱光阴影区
        """
        frame = np.full((480, 640, 3), self.wall_color_bgr, dtype=np.uint8)
        box = [80, 180, 140, 260]
        # 实际视频中的红色飞机剪纸色彩 (BGR: 36, 62, 213)
        shadow_red = np.array([36, 62, 213], dtype=np.uint8)
        frame[200:245, 95:125] = shadow_red

        taraf, k_cnt, m_cnt, oran = iff_analiz(frame, box)
        self.assertEqual(taraf, ENEMY, f"阴影弱光下的红色目标应判为 ENEMY，实际判定: {taraf} (Red: {k_cnt}, Blue: {m_cnt})")
        self.assertGreater(k_cnt, 0)
        self.assertGreater(k_cnt, m_cnt)

    def test_warm_light_dark_blue_target(self):
        """
        场景 2: 右侧深蓝飞机剪纸处在走廊暖光下
        """
        frame = np.full((480, 640, 3), self.wall_color_bgr, dtype=np.uint8)
        box = [400, 180, 460, 260]
        # 实际视频中的蓝色剪纸色彩 (BGR: 165, 145, 31)
        warm_blue = np.array([165, 145, 31], dtype=np.uint8)
        frame[200:245, 415:445] = warm_blue

        taraf, k_cnt, m_cnt, oran = iff_analiz(frame, box)
        self.assertEqual(taraf, FRIENDLY, f"暖光下的深蓝目标应判为 FRIENDLY，实际判定: {taraf} (Red: {k_cnt}, Blue: {m_cnt})")
        self.assertGreater(m_cnt, 0)
        self.assertGreater(m_cnt, k_cnt)

    def test_blue_target_with_red_alarm_fixture_on_edge(self):
        """
        场景 3: 蓝色飞机剪纸框内顶部附带了红色消防报警器/按钮
        """
        frame = np.full((480, 640, 3), self.wall_color_bgr, dtype=np.uint8)
        box = [400, 180, 470, 270]
        
        # 1. 框的极顶部 (y=181..183, x=430..435) 有微小红色报警方块 (几个像素)
        bright_red_alarm = np.array([25, 25, 220], dtype=np.uint8)
        frame[181:184, 430:436] = bright_red_alarm

        # 2. 框的中心主体是深蓝色飞机
        warm_blue = np.array([165, 145, 31], dtype=np.uint8)
        frame[205:255, 415:455] = warm_blue

        taraf, k_cnt, m_cnt, oran = iff_analiz(frame, box)
        self.assertEqual(taraf, FRIENDLY, f"带顶部红色按钮的蓝色飞机应判为 FRIENDLY，实际判定: {taraf} (Red: {k_cnt}, Blue: {m_cnt})")

    def test_neutral_grey_target(self):
        """
        场景 4: 无明显颜色的灰色中性物体或背景误报
        """
        frame = np.full((480, 640, 3), self.wall_color_bgr, dtype=np.uint8)
        box = [200, 200, 260, 260]
        grey_obj = np.array([130, 130, 130], dtype=np.uint8)
        frame[210:250, 210:250] = grey_obj

        taraf, k_cnt, m_cnt, oran = iff_analiz(frame, box)
        self.assertEqual(taraf, NEUTRAL, f"灰色无色目标应判为 NEUTRAL，实际判定: {taraf}")

    def test_temporal_iff_tracker(self):
        """
        场景 5: 时序跟踪器 IFFKarari 的防抖与轨迹平滑
        """
        tracker = IFFKarari(max_distance=75.0, max_missing=5)
        
        class DummyTarget:
            def __init__(self, box, cname="F16", conf=0.85):
                self.box = box
                self.class_name = cname
                self.confidence = conf
                self.class_id = 1

        frame = np.full((480, 640, 3), self.wall_color_bgr, dtype=np.uint8)
        # 放置红色敌机
        frame[200:240, 100:130] = np.array([30, 30, 180], dtype=np.uint8)
        # 放置蓝色友机
        frame[200:240, 400:430] = np.array([160, 60, 30], dtype=np.uint8)

        raw_targets = [
            DummyTarget([90, 190, 140, 250]),
            DummyTarget([390, 190, 440, 250])
        ]

        # 运行连续 3 帧更新
        for _ in range(3):
            results = tracker.update_frame(frame, raw_targets)

        self.assertEqual(len(results), 2)
        sides = {r["box"][0]: r["taraf"] for r in results}
        
        # 左侧应为 ENEMY，右侧应为 FRIENDLY
        left_side = [r["taraf"] for r in results if r["position"][0] < 300][0]
        right_side = [r["taraf"] for r in results if r["position"][0] > 300][0]
        
        self.assertEqual(left_side, ENEMY)
        self.assertEqual(right_side, FRIENDLY)


if __name__ == "__main__":
    unittest.main()
