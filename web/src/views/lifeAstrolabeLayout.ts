import type { LifeEntry, LifeSubject } from '../life';
import { lifeGalaxyLayout } from './lifeGalaxyLayout';

/** Use the Gemini source's own 2D targets for the same real-book entries. */
export function lifeAstrolabeLayout(entries: LifeEntry[], subjects: LifeSubject[]) {
  const layout=lifeGalaxyLayout(entries,subjects);
  const fromPositions=layout.positions.slice();
  const fromCenters=new Map([...layout.centers].map(([id,p])=>[id,p.clone()]));
  entries.forEach((entry,index)=>{
    const at=index*3, x=layout.flatPositions[at], y=layout.flatPositions[at+1];
    layout.positions[at]=x; layout.positions[at+1]=y; layout.positions[at+2]=0;
    layout.locations.get(entry.id)?.set(x,y,0);
  });
  for(const [id,point] of layout.centers) {
    const target=layout.flatCenters.get(id); if(target) point.copy(target);
  }
  layout.volumes.forEach((volume,index)=>{
    const angle=index/layout.volumes.length*Math.PI*2-Math.PI/2+Math.PI/layout.volumes.length;
    layout.volumeCenters.get(volume)?.set(Math.cos(angle)*235,Math.sin(angle)*215,0);
  });
  layout.structuralEdges.forEach((guide)=>{ guide.points.length=0; });
  return {layout,fromPositions,fromCenters};
}
