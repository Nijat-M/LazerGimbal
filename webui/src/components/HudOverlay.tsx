import React, { useEffect, useRef } from 'react';
import type { TargetDetection } from '../types/telemetry';

interface HudOverlayProps {
  pitch: number;
  yaw: number;
  errorX: number;
  errorY: number;
  detections: TargetDetection[];
  systemState: string;
  laserFiring: boolean;
  laserArmed: boolean;
  trackingMode: string;
}

export const HudOverlay: React.FC<HudOverlayProps> = ({
  pitch,
  yaw,
  errorX,
  errorY,
  detections,
  systemState,
  laserFiring,
  laserArmed,
  trackingMode,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      const cx = width / 2;
      const cy = height / 2;
      const time = Date.now() * 0.003;

      ctx.clearRect(0, 0, width, height);

      // 1. Compass Azimuth Heading Tape (Top Center)
      const compassW = 340;
      const compassH = 32;
      const compassY = 38;
      ctx.save();
      ctx.fillStyle = 'rgba(4, 12, 22, 0.6)';
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.3)';
      ctx.lineWidth = 1;
      ctx.strokeRect(cx - compassW / 2, compassY, compassW, compassH);
      ctx.fillRect(cx - compassW / 2, compassY, compassW, compassH);

      // Center pointer triangle
      ctx.fillStyle = '#00f0ff';
      ctx.beginPath();
      ctx.moveTo(cx, compassY + compassH);
      ctx.lineTo(cx - 5, compassY + compassH + 7);
      ctx.lineTo(cx + 5, compassY + compassH + 7);
      ctx.closePath();
      ctx.fill();

      // Heading ticks
      ctx.font = '10px Share Tech Mono, monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';


      for (let angle = -180; angle <= 180; angle += 15) {
        const offset = (angle - (yaw % 360)) * 2.5;
        const tickX = cx + offset;
        if (tickX > cx - compassW / 2 + 8 && tickX < cx + compassW / 2 - 8) {
          const isMajor = angle % 45 === 0;
          ctx.strokeStyle = isMajor ? 'rgba(0, 240, 255, 0.9)' : 'rgba(0, 240, 255, 0.35)';
          ctx.beginPath();
          ctx.moveTo(tickX, compassY);
          ctx.lineTo(tickX, compassY + (isMajor ? 12 : 6));
          ctx.stroke();

          if (isMajor) {
            let label = `${((angle % 360) + 360) % 360}°`;
            if (angle === 0 || angle === 360 || angle === -360) label = 'N';
            else if (angle === 90 || angle === -270) label = 'E';
            else if (angle === 180 || angle === -180) label = 'S';
            else if (angle === 270 || angle === -90) label = 'W';

            ctx.fillStyle = '#00f0ff';
            ctx.fillText(label, tickX, compassY + 22);
          }
        }
      }
      ctx.restore();

      // 2. Artificial Horizon / Pitch Ladder (Center)
      ctx.save();
      ctx.translate(cx, cy);
      const pitchOffset = pitch * 3.5;

      ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
      ctx.lineWidth = 1.5;
      ctx.fillStyle = 'rgba(0, 240, 255, 0.8)';
      ctx.font = '10px Share Tech Mono, monospace';

      // Pitch rungs (-30 to +30 degrees)
      for (let p = -30; p <= 30; p += 10) {
        if (p === 0) {
          // Zero horizon line
          const ry = pitchOffset;
          ctx.beginPath();
          ctx.moveTo(-70, ry);
          ctx.lineTo(-20, ry);
          ctx.moveTo(20, ry);
          ctx.lineTo(70, ry);
          ctx.stroke();
          ctx.fillText('00', -80, ry + 3);
          ctx.fillText('00', 80, ry + 3);
        } else {
          const ry = pitchOffset - p * 3.5;
          const rungW = Math.abs(p) % 20 === 0 ? 40 : 25;
          ctx.beginPath();
          ctx.moveTo(-rungW, ry);
          ctx.lineTo(-15, ry);
          ctx.moveTo(15, ry);
          ctx.lineTo(rungW, ry);
          ctx.stroke();
          ctx.fillText(`${Math.abs(p)}`, -rungW - 10, ry + 3);
          ctx.fillText(`${Math.abs(p)}`, rungW + 10, ry + 3);
        }
      }
      ctx.restore();

      // 3. Central Reticle & Crosshair
      ctx.save();
      ctx.translate(cx, cy);

      const isLocked = systemState === 'LOCKED' || laserFiring;
      const reticleColor = laserFiring ? '#ff3344' : isLocked ? '#ffaa00' : '#00f0ff';

      // Outer rotating segmented reticle ring
      ctx.strokeStyle = reticleColor;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(0, 0, 70, time, time + Math.PI * 0.6);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(0, 0, 70, time + Math.PI, time + Math.PI * 1.6);
      ctx.stroke();

      // Inner Reticle Crosshairs with Deadzone Circle
      ctx.strokeStyle = reticleColor;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      // Center deadzone circle
      ctx.arc(0, 0, 10, 0, Math.PI * 2);
      ctx.stroke();

      // Crosshair lines with gaps
      ctx.beginPath();
      ctx.moveTo(-45, 0);
      ctx.lineTo(-15, 0);
      ctx.moveTo(15, 0);
      ctx.lineTo(45, 0);
      ctx.moveTo(0, -45);
      ctx.lineTo(0, -15);
      ctx.moveTo(0, 15);
      ctx.lineTo(0, 45);
      ctx.stroke();

      // Mil-dots
      [-30, -20, 20, 30].forEach((d) => {
        ctx.beginPath();
        ctx.arc(d, 0, 1.2, 0, Math.PI * 2);
        ctx.arc(0, d, 1.2, 0, Math.PI * 2);
        ctx.fillStyle = reticleColor;
        ctx.fill();
      });

      // Central Aim Dot
      ctx.beginPath();
      ctx.arc(0, 0, 2, 0, Math.PI * 2);
      ctx.fillStyle = laserFiring ? '#ff3344' : '#00f0ff';
      ctx.fill();

      // Lead Angle Indicator Dot (if error is present)
      if (Math.abs(errorX) > 2 || Math.abs(errorY) > 2) {
        ctx.beginPath();
        ctx.arc(-errorX * 0.5, -errorY * 0.5, 4, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 170, 0, 0.85)';
        ctx.fill();
        ctx.strokeStyle = '#ffaa00';
        ctx.stroke();
      }

      // Expanding & Contracting Laser Energy Shockwaves (Büyüyüp Küçülen Plazma Dalgaları)
      if (laserFiring) {
        const now = Date.now() * 0.005;
        for (let i = 0; i < 4; i++) {
          const phase = (now + i * 0.75) % 2.5; // 0 to 2.5s cycle
          const waveRadius = 12 + phase * 85;   // Expands outward
          const alpha = Math.max(0, 1.0 - phase / 2.5);

          // Outer Plasma Shockwave Ring
          ctx.strokeStyle = `rgba(255, 40, 70, ${alpha * 0.9})`;
          ctx.lineWidth = Math.max(1, 3.0 - (phase / 2.5) * 2.0);
          ctx.beginPath();
          ctx.arc(0, 0, waveRadius, 0, Math.PI * 2);
          ctx.stroke();

          // Inner Golden Thermal Energy Ripple
          ctx.strokeStyle = `rgba(255, 200, 50, ${alpha * 0.75})`;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(0, 0, waveRadius * 0.9, 0, Math.PI * 2);
          ctx.stroke();

          // Energy Arc Ticks around the Wavefront
          if (phase < 1.8) {
            ctx.strokeStyle = `rgba(255, 255, 200, ${alpha * 0.85})`;
            ctx.lineWidth = 1.8;
            for (let a = 0; a < 6; a++) {
              const ang = (a * Math.PI) / 3 + now * (i % 2 === 0 ? 3 : -3);
              const px = Math.cos(ang) * waveRadius;
              const py = Math.sin(ang) * waveRadius;
              ctx.beginPath();
              ctx.moveTo(px - 5, py);
              ctx.lineTo(px + 5, py);
              ctx.stroke();
            }
          }
        }

        // Central High-Energy Core Plasma Flare
        const corePulse = 18 + Math.sin(Date.now() * 0.035) * 7;
        const grad = ctx.createRadialGradient(0, 0, 2, 0, 0, corePulse * 2.8);
        grad.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
        grad.addColorStop(0.25, 'rgba(255, 50, 90, 0.85)');
        grad.addColorStop(0.65, 'rgba(255, 140, 0, 0.45)');
        grad.addColorStop(1, 'rgba(255, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(0, 0, corePulse * 2.8, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.restore();


      // 4. Target Bounding Box Overlays
      detections.forEach((det) => {
        const [bx, by, bw, bh] = det.bbox;
        // Convert normalized or pixel coordinates
        const x = bx < 1.0 ? bx * width : (bx / 640) * width;
        const y = by < 1.0 ? by * height : (by / 480) * height;
        const w = bw < 1.0 ? bw * width : (bw / 640) * width;
        const h = bh < 1.0 ? bh * height : (bh / 480) * height;

        ctx.save();
        const boxColor = det.is_locked ? '#ff3344' : '#00f0ff';
        ctx.strokeStyle = boxColor;
        ctx.lineWidth = det.is_locked ? 2 : 1.5;

        // Tactical Corner Brackets for target
        const cornerLen = Math.min(14, w * 0.3);

        // Top-Left
        ctx.beginPath();
        ctx.moveTo(x - w / 2, y - h / 2 + cornerLen);
        ctx.lineTo(x - w / 2, y - h / 2);
        ctx.lineTo(x - w / 2 + cornerLen, y - h / 2);
        ctx.stroke();

        // Top-Right
        ctx.beginPath();
        ctx.moveTo(x + w / 2 - cornerLen, y - h / 2);
        ctx.lineTo(x + w / 2, y - h / 2);
        ctx.lineTo(x + w / 2, y - h / 2 + cornerLen);
        ctx.stroke();

        // Bottom-Left
        ctx.beginPath();
        ctx.moveTo(x - w / 2, y + h / 2 - cornerLen);
        ctx.lineTo(x - w / 2, y + h / 2);
        ctx.lineTo(x - w / 2 + cornerLen, y + h / 2);
        ctx.stroke();

        // Bottom-Right
        ctx.beginPath();
        ctx.moveTo(x + w / 2 - cornerLen, y + h / 2);
        ctx.lineTo(x + w / 2, y + h / 2);
        ctx.lineTo(x + w / 2, y + h / 2 - cornerLen);
        ctx.stroke();

        // Target Info Label Banner
        ctx.fillStyle = det.is_locked ? 'rgba(255, 51, 68, 0.85)' : 'rgba(0, 240, 255, 0.85)';
        ctx.fillRect(x - w / 2, y - h / 2 - 18, w, 16);

        ctx.fillStyle = '#000000';
        ctx.font = 'bold 10px Orbitron, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const labelText = `${det.label.toUpperCase()} [${Math.round(det.confidence * 100)}%]`;
        ctx.fillText(labelText, x, y - h / 2 - 10);

        // Target lock pulsing indicator
        if (det.is_locked) {
          ctx.strokeStyle = '#ff3344';
          ctx.beginPath();
          const pulseR = 25 + Math.sin(Date.now() * 0.01) * 5;
          ctx.arc(x, y, pulseR, 0, Math.PI * 2);
          ctx.stroke();
        }

        ctx.restore();
      });

      // 5. Tactical Corner Framing Guides
      ctx.save();
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.3)';
      ctx.lineWidth = 1;
      const pad = 16;
      const bLen = 28;

      // Top Left Corner
      ctx.beginPath();
      ctx.moveTo(pad, pad + bLen);
      ctx.lineTo(pad, pad);
      ctx.lineTo(pad + bLen, pad);
      ctx.stroke();

      // Top Right Corner
      ctx.beginPath();
      ctx.moveTo(width - pad - bLen, pad);
      ctx.lineTo(width - pad, pad);
      ctx.lineTo(width - pad, pad + bLen);
      ctx.stroke();

      // Bottom Left Corner
      ctx.beginPath();
      ctx.moveTo(pad, height - pad - bLen);
      ctx.lineTo(pad, height - pad);
      ctx.lineTo(pad + bLen, height - pad);
      ctx.stroke();

      // Bottom Right Corner
      ctx.beginPath();
      ctx.moveTo(width - pad - bLen, height - pad);
      ctx.lineTo(width - pad, height - pad);
      ctx.lineTo(width - pad, height - pad - bLen);
      ctx.stroke();
      ctx.restore();

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [pitch, yaw, errorX, errorY, detections, systemState, laserFiring, laserArmed, trackingMode]);

  return (
    <canvas
      ref={canvasRef}
      width={1280}
      height={720}
      className="absolute inset-0 w-full h-full pointer-events-none object-contain z-10"
    />
  );
};
