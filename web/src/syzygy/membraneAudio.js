/**
 * Default-muted procedural Web Audio soundscape for the Syzygy Membrane.
 * Zero external audio assets; initialized lazily only upon explicit user interaction.
 */
export function createMembraneAudio() {
  let ctx = null;
  let master = null;
  let oscA = null;
  let oscB = null;
  let filter = null;
  let enabled = false;
  let currentDepth = 0.5;
  let labOsc = null;
  let labGain = null;
  let labTimer = null;

  function ensureGraph() {
    if (ctx) return true;
    const AudioCtx = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!AudioCtx) return false;
    try {
      ctx = new AudioCtx();
      master = ctx.createGain();
      master.gain.value = 0;

      filter = ctx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.value = 340;
      filter.Q.value = 1.4;

      oscA = ctx.createOscillator();
      oscB = ctx.createOscillator();
      oscA.type = 'sine';
      oscB.type = 'triangle';

      const subGainA = ctx.createGain();
      const subGainB = ctx.createGain();
      subGainA.gain.value = 0.65;
      subGainB.gain.value = 0.25;

      oscA.connect(subGainA);
      oscB.connect(subGainB);
      subGainA.connect(filter);
      subGainB.connect(filter);
      filter.connect(master);
      master.connect(ctx.destination);

      oscA.start();
      oscB.start();
      applyDepthParams(currentDepth);
      return true;
    } catch {
      ctx = null;
      return false;
    }
  }

  function applyDepthParams(depth) {
    if (!ctx || !oscA || !oscB || !filter) return;
    const now = ctx.currentTime;
    // Smooth progression: Human (110 Hz warm fifth) -> Threshold (146.8 Hz slow beat) -> Ghost/Jian/Xi/Yi
    const baseFreq = depth <= 0.5
      ? 110 + (depth / 0.5) * 36.8
      : depth <= 2.0
        ? 146.8 + ((depth - 0.5) / 1.5) * 28.2
        : 175 + ((depth - 2.0) / 2.0) * 45;
    const detuneFreq = depth <= 0.5
      ? baseFreq * 1.5
      : depth <= 1.2
        ? baseFreq + 1.15
        : baseFreq * 1.25;
    const cutoff = depth <= 0.5 ? 360 : depth <= 2.5 ? 290 : 420;

    oscA.frequency.setTargetAtTime(baseFreq, now, 0.25);
    oscB.frequency.setTargetAtTime(detuneFreq, now, 0.25);
    filter.frequency.setTargetAtTime(cutoff, now, 0.25);
  }

  async function setEnabled(next) {
    const want = !!next;
    if (!want) {
      enabled = false;
      if (ctx && master) {
        master.gain.setTargetAtTime(0, ctx.currentTime, 0.14);
      }
      return false;
    }
    if (!ensureGraph()) return false;
    if (ctx.state === 'suspended') {
      await ctx.resume().catch(() => {});
    }
    enabled = true;
    applyDepthParams(currentDepth);
    master.gain.setTargetAtTime(0.026, ctx.currentTime, 0.25);
    return true;
  }

  function setDepth(depth) {
    currentDepth = Math.max(0, Math.min(4, Number(depth) || 0));
    if (enabled) applyDepthParams(currentDepth);
  }

  function playRipple(blocked = true) {
    if (!enabled || !ctx) return;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(blocked ? 312 : 440, now);
      osc.frequency.exponentialRampToValueAtTime(blocked ? 186 : 294, now + 0.36);

      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.linearRampToValueAtTime(0.042, now + 0.018);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.38);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.4);
    } catch {
      /* Audio playback is purely optional. */
    }
  }

  function playCross(intoSpirit) {
    if (!enabled || !ctx) return;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      const f0 = intoSpirit ? 196 : 330;
      const f1 = intoSpirit ? 330 : 196;
      osc.frequency.setValueAtTime(f0, now);
      osc.frequency.exponentialRampToValueAtTime(f1, now + 0.52);

      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.linearRampToValueAtTime(0.036, now + 0.08);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.54);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.56);
    } catch {
      /* Audio playback is purely optional. */
    }
  }

  function stopLabTone() {
    if (labTimer) {
      clearTimeout(labTimer);
      labTimer = null;
    }
    if (labOsc && labGain && ctx) {
      try {
        const now = ctx.currentTime;
        labGain.gain.setTargetAtTime(0.0001, now, 0.04);
        labOsc.stop(now + 0.12);
      } catch {
        /* Already stopped. */
      }
    }
    labOsc = null;
    labGain = null;
  }

  async function playLabTone(freqHz, durationMs = 4500) {
    stopLabTone();
    if (!ensureGraph()) return false;
    if (ctx.state === 'suspended') {
      await ctx.resume().catch(() => {});
    }
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(Math.max(15, Math.min(880, Number(freqHz) || 44)), now);
      // Scale amplitude gently for very low frequencies so transducers don't click.
      const amp = freqHz < 24 ? 0.04 : freqHz < 55 ? 0.065 : 0.045;
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.linearRampToValueAtTime(amp, now + 0.08);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      labOsc = osc;
      labGain = gain;
      labTimer = setTimeout(() => stopLabTone(), durationMs);
      return true;
    } catch {
      return false;
    }
  }

  return {
    isEnabled: () => enabled,
    setEnabled,
    setDepth,
    playRipple,
    playCross,
    playLabTone,
    stopLabTone,
  };
}
