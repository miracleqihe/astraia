import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { LifeEntry, LifeSubject } from '../life';
import { LIFE_PALETTES, lifeGalaxyLayout } from './lifeGalaxyLayout';
import { createLifeGravity } from './lifeGravity';
import { mountLifeSoftware } from './lifeSoftware';
import type { LifeDrawing, LifeHover } from './lifeSceneTypes';

interface Props {
  entries: LifeEntry[];
  subjects: LifeSubject[];
  selectedId: string | null;
  subjectId: string | null;
  highlightIds: readonly string[];
  resetSerial: number;
  onSelect: (id: string) => void;
  onSubject: (id: string) => void;
  onRenderer: (renderer: 'software' | 'webgl') => void;
}

export default function LifeScene({ entries, subjects, selectedId, subjectId, highlightIds, resetSerial, onSelect, onSubject, onRenderer }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const drawing = useRef<LifeDrawing | null>(null);
  const select = useRef(onSelect), selectSubject = useRef(onSubject);
  const [hover, setHover] = useState<LifeHover | null>(null);
  select.current = onSelect; selectSubject.current = onSubject;

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const layout = lifeGalaxyLayout(entries, subjects);
    let renderer: THREE.WebGLRenderer | null = null;
    let software = false;
    try {
      // Let the browser reject a severely slow context even when privacy
      // settings hide the unmasked renderer name. The Canvas2D path below is
      // tuned for those devices and keeps the galaxy interactive.
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, failIfMajorPerformanceCaveat: true });
      const gl = renderer.getContext(), debug = gl.getExtension('WEBGL_debug_renderer_info');
      const name = debug ? String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)) : '';
      software = /swiftshader|llvmpipe|software|warp/i.test(name);
    } catch { software = true; }
    if (software || !renderer) {
      renderer?.dispose();
      onRenderer('software');
      const fallback = mountLifeSoftware(element, entries, subjects, layout,
        (id) => select.current(id), (id) => selectSubject.current(id), setHover);
      drawing.current = fallback; fallback.update(selectedId, subjectId, highlightIds);
      return () => { fallback.dispose(); drawing.current = null; };
    }

    const webgl = renderer;
    onRenderer('webgl');
    webgl.setPixelRatio(Math.min(window.devicePixelRatio, 1.6)); webgl.setClearColor(0x04060c, 1);
    const canvas = webgl.domElement; canvas.dataset.renderer = 'webgl'; element.appendChild(canvas);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(44, 1, 1, 4000);
    camera.position.set(0, -620, 985);
    const overviewDirection = camera.position.clone().normalize();
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.dampingFactor = .08;
    controls.minDistance = 110; controls.maxDistance = 1800; controls.enablePan = true;

    const colors = new Float32Array(entries.length * 3);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(layout.positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const dotCanvas = document.createElement('canvas'); dotCanvas.width = dotCanvas.height = 32;
    const dotContext = dotCanvas.getContext('2d');
    if (!dotContext) throw new Error('无法创建星点纹理');
    const glow = dotContext.createRadialGradient(16, 16, 1, 16, 16, 15);
    glow.addColorStop(0, '#fff'); glow.addColorStop(.35, 'rgba(255,255,255,.9)');
    glow.addColorStop(1, 'rgba(255,255,255,0)');
    dotContext.fillStyle = glow; dotContext.fillRect(0, 0, 32, 32);
    const dot = new THREE.CanvasTexture(dotCanvas);
    const stars = new THREE.Points(geometry, new THREE.PointsMaterial({ size: 7, sizeAttenuation: false,
      map: dot, vertexColors: true, transparent: true, opacity: .94, depthWrite: false }));
    scene.add(stars);
    const hubPositions = new Float32Array(subjects.length * 3);
    subjects.forEach((subject, index) => layout.centers.get(subject.id)?.toArray(hubPositions, index * 3));
    const hubGeometry = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(hubPositions, 3));
    const hubs = new THREE.Points(hubGeometry, new THREE.PointsMaterial({ color: '#e5c082', map: dot,
      size: 15, sizeAttenuation: false, transparent: true, depthWrite: false }));
    scene.add(hubs);
    const rings: THREE.LineLoop[] = [];
    for (const radius of [90, 200, 320, 445]) {
      const points = Array.from({ length: 192 }, (_, i) => new THREE.Vector3(
        Math.cos(i / 192 * Math.PI * 2) * radius, Math.sin(i / 192 * Math.PI * 2) * radius, -50));
      const ring = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color: 0xc9b89b, transparent: true, opacity: .16 }));
      rings.push(ring); scene.add(ring);
    }
    const arms: THREE.Line[] = [];
    layout.volumes.forEach((volume, index) => {
      const points = [new THREE.Vector3(), ...subjects.filter((subject) => subject.volume === volume)
        .flatMap((subject) => layout.centers.get(subject.id) ?? [])];
      const curve = new THREE.CatmullRomCurve3(points).getPoints(96);
      const arm = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve),
        new THREE.LineBasicMaterial({ color: LIFE_PALETTES[index % LIFE_PALETTES.length], transparent: true, opacity: .18 }));
      arms.push(arm); scene.add(arm);
    });
    const coreGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3()]);
    const core = new THREE.Points(coreGeometry, new THREE.PointsMaterial({ color: '#efece6', map: dot,
      size: 9, sizeAttenuation: false, transparent: true, depthWrite: false }));
    scene.add(core);
    const selectedGeometry = new THREE.BufferGeometry();
    const selectedStar = new THREE.Points(selectedGeometry, new THREE.PointsMaterial({ color: 0xffe9bd, map: dot,
      size: 12, sizeAttenuation: false, transparent: true, depthTest: false }));
    scene.add(selectedStar);
    const lineGeometry = new THREE.BufferGeometry();
    const lines = new THREE.LineSegments(lineGeometry, new THREE.LineBasicMaterial({ color: 0xc29d59,
      transparent: true, opacity: .75, depthWrite: false }));
    scene.add(lines);
    let focus: THREE.Vector3 | null = null, focusDirection: THREE.Vector3 | null = null, focusDistance = 0, frame = 0;
    function schedule() { if (!frame) frame = requestAnimationFrame(render); }
    function fly(target: THREE.Vector3, distance: number, direction: THREE.Vector3 | null = null) {
      focus = target.clone(); focusDistance = distance; focusDirection = direction; schedule();
    }
    function render() {
      frame = 0;
      if (focus) {
        const delta = focus.clone().sub(controls.target).multiplyScalar(.10);
        camera.position.add(delta); controls.target.add(delta);
        const offset = camera.position.clone().sub(controls.target), distance = offset.length();
        const next = distance + (focusDistance - distance) * .10;
        const bearing = offset.multiplyScalar(1 / distance);
        if (focusDirection) bearing.lerp(focusDirection, .10).normalize();
        camera.position.copy(controls.target).add(bearing.clone().multiplyScalar(next));
        if (delta.lengthSq() < .001 && Math.abs(next - focusDistance) < .1
          && (!focusDirection || bearing.dot(focusDirection) > .99999)) { focus = null; focusDirection = null; }
      }
      const moving = controls.update(); webgl.render(scene, camera);
      if (focus || moving) schedule();
    }
    controls.addEventListener('change', schedule);
    const resize = () => {
      const width = Math.max(1, element.clientWidth), height = Math.max(1, element.clientHeight);
      camera.aspect = width / height; camera.updateProjectionMatrix(); webgl.setSize(width, height, false); schedule();
    };
    const observer = new ResizeObserver(resize); observer.observe(element); resize();
    const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
    const hit = (event: PointerEvent) => {
      const box = canvas.getBoundingClientRect();
      pointer.set((event.clientX - box.left) / box.width * 2 - 1, -(event.clientY - box.top) / box.height * 2 + 1);
      camera.updateMatrixWorld(); raycaster.setFromCamera(pointer, camera);
      raycaster.params.Points = { threshold: 8 }; const hub = raycaster.intersectObject(hubs)[0];
      raycaster.params.Points = { threshold: 5 }; const node = raycaster.intersectObject(stars)[0];
      if (hub?.index !== undefined && (hub.distanceToRay ?? Infinity) < 5) return { kind: 'hub' as const, index: hub.index };
      if (node?.index !== undefined) return { kind: 'node' as const, index: node.index };
      return null;
    };
    let hovered = '';
    let down = { x: 0, y: 0 }, gravityTimer = 0, gravityHeld = false;
    const gravity = createLifeGravity(entries, layout);
    let lastSelected: string | null = null, lastSubject: string | null = null;
    let lastHighlights: readonly string[] = [];
    const restoreGravity = () => {
      window.clearTimeout(gravityTimer); gravityTimer = 0;
      if (!gravityHeld) return;
      gravityHeld = false; gravity.clear(); geometry.getAttribute('position').needsUpdate = true;
      controller.update(lastSelected, lastSubject, lastHighlights);
    };
    const move = (event: PointerEvent) => {
      if (event.buttons) {
        if (Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) restoreGravity();
        return;
      }
      const target = hit(event), key = target ? `${target.kind}:${target.index}` : '';
      canvas.style.cursor = target ? 'pointer' : 'grab';
      if (key !== hovered) {
        hovered = key;
        const title = target?.kind === 'hub' ? `学科 · ${subjects[target.index].title}`
          : target ? entries[target.index].title : '';
        setHover(target ? { title, x: event.offsetX, y: event.offsetY } : null);
      }
    };
    const pointerDown = (event: PointerEvent) => {
      focus = null; down = { x: event.clientX, y: event.clientY };
      const target = hit(event);
      if (target?.kind === 'node') gravityTimer = window.setTimeout(() => {
        const id = entries[target.index].id; gravityHeld = true; gravity.pull(id);
        geometry.getAttribute('position').needsUpdate = true; select.current(id); schedule();
      }, 480);
    };
    const pointerUp = (event: PointerEvent) => {
      const wasHeld = gravityHeld; restoreGravity();
      if (wasHeld) return;
      if (Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) return;
      const target = hit(event);
      if (target?.kind === 'hub') selectSubject.current(subjects[target.index].id);
      else if (target) select.current(entries[target.index].id);
    };
    const leave = () => { hovered = ''; setHover(null); };
    canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerdown', pointerDown);
    canvas.addEventListener('pointerup', pointerUp); canvas.addEventListener('pointerleave', leave);
    canvas.addEventListener('pointercancel', restoreGravity);
    const color = new THREE.Color();
    let lastFocus = '';
    const controller: LifeDrawing = {
      update(selected, subject, highlights) {
        lastSelected = selected; lastSubject = subject; lastHighlights = highlights;
        const chosen = entries.find((entry) => entry.id === selected), related = new Set(chosen?.links ?? []);
        const matched = new Set(highlights);
        if (chosen) for (const entry of entries) if (entry.links.includes(chosen.id)) related.add(entry.id);
        entries.forEach((entry, i) => {
          color.set(LIFE_PALETTES[layout.volumes.indexOf(entry.volume) % LIFE_PALETTES.length]);
          const dim = subject && entry.subject !== subject ? .22 : selected && entry.id !== selected && !related.has(entry.id) ? .28
            : !selected && matched.size && !matched.has(entry.id) ? .22 : 1;
          color.multiplyScalar(dim);
          (geometry.getAttribute('color') as THREE.BufferAttribute).setXYZ(i, color.r, color.g, color.b);
        });
        geometry.getAttribute('color').needsUpdate = true;
        const origin = selected ? layout.locations.get(selected) : undefined;
        selectedGeometry.setFromPoints(origin ? [origin] : []);
        const linePoints: THREE.Vector3[] = [];
        if (origin) for (const id of related) {
          const target = layout.locations.get(id);
          if (target) linePoints.push(origin, target);
        }
        if (!origin && highlights.length > 1) {
          for (let index = 1; index < highlights.length; index++) {
            const a = layout.locations.get(highlights[index - 1]), b = layout.locations.get(highlights[index]);
            if (a && b) linePoints.push(a, b);
          }
        }
        lineGeometry.setFromPoints(linePoints);
        const target = origin ?? (subject ? layout.centers.get(subject) : undefined);
        const key = selected ? `entry:${selected}` : subject ? `subject:${subject}` : '';
        if (target && key !== lastFocus) fly(target, origin ? 285 : 390);
        else if (!target) { focus = null; schedule(); } else schedule();
        lastFocus = key;
      },
      reset() { fly(new THREE.Vector3(), 1165, overviewDirection); },
      dispose() {
        window.clearTimeout(gravityTimer); gravity.clear();
        cancelAnimationFrame(frame); observer.disconnect(); controls.removeEventListener('change', schedule); controls.dispose();
        canvas.removeEventListener('pointermove', move); canvas.removeEventListener('pointerdown', pointerDown);
        canvas.removeEventListener('pointerup', pointerUp); canvas.removeEventListener('pointerleave', leave);
        canvas.removeEventListener('pointercancel', restoreGravity);
        geometry.dispose(); (stars.material as THREE.Material).dispose(); hubGeometry.dispose(); (hubs.material as THREE.Material).dispose();
        selectedGeometry.dispose(); (selectedStar.material as THREE.Material).dispose(); lineGeometry.dispose(); (lines.material as THREE.Material).dispose();
        rings.forEach((ring) => { ring.geometry.dispose(); (ring.material as THREE.Material).dispose(); });
        arms.forEach((arm) => { arm.geometry.dispose(); (arm.material as THREE.Material).dispose(); });
        coreGeometry.dispose(); (core.material as THREE.Material).dispose();
        dot.dispose(); webgl.dispose(); canvas.remove();
      },
    };
    drawing.current = controller; controller.update(selectedId, subjectId, highlightIds);
    return () => { controller.dispose(); drawing.current = null; };
    // Selection changes update the existing scene without rebuilding it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries, subjects]);
  useEffect(() => { drawing.current?.update(selectedId, subjectId, highlightIds); }, [selectedId, subjectId, highlightIds]);
  useEffect(() => { if (resetSerial) drawing.current?.reset(); }, [resetSerial]);
  return <div className="life-scene" ref={host} aria-label="知识星图：拖动旋转，滚轮缩放，点击星点或学科星团">
    {hover && <div className="life-tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>{hover.title}</div>}
  </div>;
}
