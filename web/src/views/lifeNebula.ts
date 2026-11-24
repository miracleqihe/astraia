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
      void main() {
        vec2 p=(vUv-vec2(.46,.5))*vec2(aspect,1.0);
        float d=length(p)/max(.7,aspect*.55);
        vec3 inner=vec3(11.,19.,38.)/255.; vec3 middle=vec3(5.,8.,18.)/255.; vec3 outer=vec3(2.,3.,7.)/255.;
        gl_FragColor=vec4(mix(mix(inner,middle,smoothstep(0.,.48,d)),outer,smoothstep(.48,1.,d)),1.);
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
