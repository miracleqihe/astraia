import * as THREE from 'three';

// The surface refracts the rendered scene itself. It is only allocated and
// rendered during a crossing or a recent pointer interaction.
const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const fragmentShader = `
  uniform sampler2D uScene;
  uniform vec2 uCenter;
  uniform vec2 uPointer;
  uniform float uAspect;
  uniform float uProgress;
  uniform float uDirection;
  uniform float uPointerStrength;
  uniform float uMotionScale;
  uniform float uTime;
  varying vec2 vUv;

  void main() {
    vec2 aspect = vec2(uAspect, 1.0);
    vec2 q = (vUv - uCenter) * aspect;
    float r = max(length(q), 0.0001);
    float angle = atan(q.y, q.x);
    float phase = clamp(uProgress, 0.0, 1.0);
    float impact = pow(max(0.0, sin(3.14159265 * phase)), 0.72) * uMotionScale;
    float travel = phase * phase * (3.0 - 2.0 * phase);

    // A nonuniform, curved refractive front expands past the observer.
    float fold = sin(angle * 3.0 + phase * 5.0) * 0.055
      + sin(angle * 6.0 - phase * 3.0) * 0.022;
    float frontRadius = (uDirection > 0.0 ? 0.05 + travel * 1.05 : 1.10 - travel * 1.05) + fold;
    float surface = exp(-pow((r - frontRadius) / (0.16 + impact * 0.09), 2.0));
    float swell = exp(-r * r * 2.3);
    float interference = sin(r * 13.0 - phase * 13.0 + sin(angle * 4.0) * 0.6);
    vec2 radial = q / r / aspect;
    vec2 drift = vec2(sin(q.y * 8.0 + phase * 4.0), cos(q.x * 8.0 - phase * 3.0));
    vec2 warped = uCenter + (vUv - uCenter) * (1.0 - impact * 0.115)
      + radial * impact * (0.022 * swell + 0.007 * interference * surface)
      + drift * surface * impact * 0.0035;

    // A small local lens makes pointer movement press the same membrane.
    vec2 pq = (vUv - uPointer) * aspect;
    float pointerDistance = length(pq);
    float pointerLens = exp(-pointerDistance * pointerDistance * 105.0) * uPointerStrength;
    warped += (pq / aspect) * pointerLens * 0.075;

    float split = surface * impact * 0.00035;
    vec4 centerSample = texture2D(uScene, clamp(warped, 0.0, 1.0));
    vec3 color;
    color.r = texture2D(uScene, clamp(warped + radial * split, 0.0, 1.0)).r;
    color.g = centerSample.g;
    color.b = texture2D(uScene, clamp(warped - radial * split, 0.0, 1.0)).b;

    vec3 warm = vec3(0.78, 0.46, 0.18);
    vec3 cool = vec3(0.31, 0.60, 0.72);
    vec3 spectral = mix(warm, cool, smoothstep(-0.7, 0.7, sin(angle * 2.0 + phase * 2.4)));
    spectral = mix(spectral, uDirection > 0.0 ? cool : warm, 0.28);
    float caustic = 0.35 + 0.65 * pow(0.5 + 0.5 * sin(angle * 5.0 + r * 13.0 - phase * 8.0), 3.0);
    color += spectral * impact * surface * caustic * 0.075;
    color += vec3(0.18, 0.23, 0.24) * pointerLens * 0.035;
    float filmAlpha = impact * surface * (0.035 + caustic * 0.075) + pointerLens * 0.018;
    gl_FragColor = vec4(color, max(centerSample.a, filmAlpha));
    #include <colorspace_fragment>
  }
`;

