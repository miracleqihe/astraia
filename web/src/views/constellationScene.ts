import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EVIDENCE, LAYER_ORDER, nodeColor, type GraphIndex, type GraphLink,
  type GraphNode, type Layer, type ViewSelection } from '../graph';
import { motionDuration } from './ViewControls';

const LAYER_SPACING = 120;
const MID_HEIGHT = LAYER_SPACING * 1.5;
const PAPER = '#EFECE6';
const LINE = '#EAE5D9';
const BRASS = '#C29D59';

function heightOf(layer: Layer): number {
  return (layer - 1) * LAYER_SPACING - MID_HEIGHT;
}

export function constellationLayout(nodes: readonly GraphNode[]) {
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
      const y = Number.isFinite(node.z) ? node.z - MID_HEIGHT : heightOf(layer);
      const z = (row - (rows - 1) / 2) * 102 + (layer % 2 === 0 ? -13 : 12);
      positions.set(node.id, new THREE.Vector3(x, y, z));
    });
  }
  const span = Math.max(width, depth, 370);
  for (const layer of LAYER_ORDER) {
    positions.set(`layer:${layer}`, new THREE.Vector3(span / 2 - 17, heightOf(layer), -span / 2 + 34));
  }
  return { positions, span };
}

function plateLines(vertices: number[], color: string, opacity: number) {
  const geometry = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({color, transparent: true, opacity, depthWrite: false}));
}

function layerPlane(layer: Layer, span: number): THREE.Group {
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
  group.position.y = heightOf(layer);
  group.add(plane, ...drafting);
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
type NodeVisual = THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
type EdgeVisual = { link: GraphLink; material: THREE.LineBasicMaterial };

export function mountConstellation(host: HTMLDivElement, layout: Layout, labels: Map<string, HTMLElement>) {
  const scene = new THREE.Scene();
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
  renderer.domElement.setAttribute('aria-hidden', 'true');
  host.appendChild(renderer.domElement);

  const camera = new THREE.PerspectiveCamera(34, 1, 1, 6500);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = motionDuration(1) > 0;
  controls.dampingFactor = 0.09;
  controls.minPolarAngle = 0.2;
  controls.maxPolarAngle = Math.PI * 0.76;
  controls.minDistance = 210;
  controls.maxDistance = 4600;
  const home = new THREE.Vector3();
  const zero = new THREE.Vector3();
  const projection = new THREE.Vector3();
  let width = 1;
  let height = 1;
  let animation: { at: number; duration: number; start: THREE.Vector3; end: THREE.Vector3;
    target: THREE.Vector3; endTarget: THREE.Vector3 } | null = null;
  controls.addEventListener('start', () => { animation = null; });

  function resize() {
    width = Math.max(1, host.clientWidth);
    height = Math.max(1, host.clientHeight);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    const framing = Math.max(1.14, 1.32 / camera.aspect, layout.span / 365);
    home.set(565, 469, 620).multiplyScalar(framing);
  }
  resize();
  camera.position.copy(home);
  controls.update();
  camera.updateMatrixWorld(true);
  const observer = new ResizeObserver(resize);
  observer.observe(host);

  const guides = new THREE.Group();
  for (const layer of LAYER_ORDER) guides.add(layerPlane(layer, layout.span));
  const marks = new THREE.Group();
  const edges = new THREE.Group();
  const probe = new THREE.Group();
  scene.add(guides, edges, marks, probe);
  const nodeVisuals = new Map<string, NodeVisual>();
  const edgeVisuals: EdgeVisual[] = [];

  function transition(end: THREE.Vector3, endTarget: THREE.Vector3, duration: number) {
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
    renderer.render(scene, camera);
    for (const [id, label] of labels) {
      const position = layout.positions.get(id);
      if (!position) continue;
      projection.copy(position).project(camera);
      const visible = Math.abs(projection.x) < 1.04 && Math.abs(projection.y) < 1.04 && Math.abs(projection.z) <= 1;
      label.style.visibility = visible ? 'visible' : 'hidden';
      if (visible) {
        const x = (projection.x + 1) * width / 2;
        const y = (1 - projection.y) * height / 2;
        label.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      }
    }
  }
  renderer.setAnimationLoop(render);

  return {
    updateGraph(graph: GraphIndex) {
      disposeContents(marks);
      disposeContents(edges);
      nodeVisuals.clear();
      edgeVisuals.length = 0;
      for (const node of graph.nodes) {
        const position = layout.positions.get(node.id);
        if (!position) continue;
        const color = nodeColor(node);
        const mesh = new THREE.Mesh(nodeGeometry(node.z_layer), new THREE.MeshBasicMaterial({
          color, transparent: true,
        }));
        mesh.position.copy(position);
        mesh.rotation.set(0.2, node.z_layer * 0.38, 0.18);
        marks.add(mesh);
        nodeVisuals.set(node.id, mesh);
      }
      for (const link of graph.links) {
        const from = layout.positions.get(link.source);
        const to = layout.positions.get(link.target);
        if (!from || !to) continue;
        const color = link.status ? EVIDENCE[link.status].color : LINE;
        const options = { color, transparent: true, opacity: 0.58, depthWrite: false };
        const dashed = link.status && link.status !== 'confirmed';
        const material = dashed
          ? new THREE.LineDashedMaterial({ ...options, dashSize: 6, gapSize: 4 })
          : new THREE.LineBasicMaterial(options);
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([from, to]), material);
        if (dashed) line.computeLineDistances();
        edges.add(line);
        edgeVisuals.push({ link, material });
      }
    },
    highlight(selection: ViewSelection) {
      const id = selection.node?.id;
      for (const [nodeId, mesh] of nodeVisuals) {
        const distance = selection.neighbors.get(nodeId);
        mesh.material.opacity = id && distance === undefined ? 0.47 : 1;
      }
      for (const { link, material } of edgeVisuals) {
        const from = selection.neighbors.get(link.source);
        const to = selection.neighbors.get(link.target);
        const immediate = from === 0 || to === 0;
        material.opacity = immediate ? 0.9 : !id || (from !== undefined && to !== undefined) ? 0.48 : 0.17;
      }
      disposeContents(probe);
      const selected = id ? layout.positions.get(id) : undefined;
      if (selected) {
        const star = mainStar();
        star.position.copy(selected);
        star.position.y += 12;
        const { x, z } = selected;
        const vertical = plateLines([x, heightOf(1) - 15, z, x, heightOf(4) + 18, z], LINE, 0.72);
        probe.add(vertical, star);
        camera.updateMatrixWorld(true);
        projection.copy(selected).project(camera);
        if (Math.abs(projection.x) > 0.85 || Math.abs(projection.y) > 0.83) {
          const shift = selected.clone().sub(controls.target);
          transition(camera.position.clone().add(shift), selected, 420);
        }
      }
    },
    reset: () => transition(home, zero, 460),
    zoom(direction: -1 | 1) {
      const offset = camera.position.clone().sub(controls.target);
      const distance = THREE.MathUtils.clamp(offset.length() * (direction > 0 ? 0.81 : 1.24),
        controls.minDistance, controls.maxDistance);
      transition(offset.setLength(distance).add(controls.target), controls.target, 315);
    },
    dispose() {
      renderer.setAnimationLoop(null);
      observer.disconnect();
      controls.dispose();
      disposeContents(guides);
      disposeContents(edges);
      disposeContents(marks);
      disposeContents(probe);
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    },
  };
}
