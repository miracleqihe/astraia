import * as THREE from 'three';
import type { LifeEntry } from '../life';

/** Only connect entries that actually cite each other in the source book. */
export function sampleLifeEdges(entries: LifeEntry[], highlights: readonly string[], limit = 30): Array<[string, string]> {
  const selected = new Set(highlights), seen = new Set<string>(), edges: Array<[string, string]> = [];
  for (const entry of entries) {
    if (!selected.has(entry.id)) continue;
    for (const id of entry.links) {
      if (id === entry.id || !selected.has(id)) continue;
      const key = [entry.id, id].sort().join('|');
      if (seen.has(key)) continue;
      seen.add(key); edges.push([entry.id, id]);
      if (edges.length >= limit) return edges;
    }
  }
  return edges;
}

/** Ambient bridges are real cross-volume references, selected across volume pairs. */
export function lifeAmbientEdges(entries: LifeEntry[], limit = 8): Array<[string, string]> {
  const byId = new Map(entries.map((entry) => [entry.id, entry]));
  const seen = new Set<string>(), result: Array<[string, string]> = [];
  for (const entry of entries) for (const id of entry.links) {
    const other = byId.get(id);
    if (!other || other.volume === entry.volume) continue;
    const pair = [entry.volume, other.volume].sort().join('|');
    if (seen.has(pair)) continue;
    seen.add(pair); result.push([entry.id, other.id]);
    if (result.length >= limit) return result;
  }
  return result;
}

/** Bezier-like elevated arc between actual 3D endpoints; no new relation is created. */
export function lifeArcPoint(a: THREE.Vector3, b: THREE.Vector3, t: number, out: THREE.Vector3) {
  const distance = Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z), bend = 2 * t * (1 - t);
  const direction = a.x + a.y < b.x + b.y ? 1 : -1;
  return out.set(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t + bend * direction * distance * .08,
    a.z + (b.z - a.z) * t + bend * Math.min(95, distance * .28));
}
