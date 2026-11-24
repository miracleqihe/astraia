import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { LifeEntry, LifeSubject } from '../life';
import { LIFE_PALETTES, lifeGalaxyLayout } from './lifeGalaxyLayout';
import { animateLifeGravity, createLifeGravity } from './lifeGravity';
import { createLifeMotion } from './lifeMotion';
import { lifeStardust } from './lifeStardust';
import { createLifeGalaxyLabels } from './lifeGalaxyLabels';
import { createLifePortal } from './lifePortal';
import { createLifeNebula } from './lifeNebula';
import { lifeAtmosphere } from './lifeAtmosphere';
import { lifeCelestialGuides } from './lifeCelestialGuides';
import { lifeStarMaterial } from './lifeStarShader';
import { lifeAmbientEdges, lifeArcPoint, sampleLifeEdges } from './lifeArcs';
import { mountLifeSoftware } from './lifeSoftware';
import type { LifeDrawing, LifeHover } from './lifeSceneTypes';
import LifeStarTooltip from './LifeStarTooltip';

interface Props {
  entries: LifeEntry[];
  subjects: LifeSubject[];
  selectedId: string | null;
  subjectId: string | null;
  volumeId: string | null;
  highlightIds: readonly string[];
  connectHighlights: boolean;
  motionEnabled: boolean;
  mode: 'galaxy' | 'astrolabe';
  resetSerial: number;
  onSelect: (id: string) => void;
  onSubject: (id: string) => void;
  onVolume: (id: string) => void;
  onRenderer: (renderer: 'software' | 'webgl') => void;
}

