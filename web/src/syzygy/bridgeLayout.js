import * as THREE from 'three';

export const MAX_LEAD_ANCHORS = 24;
export const MAX_SECONDARY_ANCHORS = 48;
export const MAX_ASTERISM_SEGMENTS = 96;
export const MAX_OMNIA_OVERVIEW_CURVES = 12;
export const MAX_ACTIVE_CURVES = 18;
export const ORBITAL_LANE_COUNT = 5;

const TWO_PI = Math.PI * 2;
const PHI_INV = (Math.sqrt(5) - 1) / 2;
const DEFAULT_TRAILS = ['trail1', 'trail2', 'trail3', 'trail4', 'trail5'];

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const angularDiff = (a, b) => Math.abs(Math.atan2(Math.sin(a - b), Math.cos(a - b)));

function hashBridgeId(id) {
  let bHash = 2166136261;
  const text = String(id ?? '');
  for (let i = 0; i < text.length; i++) {
    bHash = Math.imul(bHash ^ text.charCodeAt(i), 16777619);
  }
  const u1 = (bHash >>> 0) / 4294967296;
  const u2 = (Math.imul(bHash, 2246822519) >>> 0) / 4294967296;
  return { u1, u2 };
}

function getClusterId(bridge) {
  return bridge?.sideraCluster ?? bridge?.cluster ?? null;
}

function getTrailId(bridge) {
  const t = bridge?.trail;
  return t && t !== 'all' ? t : null;
}

function getVolId(bridge) {
  return bridge?.physis?.volId ?? bridge?.volId ?? null;
}

function getAngle(bridge) {
  if (Number.isFinite(bridge?.angle)) return bridge.angle;
  if (Number.isFinite(bridge?.omniaAngle)) return bridge.omniaAngle;
  if (Number.isFinite(bridge?.parentAng)) return bridge.parentAng;
  return 0;
}

function computeOmniaSpan(bridge) {
  if (bridge?.posOmniaSyzygy && bridge?.materialNode?.posOmnia3D) {
    return bridge.posOmniaSyzygy.distanceTo(bridge.materialNode.posOmnia3D);
  }
  return angularDiff(getAngle(bridge), bridge?.parentAng ?? 0);
}

function segmentsCross2D(a, b, c, d) {
  const eps = 1e-6;
  if (
    Math.hypot(a.x - c.x, a.y - c.y) < eps || Math.hypot(a.x - d.x, a.y - d.y) < eps
    || Math.hypot(b.x - c.x, b.y - c.y) < eps || Math.hypot(b.x - d.x, b.y - d.y) < eps
  ) {
    return false;
  }
  const cross = (p, q, r) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x);
  const d1 = cross(a, b, c);
  const d2 = cross(a, b, d);
  const d3 = cross(c, d, a);
  const d4 = cross(c, d, b);
  return ((d1 > eps && d2 < -eps) || (d1 < -eps && d2 > eps))
    && ((d3 > eps && d4 < -eps) || (d3 < -eps && d4 > eps));
}

/**
 * Compute stratified 5-lane zodiac coordinates and magnitude tiers for 634..2,000+ bridges.
 */
