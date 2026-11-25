import * as THREE from 'three';

async function probeGraphics() {
  if (typeof Worker === 'undefined' || typeof OffscreenCanvas === 'undefined') return 'unknown';
  return new Promise((resolve) => {
    let done = false, worker;
    const finish = value => { if (done) return; done = true; clearTimeout(timer); worker?.terminate(); resolve(value); };
    // Do not hold the first frame for a slow or unavailable graphics driver.
    const timer = setTimeout(() => finish('unknown'), 1200);
    try {
      worker = new Worker(new URL('../views/lifeGpuProbe.js', import.meta.url), { type: 'module' });
      worker.onmessage = event => finish(event.data);
      worker.onerror = () => finish('unknown');
      worker.postMessage(null);
    } catch { finish('unknown'); }
  });
}

/** Pre-render luminous star sprites so software fallback looks celestial instead of pixelated squares. */
function makeGlowStamp(r, g, b) {
  const c = document.createElement('canvas');
  c.width = 24; c.height = 24;
  const gctx = c.getContext('2d');
  const grad = gctx.createRadialGradient(12, 12, 0.4, 12, 12, 11.5);
  grad.addColorStop(0.0, 'rgba(255,252,244,1)');
  grad.addColorStop(0.24, `rgba(${r},${g},${b},0.92)`);
  grad.addColorStop(0.55, `rgba(${r},${g},${b},0.28)`);
  grad.addColorStop(1.0, 'rgba(0,0,0,0)');
  gctx.fillStyle = grad;
  gctx.fillRect(0, 0, 24, 24);
  return c;
}

