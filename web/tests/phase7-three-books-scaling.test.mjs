import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { registerHooks } from 'node:module';
import { test } from 'node:test';
import * as THREE from 'three';

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === './graph' && context.parentURL?.endsWith('/catalogueBrowse.ts')) {
      return nextResolve('./graph.ts', context);
    }
    return nextResolve(specifier, context);
  },
});

const { nodeRegion } = await import('../src/catalogueBrowse.ts');
import {
  MAX_ACTIVE_CURVES,
  MAX_ASTERISM_SEGMENTS,
  MAX_LEAD_ANCHORS,
  MAX_OMNIA_OVERVIEW_CURVES,
  MAX_SECONDARY_ANCHORS,
  ORBITAL_LANE_COUNT,
  buildLeadAsterismSegments,
  computeAdaptiveAnchorStyle,
  computeZodiacBridgeLayout,
  selectVisibleOmniaCurves,
  selectVisibleSideraCurves,
} from '../src/syzygy/bridgeLayout.js';
import { normalizeLexiconTerm } from '../scripts/build-taxonomy-lexicon.mjs';

const readJson = async (relPath) => JSON.parse(await readFile(new URL(relPath, import.meta.url), 'utf8'));

const VOLUMES = [
  { id: 'vol1' },
  { id: 'vol2' },
  { id: 'vol3' },
  { id: 'vol4' },
  { id: 'vol5' },
];

const SIDERA_CLUSTERS = [
  { id: 'sid_myth', code: 'MYTH', center: new THREE.Vector3(0, 162, 14) },
  { id: 'sid_hag', code: 'HAG', center: new THREE.Vector3(-174, 46, 16) },
  { id: 'sid_witch', code: 'WITCH', center: new THREE.Vector3(-112, -144, -12) },
  { id: 'sid_crypt', code: 'CRYPT', center: new THREE.Vector3(112, -144, 12) },
  { id: 'sid_liminal', code: 'LIMINAL', center: new THREE.Vector3(174, 46, -14) },
];

const EXPECTED_PHASE7_DOMAIN_COUNTS = {
  wugu_talisman: 220,
  underworld_bureaucracy: 39,
  ghost_rituals_nuo: 39,
  ethnic_spirit_lexicon: 38,
  classical_zhiguai_opera: 139,
  world_mythology: 28,
  modern_liminal: 28,
};

const PHASE7_L1_CASES = [
  { id: 'case_cn_hanyi_festival_winter_robes', bridgeId: 'SYZ-635', entry: 'REL-5-0003', cluster: 'sid_hag' },
  { id: 'case_cn_quanzhou_dachengxi_soul_rescue', bridgeId: 'SYZ-636', entry: 'REL-3-0005', cluster: 'sid_hag' },
  { id: 'case_cn_yijian_changgui_tiger_ghost', bridgeId: 'SYZ-637', entry: 'LIT-2-0004', cluster: 'sid_myth' },
  { id: 'case_cn_eastern_han_dou_song_wugu', bridgeId: 'SYZ-638', entry: 'HIS-6-0006', cluster: 'sid_witch' },
  { id: 'case_cn_zhouli_shushi_chugu', bridgeId: 'SYZ-639', entry: 'SOC-2-0002', cluster: 'sid_witch' },
  { id: 'case_cn_southwest_gu_ordeal_judgment', bridgeId: 'SYZ-640', entry: 'REL-2-0010', cluster: 'sid_witch' },
  { id: 'case_cn_dujiangyan_libing_stone_rhino', bridgeId: 'SYZ-641', entry: 'GEO-LAND-0011', cluster: 'sid_myth' },
  { id: 'case_cn_minzhe_boat_eye_dotting', bridgeId: 'SYZ-642', entry: 'REL-5-0043', cluster: 'sid_myth' },
  { id: 'case_cn_fengxiang_clay_tiger_guardian', bridgeId: 'SYZ-643', entry: 'REL-5-0062', cluster: 'sid_myth' },
];

