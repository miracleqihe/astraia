import * as THREECore from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import '@fontsource/cormorant-garamond/latin-600.css';
import '@fontsource/jetbrains-mono/latin-400.css';
import '@fontsource/noto-serif-sc/400.css';
import '@fontsource/noto-serif-sc/600.css';
import '../styles.css';
import './utilities.css';
import './overrides.css';
import { createSyzygyRenderer } from './renderer';
import { createFullAtlas } from './fullAtlas';
import { genreContract, genreLabels } from './narrativeMetadata';
import { announceViewReady } from '../viewRouter';
import readingPaths from './reading-paths.json';
import { renderBridgeCard } from './bridgeCard';

const THREE = { ...THREECore, OrbitControls };
const root = import.meta.env.BASE_URL;
const initialParams = new URL(window.location.href).searchParams;
const tierOrder = ['S','A','B','C','F'];
const initialTiers = initialParams.has('tiers')
  ? new Set(tierOrder.filter(tier=>initialParams.get('tiers').split(',').includes(tier)))
  : new Set(tierOrder.filter(tier=>tier !== 'F' || initialParams.get('fiction') === '1'));
const initialShowF = initialTiers.has('F');
const loadJSON = async (url) => { const response = await fetch(url, {cache:'no-cache'}); if (!response.ok) throw new Error(`资料读取失败 (${response.status})`); return response.json(); };
const [book, bridgeDataset, initialRenderer] = await Promise.all([
  loadJSON(`${root}knowledge/index.json`), loadJSON(`${root}syzygy/boot.json`), createSyzygyRenderer(),
]);
if (book.data_sha256 !== bridgeDataset.handbook_sha256) throw new Error('星图和原书索引版本不一致，请刷新。');
if (!Array.isArray(book.entries) || !Array.isArray(bridgeDataset.bridges)) throw new Error('星图资料格式不正确。');

    // ============================================================================
    // 1. CORE DATASETS: 5 HETEROGENEOUS VOLUMES + 5 SPIRITUAL MOTIF CLUSTERS
    //    + 12 ACADEMICALLY GROUNDED SYZYGY BRIDGES & 5 CURATED TRAILS
    // ============================================================================
    const volumeStyles = [
      { en: 'SATURNIAN SHIELD', color: '#e8a856', altColor: '#d97736', center: [0,-148,20], morphDesc: '多轨同心护盾星环' },
      { en: 'FIVE-ARM SPIRAL', color: '#64b5f6', altColor: '#38bdf8', center: [206,-48,-16], morphDesc: '五旋臂星系' },
      { en: 'GEODESIC CRYSTAL', color: '#52d1a2', altColor: '#2dd4bf', center: [136,142,18], morphDesc: '测地晶格与双轴浑天环' },
      { en: 'TORUS MANIFOLD', color: '#9d8df7', altColor: '#c084fc', center: [-136,142,-14], morphDesc: '环面星系' },
      { en: 'ROSE WORMHOLE PORTAL', color: '#f3d08a', altColor: '#f4978e', center: [-206,-48,18], morphDesc: '玫瑰星冠与星门', isWormhole: true },
    ];
    const volumeNames = [...new Set(book.subjects.map(subject => subject.volume))];
    const VOLUMES = volumeNames.map((name, i) => {
      const spec = volumeStyles[i], disciplines = book.subjects.filter(subject => subject.volume === name).map(subject => ({
        id: subject.id.toLowerCase(), name: subject.title, count: subject.count, code: subject.id,
        isSupplement: bridgeDataset.bridges.some(b => b.physis.subject === subject.id),
      }));
      return { ...spec, center: new THREE.Vector3(...spec.center), id: `vol${i+1}`, num: String(i+1).padStart(2,'0'), name,
        totalNodes: disciplines.reduce((sum, item) => sum + item.count, 0), disciplines };
    });

    // 5 Spiritual Consciousness Constellation Clusters for SIDERA (玄象星络)
    const SIDERA_CLUSTERS = [
      { id: 'sid_myth', name: '创世灾变与天体神话星群', code: 'MYTHOS · I', color: '#e2d4f8', center: new THREE.Vector3(0, 152, 28) },
      { id: 'sid_hag', name: '暗夜梦魇与幻影感知星群', code: 'MYTHOS · II', color: '#a5b4fc', center: new THREE.Vector3(-188, 36, 36) },
      { id: 'sid_witch', name: '妖术恐慌与契约附体星群', code: 'MYTHOS · III', color: '#c4b5fd', center: new THREE.Vector3(-116, -148, -22) },
      { id: 'sid_crypt', name: '山海精怪与器物骚灵星群', code: 'MYTHOS · IV', color: '#93c5fd', center: new THREE.Vector3(122, -146, 24) },
      { id: 'sid_liminal', name: '现代阈限与规则展演星群', code: 'MYTHOS · V', color: '#cbd5e1', center: new THREE.Vector3(188, 38, -28) }
    ];

    // Relation Type Color & Label Dictionary
    const RELATION_META = {
      EMPIRICAL_EXPLAINS: {
        label: '机理解析 · EMPIRICAL_EXPLAINS',
        colorA: '#5ce1e6',
        colorB: '#e8c57b'
      },
      MYTHIC_PROJECTION: {
        label: '神话赋魅 · MYTHIC_PROJECTION',
        colorA: '#f5b95f',
        colorB: '#b692f6'
      },
      SOCIAL_MIRROR: {
        label: '社会对读 · SOCIAL_MIRROR',
        colorA: '#f4978e',
        colorB: '#f3d08a'
      },
      LIMINAL_SPAWNS: {
        label: '数字叙事 · LIMINAL_SPAWNS',
        colorA: '#52d1a2',
        colorB: '#e8c57b'
      },
      THEMATIC: {
        label: '专题对读 · THEMATIC',
        colorA: '#8ec8ca',
        colorB: '#d6b678'
      }
    };

    // Epistemic Confidence Status Dictionary
    const CONFIDENCE_META = {
      CONFIRMED: {
        badge: '● 个案关联已证实',
        cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/45'
      },
      UNVERIFIED: {
        badge: '◐ 个案关联待核实',
        cls: 'bg-amber-500/15 text-amber-300 border-amber-400/45'
      },
      DEBUNKED: {
        badge: '✕ 个案关联已驳回',
        cls: 'bg-rose-500/15 text-rose-300 border-rose-400/45'
      },
      CONTEXT: {
        badge: '◇ 专题对读',
        cls: 'syzygy-status-context'
      }
    };

    // Curated cross-dimensional reading bridges.
    const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);
    const textExcerpt = body => String(body ?? '').replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/⟦anchor:[^⟧]+⟧/g, '')
      .replace(/[#*_`|>]/g, '').replace(/\s+/g, ' ').trim().slice(0, 240);
    const typeLabels = { story:'故事梗概', legend:'都市传说', report:'事件报道', history:'历史个案', research:'研究提要', archive:'档案', edition:'古籍正文' };
    const codeLabels = { atu_types:'ATU', thompson_motifs:'汤普森', berezkin_codes:'别列兹金', ocm_codes:'OCM' };
    const SYZYGY_BRIDGES = bridgeDataset.bridges.map(b => {
      const node = b.mythos, entry = b.physis, sp = node.spatial, hasCoordinates = Number.isFinite(sp?.lat) && Number.isFinite(sp?.lng);
      const codes = Object.entries(codeLabels).flatMap(([key, label]) => (node.standards?.[key] ?? []).map(code => `${label} ${code}`));
      const linkStatus = b.edge?.type === 'EXPLAINED_BY' ? b.edge.status : null;
      const confidence = linkStatus === 'confirmed' ? 'CONFIRMED' : linkStatus === 'refuted' ? 'DEBUNKED' : linkStatus ? 'UNVERIFIED' : 'CONTEXT';
      return { ...b, confidence, hasCoordinates,
        umbraGeo:{lat:hasCoordinates ? sp.lat : null, lon:hasCoordinates ? sp.lng : null, place:sp?.location_name || '未记录地点'},
        mythos:{...node, genre_contract:genreContract(node), genre:typeLabels[node.reading?.kind] ?? '资料', taxonomies:codes,
          narrative:(node.reading?.paragraphs ?? []).join('\n')},
        layers: b.related ? [b.related.title, ...(b.related.reading?.paragraphs?.slice(0,1) ?? [])] : ['主题对读：从相关知识条目继续探索'],
        physis:{...entry, code:entry.id, volLabel:`${entry.volume} · ${book.subjects.find(s => s.id === entry.subject)?.title ?? entry.subject}`,
          sliceQuote:textExcerpt(entry.body)} };
    });

    let _rngState = 20260324;
    function sRand() {
      _rngState = (_rngState * 1664525 + 1013904223) % 4294967296;
      return _rngState / 4294967296;
    }
    function sGauss() {
      let u = 0, v = 0;
      while (u === 0) u = sRand();
      while (v === 0) v = sRand();
      return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    }

    const EARTH_RADIUS = 162;
    function latLonToVec3(lat, lon, r = EARTH_RADIUS) {
      const phi = (90 - lat) * (Math.PI / 180);
      const theta = (lon + 180) * (Math.PI / 180);
      return new THREE.Vector3(
        -r * Math.sin(phi) * Math.cos(theta),
         r * Math.cos(phi),
         r * Math.sin(phi) * Math.sin(theta)
      );
    }

    // Simplified Continental Landmass Ellipses so 5,300+ particles sculpt a glittering Earth in UMBRA mode!
    const CONTINENT_PATCHES = [
      { lat: 35, lon: 105, dLat: 18, dLon: 26 },  // East Asia
      { lat: 24, lon: 79,  dLat: 12, dLon: 12 },  // South Asia
      { lat: 55, lon: 85,  dLat: 12, dLon: 42 },  // Eurasia North
      { lat: 49, lon: 14,  dLat: 11, dLon: 18 },  // Europe
      { lat: 26, lon: 42,  dLat: 11, dLon: 14 },  // Middle East
      { lat: 14, lon: 18,  dLat: 16, dLon: 22 },  // North/West Africa
      { lat: -12, lon: 24, dLat: 16, dLon: 11 },  // Sub-Saharan Africa
      { lat: 42, lon: -98, dLat: 16, dLon: 24 },  // North America
      { lat: 19, lon: -99, dLat: 8,  dLon: 10 },  // Mesoamerica
      { lat: -14, lon: -60, dLat: 22, dLon: 13 }, // South America
      { lat: -25, lon: 134, dLat: 11, dLon: 16 }, // Australia
      { lat: 20, lon: -157, dLat: 6,  dLon: 12 }  // Polynesia
    ];

    function sampleUmbraContinentPoint() {
      if (sRand() < 0.82) {
        const patch = CONTINENT_PATCHES[Math.floor(sRand() * CONTINENT_PATCHES.length)];
        const lat = THREE.MathUtils.clamp(patch.lat + sGauss() * patch.dLat * 0.58, -78, 80);
        const lon = patch.lon + sGauss() * patch.dLon * 0.58;
        return latLonToVec3(lat, lon, EARTH_RADIUS + (sRand() - 0.5) * 2.2);
      }
      // Subtle high-altitude umbral ionosphere dust
      const lat = (sRand() - 0.5) * 155;
      const lon = (sRand() - 0.5) * 360;
      return latLonToVec3(lat, lon, EARTH_RADIUS + 8 + sRand() * 18);
    }

    // Golden Icosahedron Geometry for Vol 3 (造物卷 Geodesic Crystal Lattice)
    const PHI = (1 + Math.sqrt(5)) / 2;
    const ICO_VERTS = [
      [-1, PHI, 0], [1, PHI, 0], [-1, -PHI, 0], [1, -PHI, 0],
      [0, -1, PHI], [0, 1, PHI], [0, -1, -PHI], [0, 1, -PHI],
      [PHI, 0, -1], [PHI, 0, 1], [-PHI, 0, -1], [-PHI, 0, 1]
    ].map(v => new THREE.Vector3(v[0], v[1], v[2]).normalize());

    const ICO_EDGES = [];
    for (let i = 0; i < ICO_VERTS.length; i++) {
      for (let j = i + 1; j < ICO_VERTS.length; j++) {
        if (ICO_VERTS[i].distanceTo(ICO_VERTS[j]) < 1.15) ICO_EDGES.push([ICO_VERTS[i], ICO_VERTS[j]]);
      }
    }

    // Heterogeneous 3D Local Galaxy Position Generator for OMNIA's 5 Volumes
    function sampleOmniaGalaxyLocal(vIdx, dIdx, sIdx, dCount, isHub) {
      const p = new THREE.Vector3();

      if (vIdx === 0) {
        // 01 生存卷: Saturnian multi-ring concentric protective astrolabe shield + pulsar core
        const rings = [24, 42, 60, 78];
        if (isHub) {
          const r = rings[dIdx % rings.length];
          const ang = dIdx * 2.1 + 0.5;
          p.set(Math.cos(ang) * r, 0, Math.sin(ang) * r);
        } else if (sRand() < 0.24) {
          const cr = Math.pow(sRand(), 0.65) * 15;
          const th = sRand() * Math.PI * 2;
          const ph = Math.acos(2 * sRand() - 1);
          p.set(cr * Math.sin(ph) * Math.cos(th), cr * Math.cos(ph) * 0.72, cr * Math.sin(ph) * Math.sin(th));
          return p;
        } else {
          const rBase = rings[(dIdx + Math.floor(sRand() * 3)) % rings.length];
          const r = rBase + sGauss() * 2.8;
          const th = (sIdx / dCount) * Math.PI * 2 + sGauss() * 0.16;
          p.set(Math.cos(th) * r, sGauss() * 1.9, Math.sin(th) * r);
        }
        p.applyEuler(new THREE.Euler(0.45, 0.14, -0.22));
        return p;
      }

      if (vIdx === 1) {
        // 02 世界卷: Grand 5-arm logarithmic spiral galaxy
        const armBase = (dIdx / 5) * Math.PI * 2;
        if (isHub) {
          const r = 44;
          const ang = armBase + 2.35 * Math.log(1 + r / 15.5);
          p.set(Math.cos(ang) * r, 0, Math.sin(ang) * r);
        } else if (sRand() < 0.14) {
          p.set(sGauss() * 12, sGauss() * 5, sGauss() * 8);
        } else {
          const t = Math.pow(sRand(), 0.76);
          const r = 9 + t * 88;
          const swirl = 2.42 * Math.log(1 + r / 15.2);
          const ang = armBase + swirl + sGauss() * (0.13 + 0.15 * t);
          const y = sGauss() * (5.5 * Math.exp(-r / 52) + 1.6);
          p.set(Math.cos(ang) * r, y, Math.sin(ang) * r);
        }
        p.applyEuler(new THREE.Euler(0.50, -0.18, 0.26));
        return p;
      }

      if (vIdx === 2) {
        // 03 造物卷: Geodesic icosahedral crystal lattice star cluster + gimbal shell
        const R = 64;
        if (isHub) {
          p.copy(ICO_VERTS[(dIdx * 4) % ICO_VERTS.length]).multiplyScalar(R * 0.76);
          return p;
        }
        const roll = sRand();
        if (roll < 0.46) {
          const v = ICO_VERTS[Math.floor(sRand() * ICO_VERTS.length)];
          const layer = sRand() < 0.35 ? 0.45 : 0.85;
          p.copy(v).multiplyScalar(R * layer).add(new THREE.Vector3(sGauss() * 6.0, sGauss() * 6.0, sGauss() * 6.0));
        } else {
          const edge = ICO_EDGES[Math.floor(sRand() * ICO_EDGES.length)];
          p.lerpVectors(edge[0], edge[1], sRand()).multiplyScalar(R * 0.84);
          p.add(new THREE.Vector3(sGauss() * 3.4, sGauss() * 3.4, sGauss() * 3.4));
        }
        return p;
      }

      if (vIdx === 3) {
        // 04 数与人卷: 3D (2,3) torus-knot harmonic manifold ribbon
        const R = 46, rTube = 20;
        const u = isHub
          ? (dIdx / 4) * Math.PI * 2 + 0.35
          : ((dIdx + sIdx / dCount) / 4) * Math.PI * 2 + sGauss() * 0.2;
        const cx = (R + rTube * Math.cos(3 * u)) * Math.cos(2 * u);
        const cy = (R + rTube * Math.cos(3 * u)) * Math.sin(2 * u);
        const cz = rTube * Math.sin(3 * u) * 1.25;
        const spread = isHub ? 0 : 6.4;
        p.set(cx + sGauss() * spread, cy + sGauss() * spread, cz + sGauss() * spread);
        p.applyEuler(new THREE.Euler(0.36, -0.30, 0.18));
        return p;
      }

      // 05 意义卷: 6-petal sacred rose corona nebula (Lagrange Wormhole Portal)
      const petalIdx = (sIdx + dIdx * 2) % 6;
      const baseAng = (petalIdx / 6) * Math.PI * 2;
      if (isHub) {
        const r = 48;
        p.set(Math.cos(baseAng) * r, 0, Math.sin(baseAng) * r);
      } else {
        const ang = baseAng + sGauss() * 0.22;
        const env = 0.28 + 0.72 * Math.pow(Math.abs(Math.cos(3 * ang)), 0.75);
        const frac = Math.pow(sRand(), 0.64);
        const r = (9 + frac * 76) * env + sGauss() * 3.2;
        const yPlume = Math.sin(frac * Math.PI) * 11 + sGauss() * 3.8;
        p.set(Math.cos(ang) * r, yPlume, Math.sin(ang) * r);
      }
      p.applyEuler(new THREE.Euler(0.45, 0.22, 0.24));
      return p;
    }

    // Non-Euclidean Consciousness Constellation Generator for SIDERA
    function sampleSideraPoint(cIdx, idxInCluster, isHub) {
      const cl = SIDERA_CLUSTERS[cIdx % SIDERA_CLUSTERS.length];
      if (isHub) return cl.center.clone();
      // Non-Euclidean braided hyperbolic / spiral arms around motif cluster center
      const branch = idxInCluster % 3;
      const t = Math.pow(sRand(), 0.72);
      const r = 8 + t * 76;
      const theta = (branch / 3) * Math.PI * 2 + t * 3.6 + sGauss() * 0.22;
      const zWarp = Math.sin(theta * 2.0) * (14 * t) + sGauss() * 7.5;
      return new THREE.Vector3(
        cl.center.x + Math.cos(theta) * r,
        cl.center.y + Math.sin(theta) * r * 0.78,
        cl.center.z + zWarp
      );
    }

    // ============================================================================
    // 3. GENERATE 2,266 PRIMARY STARS + 68 SUPPLEMENT STARS + 3,000 MICRO-DUST
    // ============================================================================
    const PRIMARY_NODES = [];
    const DISC_HUB_MAP = new Map(); // discId -> hub star node

    let starIndexCounter = 0;
    VOLUMES.forEach((vol, vIdx) => {
      const secStart = (vIdx / 5) * Math.PI * 2 - Math.PI / 2;
      const secSpan = (Math.PI * 2) / 5 - 0.1;
      let angCursor = secStart + 0.05;
      const volSum = vol.disciplines.reduce((a, d) => a + d.count, 0);

      vol.disciplines.forEach((disc, dIdx) => {
        const dSpan = secSpan * (disc.count / volSum);
        const actualEntries = book.entries.filter(entry => entry.subject.toLowerCase() === disc.id);
        if (actualEntries.length !== disc.count) throw new Error(`学科条目数量不匹配：${disc.name}`);
        for (let s = 0; s < disc.count; s++) {
          const isHub = s === 0;
          const entry = actualEntries[s];
          const posOmnia3D = sampleOmniaGalaxyLocal(vIdx, dIdx, s, disc.count, isHub).add(vol.center);

          // 2D Astrolabe Planisphere Coordinate
          const r2D = isHub ? 142 : 90 + Math.pow((s + sRand()) / disc.count, 0.7) * 168;
          const th2D = isHub ? angCursor + dSpan * 0.5 : angCursor + sRand() * dSpan;
          const posOmnia2D = new THREE.Vector3(Math.cos(th2D) * r2D, Math.sin(th2D) * r2D * 0.92, 0);

          // UMBRA 3D Earth Coordinate
          const posUmbra3D = sampleUmbraContinentPoint();

          // SIDERA Non-Euclidean Motif Coordinate
          const posSidera3D = sampleSideraPoint((vIdx + dIdx) % 5, s, isHub && dIdx === 0);

          const colOmnia = new THREE.Color(s % 3 === 0 ? vol.altColor : vol.color);
          if (isHub) colOmnia.lerp(new THREE.Color('#ffffff'), 0.32);

          const colUmbra = new THREE.Color(s % 4 === 0 ? '#64b5f6' : '#d6b678').lerp(new THREE.Color('#475569'), 0.35);
          const colSidera = new THREE.Color(SIDERA_CLUSTERS[(vIdx + dIdx) % 5].color);

          // Only explicit crosswalks are linked; other stars keep their real identity.
          const matchedBridges = SYZYGY_BRIDGES.filter(b => b.physis.code === entry.id);

          const node = {
            index: starIndexCounter,
            volId: vol.id,
            volName: vol.name,
            volColor: vol.color,
            discId: disc.id,
            discName: disc.name,
            isSupplement: !!disc.isSupplement,
            isHub,
            code: entry.id,
            title: entry.title,
            page: entry.page,
            bridgeIds: matchedBridges.map(bridge => bridge.id),
            posOmnia3D,
            posOmnia2D,
            posUmbra3D,
            posSidera3D,
            curPos: posOmnia3D.clone(),
            colOmnia,
            colUmbra,
            colSidera,
            curCol: colOmnia.clone(),
            size: isHub || matchedBridges.length ? 21.0 : (s < 4 ? 9.5 : 4.2 + Math.pow(sRand(), 2.2) * 4.2),
            spike: isHub || matchedBridges.length ? 1.0 : (s < 3 ? 0.38 : 0.0),
            phase: sRand() * Math.PI * 2
          };

          PRIMARY_NODES.push(node);
          if (isHub) DISC_HUB_MAP.set(disc.id, node);
          starIndexCounter++;
        }
        angCursor += dSpan;
      });
    });

    // Attach coordinates in all three dimensions, distributing each cluster independently.
    SYZYGY_BRIDGES.forEach((bridge, bIdx) => {
      const targetHub = PRIMARY_NODES.find(node => node.code === bridge.physis.code);
      if (!targetHub) throw new Error(`找不到关联知识条目：${bridge.physis.code}`);
      bridge.materialNode = targetHub;

      // Upper Spiritual Halo Ring position in OMNIA when Syzygy Mode is ON
      const ringR = 238;
      const ang = -Math.PI / 2 + bIdx / SYZYGY_BRIDGES.length * Math.PI * 2;
      bridge.posOmniaSyzygy = new THREE.Vector3(
        Math.cos(ang) * ringR,
        Math.sin(ang) * ringR * 0.78 + 18,
        96 + (bIdx % 3) * 14
      );

      // Exact Geographic Lat/Lon Pin on UMBRA 3D Globe
      bridge.posUmbraPin = bridge.hasCoordinates ? latLonToVec3(bridge.umbraGeo.lat, bridge.umbraGeo.lon, EARTH_RADIUS + 4.5) : new THREE.Vector3();

      // Exact Motif Constellation Hub in SIDERA
      const cl = SIDERA_CLUSTERS.find(c => c.id === bridge.sideraCluster) || SIDERA_CLUSTERS[0];
      const clusterBridges = SYZYGY_BRIDGES.filter(item => item.sideraCluster === bridge.sideraCluster);
      const clusterIndex = clusterBridges.indexOf(bridge);
      const innerCount = clusterBridges.length > 16 ? Math.ceil(clusterBridges.length / 3) : 0;
      const inInnerRing = innerCount > 0 && clusterIndex < innerCount;
      const ringIndex = inInnerRing ? clusterIndex : clusterIndex - innerCount;
      const ringCount = inInnerRing ? innerCount : clusterBridges.length - innerCount;
      const subAng = ringIndex / ringCount * Math.PI * 2 + (innerCount && !inInnerRing ? Math.PI / ringCount : 0);
      const clusterRadius = innerCount ? (inInnerRing ? 30 : 62) : clusterBridges.length > 8 ? 48 : 32;
      bridge.posSideraHub = cl.center.clone().add(new THREE.Vector3(
        Math.cos(subAng) * clusterRadius,
        Math.sin(subAng) * clusterRadius * .82,
        ((clusterIndex % 2) * 2 - 1) * 18
      ));

      bridge.curAnchorPos = bridge.posOmniaSyzygy.clone();
    });

    // ============================================================================
    // 4. THREE.JS SCENE, RETINA RENDERER & CUSTOM GLSL ANTI-BLUR STAR SHADER
    // ============================================================================
    const viewportEl = document.getElementById('webgl-viewport');
    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 3600);
    const CAM_OMNIA = { pos: new THREE.Vector3(-18, 28, 605), target: new THREE.Vector3(-14, -4, 12) };
    const CAM_UMBRA = { pos: new THREE.Vector3(-35, 68, 465), target: new THREE.Vector3(-10, 0, 0) };
    const CAM_SIDERA = { pos: new THREE.Vector3(0, 18, 560), target: new THREE.Vector3(-10, 4, 0) };

    camera.position.copy(CAM_OMNIA.pos);

    const renderer = initialRenderer;
    document.body.dataset.renderer = renderer.isSoftware ? 'software' : 'webgl';
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    viewportEl.appendChild(renderer.domElement);
    renderer.domElement.setAttribute('aria-label', '朔望叠影星图，可拖动旋转、滚轮缩放');

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.target.copy(CAM_OMNIA.target);
    controls.enableDamping = true;
    controls.dampingFactor = 0.065;
    controls.rotateSpeed = 0.56;
    controls.zoomSpeed = 0.85;
    controls.minDistance = 85;
    controls.maxDistance = 1200;

    const cosmosGroup = new THREE.Group();
    scene.add(cosmosGroup);

    // ----------------------------------------------------------------------------
    // CUSTOM ANTI-BLUR GLSL STAR SHADER:
    // White-hot pinpoint core exp(-d*d*38.0) + Spectral halo exp(-d*d*7.5)
    // + Crisp 4-point diffraction spikes exp(-abs(uv.x)*42)*exp(-abs(uv.y)*6)
    // ----------------------------------------------------------------------------
    const starVertexGLSL = `
      attribute float aSize;
      attribute vec3 aColor;
      attribute float aSpike;
      attribute float aHighlight;
      attribute float aPhase;

      uniform float uTime;
      uniform float uPixelRatio;

      varying vec3 vColor;
      varying float vSpike;
      varying float vHighlight;

      void main() {
        vColor = aColor;
        vSpike = aSpike;
        vHighlight = aHighlight;

        vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
        float dist = max(-mvPos.z, 45.0);

        float shimmer = 0.91 + 0.09 * sin(uTime * 2.2 + aPhase);
        float sizeMod = mix(0.68, 1.0, clamp(aHighlight, 0.0, 1.0));
        if (aHighlight > 1.05) {
          sizeMod = 1.0 + (aHighlight - 1.0) * 0.48;
        }

        float pSize = aSize * sizeMod * shimmer * uPixelRatio * (400.0 / dist);
        gl_PointSize = clamp(pSize, 1.75 * uPixelRatio, 72.0 * uPixelRatio);
        gl_Position = projectionMatrix * mvPos;
      }
    `;

    const starFragmentGLSL = `
      uniform float uGlobeMode;
      varying vec3 vColor;
      varying float vSpike;
      varying float vHighlight;

      void main() {
        if (vHighlight < 0.0) discard;
        vec2 uv = gl_PointCoord - vec2(0.5);
        float d = length(uv) * 2.0;
        if (d > 1.0) discard;

        // 1. Razor-sharp incandescent white-hot pinpoint core
        float core = exp(-d * d * 38.0);

        // 2. Exponential chromatic spectral halo
        float halo = exp(-d * d * 7.5) * 0.72;

        // 3. Crisp 4-point astronomical diffraction spikes for hubs & anchors
        float spikes = 0.0;
        if (vSpike > 0.04 && uGlobeMode < 0.5) {
          float sCross = exp(-abs(uv.x) * 42.0) * exp(-abs(uv.y) * 6.0)
                       + exp(-abs(uv.y) * 42.0) * exp(-abs(uv.x) * 6.0);
          spikes = sCross * vSpike * 0.95;
        }

        float lum = core * 1.4 + halo + spikes;
        float alphaScale = clamp(vHighlight, 0.08, 2.2);
        float alpha = clamp(lum * alphaScale, 0.0, 1.0);
        if (alpha < 0.012) discard;

        // Pure incandescent white center transitioning smoothly into spectral halo
        float coreMix = clamp(core * 1.3 + spikes * 0.55, 0.0, 1.0);
        vec3 rgb = mix(vColor, vec3(1.0, 0.99, 0.96), coreMix);

        gl_FragColor = vec4(rgb * alphaScale, alpha);
      }
    `;

    const starUniforms = {
      uTime: { value: 0 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 2) },
      uGlobeMode: { value: 0 }
    };

    const starShaderMat = new THREE.ShaderMaterial({
      uniforms: starUniforms,
      vertexShader: starVertexGLSL,
      fragmentShader: starFragmentGLSL,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });

    // Build Primary Knowledge Stars Geometry (2,266 + 68 Supplement = 2,334 Primary Stars)
    const pCount = PRIMARY_NODES.length;
    const pPosArr = new Float32Array(pCount * 3);
    const pColArr = new Float32Array(pCount * 3);
    const pSizeArr = new Float32Array(pCount);
    const pSpikeArr = new Float32Array(pCount);
    const pHighArr = new Float32Array(pCount);
    const pPhaseArr = new Float32Array(pCount);

    PRIMARY_NODES.forEach((n, i) => {
      pPosArr[i * 3] = n.curPos.x;
      pPosArr[i * 3 + 1] = n.curPos.y;
      pPosArr[i * 3 + 2] = n.curPos.z;
      pColArr[i * 3] = n.curCol.r;
      pColArr[i * 3 + 1] = n.curCol.g;
      pColArr[i * 3 + 2] = n.curCol.b;
      pSizeArr[i] = n.size;
      pSpikeArr[i] = n.spike;
      pHighArr[i] = 1.0;
      pPhaseArr[i] = n.phase;
    });

    const primaryGeo = new THREE.BufferGeometry();
    primaryGeo.setAttribute('position', new THREE.BufferAttribute(pPosArr, 3));
    primaryGeo.setAttribute('aColor', new THREE.BufferAttribute(pColArr, 3));
    primaryGeo.setAttribute('aSize', new THREE.BufferAttribute(pSizeArr, 1));
    primaryGeo.setAttribute('aSpike', new THREE.BufferAttribute(pSpikeArr, 1));
    primaryGeo.setAttribute('aHighlight', new THREE.BufferAttribute(pHighArr, 1));
    primaryGeo.setAttribute('aPhase', new THREE.BufferAttribute(pPhaseArr, 1));

    const primaryStarPoints = new THREE.Points(primaryGeo, starShaderMat);
    primaryStarPoints.userData.softwareStride = 1;
    cosmosGroup.add(primaryStarPoints);

    // Build 3,000 Nebula Micro-Dust Particles (Morphing across all 3 dimensions!)
    const DUST_COUNT = 3000;
    const dustParticles = [];
    const dPosArr = new Float32Array(DUST_COUNT * 3);
    const dColArr = new Float32Array(DUST_COUNT * 3);
    const dSizeArr = new Float32Array(DUST_COUNT);
    const dSpikeArr = new Float32Array(DUST_COUNT);
    const dHighArr = new Float32Array(DUST_COUNT);
    const dPhaseArr = new Float32Array(DUST_COUNT);

    for (let i = 0; i < DUST_COUNT; i++) {
      const vIdx = i % 5;
      const vol = VOLUMES[vIdx];
      const dIdx = i % vol.disciplines.length;
      const pOmnia = sampleOmniaGalaxyLocal(vIdx, dIdx, i, 600, false).multiplyScalar(1.06).add(vol.center);

      const th2 = (vIdx / 5) * Math.PI * 2 - Math.PI / 2 + sRand() * ((Math.PI * 2) / 5);
      const r2 = 88 + Math.pow(sRand(), 0.72) * 176;
      const p2D = new THREE.Vector3(Math.cos(th2) * r2, Math.sin(th2) * r2 * 0.92, -3);

      const pUmbra = sampleUmbraContinentPoint();
      const pSidera = sampleSideraPoint(vIdx, i, false);

      const cOmnia = new THREE.Color(i % 2 === 0 ? vol.color : vol.altColor);
      const cUmbra = new THREE.Color('#a68b5b');
      const cSidera = new THREE.Color(SIDERA_CLUSTERS[vIdx].color);

      dustParticles.push({ vIdx, pOmnia, p2D, pUmbra, pSidera, cOmnia, cUmbra, cSidera });

      dPosArr[i * 3] = pOmnia.x;
      dPosArr[i * 3 + 1] = pOmnia.y;
      dPosArr[i * 3 + 2] = pOmnia.z;
      dColArr[i * 3] = cOmnia.r;
      dColArr[i * 3 + 1] = cOmnia.g;
      dColArr[i * 3 + 2] = cOmnia.b;
      dSizeArr[i] = 1.8 + sRand() * 2.1;
      dSpikeArr[i] = 0.0;
      dHighArr[i] = 0.56;
      dPhaseArr[i] = sRand() * 6.28;
    }

    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute('position', new THREE.BufferAttribute(dPosArr, 3));
    dustGeo.setAttribute('aColor', new THREE.BufferAttribute(dColArr, 3));
    dustGeo.setAttribute('aSize', new THREE.BufferAttribute(dSizeArr, 1));
    dustGeo.setAttribute('aSpike', new THREE.BufferAttribute(dSpikeArr, 1));
    dustGeo.setAttribute('aHighlight', new THREE.BufferAttribute(dHighArr, 1));
    dustGeo.setAttribute('aPhase', new THREE.BufferAttribute(dPhaseArr, 1));

    const dustPoints = new THREE.Points(dustGeo, starShaderMat);
    dustPoints.userData.softwareStride = 3;
    cosmosGroup.add(dustPoints);

    // Build the curated spiritual motif anchors (玄象母题锚点 / 坤舆异闻坐标针).
    const sCount = SYZYGY_BRIDGES.length;
    const sPosArr = new Float32Array(sCount * 3);
    const sColArr = new Float32Array(sCount * 3);
    const sSizeArr = new Float32Array(sCount);
    const sSpikeArr = new Float32Array(sCount);
    const sHighArr = new Float32Array(sCount);
    const sPhaseArr = new Float32Array(sCount);

    SYZYGY_BRIDGES.forEach((b, i) => {
      sPosArr[i * 3] = b.curAnchorPos.x;
      sPosArr[i * 3 + 1] = b.curAnchorPos.y;
      sPosArr[i * 3 + 2] = b.curAnchorPos.z;
      const relCol = new THREE.Color(RELATION_META[b.relation].colorB);
      sColArr[i * 3] = relCol.r;
      sColArr[i * 3 + 1] = relCol.g;
      sColArr[i * 3 + 2] = relCol.b;
      sSizeArr[i] = 25.0;
      sSpikeArr[i] = 1.25;
      sHighArr[i] = 1.35;
      sPhaseArr[i] = i * 0.9;
    });

    const spiritualAnchorGeo = new THREE.BufferGeometry();
    spiritualAnchorGeo.setAttribute('position', new THREE.BufferAttribute(sPosArr, 3));
    spiritualAnchorGeo.setAttribute('aColor', new THREE.BufferAttribute(sColArr, 3));
    spiritualAnchorGeo.setAttribute('aSize', new THREE.BufferAttribute(sSizeArr, 1));
    spiritualAnchorGeo.setAttribute('aSpike', new THREE.BufferAttribute(sSpikeArr, 1));
    spiritualAnchorGeo.setAttribute('aHighlight', new THREE.BufferAttribute(sHighArr, 1));
    spiritualAnchorGeo.setAttribute('aPhase', new THREE.BufferAttribute(sPhaseArr, 1));

    const spiritualAnchorPoints = new THREE.Points(spiritualAnchorGeo, starShaderMat);
    spiritualAnchorPoints.userData.globeAnchor = true;
    cosmosGroup.add(spiritualAnchorPoints);

    // Deep-Space Background Starfield (1,600 static distant stars)
    const BG_COUNT = 1600;
    const bgGeo = new THREE.BufferGeometry();
    const bgPos = new Float32Array(BG_COUNT * 3);
    const bgCol = new Float32Array(BG_COUNT * 3);
    const bgSize = new Float32Array(BG_COUNT);
    const bgSpike = new Float32Array(BG_COUNT);
    const bgHigh = new Float32Array(BG_COUNT);
    const bgPhase = new Float32Array(BG_COUNT);

    for (let i = 0; i < BG_COUNT; i++) {
      const r = 740 + sRand() * 920;
      const th = sRand() * Math.PI * 2;
      const ph = Math.acos(2 * sRand() - 1);
      bgPos[i * 3] = r * Math.sin(ph) * Math.cos(th);
      bgPos[i * 3 + 1] = r * Math.sin(ph) * Math.sin(th);
      bgPos[i * 3 + 2] = r * Math.cos(ph) - 180;
      const c = new THREE.Color(i % 3 === 0 ? '#e2e8f0' : (i % 3 === 1 ? '#fde68a' : '#bfdbfe'));
      bgCol[i * 3] = c.r; bgCol[i * 3 + 1] = c.g; bgCol[i * 3 + 2] = c.b;
      bgSize[i] = 1.6 + Math.pow(sRand(), 2.8) * 3.2;
      bgSpike[i] = sRand() > 0.985 ? 0.45 : 0.0;
      bgHigh[i] = 0.36;
      bgPhase[i] = sRand() * 6.28;
    }
    bgGeo.setAttribute('position', new THREE.BufferAttribute(bgPos, 3));
    bgGeo.setAttribute('aColor', new THREE.BufferAttribute(bgCol, 3));
    bgGeo.setAttribute('aSize', new THREE.BufferAttribute(bgSize, 1));
    bgGeo.setAttribute('aSpike', new THREE.BufferAttribute(bgSpike, 1));
    bgGeo.setAttribute('aHighlight', new THREE.BufferAttribute(bgHigh, 1));
    bgGeo.setAttribute('aPhase', new THREE.BufferAttribute(bgPhase, 1));
    const backgroundStars = new THREE.Points(bgGeo, starShaderMat);
    backgroundStars.userData.softwareStride = 4;
    scene.add(backgroundStars);

    // ============================================================================
    // 5. BESPOKE 3D CELESTIAL STRUCTURES FOR EACH DIMENSION
    // ============================================================================
    function createCircleCurve(radius, segments, color, opacity, dashed = false) {
      const pts = [];
      for (let i = 0; i <= segments; i++) {
        const a = (i / segments) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, 0));
      }
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      if (dashed) {
        const l = new THREE.Line(geo, new THREE.LineDashedMaterial({
          color, transparent: true, opacity, dashSize: 4, gapSize: 4, depthWrite: false
        }));
        l.computeLineDistances();
        return l;
      }
      return new THREE.Line(geo, new THREE.LineBasicMaterial({
        color, transparent: true, opacity, depthWrite: false
      }));
    }

    // 5A. OMNIA Astrolabe Coordinate Rings, Vol 3 Dual Gimbal Rings & Vol 5 Lagrange Portal
    const omniaScaffold = new THREE.Group();
    cosmosGroup.add(omniaScaffold);

    [56, 118, 186, 252, 274].forEach((r, idx) => {
      omniaScaffold.add(createCircleCurve(r, 160, '#d6b678', idx === 3 ? 0.16 : 0.09, idx % 2 === 1));
    });

    // Degree ticks on outer brass ring
    const degPts = [];
    for (let deg = 0; deg < 360; deg += 3) {
      const rad = THREE.MathUtils.degToRad(deg);
      const rIn = 270;
      const rOut = deg % 30 === 0 ? 282 : (deg % 15 === 0 ? 276 : 273);
      degPts.push(
        new THREE.Vector3(Math.cos(rad) * rIn, Math.sin(rad) * rIn, 0),
        new THREE.Vector3(Math.cos(rad) * rOut, Math.sin(rad) * rOut, 0)
      );
    }
    omniaScaffold.add(new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(degPts),
      new THREE.LineBasicMaterial({ color: '#d6b678', transparent: true, opacity: 0.2, depthWrite: false })
    ));

    // Vol 3 (造物卷): Geodesic Crystal Filaments + Dual Counter-Rotating Brass Gimbal Rings
    const vol3Struts = [];
    ICO_EDGES.forEach(([a, b]) => {
      vol3Struts.push(a.clone().multiplyScalar(54), b.clone().multiplyScalar(54));
    });
    const vol3Lattice = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(vol3Struts),
      new THREE.LineBasicMaterial({ color: '#52d1a2', transparent: true, opacity: 0.12, depthWrite: false })
    );
    vol3Lattice.position.copy(VOLUMES[2].center);
    omniaScaffold.add(vol3Lattice);

    const gimbalRingA = createCircleCurve(70, 108, '#d6b678', 0.22, false);
    gimbalRingA.position.copy(VOLUMES[2].center);
    const gimbalRingB = createCircleCurve(77, 108, '#52d1a2', 0.16, true);
    gimbalRingB.position.copy(VOLUMES[2].center);
    omniaScaffold.add(gimbalRingA, gimbalRingB);

    // Vol 5 (意义卷): Lagrange Wormhole Portal Vortex Rings
    const portalRingOuter = createCircleCurve(68, 108, '#f3d08a', 0.24, true);
    portalRingOuter.position.copy(VOLUMES[4].center);
    const portalRingInner = createCircleCurve(36, 90, '#b692f6', 0.26, false);
    portalRingInner.position.copy(VOLUMES[4].center);
    omniaScaffold.add(portalRingOuter, portalRingInner);

    // Upper Spiritual Halo Ring (visible when Syzygy Mode is ON in OMNIA)
    const syzygyUpperRing = new THREE.Group();
    const upperEllipsePts = [];
    for (let i = 0; i <= 160; i++) {
      const a = (i / 160) * Math.PI * 2;
      upperEllipsePts.push(new THREE.Vector3(Math.cos(a) * 238, Math.sin(a) * 238 * 0.78 + 18, 104));
    }
    syzygyUpperRing.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(upperEllipsePts),
      new THREE.LineDashedMaterial({ color: '#b692f6', transparent: true, opacity: 0.24, dashSize: 5, gapSize: 4, depthWrite: false })
    ));
    syzygyUpperRing.children[0].computeLineDistances();
    cosmosGroup.add(syzygyUpperRing);

    // 5B. UMBRA 3D Celestial Dark-Umbra Globe (Brass Latitude/Longitude Graticules & Umbral Core)
    const umbraGlobeGroup = new THREE.Group();
    umbraGlobeGroup.visible = false;
    cosmosGroup.add(umbraGlobeGroup);

    const obsidianSphere = new THREE.Mesh(
      new THREE.SphereGeometry(EARTH_RADIUS - 2.2, 48, 36),
      new THREE.MeshBasicMaterial({ color: '#050812', transparent: true, opacity: 0.88 })
    );
    umbraGlobeGroup.add(obsidianSphere);

    // Brass Latitude Parallels & Longitude Meridians
    const graticulePts = [];
    for (let lat = -75; lat <= 75; lat += 15) {
      const isEq = lat === 0;
      const segs = 96;
      for (let i = 0; i < segs; i++) {
        const lon1 = (i / segs) * 360 - 180;
        const lon2 = ((i + 1) / segs) * 360 - 180;
        graticulePts.push(
          latLonToVec3(lat, lon1, EARTH_RADIUS + (isEq ? 0.6 : 0.2)),
          latLonToVec3(lat, lon2, EARTH_RADIUS + (isEq ? 0.6 : 0.2))
        );
      }
    }
    for (let lon = -180; lon < 180; lon += 15) {
      const segs = 64;
      for (let i = 0; i < segs; i++) {
        const lat1 = (i / segs) * 170 - 85;
        const lat2 = ((i + 1) / segs) * 170 - 85;
        graticulePts.push(latLonToVec3(lat1, lon, EARTH_RADIUS + 0.2), latLonToVec3(lat2, lon, EARTH_RADIUS + 0.2));
      }
    }
    umbraGlobeGroup.add(new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(graticulePts),
      new THREE.LineBasicMaterial({ color: '#d6b678', transparent: true, opacity: 0.16, depthWrite: false })
    ));

    // Tilted 23.5° Brass Ecliptic Ring around Umbra Earth
    const umbraEcliptic = createCircleCurve(EARTH_RADIUS + 26, 128, '#d6b678', 0.28, false);
    umbraEcliptic.rotation.set(1.15, 0.25, 0.41);
    umbraGlobeGroup.add(umbraEcliptic);

    // 5C. SIDERA Shimmering Non-Euclidean Constellation Filaments
    const sideraFilamentGroup = new THREE.Group();
    sideraFilamentGroup.visible = false;
    cosmosGroup.add(sideraFilamentGroup);

    const sideraLinePts = [];
    // Connect hubs across the 5 motif clusters + connect each Syzygy Motif hub to its cluster center
    SIDERA_CLUSTERS.forEach((cl, idx) => {
      const nextCl = SIDERA_CLUSTERS[(idx + 1) % SIDERA_CLUSTERS.length];
      const oppCl = SIDERA_CLUSTERS[(idx + 2) % SIDERA_CLUSTERS.length];
      sideraLinePts.push(cl.center, nextCl.center, cl.center, oppCl.center);
    });
    SYZYGY_BRIDGES.forEach(b => {
      const cl = SIDERA_CLUSTERS.find(c => c.id === b.sideraCluster);
      if (cl) sideraLinePts.push(cl.center, b.posSideraHub);
    });
    // Also weave delicate sub-constellation filaments within each motif cluster
    for (let c = 0; c < SIDERA_CLUSTERS.length; c++) {
      const clusterStars = PRIMARY_NODES.filter((_, idx) => idx % 5 === c).slice(0, 26);
      for (let k = 0; k < clusterStars.length - 1; k++) {
        sideraLinePts.push(clusterStars[k].posSidera3D, clusterStars[k + 1].posSidera3D);
      }
    }
    sideraFilamentGroup.add(new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(sideraLinePts),
      new THREE.LineBasicMaterial({
        color: '#c4b5fd', transparent: true, opacity: 0.22, depthWrite: false, blending: THREE.AdditiveBlending
      })
    ));

    // ============================================================================
    // 6. CUBIC BEZIER PHOTON BRIDGES (心物折光弦) WITH TRAVELING PULSES
    // ============================================================================
    const bezierBridgesGroup = new THREE.Group();
    cosmosGroup.add(bezierBridgesGroup);

    // Crisp procedural photon sprite texture
    function makePhotonTexture() {
      const c = document.createElement('canvas');
      c.width = 64; c.height = 64;
      const ctx = c.getContext('2d');
      const g = ctx.createRadialGradient(32, 32, 1, 32, 32, 30);
      g.addColorStop(0.0, 'rgba(255,255,255,1.0)');
      g.addColorStop(0.22, 'rgba(255,244,214,0.85)');
      g.addColorStop(0.55, 'rgba(214,182,120,0.22)');
      g.addColorStop(1.0, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 64, 64);
      return new THREE.CanvasTexture(c);
    }
    const photonTex = makePhotonTexture();
    let activePhotonPulses = [];
    let activeBridgeCurves = [];

    function rebuildSyzygyPhotonBridges() {
      while (bezierBridgesGroup.children.length > 0) {
        const ch = bezierBridgesGroup.children[0];
        if (ch.geometry) ch.geometry.dispose();
        if (ch.material) ch.material.dispose();
        bezierBridgesGroup.remove(ch);
      }
      activePhotonPulses = [];
      activeBridgeCurves = [];

      if (!appState.syzygyOn) return;

      const bridges = appState.portalBridge && appState.dimension === 'omnia' ? [...SYZYGY_BRIDGES, appState.portalBridge] : SYZYGY_BRIDGES;
      bridges.forEach((bridge, idx) => {
        const personal = bridge === appState.portalBridge;
        if ((!personal && !bridgeAllowed(bridge)) || (personal && bridge.fiction && !appState.showF) || (appState.dimension === 'umbra' && !bridge.hasCoordinates)
          || (!personal && appState.matchingBridgeIds && !appState.matchingBridgeIds.has(bridge.id) && appState.selectedBridge?.id !== bridge.id)) return;
        // Filter visibility by trail / search / selection
        const isTrailActive = appState.activeTrail === 'all' || bridge.trail === appState.activeTrail;
        const isSelected = personal || (appState.selectedBridge && appState.selectedBridge.id === bridge.id);
        if (appState.activeTrail !== 'all' && !isTrailActive && !isSelected) return;
        // On the globe, an unrelated knowledge star has no geographic position.
        // Keep only the selected bridge visible so background links do not look
        // like line-shaped location markers or imply invented destinations.
        if (appState.dimension === 'umbra' && !isSelected) return;
        // Keep all anchors selectable, but sample background curves in the overview
        // to avoid turning a larger collection into a dense mesh on slow devices.
        const overviewStride = Math.max(1, Math.ceil(SYZYGY_BRIDGES.length / 12));
        if (appState.activeTrail === 'all' && !appState.searchQuery && !isSelected && !personal && idx % overviewStride !== 0) return;

        const pStart = bridge.curAnchorPos.clone();
        const pEnd = bridge.materialNode.curPos.clone();

        // Construct graceful 3D Cubic Bezier Control Points
        const mid = pStart.clone().lerp(pEnd, 0.5);
        const span = pStart.distanceTo(pEnd);
        const c1 = pStart.clone().lerp(mid, 0.55);
        const c2 = mid.clone().lerp(pEnd, 0.45);
        c1.z += Math.min(75, span * 0.25);
        c2.z += Math.min(45, span * 0.14);
        c1.x += (idx % 2 === 0 ? 1 : -1) * 18;

        const curve = new THREE.CubicBezierCurve3(pStart, c1, c2, pEnd);
        const segments = 52;
        const pts = curve.getPoints(segments);

        // Vertex-colored gradient along Relation Type (colorA -> colorB)
        const relMeta = RELATION_META[bridge.relation];
        const colA = new THREE.Color(relMeta.colorA);
        const colB = new THREE.Color(relMeta.colorB);
        const posBuf = new Float32Array((segments + 1) * 3);
        const colBuf = new Float32Array((segments + 1) * 3);

        pts.forEach((pt, k) => {
          posBuf[k * 3] = pt.x;
          posBuf[k * 3 + 1] = pt.y;
          posBuf[k * 3 + 2] = pt.z;
          const c = colB.clone().lerp(colA, k / segments);
          colBuf[k * 3] = c.r;
          colBuf[k * 3 + 1] = c.g;
          colBuf[k * 3 + 2] = c.b;
        });

        const lineGeo = new THREE.BufferGeometry();
        lineGeo.setAttribute('position', new THREE.BufferAttribute(posBuf, 3));
        lineGeo.setAttribute('color', new THREE.BufferAttribute(colBuf, 3));

        const baseOpacity = isSelected ? 0.92 : (appState.activeTrail !== 'all' ? 0.78 : 0.36);
        const lineMat = new THREE.LineBasicMaterial({
          vertexColors: true,
          transparent: true,
          opacity: baseOpacity,
          depthWrite: false,
          blending: THREE.AdditiveBlending
        });

        bezierBridgesGroup.add(new THREE.Line(lineGeo, lineMat));
        activeBridgeCurves.push({ bridge, idx, curve, geometry: lineGeo });

        // Add 2 bidirectional / staggered traveling photon light pulses per active bridge
        const pulseCount = isSelected || appState.activeTrail !== 'all' ? 2 : 1;
        for (let p = 0; p < pulseCount; p++) {
          const spMat = new THREE.SpriteMaterial({
            map: photonTex,
            color: p === 0 ? colA : colB,
            transparent: true,
            opacity: 0.95,
            depthWrite: false,
            blending: THREE.AdditiveBlending
          });
          const sprite = new THREE.Sprite(spMat);
          const sScale = isSelected ? 12 : 8.5;
          sprite.scale.set(sScale, sScale, 1);
          bezierBridgesGroup.add(sprite);

          activePhotonPulses.push({
            curve,
            sprite,
            speed: 0.20 + (idx % 4) * 0.04,
            offset: ((idx * 0.19) + p * 0.5) % 1.0
          });
        }
      });
    }

    const bridgeMid = new THREE.Vector3(), bridgeC1 = new THREE.Vector3(), bridgeC2 = new THREE.Vector3(), bridgePoint = new THREE.Vector3();
    function updateBridgeCurves() {
      for (const item of activeBridgeCurves) {
        const start = item.bridge.curAnchorPos, end = item.bridge.materialNode.curPos;
        bridgeMid.copy(start).lerp(end, .5);
        const span = start.distanceTo(end);
        bridgeC1.copy(start).lerp(bridgeMid, .55); bridgeC2.copy(bridgeMid).lerp(end, .45);
        bridgeC1.z += Math.min(75, span * .25); bridgeC2.z += Math.min(45, span * .14);
        bridgeC1.x += (item.idx % 2 === 0 ? 1 : -1) * 18;
        item.curve.v0.copy(start); item.curve.v1.copy(bridgeC1); item.curve.v2.copy(bridgeC2); item.curve.v3.copy(end);
        const attribute = item.geometry.getAttribute('position');
        for (let i = 0; i < attribute.count; i++) {
          item.curve.getPoint(i / (attribute.count - 1), bridgePoint);
          attribute.setXYZ(i, bridgePoint.x, bridgePoint.y, bridgePoint.z);
        }
        attribute.needsUpdate = true;
      }
    }

    // ============================================================================
    // 7. APPLICATION STATE, CAMERA INTERPOLATION & MORPH ENGINE
    // ============================================================================
    const appState = {
      dimension: 'omnia',     // 'omnia' | 'umbra' | 'sidera'
      syzygyOn: true,         // Default ON!
      is2DPlanisphere: false,
      scopeTab: 'all',        // 'all' | 'volumes' | 'supplement' | 'bridges'
      activeVolId: null,
      activeDiscId: null,
      activeTrail: 'all',
      searchQuery: '',
      openBridgeClusters: new Set(),
      openReadingPaths: new Set(),
      showF: initialShowF,
      tiers: new Set(initialTiers),
      genre: Object.hasOwn(genreLabels,initialParams.get('genre')) ? initialParams.get('genre') : 'ALL',
      selectedBridge: initialParams.has('story') || initialParams.has('entry') ? null : SYZYGY_BRIDGES.find(b=>initialTiers.has(b.mythos.credibility_tier) && (!b.fiction || initialShowF)
        && (!Object.hasOwn(genreLabels,initialParams.get('genre')) || genreContract(b.mythos) === initialParams.get('genre'))) ?? null,
      selectedGraph: null,
      selectedBook: null,
      pendingBook: null,
      portalBridge: null,
      restoringDeepLink: initialParams.has('story') || initialParams.has('entry'),
      pendingRoute: initialParams.has('story') || initialParams.has('entry') ? {story:initialParams.get('story'),entry:initialParams.get('entry')} : null,
      classicView: ['map','graph','life'].includes(initialParams.get('return')) ? initialParams.get('return')
        : initialParams.get('dim') === 'umbra' ? 'map' : initialParams.get('dim') === 'sidera' ? 'graph' : 'life',
      hoveredTarget: null,
      camAnim: null,
      needsBridgeRebuild: false
    };
    function bridgeAllowed(bridge) { return appState.tiers.has(bridge.mythos.credibility_tier) && (!bridge.fiction || appState.showF)
      && (appState.genre === 'ALL' || genreContract(bridge.mythos) === appState.genre); }
    function bridgeMatchesFilter(b) {
      if (!bridgeAllowed(b) || (appState.activeTrail !== 'all' && b.trail !== appState.activeTrail)) return false;
      const query = appState.searchQuery.trim().toLowerCase();
      if (!query) return true;
      const hay = `${b.id} ${b.shortLabel} ${b.mythos.title} ${b.mythos.genre} ${b.mythos.taxonomies.join(' ')} ${b.physis.title} ${b.physis.code} ${b.physis.volLabel} ${b.umbraGeo.place}`.toLowerCase();
      return hay.includes(query);
    }

    const fullAtlas = createFullAtlas({ root, book, dataset:bridgeDataset, state:appState, cosmosGroup,
      starMaterial:starShaderMat, latLonToVec3,
      focusNode(node, geo, semantic) {
        if (appState.dimension === 'omnia') switchDimension('sidera', true);
        if (appState.dimension === 'umbra' && !geo) { flashToast('此条未记录坐标，可在目录与星络中阅读。'); return; }
        const local = appState.dimension === 'umbra' ? geo : semantic;
        const world = local.clone().applyMatrix4(cosmosGroup.matrixWorld);
        if (appState.dimension === 'umbra') animateCameraTo(world.clone().normalize().multiplyScalar(EARTH_RADIUS + 195), world.clone().multiplyScalar(.3), 980);
        else animateCameraTo(world.clone().add(new THREE.Vector3(0, 25, 185)), world, 980);
      },
      onSelection() {
        appState.restoringDeepLink=false;
        appState.pendingRoute=null;
        clearPersonalPortal();
        if (appState.selectedBook && !appState.selectedGraph) {
          appState.classicView='life';
          if (appState.dimension !== 'omnia') switchDimension('omnia');
          const star = PRIMARY_NODES.find(item=>item.code === appState.selectedBook.id);
          if (star) { const pos=star.posOmnia3D.clone().applyMatrix4(cosmosGroup.matrixWorld); animateCameraTo(pos.clone().add(new THREE.Vector3(0,25,210)),pos,980); }
        }
        updateHighlightsAndFilters(); updateClassicLink(); syncViewURL(); setRightDrawerCollapsed(false);
      },
      onBrowseFolklore() {
        appState.scopeTab = 'supplement';
        appState.searchQuery = ''; searchInput.value = ''; btnClearQuery.classList.add('hidden'); mobileResults.hidden = true;
        fullAtlas.searchChanged(); updateHighlightsAndFilters();
        document.querySelectorAll('.scope-tab').forEach(tab=>tab.classList.toggle('active',tab.getAttribute('data-scope') === 'supplement'));
        setLeftDrawerCollapsed(false); flashToast('在左侧目录选择民俗条目。');
      },
      onPortal(node, entry) {
        if (appState.dimension !== 'omnia') switchDimension('omnia', false, true);
        if (!appState.syzygyOn) document.getElementById('btn-syzygy-toggle').click();
        const materialNode = PRIMARY_NODES.find(item => item.code === entry.id);
        if (!materialNode) { flashToast('未找到这条格物星点。'); return; }
        let hash=0; for (const c of node.id) hash=Math.imul(hash^c.charCodeAt(0),16777619);
        const angle=(hash>>>0)/4294967296*Math.PI*2;
        const anchor=new THREE.Vector3(Math.cos(angle)*238,Math.sin(angle)*186+18,112);
        appState.portalBridge = { id:'USER-PORTAL', fiction:node.credibility_tier === 'F' || node.is_fictional_quarantine,
          hasCoordinates:false, trail:'personal', relation:'THEMATIC', curAnchorPos:anchor, materialNode };
        renderer.domElement.dataset.portalStory = node.id; renderer.domElement.dataset.portalBook = entry.id;
        userPortalMarker.position.copy(anchor); userPortalMarker.visible=true;
        userPortalLabel.textContent=node.title; userPortalLabel.hidden=false;
        appState.needsBridgeRebuild=true; updateHighlightsAndFilters(); updateClassicLink();
        const mid=anchor.clone().lerp(materialNode.posOmnia3D,.5).applyMatrix4(cosmosGroup.matrixWorld);
        animateCameraTo(mid.clone().add(new THREE.Vector3(0,25,320)),mid,980);
        syncViewURL();
      },
    });

    const userPortalMarker = new THREE.Sprite(new THREE.SpriteMaterial({ map:photonTex, color:'#d8c3ff', transparent:true, depthWrite:false, blending:THREE.AdditiveBlending }));
    userPortalMarker.scale.set(18,18,1); userPortalMarker.visible=false; cosmosGroup.add(userPortalMarker);
    const userPortalLabel = document.createElement('div'); userPortalLabel.className='world-tag personal-portal-label'; userPortalLabel.hidden=true;
    function clearPersonalPortal() {
      appState.portalBridge=null; userPortalMarker.visible=false; userPortalLabel.hidden=true; appState.needsBridgeRebuild=true;
      delete renderer.domElement.dataset.portalStory; delete renderer.domElement.dataset.portalBook;
    }

    function updateClassicLink() {
      const view = appState.classicView;
      const params = new URLSearchParams({view});
      if (view === 'life') {
        const entry = appState.selectedBook?.id || appState.selectedBridge?.physis.id || appState.pendingRoute?.entry;
        if (entry) params.set('entry', entry);
      } else {
        const id = appState.selectedGraph?.id || appState.selectedBridge?.mythos.id || appState.pendingRoute?.story;
        if (id) params.set('story', id);
      }
      const story = appState.selectedGraph?.id || appState.selectedBridge?.mythos.id || appState.pendingRoute?.story;
      const entry = appState.selectedBook?.id || appState.selectedBridge?.physis.id || appState.pendingRoute?.entry;
      if (story && entry) { params.set('bridge_story',story); params.set('bridge_entry',entry); }
      params.set('tiers',tierOrder.filter(tier=>appState.tiers.has(tier)).join(','));
      if (appState.genre !== 'ALL') params.set('genre',appState.genre);
      if (appState.showF) params.set('fiction','1');
      document.getElementById('btn-classic-view').href = `${root}?${params}`;
    }

    function syncViewURL() {
      if (appState.restoringDeepLink) return;
      const url = new URL(window.location.href);
      url.searchParams.set('dim',appState.dimension);
      url.searchParams.set('return',appState.classicView);
      url.searchParams.set('tiers',tierOrder.filter(tier=>appState.tiers.has(tier)).join(','));
      const story = appState.selectedGraph?.id || appState.selectedBridge?.mythos.id;
      if (story) url.searchParams.set('story',story); else url.searchParams.delete('story');
      if (appState.selectedBook) url.searchParams.set('entry',appState.selectedBook.id); else url.searchParams.delete('entry');
      if (appState.showF) url.searchParams.set('fiction','1'); else url.searchParams.delete('fiction');
      if (appState.genre !== 'ALL') url.searchParams.set('genre',appState.genre); else url.searchParams.delete('genre');
      history.replaceState({},'',url);
    }

    function animateCameraTo(pos, target, duration = 1050) {
      appState.camAnim = {
        startPos: camera.position.clone(),
        endPos: pos.clone(),
        startTarget: controls.target.clone(),
        endTarget: target.clone(),
        startTime: performance.now(),
        duration
      };
    }

    function flashToast(text) {
      const toast = document.getElementById('status-toast');
      toast.textContent = text;
      toast.style.opacity = '1';
      clearTimeout(toast._tid);
      toast._tid = setTimeout(() => { toast.style.opacity = '0'; }, 2300);
    }

    function switchDimension(dim, skipCamera = false, preserveReturn = false) {
      appState.dimension = dim;
      starUniforms.uGlobeMode.value = dim === 'umbra' ? 1 : 0;
      const anchorSizes = spiritualAnchorGeo.getAttribute('aSize');
      anchorSizes.array.fill(dim === 'umbra' ? 14 : 25);
      anchorSizes.needsUpdate = true;
      if (!preserveReturn) appState.classicView = dim === 'umbra' ? 'map' : dim === 'sidera' ? 'graph' : 'life';
      if (dim !== 'omnia') {
        appState.is2DPlanisphere = false;
        document.getElementById('btn-proj-toggle').textContent = '2D 星盘';
        document.getElementById('btn-proj-toggle').classList.remove('active');
      }

      document.querySelectorAll('[data-dim]').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-dim') === dim);
      });

      // Toggle dimension-specific 3D scaffolds
      omniaScaffold.visible = (dim === 'omnia' && !appState.is2DPlanisphere);
      umbraGlobeGroup.visible = (dim === 'umbra');
      sideraFilamentGroup.visible = (dim === 'sidera');
      syzygyUpperRing.visible = (dim === 'omnia' && appState.syzygyOn && !appState.is2DPlanisphere);
      primaryStarPoints.visible = dim === 'omnia';
      userPortalMarker.visible = !!appState.portalBridge && dim === 'omnia' && appState.syzygyOn;
      fullAtlas.updateDimension();
      updateClassicLink();
      syncViewURL();

      // Update Top-Left Context Watermark
      const eyebrow = document.getElementById('banner-eyebrow');
      const title = document.getElementById('banner-title');
      const desc = document.getElementById('banner-desc');

      if (dim === 'umbra') {
        eyebrow.textContent = 'UMBRA / 3D CELESTIAL FOLKLORE & ANOMALY GLOBE';
        title.textContent = 'UMBRA · 坤舆异志';
        desc.textContent = '按真实坐标展示全球民俗与个案 · 可在目录中检索全部图谱条目';
        if (!skipCamera) animateCameraTo(CAM_UMBRA.pos, CAM_UMBRA.target, 1100);
      } else if (dim === 'sidera') {
        eyebrow.textContent = 'SIDERA / NON-EUCLIDEAN MOTIF CONSTELLATION';
        title.textContent = 'SIDERA · 玄象星络';
        desc.textContent = '原图谱四层条目的星域投影 · 点击星点阅读卷宗与真实关联';
        if (!skipCamera) animateCameraTo(CAM_SIDERA.pos, CAM_SIDERA.target, 1100);
      } else {
        eyebrow.textContent = 'OMNIA × SYZYGY / HETEROGENEOUS ASTROLABE';
        title.textContent = 'OMNIA · 万象星枢';
        desc.textContent = `《格物识微》五卷 · ${book.entries.length.toLocaleString()} 个真实条目与民俗卷宗对照`;
        if (!skipCamera) animateCameraTo(CAM_OMNIA.pos, CAM_OMNIA.target, 1100);
      }

      renderLeftAtlasTree();
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;
    }

    // ============================================================================
    // 8. FILTERING, STAR BRIGHTNESS & WORLD ANCHOR LABELS
    // ============================================================================
    const worldLabelsEl = document.getElementById('world-labels');
    const domAnchors = [];

    function buildWorldDOMAnchors() {
      worldLabelsEl.innerHTML = '';
      domAnchors.length = 0;

      // 1. 5 OMNIA Volume Plaques (Vol 5 features special Lagrange Wormhole badge!)
      VOLUMES.forEach(vol => {
        const el = document.createElement('div');
        el.className = 'world-tag';
        el.innerHTML = `
          <div class="vol-plaque ${vol.isWormhole ? 'wormhole-plaque' : ''}">
            <div class="font-mono-tech text-[9px] tracking-[0.16em]" style="color:${vol.color}">
              ${vol.num} / ${vol.en}
            </div>
            <div class="font-serif-sc text-xs font-semibold text-[#f7f0e2] tracking-widest mt-0.5 flex items-center justify-center gap-1">
              <span>${vol.name}</span>
              ${vol.isWormhole ? '<span class="text-[10px] text-[#b692f6]">⇄ 穿界星门</span>' : ''}
            </div>
          </div>
        `;
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          if (vol.isWormhole && appState.activeVolId === 'vol5') {
            switchDimension('sidera');
            flashToast('已通过「05 意义卷 · 拉格朗日穿界星门」跃迁至 SIDERA · 玄象星络');
          } else {
            focusOmniaVolume(vol.id);
          }
        });
        worldLabelsEl.appendChild(el);
        domAnchors.push({ type: 'omniaVol', el, vol });
      });

      // 2. 5 SIDERA Motif Cluster Plaques
      SIDERA_CLUSTERS.forEach(cl => {
        const el = document.createElement('div');
        el.className = 'world-tag';
        el.innerHTML = `
          <div class="vol-plaque border-[#b692f6]/40">
            <div class="font-mono-tech text-[9px] tracking-[0.16em] text-[#c4b5fd]">${cl.code}</div>
            <div class="font-serif-sc text-xs font-semibold text-[#f3eeff] mt-0.5">${cl.name}</div>
          </div>
        `;
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          const b = SYZYGY_BRIDGES.find(x => x.sideraCluster === cl.id);
          if (b) selectSyzygyBridge(b, true);
        });
        worldLabelsEl.appendChild(el);
        domAnchors.push({ type: 'sideraCluster', el, cl });
      });

      // 3. Curated Syzygy spiritual motif / Umbra site chips.
      SYZYGY_BRIDGES.forEach(bridge => {
        const el = document.createElement('div');
        el.className = 'world-tag';
        const dotColor = RELATION_META[bridge.relation].colorA;
        el.innerHTML = `
          <div class="motif-anchor-chip">
            <span class="w-1.5 h-1.5 rounded-full" style="background:${dotColor}"></span>
            <span>${escapeHTML(bridge.shortLabel)}</span>
          </div>
        `;
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          selectSyzygyBridge(bridge, true);
        });
        worldLabelsEl.appendChild(el);
        domAnchors.push({ type: 'bridgeAnchor', el, bridge });
      });
    }

    function updateHighlightsAndFilters() {
      const q = appState.searchQuery.trim().toLowerCase();
      const pHigh = primaryGeo.getAttribute('aHighlight');
      const sHigh = spiritualAnchorGeo.getAttribute('aHighlight');
      const dHigh = dustGeo.getAttribute('aHighlight');

      // Filter Bridges first
      const matchingBridgeIds = new Set();
      SYZYGY_BRIDGES.forEach(b => {
        if (bridgeMatchesFilter(b)) matchingBridgeIds.add(b.id);
      });
      appState.matchingBridgeIds = matchingBridgeIds;

      // Update Primary Star Brightness
      PRIMARY_NODES.forEach((n, i) => {
        let match = true;
        const hasMatchingBridge = n.bridgeIds.some(id => matchingBridgeIds.has(id));
        if (appState.scopeTab === 'supplement' && !n.isSupplement) match = false;
        if (appState.scopeTab === 'bridges' && !hasMatchingBridge) match = false;
        if (appState.activeVolId && n.volId !== appState.activeVolId) match = false;
        if (appState.activeDiscId && n.discId !== appState.activeDiscId) match = false;
        if (appState.activeTrail !== 'all' && !hasMatchingBridge) match = false;
        if (q) {
          const sHay = `${n.code} ${n.title} ${n.volName} ${n.discName}`.toLowerCase();
          if (!sHay.includes(q) && !hasMatchingBridge) match = false;
        }

        let h = match ? 0.95 : 0.10;
        if ((appState.selectedBridge && appState.selectedBridge.materialNode.index === i) || appState.portalBridge?.materialNode.index === i || appState.selectedBook?.id === n.code) {
          h = 2.2;
        } else if (n.isHub && hasMatchingBridge && appState.syzygyOn) {
          h = Math.max(h, 1.55);
        }
        pHigh.array[i] = h;
      });
      pHigh.needsUpdate = true;

      // Update spiritual anchor brightness.
      const showSpiritualPoints = appState.syzygyOn || appState.dimension !== 'omnia';
      SYZYGY_BRIDGES.forEach((b, i) => {
        if (!showSpiritualPoints || !bridgeAllowed(b) || (appState.dimension === 'umbra' && !b.hasCoordinates)) {
          sHigh.array[i] = -1;
          return;
        }
        const isSel = appState.selectedBridge && appState.selectedBridge.id === b.id;
        const ok = matchingBridgeIds.has(b.id);
        sHigh.array[i] = isSel ? 2.2 : (ok ? 1.45 : 0.14);
      });
      sHigh.needsUpdate = true;

      // Update Micro-Dust Brightness
      for (let i = 0; i < DUST_COUNT; i++) {
        const d = dustParticles[i];
        const vId = VOLUMES[d.vIdx].id;
        const dim = (appState.activeVolId && appState.activeVolId !== vId) || appState.activeTrail !== 'all' || q.length > 0;
        dHigh.array[i] = dim ? 0.15 : 0.54;
      }
      dHigh.needsUpdate = true;

      // Update Top Banner Pill
      const bannerPill = document.getElementById('banner-pill');
      bannerPill.textContent = appState.syzygyOn
        ? `◐ 朔望叠影开启 · ${matchingBridgeIds.size} 道精选星桥${appState.portalBridge ? ' · 1 道自选星桥' : ''}`
        : `○ 单界纯净观测模式`;

      renderBridgesIndexList(matchingBridgeIds);
      document.getElementById('stats-bridges').textContent = String(SYZYGY_BRIDGES.filter(bridgeAllowed).length);
    }

    // ============================================================================
    // 9. RENDER LEFT ATLAS TREE & RIGHT DUAL-PANE SYZYGY CODEX
    // ============================================================================
    function renderLeftAtlasTree() {
      const container = document.getElementById('atlas-tree');
      container.innerHTML = '';

      if (appState.scopeTab === 'reading') {
        const heading=document.createElement('p'); heading.className='syzygy-directory-heading';
        heading.textContent='跨学科阅读 · 原书选读 68 篇'; container.append(heading);
        const q=appState.searchQuery.trim().normalize('NFKC').toLocaleLowerCase();
        let visiblePaths=0;
        for (const path of readingPaths) {
          const entries=path.entries.map(id=>book.entries.find(entry=>entry.id === id)).filter(Boolean)
            .filter(entry=>!q || `${entry.id} ${entry.title} ${entry.topic}`.normalize('NFKC').toLocaleLowerCase().includes(q));
          if (!entries.length) continue;
          visiblePaths++;
          const section=document.createElement('details'); section.className='syzygy-bridge-group';
          section.open=!!q || appState.openReadingPaths.has(path.id);
          const label=document.createElement('summary'); label.className='syzygy-directory-heading';
          label.textContent=`${path.title} · ${entries.length}`;
          label.addEventListener('click',()=>{if(q)return;if(section.open)appState.openReadingPaths.delete(path.id);else appState.openReadingPaths.add(path.id);});
          section.append(label);
          entries.forEach(entry=>{
            const button=document.createElement('button'); button.className='syzygy-directory-row';
            button.innerHTML=`<b>${escapeHTML(entry.title)}</b><span>${escapeHTML(entry.id)} · PDF 第 ${escapeHTML(entry.page)} 页</span>`;
            button.addEventListener('click',()=>fullAtlas.selectBook(entry.id)); section.append(button);
          });
          container.append(section);
        }
        if (!visiblePaths) {const empty=document.createElement('p');empty.className='syzygy-reference';empty.textContent='没有匹配的选读条目。';container.append(empty);}
        return;
      }
      if (appState.scopeTab === 'bridges') {
        const heading = document.createElement('p');
        heading.className = 'syzygy-directory-heading'; heading.textContent = '心物对读 · 已整理线索'; container.append(heading);
        let groupCount = 0;
        SIDERA_CLUSTERS.forEach(cluster => {
          const bridges = SYZYGY_BRIDGES.filter(b => b.sideraCluster === cluster.id && bridgeMatchesFilter(b));
          if (!bridges.length) return;
          groupCount++;
          const section = document.createElement('details'); section.className = 'syzygy-bridge-group';
          section.open = !!appState.searchQuery.trim() || appState.openBridgeClusters.has(cluster.id);
          const label = document.createElement('summary'); label.className = 'syzygy-directory-heading';
          label.textContent = `${cluster.name} · ${bridges.length}`;
          label.addEventListener('click', () => {
            if (appState.searchQuery.trim()) return;
            if (section.open) appState.openBridgeClusters.delete(cluster.id);
            else appState.openBridgeClusters.add(cluster.id);
          });
          section.append(label);
          bridges.forEach(b => {
            const button = document.createElement('button'); button.className = 'syzygy-directory-row';
            button.innerHTML = `<b>${escapeHTML(b.shortLabel)}</b><span>${escapeHTML(b.id)} · ${escapeHTML(b.physis.id)}</span>`;
            button.addEventListener('click', () => selectSyzygyBridge(b,true)); section.append(button);
          });
          container.append(section);
        });
        if (!groupCount) {
          const empty = document.createElement('p'); empty.className = 'syzygy-reference';
          empty.textContent = '没有符合当前筛选的精选星桥。'; container.append(empty);
        }
        return;
      }
      if (appState.scopeTab === 'supplement' || appState.dimension !== 'omnia' || appState.searchQuery.trim()) {
        fullAtlas.renderDirectory(); return;
      }

      if (appState.dimension === 'umbra') {
        const hdr = document.createElement('div');
        hdr.className = 'font-mono-tech text-[10px] text-[#d6b678] tracking-wider uppercase mb-1.5';
        hdr.textContent = `◇ 民俗与个案线索 (${SYZYGY_BRIDGES.filter(bridgeAllowed).length})`;
        container.appendChild(hdr);

        SYZYGY_BRIDGES.filter(bridgeAllowed).forEach(b => {
          const active = appState.selectedBridge && appState.selectedBridge.id === b.id;
          const btn = document.createElement('button');
          btn.className = `w-full text-left px-2.5 py-2 rounded-[3px] border transition ${
            active ? 'bg-[#d6b678]/20 border-[#d6b678]/60 text-white' : 'border-transparent hover:bg-white/5 text-[#d4cbbd]'
          }`;
          btn.innerHTML = `
            <div class="text-xs font-medium">${escapeHTML(b.shortLabel)}</div>
            <div class="font-mono-tech text-[10px] text-[#9e9688] mt-0.5">${escapeHTML(b.umbraGeo.place)}${b.hasCoordinates ? '' : ' · 未标坐标'}</div>
          `;
          btn.addEventListener('click', () => selectSyzygyBridge(b, true));
          container.appendChild(btn);
        });
        return;
      }

      if (appState.dimension === 'sidera') {
        const hdr = document.createElement('div');
        hdr.className = 'font-mono-tech text-[10px] text-[#c4b5fd] tracking-wider uppercase mb-1.5';
        hdr.textContent = '+ 五大跨文化意识母题星群';
        container.appendChild(hdr);

        SIDERA_CLUSTERS.forEach(cl => {
          const box = document.createElement('div');
          box.className = 'pb-2 border-b border-[#d6b678]/12';
          const children = SYZYGY_BRIDGES.filter(b => b.sideraCluster === cl.id && bridgeAllowed(b));
          box.innerHTML = `
            <div class="flex items-center justify-between text-xs font-semibold text-[#ede6ff] py-1">
              <span>${cl.name}</span>
              <span class="font-mono-tech text-[10px] text-[#b692f6]">${children.length}</span>
            </div>
          `;
          children.forEach(b => {
            const btn = document.createElement('button');
            btn.className = 'w-full text-left py-1 px-2 text-[11.5px] text-[#b0a89c] hover:text-white hover:bg-white/5 rounded-[2px] flex items-center justify-between';
            btn.innerHTML = `<span class="truncate">${escapeHTML(b.shortLabel)}</span><span class="font-mono-tech text-[9.5px] text-[#d6b678]">↗</span>`;
            btn.addEventListener('click', () => selectSyzygyBridge(b, true));
            box.appendChild(btn);
          });
          container.appendChild(box);
        });
        return;
      }

      // Default OMNIA 5 Heterogeneous Volumes + Supplement Directory
      VOLUMES.forEach(vol => {
        const sec = document.createElement('div');
        sec.className = 'pb-2.5 border-b border-[#d6b678]/12 last:border-none';

        const volActive = appState.activeVolId === vol.id && !appState.activeDiscId;
        const vBtn = document.createElement('button');
        vBtn.className = `w-full flex items-center justify-between px-2 py-1.5 rounded-[3px] text-left transition ${
          volActive ? 'bg-[#d6b678]/20 text-white' : 'text-[#e6dfd1] hover:bg-white/5'
        }`;
        vBtn.innerHTML = `
          <span class="flex items-center gap-2 text-xs font-semibold">
            <span class="w-2 h-2 rounded-full" style="background:${vol.color}; box-shadow:0 0 8px ${vol.color}"></span>
            <span>${vol.num} · ${vol.name}</span>
            ${vol.isWormhole ? '<span class="text-[9.5px] px-1 border border-[#b692f6]/50 text-[#d8b4fe]">星门</span>' : ''}
          </span>
          <span class="font-mono-tech text-[10px] text-[#d6b678]/80">${vol.totalNodes}</span>
        `;
        vBtn.addEventListener('click', () => focusOmniaVolume(vol.id));
        sec.appendChild(vBtn);

        const dWrap = document.createElement('div');
        dWrap.className = 'mt-1 pl-2.5 space-y-0.5';
        vol.disciplines.forEach(disc => {
          if (appState.scopeTab === 'supplement' && !disc.isSupplement) return;

          const dActive = appState.activeDiscId === disc.id;
          const dBtn = document.createElement('button');
          dBtn.className = `w-full flex items-center justify-between px-2 py-1 rounded-[2px] text-[11.5px] transition ${
            dActive ? 'bg-[#d6b678]/22 text-[#fff6e0] border-l-2 border-[#d6b678]' : 'text-[#9e9688] hover:text-[#f3ece0] hover:bg-white/5'
          }`;
          dBtn.innerHTML = `
            <span class="truncate ${disc.isSupplement ? 'text-[#52d1a2]' : ''}">${disc.name}</span>
            <span class="font-mono-tech text-[10px] opacity-80">${disc.count}</span>
          `;
          dBtn.addEventListener('click', () => focusOmniaDiscipline(vol.id, disc.id));
          dWrap.appendChild(dBtn);
        });
        sec.appendChild(dWrap);
        container.appendChild(sec);
      });
    }

    function renderDualPaneSyzygyCard(bridge) {
      renderBridgeCard(bridge, {
        root, confidence:CONFIDENCE_META, relation:RELATION_META, showF:appState.showF, tiers:appState.tiers, genre:appState.genre, book, bookEntries:book.entries,
        onSelectRelated(id) { const node = fullAtlas.getNode(id); if (node) fullAtlas.select(node, true); },
        onReadBook(id) { const node = fullAtlas.getNode(bridge.mythos.id); if (node) fullAtlas.openPortal(node,id); else flashToast('目录加载中，请稍候。'); },
        onJump(dim, item) {
          if (appState.dimension !== dim) switchDimension(dim, true);
          if (dim === 'umbra' && !item.hasCoordinates) return;
          const local = dim === 'omnia' ? item.materialNode.posOmnia3D : dim === 'sidera' ? item.posSideraHub : item.posUmbraPin;
          const world = local.clone().applyMatrix4(cosmosGroup.matrixWorld);
          if (dim === 'umbra') animateCameraTo(world.clone().normalize().multiplyScalar(EARTH_RADIUS + 185), world.clone().multiplyScalar(.35), 1050);
          else animateCameraTo(world.clone().add(new THREE.Vector3(0, 25, 170)), world, 950);
        }
      });
      fullAtlas.attachCuratedSuggestions(bridge);
      if (bridge && !bridge.readingLoaded) fullAtlas.hydrateCurated(bridge).then(loaded=>{
        if (loaded && appState.selectedBridge === bridge) renderDualPaneSyzygyCard(bridge);
      }).catch(error=>{
        if (appState.selectedBridge !== bridge) return;
        const message=document.createElement('p'); message.className='syzygy-reference';
        message.textContent=`完整正文读取失败：${error.message}，请重新选择这条星桥。`;
        document.getElementById('syzygy-card-container').append(message);
      });
    }

    function renderBridgesIndexList(matchingBridgeIds) {
      const listEl = document.getElementById('bridges-index-list');
      const countLbl = document.getElementById('bridge-count-label');
      listEl.innerHTML = '';

      const visibleBridges = SYZYGY_BRIDGES.filter(b => matchingBridgeIds.has(b.id));
      countLbl.textContent = `${visibleBridges.length} / ${SYZYGY_BRIDGES.filter(bridgeAllowed).length} BRIDGES`;

      visibleBridges.forEach(b => {
        const isSel = appState.selectedBridge && appState.selectedBridge.id === b.id;
        const confMeta = CONFIDENCE_META[b.confidence];
        const row = document.createElement('div');
        row.className = `bridge-row px-3 py-2 rounded-[3px] border border-[#d6b678]/15 b-hairline cursor-pointer transition border-l-2 ${
          isSel ? 'active-row bg-[#d6b678]/16 border-l-[#d6b678]' : 'hover:bg-white/5 border-l-transparent'
        }`;
        row.innerHTML = `
          <div class="flex items-center justify-between gap-2">
            <span class="font-serif-sc text-xs font-semibold t-heading text-[#f4ede0] truncate">${escapeHTML(b.shortLabel)}</span>
            <span class="font-mono-tech text-[9px] px-1.5 py-0.5 border rounded-[2px] shrink-0 ${confMeta.cls}">
              ${b.confidence}
            </span>
          </div>
          <div class="flex items-center justify-between mt-1 font-mono-tech text-[10px] t-muted text-[#968f82]">
            <span>${escapeHTML(b.id)} ⇄ ${escapeHTML(b.physis.code)}</span>
            <span>${escapeHTML(b.physis.volLabel.split('·')[1] || b.physis.volLabel)}</span>
          </div>
        `;
        row.addEventListener('click', () => selectSyzygyBridge(b, true));
        listEl.appendChild(row);
      });
    }

    // ============================================================================
    // 10. SELECTION & FOCUS CONTROLLERS
    // ============================================================================
    function selectSyzygyBridge(bridge, flyCamera = true) {
      if (!bridgeAllowed(bridge)) return;
      appState.restoringDeepLink=false;
      appState.pendingRoute=null;
      appState.selectedBridge = bridge;
      appState.selectedGraph = null;
      appState.selectedBook = null;
      clearPersonalPortal();
      fullAtlas.clearNeighborhood();
      fullAtlas.updatePoints();
      updateClassicLink();
      syncViewURL();
      renderDualPaneSyzygyCard(bridge);
      renderLeftAtlasTree();
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;

      setRightDrawerCollapsed(false);

      if (flyCamera) {
        if (appState.dimension === 'umbra') {
          if (!bridge.hasCoordinates) { flashToast('此条未记录坐标，可在目录与星络中阅读。'); return; }
          const pinW = bridge.posUmbraPin.clone().applyMatrix4(cosmosGroup.matrixWorld);
          animateCameraTo(pinW.clone().normalize().multiplyScalar(EARTH_RADIUS + 195), pinW.clone().multiplyScalar(0.3), 980);
        } else if (appState.dimension === 'sidera') {
          const hubW = bridge.posSideraHub.clone().applyMatrix4(cosmosGroup.matrixWorld);
          animateCameraTo(hubW.clone().add(new THREE.Vector3(0, 18, 185)), hubW, 950);
        } else {
          // Frame both the spiritual anchor and material star smoothly in OMNIA
          const matW = bridge.materialNode.curPos.clone().applyMatrix4(cosmosGroup.matrixWorld);
          const midTarget = appState.syzygyOn
            ? matW.clone().lerp(bridge.curAnchorPos.clone().applyMatrix4(cosmosGroup.matrixWorld), 0.35)
            : matW;
          animateCameraTo(midTarget.clone().add(new THREE.Vector3(0, 24, 245)), midTarget, 980);
        }
      }
    }

    function focusOmniaVolume(volId) {
      if (appState.dimension !== 'omnia') switchDimension('omnia', true);
      appState.activeVolId = volId;
      appState.activeDiscId = null;
      const b = SYZYGY_BRIDGES.find(x => x.physis.volId === volId && bridgeAllowed(x));
      if (b) {
        appState.selectedBridge = b;
        appState.selectedGraph = null; appState.selectedBook = null; clearPersonalPortal(); updateClassicLink(); syncViewURL();
        renderDualPaneSyzygyCard(b);
      }
      renderLeftAtlasTree();
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;

      const vol = VOLUMES.find(v => v.id === volId);
      if (vol) {
        const wc = vol.center.clone().applyMatrix4(cosmosGroup.matrixWorld);
        animateCameraTo(wc.clone().add(new THREE.Vector3(0, 28, 225)), wc, 980);
      }
    }

    function focusOmniaDiscipline(volId, discId) {
      if (appState.dimension !== 'omnia') switchDimension('omnia', true);
      appState.activeVolId = volId;
      appState.activeDiscId = discId;
      const b = SYZYGY_BRIDGES.find(x => x.physis.discId === discId && bridgeAllowed(x)) || SYZYGY_BRIDGES.find(x => x.physis.volId === volId && bridgeAllowed(x));
      if (b) {
        appState.selectedBridge = b;
        appState.selectedGraph = null; appState.selectedBook = null; clearPersonalPortal(); updateClassicLink(); syncViewURL();
        renderDualPaneSyzygyCard(b);
      }
      renderLeftAtlasTree();
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;

      const hub = DISC_HUB_MAP.get(discId);
      if (hub) {
        const wp = hub.curPos.clone().applyMatrix4(cosmosGroup.matrixWorld);
        animateCameraTo(wp.clone().add(new THREE.Vector3(0, 20, 165)), wp, 920);
      }
    }

    // ============================================================================
    // 11. 3D RAYCASTING (SPIRITUAL ANCHORS + 2,334 KNOWLEDGE STARS)
    // ============================================================================
    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 6.0;
    const mouseNDC = new THREE.Vector2(-99, -99);
    const tooltipEl = document.getElementById('celestial-tooltip');
    const reticleEl = document.getElementById('astrolabe-reticle');
    let downPt = { x: 0, y: 0 };

    renderer.domElement.addEventListener('pointerdown', (e) => {
      downPt = { x: e.clientX, y: e.clientY };
    });

    renderer.domElement.addEventListener('pointermove', (e) => {
      mouseNDC.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouseNDC.y = -(e.clientY / window.innerHeight) * 2 + 1;

      raycaster.setFromCamera(mouseNDC, camera);

      // 1. Prioritize Spiritual Motif / Umbra Pin Anchors if visible
      let hitResult = null;
      if (appState.syzygyOn || appState.dimension !== 'omnia') {
        const anchorHit = raycaster.intersectObject(spiritualAnchorPoints).find(hit => {
          const bridge = SYZYGY_BRIDGES[hit.index];
          return bridge && bridgeAllowed(bridge) && (appState.dimension !== 'umbra' || bridge.hasCoordinates);
        });
        if (anchorHit) {
          const b = SYZYGY_BRIDGES[anchorHit.index];
          hitResult = {
            kind: 'bridge',
            bridge: b,
            worldPos: b.curAnchorPos.clone().applyMatrix4(cosmosGroup.matrixWorld),
            coord: appState.dimension === 'umbra'
              ? `LAT ${b.umbraGeo.lat.toFixed(1)}° · LON ${b.umbraGeo.lon.toFixed(1)}°`
              : `SYZYGY · ${b.id}`,
            tag: 'MYTHOS × PHYSIS',
            title: b.mythos.title,
            sub: `${b.physis.volLabel} · ${CONFIDENCE_META[b.confidence].badge}`
          };
        }
      }

      // The full catalogue is drawn separately from the curated anchors.
      if (!hitResult) hitResult = fullAtlas.hit(raycaster);

      // 2. Otherwise check Primary Knowledge Stars
      if (!hitResult && appState.dimension === 'omnia') {
        const starHits = raycaster.intersectObject(primaryStarPoints);
        if (starHits.length > 0) {
          const node = PRIMARY_NODES[starHits[0].index];
          const candidates = SYZYGY_BRIDGES.filter(bridge => node.bridgeIds.includes(bridge.id)
            && bridgeAllowed(bridge) && (appState.matchingBridgeIds?.has(bridge.id) ?? true));
          const b = candidates.length === 1 ? candidates[0] : null;
          hitResult = {
            kind: 'star',
            node,
            bridge: b,
            worldPos: node.curPos.clone().applyMatrix4(cosmosGroup.matrixWorld),
            coord: `${node.code} · P.${node.page}`,
            tag: node.volName,
            title: node.title,
            sub: b ? `点击关联朔望手卷：${b.shortLabel}`
              : candidates.length > 1 ? `点击查看 ${candidates.length} 道精选对读` : `点击阅读：${node.discName}`
          };
        }
      }

      appState.hoveredTarget = hitResult;
      if (hitResult) {
        renderer.domElement.style.cursor = 'pointer';
        document.getElementById('tt-coord').textContent = hitResult.coord;
        document.getElementById('tt-tag').textContent = hitResult.tag;
        document.getElementById('tt-title').textContent = hitResult.title;
        document.getElementById('tt-sub').textContent = hitResult.sub;

        const tx = Math.min(window.innerWidth - 305, e.clientX + 18);
        const ty = Math.max(66, Math.min(window.innerHeight - 85, e.clientY - 12));
        tooltipEl.style.left = `${tx}px`;
        tooltipEl.style.top = `${ty}px`;
        tooltipEl.style.opacity = '1';
      } else {
        renderer.domElement.style.cursor = 'grab';
        tooltipEl.style.opacity = '0';
      }
    });

    renderer.domElement.addEventListener('pointerup', (e) => {
      if (Math.hypot(e.clientX - downPt.x, e.clientY - downPt.y) > 5) return;
      if (appState.hoveredTarget && appState.hoveredTarget.bridge) {
        selectSyzygyBridge(appState.hoveredTarget.bridge, true);
      } else if (appState.hoveredTarget?.kind === 'graph') {
        fullAtlas.select(appState.hoveredTarget.node, true);
      } else if (appState.hoveredTarget?.kind === 'star') {
        fullAtlas.selectBook(appState.hoveredTarget.node.code);
      }
    });

    // ============================================================================
    // 12. UI EVENT LISTENERS (TOP BAR, TRAILS, DRAWERS, DUAL THEME, SEARCH)
    // ============================================================================
    // 3-Module Switcher
    document.querySelectorAll('[data-dim]').forEach(btn => {
      btn.addEventListener('click', () => {
        appState.activeVolId = null;
        appState.activeDiscId = null;
        switchDimension(btn.getAttribute('data-dim'));
      });
    });

    // Prominent ◐ 朔望叠影 Toggle
    const btnSyzygy = document.getElementById('btn-syzygy-toggle');
    btnSyzygy.addEventListener('click', () => {
      appState.syzygyOn = !appState.syzygyOn;
      btnSyzygy.classList.toggle('active', appState.syzygyOn);
      syzygyUpperRing.visible = (appState.dimension === 'omnia' && appState.syzygyOn && !appState.is2DPlanisphere);
      userPortalMarker.visible = !!appState.portalBridge && appState.dimension === 'omnia' && appState.syzygyOn;
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;
      flashToast(appState.syzygyOn ? '已开启「◐ 朔望叠影」：心物双界折光弦实时耦合' : '已关闭朔望叠影：进入单界纯粹观测态');
    });

    // 3D Galaxy <-> 2D Planisphere Toggle
    const btnProj = document.getElementById('btn-proj-toggle');
    btnProj.addEventListener('click', () => {
      if (appState.dimension !== 'omnia') switchDimension('omnia', true);
      appState.is2DPlanisphere = !appState.is2DPlanisphere;
      btnProj.textContent = appState.is2DPlanisphere ? '3D 星系' : '2D 星盘';
      btnProj.classList.toggle('active', appState.is2DPlanisphere);
      omniaScaffold.visible = !appState.is2DPlanisphere;
      syzygyUpperRing.visible = appState.syzygyOn && !appState.is2DPlanisphere;
      cosmosGroup.rotation.y = 0;

      if (appState.is2DPlanisphere) {
        animateCameraTo(new THREE.Vector3(-12, 0, 650), new THREE.Vector3(-12, 0, 0), 980);
        flashToast('已展平为 2D 古典天体星盘');
      } else {
        animateCameraTo(CAM_OMNIA.pos, CAM_OMNIA.target, 980);
        flashToast('已恢复 3D 五卷异构星系');
      }
      appState.needsBridgeRebuild = true;
    });

    // Reset View Button
    document.getElementById('btn-reset-cam').addEventListener('click', () => {
      appState.activeVolId = null;
      appState.activeDiscId = null;
      appState.activeTrail = 'all';
      document.querySelectorAll('[data-trail]').forEach(t => t.classList.toggle('active', t.getAttribute('data-trail') === 'all'));
      renderLeftAtlasTree();
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;

      const preset = appState.dimension === 'umbra' ? CAM_UMBRA : (appState.dimension === 'sidera' ? CAM_SIDERA : CAM_OMNIA);
      animateCameraTo(preset.pos, preset.target, 950);
    });

    // Bottom 5 Curated Syzygy Trails
    document.querySelectorAll('[data-trail]').forEach(pill => {
      pill.addEventListener('click', () => {
        const trailId = pill.getAttribute('data-trail');
        appState.activeTrail = trailId;
        appState.activeVolId = null;
        appState.activeDiscId = null;

        document.querySelectorAll('[data-trail]').forEach(p => p.classList.toggle('active', p === pill));

        if (!appState.syzygyOn && trailId !== 'all') {
          appState.syzygyOn = true;
          btnSyzygy.classList.add('active');
        }

        if (trailId !== 'all') {
          const leadBridge = SYZYGY_BRIDGES.find(b => b.trail === trailId && bridgeAllowed(b));
          if (leadBridge) selectSyzygyBridge(leadBridge, true);
          else { updateHighlightsAndFilters(); renderLeftAtlasTree(); appState.needsBridgeRebuild = true; }
        } else {
          updateHighlightsAndFilters();
          renderLeftAtlasTree();
          appState.needsBridgeRebuild = true;
          const preset = appState.dimension === 'umbra' ? CAM_UMBRA : (appState.dimension === 'sidera' ? CAM_SIDERA : CAM_OMNIA);
          animateCameraTo(preset.pos, preset.target, 980);
        }
      });
    });

    // Left Scope Filter Tabs
    document.querySelectorAll('.scope-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.scope-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        appState.scopeTab = tab.getAttribute('data-scope');
        if (appState.scopeTab === 'volumes' && appState.dimension !== 'omnia') switchDimension('omnia');
        appState.activeVolId = null;
        appState.activeDiscId = null;
        renderLeftAtlasTree();
        updateHighlightsAndFilters();
        fullAtlas.updatePoints();
      });
    });

    // Collapsible Left & Right Panels
    const leftDrawer = document.getElementById('left-drawer');
    const rightDrawer = document.getElementById('right-drawer');
    const btnOpenLeft = document.getElementById('btn-open-left');
    const btnOpenRight = document.getElementById('btn-open-right');
    const contextBanner = document.getElementById('context-banner');

    function setLeftDrawerCollapsed(collapsed) {
      if (!collapsed && window.innerWidth < 768 && !rightDrawer.classList.contains('drawer-right-hidden')) {
        setRightDrawerCollapsed(true);
      }
      leftDrawer.classList.toggle('drawer-left-hidden', collapsed);
      btnOpenLeft.classList.toggle('hidden', !collapsed);
      btnOpenLeft.classList.toggle('inline-flex', collapsed);
      contextBanner.style.left = collapsed ? '20px' : '';
    }

    function setRightDrawerCollapsed(collapsed) {
      if (!collapsed && window.innerWidth < 768 && !leftDrawer.classList.contains('drawer-left-hidden')) {
        setLeftDrawerCollapsed(true);
      }
      rightDrawer.classList.toggle('drawer-right-hidden', collapsed);
      btnOpenRight.classList.toggle('hidden', !collapsed);
      btnOpenRight.classList.toggle('inline-flex', collapsed);
    }

    document.getElementById('btn-close-left').addEventListener('click', () => setLeftDrawerCollapsed(true));
    btnOpenLeft.addEventListener('click', () => setLeftDrawerCollapsed(false));
    document.getElementById('btn-close-right').addEventListener('click', () => setRightDrawerCollapsed(true));
    btnOpenRight.addEventListener('click', () => setRightDrawerCollapsed(false));

    // Right Scroll Dual-Theme Switcher: 深空星卷 vs 羊皮典籍
    const btnDarkTheme = document.getElementById('theme-btn-dark');
    const btnParchmentTheme = document.getElementById('theme-btn-parchment');

    btnDarkTheme.addEventListener('click', () => {
      rightDrawer.classList.remove('parchment-scroll');
      btnDarkTheme.className = 'px-2 py-0.5 rounded-[2px] bg-[#d6b678]/25 text-[#fff4d8] font-medium transition';
      btnParchmentTheme.className = 'px-2 py-0.5 rounded-[2px] text-[#9e9688] hover:text-white transition';
    });

    btnParchmentTheme.addEventListener('click', () => {
      rightDrawer.classList.add('parchment-scroll');
      btnParchmentTheme.className = 'px-2 py-0.5 rounded-[2px] bg-[#8c6218]/20 text-[#2b1d05] font-semibold transition';
      btnDarkTheme.className = 'px-2 py-0.5 rounded-[2px] text-[#6e6658] hover:text-[#12151c] transition';
    });

    // Live Search Input & Cmd+K Shortcut
    const searchInput = document.getElementById('codex-search');
    const btnClearQuery = document.getElementById('btn-clear-query');
    const mobileResults = document.getElementById('btn-mobile-results');
    mobileResults.addEventListener('click',()=>{ setRightDrawerCollapsed(true); setLeftDrawerCollapsed(false); });

    searchInput.addEventListener('input', () => {
      appState.searchQuery = searchInput.value;
      btnClearQuery.classList.toggle('hidden', appState.searchQuery.length === 0);
      mobileResults.hidden = appState.searchQuery.trim().length === 0;
      updateHighlightsAndFilters();
      fullAtlas.searchChanged();
      renderLeftAtlasTree();
      appState.needsBridgeRebuild = true;
    });

    btnClearQuery.addEventListener('click', () => {
      searchInput.value = '';
      appState.searchQuery = '';
      btnClearQuery.classList.add('hidden');
      mobileResults.hidden = true;
      updateHighlightsAndFilters();
      renderLeftAtlasTree();
      fullAtlas.searchChanged();
      appState.needsBridgeRebuild = true;
    });

    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setRightDrawerCollapsed(false);
        searchInput.focus();
      }
    });

    // Auto-collapse side drawers on compact mobile/tablet viewports
    if (window.innerWidth < 1024) {
      setLeftDrawerCollapsed(true);
      if (window.innerWidth < 768) setRightDrawerCollapsed(true);
    }

    window.addEventListener('resize', () => {
      if (window.innerWidth < 768 && !leftDrawer.classList.contains('drawer-left-hidden')
        && !rightDrawer.classList.contains('drawer-right-hidden')) setLeftDrawerCollapsed(true);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setPixelRatio(dpr);
      renderer.setSize(window.innerWidth, window.innerHeight);
      starUniforms.uPixelRatio.value = dpr;
    });

    // ============================================================================
    // 13. 60FPS ANIMATION, GPU/JS PARTICLE MORPHING & 3D LABEL PROJECTION LOOP
    // ============================================================================
    const tmpProj = new THREE.Vector3();
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let lastSoftwareFrame = 0;
    function toScreenXY(worldVec) {
      tmpProj.copy(worldVec).project(camera);
      if (tmpProj.z > 1.0) return null;
      return {
        x: (tmpProj.x * 0.5 + 0.5) * window.innerWidth,
        y: (-tmpProj.y * 0.5 + 0.5) * window.innerHeight
      };
    }

    function animateLoop(nowMs) {
      requestAnimationFrame(animateLoop);
      if (document.hidden || document.documentElement.dataset.astraiaActive === 'false') return;
      if (renderer.isSoftware && nowMs - lastSoftwareFrame < 32) return;
      lastSoftwareFrame = nowMs;
      const t = reducedMotion ? 0 : nowMs * 0.001;
      starUniforms.uTime.value = t;

      // 1. Camera Smooth Fly-To Interpolation
      if (appState.camAnim) {
        const u = Math.min((nowMs - appState.camAnim.startTime) / appState.camAnim.duration, 1);
        const ease = 1 - Math.pow(1 - u, 4);
        camera.position.lerpVectors(appState.camAnim.startPos, appState.camAnim.endPos, ease);
        controls.target.lerpVectors(appState.camAnim.startTarget, appState.camAnim.endTarget, ease);
        if (u >= 1) appState.camAnim = null;
      }

      // 2. Smoothly Morph All 5,334+ Particle Positions & Colors across OMNIA / UMBRA / SIDERA
      let positionsMoving = false;
      const pPos = primaryGeo.getAttribute('position').array;
      const pCol = primaryGeo.getAttribute('aColor').array;

      for (let i = 0; i < pCount; i++) {
        const n = PRIMARY_NODES[i];
        const targetP = appState.dimension === 'umbra'
          ? n.posUmbra3D
          : (appState.dimension === 'sidera'
              ? n.posSidera3D
              : (appState.is2DPlanisphere ? n.posOmnia2D : n.posOmnia3D));

        const targetC = appState.dimension === 'umbra'
          ? n.colUmbra
          : (appState.dimension === 'sidera' ? n.colSidera : n.colOmnia);

        const dx = targetP.x - n.curPos.x;
        const dy = targetP.y - n.curPos.y;
        const dz = targetP.z - n.curPos.z;

        if (dx * dx + dy * dy + dz * dz > 0.04) {
          positionsMoving = true;
          n.curPos.x += dx * 0.085;
          n.curPos.y += dy * 0.085;
          n.curPos.z += dz * 0.085;
          pPos[i * 3] = n.curPos.x;
          pPos[i * 3 + 1] = n.curPos.y;
          pPos[i * 3 + 2] = n.curPos.z;

          n.curCol.lerp(targetC, 0.09);
          pCol[i * 3] = n.curCol.r;
          pCol[i * 3 + 1] = n.curCol.g;
          pCol[i * 3 + 2] = n.curCol.b;
        }
      }
      if (positionsMoving) {
        primaryGeo.getAttribute('position').needsUpdate = true;
        primaryGeo.getAttribute('aColor').needsUpdate = true;

        // Morph Micro-Dust Particles in lockstep
        const dPos = dustGeo.getAttribute('position').array;
        const dCol = dustGeo.getAttribute('aColor').array;
        for (let i = 0; i < DUST_COUNT; i++) {
          const d = dustParticles[i];
          const tp = appState.dimension === 'umbra'
            ? d.pUmbra
            : (appState.dimension === 'sidera' ? d.pSidera : (appState.is2DPlanisphere ? d.p2D : d.pOmnia));
          const tc = appState.dimension === 'umbra'
            ? d.cUmbra
            : (appState.dimension === 'sidera' ? d.cSidera : d.cOmnia);

          dPos[i * 3] += (tp.x - dPos[i * 3]) * 0.085;
          dPos[i * 3 + 1] += (tp.y - dPos[i * 3 + 1]) * 0.085;
          dPos[i * 3 + 2] += (tp.z - dPos[i * 3 + 2]) * 0.085;

          dCol[i * 3] += (tc.r - dCol[i * 3]) * 0.09;
          dCol[i * 3 + 1] += (tc.g - dCol[i * 3 + 1]) * 0.09;
          dCol[i * 3 + 2] += (tc.b - dCol[i * 3 + 2]) * 0.09;
        }
        dustGeo.getAttribute('position').needsUpdate = true;
        dustGeo.getAttribute('aColor').needsUpdate = true;
      }

      // Morph the curated spiritual motif anchors.
      let anchorsMoving = false;
      const sPos = spiritualAnchorGeo.getAttribute('position').array;
      SYZYGY_BRIDGES.forEach((b, i) => {
        const tp = appState.dimension === 'umbra'
          ? b.posUmbraPin
          : (appState.dimension === 'sidera' ? b.posSideraHub : b.posOmniaSyzygy);
        if (b.curAnchorPos.distanceToSquared(tp) > 0.04) {
          anchorsMoving = true;
          b.curAnchorPos.lerp(tp, 0.09);
          sPos[i * 3] = b.curAnchorPos.x;
          sPos[i * 3 + 1] = b.curAnchorPos.y;
          sPos[i * 3 + 2] = b.curAnchorPos.z;
        }
      });
      if (anchorsMoving) {
        spiritualAnchorGeo.getAttribute('position').needsUpdate = true;
      }

      // Rebuild Cubic Bezier Photon Bridges when morphing settles or state toggles
      if (appState.needsBridgeRebuild) {
        rebuildSyzygyPhotonBridges();
        appState.needsBridgeRebuild = false;
      }
      if (positionsMoving || anchorsMoving) updateBridgeCurves();

      // 3. Celestial Orbital & Counter-Rotating Brass Gimbal Motion
      if (!reducedMotion && !appState.is2DPlanisphere && !appState.hoveredTarget) {
        cosmosGroup.rotation.y += appState.dimension === 'umbra' ? 0.00075 : 0.00042;
      }
      gimbalRingA.rotation.x = t * 0.28;
      gimbalRingA.rotation.y = t * 0.19;
      gimbalRingB.rotation.y = -t * 0.24;
      gimbalRingB.rotation.z = t * 0.17;
      portalRingOuter.rotation.z = -t * 0.15;
      portalRingInner.rotation.x = Math.sin(t * 0.5) * 0.35;
      portalRingInner.rotation.z = t * 0.32;

      // 4. Glide Photon Pulses along Cubic Bezier Syzygy Bridges
      activePhotonPulses.forEach(p => {
        const u = (t * p.speed + p.offset) % 1.0;
        const pt = p.curve.getPointAt(u);
        p.sprite.position.copy(pt);
        p.sprite.material.opacity = Math.sin(u * Math.PI) * 0.95;
      });

      controls.update();

      // 5. Project 3D Floating Plaques & Anchor Chips
      domAnchors.forEach(item => {
        if (item.type === 'omniaVol') {
          if (appState.dimension !== 'omnia') {
            item.el.style.opacity = '0';
            item.el.style.pointerEvents = 'none';
            return;
          }
          const wp = item.vol.center.clone().add(new THREE.Vector3(0, 20, 0)).applyMatrix4(cosmosGroup.matrixWorld);
          const sc = toScreenXY(wp);
          if (!sc) {
            item.el.style.opacity = '0';
          } else {
            item.el.style.left = `${sc.x}px`;
            item.el.style.top = `${sc.y}px`;
            item.el.style.opacity = (appState.activeVolId && appState.activeVolId !== item.vol.id) ? '0.28' : '0.96';
            item.el.style.pointerEvents = 'auto';
          }
        } else if (item.type === 'sideraCluster') {
          if (appState.dimension !== 'sidera') {
            item.el.style.opacity = '0';
            item.el.style.pointerEvents = 'none';
            return;
          }
          const wp = item.cl.center.clone().add(new THREE.Vector3(0, 22, 0)).applyMatrix4(cosmosGroup.matrixWorld);
          const sc = toScreenXY(wp);
          if (!sc) {
            item.el.style.opacity = '0';
          } else {
            item.el.style.left = `${sc.x}px`;
            item.el.style.top = `${sc.y}px`;
            item.el.style.opacity = '0.96';
            item.el.style.pointerEvents = 'auto';
          }
        } else if (item.type === 'bridgeAnchor') {
          const visible = (appState.dimension !== 'omnia' || (appState.syzygyOn && !appState.is2DPlanisphere))
            && bridgeAllowed(item.bridge) && (appState.dimension !== 'umbra' || item.bridge.hasCoordinates)
            && (appState.activeTrail === 'all' || item.bridge.trail === appState.activeTrail)
            && (!appState.searchQuery || appState.matchingBridgeIds?.has(item.bridge.id))
            && (appState.selectedBridge?.id === item.bridge.id || appState.hoveredTarget?.bridge?.id === item.bridge.id);
          if (!visible) {
            item.el.style.opacity = '0';
            item.el.style.pointerEvents = 'none';
            return;
          }
          const wp = item.bridge.curAnchorPos.clone().applyMatrix4(cosmosGroup.matrixWorld);
          // Back-face occlusion check on Umbra Earth globe
          if (appState.dimension === 'umbra') {
            const camToCenter = camera.position.clone().normalize();
            const pinNormal = wp.clone().normalize();
            if (pinNormal.dot(camToCenter) < 0.12) {
              item.el.style.opacity = '0';
              item.el.style.pointerEvents = 'none';
              return;
            }
          }
          const sc = toScreenXY(wp.clone().add(new THREE.Vector3(0, -13, 0)));
          if (!sc) {
            item.el.style.opacity = '0';
          } else {
            item.el.style.left = `${sc.x}px`;
            item.el.style.top = `${sc.y}px`;
            const isSel = appState.selectedBridge && appState.selectedBridge.id === item.bridge.id;
            item.el.style.opacity = isSel ? '1' : '0.82';
            item.el.style.pointerEvents = 'auto';
          }
        }
      });

      if (appState.portalBridge && appState.dimension === 'omnia' && appState.syzygyOn) {
        const point = toScreenXY(appState.portalBridge.curAnchorPos.clone().applyMatrix4(cosmosGroup.matrixWorld));
        userPortalLabel.hidden = !point;
        if (point) { userPortalLabel.style.left=`${point.x}px`; userPortalLabel.style.top=`${point.y-17}px`; }
      } else userPortalLabel.hidden = true;

      // 6. Position Brass Astrolabe Reticle on Hovered or Selected Anchor
      const reticleWorld = appState.hoveredTarget
        ? appState.hoveredTarget.worldPos
        : (appState.selectedBridge
            ? (appState.dimension === 'omnia'
                ? appState.selectedBridge.materialNode.curPos.clone().applyMatrix4(cosmosGroup.matrixWorld)
                : appState.selectedBridge.curAnchorPos.clone().applyMatrix4(cosmosGroup.matrixWorld))
            : null);

      if (reticleWorld) {
        const sc = toScreenXY(reticleWorld);
        if (sc) {
          reticleEl.style.left = `${sc.x}px`;
          reticleEl.style.top = `${sc.y}px`;
          reticleEl.style.opacity = '1';
        } else {
          reticleEl.style.opacity = '0';
        }
      } else {
        reticleEl.style.opacity = '0';
      }

      renderer.render(scene, camera);
    }

    // ============================================================================
    // 14. BOOTSTRAP ON WINDOW LOAD
    // ============================================================================
    buildWorldDOMAnchors();
    worldLabelsEl.appendChild(userPortalLabel);
    document.getElementById('stats-entries').textContent = book.entries.length.toLocaleString();
    document.getElementById('stats-subjects').textContent = book.subjects.length.toLocaleString();
    const fictionButton = document.getElementById('btn-fiction');
    function syncTierButtons() {
      fictionButton.setAttribute('aria-checked', String(!appState.showF));
      document.querySelectorAll('[data-tier]').forEach(button=>button.setAttribute('aria-pressed',String(appState.tiers.has(button.dataset.tier))));
    }
    function toggleTier(tier) {
      if (appState.tiers.has(tier)) appState.tiers.delete(tier); else appState.tiers.add(tier);
      appState.showF = appState.tiers.has('F'); syncTierButtons();
      const selectedHidden = (appState.selectedBridge && !bridgeAllowed(appState.selectedBridge))
        || (appState.selectedGraph && (!appState.tiers.has(appState.selectedGraph.credibility_tier)
          || (!appState.showF && appState.selectedGraph.is_fictional_quarantine)));
      if (selectedHidden) {
        const next = SYZYGY_BRIDGES.find(bridgeAllowed);
        if (next) selectSyzygyBridge(next,false);
        else { appState.selectedBridge=null; appState.selectedGraph=null; appState.selectedBook=null; clearPersonalPortal(); fullAtlas.clearNeighborhood(); renderDualPaneSyzygyCard(null); }
      } else if (appState.selectedBridge) renderDualPaneSyzygyCard(appState.selectedBridge);
      document.querySelectorAll('#syzygy-card-container a[href]').forEach(link=>{
        const target=new URL(link.href,window.location.href);
        if (target.origin !== window.location.origin || target.pathname !== root || !target.searchParams.has('view')) return;
        target.searchParams.set('tiers',tierOrder.filter(item=>appState.tiers.has(item)).join(','));
        if (appState.showF) target.searchParams.set('fiction','1'); else target.searchParams.delete('fiction');
        link.href=target.href;
      });
      fullAtlas.refreshFilters(); updateHighlightsAndFilters(); renderLeftAtlasTree(); updateClassicLink();
      syncViewURL();
      appState.needsBridgeRebuild = true;
    }
    syncTierButtons();
    const genreSelect = document.getElementById('genre-filter');
    genreSelect.value=appState.genre;
    genreSelect.addEventListener('change',()=>{
      appState.genre=genreSelect.value;
      const hiddenBridge=appState.selectedBridge && !bridgeAllowed(appState.selectedBridge);
      const hiddenNode=appState.selectedGraph && !fullAtlas.isVisible(appState.selectedGraph);
      if (hiddenBridge || hiddenNode) {
        appState.selectedBridge=null; appState.selectedGraph=null; appState.selectedBook=null;
        clearPersonalPortal(); fullAtlas.clearNeighborhood(); renderDualPaneSyzygyCard(null);
      }
      appState.scopeTab='supplement';
      document.querySelectorAll('.scope-tab').forEach(tab=>tab.classList.toggle('active',tab.dataset.scope === 'supplement'));
      fullAtlas.refreshFilters(); updateHighlightsAndFilters(); renderLeftAtlasTree(); updateClassicLink(); syncViewURL();
      appState.needsBridgeRebuild=true;
    });
    fictionButton.addEventListener('click', () => toggleTier('F'));
    document.querySelectorAll('[data-tier]').forEach(button=>button.addEventListener('click',()=>toggleTier(button.dataset.tier)));
    let routeSequence=0;
    window.addEventListener('astraia:navigate',event=>{
      const params=new URL(event.detail).searchParams, sequence=++routeSequence;
      appState.restoringDeepLink=true;
      appState.pendingRoute={story:params.get('story'),entry:params.get('entry')};
      appState.selectedBridge=null; appState.selectedGraph=null; appState.selectedBook=null;
      clearPersonalPortal(); fullAtlas.clearNeighborhood();
      document.getElementById('syzygy-card-container').innerHTML='<p class="syzygy-reference" role="status">正在定位资料…</p>';
      appState.tiers = params.has('tiers') ? new Set(tierOrder.filter(tier=>params.get('tiers').split(',').includes(tier)))
        : new Set(tierOrder.filter(tier=>tier !== 'F' || params.get('fiction') === '1'));
      appState.showF=appState.tiers.has('F');
      appState.genre=Object.hasOwn(genreLabels,params.get('genre')) ? params.get('genre') : 'ALL';
      genreSelect.value=appState.genre; syncTierButtons();
      const dimension=['umbra','sidera','omnia'].includes(params.get('dim')) ? params.get('dim') : 'omnia';
      appState.classicView=['map','graph','life'].includes(params.get('return')) ? params.get('return')
        : dimension === 'umbra' ? 'map' : dimension === 'sidera' ? 'graph' : 'life';
      if (appState.dimension !== dimension) switchDimension(dimension,false,true);
      fullAtlas.refreshFilters(); updateHighlightsAndFilters();
      fullAtlas.start().then(()=>{
        if (sequence !== routeSequence) return;
        appState.restoringDeepLink=false;
        const storyId=params.get('story'), entryId=params.get('entry'), node=storyId && fullAtlas.getNode(storyId);
        const missing=message=>{appState.pendingRoute=null;document.getElementById('syzygy-card-container').textContent=message;updateClassicLink();flashToast(message);};
        if (node && !fullAtlas.isVisible(node)) { missing('该条目被当前筛选隐藏。'); return; }
        if (node && entryId && book.entries.some(entry=>entry.id === entryId)) fullAtlas.openPortal(node,entryId);
        else if (node && entryId) {fullAtlas.select(node,true);flashToast('未找到该知识条目，请重新选择对读。');}
        else if (node) {
          const curated=SYZYGY_BRIDGES.find(bridge=>bridge.mythos.id === storyId && bridgeAllowed(bridge));
          if (curated) selectSyzygyBridge(curated,true); else fullAtlas.select(node,true);
        } else if (entryId && book.entries.some(entry=>entry.id === entryId)) fullAtlas.selectBook(entryId);
        else if (!storyId && !entryId) {
          appState.pendingRoute=null;
          const bridge=SYZYGY_BRIDGES.find(bridgeAllowed);
          if (bridge) selectSyzygyBridge(bridge,false);
          else {appState.selectedBridge=null;appState.selectedGraph=null;appState.selectedBook=null;renderDualPaneSyzygyCard(null);}
        } else missing('未找到对应资料，请从目录重新选择。');
        renderLeftAtlasTree(); updateClassicLink(); syncViewURL();
      }).catch(error=>flashToast(`图谱载入失败：${error.message}`));
    });
    announceViewReady();
    renderLeftAtlasTree();
    renderDualPaneSyzygyCard(appState.selectedBridge);
    if (appState.restoringDeepLink) document.getElementById('syzygy-card-container').innerHTML='<p class="syzygy-reference" role="status">正在定位资料…</p>';
    updateHighlightsAndFilters();
    rebuildSyzygyPhotonBridges();
    const initial = new URL(window.location.href).searchParams;
    const dimension = ['umbra','sidera','omnia'].includes(initial.get('dim')) ? initial.get('dim') : 'omnia';
    if (dimension !== 'omnia') switchDimension(dimension, false, true);
    else updateClassicLink();
    document.getElementById('syzygy-loading')?.remove();
    requestAnimationFrame(animateLoop);
    setTimeout(() => fullAtlas.start().then(() => {
      renderLeftAtlasTree();
      if (appState.selectedBridge) renderDualPaneSyzygyCard(appState.selectedBridge);
      if (!appState.restoringDeepLink || routeSequence) return;
      const storyId = initial.get('story');
      const entryId = initial.get('entry');
      appState.restoringDeepLink = false;
      const missing = message => {
        appState.pendingRoute=null;
        appState.selectedBridge=null; appState.selectedGraph=null; appState.selectedBook=null;
        clearPersonalPortal(); fullAtlas.clearNeighborhood(); updateHighlightsAndFilters(); updateClassicLink();
        document.getElementById('syzygy-card-container').textContent=message; flashToast(message);
      };
      if (storyId) {
        const curated = SYZYGY_BRIDGES.find(b => b.mythos.id === storyId && bridgeAllowed(b));
        const node = fullAtlas.getNode(storyId);
        if (node && !fullAtlas.isVisible(node)) missing('该条目被当前信源筛选隐藏，请调整筛选。');
        else if (node && entryId && book.entries.some(entry=>entry.id === entryId)) fullAtlas.openPortal(node,entryId);
        else if (node && entryId) { fullAtlas.select(node,true); flashToast('未找到该知识条目，请重新选择对读。'); }
        else if (curated) selectSyzygyBridge(curated,true);
        else if (node) fullAtlas.select(node,true);
        else missing('未找到该图谱条目，请从目录重新选择。');
      } else if (entryId) {
        if (book.entries.some(entry=>entry.id === entryId)) fullAtlas.selectBook(entryId);
        else missing('未找到该知识条目，请从目录重新选择。');
      }
    }).catch(error => {
      console.error('完整图谱载入失败',error);
      const container = document.getElementById('atlas-tree');
      container.textContent = `完整图谱载入失败：${error.message}，请刷新后重试。`;
      flashToast('完整图谱暂时不可用，请刷新后重试。');
    }), 100);
