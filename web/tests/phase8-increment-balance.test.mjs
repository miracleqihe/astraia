import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { access, readFile } from 'node:fs/promises';
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

const readBytes = (relPath) => readFile(new URL(relPath, import.meta.url));
const readJson = async (relPath) => JSON.parse((await readBytes(relPath)).toString('utf8'));
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

const LEAK_REGEX = /([A-Za-z]:\\|\/Users\/|Downloads|\.azw3|calibre|kindle|Desktop)/i;

const EXPECTED_PHASE8_DOMAIN_COUNTS = {
  wugu_talisman: 256,
  underworld_bureaucracy: 49,
  ghost_rituals_nuo: 49,
  ethnic_spirit_lexicon: 48,
  classical_zhiguai_opera: 139,
  world_mythology: 52,
  modern_liminal: 52,
};

const PHASE7_CURATED_NODE_COUNTS = {
  wugu_talisman: 149,
  underworld_bureaucracy: 29,
  ghost_rituals_nuo: 28,
  ethnic_spirit_lexicon: 33,
  classical_zhiguai_opera: 38,
  world_mythology: 30,
  modern_liminal: 25,
};

const PHASE8_L1_CASES = [
  { id: 'case_cn_fan_zhen_shenmielun_debate', bridgeId: 'SYZ-644', entry: 'PHI-6-0002', cluster: 'sid_crypt', region: 'china', tier: 'A', fiction: false },
  { id: 'case_cn_lingnan_maishui_yankou_rite', bridgeId: 'SYZ-645', entry: 'REL-3-0010', cluster: 'sid_hag', region: 'china', tier: 'A', fiction: false },
  { id: 'case_cn_soushen_song_dingbo_ghost', bridgeId: 'SYZ-646', entry: 'LIT-2-0001', cluster: 'sid_crypt', region: 'china', tier: 'A', fiction: false },
  { id: 'case_cn_liangshan_yi_xiaobu_rite', bridgeId: 'SYZ-647', entry: 'REL-5-0005', cluster: 'sid_witch', region: 'china', tier: 'A', fiction: false },
  { id: 'case_cn_tang_qianjin_gu_antidotes', bridgeId: 'SYZ-648', entry: 'HEA-TOPIC-0002', cluster: 'sid_witch', region: 'china', tier: 'A', fiction: false },
  { id: 'case_cn_nujiang_cliff_spirit_rite', bridgeId: 'SYZ-649', entry: 'REL-5-0001', cluster: 'sid_hag', region: 'china', tier: 'B', fiction: false },
  { id: 'case_cn_han_huangshen_yuezhang_seal', bridgeId: 'SYZ-650', entry: 'HIS-4-0002', cluster: 'sid_witch', region: 'china', tier: 'A', fiction: false },
  { id: 'case_cn_shangzhou_jade_cicada_yuhan', bridgeId: 'SYZ-651', entry: 'REL-3-0010', cluster: 'sid_crypt', region: 'china', tier: 'A', fiction: false },
  { id: 'case_cn_sichuan_zhangxian_tiangou_ward', bridgeId: 'SYZ-652', entry: 'REL-5-0034', cluster: 'sid_myth', region: 'china', tier: 'B', fiction: false },
  { id: 'case_gr_corfu_gorgoneion_apotropaic', bridgeId: 'SYZ-653', entry: 'ARC-3-0002', cluster: 'sid_myth', region: 'europe', tier: 'A', fiction: false },
  { id: 'case_eg_thebes_heart_scarab_amulet', bridgeId: 'SYZ-654', entry: 'REL-1-0003', cluster: 'sid_crypt', region: 'africa', tier: 'A', fiction: false },
  { id: 'case_mx_aztec_mictlan_nine_realms', bridgeId: 'SYZ-655', entry: 'REL-3-0010', cluster: 'sid_crypt', region: 'north-america', tier: 'A', fiction: false },
  { id: 'case_us_bloody_mary_mirror_troxler', bridgeId: 'SYZ-656', entry: 'BIO-3-0004', cluster: 'sid_hag', region: 'north-america', tier: 'B', fiction: false },
  { id: 'case_uk_coventry_infrasound_189hz_lab', bridgeId: 'SYZ-657', entry: 'PHY-4-0005', cluster: 'sid_liminal', region: 'europe', tier: 'A', fiction: false },
  { id: 'case_us_blair_witch_1999_viral_ostension', bridgeId: 'SYZ-658', entry: 'LIT-4-0009', cluster: 'sid_liminal', region: 'north-america', tier: 'F', fiction: true },
];

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