function makeSyntheticBridges(count) {
  const trails = ['trail1', 'trail2', 'trail3', 'trail4', 'trail5'];
  const bridges = [];
  for (let i = 0; i < count; i += 1) {
    const vol = VOLUMES[i % VOLUMES.length];
    const cluster = SIDERA_CLUSTERS[(i * 2) % SIDERA_CLUSTERS.length];
    const trail = trails[i % trails.length];
    const parentAng = -Math.PI + (((i * 7) % count) / count) * Math.PI * 2;
    bridges.push({
      id: `SYZ-SYN-${String(i + 1).padStart(4, '0')}`,
      trail,
      sideraCluster: cluster.id,
      cluster: cluster.id,
      fiction: false,
      hasCoordinates: i % 5 !== 0,
      parentAng,
      physis: { id: `ENTRY-${i % 120}`, volId: vol.id },
      materialNode: {
        posOmnia3D: new THREE.Vector3(Math.cos(parentAng) * 162, Math.sin(parentAng) * 162, 10),
      },
    });
  }
  return bridges.sort((a, b) => a.parentAng - b.parentAng || a.id.localeCompare(b.id));
}

function assertLayoutScalingInvariants(bridges, expectedTotal, label) {
  const layout = computeZodiacBridgeLayout(bridges, {
    sideraClusters: SIDERA_CLUSTERS,
    volumes: VOLUMES,
  });

  assert.equal(layout.bridges.length, expectedTotal, `${label}: unexpected bridge count`);
  assert.ok(layout.leadCount > 0 && layout.leadCount <= MAX_LEAD_ANCHORS, `${label}: leadCount=${layout.leadCount}`);
  assert.ok(layout.secondaryCount <= MAX_SECONDARY_ANCHORS, `${label}: secondaryCount=${layout.secondaryCount}`);
  assert.equal(
    layout.leadCount + layout.secondaryCount + layout.dustCount,
    expectedTotal,
    `${label}: tier sum mismatch`,
  );

  const expectedScale = Math.max(0.42, Math.min(1.0, Math.sqrt(180 / Math.max(180, expectedTotal))));
  assert.ok(Math.abs(layout.densityScale - expectedScale) < 1e-9, `${label}: densityScale mismatch`);

  const lanesSeen = new Set();
  const clusterLeadCounts = new Map();
  for (const b of layout.bridges) {
    lanesSeen.add(b.lane);
    assert.ok(b.radius >= 234 && b.radius <= 286, `${label}: radius out of bounds (${b.radius})`);
    assert.ok(b.z >= 16 && b.z <= 52, `${label}: z out of bounds (${b.z})`);
    assert.ok(b.posOmniaSyzygy instanceof THREE.Vector3);
    if (b.isSideraClusterLead) {
      clusterLeadCounts.set(b.sideraCluster, (clusterLeadCounts.get(b.sideraCluster) ?? 0) + 1);
    }
    const sideraStyle = computeAdaptiveAnchorStyle(b, {
      dimension: 'sidera',
      sideraFocus: 'all',
      trailActive: false,
      isSelected: false,
      isHovered: false,
      isMatching: true,
      visible: true,
    });
    if (!b.isSideraClusterLead) {
      assert.ok(sideraStyle.size >= 3.6 && sideraStyle.size <= 5.4, `${label}: SIDERA dot size=${sideraStyle.size}`);
      assert.ok(sideraStyle.highlight >= 0.42 && sideraStyle.highlight <= 0.58, `${label}: SIDERA highlight=${sideraStyle.highlight}`);
    }
  }
  assert.equal(lanesSeen.size, ORBITAL_LANE_COUNT, `${label}: expected all ${ORBITAL_LANE_COUNT} orbital lanes used`);
  for (const [cl, cnt] of clusterLeadCounts.entries()) {
    assert.ok(cnt <= 3, `${label}: cluster ${cl} has ${cnt} > 3 cluster leads`);
  }

  const asterismPts = buildLeadAsterismSegments(layout.bridges);
  assert.equal(asterismPts.length % 2, 0, `${label}: asterism points must be pairs`);
  assert.ok(
    asterismPts.length / 2 <= MAX_ASTERISM_SEGMENTS,
    `${label}: asterismSegments=${asterismPts.length / 2} > ${MAX_ASTERISM_SEGMENTS}`,
  );

  const overview = selectVisibleOmniaCurves(layout.bridges, {
    dimension: 'omnia',
    activeTrail: 'all',
    searchQuery: '',
    volumes: VOLUMES,
    showF: true,
  });
  assert.ok(overview.curves.length <= MAX_OMNIA_OVERVIEW_CURVES, `${label}: OMNIA overview=${overview.curves.length}`);
  assert.equal(overview.truncatedCount, 0, `${label}: OMNIA overview must not set truncatedCount`);

  const activeFilterIds = new Set(layout.bridges.slice(0, 60).map((b) => b.id));
  const filteredOmnia = selectVisibleOmniaCurves(layout.bridges, {
    dimension: 'omnia',
    activeTrail: 'all',
    searchQuery: 'filter',
    matchingBridgeIds: activeFilterIds,
    volumes: VOLUMES,
    showF: true,
  });
  assert.ok(filteredOmnia.curves.length <= MAX_ACTIVE_CURVES, `${label}: active OMNIA=${filteredOmnia.curves.length}`);
  assert.equal(filteredOmnia.totalMatching, 60);
  assert.equal(filteredOmnia.shownCount, MAX_ACTIVE_CURVES);
  assert.equal(filteredOmnia.truncatedCount, 60 - MAX_ACTIVE_CURVES);

  const trail5Matches = layout.bridges.filter((b) => b.trail === 'trail5');
  if (trail5Matches.length > MAX_ACTIVE_CURVES) {
    const trailOmnia = selectVisibleOmniaCurves(layout.bridges, {
      dimension: 'omnia',
      activeTrail: 'trail5',
      searchQuery: '',
      volumes: VOLUMES,
      showF: true,
    });
    assert.ok(trailOmnia.curves.length <= MAX_ACTIVE_CURVES, `${label}: trail5 OMNIA=${trailOmnia.curves.length}`);
    assert.ok(trailOmnia.truncatedCount > 0, `${label}: expected truncatedCount > 0 on trail5`);
  }

  const sideraBundled = selectVisibleSideraCurves(layout.bridges, SIDERA_CLUSTERS, {
    sideraBridgeMode: 'bundled',
    activeTrail: 'all',
  });
  assert.ok(sideraBundled.curves.length <= SIDERA_CLUSTERS.length, `${label}: SIDERA bundled=${sideraBundled.curves.length}`);

  const sideraFull = selectVisibleSideraCurves(layout.bridges, SIDERA_CLUSTERS, {
    sideraBridgeMode: 'full',
    activeTrail: 'all',
  });
  assert.ok(sideraFull.curves.length <= MAX_ACTIVE_CURVES, `${label}: SIDERA full=${sideraFull.curves.length}`);

  return layout;
}

