import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import * as THREE from 'three';
import {
  animateOmniaGalaxies,
  animateSideraSculpts,
  createOmniaGalaxySculpts,
  createSideraSculpts,
  sampleOmniaGalaxyPoint,
  sampleSideraSculptAnchor,
  sampleSideraSculptDust,
} from '../src/syzygy/constellationSculpts.js';

const readJson = async (relativePath) => JSON.parse(await readFile(new URL(relativePath, import.meta.url), 'utf8'));

function makeDeterministicRng(seed = 20261125) {
  let state = seed >>> 0;
  const rand = () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
  const gauss = () => {
    let u = 0;
    let v = 0;
    while (u === 0) u = rand();
    while (v === 0) v = rand();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(Math.PI * 2 * v);
  };
  return { rand, gauss };
}

function assertFiniteVec3(vec, label) {
  assert.ok(
    Number.isFinite(vec.x) && Number.isFinite(vec.y) && Number.isFinite(vec.z),
    `${label}: vector has non-finite coordinate (${vec.x}, ${vec.y}, ${vec.z})`,
  );
}

function collectLocalVertices(root) {
  root.updateMatrixWorld(true);
  const invRoot = new THREE.Matrix4().copy(root.matrixWorld).invert();
  const localMat = new THREE.Matrix4();
  const v = new THREE.Vector3();
  const lines = [];
  const points = [];

  root.traverse((obj) => {
    if (!obj.geometry) return;
    const posAttr = obj.geometry.getAttribute('position');
    if (!posAttr) return;
    localMat.multiplyMatrices(invRoot, obj.matrixWorld);
    const verts = [];
    for (let i = 0; i < posAttr.count; i++) {
      v.fromBufferAttribute(posAttr, i).applyMatrix4(localMat);
      assertFiniteVec3(v, `${obj.type} vertex ${i}`);
      verts.push(v.clone());
    }
    if (obj.isLine || obj.isLineSegments) lines.push({ obj, verts });
    else if (obj.isPoints) points.push({ obj, verts });
  });

  return { lines, points };
}

function extractBraceBlock(source, anchor) {
  const startIdx = source.indexOf(anchor);
  assert.notEqual(startIdx, -1, `Missing anchor in scene-reference.js: ${anchor}`);
  const braceOpen = source.indexOf('{', startIdx);
  assert.notEqual(braceOpen, -1, `Missing opening brace for: ${anchor}`);
  let depth = 0;
  let inSingle = false;
  let inDouble = false;
  let inBacktick = false;
  let inLineComment = false;
  let inBlockComment = false;
  for (let i = braceOpen; i < source.length; i++) {
    const ch = source[i];
    const next = source[i + 1];
    if (inLineComment) {
      if (ch === '\n') inLineComment = false;
      continue;
    }
    if (inBlockComment) {
      if (ch === '*' && next === '/') {
        inBlockComment = false;
        i++;
      }
      continue;
    }
    if (inSingle) {
      if (ch === '\\') i++;
      else if (ch === '\'') inSingle = false;
      continue;
    }
    if (inDouble) {
      if (ch === '\\') i++;
      else if (ch === '"') inDouble = false;
      continue;
    }
    if (inBacktick) {
      if (ch === '\\') i++;
      else if (ch === '`') inBacktick = false;
      continue;
    }
    if (ch === '/' && next === '/') {
      inLineComment = true;
      i++;
      continue;
    }
    if (ch === '/' && next === '*') {
      inBlockComment = true;
      i++;
      continue;
    }
    if (ch === '\'') { inSingle = true; continue; }
    if (ch === '"') { inDouble = true; continue; }
    if (ch === '`') { inBacktick = true; continue; }
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return source.slice(startIdx, i + 1);
    }
  }
  assert.fail(`Unclosed block for: ${anchor}`);
}

