import * as THREE from 'three';
import type { LifeEntry } from '../life';

/** Spread a temporary filter constellation across represented subjects. */
export function sampleLifeTrace(entries: LifeEntry[], highlights: readonly string[], limit = 30): string[] {
  if (highlights.length <= limit) return [...highlights];
  const selected = new Set(highlights), groups = new Map<string, string[]>();
  for (const entry of entries) if (selected.has(entry.id)) {
    const group = groups.get(entry.subject); if (group) group.push(entry.id); else groups.set(entry.subject, [entry.id]);
  }
  const result: string[] = [], lists = [...groups.values()];
  for (let offset = 0; result.length < limit; offset++) {
    let found = false;
    for (const list of lists) if (offset < list.length && result.length < limit) { result.push(list[offset]); found = true; }
    if (!found) break;
  }
  return result;
}

/** Bezier-like elevated arc between actual 3D endpoints; no new relation is created. */
export function lifeArcPoint(a: THREE.Vector3, b: THREE.Vector3, t: number, out: THREE.Vector3) {
  const height = Math.min(65, Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z) * .16);
  return out.set(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t,
    a.z + (b.z - a.z) * t + 4 * t * (1 - t) * height);
}
