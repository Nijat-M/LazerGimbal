import React from 'react';
import type { TelemetryData } from '../types/telemetry';
import { Activity, Gauge, Zap, Thermometer, Radio, Wifi, WifiOff, Target } from 'lucide-react';

interface TelemetryPanelProps {
  telemetry: TelemetryData;
  onConnectPort: (port: string) => void;
  onDisconnectPort: () => void;
}

export const TelemetryPanel: React.FC<TelemetryPanelProps> = ({
  telemetry,
  onConnectPort,
  onDisconnectPort,
}) => {
  const {
    connected,
    port,
    pitch,
    yaw,
    voltage_v = 12.4,
    temperature_c = 36.5,
    latency_ms,
    detections,
  } = telemetry;


  return (
    <div className="flex flex-col gap-3 w-full">
      {/* 1. Hardware Connection & State Card */}
      <div className="hud-panel rounded-xl p-4 tactical-corners flex flex-col gap-3">
        <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2.5">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-cyan-400" />
            <span className="font-mono text-xs font-bold tracking-wider text-cyan-300">
              STM32 // SERIAL TELEMETRY
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            {connected ? (
              <span className="flex items-center gap-1 text-[11px] font-mono text-green-400 bg-green-950/70 border border-green-500/40 px-2 py-0.5 rounded">
                <Wifi className="w-3 h-3" /> CONNECTED
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[11px] font-mono text-red-400 bg-red-950/70 border border-red-500/40 px-2 py-0.5 rounded">
                <WifiOff className="w-3 h-3" /> OFFLINE
              </span>
            )}
          </div>
        </div>

        {/* Port Status & Action */}
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-cyan-400">PORT / BAUDRATE:</span>
          <span className="text-cyan-200 font-bold">{port || 'COM3 / 115200'}</span>
        </div>

        <div className="grid grid-cols-2 gap-2 mt-1">
          <button
            onClick={() => onConnectPort(port || 'COM3')}
            disabled={connected}
            className={`py-1.5 px-3 rounded text-xs font-mono font-bold tracking-wider transition-all ${
              connected
                ? 'bg-cyan-950/30 text-cyan-700 border border-cyan-900 cursor-not-allowed'
                : 'bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-500/50 hover:border-cyan-400'
            }`}
          >
            CONNECT PORT
          </button>
          <button
            onClick={onDisconnectPort}
            disabled={!connected}
            className={`py-1.5 px-3 rounded text-xs font-mono font-bold tracking-wider transition-all ${
              !connected
                ? 'bg-red-950/20 text-red-800 border border-red-950 cursor-not-allowed'
                : 'bg-red-950/80 hover:bg-red-900 text-red-300 border border-red-500/50 hover:border-red-400'
            }`}
          >
            DISCONNECT
          </button>
        </div>
      </div>

      {/* 2. Gimbal Angle & Orientation Telemetry */}
      <div className="hud-panel rounded-xl p-4 tactical-corners flex flex-col gap-3">
        <div className="flex items-center gap-2 border-b border-cyan-500/20 pb-2.5">
          <Gauge className="w-4 h-4 text-cyan-400" />
          <span className="font-mono text-xs font-bold tracking-wider text-cyan-300">
            GIMBAL ATTITUDE TELEMETRY
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {/* Pitch Gauge */}
          <div className="bg-cyan-950/30 p-2.5 rounded-lg border border-cyan-500/20 flex flex-col gap-1">
            <div className="text-[10px] font-mono text-cyan-400 flex justify-between">
              <span>PITCH (ELEVATION)</span>
              <span>-45° / +45°</span>
            </div>
            <div className="text-xl font-bold font-mono text-white glow-cyan">
              {pitch.toFixed(1)}°
            </div>
            {/* Progress bar */}
            <div className="w-full bg-cyan-950/80 h-1.5 rounded overflow-hidden">
              <div
                className="bg-cyan-400 h-full transition-all duration-75"
                style={{ width: `${Math.max(0, Math.min(100, ((pitch + 45) / 90) * 100))}%` }}
              />
            </div>
          </div>

          {/* Yaw Gauge */}
          <div className="bg-cyan-950/30 p-2.5 rounded-lg border border-cyan-500/20 flex flex-col gap-1">
            <div className="text-[10px] font-mono text-cyan-400 flex justify-between">
              <span>YAW (AZIMUTH)</span>
              <span>-80° / +80°</span>
            </div>
            <div className="text-xl font-bold font-mono text-white glow-cyan">
              {yaw.toFixed(1)}°
            </div>
            {/* Progress bar */}
            <div className="w-full bg-cyan-950/80 h-1.5 rounded overflow-hidden">
              <div
                className="bg-cyan-400 h-full transition-all duration-75"
                style={{ width: `${Math.max(0, Math.min(100, ((yaw + 80) / 160) * 100))}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 3. Power & Environmental Sensors */}
      <div className="hud-panel rounded-xl p-4 tactical-corners flex flex-col gap-3">
        <div className="flex items-center gap-2 border-b border-cyan-500/20 pb-2.5">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="font-mono text-xs font-bold tracking-wider text-cyan-300">
            SYSTEM VITALS & HEALTH
          </span>
        </div>

        <div className="grid grid-cols-3 gap-2 text-xs font-mono">
          <div className="bg-cyan-950/30 p-2 rounded border border-cyan-500/20 flex flex-col items-center">
            <Zap className="w-3.5 h-3.5 text-amber-400 mb-1" />
            <span className="text-[10px] text-cyan-400">BUS VOLT</span>
            <span className="text-sm font-bold text-white">{voltage_v.toFixed(1)} V</span>
          </div>

          <div className="bg-cyan-950/30 p-2 rounded border border-cyan-500/20 flex flex-col items-center">
            <Thermometer className="w-3.5 h-3.5 text-cyan-400 mb-1" />
            <span className="text-[10px] text-cyan-400">CORE TEMP</span>
            <span className="text-sm font-bold text-white">{temperature_c.toFixed(1)} °C</span>
          </div>

          <div className="bg-cyan-950/30 p-2 rounded border border-cyan-500/20 flex flex-col items-center">
            <Activity className="w-3.5 h-3.5 text-green-400 mb-1" />
            <span className="text-[10px] text-cyan-400">LATENCY</span>
            <span className="text-sm font-bold text-white">{latency_ms.toFixed(0)} ms</span>
          </div>
        </div>
      </div>

      {/* 4. Target Acquisition Status */}
      <div className="hud-panel rounded-xl p-4 tactical-corners flex flex-col gap-2">
        <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-cyan-400" />
            <span className="font-mono text-xs font-bold tracking-wider text-cyan-300">
              TARGET INTELLIGENCE
            </span>
          </div>
          <span className="text-[11px] font-mono text-cyan-400">
            DETECTED: <b className="text-white">{detections?.length || 0}</b>
          </span>
        </div>

        {detections && detections.length > 0 ? (
          <div className="flex flex-col gap-1.5 max-h-28 overflow-y-auto">
            {detections.map((det, idx) => (
              <div
                key={idx}
                className={`p-2 rounded flex items-center justify-between text-xs font-mono border ${
                  det.is_locked
                    ? 'bg-red-950/40 border-red-500/50 text-red-300'
                    : 'bg-cyan-950/30 border-cyan-500/20 text-cyan-200'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${det.is_locked ? 'bg-red-400 animate-ping' : 'bg-cyan-400'}`} />
                  <span className="font-bold">{det.label.toUpperCase()}</span>
                </div>
                <span>CONF: {Math.round(det.confidence * 100)}%</span>
                {det.is_locked && <span className="font-bold text-red-400 animate-pulse">LOCKED</span>}
              </div>
            ))}
          </div>
        ) : (
          <div className="py-3 text-center text-xs font-mono text-cyan-600">
            NO ACTIVE TARGETS IN SIGHT
          </div>
        )}
      </div>
    </div>
  );
};