test('Phase 4 bridges SYZ-240 through SYZ-287 resolve cleanly with balanced SIDERA clusters', async () => {
  const [graph, handbook, bridges] = await Promise.all([
    readJson('../public/data/graph_data.json'),
    readJson('../public/knowledge/data.json'),
    readJson('../src/syzygy/bridges.json'),
  ]);

  assert.ok(bridges.length >= 287, `Expected >= 287 total bridges, got ${bridges.length}`);

  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const entriesById = new Map(handbook.entries.map((entry) => [entry.id, entry]));
  const bridgesById = new Map(bridges.map((bridge) => [bridge.id, bridge]));

  const phase4Bridges = [];
  for (let number = 240; number <= 287; number++) {
    const id = `SYZ-${number}`;
    const bridge = bridgesById.get(id);
    assert.ok(bridge, `Missing Phase 4 bridge ${id}`);
    phase4Bridges.push(bridge);
  }
  assert.equal(phase4Bridges.length, 48);

  for (const bridge of phase4Bridges) {
    const node = nodesById.get(bridge.case);
    const entry = entriesById.get(bridge.entry);
    assert.ok(node, `${bridge.id}: missing graph node ${bridge.case}`);
    assert.ok(entry?.body?.trim(), `${bridge.id}: missing or empty handbook entry ${bridge.entry}`);
    assert.equal(bridge.relation, 'THEMATIC', `${bridge.id}: expected relation === 'THEMATIC'`);
    assert.equal(bridge.related, null, `${bridge.id}: expected related === null`);
    assert.ok(bridge.rationale?.trim().length > 0, `${bridge.id}: missing rationale`);
  }

  const clusterCounts = bridges.reduce((acc, bridge) => {
    acc[bridge.cluster] = (acc[bridge.cluster] ?? 0) + 1;
    return acc;
  }, {});

  assert.ok((clusterCounts.sid_witch ?? 0) >= 28, `Expected sid_witch >= 28, got ${clusterCounts.sid_witch}`);
  assert.ok((clusterCounts.sid_hag ?? 0) >= 35, `Expected sid_hag >= 35, got ${clusterCounts.sid_hag}`);
  assert.ok((clusterCounts.sid_crypt ?? 0) >= 40, `Expected sid_crypt >= 40, got ${clusterCounts.sid_crypt}`);
  assert.ok((clusterCounts.sid_myth ?? 0) >= 95, `Expected sid_myth >= 95, got ${clusterCounts.sid_myth}`);
  assert.ok((clusterCounts.sid_liminal ?? 0) >= 80, `Expected sid_liminal >= 80, got ${clusterCounts.sid_liminal}`);
});

