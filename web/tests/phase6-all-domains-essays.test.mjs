import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { registerHooks } from 'node:module';
import { test } from 'node:test';

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
  clearLexiconCache,
  filterLexiconEntries,
  getHubLexiconInfo,
  loadLexiconShard,
  loadTaxonomy,
} from '../src/syzygy/lexiconShards.js';

const readBytes = (relativePath) => readFile(new URL(relativePath, import.meta.url));
const readJson = async (relativePath) => JSON.parse((await readBytes(relativePath)).toString('utf8'));
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

const EXPECTED_DOMAINS = [
  { id: 'wugu_talisman', count: 112, sampleHub: 'motif_cn_wugu_poison_complex', sampleQuery: '金蚕' },
  { id: 'underworld_bureaucracy', count: 30, sampleHub: 'motif_cn_underworld_bureaucracy_system', sampleQuery: '十殿' },
  { id: 'ghost_rituals_nuo', count: 30, sampleHub: 'motif_cn_nuo_funeral_liminal_rites', sampleQuery: '方相' },
  { id: 'ethnic_spirit_lexicon', count: 30, sampleHub: 'motif_cn_ethnic_spirits_marvels', sampleQuery: '白泽' },
  { id: 'classical_zhiguai_opera', count: 30, sampleHub: 'motif_cn_zhiguai_ghost_opera', sampleQuery: '窦娥' },
  { id: 'world_mythology', count: 28, sampleHub: 'motif_global_comparative_myth_complex', sampleQuery: '伊南娜' },
  { id: 'modern_liminal', count: 28, sampleHub: 'motif_urban_ostension_liminal', sampleQuery: '后室' },
];

const PHASE6_L4_NODES = [
  { id: 'theory_zhenwu_four_pervasiveness', type: 'theory' },
  { id: 'mech_underworld_bureaucratic_projection', type: 'mechanism' },
];

const PHASE6_L3_HUB_IDS = [
  'motif_cn_underworld_bureaucracy_system',
  'motif_cn_nuo_funeral_liminal_rites',
  'motif_cn_ethnic_spirits_marvels',
  'motif_cn_zhiguai_ghost_opera',
  'motif_global_comparative_myth_complex',
];

const PHASE6_L2_CORPUS_IDS = [
  'corpus_cn_underworld_scriptures_opera',
];

const PHASE6_L1_CASES = [
  { id: 'case_cn_jiangnan_liumeng_locust_ward', bridgeId: 'SYZ-314', cluster: 'sid_myth', region: 'china' },
  { id: 'case_cn_duanwu_wudu_tiger_charm', bridgeId: 'SYZ-315', cluster: 'sid_witch', region: 'china' },
  { id: 'case_cn_southwest_village_gu_stigma_asc', bridgeId: 'SYZ-316', cluster: 'sid_hag', region: 'china' },
  { id: 'case_cn_digital_wugu_cloud_rumor', bridgeId: 'SYZ-317', cluster: 'sid_liminal', region: 'china' },
  { id: 'case_cn_taishan_dongyue_76_bureaus', bridgeId: 'SYZ-318', cluster: 'sid_crypt', region: 'china' },
  { id: 'case_cn_shidian_yanluo_mengpo_bridge', bridgeId: 'SYZ-319', cluster: 'sid_crypt', region: 'china' },
  { id: 'case_cn_han_danuo_fangxiangshi_exorcism', bridgeId: 'SYZ-320', cluster: 'sid_hag', region: 'china' },
  { id: 'case_cn_guizhou_dixi_nuo_masks', bridgeId: 'SYZ-321', cluster: 'sid_hag', region: 'china' },
  { id: 'case_cn_baize_shanxiao_spirit_lore', bridgeId: 'SYZ-322', cluster: 'sid_myth', region: 'china' },
  { id: 'case_cn_naxi_dongba_spirit_scrolls', bridgeId: 'SYZ-323', cluster: 'sid_myth', region: 'china' },
  { id: 'case_cn_dou_e_yuan_ghost_redress', bridgeId: 'SYZ-324', cluster: 'sid_crypt', region: 'china' },
  { id: 'case_cn_wupenji_talking_basin_opera', bridgeId: 'SYZ-325', cluster: 'sid_crypt', region: 'china' },
  { id: 'case_cn_mudanting_soul_return_opera', bridgeId: 'SYZ-326', cluster: 'sid_crypt', region: 'china' },
  { id: 'case_eu_malleus_maleficarum_1487', bridgeId: 'SYZ-327', cluster: 'sid_witch', region: 'europe' },
];