export function computeZodiacBridgeLayout(orderedBridges, opts = {}) {
  if (!Array.isArray(orderedBridges) || orderedBridges.length === 0) {
    return { bridges: [], densityScale: 1, leadCount: 0, secondaryCount: 0, dustCount: 0 };
  }

  const total = orderedBridges.length;
  const maxLead = Math.max(0, Math.min(opts.maxLeadAnchors ?? MAX_LEAD_ANCHORS, total));
  const maxSecondary = Math.max(0, Math.min(opts.maxSecondaryAnchors ?? MAX_SECONDARY_ANCHORS, total - maxLead));
  const densityScale = clamp(Math.sqrt(180 / Math.max(180, total)), 0.42, 1.0);
  const stepAng = TWO_PI / Math.max(1, total);

  const hashes = new Array(total);
  const angles = new Array(total);
  const lanes = new Array(total);
  const radii = new Array(total);
  const zs = new Array(total);

  for (let rank = 0; rank < total; rank++) {
    const bridge = orderedBridges[rank];
    const h = hashBridgeId(bridge.id);
    hashes[rank] = h;

    const lane = rank % ORBITAL_LANE_COUNT;
    const gr = ((rank * PHI_INV) % 1) - 0.5;
    const baseAng = -Math.PI + ((rank + 0.5) / total) * TWO_PI;
    const angJitter = (gr * 0.42 + (h.u1 - 0.5) * 0.48) * Math.min(0.032, stepAng * 1.4);
    const angle = baseAng + angJitter;
    const radius = clamp(238 + lane * 11 + gr * 6.5 + (h.u2 - 0.5) * 3.0, 234, 286);
    const z = clamp(19 + lane * 7.5 + Math.sin(angle * 3 + h.u1 * TWO_PI) * 3.2 + (h.u2 - 0.5) * 2.0, 16, 52);

    lanes[rank] = lane;
    angles[rank] = angle;
    radii[rank] = radius;
    zs[rank] = z;
  }

  const presentClusters = new Set();
  const presentTrails = new Set();
  const presentVolumes = new Set();
  const allowedTrails = new Set(opts.trails ?? DEFAULT_TRAILS);

  for (let i = 0; i < total; i++) {
    const b = orderedBridges[i];
    const cl = getClusterId(b);
    const tr = getTrailId(b);
    const vol = getVolId(b);
    if (cl) presentClusters.add(cl);
    if (tr && allowedTrails.has(tr)) presentTrails.add(tr);
    if (vol) presentVolumes.add(vol);
  }
  if (Array.isArray(opts.sideraClusters)) {
    for (const item of opts.sideraClusters) {
      const id = typeof item === 'string' ? item : item?.id;
      if (id && orderedBridges.some(b => getClusterId(b) === id)) presentClusters.add(id);
    }
  }
  if (Array.isArray(opts.volumes)) {
    for (const item of opts.volumes) {
      const id = typeof item === 'string' ? item : item?.id;
      if (id && orderedBridges.some(b => getVolId(b) === id)) presentVolumes.add(id);
    }
  }

  const coveredClusters = new Set();
  const coveredTrails = new Set();
  const coveredVolumes = new Set();
  const leadRanks = new Set();
  const nearestLeadDist = new Float64Array(total).fill(Math.PI);

  const addLead = (rank) => {
    leadRanks.add(rank);
    const cl = getClusterId(orderedBridges[rank]);
    const tr = getTrailId(orderedBridges[rank]);
    const vol = getVolId(orderedBridges[rank]);
    if (cl) coveredClusters.add(cl);
    if (tr && presentTrails.has(tr)) coveredTrails.add(tr);
    if (vol) coveredVolumes.add(vol);
    const ang = angles[rank];
    for (let i = 0; i < total; i++) {
      const d = angularDiff(angles[i], ang);
      if (d < nearestLeadDist[i]) nearestLeadDist[i] = d;
    }
  };

  while (
    leadRanks.size < maxLead
    && (
      coveredClusters.size < presentClusters.size
      || coveredTrails.size < presentTrails.size
      || coveredVolumes.size < presentVolumes.size
    )
  ) {
    let bestRank = -1;
    let bestScore = -1;
    for (let i = 0; i < total; i++) {
      if (leadRanks.has(i)) continue;
      const b = orderedBridges[i];
      const cl = getClusterId(b);
      const tr = getTrailId(b);
      const vol = getVolId(b);
      let newlyCovered = 0;
      if (cl && presentClusters.has(cl) && !coveredClusters.has(cl)) newlyCovered++;
      if (tr && presentTrails.has(tr) && !coveredTrails.has(tr)) newlyCovered++;
      if (vol && presentVolumes.has(vol) && !coveredVolumes.has(vol)) newlyCovered++;
      if (newlyCovered === 0) continue;
      const score = newlyCovered * 100 + nearestLeadDist[i];
      if (score > bestScore) {
        bestScore = score;
        bestRank = i;
      }
    }
    if (bestRank === -1) break;
    addLead(bestRank);
  }

  while (leadRanks.size < maxLead) {
    let bestRank = -1;
    let bestDist = -1;
    for (let i = 0; i < total; i++) {
      if (leadRanks.has(i)) continue;
      const d = leadRanks.size === 0 ? (i === 0 ? 1 : 0) : nearestLeadDist[i];
      if (d > bestDist) {
        bestDist = d;
        bestRank = i;
      }
    }
    if (bestRank === -1) break;
    addLead(bestRank);
  }

  const secondaryRanks = new Set();
  const nearestAnchorDist = Float64Array.from(nearestLeadDist);
  while (secondaryRanks.size < maxSecondary) {
    let bestRank = -1;
    let bestDist = -1;
    for (let i = 0; i < total; i++) {
      if (leadRanks.has(i) || secondaryRanks.has(i)) continue;
      const d = nearestAnchorDist[i];
      if (d > bestDist) {
        bestDist = d;
        bestRank = i;
      }
    }
    if (bestRank === -1) break;
    secondaryRanks.add(bestRank);
    const ang = angles[bestRank];
    for (let i = 0; i < total; i++) {
      const d = angularDiff(angles[i], ang);
      if (d < nearestAnchorDist[i]) nearestAnchorDist[i] = d;
    }
  }

  const clusterGroups = new Map();
  for (let i = 0; i < total; i++) {
    const cl = getClusterId(orderedBridges[i]) ?? '_default';
    if (!clusterGroups.has(cl)) clusterGroups.set(cl, []);
    clusterGroups.get(cl).push(i);
  }
  const sideraClusterLeadRanks = new Set();
  for (const ranks of clusterGroups.values()) {
    const pickMax = Math.min(3, ranks.length);
    const chosen = new Set();
    for (let k = 0; k < pickMax; k++) {
      const winStart = Math.floor((k * ranks.length) / pickMax);
      const winEnd = Math.max(winStart + 1, Math.floor(((k + 1) * ranks.length) / pickMax));
      let pick = ranks[Math.floor((winStart + winEnd - 1) / 2)];
      for (let w = winStart; w < winEnd; w++) {
        if (leadRanks.has(ranks[w])) {
          pick = ranks[w];
          break;
        }
      }
      if (!chosen.has(pick)) {
        chosen.add(pick);
        sideraClusterLeadRanks.add(pick);
      }
    }
    for (const r of ranks) {
      if (chosen.size >= pickMax) break;
      if (!chosen.has(r)) {
        chosen.add(r);
        sideraClusterLeadRanks.add(r);
      }
    }
  }

  const secScale = clamp(0.65 + 0.35 * densityScale, 0.78, 1.0);
  const dustHighScale = clamp(0.75 + 0.25 * densityScale, 0.85, 1.0);

  for (let rank = 0; rank < total; rank++) {
    const bridge = orderedBridges[rank];
    const { u1, u2 } = hashes[rank];
    const lane = lanes[rank];
    const angle = angles[rank];
    const radius = radii[rank];
    const z = zs[rank];
    const isLeadAnchor = leadRanks.has(rank);
    const isSecondaryAnchor = secondaryRanks.has(rank);
    const tier = isLeadAnchor ? 'lead' : (isSecondaryAnchor ? 'secondary' : 'dust');

    const baseSizeOmnia = isLeadAnchor
      ? 14.5 + u2 * 2.0
      : (isSecondaryAnchor ? (8.8 + u2 * 1.8) * secScale : (4.2 + u2 * 1.6) * densityScale);
    const baseSpikeOmnia = isLeadAnchor
      ? 0.68 + u1 * 0.14
      : (isSecondaryAnchor ? 0.22 + u1 * 0.10 : 0.0);
    const baseHighOmnia = isLeadAnchor
      ? 1.30 + u1 * 0.12
      : (isSecondaryAnchor ? 0.96 + u1 * 0.12 : (0.64 + u1 * 0.14) * dustHighScale);

    const posOmniaSyzygy = new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, z);

    bridge.rank = rank;
    bridge.zodiacRank = rank;
    bridge.lane = lane;
    bridge.zodiacBand = lane;
    bridge.angle = angle;
    bridge.omniaAngle = angle;
    bridge.radius = radius;
    bridge.z = z;
    bridge.isLeadAnchor = isLeadAnchor;
    bridge.isSecondaryAnchor = isSecondaryAnchor;
    bridge.isSideraClusterLead = sideraClusterLeadRanks.has(rank);
    bridge.tier = tier;
    bridge.densityScale = densityScale;
    bridge.baseSizeOmnia = baseSizeOmnia;
    bridge.baseSpikeOmnia = baseSpikeOmnia;
    bridge.baseHighOmnia = baseHighOmnia;
    bridge.posOmniaSyzygy = posOmniaSyzygy;
  }

  return {
    bridges: orderedBridges,
    densityScale,
    leadCount: leadRanks.size,
    secondaryCount: secondaryRanks.size,
    dustCount: total - leadRanks.size - secondaryRanks.size,
  };
}

