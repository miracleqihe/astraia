import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { feature } from 'topojson-client';
import type { GeometryCollection, Topology } from 'topojson-specification';
import atlas from 'world-atlas/countries-110m.json';
import { EVIDENCE, evidenceGroup, LAYER_ORDER, nodeColor, type EvidenceGroup, type GraphIndex, type GraphLink,
  type GraphNode, type Layer, type ViewSelection } from '../graph';
import { motionDuration } from './ViewControls';

const PAPER = '#EFECE6';
const LINE = '#EAE5D9';
const BRASS = '#C29D59';

function heightOf(layer: Layer, spacing: number): number {
  return (layer - 1) * spacing - spacing * 1.5;
}

export function constellationLayout(nodes: readonly GraphNode[], spacing = 120) {
  const positions = new Map<string, THREE.Vector3>();
  let width = 350;
  let depth = 235;
  for (const layer of LAYER_ORDER) {
    const group = nodes.filter((node) => node.z_layer === layer);
    const columns = Math.max(1, Math.ceil(Math.sqrt(group.length * 1.35)));
    const rows = Math.ceil(group.length / columns);
    width = Math.max(width, columns * 115 + 54);
    depth = Math.max(depth, rows * 100 + 32);
    group.forEach((node, index) => {
      const row = Math.floor(index / columns);
      const rowSize = Math.min(columns, group.length - row * columns);
      const x = ((index % columns) - (rowSize - 1) / 2) * 108 + (layer % 2 === 0 ? 23 : -13);
      const y = heightOf(layer, spacing);
      const z = (row - (rows - 1) / 2) * 102 + (layer % 2 === 0 ? -13 : 12);
      positions.set(node.id, new THREE.Vector3(x, y, z));
    });
  }
  const span = Math.max(width, depth, 370);
  for (const node of nodes) {
    const latitude = node.spatial?.lat;
    const longitude = node.spatial?.lng;
    if (node.z_layer === 1 && typeof latitude === 'number' && typeof longitude === 'number'
        && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180) {
      positions.set(node.id, new THREE.Vector3(longitude / 180 * span * 0.44,
        heightOf(1, spacing), -latitude / 90 * span * 0.40));
    }
  }
  for (const layer of LAYER_ORDER) {
    positions.set(`layer:${layer}`, new THREE.Vector3(span / 2 - 17, heightOf(layer, spacing), -span / 2 + 34));
  }
  return { positions, span, spacing };
}

function plateLines(vertices: number[], color: string, opacity: number) {
  const geometry = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({color, transparent: true, opacity, depthWrite: false}));
}

function coastlines(span: number): THREE.LineSegments {
  const world = feature(atlas as unknown as Topology<{ countries: GeometryCollection }>,
    atlas.objects.countries as unknown as GeometryCollection);
  const vertices: number[] = [];
  for (const item of world.features) {
    const geometry = item.geometry;
    if (!geometry || (geometry.type !== 'Polygon' && geometry.type !== 'MultiPolygon')) continue;
    const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
    for (const polygon of polygons) for (const ring of polygon) {
      for (let index = 1; index < ring.length; index++) {
        const [lonA, latA] = ring[index - 1], [lonB, latB] = ring[index];
        if (Math.abs(lonA - lonB) > 180) continue;
        vertices.push(lonA / 180 * span * .44, 1, -latA / 90 * span * .40,
          lonB / 180 * span * .44, 1, -latB / 90 * span * .40);
      }
    }
  }
  return plateLines(vertices, LINE, .45);
}

