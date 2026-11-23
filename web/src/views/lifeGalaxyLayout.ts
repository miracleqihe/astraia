import * as THREE from 'three';
import type { LifeEntry, LifeSubject } from '../life';

export const LIFE_PALETTES = ['#c8a86c', '#e3dbca', '#92b4aa', '#aebbc7', '#d0b69b'];

/** Five spiral arms follow the handbook's five volumes; only cited links are edges. */
export function lifeGalaxyLayout(entries: LifeEntry[], subjects: LifeSubject[]) {
  const volumes = [...new Set(subjects.map((subject) => subject.volume))];
  const subjectIndex = new Map(subjects.map((subject, index) => [subject.id, index]));
  const centers = new Map<string, THREE.Vector3>();
  for (const [arm, volume] of volumes.entries()) {
    const group = subjects.filter((subject) => subject.volume === volume);
    group.forEach((subject, index) => {
      const radius = 125 + (index + .5) / group.length * 295;
      const angle = arm * Math.PI * 2 / volumes.length + radius / 420 * .95 - Math.PI / 2;
      centers.set(subject.id, new THREE.Vector3(Math.cos(angle) * radius,
        Math.sin(angle) * radius, Math.sin(angle * 2) * 25 + (index - (group.length - 1) / 2) * 12));
    });
  }
  const positions = new Float32Array(entries.length * 3);
  const locations = new Map<string, THREE.Vector3>();
  const counts = new Map<string, number>();
  entries.forEach((entry, i) => {
    const center = centers.get(entry.subject) ?? new THREE.Vector3();
    const index = counts.get(entry.subject) ?? 0;
    counts.set(entry.subject, index + 1);
    const subject = subjects[subjectIndex.get(entry.subject) ?? 0];
    const spread = Math.sqrt((index + .5) / (subject?.count ?? 1)) * 42;
    const angle = index * 2.399963;
    const point = new THREE.Vector3(center.x + Math.cos(angle) * spread,
      center.y + Math.sin(angle) * spread,
      center.z + Math.sin(index * 1.72 + (subjectIndex.get(entry.subject) ?? 0)) * 55);
    point.toArray(positions, i * 3);
    locations.set(entry.id, point);
  });
  return { volumes, centers, positions, locations, subjectIndex };
}
