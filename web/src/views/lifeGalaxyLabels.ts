import * as THREE from 'three';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';

/** Accessible, screen-space labels track the actual centers as the camera moves. */
export function createLifeGalaxyLabels(host: HTMLElement, layout: ReturnType<typeof lifeGalaxyLayout>, onVolume: (id: string) => void) {
  const layer = document.createElement('div'); layer.className = 'life-galaxy-labels';
  const rows = layout.volumes.map((volume, index) => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'life-galaxy-label';
    button.setAttribute('aria-label', `进入${volume}星系`);
    const number = document.createElement('small'); number.textContent = `0${index + 1} / GALAXY`;
    const title = document.createElement('span'); title.textContent = volume;
    button.append(number, title); button.addEventListener('click', () => onVolume(volume)); layer.append(button);
    return { button, point: layout.volumeCenters.get(volume)! };
  });
  host.append(layer);
  const vector = new THREE.Vector3();
  return {
    update(camera: THREE.Camera, visible: boolean) {
      for (const row of rows) {
        vector.copy(row.point).project(camera);
        const show = visible && vector.z < 1 && vector.x > -.98 && vector.x < .98 && vector.y > -.9 && vector.y < .9;
        row.button.hidden = !show;
        if (show) { row.button.style.left = `${(vector.x + 1) * 50}%`; row.button.style.top = `${(1 - vector.y) * 50}%`; }
      }
    },
    dispose() { layer.remove(); },
  };
}
