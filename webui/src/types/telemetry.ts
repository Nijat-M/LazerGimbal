export interface TargetDetection {
  id?: number;
  label: string;
  confidence: number;
  bbox: [number, number, number, number]; // [x, y, width, height]
  is_locked?: boolean;
  distance_m?: number;
}

export interface CameraDevice {
  id: number;
  name: string;
  resolution?: string;
  fps?: number;
  is_live: boolean;
  is_selected?: boolean;
}

export interface SerialPortInfo {
  device: string;
  description: string;
  is_stm32: boolean;
}

export interface TelemetryData {
  timestamp: number;
  connected: boolean;
  port: string;
  pitch: number; // degrees
  yaw: number;   // degrees
  roll?: number;
  error_x: number; // pixel error
  error_y: number;
  tracking_mode: 'IDLE' | 'MANUAL' | 'COLOR_TRACKING' | 'BLUE_TRACKING' | 'YOLO_TRACKING' | 'PATROL';
  laser_armed: boolean;
  laser_firing: boolean;
  laser_power: number; // 0-100%
  fps: number;
  target_fps?: number;
  resolution?: string;
  latency_ms: number;
  temperature_c?: number;
  voltage_v?: number;
  system_state: 'READY' | 'TRACKING' | 'LOCKED' | 'SEARCHING' | 'WARNING' | 'EMERGENCY_STOP';
  detections: TargetDetection[];
  camera_id?: number;
  is_camera_live?: boolean;
  flip_mode?: 'NONE' | '180' | 'V' | 'H';
  available_cameras?: CameraDevice[];
  available_ports?: SerialPortInfo[];
  pid: {
    kp: number;
    ki: number;
    kd: number;
  };
}

export interface SystemCommand {
  action:
    | 'SET_MODE'
    | 'MANUAL_JOG'
    | 'ARM_LASER'
    | 'FIRE_LASER'
    | 'STOP_LASER'
    | 'CENTER'
    | 'EMERGENCY_STOP'
    | 'UPDATE_PID'
    | 'CONNECT_SERIAL'
    | 'DISCONNECT_SERIAL'
    | 'SCAN_PORTS'
    | 'SET_CAMERA'
    | 'SET_RESOLUTION'
    | 'SET_FLIP_MODE'
    | 'SCAN_CAMERAS';
  payload?: any;
}
