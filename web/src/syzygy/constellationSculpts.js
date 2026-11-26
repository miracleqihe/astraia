import * as THREE from 'three';

const TWO_PI = Math.PI * 2;
const PHI = (1 + Math.sqrt(5)) / 2;

const ICO_VERTS = [
  [-1, PHI, 0], [1, PHI, 0], [-1, -PHI, 0], [1, -PHI, 0],
  [0, -1, PHI], [0, 1, PHI], [0, -1, -PHI], [0, 1, -PHI],
  [PHI, 0, -1], [PHI, 0, 1], [-PHI, 0, -1], [-PHI, 0, 1],
].map(([x, y, z]) => new THREE.Vector3(x, y, z).normalize());

const ICO_EDGES = [];
for (let i = 0; i < ICO_VERTS.length; i++) {
  for (let j = i + 1; j < ICO_VERTS.length; j++) {
    if (ICO_VERTS[i].distanceTo(ICO_VERTS[j]) < 1.15) ICO_EDGES.push([ICO_VERTS[i], ICO_VERTS[j]]);
  }
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function makeDefaultGauss(rand) {
  return () => {
    let u = 0;
    let v = 0;
    while (u === 0) u = rand();
    while (v === 0) v = rand();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(TWO_PI * v);
  };
}

function makeSeededRng(seed = 135792468) {
  let state = seed >>> 0;
  const rand = () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
  return { rand, gauss: makeDefaultGauss(rand) };
}

function clampRadius(vec, maxRadius) {
  const len = vec.length();
  if (len > maxRadius && len > 0) vec.multiplyScalar(maxRadius / len);
  return vec;
}

function toVec3(center) {
  if (!center) return new THREE.Vector3();
  if (center.isVector3) return center.clone();
  if (Array.isArray(center)) return new THREE.Vector3(center[0] ?? 0, center[1] ?? 0, center[2] ?? 0);
  return new THREE.Vector3(center.x ?? 0, center.y ?? 0, center.z ?? 0);
}

function makeLine(points, { color, opacity, lineWidth = 1.2, closed = false }) {
  const pts = points.map((p) => p.clone());
  if (closed && pts.length > 2 && pts[0].distanceToSquared(pts[pts.length - 1]) > 1e-6) {
    pts.push(pts[0].clone());
  }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity,
    depthWrite: false,
    blending: THREE.NormalBlending,
  });
  const line = new THREE.Line(geo, mat);
  line.userData.strokeColor = color;
  line.userData.lineWidth = lineWidth;
  line.userData.baseOpacity = opacity;
  return line;
}

function makeLineSegments(pairs, { color, opacity, lineWidth = 1.0 }) {
  const geo = new THREE.BufferGeometry().setFromPoints(pairs.map((p) => p.clone()));
  const mat = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity,
    depthWrite: false,
    blending: THREE.NormalBlending,
  });
  const segs = new THREE.LineSegments(geo, mat);
  segs.userData.strokeColor = color;
  segs.userData.lineWidth = lineWidth;
  segs.userData.baseOpacity = opacity;
  return segs;
}

function makeArcPoints(cx, cy, cz, r, startAng, endAng, segments) {
  const pts = [];
  for (let i = 0; i <= segments; i++) {
    const a = startAng + (i / segments) * (endAng - startAng);
    pts.push(new THREE.Vector3(cx + Math.cos(a) * r, cy + Math.sin(a) * r, cz));
  }
  return pts;
}

function makeDashedArcSegments(cx, cy, cz, r, dashCount, fillFrac = 0.56, subSteps = 2) {
  const pairs = [];
  const step = TWO_PI / dashCount;
  for (let i = 0; i < dashCount; i++) {
    const a0 = i * step;
    const a1 = a0 + step * fillFrac;
    for (let s = 0; s < subSteps; s++) {
      const t0 = a0 + (s / subSteps) * (a1 - a0);
      const t1 = a0 + ((s + 1) / subSteps) * (a1 - a0);
      pairs.push(
        new THREE.Vector3(cx + Math.cos(t0) * r, cy + Math.sin(t0) * r, cz),
        new THREE.Vector3(cx + Math.cos(t1) * r, cy + Math.sin(t1) * r, cz),
      );
    }
  }
  return pairs;
}

function makeStarPoints(vertices, starShaderMat) {
  const count = vertices.length;
  const posArr = new Float32Array(count * 3);
  const colArr = new Float32Array(count * 3);
  const sizeArr = new Float32Array(count);
  const spikeArr = new Float32Array(count);
  const highArr = new Float32Array(count);
  const phaseArr = new Float32Array(count);
  const baseHighlight = new Float32Array(count);
  const col = new THREE.Color();

  for (let i = 0; i < count; i++) {
    const v = vertices[i];
    posArr[i * 3] = v.pos.x;
    posArr[i * 3 + 1] = v.pos.y;
    posArr[i * 3 + 2] = v.pos.z;
    col.set(v.color);
    colArr[i * 3] = col.r;
    colArr[i * 3 + 1] = col.g;
    colArr[i * 3 + 2] = col.b;
    sizeArr[i] = v.size;
    spikeArr[i] = v.spike;
    highArr[i] = v.highlight;
    baseHighlight[i] = v.highlight;
    phaseArr[i] = v.phase;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(posArr, 3));
  geo.setAttribute('aColor', new THREE.BufferAttribute(colArr, 3));
  geo.setAttribute('aSize', new THREE.BufferAttribute(sizeArr, 1));
  geo.setAttribute('aSpike', new THREE.BufferAttribute(spikeArr, 1));
  geo.setAttribute('aHighlight', new THREE.BufferAttribute(highArr, 1));
  geo.setAttribute('aPhase', new THREE.BufferAttribute(phaseArr, 1));

  const mat = starShaderMat || new THREE.PointsMaterial({ size: 2.4, transparent: true, depthWrite: false });
  const points = new THREE.Points(geo, mat);
  points.userData.baseHighlight = baseHighlight;
  points.userData.softwareStride = 1;
  return points;
}

