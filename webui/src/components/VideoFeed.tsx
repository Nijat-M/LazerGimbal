import React, { useState } from 'react';
import { HudOverlay } from './HudOverlay';
import type { TargetDetection } from '../types/telemetry';
import {
  Maximize2,
  Minimize2,
  Volume2,
  VolumeX,
  ShieldAlert,
  Crosshair,
  Cpu,
  Camera,
  RotateCw,
  Tv,
} from 'lucide-react';
import { soundManager } from '../utils/audioEffects';

interface VideoFeedProps {
  pitch: number;
  yaw: number;
  errorX: number;
  errorY: number;
  detections: TargetDetection[];
  systemState: string;
  laserFiring: boolean;
  laserArmed: boolean;
  trackingMode: string;
  fps: number;
  connected: boolean;
  cameraId?: number;
  isCameraLive?: boolean;
  flipMode?: string;
  onSwitchCamera?: (id: number) => void;
  onSetFlipMode?: (mode: 'NONE' | '180' | 'V' | 'H') => void;
}

export const VideoFeed: React.FC<VideoFeedProps> = ({
  pitch,
  yaw,
  errorX,
  errorY,
  detections,
  systemState,
  laserFiring,
  laserArmed,
  trackingMode,
  fps,
  connected,
  cameraId = 0,
  isCameraLive = false,
  flipMode = 'NONE',
  onSwitchCamera,
  onSetFlipMode,
}) => {
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [streamError, setStreamError] = useState<boolean>(false);
  const [showCamMenu, setShowCamMenu] = useState<boolean>(false);

  const toggleFullscreen = () => {
    const el = document.getElementById('tactical-video-container');
    if (!el) return;

    if (!document.fullscreenElement) {
      el.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  };

  const toggleSound = () => {
    const newMuted = !isMuted;
    setIsMuted(newMuted);
    soundManager.setMuted(newMuted);
  };

  const cameraOptions = [
    { id: 0, label: '📷 CAM 0: Ana Kamera (Built-in / USB)' },
    { id: 1, label: '📷 CAM 1: Gimbal EO/IR Kamera' },
    { id: 2, label: '📷 CAM 2: Harici USB Kamera' },
    { id: -1, label: '🛸 SİMÜLASYON: Taktiksel Hedef Modu' },
  ];

  const flipOptions: Array<{ mode: 'NONE' | '180' | 'V' | 'H'; label: string }> = [
    { mode: 'NONE', label: 'Normal (0°)' },
    { mode: '180', label: '180° Ters Montaj' },
    { mode: 'H', label: 'Yatay Aynalama (H)' },
    { mode: 'V', label: 'Dikey Ters (V)' },
  ];

  return (
    <div
      id="tactical-video-container"
      className="relative w-full aspect-video bg-black rounded-xl border border-cyan-500/30 overflow-hidden shadow-2xl flex items-center justify-center tactical-corners"
    >
      {/* 1. Video Stream or Tactical Standby Graphic */}
      {!streamError ? (
        <img
          src="/video_feed"
          alt="EO/IR Optical Gimbal Feed"
          onError={() => setStreamError(true)}
          className="w-full h-full object-contain select-none"
        />
      ) : (
        <div className="w-full h-full flex flex-col items-center justify-center bg-[#050b14] sci-fi-grid">
          <Crosshair className="w-16 h-16 text-cyan-500/40 animate-pulse mb-3" />
          <div className="text-cyan-400 font-mono text-sm tracking-widest uppercase">
            STANDBY // OPTICAL FEED OFFLINE
          </div>
          <div className="text-xs text-cyan-600 mt-1 font-mono">
            CONNECT BACKEND SERVER OR LAUNCH CAMERA
          </div>
          <button
            onClick={() => setStreamError(false)}
            className="mt-4 px-3 py-1 bg-cyan-950/60 hover:bg-cyan-900 border border-cyan-500/40 text-cyan-300 text-xs font-mono rounded transition-colors"
          >
            RETRY FEED
          </button>
        </div>
      )}

      {/* 2. HUD Canvas Graphics Overlay */}
      <HudOverlay
        pitch={pitch}
        yaw={yaw}
        errorX={errorX}
        errorY={errorY}
        detections={detections}
        systemState={systemState}
        laserFiring={laserFiring}
        laserArmed={laserArmed}
        trackingMode={trackingMode}
      />

      {/* 3. Scanline & Vignette Effect Layer */}
      <div className="absolute inset-0 scanlines pointer-events-none z-20" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-black/40 pointer-events-none z-20" />

      {/* 4. Top Telemetry Status Bar inside Video */}
      <div className="absolute top-3 left-4 right-4 flex items-center justify-between z-30 pointer-events-none">
        {/* Left Side: System & Mode Badges */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 bg-black/70 backdrop-blur-md px-2.5 py-1 rounded border border-cyan-500/30 text-xs font-mono font-bold tracking-wider">
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-ping' : 'bg-red-500'}`} />
            <span className="text-cyan-400">{trackingMode}</span>
          </div>

          <div className="flex items-center gap-1 bg-black/70 backdrop-blur-md px-2.5 py-1 rounded border border-cyan-500/30 text-xs font-mono text-cyan-300">
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            <span>FPS: <b className="text-white">{fps.toFixed(0)}</b></span>
          </div>
        </div>

        {/* Right Side: Action Controls */}
        <div className="flex items-center gap-2 pointer-events-auto relative">
          {/* Laser Firing Warning */}
          {laserFiring && (
            <div className="flex items-center gap-1.5 bg-red-950/90 border border-red-500 px-3 py-1 rounded text-red-300 text-xs font-mono font-bold animate-pulse">
              <ShieldAlert className="w-3.5 h-3.5 text-red-400" />
              <span>ACTIVE FIRING</span>
            </div>
          )}

          {/* Camera Selector Dropdown Trigger */}
          <button
            onClick={() => setShowCamMenu(!showCamMenu)}
            title="Kamera ve Görüntü Ayarları"
            className="flex items-center gap-1.5 px-2.5 py-1 bg-black/70 hover:bg-cyan-950 border border-cyan-500/40 rounded text-cyan-300 text-xs font-mono transition-colors"
          >
            <Camera className="w-3.5 h-3.5 text-cyan-400" />
            <span>
              {cameraId === -1 ? 'SİMÜLASYON' : isCameraLive ? `CAM ${cameraId} (LIVE)` : `CAM ${cameraId}`}
            </span>
          </button>

          {/* Camera Selection Popup Modal / Dropdown */}
          {showCamMenu && (
            <div className="absolute right-0 top-9 w-64 bg-[#070e1c] border border-cyan-500/50 rounded-xl p-3 shadow-2xl z-50 flex flex-col gap-2 font-mono text-xs text-cyan-200">
              <div className="flex items-center justify-between border-b border-cyan-500/30 pb-1.5 text-cyan-400 font-bold">
                <span className="flex items-center gap-1">
                  <Tv className="w-3.5 h-3.5" /> KAMERA SEÇİMİ
                </span>
                <button
                  onClick={() => setShowCamMenu(false)}
                  className="text-cyan-500 hover:text-white"
                >
                  ✕
                </button>
              </div>

              {/* Camera List */}
              <div className="flex flex-col gap-1">
                {cameraOptions.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => {
                      if (onSwitchCamera) onSwitchCamera(opt.id);
                      setShowCamMenu(false);
                    }}
                    className={`p-2 rounded text-left transition-colors border ${
                      cameraId === opt.id
                        ? 'bg-cyan-950 border-cyan-400 text-cyan-200 font-bold'
                        : 'bg-black/30 border-transparent hover:bg-cyan-950/50 text-cyan-400'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              {/* Image Orientation Flip Selection */}
              <div className="border-t border-cyan-500/20 pt-2 flex flex-col gap-1">
                <span className="text-[10px] text-cyan-400 flex items-center gap-1">
                  <RotateCw className="w-3 h-3" /> GÖRÜNTÜ YÖNÜ / FLIP:
                </span>
                <div className="grid grid-cols-2 gap-1">
                  {flipOptions.map((f) => (
                    <button
                      key={f.mode}
                      onClick={() => {
                        if (onSetFlipMode) onSetFlipMode(f.mode);
                      }}
                      className={`p-1.5 rounded text-[10px] text-center border ${
                        flipMode === f.mode
                          ? 'bg-cyan-900/80 border-cyan-400 text-white font-bold'
                          : 'bg-black/40 border-cyan-500/20 text-cyan-400 hover:bg-cyan-950/40'
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Sound Toggle */}
          <button
            onClick={toggleSound}
            title={isMuted ? 'Unmute Audio' : 'Mute Audio'}
            className="p-1.5 bg-black/70 hover:bg-cyan-950 border border-cyan-500/40 rounded text-cyan-400 hover:text-cyan-200 transition-colors"
          >
            {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
          </button>

          {/* Fullscreen Button */}
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
            className="p-1.5 bg-black/70 hover:bg-cyan-950 border border-cyan-500/40 rounded text-cyan-400 hover:text-cyan-200 transition-colors"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* 5. Bottom Diagnostics Bar inside Video */}
      <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between z-30 pointer-events-none text-xs font-mono">
        <div className="bg-black/70 backdrop-blur-md px-3 py-1 rounded border border-cyan-500/30 text-cyan-300 flex items-center gap-3">
          <span>ΔX: <b className="text-white">{errorX > 0 ? `+${errorX}` : errorX}px</b></span>
          <span>ΔY: <b className="text-white">{errorY > 0 ? `+${errorY}` : errorY}px</b></span>
        </div>

        <div className="bg-black/70 backdrop-blur-md px-3 py-1 rounded border border-cyan-500/30 text-cyan-400">
          EO/IR SENSOR:{' '}
          <span className={isCameraLive ? 'text-green-400 font-bold' : 'text-amber-400 font-bold'}>
            {isCameraLive ? `HARDWARE CAM ${cameraId} ACTIVE` : 'TACTICAL SIMULATION ACTIVE'}
          </span>
        </div>
      </div>
    </div>
  );
};
