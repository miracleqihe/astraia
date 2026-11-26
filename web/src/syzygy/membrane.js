import { isBeyondMembrane, realmForDepth } from './realms.js';

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function rgbMix(c1, c2, t) {
  return [
    Math.round(lerp(c1[0], c2[0], t)),
    Math.round(lerp(c1[1], c2[1], t)),
    Math.round(lerp(c1[2], c2[2], t)),
  ];
}

function paletteForDepth(depth) {
  const stops = [
    { d: 0.0, rgb: [214, 182, 120] }, // 人：暖铜金
    { d: 0.5, rgb: [240, 215, 156] }, // 膜：朔望金辉
    { d: 1.0, rgb: [176, 198, 224] }, // 鬼：冷月银青
    { d: 2.0, rgb: [190, 194, 216] }, // 聻：古银月白
    { d: 3.0, rgb: [110, 198, 174] }, // 希：律动青玉
    { d: 4.0, rgb: [239, 233, 220] }, // 夷：悬置象牙光
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i], b = stops[i + 1];
    if (depth <= b.d) {
      const span = Math.max(0.001, b.d - a.d);
      return rgbMix(a.rgb, b.rgb, Math.max(0, Math.min(1, (depth - a.d) / span)));
    }
  }
  return stops[stops.length - 1].rgb;
}

/**
 * Undulating Membrane overlay canvas (works identically across WebGL and 2D Software fallback).
 * Visualizes the living barrier between Physis and Mythos, lens ripples under the cursor,
 * non-interference blocked waves when touching material controls from beyond the membrane,
 * and fourth-wall framing in Realm V (夷).
 */
