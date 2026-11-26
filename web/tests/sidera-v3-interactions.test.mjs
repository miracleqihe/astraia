import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createMembraneLayer } from '../src/syzygy/membrane.js';
import { createMembraneRefraction } from '../src/syzygy/membraneRefraction.js';

test('crossing the membrane reports direction and preserves the requested origin', () => {
  const crossings = [];
  const layer = createMembraneLayer({ canvas: null, whisperHost: null, onCross: event => crossings.push(event) });
  layer.resize(1024, 768);
  layer.setDepth(0, { origin: { x: 300, y: 200 } });
  layer.setDepth(.5);
  layer.setDepth(1);
  layer.setDepth(2);
  layer.setDepth(.5);
  layer.setDepth(.5);
  layer.setDepth(0, { silent: true });
  assert.deepEqual(crossings.map(event => event.intoSpirit), [false, true, true, false]);
  assert.deepEqual(crossings[0], { intoSpirit: false, x: 300, y: 200 });
  assert.deepEqual(crossings[1], { intoSpirit: true, x: 512, y: 384 });
  assert.equal(layer.getDepth(), 0);
});

test('software crossing animates the scene and always restores its transform', () => {
  const canvas = { style: {} };
  const renderer = { isSoftware: true, domElement: canvas, render() {} };
  const membrane = createMembraneRefraction(renderer);
  membrane.resize(1000, 800);
  membrane.cross(true, 500, 400);
  const now = performance.now();
  membrane.render({}, {}, now + 800);
  assert.match(canvas.style.transform, /^scale\(1\.0/);
  membrane.render({}, {}, now + 2500);
  assert.equal(canvas.style.transform, '');
  assert.equal(canvas.style.transformOrigin, '');
  membrane.dispose();
});

test('GPU uses a render target only during refraction', () => {
  const targets = [], renders = [];
  const renderer = {
    domElement: { style: {} },
    setRenderTarget(target) { targets.push(target); },
    render(scene, camera) { renders.push([scene, camera]); },
  };
  const membrane = createMembraneRefraction(renderer);
  membrane.resize(1000, 800, 2);
  const scene = {}, camera = {};
  membrane.render(scene, camera, performance.now());
  assert.equal(targets.length, 0);
  membrane.cross(true, 500, 400);
  membrane.render(scene, camera, performance.now() + 500);
  assert.equal(targets.length, 2);
  assert.ok(targets[0]?.isWebGLRenderTarget);
  assert.equal(targets[1], null);
  assert.equal(renders.length, 3);
  membrane.render(scene, camera, performance.now() + 2500);
  assert.equal(targets.length, 2);
  membrane.dispose();
});

test('reduced motion avoids the software scale effect', () => {
  const canvas = { style: {} };
  const renderer = { isSoftware: true, domElement: canvas, render() {} };
  const membrane = createMembraneRefraction(renderer, { reducedMotion: true });
  membrane.resize(1000, 800);
  membrane.cross(true, 500, 400);
  membrane.render({}, {}, performance.now() + 200);
  assert.equal(canvas.style.transform, undefined);
  membrane.dispose();
});
