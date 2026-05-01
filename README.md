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
This project is an experimental 2-axis laser gimbal tracking system that operates through a combination of computer vision and a microcontroller. The system uses a PyQt6/Python-based desktop application to process camera feeds, detect targets (using either HSV color tracking or YOLO-based deep learning), and calculate position errors. These error coordinates are then sent over a high-speed serial connection to an STM32F401 microcontroller. 

On the hardware side, the STM32 runs a hardware-level Incremental PID algorithm to smoothly drive two MG996R servos, effectively keeping the camera centered on the target. The project features a user-friendly GUI for real-time monitoring, PID tuning, and manual testing.

*Note: This is just a small personal project for testing purposes. It can serve as a basic prototype for a future Teknofest project. In the future, the hardware will be upgraded with better motors, high-quality camera modules, stronger mechanical structures, and custom PCBs.*

## Demo Videos
- [V0.1.0 Laser Tracking Demo](https://www.youtube.com/shorts/czz0KMfvBXw) - Real-time laser tracking demonstration
- [V0.1.5 Laser Tracking Demo](https://www.youtube.com/watch?v=KGi6N0OxIrQ) - Real-time laser tracking demonstration PID test
- [V0.1.6 Manual Test Mode](https://www.youtube.com/shorts/dynt_BvkDTA) - Manual control and calibration

## Changelog
Please see [CHANGELOG.md](CHANGELOG.md) for a detailed history of updates and fixes.

## System Images

<div align="center">
  <img src="images/Camera_and_new_power%20suply.jpeg" width="400" alt="New Camera and Power System">
  <p><i>New External 720p USB Camera and Stable Power Module</i></p>
  
  <img src="images/Pan%20Tilt.jpeg" width="400" alt="Pan-Tilt Mechanism">
  <p><i>Pan-Tilt Servo Mechanism (MG996R)</i></p>
  
  <img src="images/GUI.png" width="600" alt="GUI Interface">
  <p><i>Control Interface - Real-time Status Monitoring & PID Tuning & Manual Test Panel</i></p>
</div>

## Core Features

### 👁️ Computer Vision (PC / Python)
- **Dual Tracking Modes**: Seamlessly switch between lightweight, high-performance HSV color tracking and Deep Learning-based object detection (YOLO26 `yolo26n.pt`).
- **Continuous Target Locking**: Center-distance data association algorithm (Euclidean distance threshold) ensures persistent lock-on against multiple targets in frame.
- **Multithreaded Processing**: Dedicated asynchronous threads for UI updates (`QTimer`), Camera parsing (`vision_worker`), and serial communication (`serial_thread`) to prevent UI freezes.
- **Clean Interface (PyQt6)**: Integrated status monitoring (FPS/Resolution), real-time PID tuning panel, Deadzone adjusters, and a comprehensive manual component test panel.

### ⚙️ Hardware Control (STM32 MCU / C)
- **Hardware Incremental PID**: The control algorithm is completely offloaded to the STM32, running at a native 50Hz hardware interrupt (`TIM2`). Uses Incremental PID to ensure mathematically stable velocity output and eliminate integral windup.
- **Zero-Latency Telemetry**: High-speed, unblocked serial pipeline continuously feeds target error directly into the microcontroller with minimal software smoothing, preventing delayed system reactions.
- **Hardware Safety Limits**: 
  - **Slew Rate Limiters** (`MAX_SERVO_DELTA`) actively protect the mechanical servos from gear-stripping during sudden high-error target jumps.
  - **Asynchronous Data Validation** (`new_data_flag`) to pause PID integral accumulation if visual telemetry is temporarily lost (Vision Signal Watchdog).
  - Software limits constraint the servos from physically over-driving (10~170 degrees).

## Future Roadmap (Road to Teknofest)
This current version serves as a functional prototype. To meet the rigorous demands of the Teknofest competition, the next stages of development will focus on:
- **Phase 3 (Predictive Tracking)**: Implementing a Kalman Filter for trajectory prediction to maintain target lock during momentary occlusions and handle noisy vision data.
- **Phase 4 (Hardware Upgrade & PCB Integration)**: Transitioning to higher-specification hardware. This includes upgrading to an industrial camera for better stability and frame rates, replacing mechanical RC servos with reliable stepper motors, and designing a custom PCB to integrate all scattered electronics into a single, compact control board.

## Hardware Requirements

### Electronics
- **Microcontroller**: STM32F401CCU6 (Blackpill)
- **Servos**: 2x MG996R High-Torque Servos
- **Capacitor**: 1000µF Electrolytic Capacitor (Power filtering for servos)
- **Camera**: External 720p USB Desktop Camera (Mounted on gimbal)
- **Power Supply**: 12V 2A DC Adapter
- **Step-Down Module**: XL4016 Buck Converter (Regulated to stable 6V for servos)
- **Serial Communication**: HC-05 Bluetooth or direct USB-TTL
- **Laser**: Red laser pointer (optional, for tracking demonstration)

### Power Supply
- **OLD**: 4x 1.5V Duracell AA Batteries (6V output)
- **NOW**: 12V DC Adapter + XL4016 Buck Converter (for stable voltage and current)

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
