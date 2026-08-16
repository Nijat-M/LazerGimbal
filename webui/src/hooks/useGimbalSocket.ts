import { useEffect, useRef, useState, useCallback } from 'react';
import type { TelemetryData, SystemCommand } from '../types/telemetry';
import { soundManager } from '../utils/audioEffects';


const INITIAL_TELEMETRY: TelemetryData = {
  timestamp: Date.now(),
  connected: false,
  port: 'DISCONNECTED',
  pitch: 0.0,
  yaw: 0.0,
  roll: 0.0,
  error_x: 0,
  error_y: 0,
  tracking_mode: 'IDLE',
  laser_armed: false,
  laser_firing: false,
  laser_power: 100,
  fps: 0,
  latency_ms: 0,
  temperature_c: 36.5,
  voltage_v: 12.4,
  system_state: 'READY',
  detections: [],
  pid: {
    kp: 0.60,
    ki: 0.16,
    kd: 0.50,
  },
};

export function useGimbalSocket() {
  const [telemetry, setTelemetry] = useState<TelemetryData>(INITIAL_TELEMETRY);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [logs, setLogs] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const prevLockRef = useRef<boolean>(false);

  const addLog = useCallback((msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [`[${timestamp}] ${msg}`, ...prev.slice(0, 49)]);
  }, []);

  const sendCommand = useCallback((cmd: SystemCommand) => {
    // 1. Instant Optimistic UI & Sound Synchronization (Zero Latency)
    if (cmd.action === 'FIRE_LASER') {
      setTelemetry((prev) => ({ ...prev, laser_firing: true }));
      soundManager.startLaserContinuousFire();
    } else if (cmd.action === 'STOP_LASER') {
      setTelemetry((prev) => ({ ...prev, laser_firing: false }));
      soundManager.stopLaserContinuousFire();
    } else if (cmd.action === 'ARM_LASER') {
      const isArmed = Boolean(cmd.payload?.armed);
      setTelemetry((prev) => ({
        ...prev,
        laser_armed: isArmed,
        laser_firing: isArmed ? prev.laser_firing : false,
      }));
      if (!isArmed) {
        soundManager.stopLaserContinuousFire();
      }
    } else if (cmd.action === 'EMERGENCY_STOP') {
      setTelemetry((prev) => ({ ...prev, laser_firing: false, laser_armed: false }));
      soundManager.stopLaserContinuousFire();
    }

    // 2. Transmit to backend WebSocket
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
      if (cmd.action !== 'FIRE_LASER' && cmd.action !== 'STOP_LASER') {
        soundManager.playClick();
      }
    } else {
      console.warn('WebSocket not connected. Command buffered or ignored:', cmd);
    }
  }, []);


  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // When developing with Vite proxy, ws://localhost:3000/ws/telemetry proxies to ws://localhost:8000/ws/telemetry
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

    try {
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setWsConnected(true);
        addLog('TELEMETRY LINK ESTABLISHED // SYSTEM ONLINE');
      };

      socket.onmessage = (event) => {
        try {
          const data: TelemetryData = JSON.parse(event.data);
          setTelemetry(data);

          // Trigger lock-on sound when transitioning to locked state
          const hasLockedTarget = data.system_state === 'LOCKED' || data.detections?.some((d) => d.is_locked);
          if (hasLockedTarget && !prevLockRef.current) {
            soundManager.playLockOn();
          }
          prevLockRef.current = hasLockedTarget;
        } catch (err) {
          console.error('Error parsing telemetry payload:', err);
        }
      };

      socket.onclose = () => {
        setWsConnected(false);
        addLog('TELEMETRY LINK LOST // ATTEMPTING RECONNECT...');
        // Try reconnecting after 2 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 2000);
      };

      socket.onerror = (err) => {
        console.warn('Telemetry WS Error:', err);
        socket.close();
      };
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 3000);
    }
  }, [addLog]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    telemetry,
    wsConnected,
    logs,
    sendCommand,
    addLog,
  };
}
