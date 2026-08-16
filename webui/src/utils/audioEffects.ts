// Web Audio API Synthesizer for Tactical HUD Sound Effects

class SoundManager {
  private ctx: AudioContext | null = null;
  private isMuted: boolean = false;

  // Active Laser Continuous Audio Nodes
  private laserOsc1: OscillatorNode | null = null;
  private laserOsc2: OscillatorNode | null = null;
  private laserLfo: OscillatorNode | null = null;
  private laserGain: GainNode | null = null;
  private isLaserAudioRunning: boolean = false;

  private initContext() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  public setMuted(muted: boolean) {
    this.isMuted = muted;
    if (muted) {
      this.stopLaserContinuousFire();
    }
  }

  public getIsMuted(): boolean {
    return this.isMuted;
  }

  // Tactical click / beep
  public playClick() {
    if (this.isMuted) return;
    this.initContext();
    if (!this.ctx) return;

    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(1200, this.ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(800, this.ctx.currentTime + 0.04);

    gain.gain.setValueAtTime(0.08, this.ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.04);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start();
    osc.stop(this.ctx.currentTime + 0.04);
  }

  // Target Lock-On Tone
  public playLockOn() {
    if (this.isMuted) return;
    this.initContext();
    if (!this.ctx) return;

    const t = this.ctx.currentTime;
    const osc1 = this.ctx.createOscillator();
    const osc2 = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc1.type = 'sawtooth';
    osc2.type = 'sine';

    osc1.frequency.setValueAtTime(1760, t);
    osc2.frequency.setValueAtTime(880, t);

    osc1.frequency.setValueAtTime(2349.3, t + 0.08);
    osc2.frequency.setValueAtTime(1174.6, t + 0.08);

    gain.gain.setValueAtTime(0.12, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.22);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(this.ctx.destination);

    osc1.start(t);
    osc2.start(t);
    osc1.stop(t + 0.22);
    osc2.stop(t + 0.22);
  }

  // Continuous Synchronized Laser Weapon Hum & Blast (While Holding Button)
  public startLaserContinuousFire() {
    if (this.isMuted || this.isLaserAudioRunning) return;
    this.initContext();
    if (!this.ctx) return;

    try {
      const t = this.ctx.currentTime;
      this.isLaserAudioRunning = true;

      // Primary High-Frequency Plasma Beam Carrier
      const osc1 = this.ctx.createOscillator();
      osc1.type = 'sawtooth';
      osc1.frequency.setValueAtTime(2400, t);
      osc1.frequency.exponentialRampToValueAtTime(1600, t + 0.08);

      // Secondary Sub-Bass Heavy Beam Core
      const osc2 = this.ctx.createOscillator();
      osc2.type = 'square';
      osc2.frequency.setValueAtTime(140, t);

      // LFO Tremolo Modulation for Pulsating Laser Shockwave Rhythm
      const lfo = this.ctx.createOscillator();
      const lfoGain = this.ctx.createGain();
      lfo.frequency.setValueAtTime(28, t); // 28Hz rapid tactical energy pulse
      lfoGain.gain.setValueAtTime(0.08, t);
      lfo.connect(lfoGain.gain);

      const mainGain = this.ctx.createGain();
      mainGain.gain.setValueAtTime(0.01, t);
      mainGain.gain.linearRampToValueAtTime(0.18, t + 0.04);

      osc1.connect(mainGain);
      osc2.connect(mainGain);
      mainGain.connect(this.ctx.destination);

      osc1.start(t);
      osc2.start(t);
      lfo.start(t);

      this.laserOsc1 = osc1;
      this.laserOsc2 = osc2;
      this.laserLfo = lfo;
      this.laserGain = mainGain;
    } catch (e) {
      console.warn('Could not start continuous laser sound:', e);
    }
  }

  // Stop Continuous Laser Sound on Release
  public stopLaserContinuousFire() {
    if (!this.isLaserAudioRunning || !this.ctx) return;
    try {
      const t = this.ctx.currentTime;
      if (this.laserGain) {
        this.laserGain.gain.setValueAtTime(this.laserGain.gain.value, t);
        this.laserGain.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
      }

      const osc1 = this.laserOsc1;
      const osc2 = this.laserOsc2;
      const lfo = this.laserLfo;

      setTimeout(() => {
        try {
          osc1?.stop();
          osc1?.disconnect();
          osc2?.stop();
          osc2?.disconnect();
          lfo?.stop();
          lfo?.disconnect();
        } catch {}
      }, 90);

      this.isLaserAudioRunning = false;
      this.laserOsc1 = null;
      this.laserOsc2 = null;
      this.laserLfo = null;
      this.laserGain = null;
    } catch (e) {
      this.isLaserAudioRunning = false;
    }
  }

  // Emergency Alert Sound
  public playAlert() {
    if (this.isMuted) return;
    this.initContext();
    if (!this.ctx) return;

    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(440, t);
    osc.frequency.setValueAtTime(880, t + 0.1);
    osc.frequency.setValueAtTime(440, t + 0.2);

    gain.gain.setValueAtTime(0.15, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.35);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start(t);
    osc.stop(t + 0.35);
  }
}

export const soundManager = new SoundManager();