test('constellationSculpts builds 5 bounded 3/4 face-on OMNIA galaxies and animates cleanly', () => {
  const volumes = [
    { id: 'vol1', color: '#e8a856', altColor: '#d97736', center: new THREE.Vector3(0, -166, 12) },
    { id: 'vol2', color: '#64b5f6', altColor: '#38bdf8', center: new THREE.Vector3(162, -50, -10) },
    { id: 'vol3', color: '#52d1a2', altColor: '#2dd4bf', center: new THREE.Vector3(102, 136, 12) },
    { id: 'vol4', color: '#9d8df7', altColor: '#c084fc', center: new THREE.Vector3(-102, 136, -10) },
    { id: 'vol5', color: '#f3d08a', altColor: '#f4978e', center: new THREE.Vector3(-162, -50, 12) },
  ];

  const shaderMat = new THREE.ShaderMaterial();
  const galaxies = createOmniaGalaxySculpts(volumes, shaderMat, null);
  assert.ok(galaxies.group instanceof THREE.Group);
  assert.equal(galaxies.volumes.length, 5);
  assert.deepEqual(galaxies.volumes.map((v) => v.id), ['vol1', 'vol2', 'vol3', 'vol4', 'vol5']);

  const galaxyFingerprints = new Set();
  const { rand, gauss } = makeDeterministicRng(12345);

  galaxies.volumes.forEach((vol, vIdx) => {
    const { lines, points } = collectLocalVertices(vol.root);
    assert.ok(lines.length >= 2, `${vol.id}: expected line geometries`);
    assert.ok(points.length >= 1, `${vol.id}: expected star-mote Points`);

    for (const { verts } of lines) {
      for (const v of verts) {
        assert.ok(v.length() <= 76, `${vol.id}: line vertex radius ${v.length().toFixed(2)} exceeds 76`);
      }
    }
    for (const { obj, verts } of points) {
      for (const attrName of ['position', 'aColor', 'aSize', 'aSpike', 'aHighlight', 'aPhase']) {
        assert.ok(obj.geometry.getAttribute(attrName), `${vol.id}: missing ${attrName} attribute`);
      }
      for (const v of verts) {
        assert.ok(v.length() <= 76, `${vol.id}: point vertex radius ${v.length().toFixed(2)} exceeds 76`);
      }
    }

    const tiltGroup = vol.root.children[0];
    assert.ok(tiltGroup, `${vol.id}: missing tiltGroup`);
    const zNormal = new THREE.Vector3(0, 0, 1).applyEuler(tiltGroup.rotation);
    assert.ok(
      zNormal.z > 0.85 && zNormal.z < 0.99,
      `${vol.id}: expected 3/4 Z-normal tilt toward +Z, got zNormal.z=${zNormal.z.toFixed(4)}`,
    );

    const sampleHub = sampleOmniaGalaxyPoint(vIdx, 0, 0, 20, true, rand, gauss);
    assertFiniteVec3(sampleHub, `${vol.id} hub sample`);
    assert.ok(sampleHub.length() <= 76, `${vol.id}: hub sample radius ${sampleHub.length()} exceeds 76`);
    for (let s = 0; s < 30; s++) {
      const sample = sampleOmniaGalaxyPoint(vIdx, s % 4, s, 30, false, rand, gauss);
      assertFiniteVec3(sample, `${vol.id} dust sample ${s}`);
      assert.ok(sample.length() <= 76, `${vol.id}: sample radius ${sample.length()} exceeds 76`);
    }

    const totalLineVerts = lines.reduce((sum, item) => sum + item.verts.length, 0);
    const totalPointVerts = points.reduce((sum, item) => sum + item.verts.length, 0);
    galaxyFingerprints.add(`${totalLineVerts}:${totalPointVerts}:${zNormal.toArray().map((n) => n.toFixed(3)).join(',')}`);
  });

  assert.equal(galaxyFingerprints.size, 5, 'Expected 5 distinct OMNIA galaxy configurations');

  animateOmniaGalaxies(galaxies, 0);
  const initialRotations = galaxies.volumes.map((vol) =>
    vol.spinParts.map((part) => [part.rotation.x, part.rotation.y, part.rotation.z]),
  );
  animateOmniaGalaxies(galaxies, 2.5);
  galaxies.volumes.forEach((vol, vIdx) => {
    const moved = vol.spinParts.some((part, pIdx) => {
      const [rx0, ry0, rz0] = initialRotations[vIdx][pIdx];
      return Math.abs(part.rotation.x - rx0) > 1e-4
        || Math.abs(part.rotation.y - ry0) > 1e-4
        || Math.abs(part.rotation.z - rz0) > 1e-4;
    });
    assert.ok(moved, `${vol.id}: expected non-zero animation between t=0 and t=2.5`);
  });
});