test('Phase 8 lexicon balance preserves the minimum domain counts, unique IDs and readable fields', async () => {
  const [taxonomy, manifestBytes] = await Promise.all([
    readJson('../public/syzygy/taxonomy.json'),
    readBytes('../public/syzygy/lexicon/manifest.json'),
  ]);
  const manifest = JSON.parse(manifestBytes.toString('utf8'));
  assert.equal(taxonomy.domains.length, 7);
  assert.equal(taxonomy.lexicon_manifest_sha256, sha256(manifestBytes));

  const globalIds = new Set();
  const globalNormTerms = new Map();
  const hubOwner = new Map();
  let totalEntries = 0;

  for (const domain of taxonomy.domains) {
    assert.ok(domain.lexicon_count >= 48, `${domain.id}: expected lexicon_count >= 48, got ${domain.lexicon_count}`);
    assert.ok(domain.lexicon_count >= EXPECTED_PHASE8_DOMAIN_COUNTS[domain.id], `${domain.id}: entries were removed`);

    const shardMeta = manifest.domains[domain.id];
    assert.ok(shardMeta, `Missing shard metadata for ${domain.id}`);
    assert.equal(shardMeta.count, domain.lexicon_count);

    const shardBytes = await readBytes(`../public/syzygy/${shardMeta.file}`);
    assert.equal(shardBytes.length, shardMeta.bytes, `${shardMeta.file}: byte length mismatch`);
    assert.equal(sha256(shardBytes), shardMeta.sha256, `${shardMeta.file}: SHA-256 mismatch`);

    const shard = JSON.parse(shardBytes.toString('utf8'));
    assert.equal(shard.domain_id, domain.id);
    assert.equal(shard.entries.length, domain.lexicon_count);
    totalEntries += shard.entries.length;

    const shardTerms = new Set();
    for (const entry of shard.entries) {
      assert.ok(!globalIds.has(entry.id), `Duplicate lexicon entry id: ${entry.id}`);
      globalIds.add(entry.id);

      const norm = normalizeLexiconTerm(entry.term);
      assert.ok(!shardTerms.has(norm), `Duplicate normalized term in ${domain.id}: ${entry.term}`);
      assert.ok(!globalNormTerms.has(norm), `Global normalized term collision: ${entry.term} (${entry.id} vs ${globalNormTerms.get(norm)})`);
      shardTerms.add(norm);
      globalNormTerms.set(norm, entry.id);

      const prevDomain = hubOwner.get(entry.hub_id);
      assert.ok(!prevDomain || prevDomain === domain.id, `Multi-domain hub_id ${entry.hub_id}: ${prevDomain} vs ${domain.id}`);
      hubOwner.set(entry.hub_id, domain.id);

      assert.ok(typeof entry.gist === 'string' && entry.gist.trim().length > 0 && entry.gist.length <= 36, `${entry.id}: invalid gist`);
      assert.ok(typeof entry.reading_tag === 'string' && entry.reading_tag.trim().length > 0, `${entry.id}: missing reading_tag`);
      assert.doesNotMatch(JSON.stringify(entry), LEAK_REGEX, `${entry.id}: leak detected`);
    }
  }

  assert.ok(totalEntries >= 645, `Expected at least 645 compiled lexicon entries, got ${totalEntries}`);
  assert.equal(globalIds.size, totalEntries);
  assert.equal(Object.keys(manifest.hub_to_domain ?? {}).length, hubOwner.size);
  assert.equal(Object.keys(taxonomy.hub_to_domain ?? {}).length, hubOwner.size);
});

