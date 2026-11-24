import type { LifeEntry } from '../life';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';

/** Slow rotations follow the five volume centers; references remain unchanged. */
export function createLifeMotion(entries: LifeEntry[], layout: ReturnType<typeof lifeGalaxyLayout>) {
  const base = layout.positions.slice();
  const points = entries.map((entry) => layout.locations.get(entry.id)!);
  const groups = entries.map((entry) => layout.volumes.indexOf(entry.volume));
  const volumeCenters = layout.volumes.map((volume) => layout.volumeCenters.get(volume)!);
  const subjectVolumes = new Map(entries.map((entry) => [entry.subject, layout.volumes.indexOf(entry.volume)]));
  const subjectPoints = [...layout.centers].map(([id, point]) => ({ point, base: point.clone(), group: subjectVolumes.get(id) ?? 0 }));
  const guides = layout.structuralEdges.map((shape) => ({ points: shape.points, base: shape.points.map((point) => point.clone()) }));
  const cos = new Float64Array(layout.volumes.length).fill(1), sin = new Float64Array(layout.volumes.length);
  let elapsed = 0;
  let rotatedX = 0, rotatedY = 0;
  function rotate(x: number, y: number, group: number) {
    const center = volumeCenters[group], dx = x - center.x, dy = y - center.y;
    rotatedX = center.x + dx * cos[group] - dy * sin[group];
    rotatedY = center.y + dx * sin[group] + dy * cos[group];
  }
  return {
    advance(seconds: number) {
      elapsed += Math.min(.2, Math.max(0, seconds));
      for (let group = 0; group < cos.length; group++) {
        const angle = elapsed * (.011 + group * .0012); cos[group] = Math.cos(angle); sin[group] = Math.sin(angle);
      }
      for (let i = 0; i < points.length; i++) {
        const phase = (i * 2.399963) % (Math.PI * 2), t = elapsed * (.08 + i % 7 * .009), at = i * 3;
        rotate(base[at], base[at + 1], groups[i]);
        const x = rotatedX + .3 * (Math.sin(phase + t) - Math.sin(phase));
        const y = rotatedY + .3 * (Math.cos(phase + t) - Math.cos(phase));
        const z = base[at + 2] + .3 * (Math.sin(phase + t) - Math.sin(phase));
        layout.positions[at] = x; layout.positions[at + 1] = y; layout.positions[at + 2] = z;
        points[i].set(x, y, z);
      }
      for (const item of subjectPoints) { rotate(item.base.x, item.base.y, item.group); item.point.set(rotatedX, rotatedY, item.base.z); }
      guides.forEach((guide, group) => guide.points.forEach((point, index) => {
        const original = guide.base[index]; rotate(original.x, original.y, group); point.set(rotatedX, rotatedY, original.z);
      }));
    },
    transformDust(target: Float32Array, original: Float32Array, dustGroups: Uint8Array) {
      for (let i = 0; i < dustGroups.length; i++) {
        const at = i * 3; rotate(original[at], original[at + 1], dustGroups[i]);
        target[at] = rotatedX; target[at + 1] = rotatedY; target[at + 2] = original[at + 2];
      }
    },
  };
}
