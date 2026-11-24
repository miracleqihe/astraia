import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { LifeEntry, LifeSubject } from '../life';
import { LIFE_PALETTES, lifeGalaxyLayout } from './lifeGalaxyLayout';
import { animateLifeGravity, createLifeGravity } from './lifeGravity';
import { createLifeMotion } from './lifeMotion';
import { lifeStardust } from './lifeStardust';
import { createLifeGalaxyLabels } from './lifeGalaxyLabels';
import { createLifePortal } from './lifePortal';
import { lifeArcPoint, sampleLifeTrace } from './lifeArcs';
import type { LifeDrawing, LifeHover } from './lifeSceneTypes';

type Layout = ReturnType<typeof lifeGalaxyLayout>;

/** CPU rasterizer for browsers without hardware WebGL; uses the same camera and node positions. */
export function mountLifeSoftware(host: HTMLDivElement, entries: LifeEntry[], subjects: LifeSubject[], layout: Layout,
  onSelect: (id: string) => void, onSubject: (id: string) => void, onVolume: (id: string) => void, onHover: (hover: LifeHover | null) => void): LifeDrawing {
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
  const labels = createLifeGalaxyLabels(host, layout, subjects, onVolume, onSubject);
  const portal = createLifePortal(host, entries, layout, onSelect);
  let labelsVisible = true, labelVolume: string | null = null, labelSubject: string | null = null, labelSelected = false;
  controls.enableDamping = true; controls.dampingFactor = .08;
  controls.minDistance = 110; controls.maxDistance = 1800; controls.enablePan = true;

  const hubPositions = new Float32Array(subjects.length * 3);
  const dust = lifeStardust(layout, 1200);
  const dustBase = dust.positions.slice();
  const dustColors = new Uint32Array(1200);
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
  for (let i = 0; i < dustColors.length; i++) dustColors[i] = rgb(
    Math.round(dust.colors[i * 3] * 255), Math.round(dust.colors[i * 3 + 1] * 255), Math.round(dust.colors[i * 3 + 2] * 255));
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
  const volumeCss = layout.volumes.map((_, index) => [1, .45, .22].map((factor) => {
    color.set(LIFE_PALETTES[index % LIFE_PALETTES.length]).multiplyScalar(factor);
    return `#${color.getHexString()}`;
  }));
  const entryVolumes = entries.map((entry) => layout.volumes.indexOf(entry.volume));
  entries.forEach((entry, i) => {
    const [full, focus, subject] = volumeColors[layout.volumes.indexOf(entry.volume)];
    fullColors[i] = full; focusColors[i] = focus; subjectColors[i] = subject;
  });
  const nodeSize = entries.map((entry) => Math.min(2.6, 1.5 + Math.log2(1 + entry.links.length + (incoming.get(entry.id)?.length ?? 0)) * .22));
  const background = rgb(4, 6, 12), guideColor = rgb(43, 49, 56), dimGuideColor = rgb(13, 16, 23), hubColor = rgb(210, 176, 113);
  const lineColor = rgb(174, 146, 93), selectedColor = rgb(255, 233, 189);
  let image: ImageData | null = null;
  let pixels = new Uint32Array();
  let width = 1, height = 1;
  let pixelRatio = 1;
  let projectedX = 0, projectedY = 0;
  let focus: THREE.Vector3 | null = null;
  let focusDirection: THREE.Vector3 | null = null;
  let focusDistance = 0;
  let selectedPoint: THREE.Vector3 | undefined, activeVolume: string | null = null;
  let edges: THREE.Vector3[] = [];
  // Reuse the flight vectors on every frame to avoid creating temporary
  // objects during long camera animations on software-rendered devices.
  const focusDelta = new THREE.Vector3(), focusBearing = new THREE.Vector3();
  const arcPoint = new THREE.Vector3();
  let frame = 0;
  let lastFrame = 0;
  let interacting = false;
  let dragging = false;
  let restoreQuality = 0;
  let drawCount = 0;
  const motion = createLifeMotion(entries, layout);
  let motionEnabled = false, motionTimer = 0, motionLast = 0, disposed = false;

  function ambientTick() {
    motionTimer = 0;
    if (!motionEnabled || disposed || document.hidden) { motionLast = 0; return; }
    const now = performance.now();
    if (!dragging && !interacting && !focus && !gravity.active()) {
      if (motionLast) {
        motion.advance((now - motionLast) / 1000);
        motion.transformDust(dust.positions, dustBase, dust.groups);
        subjects.forEach((subject, index) => layout.centers.get(subject.id)?.toArray(hubPositions, index * 3));
        schedule();
      }
      motionLast = now;
    } else motionLast = 0;
    motionTimer = window.setTimeout(ambientTick, 90);
  }
  function setMotion(enabled: boolean) {
    motionEnabled = enabled; motionLast = 0;
    window.clearTimeout(motionTimer); motionTimer = 0;
    if (enabled && !document.hidden && !disposed) motionTimer = window.setTimeout(ambientTick, 90);
  }
  const visibility = () => setMotion(motionEnabled);
  document.addEventListener('visibilitychange', visibility);

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
  // On high-DPR software canvases, batch vector paths directly into Skia.
  // This avoids transferring a full multi-megabyte ImageData on every drag.
  function drawVector() {
    ctx.fillStyle = '#04060c'; ctx.fillRect(0, 0, width, height);
    nodeHeads.fill(-1); hubHeads.fill(-1);
    camera.updateMatrixWorld(); projection.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    if (!interacting) {
      ctx.fillStyle = 'rgba(190,190,190,.2)'; ctx.beginPath();
      for (let i = 0; i < dustColors.length; i++) {
        if (project(dust.positions[i * 3], dust.positions[i * 3 + 1], dust.positions[i * 3 + 2])) ctx.rect(projectedX, projectedY, 1, 1);
      }
      ctx.fill();
    }
    ctx.lineWidth = 1;
    for (const group of layout.structuralEdges) {
      ctx.strokeStyle = activeVolume && group.volume !== activeVolume ? 'rgba(212,175,55,.025)' : 'rgba(212,175,55,.16)';
      ctx.beginPath();
      for (let i = 0; i < group.points.length; i += interacting ? 4 : 2) {
        const a = group.points[i], b = group.points[i + 1];
        if (!project(a.x, a.y, a.z)) continue;
        const x = projectedX, y = projectedY;
        if (project(b.x, b.y, b.z)) { ctx.moveTo(x, y); ctx.lineTo(projectedX, projectedY); }
      }
      ctx.stroke();
    }
    ctx.strokeStyle = 'rgba(226,190,124,.7)'; ctx.beginPath();
    for (let i = 0; i < edges.length; i += 2) {
      const a = edges[i], b = edges[i + 1]; let haveLast = false;
      for (let step = 0; step <= 10; step++) {
        lifeArcPoint(a, b, step / 10, arcPoint);
        if (project(arcPoint.x, arcPoint.y, arcPoint.z)) {
          if (haveLast) ctx.lineTo(projectedX, projectedY); else ctx.moveTo(projectedX, projectedY);
          haveLast = true;
        } else haveLast = false;
      }
    }
    ctx.stroke();
    const batches = Array.from({ length: layout.volumes.length * 3 }, () => new Path2D());
    const hardCores = new Path2D();
    for (let i = 0; i < entries.length; i++) {
      if (!project(layout.positions[i * 3], layout.positions[i * 3 + 1], layout.positions[i * 3 + 2])) { nodeScreen[i * 2] = NaN; continue; }
      const x = projectedX, y = projectedY;
      indexScreen(nodeScreen, nodeHeads, nodeNext, i, x / width, y / height);
      if (!Number.isFinite(nodeScreen[i * 2])) continue;
      const level = colors[i] === fullColors[i] ? 0 : colors[i] === focusColors[i] ? 1 : 2;
      const size = Math.max(2, Math.round(nodeSize[i] * pixelRatio));
      batches[entryVolumes[i] * 3 + level].rect(x, y, size, size);
      if (level === 0) hardCores.rect(x + Math.floor(size / 2), y + Math.floor(size / 2), 1, 1);
    }
    for (let volume = 0; volume < layout.volumes.length; volume++) for (let level = 0; level < 3; level++) {
      ctx.fillStyle = volumeCss[volume][level]; ctx.fill(batches[volume * 3 + level]);
    }
    ctx.fillStyle = '#fffdf7'; ctx.fill(hardCores);
    const brightGuides = new Path2D(), dimGuides = new Path2D();
    for (let i = 0; i < subjects.length; i++) {
      if (!project(hubPositions[i * 3], hubPositions[i * 3 + 1], hubPositions[i * 3 + 2])) { hubScreen[i * 2] = NaN; continue; }
      const x = projectedX, y = projectedY, r = 3 * pixelRatio;
      indexScreen(hubScreen, hubHeads, hubNext, i, x / width, y / height);
      const path = activeVolume && subjects[i].volume !== activeVolume ? dimGuides : brightGuides;
      path.moveTo(x-r, y); path.lineTo(x+r, y); path.moveTo(x, y-r); path.lineTo(x, y+r);
    }
    for (const volume of layout.volumes) {
      const center = layout.volumeCenters.get(volume);
      if (!center || !project(center.x, center.y, center.z)) continue;
      const x = projectedX, y = projectedY, r = 8 * pixelRatio;
      const path = activeVolume && volume !== activeVolume ? dimGuides : brightGuides;
      path.moveTo(x-r, y); path.lineTo(x+r, y); path.moveTo(x, y-r); path.lineTo(x, y+r);
    }
    ctx.strokeStyle = '#e2c28c'; ctx.stroke(brightGuides);
    ctx.strokeStyle = 'rgba(226,194,140,.2)'; ctx.stroke(dimGuides);
    ctx.fillStyle = '#fffdf7'; ctx.beginPath();
    for (const volume of layout.volumes) {
      const center = layout.volumeCenters.get(volume);
      if ((!activeVolume || volume === activeVolume) && center && project(center.x, center.y, center.z))
        ctx.rect(projectedX-pixelRatio, projectedY-pixelRatio, 2*pixelRatio, 2*pixelRatio);
    }
    if (selectedPoint && project(selectedPoint.x, selectedPoint.y, selectedPoint.z))
      ctx.rect(projectedX-2*pixelRatio, projectedY-2*pixelRatio, 4*pixelRatio, 4*pixelRatio);
    if (motionEnabled) for (let i = 0; i < edges.length; i += 2) {
      lifeArcPoint(edges[i], edges[i+1], (performance.now() / 5200 + i * .091) % 1, arcPoint);
      if (project(arcPoint.x, arcPoint.y, arcPoint.z)) ctx.rect(projectedX, projectedY, 2*pixelRatio, 2*pixelRatio);
    }
    ctx.fill();
    finishDraw();
  }
  function finishDraw() {
    labels.update(camera, labelsVisible, labelVolume, labelSubject, labelSelected);
    const portalPoint = portal.point();
    if (portalPoint && project(portalPoint.x, portalPoint.y, portalPoint.z))
      portal.position(projectedX / width * host.clientWidth + 10, projectedY / height * host.clientHeight + 10,
        projectedX >= 0 && projectedX <= width && projectedY >= 0 && projectedY <= height);
    else portal.position(0, 0, false);
  }
  function draw() {
    if (!image) return;
    if (pixelRatio > 1) { drawVector(); return; }
    const started = import.meta.env.DEV ? performance.now() : 0;
    pixels.fill(background);
    nodeHeads.fill(-1); hubHeads.fill(-1);
    camera.updateMatrixWorld();
    projection.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    for (let i = 0; i < dustColors.length; i++) {
      if (project(dust.positions[i * 3], dust.positions[i * 3 + 1], dust.positions[i * 3 + 2])) pixel(projectedX, projectedY, dustColors[i]);
    }
    for (const volume of layout.volumes) {
      const center = layout.volumeCenters.get(volume);
      if (!center || !project(center.x, center.y, center.z)) continue;
      const x = projectedX, y = projectedY;
      const dim = !!activeVolume && volume !== activeVolume;
      for (let k = -Math.round(9 * pixelRatio); k <= Math.round(9 * pixelRatio); k++) { pixel(x + k, y, dim ? dimGuideColor : guideColor); pixel(x, y + k, dim ? dimGuideColor : guideColor); }
      for (let k = -Math.round(4 * pixelRatio); k <= Math.round(4 * pixelRatio); k++) { pixel(x + k, y, dim ? guideColor : hubColor); pixel(x, y + k, dim ? guideColor : hubColor); }
      const core = Math.max(1, Math.round(pixelRatio));
      for (let dy = -core; dy <= core; dy++) for (let dx = -core; dx <= core; dx++) pixel(x + dx, y + dy, dim ? guideColor : selectedColor);
    }
    for (const group of layout.structuralEdges) for (let i = 0; i < group.points.length; i += 2) {
      const a = group.points[i], b = group.points[i + 1];
      if (!project(a.x, a.y, a.z)) continue;
      const x = projectedX, y = projectedY;
      if (project(b.x, b.y, b.z)) line(x, y, projectedX, projectedY,
        activeVolume && group.volume !== activeVolume ? dimGuideColor : guideColor);
    }
    if (project(0, 0, 0)) {
      const x = projectedX, y = projectedY;
      for (let k = -2; k <= 2; k++) { pixel(x + k, y, selectedColor); pixel(x, y + k, selectedColor); }
    }
    for (let i = 0; i < edges.length; i += 2) {
      const a = edges[i], b = edges[i + 1];
      let lastX = 0, lastY = 0, haveLast = false;
      for (let step = 0; step <= 10; step++) {
        lifeArcPoint(a, b, step / 10, arcPoint);
        if (project(arcPoint.x, arcPoint.y, arcPoint.z)) {
          if (haveLast) line(lastX, lastY, projectedX, projectedY, lineColor);
          lastX = projectedX; lastY = projectedY; haveLast = true;
        } else haveLast = false;
      }
    }
    if (motionEnabled) for (let i = 0; i < edges.length; i += 2) {
      const a = edges[i], b = edges[i + 1], progress = (performance.now() / 5200 + i * .091) % 1;
      lifeArcPoint(a, b, progress, arcPoint);
      if (project(arcPoint.x, arcPoint.y, arcPoint.z)) {
        pixel(projectedX, projectedY, selectedColor); pixel(projectedX + 1, projectedY, selectedColor);
      }
    }
    for (let i = 0; i < entries.length; i++) {
      if (!project(layout.positions[i * 3], layout.positions[i * 3 + 1], layout.positions[i * 3 + 2])) {
        nodeScreen[i * 2] = NaN;
        continue;
      }
      const x = projectedX, y = projectedY, color = colors[i];
      indexScreen(nodeScreen, nodeHeads, nodeNext, i, x / width, y / height);
      const size = Math.max(2, Math.round(nodeSize[i] * pixelRatio));
      for (let dy = 0; dy < size; dy++) for (let dx = 0; dx < size; dx++) pixel(x + dx, y + dy, color);
      if (color === fullColors[i]) pixel(x + Math.floor(size / 2), y + Math.floor(size / 2), selectedColor);
    }
    for (let i = 0; i < subjects.length; i++) {
      if (!project(hubPositions[i * 3], hubPositions[i * 3 + 1], hubPositions[i * 3 + 2])) {
        hubScreen[i * 2] = NaN;
        continue;
      }
      const x = projectedX, y = projectedY;
      indexScreen(hubScreen, hubHeads, hubNext, i, x / width, y / height);
      const size = Math.max(3, Math.round(3 * pixelRatio));
      const dim = !!activeVolume && subjects[i].volume !== activeVolume;
      for (let k = -size; k <= size; k++) { pixel(x + k, y, dim ? guideColor : hubColor); pixel(x, y + k, dim ? guideColor : hubColor); }
      pixel(x, y, dim ? guideColor : selectedColor);
    }
    if (selectedPoint && project(selectedPoint.x, selectedPoint.y, selectedPoint.z)) {
      const x = projectedX, y = projectedY;
      for (let j = -2; j <= 2; j++) for (let i = -2; i <= 2; i++) pixel(x + i, y + j, selectedColor);
    }
    ctx.putImageData(image, 0, 0);
    finishDraw();
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
    // Preserve physical-pixel sharpness in both idle and interaction states.
    const scale = Math.min(window.devicePixelRatio || 1, 2);
    pixelRatio = scale;
    const nextWidth = Math.max(1, Math.round(cssWidth * scale));
    const nextHeight = Math.max(1, Math.round(cssHeight * scale));
    if (nextWidth !== width || nextHeight !== height || !image) {
      width = nextWidth; height = nextHeight;
      canvas.width = width; canvas.height = height;
      image = ctx.createImageData(width, height); pixels = new Uint32Array(image.data.buffer);
    }
    camera.aspect = cssWidth / cssHeight;
    if (cssWidth > 760) camera.setViewOffset(cssWidth, cssHeight, Math.round(cssWidth * .06), 0, cssWidth, cssHeight);
    else camera.clearViewOffset();
    camera.updateProjectionMatrix(); schedule();
  };
  // A moving divider or an animated browser resize can otherwise allocate and
  // upload a full-resolution image on every resize notification. Use the
  // same bounded raster as a camera drag while the viewport is changing,
  // then restore the detailed image once its dimensions have settled.
  let observedWidth = host.clientWidth, observedHeight = host.clientHeight;
  const observer = new ResizeObserver(() => {
    const nextWidth = host.clientWidth, nextHeight = host.clientHeight;
    if (nextWidth === observedWidth && nextHeight === observedHeight) return;
    observedWidth = nextWidth; observedHeight = nextHeight;
    if (interacting) resize(); else beginMotion();
    if (!dragging && !focus) {
      window.clearTimeout(restoreQuality); restoreQuality = 0;
      restoreWhenStill();
    }
  });
  observer.observe(host); resize();
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
  const gravity = createLifeGravity(entries, layout);
  const gravityAnimation = animateLifeGravity(gravity, schedule);
  let gravityTimer = 0, gravityHeld = false;
  const restoreGravity = () => {
    window.clearTimeout(gravityTimer); gravityTimer = 0;
    if (gravityHeld) { gravityHeld = false; gravityAnimation.release(); }
  };
  const move = (event: PointerEvent) => {
    if (event.buttons) {
      if (Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) restoreGravity();
      return;
    }
    pendingHover = { clientX: event.clientX, clientY: event.clientY, offsetX: event.offsetX, offsetY: event.offsetY };
    if (!hoverFrame) hoverFrame = requestAnimationFrame(processHover);
  };
  let down = { x: 0, y: 0 };
  const pointerDown = (event: PointerEvent) => {
    focus = null; dragging = true; down = { x: event.clientX, y: event.clientY };
    pendingHover = null; clearHover(); beginMotion();
    const target = hit(event);
    if (target?.kind === 'node') gravityTimer = window.setTimeout(() => {
      const id = entries[target.index].id; gravityHeld = true; gravityAnimation.pull(id); onSelect(id); schedule();
    }, 480);
  };
  const pointerUp = (event: PointerEvent) => {
    dragging = false; restoreWhenStill();
    const wasHeld = gravityHeld; restoreGravity();
    if (wasHeld) return;
    if (Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) return;
    const target = hit(event);
    if (target?.kind === 'hub') onSubject(subjects[target.index].id);
    else if (target) onSelect(entries[target.index].id);
  };
  const pointerCancel = () => {
    dragging = false; restoreGravity(); restoreWhenStill();
  };
  const leave = () => { pendingHover = null; clearHover(); };
  canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerdown', pointerDown);
  canvas.addEventListener('pointerup', pointerUp); canvas.addEventListener('pointercancel', pointerCancel);
  canvas.addEventListener('pointerleave', leave);
  let lastFocus = '';
  return {
    update(selected, subject, highlights, connectHighlights = true, volume = null) {
      labelsVisible = !selected && !subject && !volume;
      labelVolume = volume; labelSubject = subject; labelSelected = !!selected;
      portal.select(selected);
      const chosen = selected ? entryById.get(selected) : undefined;
      activeVolume = volume ?? subjects.find((item) => item.id === subject)?.volume ?? chosen?.volume ?? null;
      const related = new Set(chosen?.links ?? []);
      const matched = new Set(highlights);
      if (chosen) for (const id of incoming.get(chosen.id) ?? []) related.add(id);
      entries.forEach((entry, i) => {
        colors[i] = subject && entry.subject !== subject || volume && entry.volume !== volume ? subjectColors[i]
          : selected && entry.id !== selected && !related.has(entry.id) ? focusColors[i]
          : !selected && matched.size && !matched.has(entry.id) ? subjectColors[i] : fullColors[i];
      });
      selectedPoint = selected ? layout.locations.get(selected) : undefined;
      edges = [];
      if (selectedPoint) for (const id of related) {
        const target = layout.locations.get(id);
        if (target) edges.push(selectedPoint, target);
      }
      if (!selectedPoint && connectHighlights && highlights.length > 1) {
        const trace = sampleLifeTrace(entries, highlights);
        for (let index = 1; index < trace.length; index++) {
          const a = layout.locations.get(trace[index - 1]), b = layout.locations.get(trace[index]);
          if (a && b) edges.push(a, b);
        }
      }
      const target = selectedPoint ?? (subject ? layout.centers.get(subject) : volume ? layout.volumeCenters.get(volume) : undefined);
      const key = selected ? `entry:${selected}` : subject ? `subject:${subject}` : volume ? `volume:${volume}` : '';
      if (target && key !== lastFocus) fly(target, selectedPoint ? 285 : subject ? 390 : 590);
      else if (!target && lastFocus) { focus = null; schedule(); } else schedule();
      lastFocus = key;
    },
    setMotion,
    reset() { fly(new THREE.Vector3(), 1165, overviewDirection); },
    dispose() {
      disposed = true; setMotion(false); document.removeEventListener('visibilitychange', visibility);
      labels.dispose(); portal.dispose();
      restoreGravity(); gravityAnimation.dispose(); cancelAnimationFrame(frame); cancelAnimationFrame(hoverFrame); window.clearTimeout(restoreQuality);
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