test('Phase 8 preserves 15 L1 cases, contiguous bridges, region routing, and F-tier quarantine', async () => {
  const [graphBytes, handbook, bridges, matchesIndex] = await Promise.all([
    readBytes('../public/data/graph_data.json'),
    readJson('../public/knowledge/data.json'),
    readJson('../src/syzygy/bridges.json'),
    readJson('../public/syzygy/matches.json'),
  ]);

  // The private development catalogue is optional in a clean checkout.
  const catalogueBytes = await readBytes('../public/data/catalogue_data.json').catch(error => {
    if (error.code === 'ENOENT') return null;
    throw error;
  });
  if (catalogueBytes) assert.ok(graphBytes.equals(catalogueBytes), 'graph_data.json and catalogue_data.json must be byte-identical');
  const graph = JSON.parse(graphBytes.toString('utf8'));
  assert.ok(graph.nodes.length >= 11802, `Expected at least 11,802 nodes, got ${graph.nodes.length}`);

  assert.ok(bridges.length >= 658, `Expected at least 658 total bridges, got ${bridges.length}`);
  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const entriesById = new Map(handbook.entries.map((entry) => [entry.id, entry]));
  const bridgesById = new Map(bridges.map((bridge) => [bridge.id, bridge]));
  assert.equal(bridgesById.size, bridges.length, 'Bridge identifiers must be unique');

  for (let i = 1; i <= bridges.length; i += 1) {
    const id = `SYZ-${String(i).padStart(2, '0')}`;
    assert.ok(bridgesById.has(id), `Missing contiguous bridge ${id}`);
  }

  assert.equal(PHASE8_L1_CASES.length, 15);
  for (const spec of PHASE8_L1_CASES) {
    const node = nodesById.get(spec.id);
    assert.ok(node, `Missing Phase 8 L1 case ${spec.id}`);
    assert.equal(node.z_layer, 1);
    assert.equal(node.node_type, 'case');
    assert.equal(node.credibility_tier, spec.tier);
    assert.equal(Boolean(node.is_fictional_quarantine), spec.fiction);
    assert.equal(nodeRegion(node), spec.region, `${spec.id}: expected region ${spec.region}`);
    assert.ok(Number.isFinite(node.spatial?.lat) && Number.isFinite(node.spatial?.lng));
    assert.ok(Array.isArray(node.reading?.paragraphs) && node.reading.paragraphs.length >= 2);
    assert.doesNotMatch(JSON.stringify(node), LEAK_REGEX, `${spec.id}: leak detected`);

    const vaultFolder = spec.fiction ? '05_quarantine_fiction' : '01_cases';
    await access(new URL(`../../vault/${vaultFolder}/${spec.id}.md`, import.meta.url));
    if (spec.fiction) {
      await assert.rejects(access(new URL(`../../vault/01_cases/${spec.id}.md`, import.meta.url)));
    }

    const bridge = bridgesById.get(spec.bridgeId);
    assert.ok(bridge, `Missing bridge ${spec.bridgeId}`);
    assert.equal(bridge.case, spec.id);
    assert.equal(bridge.entry, spec.entry);
    assert.equal(bridge.cluster, spec.cluster);
    assert.equal(bridge.trail, 'all');
    assert.equal(bridge.relation, 'THEMATIC');
    assert.ok(bridge.rationale?.trim());
    assert.ok(entriesById.get(spec.entry)?.body?.trim(), `${spec.bridgeId}: missing handbook body for ${spec.entry}`);

    const rows = matchesIndex.matches[spec.id] ?? [];
    assert.ok(
      rows.some((row) => row.kind === 'curated' && row.bridge_id === spec.bridgeId && row.entry === spec.entry),
      `${spec.id}: curated bridge ${spec.bridgeId} missing from matches.json`,
    );
  }
});

test('Phase 8 curated dedup expansion preserves classifications and complete corpus coverage', async () => {
  const [graph, taxonomy, beeGhost, beeWugu, beeZhenwu, beeWorld, beeModern] = await Promise.all([
    readJson('../public/data/graph_data.json'),
    readJson('../public/syzygy/taxonomy.json'),
    readJson('../../reference/staging/p8_bee_ghost_dict/dedup_classification.json'),
    readJson('../../reference/staging/p8_bee_wugu/dedup_classification.json'),
    readJson('../../reference/staging/p8_bee_zhenwu/dedup_classification.json'),
    readJson('../../reference/staging/p8_bee_world_myth/dedup_classification.json'),
    readJson('../../reference/staging/p8_bee_modern_liminal/dedup_classification.json'),
  ]);

  assert.ok(graph.nodes.length >= 11802);
  assert.equal(taxonomy.corpus_classification_coverage?.total_graph_nodes, graph.nodes.length);
  assert.equal(taxonomy.corpus_classification_coverage?.total_classified_unique, graph.nodes.length);

  const graphIds = new Set(graph.nodes.map((n) => n.id));
  const groupFeatured = new Map();

  for (const domain of taxonomy.domains) {
    assert.ok(domain.classified_node_count >= domain.node_count, `${domain.id}: classified_node_count < node_count`);
    assert.ok(
      domain.node_count > PHASE7_CURATED_NODE_COUNTS[domain.id],
      `${domain.id}: expected node_count (${domain.node_count}) > Phase 7 baseline (${PHASE7_CURATED_NODE_COUNTS[domain.id]})`,
    );
    const uniqueDomainNodes = new Set();
    for (const group of domain.groups) {
      const feat = group.featured_nodes ?? [];
      assert.equal(new Set(feat).size, feat.length, `${domain.id}/${group.id}: duplicate featured_nodes`);
      groupFeatured.set(`${domain.id}/${group.id}`, new Set(feat));
      for (const id of [...(group.hub_ids ?? []), ...feat]) {
        assert.ok(graphIds.has(id), `${domain.id}/${group.id}: unknown node ${id}`);
        uniqueDomainNodes.add(id);
      }
    }
    assert.equal(domain.node_count, uniqueDomainNodes.size, `${domain.id}: node_count mismatch`);
  }

  const allBeeItems = [
    ...(beeGhost.classifications ?? []),
    ...(beeWugu.mappings ?? []),
    ...(beeZhenwu.classifications ?? []),
    ...(beeWorld.classifications ?? []),
    ...(beeModern.classifications ?? []),
  ];
  assert.equal(allBeeItems.length, 178);
  for (const item of allBeeItems) {
    const set = groupFeatured.get(`${item.domain_id}/${item.group_id}`);
    assert.ok(set?.has(item.node_id), `Dedup node ${item.node_id} missing from ${item.domain_id}/${item.group_id}`);
  }

  const allFeaturedFlat = new Set(
    taxonomy.domains.flatMap((d) => d.groups.flatMap((g) => g.featured_nodes ?? [])),
  );
  for (const { id } of PHASE8_L1_CASES) {
    assert.ok(allFeaturedFlat.has(id), `Phase 8 L1 case ${id} missing from taxonomy featured_nodes`);
  }
});

