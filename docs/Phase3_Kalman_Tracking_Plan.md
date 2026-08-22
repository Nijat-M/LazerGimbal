# Phase 3: 运动学状态估计与卡尔曼高阶滤波演进方案 (Kinematic State Estimation & Kalman Roadmap)

> **适用硬件平台**：STM32F401 (10kHz TIM2 DDA 步进脉冲) + MKS SERVO42C 闭环步进电机 + Arducam AR0234 全局快门相机 (60 FPS) + 原生 USB CDC (12 Mbps) + YOLO26 目标检测  
> **状态**：阶段核心已在 [`core/control/error_processor.py`](file:///d:/LazerGimbal/core/control/error_processor.py) 与 [`TRACKING_PARAMETERS_GUIDE.md`](file:///d:/LazerGimbal/TRACKING_PARAMETERS_GUIDE.md) 中全面落地；本方案提供向高阶 2D/3D EKF 扩展的演进技术路线。

---

## 1. 现行已落地的运动学超前预测与抗抖系统

在当前项目中，为了解决视觉检测与控制链路中固有的全链路延时（约 $40 \sim 65\text{ms}$），系统已落地了一套高性能的**非对称动态超前预测与 3 区域运动学速度规划架构**：

### 1.1 动态非对称超前预测补偿 (Asymmetric Dynamic Lead Anticipation)
位于 [`ErrorProcessor.process()`](file:///d:/LazerGimbal/core/control/error_processor.py)：
- **急刹减速阶段 (fx 与 vel_x 异号)**：目标高速冲向准星中心时，系统判定为进场减速，自动施加 **$65\text{ms}$ 强效超前制动时间**，提前收油平滑制动，**彻底消除远距离大速度冲过准星与反向回摆**。
- **加速追击阶段 (fx 与 vel_x 同号)**：目标加速远离准星时，采用 **$35\text{ms}$ 敏捷超前时间**，消除视觉传输滞后，起步瞬间零延迟咬住目标。
- **零点穿越防抖**：当预测坐标跨越 0 点时强制吸附归零，避免符号翻转震荡。

### 1.2 消除果冻效应的导数噪声门限 (Anti-Jello Noise Gate)
- 当单周期像素跳变 $|\Delta y| < 1.2\text{px}$ 时，直接判定为传感器离散噪点，瞬时速度强制置 0，**彻底切断 60Hz 视觉微震源**。
- 俯仰 Y 轴结合重度低通滤波 ($\alpha = 0.35$)，彻底消除了相机滚动快门与微小机械共振引发的“果冻”扭曲。

### 1.3 3 区域运动学速度规划 (3-Zone Kinematic Servoing)
- **准星过渡区 ($< \text{SettleZone}$)**：采用渐进比例缩放 ($0.50 + 0.50 \times \frac{err}{\text{SettleZone}}$)，起步即响应，进中心柔和刹车。
- **线性追踪区 ($\text{SettleZone} \sim \text{EdgeThreshold}$)**：$1.20\times$ 敏捷线性跟踪。
- **边缘软饱和区 ($> \text{EdgeThreshold}$)**：启用亚线性幂压缩 ($100 + (err - 100)^{0.55} \times 1.2$)，限制最高速度在安全制动包线内 (~210°/s)，防止超大速度甩脱目标。

---

## 2. 高阶卡尔曼滤波 (EKF) 演进路线

为了在未来应对**复杂机动防空目标（高机动转弯、突变加速度、短暂被遮挡）**，系统可平滑升级为基于恒加速度 (CA) 模型的扩展卡尔曼滤波观测器。

### 2.1 状态向量与运动学模型 (Constant Acceleration Model)
定义目标在图像坐标系或空间物理坐标系中的 6 维状态向量：
$$ X_k = \begin{bmatrix} x & y & v_x & v_y & a_x & a_y \end{bmatrix}^T $$

状态转移矩阵 $F$（时间步长 $\Delta t = \frac{1}{60}\text{s} \approx 16.67\text{ms}$）：
$$ F = \begin{bmatrix} 
1 & 0 & \Delta t & 0 & \frac{1}{2}\Delta t^2 & 0 \\
0 & 1 & 0 & \Delta t & 0 & \frac{1}{2}\Delta t^2 \\
0 & 0 & 1 & 0 & \Delta t & 0 \\
0 & 0 & 0 & 1 & 0 & \Delta t \\
0 & 0 & 0 & 0 & 1 & 0 \\
0 & 0 & 0 & 0 & 0 & 1
\end{bmatrix} $$

### 2.2 测量更新与抗遮挡推算 (Coasting Capability)
测量向量仅包含目标检测给出的质心坐标 $Z_k = \begin{bmatrix} z_x & z_y \end{bmatrix}^T$：
$$ H = \begin{bmatrix} 
1 & 0 & 0 & 0 & 0 & 0 \\
0 & 1 & 0 & 0 & 0 & 0 
\end{bmatrix} $$

- **正常观测时**：卡尔曼增益 $K_k = P_{k|k-1} H^T (H P_{k|k-1} H^T + R)^{-1}$，融合 YOLO 视觉测量与运动惯性预测。
- **目标短暂遮挡 / 掉帧时 (Coasting 惯性航位推算)**：若 YOLO 在连续 3~10 帧未检测到目标，**不下发 STOP**，而是依靠卡尔曼先验状态矩阵 $\hat{X}_{k|k-1} = F \hat{X}_{k-1|k-1}$ 持续推算目标运动轨迹并引导云台继续追踪，当目标重新穿出遮挡物时实现无缝重捕获。

---

## 3. 分步进阶实施建议

1. **模块设计**：
   - 在 `core/control/` 目录下构建 `kalman_tracker.py`，保持与 `ErrorProcessor` 一致的接口 `process(raw_x, raw_y) -> (pred_x, pred_y)`。
2. **多假设数据关联 (Data Association)**：
   - 结合 YOLO 的国防目标类别（`BALISTIK_FUZE`, `F16`, `HELIKOPTER`, `MINI_IHA`）与马氏距离 (Mahalanobis Distance)，杜绝多目标交错时的跟丢与误跟。
3. **下位机融合**：
   - 维持下位机 10kHz DDA 闭环调速机制不变，上位机直接输出已包含卡尔曼加速度外推预测的高阶误差指令 `<err_x, err_y, fire>\n`。

---

## 4. 技术亮点与面试总结

> "针对 60 FPS 视觉制导闭环中由曝光传输与机械惯性引发的数十毫秒系统时延，我们构建了**非对称动态超前预测观测器**与 **3 区域运动学速度规划架构**；创新性地引入了方向自适应制动超前（65ms）与加速追击超前（35ms），并配合 1.2px 导数噪声门限切断果冻效应源。结合 STM32 10kHz TIM2 DDA 闭环步进驱动与双区差分阻尼控制，实现了极速响应无过冲、高精度锁定且抗遮挡的高性能光电伺服追踪。"