import React, { useState } from 'react';
import { X, Sliders, Save, RotateCcw } from 'lucide-react';
import type { SystemCommand } from '../types/telemetry';


interface PidTuningModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentPid: {
    kp: number;
    ki: number;
    kd: number;
  };
  onSendCommand: (cmd: SystemCommand) => void;
}

export const PidTuningModal: React.FC<PidTuningModalProps> = ({
  isOpen,
  onClose,
  currentPid,
  onSendCommand,
}) => {
  const [kp, setKp] = useState<number>(currentPid.kp || 0.60);
  const [ki, setKi] = useState<number>(currentPid.ki || 0.16);
  const [kd, setKd] = useState<number>(currentPid.kd || 0.50);
  const [deadzone, setDeadzone] = useState<number>(5);

  if (!isOpen) return null;

  const handleApply = () => {
    onSendCommand({
      action: 'UPDATE_PID',
      payload: {
        kp: parseFloat(kp.toString()),
        ki: parseFloat(ki.toString()),
        kd: parseFloat(kd.toString()),
        deadzone: parseInt(deadzone.toString(), 10),
      },
    });
    onClose();
  };

  const handleResetDefaults = () => {
    setKp(0.60);
    setKi(0.16);
    setKd(0.50);
    setDeadzone(5);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
      <div className="hud-panel rounded-2xl w-full max-w-md p-6 tactical-corners border border-cyan-500/50 shadow-2xl flex flex-col gap-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-cyan-500/30 pb-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-5 h-5 text-cyan-400" />
            <h2 className="font-mono text-base font-bold tracking-wider text-cyan-200">
              PID CONTROLLER & FILTER TUNING
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-cyan-950/80 rounded border border-cyan-500/30 text-cyan-400 hover:text-cyan-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Sliders Body */}
        <div className="flex flex-col gap-4 font-mono text-xs">
          {/* Kp Slider */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-cyan-300">
              <span>PROPORTIONAL GAIN (Kp):</span>
              <span className="font-bold text-white">{kp.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="2.5"
              step="0.01"
              value={kp}
              onChange={(e) => setKp(parseFloat(e.target.value))}
              className="accent-cyan-400 w-full cursor-pointer"
            />
            <span className="text-[10px] text-cyan-600">Speed and fast convergence responsiveness</span>
          </div>

          {/* Ki Slider */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-cyan-300">
              <span>INTEGRAL GAIN (Ki):</span>
              <span className="font-bold text-white">{ki.toFixed(3)}</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="0.8"
              step="0.005"
              value={ki}
              onChange={(e) => setKi(parseFloat(e.target.value))}
              className="accent-cyan-400 w-full cursor-pointer"
            />
            <span className="text-[10px] text-cyan-600">Eliminates steady-state tracking error</span>
          </div>

          {/* Kd Slider */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-cyan-300">
              <span>DERIVATIVE GAIN (Kd):</span>
              <span className="font-bold text-white">{kd.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="1.5"
              step="0.01"
              value={kd}
              onChange={(e) => setKd(parseFloat(e.target.value))}
              className="accent-cyan-400 w-full cursor-pointer"
            />
            <span className="text-[10px] text-cyan-600">Damping to prevent overshoot and oscillations</span>
          </div>

          {/* Deadzone */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-cyan-300">
              <span>TRACKING DEADZONE:</span>
              <span className="font-bold text-white">{deadzone} px</span>
            </div>
            <input
              type="range"
              min="0"
              max="20"
              step="1"
              value={deadzone}
              onChange={(e) => setDeadzone(parseInt(e.target.value, 10))}
              className="accent-cyan-400 w-full cursor-pointer"
            />
            <span className="text-[10px] text-cyan-600">Pixel threshold for jitter suppression</span>
          </div>
        </div>

        {/* Actions Footer */}
        <div className="flex items-center justify-between gap-3 pt-3 border-t border-cyan-500/20 font-mono text-xs">
          <button
            onClick={handleResetDefaults}
            className="py-2 px-3 bg-cyan-950/40 hover:bg-cyan-950 text-cyan-400 border border-cyan-500/30 rounded-lg flex items-center gap-1.5 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" /> DEFAULTS
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="py-2 px-4 bg-transparent hover:bg-cyan-950/50 text-cyan-300 border border-cyan-500/20 rounded-lg transition-colors"
            >
              CANCEL
            </button>
            <button
              onClick={handleApply}
              className="py-2 px-4 bg-cyan-500 hover:bg-cyan-400 text-black font-bold rounded-lg flex items-center gap-1.5 shadow-[0_0_15px_rgba(0,240,255,0.5)] transition-all"
            >
              <Save className="w-3.5 h-3.5" /> APPLY TO STM32
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
