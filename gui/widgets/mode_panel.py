# -*- coding: utf-8 -*-
"""
模式选择面板 (Mode Selection Panel)

工作模式：待机、蓝色物体追踪、YOLO 目标追踪、按钮测试和 FPS 风格鼠标瞄准。
支持针对防空国防模型 (savunma_yolo26.pt) 与通用模型的动态热换、目标类别精准过滤与置信度调节。
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QRadioButton, 
    QButtonGroup, QMessageBox, QComboBox, QLabel, QSlider, QWidget
)
from PyQt6.QtCore import pyqtSignal, Qt

from config.vision_config import VisionConfig
from vision.yolo_detector import YOLODetector
from utils.logger import Logger

logger = Logger("ModePanel")


class ModePanel(QGroupBox):
    """模式选择面板"""
    
    # 信号
    mode_changed = pyqtSignal(str)
    yolo_model_changed = pyqtSignal(str)
    yolo_class_changed = pyqtSignal(object)  # None 或 int 类别ID
    yolo_conf_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__("Mode", parent)
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        
        # 按钮组
        self.mode_group = QButtonGroup(self)
        
        # 工作模式单选框
        self.rb_idle = QRadioButton("IDLE")
        self.rb_blue_tracking = QRadioButton("Blue Object Tracking")
        self.rb_yolo_tracking = QRadioButton("YOLO Defense Tracking")
        self.rb_test = QRadioButton("Test Mode")
        self.rb_mouse_manual = QRadioButton("Mouse Aim")
        
        self.rb_idle.setChecked(True)
        
        # 设置提示文本
        self.rb_blue_tracking.setToolTip("Center blue object")
        self.rb_yolo_tracking.setToolTip("Center defense & aerial targets using YOLO")
        self.rb_mouse_manual.setToolTip("Click live view to capture mouse for manual aiming")
        
        self.mode_group.addButton(self.rb_idle, 0)
        self.mode_group.addButton(self.rb_blue_tracking, 1)
        self.mode_group.addButton(self.rb_yolo_tracking, 2)
        self.mode_group.addButton(self.rb_test, 3)
        self.mode_group.addButton(self.rb_mouse_manual, 4)
        
        # 连接模式选择信号
        self.mode_group.idToggled.connect(self._on_mode_toggled)
        
        layout.addWidget(self.rb_idle)
        layout.addWidget(self.rb_blue_tracking)
        layout.addWidget(self.rb_yolo_tracking)
        
        # ==========================
        # YOLO 专属配置子面板 (动态模型与类别选择)
        # ==========================
        self.yolo_settings_widget = QWidget()
        yolo_layout = QVBoxLayout(self.yolo_settings_widget)
        yolo_layout.setContentsMargins(16, 2, 6, 6)
        yolo_layout.setSpacing(4)
        
        # 1. 模型选择
        model_h_layout = QHBoxLayout()
        model_label = QLabel("Model:")
        model_label.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        self.combo_model = QComboBox()
        self.combo_model.setStyleSheet("font-size: 11px; padding: 2px;")
        model_h_layout.addWidget(model_label)
        model_h_layout.addWidget(self.combo_model, 1)
        yolo_layout.addLayout(model_h_layout)
        
        # 2. 追踪目标类别过滤
        class_h_layout = QHBoxLayout()
        class_label = QLabel("Target:")
        class_label.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        self.combo_class = QComboBox()
        self.combo_class.setStyleSheet("font-size: 11px; padding: 2px;")
        class_h_layout.addWidget(class_label)
        class_h_layout.addWidget(self.combo_class, 1)
        yolo_layout.addLayout(class_h_layout)

        # 3. 置信度阈值微调
        conf_h_layout = QHBoxLayout()
        default_conf = getattr(VisionConfig, "YOLO_CONF_THRESHOLD", 0.50)
        self.label_conf = QLabel(f"Confidence: {default_conf:.2f}")
        self.label_conf.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        self.slider_conf = QSlider(Qt.Orientation.Horizontal)
        self.slider_conf.setRange(15, 95)
        self.slider_conf.setValue(int(default_conf * 100))
        self.slider_conf.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #555; border-radius: 2px; }
            QSlider::handle:horizontal { background: #00bcd4; width: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        conf_h_layout.addWidget(self.label_conf)
        conf_h_layout.addWidget(self.slider_conf, 1)
        yolo_layout.addLayout(conf_h_layout)

        
        layout.addWidget(self.yolo_settings_widget)
        self.yolo_settings_widget.setVisible(False)  # 默认待机模式下隐藏
        
        layout.addWidget(self.rb_test)
        layout.addWidget(self.rb_mouse_manual)
        
        # 初始化模型与类别列表
        self._populate_models()
        
        # 连接 YOLO 控件信号
        self.combo_model.currentIndexChanged.connect(self._on_model_changed)
        self.combo_class.currentIndexChanged.connect(self._on_class_changed)
        self.slider_conf.valueChanged.connect(self._on_conf_slider_changed)

    def _populate_models(self):
        """扫描并加载所有可用的 YOLO 模型"""
        self.combo_model.blockSignals(True)
        self.combo_model.clear()
        
        models = YOLODetector.list_available_models()
        default_model = getattr(VisionConfig, "DEFAULT_YOLO_MODEL", "vision/models/savunma_yolo26.pt")
        selected_idx = 0

        if models:
            for idx, m in enumerate(models):
                self.combo_model.addItem(m["display_name"], m["path"])
                if m["path"] == default_model or m["filename"] in default_model:
                    selected_idx = idx
        else:
            self.combo_model.addItem("savunma_yolo26.pt (Defense Model)", "vision/models/savunma_yolo26.pt")
            self.combo_model.addItem("yolo26n.pt (Standard COCO Model)", "vision/models/yolo26n.pt")

        self.combo_model.setCurrentIndex(selected_idx)
        self.combo_model.blockSignals(False)
        
        # 更新对应的类别列表
        self._update_classes_for_current_model()

    def _update_classes_for_current_model(self):
        """根据当前选中的模型动态更新类别下拉列表"""
        model_path = self.combo_model.currentData() or "vision/models/savunma_yolo26.pt"
        
        self.combo_class.blockSignals(True)
        self.combo_class.clear()
        self.combo_class.addItem("All Targets (Any Detection)", None)
        
        # 尝试读取该模型的 class names
        resolved = YOLODetector.resolve_model_path(model_path)
        class_dict = {}
        if resolved and ("savunma" in resolved.lower() or "yetenek" in resolved.lower()):
            class_dict = {
                0: "BALISTIK_FUZE",
                1: "F16",
                2: "HELIKOPTER",
                3: "MINI_IHA"
            }
        elif resolved and "yolo26n" in resolved.lower():
            class_dict = {
                0: "person",
                4: "airplane",
                2: "car",
                14: "bird"
            }
            
        for cid, cname in class_dict.items():
            display_name = VisionConfig.get_class_display_name(cname)
            self.combo_class.addItem(f"{display_name}", cid)
            
        self.combo_class.setCurrentIndex(0)
        self.combo_class.blockSignals(False)

    def _on_model_changed(self, index):
        """模型下拉框改变"""
        model_path = self.combo_model.currentData()
        if model_path:
            logger.info(f"[MODE PANEL] Selected YOLO Model: {model_path}")
            self._update_classes_for_current_model()
            self.yolo_model_changed.emit(model_path)
            self.yolo_class_changed.emit(None)

    def _on_class_changed(self, index):
        """目标类别下拉框改变"""
        target_class = self.combo_class.currentData()
        logger.info(f"[MODE PANEL] Selected YOLO Target Class: {target_class}")
        self.yolo_class_changed.emit(target_class)

    def _on_conf_slider_changed(self, value):
        """置信度阈值滑块改变"""
        conf = value / 100.0
        self.label_conf.setText(f"Confidence: {conf:.2f}")
        self.yolo_conf_changed.emit(conf)

    def _on_mode_toggled(self, btn_id, checked):
        """模式切换处理"""
        if not checked:
            return
        
        mode_map = {
            0: "IDLE",
            1: "BLUE_TRACKING",
            2: "YOLO_TRACKING",
            3: "TEST",
            4: "MANUAL_MOUSE",
        }
        mode = mode_map.get(btn_id, "IDLE")
        
        # 仅在 YOLO 模式下展开 YOLO 配置项
        self.yolo_settings_widget.setVisible(mode == "YOLO_TRACKING")
        
        # 手动模式需要确认
        if mode in ("TEST", "MANUAL_MOUSE"):
            mode_name = "Manual Mouse Aim" if mode == "MANUAL_MOUSE" else "Manual Test Mode"
            reply = QMessageBox.question(
                self,
                f"Confirm {mode_name}",
                f"Entering {mode_name} allows manual gimbal control.\n\n"
                "Please confirm:\n"
                "1. No obstacles around gimbal movement range\n"
                "2. Steppers soft limits verified\n"
                "3. Ready to press Esc to stop immediately\n\n"
                "Do you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                # 取消，回到待机模式
                self.rb_idle.setChecked(True)
                return
        
        # 发射信号
        self.mode_changed.emit(mode)
    
    def get_current_mode(self) -> str:
        """获取当前选中的模式字符串"""
        btn_id = self.mode_group.checkedId()
        mode_map = {
            0: "IDLE",
            1: "BLUE_TRACKING",
            2: "YOLO_TRACKING",
            3: "TEST",
            4: "MANUAL_MOUSE",
        }
        return mode_map.get(btn_id, "IDLE")

    def set_mode(self, mode: str):
        """通过代码切换当前选中的模式"""
        if mode == "BLUE_TRACKING":
            self.rb_blue_tracking.setChecked(True)
        elif mode == "YOLO_TRACKING":
            self.rb_yolo_tracking.setChecked(True)
        elif mode == "TEST":
            self.rb_test.setChecked(True)
        elif mode == "MANUAL_MOUSE":
            self.rb_mouse_manual.setChecked(True)
        else:
            self.rb_idle.setChecked(True)
        self.yolo_settings_widget.setVisible(mode == "YOLO_TRACKING")


