# Changelog

<div align="right">
  🇬🇧 <a href="CHANGELOG.md">English</a> | 🇹🇷 <a href="CHANGELOG_TR.md">Türkçe</a>
</div>

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
