import * as THREE from 'three';

/** A low-frequency screen-space nebula, used only on accelerated WebGL. */
export function createLifeNebula() {
  const scene = new THREE.Scene(), camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 2);
  camera.position.z = 1;
  const material = new THREE.ShaderMaterial({ depthTest: false, depthWrite: false,
    uniforms: { time: { value: 0 }, aspect: { value: 1 } },
    vertexShader: `varying vec2 vUv;
      void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `varying vec2 vUv;
      uniform float time;
      uniform float aspect;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }
      float noise(vec2 p) {
        vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
        return mix(mix(hash(i), hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),f.x),f.y);
      }
      float clouds(vec2 p) { float v=0., a=.5; for(int i=0;i<4;i++){ v+=a*noise(p); p=p*2.05+17.1; a*=.5; } return v; }
      void main() {
        vec2 p=(vUv-.5)*vec2(aspect,1.0);
        float n=clouds(p*3.2+vec2(time*.006,-time*.004));
        float n2=clouds(p*4.5+vec2(-time*.003,time*.004)+4.2);
        float veil=exp(-dot(p*vec2(1.2,2.0),p*vec2(1.2,2.0))*1.6);
        vec3 dark=vec3(.015,.023,.047);
        vec3 blue=vec3(.025,.12,.20)*smoothstep(.25,.8,n);
        vec3 violet=vec3(.13,.04,.19)*smoothstep(.33,.82,n2);
        vec3 emerald=vec3(.015,.095,.065)*smoothstep(.48,.86,n+n2*.18);
        gl_FragColor=vec4(dark+(blue+violet+emerald)*veil*.85,1.);
      }` });
  const geometry = new THREE.PlaneGeometry(2, 2), mesh = new THREE.Mesh(geometry, material);
  scene.add(mesh);
  return {
    render(renderer: THREE.WebGLRenderer, mainScene: THREE.Scene, mainCamera: THREE.Camera, seconds: number, aspect: number) {
      material.uniforms.time.value = seconds; material.uniforms.aspect.value = aspect;
      renderer.autoClear = false; renderer.clear(); renderer.render(scene, camera); renderer.clearDepth(); renderer.render(mainScene, mainCamera);
    },
    dispose() { geometry.dispose(); material.dispose(); },
  };
}
