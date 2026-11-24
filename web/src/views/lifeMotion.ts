import type { LifeEntry } from '../life';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';
import type { CelestialGuide } from './lifeCelestialGuides';

/** Slow rotations follow the five volume centers; references remain unchanged. */
export function createLifeMotion(entries: LifeEntry[], layout: ReturnType<typeof lifeGalaxyLayout>, celestial: CelestialGuide[] = []) {
  const base = layout.positions.slice();
  const points = entries.map((entry) => layout.locations.get(entry.id)!);
  const volumePoints = [...layout.volumeCenters.values()].map((point) => ({ point, base: point.clone() }));
  const subjectPoints = [...layout.centers.values()].map((point) => ({ point, base: point.clone() }));
  const guides = [...layout.structuralEdges, ...celestial].map((shape) => ({ points: shape.points, base: shape.points.map((point) => point.clone()) }));
  let elapsed = 0;
  let cosine = 1, sine = 0;
  return {
    advance(seconds: number) {
      elapsed += Math.min(.2, Math.max(0, seconds));
      const angle = elapsed * .033; cosine = Math.cos(angle); sine = Math.sin(angle);
      for (let i = 0; i < points.length; i++) {
        const at = i * 3, x = base[at] * cosine + base[at + 2] * sine;
        const y = base[at + 1], z = -base[at] * sine + base[at + 2] * cosine;
        layout.positions[at] = x; layout.positions[at + 1] = y; layout.positions[at + 2] = z;
        points[i].set(x, y, z);
      }
      for (const item of [...subjectPoints, ...volumePoints])
        item.point.set(item.base.x * cosine + item.base.z * sine, item.base.y, -item.base.x * sine + item.base.z * cosine);
      guides.forEach((guide) => guide.points.forEach((point, index) => {
        const original = guide.base[index]; point.set(original.x * cosine + original.z * sine, original.y, -original.x * sine + original.z * cosine);
      }));
    },
    transformDust(target: Float32Array, original: Float32Array, dustGroups: Uint8Array) {
      for (let i = 0; i < dustGroups.length; i++) {
        const at = i * 3, x = original[at], z = original[at + 2];
        target[at] = x * cosine + z * sine; target[at + 1] = original[at + 1]; target[at + 2] = -x * sine + z * cosine;
      }
    },
    reset() { elapsed=0; this.advance(0); },
    angle() { return elapsed * .033; },
  };
}