function layerPlane(layer: Layer, span: number, spacing: number): THREE.Group {
  const group = new THREE.Group();
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(span, span), new THREE.MeshBasicMaterial({
    color: PAPER, transparent: true, opacity: 0.16, side: THREE.DoubleSide, depthWrite: false,
  }));
  plane.rotation.x = -Math.PI / 2;
  plane.renderOrder = -3;
  const half = span / 2;
  const radius = half * 0.80;
  const ink: number[] = [];
  const grid: number[] = [];
  const ticks: number[] = [];
  const corners = [[-half, -half], [half, -half], [half, half], [-half, half]];
  for (let i = 0; i < corners.length; i++) {
    const [x, z] = corners[i];
    const [nextX, nextZ] = corners[(i + 1) % corners.length];
    ink.push(x, 0, z, nextX, 0, nextZ);
    const markX = x * 0.90;
    const markZ = z * 0.90;
    ink.push(markX - 5, 0, markZ, markX + 5, 0, markZ, markX, 0, markZ - 5, markX, 0, markZ + 5);
  }
  for (const ring of [radius * 0.56, radius, radius + 9]) {
    const vertices = ring < radius ? grid : ink;
    for (let tick = 0; tick < 96; tick++) {
      const angle = tick * Math.PI / 48;
      const next = (tick + 1) * Math.PI / 48;
      vertices.push(Math.cos(angle) * ring, 0, Math.sin(angle) * ring, Math.cos(next) * ring, 0, Math.sin(next) * ring);
    }
  }
  for (let tick = 0; tick < 72; tick++) {
    const angle = tick * Math.PI / 36;
    const x = Math.cos(angle);
    const z = Math.sin(angle);
    const major = tick % 6 === 0;
    if (major) grid.push(0, 0, 0, x * radius, 0, z * radius);
    ticks.push(x * (radius + (major ? 2 : 6)), 0, z * (radius + (major ? 2 : 6)), x * (radius + 9), 0, z * (radius + 9));
  }
  const drafting = [plateLines(grid, PAPER, 0.12), plateLines(ink, PAPER, 0.55), plateLines(ticks, BRASS, 0.85)];
  drafting.forEach((part) => { part.renderOrder = -2; });
  group.position.y = heightOf(layer, spacing);
  group.add(plane, ...drafting);
  if (layer === 1) group.add(coastlines(span));
  return group;
}

function nodeGeometry(layer: Layer): THREE.BufferGeometry {
  switch (layer) {
    case 1: return new THREE.IcosahedronGeometry(8.3);
    case 2: return new THREE.OctahedronGeometry(10);
    case 3: return new THREE.IcosahedronGeometry(10, 1);
    case 4: return new THREE.DodecahedronGeometry(10);
  }
}

function mainStar() {
  const shape = new THREE.Shape();
  for (let index = 0; index < 16; index++) {
    const angle = index * Math.PI / 8;
    const size = index % 2 ? 4 : index % 4 ? 10 : 15;
    const x = Math.cos(angle) * size;
    const y = Math.sin(angle) * size;
    if (index) shape.lineTo(x, y);
    else shape.moveTo(x, y);
  }
  shape.closePath();
  const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshBasicMaterial({color: BRASS, side: THREE.DoubleSide}));
  mesh.rotation.x = -Math.PI / 2;
  return mesh;
}

function disposeContents(group: THREE.Group) {
  group.traverse((object) => {
    if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
      object.geometry.dispose();
      object.material.dispose();
    }
  });
  group.clear();
}

type Layout = ReturnType<typeof constellationLayout>;
type NodeVisual = { mesh: THREE.InstancedMesh; index: number; color: string; layer: Layer };
type EdgeKind = EvidenceGroup | 'structure' | 'fiction';
type EdgeVisual = { link: GraphLink; startColors: THREE.InterleavedBufferAttribute;
  endColors: THREE.InterleavedBufferAttribute; start: number; end: number; color: string };

const EDGE_STYLES: Record<EdgeKind, { color: string; width: number; pattern?: readonly number[] }> = {
  structure: { color: LINE, width: 1 },
  confirmed: { color: EVIDENCE.confirmed.color, width: 1.75 },
  unverified: { color: BRASS, width: 1.25, pattern: [6, 4.5] },
  refuted: { color: EVIDENCE.refuted.color, width: 1.5, pattern: [8, 3, 1.7, 3] },
  fiction: { color: '#C94A6A', width: 1.25, pattern: [1.5, 7] },
};

function pushStroke(vertices: number[], from: THREE.Vector3, to: THREE.Vector3, kind: EdgeKind) {
  const pattern = EDGE_STYLES[kind].pattern;
  const length = from.distanceTo(to);
  if (!pattern || length === 0) {
    vertices.push(...from.toArray(), ...to.toArray());
    return;
  }
  for (let at = 0, index = 0; at < length; index++) {
    const end = Math.min(at + pattern[index % pattern.length], length);
    if (index % 2 === 0) vertices.push(
      ...from.clone().lerp(to, at / length).toArray(), ...from.clone().lerp(to, end / length).toArray(),
    );
    at = end;
  }
  if (kind === 'refuted') {
    const { x, y, z } = from.clone().lerp(to, .5);
    vertices.push(x - 4, y, z - 4, x + 4, y, z + 4, x + 4, y, z - 4, x - 4, y, z + 4);
  }
}

