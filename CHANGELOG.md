# Changelog

<div align="right">
  🇬🇧 <a href="CHANGELOG.md">English</a> | 🇹🇷 <a href="CHANGELOG_TR.md">Türkçe</a>
</div>

### [v0.5.0] - 2026-08-20
- **Yetenek 6 Zero-Manual-Annotation 3MF Synthetic AI Dataset & Training Pipeline**:
  - Engineered an automated synthetic pipeline generating labeled datasets directly from official competition 3MF models (`Modeller.3mf`), eliminating manual bounding box labeling.
  - Implemented automated multi-angle target rendering with lighting variation and realistic hallway/room background compositing (`yetenek6/scripts/s0` ~ `s6`).
  - Added native multi-class air defense model training and inference support for 4 critical aerial targets: `F16` (Fighter Jet), `HELIKOPTER` (Attack Helicopter), `BALISTIK_FUZE` (Ballistic Missile), and `MINI_IHA` (Mini/Micro UAV) across 5m, 10m, and 15m competition ranges.
  - Deployed `yetenek6_best.pt` air-defense deep learning model with strict confidence threshold filtering and dynamic class discovery.
  - Built spatial-temporal target stabilizer (`yetenek6_stabilizer.py`) and anti-jitter filtering for thin missile and aircraft geometries.
- **Stage 3 Autonomous Air Defense Mission & IFF Separation (Çelikkubbe Competition)**:
  - Designed and deployed `Stage3MissionDirector` autonomous 6-state competition sequence: 1. Hostile Target Acquisition & Lock -> 2. Continuous Tracking & Laser Engagement -> 3. Post-Engagement Wait (10s) -> 4. Automated Emergency Stop (ESTOP) Trigger -> 5. Post-ESTOP Stabilization Delay (10s) -> 6. Safe System Shutdown.
  - Upgraded IFF (Identification Friend or Foe) chromatic engine (`vision/iff.py`) combining HSV, normalized BGR differential, and CIELAB chroma spaces, reliably distinguishing Red Hostile vs. Blue Friendly targets under yellow lighting and ambient reflections.
  - Implemented 100% Friendly Fire Interlock to strictly suppress laser firing whenever friendly blue targets enter the reticle zone.
  - Added Orange Balloon Hunt Mode (`BALLOON_HUNT`) with persistent lock-on and optical destruction verification.
- **Tactical HUD, PiP Reticle Scope & High-Fidelity Video Recording**:
  - Implemented synchronized Picture-in-Picture (PiP) tactical magnification scope with live crosshair alignment and real-time zoom controls (`[` / `]`).
  - Added Constant Frame Rate (CFR 30fps) `.mp4` video recording with wall-clock frame pacing, microphone ambient audio capture, and automated AAC audio-video muxing.
  - Introduced 3-speed motor gear selector (Keys `1`, `2`, `3` for Recon, Cruise, and Fast Slewing speeds).
  - Added dedicated manual D-Pad jog controls and live STM32 serial monitor logging.

### [v0.4.5] - 2026-08-16
- **Savunma YOLO26 Air-Defense Neural Model Adaptation & Tactical Defense HUD**:
  - Integrated `savunma_yolo26.pt` air-defense model with automatic model discovery and native **960×960 GPU inference** resolution.
  - Added target class filtering for 4 defense target classes (`BALISTIK_FUZE`, `F16`, `HELIKOPTER`, `MINI_IHA`) with dynamic class-consistent tracking.
  - Implemented tactical defense HUD overlays with threat-level color coding, crosshair lock-on percentage, and offset vectors.
  - Built Model Selection, Class Selection, and Confidence threshold tuning controls in `ModePanel`.
- **Zero-Lag Dynamic Lead Anticipation & Phase Compensator**:
  - Replaced legacy sluggish coordinate low-pass filters with a **Dynamic Phase-Lead Compensator** ($\tau_{\text{lead}} = 35\text{ms} \sim 65\text{ms}$), eliminating closed-loop phase lag and hunting oscillations.
  - Added predictive braking anticipation: automatically anticipates arrival when approaching the crosshair at high speed, achieving overshoot-free lock-on.
- **Y-Axis Rolling-Shutter Jello Effect Elimination**:
  - Introduced derivative noise-gating deadband (`|\Delta y| < 1.2\text{px} \implies \text{Vel} = 0`) to cut off 60Hz discrete sensor pixel noise from driving high-frequency pitch micro-vibrations.
  - Implemented heavy velocity low-pass smoothing on the pitch axis (`\alpha = 0.35`), completely eliminating CMOS rolling shutter jello distortion.
