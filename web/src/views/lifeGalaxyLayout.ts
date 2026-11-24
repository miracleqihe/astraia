import * as THREE from 'three';
import type { LifeEntry, LifeSubject } from '../life';

export const LIFE_PALETTES = ['#F59E0B', '#38BDF8', '#10B981', '#A855F7', '#FDE047'];

/** Stable, semantic geometry: each book volume has its own celestial morphology. */
export function lifeGalaxyLayout(entries: LifeEntry[], subjects: LifeSubject[]) {
  const volumes = [...new Set(subjects.map((subject) => subject.volume))];
  const subjectIndex = new Map(subjects.map((subject, index) => [subject.id, index]));
  const volumeCenters = new Map<string, THREE.Vector3>();
  const centers = new Map<string, THREE.Vector3>();
  const positions = new Float32Array(entries.length * 3);
  const locations = new Map<string, THREE.Vector3>();
  const structuralEdges: Array<{ volume: string; points: THREE.Vector3[] }> = [];
  const counts = new Map<string, number>();
  const groups = volumes.map((volume) => subjects.filter((subject) => subject.volume === volume));
  const localSubjectIndex = new Map(groups.flatMap((group) => group.map((subject, index) => [subject.id, index] as const)));
  volumes.forEach((volume, index) => {
    const angle = index * Math.PI * 2 / volumes.length - Math.PI / 2;
    const radius = [258, 255, 270, 262, 245][index] ?? 255;
    volumeCenters.set(volume, new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius,
      [28, -12, 48, -35, 20][index] ?? 0));
  });

  // The construction volume uses real icosahedral vertices and edges.
  const ico = new THREE.IcosahedronGeometry(1, 0);
  const raw = ico.getAttribute('position'), uniqueEdges = new Map<string, [THREE.Vector3, THREE.Vector3]>();
  const key = (v: THREE.Vector3) => `${v.x.toFixed(4)},${v.y.toFixed(4)},${v.z.toFixed(4)}`;
  for (let i = 0; i < raw.count; i += 3) {
    const tri = [0, 1, 2].map((offset) => new THREE.Vector3().fromBufferAttribute(raw, i + offset).normalize());
    for (let j = 0; j < 3; j++) {
      const a = tri[j], b = tri[(j + 1) % 3], pair = [key(a), key(b)].sort().join('|');
      if (!uniqueEdges.has(pair)) uniqueEdges.set(pair, [a, b]);
    }
  }
  ico.dispose();
  const crystalEdges = [...uniqueEdges.values()];
  const jitter = (n: number) => { const v = Math.sin(n * 127.1 + 311.7) * 43758.5453; return v - Math.floor(v) - .5; };
  function localPosition(volumeIndex: number, subject: LifeSubject, sub: number, index: number, count: number) {
    const u = (index + .5) / Math.max(1, count), n = index + (subjectIndex.get(subject.id) ?? 0) * 8191;
    if (volumeIndex === 0) {
      const ring = subject.id === 'HEA' ? index % 2 : 2 + index % 2;
      const radius = [40, 54, 76, 92][ring] * (1 + jitter(n) * .018);
      const theta = index * 2.399963, tilt = [.25, -.35, .42, -.27][ring];
      return new THREE.Vector3(radius * Math.cos(theta), radius * Math.sin(theta) * Math.cos(tilt), radius * Math.sin(theta) * Math.sin(tilt));
    }
    if (volumeIndex === 1) {
      const theta = .15 + u * 3.35, radius = 12 * Math.exp(.59 * theta);
      const angle = theta + sub * Math.PI * 2 / 5 + jitter(n) * .075;
      return new THREE.Vector3(radius * Math.cos(angle), radius * Math.sin(angle), jitter(n + 4) * (3 + radius * .09));
    }
    if (volumeIndex === 2) {
      const edge = crystalEdges[index % crystalEdges.length], t = ((Math.floor(index / crystalEdges.length) + .5) * .61803398875) % 1;
      const radius = subject.id === 'TEC' ? 47 : subject.id === 'ARC' ? 72 : 99;
      return edge[0].clone().lerp(edge[1], t).multiplyScalar(radius);
    }
    if (volumeIndex === 3) {
      const t = u * Math.PI * 2 + sub * .026, tube = 20 + (sub - 1.5) * 2.1;
      return new THREE.Vector3((53 + tube * Math.cos(3 * t)) * Math.cos(2 * t),
        (53 + tube * Math.cos(3 * t)) * Math.sin(2 * t), tube * Math.sin(3 * t) + jitter(n) * 1.4);
    }
    const theta = (sub + u - .5) * Math.PI * 2 / Math.max(1, groups[volumeIndex].length);
    const radius = 43 + 39 * Math.cos(6 * theta) + jitter(n) * 1.6;
    return new THREE.Vector3(radius * Math.cos(theta), radius * Math.sin(theta),
      18 * Math.sin(6 * theta) ** 2 + Math.max(0, jitter(n + 7)) * 14);
  }
  for (const [volumeIndex, volume] of volumes.entries()) {
    const center = volumeCenters.get(volume)!;
    groups[volumeIndex].forEach((subject, sub) => {
      const sampleIndex = Math.max(0, Math.floor(subject.count * .7));
      centers.set(subject.id, localPosition(volumeIndex, subject, sub, sampleIndex, subject.count).add(center));
    });
    const points: THREE.Vector3[] = [];
    const line = (a: THREE.Vector3, b: THREE.Vector3) => { points.push(a.add(center), b.add(center)); };
    const curve = (segments: number, fn: (u: number) => THREE.Vector3) => {
      let previous = fn(0);
      for (let i = 1; i <= segments; i++) { const next = fn(i / segments); line(previous.clone(), next.clone()); previous = next; }
    };
    if (volumeIndex === 0) for (const [r, tilt] of [[40,.25],[58,-.35],[84,.42]])
      curve(64, (u) => new THREE.Vector3(r * Math.cos(u * Math.PI * 2), r * Math.sin(u * Math.PI * 2) * Math.cos(tilt), r * Math.sin(u * Math.PI * 2) * Math.sin(tilt)));
    if (volumeIndex === 1) for (let arm = 0; arm < 5; arm++) curve(48, (u) => {
      const theta = .15 + u * 3.35, r = 12 * Math.exp(.59 * theta), a = theta + arm * Math.PI * 2 / 5;
      return new THREE.Vector3(r * Math.cos(a), r * Math.sin(a), 0);
    });
    if (volumeIndex === 2) for (const radius of [47,72,99]) for (const [a,b] of crystalEdges)
      line(a.clone().multiplyScalar(radius),b.clone().multiplyScalar(radius));
    if (volumeIndex === 3) curve(160, (u) => {
      const t = u * Math.PI * 2; return new THREE.Vector3((53 + 20 * Math.cos(3 * t)) * Math.cos(2 * t),
        (53 + 20 * Math.cos(3 * t)) * Math.sin(2 * t), 20 * Math.sin(3 * t));
    });
    if (volumeIndex === 4) curve(192, (u) => {
      const t = u * Math.PI * 2, r = 43 + 39 * Math.cos(6 * t);
      return new THREE.Vector3(r * Math.cos(t), r * Math.sin(t), 18 * Math.sin(6 * t) ** 2);
    });
    structuralEdges.push({ volume, points });
  }
  entries.forEach((entry, i) => {
    const volumeIndex = volumes.indexOf(entry.volume), subject = subjects[subjectIndex.get(entry.subject) ?? 0];
    const index = counts.get(entry.subject) ?? 0; counts.set(entry.subject, index + 1);
    const point = localPosition(volumeIndex, subject, localSubjectIndex.get(entry.subject) ?? 0, index, subject.count)
      .add(volumeCenters.get(entry.volume) ?? new THREE.Vector3());
    point.toArray(positions, i * 3); locations.set(entry.id, point);
  });
  return { volumes, centers, volumeCenters, positions, locations, subjectIndex, structuralEdges };
}
