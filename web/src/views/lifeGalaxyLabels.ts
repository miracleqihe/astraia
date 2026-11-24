import * as THREE from 'three';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';
import { LIFE_PALETTES } from './lifeGalaxyLayout';
import type { LifeSubject } from '../life';

/** Accessible, screen-space labels track the actual centers as the camera moves. */
export function createLifeGalaxyLabels(host: HTMLElement, layout: ReturnType<typeof lifeGalaxyLayout>, subjects: LifeSubject[],
  onVolume: (id: string) => void, onSubject: (id: string) => void) {
  const layer = document.createElement('div'); layer.className = 'life-galaxy-labels';
  const rows = layout.volumes.map((volume, index) => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'life-galaxy-label';
    button.setAttribute('aria-label', `进入${volume}星系`);
    const number = document.createElement('small'); number.textContent = `0${index + 1} / GALAXY`;
    number.style.color=LIFE_PALETTES[index % LIFE_PALETTES.length];
    const title = document.createElement('span'); title.textContent = volume;
    button.append(number, title); button.addEventListener('click', () => onVolume(volume)); layer.append(button);
    return { button, point: layout.volumeCenters.get(volume)!, volume, index };
  });
  const subjectRows = subjects.map((subject) => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'life-subject-label';
    button.textContent = `${subject.title} ${subject.count}`;
    button.style.setProperty('--subject-color',LIFE_PALETTES[layout.volumes.indexOf(subject.volume) % LIFE_PALETTES.length]);
    button.setAttribute('aria-label', `进入${subject.title}学科，${subject.count}条`);
    button.addEventListener('click', () => onSubject(subject.id)); layer.append(button);
    return { button, point: layout.centers.get(subject.id)!, subject };
  });
  host.append(layer);
  const vector = new THREE.Vector3();
  return {
    update(camera: THREE.Camera, visible: boolean, volume: string | null, selectedSubject: string | null, selected: boolean, flatMode = false, morph = 0) {
      const activeVolume = volume ?? subjects.find((item) => item.id === selectedSubject)?.volume ?? null;
      for (const row of rows) {
        if(morph>.5) {
          const angle=row.index/layout.volumes.length*Math.PI*2-Math.PI/2+Math.PI/layout.volumes.length;
          vector.set(Math.cos(angle)*235,Math.sin(angle)*215,0);
        } else { vector.copy(row.point); vector.y += 18; }
        vector.project(camera);
        const show = (visible || flatMode || (!selected && row.volume === activeVolume))
          && vector.z < 1 && vector.x > -.98 && vector.x < .98 && vector.y > -.9 && vector.y < .9;
        row.button.hidden = !show;
        if (show) { row.button.style.left = `${(vector.x + 1) * 50}%`; row.button.style.top = `${(1 - vector.y) * 50}%`; }
      }
      for (const row of subjectRows) {
        vector.copy(row.point); vector.y -= 10; vector.project(camera);
        const show = (flatMode || (!selected && (row.subject.volume === volume || row.subject.id === selectedSubject)))
          && vector.z < 1 && Math.abs(vector.x) < .96 && Math.abs(vector.y) < .94;
        row.button.hidden = !show;
        if (show) { row.button.style.left = `${(vector.x + 1) * 50}%`; row.button.style.top = `${(1 - vector.y) * 50}%`; }
      }
    },
    dispose() { layer.remove(); },
  };
}
