# -*- coding: utf-8 -*-
"""
云台追踪核心调参配置单 (Gimbal Tracking Parameters & Tuning Profiles)
====================================================================
此文件集中汇总保存了当前优化调优后的全部追踪控制与视觉算法参数。
包含：
  1. 运动学三级速度规划 (3-Zone Kinematic Servoing Profile)
  2. 非对称超前预测与果冻效应抑制 (Phase-Lead Anticipation & Anti-Jello)
  3. 下位机 PID 与闭环死区控制 (Closed-Loop PID & Deadzone)
  4. YOLO 深度学习目标检测与追踪锁定 (YOLO Model & Target Locking)
  5. 蓝色物体/颜色形态学追踪 (Color Morphology Tracking)
  6. 下位机 STM32 固件运动学参考 (STM32 Firmware Kinematics)

使用说明：
  - 代码中可直接导入此类：from config.tracking_parameters import TrackingParameters
  - 支持导出/导入 JSON 配置文件进行保存与快速加载
"""

import json
import os
from typing import Dict, Any


class TrackingParameters:
    """
    云台全系统追踪参数集合（当前调优最优基线）
    """

    # =========================================================================
    # 1. 运动学三级速度规划与防过冲 (3-Zone Kinematic Servoing Profile)
    # =========================================================================
    # 上位机控制循环调度频率 (Hz)，与相机 60 FPS 满速硬件同步
    CONTROL_LOOP_HZ: float = 60.0

    # X / Y 轴误差比例系数（将像素误差转换为下位机速度期望）
    TRACKING_SCALE_X: float = 1.20       # X 轴水平追踪增益 (配合下位机直接速度闭环)
    TRACKING_SCALE_Y: float = 0.45       # Y 轴俯仰追踪增益 (柔和防点头)

    # 单控制周期最大输出误差限幅 (Max Error Output Clamp)
    # 限制最高追踪转速在安全制动包线内 (~210°/s)，彻底杜绝远距离大速度过冲与飞车甩脱
    TRACKING_MAX_ERROR_X: int = 120
    TRACKING_MAX_ERROR_Y: int = 50

    # 准星过渡区半径 (Settle Zone Radius, 像素)
    # 进入此区域后启动渐进平滑刹车，使目标平稳贴合十字准心
    SETTLE_ZONE_X: int = 45              # X 轴准星减速过渡区 (px)
    SETTLE_ZONE_Y: int = 25              # Y 轴准星减速过渡区 (px)
    SETTLE_FACTOR_BASE: float = 0.50     # 准星过渡区起始基础增益 (0.50 + 0.50 * dist/settle_zone)

    # 屏幕边缘软饱和压缩起点 (Edge Soft-Saturation Threshold, 像素)
    # 目标超出此像素距离时，启动亚线性幂压缩，防止边缘超速失控
    EDGE_COMPRESS_THRESHOLD_X: int = 100
    EDGE_COMPRESS_THRESHOLD_Y: int = 100
    EDGE_COMPRESS_EXPONENT: float = 0.55 # 亚线性压缩指数
    EDGE_COMPRESS_MULTIPLIER: float = 1.20 # 压缩缩放系数

    # 轴向符号反转 (视觉坐标系 -> 机械坐标系)
    INVERT_X: bool = False               # X 轴默认不反转 (目标在右(+), 云台向右转(+))
    INVERT_Y: bool = True                # Y 轴取反 (图像坐标向下为(+), 云台抬头需向正向转)


    # =========================================================================
    # 2. 非对称超前预测与果冻效应抑制 (Phase-Lead Anticipation & Anti-Jello)
    # =========================================================================
    # 导数死区门限 (Noise Gate Threshold, 像素)
    # 变化量小于此值时判定为传感器离散跳动，瞬时速度直接置 0，彻底切断高频微震与果冻效应！
    NOISE_GATE_THRESHOLD: float = 1.2

    # 速度估计低通滤波平滑系数 (EMA Alpha)
    VELOCITY_FILTER_ALPHA_X: float = 0.55
    VELOCITY_FILTER_ALPHA_Y: float = 0.35 # Y 轴加重滤波，消除俯仰共振

    # 非对称超前补偿时间 (Lead Time, 秒)
    # 用于消除视觉回路 ~45ms 固有延迟
    LEAD_TIME_BRAKE_X: float = 0.065     # X 轴急刹阶段超前时间 (65ms, 远距离提前收油)
    LEAD_TIME_ACCEL_X: float = 0.035     # X 轴追击阶段超前时间 (35ms, 离开准星即刻响应)
    LEAD_TIME_BRAKE_Y: float = 0.055     # Y 轴急刹阶段超前时间 (55ms)
    LEAD_TIME_ACCEL_Y: float = 0.025     # Y 轴追击阶段超前时间 (25ms)

    # 单帧最大像素跳变安全拦截门限
    MAX_PIXEL_JUMP_X: int = 350
    MAX_PIXEL_JUMP_Y: int = 120


    # =========================================================================
    # 3. PID 与死区控制参数 (PID & Deadzone Parameters)
    # =========================================================================
    KP: float = 0.60                     # 比例增益 (敏捷跟手，响应极速)
    KI: float = 0.16                     # 积分增益 (消除稳态微小残余静差)
    KD: float = 0.50                     # 微分增益 (阻尼平滑，抑制振荡)
    DEADZONE: int = 5                    # 像素死区 (进入 +/-5 像素内强制认定到达中心)
    VISION_WATCHDOG_TIMEOUT: float = 0.25 # 视觉看门狗超时时间 (秒, 250ms未收到坐标自动急停)


    # =========================================================================
    # 4. YOLO 深度学习目标检测与追踪参数 (YOLO Detection & Tracking)
    # =========================================================================
    DEFAULT_YOLO_MODEL: str = "vision/models/savunma_yolo26.pt"
    YOLO_CONF_THRESHOLD: float = 0.50    # 默认置信度阈值 (0.50 有效过滤室内杂波误报)
    YOLO_IOU_THRESHOLD: float = 0.45     # NMS 非极大值抑制 IoU 阈值
    YOLO_MAX_DETECTIONS: int = 20        # 单帧最多保留检测目标数
    YOLO_MIN_BOX_SIZE: int = 16          # 最小目标边长 (过滤过小碎片噪点)
    YOLO_MIN_BOX_AREA: int = 256         # 最小目标包围框面积 (px^2)
    YOLO_DEFENSE_IMGSZ: int = 960        # 国防防空模型原生训练分辨率
    YOLO_STANDARD_IMGSZ: int = 640       # 通用 COCO 模型推理分辨率
    YOLO_LOCK_DISTANCE_THRESHOLD: int = 180 # 连续追踪目标最大跳变锁定阈值 (像素)
    YOLO_MAX_LOST_FRAMES: int = 10       # 目标丢失判定最大容忍连续丢失帧数


    # =========================================================================
    # 5. 颜色 / 蓝色物体追踪参数 (Color / Blue Object Tracking)
    # =========================================================================
    HSV_BLUE_LOWER = (100, 120, 50)      # 蓝色 HSV 识别下限
    HSV_BLUE_UPPER = (135, 255, 255)     # 蓝色 HSV 识别上限
    MIN_CONTOUR_AREA: float = 300.0      # 最小有效目标连通域面积
    MORPHOLOGY_KERNEL_SIZE: int = 5      # 开闭运算形态学去噪核大小
    PYRAMID_DOWNSCALE_WIDTH: int = 640   # 工业相机金字塔下采样加速基准宽度


    # =========================================================================
    # 6. 下位机 STM32 固件对应参数 (STM32 Firmware Reference)
    # =========================================================================
    STM32_STEP_TIMER_HZ: float = 10000.0 # 定时器 TIM2 调度频率 (10kHz)
    STM32_PID_CONTROL_HZ: float = 50.0   # 下位机 PID 解算频率 (50Hz)
    STM32_MAX_STEP_RATE: float = 9000.0  # 步进电机极限转速上限 (steps/s)
    STM32_MAX_STEP_ACCEL: float = 10000.0# 步进电机最大加速度 (steps/s^2)
    STM32_FRICTION_BREAKAWAY_X: float = 120.0 # X 轴静摩擦起步前馈
    STM32_RATE_SCALE_X: float = 55.0     # X 轴速度增益乘数
    STM32_RATE_SCALE_Y: float = 18.0     # Y 轴速度增益乘数
    STM32_D_GAIN_NEAR_X: float = 160.0   # 准星近距离重度微分阻尼增益
    STM32_D_GAIN_FAR_X: float = 25.0     # 远距离轻度微分阻尼增益


    # =========================================================================
    # 实用工具方法 (Serialization & Management)
    # =========================================================================
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """导出为易读字典"""
        params = {}
        for k, v in cls.__dict__.items():
            if not k.startswith("_") and not callable(v) and not isinstance(v, classmethod):
                params[k] = v
        return params

    @classmethod
    def save_to_json(cls, file_path: str = "config/tracking_parameters.json") -> bool:
        """保存当前参数为 JSON 格式文件"""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(cls.to_dict(), f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] 保存追踪参数失败: {e}")
            return False

    @classmethod
    def load_from_json(cls, file_path: str = "config/tracking_parameters.json") -> bool:
        """从 JSON 配置文件快速恢复参数"""
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(cls, k):
                    setattr(cls, k, v)
            return True
        except Exception as e:
            print(f"[ERROR] 加载追踪参数失败: {e}")
            return False


if __name__ == "__main__":
    # 执行本脚本自动导出 JSON 参数镜像
    saved = TrackingParameters.save_to_json()
    print(f"追踪参数镜像文件已生成: {saved}")
