import * as THREE from 'three';
import { LIFE_PALETTES } from './lifeGalaxyLayout';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';

/** Decorative particles only: never participate in picking or knowledge links. */
export function lifeStardust(layout: ReturnType<typeof lifeGalaxyLayout>, count: number) {
  const positions = new Float32Array(count * 3), colors = new Float32Array(count * 3), groups = new Uint8Array(count);
  const color = new THREE.Color();
  const random = (n: number) => { const v = Math.sin(n * 127.1 + 311.7) * 43758.5453; return v - Math.floor(v); };
  for (let i = 0; i < count; i++) {
    const volumeIndex = i % layout.volumes.length;
    groups[i] = volumeIndex;
    const edges = layout.structuralEdges[volumeIndex].points;
    const segment = Math.floor(random(i + 1) * edges.length / 2) * 2, t = random(i + 911);
    const a = edges[segment], b = edges[segment + 1];
    positions[i * 3] = a.x + (b.x - a.x) * t + (random(i + 31) - .5) * 2.2;
    positions[i * 3 + 1] = a.y + (b.y - a.y) * t + (random(i + 73) - .5) * 2.2;
    positions[i * 3 + 2] = a.z + (b.z - a.z) * t + (random(i + 109) - .5) * 2.2;
    if (volumeIndex === 4 && i % 5 === 0) positions[i * 3 + 2] += 8 + random(i + 509) * 42;
    color.set(LIFE_PALETTES[volumeIndex % LIFE_PALETTES.length]).multiplyScalar(.25 + random(i + 17) * .2);
    color.toArray(colors, i * 3);
  }
  return { positions, colors, groups };
}
