import * as THREE from 'three';
import { LIFE_PALETTES } from './lifeGalaxyLayout';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';

/** Decorative particles only: never participate in picking or knowledge links. */
export function lifeStardust(layout: ReturnType<typeof lifeGalaxyLayout>, count: number) {
  const positions = new Float32Array(count * 3), colors = new Float32Array(count * 3);
  const color = new THREE.Color();
  const random = (n: number) => { const v = Math.sin(n * 127.1 + 311.7) * 43758.5453; return v - Math.floor(v); };
  for (let i = 0; i < count; i++) {
    const volumeIndex = i % layout.volumes.length;
    const center = layout.volumeCenters.get(layout.volumes[volumeIndex])!;
    const radius = Math.sqrt(random(i + 1)) * 115;
    const arm = (i % 3) * Math.PI * 2 / 3;
    const angle = arm + radius * .025 + (random(i + 908) - .5) * .85;
    positions[i * 3] = center.x + Math.cos(angle) * radius;
    positions[i * 3 + 1] = center.y + Math.sin(angle) * radius;
    positions[i * 3 + 2] = center.z + (random(i + 3701) - .5) * (22 + radius * .35);
    color.set(LIFE_PALETTES[volumeIndex % LIFE_PALETTES.length]).multiplyScalar(.25 + random(i + 17) * .2);
    color.toArray(colors, i * 3);
  }
  return { positions, colors };
}