/**
 * Build at most 96 non-crossing constellation segments exclusively between Lead + Secondary anchors.
 */
export function buildLeadAsterismSegments(orderedBridges) {
  if (!Array.isArray(orderedBridges) || orderedBridges.length < 2) return [];

  const anchors = orderedBridges
    .filter(b => b && (b.isLeadAnchor || b.isSecondaryAnchor) && b.posOmniaSyzygy)
    .sort((a, b) => getAngle(a) - getAngle(b) || String(a.id).localeCompare(String(b.id)));

  if (anchors.length < 2) return [];

  const pairs = [];
  const usedEdges = new Set();
  const edgeKey = (i, j) => (i < j ? `${i}:${j}` : `${j}:${i}`);

  const tryAdd = (i, j) => {
    if (pairs.length >= MAX_ASTERISM_SEGMENTS) return false;
    const key = edgeKey(i, j);
    if (usedEdges.has(key)) return false;
    const a = anchors[i];
    const b = anchors[j];
    const pA = a.posOmniaSyzygy;
    const pB = b.posOmniaSyzygy;
    for (const [eStart, eEnd] of pairs) {
      if (segmentsCross2D(pA, pB, eStart, eEnd)) return false;
    }
    usedEdges.add(key);
    pairs.push([pA, pB]);
    return true;
  };

  const count = anchors.length;
  for (let i = 0; i < count && pairs.length < MAX_ASTERISM_SEGMENTS; i++) {
    const j = (i + 1) % count;
    if (i === j) continue;
    const a = anchors[i];
    const b = anchors[j];
    const angGap = angularDiff(getAngle(a), getAngle(b));
    const dist = a.posOmniaSyzygy.distanceTo(b.posOmniaSyzygy);
    if (angGap > 0.38 || dist > 92) continue;
    if (count >= 24 && i % 7 === 6 && getClusterId(a) !== getClusterId(b)) continue;
    tryAdd(i, j);
  }

  for (let step = 2; step <= 3 && pairs.length < MAX_ASTERISM_SEGMENTS; step++) {
    if (count <= step * 2) break;
    for (let i = 0; i < count && pairs.length < MAX_ASTERISM_SEGMENTS; i++) {
      const j = (i + step) % count;
      const a = anchors[i];
      const b = anchors[j];
      if (!a.isLeadAnchor && !b.isLeadAnchor) continue;
      const angGap = angularDiff(getAngle(a), getAngle(b));
      const dist = a.posOmniaSyzygy.distanceTo(b.posOmniaSyzygy);
      if (angGap > 0.42 || dist > 92) continue;
      if (getClusterId(a) !== getClusterId(b) && dist > 64) continue;
      tryAdd(i, j);
    }
  }

  const pts = [];
  for (const [pA, pB] of pairs) {
    pts.push(pA.clone(), pB.clone());
  }
  return pts;
}