- **3-Zone Kinematic Servoing & Far-Distance Overshoot Elimination**:
  - Re-engineered full-field 3-zone motion profile: Settle Zone progressive deceleration ($0.50 \sim 1.00$), Linear Tracking Zone ($1.20\times$), and Edge Soft-Saturation Compression ($e_{\text{compressed}} = 100 + (e - 100)^{0.55} \times 1.2$).
  - Bounded maximum tracking output (`TRACKING_MAX_ERROR_X = 120`) within the safe braking envelope (~210°/s), eliminating extreme-distance runaway and reverse back-swinging.
- **Standalone Parameter Archive & Tuning Guide**:
  - Created centralized [`config/tracking_parameters.py`](file:///d:/LazerGimbal/config/tracking_parameters.py) and [`config/tracking_parameters.json`](file:///d:/LazerGimbal/config/tracking_parameters.json).
  - Authored comprehensive tuning guide [`TRACKING_PARAMETERS_GUIDE.md`](file:///d:/LazerGimbal/TRACKING_PARAMETERS_GUIDE.md) with parameter baseline references and physical formulas.

### [v0.4.4] - 2026-08-16

- **Industrial Visual Servo Closed-Loop Architecture & Adaptive Differential Braking**:
  - Re-engineered STM32 firmware motion control from legacy incremental PID to a high-speed **Position-to-Velocity Visual Servo** control law with active differential braking.
  - Implemented **Adaptive Dual-Zone Differential Damping**: applies low damping ($D=25.0f$) during high-speed chasing for zero-drag acceleration, and automatically engages heavy damping ($D=160.0f$) within the central 25px zone for instant, overshoot-free crosshair lock-on.
- **Dry Friction Breakaway Feedforward for Unbearinged Chassis**:
  - Added dynamic stiction compensation (`FRICTION_BREAKAWAY_RATE_X = 120.0f`) with linear center attenuation (<15px), eliminating start-up deadband sluggishness on pan axes without bearings while preventing slow-speed hunting/oscillation.
- **Hardware Performance Unleashed (9000 steps/s & 10000 steps/s²)**:
  - Boosted firmware speed limits to `MAX_STEP_RATE = 9000.0f` (~1000°/s) and `MAX_STEP_ACCEL = 10000.0f`, delivering ultra-responsive high-speed target tracking.
- **60 FPS Real-Time Control Pipeline Synchronization**:
  - Synchronized Python host control loop to **60.0 Hz** (`CONTROL_LOOP_HZ = 60.0`) matching the 60 FPS camera capture frequency.
  - Decoupled X/Y tracking scales and added Y-axis center damping and soft travel limits.

### [v0.4.2] - 2026-08-16
- **Complete Native USB CDC (12 Mbps) Migration & Bluetooth Deprecation**:
  - Successfully migrated STM32F401 hardware firmware from legacy Bluetooth UART (115.2 kbps) to **STM32 Native USB CDC Virtual COM Port (12 Mbps Full-Speed)**.
  - Re-engineered STM32 clock tree for exact **48.0 MHz USB clock** via 25MHz HSE ($PLLM=25, PLLN=336, PLLP=4, PLLQ=7$).
  - Integrated official ST USB Device Core & CDC class middlewares, implementing bidirectional microsecond-latency control streaming.
  - Thoroughly purged all legacy Bluetooth / USART1 firmware code (`usart.c`, `usart.h`, `HAL_UART` driver modules, and ISR handlers), completely freeing `PA9` and `PA10` pins on STM32 for future industrial expansion.
- **Intelligent GUI Hardware Recognition & Responsive Layout**:
  - Re-designed `SerialPanel` with card layout and automatic word-wrapping, eliminating text clipping across varying display scaling factors.
  - Added smart USB device identification matching STMicroelectronics USB CDC (VID: `0x0483`, PID: `0x5740`) with automatic port pre-selection and real-time connection state indicators.

### [v0.4.1] - 2026-08-16
- **Ultralytics YOLO26 NMS-Free Engine & CUDA 12.6 Hardware Acceleration**:
  - Fully integrated the latest **Ultralytics YOLO26** (`yolo26n.pt`) native end-to-end framework, completely eliminating NMS (Non-Maximum Suppression) post-processing overhead and target bounding jitter.
  - Activated NVIDIA CUDA 12.6 hardware acceleration with FP16 tensor core execution on RTX 3060, dropping inference latency down to ~30ms.
  - Thoroughly purged legacy YOLOv8 model remnants, unneeded checkpoints, and legacy code bloat.
- **Asynchronous Decoupled Visual Pipeline (`AsyncYOLODetector`)**:
  - Built an asynchronous double-buffered worker that decouples the main 60 FPS camera capture & UI rendering stream from background GPU neural inference.
  - Completely neutralized micro-stuttering and uneven frame-pacing across 1080p/720p/480p, delivering a perfectly smooth 60.0 FPS live feed while sustaining high-frequency target coordinate updates.
- **Arducam AR0234 Global Shutter Industrial Camera Adaptation**:
  - Fully integrated and optimized for Arducam AR0234 Global Shutter (Onsemi AR0234CS) high-speed cameras, eliminating motion blur and rolling-shutter jello distortion during rapid gimbal panning.
  - Enforced prioritized `CAP_PROP_FOURCC = 'MJPG'` DirectShow hardware compression negotiation to eliminate USB bandwidth bottlenecks.
  - Added dedicated DirectShow hardware settings trigger (`CAP_PROP_SETTINGS`), allowing microsecond-level manual Exposure Time, Gain, and White Balance tuning directly from the UI.
- **Pyramid Multi-Scale Detection Acceleration & Single-Pass Pipeline**:
  - Implemented real-time pyramid subsampling in `TargetDetector`: 1080p frames are downscaled on-the-fly for color segmentation and morphological filtering, reducing CPU latency from 18ms down to **~3.2ms (5.5x speedup)**.
  - Restored rock-solid **60.0 FPS** in active tracking modes (`BLUE_TRACKING` / `TRACKING`) with zero frame drops.
  - Preserved sub-pixel precision with automatic coordinate and bounding radius upscale mapping.
- **Instant Frame Orientation & Inverted-Mount Hot-Switching**:
  - Added zero-latency frame flipping (`Normal`, `180° Inverted (Upside-Down Mount)`, `Vertical Flip`, `Horizontal Mirror`) applied at the capture ingress before detection, keeping PID coordinate polarity 100% unified.
- **GUI Camera Panel Streamlining & Bug Fixes**:
  - Reorganized camera panel with clean dual-column button groupings (`Open/Close` & `Apply`, `Exposure/Gain Settings` & `Refresh Devices`).
  - Standardized resolution presets focused on the golden **60 FPS** gimbal tracking frequency (`640x480`, `1280x720`, `1920x1080`).
  - Fixed `AttributeError: 'ModePanel' object has no attribute 'get_current_mode'` on start control toggle.

### [v0.4.0] - 2026-08-16
- **MKS SERVO42C Closed-Loop Stepper Motor Upgrade**: Replaced legacy MG996R RC servos with high-precision NEMA 17 stepper motors and Makerbase MKS SERVO42C closed-loop vector FOC (`CR_vFOC`) drivers powered by 20V DC for ultra-high holding torque, anti-stall protection, and zero lost steps.
- **10kHz Hardware DDA Microstep Pulse Generator**: Rewrote STM32F401 firmware around a native 10kHz hardware timer interrupt (`TIM2`) with Bresenham / DDA real-time pulse interpolation, delivering whisper-quiet, ultra-smooth microstepping at 50Hz Incremental PID velocity loops.
- **5-Layer Industrial Safety & Fault Protection**:
  - Auto-healing exception handler (`HardFault_Handler` / `Error_Handler`) instantly clamps motor pins to 0V and self-resets (`NVIC_SystemReset()`) in 1ms against back-EMF / power surges.
  - 2.0-second hardware visual watchdog automatically engages braking and holding torque on telemetry disconnect.
  - Slew rate velocity limiter (`MAX_STEPS_PER_CYCLE = 80`) and physical UART coordinate clamping ($\pm 400\text{px}$) to prevent motor runaway.
  - 500ms non-blocking heartbeat LED (`PC13`) for visual proof of hardware health.
- **Enhanced Manual & Keyboard Control**:
  - Dual-mode manual control: Tap/short-press for crisp single-step jog, press-and-hold for smooth 40Hz continuous rotation with instant release braking.
  - Selectable Keyboard Control Mode with dedicated toggle switch for `WASD` / Arrow keys (`↑ / ↓ / ← / →`) with OS auto-repeat filtering.
  - Differentiated axis inertia compensation (X-axis base inertia boost vs Y-axis pitch precision).
- **Smart Tracking Control Linkage**: One-click "Start Control" button with automatic serial/camera readiness validation and seamless tracking mode engagement.

### [v0.3.7] - 2026-08-09

- **GUI & Control Refactor**: Updated PyQt6 interface components (Camera view, Camera panel, Serial panel) with improved stats display and control signals.
- **Gimbal Controller Stability**: Enhanced thread loop performance, refined watchdog mechanisms, and optimized telemetry handling.
- **Vision Model & Logging**: Integrated default YOLOv8 model weights (`yolov8n.pt`) alongside YOLO26 support, and standardized logging across vision worker threads.
- **Automated Launcher**: Added `run_app.bat` script for automated environment setup and dependency initialization.

### [v0.3.6] - 2026-03-19
- **YOLO26 Tracking Engine**: Upgraded computer vision architecture from YOLOv8 to the cutting-edge NMS-Free YOLO26 `yolo26n.pt` model, substantially reducing bounding-box jitter and latency.
- **Center-Distance Data Association**: Implemented Euclidean distance-based target locking (`150px` threshold) instead of naive highest-confidence selection, securing persistent lock-on across frames.
- **Zero-Latency Error Processor**: Stripped out legacy `deque` moving average software filters in favor of raw 0-delay error passthrough with a structural `.max_pixel_jump` safety clamp.
- **Multithreaded PID Concurrency**: Decoupled the `GimbalController` from the PyQt `QTimer` event loop into an independent async Thread running at a rigid 40Hz (`time.perf_counter()`), neutralizing UI freeze impact on PID derivates.
- **Serial Comm Unblocking**: Rewrote `serial_thread.py` to prevent `readline()` deadlocks, securing microsecond-level telemetry transmission without queue blockage.
- **STM32 Edge-Case Mitigations**: 
  - Deployed `new_data_flag` logic to prevent "Blind Integral Windup" on asynchronous telemetry loss.
  - Rectified "Derivative Kick" spikes by ensuring continuous error-state flow when exiting deadzones.
  - Integrated Slew Rate Limiters (`MAX_SERVO_DELTA`) to protect physical servos from gear-stripping snapbacks.

### [v0.3.5] - 2026-03-19
- **STM32 Incremental PID**: Reverted the mathematically explosive positional PID algorithm on the STM32 to a true Incremental PID system, ensuring stable and reliable motor velocity output.
- **UI Deadzone Tuning**: Added a dedicated Deadzone control slider to the PID tuning panel. This allows structural "hunting" oscillation across stationary targets (caused by low camera framerate/delays) to be software filtered out.
- **Architectural Cleanup**: Removed hardcoded scaling tables and obsolete logic (`CONTROL_DEADZONE_LEVELS`, `ERROR_SCALING`) from `error_processor` enabling pure linear tracking control.
- **Industrial Tracking Roadmaps**: Documented future upgrade pathways (Kalman Filter, ADRC, Kinematic Lead Calculation) towards a professional-grade continuous tracking structure.

### [v0.3.0] - 2026-03-13
- **YOLOv8 Object Tracking**: Added Deep Learning capability with Ultralytics YOLOv8. 
- **Multi-Target Detection**: System can now scan and highlight multiple objects in the frame simultaneously (Yellow boxes) while selecting and tracking the most confident target (Red Box with `[LOCKED]` label).
- **Dynamic Object Switching**: YOLO mode is configured to track any COCO dataset object dynamically, easily adaptable for specialized datasets (e.g., Drone tracking, Face tracking) by swapping the `.pt` models.
- **Dependency Loading Fix**: Resolved `WinError 1114` PyTorch CUDA runtime and PyQt6 DLL overlap issues ensuring smooth loading on Windows environments.

### [v0.2.0] - 2026-03-12
- **Power System Upgrade**: Integrated a 12V DC Adapter with an XL4016 Buck Converter to provide a dedicated, stable 6V power supply for the gimbal servos.
- **Framework Refactor & Bug Fixes**: Comprehensive codebase restructuring and resolution of several critical issues, including:
    - Fixed instability in serial communication for more reliable hardware commands.
    - Improved consistency of visual tracking for better target lock.
    - Stabilized PID control logic for significantly smoother movements.
    - Overhauled Graphical User Interface (GUI) for a more modern and intuitive aesthetic.
    - Enhanced step size and deadzone algorithms to increase tracking speed and responsiveness.
