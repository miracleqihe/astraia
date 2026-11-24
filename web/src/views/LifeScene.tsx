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
import { lifeArcPoint, sampleLifeTrace } from './lifeArcs';
import { mountLifeSoftware } from './lifeSoftware';
import type { LifeDrawing, LifeHover } from './lifeSceneTypes';

interface Props {
  entries: LifeEntry[];
  subjects: LifeSubject[];
  selectedId: string | null;
  subjectId: string | null;
  volumeId: string | null;
  highlightIds: readonly string[];
  connectHighlights: boolean;
  motionEnabled: boolean;
  resetSerial: number;
  onSelect: (id: string) => void;
  onSubject: (id: string) => void;
  onVolume: (id: string) => void;
  onRenderer: (renderer: 'software' | 'webgl') => void;
}

export default function LifeScene({ entries, subjects, selectedId, subjectId, volumeId, highlightIds, connectHighlights, motionEnabled, resetSerial, onSelect, onSubject, onVolume, onRenderer }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const drawing = useRef<LifeDrawing | null>(null);
  const select = useRef(onSelect), selectSubject = useRef(onSubject), selectVolume = useRef(onVolume);
  const [hover, setHover] = useState<LifeHover | null>(null);
  select.current = onSelect; selectSubject.current = onSubject; selectVolume.current = onVolume;

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
        (id) => select.current(id), (id) => selectSubject.current(id), (id) => selectVolume.current(id), setHover);
      drawing.current = fallback; fallback.update(selectedId, subjectId, highlightIds, connectHighlights, volumeId); fallback.setMotion(motionEnabled);
      return () => { fallback.dispose(); drawing.current = null; };
    }

    const webgl = renderer;
    onRenderer('webgl');
    webgl.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); webgl.setClearColor(0x04060c, 1);
    const canvas = webgl.domElement; canvas.dataset.renderer = 'webgl'; element.appendChild(canvas);
    const scene = new THREE.Scene();
    const nebula = createLifeNebula();
    const camera = new THREE.PerspectiveCamera(44, 1, 1, 4000);
    camera.position.set(0, -620, 985);
    const overviewDirection = camera.position.clone().normalize();
    const controls = new OrbitControls(camera, canvas);
    const labels = createLifeGalaxyLabels(element, layout, subjects, (id) => selectVolume.current(id), (id) => selectSubject.current(id));
    const portal = createLifePortal(element, entries, layout, (id) => select.current(id));
    const portalProjection = new THREE.Vector3();
    controls.enableDamping = true; controls.dampingFactor = .08;
    controls.minDistance = 110; controls.maxDistance = 1800; controls.enablePan = true;

    const colors = new Float32Array(entries.length * 3);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(layout.positions, 3));
    geometry.setAttribute('nodeColor', new THREE.BufferAttribute(colors, 3));
    const degree = new Map(entries.map((entry) => [entry.id, entry.links.length]));
    for (const entry of entries) for (const id of entry.links) if (degree.has(id)) degree.set(id, degree.get(id)! + 1);
    const sizes = new Float32Array(entries.map((entry) => Math.min(2.6, 1.5 + Math.log2(1 + (degree.get(entry.id) ?? 0)) * .22)));
    geometry.setAttribute('starSize', new THREE.BufferAttribute(sizes, 1));
    const dotCanvas = document.createElement('canvas'); dotCanvas.width = dotCanvas.height = 32;
    const dotContext = dotCanvas.getContext('2d');
    if (!dotContext) throw new Error('无法创建星点纹理');
    const glow = dotContext.createRadialGradient(16, 16, 1, 16, 16, 15);
    glow.addColorStop(0, '#fff'); glow.addColorStop(.35, 'rgba(255,255,255,.9)');
    glow.addColorStop(1, 'rgba(255,255,255,0)');
    dotContext.fillStyle = glow; dotContext.fillRect(0, 0, 32, 32);
    const dot = new THREE.CanvasTexture(dotCanvas);
    const dustData = lifeStardust(layout, 4200);
    const dustBase = dustData.positions.slice();
    const dustGeometry = new THREE.BufferGeometry();
    dustGeometry.setAttribute('position', new THREE.BufferAttribute(dustData.positions, 3));
    dustGeometry.setAttribute('color', new THREE.BufferAttribute(dustData.colors, 3));
    const dust = new THREE.Points(dustGeometry, new THREE.PointsMaterial({ size: 1, sizeAttenuation: false,
      vertexColors: true, transparent: true, opacity: .55, depthWrite: false }));
    scene.add(dust);
    const galaxyCoreGeometry = new THREE.BufferGeometry();
    const galaxyCorePositions = new Float32Array(layout.volumes.length * 3), galaxyCoreColors = new Float32Array(layout.volumes.length * 3);
    layout.volumes.forEach((volume, index) => {
      layout.volumeCenters.get(volume)?.toArray(galaxyCorePositions, index * 3);
      new THREE.Color(LIFE_PALETTES[index % LIFE_PALETTES.length]).toArray(galaxyCoreColors, index * 3);
    });
    galaxyCoreGeometry.setAttribute('position', new THREE.BufferAttribute(galaxyCorePositions, 3));
    galaxyCoreGeometry.setAttribute('nodeColor', new THREE.BufferAttribute(galaxyCoreColors, 3));
    galaxyCoreGeometry.setAttribute('brightness', new THREE.BufferAttribute(new Float32Array(layout.volumes.length).fill(1), 1));
    function navigationMaterial(size: number) {
      return new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        uniforms: { pixelRatio: { value: Math.min(window.devicePixelRatio || 1, 2) }, size: { value: size }, time: { value: 0 } },
        vertexShader: `attribute vec3 nodeColor; attribute float brightness; varying vec3 vColor; varying float vBrightness; uniform float pixelRatio; uniform float size;
          void main(){vColor=nodeColor; vBrightness=brightness; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); gl_PointSize=size*pixelRatio;}`,
        fragmentShader: `varying vec3 vColor; varying float vBrightness; uniform float time;
          void main(){vec2 p=gl_PointCoord-vec2(.5); float d=length(p); if(d>.5) discard;
            float core=exp(-d*d*45.); float halo=.35*exp(-d*6.5);
            float cross=max(0.,1.-abs(p.x)*35.)*max(0.,1.-abs(p.y)*4.)
                       +max(0.,1.-abs(p.y)*35.)*max(0.,1.-abs(p.x)*4.);
            vec3 color=mix(vColor,vec3(1.),exp(-d*d*30.));
            gl_FragColor=vec4(color,min(1.,core+halo+cross*.35)*(0.95+0.05*sin(time))*vBrightness);
            #include <colorspace_fragment>
          }` });
    }
    const galaxyCores = new THREE.Points(galaxyCoreGeometry, navigationMaterial(26));
    scene.add(galaxyCores);
    const stars = new THREE.Points(geometry, new THREE.ShaderMaterial({ transparent: true, depthWrite: false,
      uniforms: { pixelRatio: { value: Math.min(window.devicePixelRatio || 1, 2) } },
      vertexShader: `attribute float starSize; attribute vec3 nodeColor; varying vec3 vColor; uniform float pixelRatio;
        void main() { vColor=nodeColor; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); gl_PointSize=starSize*pixelRatio; }`,
      fragmentShader: `varying vec3 vColor;
        void main() { float d=length(gl_PointCoord-vec2(.5)); if(d>.5) discard;
          float core=exp(-d*d*45.); float halo=.45*exp(-d*6.5);
          vec3 color=mix(vColor,vec3(1.),exp(-d*d*30.));
          gl_FragColor=vec4(color,min(1.,core+halo)*.92);
          #include <colorspace_fragment>
        }`,
    }));
    scene.add(stars);
    const hubPositions = new Float32Array(subjects.length * 3), hubColors = new Float32Array(subjects.length * 3);
    subjects.forEach((subject, index) => {
      layout.centers.get(subject.id)?.toArray(hubPositions, index * 3);
      new THREE.Color(LIFE_PALETTES[layout.volumes.indexOf(subject.volume) % LIFE_PALETTES.length]).toArray(hubColors, index * 3);
    });
    const hubGeometry = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(hubPositions, 3));
    hubGeometry.setAttribute('nodeColor', new THREE.BufferAttribute(hubColors, 3));
    hubGeometry.setAttribute('brightness', new THREE.BufferAttribute(new Float32Array(subjects.length).fill(1), 1));
    const hubs = new THREE.Points(hubGeometry, navigationMaterial(13));
    scene.add(hubs);
    const structures = layout.structuralEdges.map((group, index) => {
      const guide = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(group.points),
        new THREE.LineBasicMaterial({ color: LIFE_PALETTES[index % LIFE_PALETTES.length], transparent: true, opacity: .16, depthWrite: false }));
      scene.add(guide); return guide;
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
    lines.frustumCulled = false;
    scene.add(lines);
    const pulseGeometry = new THREE.BufferGeometry();
    pulseGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(), 3));
    const pulses = new THREE.Points(pulseGeometry, new THREE.PointsMaterial({ color: '#fff0c5', map: dot,
      size: 7, sizeAttenuation: false, transparent: true, opacity: .9, depthWrite: false }));
    pulses.frustumCulled = false;
    scene.add(pulses);
    const motion = createLifeMotion(entries, layout);
    let movingStars = false, lastMotion = 0, pointerActive = false;
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
    let focus: THREE.Vector3 | null = null, focusDirection: THREE.Vector3 | null = null, focusDistance = 0, frame = 0;
    function schedule() { if (!frame) frame = requestAnimationFrame(render); }
    function fly(target: THREE.Vector3, distance: number, direction: THREE.Vector3 | null = null) {
      focus = target.clone(); focusDistance = distance; focusDirection = direction; schedule();
    }
    function render(now: number) {
      frame = 0;
      (galaxyCores.material as THREE.ShaderMaterial).uniforms.time.value = now / 2000;
      (hubs.material as THREE.ShaderMaterial).uniforms.time.value = now / 2000;
      if (movingStars && !pointerActive && !gravity.active() && !document.hidden) {
        if (lastMotion) {
          motion.advance((now - lastMotion) / 1000);
          geometry.getAttribute('position').needsUpdate = true;
          subjects.forEach((subject, index) => layout.centers.get(subject.id)?.toArray(hubPositions, index * 3));
          hubGeometry.getAttribute('position').needsUpdate = true;
          motion.transformDust(dustData.positions, dustBase, dustData.groups);
          dustGeometry.getAttribute('position').needsUpdate = true;
          structures.forEach((guide, group) => {
            const attribute = guide.geometry.getAttribute('position') as THREE.BufferAttribute;
            layout.structuralEdges[group].points.forEach((point, index) => attribute.setXYZ(index, point.x, point.y, point.z));
            attribute.needsUpdate = true;
          });
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
      labels.update(camera, labelsVisible, labelVolume, labelSubject, labelSelected);
      const portalPoint = portal.point();
      if (portalPoint) {
        portalProjection.copy(portalPoint).project(camera);
        portal.position((portalProjection.x + 1) * canvas.clientWidth / 2 + 10,
          (1 - portalProjection.y) * canvas.clientHeight / 2 + 10, portalProjection.z < 1 && Math.abs(portalProjection.x) < .95 && Math.abs(portalProjection.y) < .95);
      }
      if (focus || moving || (movingStars && !document.hidden)) schedule();
    }
    const visibility = () => { lastMotion = 0; if (!document.hidden && movingStars) schedule(); };
    document.addEventListener('visibilitychange', visibility);
    controls.addEventListener('change', schedule);
    const resize = () => {
      const width = Math.max(1, element.clientWidth), height = Math.max(1, element.clientHeight);
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      if (webgl.getPixelRatio() !== ratio) {
        webgl.setPixelRatio(ratio);
        (stars.material as THREE.ShaderMaterial).uniforms.pixelRatio.value = ratio;
        (galaxyCores.material as THREE.ShaderMaterial).uniforms.pixelRatio.value = ratio;
        (hubs.material as THREE.ShaderMaterial).uniforms.pixelRatio.value = ratio;
      }
      camera.aspect = width / height;
      if (width > 760) camera.setViewOffset(width, height, Math.round(width * .06), 0, width, height);
      else camera.clearViewOffset();
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
        setHover(target ? { title, x: event.offsetX, y: event.offsetY } : null);
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
    const color = new THREE.Color();
    let lastFocus = '';
    const controller: LifeDrawing = {
      update(selected, subject, highlights, connect = true, volume = null) {
        labelsVisible = !selected && !subject && !volume;
        labelVolume = volume; labelSubject = subject; labelSelected = !!selected;
        portal.select(selected);
        const chosen = entries.find((entry) => entry.id === selected), related = new Set(chosen?.links ?? []);
        const matched = new Set(highlights);
        const activeVolume = volume ?? subjects.find((item) => item.id === subject)?.volume ?? chosen?.volume ?? null;
        structures.forEach((guide, index) => {
          (guide.material as THREE.LineBasicMaterial).opacity = activeVolume && layout.volumes[index] !== activeVolume ? .032 : .16;
        });
        const coreBrightness = galaxyCoreGeometry.getAttribute('brightness') as THREE.BufferAttribute;
        layout.volumes.forEach((item, index) => coreBrightness.setX(index, activeVolume && item !== activeVolume ? .2 : 1));
        coreBrightness.needsUpdate = true;
        const subjectBrightness = hubGeometry.getAttribute('brightness') as THREE.BufferAttribute;
        subjects.forEach((item, index) => subjectBrightness.setX(index, activeVolume && item.volume !== activeVolume ? .2 : 1));
        subjectBrightness.needsUpdate = true;
        if (chosen) for (const entry of entries) if (entry.links.includes(chosen.id)) related.add(entry.id);
        entries.forEach((entry, i) => {
          color.set(LIFE_PALETTES[layout.volumes.indexOf(entry.volume) % LIFE_PALETTES.length]);
          const dim = subject && entry.subject !== subject || volume && entry.volume !== volume ? .22 : selected && entry.id !== selected && !related.has(entry.id) ? .28
            : !selected && matched.size && !matched.has(entry.id) ? .22 : 1;
          color.multiplyScalar(dim);
          (geometry.getAttribute('nodeColor') as THREE.BufferAttribute).setXYZ(i, color.r, color.g, color.b);
        });
        geometry.getAttribute('nodeColor').needsUpdate = true;
        const origin = selected ? layout.locations.get(selected) : undefined;
        liveSelectedPoint = origin; selectedGeometry.setFromPoints(origin ? [origin] : []);
        const linePoints: THREE.Vector3[] = [];
        if (origin) for (const id of related) {
          const target = layout.locations.get(id);
          if (target) linePoints.push(origin, target);
        }
        if (!origin && connect && highlights.length > 1) {
          const trace = sampleLifeTrace(entries, highlights);
          for (let index = 1; index < trace.length; index++) {
            const a = layout.locations.get(trace[index - 1]), b = layout.locations.get(trace[index]);
            if (a && b) linePoints.push(a, b);
          }
        }
        liveLinePoints = linePoints;
        lineGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(linePoints.length / 2 * arcSegments * 6), 3));
        updateArcs();
        pulseGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(linePoints.length / 2 * 3), 3));
        const target = origin ?? (subject ? layout.centers.get(subject) : volume ? layout.volumeCenters.get(volume) : undefined);
        const key = selected ? `entry:${selected}` : subject ? `subject:${subject}` : volume ? `volume:${volume}` : '';
        if (target && key !== lastFocus) fly(target, origin ? 285 : subject ? 390 : 590);
        else if (!target && lastFocus) { focus = null; schedule(); } else schedule();
        lastFocus = key;
      },
      setMotion(enabled) { movingStars = enabled; lastMotion = 0; if (enabled && !document.hidden) schedule(); },
      reset() { fly(new THREE.Vector3(), 1165, overviewDirection); },
      dispose() {
        movingStars = false; document.removeEventListener('visibilitychange', visibility);
        labels.dispose(); portal.dispose();
        window.clearTimeout(gravityTimer); gravityAnimation.dispose();
        cancelAnimationFrame(frame); observer.disconnect(); controls.removeEventListener('change', schedule); controls.dispose();
        canvas.removeEventListener('pointermove', move); canvas.removeEventListener('pointerdown', pointerDown);
        canvas.removeEventListener('pointerup', pointerUp); canvas.removeEventListener('pointerleave', leave);
        canvas.removeEventListener('pointercancel', pointerCancel);
        geometry.dispose(); (stars.material as THREE.Material).dispose(); hubGeometry.dispose(); (hubs.material as THREE.Material).dispose();
        dustGeometry.dispose(); (dust.material as THREE.Material).dispose();
        galaxyCoreGeometry.dispose(); (galaxyCores.material as THREE.Material).dispose();
        selectedGeometry.dispose(); (selectedStar.material as THREE.Material).dispose(); lineGeometry.dispose(); (lines.material as THREE.Material).dispose();
        pulseGeometry.dispose(); (pulses.material as THREE.Material).dispose();
        structures.forEach((guide) => { guide.geometry.dispose(); (guide.material as THREE.Material).dispose(); });
        coreGeometry.dispose(); (core.material as THREE.Material).dispose();
        nebula.dispose(); dot.dispose(); webgl.dispose(); canvas.remove();
      },
    };
    drawing.current = controller; controller.update(selectedId, subjectId, highlightIds, connectHighlights, volumeId); controller.setMotion(motionEnabled);
    return () => { controller.dispose(); drawing.current = null; };
    // Selection changes update the existing scene without rebuilding it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries, subjects]);
  useEffect(() => { drawing.current?.update(selectedId, subjectId, highlightIds, connectHighlights, volumeId); }, [selectedId, subjectId, highlightIds, connectHighlights, volumeId]);
  useEffect(() => { drawing.current?.setMotion(motionEnabled); }, [motionEnabled]);
  useEffect(() => { if (resetSerial) drawing.current?.reset(); }, [resetSerial]);
  return <div className="life-scene" ref={host} aria-label="知识星图：拖动旋转，滚轮缩放，点击星点或学科星团">
    {hover && <div className="life-tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>{hover.title}</div>}
  </div>;
}