/**
 * Select up to 12 Overview trunks or 18 angularly distributed curves in OMNIA / UMBRA.
 */
export function selectVisibleOmniaCurves(bridges, state = {}) {
  const list = Array.isArray(bridges) ? bridges : [];
  const dimension = state.dimension ?? 'omnia';
  const activeTrail = state.activeTrail ?? 'all';
  const searchTrim = String(state.searchQuery ?? '').trim();
  const bridgeAllowed = typeof state.bridgeAllowed === 'function'
    ? state.bridgeAllowed
    : (b) => !b?.fiction || !!state.showF;
  const maxOverview = Math.max(1, state.maxOverviewCurves ?? MAX_OMNIA_OVERVIEW_CURVES);
  const maxActive = Math.max(1, state.maxActiveCurves ?? MAX_ACTIVE_CURVES);

  const eligible = [];
  const eligibleIds = new Set();
  for (const b of list) {
    if (!b || b === state.portalBridge) continue;
    if (!bridgeAllowed(b)) continue;
    if (dimension === 'umbra' && !b.hasCoordinates) continue;
    if (state.matchingBridgeIds && !state.matchingBridgeIds.has(b.id)) continue;
    if (activeTrail !== 'all' && b.trail !== activeTrail) continue;
    eligible.push(b);
    eligibleIds.add(b.id);
  }

  const pinned = [];
  const seenIds = new Set();
  if (
    dimension === 'omnia'
    && state.portalBridge
    && (!state.portalBridge.fiction || state.showF)
  ) {
    pinned.push(state.portalBridge);
    seenIds.add(state.portalBridge.id ?? '__USER_PORTAL__');
  }
  if (
    state.selectedBridge
    && bridgeAllowed(state.selectedBridge)
    && (dimension !== 'umbra' || state.selectedBridge.hasCoordinates)
    && !seenIds.has(state.selectedBridge.id)
  ) {
    pinned.push(state.selectedBridge);
    seenIds.add(state.selectedBridge.id);
  }

  if (dimension === 'umbra') {
    const umbraCurves = pinned.filter(b => b !== state.portalBridge);
    return {
      curves: umbraCurves,
      totalMatching: eligible.length,
      shownCount: umbraCurves.length,
      truncatedCount: 0,
      overviewBridgeIds: new Set(),
    };
  }

  const isOverview = activeTrail === 'all' && !searchTrim && !state.selectedBook;
  if (isOverview) {
    const volOrder = Array.isArray(state.volumes) && state.volumes.length
      ? state.volumes.map(v => (typeof v === 'string' ? v : v.id))
      : [...new Set(eligible.map(getVolId).filter(Boolean))].sort();

    const firstTrunks = [];
    const secondTrunks = [];

    for (const volId of volOrder) {
      const volBridges = eligible
        .filter(b => getVolId(b) === volId && !seenIds.has(b.id))
        .sort((a, b) => getAngle(a) - getAngle(b) || String(a.id).localeCompare(String(b.id)));
      if (!volBridges.length) continue;

      if (volBridges.length === 1) {
        firstTrunks.push(volBridges[0]);
        continue;
      }

      const mid = Math.ceil(volBridges.length / 2);
      const firstHalf = volBridges.slice(0, mid);
      const secondHalf = volBridges.slice(mid);

      const pickShortest = (arr) => arr.reduce((best, cand) => {
        if (!best) return cand;
        const diff = computeOmniaSpan(cand) - computeOmniaSpan(best);
        if (Math.abs(diff) > 1e-6) return diff < 0 ? cand : best;
        return String(cand.id).localeCompare(String(best.id)) < 0 ? cand : best;
      }, null);

      const p1 = pickShortest(firstHalf);
      const p2 = pickShortest(secondHalf);
      if (p1) firstTrunks.push(p1);
      if (p2 && p2.id !== p1?.id) secondTrunks.push(p2);
    }

    const curves = [...pinned];
    for (const trunk of [...firstTrunks, ...secondTrunks]) {
      if (curves.length >= maxOverview) break;
      if (seenIds.has(trunk.id)) continue;
      seenIds.add(trunk.id);
      curves.push(trunk);
    }

    const overviewBridgeIds = new Set(
      curves.filter(b => b !== state.portalBridge).map(b => b.id),
    );
    return {
      curves,
      totalMatching: eligible.length,
      shownCount: curves.length,
      truncatedCount: 0,
      overviewBridgeIds,
    };
  }

  if (activeTrail === 'all' && !searchTrim && state.selectedBook) {
    const curves = pinned.slice(0, maxActive);
    return {
      curves,
      totalMatching: curves.length,
      shownCount: curves.length,
      truncatedCount: 0,
      overviewBridgeIds: new Set(),
    };
  }

  const curves = [...pinned.slice(0, maxActive)];
  const activeSeen = new Set(curves.map(b => b.id ?? '__USER_PORTAL__'));
  const pool = eligible
    .filter(b => !activeSeen.has(b.id))
    .sort((a, b) => getAngle(a) - getAngle(b) || String(a.id).localeCompare(String(b.id)));

  const remainingCap = Math.max(0, maxActive - curves.length);
  if (pool.length <= remainingCap) {
    for (const b of pool) {
      activeSeen.add(b.id);
      curves.push(b);
    }
  } else if (remainingCap > 0) {
    for (let k = 0; k < remainingCap; k++) {
      const start = Math.floor((k * pool.length) / remainingCap);
      const end = Math.max(start + 1, Math.floor(((k + 1) * pool.length) / remainingCap));
      let best = pool[start];
      let bestSpan = computeOmniaSpan(best);
      for (let i = start + 1; i < end; i++) {
        const cand = pool[i];
        const span = computeOmniaSpan(cand);
        if (span < bestSpan - 1e-6) {
          best = cand;
          bestSpan = span;
        }
      }
      if (best && !activeSeen.has(best.id)) {
        activeSeen.add(best.id);
        curves.push(best);
      }
    }
  }

  const matchedShownCount = curves.filter(b => b !== state.portalBridge && eligibleIds.has(b.id)).length;
  const totalMatching = eligible.length;
  const truncatedCount = Math.max(0, totalMatching - matchedShownCount);

  return {
    curves,
    totalMatching,
    shownCount: matchedShownCount,
    truncatedCount,
    overviewBridgeIds: new Set(),
  };
}