test('constellationSculpts builds 5 distinct closed-contour SIDERA sculpts with fade and animation', () => {
  const clusters = [
    { id: 'sid_myth', center: new THREE.Vector3(0, 162, 14) },
    { id: 'sid_hag', center: new THREE.Vector3(-174, 46, 16) },
    { id: 'sid_witch', center: new THREE.Vector3(-112, -144, -12) },
    { id: 'sid_crypt', center: new THREE.Vector3(112, -144, 12) },
    { id: 'sid_liminal', center: new THREE.Vector3(174, 46, -14) },
  ];

  const shaderMat = new THREE.ShaderMaterial();
  const sculpts = createSideraSculpts(clusters, shaderMat, null);
  assert.ok(sculpts.group instanceof THREE.Group);
  assert.equal(sculpts.clusters.length, 5);
  assert.deepEqual(
    sculpts.clusters.map((c) => c.id),
    ['sid_myth', 'sid_hag', 'sid_witch', 'sid_crypt', 'sid_liminal'],
  );

  const clusterSignatures = new Set();
  const anchorSignatures = new Set();
  const { rand, gauss } = makeDeterministicRng(67890);

  for (const cluster of sculpts.clusters) {
    assert.ok(cluster.primaryLines.length > 0, `${cluster.id}: expected closed primary contour lines`);
    for (const line of cluster.primaryLines) {
      const pos = line.geometry.getAttribute('position');
      assert.ok(pos.count >= 4, `${cluster.id}: primary line too short`);
      const first = new THREE.Vector3().fromBufferAttribute(pos, 0);
      const last = new THREE.Vector3().fromBufferAttribute(pos, pos.count - 1);
      assert.ok(
        first.distanceTo(last) < 1e-3,
        `${cluster.id}: primary contour must be closed (gap=${first.distanceTo(last)})`,
      );
    }

    const { lines, points } = collectLocalVertices(cluster.root);
    for (const { verts } of lines) {
      for (const v of verts) {
        assert.ok(v.length() <= 76, `${cluster.id}: local vertex radius ${v.length().toFixed(2)} exceeds 76`);
      }
    }
    assert.equal(points.length, 1, `${cluster.id}: expected constellation vertex stars Points`);
    for (const v of points[0].verts) {
      assert.ok(v.length() <= 76, `${cluster.id}: star vertex radius ${v.length().toFixed(2)} exceeds 76`);
    }

    const anchors = [];
    for (let i = 0; i < 24; i++) {
      const anchor = sampleSideraSculptAnchor(cluster.id, i, 24);
      assertFiniteVec3(anchor, `${cluster.id} anchor ${i}`);
      assert.ok(anchor.length() <= 76, `${cluster.id}: anchor radius ${anchor.length()} exceeds 76`);
      anchors.push(anchor);
    }
    for (let i = 0; i < 40; i++) {
      const dust = sampleSideraSculptDust(cluster.id, i, rand, gauss);
      assertFiniteVec3(dust, `${cluster.id} dust ${i}`);
      assert.ok(dust.length() <= 76, `${cluster.id}: dust radius ${dust.length()} exceeds 76`);
    }

    const bbox = new THREE.Box3();
    for (const { verts } of lines) verts.forEach((v) => bbox.expandByPoint(v));
    const size = bbox.getSize(new THREE.Vector3());
    clusterSignatures.add(`${lines.length}:${points[0].verts.length}:${size.toArray().map((n) => n.toFixed(1)).join(',')}`);
    anchorSignatures.add(anchors.slice(0, 4).map((a) => a.toArray().map((n) => n.toFixed(1)).join(',')).join('|'));
  }

  assert.equal(clusterSignatures.size, 5, 'Expected 5 distinct SIDERA sculpture geometries');
  assert.equal(anchorSignatures.size, 5, 'Expected 5 distinct SIDERA anchor distributions');

  sculpts.setFade(0);
  for (const cluster of sculpts.clusters) {
    for (const line of [...cluster.primaryLines, ...cluster.accentLines]) {
      assert.equal(line.visible, false, `${cluster.id}: line should be hidden at fade=0`);
      assert.equal(line.material.opacity, 0, `${cluster.id}: line opacity should be 0 at fade=0`);
    }
    assert.equal(cluster.stars.visible, false, `${cluster.id}: stars should be hidden at fade=0`);
  }

  sculpts.setFade(1);
  for (const cluster of sculpts.clusters) {
    for (const line of [...cluster.primaryLines, ...cluster.accentLines]) {
      assert.equal(line.visible, true, `${cluster.id}: line should be visible at fade=1`);
      assert.ok(line.material.opacity > 0, `${cluster.id}: line opacity should be > 0 at fade=1`);
    }
    assert.equal(cluster.stars.visible, true, `${cluster.id}: stars should be visible at fade=1`);
  }

  const snapshotClusterState = (cluster) => {
    const parts = cluster.animParts.map((part) => {
      const posAttr = part.geometry?.getAttribute?.('position');
      const coords = posAttr ? Array.from(posAttr.array.slice(0, 12)) : [];
      return [
        part.position.x, part.position.y, part.position.z,
        part.rotation.x, part.rotation.y, part.rotation.z,
        part.scale.x, part.scale.y, part.scale.z,
        ...coords,
      ];
    });
    return parts.flat();
  };

  animateSideraSculpts(sculpts, 0);
  const stateAtZero = sculpts.clusters.map(snapshotClusterState);
  animateSideraSculpts(sculpts, 2.5);
  const stateAtTwoFive = sculpts.clusters.map(snapshotClusterState);

  sculpts.clusters.forEach((cluster, idx) => {
    const changed = stateAtZero[idx].some((val, k) => Math.abs(val - stateAtTwoFive[idx][k]) > 1e-4);
    assert.ok(changed, `${cluster.id}: expected non-zero animation between t=0 and t=2.5`);
  });
});