test('bridgeLayout.js visual budgets hold as the curated bridges grow', async () => {
  const boot = await readJson('../public/syzygy/boot.json');
  assert.ok(boot.bridges.length >= 658, `Expected at least 658 bridges in boot.json, got ${boot.bridges.length}`);

  const ordered = boot.bridges.map((b, idx) => {
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

  const layout = computeZodiacBridgeLayout(ordered, {
    sideraClusters: SIDERA_CLUSTERS,
    volumes: VOLUMES,
  });

  assert.equal(layout.bridges.length, boot.bridges.length);
  assert.ok(layout.leadCount > 0 && layout.leadCount <= MAX_LEAD_ANCHORS, `leadCount=${layout.leadCount}`);
  assert.ok(layout.secondaryCount <= MAX_SECONDARY_ANCHORS, `secondaryCount=${layout.secondaryCount}`);
  assert.equal(layout.leadCount + layout.secondaryCount + layout.dustCount, boot.bridges.length);

  const lanesSeen = new Set();
  for (const b of layout.bridges) {
    lanesSeen.add(b.lane);
    const style = computeAdaptiveAnchorStyle(b, {
      dimension: 'sidera',
      sideraFocus: 'all',
      trailActive: false,
      isSelected: false,
      isHovered: false,
      isMatching: true,
      visible: true,
    });
    if (!b.isSideraClusterLead) {
      assert.ok(style.size >= 3.6 && style.size <= 5.4);
    }
  }
  assert.equal(lanesSeen.size, ORBITAL_LANE_COUNT);

  const asterismPts = buildLeadAsterismSegments(layout.bridges);
  assert.equal(asterismPts.length % 2, 0);
  assert.ok(asterismPts.length / 2 <= MAX_ASTERISM_SEGMENTS, `asterismSegments=${asterismPts.length / 2}`);

  const overview = selectVisibleOmniaCurves(layout.bridges, {
    dimension: 'omnia',
    activeTrail: 'all',
    searchQuery: '',
    volumes: VOLUMES,
    showF: true,
  });
  assert.ok(overview.curves.length <= MAX_OMNIA_OVERVIEW_CURVES, `overview=${overview.curves.length}`);
  assert.equal(overview.truncatedCount, 0);

  const activeIds = new Set(layout.bridges.slice(0, 60).map((b) => b.id));
  const activeOmnia = selectVisibleOmniaCurves(layout.bridges, {
    dimension: 'omnia',
    activeTrail: 'all',
    searchQuery: 'filter',
    matchingBridgeIds: activeIds,
    volumes: VOLUMES,
    showF: true,
  });
  assert.ok(activeOmnia.curves.length <= MAX_ACTIVE_CURVES, `activeOmnia=${activeOmnia.curves.length}`);
  assert.equal(activeOmnia.shownCount, MAX_ACTIVE_CURVES);
  assert.equal(activeOmnia.truncatedCount, 60 - MAX_ACTIVE_CURVES);

  const sideraBundled = selectVisibleSideraCurves(layout.bridges, SIDERA_CLUSTERS, {
    sideraBridgeMode: 'bundled',
    activeTrail: 'all',
  });
  assert.ok(sideraBundled.curves.length <= SIDERA_CLUSTERS.length);

  const sideraFull = selectVisibleSideraCurves(layout.bridges, SIDERA_CLUSTERS, {
    sideraBridgeMode: 'full',
    activeTrail: 'all',
  });
  assert.ok(sideraFull.curves.length <= MAX_ACTIVE_CURVES);
});