const EXPECTED_PHASE6_RELAY_IDS = [
  'relay-node-underworld-law',
  'relay-node-underworld-rel',
  'relay-node-nuo-liminal-rel',
  'relay-node-nuo-liminal-hea',
  'relay-node-ethnic-spirits-geo',
  'relay-node-ethnic-spirits-lit',
  'relay-node-zhiguai-opera-lit',
  'relay-node-zhiguai-opera-for',
  'relay-node-global-myth-phi',
  'relay-node-global-myth-his',
  'relay-node-underworld-corpus-his',
  'relay-node-underworld-corpus-lit',
  'relay-node-four-pervasiveness-arc',
  'relay-node-four-pervasiveness-soc',
  'relay-node-bureaucratic-proj-soc',
  'relay-node-bureaucratic-proj-law',
];

test('taxonomy.json contains editorial_preface, 7/7 domain editorial_intro essays, and every group chapter_intro', async () => {
  const [graph, taxonomyBytes] = await Promise.all([
    readJson('../public/data/graph_data.json'),
    readBytes('../public/syzygy/taxonomy.json'),
  ]);

  const taxonomy = JSON.parse(taxonomyBytes.toString('utf8'));
  const graphIds = new Set(graph.nodes.map((node) => node.id));

  assert.equal(taxonomy.version, 1);
  assert.equal(taxonomy.snapshot_id, graph.snapshot_id);

  const preface = taxonomy.editorial_preface;
  assert.ok(preface && typeof preface === 'object' && !Array.isArray(preface), 'Missing taxonomy.editorial_preface');
  assert.ok(typeof preface.title === 'string' && preface.title.trim().length > 0, 'Missing editorial_preface.title');
  assert.ok(typeof preface.subtitle === 'string' && preface.subtitle.trim().length > 0, 'Missing editorial_preface.subtitle');
  assert.ok(
    Array.isArray(preface.paragraphs)
      && preface.paragraphs.length >= 2
      && preface.paragraphs.every((p) => typeof p === 'string' && p.trim().length > 0),
    'editorial_preface.paragraphs must contain >= 2 non-empty strings',
  );
  assert.ok(
    Array.isArray(preface.principles) && preface.principles.length >= 3,
    'editorial_preface.principles must contain >= 3 items',
  );
  for (const [idx, principle] of preface.principles.entries()) {
    assert.ok(
      typeof principle?.label === 'string' && principle.label.trim().length > 0,
      `editorial_preface.principles[${idx}].label must be non-empty`,
    );
    assert.ok(
      typeof principle?.text === 'string' && principle.text.trim().length > 0,
      `editorial_preface.principles[${idx}].text must be non-empty`,
    );
  }

  assert.equal(taxonomy.domains.length, 7);
  assert.deepEqual(
    taxonomy.domains.map((domain) => domain.id),
    EXPECTED_DOMAINS.map((domain) => domain.id),
  );
  assert.deepEqual(
    taxonomy.domains.map((domain) => domain.order),
    [1, 2, 3, 4, 5, 6, 7],
  );

  for (const domain of taxonomy.domains) {
    const intro = domain.editorial_intro;
    assert.ok(intro && typeof intro === 'object' && !Array.isArray(intro), `${domain.id}: missing editorial_intro`);
    assert.ok(typeof intro.heading === 'string' && intro.heading.trim().length > 0, `${domain.id}: missing heading`);
    assert.ok(
      typeof intro.epigraph_thesis === 'string' && intro.epigraph_thesis.trim().length > 0,
      `${domain.id}: missing epigraph_thesis`,
    );
    assert.ok(
      Array.isArray(intro.paragraphs)
        && intro.paragraphs.length >= 2
        && intro.paragraphs.every((p) => typeof p === 'string' && p.trim().length > 0),
      `${domain.id}: editorial_intro.paragraphs must have >= 2 non-empty paragraphs`,
    );
    assert.ok(
      Array.isArray(intro.lenses)
        && intro.lenses.length >= 1
        && intro.lenses.every((tag) => typeof tag === 'string' && tag.trim().length > 0),
      `${domain.id}: editorial_intro.lenses must be non-empty`,
    );

    assert.ok(Array.isArray(domain.groups) && domain.groups.length >= 3, `${domain.id}: expected >= 3 groups`);
    const resolved = new Set();
    for (const group of domain.groups) {
      assert.ok(
        typeof group.chapter_intro === 'string' && group.chapter_intro.trim().length > 0,
        `${domain.id}/${group.id}: missing non-empty chapter_intro`,
      );
      for (const id of [...(group.hub_ids ?? []), ...(group.featured_nodes ?? [])]) {
        assert.ok(graphIds.has(id), `${domain.id}/${group.id}: unknown node ${id}`);
        resolved.add(id);
      }
    }
    assert.equal(domain.node_count, resolved.size, `${domain.id}: node_count mismatch`);
  }
});

