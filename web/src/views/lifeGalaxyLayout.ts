import * as THREE from 'three';
import type { LifeEntry, LifeSubject } from '../life';
import geminiSky from './geminiSkyGeometry.json';

export const LIFE_PALETTES = ['#ffb84d', '#4fd8eb', '#34d399', '#a78bfa', '#f5d082'];

/**
 * Use the exact visual coordinates produced by the user's Gemini HTML. The
 * geometry file contains numbers only: titles, pages and links always come
 * from the real handbook. Different subject counts are resampled locally.
 */
export function lifeGalaxyLayout(entries: LifeEntry[], subjects: LifeSubject[]) {
  const volumes = [...new Set(subjects.map((subject) => subject.volume))];
  const subjectIndex = new Map(subjects.map((subject, index) => [subject.id,index]));
  const volumeCenters = new Map<string,THREE.Vector3>(), centers = new Map<string,THREE.Vector3>();
  const flatCenters = new Map<string,THREE.Vector3>(), locations = new Map<string,THREE.Vector3>();
  const positions = new Float32Array(entries.length * 3), flatPositions = new Float32Array(entries.length * 3);
  const sizes = new Float32Array(entries.length), phases = new Float32Array(entries.length), spikes = new Float32Array(entries.length);
  const colors = new Float32Array(entries.length * 3);
  const referenceCenters = [[0,-148,22],[212,-52,-16],[142,146,18],[-138,144,-14],[-210,-54,15]];
  volumes.forEach((volume,index) => {
    const [x,y,z] = referenceCenters[index] ?? [0,0,0]; volumeCenters.set(volume,new THREE.Vector3(x,y,z));
  });
  const groups = volumes.map((volume) => subjects.filter((subject) => subject.volume === volume));
  const entryGroups = new Map<string,number[]>();
  entries.forEach((entry,index) => { const group=entryGroups.get(entry.subject); if(group) group.push(index); else entryGroups.set(entry.subject,[index]); });
  const templateGroups = new Map<string,number[][]>();
  for (const node of geminiSky.nodes) {
    const key=`${node[0]}:${node[1]}`, group=templateGroups.get(key);
    if(group) group.push(node); else templateGroups.set(key,[node]);
  }
  const color = new THREE.Color();
  groups.forEach((group,volumeIndex) => group.forEach((subject,disciplineIndex) => {
    const template = templateGroups.get(`${volumeIndex}:${disciplineIndex}`) ?? [];
    const indices = entryGroups.get(subject.id) ?? [];
    if (!template.length || !indices.length) return;
    const alpha=template[0];
    centers.set(subject.id,new THREE.Vector3(alpha[3],alpha[4],alpha[5]));
    flatCenters.set(subject.id,new THREE.Vector3(alpha[6],alpha[7],0));
    let lastTemplate=-1, duplicate=0;
    indices.forEach((entryIndex,ordinal) => {
      const slot=indices.length === 1 ? 0 : Math.round(ordinal*(template.length-1)/(indices.length-1));
      duplicate = slot === lastTemplate ? duplicate+1 : 0; lastTemplate=slot;
      const node=template[slot], offset=duplicate ? .25*duplicate : 0, at=entryIndex*3;
      const point=new THREE.Vector3(node[3]+offset,node[4]-offset,node[5]+offset);
      point.toArray(positions,at); locations.set(entries[entryIndex].id,point);
      flatPositions[at]=node[6]+offset; flatPositions[at+1]=node[7]-offset; flatPositions[at+2]=0;
      sizes[entryIndex]=node[8]; phases[entryIndex]=node[9]; spikes[entryIndex]=node[10];
      color.setRGB(node[11],node[12],node[13],THREE.SRGBColorSpace).toArray(colors,at);
    });
  }));
  if (locations.size !== entries.length) throw new Error('知识星图中有条目无法匹配其学科星域');

  // Reference geometry for the planet rings and icosahedral cage.
  const phi=(1+Math.sqrt(5))/2;
  const vertices=[[-1,phi,0],[1,phi,0],[-1,-phi,0],[1,-phi,0],[0,-1,phi],[0,1,phi],
    [0,-1,-phi],[0,1,-phi],[phi,0,-1],[phi,0,1],[-phi,0,-1],[-phi,0,1]]
    .map(([x,y,z])=>new THREE.Vector3(x,y,z).normalize());
  const crystalEdges: Array<[THREE.Vector3,THREE.Vector3]> = [];
  for(let i=0;i<vertices.length;i++) for(let j=i+1;j<vertices.length;j++)
    if(vertices[i].distanceTo(vertices[j])<1.15) crystalEdges.push([vertices[i],vertices[j]]);
  const structuralEdges: Array<{volume:string;points:THREE.Vector3[]}> = [];
  for(const [volumeIndex,volume] of volumes.entries()) {
    const center=volumeCenters.get(volume)!, points:THREE.Vector3[]=[];
    const line=(a:THREE.Vector3,b:THREE.Vector3)=>points.push(a.add(center),b.add(center));
    const circle=(radius:number,rotation:THREE.Euler) => {
      let previous=new THREE.Vector3(radius,0,0).applyEuler(rotation);
      for(let i=1;i<=96;i++) { const angle=i/96*Math.PI*2;
        const next=new THREE.Vector3(radius*Math.cos(angle),radius*Math.sin(angle),0).applyEuler(rotation);
        line(previous.clone(),next.clone()); previous=next; }
    };
    if(volumeIndex===0) for(const radius of [24,42,62,82]) circle(radius,new THREE.Euler(Math.PI/2+.44,.15,-.24));
    if(volumeIndex===2) {
      for(const [a,b] of crystalEdges) line(a.clone().multiplyScalar(58),b.clone().multiplyScalar(58));
      circle(72,new THREE.Euler(.1,.1,0)); circle(78,new THREE.Euler(0,-.1,.1));
    }
    structuralEdges.push({volume,points});
  }
  const volumeNodeIndices=volumes.map((volume)=>entries.flatMap((entry,index)=>entry.volume===volume?[index]:[]));
  return {volumes,centers,flatCenters,volumeCenters,positions,flatPositions,locations,subjectIndex,structuralEdges,volumeNodeIndices,
    reference:{sizes,phases,spikes,colors}};
}
