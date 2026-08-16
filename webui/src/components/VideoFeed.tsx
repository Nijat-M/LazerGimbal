import React, { useState } from 'react';
import { HudOverlay } from './HudOverlay';
import type { TargetDetection, CameraDevice } from '../types/telemetry';
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
  RefreshCw,
  CheckCircle2,
  Radio,
  SlidersHorizontal,
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
  targetFps?: number;
  resolution?: string;
  connected: boolean;
  cameraId?: number;
  isCameraLive?: boolean;
  flipMode?: string;
  availableCameras?: CameraDevice[];
  onSwitchCamera?: (id: number, width?: number, height?: number, fps?: number) => void;
  onSetResolution?: (width: number, height: number, fps: number) => void;
  onSetFlipMode?: (mode: 'NONE' | '180' | 'V' | 'H') => void;
  onRescanCameras?: () => void;
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
  targetFps = 60,
  resolution = '640x480',
  connected,
  cameraId = 0,
  isCameraLive = false,
  flipMode = 'NONE',
  availableCameras = [],
  onSwitchCamera,
  onSetResolution,
  onSetFlipMode,
  onRescanCameras,
}) => {
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [streamError, setStreamError] = useState<boolean>(false);
  const [showCamMenu, setShowCamMenu] = useState<boolean>(false);
  const [isScanning, setIsScanning] = useState<boolean>(false);

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

  const handleRescan = async () => {
    setIsScanning(true);
    soundManager.playClick();
    if (onRescanCameras) {
      onRescanCameras();
    } else {
      try {
        await fetch('/api/cameras/scan', { method: 'POST' });
      } catch (e) {
        console.warn('Failed to trigger camera scan:', e);
      }
    }
    setTimeout(() => setIsScanning(false), 1200);
  };

  // Resolution presets including 1920x1200
  const resolutionPresets = [
    { label: '1920x1200 (WUXGA 16:10 - 60 FPS)', width: 1920, height: 1200, fps: 60 },
    { label: '1920x1080 (FHD 16:9 - 60 FPS)', width: 1920, height: 1080, fps: 60 },
    { label: '1280x720 (HD 16:9 - 60 FPS)', width: 1280, height: 720, fps: 60 },
    { label: '640x480 (SD 4:3 - 60 FPS / 低延迟)', width: 640, height: 480, fps: 60 },
  ];

  // Default camera fallback list if no active scan yet
  const defaultCameras: CameraDevice[] = [
    { id: 0, name: 'Kamera 0 (Dahili / USB Ana Kamera)', resolution: '1920x1200', fps: 60, is_live: true },
    { id: 1, name: 'Kamera 1 (Harici Gimbal / EO Kamera)', resolution: '1920x1080', fps: 60, is_live: true },
    { id: 2, name: 'Kamera 2 (USB Video Aygıtı)', resolution: '640x480', fps: 60, is_live: true },
    { id: -1, name: 'Simülasyon / Test Akışı', resolution: '640x480', fps: 60, is_live: false },
  ];

  const cameraList = availableCameras.length > 0 ? availableCameras : defaultCameras;

  const flipOptions: Array<{ mode: 'NONE' | '180' | 'V' | 'H'; label: string }> = [
    { mode: 'NONE', label: 'Normal (0°)' },
    { mode: '180', label: '180° 翻转 (倒装)' },
    { mode: 'H', label: '水平镜像 (H)' },
    { mode: 'V', label: '垂直镜像 (V)' },
  ];

  const handleResolutionChange = (width: number, height: number, presetFps: number) => {
    if (onSetResolution) {
      onSetResolution(width, height, presetFps);
    } else if (onSwitchCamera) {
      onSwitchCamera(cameraId, width, height, presetFps);
    }
  };

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
            <span>FPS: <b className="text-white">{fps > 0 ? fps.toFixed(0) : targetFps}</b></span>
            <span className="text-cyan-600">|</span>
            <span className="text-cyan-400 font-bold">{resolution}</span>
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

          {/* Camera Device & Resolution Selector Dropdown Trigger Button */}
          <button
            onClick={() => setShowCamMenu(!showCamMenu)}
            title="Kamera Aygıt Seçimi & Çözünürlük Ayarları"
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-mono font-bold transition-all border ${
              showCamMenu
                ? 'bg-cyan-500/30 border-cyan-400 text-cyan-200 glow-cyan'
                : 'bg-black/70 hover:bg-cyan-950/80 border-cyan-500/40 text-cyan-300'
            }`}
          >
            <Camera className="w-3.5 h-3.5 text-cyan-400" />
            <span>
              {cameraId === -1 ? 'SİMÜLASYON' : isCameraLive ? `KAMERA ${cameraId} (${resolution})` : `KAMERA ${cameraId}`}
            </span>
          </button>

          {/* Comprehensive Camera Selection Popup Modal / Dropdown */}
          {showCamMenu && (
            <div className="absolute right-0 top-9 w-84 bg-[#070e1c]/95 backdrop-blur-xl border border-cyan-500/60 rounded-xl p-3.5 shadow-2xl z-50 flex flex-col gap-3 font-mono text-xs text-cyan-200">
              {/* Header with Rescan Button */}
              <div className="flex items-center justify-between border-b border-cyan-500/30 pb-2">
                <div className="flex items-center gap-1.5 text-cyan-300 font-bold text-xs">
                  <Tv className="w-4 h-4 text-cyan-400" />
                  <span>KAMERA & ÇÖZÜNÜRLÜK AYARLARI</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={handleRescan}
                    disabled={isScanning}
                    title="Bağlı Kameraları Yeniden Tara"
                    className="p-1 bg-cyan-950 hover:bg-cyan-900 border border-cyan-500/40 rounded text-cyan-300 transition-colors flex items-center gap-1 text-[10px]"
                  >
                    <RefreshCw className={`w-3 h-3 ${isScanning ? 'animate-spin text-amber-400' : 'text-cyan-400'}`} />
                    <span>{isScanning ? 'TARANIYOR...' : 'YENİDEN TARA'}</span>
                  </button>
                  <button
                    onClick={() => setShowCamMenu(false)}
                    className="p-1 text-cyan-500 hover:text-white rounded hover:bg-cyan-950"
                  >
                    ✕
                  </button>
                </div>
              </div>

              {/* 1. Dynamic Camera Devices List */}
              <div className="flex flex-col gap-1">
                <span className="text-[10px] text-cyan-400 font-bold flex items-center gap-1">
                  <Camera className="w-3 h-3 text-cyan-400" /> AYGIT SEÇİMİ (DEVICE):
                </span>
                <div className="flex flex-col gap-1 max-h-36 overflow-y-auto pr-1">
                  {cameraList.map((cam) => {
                    const isSelected = cameraId === cam.id;
                    return (
                      <button
                        key={cam.id}
                        onClick={() => {
                          if (onSwitchCamera) onSwitchCamera(cam.id);
                        }}
                        className={`p-2 rounded-lg text-left transition-all border flex items-center justify-between ${
                          isSelected
                            ? 'bg-cyan-950/90 border-cyan-400 text-cyan-100 glow-cyan font-bold'
                            : 'bg-black/40 border-cyan-500/20 hover:bg-cyan-950/50 text-cyan-400'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {cam.id === -1 ? (
                            <Radio className={`w-3.5 h-3.5 ${isSelected ? 'text-cyan-300' : 'text-cyan-600'}`} />
                          ) : (
                            <Camera className={`w-3.5 h-3.5 ${isSelected ? 'text-cyan-300' : 'text-cyan-600'}`} />
                          )}
                          <div className="flex flex-col">
                            <span className="text-[11px] leading-tight">{cam.name}</span>
                          </div>
                        </div>

                        {isSelected && <CheckCircle2 className="w-4 h-4 text-cyan-300" />}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 2. Resolution Presets (Includes 1920x1200) */}
              <div className="border-t border-cyan-500/20 pt-2 flex flex-col gap-1">
                <span className="text-[10px] text-cyan-400 font-bold flex items-center gap-1">
                  <SlidersHorizontal className="w-3 h-3 text-cyan-400" /> ÇÖZÜNÜRLÜK VE KARE HIZI (60 FPS MJPG):
                </span>
                <div className="flex flex-col gap-1">
                  {resolutionPresets.map((r) => {
                    const isCurrent = resolution === `${r.width}x${r.height}`;
                    return (
                      <button
                        key={`${r.width}x${r.height}`}
                        onClick={() => handleResolutionChange(r.width, r.height, r.fps)}
                        className={`py-1.5 px-2 rounded text-[11px] text-left border transition-colors flex items-center justify-between ${
                          isCurrent
                            ? 'bg-cyan-900/90 border-cyan-400 text-white font-bold glow-cyan'
                            : 'bg-black/40 border-cyan-500/20 text-cyan-300 hover:bg-cyan-950/50'
                        }`}
                      >
                        <span>{r.label}</span>
                        {isCurrent && <CheckCircle2 className="w-3.5 h-3.5 text-cyan-300" />}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 3. Image Orientation Flip Selection */}
              <div className="border-t border-cyan-500/20 pt-2 flex flex-col gap-1">
                <span className="text-[10px] text-cyan-400 flex items-center gap-1 font-bold">
                  <RotateCw className="w-3 h-3 text-cyan-400" /> GÖRÜNTÜ YÖNÜ / FLIP AYARI:
                </span>
                <div className="grid grid-cols-2 gap-1.5">
                  {flipOptions.map((f) => (
                    <button
                      key={f.mode}
                      onClick={() => {
                        if (onSetFlipMode) onSetFlipMode(f.mode);
                      }}
                      className={`py-1 px-2 rounded text-[10px] text-center border transition-colors ${
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
            {isCameraLive ? `HARDWARE CAM ${cameraId} (${resolution})` : 'TACTICAL SIMULATION ACTIVE'}
          </span>
        </div>
      </div>
    </div>
  );
};
