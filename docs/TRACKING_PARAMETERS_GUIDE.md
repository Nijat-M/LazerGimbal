# 云台全系统追踪参数速查与调试手册 (Tracking Parameters & Tuning Guide)

> **版本**：v2.4.0 调优基线  
> **参数配置文件**：[`config/tracking_parameters.py`](file:///d:/LazerGimbal/config/tracking_parameters.py) 与 [`config/tracking_parameters.json`](file:///d:/LazerGimbal/config/tracking_parameters.json)

---

## 1. 运动学三级速度规划与防过冲参数 (3-Zone Kinematic Servoing)

| 参数名 | 推荐基线值 | 单位 | 说明与调试经验 |
| :--- | :---: | :---: | :--- |
| `CONTROL_LOOP_HZ` | `60.0` | Hz | 上位机控制循环频率，与 60 FPS 工业相机硬件曝光完全对齐。 |
| `TRACKING_SCALE_X` | `1.20` | - | X 轴（偏航轴）误差增益。调大响应更快，调过大易震颤。 |
| `TRACKING_SCALE_Y` | `0.45` | - | Y 轴（俯仰轴）误差增益。由于俯仰负载轻且易点头，取 0.40~0.50 最稳。 |
| `TRACKING_MAX_ERROR_X` | `120` | px | X 轴单周期最大输出限幅。限制最高速度在安全制动包线内 (~210°/s)，**彻底杜绝远距离大速度冲过头与回摆**。 |
| `TRACKING_MAX_ERROR_Y` | `50` | px | Y 轴单周期最大输出限幅。防止超速打到机械限位。 |
| `SETTLE_ZONE_X` | `45` | px | X 轴准星减速过渡区。进入 45px 内启动平滑刹车，使目标平稳吸附十字准心。 |
| `SETTLE_ZONE_Y` | `25` | px | Y 轴准星减速过渡区。 |
| `SETTLE_FACTOR_BASE` | `0.50` | - | 准星区起始基础增益 ($0.50 + 0.50 \times \frac{err}{SettleZone}$)，起步立刻有动力，靠近死区柔和刹车。 |
| `EDGE_COMPRESS_THRESHOLD_X` | `100` | px | X 轴屏幕边缘软饱和压缩起点。目标超出 100px 时启动亚线性幂压缩，防止边缘飞车甩脱目标。 |
| `EDGE_COMPRESS_EXPONENT` | `0.55` | - | 亚线性压缩幂指数：$err_{\text{compressed}} = 100 + (err - 100)^{0.55} \times 1.2$。 |

---

## 2. 非对称超前预测与果冻效应消除参数 (Lead Anticipation & Anti-Jello)

| 参数名 | 推荐基线值 | 单位 | 说明与调试经验 |
| :--- | :---: | :---: | :--- |
| `NOISE_GATE_THRESHOLD` | `1.2` | px | **【消除果冻效应核心】** 导数噪声死区门限。坐标变化 $<1.2\text{px}$ 直接判定为传感器噪点，瞬时速度置 0，**彻底切断 60Hz 视觉微震源**。 |
| `VELOCITY_FILTER_ALPHA_Y` | `0.35` | - | Y 轴速度估计低通滤波系数。重度滤波消除俯仰高频微抖共振。 |
| `VELOCITY_FILTER_ALPHA_X` | `0.55` | - | X 轴速度估计低通滤波系数。 |
| `LEAD_TIME_BRAKE_X` | `0.065` | s (65ms) | **【远距离防过冲核心】** 高速向中心逼近时的超前刹车时间。根据进场速度提前 65ms 平滑收油，**杜绝冲过中心反向回摆**。 |
| `LEAD_TIME_ACCEL_X` | `0.035` | s (35ms) | 目标加速远离准星时的超前追击时间。消除 35ms 视觉滞后，起步瞬间咬住目标。 |
| `LEAD_TIME_BRAKE_Y` | `0.055` | s (55ms) | Y 轴急刹阶段超前时间。 |
| `LEAD_TIME_ACCEL_Y` | `0.025` | s (25ms) | Y 轴追击阶段超前时间。 |
| `MAX_PIXEL_JUMP_X` | `350` | px/frame | 单帧允许的最大跳变步长，防止跳变框导致云台瞬间抽搐。 |

---

## 3. 下位机闭环 PID 与死区控制 (Closed-Loop PID)

| 参数名 | 推荐基线值 | 单位 | 说明与调试经验 |
| :--- | :---: | :---: | :--- |
| `KP` | `0.60` | - | 比例系数。敏捷跟手，平稳无超调。 |
| `KI` | `0.16` | - | 积分系数。消除稳态静差。 |
| `KD` | `0.50` | - | 微分系数。高速阻尼，抑制中高频振荡。 |
| `DEADZONE` | `5` | px | 准星中心死区。误差在 $\pm 5\text{px}$ 内强制锁定为 0，防止电机频繁微动发热。 |
| `VISION_WATCHDOG_TIMEOUT` | `0.25` | s | 视觉看门狗。250ms 未收到新坐标自动平滑急停。 |

---

## 4. 深度学习 YOLO 识别与防误判参数 (YOLO Tracking)

| 参数名 | 推荐基线值 | 说明与调试经验 |
| :--- | :---: | :--- |
| `DEFAULT_YOLO_MODEL` | `savunma_yolo26.pt` | 国防防空模型（4类目标：BALISTIK_FUZE, F16, HELIKOPTER, MINI_IHA）。 |
| `YOLO_CONF_THRESHOLD` | `0.50` | 默认置信度。0.50 能有效阻隔室内杂乱背景与低置信度虚警。 |
| `YOLO_DEFENSE_IMGSZ` | `960` | 防空模型原生训练尺寸。在 GPU (CUDA) 下以 960 推理，小目标识别特征大幅增强。 |
| `YOLO_MIN_BOX_SIZE` | `16` px | 最小目标边长。过滤小于 16 像素的杂散噪点框。 |
| `YOLO_LOCK_DISTANCE_THRESHOLD` | `180` px | 连续追踪目标最大跳变锁定阈值，结合同类别优先逻辑防止脱锁乱跳。 |

---

## 5. 颜色 / 蓝色物体追踪参数 (Color Tracking)

| 参数名 | 推荐基线值 | 说明与调试经验 |
| :--- | :---: | :--- |
| `HSV_BLUE_LOWER` | `[100, 120, 50]` | 蓝色 HSV 识别下限。 |
| `HSV_BLUE_UPPER` | `[135, 255, 255]` | 蓝色 HSV 识别上限。 |
| `MIN_CONTOUR_AREA` | `300.0` px | 最小有效蓝色目标轮廓面积。 |
| `PYRAMID_DOWNSCALE_WIDTH` | `640` px | 金字塔下采样基准宽度。将 1080p 图像耗时由 18ms 压缩至 1.5ms，释放 60~120 FPS 高帧率潜能。 |

---

## 6. 下位机 STM32 固件对应参数 (STM32 Firmware Reference)

| 固件宏定义 | 推荐值 | 说明 |
| :--- | :---: | :--- |
| `STEP_TIMER_HZ` | `10000.0` Hz | TIM2 步进脉冲调度时基 (10kHz DDA)。 |
| `PID_CONTROL_HZ` | `50.0` Hz | 固件 PID 解算频率。 |
| `MAX_STEP_ACCEL` | `10000.0` steps/s² | 步进电机最大加速度（实现毫秒级起步与强力制动）。 |
| `FRICTION_BREAKAWAY_RATE_X` | `120.0` steps/s | X 轴克服静摩擦起步前馈，在准星中心 15px 内平滑衰减至 0。 |
| `d_gain_x (近距离 / 远距离)` | `160.0` / `25.0` | 近距离强效定点急刹，远距离快速跟手。 |

---

## 7. 如何在代码中加载或备份参数？

```python
from config.tracking_parameters import TrackingParameters

# 1. 导出当前参数为 JSON 备份
TrackingParameters.save_to_json("config/my_tuning_backup.json")

# 2. 从 JSON 恢复参数
TrackingParameters.load_from_json("config/my_tuning_backup.json")

# 3. 实时读取参数
max_err = TrackingParameters.TRACKING_MAX_ERROR_X
print(f"当前 X 轴最大误差限幅: {max_err}")
```
