# Laser Gimbal Pro

<div align="left">
  <img src="https://img.shields.io/badge/Language-Python%20%7C%20C-blue">
  <img src="https://img.shields.io/badge/GUI-PyQt6-green">
  <img src="https://img.shields.io/badge/Vision-OpenCV%20%7C%20YOLO-orange">
  <img src="https://img.shields.io/badge/Hardware-STM32F401-lightgrey">
</div>

<br>

<div align="right">
  🇬🇧 <a href="README.md">English</a> | 🇹🇷 <a href="README_TR.md">Türkçe</a>
</div>

A 2-axis laser gimbal tracking system combining desktop computer vision with real-time microcontroller hardware execution.

## Overview
This project is an experimental 2-axis laser gimbal tracking system that operates through a combination of computer vision and a real-time microcontroller. The system uses a PyQt6/Python-based desktop application to process camera feeds, detect targets (using either HSV color tracking or YOLO-based deep learning), and calculate position errors. These error coordinates are then sent over a high-speed serial connection (115200 baud) to an STM32F401 microcontroller.

On the hardware side, the STM32 runs a **10kHz hardware DDA (Digital Differential Analyzer) microstep pulse engine** alongside a **50Hz Incremental PID algorithm** to smoothly drive two **Makerbase MKS SERVO42C closed-loop stepper motors (`CR_vFOC`)**, effectively keeping the camera centered on the target with zero lost steps and high holding torque. The project features a modern PyQt6 GUI with real-time status monitoring, PID tuning, dual-mode manual control (tap-to-step & hold-to-spin), and dedicated keyboard controls.

*Note: This is a prototype system developed towards Teknofest competitions and precision optical gimbal research.*