export default function LifeScene({ entries, subjects, selectedId, subjectId, volumeId, highlightIds, connectHighlights, motionEnabled, mode, resetSerial, onSelect, onSubject, onVolume, onRenderer }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const drawing = useRef<LifeDrawing | null>(null);
  const select = useRef(onSelect), selectSubject = useRef(onSubject), selectVolume = useRef(onVolume);
  const [hover, setHover] = useState<LifeHover | null>(null);
  const [tryWebGL, setTryWebGL] = useState(false);
  select.current = onSelect; selectSubject.current = onSubject; selectVolume.current = onVolume;

  useEffect(() => {
    if (typeof Worker === 'undefined' || typeof OffscreenCanvas === 'undefined') { setTryWebGL(true); return; }
    let active = true;
    let worker: Worker | undefined;
    let probeTimer = 0, startTimer = 0;
    const finish = (result: string) => {
      if (!active) return;
      active = false; window.clearTimeout(probeTimer); worker?.terminate();
      // If the worker cannot establish a reliable answer, let the main
      // renderer try normally rather than silently disabling acceleration.
      if (result !== 'software') setTryWebGL(true);
    };
    // Give the Canvas 2D preview a frame before the GPU process begins its
    // probe, so the probe does not compete with the first drawing.
    const frame = requestAnimationFrame(() => { startTimer = window.setTimeout(() => {
      if (!active) return;
      try { worker = new Worker(new URL('./lifeGpuProbe.js', import.meta.url), { type: 'module' }); }
      catch { finish('unknown'); return; }
      probeTimer = window.setTimeout(() => finish('unknown'), 8000);
      worker.onmessage = (event: MessageEvent<string>) => finish(event.data);
      worker.onerror = () => finish('unknown');
      worker.postMessage(null);
    }, 250); });
    return () => { active = false; cancelAnimationFrame(frame); window.clearTimeout(startTimer); window.clearTimeout(probeTimer); worker?.terminate(); };
  }, []);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const layout = lifeGalaxyLayout(entries, subjects);
    let renderer: THREE.WebGLRenderer | null = null;
    if (tryWebGL) {
      try {
        // Probe only once. Three.js otherwise retries without the performance
        // guard when the first context request fails, initializing slow software
        // WebGL before we can switch to the much faster Canvas 2D renderer.
        const canvas = document.createElement('canvas');
        const options = { antialias: true, alpha: true, failIfMajorPerformanceCaveat: true };
        const gl = canvas.getContext('webgl2', options) as WebGL2RenderingContext | null;
        if (gl) {
          const debug = gl.getExtension('WEBGL_debug_renderer_info');
          const name = debug ? String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)) : '';
          if (/swiftshader|llvmpipe|software|warp/i.test(name)) gl.getExtension('WEBGL_lose_context')?.loseContext();
          else renderer = new THREE.WebGLRenderer({ canvas, context: gl, ...options });
        }
      } catch { /* Canvas 2D remains available when WebGL is unavailable. */ }
    }
    if (!renderer) {
      onRenderer('software');
      const fallback = mountLifeSoftware(element, entries, subjects, layout,
        (id) => select.current(id), (id) => selectSubject.current(id), (id) => selectVolume.current(id), setHover);
      drawing.current = fallback; fallback.update(selectedId, subjectId, highlightIds, connectHighlights, volumeId); fallback.setMotion(motionEnabled);
      return () => { fallback.dispose(); drawing.current = null; };
    }

    const webgl = renderer;
    onRenderer('webgl');
    webgl.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); webgl.setClearColor(0x04060c, 1);
    const canvas = webgl.domElement; canvas.dataset.renderer = 'webgl'; element.appendChild(canvas);
    const scene = new THREE.Scene();
    const nebula = createLifeNebula(), starMaterial = lifeStarMaterial(), atmosphere = lifeAtmosphere(scene, layout, starMaterial);
    const camera = new THREE.PerspectiveCamera(46, 1, 1, 3500);
    camera.position.set(-18, 22, 575);
    const controls = new OrbitControls(camera, canvas);
    const overviewTarget = new THREE.Vector3(-14,-4,0);
    controls.target.copy(overviewTarget);
    const overviewDirection = camera.position.clone().sub(overviewTarget).normalize();
    const labels = createLifeGalaxyLabels(element, layout, subjects, (id) => selectVolume.current(id), (id) => selectSubject.current(id));
    const portal = createLifePortal(element, entries, layout, (id) => select.current(id));
    const portalProjection = new THREE.Vector3();
    controls.enableDamping = true; controls.dampingFactor = .065; controls.rotateSpeed = .58; controls.zoomSpeed = .85;
    controls.minDistance = 75; controls.maxDistance = 1150; controls.enablePan = true;

    const colors = layout.reference.colors.slice();
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(layout.positions, 3));
    geometry.setAttribute('nodeColor', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('starSize', new THREE.BufferAttribute(layout.reference.sizes, 1));
    geometry.setAttribute('starPhase', new THREE.BufferAttribute(layout.reference.phases, 1));
    geometry.setAttribute('starSpike', new THREE.BufferAttribute(layout.reference.spikes, 1));
    geometry.setAttribute('starBrightness', new THREE.BufferAttribute(new Float32Array(entries.length).fill(1), 1));
    const dotCanvas = document.createElement('canvas'); dotCanvas.width = dotCanvas.height = 32;
    const dotContext = dotCanvas.getContext('2d');
    if (!dotContext) throw new Error('无法创建星点纹理');
    const glow = dotContext.createRadialGradient(16, 16, 1, 16, 16, 15);
    glow.addColorStop(0, '#fff'); glow.addColorStop(.35, 'rgba(255,255,255,.9)');
    glow.addColorStop(1, 'rgba(255,255,255,0)');
    dotContext.fillStyle = glow; dotContext.fillRect(0, 0, 32, 32);
    const dot = new THREE.CanvasTexture(dotCanvas);
    const dustData = lifeStardust(layout, 3400);
    const dustBase = dustData.positions.slice();
    const dustGeometry = new THREE.BufferGeometry();
    dustGeometry.setAttribute('position', new THREE.BufferAttribute(dustData.positions, 3));
    dustGeometry.setAttribute('nodeColor', new THREE.BufferAttribute(dustData.colors, 3));
    dustGeometry.setAttribute('starSize',new THREE.BufferAttribute(dustData.sizes,1));
    dustGeometry.setAttribute('starPhase',new THREE.BufferAttribute(dustData.phases,1));
    dustGeometry.setAttribute('starSpike',new THREE.BufferAttribute(new Float32Array(dustData.sizes.length),1));
    dustGeometry.setAttribute('starBrightness',new THREE.BufferAttribute(new Float32Array(dustData.sizes.length).fill(.58),1));
    const dust = new THREE.Points(dustGeometry, starMaterial);
    scene.add(dust);
    const galaxyCoreGeometry = new THREE.BufferGeometry();
    const galaxyCorePositions = new Float32Array(layout.volumes.length * 3), galaxyCoreColors = new Float32Array(layout.volumes.length * 3);
    layout.volumes.forEach((volume, index) => {
      layout.volumeCenters.get(volume)?.toArray(galaxyCorePositions, index * 3);
      new THREE.Color(LIFE_PALETTES[index % LIFE_PALETTES.length]).toArray(galaxyCoreColors, index * 3);
    });
    galaxyCoreGeometry.setAttribute('position', new THREE.BufferAttribute(galaxyCorePositions, 3));
    galaxyCoreGeometry.setAttribute('nodeColor', new THREE.BufferAttribute(galaxyCoreColors, 3));
    galaxyCoreGeometry.setAttribute('starSize',new THREE.BufferAttribute(new Float32Array(layout.volumes.length).fill(34),1));
    galaxyCoreGeometry.setAttribute('starPhase',new THREE.BufferAttribute(new Float32Array(layout.volumes.map((_,i)=>i*1.3)),1));
    galaxyCoreGeometry.setAttribute('starSpike',new THREE.BufferAttribute(new Float32Array(layout.volumes.length).fill(1.35),1));
    galaxyCoreGeometry.setAttribute('starBrightness',new THREE.BufferAttribute(new Float32Array(layout.volumes.length).fill(1.15),1));
    const galaxyCores = new THREE.Points(galaxyCoreGeometry, starMaterial);
    scene.add(galaxyCores);
    const stars = new THREE.Points(geometry, starMaterial);
    scene.add(stars);
    const hubPositions = new Float32Array(subjects.length * 3), hubColors = new Float32Array(subjects.length * 3);
    subjects.forEach((subject, index) => {
      layout.centers.get(subject.id)?.toArray(hubPositions, index * 3);
      new THREE.Color(LIFE_PALETTES[layout.volumes.indexOf(subject.volume) % LIFE_PALETTES.length]).toArray(hubColors, index * 3);
    });
    const hubGeometry = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(hubPositions, 3));
    hubGeometry.setAttribute('nodeColor', new THREE.BufferAttribute(hubColors, 3));
    // Alpha stars are already present in the reference mesh. This transparent
    // points object supplies their larger, accessible picking targets only.
    const hubs = new THREE.Points(hubGeometry, new THREE.PointsMaterial({transparent:true,opacity:0,depthWrite:false}));
    scene.add(hubs);
    const structures = layout.structuralEdges.map((group, index) => {
      const guide = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(group.points),
        new THREE.LineBasicMaterial({ color: LIFE_PALETTES[index % LIFE_PALETTES.length], transparent: true, opacity: .16, depthWrite: false }));
      scene.add(guide); return guide;
    });
    const celestial = lifeCelestialGuides(layout, entries, subjects);
    const celestialLines = celestial.map((guide) => {
      const line = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(guide.points),
        new THREE.LineBasicMaterial({color:guide.color,transparent:true,opacity:guide.opacity,depthWrite:false}));
      scene.add(line); return line;
    });
    const coreGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3()]);
    coreGeometry.setAttribute('nodeColor',new THREE.BufferAttribute(new Float32Array(new THREE.Color('#ffe7b3').toArray()),3));
    coreGeometry.setAttribute('starSize',new THREE.BufferAttribute(new Float32Array([42]),1));
    coreGeometry.setAttribute('starPhase',new THREE.BufferAttribute(new Float32Array([.5]),1));
    coreGeometry.setAttribute('starSpike',new THREE.BufferAttribute(new Float32Array([1.5]),1));
    coreGeometry.setAttribute('starBrightness',new THREE.BufferAttribute(new Float32Array([1.25]),1));
    const core = new THREE.Points(coreGeometry, starMaterial);
    scene.add(core);
    const selectedGeometry = new THREE.BufferGeometry();
    const selectedStar = new THREE.Points(selectedGeometry, new THREE.PointsMaterial({ color: 0xffe9bd, map: dot,
      size: 12, sizeAttenuation: false, transparent: true, depthTest: false }));
    scene.add(selectedStar);
    const lineGeometry = new THREE.BufferGeometry();
    const lines = new THREE.LineSegments(lineGeometry, new THREE.LineBasicMaterial({ color: 0xdec084,
      transparent: true, opacity: .26, depthWrite: false, blending: THREE.AdditiveBlending }));
    lines.frustumCulled = false;
    scene.add(lines);
    const pulseGeometry = new THREE.BufferGeometry();
    pulseGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(), 3));
    const pulses = new THREE.Points(pulseGeometry, new THREE.PointsMaterial({ color: '#fff0c5', map: dot,
      size: 7, sizeAttenuation: false, transparent: true, opacity: .9, depthWrite: false }));
    pulses.frustumCulled = false;
    scene.add(pulses);
    const motion = createLifeMotion(entries, layout, celestial);
    const morphBase=layout.positions.slice(), morphPoints=entries.map((entry)=>layout.locations.get(entry.id)!);
    const subjectBase=new Map([...layout.centers].map(([id,point])=>[id,point.clone()]));
    const ambientEdges = lifeAmbientEdges(entries);
    let movingStars = false, lastMotion = 0, pointerActive = false;
    let currentMode: 'galaxy' | 'astrolabe' = 'galaxy', morph=0, morphTarget=0;
    let selectedActive = false;
    let liveLinePoints: THREE.Vector3[] = [], liveSelectedPoint: THREE.Vector3 | undefined, labelsVisible = true;
    let labelVolume: string | null = null, labelSubject: string | null = null, labelSelected = false;
    const arcA = new THREE.Vector3(), arcB = new THREE.Vector3(), arcPulse = new THREE.Vector3(), arcSegments = 10;
    function updateArcs() {
      const attribute = lineGeometry.getAttribute('position') as THREE.BufferAttribute | undefined;
      if (!attribute) return;
      for (let pair = 0; pair < liveLinePoints.length; pair += 2) for (let step = 0; step < arcSegments; step++) {
        const a = liveLinePoints[pair], b = liveLinePoints[pair + 1];
        lifeArcPoint(a, b, step / arcSegments, arcA); lifeArcPoint(a, b, (step + 1) / arcSegments, arcB);
        const at = (pair / 2 * arcSegments + step) * 2;
        attribute.setXYZ(at, arcA.x, arcA.y, arcA.z); attribute.setXYZ(at + 1, arcB.x, arcB.y, arcB.z);
      }
      attribute.needsUpdate = true;
    }
    function syncGuides() {
      structures.forEach((guide,group)=>{
        const attribute=guide.geometry.getAttribute('position') as THREE.BufferAttribute;
        layout.structuralEdges[group].points.forEach((point,index)=>attribute.setXYZ(index,point.x,point.y,point.z));
        attribute.needsUpdate=true;
      });
      celestialLines.forEach((line,group)=>{
        const attribute=line.geometry.getAttribute('position') as THREE.BufferAttribute;
        celestial[group].points.forEach((point,index)=>attribute.setXYZ(index,point.x,point.y,point.z));
        attribute.needsUpdate=true;
      });
    }
    function applyMorph(value:number) {
      for(let i=0;i<morphPoints.length;i++) {
        const at=i*3, x=morphBase[at]+(layout.flatPositions[at]-morphBase[at])*value;
        const y=morphBase[at+1]+(layout.flatPositions[at+1]-morphBase[at+1])*value;
        const z=morphBase[at+2]*(1-value);
        layout.positions[at]=x;layout.positions[at+1]=y;layout.positions[at+2]=z;morphPoints[i].set(x,y,z);
      }
      geometry.getAttribute('position').needsUpdate=true;
      subjects.forEach((subject,index)=>{
        const point=layout.centers.get(subject.id), from=subjectBase.get(subject.id), to=layout.flatCenters.get(subject.id);
        if(point && from && to) { point.lerpVectors(from,to,value); point.toArray(hubPositions,index*3); }
      });
      hubGeometry.getAttribute('position').needsUpdate=true;
      for(let i=0;i<dustData.positions.length;i++) dustData.positions[i]=dustBase[i]+(dustData.flatPositions[i]-dustBase[i])*value;
      dustGeometry.getAttribute('position').needsUpdate=true;
      structures.forEach((guide)=>{guide.visible=value<.55;});
      celestialLines[celestialLines.length-1].visible=value<.45;
      updateArcs();
      const selectedPosition=selectedGeometry.getAttribute('position') as THREE.BufferAttribute|undefined;
      if(selectedPosition && liveSelectedPoint) { selectedPosition.setXYZ(0,liveSelectedPoint.x,liveSelectedPoint.y,liveSelectedPoint.z); selectedPosition.needsUpdate=true; }
    }
    let focus: THREE.Vector3 | null = null, focusDirection: THREE.Vector3 | null = null, focusDistance = 0, frame = 0;
    function schedule() { if (!frame) frame = requestAnimationFrame(render); }
    function fly(target: THREE.Vector3, distance: number, direction: THREE.Vector3 | null = null) {
      focus = target.clone(); focusDistance = distance; focusDirection = direction; schedule();
    }
    function render(now: number) {
      frame = 0;
      if (document.documentElement.dataset.astraiaActive === 'false') { lastMotion = 0; return; }
      if (movingStars) (stars.material as THREE.ShaderMaterial).uniforms.time.value = now / 1000;
      if(Math.abs(morphTarget-morph)>.001) {
        morph+=(morphTarget-morph)*.085;
        if(Math.abs(morphTarget-morph)<=.001) morph=morphTarget;
        applyMorph(morph);
      }
      if (movingStars && currentMode==='galaxy' && morph===0 && !selectedActive && !pointerActive && !gravity.active() && !document.hidden) {
        if (lastMotion) {
          motion.advance((now - lastMotion) / 1000);
          geometry.getAttribute('position').needsUpdate = true;
          subjects.forEach((subject, index) => layout.centers.get(subject.id)?.toArray(hubPositions, index * 3));
          hubGeometry.getAttribute('position').needsUpdate = true;
          layout.volumes.forEach((volume, index) => layout.volumeCenters.get(volume)?.toArray(galaxyCorePositions, index * 3));
          galaxyCoreGeometry.getAttribute('position').needsUpdate = true;
          atmosphere.rotate(motion.angle());
          motion.transformDust(dustData.positions, dustBase, dustData.groups);
          dustGeometry.getAttribute('position').needsUpdate = true;
          syncGuides();
          updateArcs();
          const selectedPosition = selectedGeometry.getAttribute('position') as THREE.BufferAttribute | undefined;
          if (selectedPosition && liveSelectedPoint) {
            selectedPosition.setXYZ(0, liveSelectedPoint.x, liveSelectedPoint.y, liveSelectedPoint.z);
            selectedPosition.needsUpdate = true;
          }
        }
        lastMotion = now;
      } else lastMotion = 0;
      pulses.visible = movingStars;
      if (movingStars && liveLinePoints.length) {
        const positions = pulseGeometry.getAttribute('position') as THREE.BufferAttribute;
        for (let i = 0; i < liveLinePoints.length; i += 2) {
          const a = liveLinePoints[i], b = liveLinePoints[i + 1], progress = (now / 5200 + i * .091) % 1;
          lifeArcPoint(a, b, progress, arcPulse); positions.setXYZ(i / 2, arcPulse.x, arcPulse.y, arcPulse.z);
        }
        positions.needsUpdate = true;
      }
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
      const moving = controls.update(); nebula.render(webgl, scene, camera, now / 1000, camera.aspect);
      labels.update(camera, labelsVisible, labelVolume, labelSubject, labelSelected,currentMode==='astrolabe',morph);
      const portalPoint = portal.point();
      if (portalPoint) {
        portalProjection.copy(portalPoint).project(camera);
        portal.position((portalProjection.x + 1) * canvas.clientWidth / 2 + 10,
          (1 - portalProjection.y) * canvas.clientHeight / 2 + 10, portalProjection.z < 1 && Math.abs(portalProjection.x) < .95 && Math.abs(portalProjection.y) < .95);
      }
      if (focus || moving || Math.abs(morphTarget-morph)>.001 || (movingStars && !document.hidden)) schedule();
    }
    const visibility = () => { lastMotion = 0; if (!document.hidden && document.documentElement.dataset.astraiaActive !== 'false') schedule(); };
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('astraia:visibility', visibility);
    controls.addEventListener('change', schedule);
    const resize = () => {
      const width = Math.max(1, element.clientWidth), height = Math.max(1, element.clientHeight);
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      if (webgl.getPixelRatio() !== ratio) {
        webgl.setPixelRatio(ratio);
        (stars.material as THREE.ShaderMaterial).uniforms.pixelRatio.value = ratio;
      }
      camera.aspect = width / height;
      // The original canvas continues behind the 48 px navigation bar.
      // Match that full-window projection while keeping the app header intact.
      const topInset = width > 760 ? Math.max(0,Math.min(80,Math.round(element.getBoundingClientRect().top))) : 0;
      if(topInset) camera.setViewOffset(width,height+topInset,0,topInset,width,height); else camera.clearViewOffset();
      camera.updateProjectionMatrix(); webgl.setSize(width, height, false); schedule();
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
    const gravityAnimation = animateLifeGravity(gravity, () => {
      geometry.getAttribute('position').needsUpdate = true;
      updateArcs();
      schedule();
    });
    const restoreGravity = () => {
      window.clearTimeout(gravityTimer); gravityTimer = 0;
      if (!gravityHeld) return;
      gravityHeld = false; gravityAnimation.release();
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
        const entry = target?.kind === 'node' ? entries[target.index] : undefined;
        const discipline = target?.kind === 'hub' ? subjects[target.index] : undefined;
        setHover(target ? { title, x: event.offsetX, y: event.offsetY, id: entry?.id,
          volume: entry?.volume ?? discipline?.volume,
          detail: entry ? `${entry.topic} · 原书第 ${entry.page} 页` : '点击进入学科星域' } : null);
      }
    };
    const pointerDown = (event: PointerEvent) => {
      focus = null; pointerActive = true; down = { x: event.clientX, y: event.clientY };
      const target = hit(event);
      if (target?.kind === 'node') gravityTimer = window.setTimeout(() => {
        const id = entries[target.index].id; gravityHeld = true; gravityAnimation.pull(id);
        geometry.getAttribute('position').needsUpdate = true; select.current(id); schedule();
      }, 480);
    };
    const pointerUp = (event: PointerEvent) => {
      pointerActive = false;
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
    const pointerCancel = () => { pointerActive = false; restoreGravity(); };
    canvas.addEventListener('pointercancel', pointerCancel);
    let lastFocus = '';
    const controller: LifeDrawing = {
      update(selected, subject, highlights, connect = true, volume = null) {
        selectedActive = !!selected;
        labelsVisible = !selected && !subject && !volume;
        labelVolume = volume; labelSubject = subject; labelSelected = !!selected;
        portal.select(connect ? selected : null);
        const chosen = entries.find((entry) => entry.id === selected), related = new Set(chosen?.links ?? []);
        const matched = new Set(highlights);
        const activeVolume = volume ?? subjects.find((item) => item.id === subject)?.volume ?? chosen?.volume ?? null;
        atmosphere.focus(activeVolume);
        structures.forEach((guide, index) => {
          (guide.material as THREE.LineBasicMaterial).opacity = activeVolume && layout.volumes[index] !== activeVolume ? .032 : .16;
        });
        const coreBrightness = galaxyCoreGeometry.getAttribute('starBrightness') as THREE.BufferAttribute;
        layout.volumes.forEach((item, index) => coreBrightness.setX(index, activeVolume && item !== activeVolume ? .2 : 1.15));
        coreBrightness.needsUpdate = true;
        if (chosen) for (const entry of entries) if (entry.links.includes(chosen.id)) related.add(entry.id);
        entries.forEach((entry, i) => {
          const dim = subject && entry.subject !== subject || volume && entry.volume !== volume ? .22 : selected && entry.id !== selected && !related.has(entry.id) ? .28
            : !selected && matched.size && !matched.has(entry.id) ? .22 : 1;
          (geometry.getAttribute('starBrightness') as THREE.BufferAttribute).setX(i, dim);
        });
        geometry.getAttribute('starBrightness').needsUpdate = true;
        const origin = selected ? layout.locations.get(selected) : undefined;
        (lines.material as THREE.LineBasicMaterial).opacity = origin ? .72 : highlights.length ? .48 : .26;
        liveSelectedPoint = origin; selectedGeometry.setFromPoints(origin ? [origin] : []);
        const linePoints: THREE.Vector3[] = [];
        if (origin && connect) for (const id of related) {
          const target = layout.locations.get(id);
          if (target) linePoints.push(origin, target);
        }
        if (!origin && connect && highlights.length > 1) {
          for (const [from, to] of sampleLifeEdges(entries, highlights)) {
            const a = layout.locations.get(from), b = layout.locations.get(to);
            if (a && b) linePoints.push(a, b);
          }
        }
        if (!origin && connect && !highlights.length && !subject && !volume) for (const [from,to] of ambientEdges) {
          const a=layout.locations.get(from), b=layout.locations.get(to); if(a && b) linePoints.push(a,b);
        }
        liveLinePoints = linePoints;
        lineGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(linePoints.length / 2 * arcSegments * 6), 3));
        updateArcs();
        pulseGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(linePoints.length / 2 * 3), 3));
        const target = origin ?? (subject ? layout.centers.get(subject) : volume && currentMode==='galaxy' ? layout.volumeCenters.get(volume) : undefined);
        const key = selected ? `entry:${selected}` : subject ? `subject:${subject}` : volume ? `volume:${volume}` : '';
        if (target && key !== lastFocus) fly(target, currentMode==='astrolabe' ? origin ? 185 : 190 : origin ? 150 : subject ? 170 : 240);
        else if (!target && lastFocus) { focus = null; schedule(); } else schedule();
        lastFocus = key;
      },
      setMotion(enabled) { movingStars = enabled; lastMotion = 0; if (enabled && !document.hidden) schedule(); },
      setMode(next) {
        if(next===currentMode) return;
        if(next==='astrolabe' && morph===0) {
          // Gemini returns its slowly turning universe to its original axis
          // before morphing the same stars and dust into the flat target.
          motion.reset(); atmosphere.rotate(0); dustData.positions.set(dustBase);
          layout.volumes.forEach((volume,index)=>layout.volumeCenters.get(volume)?.toArray(galaxyCorePositions,index*3));
          galaxyCoreGeometry.getAttribute('position').needsUpdate=true; syncGuides();
        }
        currentMode=next; morphTarget=next==='astrolabe'?1:0; canvas.dataset.sceneMode=next;
        controls.enableRotate=next==='galaxy';
        controls.mouseButtons.LEFT=next==='astrolabe'?THREE.MOUSE.PAN:THREE.MOUSE.ROTATE;
        if(window.matchMedia('(prefers-reduced-motion: reduce)').matches) { morph=morphTarget; applyMorph(morph); }
        if(next==='astrolabe') fly(new THREE.Vector3(-12,0,0),640,new THREE.Vector3(0,0,1));
        else fly(overviewTarget,576,overviewDirection);
        schedule();
      },
      reset() {
        if(currentMode==='astrolabe') fly(new THREE.Vector3(-12,0,0),640,new THREE.Vector3(0,0,1));
        else fly(overviewTarget,576,overviewDirection);
      },
      dispose() {
        movingStars = false; document.removeEventListener('visibilitychange', visibility); window.removeEventListener('astraia:visibility', visibility);
        labels.dispose(); portal.dispose();
        window.clearTimeout(gravityTimer); gravityAnimation.dispose();
        cancelAnimationFrame(frame); observer.disconnect(); controls.removeEventListener('change', schedule); controls.dispose();
        canvas.removeEventListener('pointermove', move); canvas.removeEventListener('pointerdown', pointerDown);
        canvas.removeEventListener('pointerup', pointerUp); canvas.removeEventListener('pointerleave', leave);
        canvas.removeEventListener('pointercancel', pointerCancel);
        geometry.dispose(); (stars.material as THREE.Material).dispose(); hubGeometry.dispose(); (hubs.material as THREE.Material).dispose();
        dustGeometry.dispose();
        galaxyCoreGeometry.dispose();
        selectedGeometry.dispose(); (selectedStar.material as THREE.Material).dispose(); lineGeometry.dispose(); (lines.material as THREE.Material).dispose();
        pulseGeometry.dispose(); (pulses.material as THREE.Material).dispose();
        structures.forEach((guide) => { guide.geometry.dispose(); (guide.material as THREE.Material).dispose(); });
        celestialLines.forEach((line) => { line.geometry.dispose(); (line.material as THREE.Material).dispose(); });
        coreGeometry.dispose();
        atmosphere.dispose(); nebula.dispose(); dot.dispose(); webgl.dispose(); canvas.remove();
      },
    };
    drawing.current = controller; controller.update(selectedId, subjectId, highlightIds, connectHighlights, volumeId); controller.setMotion(motionEnabled); controller.setMode?.(mode);
    return () => { controller.dispose(); drawing.current = null; };
    // Selection changes update the existing scene without rebuilding it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries, subjects, tryWebGL]);
  useEffect(() => { drawing.current?.update(selectedId, subjectId, highlightIds, connectHighlights, volumeId); }, [selectedId, subjectId, highlightIds, connectHighlights, volumeId]);
  useEffect(() => { drawing.current?.setMotion(motionEnabled); }, [motionEnabled]);
  useEffect(() => { drawing.current?.setMode?.(mode); }, [mode]);
  useEffect(() => { if (resetSerial) drawing.current?.reset(); }, [resetSerial]);
  return <div className="life-scene" ref={host} aria-label={mode==='galaxy' ? '知识星图：拖动旋转，滚轮缩放，点击星点或学科星团' : '二维知识星盘：拖动平移，滚轮缩放，点击星点或学科'}>
    <LifeStarTooltip hover={hover} />
  </div>;
}