/** A lightweight 2D projection of the same real nodes, coastlines, and bridge geometry. */
function makeSoftwareRenderer() {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
  if (!ctx) throw new Error('浏览器无法创建星图画布。');
  canvas.dataset.renderer = 'software';
  let width = 1, height = 1, ratio = 1;
  const mvp = new THREE.Matrix4(), projected = new THREE.Vector3();
  const stampCache = new Map();
  function stampFor(r, g, b) {
    const key = `${r >> 4}-${g >> 4}-${b >> 4}`;
    let stamp = stampCache.get(key);
    if (!stamp) {
      stamp = makeGlowStamp(r, g, b);
      stampCache.set(key, stamp);
    }
    return stamp;
  }
  const pulseStamp = makeGlowStamp(246, 224, 168);

  function screen(point, matrix) {
    projected.copy(point).applyMatrix4(matrix);
    return [width * (projected.x + 1) / 2, height * (1 - projected.y) / 2, projected.z];
  }
  function render(scene, camera) {
    scene.updateMatrixWorld(); camera.updateMatrixWorld(); camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const bg = ctx.createRadialGradient(width * 0.44, height * 0.5, 20, width * 0.46, height * 0.5, Math.max(width, height) * 0.72);
    bg.addColorStop(0, '#0a1021');
    bg.addColorStop(0.55, '#060a14');
    bg.addColorStop(1, '#04060d');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, width, height);

    scene.traverseVisible(object => {
      if (!object.geometry || !object.material) return;
      const position = object.geometry.getAttribute('position');
      if (!position) return;
      mvp.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).multiply(object.matrixWorld);
      if (object.isPoints) {
        const colors = object.geometry.getAttribute('aColor'), sizes = object.geometry.getAttribute('aSize');
        const spikes = object.geometry.getAttribute('aSpike'), highlights = object.geometry.getAttribute('aHighlight');
        const e = mvp.elements, arr = position.array, stride = object.userData.softwareStride ?? 1;
        const roundGlobePoints = object.material.uniforms?.uGlobeMode?.value > .5;
        const roundMarkers = roundGlobePoints && (object.userData.geographicMarkers || object.userData.globeAnchor);
        const localEye = object.userData.geoOcclusion ? object.worldToLocal(camera.getWorldPosition(new THREE.Vector3())) : null;
        let cache = object.userData.softwareColors;
        if (colors && (!cache || cache.version !== colors.version || cache.stride !== stride)) {
          const styles = new Array(position.count);
          const stamps = new Array(position.count);
          for (let i = 0; i < position.count; i += stride) {
            const r = Math.round(Math.sqrt(Math.max(0, colors.getX(i))) * 255);
            const g = Math.round(Math.sqrt(Math.max(0, colors.getY(i))) * 255);
            const b = Math.round(Math.sqrt(Math.max(0, colors.getZ(i))) * 255);
            styles[i] = `rgb(${r},${g},${b})`;
            stamps[i] = stampFor(r, g, b);
          }
          cache = object.userData.softwareColors = { version: colors.version, stride, styles, stamps };
        }
        let lastStyle = '', lastAlpha = -1;
        for (let i = 0; i < position.count; i += stride) {
          const h = highlights ? highlights.getX(i) : 1;
          if (h < 0) continue;
          const j = i * 3, x = arr[j], y = arr[j + 1], z = arr[j + 2];
          if (localEye && x * localEye.x + y * localEye.y + z * localEye.z <= 165 * 165) continue;
          const w = e[3] * x + e[7] * y + e[11] * z + e[15];
          if (w <= 0) continue;
          const px = (e[0] * x + e[4] * y + e[8] * z + e[12]) / w;
          const py = (e[1] * x + e[5] * y + e[9] * z + e[13]) / w;
          const pz = (e[2] * x + e[6] * y + e[10] * z + e[14]) / w;
          if (Math.abs(px) > 1.04 || Math.abs(py) > 1.04 || pz < -1 || pz > 1) continue;
          const x2 = width * (px + 1) / 2, y2 = height * (1 - py) / 2;
          const size = Math.max(1.2, Math.min(8.5, (sizes?.getX(i) ?? 2.5) * 195 / w));
          const alpha = Math.max(.08, Math.min(1, h * .88));
          const style = colors ? cache.styles[i] : 'rgb(230,220,205)';
          if (alpha !== lastAlpha) { ctx.globalAlpha = alpha; lastAlpha = alpha; }
          if (roundMarkers) {
            if (style !== lastStyle) { ctx.fillStyle = style; lastStyle = style; }
            ctx.beginPath(); ctx.arc(x2, y2, Math.max(1.4, size * 0.45), 0, Math.PI * 2); ctx.fill();
          } else if (colors && (size > 2.2 || (spikes?.getX(i) ?? 0) > 0.35)) {
            const d = size * 2.5;
            ctx.drawImage(cache.stamps[i], x2 - d / 2, y2 - d / 2, d, d);
          } else {
            if (style !== lastStyle) { ctx.fillStyle = style; lastStyle = style; }
            ctx.beginPath(); ctx.arc(x2, y2, Math.max(0.9, size * 0.42), 0, Math.PI * 2); ctx.fill();
          }
          if (!roundGlobePoints && (spikes?.getX(i) ?? 0) > .55 && h > .4) {
            const flare = Math.min(11, 4.5 + size * 0.85);
            ctx.globalAlpha = Math.min(0.95, h * 0.72);
            ctx.strokeStyle = '#fff5dc';
            ctx.lineWidth = 0.85;
            ctx.beginPath();
            ctx.moveTo(x2 - flare, y2); ctx.lineTo(x2 + flare, y2);
            ctx.moveTo(x2, y2 - flare); ctx.lineTo(x2, y2 + flare);
            ctx.stroke();
            lastAlpha = -1;
          }
        }
        ctx.globalAlpha = 1;
      } else if (object.isLine || object.isLineSegments) {
        const material = Array.isArray(object.material) ? object.material[0] : object.material;
        if (material.opacity <= .01) return;
        const localEye = object.userData.sphereCull ? object.worldToLocal(camera.getWorldPosition(new THREE.Vector3())) : null;
        const cullLimit = object.userData.sphereCullRadius ? object.userData.sphereCullRadius * object.userData.sphereCullRadius * 0.96 : 0;
        ctx.strokeStyle = object.userData.strokeColor || `#${material.color?.getHexString() ?? 'cfa962'}`;
        ctx.globalAlpha = material.opacity;
        ctx.lineWidth = object.userData.lineWidth ?? 0.8;
        ctx.beginPath();
        const point = new THREE.Vector3();
        if (object.isLineSegments) {
          const p2 = new THREE.Vector3();
          for (let i = 0; i < position.count; i += 2) {
            point.fromBufferAttribute(position, i); p2.fromBufferAttribute(position, i + 1);
            if (localEye && (point.dot(localEye) < cullLimit || p2.dot(localEye) < cullLimit)) continue;
            const [x1, y1, z1] = screen(point, mvp), [x2, y2, z2] = screen(p2, mvp);
            if (z1 < -1 || z1 > 1 || z2 < -1 || z2 > 1) continue;
            ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
          }
        } else {
          let penDown = false;
          for (let i = 0; i < position.count; i++) {
            point.fromBufferAttribute(position, i);
            if (localEye && point.dot(localEye) < cullLimit) { penDown = false; continue; }
            const [x, y, z] = screen(point, mvp);
            if (z < -1 || z > 1) { penDown = false; continue; }
            if (!penDown) { ctx.moveTo(x, y); penDown = true; } else ctx.lineTo(x, y);
          }
        }
        ctx.stroke(); ctx.globalAlpha = 1;
      } else if (object.isMesh && object.userData.globeShellRadius) {
        const radius = object.userData.globeShellRadius;
        const [cx, cy, cz] = screen(new THREE.Vector3(0, 0, 0), mvp);
        if (cz >= -1 && cz <= 1) {
          const camDist = camera.getWorldPosition(new THREE.Vector3()).distanceTo(object.getWorldPosition(new THREE.Vector3()));
          const fovRad = (camera.fov * Math.PI) / 180;
          const rPx = (radius / Math.max(1, Math.sqrt(Math.max(1, camDist * camDist - radius * radius)))) * (height / (2 * Math.tan(fovRad / 2)));
          if (rPx > 4 && rPx < Math.max(width, height) * 2) {
            const grad = ctx.createRadialGradient(cx - rPx * 0.28, cy - rPx * 0.26, rPx * 0.08, cx, cy, rPx);
            grad.addColorStop(0, '#101b32');
            grad.addColorStop(0.62, '#070d1b');
            grad.addColorStop(1, '#040710');
            ctx.beginPath();
            ctx.arc(cx, cy, rPx, 0, Math.PI * 2);
            ctx.fillStyle = grad;
            ctx.fill();
            ctx.lineWidth = 1.15;
            ctx.strokeStyle = 'rgba(207, 169, 98, 0.34)';
            ctx.stroke();
          }
        }
      } else if (object.isSprite) {
        const [x, y, z] = screen(new THREE.Vector3(), mvp);
        if (z >= -1 && z <= 1) {
          ctx.globalAlpha = object.material.opacity;
          ctx.drawImage(pulseStamp, x - 7, y - 7, 14, 14);
          ctx.globalAlpha = 1;
        }
      }
    });
  }
  return {
    domElement: canvas, isSoftware: true, render,
    setPixelRatio(value) { ratio = Math.min(value || 1, 1.5); },
    setSize(w, h) { width = w; height = h; canvas.width = Math.round(w * ratio); canvas.height = Math.round(h * ratio); canvas.style.width = `${w}px`; canvas.style.height = `${h}px`; },
  };
}

export async function createSyzygyRenderer() {
  const probe = await probeGraphics();
  if (probe === 'webgl') {
    try {
      const canvas = document.createElement('canvas');
      const options = { antialias: true, alpha: true, powerPreference: 'high-performance', failIfMajorPerformanceCaveat: true };
      const gl = canvas.getContext('webgl2', options);
      if (gl) {
        const debug = gl.getExtension('WEBGL_debug_renderer_info');
        const name = debug ? String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)) : '';
        if (!/swiftshader|llvmpipe|software|warp/i.test(name)) {
          const renderer = new THREE.WebGLRenderer({ canvas, context: gl, ...options });
          renderer.domElement.dataset.renderer = 'webgl';
          renderer.isSoftware = false;
          return renderer;
        }
        gl.getExtension('WEBGL_lose_context')?.loseContext();
      }
    } catch { /* Canvas rendering remains available. */ }
  }
  return makeSoftwareRenderer();
}
