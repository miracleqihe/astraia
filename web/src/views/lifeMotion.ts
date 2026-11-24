import type { LifeEntry } from '../life';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';

/** Individual, bounded drift around each stable position; no invented graph edges. */
export function createLifeMotion(entries: LifeEntry[], layout: ReturnType<typeof lifeGalaxyLayout>) {
  const base = layout.positions.slice();
  const points = entries.map((entry) => layout.locations.get(entry.id)!);
  let elapsed = 0;
  return {
    advance(seconds: number) {
      elapsed += Math.min(.2, Math.max(0, seconds));
      for (let i = 0; i < points.length; i++) {
        const phase = (i * 2.399963) % (Math.PI * 2);
        const speed = .12 + (i % 11) * .012;
        const t = elapsed * speed, amplitude = 3 + (i % 5) * .7, at = i * 3;
        const x = base[at] + amplitude * (Math.sin(phase + t) - Math.sin(phase));
        const y = base[at + 1] + amplitude * (Math.cos(phase + t) - Math.cos(phase));
        const z = base[at + 2] + 2 * (Math.sin(phase * 1.3 + t * .7) - Math.sin(phase * 1.3));
        layout.positions[at] = x; layout.positions[at + 1] = y; layout.positions[at + 2] = z;
        points[i].set(x, y, z);
      }
    },
  };
}