/**
 * Select bounded, constellation-preserving curves in SIDERA mode.
 */
export function selectVisibleSideraCurves(sideraVisible, clusters = [], state = {}) {
  const visible = Array.isArray(sideraVisible) ? sideraVisible : [];
  const clusterList = Array.isArray(clusters) ? clusters : [];
  const clusterMap = new Map(clusterList.map(c => [c.id, c]));
  const mode = state.sideraBridgeMode ?? 'bundled';
  const activeTrail = state.activeTrail ?? 'all';
  const maxActive = Math.max(1, state.maxActiveCurves ?? MAX_ACTIVE_CURVES);
  const visibleIds = new Set(visible.map(b => b.id));
  const sel = state.selectedBridge && visibleIds.has(state.selectedBridge.id) ? state.selectedBridge : null;

  const curves = [];
  let totalMatching = visible.length;
  let shownCount = 0;
  let truncatedCount = 0;

  if (mode !== 'minimal' && activeTrail !== 'all') {
    const trailBridges = visible
      .filter(b => b.trail === activeTrail)
      .sort((a, b) => (getClusterId(a) ?? '').localeCompare(getClusterId(b) ?? '') || String(a.id).localeCompare(String(b.id)));
    totalMatching = trailBridges.length;

    let sampled = trailBridges;
    const maxNodes = maxActive + 1;
    if (trailBridges.length > maxNodes) {
      const pickedIdx = new Set();
      if (sel) {
        const selIdx = trailBridges.findIndex(b => b.id === sel.id);
        if (selIdx >= 0) pickedIdx.add(selIdx);
      }
      for (let k = 0; k < maxNodes && pickedIdx.size < maxNodes; k++) {
        const idx = Math.floor(((k + 0.5) * trailBridges.length) / maxNodes);
        pickedIdx.add(clamp(idx, 0, trailBridges.length - 1));
      }
      for (let i = 0; i < trailBridges.length && pickedIdx.size < maxNodes; i++) {
        pickedIdx.add(i);
      }
      sampled = [...pickedIdx].sort((a, b) => a - b).map(idx => trailBridges[idx]);
    }

    for (let k = 0; k < sampled.length - 1 && curves.length < maxActive; k++) {
      const bA = sampled[k];
      const bB = sampled[k + 1];
      curves.push({
        kind: 'trail',
        fromBridge: bA,
        toBridge: bB,
        idx: k,
        baseOpacity: 0.72,
        pulseCount: 1,
        spriteScale: 9.5,
      });
    }
    shownCount = curves.length;
    truncatedCount = trailBridges.length > maxNodes ? Math.max(0, totalMatching - shownCount) : 0;
  }

  if (mode === 'bundled' && activeTrail === 'all') {
    for (const cl of clusterList) {
      const clusterMatches = visible.filter(b => getClusterId(b) === cl.id);
      const rep = clusterMatches.find(b => b.isSideraClusterLead || b.isLeadAnchor) ?? clusterMatches[0];
      if (!rep) continue;
      curves.push({
        kind: 'cluster_trunk',
        fromBridge: rep,
        cluster: cl,
        idx: cl.code?.length ?? 5,
        baseOpacity: 0.27,
        pulseCount: 1,
        spriteScale: 6,
      });
    }
    shownCount = curves.length;
    truncatedCount = 0;
  }

  if (mode === 'full') {
    const byEntry = new Map();
    for (const bridge of visible) {
      const key = bridge?.physis?.id ?? bridge?.entry;
      if (!key) continue;
      if (!byEntry.has(key)) byEntry.set(key, []);
      byEntry.get(key).push(bridge);
    }

    const buckets = new Map();
    let totalCross = 0;
    for (const rows of byEntry.values()) {
      const first = rows[0];
      const other = rows.find(item => getClusterId(item) !== getClusterId(first));
      if (!other) continue;
      totalCross++;
      const cA = getClusterId(first) ?? '';
      const cB = getClusterId(other) ?? '';
      const bucketKey = cA < cB ? `${cA}|${cB}` : `${cB}|${cA}`;
      if (!buckets.has(bucketKey)) buckets.set(bucketKey, []);
      buckets.get(bucketKey).push([first, other]);
    }

    const bucketKeys = [...buckets.keys()].sort();
    const bucketOffset = new Map(bucketKeys.map(k => [k, 0]));
    const remainingBudget = activeTrail === 'all' ? maxActive : Math.max(0, maxActive - curves.length);
    const crossPicked = [];

    while (crossPicked.length < remainingBudget) {
      let progressed = false;
      for (const key of bucketKeys) {
        if (crossPicked.length >= remainingBudget) break;
        const arr = buckets.get(key);
        const pos = bucketOffset.get(key);
        if (pos < arr.length) {
          crossPicked.push(arr[pos]);
          bucketOffset.set(key, pos + 1);
          progressed = true;
        }
      }
      if (!progressed) break;
    }

    crossPicked.forEach(([first, other], idx) => {
      curves.push({
        kind: 'cross_cluster',
        fromBridge: first,
        toBridge: other,
        idx,
        baseOpacity: 0.35,
        pulseCount: 1,
        spriteScale: 7,
      });
    });

    if (activeTrail === 'all') {
      totalMatching = totalCross;
      shownCount = crossPicked.length;
      truncatedCount = Math.max(0, totalCross - crossPicked.length);
    } else if (totalCross > crossPicked.length && truncatedCount === 0) {
      totalMatching = Math.max(totalMatching, totalCross);
      truncatedCount = Math.max(0, totalCross - crossPicked.length);
    }
  }

  if (sel && clusterMap.has(getClusterId(sel))) {
    curves.push({
      kind: 'selected',
      fromBridge: sel,
      cluster: clusterMap.get(getClusterId(sel)),
      idx: 0,
      baseOpacity: 0.85,
      pulseCount: 2,
      spriteScale: 12,
    });
  }

  return {
    curves,
    totalMatching,
    shownCount,
    truncatedCount,
    mode,
  };
}