export function createMembraneRefraction(renderer, { reducedMotion = false } = {}) {
  const source = renderer.domElement;
  const isSoftware = renderer.isSoftware || typeof renderer.setRenderTarget !== 'function';
  let width = 1, height = 1, centerX = .5, centerY = .5;
  let crossingStart = -Infinity, duration = reducedMotion ? 420 : 1950, direction = 1;
  let pointerX = .5, pointerY = .5, pointerUntil = 0, pointerStrength = 0;
  let transformed = false;
  let target, postScene, postCamera, quad, material;

  if (!isSoftware) {
    target = new THREE.WebGLRenderTarget(1, 1, { depthBuffer: true, stencilBuffer: false });
    target.texture.minFilter = THREE.LinearFilter;
    target.texture.magFilter = THREE.LinearFilter;
    material = new THREE.ShaderMaterial({
      uniforms: {
        uScene: { value: target.texture }, uCenter: { value: new THREE.Vector2(.5, .5) },
        uPointer: { value: new THREE.Vector2(.5, .5) }, uAspect: { value: 1 },
        uProgress: { value: 1 }, uDirection: { value: 1 }, uPointerStrength: { value: 0 },
        uMotionScale: { value: reducedMotion ? .18 : 1 }, uTime: { value: 0 },
      },
      vertexShader, fragmentShader, depthWrite: false, depthTest: false, toneMapped: false,
    });
    postScene = new THREE.Scene();
    postCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    quad.frustumCulled = false;
    postScene.add(quad);
  }

  function resize(w, h, dpr = 1) {
    width = Math.max(1, w); height = Math.max(1, h);
    if (target) {
      const pixelRatio = Math.min(1.25, Math.max(1, dpr || 1));
      target.setSize(Math.round(width * pixelRatio), Math.round(height * pixelRatio));
      material.uniforms.uAspect.value = width / height;
    }
  }

  function cross(intoSpirit, x, y) {
    crossingStart = performance.now();
    direction = intoSpirit ? 1 : -1;
    centerX = Math.max(0, Math.min(1, x / width));
    centerY = Math.max(0, Math.min(1, 1 - y / height));
  }

  function pointer(x, y, active, enabled) {
    if (!active || !enabled || reducedMotion) { pointerUntil = 0; return; }
    pointerX = Math.max(0, Math.min(1, x / width));
    pointerY = Math.max(0, Math.min(1, 1 - y / height));
    pointerUntil = performance.now() + 900;
  }

  function render(scene, camera, now) {
    const p = Math.max(0, Math.min(1, (now - crossingStart) / duration));
    const crossing = p < 1;
    const desiredPointer = now < pointerUntil && !reducedMotion ? .8 : 0;
    pointerStrength += (desiredPointer - pointerStrength) * .11;
    const lens = pointerStrength > .015;
    if (isSoftware) {
      if (crossing && !reducedMotion) {
        const pulse = Math.pow(Math.max(0, Math.sin(Math.PI * p)), .72);
        source.style.transformOrigin = `${centerX * 100}% ${(1 - centerY) * 100}%`;
        source.style.transform = `scale(${(1 + pulse * .085).toFixed(4)})`;
        transformed = true;
      } else if (transformed) {
        source.style.transform = '';
        source.style.transformOrigin = '';
        transformed = false;
      }
      renderer.render(scene, camera);
      return;
    }
    if (!crossing && !lens) {
      renderer.render(scene, camera);
      return;
    }
    const u = material.uniforms;
    u.uProgress.value = crossing ? p : 1;
    u.uDirection.value = direction;
    u.uCenter.value.set(centerX, centerY);
    u.uPointer.value.set(pointerX, pointerY);
    u.uPointerStrength.value = pointerStrength;
    u.uTime.value = now * .001;
    renderer.setRenderTarget(target);
    renderer.render(scene, camera);
    renderer.setRenderTarget(null);
    renderer.render(postScene, postCamera);
  }

  function dispose() {
    if (transformed) { source.style.transform = ''; source.style.transformOrigin = ''; }
    target?.dispose(); quad?.geometry.dispose(); material?.dispose();
  }
  return { resize, cross, pointer, render, dispose };
}