## Demo Videos
- [V0.1.0 Laser Tracking Demo](https://www.youtube.com/shorts/czz0KMfvBXw) - Real-time laser tracking demonstration
- [V0.1.5 Laser Tracking Demo](https://www.youtube.com/watch?v=KGi6N0OxIrQ) - Real-time laser tracking demonstration PID test
- [V0.1.6 Manual Test Mode](https://www.youtube.com/shorts/dynt_BvkDTA) - Manual control and calibration

## Changelog
Please see [CHANGELOG.md](CHANGELOG.md) for a detailed history of updates and fixes.

## Core Features

### 👁️ Computer Vision & Control GUI (PC / Python)
- **Arducam AR0234 Global Shutter Camera Support**: Fully adapted for high-speed industrial global shutter sensors (Onsemi AR0234CS), ensuring zero-distortion and jello-free visual tracking under aggressive gimbal accelerations.
- **Pyramid Multi-Scale Detection Acceleration**: Ultra-fast single-pass HSV segmentation and pyramid subsampling reduces 1080p algorithm latency to **~3.2ms**, delivering rock-solid **60 FPS** real-time tracking with zero frame drops.
- **Instant Frame Orientation Hot-Switching**: Built-in zero-latency support for 180° inverted ceiling/upside-down mounting and mirror flipping directly from the GUI.
- **Ultralytics YOLO26 NMS-Free Deep Learning**: Native end-to-end object detection engine powered by `yolo26n.pt` and NVIDIA CUDA 12.6 GPU acceleration, eliminating NMS post-processing delays and target bounding jitter.
- **Asynchronous Decoupled Detection Pipeline**: Fully decoupled double-buffered architecture separating 60 FPS video capture and UI rendering from GPU neural inference, completely eliminating micro-stuttering.
- **Dual Tracking Modes**: Seamlessly switch between lightweight, high-performance HSV color tracking and Deep Learning-based object detection (Ultralytics YOLO26 `yolo26n.pt`).
- **Continuous Target Locking**: Center-distance data association algorithm (Euclidean distance threshold) ensures persistent lock-on against multiple targets in frame.
- **Multithreaded Architecture**: Dedicated asynchronous threads for UI rendering (`QTimer`), Camera processing (`vision_worker`), and high-speed serial telemetry (`serial_thread`) preventing any UI freezes.
- **Enhanced Manual & Keyboard Controls**:
  - **Tap-to-Step**: Short clicks produce crisp, precise single-step adjustments.
  - **Press-and-Hold**: Continuous 40Hz smooth rotation with immediate deceleration braking upon release.
  - **Keyboard Mode Switch**: Dedicated toggle to enable/disable `WASD` and Arrow key (`↑ / ↓ / ← / →`) control with anti-repeat event handling.
- **One-Click Tracking Linkage**: Intelligent "Start Control" button validates serial and camera readiness and seamlessly activates target tracking.

### ⚙️ Real-Time Motion Control (STM32 MCU / C)
- **10kHz Hardware DDA Microstep Pulse Generator**: 100μs granularity Bresenham / DDA pulse distributor on `TIM2` hardware interrupt, delivering whisper-quiet, ultra-smooth microstepping (16 microsteps = 3200 pulses/rev).
- **50Hz Incremental PID Engine**: Computes velocity microstep deltas ($\Delta\text{Steps}$) every 20ms, natively immune to integral windup.
- **5-Layer Industrial Safety & Fault Protection**:
  1. **Surge Auto-Healing Reset**: Exception handlers (`HardFault_Handler` / `Error_Handler`) instantly clamp motor pins to 0V and trigger a 1ms auto-reboot (`NVIC_SystemReset()`) to recover from back-EMF or voltage transients.
  2. **Hardware Visual Watchdog**: 2.0-second timeout automatically halts pulses and locks motor shafts if telemetry is lost.
  3. **Velocity Slew Rate Limiter**: Maximum step limit (`MAX_STEPS_PER_CYCLE = 80`) mathematically prevents mechanical runaway.
  4. **UART Coordinate Clamping**: Input error bounded to $\pm 400\text{px}$ to shield against serial noise.
  5. **500ms Non-Blocking Heartbeat LED (`PC13`)**: Instant visual feedback of MCU execution status.

## Hardware Requirements

### Electronics
- **Microcontroller**: STM32F401CCU6 (Blackpill)
- **Motors & Drivers**: 2x NEMA 17 Stepper Motors with Makerbase MKS SERVO42C Closed-Loop Vector Driver Boards (`CR_vFOC` mode)
- **Camera**: Arducam AR0234 Global Shutter High-Speed USB Camera (1080p @ 60 FPS) / UVC Desktop Camera
- **Power Supply**: 20V DC 2A+ Power Supply (Motor power rail)
- **Logic Wiring**: Common Cathode configuration (`COM` and `GND` to STM32 GND; `PA0` X_STP, `PA4` X_DIR, `PA1` Y_STP, `PA5` Y_DIR)
- **Laser**: Red laser diode / pointer (optional, for tracking demonstration)

### Power Architecture
- **Motor Power**: 20V DC directly connected to driver board `V+` and `GND` terminals.
- **Logic Level**: 3.3V STM32 GPIO signal drive with common ground referencing.


### Mechanical Structure
- **3D Printed Pan-Tilt Mechanism**: [MakerWorld - Pan Tilt Servo Antenna Tracker MG996R](https://makerworld.com/en/models/973248-pan-tilt-servo-antenna-tracker-mg996r#profileId-945437)
- Designed for MG996R servos with robust mounting

### Circuit Schematic
<div align="center">
  <img src="images/Schematic.svg" width="700" alt="Circuit Schematic">
  <p><i>System Wiring Diagram - STM32F401, HC-05, MG996R Servos</i></p>
</div>

### Project Structure
```text
LazerGimbal/
├── config/                # Global configuration profiles
│   ├── control_config.py  # PID parameters, limits, and speed levels
│   ├── hardware_config.py # COM port and baud rate settings
│   └── vision_config.py   # HSV thresholds and camera resolution
├── core/                  # Core logic and hardware communication
│   ├── serial_thread.py   # Async high-speed serial communication worker
│   ├── gimbal_controller.py # 40Hz Control loop & safety watchdog
│   └── control/           
│       └── error_processor.py # Vision error interpretation & bounds
├── gui/                   # Graphical User Interface (PyQt6)
│   ├── main_window.py     # Main application window assembly
│   ├── test_panel.py      # Manual servo control panel
│   └── widgets/           # Modular UI components
│       ├── camera_view.py # Video feed display
│       ├── camera_panel.py# Camera/Resolution selection & Stats
│       ├── control_panel.py# Operation controls
│       ├── mode_panel.py  # Tracking mode toggle
│       ├── serial_panel.py# Serial connection UI
│       └── pid_tuner.py   # Real-time PID parameter slider
├── STM32F401/             # MCU Firmware (C/C++ HAL)
│   ├── Core/Src/main.c    # Hardware Incremental PID core & safety limits
│   └── Lazer_F401.ioc     # STM32CubeMX configuration
├── utils/                 # General utilities
│   ├── data_recorder.py   # Telemetry recording
│   └── logger.py          # Unified logging system
├── vision/                # Computer vision processing
│   ├── vision_worker.py   # Frame processing and object isolation
│   ├── detector.py        # Base interface
│   ├── yolo_detector.py   # Deep learning via YOLO26
│   └── models/            # Neural network weights (.pt)
├── images/                # Hardware and schematic documentation
├── CHANGELOG.md           # Externalized version history
├── main.py                # Main application entry point
└── requirements.txt       # Project dependencies
```

## Software Requirements
- Python 3.10+
- Dependencies: `PyQt6`, `opencv-python`, `numpy`, `pyserial`, `qdarktheme`

## Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/Nijat-M/LazerGimbal.git
   cd LazerGimbal
   ```

2. **Setup virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python main.py
   ```

## License
[MIT License](LICENSE)
