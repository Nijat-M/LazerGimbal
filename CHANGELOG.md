# Changelog

<div align="right">
  🇬🇧 <a href="CHANGELOG.md">English</a> | 🇹🇷 <a href="CHANGELOG_TR.md">Türkçe</a>
</div>

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
