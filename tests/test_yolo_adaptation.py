# -*- coding: utf-8 -*-
import os
import unittest
import numpy as np
from typing import ClassVar

_ = os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from config.vision_config import VisionConfig
from vision.yolo_detector import YOLODetector, AsyncYOLODetector
from gui.widgets.mode_panel import ModePanel


class YOLOAdaptationTests(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        instance = QApplication.instance()
        cls.app = instance if isinstance(instance, QApplication) else QApplication([])

    def test_defense_model_path_resolution(self):
        """测试 savunma_yolo26.pt 模型文件路径解析"""
        resolved = YOLODetector.resolve_model_path("vision/models/savunma_yolo26.pt")
        self.assertIsNotNone(resolved)
        self.assertTrue(os.path.exists(resolved))
        self.assertTrue(resolved.endswith("savunma_yolo26.pt"))

    def test_list_available_models(self):
        """测试自动扫描并发现可用的 YOLO 模型"""
        models = YOLODetector.list_available_models()
        self.assertGreater(len(models), 0)
        
        # 验证防空模型排在最前面
        self.assertIn(models[0]["filename"], ["yetenek6_best.pt", "savunma_yolo26.pt"])

    def test_defense_model_classes(self):
        """测试国防防空模型正确读取其4个军事防御目标类别"""
        detector = YOLODetector("vision/models/savunma_yolo26.pt")
        class_names = detector.get_class_names()
        
        self.assertIn(0, class_names)
        self.assertEqual(class_names[0], "BALISTIK_FUZE")
        self.assertEqual(class_names[1], "F16")
        self.assertEqual(class_names[2], "HELIKOPTER")
        self.assertEqual(class_names[3], "MINI_IHA")

    def test_detector_inference_and_filtering(self):
        """测试检测推理与类别过滤"""
        detector = YOLODetector("vision/models/savunma_yolo26.pt")
        # 构造纯黑测试图像
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 测试全部类别检测 (不崩溃)
        res_all = detector.detect_target(dummy_frame, target_class=None)
        self.assertIsNotNone(res_all)
        self.assertIsInstance(res_all.all_targets, list)
        
        # 测试指定类别过滤 (BALISTIK_FUZE)
        res_fuze = detector.detect_target(dummy_frame, target_class="BALISTIK_FUZE")
        self.assertIsNotNone(res_fuze)

    def test_async_yolo_detector_controls(self):
        """测试 AsyncYOLODetector 线程安全的动态配置接口"""
        async_det = AsyncYOLODetector("vision/models/savunma_yolo26.pt", conf_threshold=0.30)
        
        # 验证类别与模型路径
        cnames = async_det.get_class_names()
        self.assertIn("BALISTIK_FUZE", cnames.values())
        
        # 动态修改类别与置信度
        async_det.set_target_class("F16")
        async_det.set_conf_threshold(0.45)
        
        # 动态切换模型至通用模型（若存在）或重新加载
        success = async_det.set_model("vision/models/savunma_yolo26.pt")
        self.assertTrue(success)
        
        async_det.close()

    def test_mode_panel_yolo_subpanel_and_signals(self):
        """测试 ModePanel 中 YOLO 设置控件、联动与信号"""
        panel = ModePanel()
        panel.show()
        
        # 验证初始状态下 YOLO 配置区域隐藏
        self.assertFalse(panel.yolo_settings_widget.isVisible())
        
        # 切换到 YOLO 模式，配置区域展开
        panel.set_mode("YOLO_TRACKING")
        self.assertTrue(panel.yolo_settings_widget.isVisible())

        
        # 验证模型下拉框包含 savunma 模型
        model_paths = [panel.combo_model.itemData(i) for i in range(panel.combo_model.count())]
        self.assertTrue(any("savunma" in str(p).lower() for p in model_paths))
        
        # 验证类别下拉框已加载国防目标 (支持英文标签及原始类别映射)
        classes_in_combo = [panel.combo_class.itemText(i) for i in range(panel.combo_class.count())]
        self.assertTrue(any("Ballistic" in c or "BALISTIK_FUZE" in c for c in classes_in_combo))
        self.assertTrue(any("F-16" in c or "F16" in c for c in classes_in_combo))
        self.assertTrue(any("Helicopter" in c or "HELIKOPTER" in c for c in classes_in_combo))
        self.assertTrue(any("UAV" in c or "Drone" in c or "MINI_IHA" in c for c in classes_in_combo))
        
        # 验证信号触发
        received_models = []
        received_classes = []
        received_confs = []
        
        panel.yolo_model_changed.connect(lambda m: received_models.append(m))
        panel.yolo_class_changed.connect(lambda c: received_classes.append(c))
        panel.yolo_conf_changed.connect(lambda f: received_confs.append(f))
        
        panel.combo_class.setCurrentIndex(1)
        self.assertGreaterEqual(len(received_classes), 1)
        
        panel.slider_conf.setValue(65)
        self.assertIn(0.65, received_confs)


    def test_error_processor_dynamic_lead_anticipation(self):
        """测试误差处理器动态超前预测（加速迅速跟手与靠拢提前制动）"""
        from core.control.error_processor import ErrorProcessor
        ep = ErrorProcessor()
        
        # 第一次采样
        x1, y1 = ep.process(20, 15)
        self.assertEqual(x1, 20)
        self.assertEqual(y1, 15)
        
        # 目标加速远离准星 (从 20 像素增加到 30 像素) -> 超前预测误差增大 (>=30)，瞬间爆发加速度跟手
        x2, y2 = ep.process(30, 15)
        self.assertGreaterEqual(x2, 30)
        
        # 目标快速靠近准星 (从 30 像素快速减小到 10 像素) -> 超前预测提前制动 (<10)，防止冲过头
        x3, y3 = ep.process(10, 15)
        self.assertLessEqual(x3, 10)



if __name__ == "__main__":
    unittest.main()