test('bridgeLayout.js preserves visual scaling invariants at real 643 bridges and synthetic 1,000 bridges', async () => {
  const boot = await readJson('../public/syzygy/boot.json');
  assert.ok(boot.bridges.length >= 643, `Expected >= 643 bridges in boot.json, got ${boot.bridges.length}`);

  const realOrdered = boot.bridges.map((b, idx) => {
    const parentAng = -Math.PI + (((idx * 13) % boot.bridges.length) / boot.bridges.length) * Math.PI * 2;
    return {
      ...b,
      hasCoordinates: Number.isFinite(b.mythos?.spatial?.lat) && Number.isFinite(b.mythos?.spatial?.lng),
      parentAng,
      materialNode: {
        posOmnia3D: new THREE.Vector3(Math.cos(parentAng) * 162, Math.sin(parentAng) * 162, 10),
      },
    };
  }).sort((a, b) => a.parentAng - b.parentAng || a.sideraCluster.localeCompare(b.sideraCluster) || a.id.localeCompare(b.id));

  const layoutReal = assertLayoutScalingInvariants(realOrdered, boot.bridges.length, 'real-643');
  const layout1000 = assertLayoutScalingInvariants(makeSyntheticBridges(1000), 1000, 'synthetic-1000');

  assert.ok(
    layout1000.densityScale < layoutReal.densityScale && layoutReal.densityScale < 1.0,
    `Expected densityScale to decrease with bridge count: 643=${layoutReal.densityScale}, 1000=${layout1000.densityScale}`,
  );
});

