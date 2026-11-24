import type { LifeEntry } from '../life';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';

type Layout = ReturnType<typeof lifeGalaxyLayout>;

/** Temporarily draw the handbook's real one-hop references towards a held node. */
export function createLifeGravity(entries: LifeEntry[], layout: Layout) {
  const indices = new Map(entries.map((entry, index) => [entry.id, index]));
  const incoming = new Map<string, string[]>();
  for (const entry of entries) for (const id of entry.links) {
    const group = incoming.get(id);
    if (group) group.push(entry.id); else incoming.set(id, [entry.id]);
  }
  const originals: Array<{ id: string; x: number; y: number; z: number }> = [];
  function clear() {
    for (const { id, x, y, z } of originals) {
      const point = layout.locations.get(id), index = indices.get(id);
      if (point && index !== undefined) point.set(x, y, z).toArray(layout.positions, index * 3);
    }
    originals.length = 0;
  }
  function pull(id: string) {
    clear();
    const index = indices.get(id), origin = layout.locations.get(id);
    if (index === undefined || !origin) return;
    const related = new Set([...entries[index].links, ...(incoming.get(id) ?? [])]);
    related.delete(id);
    for (const other of related) {
      const point = layout.locations.get(other), otherIndex = indices.get(other);
      if (!point || otherIndex === undefined) continue;
      originals.push({ id: other, x: point.x, y: point.y, z: point.z });
      point.lerp(origin, .32).toArray(layout.positions, otherIndex * 3);
    }
  }
  return { pull, clear };
}