test('scene-reference.js wires galaxy and SIDERA v3 rendering, closed bridges, and camera framing', async () => {
  const source = await readFile(new URL('../src/syzygy/scene-reference.js', import.meta.url), 'utf8');

  const importMatch = source.match(/import\s*\{([\s\S]*?)\}\s*from\s*['"]\.\/constellationSculpts['"]\s*;/);
  assert.ok(importMatch, 'Missing import from ./constellationSculpts in scene-reference.js');
  for (const symbol of [
    'sampleOmniaGalaxyPoint',
    'createOmniaGalaxySculpts',
    'animateOmniaGalaxies',
  ]) {
    assert.match(importMatch[1], new RegExp(`\\b${symbol}\\b`), `Missing import ${symbol} from ./constellationSculpts`);
  }

  const sideraImport = source.match(/import\s*\{([^}]+)\}\s*from\s*['"]\.\/sideraV3Sculpts['"]\s*;/);
  assert.ok(sideraImport, 'Missing SIDERA v3 sculpt import');
  for (const symbol of ['sampleV3Anchor', 'sampleV3Dust', 'createSideraV3Sculpts']) {
    assert.match(sideraImport[1], new RegExp(`\\b${symbol}\\b`), `Missing SIDERA v3 import ${symbol}`);
  }

  assert.match(source, /\banimateOmniaGalaxies\s*\(\s*omniaGalaxies\s*,/, 'Missing animateOmniaGalaxies call in loop');
  assert.match(source, /\bsideraSculpts\.animate\s*\(/, 'Missing SIDERA v3 animation in loop');

  const rebuildBody = extractBraceBlock(source, 'function rebuildSyzygyPhotonBridges()');
  const sideraBranch = extractBraceBlock(rebuildBody, "if (appState.dimension === 'sidera')");
  assert.match(sideraBranch, /\breturn\s*;/, 'SIDERA branch in rebuildSyzygyPhotonBridges must return early');
  assert.doesNotMatch(
    sideraBranch,
    /bridge\.materialNode\.curPos/,
    'SIDERA branch in rebuildSyzygyPhotonBridges must never reference bridge.materialNode.curPos',
  );

  const metricsBody = extractBraceBlock(source, 'function getClearViewportMetrics()');
  assert.match(
    metricsBody,
    /bottomOcc\s*-\s*topOcc/,
    'getClearViewportMetrics must compute vertical centering using (bottomOcc - topOcc)',
  );

  const offsetBody = extractBraceBlock(source, 'function updateCameraOffset()');
  assert.match(offsetBody, /getClearViewportMetrics\s*\(/, 'updateCameraOffset must use getClearViewportMetrics');
  assert.match(offsetBody, /camera\.setViewOffset\s*\(\s*w\s*,\s*h\s*,\s*shiftX\s*,\s*shiftY/, 'updateCameraOffset must apply shiftY');

  const presetBody = extractBraceBlock(source, 'function getOverviewPreset(');
  assert.match(
    presetBody,
    /new\s+THREE\.Vector3\s*\(\s*0\s*,\s*0\s*,\s*0\s*\)/,
    'getOverviewPreset must target (0, 0, 0)',
  );
});
