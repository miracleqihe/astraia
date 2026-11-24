import * as THREE from 'three';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';
import geminiSky from './geminiSkyGeometry.json';

/** Decorative particles only: never participate in picking or knowledge links. */
export function lifeStardust(layout: ReturnType<typeof lifeGalaxyLayout>, count: number) {
  const positions = new Float32Array(count * 3), colors = new Float32Array(count * 3), groups = new Uint8Array(count);
  const sizes = new Float32Array(count), phases = new Float32Array(count), flatPositions = new Float32Array(count * 3);
  const color = new THREE.Color();
  for (let i = 0; i < count; i++) {
    const sourceIndex=Math.floor(i*geminiSky.dust.length/count), point=geminiSky.dust[sourceIndex], flat=geminiSky.flatDust[sourceIndex];
    groups[i]=point[0]; positions[i*3]=point[1]; positions[i*3+1]=point[2]; positions[i*3+2]=point[3];
    sizes[i]=point[4]; phases[i]=point[5];
    flatPositions[i*3]=flat[0]; flatPositions[i*3+1]=flat[1]; flatPositions[i*3+2]=flat[2];
    color.setRGB(point[6],point[7],point[8],THREE.SRGBColorSpace).toArray(colors,i*3);
  }
  // A missing volume is a schema error, not a reason to invent a coordinate.
  if (groups.some((group)=>group>=layout.volumes.length)) throw new Error('星尘与知识卷册不匹配');
  return { positions, colors, groups, sizes, phases, flatPositions };
}