test('all seven domains retain their original entries and have verified, unique lexicon shards', async () => {
  const [graph, taxonomyBytes, manifestBytes] = await Promise.all([
    readJson('../public/data/graph_data.json'),
    readBytes('../public/syzygy/taxonomy.json'),
    readBytes('../public/syzygy/lexicon/manifest.json'),
  ]);

  const taxonomy = JSON.parse(taxonomyBytes.toString('utf8'));
  const manifest = JSON.parse(manifestBytes.toString('utf8'));
  const graphIds = new Set(graph.nodes.map((node) => node.id));

  assert.equal(manifest.version, 1);
  assert.equal(taxonomy.lexicon_manifest_sha256, sha256(manifestBytes));
  assert.deepEqual(
    Object.keys(manifest.domains ?? {}),
    EXPECTED_DOMAINS.map((domain) => domain.id),
  );

  const globalSeenIds = new Set();
  const expectedHubMappings = new Map();
  let totalEntries = 0;

  for (const [idx, expected] of EXPECTED_DOMAINS.entries()) {
    const domain = taxonomy.domains[idx];
    const shardMeta = manifest.domains[expected.id];
    assert.ok(shardMeta, `Missing manifest entry for ${expected.id}`);
    assert.ok(domain.lexicon_count >= expected.count, `${expected.id}: original lexicon entries must remain`);
    assert.equal(shardMeta.count, domain.lexicon_count, `${expected.id}: manifest count mismatch`);
    assert.deepEqual(domain.lexicon_shard, {
      file: shardMeta.file,
      sha256: shardMeta.sha256,
      count: shardMeta.count,
      categories: shardMeta.categories,
      hub_ids: shardMeta.hub_ids,
    });
    assert.match(shardMeta.file, new RegExp(`^lexicon/${expected.id}-[a-f0-9]{12}\\.json$`));

    const shardBytes = await readBytes(`../public/syzygy/${shardMeta.file}`);
    assert.equal(shardBytes.length, shardMeta.bytes, `${shardMeta.file}: byte length mismatch`);
    assert.equal(sha256(shardBytes), shardMeta.sha256, `${shardMeta.file}: SHA-256 mismatch`);

    const shard = JSON.parse(shardBytes.toString('utf8'));
    assert.equal(shard.version, 1);
    assert.equal(shard.domain_id, expected.id);
    assert.equal(shard.entries.length, domain.lexicon_count);
    totalEntries += shard.entries.length;

    const shardHubCounts = new Map();
    for (const entry of shard.entries) {
      assert.match(entry.id, /^lex_[a-z0-9_]+$/);
      assert.ok(!globalSeenIds.has(entry.id), `Duplicate lexicon entry id across shards: ${entry.id}`);
      globalSeenIds.add(entry.id);
      assert.ok(graphIds.has(entry.hub_id), `${entry.id}: unknown hub_id ${entry.hub_id}`);
      assert.ok(typeof entry.term === 'string' && entry.term.trim().length > 0, `${entry.id}: empty term`);
      assert.ok(typeof entry.summary === 'string' && entry.summary.trim().length > 0, `${entry.id}: empty summary`);
      assert.ok(Array.isArray(entry.primary_sources) && entry.primary_sources.length > 0);
      assert.ok(
        entry.primary_sources.some((src) => /^https:\/\//i.test(src.url ?? '') || (!src.url && src.locator?.trim())),
        `${entry.id}: needs an HTTPS source or a print source with a locator`,
      );
      shardHubCounts.set(entry.hub_id, (shardHubCounts.get(entry.hub_id) ?? 0) + 1);
    }

    assert.deepEqual(shardMeta.hub_ids, [...shardHubCounts.keys()], `${expected.id}: hub_ids index mismatch`);
    for (const [hubId, count] of shardHubCounts.entries()) {
      assert.ok(!expectedHubMappings.has(hubId), `Hub ${hubId} mapped across multiple domains`);
      expectedHubMappings.set(hubId, {
        domain_id: expected.id,
        domain_name: domain.name,
        count,
        shard: domain.lexicon_shard,
      });
    }
  }

  assert.ok(totalEntries >= 288);
  assert.equal(globalSeenIds.size, totalEntries);
  assert.equal(Object.keys(manifest.hub_to_domain ?? {}).length, expectedHubMappings.size);
  assert.equal(Object.keys(taxonomy.hub_to_domain ?? {}).length, expectedHubMappings.size);

  for (const [hubId, expectedInfo] of expectedHubMappings.entries()) {
    assert.ok(graphIds.has(hubId), `Mapped hub ${hubId} missing from graph_data.json`);
    assert.deepEqual(manifest.hub_to_domain[hubId], {
      domain_id: expectedInfo.domain_id,
      domain_name: expectedInfo.domain_name,
      count: expectedInfo.count,
    });
    assert.deepEqual(taxonomy.hub_to_domain[hubId], expectedInfo);
  }
});

test('lexiconShards.js loads and verifies all 7 domain shards cleanly and rejects tampered hashes', async () => {
  const [taxonomyBytes, manifest] = await Promise.all([
    readBytes('../public/syzygy/taxonomy.json'),
    readJson('../public/syzygy/lexicon/manifest.json'),
  ]);

  const files = new Map([['syzygy/taxonomy.json', taxonomyBytes]]);
  const rawShardBytes = new Map();
  for (const domain of EXPECTED_DOMAINS) {
    const shardFile = manifest.domains[domain.id].file;
    const bytes = await readBytes(`../public/syzygy/${shardFile}`);
    files.set(`syzygy/${shardFile}`, bytes);
    rawShardBytes.set(domain.id, { shardFile, bytes });
  }

  const calls = [];
  const oldFetch = globalThis.fetch;
  const oldCrypto = globalThis.crypto;
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
  globalThis.fetch = async (url) => {
    const pathname = new URL(url, 'http://localhost').pathname.replace(/^\/astraia\//, '');
    calls.push(pathname);
    return files.has(pathname)
      ? new Response(files.get(pathname), { status: 200 })
      : new Response('not found', { status: 404 });
  };

  try {
    clearLexiconCache();
    const loadedTax = await loadTaxonomy('/astraia/');
    assert.ok(loadedTax);
    assert.equal(loadedTax.domains.length, 7);

    let loadedTotal = 0;
    for (const domain of EXPECTED_DOMAINS) {
      const shardMeta = manifest.domains[domain.id];
      const loadedShard = await loadLexiconShard('/astraia/', loadedTax, domain.id);
      const cachedShard = await loadLexiconShard('/astraia/', loadedTax, domain.id);
      assert.equal(loadedShard.domain_id, domain.id);
      assert.equal(loadedShard.entries.length, shardMeta.count);
      assert.equal(loadedShard.sha256, shardMeta.sha256);
      assert.equal(cachedShard, loadedShard);
      assert.equal(calls.filter((item) => item === `syzygy/${shardMeta.file}`).length, 1);

      const hubInfo = getHubLexiconInfo(loadedTax, domain.sampleHub);
      assert.equal(hubInfo?.domain_id, domain.id);
      assert.ok((hubInfo?.count ?? 0) > 0);
      assert.deepEqual(hubInfo?.shard, loadedTax.domains.find((d) => d.id === domain.id)?.lexicon_shard);

      const filtered = filterLexiconEntries(loadedShard.entries, domain.sampleQuery);
      assert.ok(filtered.length >= 1, `${domain.id}: expected query '${domain.sampleQuery}' to match >= 1 entry`);
      loadedTotal += loadedShard.entries.length;
    }
    assert.equal(loadedTotal, Object.values(manifest.domains).reduce((sum, item) => sum + item.count, 0));

    // Tamper each of the 7 domain shards and verify SHA-256 rejection + cache recovery.
    for (const domain of EXPECTED_DOMAINS) {
      clearLexiconCache();
      const { shardFile, bytes } = rawShardBytes.get(domain.id);
      const tampered = Buffer.from(bytes.toString('utf8').replace('"version":1', '"version":2'), 'utf8');
      assert.notEqual(sha256(tampered), manifest.domains[domain.id].sha256);
      files.set(`syzygy/${shardFile}`, tampered);

      await assert.rejects(
        loadLexiconShard('/astraia/', loadedTax, domain.id),
        /校验失败/,
      );

      files.set(`syzygy/${shardFile}`, bytes);
      const recovered = await loadLexiconShard('/astraia/', loadedTax, domain.id);
      assert.equal(recovered.entries.length, manifest.domains[domain.id].count);
    }
  } finally {
    clearLexiconCache();
    globalThis.fetch = oldFetch;
    Object.defineProperty(globalThis, 'crypto', { value: oldCrypto, configurable: true });
  }
});

test('Phase 6 integration preserves its nodes and contiguous bridges as the atlas grows', async () => {
  const [graph, handbook, bridges, relays, matchesIndex] = await Promise.all([
    readJson('../public/data/graph_data.json'),
    readJson('../public/knowledge/data.json'),
    readJson('../src/syzygy/bridges.json'),
    readJson('../src/syzygy/matching-relays.json'),
    readJson('../public/syzygy/matches.json'),
  ]);

  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const entriesById = new Map(handbook.entries.map((entry) => [entry.id, entry]));
  const bridgesById = new Map(bridges.map((bridge) => [bridge.id, bridge]));
  const relaysById = new Map(relays.map((rule) => [rule.id, rule]));

  assert.ok(graph.nodes.length >= 11473, `Expected at least 11473 nodes, got ${graph.nodes.length}`);
  assert.ok(bridges.length >= 327, `Expected at least 327 bridges, got ${bridges.length}`);
  assert.equal(relays.length, 156, `Expected 156 total relay rules, got ${relays.length}`);
  assert.equal(bridgesById.size, bridges.length, 'Bridge identifiers must be unique');

  for (let i = 1; i <= bridges.length; i += 1) {
    const id = `SYZ-${String(i).padStart(2, '0')}`;
    assert.ok(bridgesById.has(id), `Missing contiguous bridge ${id}`);
  }

  for (const { id, type } of PHASE6_L4_NODES) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing L4 node ${id}`);
    assert.equal(node.z_layer, 4);
    assert.equal(node.node_type, type);
    assert.equal(node.reading?.kind, 'research');
    assert.equal(node.reading?.paragraphs?.length, 3);
  }

  for (const id of PHASE6_L3_HUB_IDS) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing L3 hub ${id}`);
    assert.equal(node.z_layer, 3);
    assert.equal(node.node_type, 'motif_index');
    assert.equal(node.reading?.kind, 'research');
    assert.equal(node.reading?.paragraphs?.length, 3);
  }

  for (const id of PHASE6_L2_CORPUS_IDS) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing L2 corpus ${id}`);
    assert.equal(node.z_layer, 2);
    assert.equal(node.node_type, 'myth_corpus');
    assert.equal(node.reading?.kind, 'research');
    assert.equal(node.reading?.paragraphs?.length, 3);
  }

  assert.equal(PHASE6_L1_CASES.length, 14);
  for (const { id, bridgeId, cluster, region } of PHASE6_L1_CASES) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing L1 case ${id}`);
    assert.equal(node.z_layer, 1);
    assert.equal(node.node_type, 'case');
    assert.equal(nodeRegion(node), region, `${id}: expected region ${region}`);
    assert.ok(node.spatial && node.spatial.precision !== 'global');
    assert.equal(node.reading?.paragraphs?.length, 3);

    const bridge = bridgesById.get(bridgeId);
    assert.ok(bridge, `Missing bridge ${bridgeId}`);
    assert.equal(bridge.case, id);
    assert.equal(bridge.cluster, cluster);
    assert.equal(bridge.trail, 'all');
    assert.equal(bridge.relation, 'THEMATIC');
    assert.equal(bridge.related, null);
    assert.ok(bridge.rationale?.trim());

    const entry = entriesById.get(bridge.entry);
    assert.ok(entry?.body?.trim(), `${bridgeId}: missing/empty handbook entry ${bridge.entry}`);
  }

  const coveredTargets = new Set();
  const relaySubjects = new Set();
  for (const relayId of EXPECTED_PHASE6_RELAY_IDS) {
    const rule = relaysById.get(relayId);
    assert.ok(rule, `Missing Phase 6 relay rule ${relayId}`);
    assert.equal(rule.trigger, 'node_id');
    assert.equal(rule.propagate_edges, true);
    assert.ok(nodesById.has(rule.match), `${relayId}: unknown node ${rule.match}`);
    const entry = entriesById.get(rule.entry);
    assert.ok(entry?.body?.trim(), `${relayId}: missing/empty entry ${rule.entry}`);
    assert.ok(rule.reason?.trim(), `${relayId}: missing reason`);
    coveredTargets.add(rule.match);
    relaySubjects.add(entry.subject);

    const matched = matchesIndex.matches[rule.match] ?? [];
    assert.ok(
      matched.some((row) => row.kind === 'relay' && row.rule === relayId && row.entry === rule.entry),
      `${relayId}: missing relay match for ${rule.match} -> ${rule.entry}`,
    );
  }
  assert.equal(coveredTargets.size, 8, 'All 8 new Phase 6 L2/L3/L4 nodes must be covered by new relay rules');
  for (const subject of ['ARC', 'FOR', 'GEO', 'HEA', 'HIS', 'LAW', 'LIT', 'PHI', 'REL', 'SOC']) {
    assert.ok(relaySubjects.has(subject), `Expected Phase 6 relays to cover discipline ${subject}`);
  }
});