test('Phase 7 compiled corpus covers >= 11,787 nodes, 531 unique lexicon entries across 7/7 shards, and full readability fields', async () => {
  const [graph, taxonomy, manifest] = await Promise.all([
    readJson('../public/data/graph_data.json'),
    readJson('../public/syzygy/taxonomy.json'),
    readJson('../public/syzygy/lexicon/manifest.json'),
  ]);

  assert.ok(graph.nodes.length >= 11787, `Expected >= 11787 nodes, got ${graph.nodes.length}`);
  assert.equal(taxonomy.domains.length, 7);
  assert.equal(taxonomy.corpus_classification_coverage?.total_graph_nodes, graph.nodes.length);
  assert.equal(taxonomy.corpus_classification_coverage?.total_classified_unique, graph.nodes.length);
  assert.ok(taxonomy.corpus_classification_coverage.total_classified_unique >= 11787);

  const graphIds = new Set(graph.nodes.map((n) => n.id));
  const leakRegex = /([A-Za-z]:\\|\/Users\/|Downloads|\.azw3|calibre|kindle|Desktop)/i;
  const globalIds = new Set();
  const globalNormTerms = new Map();
  let totalEntries = 0;
  let totalGroups = 0;

  for (const domain of taxonomy.domains) {
    assert.ok(domain.classified_node_count >= domain.node_count, `${domain.id}: classified_node_count < node_count`);
    const qo = domain.quick_overview;
    assert.ok(qo && typeof qo === 'object' && !Array.isArray(qo), `${domain.id}: missing quick_overview`);
    assert.ok(typeof qo.three_book_anchor === 'string' && qo.three_book_anchor.trim().length > 0, `${domain.id}: empty three_book_anchor`);
    assert.ok(typeof qo.core_question === 'string' && qo.core_question.trim().length > 0, `${domain.id}: empty core_question`);
    assert.ok(
      Array.isArray(qo.key_takeaways)
        && qo.key_takeaways.length === 3
        && qo.key_takeaways.every((t) => typeof t === 'string' && t.trim().length > 0),
      `${domain.id}: quick_overview.key_takeaways must have 3 non-empty strings`,
    );

    const shardMeta = manifest.domains[domain.id];
    assert.ok(shardMeta, `Missing shard manifest for ${domain.id}`);
    assert.ok(domain.lexicon_count >= EXPECTED_PHASE7_DOMAIN_COUNTS[domain.id], `${domain.id}: lexicon_count must preserve >= ${EXPECTED_PHASE7_DOMAIN_COUNTS[domain.id]}`);
    assert.equal(shardMeta.count, domain.lexicon_count);

    for (const group of domain.groups) {
      totalGroups += 1;
      assert.ok(typeof group.tldr === 'string' && group.tldr.trim().length > 0, `${domain.id}/${group.id}: missing tldr`);
      for (const id of [...(group.hub_ids ?? []), ...(group.featured_nodes ?? [])]) {
        assert.ok(graphIds.has(id), `${domain.id}/${group.id}: missing node ${id} in graph_data.json`);
      }
    }

    const shard = await readJson(`../public/syzygy/${shardMeta.file}`);
    assert.equal(shard.entries.length, domain.lexicon_count);
    assert.ok(shard.entries.length >= EXPECTED_PHASE7_DOMAIN_COUNTS[domain.id]);
    totalEntries += shard.entries.length;

    const shardTerms = new Set();
    for (const entry of shard.entries) {
      assert.ok(!globalIds.has(entry.id), `Duplicate lexicon entry id: ${entry.id}`);
      globalIds.add(entry.id);
      const norm = normalizeLexiconTerm(entry.term);
      assert.ok(!shardTerms.has(norm), `Duplicate normalized term in ${domain.id}: ${entry.term}`);
      assert.ok(!globalNormTerms.has(norm), `Cross-domain normalized term collision: ${entry.term} (${entry.id} vs ${globalNormTerms.get(norm)})`);
      shardTerms.add(norm);
      globalNormTerms.set(norm, entry.id);

      assert.ok(typeof entry.gist === 'string' && entry.gist.trim().length > 0 && entry.gist.length <= 36, `${entry.id}: invalid gist`);
      assert.ok(typeof entry.reading_tag === 'string' && entry.reading_tag.trim().length > 0, `${entry.id}: missing reading_tag`);
      assert.doesNotMatch(JSON.stringify(entry), leakRegex, `${entry.id}: local path or format leak detected`);
    }
  }

  assert.equal(totalGroups, 24, 'Expected 24 total taxonomy groups across 7 domains');
  assert.ok(totalEntries >= 531, `Expected >= 531 compiled lexicon entries, got ${totalEntries}`);
  assert.equal(globalIds.size, totalEntries);

  const allFeatured = new Set(
    taxonomy.domains.flatMap((d) => d.groups.flatMap((g) => g.featured_nodes ?? [])),
  );
  for (const { id } of PHASE7_L1_CASES) {
    assert.ok(allFeatured.has(id), `New Phase 7 case ${id} missing from thematic_taxonomy featured_nodes`);
  }
});

