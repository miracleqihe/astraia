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

/** A lightweight 2D projection of the same real nodes and bridge geometry. */
function makeSoftwareRenderer() {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
  if (!ctx) throw new Error('浏览器无法创建星图画布。');
  canvas.dataset.renderer = 'software';
  let width = 1, height = 1, ratio = 1;
  const mvp = new THREE.Matrix4(), projected = new THREE.Vector3();
  function screen(point, matrix) {
    projected.copy(point).applyMatrix4(matrix);
    return [width * (projected.x + 1) / 2, height * (1 - projected.y) / 2, projected.z];
  }
  function render(scene, camera) {
    scene.updateMatrixWorld(); camera.updateMatrixWorld(); camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.fillStyle = '#04060b'; ctx.fillRect(0, 0, width, height);
    scene.traverseVisible(object => {
      if (!object.geometry || !object.material) return;
      const position = object.geometry.getAttribute('position');
      if (!position) return;
      mvp.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).multiply(object.matrixWorld);
      if (object.isPoints) {
        const colors = object.geometry.getAttribute('aColor'), sizes = object.geometry.getAttribute('aSize');
        const spikes = object.geometry.getAttribute('aSpike'), highlights = object.geometry.getAttribute('aHighlight');
        const e = mvp.elements, arr = position.array, stride = object.userData.softwareStride ?? 1;
        const localEye = object.userData.geoOcclusion ? object.worldToLocal(camera.getWorldPosition(new THREE.Vector3())) : null;
        let cache = object.userData.softwareColors;
        if (colors && (!cache || cache.version !== colors.version || cache.stride !== stride)) {
          const styles = new Array(position.count);
          for (let i = 0; i < position.count; i += stride) {
            const r = Math.round(Math.sqrt(Math.max(0,colors.getX(i)))*255);
            const g = Math.round(Math.sqrt(Math.max(0,colors.getY(i)))*255);
            const b = Math.round(Math.sqrt(Math.max(0,colors.getZ(i)))*255);
            styles[i] = `rgb(${r},${g},${b})`;
          }
          cache = object.userData.softwareColors = { version:colors.version, stride, styles };
        }
        let lastStyle = '', lastAlpha = -1;
        for (let i = 0; i < position.count; i += stride) {
          const h = highlights ? highlights.getX(i) : 1;
          if (h < 0) continue;
          const j = i * 3, x = arr[j], y = arr[j+1], z = arr[j+2];
          if (localEye && x * localEye.x + y * localEye.y + z * localEye.z <= 165 * 165) continue;
          const w = e[3]*x + e[7]*y + e[11]*z + e[15];
          if (w <= 0) continue;
          const px = (e[0]*x + e[4]*y + e[8]*z + e[12]) / w;
          const py = (e[1]*x + e[5]*y + e[9]*z + e[13]) / w;
          const pz = (e[2]*x + e[6]*y + e[10]*z + e[14]) / w;
          if (Math.abs(px) > 1.04 || Math.abs(py) > 1.04 || pz < -1 || pz > 1) continue;
          const x2 = width*(px+1)/2, y2 = height*(1-py)/2;
          const size = Math.max(1, Math.min(5, (sizes?.getX(i) ?? 2) * 180 / w));
          const alpha = Math.max(.07, Math.min(1,h*.82)), style = colors ? cache.styles[i] : 'rgb(230,220,205)';
          if (alpha !== lastAlpha) { ctx.globalAlpha=alpha; lastAlpha=alpha; }
          if (style !== lastStyle) { ctx.fillStyle=style; lastStyle=style; }
          ctx.fillRect(x2-size/2, y2-size/2, size, size);
          if ((spikes?.getX(i) ?? 0) > .6 && h > .4) {
            ctx.globalAlpha = Math.min(1,h); ctx.fillStyle='#fff8e6'; lastAlpha=ctx.globalAlpha; lastStyle='#fff8e6';
            ctx.fillRect(x2-1,y2-4,2,8);ctx.fillRect(x2-4,y2-1,8,2);
          }
        }
        ctx.globalAlpha = 1;
      } else if (object.isLine || object.isLineSegments) {
        const material = Array.isArray(object.material) ? object.material[0] : object.material;
        if (material.opacity <= .01) return;
        ctx.strokeStyle = `#${material.color?.getHexString() ?? 'd6b678'}`;
        ctx.globalAlpha = material.opacity; ctx.lineWidth = .7; ctx.beginPath();
        const point = new THREE.Vector3();
        for (let i = 0; i < position.count; i++) {
          point.fromBufferAttribute(position,i); const [x,y,z] = screen(point,mvp);
          if (z < -1 || z > 1) continue;
          if (object.isLineSegments ? i % 2 === 0 : i === 0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
        }
        ctx.stroke(); ctx.globalAlpha = 1;
      } else if (object.isSprite) {
        const [x,y,z] = screen(new THREE.Vector3(),mvp);
        if (z >= -1 && z <= 1) { ctx.globalAlpha=object.material.opacity;ctx.fillStyle='#e8d4a0';ctx.fillRect(x-2,y-2,4,4);ctx.globalAlpha=1; }
      }
    });
  }
  return {
    domElement: canvas, isSoftware: true, render,
    setPixelRatio(value) { ratio = Math.min(value || 1, 1.5); },
    setSize(w,h) { width=w;height=h;canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);canvas.style.width=`${w}px`;canvas.style.height=`${h}px`; },
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
