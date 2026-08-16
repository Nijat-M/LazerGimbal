import React from 'react';
import type { SystemCommand } from '../types/telemetry';
import {
  Flame,
  Shield,
  ShieldOff,
  Crosshair,
  Octagon,
  RotateCcw,
  Sliders,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Eye,
  Bot,
  Play,
  Square,
} from 'lucide-react';
import { soundManager } from '../utils/audioEffects';

interface ControlCenterProps {
  trackingMode: string;
  laserArmed: boolean;
  laserFiring: boolean;
  onSendCommand: (cmd: SystemCommand) => void;
  onOpenPidModal: () => void;
}

export const ControlCenter: React.FC<ControlCenterProps> = ({
  trackingMode,
  laserArmed,
  laserFiring,
  onSendCommand,
  onOpenPidModal,
}) => {
  const toggleLaserArm = () => {
    onSendCommand({
      action: 'ARM_LASER',
      payload: { armed: !laserArmed },
    });
  };

  const handleLaserFirePress = () => {
    if (!laserArmed) return;
    onSendCommand({
      action: 'FIRE_LASER',
      payload: { firing: true },
    });
  };

  const handleLaserFireRelease = () => {
    if (!laserArmed) return;
    onSendCommand({
      action: 'STOP_LASER',
      payload: { firing: false },
    });
  };


  const setTrackingMode = (mode: string) => {
    onSendCommand({
      action: 'SET_MODE',
      payload: { mode },
    });
  };

  const handleManualJog = (axis: 'x' | 'y', dir: number) => {
    onSendCommand({
      action: 'MANUAL_JOG',
      payload: { axis, dir, step: 5 },
    });
  };

  const handleCenter = () => {
    onSendCommand({ action: 'CENTER' });
  };

  const handleEmergencyStop = () => {
    soundManager.playAlert();
    onSendCommand({ action: 'EMERGENCY_STOP' });
  };

  return (
    <div className="flex flex-col gap-3 w-full">
      {/* 1. Tactical Mode Selector Bar */}
      <div className="hud-panel rounded-xl p-3 tactical-corners flex flex-col gap-2">
        <div className="flex items-center justify-between border-b border-cyan-500/20 pb-1.5">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-cyan-400" />
            <span className="font-mono text-xs font-bold tracking-wider text-cyan-300">
              OPERATIONAL TRACKING MODE // ÇALIŞMA MODU
            </span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 bg-cyan-950/80 rounded border border-cyan-500/30 text-cyan-400">
            {trackingMode}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <button
            onClick={() => setTrackingMode('IDLE')}
            className={`py-2 px-2 rounded text-xs font-mono font-bold tracking-wider border transition-all flex items-center justify-center gap-1.5 ${
              trackingMode === 'IDLE'
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 glow-cyan'
                : 'bg-black/40 border-cyan-500/20 text-cyan-400 hover:bg-cyan-950/50'
            }`}
          >
            <Square className="w-3.5 h-3.5" /> IDLE (BOŞTA)
          </button>

          <button
            onClick={() => setTrackingMode('COLOR_TRACKING')}
            className={`py-2 px-2 rounded text-xs font-mono font-bold tracking-wider border transition-all flex items-center justify-center gap-1.5 ${
              trackingMode === 'COLOR_TRACKING' || trackingMode === 'BLUE_TRACKING'
                ? 'bg-blue-500/30 border-blue-400 text-blue-200 glow-cyan'
                : 'bg-black/40 border-cyan-500/20 text-cyan-400 hover:bg-cyan-950/50'
            }`}
          >
            <Crosshair className="w-3.5 h-3.5 text-blue-400" /> MAVİ HEDEF
          </button>

          <button
            onClick={() => setTrackingMode('YOLO_TRACKING')}
            className={`py-2 px-2 rounded text-xs font-mono font-bold tracking-wider border transition-all flex items-center justify-center gap-1.5 ${
              trackingMode === 'YOLO_TRACKING'
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 glow-cyan'
                : 'bg-black/40 border-cyan-500/20 text-cyan-400 hover:bg-cyan-950/50'
            }`}
          >
            <Eye className="w-3.5 h-3.5" /> YOLO AI
          </button>

          <button
            onClick={() => setTrackingMode('PATROL')}
            className={`py-2 px-2 rounded text-xs font-mono font-bold tracking-wider border transition-all flex items-center justify-center gap-1.5 ${
              trackingMode === 'PATROL'
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 glow-cyan'
                : 'bg-black/40 border-cyan-500/20 text-cyan-400 hover:bg-cyan-950/50'
            }`}
          >
            <Play className="w-3.5 h-3.5" /> DEVRİYE
          </button>
        </div>
      </div>

      {/* 2. Side-by-Side Weapon & Manual Jog Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Left: Laser Weapon Controls */}
        <div
          className={`rounded-xl p-3.5 tactical-corners flex flex-col justify-between gap-3 transition-colors ${
            laserArmed ? 'hud-panel-danger' : 'hud-panel'
          }`}
        >
          <div className="flex items-center justify-between border-b border-cyan-500/20 pb-1.5">
            <div className="flex items-center gap-2">
              <Flame className={`w-4 h-4 ${laserArmed ? 'text-red-400 animate-pulse' : 'text-cyan-400'}`} />
              <span className="font-mono text-xs font-bold tracking-wider text-cyan-300">
                LAZER SİLAH SİSTEMİ
              </span>
            </div>

            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded border font-bold ${
                laserArmed
                  ? 'bg-red-950 text-red-300 border-red-500'
                  : 'bg-cyan-950/80 text-cyan-400 border-cyan-500/30'
              }`}
            >
              {laserArmed ? 'ARMED' : 'SAFE'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {/* Arm Toggle Button */}
            <button
              onClick={toggleLaserArm}
              className={`py-2.5 px-2 rounded-lg text-xs font-mono font-bold tracking-wider border transition-all flex items-center justify-center gap-1.5 ${
                laserArmed
                  ? 'bg-amber-950/80 hover:bg-amber-900 border-amber-500 text-amber-300 glow-amber'
                  : 'bg-cyan-950/80 hover:bg-cyan-900 border-cyan-500/50 text-cyan-200'
              }`}
            >
              {laserArmed ? (
                <>
                  <ShieldOff className="w-4 h-4 text-amber-400" /> SİLAHI KAPAT
                </>
              ) : (
                <>
                  <Shield className="w-4 h-4 text-cyan-400" /> SİLAHI KUR (ARM)
                </>
              )}
            </button>

            {/* Fire Trigger Button */}
            <button
              onMouseDown={handleLaserFirePress}
              onMouseUp={handleLaserFireRelease}
              onMouseLeave={handleLaserFireRelease}
              onTouchStart={handleLaserFirePress}
              onTouchEnd={handleLaserFireRelease}
              onTouchCancel={handleLaserFireRelease}
              disabled={!laserArmed}
              className={`py-2.5 px-2 rounded-lg text-xs font-mono font-black tracking-wider border transition-all flex items-center justify-center gap-1.5 select-none ${
                !laserArmed
                  ? 'bg-red-950/20 border-red-950 text-red-800 cursor-not-allowed'
                  : laserFiring
                  ? 'bg-red-600 border-red-400 text-white shadow-[0_0_25px_rgba(255,0,0,0.9)] scale-95'
                  : 'bg-red-950 hover:bg-red-900 border-red-500 text-red-200 glow-red animate-pulse'
              }`}
            >
              <Flame className="w-4 h-4" />
              {laserFiring ? 'ATEŞLENİYOR...' : 'BASILI TUT (ATEŞ)'}
            </button>

          </div>
          <div className="text-[10px] font-mono text-cyan-600/90 text-center">
            İpucu: Boşluk (Space) tuşuna basılı tutarak da ateşleyebilirsiniz
          </div>
        </div>

        {/* Right: Manual Jog D-Pad & Alignment Actions */}
        <div className="hud-panel rounded-xl p-3.5 tactical-corners flex flex-col justify-between gap-2.5">
          <div className="flex items-center justify-between border-b border-cyan-500/20 pb-1.5">
            <div className="flex items-center gap-2">
              <Crosshair className="w-4 h-4 text-cyan-400" />
              <span className="font-mono text-xs font-bold tracking-wider text-cyan-300">
                MANUEL YÖNLENDİRME (JOG)
              </span>
            </div>

            <button
              onClick={onOpenPidModal}
              className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 bg-cyan-950 hover:bg-cyan-900 border border-cyan-500/40 text-cyan-300 rounded transition-colors"
            >
              <Sliders className="w-3 h-3" /> PID AYARI
            </button>
          </div>

          <div className="flex items-center justify-between gap-3">
            {/* D-Pad Jog Controls */}
            <div className="grid grid-cols-3 gap-1 w-28">
              <div />
              <button
                onClick={() => handleManualJog('y', 1)}
                title="Pitch Yukarı"
                className="p-2 bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-500/40 rounded flex items-center justify-center text-cyan-300 active:scale-95"
              >
                <ArrowUp className="w-3.5 h-3.5" />
              </button>
              <div />

              <button
                onClick={() => handleManualJog('x', -1)}
                title="Yaw Sola"
                className="p-2 bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-500/40 rounded flex items-center justify-center text-cyan-300 active:scale-95"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleCenter}
                title="Merkeze Sıfırla"
                className="p-2 bg-cyan-900/60 hover:bg-cyan-800 border border-cyan-400/60 rounded flex items-center justify-center text-white active:scale-95"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => handleManualJog('x', 1)}
                title="Yaw Sağa"
                className="p-2 bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-500/40 rounded flex items-center justify-center text-cyan-300 active:scale-95"
              >
                <ArrowRight className="w-3.5 h-3.5" />
              </button>

              <div />
              <button
                onClick={() => handleManualJog('y', -1)}
                title="Pitch Aşağı"
                className="p-2 bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-500/40 rounded flex items-center justify-center text-cyan-300 active:scale-95"
              >
                <ArrowDown className="w-3.5 h-3.5" />
              </button>
              <div />
            </div>

            {/* Quick Action Commands */}
            <div className="flex-1 flex flex-col gap-2">
              <button
                onClick={handleCenter}
                className="w-full py-1.5 px-2 bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-500/50 rounded text-[11px] font-mono font-bold text-cyan-200 tracking-wider flex items-center justify-center gap-1.5"
              >
                <RotateCcw className="w-3 h-3 text-cyan-400" /> MERKEZE SIFIRLA (C)
              </button>

              <button
                onClick={handleEmergencyStop}
                className="w-full py-1.5 px-2 bg-red-950/90 hover:bg-red-900 border border-red-500 rounded text-[11px] font-mono font-black text-red-200 tracking-wider flex items-center justify-center gap-1.5 glow-red active:scale-95"
              >
                <Octagon className="w-3.5 h-3.5 text-red-400" /> ACİL DURDUR (ESC)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