export function mountConstellation(host: HTMLDivElement, layout: Layout, labels: Map<string, HTMLElement>) {
  const scene = new THREE.Scene();
  const dense = layout.positions.size > 200;
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: !dense, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, dense ? 0.65 : 1.7));
  renderer.domElement.setAttribute('aria-hidden', 'true');
  host.appendChild(renderer.domElement);

  const camera = new THREE.PerspectiveCamera(34, 1, 1, Math.max(6500, layout.span * 8));
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = motionDuration(1) > 0;
  controls.dampingFactor = 0.09;
  controls.minPolarAngle = 0.2;
  controls.maxPolarAngle = Math.PI * 0.76;
  controls.minDistance = 210;
  controls.maxDistance = Math.max(4600, layout.span * 4);
  const home = new THREE.Vector3();
  const zero = new THREE.Vector3();
  const projection = new THREE.Vector3();
  let width = 1;
  let height = 1;
  let dirty = true;
  let animation: { at: number; duration: number; start: THREE.Vector3; end: THREE.Vector3;
    target: THREE.Vector3; endTarget: THREE.Vector3 } | null = null;
  controls.addEventListener('start', () => { animation = null; });
  controls.addEventListener('change', () => { dirty = true; });

  function resize() {
    width = Math.max(1, host.clientWidth);
    height = Math.max(1, host.clientHeight);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    dirty = true;
    const framing = Math.max(1.14, 1.32 / camera.aspect, layout.span / 320);
    home.set(565, 469, 620).multiplyScalar(framing);
  }
  resize();
  camera.position.copy(home);
  controls.update();
  camera.updateMatrixWorld(true);
  const observer = new ResizeObserver(resize);
  observer.observe(host);

  const guides = new THREE.Group();
  for (const layer of LAYER_ORDER) guides.add(layerPlane(layer, layout.span, layout.spacing));
  const marks = new THREE.Group();
  const edges = new THREE.Group();
  const probe = new THREE.Group();
  const codeLines = new THREE.Group();
  scene.add(guides, edges, marks, probe, codeLines);
  const nodeVisuals = new Map<string, NodeVisual>();
  const edgeVisuals: EdgeVisual[] = [];
  const background = new THREE.Color('#101722');
  const mixedColor = new THREE.Color();
  let soloLayer: Layer | null = null;
  let onHover: (id: string | null) => void = () => {};
  let onSelect: (id: string, compare?: boolean) => void = () => {};
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let lastHover: string | null = null;
  let pointerFrame = 0;
  let startPoint: { x: number; y: number } | null = null;

  function pick(event: PointerEvent): string | null {
    const box = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - box.left) / box.width * 2 - 1, -(event.clientY - box.top) / box.height * 2 + 1);
    camera.updateMatrixWorld();
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(marks.children, false)[0];
    if (!hit || hit.instanceId === undefined) return null;
    const ids = hit.object.userData.nodeIds as string[] | undefined;
    return ids?.[hit.instanceId] ?? null;
  }
  function pointerMove(event: PointerEvent) {
    if (event.buttons) return;
    cancelAnimationFrame(pointerFrame);
    pointerFrame = requestAnimationFrame(() => {
      const id = pick(event);
      if (id !== lastHover) { lastHover = id; onHover(id); }
    });
  }
  function pointerLeave(event: PointerEvent) {
    cancelAnimationFrame(pointerFrame);
    if (event.relatedTarget instanceof HTMLElement && event.relatedTarget.closest('.constellation-node')) return;
    lastHover = null; onHover(null);
  }
  function pointerDown(event: PointerEvent) { startPoint = { x: event.clientX, y: event.clientY }; }
  function pointerUp(event: PointerEvent) {
    if (!startPoint) return;
    if (Math.hypot(event.clientX - startPoint.x, event.clientY - startPoint.y) > 5) { startPoint = null; return; }
    const id = pick(event);
    if (id) onSelect(id, event.shiftKey);
    startPoint = null;
  }
  renderer.domElement.addEventListener('pointermove', pointerMove);
  renderer.domElement.addEventListener('pointerleave', pointerLeave);
  renderer.domElement.addEventListener('pointerdown', pointerDown);
  renderer.domElement.addEventListener('pointerup', pointerUp);

  function transition(end: THREE.Vector3, endTarget: THREE.Vector3, duration: number) {
    dirty = true;
    const length = motionDuration(duration);
    if (!length) {
      camera.position.copy(end);
      controls.target.copy(endTarget);
      controls.update();
      return;
    }
    animation = { at: performance.now(), duration: length, start: camera.position.clone(), end: end.clone(),
      target: controls.target.clone(), endTarget: endTarget.clone() };
  }

  function render(now: number) {
    if (animation) {
      const progress = Math.min(1, (now - animation.at) / animation.duration);
      const ease = 1 - (1 - Math.max(0, progress)) ** 3;
      camera.position.lerpVectors(animation.start, animation.end, ease);
      controls.target.lerpVectors(animation.target, animation.endTarget, ease);
      if (progress >= 1) animation = null;
    }
    controls.update();
    if (!dirty && !animation) return;
    renderer.render(scene, camera);
    const placements: Array<{ element: HTMLElement; x: number; y: number; priority: number }> = [];
    for (const [id, label] of labels) {
      const position = layout.positions.get(id);
      if (!position) continue;
      const isLayer = label.classList.contains('constellation-layer');
      projection.copy(position).project(camera);
      const visible = (!isLayer || !soloLayer || id === `layer:${soloLayer}`)
        && Math.abs(projection.x) < 1.04 && Math.abs(projection.y) < 1.04 && Math.abs(projection.z) <= 1;
      label.style.visibility = visible ? 'visible' : 'hidden';
      if (visible) {
        const projectedX = Math.round((projection.x + 1) * width / 2);
        const x = isLayer ? Math.max(18, Math.min(projectedX, width - label.offsetWidth - 19)) : projectedX;
        const y = Math.round((1 - projection.y) * height / 2);
        label.style.transform = `translate3d(${x}px, ${y}px, 0)`;
        if (label.classList.contains('constellation-node') && label.dataset.label === 'true') {
          const child = label.querySelector<HTMLElement>('.constellation-node-label');
          if (child) placements.push({ element: child, x, y, priority: Number(label.dataset.labelPriority ?? 3) });
        }
      }
    }
    const occupied = new Map<number, Array<[number, number]>>();
    placements.sort((a, b) => a.priority - b.priority);
    for (const item of placements) {
      const estimated = Math.min(180, Math.max(55, [...(item.element.textContent ?? '')].reduce((sum, char) => sum + (char.charCodeAt(0) > 255 ? 12 : 7), 14)));
      const preferred = item.x + estimated + 30 > width ? item.x - estimated - 16 : item.x + 14;
      const left = Math.max(16, Math.min(preferred, width - estimated - 16)), right = left + estimated;
      const shiftX = left - (item.x + 14);
      let offset = 0;
      let available = false;
      for (let attempt = 0; attempt < 20; attempt++) {
        const delta = attempt === 0 ? 0 : Math.ceil(attempt / 2) * 24 * (attempt % 2 ? -1 : 1);
        const targetY = item.y + delta;
        if (targetY < 58 || targetY > height - 90) continue;
        const row = Math.round(targetY / 24);
        const overlaps = [row - 1, row, row + 1].some((key) => (occupied.get(key) ?? []).some(([a, b]) => left < b && right > a));
        if (!overlaps) { offset = delta; available = true; break; }
      }
      item.element.style.visibility = available ? 'visible' : 'hidden';
      if (!available) continue;
      const row = Math.round((item.y + offset) / 24);
      const entries = occupied.get(row) ?? [];
      entries.push([left, right]); occupied.set(row, entries);
      item.element.style.setProperty('--label-offset', `${offset}px`);
      item.element.style.setProperty('--label-x', `${shiftX}px`);
    }
    dirty = false;
  }
  renderer.setAnimationLoop(render);

  return {
    updateGraph(graph: GraphIndex, selected: ViewSelection) {
      dirty = true;
      disposeContents(marks);
      disposeContents(edges);
      nodeVisuals.clear();
      edgeVisuals.length = 0;
      for (const layer of LAYER_ORDER) {
        const group = graph.nodes.filter((node) => node.z_layer === layer && layout.positions.has(node.id));
        if (!group.length) continue;
        const mesh = new THREE.InstancedMesh(nodeGeometry(layer), new THREE.MeshBasicMaterial({ color: '#ffffff' }), group.length);
        mesh.userData.nodeIds = group.map((node) => node.id);
        const instance = new THREE.Object3D();
        group.forEach((node, index) => {
          const color = nodeColor(node);
          instance.position.copy(layout.positions.get(node.id)!);
          instance.rotation.set(0.2, layer * .38, .18);
          instance.updateMatrix();
          mesh.setMatrixAt(index, instance.matrix);
          mesh.setColorAt(index, new THREE.Color(color));
          nodeVisuals.set(node.id, { mesh, index, color, layer });
        });
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        marks.add(mesh);
      }
      const grouped = new Map<EdgeKind, Array<{ link: GraphLink; from: THREE.Vector3; to: THREE.Vector3 }>>();
      const score = (link: GraphLink) =>
        (selected.neighbors.get(link.source) === 0 || selected.neighbors.get(link.target) === 0 ? 2 : 0) + Number(!!link.status);
      const visibleLinks = graph.links.length > 96 ? [...graph.links].sort((a, b) => score(b) - score(a)).slice(0, 96) : graph.links;
      for (const link of visibleLinks) {
        const from = layout.positions.get(link.source);
        const to = layout.positions.get(link.target);
        if (!from || !to) continue;
        const kind = link.is_fictional_quarantine ? 'fiction' : evidenceGroup(link.status) ?? 'structure';
        const items = grouped.get(kind) ?? [];
        items.push({ link, from, to });
        grouped.set(kind, items);
      }
      for (const [kind, items] of grouped) {
        const vertices: number[] = [];
        const spans = items.map(({ link, from, to }) => {
          const start = vertices.length / 6;
          pushStroke(vertices, from, to, kind);
          return { link, start, end: vertices.length / 6 };
        });
        const style = EDGE_STYLES[kind];
        const geometry = new LineSegmentsGeometry().setPositions(vertices).setColors(new Float32Array(vertices.length));
        const startColors = geometry.getAttribute('instanceColorStart') as THREE.InterleavedBufferAttribute;
        const endColors = geometry.getAttribute('instanceColorEnd') as THREE.InterleavedBufferAttribute;
        edges.add(new LineSegments2(geometry, new LineMaterial({ vertexColors: true, linewidth: style.width, depthWrite: false })));
        spans.forEach((span) => edgeVisuals.push({ ...span, startColors, endColors, color: style.color }));
      }
    },
    highlight(selection: ViewSelection, probeId: string | null, lockedId: string | null, highlightedCodes: ReadonlySet<string>, commonIds: ReadonlySet<string>, activeLayer: Layer | null) {
      dirty = true;
      const id = selection.node?.id;
      const updatedMeshes = new Set<THREE.InstancedMesh>();
      for (const [nodeId, visual] of nodeVisuals) {
        const distance = selection.neighbors.get(nodeId);
        const inSolo = !soloLayer || visual.layer === soloLayer;
        const inActive = !activeLayer || visual.layer === activeLayer;
        const opacity = !inSolo ? 0.05 : activeLayer && !inActive ? 0.18 : highlightedCodes.size ? (highlightedCodes.has(nodeId) ? 1 : 0.18)
          : id && distance === undefined ? 0.18 : 1;
        mixedColor.set(commonIds.has(nodeId) ? '#B3D0BF' : visual.color).lerp(background, 1 - opacity);
        visual.mesh.setColorAt(visual.index, mixedColor);
        updatedMeshes.add(visual.mesh);
      }
      for (const mesh of updatedMeshes) if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      const updatedColors = new Set<THREE.InterleavedBuffer>();
      for (const { link, startColors, endColors, start, end, color } of edgeVisuals) {
        const from = selection.neighbors.get(link.source);
        const to = selection.neighbors.get(link.target);
        const immediate = from === 0 || to === 0;
        const a = layout.positions.get(link.source), b = layout.positions.get(link.target);
        const inSolo = !soloLayer || (a && b && Math.abs(a.y - heightOf(soloLayer, layout.spacing)) < 1 && Math.abs(b.y - heightOf(soloLayer, layout.spacing)) < 1);
        const opacity = !inSolo ? .03 : immediate ? 0.9 : !id || (from !== undefined && to !== undefined) ? 0.48 : 0.17;
        mixedColor.set(color).lerp(background, 1 - opacity);
        for (let index = start; index < end; index++) {
          startColors.setXYZ(index, mixedColor.r, mixedColor.g, mixedColor.b);
          endColors.setXYZ(index, mixedColor.r, mixedColor.g, mixedColor.b);
        }
        updatedColors.add(startColors.data);
      }
      for (const colors of updatedColors) colors.needsUpdate = true;
      disposeContents(probe);
      for (const [nodeId, opacity] of [[lockedId, probeId === lockedId ? .78 : .35], [probeId === lockedId ? null : probeId, .78]] as const) {
        const position = nodeId ? layout.positions.get(nodeId) : undefined;
        if (!position) continue;
        if (nodeId === lockedId) {
          const star = mainStar();
          star.position.copy(position);
          star.position.y += 12;
          probe.add(star);
        }
        if (soloLayer) continue;
        const { x, z } = position;
        const vertices = [x, heightOf(1, layout.spacing) - 15, z, x, heightOf(4, layout.spacing) + 18, z];
        for (const layer of LAYER_ORDER) {
          const y = heightOf(layer, layout.spacing) + 2;
          vertices.push(x - 5, y, z, x + 5, y, z, x, y, z - 5, x, y, z + 5);
        }
        probe.add(plateLines(vertices, LINE, opacity));
      }
      const selected = lockedId ? layout.positions.get(lockedId) : undefined;
      if (selected && !soloLayer) {
        camera.updateMatrixWorld(true);
        projection.copy(selected).project(camera);
        if (!probeId && (Math.abs(projection.x) > 0.85 || Math.abs(projection.y) > 0.83)) {
          const shift = selected.clone().sub(controls.target);
          transition(camera.position.clone().add(shift), selected, 420);
        }
      }
      disposeContents(codeLines);
      const codePositions = [...highlightedCodes].map((key) => layout.positions.get(key)).filter((p): p is THREE.Vector3 => !!p);
      if (codePositions.length > 1) {
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(codePositions),
          new THREE.LineBasicMaterial({ color: BRASS, transparent: true, opacity: .9 }));
        codeLines.add(line);
      }
    },
    solo(layer: Layer | null) {
      dirty = true;
      soloLayer = layer;
      guides.children.forEach((group, index) => { group.visible = !layer || LAYER_ORDER[index] === layer; });
      controls.minPolarAngle = layer ? 0.001 : 0.2;
      controls.enableRotate = !layer;
      if (layer) {
        const target = new THREE.Vector3(0, heightOf(layer, layout.spacing), 0);
        transition(target.clone().add(new THREE.Vector3(0, Math.max(680, layout.span * 1.7), 0.01)), target, 520);
      } else transition(home, zero, 520);
    },
    reset: () => transition(home, zero, 460),
    invalidate: () => { dirty = true; },
    interactions(hover: (id: string | null) => void, select: (id: string, compare?: boolean) => void) {
      onHover = hover; onSelect = select;
    },
    zoom(direction: -1 | 1) {
      const offset = camera.position.clone().sub(controls.target);
      const distance = THREE.MathUtils.clamp(offset.length() * (direction > 0 ? 0.81 : 1.24),
        controls.minDistance, controls.maxDistance);
      transition(offset.setLength(distance).add(controls.target), controls.target, 315);
    },
    dispose() {
      renderer.setAnimationLoop(null);
      observer.disconnect();
      cancelAnimationFrame(pointerFrame);
      renderer.domElement.removeEventListener('pointermove', pointerMove);
      renderer.domElement.removeEventListener('pointerleave', pointerLeave);
      renderer.domElement.removeEventListener('pointerdown', pointerDown);
      renderer.domElement.removeEventListener('pointerup', pointerUp);
      controls.dispose();
      disposeContents(guides);
      disposeContents(edges);
      disposeContents(marks);
      disposeContents(probe);
      disposeContents(codeLines);
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    },
  };
}
