import * as THREE from 'three';
import design from './sidera-v3-design.json';

// The reference JSON supplies design anchors only; project stories and relation
// statuses continue to come from the real graph, not the 35 demo records.
const SCALE = 10.35;
const byId = new Map(design.map(item => [item.id, item]));
export const SIDERA_V3_DESIGN = design;

export function sampleV3Anchor(clusterId, index, total) {
  const positions = (byId.get(clusterId) || design[0]).anchors;
  const n = Math.max(1, total || 1), safe = ((index % n) + n) % n;
  const a = positions[safe % positions.length];
  const turn = Math.floor(safe / positions.length);
  const angle = turn * 2.3999632297 + safe * 0.12;
  const r = Math.min(6, 1.15 + Math.sqrt(turn) * 1.22);
  return new THREE.Vector3(a[0] * SCALE + Math.cos(angle) * r,
    a[1] * SCALE + Math.sin(angle) * r, a[2] * SCALE + Math.sin(angle * 0.71) * 1.8);
}

export function sampleV3Dust(clusterId, index, rand = Math.random) {
  const positions = (byId.get(clusterId) || design[0]).anchors;
  const a = positions[Math.abs(Math.floor(index)) % positions.length];
  const angle = rand() * Math.PI * 2, radius = Math.sqrt(rand()) * 10.5;
  return new THREE.Vector3(a[0] * SCALE + Math.cos(angle) * radius,
    a[1] * SCALE + Math.sin(angle) * radius, a[2] * SCALE + (rand() - 0.5) * 12);
}

