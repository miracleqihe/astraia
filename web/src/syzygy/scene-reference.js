import * as THREECore from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { feature } from 'topojson-client';
import worldAtlas from 'world-atlas/countries-110m.json';
import '@fontsource/cormorant-garamond/latin-600.css';
import '@fontsource/jetbrains-mono/latin-400.css';
import '@fontsource/noto-serif-sc/400.css';
import '@fontsource/noto-serif-sc/600.css';
import '../styles.css';
import './utilities.css';
import './overrides.css';
import { createSyzygyRenderer } from './renderer';
import { createFullAtlas } from './fullAtlas';
import { initSyzygyShell } from './shell';
import { isCompactViewport } from '../compactViewport';
import { genreContract, genreLabels } from './narrativeMetadata';
import { announceViewReady } from '../viewRouter';
import { TIER_META, engravingFrieze, engravingPatternForVolume, syncEngravingBeam, tierSeal } from '../engraving';
import readingPaths from './reading-paths.json';
import { renderBridgeCard } from './bridgeCard';
import {
  DEFAULT_MEMBRANE_DEPTH, clampDepth, computeLunarSyzygy, isBeyondMembrane,
  loadObserverTrace, realmById, realmForDepth, recordObservation, summarizeObserverBalance,
} from './realms';
import { createMembraneLayer } from './membrane';
import { createMembraneRefraction } from './membraneRefraction';
import { createMembraneAudio } from './membraneAudio';
import {
  sampleOmniaGalaxyPoint,
  createOmniaGalaxySculpts,
  animateOmniaGalaxies,
} from './constellationSculpts';
import { SIDERA_V3_DESIGN, sampleV3Anchor, sampleV3Dust, createSideraV3Sculpts } from './sideraV3Sculpts';
import { loadLexiconShard, loadTaxonomy } from './lexiconShards.js';
import {
  computeZodiacBridgeLayout,
  buildLeadAsterismSegments,
  selectVisibleOmniaCurves,
  selectVisibleSideraCurves,
  computeAdaptiveAnchorStyle,
} from './bridgeLayout.js';
import { renderTaxonomyExplorerView } from './taxonomyExplorer.js';

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
      { en: 'SATURNIAN SHIELD', color: '#e8a856', altColor: '#d97736', center: [0,-166,12], morphDesc: '多轨同心护盾星环' },
      { en: 'FIVE-ARM SPIRAL', color: '#64b5f6', altColor: '#38bdf8', center: [162,-50,-10], morphDesc: '五旋臂星系' },
      { en: 'GEODESIC CRYSTAL', color: '#52d1a2', altColor: '#2dd4bf', center: [102,136,12], morphDesc: '测地晶格与双轴浑天环' },
      { en: 'TORUS MANIFOLD', color: '#9d8df7', altColor: '#c084fc', center: [-102,136,-10], morphDesc: '环面星系' },
      { en: 'ROSE WORMHOLE PORTAL', color: '#f3d08a', altColor: '#f4978e', center: [-162,-50,12], morphDesc: '玫瑰星冠与星门', isWormhole: true },
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
      { id: 'sid_myth', name: '创世灾变与天体神话星群', shortName: '创世天象', code: 'MYTHOS · I', color: '#f5d487', center: new THREE.Vector3(0, 162, 14) },
      { id: 'sid_hag', name: '暗夜梦魇与幻影感知星群', shortName: '梦魇幻影', code: 'MYTHOS · II', color: '#a3c6ff', center: new THREE.Vector3(-174, 46, 16) },
      { id: 'sid_witch', name: '妖术恐慌与契约附体星群', shortName: '妖术附体', code: 'MYTHOS · III', color: '#c8a6ff', center: new THREE.Vector3(-112, -144, -12) },
      { id: 'sid_crypt', name: '山海精怪与器物骚灵星群', shortName: '山海精怪', code: 'MYTHOS · IV', color: '#ff5238', center: new THREE.Vector3(112, -144, 12) },
      { id: 'sid_liminal', name: '现代阈限与规则展演星群', shortName: '现代传说', code: 'MYTHOS · V', color: '#e8cf82', center: new THREE.Vector3(174, 46, -14) }
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

    // Epistemic Confidence Status Dictionary (mineral pigments calibrated for both Obsidian & Parchment)
    const CONFIDENCE_META = {
      CONFIRMED: {
        badge: '● 个案关联已证实',
        cls: 'syzygy-badge-confirmed'
      },
      UNVERIFIED: {
        badge: '◐ 个案关联待核实',
        cls: 'syzygy-badge-unverified'
      },
      DEBUNKED: {
        badge: '✕ 个案关联已驳回',
        cls: 'syzygy-badge-refuted'
      },
      CONTEXT: {
        badge: '◇ 专题对读',
        cls: 'syzygy-badge-context'
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
      const genre = genreContract(node);
      const explicitGenres = ['MYTH', 'FABULATE', 'FOLKTALE', 'MEMORATE', 'HISTORICAL'];
      const readingGenre = node.reading?.kind === 'legend' && explicitGenres.includes(genre)
        ? genreLabels[genre] : typeLabels[node.reading?.kind] ?? '资料';
      return { ...b, confidence, hasCoordinates,
        umbraGeo:{lat:hasCoordinates ? sp.lat : null, lon:hasCoordinates ? sp.lng : null, place:sp?.location_name || '未记录地点'},
        mythos:{...node, genre_contract:genre, genre:readingGenre, taxonomies:codes,
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

    // OMNIA galaxy & SIDERA constellation sculpt generators imported from ./constellationSculpts

    // ============================================================================
    // 3. GENERATE 2,266 PRIMARY STARS + 68 SUPPLEMENT STARS + 3,000 MICRO-DUST
    // ============================================================================
    const PRIMARY_NODES = [];
    const DISC_HUB_MAP = new Map(); // discId -> hub star node
    const bootBookMatchCounts = bridgeDataset.match_summary?.book_match_counts ?? {};

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
          const posOmnia3D = sampleOmniaGalaxyPoint(vIdx, dIdx, s, disc.count, isHub, sRand, sGauss).add(vol.center);

          // 2D Astrolabe Planisphere Coordinate
          const r2D = isHub ? 142 : 90 + Math.pow((s + sRand()) / disc.count, 0.7) * 168;
          const th2D = isHub ? angCursor + dSpan * 0.5 : angCursor + sRand() * dSpan;
          const posOmnia2D = new THREE.Vector3(Math.cos(th2D) * r2D, Math.sin(th2D) * r2D * 0.92, 0);

          // UMBRA 3D Earth Coordinate
          const posUmbra3D = sampleUmbraContinentPoint();

          // SIDERA Non-Euclidean Motif Coordinate
          const sideraCl = SIDERA_CLUSTERS[(vIdx + dIdx) % 5];
          const posSidera3D = sampleV3Dust(sideraCl.id, s, sRand).add(sideraCl.center);

          const colOmnia = new THREE.Color(s % 3 === 0 ? vol.altColor : vol.color);
          if (isHub) colOmnia.lerp(new THREE.Color('#ffffff'), 0.32);

          const colUmbra = new THREE.Color(s % 4 === 0 ? '#64b5f6' : '#d6b678').lerp(new THREE.Color('#475569'), 0.35);
          const colSidera = new THREE.Color(sideraCl.color);

          // Only explicit crosswalks are linked; other stars keep their real identity.
          const matchedBridges = SYZYGY_BRIDGES.filter(b => b.physis.code === entry.id);
          const semanticMatchCount = Number(bootBookMatchCounts[entry.id]) || 0;

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
            semanticMatchCount,
            posOmnia3D,
            posOmnia2D,
            posUmbra3D,
            posSidera3D,
            curPos: posOmnia3D.clone(),
            colOmnia,
            colUmbra,
            colSidera,
            curCol: colOmnia.clone(),
            size: isHub || matchedBridges.length ? 21.0 : (semanticMatchCount > 0 ? 11.5 : (s < 4 ? 9.5 : 5.4 + Math.pow(sRand(), 2.0) * 5.2)),
            spike: isHub || matchedBridges.length ? 1.0 : (semanticMatchCount > 0 ? 0.48 : (s < 3 ? 0.38 : 0.0)),
            phase: sRand() * Math.PI * 2
          };

          PRIMARY_NODES.push(node);
          if (isHub) DISC_HUB_MAP.set(disc.id, node);
          starIndexCounter++;
        }
        angCursor += dSpan;
      });
    });

    VOLUMES.forEach(vol => {
      vol.disciplines.forEach(disc => {
        disc.connectedEntries = PRIMARY_NODES.filter(node => node.discId === disc.id && node.semanticMatchCount > 0).length;
      });
    });

    // Attach coordinates in all three dimensions, distributing outer zodiac anchors across 5 stratified orbital lanes.
    SYZYGY_BRIDGES.forEach(bridge => {
      const targetHub = PRIMARY_NODES.find(node => node.code === bridge.physis.code);
      if (!targetHub) throw new Error(`找不到关联知识条目：${bridge.physis.code}`);
      bridge.materialNode = targetHub;
      bridge.parentAng = Math.atan2(targetHub.posOmnia3D.y, targetHub.posOmnia3D.x);
    });

    const orderedBridges = [...SYZYGY_BRIDGES].sort((a, b) =>
      a.parentAng - b.parentAng || a.sideraCluster.localeCompare(b.sideraCluster) || a.id.localeCompare(b.id)
    );
    computeZodiacBridgeLayout(orderedBridges, {
      sideraClusters: SIDERA_CLUSTERS,
      volumes: VOLUMES,
    });

    SYZYGY_BRIDGES.forEach(bridge => {
      // Exact Geographic Lat/Lon Pin on UMBRA 3D Globe
      bridge.posUmbraPin = bridge.hasCoordinates ? latLonToVec3(bridge.umbraGeo.lat, bridge.umbraGeo.lon, EARTH_RADIUS + 4.5) : new THREE.Vector3();

      // Exact Motif Constellation Hub in SIDERA
      const cl = SIDERA_CLUSTERS.find(c => c.id === bridge.sideraCluster) || SIDERA_CLUSTERS[0];
      const clusterBridges = SYZYGY_BRIDGES.filter(item => item.sideraCluster === bridge.sideraCluster);
      const clusterIndex = clusterBridges.indexOf(bridge);
      bridge.posSideraHub = sampleV3Anchor(cl.id, clusterIndex, clusterBridges.length).add(cl.center);

      bridge.curAnchorPos = bridge.posOmniaSyzygy.clone();
    });

    // ============================================================================
    // 4. THREE.JS SCENE, RETINA RENDERER & CUSTOM GLSL ANTI-BLUR STAR SHADER
    // ============================================================================
    const viewportEl = document.getElementById('webgl-viewport');
    const leftDrawer = document.getElementById('left-drawer');
    const rightDrawer = document.getElementById('right-drawer');
    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 4500);
    function getClearViewportMetrics() {
      const w = Math.max(1, window.innerWidth), h = Math.max(1, window.innerHeight);
      const compact = w <= 760 || (w <= 1100 && h <= 500);
      // Reserve room for the title as well as the navigation on short screens.
      const topOcc = compact ? Math.min(Math.round(h * 0.45), h <= 500 ? (w >= 600 ? 130 : 170) : 220) : 56;
      const bottomOcc = document.body.dataset.observatoryPanel ? 145 : 64;
      if (w >= 768) {
        const leftOpen = leftDrawer && !leftDrawer.classList.contains('drawer-left-hidden');
        const rightOpen = rightDrawer && !rightDrawer.classList.contains('drawer-right-hidden');
        const leftOcc = leftOpen ? 262 : 0;
        const spreadOn = rightDrawer && rightDrawer.classList.contains('codex-spread');
        const rightOcc = rightOpen ? (spreadOn ? Math.min(760, Math.round(w * 0.56)) : 438) : 0;
        const rawShiftX = Math.round((rightOcc - leftOcc) / 2);
        const shiftX = Math.max(-Math.round(w * 0.24), Math.min(Math.round(w * 0.24), rawShiftX));
        const shiftY = Math.round((bottomOcc - topOcc) / 2);
        const clearW = Math.max(320, w - leftOcc - rightOcc);
        const clearH = Math.max(compact ? 160 : 300, h - topOcc - bottomOcc);
        const originScreenX = w / 2 - shiftX;
        const availHalfW = Math.max(160, Math.min(originScreenX - leftOcc, (w - rightOcc) - originScreenX));
        const originScreenY = h / 2 - shiftY;
        const availHalfH = Math.max(compact ? 80 : 150, Math.min(originScreenY - topOcc, (h - bottomOcc) - originScreenY));
        return { w, h, shiftX, shiftY, clearW, clearH, availHalfW, availHalfH };
      }
      const clearW = Math.max(260, w - 24);
      const clearH = Math.max(160, h - topOcc - bottomOcc);
      const shiftY = Math.round((bottomOcc - topOcc) / 2);
      return { w, h, shiftX: 0, shiftY, clearW, clearH, availHalfW: clearW / 2, availHalfH: clearH / 2 };
    }
    function getOverviewPreset(dim) {
      const { h, availHalfW, availHalfH } = getClearViewportMetrics();
      const contentRadius = dim === 'umbra' ? EARTH_RADIUS + 46 : (dim === 'sidera' ? 254 : 292);
      const fovRad = (camera.fov * Math.PI) / 180;
      const clearRatio = Math.min((availHalfH * 2) / h, (availHalfW * 2) / h);
      const dist = Math.round((contentRadius * 1.12) / (Math.tan(fovRad / 2) * Math.max(0.25, clearRatio)));
      const target = new THREE.Vector3(0, 0, 0);
      if (dim === 'umbra') {
        return { pos: new THREE.Vector3(-Math.round(dist * 0.035), Math.round(dist * 0.10), dist), target };
      }
      return { pos: new THREE.Vector3(0, 0, dist), target };
    }
    const CAM_OMNIA = { get pos() { return getOverviewPreset('omnia').pos; }, get target() { return getOverviewPreset('omnia').target; } };
    const CAM_UMBRA = { get pos() { return getOverviewPreset('umbra').pos; }, get target() { return getOverviewPreset('umbra').target; } };
    const CAM_SIDERA = { get pos() { return getOverviewPreset('sidera').pos; }, get target() { return getOverviewPreset('sidera').target; } };

    camera.position.copy(getOverviewPreset('omnia').pos);

    const renderer = initialRenderer;
    document.body.dataset.renderer = renderer.isSoftware ? 'software' : 'webgl';
    const renderPixelRatio = () => Math.min(window.devicePixelRatio || 1, isCompactViewport() ? 1.25 : 2);
    renderer.setPixelRatio(renderPixelRatio());
    renderer.setSize(window.innerWidth, window.innerHeight);
    viewportEl.appendChild(renderer.domElement);
    renderer.domElement.setAttribute('aria-label', '朔望叠影星图，可拖动旋转、滚轮缩放');

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.target.copy(getOverviewPreset('omnia').target);
    controls.enableDamping = true;
    controls.dampingFactor = 0.065;
    controls.rotateSpeed = 0.56;
    controls.zoomSpeed = 0.85;
    controls.minDistance = 85;
    controls.maxDistance = 2200;

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
      uPixelRatio: { value: renderPixelRatio() },
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
    const DUST_COUNT = isCompactViewport() ? 1800 : 3000;
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
      const pOmnia = sampleOmniaGalaxyPoint(vIdx, dIdx, i, 600, false, sRand, sGauss).multiplyScalar(1.06).add(vol.center);

      const th2 = (vIdx / 5) * Math.PI * 2 - Math.PI / 2 + sRand() * ((Math.PI * 2) / 5);
      const r2 = 88 + Math.pow(sRand(), 0.72) * 176;
      const p2D = new THREE.Vector3(Math.cos(th2) * r2, Math.sin(th2) * r2 * 0.92, -3);

      const pUmbra = sampleUmbraContinentPoint();
      const sideraDustCluster = SIDERA_CLUSTERS[vIdx];
      const pSidera = sampleV3Dust(sideraDustCluster.id, i, sRand).add(sideraDustCluster.center);

      const cOmnia = new THREE.Color(i % 2 === 0 ? vol.color : vol.altColor);
      const cUmbra = new THREE.Color('#a68b5b');
      const cSidera = new THREE.Color(sideraDustCluster.color);

      dustParticles.push({ vIdx, pOmnia, p2D, pUmbra, pSidera, cOmnia, cUmbra, cSidera });

      dPosArr[i * 3] = pOmnia.x;
      dPosArr[i * 3 + 1] = pOmnia.y;
      dPosArr[i * 3 + 2] = pOmnia.z;
      dColArr[i * 3] = cOmnia.r;
      dColArr[i * 3 + 1] = cOmnia.g;
      dColArr[i * 3 + 2] = cOmnia.b;
      dSizeArr[i] = 2.2 + sRand() * 2.6;
      dSpikeArr[i] = 0.0;
      dHighArr[i] = 0.74;
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
    dustPoints.userData.softwareStride = 2;
    cosmosGroup.add(dustPoints);

    // Build the curated spiritual motif anchors (玄象母题锚点 / 坤舆异闻坐标针).
    const sCount = SYZYGY_BRIDGES.length;
    const sPosArr = new Float32Array(sCount * 3);
    const sColArr = new Float32Array(sCount * 3);
    const sSizeArr = new Float32Array(sCount);
    const sSpikeArr = new Float32Array(sCount);
    const sHighArr = new Float32Array(sCount);
    const sPhaseArr = new Float32Array(sCount);

    const anchorSpectralHex = bridge => {
      if (bridge.relation === 'EMPIRICAL_EXPLAINS') return '#7ce8ee';
      if (bridge.relation === 'MYTHIC_PROJECTION') return '#f6c978';
      if (bridge.relation === 'SOCIAL_MIRROR') return '#f2a89b';
      if (bridge.relation === 'LIMINAL_SPAWNS') return '#6ee7c0';
      if (bridge.sideraCluster === 'sid_hag' || bridge.sideraCluster === 'sid_crypt') return '#9ec8f6';
      if (bridge.sideraCluster === 'sid_witch') return '#dfd2f0';
      return '#efd394';
    };
    const leadCoreWhite = new THREE.Color('#fff8ea');
    SYZYGY_BRIDGES.forEach((b, i) => {
      sPosArr[i * 3] = b.curAnchorPos.x;
      sPosArr[i * 3 + 1] = b.curAnchorPos.y;
      sPosArr[i * 3 + 2] = b.curAnchorPos.z;
      const relCol = new THREE.Color(anchorSpectralHex(b));
      if (b.isLeadAnchor) relCol.lerp(leadCoreWhite, 0.22);
      else if (b.isSecondaryAnchor) relCol.lerp(leadCoreWhite, 0.08);
      sColArr[i * 3] = relCol.r;
      sColArr[i * 3 + 1] = relCol.g;
      sColArr[i * 3 + 2] = relCol.b;
      sSizeArr[i] = b.baseSizeOmnia;
      sSpikeArr[i] = b.baseSpikeOmnia;
      sHighArr[i] = b.baseHighOmnia;
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
    const BG_COUNT = isCompactViewport() ? 1000 : 1600;
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

    // Crisp procedural photon sprite texture (shared by galaxy cores, constellation pulses, and bridges)
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

    // 5A. OMNIA Astrolabe Coordinate Rings & Living Galaxy Sculpts
    const omniaScaffold = new THREE.Group();
    cosmosGroup.add(omniaScaffold);

    [56, 118, 182, 236, 260].forEach((r, idx) => {
      omniaScaffold.add(createCircleCurve(r, 160, '#d6b678', idx === 3 ? 0.16 : 0.09, idx % 2 === 1));
    });

    // Degree ticks on outer brass ring
    const degPts = [];
    for (let deg = 0; deg < 360; deg += 3) {
      const rad = THREE.MathUtils.degToRad(deg);
      const rIn = 256;
      const rOut = deg % 30 === 0 ? 268 : (deg % 15 === 0 ? 262 : 259);
      degPts.push(
        new THREE.Vector3(Math.cos(rad) * rIn, Math.sin(rad) * rIn, 0),
        new THREE.Vector3(Math.cos(rad) * rOut, Math.sin(rad) * rOut, 0)
      );
    }
    omniaScaffold.add(new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(degPts),
      new THREE.LineBasicMaterial({ color: '#d6b678', transparent: true, opacity: 0.2, depthWrite: false })
    ));

    const omniaGalaxies = createOmniaGalaxySculpts(VOLUMES, starShaderMat, photonTex);
    omniaScaffold.add(omniaGalaxies.group);

    // Outer Zodiac Celestial Veil Rings (twin circular hairline astrolabe bands + 12 ticks + local asterisms)
    const syzygyUpperRing = new THREE.Group();
    [
      { r: 240, z: 28, color: '#cfa962', opacity: 0.12 },
      { r: 280, z: 44, color: '#9eb8d8', opacity: 0.07 },
    ].forEach(({ r, z, color, opacity }) => {
      const ringPts = [];
      for (let i = 0; i <= 180; i++) {
        const a = (i / 180) * Math.PI * 2;
        ringPts.push(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, z));
      }
      const ringLine = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(ringPts),
        new THREE.LineDashedMaterial({ color, transparent: true, opacity, dashSize: 5, gapSize: 5, depthWrite: false })
      );
      ringLine.computeLineDistances();
      syzygyUpperRing.add(ringLine);
    });
    const zodiacTickPts = [];
    for (let m = 0; m < 12; m++) {
      const a = (m / 12) * Math.PI * 2;
      zodiacTickPts.push(
        new THREE.Vector3(Math.cos(a) * 232, Math.sin(a) * 232, 36),
        new THREE.Vector3(Math.cos(a) * 286, Math.sin(a) * 286, 36)
      );
    }
    const zodiacTicks = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(zodiacTickPts),
      new THREE.LineBasicMaterial({ color: '#cfa962', transparent: true, opacity: 0.14, depthWrite: false })
    );
    zodiacTicks.userData.strokeColor = '#cfa962';
    zodiacTicks.userData.lineWidth = 0.7;
    syzygyUpperRing.add(zodiacTicks);

    const asterismPts = buildLeadAsterismSegments(orderedBridges);
    if (asterismPts.length) {
      const asterismLines = new THREE.LineSegments(
        new THREE.BufferGeometry().setFromPoints(asterismPts),
        new THREE.LineBasicMaterial({ color: '#dcc79a', transparent: true, opacity: 0.22, depthWrite: false })
      );
      asterismLines.userData.strokeColor = '#dcc79a';
      asterismLines.userData.lineWidth = 0.65;
      syzygyUpperRing.add(asterismLines);
    }
    cosmosGroup.add(syzygyUpperRing);

    // 5B. UMBRA 3D Celestial Dark-Umbra Globe (Brass Latitude/Longitude Graticules & Umbral Core)
    const umbraGlobeGroup = new THREE.Group();
    umbraGlobeGroup.visible = false;
    cosmosGroup.add(umbraGlobeGroup);

    const obsidianSphere = new THREE.Mesh(
      new THREE.SphereGeometry(EARTH_RADIUS - 2.2, 48, 36),
      new THREE.MeshBasicMaterial({ color: '#050812', transparent: true, opacity: 0.9 })
    );
    obsidianSphere.userData.globeShellRadius = EARTH_RADIUS;
    umbraGlobeGroup.add(obsidianSphere);

    // Brass Latitude Parallels & Longitude Meridians (front-hemisphere culled)
    const graticulePts = [];
    for (let lat = -75; lat <= 75; lat += 15) {
      const isEq = lat === 0;
      const segs = 96;
      for (let i = 0; i < segs; i++) {
        const lon1 = (i / segs) * 360 - 180;
        const lon2 = ((i + 1) / segs) * 360 - 180;
        graticulePts.push(
          latLonToVec3(lat, lon1, EARTH_RADIUS + (isEq ? 0.5 : 0.2)),
          latLonToVec3(lat, lon2, EARTH_RADIUS + (isEq ? 0.5 : 0.2))
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
    const graticuleLines = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(graticulePts),
      new THREE.LineBasicMaterial({ color: '#cfa962', transparent: true, opacity: 0.14, depthWrite: false })
    );
    graticuleLines.userData.sphereCull = true;
    graticuleLines.userData.sphereCullRadius = EARTH_RADIUS;
    graticuleLines.userData.strokeColor = '#cfa962';
    graticuleLines.userData.lineWidth = 0.65;
    umbraGlobeGroup.add(graticuleLines);

    // Engraved Brass World Coastlines projected from real world-atlas land geometry
    const coastPts = [];
    const landGeo = feature(worldAtlas, worldAtlas.objects.land);
    const pushRing = (ring) => {
      for (let i = 0; i < ring.length - 1; i++) {
        const [lon1, lat1] = ring[i], [lon2, lat2] = ring[i + 1];
        if (Math.abs(lon2 - lon1) > 180) continue;
        coastPts.push(
          latLonToVec3(lat1, lon1, EARTH_RADIUS + 0.55),
          latLonToVec3(lat2, lon2, EARTH_RADIUS + 0.55)
        );
      }
    };
    const landGeometries = landGeo.type === 'FeatureCollection'
      ? landGeo.features.map(f => f.geometry)
      : [landGeo.geometry || landGeo];
    for (const geom of landGeometries) {
      if (!geom) continue;
      if (geom.type === 'Polygon') geom.coordinates.forEach(pushRing);
      else if (geom.type === 'MultiPolygon') geom.coordinates.forEach(poly => poly.forEach(pushRing));
    }
    const coastLines = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(coastPts),
      new THREE.LineBasicMaterial({ color: '#d9b977', transparent: true, opacity: 0.54, depthWrite: false })
    );
    coastLines.userData.sphereCull = true;
    coastLines.userData.sphereCullRadius = EARTH_RADIUS;
    coastLines.userData.strokeColor = '#e0c07f';
    coastLines.userData.lineWidth = 1.05;
    umbraGlobeGroup.add(coastLines);

    // Tilted 23.5° Brass Ecliptic Ring around Umbra Earth
    const umbraEcliptic = createCircleCurve(EARTH_RADIUS + 26, 128, '#cfa962', 0.28, false);
    umbraEcliptic.rotation.set(1.15, 0.25, 0.41);
    umbraGlobeGroup.add(umbraEcliptic);

    // 5C. SIDERA Iconic Mythos Constellation Sculpts
    const sideraFilamentGroup = new THREE.Group();
    sideraFilamentGroup.visible = false;
    cosmosGroup.add(sideraFilamentGroup);

    const sideraCenterCircle = createCircleCurve(126, 128, '#cfa962', 0.11, false);
    sideraCenterCircle.userData.strokeColor = '#cfa962';
    sideraCenterCircle.userData.lineWidth = 0.65;
    // The v3 astrolabe supplies its own center ring and orbital guides.

    const sideraPentagonPts = [];
    for (let i = 0; i <= SIDERA_CLUSTERS.length; i++) {
      sideraPentagonPts.push(SIDERA_CLUSTERS[i % SIDERA_CLUSTERS.length].center.clone());
    }
    const sideraPentagonLoop = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(sideraPentagonPts),
      new THREE.LineBasicMaterial({ color: '#b8c6de', transparent: true, opacity: 0.07, depthWrite: false })
    );
    sideraPentagonLoop.userData.strokeColor = '#b8c6de';
    sideraPentagonLoop.userData.lineWidth = 0.6;
    // The v3 astrolabe supplies its own center ring and orbital guides.

    const sideraSculpts = createSideraV3Sculpts(SIDERA_CLUSTERS, {
      software: renderer.isSoftware,
      pixelRatio: renderPixelRatio(),
    });
    sideraSculpts.setFade(0);
    sideraFilamentGroup.add(sideraSculpts.group);

    let sideraFade = 0;
    let dimTransitionUntil = 0;
    let dustNeedsMorph = false;

    // ============================================================================
    // 6. CUBIC BEZIER PHOTON BRIDGES (心物折光弦) WITH TRAVELING PULSES
    // ============================================================================
    const bezierBridgesGroup = new THREE.Group();
    cosmosGroup.add(bezierBridgesGroup);

    let activePhotonPulses = [];
    let activeBridgeCurves = [];

    function addPhotonCurve({ pStart, pEnd, idx, relMeta, baseOpacity, pulseCount, spriteScale, bridge = null, startFn = null, endFn = null }) {
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

      const lineMat = new THREE.LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: baseOpacity,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      });

      const bridgeLine = new THREE.Line(lineGeo, lineMat);
      bridgeLine.userData.strokeColor = relMeta.colorA;
      bridgeLine.userData.lineWidth = baseOpacity > 0.8 ? 1.65 : 0.9;
      bezierBridgesGroup.add(bridgeLine);
      const getStart = startFn ?? (bridge ? () => bridge.curAnchorPos : null);
      const getEnd = endFn ?? (bridge ? () => bridge.materialNode.curPos : null);
      if (getStart && getEnd) {
        activeBridgeCurves.push({ idx, curve, geometry: lineGeo, getStart, getEnd });
      }

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
        sprite.scale.set(spriteScale, spriteScale, 1);
        bezierBridgesGroup.add(sprite);

        activePhotonPulses.push({
          curve,
          sprite,
          speed: 0.20 + (idx % 4) * 0.04,
          offset: ((idx * 0.19) + p * 0.5) % 1.0
        });
      }
    }

    function rebuildSyzygyPhotonBridges() {
      while (bezierBridgesGroup.children.length > 0) {
        const ch = bezierBridgesGroup.children[0];
        if (ch.geometry) ch.geometry.dispose();
        if (ch.material) ch.material.dispose();
        bezierBridgesGroup.remove(ch);
      }
      activePhotonPulses = [];
      activeBridgeCurves = [];

      if (!appState.syzygyOn) {
        appState.bridgeBundleStats = null;
        renderer.domElement.dataset.bridgeCount = '0';
        updateBannerPill(appState.matchingBridgeIds?.size ?? 0);
        return;
      }

      if (appState.dimension === 'sidera') {
        const sideraVisible = SYZYGY_BRIDGES.filter(b =>
          bridgeAllowed(b) && (!appState.matchingBridgeIds || appState.matchingBridgeIds.has(b.id))
        );
        const sideraSelection = selectVisibleSideraCurves(sideraVisible, SIDERA_CLUSTERS, appState);
        for (const spec of sideraSelection.curves) {
          if (spec.kind === 'cluster_trunk' || spec.kind === 'selected') {
            const fromB = spec.fromBridge;
            const cl = spec.cluster;
            addPhotonCurve({
              pStart: fromB.curAnchorPos.clone(),
              pEnd: cl.center.clone(),
              idx: spec.idx,
              relMeta: spec.kind === 'selected'
                ? (RELATION_META[fromB.relation] || RELATION_META.THEMATIC)
                : RELATION_META.THEMATIC,
              baseOpacity: spec.baseOpacity,
              pulseCount: spec.pulseCount,
              spriteScale: spec.spriteScale,
              startFn: () => fromB.curAnchorPos,
              endFn: () => cl.center,
            });
          } else {
            const bA = spec.fromBridge;
            const bB = spec.toBridge;
            addPhotonCurve({
              pStart: bA.curAnchorPos.clone(),
              pEnd: bB.curAnchorPos.clone(),
              idx: spec.idx,
              relMeta: RELATION_META[bA.relation] || RELATION_META.THEMATIC,
              baseOpacity: spec.baseOpacity,
              pulseCount: spec.pulseCount,
              spriteScale: spec.spriteScale,
              startFn: () => bA.curAnchorPos,
              endFn: () => bB.curAnchorPos,
            });
          }
        }
        appState.bridgeBundleStats = {
          shown: sideraSelection.shownCount,
          total: sideraSelection.totalMatching,
          truncatedCount: sideraSelection.truncatedCount,
        };
        renderer.domElement.dataset.bridgeMode = appState.sideraBridgeMode;
        renderer.domElement.dataset.bridgeCount = String(activeBridgeCurves.length);
        updateBannerPill(appState.matchingBridgeIds?.size ?? 0);
        return;
      }

      const bridges = appState.portalBridge && appState.dimension === 'omnia' ? [...SYZYGY_BRIDGES, appState.portalBridge] : SYZYGY_BRIDGES;
      const omniaSelection = selectVisibleOmniaCurves(bridges, {
        ...appState,
        volumes: VOLUMES,
        bridgeAllowed,
      });
      const overviewBridgeIds = omniaSelection.overviewBridgeIds;
      const isTrailOrFilter = appState.activeTrail !== 'all' || appState.searchQuery.trim().length > 0;

      omniaSelection.curves.forEach((bridge, idx) => {
        const personal = bridge === appState.portalBridge;
        const isSelected = personal || (appState.selectedBridge && appState.selectedBridge.id === bridge.id);
        addPhotonCurve({
          pStart: bridge.curAnchorPos.clone(),
          pEnd: bridge.materialNode.curPos.clone(),
          idx,
          relMeta: RELATION_META[bridge.relation] || RELATION_META.THEMATIC,
          baseOpacity: isSelected ? 0.88 : (isTrailOrFilter ? 0.78 : (overviewBridgeIds.has(bridge.id) ? 0.34 : 0.42)),
          pulseCount: isSelected || isTrailOrFilter ? 2 : 1,
          spriteScale: isSelected ? 12 : 8.5,
          bridge,
        });
      });

      if (appState.dimension === 'omnia' && appState.syzygyOn && appState.selectedBook && !appState.portalBridge) {
        const materialNode = PRIMARY_NODES.find(item => item.code === appState.selectedBook.id);
        const reverseRows = fullAtlas.getMatchIndex()?.reverse?.get(appState.selectedBook.id) ?? [];
        const topSubstantive = reverseRows
          .filter(row => row.kind !== 'guide' && fullAtlas.isVisible(fullAtlas.getNode(row.nodeId)))
          .slice(0, 6);
        if (materialNode && topSubstantive.length) {
          const starAng = Math.atan2(materialNode.posOmnia3D.y, materialNode.posOmnia3D.x);
          const fanCount = topSubstantive.length;
          topSubstantive.forEach((row, mIdx) => {
            const angle = starAng + (mIdx - (fanCount - 1) / 2) * 0.16;
            const fanR = 276 + (mIdx % 2) * 18;
            const fanZ = 78 + (mIdx % 3) * 14;
            const anchor = new THREE.Vector3(Math.cos(angle) * fanR, Math.sin(angle) * fanR, fanZ);
            addPhotonCurve({
              pStart: anchor,
              pEnd: materialNode.curPos.clone(),
              idx: mIdx,
              relMeta: RELATION_META[row.kind === 'relay' ? 'EMPIRICAL_EXPLAINS' : 'THEMATIC'],
              baseOpacity: 0.72,
              pulseCount: 1,
              spriteScale: 9.5,
              bridge: { curAnchorPos: anchor, materialNode },
            });
          });
        }
      }

      appState.bridgeBundleStats = {
        shown: omniaSelection.shownCount,
        total: omniaSelection.totalMatching,
        truncatedCount: omniaSelection.truncatedCount,
      };
      renderer.domElement.dataset.bridgeCount = String(activeBridgeCurves.length);
      updateBannerPill(appState.matchingBridgeIds?.size ?? 0);
    }

    const bridgeMid = new THREE.Vector3(), bridgeC1 = new THREE.Vector3(), bridgeC2 = new THREE.Vector3(), bridgePoint = new THREE.Vector3();
    function updateBridgeCurves() {
      for (const item of activeBridgeCurves) {
        const start = item.getStart(), end = item.getEnd();
        if (!start || !end) continue;
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
    const initialRealm = realmById(initialParams.get('realm'));
    const appState = {
      dimension: 'omnia',     // 'omnia' | 'umbra' | 'sidera'
      sideraFocus: 'all',
      sideraTempo: 'tide',
      sideraBridgeMode: 'bundled',
      syzygyOn: true,         // Default ON!
      is2DPlanisphere: false,
      membraneDepth: initialRealm ? initialRealm.depth : DEFAULT_MEMBRANE_DEPTH,
      observerHudDismissed: false,
      scopeTab: 'all',        // 'all' | 'volumes' | 'supplement' | 'bridges' | 'reading' | 'taxonomy'
      lastNonTaxonomyScope: 'all',
      taxonomyData: null,
      taxonomyPromise: null,
      taxonomyLoading: false,
      taxonomySelectedDomainId: null,
      taxonomyLexiconQuery: '',
      taxonomyLexiconCategory: '',
      taxonomyShardState: new Map(),
      taxonomyExpandedGroups: new Set(),
      bridgeBundleStats: null,
      activeVolId: null,
      activeDiscId: null,
      activeTrail: 'all',
      searchQuery: '',
      openBridgeClusters: new Set(),
      openHubVolumes: new Set(),
      openReadingPaths: new Set(),
      substantiveMatchCount: bridgeDataset.match_summary?.stats?.substantive_nodes ?? null,
      showF: initialShowF,
      tiers: new Set(initialTiers),
      genre: Object.hasOwn(genreLabels,initialParams.get('genre')) ? initialParams.get('genre') : 'ALL',
      selectedBridge: null,
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
      isOverview: true,
      needsBridgeRebuild: false
    };
    const lunarInfo = computeLunarSyzygy();
    let observerTrace = loadObserverTrace();
    const membraneAudio = createMembraneAudio();
    const membraneRefraction = createMembraneRefraction(renderer, {
      reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    });
    membraneRefraction.resize(window.innerWidth, window.innerHeight, renderPixelRatio());
    const membrane = createMembraneLayer({
      canvas: document.getElementById('membrane-canvas'),
      whisperHost: document.getElementById('membrane-whispers'),
      reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      onCross: ({ intoSpirit, x, y }) => {
        membraneRefraction.cross(intoSpirit, x, y);
        membraneAudio.playCross(intoSpirit);
      },
    });
    membrane.resize(window.innerWidth, window.innerHeight, Math.min(renderPixelRatio(), 1.5));
    membrane.setDepth(appState.membraneDepth, { silent: true });
    membraneAudio.setDepth(appState.membraneDepth);

    function elementCenter(el) {
      const rect = el?.getBoundingClientRect?.();
      return rect && rect.width ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    }
    let renderObserverHud = () => {};
    function recordObs(event) {
      observerTrace = recordObservation(observerTrace, {
        ...event,
        depth: appState.membraneDepth,
        realm: realmForDepth(appState.membraneDepth).id,
      });
      renderObserverHud();
    }
    function triggerBlockedMembrane(x, y) {
      const realm = realmForDepth(appState.membraneDepth);
      membrane.triggerRipple(x, y, { kind: 'blocked', whisper: realm.whisper });
      membraneAudio.playRipple(true);
      recordObs({ type: 'ripple', label: realm.whisper });
      flashToast('身处界膜彼岸：此界可观不可涉，点击「人」或「界膜」即可返界操作');
    }
    function bridgeAllowed(bridge) { return appState.tiers.has(bridge.mythos.credibility_tier) && (!bridge.fiction || appState.showF)
      && (appState.genre === 'ALL' || genreContract(bridge.mythos) === appState.genre); }
    function bridgeMatchesFilter(b) {
      if (!bridgeAllowed(b) || (appState.activeTrail !== 'all' && b.trail !== appState.activeTrail)) return false;
      const query = appState.searchQuery.trim().toLowerCase();
      if (!query) return true;
      const hay = `${b.id} ${b.shortLabel} ${b.mythos.title} ${b.mythos.genre} ${b.mythos.taxonomies.join(' ')} ${b.physis.title} ${b.physis.code} ${b.physis.volLabel} ${b.umbraGeo.place}`.toLowerCase();
      return hay.includes(query);
    }

    const fullAtlas = createFullAtlas({ root, book, dataset:bridgeDataset, state:appState, cosmosGroup, software: renderer.isSoftware,
      starMaterial:starShaderMat, latLonToVec3, audio: membraneAudio, getMembraneDepth: () => appState.membraneDepth, onObserve: recordObs,
      onMatchesUpdated(count) {
        appState.substantiveMatchCount = count;
        updateBannerPill(appState.matchingBridgeIds?.size ?? 0);
      },
      onMatchesReady(index) {
        const sizeAttr = primaryGeo.getAttribute('aSize');
        const spikeAttr = primaryGeo.getAttribute('aSpike');
        let geomDirty = false;
        PRIMARY_NODES.forEach((node, idx) => {
          const nextCount = index.bookMatchCounts?.get(node.code) ?? 0;
          if (node.semanticMatchCount !== nextCount) {
            node.semanticMatchCount = nextCount;
            if (!node.isHub && !node.bridgeIds.length) {
              const nextSize = nextCount > 0 ? 11.5 : sizeAttr.array[idx];
              const nextSpike = nextCount > 0 ? 0.48 : spikeAttr.array[idx];
              if (sizeAttr.array[idx] !== nextSize || spikeAttr.array[idx] !== nextSpike) {
                sizeAttr.array[idx] = nextSize;
                spikeAttr.array[idx] = nextSpike;
                geomDirty = true;
              }
            }
          }
        });
        if (geomDirty) {
          sizeAttr.needsUpdate = true;
          spikeAttr.needsUpdate = true;
        }
        VOLUMES.forEach(vol => {
          vol.disciplines.forEach(disc => {
            disc.connectedEntries = PRIMARY_NODES.filter(node => node.discId === disc.id && node.semanticMatchCount > 0).length;
          });
        });
        updateHighlightsAndFilters();
        renderLeftAtlasTree();
        if (appState.selectedBook) appState.needsBridgeRebuild = true;
      },
      focusNode(node, geo, semantic) {
        if (appState.dimension === 'omnia') switchDimension('sidera', true);
        if (appState.dimension === 'umbra' && !geo) { flashToast('此条未记录坐标，可在目录与星络中阅读。'); return; }
        appState.isOverview = false;
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
          if (appState.dimension !== 'omnia') switchDimension('omnia', true);
          appState.needsBridgeRebuild = true;
          appState.isOverview = false;
          const star = PRIMARY_NODES.find(item=>item.code === appState.selectedBook.id);
          if (star) { const pos=star.posOmnia3D.clone().applyMatrix4(cosmosGroup.matrixWorld); animateCameraTo(pos.clone().add(new THREE.Vector3(0,25,210)),pos,980); }
        } else if (appState.selectedGraph) {
          appState.isOverview = false;
        }
        updateHighlightsAndFilters(); updateClassicLink(); syncViewURL(); setRightDrawerCollapsed(false);
      },
      onBrowseFolklore() {
        appState.searchQuery = ''; searchInput.value = ''; btnClearQuery.classList.add('hidden'); mobileResults.hidden = true;
        setScopeTab('supplement');
        fullAtlas.searchChanged();
        setLeftDrawerCollapsed(false); flashToast('在左侧目录选择民俗条目。');
      },
      onPortal(node, entry) {
        if (appState.dimension !== 'omnia') switchDimension('omnia', false, true);
        if (!appState.syzygyOn) document.getElementById('btn-syzygy-toggle').click();
        const materialNode = PRIMARY_NODES.find(item => item.code === entry.id);
        if (!materialNode) { flashToast('未找到这条格物星点。'); return; }
        let hash=0; for (const c of node.id) hash=Math.imul(hash^c.charCodeAt(0),16777619);
        const starAng = Math.atan2(materialNode.posOmnia3D.y, materialNode.posOmnia3D.x);
        const hashNorm = (hash >>> 0) / 4294967296;
        const angle = starAng + (hashNorm - 0.5) * 0.45;
        const anchor = new THREE.Vector3(Math.cos(angle) * 282, Math.sin(angle) * 282, 88);
        appState.portalBridge = { id:'USER-PORTAL', fiction:node.credibility_tier === 'F' || node.is_fictional_quarantine,
          hasCoordinates:false, trail:'personal', relation:'THEMATIC', curAnchorPos:anchor, materialNode };
        renderer.domElement.dataset.portalStory = node.id; renderer.domElement.dataset.portalBook = entry.id;
        userPortalMarker.position.copy(anchor); userPortalMarker.visible=true;
        userPortalLabel.textContent=node.title; userPortalLabel.hidden=false;
        appState.needsBridgeRebuild=true; updateHighlightsAndFilters(); updateClassicLink();
        appState.isOverview = false;
        const mid=anchor.clone().lerp(materialNode.posOmnia3D,.5).applyMatrix4(cosmosGroup.matrixWorld);
        animateCameraTo(mid.clone().add(new THREE.Vector3(0,25,320)),mid,980);
        syncViewURL();
      },
    });

    const userPortalMarker = new THREE.Sprite(new THREE.SpriteMaterial({ map:photonTex, color:'#e8d8b0', transparent:true, depthWrite:false, blending:THREE.AdditiveBlending }));
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
      const curRealm = realmForDepth(appState.membraneDepth);
      if (curRealm.id !== 'threshold') url.searchParams.set('realm', curRealm.id); else url.searchParams.delete('realm');
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
      const changed = appState.dimension !== dim;
      appState.dimension = dim;
      document.body.dataset.dimension = dim;
      if (changed) setObservatoryPanel('');
      const sideraControls = document.getElementById('sidera-v3-controls');
      if (sideraControls) sideraControls.hidden = dim !== 'sidera';
      dimTransitionUntil = performance.now() + 450;
      dustNeedsMorph = true;
      if (dim === 'sidera') {
        sideraFade = 0;
        sideraSculpts.setFade(0);
      }
      if (dim === 'umbra') {
        cosmosGroup.rotation.x = 0;
      }
      starUniforms.uGlobeMode.value = dim === 'umbra' ? 1 : 0;
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
      dustPoints.visible = (dim !== 'umbra');
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
        if (!skipCamera) {
          appState.isOverview = true;
          const preset = getOverviewPreset('umbra');
          animateCameraTo(preset.pos, preset.target, 1100);
        }
      } else if (dim === 'sidera') {
        eyebrow.textContent = 'SIDERA / NON-EUCLIDEAN MOTIF CONSTELLATION';
        title.textContent = 'SIDERA · 玄象星络';
        desc.textContent = '原图谱四层条目的星域投影 · 点击星点阅读卷宗与真实关联';
        if (!skipCamera) {
          appState.isOverview = true;
          const preset = getOverviewPreset('sidera');
          animateCameraTo(preset.pos, preset.target, 1100);
        }
      } else {
        eyebrow.textContent = 'OMNIA × SYZYGY / HETEROGENEOUS ASTROLABE';
        title.textContent = 'OMNIA · 万象星枢';
        desc.textContent = `《格物识微》五卷 · ${book.entries.length.toLocaleString()} 个真实条目与民俗卷宗对照`;
        if (!skipCamera) {
          appState.isOverview = true;
          const preset = getOverviewPreset('omnia');
          animateCameraTo(preset.pos, preset.target, 1100);
        }
      }

      renderLeftAtlasTree();
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;
      return changed;
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
          if (vol.isWormhole && (appState.activeVolId === 'vol5' || isBeyondMembrane(appState.membraneDepth))) {
            switchDimension('sidera');
            flashToast('已通过「05 意义卷 · 拉格朗日穿界星门」跃迁至 SIDERA · 玄象星络');
          } else if (isBeyondMembrane(appState.membraneDepth)) {
            triggerBlockedMembrane(e.clientX, e.clientY);
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
        el.className = 'world-tag sidera-cluster-tag';
        el.innerHTML = `
          <div class="vol-plaque border-[#b692f6]/40">
            <div class="font-mono-tech text-[9px] tracking-[0.16em] text-[#c4b5fd]">${cl.code}</div>
            <div class="font-serif-sc text-xs font-semibold text-[#f3eeff] mt-0.5"><span class="plaque-full">${cl.name}</span><span class="plaque-short">${cl.shortName}</span></div>
          </div>
        `;
        el.setAttribute('title', cl.name);
        el.setAttribute('aria-label', cl.name);
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

    function syncSpiritualAnchorAttributes() {
      const sSize = spiritualAnchorGeo.getAttribute('aSize');
      const sSpike = spiritualAnchorGeo.getAttribute('aSpike');
      const sHigh = spiritualAnchorGeo.getAttribute('aHighlight');
      const showSpiritualPoints = appState.syzygyOn || appState.dimension !== 'omnia';
      const beyondMembrane = isBeyondMembrane(appState.membraneDepth);
      const trailActive = appState.activeTrail !== 'all' || appState.searchQuery.trim().length > 0;

      SYZYGY_BRIDGES.forEach((b, i) => {
        const visible = showSpiritualPoints && bridgeAllowed(b) && (appState.dimension !== 'umbra' || b.hasCoordinates);
        const isSel = appState.selectedBridge?.id === b.id;
        const isHover = appState.hoveredTarget?.bridge?.id === b.id;
        const ok = appState.matchingBridgeIds?.has(b.id) ?? true;
        const style = computeAdaptiveAnchorStyle(b, {
          dimension: appState.dimension,
          visible,
          isSelected: isSel,
          isHovered: isHover,
          isMatching: ok,
          trailActive,
          beyondMembrane,
          sideraFocus: appState.sideraFocus,
        });
        sSize.array[i] = style.size;
        sSpike.array[i] = style.spike;
        sHigh.array[i] = style.highlight;
      });
      sSize.needsUpdate = true;
      sSpike.needsUpdate = true;
      sHigh.needsUpdate = true;
    }

    function updateHighlightsAndFilters() {
      const q = appState.searchQuery.trim().toLowerCase();
      const pHigh = primaryGeo.getAttribute('aHighlight');
      const dHigh = dustGeo.getAttribute('aHighlight');

      // Filter Bridges first
      const matchingBridgeIds = new Set();
      SYZYGY_BRIDGES.forEach(b => {
        if (bridgeMatchesFilter(b)) matchingBridgeIds.add(b.id);
      });
      appState.matchingBridgeIds = matchingBridgeIds;

      // Update Primary Star Brightness
      const beyondMembrane = isBeyondMembrane(appState.membraneDepth);
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
        const isFocused = (appState.selectedBridge && appState.selectedBridge.materialNode.index === i) || appState.portalBridge?.materialNode.index === i || appState.selectedBook?.id === n.code;
        if (isFocused) {
          h = 2.2;
        } else if (n.isHub && hasMatchingBridge && appState.syzygyOn) {
          h = Math.max(h, 1.55);
        } else if (match && n.semanticMatchCount > 0 && appState.syzygyOn) {
          h = Math.max(h, 1.24);
        }
        if (beyondMembrane && !isFocused && !hasMatchingBridge) {
          h = Math.max(0.08, h * 0.44);
        }
        pHigh.array[i] = h;
      });
      pHigh.needsUpdate = true;

      // Update spiritual anchor magnitude & brightness hierarchy.
      syncSpiritualAnchorAttributes();

      // Update Micro-Dust Brightness
      for (let i = 0; i < DUST_COUNT; i++) {
        const d = dustParticles[i];
        const vId = VOLUMES[d.vIdx].id;
        const dim = (appState.activeVolId && appState.activeVolId !== vId) || appState.activeTrail !== 'all' || q.length > 0;
        dHigh.array[i] = dim ? 0.15 : (beyondMembrane ? 0.44 : 0.74);
      }
      dHigh.needsUpdate = true;

      // Update Top Banner Pill
      updateBannerPill(matchingBridgeIds.size);

      renderBridgesIndexList(matchingBridgeIds);
      document.getElementById('stats-bridges').textContent = String(SYZYGY_BRIDGES.filter(bridgeAllowed).length);
    }

    function updateBannerPill(matchingCount) {
      const bannerPill = document.getElementById('banner-pill');
      if (!bannerPill) return;
      const curRealm = realmForDepth(appState.membraneDepth);
      const subCount = appState.substantiveMatchCount ?? bridgeDataset.match_summary?.stats?.substantive_nodes ?? matchingCount;
      const discCount = VOLUMES.reduce((sum, v) => sum + v.disciplines.filter(d => d.connectedEntries > 0 || d.isSupplement).length, 0);
      const bundle = appState.bridgeBundleStats;
      const bundleSuffix = bundle && bundle.truncatedCount > 0
        ? ` · 星桥束流 ${bundle.shown} / ${bundle.total} · 点选星点展开专属连线`
        : '';
      bannerPill.textContent = appState.syzygyOn
        ? `${curRealm.rank} ${curRealm.char} · ${subCount.toLocaleString()} 实质星桥 · ${matchingCount} 精选 · ${discCount}/${book.subjects.length} 学科${bundleSuffix}${appState.portalBridge ? ' · 1 自选' : ''}`
        : `○ 单界纯净观测模式 · ${curRealm.rank} ${curRealm.char}`;
    }

    // ============================================================================
    // 9. RENDER LEFT ATLAS TREE & RIGHT DUAL-PANE SYZYGY CODEX
    // ============================================================================
    function renderLeftAtlasTree() {
      const container = document.getElementById('atlas-tree');
      container.innerHTML = '';

      if (appState.dimension === 'sidera' && appState.sideraFocus !== 'all'
        && appState.scopeTab === 'all' && !appState.searchQuery.trim()) {
        const cluster = SIDERA_CLUSTERS.find(item => item.id === appState.sideraFocus);
        const entries = SYZYGY_BRIDGES.filter(item => item.sideraCluster === cluster?.id && bridgeMatchesFilter(item));
        const heading = document.createElement('p');
        heading.className = 'syzygy-directory-heading';
        heading.textContent = `${cluster?.name ?? '玄象星群'} · ${entries.length} 道精选对读`;
        container.append(heading);
        if (cluster?.id === 'sid_crypt') {
          const origin = document.createElement('div');
          origin.className = 'sidera-v3-origin';
          origin.innerHTML = '<strong>赤金烛龙 · 图像原型</strong><p>《山海经》描写烛龙为人面蛇身、赤色，眼目的开合与天地晦明相连。</p><a href="https://zh.wikisource.org/wiki/%E5%B1%B1%E6%B5%B7%E7%B6%93/%E5%A4%A7%E8%8D%92%E5%8C%97%E7%B6%93" target="_blank" rel="noopener noreferrer">阅读《大荒北经》原文 ↗</a>';
          container.append(origin);
        }
        const tip = document.createElement('p');
        tip.className = 'sidera-v3-directory-tip';
        tip.textContent = '搜索可检索完整馆藏；点击条目阅读故事与出处。';
        container.append(tip);
        for (const bridge of entries) {
          const button = document.createElement('button');
          button.className = 'syzygy-directory-row';
          if (appState.selectedBridge?.id === bridge.id) button.classList.add('is-selected');
          button.innerHTML = `<b>${escapeHTML(bridge.mythos.title)}</b><span>${escapeHTML(bridge.umbraGeo.place)} · ${escapeHTML(bridge.mythos.credibility_tier)} 级</span>`;
          button.addEventListener('click', () => selectSyzygyBridge(bridge, true));
          container.append(button);
        }
        return;
      }

      if (appState.scopeTab === 'taxonomy' && !appState.searchQuery.trim()) {
        const heading = document.createElement('p');
        heading.className = 'syzygy-directory-heading';
        heading.textContent = '专题谱系 · 七大主题域';
        container.append(heading);
        const domains = appState.taxonomyData?.domains ?? [];
        if (!domains.length) {
          const note = document.createElement('p');
          note.className = 'syzygy-reference';
          note.textContent = appState.taxonomyLoading ? '正在载入专题谱系…' : '专题谱系暂未编译，可在主视窗查看详情。';
          container.append(note);
          return;
        }
        domains.forEach((domain) => {
          const button = document.createElement('button');
          button.className = 'syzygy-directory-row';
          if (appState.taxonomySelectedDomainId === domain.id) button.classList.add('is-selected');
          const lexLabel = domain.lexicon_shard
            ? `${domain.lexicon_count ?? domain.lexicon_shard.count} 辞条`
            : '规划分片';
          button.innerHTML = `<b>${escapeHTML(domain.name)}</b><span>${escapeHTML(String(domain.node_count ?? 0))} 节点 · ${escapeHTML(lexLabel)}</span>`;
          button.addEventListener('click', () => openTaxonomyDomain(domain.id));
          container.append(button);
        });
        return;
      }

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
        const qNorm = appState.searchQuery.trim().normalize('NFKC').toLocaleLowerCase();
        const connectedNodesAll = PRIMARY_NODES.filter(n => n.semanticMatchCount > 0);
        const connectedDiscCount = VOLUMES.reduce((sum, v) => sum + v.disciplines.filter(d => d.connectedEntries > 0 || d.isSupplement).length, 0);
        const hubHeading = document.createElement('p');
        hubHeading.className = 'syzygy-directory-heading';
        hubHeading.textContent = `全学科星桥枢纽 · ${connectedDiscCount}/${book.subjects.length} 学科（${connectedNodesAll.length} 格物条目）`;
        container.append(hubHeading);

        let hubGroupsShown = 0;
        VOLUMES.forEach(vol => {
          const volNodes = connectedNodesAll
            .filter(n => n.volId === vol.id)
            .filter(n => !qNorm || `${n.code} ${n.title} ${n.discName} ${vol.name}`.normalize('NFKC').toLocaleLowerCase().includes(qNorm))
            .sort((a, b) => b.semanticMatchCount - a.semanticMatchCount || a.code.localeCompare(b.code));
          if (!volNodes.length) return;
          hubGroupsShown++;
          const section = document.createElement('details');
          section.className = 'syzygy-bridge-group';
          const isSelectedInVol = !!(appState.selectedBook && volNodes.some(n => n.code === appState.selectedBook.id));
          section.open = !!qNorm || appState.openHubVolumes.has(vol.id) || isSelectedInVol;
          const summary = document.createElement('summary');
          summary.className = 'syzygy-directory-heading';
          summary.textContent = `${vol.num} · ${vol.name}（${volNodes.length} 枢纽）`;
          summary.addEventListener('click', () => {
            if (qNorm) return;
            if (section.open) appState.openHubVolumes.delete(vol.id);
            else appState.openHubVolumes.add(vol.id);
          });
          section.append(summary);
          volNodes.forEach(node => {
            const btn = document.createElement('button');
            btn.className = 'syzygy-directory-row';
            if (appState.selectedBook?.id === node.code) btn.classList.add('is-selected');
            btn.innerHTML = `<b>${escapeHTML(node.title)}</b><span>${escapeHTML(node.discName)} · ${node.semanticMatchCount.toLocaleString()} 条关联</span>`;
            btn.addEventListener('click', () => fullAtlas.selectBook(node.code));
            section.append(btn);
          });
          container.append(section);
        });
        if (!hubGroupsShown) {
          const emptyHub = document.createElement('p');
          emptyHub.className = 'syzygy-reference';
          emptyHub.textContent = '没有匹配当前搜索的学科枢纽。';
          container.append(emptyHub);
        }

        const curatedSection = document.createElement('div');
        curatedSection.className = 'syzygy-bridge-section';
        const visibleCuratedCount = SYZYGY_BRIDGES.filter(b => bridgeMatchesFilter(b)).length;
        const heading = document.createElement('p');
        heading.className = 'syzygy-directory-heading';
        heading.textContent = `精选心物对读 · ${visibleCuratedCount} 道典范星桥`;
        curatedSection.append(heading);
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
          curatedSection.append(section);
        });
        if (!groupCount) {
          const empty = document.createElement('p'); empty.className = 'syzygy-reference';
          empty.textContent = '没有符合当前筛选的精选星桥。'; curatedSection.append(empty);
        }
        container.append(curatedSection);
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
        const frieze=document.createElement('div'); frieze.className='engraving-volume-frieze';
        frieze.innerHTML=engravingFrieze(engravingPatternForVolume(vol.id),`engraving-volume-${vol.id}`);
        sec.appendChild(frieze);

        const dWrap = document.createElement('div');
        dWrap.className = 'mt-1 pl-2.5 space-y-0.5';
        vol.disciplines.forEach(disc => {
          if (appState.scopeTab === 'supplement' && !disc.isSupplement) return;

          const dActive = appState.activeDiscId === disc.id;
          const dBtn = document.createElement('button');
          dBtn.className = `w-full flex items-center justify-between px-2 py-1 rounded-[2px] text-[11.5px] transition ${
            dActive ? 'bg-[#d6b678]/22 text-[#fff6e0] border-l-2 border-[#d6b678]' : 'text-[#9e9688] hover:text-[#f3ece0] hover:bg-white/5'
          }`;
          const hasConnected = disc.isSupplement || disc.connectedEntries > 0;
          const badgeTitle = disc.connectedEntries > 0
            ? `已连通 ${disc.connectedEntries} / ${disc.count} 条格物条目`
            : '含精选心物星桥';
          dBtn.innerHTML = `
            <span class="truncate flex items-center gap-1.5"><span>${disc.name}</span>${hasConnected ? `<span class="text-[9px] text-[#cfa962]/85" title="${badgeTitle}">✦</span>` : ''}</span>
            <span class="font-mono-tech text-[10px] opacity-80">${disc.connectedEntries > 0 ? `${disc.connectedEntries}/` : ''}${disc.count}</span>
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
        membraneDepth: appState.membraneDepth, audio: membraneAudio,
        onSelectRelated(id) { const node = fullAtlas.getNode(id); if (node) fullAtlas.select(node, true); },
        onReadBook(id) { const node = fullAtlas.getNode(bridge.mythos.id); if (node) fullAtlas.openPortal(node,id); else flashToast('目录加载中，请稍候。'); },
        onOpenBook(id) { const node = fullAtlas.getNode(bridge.mythos.id); if (node) fullAtlas.openPortal(node,id); else fullAtlas.selectBook(id); },
        onJump(dim, item) {
          if (appState.dimension !== dim) switchDimension(dim, true);
          if (dim === 'umbra' && !item.hasCoordinates) return;
          appState.isOverview = false;
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
      if (!listEl || !countLbl) return;
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
    function selectSyzygyBridge(bridge, flyCamera = true, openDrawer = true) {
      if (!bridgeAllowed(bridge)) return;
      if (flyCamera) recordObs({ type: 'bridge', id: bridge.id, label: bridge.shortLabel });
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

      if (openDrawer) setRightDrawerCollapsed(false);

      if (flyCamera) {
        appState.isOverview = false;
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

      appState.isOverview = false;
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
      const b = SYZYGY_BRIDGES.find(x => x.physis.discId === discId && bridgeAllowed(x));
      if (b) {
        appState.selectedBridge = b;
        appState.selectedGraph = null; appState.selectedBook = null; clearPersonalPortal(); updateClassicLink(); syncViewURL();
        renderDualPaneSyzygyCard(b);
      } else {
        const topHub = PRIMARY_NODES
          .filter(node => node.discId === discId && node.semanticMatchCount > 0)
          .sort((a, bNode) => bNode.semanticMatchCount - a.semanticMatchCount || a.index - bNode.index)[0];
        if (topHub) {
          fullAtlas.selectBook(topHub.code);
          return;
        }
        const volBridge = SYZYGY_BRIDGES.find(x => x.physis.volId === volId && bridgeAllowed(x));
        if (volBridge) {
          appState.selectedBridge = volBridge;
          appState.selectedGraph = null; appState.selectedBook = null; clearPersonalPortal(); updateClassicLink(); syncViewURL();
          renderDualPaneSyzygyCard(volBridge);
        }
      }
      renderLeftAtlasTree();
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;

      appState.isOverview = false;
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
    const sideraPointerPlane = new THREE.Plane();
    const sideraPointerNormal = new THREE.Vector3();
    const sideraPointerOrigin = new THREE.Vector3();
    const sideraPointerHit = new THREE.Vector3();
    const mouseNDC = new THREE.Vector2(-99, -99);
    const tooltipEl = document.getElementById('celestial-tooltip');
    const reticleEl = document.getElementById('astrolabe-reticle');
    let downPt = { x: 0, y: 0 };

    renderer.domElement.addEventListener('pointerdown', (e) => {
      downPt = { x: e.clientX, y: e.clientY };
      // Touch taps need their own hit test; they do not have a preceding hover.
      if (e.pointerType !== 'mouse') updateScenePointer(e);
    });

    function updateScenePointer(e) {
      membrane.setPointer(e.clientX, e.clientY, true);
      membraneRefraction.pointer(e.clientX, e.clientY, true, true);
      mouseNDC.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouseNDC.y = -(e.clientY / window.innerHeight) * 2 + 1;

      raycaster.setFromCamera(mouseNDC, camera);
      if (appState.dimension === 'sidera') {
        cosmosGroup.updateMatrixWorld();
        sideraPointerNormal.set(0, 0, 1).transformDirection(cosmosGroup.matrixWorld);
        sideraPointerOrigin.setFromMatrixPosition(cosmosGroup.matrixWorld);
        sideraPointerPlane.setFromNormalAndCoplanarPoint(sideraPointerNormal, sideraPointerOrigin);
        const point = raycaster.ray.intersectPlane(sideraPointerPlane, sideraPointerHit);
        sideraSculpts.setPointer(point, !!point && appState.sideraTempo !== 'still');
      }

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
              : candidates.length > 1 ? `点击查看 ${candidates.length} 道精选对读`
                : node.semanticMatchCount > 0 ? `已连通 ${node.semanticMatchCount.toLocaleString()} 条民俗/母题星桥 · 点击反向检视`
                  : `点击阅读：${node.discName}`
          };
        }
      }

      const prevHoveredBridgeId = appState.hoveredTarget?.bridge?.id ?? null;
      appState.hoveredTarget = hitResult;
      if ((hitResult?.bridge?.id ?? null) !== prevHoveredBridgeId) {
        syncSpiritualAnchorAttributes();
      }
      if (hitResult) {
        renderer.domElement.style.cursor = 'pointer';
        document.getElementById('tt-coord').textContent = hitResult.coord;
        document.getElementById('tt-tag').textContent = hitResult.tag;
        document.getElementById('tt-title').textContent = hitResult.title;
        document.getElementById('tt-sub').textContent = hitResult.sub;

        const tx = Math.max(8, Math.min(window.innerWidth - 305, e.clientX + 18));
        const ty = Math.max(66, Math.min(window.innerHeight - 85, e.clientY - 12));
        tooltipEl.style.left = `${tx}px`;
        tooltipEl.style.top = `${ty}px`;
        tooltipEl.style.opacity = e.pointerType === 'touch' ? '0' : '1';
      } else {
        renderer.domElement.style.cursor = 'grab';
        tooltipEl.style.opacity = '0';
      }
    }
    renderer.domElement.addEventListener('pointermove', updateScenePointer);

    function clearScenePointer() {
      membrane.setPointer(-999, -999, false);
      membraneRefraction.pointer(0, 0, false, false);
      sideraSculpts.setPointer(null, false);
      const hadBridge = !!appState.hoveredTarget?.bridge;
      appState.hoveredTarget = null;
      tooltipEl.style.opacity = '0';
      if (hadBridge) syncSpiritualAnchorAttributes();
    }
    renderer.domElement.addEventListener('pointerleave', clearScenePointer);
    renderer.domElement.addEventListener('pointercancel', clearScenePointer);

    renderer.domElement.addEventListener('pointerup', (e) => {
      const clearTouchTarget = () => {
        if (e.pointerType !== 'touch') return;
        const hadBridge = !!appState.hoveredTarget?.bridge;
        appState.hoveredTarget = null;
        tooltipEl.style.opacity = '0';
        if (hadBridge) syncSpiritualAnchorAttributes();
      };
      if (Math.hypot(e.clientX - downPt.x, e.clientY - downPt.y) > 5) { clearTouchTarget(); return; }
      if (appState.hoveredTarget && appState.hoveredTarget.bridge) {
        selectSyzygyBridge(appState.hoveredTarget.bridge, true);
      } else if (appState.hoveredTarget?.kind === 'graph') {
        fullAtlas.select(appState.hoveredTarget.node, true);
      } else if (appState.hoveredTarget?.kind === 'star') {
        if (isBeyondMembrane(appState.membraneDepth)) triggerBlockedMembrane(e.clientX, e.clientY);
        else fullAtlas.selectBook(appState.hoveredTarget.node.code);
      } else if (isBeyondMembrane(appState.membraneDepth)) {
        raycaster.setFromCamera(mouseNDC, camera);
        if (appState.dimension === 'umbra' && raycaster.intersectObject(obsidianSphere).length > 0) {
          triggerBlockedMembrane(e.clientX, e.clientY);
        } else {
          membrane.triggerRipple(e.clientX, e.clientY, { kind: 'soft' });
          membraneAudio.playRipple(false);
        }
      }
      clearTouchTarget();
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

    for (const design of SIDERA_V3_DESIGN) {
      const button = document.querySelector(`[data-v3-focus="${design.id}"]`);
      if (button) button.title = `${design.emblemName} · ${design.name}`;
    }
    document.querySelectorAll('[data-v3-focus]').forEach(button => {
      button.addEventListener('click', () => {
        const id = button.dataset.v3Focus;
        const cluster = SIDERA_CLUSTERS.find(item => item.id === id);
        if (id !== 'all' && !cluster) return;
        setObservatoryPanel('');
        appState.sideraFocus = id;
        sideraSculpts.setFocus(id);
        document.querySelectorAll('[data-v3-focus]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
        if (cluster) {
          const first = SYZYGY_BRIDGES.find(item => item.sideraCluster === id && bridgeMatchesFilter(item));
          if (first && appState.selectedBridge?.sideraCluster !== id) selectSyzygyBridge(first, false, false);
          appState.isOverview = false;
          cosmosGroup.updateMatrixWorld();
          const target = cluster.center.clone().applyMatrix4(cosmosGroup.matrixWorld);
          const metrics = getClearViewportMetrics();
          const canvasCenterY = metrics.h / 2 - metrics.shiftY;
          const clearHalfHeight = Math.max(120, Math.min(metrics.availHalfH, metrics.h - 75 - canvasCenterY));
          const clearRatio = Math.min(metrics.availHalfW * 2 / metrics.h, clearHalfHeight * 2 / metrics.h);
          const focusDistance = Math.max(175, 52 / (Math.tan(camera.fov * Math.PI / 360) * Math.max(.25, clearRatio)));
          animateCameraTo(target.clone().add(new THREE.Vector3(0, 0, focusDistance)), target, 1050);
        } else {
          appState.isOverview = true;
          const preset = getOverviewPreset('sidera');
          animateCameraTo(preset.pos, preset.target, 1050);
        }
        renderLeftAtlasTree();
        updateHighlightsAndFilters();
        appState.needsBridgeRebuild = true;
      });
    });
    document.querySelectorAll('[data-v3-tempo]').forEach(button => {
      button.addEventListener('click', () => {
        appState.sideraTempo = button.dataset.v3Tempo;
        const speed = { tide: 1, calm: .32, still: 0 }[appState.sideraTempo] ?? 1;
        sideraSculpts.setSpeed(speed);
        document.querySelectorAll('[data-v3-tempo]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
        if (!speed) sideraSculpts.setPointer(null, false);
      });
    });
    document.querySelectorAll('[data-v3-bridge]').forEach(button => {
      button.addEventListener('click', () => {
        appState.sideraBridgeMode = button.dataset.v3Bridge;
        document.querySelectorAll('[data-v3-bridge]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
        appState.needsBridgeRebuild = true;
      });
    });
    document.getElementById('sidera-v3-export')?.addEventListener('click', () => {
      const rows = SYZYGY_BRIDGES.filter(item => bridgeMatchesFilter(item)
        && (appState.sideraFocus === 'all' || item.sideraCluster === appState.sideraFocus));
      const payload = {
        schema_version: 'astraia.sidera.preview.v3', generated_at: new Date().toISOString(),
        view: { focus: appState.sideraFocus, tempo: appState.sideraTempo, bridges: appState.sideraBridgeMode,
          source_tiers: [...appState.tiers], fiction_visible: appState.showF },
        scope: '当前筛选的精选星桥；正文节选以本地数据为准',
        curated_bridges: rows.map(item => ({ id: item.id, cluster: item.sideraCluster, relation: item.relation,
          evidence_status: item.edge?.status ?? null,
          story: { id: item.mythos.id, title: item.mythos.title, tier: item.mythos.credibility_tier,
            location: item.mythos.spatial, excerpt: item.mythos.reading?.paragraphs ?? [], sources: item.mythos.sources ?? [] },
          knowledge: { id: item.physis.id, title: item.physis.title, volume: item.physis.volume, page: item.physis.page } })),
      };
      const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' }));
      const link = document.createElement('a'); link.href = url; link.download = 'astraia-sidera-view.json'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });

    // Prominent ◐ 折光星桥 Toggle
    const btnSyzygy = document.getElementById('btn-syzygy-toggle');
    btnSyzygy.addEventListener('click', () => {
      appState.syzygyOn = !appState.syzygyOn;
      btnSyzygy.classList.toggle('active', appState.syzygyOn);
      syncEngravingBeam();
      syzygyUpperRing.visible = (appState.dimension === 'omnia' && appState.syzygyOn && !appState.is2DPlanisphere);
      userPortalMarker.visible = !!appState.portalBridge && appState.dimension === 'omnia' && appState.syzygyOn;
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;
      flashToast(appState.syzygyOn ? '已开启「◐ 折光星桥」：心物双界折光弦实时耦合' : '已隐藏折光星桥：进入单界纯粹观测态');
    });

    // 3D Galaxy <-> 2D Planisphere Toggle
    const btnProj = document.getElementById('btn-proj-toggle');
    btnProj.addEventListener('click', (e) => {
      if (isBeyondMembrane(appState.membraneDepth)) {
        const pt = e.clientX ? { x: e.clientX, y: e.clientY } : elementCenter(btnProj);
        triggerBlockedMembrane(pt.x, pt.y);
        return;
      }
      if (appState.dimension !== 'omnia') switchDimension('omnia', true);
      appState.is2DPlanisphere = !appState.is2DPlanisphere;
      btnProj.textContent = appState.is2DPlanisphere ? '3D 星系' : '2D 星盘';
      btnProj.classList.toggle('active', appState.is2DPlanisphere);
      omniaScaffold.visible = !appState.is2DPlanisphere;
      syzygyUpperRing.visible = appState.syzygyOn && !appState.is2DPlanisphere;
      cosmosGroup.rotation.y = 0;
      cosmosGroup.rotation.x = 0;

      if (appState.is2DPlanisphere) {
        appState.isOverview = false;
        animateCameraTo(new THREE.Vector3(0, 0, 720), new THREE.Vector3(0, 0, 0), 980);
        flashToast('已展平为 2D 古典天体星盘');
      } else {
        appState.isOverview = true;
        const preset = getOverviewPreset('omnia');
        animateCameraTo(preset.pos, preset.target, 980);
        flashToast('已恢复 3D 五卷异构星系');
      }
      appState.needsBridgeRebuild = true;
    });

    // Reset View Button
    document.getElementById('btn-reset-cam').addEventListener('click', () => {
      appState.activeVolId = null;
      appState.activeDiscId = null;
      appState.activeTrail = 'all';
      appState.isOverview = true;
      document.querySelectorAll('[data-trail]').forEach(t => t.classList.toggle('active', t.getAttribute('data-trail') === 'all'));
      renderLeftAtlasTree();
      updateHighlightsAndFilters();
      appState.needsBridgeRebuild = true;

      const preset = getOverviewPreset(appState.dimension);
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
          syncEngravingBeam();
        }

        if (trailId !== 'all') {
          const leadBridge = SYZYGY_BRIDGES.find(b => b.trail === trailId && bridgeAllowed(b));
          if (leadBridge) selectSyzygyBridge(leadBridge, true);
          else { updateHighlightsAndFilters(); renderLeftAtlasTree(); appState.needsBridgeRebuild = true; }
        } else {
          appState.isOverview = true;
          updateHighlightsAndFilters();
          renderLeftAtlasTree();
          appState.needsBridgeRebuild = true;
          const preset = getOverviewPreset(appState.dimension);
          animateCameraTo(preset.pos, preset.target, 980);
        }
      });
    });

    // Left Scope Filter Tabs & Thematic Taxonomy Explorer
    const taxonomyExplorer = document.getElementById('taxonomy-explorer');
    const taxonomyDockBtn = document.getElementById('btn-taxonomy-dock');
    const taxonomyNodeLabel = id => {
      const node = fullAtlas.getNode(id);
      if (node) return { title: node.title, layer: `L${node.z_layer ?? '—'}` };
      const entry = book.entries.find(item => item.id === id);
      if (entry) return { title: entry.title, layer: entry.id };
      return { title: id, layer: '节点' };
    };

    function formatBibliographyNote(taxonomy) {
      const items = Array.isArray(taxonomy?.bibliography) ? taxonomy.bibliography : [];
      const citations = items
        .map(item => (typeof item === 'string' ? item : (item?.citation || item?.title || '')))
        .filter(Boolean);
      const baseNote = '辞条按所列资料整理；出处与定位见各条，部分材料仍待进一步核对。';
      return citations.length ? `${baseNote} 书目参照：${citations.join('；')}。` : baseNote;
    }

    function ensureTaxonomyData() {
      if (appState.taxonomyData) return Promise.resolve(appState.taxonomyData);
      if (!appState.taxonomyPromise) {
        appState.taxonomyLoading = true;
        appState.taxonomyPromise = loadTaxonomy(root).then(data => {
          appState.taxonomyLoading = false;
          appState.taxonomyData = data;
          if (!data) appState.taxonomyPromise = null;
          if (appState.scopeTab === 'taxonomy') {
            renderLeftAtlasTree();
            renderTaxonomyExplorer();
          }
          return data;
        }).catch(() => {
          appState.taxonomyLoading = false;
          appState.taxonomyPromise = null;
          return null;
        });
      }
      return appState.taxonomyPromise;
    }

    async function navigateToTaxonomyNode(nodeId) {
      try {
        await fullAtlas.start();
      } catch (error) {
        flashToast(`图谱载入失败：${error.message}`);
        return;
      }
      const node = fullAtlas.getNode(nodeId);
      if (!node) {
        const entry = book.entries.find(item => item.id === nodeId);
        if (entry) {
          setScopeTab(appState.lastNonTaxonomyScope || 'all');
          fullAtlas.selectBook(entry.id);
          return;
        }
        flashToast('该节点尚未并入当前星图快照，请先查阅下方辞条或稍后刷新。');
        return;
      }
      if (!fullAtlas.isVisible(node)) {
        flashToast('该条目被当前信源或体裁筛选隐藏，请先调整左侧筛选。');
        return;
      }
      const curated = SYZYGY_BRIDGES.find(bridge => bridge.mythos.id === nodeId && bridgeAllowed(bridge));
      setScopeTab(appState.lastNonTaxonomyScope || 'all');
      if (curated) selectSyzygyBridge(curated, true);
      else fullAtlas.select(node, true);
    }

    function openTaxonomyDomain(domainId, forceReload = false) {
      appState.taxonomySelectedDomainId = domainId;
      if (!forceReload) {
        appState.taxonomyLexiconQuery = '';
        appState.taxonomyLexiconCategory = '';
      }
      renderLeftAtlasTree();
      renderTaxonomyExplorer();

      const taxonomy = appState.taxonomyData;
      const domain = taxonomy?.domains?.find(item => item.id === domainId);
      if (!domain || !domain.lexicon_shard) return;

      const existing = appState.taxonomyShardState.get(domainId);
      if (!forceReload && existing && (existing.loading || existing.data)) return;

      appState.taxonomyShardState.set(domainId, { loading: true, error: '', data: null });
      if (appState.scopeTab === 'taxonomy' && appState.taxonomySelectedDomainId === domainId) {
        renderTaxonomyExplorer();
      }

      loadLexiconShard(root, taxonomy, domainId).then(shard => {
        appState.taxonomyShardState.set(domainId, { loading: false, error: '', data: shard });
        if (appState.scopeTab === 'taxonomy' && appState.taxonomySelectedDomainId === domainId) {
          renderTaxonomyExplorer();
        }
      }).catch(error => {
        appState.taxonomyShardState.set(domainId, { loading: false, error: error.message, data: null });
        if (appState.scopeTab === 'taxonomy' && appState.taxonomySelectedDomainId === domainId) {
          renderTaxonomyExplorer();
        }
      });
    }

    function renderTaxonomyExplorer() {
      if (!taxonomyExplorer) return;
      const hidden = appState.scopeTab !== 'taxonomy';
      taxonomyExplorer.hidden = hidden;
      if (hidden) return;
      renderTaxonomyExplorerView({
        container: taxonomyExplorer,
        taxonomy: appState.taxonomyData,
        state: appState,
        root,
        bookEntries: book.entries,
        onClose: () => setScopeTab(appState.lastNonTaxonomyScope || 'all'),
        onSelectDomain: (domainId) => openTaxonomyDomain(domainId),
        onSelectNode: (nodeId) => navigateToTaxonomyNode(nodeId),
        onSearchQuery: (query) => {
          appState.taxonomyLexiconQuery = query;
        },
        onSelectCategory: (category) => {
          appState.taxonomyLexiconCategory = category;
        },
        onFocusSidera: (sideraId) => {
          setScopeTab(appState.lastNonTaxonomyScope || 'all');
          switchDimension('sidera', false);
          const focusBtn = document.querySelector(`[data-v3-focus="${sideraId}"]`);
          focusBtn?.click();
        },
        onRetryShard: (domainId) => {
          appState.taxonomyShardState.delete(domainId);
          openTaxonomyDomain(domainId, true);
        },
        resolveNodeLabel: taxonomyNodeLabel,
        escapeHTML,
        formatBibliographyNote,
      });
    }

    function setScopeTab(nextScope) {
      const scope = nextScope || 'all';
      if (scope !== 'taxonomy') appState.lastNonTaxonomyScope = scope;
      appState.scopeTab = scope;
      document.querySelectorAll('.scope-tab').forEach(tab => {
        tab.classList.toggle('active', tab.getAttribute('data-scope') === scope);
      });
      if (taxonomyDockBtn) {
        taxonomyDockBtn.setAttribute('aria-expanded', String(scope === 'taxonomy'));
      }
      if (scope === 'volumes' && appState.dimension !== 'omnia') switchDimension('omnia');
      if (scope === 'taxonomy') {
        setObservatoryPanel('');
        void ensureTaxonomyData();
        renderTaxonomyExplorer();
      } else if (taxonomyExplorer) {
        taxonomyExplorer.hidden = true;
      }
      appState.activeVolId = null;
      appState.activeDiscId = null;
      renderLeftAtlasTree();
      updateHighlightsAndFilters();
      fullAtlas.updatePoints();
    }

    document.querySelectorAll('.scope-tab').forEach(tab => {
      tab.addEventListener('click', () => setScopeTab(tab.getAttribute('data-scope')));
    });
    taxonomyDockBtn?.addEventListener('click', () => {
      setScopeTab(appState.scopeTab === 'taxonomy' ? (appState.lastNonTaxonomyScope || 'all') : 'taxonomy');
    });

    // Collapsible Left & Right Panels + Dynamic Drawer-Aware Camera Framing
    const drawerShell = initSyzygyShell();
    const setLeftDrawerCollapsed = drawerShell.setLeftCollapsed;
    const setRightDrawerCollapsed = drawerShell.setRightCollapsed;
    const btnSpreadCodex = document.getElementById('btn-spread-codex');
    const contextBanner = document.getElementById('context-banner');

    function setObservatoryPanel(panel) {
      document.body.dataset.observatoryPanel = panel;
      document.querySelectorAll('#observatory-dock [data-observatory-panel]').forEach(button => {
        button.setAttribute('aria-expanded', String(button.dataset.observatoryPanel === panel));
      });
    }

    document.querySelectorAll('#observatory-dock [data-observatory-panel]').forEach(button => {
      button.addEventListener('click', () => {
        const panel = button.dataset.observatoryPanel;
        setObservatoryPanel(document.body.dataset.observatoryPanel === panel ? '' : panel);
      });
    });
    document.addEventListener('pointerdown', event => {
      if (!document.body.dataset.observatoryPanel) return;
      if (event.target.closest('#observatory-dock, #observatory-popovers, #sidera-v3-controls')) return;
      setObservatoryPanel('');
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        setObservatoryPanel('');
        if (appState.scopeTab === 'taxonomy') {
          setScopeTab(appState.lastNonTaxonomyScope || 'all');
        }
      }
    });
    for (const [drawer,id] of [[leftDrawer,'engraving-left-heading'],[rightDrawer,'engraving-right-heading']]) {
      const heading=drawer.querySelector(':scope > div');
      if (heading) {
        heading.classList.add('engraving-panel-heading');
        heading.insertAdjacentHTML('afterbegin',`<div class="engraving-panel-frieze">${engravingFrieze('cloud',id)}</div>`);
      }
    }

    function isOverviewActive() {
      return appState.isOverview
        && !appState.activeVolId
        && !appState.activeDiscId
        && !appState.is2DPlanisphere
        && realmForDepth(appState.membraneDepth).id !== 'yi';
    }

    function syncOverviewCameraIfActive(animate = false) {
      if (!isOverviewActive()) return;
      const preset = getOverviewPreset(appState.dimension);
      if (animate) {
        animateCameraTo(preset.pos, preset.target, 380);
      } else {
        appState.camAnim = null;
        camera.position.copy(preset.pos);
        controls.target.copy(preset.target);
      }
    }

    function updateCameraOffset() {
      const { w, h, shiftX, shiftY } = getClearViewportMetrics();
      camera.aspect = w / h;
      if (shiftX || shiftY) camera.setViewOffset(w, h, shiftX, shiftY, w, h);
      else camera.clearViewOffset();
      camera.updateProjectionMatrix();
    }

    function syncContextBannerOffset() {
      const collapsed = leftDrawer.classList.contains('drawer-left-hidden');
      contextBanner.style.left = collapsed && !isCompactViewport() ? '128px' : '';
    }

    drawerShell.setOnChange(() => {
      syncContextBannerOffset();
      updateCameraOffset();
      syncOverviewCameraIfActive(true);
    });

    if (btnSpreadCodex) {
      let leftWasOpenBeforeSpread = false;
      btnSpreadCodex.addEventListener('click', () => {
        const nextSpread = !rightDrawer.classList.contains('codex-spread');
        const compact = isCompactViewport();
        if (nextSpread && compact && !rightDrawer.querySelector('.syzygy-dual-body')) {
          if (appState.restoringDeepLink) flashToast('正在载入对读，请稍候。');
          else { setLeftDrawerCollapsed(false); flashToast('先从目录选择一条心物对读。'); }
          return;
        }
        rightDrawer.classList.toggle('codex-spread', nextSpread);
        btnSpreadCodex.setAttribute('aria-pressed', String(nextSpread));
        btnSpreadCodex.textContent = nextSpread ? (compact ? '收起对读' : '单卷阅读') : '展卷并读';
        if (nextSpread) {
          if (rightDrawer.classList.contains('drawer-right-hidden')) setRightDrawerCollapsed(false);
          if (!compact && !leftDrawer.classList.contains('drawer-left-hidden')) {
            leftWasOpenBeforeSpread = true;
            setLeftDrawerCollapsed(true);
          } else {
            leftWasOpenBeforeSpread = false;
          }
        } else if (leftWasOpenBeforeSpread && window.innerWidth >= 1024) {
          leftWasOpenBeforeSpread = false;
          setLeftDrawerCollapsed(false);
        }
        updateCameraOffset();
        syncOverviewCameraIfActive(true);
        if (nextSpread && compact) {
          rightDrawer.querySelector('.syzygy-dual-body')?.scrollIntoView({
            behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start',
          });
        }
      });
    }

    // The canvas and its geometry stay unchanged; the reading codex shifts between 深空金错 and 古拓羊皮.
    const btnDarkTheme = document.getElementById('theme-btn-dark');
    const btnParchmentTheme = document.getElementById('theme-btn-parchment');
    const applyEngravingTheme = theme => {
      const parchment=theme === 'parchment';
      document.body.dataset.engravingTheme=parchment ? 'parchment' : 'obsidian';
      rightDrawer.classList.toggle('parchment-scroll',parchment);
      btnDarkTheme.setAttribute('aria-pressed',String(!parchment));
      btnParchmentTheme.setAttribute('aria-pressed',String(parchment));
      try { localStorage.setItem('astraia-engraving-theme',parchment ? 'parchment' : 'obsidian'); } catch { /* Private browsing can disable storage. */ }
    };
    btnDarkTheme.addEventListener('click',()=>applyEngravingTheme('obsidian'));
    btnParchmentTheme.addEventListener('click',()=>applyEngravingTheme('parchment'));
    let storedTheme='obsidian';
    try { storedTheme=localStorage.getItem('astraia-engraving-theme') || 'obsidian'; } catch { /* Use the default. */ }
    applyEngravingTheme(storedTheme);

    // Live Search Input & Cmd+K Shortcut (co-located inside Left Atlas Drawer)
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
        setLeftDrawerCollapsed(false);
        searchInput.focus();
      }
    });

    // Preserve a directory or dossier opened while the scene was loading.
    syncContextBannerOffset();
    updateCameraOffset();
    syncOverviewCameraIfActive(false);

    window.addEventListener('resize', () => {
      if (isCompactViewport() && !leftDrawer.classList.contains('drawer-left-hidden')
        && !rightDrawer.classList.contains('drawer-right-hidden')) setLeftDrawerCollapsed(true);
      const dpr = renderPixelRatio();
      syncContextBannerOffset();
      updateCameraOffset();
      syncOverviewCameraIfActive(false);
      renderer.setPixelRatio(dpr);
      renderer.setSize(window.innerWidth, window.innerHeight);
      membrane.resize(window.innerWidth, window.innerHeight, Math.min(dpr, 1.5));
      membraneRefraction.resize(window.innerWidth, window.innerHeight, dpr);
      starUniforms.uPixelRatio.value = dpr;
      const obsViewportEl = document.getElementById('obs-viewport');
      if (obsViewportEl) obsViewportEl.textContent = `${window.innerWidth} × ${window.innerHeight}`;
    });

    // ============================================================================
    // 13. 60FPS ANIMATION, GPU/JS PARTICLE MORPHING & 3D LABEL PROJECTION LOOP
    // ============================================================================
    const tmpProj = new THREE.Vector3();
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let lastSoftwareFrame = 0;
    let lastClockSec = -1;
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
      starUniforms.uTime.value = appState.dimension === 'sidera' ? sideraSculpts.motionTime : t;

      // 1. Camera Smooth Fly-To Interpolation
      if (appState.camAnim) {
        const u = Math.min((nowMs - appState.camAnim.startTime) / appState.camAnim.duration, 1);
        const ease = 1 - Math.pow(1 - u, 4);
        camera.position.lerpVectors(appState.camAnim.startPos, appState.camAnim.endPos, ease);
        controls.target.lerpVectors(appState.camAnim.startTarget, appState.camAnim.endTarget, ease);
        if (u >= 1) appState.camAnim = null;
      }

      // 2. Smoothly Morph OMNIA Primary Stars (only while in OMNIA) & Dust across dimensions
      let positionsMoving = false;
      if (appState.dimension === 'omnia') {
        const pPos = primaryGeo.getAttribute('position').array;
        const pCol = primaryGeo.getAttribute('aColor').array;

        for (let i = 0; i < pCount; i++) {
          const n = PRIMARY_NODES[i];
          const targetP = appState.is2DPlanisphere ? n.posOmnia2D : n.posOmnia3D;
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

            n.curCol.lerp(n.colOmnia, 0.09);
            pCol[i * 3] = n.curCol.r;
            pCol[i * 3 + 1] = n.curCol.g;
            pCol[i * 3 + 2] = n.curCol.b;
          }
        }
        if (positionsMoving) {
          primaryGeo.getAttribute('position').needsUpdate = true;
          primaryGeo.getAttribute('aColor').needsUpdate = true;
        }
      }

      if (positionsMoving || dustNeedsMorph) {
        const dPos = dustGeo.getAttribute('position').array;
        const dCol = dustGeo.getAttribute('aColor').array;
        let maxDustDeltaSq = 0;
        for (let i = 0; i < DUST_COUNT; i++) {
          const d = dustParticles[i];
          const tp = appState.dimension === 'umbra'
            ? d.pUmbra
            : (appState.dimension === 'sidera' ? d.pSidera : (appState.is2DPlanisphere ? d.p2D : d.pOmnia));
          const tc = appState.dimension === 'umbra'
            ? d.cUmbra
            : (appState.dimension === 'sidera' ? d.cSidera : d.cOmnia);

          const ddx = tp.x - dPos[i * 3];
          const ddy = tp.y - dPos[i * 3 + 1];
          const ddz = tp.z - dPos[i * 3 + 2];
          const dSq = ddx * ddx + ddy * ddy + ddz * ddz;
          if (dSq > maxDustDeltaSq) maxDustDeltaSq = dSq;

          dPos[i * 3] += ddx * 0.085;
          dPos[i * 3 + 1] += ddy * 0.085;
          dPos[i * 3 + 2] += ddz * 0.085;

          dCol[i * 3] += (tc.r - dCol[i * 3]) * 0.09;
          dCol[i * 3 + 1] += (tc.g - dCol[i * 3 + 1]) * 0.09;
          dCol[i * 3 + 2] += (tc.b - dCol[i * 3 + 2]) * 0.09;
        }
        dustGeo.getAttribute('position').needsUpdate = true;
        dustGeo.getAttribute('aColor').needsUpdate = true;
        dustNeedsMorph = maxDustDeltaSq > 0.04;
      }

      if (sideraFilamentGroup.visible && sideraFade < 1) {
        sideraFade = Math.min(1, sideraFade + 0.06);
        sideraSculpts.setFade(sideraFade);
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

      // 3. Living Sculpted Galaxies/Constellations & Balanced Cosmic Breathing Parallax
      if (omniaScaffold.visible) animateOmniaGalaxies(omniaGalaxies, t);
      if (sideraFilamentGroup.visible) sideraSculpts.animate(t);
      if (!reducedMotion && !appState.is2DPlanisphere && !appState.hoveredTarget
        && (appState.dimension !== 'sidera' || appState.sideraTempo !== 'still')) {
        if (appState.dimension === 'umbra') {
          cosmosGroup.rotation.y += 0.00075;
          cosmosGroup.rotation.x += (0 - cosmosGroup.rotation.x) * 0.05;
        } else {
          const parallaxTime = appState.dimension === 'sidera' ? sideraSculpts.motionTime : t;
          const tgtY = Math.sin(parallaxTime * 0.14) * 0.15;
          const tgtX = Math.sin(parallaxTime * 0.10) * 0.04;
          cosmosGroup.rotation.y += (tgtY - cosmosGroup.rotation.y) * 0.03;
          cosmosGroup.rotation.x += (tgtX - cosmosGroup.rotation.x) * 0.03;
        }
      } else if (appState.is2DPlanisphere) {
        cosmosGroup.rotation.x = 0;
      }

      // 4. Glide Photon Pulses along Cubic Bezier Syzygy Bridges
      activePhotonPulses.forEach(p => {
        const motionTime = appState.dimension === 'sidera' ? sideraSculpts.motionTime : t;
        const u = (motionTime * p.speed + p.offset) % 1.0;
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
          const offsetY = item.vol.id === 'vol1' ? -58 : -64;
          const wp = item.vol.center.clone().add(new THREE.Vector3(0, offsetY, 0)).applyMatrix4(cosmosGroup.matrixWorld);
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
          if (appState.dimension !== 'sidera' || appState.sideraFocus !== 'all') {
            item.el.style.opacity = '0';
            item.el.style.pointerEvents = 'none';
            return;
          }
          const offsetY = (item.cl.id === 'sid_witch' || item.cl.id === 'sid_crypt') ? -62 : -64;
          const wp = item.cl.center.clone().add(new THREE.Vector3(0, offsetY, 0)).applyMatrix4(cosmosGroup.matrixWorld);
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

      membraneRefraction.render(scene, camera, nowMs);
      membrane.render(nowMs, { lunarPhase: lunarInfo.phase, isSoftware: renderer.isSoftware });
      const nowSec = Math.floor(nowMs * 0.001);
      if (nowSec !== lastClockSec) {
        lastClockSec = nowSec;
        const obsClockEl = document.getElementById('obs-clock');
        if (obsClockEl && !document.getElementById('observer-veil-hud')?.hidden) {
          obsClockEl.textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
        }
      }
    }

    // ============================================================================
    // 14. BOOTSTRAP ON WINDOW LOAD
    // ============================================================================
    buildWorldDOMAnchors();
    worldLabelsEl.appendChild(userPortalLabel);
    document.getElementById('stats-entries').textContent = book.entries.length.toLocaleString();
    document.getElementById('stats-subjects').textContent = book.subjects.length.toLocaleString();
    document.getElementById('stats-matches').textContent = appState.substantiveMatchCount != null
      ? appState.substantiveMatchCount.toLocaleString()
      : '—';
    const fictionButton = document.getElementById('btn-fiction');
    document.querySelectorAll('[data-tier]').forEach(button=>{
      const tier = button.dataset.tier;
      const meta = TIER_META[tier];
      button.innerHTML=tierSeal(tier);
      button.title = meta ? `${meta.title}（${meta.summary}）` : `${tier} 级信源`;
      button.setAttribute('aria-label', meta ? meta.title : `${tier} 级信源`);
    });
    function syncTierButtons() {
      fictionButton.setAttribute('aria-checked', String(!appState.showF));
      document.querySelectorAll('[data-tier]').forEach(button=>button.setAttribute('aria-pressed',String(appState.tiers.has(button.dataset.tier))));
    }
    function toggleTier(tier, eventOrEl) {
      if (isBeyondMembrane(appState.membraneDepth)) {
        const pt = eventOrEl?.clientX ? { x: eventOrEl.clientX, y: eventOrEl.clientY } : elementCenter(eventOrEl?.currentTarget || eventOrEl);
        triggerBlockedMembrane(pt.x, pt.y);
        return;
      }
      if (appState.tiers.has(tier)) appState.tiers.delete(tier); else appState.tiers.add(tier);
      appState.showF = appState.tiers.has('F'); syncTierButtons();
      const selectedHidden = (appState.selectedBridge && !bridgeAllowed(appState.selectedBridge))
        || (appState.selectedGraph && (!appState.tiers.has(appState.selectedGraph.credibility_tier)
          || (!appState.showF && appState.selectedGraph.is_fictional_quarantine)));
      if (selectedHidden) {
        appState.selectedBridge=null; appState.selectedGraph=null; appState.selectedBook=null;
        clearPersonalPortal(); fullAtlas.clearNeighborhood(); renderDualPaneSyzygyCard(null);
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
      if (isBeyondMembrane(appState.membraneDepth)) {
        genreSelect.value = appState.genre;
        const pt = elementCenter(genreSelect);
        triggerBlockedMembrane(pt.x, pt.y);
        return;
      }
      appState.genre=genreSelect.value;
      const hiddenBridge=appState.selectedBridge && !bridgeAllowed(appState.selectedBridge);
      const hiddenNode=appState.selectedGraph && !fullAtlas.isVisible(appState.selectedGraph);
      if (hiddenBridge || hiddenNode) {
        appState.selectedBridge=null; appState.selectedGraph=null; appState.selectedBook=null;
        clearPersonalPortal(); fullAtlas.clearNeighborhood(); renderDualPaneSyzygyCard(null);
      }
      appState.scopeTab='supplement';
      appState.lastNonTaxonomyScope='supplement';
      if (taxonomyExplorer) taxonomyExplorer.hidden = true;
      if (taxonomyDockBtn) taxonomyDockBtn.setAttribute('aria-expanded', 'false');
      document.querySelectorAll('.scope-tab').forEach(tab=>tab.classList.toggle('active',tab.dataset.scope === 'supplement'));
      fullAtlas.refreshFilters(); updateHighlightsAndFilters(); renderLeftAtlasTree(); updateClassicLink(); syncViewURL();
      appState.needsBridgeRebuild=true;
    });
    fictionButton.addEventListener('click', (e) => toggleTier('F', e));
    document.querySelectorAll('[data-tier]').forEach(button=>button.addEventListener('click',(e)=>toggleTier(button.dataset.tier, e)));

    // Syzygy Membrane Instrument, Five Realms & Fourth-Wall Observer HUD
    const lunarPill = document.getElementById('lunar-phase-pill');
    if (lunarPill) lunarPill.textContent = `◐ ${lunarInfo.syzygyLabel}`;
    const membraneSlider = document.getElementById('membrane-depth-slider');
    const audioBtn = document.getElementById('btn-membrane-audio');
    const observerHud = document.getElementById('observer-veil-hud');

    renderObserverHud = () => {
      if (!observerHud) return;
      const realm = realmForDepth(appState.membraneDepth);
      const showHud = realm.id === 'yi' && !appState.observerHudDismissed;
      observerHud.hidden = !showHud;
      if (!showHud) return;
      const summary = summarizeObserverBalance(observerTrace);
      const clockEl = document.getElementById('obs-clock');
      const lunarEl = document.getElementById('obs-lunar');
      const viewportEl2 = document.getElementById('obs-viewport');
      const ripplesEl = document.getElementById('obs-ripples');
      const titleEl = document.getElementById('obs-balance-title');
      const markerEl = document.getElementById('obs-balance-marker');
      const reflEl = document.getElementById('obs-balance-reflection');
      if (clockEl) clockEl.textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
      if (lunarEl) lunarEl.textContent = `${lunarInfo.phaseName} (${Math.round(lunarInfo.illumination * 100)}%)`;
      if (viewportEl2) viewportEl2.textContent = `${window.innerWidth} × ${window.innerHeight}`;
      if (ripplesEl) ripplesEl.textContent = `${observerTrace.rippleCount} 次`;
      if (titleEl) titleEl.textContent = summary.label;
      if (markerEl) {
        const pct = Math.max(6, Math.min(94, (1 - summary.physisRatio) * 100));
        markerEl.style.left = `${pct.toFixed(1)}%`;
      }
      if (reflEl) reflEl.textContent = summary.reflection;
    };

    let realmCardRenderSeq = 0;

    function setMembraneDepth(nextDepth, { fromSlider = false, flyCamera = true, silent = false } = {}) {
      const prevDepth = appState.membraneDepth;
      const prevRealm = realmForDepth(prevDepth);
      const d = clampDepth(nextDepth);
      appState.membraneDepth = d;
      const realm = realmForDepth(d);
      const wasBeyond = isBeyondMembrane(prevDepth);
      const nowBeyond = isBeyondMembrane(d);
      if (realm.id === 'yi' && prevRealm.id !== 'yi') appState.observerHudDismissed = false;

      document.body.dataset.realm = realm.id;
      document.body.dataset.beyondMembrane = String(nowBeyond);
      document.querySelectorAll('.realm-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.realm === realm.id);
      });
      if (!fromSlider && membraneSlider) membraneSlider.value = String(d);

      const viewport = getClearViewportMetrics();
      membrane.setDepth(d, { silent, origin: { x: viewport.w / 2 - viewport.shiftX, y: viewport.h / 2 - viewport.shiftY } });
      membraneAudio.setDepth(d);
      if (!silent && wasBeyond !== nowBeyond) {
        recordObs({ type: 'cross', label: `${realm.rank} ${realm.char}` });
      }

      let switchedDim = false;
      if (flyCamera && !fromSlider) {
        if (realm.id === 'jian' && appState.dimension !== 'sidera') {
          switchedDim = switchDimension('sidera', false);
        } else if (realm.id === 'xi' && appState.dimension !== 'omnia') {
          switchedDim = switchDimension('omnia', false);
        } else if (realm.id === 'yi') {
          appState.isOverview = false;
          animateCameraTo(new THREE.Vector3(0, 138, 960), new THREE.Vector3(0, 0, 0), 1100);
        } else if ((realm.id === 'human' || realm.id === 'threshold') && (prevRealm.id === 'yi' || wasBeyond)) {
          appState.isOverview = true;
          const preset = getOverviewPreset(appState.dimension);
          animateCameraTo(preset.pos, preset.target, 980);
        }
      }

      if (!fromSlider && prevRealm.id !== realm.id && appState.selectedBridge) {
        const seq = ++realmCardRenderSeq;
        const targetBridge = appState.selectedBridge;
        requestAnimationFrame(() => {
          if (seq === realmCardRenderSeq && appState.selectedBridge === targetBridge) {
            renderDualPaneSyzygyCard(targetBridge);
          }
        });
      }
      if (!switchedDim) {
        updateHighlightsAndFilters();
        syncViewURL();
      }
      renderObserverHud();
      if (!silent && prevRealm.id !== realm.id) {
        flashToast(`${realm.rank} ${realm.label}：${realm.classicalQuote}`);
      }
    }

    document.querySelectorAll('.realm-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        setMembraneDepth(Number(btn.dataset.depth), { fromSlider: false, flyCamera: true, silent: false });
      });
    });
    membraneSlider?.addEventListener('input', () => {
      setMembraneDepth(Number(membraneSlider.value), { fromSlider: true, flyCamera: false, silent: false });
    });
    membraneSlider?.addEventListener('change', () => {
      if (appState.selectedBridge) renderDualPaneSyzygyCard(appState.selectedBridge);
    });
    audioBtn?.addEventListener('click', async () => {
      const nextState = await membraneAudio.setEnabled(!membraneAudio.isEnabled());
      audioBtn.setAttribute('aria-pressed', String(nextState));
      audioBtn.classList.toggle('active', nextState);
      const span = audioBtn.querySelector('span');
      if (span) span.textContent = nextState ? '声景：启' : '声景：静';
      flashToast(nextState ? '已开启界膜微澜声景' : '已静音界膜声景');
    });
    document.getElementById('btn-observer-close')?.addEventListener('click', () => {
      appState.observerHudDismissed = true;
      renderObserverHud();
    });
    document.getElementById('btn-obs-return')?.addEventListener('click', () => {
      setMembraneDepth(0, { fromSlider: false, flyCamera: true, silent: false });
    });
    document.getElementById('btn-obs-zibuyu')?.addEventListener('click', async () => {
      try {
        await fullAtlas.start();
        const zNode = fullAtlas.getNode('case_cn_zibuyu_v03_s023');
        if (!zNode) {
          flashToast('正在加载完整图谱目录，请稍候再试。');
          return;
        }
        if (!fullAtlas.isVisible(zNode)) {
          flashToast('当前筛选隐藏了《子不语》条目，请先返膜调整信源或体裁筛选。');
          return;
        }
        if (window.innerWidth < 1100) {
          appState.observerHudDismissed = true;
          renderObserverHud();
        }
        fullAtlas.openPortal(zNode, 'PHI-6-0002');
      } catch (error) {
        flashToast(`无法打开典籍示范：${error.message}`);
      }
    });
    setMembraneDepth(appState.membraneDepth, { fromSlider: false, flyCamera: false, silent: true });
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
      const navRealm = realmById(params.get('realm'));
      setMembraneDepth(navRealm ? navRealm.depth : DEFAULT_MEMBRANE_DEPTH, { fromSlider: false, flyCamera: false, silent: true });
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
          renderDualPaneSyzygyCard(null);
        } else missing('未找到对应资料，请从目录重新选择。');
        renderLeftAtlasTree(); updateClassicLink(); syncViewURL();
      }).catch(error=>flashToast(`图谱载入失败：${error.message}`));
    });
    renderLeftAtlasTree();
    renderDualPaneSyzygyCard(appState.selectedBridge);
    if (appState.restoringDeepLink) document.getElementById('syzygy-card-container').innerHTML='<p class="syzygy-reference" role="status">正在定位资料…</p>';
    updateHighlightsAndFilters();
    rebuildSyzygyPhotonBridges();
    // The initial membrane setup can update the URL; retain the requested route.
    const initial = initialParams;
    const dimension = ['umbra','sidera','omnia'].includes(initial.get('dim')) ? initial.get('dim') : 'omnia';
    if (dimension !== 'omnia') switchDimension(dimension, false, true);
    else { document.body.dataset.dimension = 'omnia'; updateClassicLink(); }
    document.getElementById('syzygy-loading')?.remove();
    drawerShell.markReady();
    announceViewReady();
    requestAnimationFrame(animateLoop);
    setTimeout(() => fullAtlas.start().then(() => {
      renderLeftAtlasTree();
      if (appState.scopeTab === 'taxonomy') renderTaxonomyExplorer();
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
