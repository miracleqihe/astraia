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
  let destination: { x: number; y: number; z: number } | null = null, strength = 0;
  function clear() {
    for (const { id, x, y, z } of originals) {
      const point = layout.locations.get(id), index = indices.get(id);
      if (point && index !== undefined) point.set(x, y, z).toArray(layout.positions, index * 3);
    }
    originals.length = 0;
    destination = null; strength = 0;
  }
  function setStrength(value: number) {
    strength = value;
    if (!destination) return;
    for (const { id, x, y, z } of originals) {
      const point = layout.locations.get(id), index = indices.get(id);
      if (point && index !== undefined) point.set(x + (destination.x - x) * value,
        y + (destination.y - y) * value, z + (destination.z - z) * value).toArray(layout.positions, index * 3);
    }
  }
  function pull(id: string) {
    clear();
    const index = indices.get(id), origin = layout.locations.get(id);
    if (index === undefined || !origin) return;
    destination = { x: origin.x, y: origin.y, z: origin.z };
    const related = new Set([...entries[index].links, ...(incoming.get(id) ?? [])]);
    related.delete(id);
    for (const other of related) {
      const point = layout.locations.get(other), otherIndex = indices.get(other);
      if (!point || otherIndex === undefined) continue;
      originals.push({ id: other, x: point.x, y: point.y, z: point.z });
    }
    setStrength(.32);
  }
  return { pull, clear, setStrength, strength: () => strength, active: () => destination !== null };
}

/** Eased pull and release; the original graph positions remain the source of truth. */
export function animateLifeGravity(gravity: ReturnType<typeof createLifeGravity>, onChange: () => void) {
  let frame = 0;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function transition(target: number, done?: () => void) {
    cancelAnimationFrame(frame); frame = 0;
    const from = gravity.strength(), started = performance.now(), duration = reduced ? 0 : 420;
    const step = (now: number) => {
      const progress = duration ? Math.min(1, (now - started) / duration) : 1;
      const eased = 1 - Math.pow(1 - progress, 3);
      gravity.setStrength(from + (target - from) * eased); onChange();
      if (progress < 1) frame = requestAnimationFrame(step);
      else { frame = 0; done?.(); }
    };
    step(started);
  }
  return {
    pull(id: string) { gravity.pull(id); gravity.setStrength(0); transition(.32); },
    release() { if (gravity.active()) transition(0, () => { gravity.clear(); onChange(); }); },
    dispose() { cancelAnimationFrame(frame); gravity.clear(); },
  };
}