export function createSideraV3Sculpts(projectClusters, options = {}) {
  const CLUSTER_MAP = Object.fromEntries(design.map((item, i) => [item.referenceId, {
    ...item, id: item.referenceId,
    center: projectClusters[i].center.clone().multiplyScalar(1 / SCALE),
  }]));
  const RING_RADIUS = 16;
    function makeClosedCircleLoop(radius, segments, colorHex, opacity = 0.42) {
      const pts = [];
      for (let i = 0; i < segments; i++) {
        const a = (i / segments) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, 0));
      }
      return new THREE.LineLoop(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: colorHex, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending })
      );
    }

    function makeClosedPolygonLoop(vec3Array, colorHex, opacity = 0.55) {
      return new THREE.LineLoop(
        new THREE.BufferGeometry().setFromPoints(vec3Array),
        new THREE.LineBasicMaterial({ color: colorHex, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending })
      );
    }

    function makeDegreeTicks(rInner, rOuter, count, colorHex, opacity = 0.35) {
      const pts = [];
      for (let i = 0; i < count; i++) {
        const a = (i / count) * Math.PI * 2;
        const len = i % 3 === 0 ? rOuter : (rInner + (rOuter - rInner) * 0.55);
        pts.push(
          new THREE.Vector3(Math.cos(a) * rInner, Math.sin(a) * rInner, 0),
          new THREE.Vector3(Math.cos(a) * len, Math.sin(a) * len, 0)
        );
      }
      return new THREE.LineSegments(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: colorHex, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending })
      );
    }

    function makeLineSegments(pairPoints, colorHex, opacity = 0.52) {
      return new THREE.LineSegments(
        new THREE.BufferGeometry().setFromPoints(pairPoints),
        new THREE.LineBasicMaterial({ color: colorHex, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending })
      );
    }

    // Living Photon Streamer Tracks across all 5 constellations & central rings
    const masterUniverse = new THREE.Group();
    // The parent scene attaches the isolated art group.

    const clusterGroups = {};
    const kineticRig = [];         // Custom per-frame 3D object animations
    const decorativeStars = [];    // Volumetric & structural stars
    const constellationTracks = []; // Closed/smooth 3D paths for Living Photon Streamers!

    function pushDecoStar(localVec, clusterCenter, colorHex, size, spike = 0, amp = 0.05, freq = 1.2, mode = 0) {
      decorativeStars.push({ clusterId: (Object.values(CLUSTER_MAP).find(c => c.center === clusterCenter)?.id ?? null),
        pos: localVec.clone().add(clusterCenter),
        color: new THREE.Color(colorHex),
        size,
        spike,
        amp,
        freq,
        mode,
        phase: Math.random() * Math.PI * 2
      });
    }

    function registerCircleStreamerTrack(centerVec, radius, eulerRot, colorHex, photonCount, speed, size = 5.6) {
      const pts = [];
      const N = 72;
      for (let i = 0; i <= N; i++) {
        const a = (i / N) * Math.PI * 2;
        const v = new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, 0);
        if (eulerRot) v.applyEuler(eulerRot);
        v.add(centerVec);
        pts.push(v);
      }
      const curve = new THREE.CatmullRomCurve3(pts, true);
      for (let k = 0; k < photonCount; k++) {
        constellationTracks.push({
          curve,
          color: new THREE.Color(colorHex),
          speed,
          offset: k / photonCount,
          size
        });
      }
    }

    function registerCurveStreamerTrack(worldPoints, closed, colorHex, photonCount, speed, size = 6.0) {
      const curve = new THREE.CatmullRomCurve3(worldPoints, closed);
      for (let k = 0; k < photonCount; k++) {
        constellationTracks.push({
          curve,
          color: new THREE.Color(colorHex),
          speed,
          offset: k / photonCount,
          size
        });
      }
    }

    // =========================================================================
    // 5. SCULPT THE 5 SACRED CONSTELLATIONS (WITH NEW M2, NEW M4 ZHULONG & 4D M5)
    // =========================================================================

    // -------------------------------------------------------------------------
    // MYTHOS I: 太初托天星神 · Cosmic Deity Urania (Counter-rotating Sun/Moon + Cascading Robe)
    // -------------------------------------------------------------------------
    (function buildMythosI() {
      const cl = CLUSTER_MAP.M1;
      const g = new THREE.Group();
      g.position.copy(cl.center);
      masterUniverse.add(g);
      clusterGroups.M1 = g;

      g.add(makeClosedCircleLoop(4.65, 128, cl.color, 0.36));
      g.add(makeClosedCircleLoop(4.32, 128, cl.secondary, 0.22));
      g.add(makeDegreeTicks(4.32, 4.62, 36, cl.color, 0.32));

      const eqRing = makeClosedCircleLoop(4.48, 112, cl.color, 0.22);
      eqRing.rotation.set(1.18, 0.15, 0);
      g.add(eqRing);
      kineticRig.push(dt => { eqRing.rotation.z += dt * 0.24; });

      registerCircleStreamerTrack(cl.center, 4.65, null, cl.accent, 5, 0.085, 5.8);

      // Rotating Divine Eclipse Crown & Head Halo
      const crownGroup = new THREE.Group();
      crownGroup.position.set(0, 2.28, 0.2);
      crownGroup.add(makeClosedCircleLoop(0.86, 64, cl.accent, 0.68));
      crownGroup.add(makeClosedCircleLoop(0.46, 48, cl.color, 0.75));
      const crownStarPts = [];
      for (let i = 0; i < 16; i++) {
        const r = i % 2 === 0 ? 1.08 : 0.62;
        const a = (i / 16) * Math.PI * 2;
        crownStarPts.push(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, 0));
      }
      const crownBurst = makeClosedPolygonLoop(crownStarPts, cl.color, 0.45);
      crownGroup.add(crownBurst);
      g.add(crownGroup);
      kineticRig.push(dt => { crownBurst.rotation.z -= dt * 0.32; });

      // Left Hand: Counter-Rotating Closed Radiant Sun Wheel
      const sunPos = new THREE.Vector3(-2.85, 0.95, 0.2);
      const sunWheel = new THREE.Group();
      sunWheel.position.copy(sunPos);
      sunWheel.add(makeClosedCircleLoop(0.64, 56, cl.accent, 0.82));
      sunWheel.add(makeClosedCircleLoop(0.32, 40, cl.secondary, 0.58));
      const sunSpokes = [];
      for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2;
        sunSpokes.push(new THREE.Vector3(0, 0, 0), new THREE.Vector3(Math.cos(a) * 0.64, Math.sin(a) * 0.64, 0));
      }
      sunWheel.add(makeLineSegments(sunSpokes, cl.color, 0.52));
      g.add(sunWheel);

      // Right Hand: Counter-Rotating Closed Lunar-Eclipse Orb
      const moonPos = new THREE.Vector3(2.85, 0.95, -0.2);
      const moonOrb = new THREE.Group();
      moonOrb.position.copy(moonPos);
      moonOrb.add(makeClosedCircleLoop(0.64, 56, '#dce8ff', 0.82));
      const moonShadow = makeClosedCircleLoop(0.46, 48, cl.color, 0.56);
      moonShadow.position.set(-0.14, 0.05, 0);
      moonOrb.add(moonShadow);
      g.add(moonOrb);

      kineticRig.push(dt => {
        sunWheel.rotation.z += dt * 0.55;
        moonOrb.rotation.z -= dt * 0.42;
      });

      // Closed Celestial Vault Arch + Deity Torso + 3D Astral Robe
      const vaultLoopPts = [];
      for (let i = 0; i <= 28; i++) {
        const t = i / 28;
        const a = Math.PI * (1 - t);
        vaultLoopPts.push(new THREE.Vector3(Math.cos(a) * 2.85, 0.95 + Math.sin(a) * 2.38, THREE.MathUtils.lerp(0.2, -0.2, t)));
      }
      const neck = new THREE.Vector3(0, 1.72, 0.22);
      const shL = new THREE.Vector3(-1.28, 1.32, 0.15);
      const shR = new THREE.Vector3(1.28, 1.32, 0.15);
      const elL = new THREE.Vector3(-2.22, 1.05, 0.18);
      const elR = new THREE.Vector3(2.22, 1.05, -0.12);
      const heart = new THREE.Vector3(0, 0.88, 0.30);
      const waistL = new THREE.Vector3(-0.56, 0.02, 0.22);
      const waistR = new THREE.Vector3(0.56, 0.02, 0.22);
      const navel = new THREE.Vector3(0, -0.22, 0.30);
      const hemL = new THREE.Vector3(-1.62, -2.55, 0.25);
      const hemML = new THREE.Vector3(-0.68, -2.82, 0.48);
      const hemC = new THREE.Vector3(0.0, -2.90, 0.55);
      const hemMR = new THREE.Vector3(0.68, -2.82, 0.48);
      const hemR = new THREE.Vector3(1.62, -2.55, 0.25);

      vaultLoopPts.push(elR, shR, heart, shL, elL);
      g.add(makeClosedPolygonLoop(vaultLoopPts, cl.color, 0.44));
      g.add(makeClosedPolygonLoop([neck, shR, waistR, navel, waistL, shL], cl.accent, 0.64));
      g.add(makeClosedPolygonLoop([shL, elL, sunPos, elL, waistL, heart], cl.color, 0.36));
      g.add(makeClosedPolygonLoop([shR, elR, moonPos, elR, waistR, heart], cl.color, 0.36));

      const hemRingPts = [];
      for (let i = 0; i < 64; i++) {
        const a = (i / 64) * Math.PI * 2;
        hemRingPts.push(new THREE.Vector3(Math.cos(a) * 1.65, -2.65 + Math.sin(a) * 0.26, Math.sin(a) * 0.55));
      }
      g.add(makeClosedPolygonLoop(hemRingPts, cl.color, 0.44));
      g.add(makeLineSegments([
        neck, heart, heart, navel, navel, hemC, shL, heart, shR, heart,
        waistL, hemL, waistL, hemML, waistR, hemMR, waistR, hemR
      ], cl.accent, 0.52));

      // Photon streamer flowing across the Sun -> Crown -> Moon Celestial Vault!
      registerCurveStreamerTrack(vaultLoopPts.map(p => p.clone().add(cl.center)), true, cl.accent, 4, 0.12, 6.2);

      [shL, shR, elL, elR, waistL, waistR, navel, hemR, hemML, hemMR].forEach(pt => {
        pushDecoStar(pt, cl.center, cl.accent, 4.8, 0.45, 0.02, 1.0, 1);
      });

      for (let i = 0; i < 560; i++) {
        if (i < 360) {
          const v = Math.pow(Math.random(), 0.85);
          const y = THREE.MathUtils.lerp(0.95, -2.95, v);
          const coneR = THREE.MathUtils.lerp(0.35, 1.72, v) + (Math.random() - 0.5) * 0.26;
          const th = Math.random() * Math.PI * 2;
          const pt = new THREE.Vector3(Math.cos(th) * coneR, y, Math.sin(th) * coneR * 0.42);
          pushDecoStar(pt, cl.center, i % 3 === 0 ? cl.accent : cl.color, 1.45 + Math.random() * 1.85, 0, 0.06, 1.5, 1);
        } else {
          const a = Math.random() * Math.PI * 2;
          const r = 3.98 + (Math.random() - 0.5) * 0.8;
          const pt = new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, (Math.random() - 0.5) * 0.6);
          pushDecoStar(pt, cl.center, cl.secondary, 1.3 + Math.random() * 1.5, 0, 0.04, 0.9, 1);
        }
      }
    })();

    // -------------------------------------------------------------------------
    // MYTHOS II (REDESIGNED): 月蚀重冕 · 十二宫捕梦浑仪 (Lunar Eclipse Orrery & 12-Fold Mandala)
    // -------------------------------------------------------------------------
    (function buildMythosII() {
      const cl = CLUSTER_MAP.M2;
      const g = new THREE.Group();
      g.position.copy(cl.center);
      masterUniverse.add(g);
      clusterGroups.M2 = g;

      // 1. Outer Stationary Astrolabe Bezel (Strictly Closed)
      g.add(makeClosedCircleLoop(4.68, 128, cl.color, 0.38));
      g.add(makeDegreeTicks(4.38, 4.66, 36, cl.accent, 0.34));
      registerCircleStreamerTrack(cl.center, 4.68, null, cl.accent, 5, -0.08, 5.6);

      // 2. Three Concentric Silver-Indigo Gimbal Rings Precessing on Independent X/Y/Z Axes!
      const gimbalOuter = new THREE.Group();
      gimbalOuter.add(makeClosedCircleLoop(4.26, 112, cl.color, 0.44));
      gimbalOuter.add(makeDegreeTicks(4.08, 4.25, 24, cl.color, 0.28));
      gimbalOuter.rotation.set(0.58, 0.22, 0);

      const gimbalMid = new THREE.Group();
      gimbalMid.add(makeClosedCircleLoop(3.68, 108, cl.secondary, 0.42));
      gimbalMid.rotation.set(-0.46, 0.62, 0.18);

      const gimbalInner = new THREE.Group();
      gimbalInner.add(makeClosedCircleLoop(3.08, 96, cl.accent, 0.36));
      gimbalInner.rotation.set(0.72, -0.45, -0.25);

      g.add(gimbalOuter, gimbalMid, gimbalInner);

      // 3. Intricate 12-Fold Sacred Inscribed Chord Mandala (Matches the Sacred Geometry Elegance of III!)
      const mandalaGroup = new THREE.Group();
      const mR = 2.58;
      mandalaGroup.add(makeClosedCircleLoop(mR, 96, cl.color, 0.52));

      const twelveNodes = [];
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * Math.PI * 2 + Math.PI / 2;
        const v = new THREE.Vector3(Math.cos(a) * mR, Math.sin(a) * mR, 0.08);
        twelveNodes.push(v);
        pushDecoStar(v, cl.center, cl.accent, 5.2, 0.55, 0.02, 1.0, 2);
      }

      // {12/5} Star Dodecagram: single continuous closed LineLoop visiting all 12 mansion nodes (gcd(12,5)=1)!
      const dodecagramLoop = [];
      for (let k = 0; k < 12; k++) {
        dodecagramLoop.push(twelveNodes[(k * 5) % 12]);
      }
      mandalaGroup.add(makeClosedPolygonLoop(dodecagramLoop, cl.accent, 0.58));

      // {12/4} Four Closed Interlocking Equilateral Triangles
      for (let t = 0; t < 4; t++) {
        mandalaGroup.add(makeClosedPolygonLoop([
          twelveNodes[t], twelveNodes[t + 4], twelveNodes[t + 8]
        ], cl.secondary, 0.34));
      }

      // {12/3} Three Closed Interlocking Squares
      for (let s = 0; s < 3; s++) {
        mandalaGroup.add(makeClosedPolygonLoop([
          twelveNodes[s], twelveNodes[s + 3], twelveNodes[s + 6], twelveNodes[s + 9]
        ], cl.color, 0.24));
      }
      g.add(mandalaGroup);

      // Register photon streamer tracing the 12-fold Dodecagram Mandala!
      registerCurveStreamerTrack(dodecagramLoop.map(p => p.clone().add(cl.center)), true, cl.accent, 4, 0.11, 5.8);

      // 4. Dark Eclipsed Lunar Core + Glowing Silver-Violet Baily's Beads Corona
      const eclipseCoreGroup = new THREE.Group();
      eclipseCoreGroup.position.set(0, 0, 0.16);
      const darkMoonMesh = new THREE.Mesh(
        new THREE.CircleGeometry(0.84, 64),
        new THREE.MeshBasicMaterial({ color: '#03050c', transparent: true, opacity: 0.96, side: THREE.DoubleSide })
      );
      eclipseCoreGroup.add(darkMoonMesh);
      eclipseCoreGroup.add(makeClosedCircleLoop(0.86, 72, '#ffffff', 0.92));
      eclipseCoreGroup.add(makeClosedCircleLoop(1.04, 72, cl.secondary, 0.48));

      // Baily's Beads & Diamond-Ring Solar-Lunar Flare Stars around the dark moon limb
      for (let b = 0; b < 24; b++) {
        const a = (b / 24) * Math.PI * 2;
        const isDiamond = (b === 3 || b === 15);
        const beadPt = new THREE.Vector3(Math.cos(a) * 0.87, Math.sin(a) * 0.87, 0.22);
        pushDecoStar(
          beadPt, cl.center,
          isDiamond ? '#ffffff' : cl.accent,
          isDiamond ? 11.5 : (2.6 + (b % 3) * 1.4),
          isDiamond ? 1.25 : 0.25,
          0.015, 2.0, 2
        );
      }
      g.add(eclipseCoreGroup);

      // 5. Orbiting 8 Lunar Phase Pearls (New Moon -> Waxing -> Full Moon -> Waning Gradient)
      const phaseOrbitGroup = new THREE.Group();
      phaseOrbitGroup.add(makeClosedCircleLoop(3.36, 96, cl.color, 0.24));
      for (let m = 0; m < 8; m++) {
        const a = (m / 8) * Math.PI * 2;
        const illumination = 0.22 + 0.78 * Math.sin((m / 8) * Math.PI); // New -> Full -> New
        const px = Math.cos(a) * 3.36;
        const py = Math.sin(a) * 3.36;
        const pearlRim = makeClosedCircleLoop(0.18 + illumination * 0.08, 28, m === 4 ? '#ffffff' : cl.color, 0.35 + illumination * 0.55);
        pearlRim.position.set(px, py, 0.14);
        phaseOrbitGroup.add(pearlRim);

        const pearlCore = new THREE.Mesh(
          new THREE.CircleGeometry(0.11 + illumination * 0.06, 24),
          new THREE.MeshBasicMaterial({
            color: m === 4 ? '#ffffff' : cl.accent,
            transparent: true,
            opacity: illumination * 0.88,
            blending: THREE.AdditiveBlending
          })
        );
        pearlCore.position.set(px, py, 0.15);
        phaseOrbitGroup.add(pearlCore);
      }
      g.add(phaseOrbitGroup);

      // 6. Phase-Shifted Twin Halo ("重影幻身环" — Symbolizing REM Dissociation & TPJ Felt Presence!)
      const twinPhantomHalo = new THREE.Group();
      twinPhantomHalo.add(makeClosedCircleLoop(2.58, 84, '#67e8f9', 0.32));
      twinPhantomHalo.add(makeClosedCircleLoop(0.88, 56, '#c4b5fd', 0.42));
      g.add(twinPhantomHalo);

      let m2Clock = 0;
      kineticRig.push(dt => {
        m2Clock += dt;
        gimbalOuter.rotation.y += dt * 0.28;
        gimbalOuter.rotation.z += dt * 0.12;
        gimbalMid.rotation.x -= dt * 0.34;
        gimbalMid.rotation.z += dt * 0.18;
        gimbalInner.rotation.y -= dt * 0.42;
        gimbalInner.rotation.x += dt * 0.22;
        mandalaGroup.rotation.z += dt * 0.08;
        phaseOrbitGroup.rotation.z -= dt * 0.24;

        // Ghostly phase-shifted spatial drift (TPJ body-schema dissociation!)
        twinPhantomHalo.position.set(
          Math.sin(m2Clock * 1.35) * 0.36,
          Math.cos(m2Clock * 1.05) * 0.28,
          0.35 + Math.sin(m2Clock * 1.7) * 0.26
        );
        twinPhantomHalo.rotation.y = Math.sin(m2Clock * 0.9) * 0.25;
      });

      // Penumbra silver-violet stardust cloud (520 particles)
      for (let i = 0; i < 520; i++) {
        const a = Math.random() * Math.PI * 2;
        const r = i < 220 ? (0.92 + Math.random() * 1.65) : (2.7 + Math.random() * 1.75);
        const pt = new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, (Math.random() - 0.5) * 0.85);
        pushDecoStar(pt, cl.center, i % 2 === 0 ? cl.color : cl.secondary, 1.35 + Math.random() * 1.75, 0, 0.06, 1.25, 2);
      }
    })();

    // -------------------------------------------------------------------------
    // MYTHOS III: 所罗门六芒星盘 · Sabbat Hexagram Seal (Upgraded Counter-Rotation & Orbiting Sigils)
    // -------------------------------------------------------------------------
    (function buildMythosIII() {
      const cl = CLUSTER_MAP.M3;
      const g = new THREE.Group();
      g.position.copy(cl.center);
      masterUniverse.add(g);
      clusterGroups.M3 = g;

      g.add(makeClosedCircleLoop(4.62, 128, cl.accent, 0.44));
      g.add(makeClosedCircleLoop(4.18, 128, cl.color, 0.35));
      g.add(makeClosedCircleLoop(2.85, 96, cl.color, 0.28));
      g.add(makeClosedCircleLoop(1.42, 64, cl.accent, 0.40));
      g.add(makeDegreeTicks(4.18, 4.60, 24, cl.accent, 0.42));

      // Counter-rotating Sacred Interlocking Hexagrams + Inner Dodecagram
      const hexUpGroup = new THREE.Group();
      const hexDownGroup = new THREE.Group();
      const triUp = [];
      const triDown = [];
      for (let i = 0; i < 3; i++) {
        const a1 = Math.PI / 2 + (i * Math.PI * 2) / 3;
        const a2 = -Math.PI / 2 + (i * Math.PI * 2) / 3;
        triUp.push(new THREE.Vector3(Math.cos(a1) * 3.35, Math.sin(a1) * 3.35, 0.12));
        triDown.push(new THREE.Vector3(Math.cos(a2) * 3.35, Math.sin(a2) * 3.35, -0.12));
      }
      hexUpGroup.add(makeClosedPolygonLoop(triUp, cl.accent, 0.80));
      hexDownGroup.add(makeClosedPolygonLoop(triDown, cl.color, 0.74));
      g.add(hexUpGroup, hexDownGroup);

      const innerTwelve = [];
      for (let i = 0; i < 12; i++) {
        const a = (i * 5 * Math.PI * 2) / 12;
        innerTwelve.push(new THREE.Vector3(Math.cos(a) * 2.85, Math.sin(a) * 2.85, 0));
      }
      const dodecaRing = makeClosedPolygonLoop(innerTwelve, cl.color, 0.26);
      g.add(dodecaRing);

      // Orbiting Planetary Sigil Diamonds along the Seal Rim
      const sigilRingGroup = new THREE.Group();
      for (let s = 0; s < 6; s++) {
        const a = (s / 6) * Math.PI * 2 + Math.PI / 6;
        const sx = Math.cos(a) * 4.40;
        const sy = Math.sin(a) * 4.40;
        const rSig = 0.18;
        sigilRingGroup.add(makeClosedPolygonLoop([
          new THREE.Vector3(sx - rSig, sy, 0.1),
          new THREE.Vector3(sx, sy + rSig, 0.1),
          new THREE.Vector3(sx + rSig, sy, 0.1),
          new THREE.Vector3(sx, sy - rSig, 0.1)
        ], cl.accent, 0.75));
      }
      g.add(sigilRingGroup);

      const tiltedOrbit = makeClosedCircleLoop(3.85, 112, cl.accent, 0.34);
      tiltedOrbit.rotation.set(1.08, 0.28, -0.18);
      g.add(tiltedOrbit);

      let m3Phase = 0;
      kineticRig.push(dt => {
        m3Phase += dt;
        // Subtle harmonic counter-oscillation so story stars remain aligned while seal breathes alive!
        hexUpGroup.rotation.z = Math.sin(m3Phase * 0.45) * 0.08;
        hexDownGroup.rotation.z = -Math.sin(m3Phase * 0.45) * 0.08;
        dodecaRing.rotation.z -= dt * 0.12;
        sigilRingGroup.rotation.z += dt * 0.22;
        tiltedOrbit.rotation.z += dt * 0.32;
      });

      registerCurveStreamerTrack(triUp.map(p => p.clone().add(cl.center)), true, cl.accent, 3, 0.16, 6.2);
      registerCurveStreamerTrack(triDown.map(p => p.clone().add(cl.center)), true, cl.color, 3, -0.16, 6.2);

      [...triUp, ...triDown].forEach(pt => pushDecoStar(pt, cl.center, cl.accent, 5.2, 0.55, 0.02, 1.1, 3));

      const tiltEuler = new THREE.Euler(1.18, 0.12, -0.08);
      for (let i = 0; i < 620; i++) {
        const a = Math.random() * Math.PI * 2;
        const r = 1.55 + Math.random() * 2.95;
        const pt = new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, (Math.random() - 0.5) * 0.32);
        if (i < 420) pt.applyEuler(tiltEuler);
        pushDecoStar(pt, cl.center, i % 3 === 0 ? cl.color : cl.accent, 1.45 + Math.random() * 2.0, 0, 0.07, 1.4, 3);
      }
    })();

    // -------------------------------------------------------------------------
    // MYTHOS IV (REBUILT FROM REFERENCE ARTWORK): 赤金人面烛龙星宿 (Crimson-Gold Human-Deity Zhulong)
    // -------------------------------------------------------------------------
    (function buildMythosIV() {
      const cl = CLUSTER_MAP.M4;
      const g = new THREE.Group();
      g.position.copy(cl.center);
      masterUniverse.add(g);
      clusterGroups.M4 = g;

      const GOLD_BRIGHT = '#ffe6a3';
      const GOLD_WARM = '#f5cb73';
      const CINNABAR = '#ff4d36';
      const CRIMSON_DEEP = '#a31d14';

      // 1. Subtle Tilted Crimson-Gold Meridian Astrolabe Frame (Harmonizes with Sister Clusters!)
      g.add(makeClosedCircleLoop(4.68, 128, GOLD_WARM, 0.32));
      g.add(makeClosedCircleLoop(4.42, 128, CINNABAR, 0.24));
      g.add(makeDegreeTicks(4.42, 4.66, 36, GOLD_WARM, 0.30));

      const zhulongOrbit = makeClosedCircleLoop(4.52, 112, CINNABAR, 0.20);
      zhulongOrbit.rotation.set(1.12, -0.28, 0.15);
      g.add(zhulongOrbit);
      registerCircleStreamerTrack(cl.center, 4.68, null, GOLD_BRIGHT, 5, 0.09, 5.8);

      // 2. FOCAL CENTER — Sculpted Gilded Human Deity Profile Facing LEFT (`鎏金神面侧颜`)
      // High-precision silhouette matching the serene left-facing gold mask in the reference painting!
      const faceProfile2D = [
        [ 0.14,  0.86], // Crown peak
        [-0.04,  0.76], // Upper forehead
        [-0.17,  0.58], // Mid forehead
        [-0.22,  0.44], // Supraorbital brow ridge
        [-0.16,  0.34], // Nasal bridge root
        [-0.29,  0.19], // Straight noble nose bridge
        [-0.39,  0.07], // Sculpted nose tip (facing left!)
        [-0.27,  0.02], // Nostril base
        [-0.32, -0.04], // Upper lip peak
        [-0.24, -0.08], // Parted lip line
        [-0.29, -0.14], // Lower lip curve
        [-0.22, -0.21], // Labiomental chin indent
        [-0.25, -0.34], // Serene chin tip
        [-0.08, -0.42], // Under-jaw line
        [ 0.18, -0.37], // Jawline corner near solar earring
        [ 0.32, -0.16], // Scalloped golden cheek-mask lower curve
        [ 0.40,  0.10], // Golden cheek-mask mid border
        [ 0.36,  0.38], // Temple border
        [ 0.26,  0.66]  // Flame-peaked golden hairline
      ];
      const faceContour3D = faceProfile2D.map(([x, y]) => new THREE.Vector3(x, y, 0.30));
      g.add(makeClosedPolygonLoop(faceContour3D, GOLD_BRIGHT, 0.94));

      // Inner gilded bevel contour + serene divine eye (`烛阴之目`) & brow line
      const faceInner3D = faceProfile2D.map(([x, y]) => new THREE.Vector3(x * 0.88 + 0.02, y * 0.90, 0.31));
      g.add(makeClosedPolygonLoop(faceInner3D, GOLD_WARM, 0.45));

      const eyeLoop = [
        new THREE.Vector3(-0.16, 0.33, 0.33),
        new THREE.Vector3(-0.07, 0.37, 0.33),
        new THREE.Vector3( 0.04, 0.34, 0.33),
        new THREE.Vector3(-0.06, 0.29, 0.33)
      ];
      g.add(makeClosedPolygonLoop(eyeLoop, '#ffffff', 0.92));

      // Closed double-line eyebrow crest above eye
      g.add(makeClosedPolygonLoop([
        new THREE.Vector3(-0.19, 0.42, 0.32),
        new THREE.Vector3(-0.04, 0.47, 0.32),
        new THREE.Vector3( 0.14, 0.52, 0.32),
        new THREE.Vector3(-0.03, 0.44, 0.32)
      ], GOLD_BRIGHT, 0.78));

      // Point-in-polygon helper to fill the Gilded Mask with shimmering golden leaf micro-stars!
      function isInsideFaceMask(px, py) {
        let inside = false;
        for (let i = 0, j = faceProfile2D.length - 1; i < faceProfile2D.length; j = i++) {
          const xi = faceProfile2D[i][0], yi = faceProfile2D[i][1];
          const xj = faceProfile2D[j][0], yj = faceProfile2D[j][1];
          const intersect = ((yi > py) !== (yj > py)) && (px < ((xj - xi) * (py - yi)) / (yj - yi + 1e-6) + xi);
          if (intersect) inside = !inside;
        }
        return inside;
      }

      let maskStarsPlaced = 0;
      while (maskStarsPlaced < 260) {
        const rx = -0.40 + Math.random() * 0.84;
        const ry = -0.44 + Math.random() * 1.32;
        if (isInsideFaceMask(rx, ry)) {
          pushDecoStar(
            new THREE.Vector3(rx, ry, 0.29 + (Math.random() - 0.5) * 0.04),
            cl.center,
            maskStarsPlaced % 3 === 0 ? GOLD_BRIGHT : GOLD_WARM,
            1.7 + Math.random() * 1.8,
            0, 0.012, 1.5, 4
          );
          maskStarsPlaced++;
        }
      }

      // 8-Spoked Rotating Solar Wheel Earring (`八芒日轮耳珰`) + Periodic "视为昼" Daybreak Flare Wave!
      const earringGroup = new THREE.Group();
      earringGroup.position.set(0.24, -0.22, 0.35);
      earringGroup.add(makeClosedCircleLoop(0.30, 40, GOLD_BRIGHT, 0.92));
      earringGroup.add(makeClosedCircleLoop(0.11, 24, '#ffffff', 0.88));
      const earSpokes = [];
      for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2;
        earSpokes.push(new THREE.Vector3(0, 0, 0), new THREE.Vector3(Math.cos(a) * 0.36, Math.sin(a) * 0.36, 0));
      }
      earringGroup.add(makeLineSegments(earSpokes, GOLD_BRIGHT, 0.82));
      g.add(earringGroup);

      // Periodic "视为昼 (Daybreak Solar Pulse)" expanding golden ring wave
      const daybreakWave = makeClosedCircleLoop(1.0, 96, GOLD_BRIGHT, 0.0);
      daybreakWave.position.set(0.08, 0.12, 0.34);
      g.add(daybreakWave);

      // 3. Soaring Crimson-Gold Flame Horns (`冲天赤焰双角`) & 5 Flowing Fiery Mane Ribbons (`流火长鬃`)
      function buildClosedFlameRibbon(spineCoords, halfWidths, edgeCol, op = 0.78) {
        const curve = new THREE.CatmullRomCurve3(spineCoords.map(c => new THREE.Vector3(c[0], c[1], c[2])));
        const N = 36;
        const pts = curve.getPoints(N);
        const sideA = [];
        const sideB = [];
        for (let i = 0; i <= N; i++) {
          const t = i / N;
          const tan = curve.getTangent(t);
          const norm = new THREE.Vector3(-tan.y, tan.x, 0).normalize();
          // Smoothly taper to 0 at both root and sharp flame tip!
          const wProfile = Math.sin(Math.pow(t, 0.7) * Math.PI) * halfWidths;
          sideA.push(pts[i].clone().addScaledVector(norm, wProfile));
          sideB.push(pts[i].clone().addScaledVector(norm, -wProfile));
        }
        const loopPts = [...sideA, ...sideB.reverse()];
        return { loop: makeClosedPolygonLoop(loopPts, edgeCol, op), curve };
      }

      // Left/Front Tall Soaring Flame Horn (Sweeping up-right to y=3.95 just like the painting!)
      const horn1 = buildClosedFlameRibbon([
        [0.04, 0.80, 0.26], [0.22, 1.55, 0.24], [0.42, 2.38, 0.20], [0.68, 3.22, 0.16], [0.95, 3.96, 0.12]
      ], 0.17, GOLD_BRIGHT, 0.86);
      // Right/Secondary Soaring Flame Horn
      const horn2 = buildClosedFlameRibbon([
        [0.24, 0.70, 0.22], [0.58, 1.48, 0.18], [0.86, 2.25, 0.14], [1.24, 3.05, 0.10], [1.56, 3.68, 0.08]
      ], 0.16, CINNABAR, 0.82);
      g.add(horn1.loop, horn2.loop);

      // 5 Flowing Fiery Crimson-Gold Hair/Mane Streams sweeping toward the right
      const manePaths = [
        [[0.34, 0.56, 0.20], [0.95, 0.92, 0.16], [1.72, 1.48, 0.10], [2.58, 2.02, 0.04]],
        [[0.38, 0.34, 0.22], [1.12, 0.52, 0.18], [1.95, 0.98, 0.14], [2.95, 1.28, 0.08]],
        [[0.38, 0.10, 0.22], [1.15, 0.08, 0.20], [2.08, 0.42, 0.15], [3.22, 0.58, 0.08]],
        [[0.32, -0.14, 0.20], [1.05, -0.34, 0.16], [1.92, -0.08, 0.12], [2.88, -0.18, 0.05]],
        [[0.16, -0.38, 0.18], [0.72, -0.72, 0.14], [1.48, -0.58, 0.10], [2.25, -0.68, 0.04]]
      ];
      manePaths.forEach((mp, idx) => {
        const mr = buildClosedFlameRibbon(mp, 0.13 - idx * 0.01, idx % 2 === 0 ? GOLD_WARM : CINNABAR, 0.72);
        g.add(mr.loop);
        // Seed dense glowing flame-mane particles along each ribbon
        for (let p = 0; p < 52; p++) {
          const pt = mr.curve.getPoint(Math.random());
          pt.x += (Math.random() - 0.5) * 0.16;
          pt.y += (Math.random() - 0.5) * 0.16;
          pushDecoStar(pt, cl.center, p % 3 === 0 ? GOLD_BRIGHT : CINNABAR, 1.6 + Math.random() * 2.0, 0, 0.085, 2.1, 4);
        }
      });

      // Seed soaring horn flame stars
      [horn1.curve, horn2.curve].forEach(hc => {
        for (let p = 0; p < 85; p++) {
          const pt = hc.getPoint(Math.random());
          pt.x += (Math.random() - 0.5) * 0.18;
          pt.y += (Math.random() - 0.5) * 0.18;
          pushDecoStar(pt, cl.center, p % 2 === 0 ? GOLD_BRIGHT : CINNABAR, 1.7 + Math.random() * 2.1, 0, 0.09, 2.3, 4);
        }
      });

      // 4. DRAMATIC LEFT-ARCHED C-COILED CRIMSON DRAGON BODY (`左拱回旋赤龙巨躯`)
      // Sweeps from lower-left flame tail -> across base -> lower-right loop -> under chin ->
      // iconic wide LEFT C-ARCH around the golden face -> soaring up-right behind the horns!
      const dragonSpineWaypoints = [
        new THREE.Vector3(-3.55, -2.52,  0.14), // Lower-left flame tail tip
        new THREE.Vector3(-1.85, -2.28, -0.06), // Lower mountain wave
        new THREE.Vector3( 0.25, -1.98, -0.18), // Bottom sweep
        new THREE.Vector3( 1.98, -1.42, -0.14), // Lower-right outer coil
        new THREE.Vector3( 1.72, -0.78,  0.04), // Rising inner turn
        new THREE.Vector3( 0.18, -1.16,  0.16), // Sweeping beneath the golden chin
        new THREE.Vector3(-1.38, -0.96,  0.22), // Entering the grand left C-arch
        new THREE.Vector3(-2.46, -0.05,  0.24), // Leftmost C-arch belly framing the face!
        new THREE.Vector3(-2.36,  1.18,  0.18), // Upper-left C-arch shoulder
        new THREE.Vector3(-1.42,  2.06,  0.06), // Over-arch crest
        new THREE.Vector3( 0.12,  2.14, -0.14), // Passing behind the soaring flame horns
        new THREE.Vector3( 1.82,  2.58, -0.18), // Ascending toward upper-right heavens
        new THREE.Vector3( 3.28,  3.38, -0.12)  // Upper-right celestial crest tip
      ];

      const dragonCurve = new THREE.CatmullRomCurve3(dragonSpineWaypoints, false, 'catmullrom', 0.5);
      const segN = 150;
      const dPts = dragonCurve.getPoints(segN);
      const outerGoldFlank = [];
      const innerCrimsonFlank = [];
      const scaleScrollChords = [];

      for (let i = 0; i <= segN; i++) {
        const u = i / segN;
        const tan = dragonCurve.getTangent(u);
        const norm = new THREE.Vector3(-tan.y, tan.x, 0.12).normalize();
        // Broad sculptural body along the iconic C-arch (u = 0.45..0.85), graceful taper at tail & upper crest
        const bodyHalfW = Math.sin(Math.pow(u, 0.65) * Math.PI) * (0.44 + 0.16 * Math.sin(u * Math.PI * 2.2));
        const pOut = dPts[i].clone().addScaledVector(norm, bodyHalfW);
        const pIn = dPts[i].clone().addScaledVector(norm, -bodyHalfW);
        outerGoldFlank.push(pOut);
        innerCrimsonFlank.push(pIn);

        // Internal Chinese scroll/cloud scale ribs inside the closed dragon body
        if (i > 6 && i < segN - 4 && i % 5 === 0) {
          scaleScrollChords.push(pOut, dPts[i], dPts[i], pIn);
        }

        // Stippled gold-pearl constellation trail hugging just outside the C-arch (matching artwork dotted gold trails!)
        if (i > 12 && i < segN - 8 && i % 3 === 0) {
          const pearlTrailPt = dPts[i].clone().addScaledVector(norm, bodyHalfW + 0.24);
          pushDecoStar(pearlTrailPt, cl.center, GOLD_BRIGHT, 2.3, 0, 0.025, 1.2, 4);
        }
      }

      // 100% Closed Dragon Silhouette Loop (Outer Gold Contour + Inner Crimson-Gold Contour)
      g.add(makeClosedPolygonLoop([...outerGoldFlank, ...innerCrimsonFlank.slice().reverse()], GOLD_WARM, 0.82));
      g.add(makeLineSegments(scaleScrollChords, CINNABAR, 0.36));

      // 3 Parallel Weaving Golden Silk Cloud-Ribbons (`流金云气飘带`) with Living Photon Streamers!
      const silkRibbon1 = [
        new THREE.Vector3(-3.65, -1.55, 0.28),
        new THREE.Vector3(-2.15, -1.42, 0.32),
        new THREE.Vector3(-0.75, -0.82, 0.34),
        new THREE.Vector3( 0.88, -0.58, 0.28),
        new THREE.Vector3( 2.45,  0.12, 0.22),
        new THREE.Vector3( 3.65,  0.05, 0.16)
      ];
      const silkRibbon2 = [
        new THREE.Vector3(-2.78,  0.42, 0.32),
        new THREE.Vector3(-2.45,  1.68, 0.28),
        new THREE.Vector3(-1.45,  2.58, 0.22),
        new THREE.Vector3(-0.35,  3.18, 0.16)
      ];

      // Close each silk ribbon delicately as a thin double-edged golden sash (`LineLoop`)
      [silkRibbon1, silkRibbon2].forEach((ribPts, idx) => {
        const rc = new THREE.CatmullRomCurve3(ribPts);
        const rSamples = rc.getPoints(48);
        const topEdge = [];
        const botEdge = [];
        rSamples.forEach((pt, k) => {
          const u = k / 48;
          const w = Math.sin(u * Math.PI) * 0.065;
          topEdge.push(new THREE.Vector3(pt.x, pt.y + w, pt.z));
          botEdge.push(new THREE.Vector3(pt.x, pt.y - w, pt.z));
        });
        g.add(makeClosedPolygonLoop([...topEdge, ...botEdge.reverse()], GOLD_BRIGHT, 0.76));
        registerCurveStreamerTrack(rSamples.map(p => p.clone().add(cl.center)), false, GOLD_BRIGHT, 4 - idx, 0.18, 6.4);
      });

      // Register major crimson-gold photon streamers racing along Zhulong's C-Arched Spine!
      registerCurveStreamerTrack(dPts.map(p => p.clone().add(cl.center)), false, GOLD_BRIGHT, 8, 0.14, 7.2);

      // Dense Cinnabar, Lacquer-Red & Gold Volumetric Body Stars (880 stars sculpting the crimson dragon!)
      for (let i = 0; i < 880; i++) {
        const u = Math.random();
        const centerPt = dragonCurve.getPoint(u);
        const tan = dragonCurve.getTangent(u);
        const norm = new THREE.Vector3(-tan.y, tan.x, 0).normalize();
        const maxW = Math.sin(Math.pow(u, 0.65) * Math.PI) * 0.48;
        const latOffset = (Math.random() - 0.5) * 2.0 * maxW;
        const pt = centerPt.clone()
          .addScaledVector(norm, latOffset)
          .add(new THREE.Vector3(0, 0, (Math.random() - 0.5) * 0.26));

        const colChoice = i % 7 === 0 ? GOLD_BRIGHT : (i % 2 === 0 ? CINNABAR : CRIMSON_DEEP);
        pushDecoStar(pt, cl.center, colChoice, 1.55 + Math.random() * 2.25, 0, 0.065, 1.75, 4);
      }

      // Animate Solar Earring Rotation & Periodic "视为昼" Golden Flare Wave!
      let m4Clock = 0;
      kineticRig.push(dt => {
        m4Clock += dt;
        earringGroup.rotation.z -= dt * 0.68;
        zhulongOrbit.rotation.z += dt * 0.18;

        // Every ~4.5 seconds, emit a serene golden "视为昼 (Eyes Open = Daybreak)" corona wave!
        const pulsePhase = (m4Clock * 0.24) % 1.0;
        const waveScale = 0.28 + pulsePhase * 4.35;
        daybreakWave.scale.setScalar(waveScale);
        daybreakWave.material.opacity = Math.sin(pulsePhase * Math.PI) * (1.0 - pulsePhase) * 0.68;
      });
    })();

    // -------------------------------------------------------------------------
    // MYTHOS V: 外圆内方·四维超立方星门 (Real-Time 4D XW/ZW Rotating Tesseract!)
    // -------------------------------------------------------------------------
    (function buildMythosV() {
      const cl = CLUSTER_MAP.M5;
      const g = new THREE.Group();
      g.position.copy(cl.center);
      masterUniverse.add(g);
      clusterGroups.M5 = g;

      // 1. "外圆内方" Closed Circular Event-Horizon Astrolabe Frame + 4 Cardinal Fret Diamonds
      g.add(makeClosedCircleLoop(4.64, 128, cl.color, 0.42));
      g.add(makeClosedCircleLoop(4.30, 128, cl.accent, 0.26));
      g.add(makeDegreeTicks(4.30, 4.62, 32, cl.color, 0.36));
      registerCircleStreamerTrack(cl.center, 4.64, null, cl.accent, 5, 0.095, 5.8);

      [0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2].forEach(ang => {
        const cx = Math.cos(ang) * 4.47;
        const cy = Math.sin(ang) * 4.47;
        const d = 0.24;
        g.add(makeClosedPolygonLoop([
          new THREE.Vector3(cx - d, cy, 0), new THREE.Vector3(cx, cy + d, 0),
          new THREE.Vector3(cx + d, cy, 0), new THREE.Vector3(cx, cy - d, 0)
        ], cl.accent, 0.70));
      });

      // 2. TRUE 4D TESSERACT (16 Vertices in R^4, 32 Edges Continuously Rotating in XW & ZW!)
      const verts4D = [];
      for (let i = 0; i < 16; i++) {
        verts4D.push([
          (i & 1) ? 1 : -1,
          (i & 2) ? 1 : -1,
          (i & 4) ? 1 : -1,
          (i & 8) ? 1 : -1
        ]);
      }

      const edges4D = [];
      for (let i = 0; i < 16; i++) {
        for (let j = i + 1; j < 16; j++) {
          const diff = i ^ j;
          // Connect iff Hamming distance == 1 (32 exact hypercube edges!)
          if (diff === 1 || diff === 2 || diff === 4 || diff === 8) {
            edges4D.push([i, j]);
          }
        }
      }

      const tesseractGroup = new THREE.Group();
      tesseractGroup.rotation.set(0.34, -0.42, 0.08);
      g.add(tesseractGroup);

      const tessEdgePos = new Float32Array(edges4D.length * 2 * 3);
      const tessEdgeCol = new Float32Array(edges4D.length * 2 * 3);
      const tessGeo = new THREE.BufferGeometry();
      tessGeo.setAttribute('position', new THREE.BufferAttribute(tessEdgePos, 3));
      tessGeo.setAttribute('color', new THREE.BufferAttribute(tessEdgeCol, 3));

      const tessLines = new THREE.LineSegments(
        tessGeo,
        new THREE.LineBasicMaterial({
          vertexColors: true,
          transparent: true,
          opacity: 0.78,
          depthWrite: false,
          blending: THREE.AdditiveBlending
        })
      );
      tesseractGroup.add(tessLines);

      // 16 Dynamic 4D Vertex Star Nodes
      const vStarPos = new Float32Array(16 * 3);
      const vStarGeo = new THREE.BufferGeometry();
      vStarGeo.setAttribute('position', new THREE.BufferAttribute(vStarPos, 3));
      const vStarPoints = new THREE.Points(
        vStarGeo,
        new THREE.PointsMaterial({ color: cl.accent, size: 0.22, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending })
      );
      tesseractGroup.add(vStarPoints);

      const colGold = new THREE.Color(cl.color);
      const colEmerald = new THREE.Color(cl.accent);
      const projected3D = new Array(16).fill(0).map(() => new THREE.Vector3());

      function update4DTesseract(angleXW, angleZW) {
        const cosXW = Math.cos(angleXW), sinXW = Math.sin(angleXW);
        const cosZW = Math.cos(angleZW), sinZW = Math.sin(angleZW);
        const cam4D = 2.85; // 4D camera distance for dramatic inner/outer cube inversion

        for (let i = 0; i < 16; i++) {
          let [x, y, z, w] = verts4D[i];
          // Rotate in 4D XW plane
          const x1 = x * cosXW - w * sinXW;
          const w1 = x * sinXW + w * cosXW;
          // Rotate in 4D ZW plane
          const z2 = z * cosZW - w1 * sinZW;
          const w2 = z * sinZW + w1 * cosZW;

          const persp = 1.92 / (cam4D - w2);
          projected3D[i].set(x1 * persp * 2.05, y * persp * 2.05, z2 * persp * 1.65);

          vStarPos[i * 3] = projected3D[i].x;
          vStarPos[i * 3 + 1] = projected3D[i].y;
          vStarPos[i * 3 + 2] = projected3D[i].z;
        }
        vStarGeo.attributes.position.needsUpdate = true;

        edges4D.forEach(([a, b], idx) => {
          const pA = projected3D[a];
          const pB = projected3D[b];
          const base = idx * 6;
          tessEdgePos[base] = pA.x; tessEdgePos[base + 1] = pA.y; tessEdgePos[base + 2] = pA.z;
          tessEdgePos[base + 3] = pB.x; tessEdgePos[base + 4] = pB.y; tessEdgePos[base + 5] = pB.z;

          // Blend between champagne gold (outer W) and emerald cyan (inner W)
          const mixFactor = ((a & 8) !== (b & 8)) ? 0.5 : ((a & 8) ? 0.85 : 0.15);
          const c = colGold.clone().lerp(colEmerald, mixFactor);
          tessEdgeCol[base] = c.r; tessEdgeCol[base + 1] = c.g; tessEdgeCol[base + 2] = c.b;
          tessEdgeCol[base + 3] = c.r; tessEdgeCol[base + 4] = c.g; tessEdgeCol[base + 5] = c.b;
        });
        tessGeo.attributes.position.needsUpdate = true;
        tessGeo.attributes.color.needsUpdate = true;
      }

      update4DTesseract(0.25, 0.15);

      // 3. Central Pulsing "13th-Floor Liminal Singularity" Core
      const corePortal = new THREE.Group();
      const coreOct = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.OctahedronGeometry(0.46, 0)),
        new THREE.LineBasicMaterial({ color: cl.accent, transparent: true, opacity: 0.92 })
      );
      corePortal.add(coreOct, makeClosedCircleLoop(0.62, 48, cl.color, 0.58));
      g.add(corePortal);

      let wClock = 0.25;
      kineticRig.push(dt => {
        wClock += dt * 0.52;
        update4DTesseract(wClock, wClock * 0.68);
        corePortal.rotation.y -= dt * 0.85;
        corePortal.rotation.z += dt * 0.45;
      });

      for (let i = 0; i < 480; i++) {
        const a = Math.random() * Math.PI * 2;
        const r = i < 240 ? (0.65 + Math.random() * 2.15) : (3.85 + (Math.random() - 0.5) * 0.72);
        const pt = new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, (Math.random() - 0.5) * 1.25);
        pushDecoStar(pt, cl.center, i % 3 === 0 ? cl.accent : cl.color, 1.35 + Math.random() * 1.75, 0, 0.05, 1.2, 5);
      }
    })();

    // =========================================================================
    // 6. CENTRAL 3D TOTEM SYZYGY CRUX (`中央金石星枢柱`) & CLEAN ECLIPTIC ORBITS
    // =========================================================================
    const centralHubGroup = new THREE.Group();
    masterUniverse.add(centralHubGroup);

    centralHubGroup.add(makeClosedCircleLoop(2.35, 84, '#d8b56a', 0.30));
    centralHubGroup.add(makeClosedCircleLoop(1.68, 64, '#ffe6a3', 0.20));
    centralHubGroup.add(makeDegreeTicks(2.12, 2.34, 24, '#d8b56a', 0.34));

    // Sculpted 3D Intersecting Totem Pillar Crux (From User's Hand-Drawn Totem!)
    const totemCrux3D = new THREE.Group();
    const vPillarGeo = new THREE.BoxGeometry(0.32, 2.25, 0.32);
    const hBeamGeo = new THREE.BoxGeometry(1.85, 0.26, 0.26);
    const cruxMat = new THREE.LineBasicMaterial({ color: '#ffe6a3', transparent: true, opacity: 0.68 });
    const vPillarWire = new THREE.LineSegments(new THREE.EdgesGeometry(vPillarGeo), cruxMat);
    const hBeamWire = new THREE.LineSegments(new THREE.EdgesGeometry(hBeamGeo), cruxMat);
    hBeamWire.position.y = 0.24;
    totemCrux3D.add(vPillarWire, hBeamWire);
    totemCrux3D.rotation.set(0.32, -0.58, 0.12);
    centralHubGroup.add(totemCrux3D);

    kineticRig.push(dt => {
      totemCrux3D.rotation.y += dt * 0.36;
    });
    pushDecoStar(new THREE.Vector3(0, 0.24, 0), new THREE.Vector3(0, 0, 0), '#fff6dc', 13.5, 1.25, 0, 1, 0);

    // Outer Closed Elliptical Ecliptic Rings + Living Photon Streamers Orbiting the Entire Cosmos
    const mainOrbitPts = [];
    const innerOrbitPts = [];
    for (let i = 0; i < 180; i++) {
      const a = (i / 180) * Math.PI * 2;
      mainOrbitPts.push(new THREE.Vector3(Math.cos(a) * RING_RADIUS, Math.sin(a) * RING_RADIUS * 0.92, -0.5));
      innerOrbitPts.push(new THREE.Vector3(Math.cos(a) * (RING_RADIUS * 0.58), Math.sin(a) * (RING_RADIUS * 0.58) * 0.92, -0.6));
    }
    masterUniverse.add(makeClosedPolygonLoop(mainOrbitPts, '#d8b56a', 0.16));
    masterUniverse.add(makeClosedPolygonLoop(innerOrbitPts, '#d8b56a', 0.10));

    registerCurveStreamerTrack(mainOrbitPts, true, '#ffe6a3', 10, 0.035, 6.2);
    registerCurveStreamerTrack(innerOrbitPts, true, '#d8b56a', 6, -0.05, 5.2);


  masterUniverse.name = 'SIDERA-v3-kinetic';
  masterUniverse.scale.setScalar(SCALE);
  const starUniforms = {
    uMotionTime: { value: 0 }, uRawTime: { value: 0 },
    uPixelRatio: { value: Math.min(options.pixelRatio || 1, 2) },
    uPointerWorld: { value: new THREE.Vector3(999, 999, 0) },
    uPointerActive: { value: 0 }, uFocus: { value: 0 },
  };
  const starMaterial = new THREE.ShaderMaterial({
    uniforms: starUniforms, vertexShader: "\n      attribute float aSize;\n      attribute vec3 aColor;\n      attribute float aSpike;\n      attribute float aHighlight;\n      attribute float aPhase;\n      attribute float aCluster;\n      uniform float uFocus;\n      attribute vec3 aKinetic; // x: motionAmp, y: motionFreq, z: clusterMode (0=static/story, 1=M1_robe, 2=M2_orrery, 3=M3_swirl, 4=M4_zhulong, 5=M5_horizon)\n\n      uniform float uMotionTime;\n      uniform float uRawTime;\n      uniform float uPixelRatio;\n      uniform vec3 uPointerWorld;\n      uniform float uPointerActive;\n\n      varying vec3 vColor;\n      varying float vSpike;\n      varying float vHighlight;\n\n      void main() {\n        vec3 pos = position;\n        float amp = aKinetic.x;\n        float freq = aKinetic.y;\n        float mode = aKinetic.z;\n\n        // Organic kinetic displacement controlled by Tempo (uMotionTime)\n        if (amp > 0.001) {\n          if (mode > 3.5 && mode < 4.5) {\n            // M4 Zhulong: Sinuous crimson-gold dragon qi & rising flame-mane undulation\n            pos.x += sin(uMotionTime * freq + pos.y * 1.45 + aPhase) * amp;\n            pos.y += cos(uMotionTime * (freq * 0.85) + pos.x * 1.15 + aPhase) * amp * 0.9;\n            pos.z += sin(uMotionTime * 1.3 + aPhase) * amp * 1.2;\n          } else if (mode > 0.5 && mode < 1.5) {\n            // M1 Deity Robe: Cascading starlight wave ripples\n            pos.x += sin(uMotionTime * freq - pos.y * 2.2 + aPhase) * amp;\n            pos.z += cos(uMotionTime * freq - pos.y * 2.0 + aPhase) * amp;\n          } else {\n            // Harmonic 3D orbital drift\n            pos.x += cos(uMotionTime * freq + aPhase) * amp;\n            pos.y += sin(uMotionTime * freq + aPhase * 1.3) * amp;\n            pos.z += sin(uMotionTime * (freq * 0.7) + aPhase) * amp * 0.8;\n          }\n        }\n\n        // Subtle Mouse-Cursor Gravitational Star-Tide Ripple\n        float cursorBoost = 0.0;\n        if (uPointerActive > 0.01 && aHighlight > 0.05) {\n          float dPtr = distance(pos.xy, uPointerWorld.xy);\n          float ripple = exp(-dPtr * dPtr * 0.14) * uPointerActive;\n          pos.z += ripple * 0.68;\n          cursorBoost = ripple * 0.55;\n        }\n\n        vColor = aColor;\n        vSpike = aSpike;\n\n        // Scintillation & flowing wave brightness\n        float twinkle = 0.88 + 0.12 * sin(uRawTime * 2.6 + aPhase * 3.0);\n        if (mode > 3.5 && mode < 4.5) {\n          // Zhulong periodic solar-breath luminance wave\n          twinkle *= 0.92 + 0.22 * sin(uMotionTime * 1.8 - pos.x * 0.6 + aPhase);\n        } else if (mode > 0.5 && mode < 1.5) {\n          // Downward cascading luminance ripple along M1 robe\n          twinkle *= 0.90 + 0.20 * sin(uMotionTime * 2.4 + pos.y * 1.8);\n        }\n\n        vHighlight = (aHighlight + cursorBoost) * (uFocus < 0.5 || aCluster < 0.5 || abs(aCluster - uFocus) < 0.5 ? 1.0 : 0.26);\n\n        vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);\n        float dist = max(-mvPos.z, 45.0);\n        float boost = mix(0.65, 1.0, clamp(vHighlight, 0.0, 1.0));\n        if (vHighlight > 1.05) boost = 1.0 + (vHighlight - 1.0) * 0.44;\n\n        float pSize = aSize * boost * twinkle * uPixelRatio * (350.0 / dist);\n        gl_PointSize = clamp(pSize, 1.55 * uPixelRatio, 70.0 * uPixelRatio);\n        gl_Position = projectionMatrix * mvPos;\n      }\n    ", fragmentShader: "\n      varying vec3 vColor;\n      varying float vSpike;\n      varying float vHighlight;\n\n      void main() {\n        vec2 uv = gl_PointCoord - vec2(0.5);\n        float d = length(uv) * 2.0;\n        if (d > 1.0) discard;\n\n        // 1. Razor-sharp white-hot pinpoint core\n        float core = exp(-d * d * 36.0);\n        // 2. Smooth spectral halo\n        float halo = exp(-d * d * 6.4) * 0.72;\n        // 3. Crisp 4-point diffraction spikes on major stars & living photons\n        float spikes = 0.0;\n        if (vSpike > 0.04) {\n          float sx = exp(-abs(uv.x) * 44.0) * exp(-abs(uv.y) * 5.0);\n          float sy = exp(-abs(uv.y) * 44.0) * exp(-abs(uv.x) * 5.0);\n          spikes = (sx + sy) * vSpike * 0.98;\n        }\n\n        float lum = core * 1.48 + halo + spikes;\n        float alphaMod = clamp(vHighlight, 0.0, 2.3);\n        if (alphaMod < 0.02) discard;\n        float alpha = clamp(lum * alphaMod, 0.0, 1.0);\n        if (alpha < 0.012) discard;\n\n        float whiteMix = clamp(core * 1.32 + spikes * 0.58, 0.0, 1.0);\n        vec3 rgb = mix(vColor, vec3(1.0, 0.99, 0.95), whiteMix);\n        gl_FragColor = vec4(rgb * min(alphaMod, 1.65), alpha);\n      }\n    ",
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const artPoints = (items, isPhoton = false) => {
    const count = items.length, position = new Float32Array(count * 3), colors = new Float32Array(count * 3);
    const size = new Float32Array(count), spike = new Float32Array(count), high = new Float32Array(count);
    const phase = new Float32Array(count), kinetic = new Float32Array(count * 3), cluster = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      const item = items[i], j = i * 3;
      position[j] = item.pos?.x || 0; position[j + 1] = item.pos?.y || 0; position[j + 2] = item.pos?.z || 0;
      colors[j] = item.color.r; colors[j + 1] = item.color.g; colors[j + 2] = item.color.b;
      size[i] = item.size; spike[i] = item.spike || 0; high[i] = item.highlight ?? (item.spike > 0 ? 1.05 : 0.68);
      phase[i] = item.phase || 0; kinetic[j] = item.amp || 0; kinetic[j + 1] = item.freq || 0; kinetic[j + 2] = item.mode || 0;
      cluster[i] = Number(item.clusterId?.slice(1)) || 0;
    }
    const geometry = new THREE.BufferGeometry();
    for (const [name, arr, width] of [['position', position, 3], ['aColor', colors, 3], ['aSize', size, 1],
      ['aSpike', spike, 1], ['aHighlight', high, 1], ['aPhase', phase, 1], ['aKinetic', kinetic, 3], ['aCluster', cluster, 1]]) {
      geometry.setAttribute(name, new THREE.BufferAttribute(arr, width));
    }
    const points = new THREE.Points(geometry, starMaterial);
    points.frustumCulled = false;
    points.userData.softwareStride = options.software ? (isPhoton ? 3 : 3) : 1;
    masterUniverse.add(points);
    return { points, geometry, baseHigh: Float32Array.from(high) };
  };
  const nebula = artPoints(decorativeStars);
  const TRAIL_STEPS = options.software ? 2 : 3;
  const movingItems = [];
  constellationTracks.forEach((track, i) => {
    for (let sub = 0; sub < TRAIL_STEPS; sub++) {
      const fade = sub === 0 ? 1 : sub === 1 ? 0.62 : 0.34;
      movingItems.push({ color: track.color, size: track.size * fade, spike: sub === 0 ? 0.55 : 0,
        highlight: 1.35 * fade, phase: i * 0.7 });
    }
  });
  const photons = artPoints(movingItems, true);
  const clusterMaterials = [];
  for (const [refId, obj] of Object.entries(clusterGroups)) {
    obj.traverse(child => {
      if (!child.material) return;
      for (const material of Array.isArray(child.material) ? child.material : [child.material]) {
        if (!material.userData.v3Recorded) {
          material.userData.v3Recorded = true;
          clusterMaterials.push({ material, refId, opacity: material.opacity });
        }
      }
    });
  }
  let fade = 0, focused = 'all', speed = 1, motionTime = 0, lastTime = null, pointerTarget = 0;
  const tmp = new THREE.Vector3();
  function setFade(value) {
    fade = Math.max(0, Math.min(1, Number(value) || 0));
    masterUniverse.visible = fade > 0.004;
    for (const item of clusterMaterials) {
      // The zero-opacity solar flare is controlled by its own animation.
      if (item.opacity > 0) item.material.opacity = item.opacity * fade * (focused === 'all' || focused === item.refId ? 1 : 0.26);
    }
    for (const p of [nebula, photons]) {
      const attr = p.geometry.getAttribute('aHighlight');
      for (let i = 0; i < attr.count; i++) attr.array[i] = p.baseHigh[i] * fade;
      attr.needsUpdate = true;
    }
  }
  function setFocus(id) {
    focused = byId.get(id)?.referenceId || 'all';
    starUniforms.uFocus.value = Number(focused.slice(1)) || 0;
    setFade(fade);
  }
  function setPointer(worldPoint, active) {
    pointerTarget = active ? 1 : 0;
    if (worldPoint && active) starUniforms.uPointerWorld.value.copy(masterUniverse.worldToLocal(worldPoint.clone()));
  }
  function animate(t) {
    const delta = lastTime === null ? 0 : Math.min(0.05, Math.max(0, t - lastTime));
    lastTime = t;
    const dt = delta * speed;
    motionTime += dt;
    starUniforms.uMotionTime.value = motionTime;
    starUniforms.uRawTime.value = motionTime;
    starUniforms.uPointerActive.value += (pointerTarget - starUniforms.uPointerActive.value) * 0.1;
    if (dt > 0.00001) for (const update of kineticRig) update(dt);
    Object.values(clusterGroups).forEach((grp, idx) => {
      grp.rotation.y = Math.sin(motionTime * 0.42 + idx * 1.25) * 0.12;
      grp.rotation.x = Math.cos(motionTime * 0.31 + idx * 0.9) * 0.05;
    });
    const attr = photons.geometry.getAttribute('position');
    constellationTracks.forEach((track, index) => {
      for (let sub = 0; sub < TRAIL_STEPS; sub++) {
        let u = (motionTime * track.speed + track.offset - sub * 0.014) % 1;
        if (u < 0) u += 1;
        track.curve.getPointAt(u, tmp);
        attr.setXYZ(index * TRAIL_STEPS + sub, tmp.x, tmp.y, tmp.z);
      }
    });
    attr.needsUpdate = true;
  }
  function setSpeed(value) { speed = Math.max(0, Math.min(1, Number(value) || 0)); }
  setFade(0);
  return { group: masterUniverse, setFade, setFocus, setPointer, setSpeed, animate,
    get motionTime() { return motionTime; }, photonCount: constellationTracks.length * TRAIL_STEPS };
}
