import { useState, useEffect } from 'react';
import { useGimbalSocket } from './hooks/useGimbalSocket';
import { VideoFeed } from './components/VideoFeed';
import { Gimbal3DView } from './components/Gimbal3DView';
import { TelemetryPanel } from './components/TelemetryPanel';
import { ControlCenter } from './components/ControlCenter';
import { TacticalLog } from './components/TacticalLog';
import { PidTuningModal } from './components/PidTuningModal';
import {
  Crosshair,
  Wifi,
  WifiOff,
  Keyboard,
  Clock,
} from 'lucide-react';


export function App() {
  const { telemetry, wsConnected, logs, sendCommand } = useGimbalSocket();
  const [isPidModalOpen, setIsPidModalOpen] = useState<boolean>(false);
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<string>('');

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString('tr-TR', { hour12: false }) + ' UTC');
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if typing in an input
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) return;

      if (e.key === 'ArrowUp' || e.key.toLowerCase() === 'w') {
        sendCommand({ action: 'MANUAL_JOG', payload: { axis: 'y', dir: 1 } });
      } else if (e.key === 'ArrowDown' || e.key.toLowerCase() === 's') {
        sendCommand({ action: 'MANUAL_JOG', payload: { axis: 'y', dir: -1 } });
      } else if (e.key === 'ArrowLeft' || e.key.toLowerCase() === 'a') {
        sendCommand({ action: 'MANUAL_JOG', payload: { axis: 'x', dir: -1 } });
      } else if (e.key === 'ArrowRight' || e.key.toLowerCase() === 'd') {
        sendCommand({ action: 'MANUAL_JOG', payload: { axis: 'x', dir: 1 } });
      } else if (e.key.toLowerCase() === 'c') {
        sendCommand({ action: 'CENTER' });
      } else if (e.key === 'Escape') {
        sendCommand({ action: 'EMERGENCY_STOP' });
      } else if (e.key === ' ') {
        e.preventDefault();
        if (telemetry.laser_armed && !telemetry.laser_firing) {
          sendCommand({ action: 'FIRE_LASER', payload: { firing: true } });
        }
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === ' ') {
        if (telemetry.laser_armed) {
          sendCommand({ action: 'STOP_LASER', payload: { firing: false } });
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [sendCommand, telemetry.laser_armed, telemetry.laser_firing]);

  const handleConnectPort = (port: string) => {
    sendCommand({ action: 'CONNECT_SERIAL', payload: { port } });
  };

  const handleDisconnectPort = () => {
    sendCommand({ action: 'DISCONNECT_SERIAL' });
  };

  return (
    <div className="min-h-screen bg-[#040711] text-cyan-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-black">
      {/* 1. Futuristic Top Command Bar */}
      <header className="hud-panel sticky top-0 z-40 px-4 py-2.5 border-b border-cyan-500/30 flex items-center justify-between">
        {/* Left: Branding & Mission Info */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-700 flex items-center justify-center shadow-[0_0_15px_rgba(0,240,255,0.4)]">
            <Crosshair className="w-5 h-5 text-black stroke-[2.5]" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-mono text-sm font-black tracking-wider text-white">
                LAZER GIMBAL // TEKNOFEST HSS
              </h1>
              <span className="text-[10px] font-mono px-1.5 py-0.2 bg-cyan-950 text-cyan-400 border border-cyan-500/40 rounded">
                GCS v2.0
              </span>
            </div>
            <p className="text-[11px] font-mono text-cyan-400/70">
              AIR DEFENSE LASER TURRET COMMAND & CONTROL
            </p>
          </div>
        </div>

        {/* Center: System Clock & Health */}
        <div className="hidden md:flex items-center gap-6 font-mono text-xs">
          <div className="flex items-center gap-2 text-cyan-300">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span>{currentTime || '12:00:00 UTC'}</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-cyan-500">LINK:</span>
            {wsConnected ? (
              <span className="flex items-center gap-1 text-green-400 font-bold">
                <Wifi className="w-3.5 h-3.5" /> SECURE WS
              </span>
            ) : (
              <span className="flex items-center gap-1 text-red-400 font-bold">
                <WifiOff className="w-3.5 h-3.5" /> DISCONNECTED
              </span>
            )}
          </div>
        </div>

        {/* Right: Quick Action Modals */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsHelpOpen(!isHelpOpen)}
            title="Keyboard Shortcuts"
            className="p-1.5 bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-500/30 rounded text-cyan-300 text-xs font-mono flex items-center gap-1.5 transition-colors"
          >
            <Keyboard className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">KEYS</span>
          </button>
        </div>
      </header>

      {/* 2. Main Tactical Dashboard Content */}
      <main className="flex-1 p-3 sm:p-4 max-w-[1920px] w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (7 Cols): Video HUD + Tactical Weapon & Gimbal Controls directly under camera */}
        <div className="lg:col-span-7 flex flex-col gap-3">
          <VideoFeed
            pitch={telemetry.pitch}
            yaw={telemetry.yaw}
            errorX={telemetry.error_x}
            errorY={telemetry.error_y}
            detections={telemetry.detections || []}
            systemState={telemetry.system_state}
            laserFiring={telemetry.laser_firing}
            laserArmed={telemetry.laser_armed}
            trackingMode={telemetry.tracking_mode}
            fps={telemetry.fps}
            connected={telemetry.connected}
            cameraId={telemetry.camera_id}
            isCameraLive={telemetry.is_camera_live}
            flipMode={telemetry.flip_mode}
            onSwitchCamera={(id) => sendCommand({ action: 'SET_CAMERA', payload: { camera_id: id } })}
            onSetFlipMode={(mode) => sendCommand({ action: 'SET_FLIP_MODE', payload: { flip_mode: mode } })}
          />

          {/* Tactical Weapon & Mode Controls (Directly Under Video Feed) */}
          <ControlCenter
            trackingMode={telemetry.tracking_mode}
            laserArmed={telemetry.laser_armed}
            laserFiring={telemetry.laser_firing}
            onSendCommand={sendCommand}
            onOpenPidModal={() => setIsPidModalOpen(true)}
          />
        </div>

        {/* Right Column (5 Cols): 3D Twin + Telemetry Vitals + Mission Log */}
        <div className="lg:col-span-5 flex flex-col gap-3">
          {/* 3D Hardware Digital Twin Viewport */}
          <div className="h-60 sm:h-64 w-full">
            <Gimbal3DView
              pitch={telemetry.pitch}
              yaw={telemetry.yaw}
              roll={telemetry.roll}
              laserFiring={telemetry.laser_firing}
              laserArmed={telemetry.laser_armed}
              systemState={telemetry.system_state}
            />
          </div>

          {/* Telemetry Sensor Panels */}
          <TelemetryPanel
            telemetry={telemetry}
            onConnectPort={handleConnectPort}
            onDisconnectPort={handleDisconnectPort}
          />

          {/* Tactical Event Stream & Mission Logs */}
          <TacticalLog logs={logs} />
        </div>
      </main>


      {/* 3. PID Tuning Modal */}
      <PidTuningModal
        isOpen={isPidModalOpen}
        onClose={() => setIsPidModalOpen(false)}
        currentPid={telemetry.pid}
        onSendCommand={sendCommand}
      />

      {/* 4. Keyboard Shortcuts Modal */}
      {isHelpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
          <div className="hud-panel rounded-2xl w-full max-w-md p-6 tactical-corners border border-cyan-500/50 shadow-2xl flex flex-col gap-4 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-cyan-500/30 pb-3">
              <div className="flex items-center gap-2">
                <Keyboard className="w-4 h-4 text-cyan-400" />
                <h3 className="font-bold text-cyan-200">TACTICAL KEYBOARD HOTKEYS</h3>
              </div>
              <button onClick={() => setIsHelpOpen(false)} className="text-cyan-400 hover:text-white">
                ✕
              </button>
            </div>

            <div className="flex flex-col gap-2.5">
              <div className="flex justify-between border-b border-cyan-500/10 pb-1">
                <span className="text-cyan-300">W / A / S / D or Arrow Keys:</span>
                <span className="text-white font-bold">Manual Gimbal Jog (Pitch / Yaw)</span>
              </div>
              <div className="flex justify-between border-b border-cyan-500/10 pb-1">
                <span className="text-cyan-300">Spacebar (Hold):</span>
                <span className="text-red-400 font-bold">Fire Laser Beam (When Armed)</span>
              </div>
              <div className="flex justify-between border-b border-cyan-500/10 pb-1">
                <span className="text-cyan-300">C Key:</span>
                <span className="text-cyan-400 font-bold">Center Gimbal to (0, 0)</span>
              </div>
              <div className="flex justify-between border-b border-cyan-500/10 pb-1">
                <span className="text-cyan-300">Escape Key:</span>
                <span className="text-red-500 font-bold">Emergency Stop (!STOP)</span>
              </div>
            </div>

            <button
              onClick={() => setIsHelpOpen(false)}
              className="mt-2 py-2 w-full bg-cyan-950 hover:bg-cyan-900 border border-cyan-500/40 text-cyan-200 rounded-lg transition-colors font-bold"
            >
              CLOSE
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
export default App;
