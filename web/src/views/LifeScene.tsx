import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { LifeEntry, LifeSubject } from '../life';

interface Props {
  entries: LifeEntry[];
  subjects: LifeSubject[];
  selectedId: string | null;
  subjectId: string | null;
  onSelect: (id: string) => void;
}

interface Drawing {
  update: (selected: string | null, subject: string | null) => void;
}

const palettes = ['#c8a86c', '#e3dbca', '#92b4aa', '#aebbc7', '#d0b69b'];

export default function LifeScene({ entries, subjects, selectedId, subjectId, onSelect }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const drawing = useRef<Drawing | null>(null);
  const select = useRef(onSelect);
  const [hover, setHover] = useState<{ title: string; x: number; y: number } | null>(null);
  select.current = onSelect;

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
    renderer.setClearColor(0x101722, 1);
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(44, 1, 1, 4000);
    camera.position.set(0, -355, 1110);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = .08;
    controls.minDistance = 110;
    controls.maxDistance = 1800;
    controls.enablePan = true;

    const positions = new Float32Array(entries.length * 3);
    const colors = new Float32Array(entries.length * 3);
    const locations = new Map<string, THREE.Vector3>();
    const subjectIndex = new Map(subjects.map((item, i) => [item.id, i]));
    const subjectCounts = new Map<string, number>();
    entries.forEach((entry, i) => {
      const group = subjectIndex.get(entry.subject) ?? 0;
      const inner = group < 6;
      const angle = (inner ? group / 6 : (group - 6) / 14) * Math.PI * 2 - Math.PI / 2;
      const ring = inner ? 165 : 365;
      const index = subjectCounts.get(entry.subject) ?? 0;
      subjectCounts.set(entry.subject, index + 1);
      const spread = Math.sqrt((index + .5) / (subjects[group]?.count ?? 1)) * (inner ? 57 : 63);
      const spiral = index * 2.399963;
      const point = new THREE.Vector3(Math.cos(angle) * ring + Math.cos(spiral) * spread,
        Math.sin(angle) * ring + Math.sin(spiral) * spread, Math.sin(index * 1.72 + group) * 22);
      point.toArray(positions, i * 3);
      locations.set(entry.id, point);
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const dotCanvas = document.createElement('canvas'); dotCanvas.width = dotCanvas.height = 32;
    const dotContext = dotCanvas.getContext('2d');
    if (!dotContext) throw new Error('无法创建星点纹理');
    dotContext.fillStyle = '#fff'; dotContext.beginPath(); dotContext.arc(16, 16, 13, 0, Math.PI * 2); dotContext.fill();
    const dot = new THREE.CanvasTexture(dotCanvas);
    const stars = new THREE.Points(geometry, new THREE.PointsMaterial({ size: 5, sizeAttenuation: false,
      map: dot, vertexColors: true, transparent: true, opacity: .94, depthWrite: false }));
    scene.add(stars);
    const rings: THREE.LineLoop[] = [];
    for (const radius of [90, 165, 260, 365, 445]) {
      const points = Array.from({ length: 192 }, (_, i) => new THREE.Vector3(
        Math.cos(i / 192 * Math.PI * 2) * radius, Math.sin(i / 192 * Math.PI * 2) * radius, -27));
      const ring = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color: 0xc9b89b, transparent: true, opacity: .16 }));
      rings.push(ring); scene.add(ring);
    }
    const selectedGeometry = new THREE.BufferGeometry();
    const selectedStar = new THREE.Points(selectedGeometry, new THREE.PointsMaterial({ color: 0xffe9bd, map: dot,
      size: 12, sizeAttenuation: false, transparent: true, depthTest: false }));
    scene.add(selectedStar);
    const lineGeometry = new THREE.BufferGeometry();
    const lines = new THREE.LineSegments(lineGeometry, new THREE.LineBasicMaterial({ color: 0xc29d59,
      transparent: true, opacity: .75, depthWrite: false }));
    scene.add(lines);
    let focus: THREE.Vector3 | null = null;
    const color = new THREE.Color();
    drawing.current = {
      update(selected, subject) {
        const chosen = entries.find((entry) => entry.id === selected);
        const related = new Set(chosen?.links ?? []);
        if (chosen) for (const entry of entries) if (entry.links.includes(chosen.id)) related.add(entry.id);
        entries.forEach((entry, i) => {
          color.set(palettes[Math.floor((subjectIndex.get(entry.subject) ?? 0) / 4) % palettes.length]);
          const dim = subject && entry.subject !== subject ? .22 : selected && entry.id !== selected && !related.has(entry.id) ? .45 : 1;
          color.multiplyScalar(dim);
          (geometry.getAttribute('color') as THREE.BufferAttribute).setXYZ(i, color.r, color.g, color.b);
        });
        geometry.getAttribute('color').needsUpdate = true;
        const origin = selected ? locations.get(selected) : undefined;
        selectedGeometry.setFromPoints(origin ? [origin] : []);
        const linePoints: THREE.Vector3[] = [];
        if (origin) for (const id of related) {
          const target = locations.get(id);
          if (target) linePoints.push(origin, target);
        }
        lineGeometry.setFromPoints(linePoints);
        focus = origin?.clone() ?? null;
      },
    };
    const resize = () => {
      const width = Math.max(1, element.clientWidth), height = Math.max(1, element.clientHeight);
      camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.setSize(width, height, false);
    };
    const observer = new ResizeObserver(resize); observer.observe(element); resize();
    const raycaster = new THREE.Raycaster();
    raycaster.params.Points = { threshold: 7 };
    const pointer = new THREE.Vector2();
    let hovered = -1;
    const hit = (event: PointerEvent) => {
      const box = renderer.domElement.getBoundingClientRect();
      pointer.set((event.clientX - box.left) / box.width * 2 - 1, -(event.clientY - box.top) / box.height * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      return raycaster.intersectObject(stars)[0]?.index ?? -1;
    };
    const move = (event: PointerEvent) => {
      if (event.buttons) return;
      const index = hit(event);
      renderer.domElement.style.cursor = index >= 0 ? 'pointer' : 'grab';
      if (index !== hovered) {
        hovered = index;
        setHover(index < 0 ? null : { title: entries[index].title, x: event.offsetX, y: event.offsetY });
      }
    };
    let down = { x: 0, y: 0 };
    const pointerDown = (event: PointerEvent) => { down = { x: event.clientX, y: event.clientY }; };
    const pointerUp = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) return;
      const index = hit(event);
      if (index >= 0) select.current(entries[index].id);
    };
    const leave = () => { hovered = -1; setHover(null); };
    renderer.domElement.addEventListener('pointermove', move);
    renderer.domElement.addEventListener('pointerdown', pointerDown);
    renderer.domElement.addEventListener('pointerup', pointerUp);
    renderer.domElement.addEventListener('pointerleave', leave);
    let frame = 0;
    const animate = () => {
      if (focus) {
        const delta = focus.clone().sub(controls.target).multiplyScalar(.08);
        camera.position.add(delta); controls.target.add(delta);
        if (delta.lengthSq() < .001) focus = null;
      }
      controls.update(); renderer.render(scene, camera); frame = requestAnimationFrame(animate);
    };
    drawing.current.update(selectedId, subjectId);
    animate();
    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); controls.dispose();
      renderer.domElement.removeEventListener('pointermove', move);
      renderer.domElement.removeEventListener('pointerdown', pointerDown);
      renderer.domElement.removeEventListener('pointerup', pointerUp);
      renderer.domElement.removeEventListener('pointerleave', leave);
      geometry.dispose(); (stars.material as THREE.Material).dispose();
      selectedGeometry.dispose(); (selectedStar.material as THREE.Material).dispose();
      lineGeometry.dispose(); (lines.material as THREE.Material).dispose();
      rings.forEach((ring) => { ring.geometry.dispose(); (ring.material as THREE.Material).dispose(); });
      dot.dispose(); renderer.dispose(); renderer.domElement.remove(); drawing.current = null;
    };
    // Selection is updated separately to avoid rebuilding the 2,266-node scene.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries, subjects]);
  useEffect(() => { drawing.current?.update(selectedId, subjectId); }, [selectedId, subjectId]);
  return <div className="life-scene" ref={host} aria-label="知识星图：拖动旋转，滚轮缩放，点击星点阅读条目">
    {hover && <div className="life-tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>{hover.title}</div>}
  </div>;
}
