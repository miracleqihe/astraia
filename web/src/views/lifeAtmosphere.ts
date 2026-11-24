import * as THREE from 'three';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';
import geminiSky from './geminiSkyGeometry.json';

/** Procedural, local textures for the reference's five volume clouds and deep stars. */
export function lifeAtmosphere(scene: THREE.Scene, layout: ReturnType<typeof lifeGalaxyLayout>, starMaterial: THREE.ShaderMaterial) {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('无法创建星云纹理');
  const glow = ctx.createRadialGradient(128,128,4,128,128,126);
  glow.addColorStop(0,'rgba(255,255,255,1)'); glow.addColorStop(.28,'rgba(255,255,255,.42)');
  glow.addColorStop(.65,'rgba(255,255,255,.10)'); glow.addColorStop(1,'rgba(255,255,255,0)');
  ctx.fillStyle = glow; ctx.fillRect(0,0,256,256);
  const texture = new THREE.CanvasTexture(canvas), group = new THREE.Group(); scene.add(group);
  const clouds: Array<{ sprite: THREE.Sprite; base: THREE.Vector3; opacity: number; volume: string | null }> = [];
  for(const cloud of geminiSky.clouds) {
    const [volumeIndex,x,y,z,size,opacity,r,g,b]=cloud;
    const color=new THREE.Color().setRGB(r,g,b,THREE.SRGBColorSpace);
    const material=new THREE.SpriteMaterial({map:texture,color,transparent:true,opacity,depthWrite:false,blending:THREE.AdditiveBlending});
    const sprite=new THREE.Sprite(material); sprite.position.set(x,y,z); sprite.scale.set(size,size,1); group.add(sprite);
    clouds.push({sprite,base:sprite.position.clone(),opacity,volume:volumeIndex>=0?layout.volumes[volumeIndex]:null});
  }
  const count=geminiSky.background.length,positions=new Float32Array(count*3),colors=new Float32Array(count*3);
  const sizes=new Float32Array(count),phases=new Float32Array(count),spikes=new Float32Array(count),brightness=new Float32Array(count);
  const color=new THREE.Color();
  geminiSky.background.forEach((point,i)=>{
    positions[i*3]=point[0];positions[i*3+1]=point[1];positions[i*3+2]=point[2];
    sizes[i]=point[3];phases[i]=point[4];spikes[i]=point[5];brightness[i]=point[6];
    color.setRGB(point[7],point[8],point[9],THREE.SRGBColorSpace).toArray(colors,i*3);
  });
  const starGeometry=new THREE.BufferGeometry().setAttribute('position',new THREE.BufferAttribute(positions,3));
  starGeometry.setAttribute('nodeColor',new THREE.BufferAttribute(colors,3));
  starGeometry.setAttribute('starSize',new THREE.BufferAttribute(sizes,1));
  starGeometry.setAttribute('starPhase',new THREE.BufferAttribute(phases,1));
  starGeometry.setAttribute('starSpike',new THREE.BufferAttribute(spikes,1));
  starGeometry.setAttribute('starBrightness',new THREE.BufferAttribute(brightness,1));
  const stars=new THREE.Points(starGeometry,starMaterial); scene.add(stars);
  return {
    rotate(angle:number) { const c=Math.cos(angle),s=Math.sin(angle); for(const cloud of clouds)
      cloud.sprite.position.set(cloud.base.x*c+cloud.base.z*s,cloud.base.y,-cloud.base.x*s+cloud.base.z*c); },
    focus(volume:string|null) { for(const cloud of clouds) (cloud.sprite.material as THREE.SpriteMaterial).opacity =
      cloud.opacity * (volume && cloud.volume && volume !== cloud.volume ? .22 : 1); },
    dispose() { scene.remove(group,stars); for(const cloud of clouds) (cloud.sprite.material as THREE.SpriteMaterial).dispose();
      texture.dispose(); starGeometry.dispose(); },
  };
}
