import * as THREE from 'three';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';
import type { LifeEntry, LifeSubject } from '../life';

export interface CelestialGuide { points: THREE.Vector3[]; color: string; opacity: number; }

/** The rings, ticks and armillary are the spatial guides from the supplied Gemini scene. */
export function lifeCelestialGuides(layout: ReturnType<typeof lifeGalaxyLayout>, entries: LifeEntry[], subjects: LifeSubject[]): CelestialGuide[] {
  const guides: CelestialGuide[] = [];
  const circle = (radius: number, opacity: number, dashed = false, rotation = new THREE.Euler(), color = '#dec084') => {
    const points: THREE.Vector3[] = [], segments = 96;
    const at = (i: number) => new THREE.Vector3(Math.cos(i / segments * Math.PI * 2) * radius,
      Math.sin(i / segments * Math.PI * 2) * radius, 0).applyEuler(rotation);
    for (let i = 0; i < segments; i++) if (!dashed || i % 3 !== 2) points.push(at(i), at(i + 1));
    guides.push({ points, color, opacity });
  };
  [52,108,178,242,268].forEach((r, index) => circle(r, index === 3 ? .15 : .08, index % 2 === 1));
  const ticks: THREE.Vector3[] = [];
  for (let degrees = 0; degrees < 360; degrees += 3) {
    const a = THREE.MathUtils.degToRad(degrees), outer = degrees % 30 === 0 ? 276 : degrees % 15 === 0 ? 271 : 267.5;
    ticks.push(new THREE.Vector3(Math.cos(a) * 264, Math.sin(a) * 264, 0),
      new THREE.Vector3(Math.cos(a) * outer, Math.sin(a) * outer, 0));
  }
  guides.push({ points: ticks, color: '#dec084', opacity: .18 });
  circle(74, .16, false, new THREE.Euler(.75, .32, 0));
  circle(88, .10, true, new THREE.Euler(-.62, .55, .2), '#93c5fd');
  const chords: THREE.Vector3[] = [];
  layout.volumes.forEach((volume, index) => {
    const center = layout.volumeCenters.get(volume)!;
    chords.push(new THREE.Vector3(), center.clone(), center.clone(), layout.volumeCenters.get(layout.volumes[(index + 1) % layout.volumes.length])!.clone(),
      center.clone(), layout.volumeCenters.get(layout.volumes[(index + 2) % layout.volumes.length])!.clone());
  });
  guides.push({ points: chords, color: '#dec084', opacity: .085 });
  const branches: THREE.Vector3[] = [];
  for (const subject of subjects) {
    const hub = layout.centers.get(subject.id), center = layout.volumeCenters.get(subject.volume);
    if (!hub || !center) continue;
    branches.push(center.clone(),hub.clone());
    for (const entry of entries.filter((item) => item.subject === subject.id).slice(0,5)) {
      const point = layout.locations.get(entry.id); if (point) branches.push(hub.clone(),point.clone());
    }
  }
  guides.push({ points: branches, color: '#e2d1a8', opacity: .13 });
  return guides;
}
