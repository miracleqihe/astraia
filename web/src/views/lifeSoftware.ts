import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { LifeEntry, LifeSubject } from '../life';
import { LIFE_PALETTES, lifeGalaxyLayout } from './lifeGalaxyLayout';
import type { LifeDrawing, LifeHover } from './lifeSceneTypes';

type Layout = ReturnType<typeof lifeGalaxyLayout>;

/** CPU rasterizer for browsers without hardware WebGL; uses the same camera and node positions. */
export function mountLifeSoftware(host: HTMLDivElement, entries: LifeEntry[], subjects: LifeSubject[], layout: Layout,
  onSelect: (id: string) => void, onSubject: (id: string) => void, onHover: (hover: LifeHover | null) => void): LifeDrawing {
  const canvas = document.createElement('canvas');
  // Permit low-latency canvas presentation when the browser supports it.
  const drawingContext = canvas.getContext('2d', { alpha: false, desynchronized: true });
  if (!drawingContext) throw new Error('无法创建知识星图画布');
  const ctx: CanvasRenderingContext2D = drawingContext;
  canvas.dataset.renderer = 'software';
  host.appendChild(canvas);
  const camera = new THREE.PerspectiveCamera(44, 1, 1, 4000);
  camera.position.set(0, -620, 985);
  const overviewDirection = camera.position.clone().normalize();
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true; controls.dampingFactor = .08;
  controls.minDistance = 110; controls.maxDistance = 1800; controls.enablePan = true;

  const hubPositions = new Float32Array(subjects.length * 3);
  subjects.forEach((subject, index) => layout.centers.get(subject.id)?.toArray(hubPositions, index * 3));
  // Reuse the screen projections from drawing for pointer hit tests.  This
  // avoids a second 3D traversal of the entire galaxy on every mouse move.
  const nodeScreen = new Float32Array(entries.length * 2);
  const hubScreen = new Float32Array(subjects.length * 2);
  nodeScreen.fill(NaN); hubScreen.fill(NaN);
  const gridSize = 32;
  const nodeHeads = new Int32Array(gridSize * gridSize), hubHeads = new Int32Array(gridSize * gridSize);
  nodeHeads.fill(-1); hubHeads.fill(-1);
  const nodeNext = new Int32Array(entries.length), hubNext = new Int32Array(subjects.length);
  let hitMarginX = 1, hitMarginY = 1;
  const gridCell = (x: number, y: number) => {
    const col = Math.max(0, Math.min(gridSize - 1, Math.floor(x * gridSize)));
    const row = Math.max(0, Math.min(gridSize - 1, Math.floor(y * gridSize)));
    return row * gridSize + col;
  };
  const indexScreen = (positions: Float32Array, heads: Int32Array, next: Int32Array,
    index: number, x: number, y: number) => {
    // Offscreen stars cannot be picked. Exclude them from the edge cells so
    // zooming into a dense galaxy does not turn an edge hover into a scan of
    // thousands of invisible stars. Keep a small margin for near-edge hits.
    if (x < -hitMarginX || x > 1 + hitMarginX || y < -hitMarginY || y > 1 + hitMarginY) {
      positions[index * 2] = NaN;
      return;
    }
    positions[index * 2] = x; positions[index * 2 + 1] = y;
    const cell = gridCell(x, y);
    next[index] = heads[cell]; heads[cell] = index;
  };
  const projection = new THREE.Matrix4();
  const colors = new Uint32Array(entries.length);
  const littleEndian = new Uint8Array(new Uint32Array([0x01020304]).buffer)[0] === 4;
  const rgb = (r: number, g: number, b: number) => littleEndian
    ? (0xff000000 | b << 16 | g << 8 | r) >>> 0 : (r << 24 | g << 16 | b << 8 | 255) >>> 0;
  // Selection changes frequently. Build the reverse links and the three
  // possible display colors once instead of recomputing them for every star
  // whenever a dossier or subject is selected.
  const entryById = new Map(entries.map((entry) => [entry.id, entry]));
  const incoming = new Map<string, string[]>();
  for (const entry of entries) for (const target of entry.links) {
    const sources = incoming.get(target);
    if (sources) sources.push(entry.id); else incoming.set(target, [entry.id]);
  }
  const fullColors = new Uint32Array(entries.length);
  const focusColors = new Uint32Array(entries.length);
  const subjectColors = new Uint32Array(entries.length);
  const color = new THREE.Color();
  const volumeColors = layout.volumes.map((_, index) => {
    const palette = LIFE_PALETTES[index % LIFE_PALETTES.length];
    return [1, .45, .22].map((factor) => {
      color.set(palette).multiplyScalar(factor);
      const value = color.getHex();
      return rgb(value >> 16 & 255, value >> 8 & 255, value & 255);
    });
  });
  entries.forEach((entry, i) => {
    const [full, focus, subject] = volumeColors[layout.volumes.indexOf(entry.volume)];
    fullColors[i] = full; focusColors[i] = focus; subjectColors[i] = subject;
  });
  const background = rgb(16, 23, 34), guideColor = rgb(43, 49, 56), hubColor = rgb(210, 176, 113);
  const lineColor = rgb(174, 146, 93), selectedColor = rgb(255, 233, 189);
  // These guides are fixed in world space; only their projection changes.
  const rings = [90, 200, 320, 445].map((radius) => {
    const coordinates = new Float32Array(129 * 3);
    for (let i = 0; i <= 128; i++) {
      const angle = i / 128 * Math.PI * 2;
      coordinates[i * 3] = Math.cos(angle) * radius;
      coordinates[i * 3 + 1] = Math.sin(angle) * radius;
      coordinates[i * 3 + 2] = -50;
    }
    return coordinates;
  });
  const guideEdges: THREE.Vector3[] = [];
  for (const volume of layout.volumes) {
    let previous = new THREE.Vector3();
    for (const subject of subjects) {
      if (subject.volume !== volume) continue;
      const next = layout.centers.get(subject.id);
      if (next) { guideEdges.push(previous, next); previous = next; }
    }
  }
  let image: ImageData | null = null;
  let pixels = new Uint32Array();
  let width = 1, height = 1;
  let projectedX = 0, projectedY = 0;
  let focus: THREE.Vector3 | null = null;
  let focusDirection: THREE.Vector3 | null = null;
  let focusDistance = 0;
  let selectedPoint: THREE.Vector3 | undefined;
  let edges: THREE.Vector3[] = [];
  // Reuse the flight vectors on every frame to avoid creating temporary
  // objects during long camera animations on software-rendered devices.
  const focusDelta = new THREE.Vector3(), focusBearing = new THREE.Vector3();
  let frame = 0;
  let lastFrame = 0;
  let interacting = false;
  let dragging = false;
  let restoreQuality = 0;
  let drawCount = 0;

  function schedule() { if (!frame) frame = requestAnimationFrame(render); }
  function beginMotion() {
    window.clearTimeout(restoreQuality); restoreQuality = 0;
    if (!interacting) { interacting = true; resize(); }
  }
  function restoreWhenStill() {
    if (!interacting || dragging || focus || restoreQuality) return;
    restoreQuality = window.setTimeout(() => {
      restoreQuality = 0;
      if (!dragging && !focus) { interacting = false; resize(); }
    }, 180);
  }
  function fly(target: THREE.Vector3, distance: number, direction: THREE.Vector3 | null = null) {
    focus = target.clone(); focusDistance = distance; focusDirection = direction; beginMotion(); schedule();
  }
  function project(x: number, y: number, z: number): boolean {
    const m = projection.elements;
    const divisor = m[3] * x + m[7] * y + m[11] * z + m[15];
    if (divisor <= .001) return false;
    const inverse = 1 / divisor;
    const depth = (m[2] * x + m[6] * y + m[10] * z + m[14]) * inverse;
    if (depth < -1 || depth > 1) return false;
    projectedX = Math.round(((m[0] * x + m[4] * y + m[8] * z + m[12]) * inverse + 1) * width / 2);
    projectedY = Math.round((1 - (m[1] * x + m[5] * y + m[9] * z + m[13]) * inverse) * height / 2);
    return true;
  }
  function pixel(x: number, y: number, color: number) {
    if (x >= 0 && x < width && y >= 0 && y < height) pixels[y * width + x] = color;
  }
  function line(x0: number, y0: number, x1: number, y1: number, color: number) {
    // Clip first so a line crossing the camera plane never causes an enormous loop.
    const dx0 = x1 - x0, dy0 = y1 - y0;
    let lo = 0, hi = 1;
    for (let side = 0; side < 4; side++) {
      const p = side === 0 ? -dx0 : side === 1 ? dx0 : side === 2 ? -dy0 : dy0;
      const q = side === 0 ? x0 : side === 1 ? width - 1 - x0 : side === 2 ? y0 : height - 1 - y0;
      if (p === 0) { if (q < 0) return; continue; }
      const t = q / p;
      if (p < 0) lo = Math.max(lo, t); else hi = Math.min(hi, t);
      if (lo > hi) return;
    }
    const endX = Math.round(x0 + hi * dx0), endY = Math.round(y0 + hi * dy0);
    x0 = Math.round(x0 + lo * dx0); y0 = Math.round(y0 + lo * dy0);
    const dx = Math.abs(endX - x0), sx = x0 < endX ? 1 : -1;
    const dy = -Math.abs(endY - y0), sy = y0 < endY ? 1 : -1;
    let error = dx + dy;
    for (;;) {
      pixel(x0, y0, color);
      if (x0 === endX && y0 === endY) break;
      const twice = error * 2;
      if (twice >= dy) { error += dy; x0 += sx; }
      if (twice <= dx) { error += dx; y0 += sy; }
    }
  }
  function draw() {
    if (!image) return;
    const started = import.meta.env.DEV ? performance.now() : 0;
    pixels.fill(background);
    nodeHeads.fill(-1); hubHeads.fill(-1);
    camera.updateMatrixWorld();
    projection.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    for (const ring of rings) {
      let lastX = 0, lastY = 0, haveLast = false;
      for (let i = 0; i <= 128; i++) {
        if (project(ring[i * 3], ring[i * 3 + 1], ring[i * 3 + 2])) {
          if (haveLast) line(lastX, lastY, projectedX, projectedY, guideColor);
          lastX = projectedX; lastY = projectedY; haveLast = true;
        } else haveLast = false;
      }
    }
    for (let i = 0; i < guideEdges.length; i += 2) {
      const a = guideEdges[i], b = guideEdges[i + 1];
      if (!project(a.x, a.y, a.z)) continue;
      const x = projectedX, y = projectedY;
      if (project(b.x, b.y, b.z)) line(x, y, projectedX, projectedY, guideColor);
    }
    if (project(0, 0, 0)) {
      const x = projectedX, y = projectedY;
      for (let k = -2; k <= 2; k++) { pixel(x + k, y, selectedColor); pixel(x, y + k, selectedColor); }
    }
    for (let i = 0; i < edges.length; i += 2) {
      const a = edges[i], b = edges[i + 1];
      if (!project(a.x, a.y, a.z)) continue;
      const x = projectedX, y = projectedY;
      if (project(b.x, b.y, b.z)) line(x, y, projectedX, projectedY, lineColor);
    }
    for (let i = 0; i < entries.length; i++) {
      if (!project(layout.positions[i * 3], layout.positions[i * 3 + 1], layout.positions[i * 3 + 2])) {
        nodeScreen[i * 2] = NaN;
        continue;
      }
      const x = projectedX, y = projectedY, color = colors[i];
      indexScreen(nodeScreen, nodeHeads, nodeNext, i, x / width, y / height);
      if (x >= 0 && x < width - 1 && y >= 0 && y < height - 1) {
        const index = y * width + x;
        pixels[index] = color; pixels[index + 1] = color;
        pixels[index + width] = color; pixels[index + width + 1] = color;
      }
    }
    for (let i = 0; i < subjects.length; i++) {
      if (!project(hubPositions[i * 3], hubPositions[i * 3 + 1], hubPositions[i * 3 + 2])) {
        hubScreen[i * 2] = NaN;
        continue;
      }
      const x = projectedX, y = projectedY;
      indexScreen(hubScreen, hubHeads, hubNext, i, x / width, y / height);
      for (let k = -3; k <= 3; k++) { pixel(x + k, y, hubColor); pixel(x, y + k, hubColor); }
    }
    if (selectedPoint && project(selectedPoint.x, selectedPoint.y, selectedPoint.z)) {
      const x = projectedX, y = projectedY;
      for (let j = -2; j <= 2; j++) for (let i = -2; i <= 2; i++) pixel(x + i, y + j, selectedColor);
    }
    ctx.putImageData(image, 0, 0);
    if (import.meta.env.DEV) {
      canvas.dataset.drawMs = String(performance.now() - started);
      canvas.dataset.drawCount = String(++drawCount);
    }
  }
  function render(now: number) {
    frame = 0;
    // Keep camera motion tied to elapsed time, not to the number of frames.
    // A software renderer may only present a few frames per second; without
    // this adjustment a one-second flight can take ten seconds on that device.
    // Allow up to a quarter-second of progress per frame so that very slow
    // software devices can still complete a focus flight in real time, while
    // bounding the jump after a suspended or backgrounded tab resumes.
    const elapsed = lastFrame ? Math.min(250, Math.max(0, now - lastFrame)) : 1000 / 60;
    lastFrame = now;
    const frames = elapsed / (1000 / 60);
    const easing = 1 - Math.pow(.9, frames);
    controls.dampingFactor = 1 - Math.pow(.92, frames);
    if (focus) {
      focusDelta.subVectors(focus, controls.target).multiplyScalar(easing);
      camera.position.add(focusDelta); controls.target.add(focusDelta);
      const distance = focusBearing.subVectors(camera.position, controls.target).length();
      const next = distance + (focusDistance - distance) * easing;
      focusBearing.multiplyScalar(1 / distance);
      if (focusDirection) focusBearing.lerp(focusDirection, easing).normalize();
      camera.position.copy(controls.target).addScaledVector(focusBearing, next);
      if (focusDelta.lengthSq() < .001 && Math.abs(next - focusDistance) < .1
        && (!focusDirection || focusBearing.dot(focusDirection) > .99999)) { focus = null; focusDirection = null; }
    }
    const moving = controls.update();
    draw();
    if (focus || moving) {
      if (restoreQuality) { window.clearTimeout(restoreQuality); restoreQuality = 0; }
      schedule();
    } else { lastFrame = 0; restoreWhenStill(); }
  }
  controls.addEventListener('change', schedule);
  controls.addEventListener('start', beginMotion);
  controls.addEventListener('end', restoreWhenStill);
  const resize = () => {
    const cssWidth = Math.max(1, host.clientWidth), cssHeight = Math.max(1, host.clientHeight);
    hitMarginX = 12 / cssWidth; hitMarginY = 12 / cssHeight;
    // Reduce raster cost for every kind of camera movement, then sharpen at rest.
    const scale = interacting ? .3 : .7;
    const nextWidth = Math.max(1, Math.round(cssWidth * scale));
    const nextHeight = Math.max(1, Math.round(cssHeight * scale));
    if (nextWidth !== width || nextHeight !== height || !image) {
      width = nextWidth; height = nextHeight;
      canvas.width = width; canvas.height = height;
      image = ctx.createImageData(width, height); pixels = new Uint32Array(image.data.buffer);
    }
    camera.aspect = cssWidth / cssHeight; camera.updateProjectionMatrix(); schedule();
  };
  const observer = new ResizeObserver(resize); observer.observe(host); resize();
  const hit = (event: Pick<PointerEvent, 'clientX' | 'clientY'>) => {
    const box = canvas.getBoundingClientRect();
    if (!box.width || !box.height) return null;
    const x = event.clientX - box.left, y = event.clientY - box.top;
    const nearest = (positions: Float32Array, heads: Int32Array, next: Int32Array, radius: number) => {
      let best = radius * radius, index = -1;
      const minX = Math.max(0, Math.floor((x - radius) / box.width * gridSize));
      const maxX = Math.min(gridSize - 1, Math.floor((x + radius) / box.width * gridSize));
      const minY = Math.max(0, Math.floor((y - radius) / box.height * gridSize));
      const maxY = Math.min(gridSize - 1, Math.floor((y + radius) / box.height * gridSize));
      for (let row = minY; row <= maxY; row++) for (let col = minX; col <= maxX; col++) {
        for (let i = heads[row * gridSize + col]; i >= 0; i = next[i]) {
          const dx = positions[i * 2] * box.width - x, dy = positions[i * 2 + 1] * box.height - y;
          const distance = dx * dx + dy * dy;
          if (distance < best) { best = distance; index = i; }
        }
      }
      return index;
    };
    const hub = nearest(hubScreen, hubHeads, hubNext, 10);
    if (hub >= 0) return { kind: 'hub' as const, index: hub };
    const node = nearest(nodeScreen, nodeHeads, nodeNext, 8);
    if (node >= 0) return { kind: 'node' as const, index: node };
    return null;
  };
  let hovered = '';
  let hoverFrame = 0;
  let hoverTimer = 0;
  let tooltipVisible = false;
  let pendingHover: { clientX: number; clientY: number; offsetX: number; offsetY: number } | null = null;
  const clearHover = () => {
    window.clearTimeout(hoverTimer); hoverTimer = 0;
    hovered = '';
    if (tooltipVisible) { tooltipVisible = false; onHover(null); }
  };
  const processHover = () => {
    hoverFrame = 0;
    const event = pendingHover; pendingHover = null;
    if (!event || dragging) return;
    const started = import.meta.env.DEV ? performance.now() : 0;
    const target = hit(event), key = target ? `${target.kind}:${target.index}` : '';
    if (import.meta.env.DEV) canvas.dataset.hitMs = String(performance.now() - started);
    canvas.style.cursor = target ? 'pointer' : 'grab';
    if (key !== hovered) {
      window.clearTimeout(hoverTimer); hoverTimer = 0;
      hovered = key;
      if (tooltipVisible) { tooltipVisible = false; onHover(null); }
      const title = target?.kind === 'hub' ? `学科 · ${subjects[target.index].title}`
        : target ? entries[target.index].title : '';
      // Avoid repainting the whole software-composited canvas as the pointer
      // races across a dense cluster; show the label once it briefly settles.
      if (target) hoverTimer = window.setTimeout(() => {
        hoverTimer = 0; tooltipVisible = true;
        onHover({ title, x: event.offsetX, y: event.offsetY });
      }, 60);
    }
  };
  const move = (event: PointerEvent) => {
    if (event.buttons) return;
    pendingHover = { clientX: event.clientX, clientY: event.clientY, offsetX: event.offsetX, offsetY: event.offsetY };
    if (!hoverFrame) hoverFrame = requestAnimationFrame(processHover);
  };
  let down = { x: 0, y: 0 };
  const pointerDown = (event: PointerEvent) => {
    focus = null; dragging = true; down = { x: event.clientX, y: event.clientY };
    pendingHover = null; clearHover(); beginMotion();
  };
  const pointerUp = (event: PointerEvent) => {
    dragging = false; restoreWhenStill();
    if (Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) return;
    const target = hit(event);
    if (target?.kind === 'hub') onSubject(subjects[target.index].id);
    else if (target) onSelect(entries[target.index].id);
  };
  const pointerCancel = () => {
    dragging = false; restoreWhenStill();
  };
  const leave = () => { pendingHover = null; clearHover(); };
  canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerdown', pointerDown);
  canvas.addEventListener('pointerup', pointerUp); canvas.addEventListener('pointercancel', pointerCancel);
  canvas.addEventListener('pointerleave', leave);
  return {
    update(selected, subject) {
      const chosen = selected ? entryById.get(selected) : undefined;
      const related = new Set(chosen?.links ?? []);
      if (chosen) for (const id of incoming.get(chosen.id) ?? []) related.add(id);
      entries.forEach((entry, i) => {
        colors[i] = subject && entry.subject !== subject ? subjectColors[i]
          : selected && entry.id !== selected && !related.has(entry.id) ? focusColors[i] : fullColors[i];
      });
      selectedPoint = selected ? layout.locations.get(selected) : undefined;
      edges = [];
      if (selectedPoint) for (const id of related) {
        const target = layout.locations.get(id);
        if (target) edges.push(selectedPoint, target);
      }
      const target = selectedPoint ?? (subject ? layout.centers.get(subject) : undefined);
      if (target) fly(target, selectedPoint ? 285 : 390); else { focus = null; schedule(); }
    },
    reset() { fly(new THREE.Vector3(), 1165, overviewDirection); },
    dispose() {
      cancelAnimationFrame(frame); cancelAnimationFrame(hoverFrame); window.clearTimeout(restoreQuality);
      window.clearTimeout(hoverTimer); observer.disconnect();
      controls.removeEventListener('change', schedule); controls.dispose();
      controls.removeEventListener('start', beginMotion); controls.removeEventListener('end', restoreWhenStill);
      canvas.removeEventListener('pointermove', move); canvas.removeEventListener('pointerdown', pointerDown);
      canvas.removeEventListener('pointerup', pointerUp); canvas.removeEventListener('pointercancel', pointerCancel);
      canvas.removeEventListener('pointerleave', leave);
      canvas.remove();
    },
  };
}