test('Phase 7 Wave 2 imports all 9 L1 cases and preserves contiguous bridges SYZ-01..N (>= 643)', async () => {
  const [graph, handbook, bridges, matchesIndex] = await Promise.all([
    readJson('../public/data/graph_data.json'),
    readJson('../public/knowledge/data.json'),
    readJson('../src/syzygy/bridges.json'),
    readJson('../public/syzygy/matches.json'),
  ]);

  assert.ok(bridges.length >= 643, `Expected >= 643 total bridges, got ${bridges.length}`);
  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const entriesById = new Map(handbook.entries.map((entry) => [entry.id, entry]));
  const bridgesById = new Map(bridges.map((bridge) => [bridge.id, bridge]));
  assert.equal(bridgesById.size, bridges.length, 'Bridge identifiers must be unique');

  for (let i = 1; i <= bridges.length; i += 1) {
    const id = `SYZ-${String(i).padStart(2, '0')}`;
    assert.ok(bridgesById.has(id), `Missing contiguous bridge ${id}`);
  }

  const leakRegex = /([A-Za-z]:\\|\/Users\/|Downloads|\.azw3|calibre|kindle|Desktop)/i;
  for (const { id, bridgeId, entry, cluster } of PHASE7_L1_CASES) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing Phase 7 L1 case ${id}`);
    assert.equal(node.z_layer, 1);
    assert.equal(node.node_type, 'case');
    assert.equal(nodeRegion(node), 'china', `${id}: expected region china`);
    assert.ok(Number.isFinite(node.spatial?.lat) && Number.isFinite(node.spatial?.lng));
    assert.ok(Array.isArray(node.reading?.paragraphs) && node.reading.paragraphs.length >= 2);
    assert.doesNotMatch(JSON.stringify(node), leakRegex, `${id}: leak detected`);

    const bridge = bridgesById.get(bridgeId);
    assert.ok(bridge, `Missing bridge ${bridgeId}`);
    assert.equal(bridge.case, id);
    assert.equal(bridge.entry, entry);
    assert.equal(bridge.cluster, cluster);
    assert.equal(bridge.trail, 'all');
    assert.equal(bridge.relation, 'THEMATIC');
    assert.ok(bridge.rationale?.trim());
    assert.ok(entriesById.get(entry)?.body?.trim(), `${bridgeId}: missing handbook body for ${entry}`);

    const rows = matchesIndex.matches[id] ?? [];
    assert.ok(
      rows.some((row) => row.kind === 'curated' && row.bridge_id === bridgeId && row.entry === entry),
      `${id}: curated bridge ${bridgeId} missing from matches.json`,
    );
  }
});