function makeCoreSprite(photonTex, color, scale, opacity) {
  if (!photonTex) return null;
  const mat = new THREE.SpriteMaterial({
    map: photonTex,
    color,
    transparent: true,
    opacity,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(scale, scale, 1);
  sprite.userData.baseScale = scale;
  sprite.userData.baseOpacity = opacity;
  return sprite;
}

function samplePolylinesEvenly(polylines, targetCount, maxRadius = 64) {
  const segments = [];
  let totalLen = 0;
  for (const line of polylines) {
    for (let i = 0; i < line.length - 1; i++) {
      const a = line[i];
      const b = line[i + 1];
      const len = a.distanceTo(b);
      if (len > 1e-4) {
        totalLen += len;
        segments.push({ a, b, cumLen: totalLen });
      }
    }
  }
  if (!segments.length || totalLen <= 1e-4) return [new THREE.Vector3()];

  const out = [];
  let segIdx = 0;
  for (let i = 0; i < targetCount; i++) {
    const d = ((i + 0.5) / targetCount) * totalLen;
    while (segIdx < segments.length - 1 && segments[segIdx].cumLen < d) segIdx++;
    const seg = segments[segIdx];
    const prevCum = segIdx > 0 ? segments[segIdx - 1].cumLen : 0;
    const segLen = Math.max(1e-5, seg.cumLen - prevCum);
    const t = clamp((d - prevCum) / segLen, 0, 1);
    const p = new THREE.Vector3().lerpVectors(seg.a, seg.b, t);
    out.push(clampRadius(p, maxRadius));
  }
  return out;
}

// ============================================================================
// PART A: 5 LIVING ANIMATED OMNIA GALAXIES (3/4 FACE-ON ~66-69 DEG TOWARD +Z)
// ============================================================================

const OMNIA_SPECS = [
  {
    id: 'vol1',
    color: '#e8a856',
    altColor: '#d97736',
    tilt: new THREE.Euler(-0.34, 0.22, 0.14, 'XYZ'), // ~66.9 deg face-on
    rings: [20, 34, 48, 62],
  },
  {
    id: 'vol2',
    color: '#64b5f6',
    altColor: '#38bdf8',
    tilt: new THREE.Euler(-0.30, -0.22, -0.12, 'XYZ'), // ~68.8 deg face-on
  },
  {
    id: 'vol3',
    color: '#52d1a2',
    altColor: '#2dd4bf',
    tilt: new THREE.Euler(0.32, 0.20, 0.12, 'XYZ'), // ~68.4 deg face-on
  },
  {
    id: 'vol4',
    color: '#9d8df7',
    altColor: '#c084fc',
    tilt: new THREE.Euler(0.35, -0.22, 0.16, 'XYZ'), // ~66.4 deg face-on
  },
  {
    id: 'vol5',
    color: '#f3d08a',
    altColor: '#f4978e',
    accentColor: '#9eb8d8',
    tilt: new THREE.Euler(-0.32, 0.25, -0.14, 'XYZ'), // ~66.9 deg face-on
  },
];

function sampleSpiralArmLocal(armIdx, r) {
  const armBase = (armIdx / 5) * TWO_PI;
  const ang = armBase + 2.15 * Math.log(1 + r / 12.5);
  return new THREE.Vector3(Math.cos(ang) * r, Math.sin(ang) * r, 0);
}

function sampleTorusKnotLocal(u, R = 40, rTube = 16) {
  return new THREE.Vector3(
    (R + rTube * Math.cos(3 * u)) * Math.cos(2 * u),
    (R + rTube * Math.cos(3 * u)) * Math.sin(2 * u),
    rTube * Math.sin(3 * u) * 1.15,
  );
}

function roseEnvelope(theta) {
  return 0.28 + 0.72 * Math.pow(Math.abs(Math.cos(3 * theta)), 0.75);
}

/**
 * Sample a local 3D point within one of the 5 OMNIA galaxies, oriented 3/4 face-on toward +Z
 * and strictly bounded within radius <= 66.
 */
export function sampleOmniaGalaxyPoint(vIdx, dIdx, sIdx, dCount, isHub, rand = Math.random, gauss = null) {
  const idx = ((vIdx % 5) + 5) % 5;
  const gFn = gauss || makeDefaultGauss(rand);
  const spec = OMNIA_SPECS[idx];
  const count = Math.max(1, dCount || 1);
  const p = new THREE.Vector3();

  if (idx === 0) {
    const rings = spec.rings;
    if (isHub) {
      const r = rings[dIdx % rings.length];
      const ang = dIdx * 2.1 + 0.5;
      p.set(Math.cos(ang) * r, Math.sin(ang) * r, 0);
    } else if (rand() < 0.22) {
      const cr = Math.pow(rand(), 0.65) * 12;
      const th = rand() * TWO_PI;
      const ph = Math.acos(2 * rand() - 1);
      p.set(cr * Math.sin(ph) * Math.cos(th), cr * Math.sin(ph) * Math.sin(th), cr * Math.cos(ph) * 0.78);
    } else {
      const rBase = rings[(dIdx + Math.floor(rand() * rings.length)) % rings.length];
      const r = rBase + clamp(gFn(), -2.2, 2.2) * 1.6;
      const th = ((sIdx % count) / count) * TWO_PI + clamp(gFn(), -2.4, 2.4) * 0.16;
      p.set(Math.cos(th) * r, Math.sin(th) * r, clamp(gFn(), -2.4, 2.4) * 1.4);
    }
    p.applyEuler(spec.tilt);
    return clampRadius(p, 65.5);
  }

  if (idx === 1) {
    const armIdx = dIdx % 5;
    if (isHub) {
      p.copy(sampleSpiralArmLocal(armIdx, 36));
    } else if (rand() < 0.14) {
      const bx = clamp(gFn(), -2.2, 2.2) * 8.5;
      const by = clamp(gFn(), -2.2, 2.2) * 4.2;
      const bz = clamp(gFn(), -2.2, 2.2) * 3.2;
      p.set(bx, by, bz).applyAxisAngle(new THREE.Vector3(0, 0, 1), 0.42);
    } else {
      const t = Math.pow(rand(), 0.78);
      const r = 8 + t * 54;
      const armBase = (armIdx / 5) * TWO_PI;
      const ang = armBase + 2.15 * Math.log(1 + r / 12.5) + clamp(gFn(), -2.2, 2.2) * (0.12 + 0.13 * t);
      const z = clamp(gFn(), -2.4, 2.4) * (3.2 * Math.exp(-r / 40) + 1.1);
      p.set(Math.cos(ang) * r, Math.sin(ang) * r, z);
    }
    p.applyEuler(spec.tilt);
    return clampRadius(p, 65.5);
  }

  if (idx === 2) {
    const R = 54;
    if (isHub) {
      p.copy(ICO_VERTS[(dIdx * 4) % ICO_VERTS.length]).multiplyScalar(R * 0.86);
    } else if (rand() < 0.46) {
      const v = ICO_VERTS[Math.floor(rand() * ICO_VERTS.length)];
      const layer = rand() < 0.36 ? 0.54 : 0.94;
      p.copy(v).multiplyScalar(R * layer).add(new THREE.Vector3(
        clamp(gFn(), -2.2, 2.2) * 3.6,
        clamp(gFn(), -2.2, 2.2) * 3.6,
        clamp(gFn(), -2.2, 2.2) * 3.6,
      ));
    } else {
      const edge = ICO_EDGES[Math.floor(rand() * ICO_EDGES.length)];
      p.lerpVectors(edge[0], edge[1], rand()).multiplyScalar(R * 0.92).add(new THREE.Vector3(
        clamp(gFn(), -2.2, 2.2) * 2.3,
        clamp(gFn(), -2.2, 2.2) * 2.3,
        clamp(gFn(), -2.2, 2.2) * 2.3,
      ));
    }
    p.applyEuler(spec.tilt);
    return clampRadius(p, 65.5);
  }

  if (idx === 3) {
    const u = isHub
      ? (dIdx / 4) * TWO_PI + 0.35
      : ((dIdx + (sIdx % count) / count) / 4) * TWO_PI + clamp(gFn(), -2.2, 2.2) * 0.18;
    p.copy(sampleTorusKnotLocal(u, 40, 16));
    if (!isHub) {
      p.x += clamp(gFn(), -2.2, 2.2) * 3.6;
      p.y += clamp(gFn(), -2.2, 2.2) * 3.6;
      p.z += clamp(gFn(), -2.2, 2.2) * 3.6;
    }
    p.applyEuler(spec.tilt);
    return clampRadius(p, 65.5);
  }

  const petalIdx = (sIdx + dIdx * 2) % 6;
  const baseAng = (petalIdx / 6) * TWO_PI;
  if (isHub) {
    p.set(Math.cos(baseAng) * 44, Math.sin(baseAng) * 44, 0);
  } else {
    const ang = baseAng + clamp(gFn(), -2.2, 2.2) * 0.19;
    const env = roseEnvelope(ang);
    const frac = Math.pow(rand(), 0.64);
    const r = (8 + frac * 53) * env + clamp(gFn(), -2.0, 2.0) * 2.1;
    const zPlume = Math.sin(frac * Math.PI) * 8.0 + clamp(gFn(), -2.0, 2.0) * 2.2;
    p.set(Math.cos(ang) * r, Math.sin(ang) * r, zPlume);
  }
  p.applyEuler(spec.tilt);
  return clampRadius(p, 65.5);
}

function buildShieldBrackets(rInner, rOuter, halfSpanRad, centerAngle) {
  const segs = 16;
  const outer = makeArcPoints(0, 0, 0, rOuter, centerAngle - halfSpanRad, centerAngle + halfSpanRad, segs);
  const inner = makeArcPoints(0, 0, 0, rInner, centerAngle + halfSpanRad, centerAngle - halfSpanRad, segs);
  return [...outer, ...inner, outer[0]];
}

function buildGalaxyMotes(count, posSampler, colorA, colorB, starShaderMat, seed) {
  const { rand, gauss } = makeSeededRng(seed);
  const verts = [];
  for (let i = 0; i < count; i++) {
    const pos = clampRadius(posSampler(i, count, rand, gauss), 64.5);
    verts.push({
      pos,
      color: i % 3 === 0 ? colorB : colorA,
      size: 2.3 + Math.pow(rand(), 1.6) * 3.4,
      spike: i % 19 === 0 ? 0.42 : 0.0,
      highlight: 0.72 + rand() * 0.5,
      phase: rand() * TWO_PI,
    });
  }
  return makeStarPoints(verts, starShaderMat);
}

function createSaturnianShieldSculpt(vol, spec, starShaderMat, photonTex) {
  const root = new THREE.Group();
  root.position.copy(toVec3(vol.center));
  const tiltGroup = new THREE.Group();
  tiltGroup.rotation.copy(spec.tilt);
  root.add(tiltGroup);

  const primary = vol.color || spec.color;
  const alt = vol.altColor || spec.altColor;
  const spinParts = [];
  const pulseParts = [];

  spec.rings.forEach((r, idx) => {
    const pts = makeArcPoints(0, 0, 0, r, 0, TWO_PI, 108);
    tiltGroup.add(makeLine(pts, {
      color: idx % 2 === 0 ? primary : alt,
      opacity: idx === 3 ? 0.34 : 0.28,
      lineWidth: idx % 2 === 0 ? 1.25 : 0.95,
      closed: true,
    }));
  });

  // Degree ticks strictly around the outer shield ring
  const tickPairs = [];
  for (let deg = 0; deg < 360; deg += 15) {
    const a = THREE.MathUtils.degToRad(deg);
    const rIn = deg % 45 === 0 ? 59 : 60.5;
    tickPairs.push(
      new THREE.Vector3(Math.cos(a) * rIn, Math.sin(a) * rIn, 0),
      new THREE.Vector3(Math.cos(a) * 63.5, Math.sin(a) * 63.5, 0),
    );
  }
  tiltGroup.add(makeLineSegments(tickPairs, { color: primary, opacity: 0.34, lineWidth: 0.9 }));

  const shieldGroupA = new THREE.Group();
  shieldGroupA.add(makeLine(buildShieldBrackets(53, 57, 0.55, 0), { color: '#f3d08a', opacity: 0.56, lineWidth: 1.4, closed: true }));
  shieldGroupA.add(makeLine(buildShieldBrackets(53, 57, 0.55, Math.PI), { color: '#f3d08a', opacity: 0.56, lineWidth: 1.4, closed: true }));
  shieldGroupA.userData.anim = { rzSpeed: 0.24 };
  tiltGroup.add(shieldGroupA);
  spinParts.push(shieldGroupA);

  const shieldGroupB = new THREE.Group();
  shieldGroupB.add(makeLine(buildShieldBrackets(26, 29.5, 0.65, Math.PI / 2), { color: alt, opacity: 0.50, lineWidth: 1.25, closed: true }));
  shieldGroupB.add(makeLine(buildShieldBrackets(26, 29.5, 0.65, -Math.PI / 2), { color: alt, opacity: 0.50, lineWidth: 1.25, closed: true }));
  shieldGroupB.userData.anim = { rzSpeed: -0.32 };
  tiltGroup.add(shieldGroupB);
  spinParts.push(shieldGroupB);

  const moteGroup = new THREE.Group();
  const motes = buildGalaxyMotes(
    160,
    (i, _n, rand, gauss) => {
      if (i < 24) {
        const cr = Math.pow(rand(), 0.7) * 11;
        const a = rand() * TWO_PI;
        return new THREE.Vector3(Math.cos(a) * cr, Math.sin(a) * cr, gauss() * 2.2);
      }
      const rBase = spec.rings[i % spec.rings.length];
      const r = rBase + clamp(gauss(), -1.8, 1.8) * 1.4;
      const th = (i / 160) * TWO_PI * 3 + rand() * 0.35;
      return new THREE.Vector3(Math.cos(th) * r, Math.sin(th) * r, clamp(gauss(), -2, 2) * 1.2);
    },
    primary,
    '#fae1a8',
    starShaderMat,
    1011,
  );
  moteGroup.add(motes);
  moteGroup.userData.anim = { rzSpeed: 0.18 };
  tiltGroup.add(moteGroup);
  spinParts.push(moteGroup);

  const coreSprite = makeCoreSprite(photonTex, primary, 32, 0.44);
  if (coreSprite) {
    root.add(coreSprite);
    pulseParts.push(coreSprite);
  }

  return { id: vol.id || spec.id, root, spinParts, pulseParts, coreSprite };
}

function createFiveArmSpiralSculpt(vol, spec, starShaderMat, photonTex) {
  const root = new THREE.Group();
  root.position.copy(toVec3(vol.center));
  const tiltGroup = new THREE.Group();
  tiltGroup.rotation.copy(spec.tilt);
  root.add(tiltGroup);

  const primary = vol.color || spec.color;
  const alt = vol.altColor || spec.altColor;
  const spinParts = [];
  const pulseParts = [];

  tiltGroup.add(makeLine(makeArcPoints(0, 0, 0, 64, 0, TWO_PI, 120), {
    color: alt,
    opacity: 0.24,
    lineWidth: 0.95,
    closed: true,
  }));

  const spiralSpinGroup = new THREE.Group();
  for (let arm = 0; arm < 5; arm++) {
    const pts = [];
    for (let k = 0; k <= 44; k++) {
      const r = 7 + (k / 44) * 54;
      pts.push(sampleSpiralArmLocal(arm, r));
    }
    spiralSpinGroup.add(makeLine(pts, {
      color: arm % 2 === 0 ? primary : alt,
      opacity: 0.44,
      lineWidth: 1.25,
      closed: false,
    }));
  }

  // Luminous galactic bar ellipse
  const barPts = [];
  for (let k = 0; k <= 40; k++) {
    const a = (k / 40) * TWO_PI;
    barPts.push(new THREE.Vector3(Math.cos(a) * 11, Math.sin(a) * 4.2, 0).applyAxisAngle(new THREE.Vector3(0, 0, 1), 0.42));
  }
  spiralSpinGroup.add(makeLine(barPts, { color: '#cfe8ff', opacity: 0.54, lineWidth: 1.2, closed: true }));

  const motes = buildGalaxyMotes(
    180,
    (i, _n, rand, gauss) => {
      if (i < 22) {
        return new THREE.Vector3(clamp(gauss(), -2, 2) * 5.2, clamp(gauss(), -2, 2) * 2.5, clamp(gauss(), -2, 2) * 2.2)
          .applyAxisAngle(new THREE.Vector3(0, 0, 1), 0.42);
      }
      const arm = i % 5;
      const t = Math.pow(rand(), 0.76);
      const r = 8 + t * 53;
      const armBase = (arm / 5) * TWO_PI;
      const ang = armBase + 2.15 * Math.log(1 + r / 12.5) + clamp(gauss(), -2.0, 2.0) * (0.10 + 0.11 * t);
      return new THREE.Vector3(Math.cos(ang) * r, Math.sin(ang) * r, clamp(gauss(), -2, 2) * 1.8);
    },
    primary,
    '#cfe8ff',
    starShaderMat,
    2022,
  );
  spiralSpinGroup.add(motes);
  spiralSpinGroup.userData.anim = { rzSpeed: 0.24 };
  tiltGroup.add(spiralSpinGroup);
  spinParts.push(spiralSpinGroup);

  const coreSprite = makeCoreSprite(photonTex, '#7cc6fc', 34, 0.44);
  if (coreSprite) {
    root.add(coreSprite);
    pulseParts.push(coreSprite);
  }

  return { id: vol.id || spec.id, root, spinParts, pulseParts, coreSprite };
}

function createGeodesicCrystalSculpt(vol, spec, starShaderMat, photonTex) {
  const root = new THREE.Group();
  root.position.copy(toVec3(vol.center));
  const tiltGroup = new THREE.Group();
  tiltGroup.rotation.copy(spec.tilt);
  root.add(tiltGroup);

  const primary = vol.color || spec.color;
  const alt = vol.altColor || spec.altColor;
  const spinParts = [];
  const pulseParts = [];

  const crystalGroup = new THREE.Group();
  const outerPairs = [];
  const innerPairs = [];
  const strutPairs = [];
  for (const [a, b] of ICO_EDGES) {
    outerPairs.push(a.clone().multiplyScalar(51), b.clone().multiplyScalar(51));
    innerPairs.push(a.clone().multiplyScalar(29), b.clone().multiplyScalar(29));
  }
  for (const v of ICO_VERTS) {
    strutPairs.push(v.clone().multiplyScalar(29), v.clone().multiplyScalar(51));
  }
  crystalGroup.add(makeLineSegments(outerPairs, { color: primary, opacity: 0.34, lineWidth: 1.15 }));
  crystalGroup.add(makeLineSegments(innerPairs, { color: alt, opacity: 0.22, lineWidth: 0.9 }));
  crystalGroup.add(makeLineSegments(strutPairs, { color: '#9eead0', opacity: 0.16, lineWidth: 0.75 }));

  const motes = buildGalaxyMotes(
    144,
    (i, _n, rand, gauss) => {
      if (i < 48) {
        const v = ICO_VERTS[i % ICO_VERTS.length];
        const r = i % 2 === 0 ? 50 : 29;
        return v.clone().multiplyScalar(r).add(new THREE.Vector3(gauss() * 2.2, gauss() * 2.2, gauss() * 2.2));
      }
      const edge = ICO_EDGES[i % ICO_EDGES.length];
      return new THREE.Vector3().lerpVectors(edge[0], edge[1], rand()).multiplyScalar(50)
        .add(new THREE.Vector3(gauss() * 1.6, gauss() * 1.6, gauss() * 1.6));
    },
    primary,
    '#b8f5df',
    starShaderMat,
    3033,
  );
  crystalGroup.add(motes);
  crystalGroup.userData.anim = { rxSpeed: 0.08, rySpeed: 0.17, rzSpeed: 0.06 };
  tiltGroup.add(crystalGroup);
  spinParts.push(crystalGroup);

  const gimbalA = makeLine(makeArcPoints(0, 0, 0, 59, 0, TWO_PI, 100), {
    color: '#d6b678',
    opacity: 0.36,
    lineWidth: 1.1,
    closed: true,
  });
  gimbalA.userData.anim = { rxSpeed: 0.26, rySpeed: 0.18, baseRot: new THREE.Euler(0.35, 0.2, 0) };
  tiltGroup.add(gimbalA);
  spinParts.push(gimbalA);

  const gimbalB = makeLine(makeArcPoints(0, 0, 0, 63, 0, TWO_PI, 100), {
    color: primary,
    opacity: 0.28,
    lineWidth: 0.95,
    closed: true,
  });
  gimbalB.userData.anim = { rySpeed: -0.22, rzSpeed: 0.19, baseRot: new THREE.Euler(-0.45, 0.3, 0.2) };
  tiltGroup.add(gimbalB);
  spinParts.push(gimbalB);

  const coreSprite = makeCoreSprite(photonTex, primary, 30, 0.40);
  if (coreSprite) {
    root.add(coreSprite);
    pulseParts.push(coreSprite);
  }

  return { id: vol.id || spec.id, root, spinParts, pulseParts, coreSprite };
}

function createTorusManifoldSculpt(vol, spec, starShaderMat, photonTex) {
  const root = new THREE.Group();
  root.position.copy(toVec3(vol.center));
  const tiltGroup = new THREE.Group();
  tiltGroup.rotation.copy(spec.tilt);
  root.add(tiltGroup);

  const primary = vol.color || spec.color;
  const alt = vol.altColor || spec.altColor;
  const spinParts = [];
  const pulseParts = [];

  const torusSpinGroup = new THREE.Group();
  const braidCount = 3;
  const steps = 160;
  for (let b = 0; b < braidCount; b++) {
    const pts = [];
    const offset = (b / braidCount) * TWO_PI;
    for (let k = 0; k <= steps; k++) {
      const u = (k / steps) * TWO_PI;
      const base = sampleTorusKnotLocal(u, 40, 16);
      const next = sampleTorusKnotLocal(u + 0.01, 40, 16);
      const tang = next.sub(base).normalize();
      const norm = new THREE.Vector3(base.x, base.y, 0).normalize();
      const binorm = new THREE.Vector3().crossVectors(tang, norm).normalize();
      const braidAng = u * 6 + offset;
      base.addScaledVector(norm, Math.cos(braidAng) * 3.0);
      base.addScaledVector(binorm, Math.sin(braidAng) * 3.0);
      pts.push(clampRadius(base, 63.5));
    }
    torusSpinGroup.add(makeLine(pts, {
      color: b === 0 ? primary : (b === 1 ? alt : '#d8ccff'),
      opacity: b === 0 ? 0.48 : 0.34,
      lineWidth: b === 0 ? 1.3 : 1.0,
      closed: true,
    }));
  }

  // 6 delicate closed meridian cross-rings around torus core R=40
  for (let m = 0; m < 6; m++) {
    const phi = (m / 6) * TWO_PI;
    const radVec = new THREE.Vector3(Math.cos(phi), Math.sin(phi), 0);
    const zVec = new THREE.Vector3(0, 0, 1);
    const center = radVec.clone().multiplyScalar(40);
    const ringPts = [];
    for (let k = 0; k <= 36; k++) {
      const a = (k / 36) * TWO_PI;
      const pt = center.clone()
        .addScaledVector(radVec, Math.cos(a) * 16)
        .addScaledVector(zVec, Math.sin(a) * 18);
      ringPts.push(clampRadius(pt, 63));
    }
    torusSpinGroup.add(makeLine(ringPts, {
      color: alt,
      opacity: 0.22,
      lineWidth: 0.85,
      closed: true,
    }));
  }

  const motes = buildGalaxyMotes(
    160,
    (i, n, _rand, gauss) => {
      const u = (i / n) * TWO_PI;
      const base = sampleTorusKnotLocal(u, 40, 16);
      return base.add(new THREE.Vector3(
        clamp(gauss(), -2, 2) * 2.6,
        clamp(gauss(), -2, 2) * 2.6,
        clamp(gauss(), -2, 2) * 2.6,
      ));
    },
    primary,
    '#e4d8ff',
    starShaderMat,
    4044,
  );
  torusSpinGroup.add(motes);
  torusSpinGroup.userData.anim = { rzSpeed: 0.22, rxAmp: 0.08, rxFreq: 0.45 };
  tiltGroup.add(torusSpinGroup);
  spinParts.push(torusSpinGroup);

  const coreSprite = makeCoreSprite(photonTex, primary, 30, 0.38);
  if (coreSprite) {
    root.add(coreSprite);
    pulseParts.push(coreSprite);
  }

  return { id: vol.id || spec.id, root, spinParts, pulseParts, coreSprite };
}

function createRoseWormholeSculpt(vol, spec, starShaderMat, photonTex) {
  const root = new THREE.Group();
  root.position.copy(toVec3(vol.center));
  const tiltGroup = new THREE.Group();
  tiltGroup.rotation.copy(spec.tilt);
  root.add(tiltGroup);

  const primary = vol.color || spec.color;
  const alt = vol.altColor || spec.altColor;
  const accent = spec.accentColor || '#9eb8d8';
  const spinParts = [];
  const pulseParts = [];

  const roseSpinGroup = new THREE.Group();
  const outerRose = [];
  const innerRose = [];
  const steps = 180;
  for (let k = 0; k <= steps; k++) {
    const th = (k / steps) * TWO_PI;
    const rOut = 59 * roseEnvelope(th);
    outerRose.push(new THREE.Vector3(Math.cos(th) * rOut, Math.sin(th) * rOut, Math.sin(3 * th) * 2.2));
    const rIn = 40 * roseEnvelope(th + Math.PI / 6);
    innerRose.push(new THREE.Vector3(Math.cos(th) * rIn, Math.sin(th) * rIn, -Math.sin(3 * th) * 2.4));
  }
  roseSpinGroup.add(makeLine(outerRose, { color: primary, opacity: 0.50, lineWidth: 1.3, closed: true }));
  roseSpinGroup.add(makeLine(innerRose, { color: alt, opacity: 0.42, lineWidth: 1.1, closed: true }));

  const motes = buildGalaxyMotes(
    160,
    (i, _n, rand, gauss) => {
      const petal = i % 6;
      const baseAng = (petal / 6) * TWO_PI;
      const ang = baseAng + clamp(gauss(), -2, 2) * 0.18;
      const env = roseEnvelope(ang);
      const frac = Math.pow(rand(), 0.64);
      const r = (7 + frac * 52) * env + clamp(gauss(), -1.8, 1.8) * 1.8;
      return new THREE.Vector3(Math.cos(ang) * r, Math.sin(ang) * r, Math.sin(frac * Math.PI) * 6.5 + gauss() * 1.6);
    },
    primary,
    alt,
    starShaderMat,
    5055,
  );
  roseSpinGroup.add(motes);
  roseSpinGroup.userData.anim = { rzSpeed: 0.16 };
  tiltGroup.add(roseSpinGroup);
  spinParts.push(roseSpinGroup);

  const horizonOuter = makeLineSegments(makeDashedArcSegments(0, 0, 0, 63, 42, 0.58, 2), {
    color: primary,
    opacity: 0.34,
    lineWidth: 1.05,
  });
  horizonOuter.userData.anim = { rzSpeed: -0.22 };
  tiltGroup.add(horizonOuter);
  spinParts.push(horizonOuter);

  const horizonInner = new THREE.Group();
  horizonInner.add(makeLine(makeArcPoints(0, 0, 0, 22, 0, TWO_PI, 84), {
    color: accent,
    opacity: 0.44,
    lineWidth: 1.2,
    closed: true,
  }));
  const vortexPts = [];
  for (let k = 0; k <= 64; k++) {
    const u = k / 64;
    const r = 3 + u * 18.5;
    const a = u * TWO_PI * 2.1;
    vortexPts.push(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, (1 - u) * -3.5));
  }
  horizonInner.add(makeLine(vortexPts, { color: accent, opacity: 0.36, lineWidth: 1.0, closed: false }));
  horizonInner.userData.anim = { rzSpeed: -0.42, rxAmp: 0.18, rxFreq: 0.6 };
  tiltGroup.add(horizonInner);
  spinParts.push(horizonInner);

  const coreSprite = makeCoreSprite(photonTex, '#f6c28e', 36, 0.48);
  if (coreSprite) {
    root.add(coreSprite);
    pulseParts.push(coreSprite);
  }

  return { id: vol.id || spec.id, root, spinParts, pulseParts, coreSprite };
}

/**
 * Create the 5 living 3D sculptural OMNIA galaxies oriented 3/4 face-on toward +Z.
 */
export function createOmniaGalaxySculpts(VOLUMES, starShaderMat, photonTex = null) {
  const group = new THREE.Group();
  const builders = [
    createSaturnianShieldSculpt,
    createFiveArmSpiralSculpt,
    createGeodesicCrystalSculpt,
    createTorusManifoldSculpt,
    createRoseWormholeSculpt,
  ];
  const volumes = (VOLUMES || []).map((vol, idx) => {
    const specIdx = OMNIA_SPECS.findIndex((s) => s.id === vol.id);
    const useIdx = specIdx >= 0 ? specIdx : idx % 5;
    const item = builders[useIdx](vol, OMNIA_SPECS[useIdx], starShaderMat, photonTex);
    group.add(item.root);
    return item;
  });
  return { group, volumes };
}

/**
 * Continuously animate all 5 OMNIA galaxy sculptures and their orbiting star-motes.
 */
export function animateOmniaGalaxies(omniaGalaxies, t) {
  if (!omniaGalaxies?.volumes) return;
  for (let i = 0; i < omniaGalaxies.volumes.length; i++) {
    const vol = omniaGalaxies.volumes[i];
    for (const part of vol.spinParts || []) {
      const anim = part.userData?.anim;
      if (!anim) continue;
      const base = anim.baseRot;
      const bx = base ? base.x : 0;
      const by = base ? base.y : 0;
      const bz = base ? base.z : 0;
      part.rotation.x = bx + (anim.rxSpeed ? t * anim.rxSpeed : 0) + (anim.rxAmp ? Math.sin(t * (anim.rxFreq || 0.5) + i) * anim.rxAmp : 0);
      part.rotation.y = by + (anim.rySpeed ? t * anim.rySpeed : 0);
      part.rotation.z = bz + (anim.rzSpeed ? t * anim.rzSpeed : 0);
    }
    if (vol.coreSprite && vol.coreSprite.material) {
      const baseScale = vol.coreSprite.userData.baseScale || 32;
      const baseOp = vol.coreSprite.userData.baseOpacity || 0.42;
      const pulse = 1 + 0.08 * Math.sin(t * 1.4 + i * 1.3);
      vol.coreSprite.scale.set(baseScale * pulse, baseScale * pulse, 1);
      vol.coreSprite.material.opacity = baseOp * (0.9 + 0.1 * Math.sin(t * 1.7 + i));
    }
  }
}

// ============================================================================
// PART B: 5 ICONIC CLOSED-CONTOUR MYTHOS CONSTELLATIONS (SIDERA)
// ============================================================================

function evalQuadBezier(p0, p1, p2, steps) {
  const curve = new THREE.QuadraticBezierCurve3(p0, p1, p2);
  return curve.getPoints(steps);
}

function buildMythDeityGeometry() {
  const primary = [];
  const accent = [];
  const polylines = [];
  const stars = [];

  // 1. Crown Halo centered at (0, 43.5, -2): inner r=9.5 (y: 34..53), outer r=13.5 (y: 30..57)
  const haloCenter = new THREE.Vector3(0, 43.5, -2);
  const haloInner = makeArcPoints(0, 0, 0, 9.5, 0, TWO_PI, 54);
  const haloOuter = makeArcPoints(0, 0, 0, 13.5, 0, TWO_PI, 64);
  const haloRays = [];
  for (let k = 0; k < 12; k++) {
    const a = (k / 12) * TWO_PI;
    haloRays.push(
      new THREE.Vector3(Math.cos(a) * 9.5, Math.sin(a) * 9.5, 0),
      new THREE.Vector3(Math.cos(a) * 13.5, Math.sin(a) * 13.5, 0),
    );
  }
  const haloPolylines = [
    haloInner.map((p) => p.clone().add(haloCenter)),
    haloOuter.map((p) => p.clone().add(haloCenter)),
  ];
  polylines.push(...haloPolylines);

  // 2. Head ring (0, 34, 0) radius 6.2 & Polar Apex Star (0, 58, 0)
  const headRing = makeArcPoints(0, 34, 0, 6.2, 0, TWO_PI, 44);
  primary.push({ type: 'line', pts: headRing, color: '#dce4f2', opacity: 0.78, lineWidth: 1.45, closed: true });
  polylines.push(headRing);

  // 3. Closed Shoulder Yoke + Outstretched Robed Arms
  const collarYoke = [
    new THREE.Vector3(-17, 22, 0),
    new THREE.Vector3(0, 26, 0),
    new THREE.Vector3(17, 22, 0),
    new THREE.Vector3(0, 18.5, 1.2),
    new THREE.Vector3(-17, 22, 0),
  ];
  const leftSleeve = [
    new THREE.Vector3(-17, 22, 0),
    new THREE.Vector3(-29, 24.5, 0.8),
    new THREE.Vector3(-40.5, 22, 0.8),
    new THREE.Vector3(-29, 17.5, 0.4),
    new THREE.Vector3(-16, 17, 0),
    new THREE.Vector3(-17, 22, 0),
  ];
  const rightSleeve = leftSleeve.map((p) => new THREE.Vector3(-p.x, p.y, p.z));
  primary.push(
    { type: 'line', pts: collarYoke, color: '#f2dca4', opacity: 0.76, lineWidth: 1.4, closed: true },
    { type: 'line', pts: leftSleeve, color: '#f2dca4', opacity: 0.78, lineWidth: 1.45, closed: true },
    { type: 'line', pts: rightSleeve, color: '#dce4f2', opacity: 0.78, lineWidth: 1.45, closed: true },
  );
  polylines.push(collarYoke, leftSleeve, rightSleeve);

  // 4. Left Solar Ring (-47, 22, 1.2) and Right Lunar Crescent (+47, 22, 1.2)
  const sunOuter = makeArcPoints(0, 0, 0, 6.8, 0, TWO_PI, 40);
  const sunInner = makeArcPoints(0, 0, 0, 3.6, 0, TWO_PI, 28);
  const sunRays = [];
  for (let k = 0; k < 8; k++) {
    const a = (k / 8) * TWO_PI;
    sunRays.push(
      new THREE.Vector3(Math.cos(a) * 3.6, Math.sin(a) * 3.6, 0),
      new THREE.Vector3(Math.cos(a) * 6.8, Math.sin(a) * 6.8, 0),
    );
  }
  const sunCenter = new THREE.Vector3(-47, 22, 1.2);
  polylines.push(sunOuter.map((p) => p.clone().add(sunCenter)));

  // Closed silver lunar crescent centered around (+47, 22, 1.2), reaching ~x=+53.5
  const moonTop = new THREE.Vector3(-1.0, 7.4, 0);
  const moonBot = new THREE.Vector3(-1.0, -7.4, 0);
  const moonOuter = evalQuadBezier(moonTop, new THREE.Vector3(12.2, 0, 0), moonBot, 22);
  const moonInner = evalQuadBezier(moonBot, new THREE.Vector3(2.8, 0, 0), moonTop, 22);
  const moonCrescent = [...moonOuter, ...moonInner.slice(1)];
  const moonCenter = new THREE.Vector3(47, 22, 1.2);
  polylines.push(moonCrescent.map((p) => p.clone().add(moonCenter)));

  // 5. Flowing Robed Hourglass Torso (y: -48..+22) + Central Spine + Rib Arcs
  const robeContour = [
    new THREE.Vector3(-16, 21, 0),
    new THREE.Vector3(-8.5, 2, 1.0),
    new THREE.Vector3(-22, -46, 0),
    new THREE.Vector3(-11, -48, 1.0),
    new THREE.Vector3(0, -49, 1.5),
    new THREE.Vector3(11, -48, 1.0),
    new THREE.Vector3(22, -46, 0),
    new THREE.Vector3(8.5, 2, 1.0),
    new THREE.Vector3(16, 21, 0),
    new THREE.Vector3(0, 26, 0),
    new THREE.Vector3(-16, 21, 0),
  ];
  const spineAxis = [
    new THREE.Vector3(0, 27.8, 0),
    new THREE.Vector3(0, 2, 1.3),
    new THREE.Vector3(0, -49, 1.5),
  ];
  primary.push(
    { type: 'line', pts: robeContour, color: '#f2dca4', opacity: 0.78, lineWidth: 1.5, closed: true },
  );
  accent.push(
    { type: 'line', pts: spineAxis, color: '#dce4f2', opacity: 0.48, lineWidth: 1.0, closed: false },
  );
  polylines.push(robeContour, spineAxis);

  // Symmetric starlight rib arcs connecting spine cleanly to exact torso edge points
  const waistPt = new THREE.Vector3(8.5, 2, 1.0);
  const shoulderBase = new THREE.Vector3(16, 21, 0);
  for (const frac of [0.26, 0.50, 0.74]) {
    const edgePt = new THREE.Vector3().lerpVectors(waistPt, shoulderBase, frac);
    const spineY = edgePt.y + 2.4;
    const leftRib = evalQuadBezier(
      new THREE.Vector3(0, spineY, 1.2),
      new THREE.Vector3(-edgePt.x * 0.52, spineY + 1.2, 1.0),
      new THREE.Vector3(-edgePt.x, edgePt.y, edgePt.z),
      12,
    );
    const rightRib = evalQuadBezier(
      new THREE.Vector3(0, spineY, 1.2),
      new THREE.Vector3(edgePt.x * 0.52, spineY + 1.2, 1.0),
      edgePt,
      12,
    );
    accent.push(
      { type: 'line', pts: leftRib, color: '#dce4f2', opacity: 0.44, lineWidth: 0.9, closed: false },
      { type: 'line', pts: rightRib, color: '#dce4f2', opacity: 0.44, lineWidth: 0.9, closed: false },
    );
  }
  // Closed skirt folds inside robe connecting waist to closed hem
  const leftPleat = [new THREE.Vector3(-8.5, 2, 1.0), new THREE.Vector3(-11, -48, 1.0)];
  const rightPleat = [new THREE.Vector3(8.5, 2, 1.0), new THREE.Vector3(11, -48, 1.0)];
  accent.push(
    { type: 'line', pts: leftPleat, color: '#f2dca4', opacity: 0.34, lineWidth: 0.85, closed: false },
    { type: 'line', pts: rightPleat, color: '#f2dca4', opacity: 0.34, lineWidth: 0.85, closed: false },
  );

  // Constellation vertex stars
  const starSpec = [
    { pos: new THREE.Vector3(0, 58, 0), color: '#fff2cf', size: 22, spike: 1.0, highlight: 1.5 },
    { pos: new THREE.Vector3(0, 34, 0), color: '#dce4f2', size: 15, spike: 0.6, highlight: 1.25 },
    { pos: new THREE.Vector3(0, 18.5, 1.2), color: '#f2dca4', size: 16, spike: 0.72, highlight: 1.3 },
    { pos: new THREE.Vector3(-17, 22, 0), color: '#f2dca4', size: 13, spike: 0.42, highlight: 1.15 },
    { pos: new THREE.Vector3(17, 22, 0), color: '#dce4f2', size: 13, spike: 0.42, highlight: 1.15 },
    { pos: new THREE.Vector3(-29, 24.5, 0.8), color: '#f2dca4', size: 12, spike: 0.35, highlight: 1.1 },
    { pos: new THREE.Vector3(29, 24.5, 0.8), color: '#dce4f2', size: 12, spike: 0.35, highlight: 1.1 },
    { pos: new THREE.Vector3(-47, 22, 1.2), color: '#ffe5a3', size: 18, spike: 0.85, highlight: 1.4 },
    { pos: new THREE.Vector3(47.5, 29.2, 1.2), color: '#e6f0ff', size: 12, spike: 0.4, highlight: 1.2 },
    { pos: new THREE.Vector3(47.5, 14.8, 1.2), color: '#e6f0ff', size: 12, spike: 0.4, highlight: 1.2 },
    { pos: new THREE.Vector3(52, 22, 1.2), color: '#dce4f2', size: 15, spike: 0.65, highlight: 1.3 },
    { pos: new THREE.Vector3(-8.5, 2, 1.0), color: '#f2dca4', size: 12, spike: 0.35, highlight: 1.1 },
    { pos: new THREE.Vector3(8.5, 2, 1.0), color: '#f2dca4', size: 12, spike: 0.35, highlight: 1.1 },
    { pos: new THREE.Vector3(-22, -46, 0), color: '#f2dca4', size: 13.5, spike: 0.48, highlight: 1.15 },
    { pos: new THREE.Vector3(22, -46, 0), color: '#f2dca4', size: 13.5, spike: 0.48, highlight: 1.15 },
    { pos: new THREE.Vector3(0, -49, 1.5), color: '#dce4f2', size: 14, spike: 0.52, highlight: 1.2 },
  ];
  starSpec.forEach((s, idx) => stars.push({ ...s, phase: idx * 0.7 }));

  return {
    primary,
    accent,
    polylines,
    stars,
    haloCenter,
    haloInner,
    haloOuter,
    haloRays,
    sunCenter,
    sunOuter,
    sunInner,
    sunRays,
    moonCenter,
    moonCrescent,
  };
}

function buildHagEyeGeometry() {
  const polylines = [];
  const stars = [];

  // 1. Closed outer lunar crescent with sharp cusps at (24, +50) and (24, -50)
  const cuspTop = new THREE.Vector3(24, 50, -2);
  const cuspBot = new THREE.Vector3(24, -50, -2);
  const rOut = Math.hypot(24, 50); // ~55.46
  const aTop = Math.atan2(50, 24);
  const aBot = TWO_PI - aTop;
  const outerArc = makeArcPoints(0, 0, -2, rOut, aTop, aBot, 72);

  // Inner circle through (24, 50), (-31, 0), (24, -50): cx = 19.227, rIn = 50.227
  const cxIn = 19.22727;
  const rIn = 50.22727;
  const aInBot = Math.atan2(-50, 24 - cxIn);
  const aInTop = Math.atan2(50, 24 - cxIn);
  const innerArc = makeArcPoints(cxIn, 0, -2, rIn, TWO_PI + aInBot, aInTop, 64);
  const crescentLoop = [...outerArc, ...innerArc.slice(1)];
  polylines.push(crescentLoop);

  // 2. Closed almond spectral eye centered at (8, 0, 2)
  const eyeCenter = new THREE.Vector3(8, 0, 2);
  const eyeLeft = new THREE.Vector3(-24, 0, 2);
  const eyeRight = new THREE.Vector3(40, 0, 2);
  const upperLid = evalQuadBezier(eyeLeft, new THREE.Vector3(8, 36, 2), eyeRight, 40);
  const lowerLid = evalQuadBezier(eyeRight, new THREE.Vector3(8, -36, 2), eyeLeft, 40);
  const eyeAlmond = [...upperLid, ...lowerLid.slice(1)];
  const upperBrow = evalQuadBezier(eyeLeft, new THREE.Vector3(8, 46, 1.2), eyeRight, 36);
  const lowerFold = evalQuadBezier(eyeLeft, new THREE.Vector3(8, -44, 1.2), eyeRight, 36);
  polylines.push(eyeAlmond, upperBrow);

  // 3. Iris ring r=13.2, pupil ring r=6.0, radial iris ticks strictly between 6.0 and 13.2
  const irisOuter = makeArcPoints(0, 0, 0, 13.2, 0, TWO_PI, 56);
  const irisInner = makeArcPoints(0, 0, 0, 6.0, 0, TWO_PI, 40);
  const irisTicks = [];
  for (let k = 0; k < 16; k++) {
    const a = (k / 16) * TWO_PI;
    irisTicks.push(
      new THREE.Vector3(Math.cos(a) * 6.1, Math.sin(a) * 6.1, 0),
      new THREE.Vector3(Math.cos(a) * 13.1, Math.sin(a) * 13.1, 0),
    );
  }
  polylines.push(irisOuter.map((p) => p.clone().add(eyeCenter)));

  // 4. Luminous vertical slit pupil
  const pTop = new THREE.Vector3(0, 10.6, 0);
  const pBot = new THREE.Vector3(0, -10.6, 0);
  const slitR = evalQuadBezier(pTop, new THREE.Vector3(5.2, 0, 0), pBot, 18);
  const slitL = evalQuadBezier(pBot, new THREE.Vector3(-5.2, 0, 0), pTop, 18);
  const slitLoop = [...slitR, ...slitL.slice(1)];

  const starSpec = [
    { pos: cuspTop, color: '#c8dcf4', size: 17, spike: 0.8, highlight: 1.35 },
    { pos: cuspBot, color: '#c8dcf4', size: 17, spike: 0.8, highlight: 1.35 },
    { pos: new THREE.Vector3(-rOut, 0, -2), color: '#9ec8f6', size: 16, spike: 0.72, highlight: 1.3 },
    { pos: new THREE.Vector3(-40, 38, -2), color: '#9ec8f6', size: 13, spike: 0.4, highlight: 1.15 },
    { pos: new THREE.Vector3(-40, -38, -2), color: '#9ec8f6', size: 13, spike: 0.4, highlight: 1.15 },
    { pos: eyeLeft, color: '#e6f2ff', size: 15, spike: 0.65, highlight: 1.25 },
    { pos: eyeRight, color: '#e6f2ff', size: 15, spike: 0.65, highlight: 1.25 },
    { pos: new THREE.Vector3(8, 18, 2), color: '#9ec8f6', size: 13, spike: 0.42, highlight: 1.15 },
    { pos: new THREE.Vector3(8, -18, 2), color: '#9ec8f6', size: 13, spike: 0.42, highlight: 1.15 },
    { pos: new THREE.Vector3(8, 0, 3.2), color: '#ffffff', size: 22, spike: 1.05, highlight: 1.55 },
  ];
  starSpec.forEach((s, idx) => stars.push({ ...s, phase: idx * 0.8 }));

  return {
    polylines,
    stars,
    crescentLoop,
    eyeCenter,
    eyeAlmond,
    upperBrow,
    lowerFold,
    irisOuter,
    irisInner,
    irisTicks,
    slitLoop,
  };
}

function buildWitchHexagramGeometry() {
  const polylines = [];
  const stars = [];

  const outerCircle = makeArcPoints(0, 0, 0, 54, 0, TWO_PI, 96);
  const dashedCirclePairs = makeDashedArcSegments(0, 0, 0, 47, 36, 0.56, 2);
  const notchPairs = [];
  for (let k = 0; k < 12; k++) {
    const a = (k / 12) * TWO_PI;
    notchPairs.push(
      new THREE.Vector3(Math.cos(a) * 47.2, Math.sin(a) * 47.2, 0),
      new THREE.Vector3(Math.cos(a) * 53.8, Math.sin(a) * 53.8, 0),
    );
  }

  const triUp = [];
  const triDown = [];
  const R = 44;
  for (let k = 0; k <= 3; k++) {
    const aU = Math.PI / 2 + (k * TWO_PI) / 3;
    const aD = -Math.PI / 2 + (k * TWO_PI) / 3;
    triUp.push(new THREE.Vector3(Math.cos(aU) * R, Math.sin(aU) * R, 1.5));
    triDown.push(new THREE.Vector3(Math.cos(aD) * R, Math.sin(aD) * R, -1.5));
  }

  const rHex = R / Math.sqrt(3);
  const hexagon = [];
  for (let k = 0; k <= 6; k++) {
    const a = (k * TWO_PI) / 6;
    hexagon.push(new THREE.Vector3(Math.cos(a) * rHex, Math.sin(a) * rHex, 0));
  }
  const innerCircle = makeArcPoints(0, 0, 0, 14, 0, TWO_PI, 48);

  polylines.push(outerCircle, triUp, triDown, hexagon);

  const ringRadii = [57.5, 59.2, 60.8];
  const ringTilts = [
    new THREE.Euler(0.96, 0.34, 0),
    new THREE.Euler(-0.84, 0.62, 0.42),
    new THREE.Euler(0.28, -1.04, -0.48),
  ];
  const ringCircles = ringRadii.map((r) => makeArcPoints(0, 0, 0, r, 0, TWO_PI, 84));

  const starSpec = [];
  // Indices 0..5: rotating hexagram tips
  for (let k = 0; k < 6; k++) {
    const a = Math.PI / 2 + (k * Math.PI) / 3;
    starSpec.push({
      pos: new THREE.Vector3(Math.cos(a) * R, Math.sin(a) * R, k % 2 === 0 ? 1.5 : -1.5),
      color: k % 2 === 0 ? '#e2c88e' : '#d4c2f0',
      size: 16,
      spike: 0.72,
      highlight: 1.32,
      phase: k * 0.7,
    });
  }
  // Indices 6..17: 12 outer circle zodiac seal notches
  for (let k = 0; k < 12; k++) {
    const a = (k / 12) * TWO_PI;
    starSpec.push({
      pos: new THREE.Vector3(Math.cos(a) * 54, Math.sin(a) * 54, 0),
      color: k % 2 === 0 ? '#d4c2f0' : '#e2c88e',
      size: k % 3 === 0 ? 14 : 10,
      spike: k % 3 === 0 ? 0.5 : 0.0,
      highlight: k % 3 === 0 ? 1.2 : 1.0,
      phase: k * 0.5,
    });
  }
  // Index 18: center seal star
  starSpec.push({
    pos: new THREE.Vector3(0, 0, 0),
    color: '#f5e7c4',
    size: 20,
    spike: 0.95,
    highlight: 1.45,
    phase: 0,
  });

  return {
    polylines,
    stars: starSpec,
    outerCircle,
    dashedCirclePairs,
    notchPairs,
    triUp,
    triDown,
    hexagon,
    innerCircle,
    ringCircles,
    ringTilts,
    hexTipRadius: R,
  };
}

function buildCryptDragonGeometry() {
  const polylines = [];
  const stars = [];

  const spineWaypoints = [
    new THREE.Vector3(-50, -32, -4),
    new THREE.Vector3(-54, -18, -2),
    new THREE.Vector3(-44, -10, 0),
    new THREE.Vector3(-34, -26, 2),
    new THREE.Vector3(-18, -36, 5),
    new THREE.Vector3(-2, -16, 8),
    new THREE.Vector3(-16, 12, 4),
    new THREE.Vector3(-6, 36, -3),
    new THREE.Vector3(14, 42, -2),
    new THREE.Vector3(26, 34, 2),
    new THREE.Vector3(32, 36, 4),
  ];
  const spineCurve = new THREE.CatmullRomCurve3(spineWaypoints, false, 'centripetal', 0.5);
  const steps = 96;
  const spinePts = [];
  const dorsalPts = [];
  const ventralPts = [];
  const upZ = new THREE.Vector3(0, 0, 1);

  for (let i = 0; i <= steps; i++) {
    const u = i / steps;
    const pt = spineCurve.getPointAt(u);
    const tang = spineCurve.getTangentAt(u);
    const perp = new THREE.Vector3().crossVectors(upZ, tang).setZ(0);
    if (perp.lengthSq() < 1e-6) perp.set(0, 1, 0);
    else perp.normalize();

    // Smooth taper from 0 at curled tail tip to full sinuous dragon body, narrowing smoothly at neck base
    const bodyEnv = u < 0.08 ? (u / 0.08) : 1.0;
    const neckTaper = u > 0.85 ? 1 - ((u - 0.85) / 0.15) * 0.35 : 1.0;
    const halfW = (1.6 + 3.4 * Math.sin(u * Math.PI)) * bodyEnv * neckTaper;

    spinePts.push(pt);
    dorsalPts.push(pt.clone().addScaledVector(perp, halfW));
    ventralPts.push(pt.clone().addScaledVector(perp, -halfW));
  }

  // Head silhouette attached seamlessly from dorsalPts[last] around jaws back to ventralPts[last]
  const headCrown = new THREE.Vector3(36, 40, 4.5);
  const upperJaw = new THREE.Vector3(43, 31, 5.0);
  const innerMouth = new THREE.Vector3(36, 31, 4.2);
  const lowerJaw = new THREE.Vector3(41, 25, 4.8);
  const chin = new THREE.Vector3(33, 28, 4.2);

  const closedDragonLoop = [
    ...dorsalPts,
    headCrown,
    upperJaw,
    innerMouth,
    lowerJaw,
    chin,
    ...ventralPts.slice().reverse(),
  ];

  // Closed dorsal head crest + cleanly attached branched antler & whiskers
  const crestLoop = [
    new THREE.Vector3(29, 39, 3.8),
    new THREE.Vector3(24, 49, 1.5),
    new THREE.Vector3(33, 44, 3.2),
    new THREE.Vector3(36, 40, 4.5),
    new THREE.Vector3(29, 39, 3.8),
  ];
  const antlerMain = [
    new THREE.Vector3(30, 39.5, 3.8),
    new THREE.Vector3(22, 50, 1.0),
    new THREE.Vector3(17, 56, 0.0),
  ];
  const antlerFork = [
    new THREE.Vector3(22, 50, 1.0),
    new THREE.Vector3(28, 55, 1.2),
  ];
  const whiskerUpper = [
    upperJaw,
    new THREE.Vector3(47, 34.5, 5.2),
    new THREE.Vector3(52, 33, 4.5),
  ];
  const whiskerLower = [
    lowerJaw,
    new THREE.Vector3(45, 22, 4.5),
  ];

  // Spirit pearl centered around (50, 18, 6)
  const pearlCenter = new THREE.Vector3(50, 18, 6);
  const pearlOuter = makeArcPoints(0, 0, 0, 5.6, 0, TWO_PI, 40);
  const pearlInner = makeArcPoints(0, 0, 0, 2.6, 0, TWO_PI, 28);
  const pearlHalo = makeArcPoints(0, 0, 0, 7.6, 0, TWO_PI, 44);

  polylines.push(
    closedDragonLoop,
    crestLoop,
    pearlOuter.map((p) => p.clone().add(pearlCenter)),
  );

  const starSpec = [
    { pos: new THREE.Vector3(-50, -32, -4), color: '#72d6c4', size: 15, spike: 0.65, highlight: 1.25 },
    { pos: new THREE.Vector3(-54, -18, -2), color: '#9ec4dc', size: 12, spike: 0.35, highlight: 1.1 },
    { pos: new THREE.Vector3(-34, -26, 2), color: '#72d6c4', size: 12.5, spike: 0.4, highlight: 1.15 },
    { pos: new THREE.Vector3(-18, -36, 5), color: '#72d6c4', size: 14, spike: 0.5, highlight: 1.2 },
    { pos: new THREE.Vector3(-2, -16, 8), color: '#9ec4dc', size: 14, spike: 0.52, highlight: 1.2 },
    { pos: new THREE.Vector3(-16, 12, 4), color: '#72d6c4', size: 13.5, spike: 0.45, highlight: 1.15 },
    { pos: new THREE.Vector3(-6, 36, -3), color: '#9ec4dc', size: 14, spike: 0.5, highlight: 1.2 },
    { pos: new THREE.Vector3(14, 42, -2), color: '#72d6c4', size: 14, spike: 0.5, highlight: 1.2 },
    { pos: new THREE.Vector3(17, 56, 0), color: '#9ec4dc', size: 13, spike: 0.45, highlight: 1.15 },
    { pos: new THREE.Vector3(35, 36.5, 4.5), color: '#d8fff4', size: 17, spike: 0.82, highlight: 1.4 },
    { pos: upperJaw, color: '#9ec4dc', size: 12, spike: 0.38, highlight: 1.1 },
    // Last star: spirit pearl center (updated dynamically in animateSideraSculpts)
    { pos: pearlCenter.clone(), color: '#ffe5a3', size: 22, spike: 1.05, highlight: 1.55 },
  ];
  starSpec.forEach((s, idx) => stars.push({ ...s, phase: idx * 0.65 }));

  return {
    polylines,
    stars,
    closedDragonLoop,
    spinePts,
    crestLoop,
    antlerMain,
    antlerFork,
    whiskerUpper,
    whiskerLower,
    pearlCenter,
    pearlOuter,
    pearlInner,
    pearlHalo,
  };
}

function buildLiminalCorridorGeometry() {
  const polylines = [];
  const stars = [];

  const frameSpecs = [
    { w: 34, h: 46, z: 22, color: '#e6d6a8', opacity: 0.82, lineWidth: 1.6 },
    { w: 24.5, h: 33, z: 6, color: '#d8ceb8', opacity: 0.68, lineWidth: 1.35 },
    { w: 16.5, h: 22.5, z: -11, color: '#9ae2cb', opacity: 0.56, lineWidth: 1.15 },
    { w: 10.0, h: 13.5, z: -28, color: '#6ee7c0', opacity: 0.50, lineWidth: 1.05 },
  ];
  const signs = [
    [-1, -1],
    [1, -1],
    [1, 1],
    [-1, 1],
  ];

  const frameLoops = frameSpecs.map((f) =>
    signs.map(([sx, sy]) => new THREE.Vector3(sx * f.w, sy * f.h, f.z)),
  );
  const closedLoops = frameLoops.map((loop) => [...loop, loop[0]]);
  polylines.push(...closedLoops);

  const railPairs = [];
  for (let k = 0; k < frameSpecs.length - 1; k++) {
    const a = frameSpecs[k];
    const b = frameSpecs[k + 1];
    for (const [sx, sy] of signs) {
      const pa = new THREE.Vector3(sx * a.w, sy * a.h, a.z);
      const pb = new THREE.Vector3(sx * b.w, sy * b.h, b.z);
      railPairs.push(pa, pb);
      polylines.push([pa, pb]);
    }
  }

  const diamondCenter = new THREE.Vector3(0, 0, -28);
  const diamondOuter = [
    new THREE.Vector3(0, 7.2, 0),
    new THREE.Vector3(7.2, 0, 0),
    new THREE.Vector3(0, -7.2, 0),
    new THREE.Vector3(-7.2, 0, 0),
    new THREE.Vector3(0, 7.2, 0),
  ];
  const diamondInner = [
    new THREE.Vector3(3.2, 3.2, 0),
    new THREE.Vector3(3.2, -3.2, 0),
    new THREE.Vector3(-3.2, -3.2, 0),
    new THREE.Vector3(-3.2, 3.2, 0),
    new THREE.Vector3(3.2, 3.2, 0),
  ];
  polylines.push(diamondOuter.map((p) => p.clone().add(diamondCenter)));

  // 16 doorway corner stars + vanishing center star
  frameSpecs.forEach((f, fIdx) => {
    signs.forEach(([sx, sy], cIdx) => {
      stars.push({
        pos: new THREE.Vector3(sx * f.w, sy * f.h, f.z),
        color: fIdx < 2 ? '#e6d6a8' : '#6ee7c0',
        size: fIdx === 0 ? 15 : (fIdx === 1 ? 12 : 10),
        spike: fIdx === 0 ? 0.65 : (fIdx === 1 ? 0.35 : 0.0),
        highlight: fIdx === 0 ? 1.3 : 1.1,
        phase: (fIdx * 4 + cIdx) * 0.45,
      });
    });
  });
  stars.push({
    pos: diamondCenter.clone(),
    color: '#9efae0',
    size: 20,
    spike: 1.0,
    highlight: 1.5,
    phase: 0.2,
  });

  return {
    polylines,
    stars,
    frameSpecs,
    signs,
    railPairs,
    diamondCenter,
    diamondOuter,
    diamondInner,
  };
}

const SIDERA_BUILDERS = {
  sid_myth: buildMythDeityGeometry,
  sid_hag: buildHagEyeGeometry,
  sid_witch: buildWitchHexagramGeometry,
  sid_crypt: buildCryptDragonGeometry,
  sid_liminal: buildLiminalCorridorGeometry,
};

const SIDERA_SAMPLE_BANK = new Map();

function getSideraSampleBank(clusterId) {
  const key = SIDERA_BUILDERS[clusterId] ? clusterId : 'sid_myth';
  let bank = SIDERA_SAMPLE_BANK.get(key);
  if (!bank) {
    const geom = SIDERA_BUILDERS[key]();
    bank = samplePolylinesEvenly(geom.polylines, 240, 63.5);
    SIDERA_SAMPLE_BANK.set(key, bank);
  }
  return bank;
}

/**
 * Sample a deterministic local anchor point strictly along one of the 5 Mythos constellation figures
 * (radius <= 64).
 */
export function sampleSideraSculptAnchor(clusterId, index, total) {
  const bank = getSideraSampleBank(clusterId);
  const count = Math.max(1, total || 1);
  const safeIdx = ((index % count) + count) % count;
  const u = (safeIdx + 0.5) / count;
  const bankIdx = Math.floor(u * bank.length) % bank.length;
  return bank[bankIdx].clone();
}

/**
 * Sample a dust particle tracing the exact sculpted Mythos figure around local origin (0,0,0).
 */
export function sampleSideraSculptDust(clusterId, index, rand = Math.random, gauss = null) {
  const bank = getSideraSampleBank(clusterId);
  const gFn = gauss || makeDefaultGauss(rand);
  const safeIdx = Math.abs(Math.floor(index || 0));
  const u = ((safeIdx * 0.61803398875 + rand() * 0.08) % 1 + 1) % 1;
  const base = bank[Math.floor(u * bank.length) % bank.length].clone();
  base.x += clamp(gFn(), -2.2, 2.2) * 1.7;
  base.y += clamp(gFn(), -2.2, 2.2) * 1.7;
  base.z += clamp(gFn(), -2.2, 2.2) * 2.1;
  return clampRadius(base, 64.5);
}

function assembleSideraCluster(cl, idx, starShaderMat, photonTex) {
  const id = SIDERA_BUILDERS[cl.id] ? cl.id : Object.keys(SIDERA_BUILDERS)[idx % 5];
  const root = new THREE.Group();
  root.position.copy(toVec3(cl.center));
  const primaryLines = [];
  const accentLines = [];
  const animParts = [];
  const sprites = [];
  let stars = null;

  if (id === 'sid_myth') {
    const g = buildMythDeityGeometry();
    const breathGroup = new THREE.Group();
    breathGroup.userData.anim = { kind: 'mythBreath' };
    root.add(breathGroup);
    animParts.push(breathGroup);

    for (const item of g.primary) {
      const l = makeLine(item.pts, item);
      breathGroup.add(l);
      primaryLines.push(l);
    }
    for (const item of g.accent) {
      const l = makeLine(item.pts, item);
      breathGroup.add(l);
      accentLines.push(l);
    }

    const haloGroup = new THREE.Group();
    haloGroup.position.copy(g.haloCenter);
    const lInner = makeLine(g.haloInner, { color: '#f2dca4', opacity: 0.72, lineWidth: 1.25, closed: true });
    const lOuter = makeLine(g.haloOuter, { color: '#f2dca4', opacity: 0.56, lineWidth: 1.15, closed: true });
    const lRays = makeLineSegments(g.haloRays, { color: '#f2dca4', opacity: 0.54, lineWidth: 0.95 });
    haloGroup.add(lInner, lOuter, lRays);
    primaryLines.push(lInner, lOuter);
    accentLines.push(lRays);
    haloGroup.userData.anim = { kind: 'spinZ', speed: 0.14 };
    breathGroup.add(haloGroup);
    animParts.push(haloGroup);

    const sunGroup = new THREE.Group();
    sunGroup.position.copy(g.sunCenter);
    const lSunOut = makeLine(g.sunOuter, { color: '#f2dca4', opacity: 0.80, lineWidth: 1.4, closed: true });
    const lSunIn = makeLine(g.sunInner, { color: '#ffe8af', opacity: 0.68, lineWidth: 1.1, closed: true });
    const lSunRays = makeLineSegments(g.sunRays, { color: '#f2dca4', opacity: 0.62, lineWidth: 0.95 });
    sunGroup.add(lSunOut, lSunIn, lSunRays);
    primaryLines.push(lSunOut);
    accentLines.push(lSunIn, lSunRays);
    sunGroup.userData.anim = { kind: 'mythSun', baseY: g.sunCenter.y };
    breathGroup.add(sunGroup);
    animParts.push(sunGroup);

    const moonGroup = new THREE.Group();
    moonGroup.position.copy(g.moonCenter);
    const lMoon = makeLine(g.moonCrescent, { color: '#dce4f2', opacity: 0.80, lineWidth: 1.4, closed: true });
    moonGroup.add(lMoon);
    primaryLines.push(lMoon);
    moonGroup.userData.anim = { kind: 'mythMoon', baseY: g.moonCenter.y };
    breathGroup.add(moonGroup);
    animParts.push(moonGroup);

    stars = makeStarPoints(g.stars, starShaderMat);
    breathGroup.add(stars);

    const heartGlow = makeCoreSprite(photonTex, '#f2dca4', 20, 0.42);
    if (heartGlow) {
      heartGlow.position.set(0, 18.5, 1.4);
      breathGroup.add(heartGlow);
      sprites.push(heartGlow);
    }
    const sunGlow = makeCoreSprite(photonTex, '#ffe29a', 18, 0.38);
    if (sunGlow) {
      sunGroup.add(sunGlow);
      sprites.push(sunGlow);
    }
  } else if (id === 'sid_hag') {
    const g = buildHagEyeGeometry();
    const lunarGroup = new THREE.Group();
    lunarGroup.userData.anim = { kind: 'hagSway' };
    root.add(lunarGroup);
    animParts.push(lunarGroup);

    const lCrescent = makeLine(g.crescentLoop, { color: '#9ec8f6', opacity: 0.78, lineWidth: 1.55, closed: true });
    const lEye = makeLine(g.eyeAlmond, { color: '#c8dcf4', opacity: 0.84, lineWidth: 1.55, closed: true });
    const lBrow = makeLine(g.upperBrow, { color: '#9ec8f6', opacity: 0.42, lineWidth: 0.9, closed: false });
    const lFold = makeLine(g.lowerFold, { color: '#9ec8f6', opacity: 0.36, lineWidth: 0.85, closed: false });
    lunarGroup.add(lCrescent, lEye, lBrow, lFold);
    primaryLines.push(lCrescent, lEye);
    accentLines.push(lBrow, lFold);

    const irisGroup = new THREE.Group();
    irisGroup.position.copy(g.eyeCenter);
    const lIrisOut = makeLine(g.irisOuter, { color: '#9ec8f6', opacity: 0.72, lineWidth: 1.25, closed: true });
    const lIrisIn = makeLine(g.irisInner, { color: '#c8dcf4', opacity: 0.62, lineWidth: 1.05, closed: true });
    const lIrisTicks = makeLineSegments(g.irisTicks, { color: '#9ec8f6', opacity: 0.56, lineWidth: 0.9 });
    irisGroup.add(lIrisOut, lIrisIn, lIrisTicks);
    primaryLines.push(lIrisOut);
    accentLines.push(lIrisIn, lIrisTicks);
    irisGroup.userData.anim = { kind: 'spinZ', speed: 0.22 };
    lunarGroup.add(irisGroup);
    animParts.push(irisGroup);

    const pupilGroup = new THREE.Group();
    pupilGroup.position.set(g.eyeCenter.x, g.eyeCenter.y, g.eyeCenter.z + 0.6);
    const lSlit = makeLine(g.slitLoop, { color: '#e6f2ff', opacity: 0.88, lineWidth: 1.45, closed: true });
    pupilGroup.add(lSlit);
    primaryLines.push(lSlit);
    pupilGroup.userData.anim = { kind: 'hagPupil' };
    lunarGroup.add(pupilGroup);
    animParts.push(pupilGroup);

    stars = makeStarPoints(g.stars, starShaderMat);
    lunarGroup.add(stars);

    const eyeGlow = makeCoreSprite(photonTex, '#9ec8f6', 24, 0.48);
    if (eyeGlow) {
      eyeGlow.position.set(g.eyeCenter.x, g.eyeCenter.y, g.eyeCenter.z + 1.0);
      lunarGroup.add(eyeGlow);
      sprites.push(eyeGlow);
    }
  } else if (id === 'sid_witch') {
    const g = buildWitchHexagramGeometry();

    const outerSealGroup = new THREE.Group();
    const lOuter = makeLine(g.outerCircle, { color: '#d4c2f0', opacity: 0.78, lineWidth: 1.5, closed: true });
    const lDashed = makeLineSegments(g.dashedCirclePairs, { color: '#e2c88e', opacity: 0.64, lineWidth: 1.15 });
    const lNotches = makeLineSegments(g.notchPairs, { color: '#e2c88e', opacity: 0.58, lineWidth: 1.0 });
    outerSealGroup.add(lOuter, lDashed, lNotches);
    primaryLines.push(lOuter);
    accentLines.push(lDashed, lNotches);
    outerSealGroup.userData.anim = { kind: 'spinZ', speed: 0.11 };
    root.add(outerSealGroup);
    animParts.push(outerSealGroup);

    const hexGroup = new THREE.Group();
    const lTriUp = makeLine(g.triUp, { color: '#e2c88e', opacity: 0.82, lineWidth: 1.5, closed: true });
    const lTriDown = makeLine(g.triDown, { color: '#d4c2f0', opacity: 0.78, lineWidth: 1.45, closed: true });
    const lHexagon = makeLine(g.hexagon, { color: '#e2c88e', opacity: 0.56, lineWidth: 1.1, closed: true });
    const lInner = makeLine(g.innerCircle, { color: '#d4c2f0', opacity: 0.50, lineWidth: 1.0, closed: true });
    hexGroup.add(lTriUp, lTriDown, lHexagon, lInner);
    primaryLines.push(lTriUp, lTriDown);
    accentLines.push(lHexagon, lInner);
    hexGroup.userData.anim = { kind: 'spinZ', speed: -0.16 };
    root.add(hexGroup);
    animParts.push(hexGroup);

    g.ringCircles.forEach((pts, rIdx) => {
      const ring = makeLine(pts, {
        color: rIdx % 2 === 0 ? '#e2c88e' : '#d4c2f0',
        opacity: 0.40,
        lineWidth: 0.95,
        closed: true,
      });
      ring.rotation.copy(g.ringTilts[rIdx]);
      ring.userData.anim = {
        kind: 'witchRing',
        baseRot: g.ringTilts[rIdx],
        rxSpeed: (rIdx % 2 === 0 ? 1 : -1) * (0.14 + rIdx * 0.04),
        rySpeed: (rIdx === 1 ? -1 : 1) * (0.18 + rIdx * 0.03),
      };
      root.add(ring);
      accentLines.push(ring);
      animParts.push(ring);
    });

    stars = makeStarPoints(g.stars, starShaderMat);
    stars.userData.anim = { kind: 'witchStars', hexRadius: g.hexTipRadius, outerSpeed: 0.11, hexSpeed: -0.16 };
    root.add(stars);
    animParts.push(stars);

    const sealGlow = makeCoreSprite(photonTex, '#d4c2f0', 22, 0.40);
    if (sealGlow) {
      root.add(sealGlow);
      sprites.push(sealGlow);
    }
  } else if (id === 'sid_crypt') {
    const g = buildCryptDragonGeometry();
    const dragonGroup = new THREE.Group();
    dragonGroup.userData.anim = { kind: 'cryptSway' };
    root.add(dragonGroup);
    animParts.push(dragonGroup);

    const lBody = makeLine(g.closedDragonLoop, { color: '#72d6c4', opacity: 0.82, lineWidth: 1.55, closed: true });
    const lSpine = makeLine(g.spinePts, { color: '#9ec4dc', opacity: 0.42, lineWidth: 0.95, closed: false });
    const lCrest = makeLine(g.crestLoop, { color: '#9ec4dc', opacity: 0.72, lineWidth: 1.25, closed: true });
    const lAntler = makeLine(g.antlerMain, { color: '#9ec4dc', opacity: 0.68, lineWidth: 1.15, closed: false });
    const lFork = makeLine(g.antlerFork, { color: '#9ec4dc', opacity: 0.60, lineWidth: 1.0, closed: false });
    const lWUp = makeLine(g.whiskerUpper, { color: '#72d6c4', opacity: 0.56, lineWidth: 0.95, closed: false });
    const lWLow = makeLine(g.whiskerLower, { color: '#72d6c4', opacity: 0.52, lineWidth: 0.9, closed: false });
    dragonGroup.add(lBody, lSpine, lCrest, lAntler, lFork, lWUp, lWLow);
    primaryLines.push(lBody, lCrest);
    accentLines.push(lSpine, lAntler, lFork, lWUp, lWLow);

    const pearlGroup = new THREE.Group();
    pearlGroup.position.copy(g.pearlCenter);
    const lPearlOut = makeLine(g.pearlOuter, { color: '#f2dca4', opacity: 0.84, lineWidth: 1.4, closed: true });
    const lPearlIn = makeLine(g.pearlInner, { color: '#fff3cf', opacity: 0.72, lineWidth: 1.1, closed: true });
    const lPearlHalo = makeLine(g.pearlHalo, { color: '#72d6c4', opacity: 0.52, lineWidth: 0.95, closed: true });
    lPearlHalo.rotation.set(0.55, 0.3, 0);
    pearlGroup.add(lPearlOut, lPearlIn, lPearlHalo);
    primaryLines.push(lPearlOut);
    accentLines.push(lPearlIn, lPearlHalo);
    pearlGroup.userData.anim = { kind: 'cryptPearl', baseCenter: g.pearlCenter, halo: lPearlHalo };
    root.add(pearlGroup);
    animParts.push(pearlGroup);

    stars = makeStarPoints(g.stars, starShaderMat);
    stars.userData.anim = { kind: 'cryptStars', pearlIndex: g.stars.length - 1, baseCenter: g.pearlCenter };
    dragonGroup.add(stars);
    animParts.push(stars);

    const pearlGlow = makeCoreSprite(photonTex, '#f2dca4', 22, 0.50);
    if (pearlGlow) {
      pearlGroup.add(pearlGlow);
      sprites.push(pearlGlow);
    }
  } else {
    const g = buildLiminalCorridorGeometry();
    const corridorGroup = new THREE.Group();
    root.add(corridorGroup);

    const frameObjs = g.frameSpecs.map((f, fIdx) => {
      const pts = g.signs.map(([sx, sy]) => new THREE.Vector3(sx * f.w, sy * f.h, 0));
      const l = makeLine(pts, { color: f.color, opacity: f.opacity, lineWidth: f.lineWidth, closed: true });
      l.position.z = f.z;
      corridorGroup.add(l);
      if (fIdx < 2) primaryLines.push(l);
      else accentLines.push(l);
      return { line: l, spec: f };
    });

    const railsLine = makeLineSegments(g.railPairs, { color: '#9be7cf', opacity: 0.54, lineWidth: 1.0 });
    corridorGroup.add(railsLine);
    accentLines.push(railsLine);

    const diamondGroup = new THREE.Group();
    diamondGroup.position.copy(g.diamondCenter);
    const lDiaOut = makeLine(g.diamondOuter, { color: '#6ee7c0', opacity: 0.84, lineWidth: 1.45, closed: true });
    const lDiaIn = makeLine(g.diamondInner, { color: '#e6d6a8', opacity: 0.70, lineWidth: 1.15, closed: true });
    diamondGroup.add(lDiaOut, lDiaIn);
    primaryLines.push(lDiaOut);
    accentLines.push(lDiaIn);
    diamondGroup.userData.anim = { kind: 'liminalDiamond', baseZ: g.diamondCenter.z };
    corridorGroup.add(diamondGroup);
    animParts.push(diamondGroup);

    stars = makeStarPoints(g.stars, starShaderMat);
    corridorGroup.add(stars);

    corridorGroup.userData.anim = {
      kind: 'liminalCorridor',
      frames: frameObjs,
      signs: g.signs,
      railsLine,
      stars,
    };
    animParts.push(corridorGroup);

    const portalGlow = makeCoreSprite(photonTex, '#6ee7c0', 22, 0.46);
    if (portalGlow) {
      diamondGroup.add(portalGlow);
      sprites.push(portalGlow);
    }
  }

  return {
    id: cl.id || id,
    root,
    primaryLines,
    accentLines,
    stars,
    animParts,
    _sprites: sprites,
  };
}

/**
 * Create the 5 closed-contour animated MYTHOS constellations in SIDERA.
 */
export function createSideraSculpts(SIDERA_CLUSTERS, starShaderMat, photonTex = null) {
  const group = new THREE.Group();
  const clusters = (SIDERA_CLUSTERS || []).map((cl, idx) => {
    const built = assembleSideraCluster(cl, idx, starShaderMat, photonTex);
    group.add(built.root);
    return built;
  });

  function setFade(fade01) {
    const f = clamp(Number.isFinite(fade01) ? fade01 : 0, 0, 1);
    const vis = f > 0.004;
    for (const cluster of clusters) {
      for (const line of cluster.primaryLines) {
        line.material.opacity = (line.userData.baseOpacity ?? 0.78) * f;
        line.visible = vis;
      }
      for (const line of cluster.accentLines) {
        line.material.opacity = (line.userData.baseOpacity ?? 0.45) * f;
        line.visible = vis;
      }
      if (cluster.stars) {
        const highAttr = cluster.stars.geometry.getAttribute('aHighlight');
        const baseHigh = cluster.stars.userData.baseHighlight;
        if (highAttr && baseHigh) {
          const arr = highAttr.array;
          for (let i = 0; i < arr.length; i++) {
            arr[i] = vis ? baseHigh[i] * f : -1;
          }
          highAttr.needsUpdate = true;
        }
        cluster.stars.visible = vis;
      }
      for (const sp of cluster._sprites) {
        sp.material.opacity = (sp.userData.baseOpacity ?? 0.44) * f;
        sp.visible = vis;
      }
    }
  }

  return { group, clusters, setFade };
}

/**
 * Animate all 5 MYTHOS constellations with smooth breathing, halo rotation, eye pulse,
 * hexagram counter-rotation, dragon sway, and corridor depth pulse.
 */
export function animateSideraSculpts(sideraSculpts, t) {
  if (!sideraSculpts?.clusters) return;
  for (const cluster of sideraSculpts.clusters) {
    for (const part of cluster.animParts || []) {
      const anim = part.userData?.anim;
      if (!anim) continue;

      if (anim.kind === 'mythBreath') {
        part.position.y = Math.sin(t * 0.78) * 1.6;
      } else if (anim.kind === 'spinZ') {
        part.rotation.z = t * anim.speed;
      } else if (anim.kind === 'mythSun') {
        part.rotation.z = t * 0.28;
        part.position.y = anim.baseY + Math.sin(t * 1.15) * 1.1;
      } else if (anim.kind === 'mythMoon') {
        part.rotation.z = Math.sin(t * 0.95) * 0.14;
        part.position.y = anim.baseY - Math.sin(t * 1.15) * 1.1;
      } else if (anim.kind === 'hagSway') {
        part.rotation.z = Math.sin(t * 0.62) * 0.055;
      } else if (anim.kind === 'hagPupil') {
        const s = 0.65 + 0.45 * (0.5 + 0.5 * Math.sin(t * 1.55));
        part.scale.set(s, 0.95 + 0.08 * Math.cos(t * 1.55), 1);
      } else if (anim.kind === 'witchRing') {
        part.rotation.x = anim.baseRot.x + t * anim.rxSpeed;
        part.rotation.y = anim.baseRot.y + t * anim.rySpeed;
      } else if (anim.kind === 'witchStars') {
        const posAttr = part.geometry.getAttribute('position');
        const hexAngle = t * anim.hexSpeed;
        const outerAngle = t * anim.outerSpeed;
        for (let k = 0; k < 6; k++) {
          const a = Math.PI / 2 + (k * Math.PI) / 3 + hexAngle;
          posAttr.setXYZ(k, Math.cos(a) * anim.hexRadius, Math.sin(a) * anim.hexRadius, k % 2 === 0 ? 1.5 : -1.5);
        }
        for (let k = 0; k < 12; k++) {
          const a = (k / 12) * TWO_PI + outerAngle;
          posAttr.setXYZ(6 + k, Math.cos(a) * 54, Math.sin(a) * 54, 0);
        }
        posAttr.needsUpdate = true;
      } else if (anim.kind === 'cryptSway') {
        part.rotation.z = Math.sin(t * 0.85) * 0.045;
        part.position.y = Math.sin(t * 1.1) * 1.3;
      } else if (anim.kind === 'cryptPearl') {
        const ox = Math.cos(t * 1.35) * 1.8;
        const oy = Math.sin(t * 1.35) * 2.2;
        part.position.set(anim.baseCenter.x + ox, anim.baseCenter.y + oy, anim.baseCenter.z);
        part.rotation.z = t * 0.35;
        if (anim.halo) anim.halo.rotation.y = t * 0.7;
      } else if (anim.kind === 'cryptStars') {
        const posAttr = part.geometry.getAttribute('position');
        const swayZ = Math.sin(t * 0.85) * 0.045;
        const swayY = Math.sin(t * 1.1) * 1.3;
        const wx = anim.baseCenter.x + Math.cos(t * 1.35) * 1.8;
        const wy = anim.baseCenter.y + Math.sin(t * 1.35) * 2.2 - swayY;
        const cosA = Math.cos(-swayZ);
        const sinA = Math.sin(-swayZ);
        posAttr.setXYZ(anim.pearlIndex, wx * cosA - wy * sinA, wx * sinA + wy * cosA, anim.baseCenter.z);
        posAttr.needsUpdate = true;
      } else if (anim.kind === 'liminalDiamond') {
        part.rotation.z = t * 0.45;
        part.rotation.y = Math.sin(t * 0.75) * 0.35;
        const ds = 0.94 + 0.10 * Math.sin(t * 1.5);
        part.scale.set(ds, ds, 1);
        part.position.z = anim.baseZ + Math.sin(t * 1.25 - 1.95) * 2.2;
      } else if (anim.kind === 'liminalCorridor') {
        part.rotation.y = Math.sin(t * 0.48) * 0.065;
        part.rotation.x = Math.cos(t * 0.38) * 0.035;
        const animFrames = anim.frames.map((item, fIdx) => {
          const phase = t * 1.25 - fIdx * 0.65;
          const sc = 1 + 0.036 * Math.sin(phase);
          const z = item.spec.z + Math.sin(phase) * 2.2;
          item.line.scale.set(sc, sc, 1);
          item.line.position.z = z;
          return { w: item.spec.w * sc, h: item.spec.h * sc, z };
        });
        const railPos = anim.railsLine.geometry.getAttribute('position');
        let rIdx = 0;
        for (let fIdx = 0; fIdx < animFrames.length - 1; fIdx++) {
          const fa = animFrames[fIdx];
          const fb = animFrames[fIdx + 1];
          for (const [sx, sy] of anim.signs) {
            railPos.setXYZ(rIdx++, sx * fa.w, sy * fa.h, fa.z);
            railPos.setXYZ(rIdx++, sx * fb.w, sy * fb.h, fb.z);
          }
        }
        railPos.needsUpdate = true;
        const starPos = anim.stars.geometry.getAttribute('position');
        let sIdx = 0;
        for (const af of animFrames) {
          for (const [sx, sy] of anim.signs) {
            starPos.setXYZ(sIdx++, sx * af.w, sy * af.h, af.z);
          }
        }
        starPos.setXYZ(sIdx, 0, 0, animFrames[3].z);
        starPos.needsUpdate = true;
      }
    }
  }
}
