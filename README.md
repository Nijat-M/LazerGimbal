# Laser Gimbal Pro

A 2-axis laser gimbal tracking system using OpenCV and STM32.

## Overview
This project implements a computer vision-based tracking system that controls a 2-axis servo gimbal to follow a target (Red Laser or Blue Object). It uses a PID controller for smooth movement and includes a manual test mode for calibration.

## Features
- **Visual Tracking**: Real-time tracking of Red (Laser) or Blue objects using HSV color space.
- **PID Control**: Custom PID algorithm (`core/pid.py`) for smooth and accurate servo positioning.
- **Manual Test Mode**: Keyboard and UI controls to manually move the gimbal for testing and calibration.
- **Safety Mechanisms**:
  - Software Limits (0-180 degrees)
  - Vision Signal Watchdog (Stops if target lost > 1s)
  - Movement Deadzone (Prevents jitter)
- **Architecture**: Multi-threaded design separating Vision (OpenCV), GUI (PyQt6), and Serial Communication.

## Hardware Requirements
- **Microcontroller**: STM32F401 
- **Actuators**: 2x SG90/MG90S Servos (Pan/Tilt)
- **Camera**: USB Webcam (ID 0)
- **Laser**: Red laser pointer (optional, for tracking)

## Software Requirements
- Python 3.x
- Dependencies: `PyQt6`, `opencv-python`, `numpy`, `pyserial`, `qdarktheme`

## installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
1. Connect the STM32 board via USB.
2. Run the application:
   ```bash
   python main.py
   ```
3. **Connect**: Select the correct COM port and click "Connect".
4. **Tracking**:
   - Select "Tracking" mode.
   - Click "Start Control" to enable servo movement.
   - Toggle "Target Color" (Red/Blue) as needed.
5. **Testing**:
   - Select "Test Mode" to manually move the gimbal using Arrow Keys or UI buttons.
   - **Note**: Ensure the gimbal has free range of motion before testing.

## configuration
- config.py: Contains global settings (PID constants, Color Thresholds, Serial Port).
- Calibration:
  - `SERVO_SOFTWARE_STEP_SCALE`: Adjusts the ratio between software steps and physical degrees (Default: 0.1).

## License
[MIT License](LICENSE)