export function createMembraneLayer({ canvas, whisperHost, reducedMotion = false, onCross = null }) {
  const ctx = canvas?.getContext('2d', { alpha: true }) ?? null;
  let width = 1, height = 1, ratio = 1;
  let targetDepth = 0.5;
  let curDepth = 0.5;
  let pointerX = -999, pointerY = -999, pointerActive = false;
  let lastPointerMoveMs = 0;
  let lastSoftwareFrame = 0;
  let lastMotionDirty = true;
  let hadPaint = false;
  const ripples = [];

  function resize(w, h, dpr = 1) {
    width = Math.max(1, w);
    height = Math.max(1, h);
    ratio = Math.min(dpr || 1, 1.5);
    if (canvas) {
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    }
    lastMotionDirty = true;
  }

  function spawnWhisper(x, y, text, colorCss) {
    if (!whisperHost || !text) return;
    while (whisperHost.children.length >= 3) {
      whisperHost.firstElementChild?.remove();
    }
    const el = document.createElement('div');
    el.className = 'membrane-whisper';
    const clampedX = Math.max(110, Math.min(width - 110, x || width * 0.5));
    const clampedY = Math.max(88, Math.min(height - 120, y || height * 0.5));
    el.style.left = `${clampedX}px`;
    el.style.top = `${clampedY}px`;
    if (colorCss) el.style.setProperty('--whisper-accent', colorCss);
    el.textContent = text;
    whisperHost.appendChild(el);
    setTimeout(() => {
      el.remove();
    }, 2200);
  }

  function triggerRipple(x, y, { kind = 'blocked', whisper = '', rgbOverride = null, intoSpirit = true } = {}) {
    const px = Number.isFinite(x) ? x : width * 0.5;
    const py = Number.isFinite(y) ? y : height * 0.5;
    const realm = realmForDepth(targetDepth);
    const rgb = rgbOverride || (kind === 'cross' ? [240, 215, 156] : paletteForDepth(targetDepth));
    ripples.push({
      x: px,
      y: py,
      bornAt: performance.now(),
      duration: kind === 'cross' ? (reducedMotion ? 420 : 1950) : 1450,
      maxR: kind === 'cross' ? Math.max(width, height) * 0.65 : 165,
      kind,
      rgb,
      intoSpirit,
    });
    if (ripples.length > 8) ripples.shift();
    lastMotionDirty = true;
    if (whisper) {
      spawnWhisper(px, py, whisper, realm.accentColor);
    }
  }

  function triggerCrossing(intoSpirit, origin = null) {
    const x = Number.isFinite(origin?.x) ? origin.x : width * 0.5;
    const y = Number.isFinite(origin?.y) ? origin.y : height * 0.5;
    triggerRipple(x, y, {
      kind: 'cross',
      rgbOverride: intoSpirit ? [216, 224, 236] : [240, 215, 156],
      intoSpirit,
    });
    onCross?.({ intoSpirit, x, y });
  }

  function setDepth(nextDepth, { silent = false, origin = null } = {}) {
    const clamped = Math.max(0, Math.min(4, Number(nextDepth) || 0));
    const previousDepth = targetDepth;
    const wasBeyond = isBeyondMembrane(targetDepth);
    const willBeBeyond = isBeyondMembrane(clamped);
    targetDepth = clamped;
    // The default .5 state sits on the surface: leaving it toward either side
    // should feel like a crossing, including slow drags of the depth slider.
    const crossedPhysicalLip = !wasBeyond && !willBeBeyond
      && ((previousDepth >= .30) !== (clamped >= .30));
    if (!silent && (wasBeyond !== willBeBeyond || crossedPhysicalLip)) {
      triggerCrossing(wasBeyond !== willBeBeyond ? willBeBeyond : clamped > previousDepth, origin);
    }
    lastMotionDirty = true;
  }

  function setPointer(x, y, active = true) {
    pointerX = x;
    pointerY = y;
    pointerActive = active;
    lastPointerMoveMs = performance.now();
    lastMotionDirty = true;
  }

  function drawInteractiveOverlay(t, rgb) {
    const beyond = isBeyondMembrane(curDepth);
    const pointerFresh = pointerActive && (performance.now() - lastPointerMoveMs < 3500);
    const [r, g, b] = rgb;
    let painted = false;

    // Cursor "Peephole Lens" on the membrane when beyond the threshold (隔膜窥镜)
    if (pointerFresh && beyond && curDepth < 3.6) {
      painted = true;
      const lensR = 26;
      ctx.save();
      ctx.strokeStyle = `rgba(${r},${g},${b},0.22)`;
      ctx.lineWidth = 0.85;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(pointerX, pointerY, lensR + Math.sin(t * 2.2) * 1.4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.strokeStyle = 'rgba(255, 245, 220, 0.12)';
      ctx.beginPath();
      ctx.arc(pointerX, pointerY, lensR * 0.55, t * 0.5, t * 0.5 + Math.PI * 1.35);
      ctx.stroke();
      ctx.restore();
    }

    // Fourth-Wall Observer Frame in Realm V (夷)
    if (curDepth >= 3.3) {
      painted = true;
      const yiFactor = Math.min(1, (curDepth - 3.3) / 0.7);
      const pad = 16;
      const corner = 24;
      ctx.save();
      ctx.strokeStyle = `rgba(239, 233, 220, ${(yiFactor * 0.38).toFixed(3)})`;
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      // NW
      ctx.moveTo(pad, pad + 52 + corner); ctx.lineTo(pad, pad + 52); ctx.lineTo(pad + corner, pad + 52);
      // NE
      ctx.moveTo(width - pad - corner, pad + 52); ctx.lineTo(width - pad, pad + 52); ctx.lineTo(width - pad, pad + 52 + corner);
      // SW
      ctx.moveTo(pad, height - pad - corner); ctx.lineTo(pad, height - pad); ctx.lineTo(pad + corner, height - pad);
      // SE
      ctx.moveTo(width - pad - corner, height - pad); ctx.lineTo(width - pad, height - pad); ctx.lineTo(width - pad, height - pad - corner);
      ctx.stroke();
      ctx.restore();
    }

    return painted;
  }

  function drawCrossingSurface(rp, u, isSoftware) {
    const ease = u * u * (3 - 2 * u);
    const envelope = Math.pow(Math.max(0, Math.sin(Math.PI * u)), .72) * (reducedMotion ? .18 : 1);
    const travel = rp.intoSpirit ? ease : 1 - ease;
    const radius = Math.max(5, rp.maxR * (.05 + travel));
    const [r, g, b] = rp.rgb;
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    const fill = ctx.createRadialGradient(rp.x, rp.y, radius * .2, rp.x, rp.y, Math.max(1, radius * 1.28));
    fill.addColorStop(0, `rgba(${r},${g},${b},0)`);
    fill.addColorStop(.63, `rgba(${r},${g},${b},${(envelope * (isSoftware ? .065 : .025)).toFixed(3)})`);
    fill.addColorStop(.87, `rgba(${r},${g},${b},${(envelope * (isSoftware ? .11 : .045)).toFixed(3)})`);
    fill.addColorStop(1, `rgba(${r},${g},${b},0)`);
    ctx.beginPath();
    for (let i = 0; i <= 72; i++) {
      const a = i / 72 * Math.PI * 2;
      const deformation = 1 + .052 * Math.sin(3 * a + u * 5) + .022 * Math.sin(6 * a - u * 3);
      const x = rp.x + Math.cos(a) * radius * 1.12 * deformation;
      const y = rp.y + Math.sin(a) * radius * .90 * deformation;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.lineWidth = 16 * envelope + 3;
    ctx.strokeStyle = `rgba(${r},${g},${b},${(envelope * (isSoftware ? .09 : .045)).toFixed(3)})`;
    ctx.stroke();
    const edge = ctx.createLinearGradient(rp.x - radius, rp.y - radius, rp.x + radius, rp.y + radius);
    edge.addColorStop(0, 'rgba(216,224,236,0)');
    edge.addColorStop(.28, `rgba(${r},${g},${b},${(envelope * .18).toFixed(3)})`);
    edge.addColorStop(.62, `rgba(240,215,156,${(envelope * .22).toFixed(3)})`);
    edge.addColorStop(1, 'rgba(240,215,156,0)');
    ctx.lineWidth = .7 + envelope;
    ctx.strokeStyle = edge;
    ctx.stroke();
    ctx.restore();
  }

  function drawRipples(nowMs, isSoftware) {
    for (let i = ripples.length - 1; i >= 0; i--) {
      const rp = ripples[i];
      const u = (nowMs - rp.bornAt) / rp.duration;
      if (u >= 1) {
        ripples.splice(i, 1);
        continue;
      }
      const ease = 1 - Math.pow(1 - u, 3);
      const fade = (1 - u) * (1 - u);
      const [r, g, b] = rp.rgb;
      if (rp.kind === 'cross') {
        drawCrossingSurface(rp, u, isSoftware);
        continue;
      }
      for (let ring = 0; ring < 3; ring++) {
        const radius = Math.max(2, ease * rp.maxR - ring * 18);
        if (radius <= 2) continue;
        const baseAlpha = rp.kind === 'cross' ? (0.48 - ring * 0.14) : (0.72 - ring * 0.18);
        ctx.beginPath();
        ctx.lineWidth = Math.max(0.6, (1.6 - ring * 0.4) * (1 - u * 0.4));
        ctx.strokeStyle = `rgba(${r},${g},${b},${Math.max(0.02, fade * baseAlpha).toFixed(3)})`;
        ctx.arc(rp.x, rp.y, radius, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }

  function render(nowMs, { isSoftware = false } = {}) {
    if (!ctx) return;
    const pointerFresh = pointerActive && (nowMs - lastPointerMoveMs < 3500);
    const lensActive = pointerFresh && isBeyondMembrane(curDepth) && curDepth < 3.6;
    const yiActive = curDepth >= 3.3;
    const depthSettling = Math.abs(curDepth - targetDepth) >= 0.005;
    const hasActivePaint = ripples.length > 0 || lensActive || yiActive;
    if (!lastMotionDirty && !hasActivePaint && !depthSettling && !hadPaint) return;
    if (isSoftware && nowMs - lastSoftwareFrame < 32 && !ripples.length) return;
    if (reducedMotion && !lastMotionDirty && !ripples.length && !depthSettling && !lensActive) {
      return;
    }
    lastSoftwareFrame = nowMs;
    lastMotionDirty = false;
    curDepth += (targetDepth - curDepth) * (reducedMotion ? 1 : 0.12);

    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    if (!hasActivePaint && Math.abs(curDepth - targetDepth) < 0.005) {
      hadPaint = false;
      return;
    }

    const t = reducedMotion ? 0 : nowMs * 0.001;
    const rgb = paletteForDepth(curDepth);
    const overlayPainted = drawInteractiveOverlay(t, rgb);
    const ripplesBefore = ripples.length;
    drawRipples(nowMs, isSoftware);
    hadPaint = overlayPainted || ripplesBefore > 0;
  }

  return {
    resize,
    setDepth,
    setPointer,
    triggerRipple,
    triggerCrossing,
    render,
    getDepth: () => targetDepth,
  };
}