/**
 * Compute per-dimension magnitude, spike, and highlight styling for a bridge anchor star.
 */
export function computeAdaptiveAnchorStyle(bridge, ctx = {}) {
  if (ctx.visible === false) {
    return { size: 0, spike: 0, highlight: -1 };
  }

  const dimension = ctx.dimension ?? 'omnia';
  const isSel = !!ctx.isSelected;
  const isHover = !!ctx.isHovered;
  const ok = ctx.isMatching !== false;
  const trailActive = !!ctx.trailActive;
  const beyondMembrane = !!ctx.beyondMembrane;
  const { u1, u2 } = hashBridgeId(bridge?.id);

  if (dimension === 'umbra') {
    if (isSel) return { size: 18.5, spike: 0.95, highlight: 2.15 };
    if (isHover) return { size: 15.5, spike: 0.65, highlight: 1.8 };
    if (!ok) return { size: 4.8, spike: 0.0, highlight: 0.12 };
    return {
      size: 5.6 + u2 * 1.6,
      spike: 0.0,
      highlight: trailActive ? 1.15 : 0.88,
    };
  }

  if (dimension === 'sidera') {
    const focus = ctx.sideraFocus ?? 'all';
    const isFocusedCluster = focus !== 'all';
    const isClusterLead = ctx.clusterLeadIds
      ? ctx.clusterLeadIds.has(bridge?.id)
      : !!bridge?.isSideraClusterLead;

    if (isSel) {
      return isFocusedCluster
        ? { size: 16.0, spike: 0.85, highlight: 1.85 }
        : { size: 21.5, spike: 1.10, highlight: 2.15 };
    }
    if (isHover) return { size: 17.5, spike: 0.85, highlight: 1.80 };
    if (!ok) return { size: 3.2, spike: 0.0, highlight: 0.10 };

    if (isFocusedCluster) {
      if (getClusterId(bridge) !== focus) {
        return { size: 3.2, spike: 0.0, highlight: 0.10 };
      }
      if (isClusterLead) {
        return { size: 7.2 + u2 * 1.2, spike: 0.36, highlight: 0.92 };
      }
      if (trailActive) {
        return { size: 5.2 + u2 * 1.4, spike: 0.16, highlight: 0.78 };
      }
      return { size: 3.8 + u2 * 1.4, spike: 0.0, highlight: 0.44 + u1 * 0.12 };
    }

    if (trailActive) {
      if (isClusterLead || bridge?.isLeadAnchor) {
        return { size: 10.5 + u2 * 1.8, spike: 0.48, highlight: 1.25 };
      }
      return { size: 6.4 + u2 * 1.6, spike: 0.16, highlight: 0.95 };
    }

    if (isClusterLead) {
      return {
        size: 9.2 + u2 * 1.8,
        spike: 0.44 + u1 * 0.10,
        highlight: 1.08 + u1 * 0.14,
      };
    }

    return {
      size: 3.6 + u2 * 1.8,
      spike: 0.0,
      highlight: 0.42 + u1 * 0.16,
    };
  }

  // Default: OMNIA dimension
  if (isSel) return { size: 24.0, spike: 1.20, highlight: 2.2 };
  if (isHover) return { size: 20.0, spike: 0.95, highlight: 1.9 };
  if (!ok) {
    return {
      size: Math.min(5.2, (bridge?.baseSizeOmnia ?? 5.0) * 0.8),
      spike: 0.0,
      highlight: 0.12,
    };
  }
  if (trailActive) {
    if (bridge?.isLeadAnchor) return { size: 16.5, spike: 0.72, highlight: 1.48 };
    if (bridge?.isSecondaryAnchor) return { size: 11.8, spike: 0.36, highlight: 1.42 };
    return {
      size: Math.max(6.8, (bridge?.baseSizeOmnia ?? 4.5) * 1.5),
      spike: 0.22,
      highlight: 1.28,
    };
  }

  const baseHigh = bridge?.baseHighOmnia ?? 0.68;
  return {
    size: bridge?.baseSizeOmnia ?? 4.8,
    spike: bridge?.baseSpikeOmnia ?? 0.0,
    highlight: beyondMembrane ? Math.min(1.5, baseHigh + 0.16) : baseHigh,
  };
}
