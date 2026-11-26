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
import { hydrateGraphIndex as hydrateAppGraphIndex } from '../src/graph.ts';
import { hydrateGraphIndex as hydrateBridgeGraphIndex } from '../src/syzygy/graphBridge.js';
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

const PHASE5_L4_IDS = [
  'mech_gu_sorcery_social_scapegoat',
  'mech_apotropaic_boundary_seal',
  'theory_poison_panic_projection',
  'theory_sympathetic_contagious_magic_cn',
  'theory_altered_states_wugu_psychiatry',
  'mech_zhenwu_symbolic_materialization',
];

const PHASE5_L3_HUB_IDS = [
  'motif_cn_wugu_poison_complex',
  'motif_cn_yansheng_talisman_seal',
  'motif_cn_zhuyou_incantation_craft',
  'motif_cn_household_apotropaic_guardians',
  'motif_cn_zhenwu_material_taxonomy',
];

const PHASE5_L2_CORPUS_IDS = [
  'corpus_cn_zhubing_gu_toxicology',
  'corpus_cn_suishi_talisman_almanacs',
  'corpus_cn_imperial_wugu_statutes',
];

const PHASE5_L1_CASES = [
  { id: 'case_cn_han_wugu_91bce', bridgeId: 'SYZ-288', cluster: 'sid_witch' },
  { id: 'case_cn_sui_dugu_tuo_maogui', bridgeId: 'SYZ-289', cluster: 'sid_witch' },
  { id: 'case_cn_quanzhou_jincan_gu', bridgeId: 'SYZ-290', cluster: 'sid_witch' },
  { id: 'case_cn_lingnan_tiaosheng_gu', bridgeId: 'SYZ-291', cluster: 'sid_witch' },
  { id: 'case_cn_xiangxi_luodong_nu_ritual', bridgeId: 'SYZ-292', cluster: 'sid_hag' },
  { id: 'case_cn_han_taofu_shentu_yulei', bridgeId: 'SYZ-293', cluster: 'sid_myth' },
  { id: 'case_cn_tang_zhongkui_meng_expel', bridgeId: 'SYZ-294', cluster: 'sid_crypt' },
  { id: 'case_cn_grave_zhenmushou_tomb', bridgeId: 'SYZ-295', cluster: 'sid_crypt' },
  { id: 'case_cn_house_taiji_bagua_mirror', bridgeId: 'SYZ-296', cluster: 'sid_witch' },
  { id: 'case_cn_luban_mujiu_stealth_hex', bridgeId: 'SYZ-297', cluster: 'sid_witch' },
  { id: 'case_cn_zhuyou_shisan_ke_healing', bridgeId: 'SYZ-298', cluster: 'sid_witch' },
  { id: 'case_cn_child_baijia_suo_pendant', bridgeId: 'SYZ-299', cluster: 'sid_hag' },
  { id: 'case_cn_xiangxi_gan_shi_ritual', bridgeId: 'SYZ-300', cluster: 'sid_crypt' },
  { id: 'case_cn_jiangshi_huangfu_seal', bridgeId: 'SYZ-301', cluster: 'sid_crypt' },
  { id: 'case_cn_red_sash_huasha_wedding', bridgeId: 'SYZ-302', cluster: 'sid_hag' },
  { id: 'case_cn_chizhou_wuchang_nuo', bridgeId: 'SYZ-303', cluster: 'sid_myth' },
  { id: 'case_cn_qin_zuchu_wen_curse', bridgeId: 'SYZ-304', cluster: 'sid_witch' },
  { id: 'case_cn_tang_code_gu_statute', bridgeId: 'SYZ-305', cluster: 'sid_witch' },
  { id: 'case_cn_kunming_gungu_egg_rite', bridgeId: 'SYZ-306', cluster: 'sid_hag' },
  { id: 'case_cn_fengshui_yansheng_dispute', bridgeId: 'SYZ-307', cluster: 'sid_witch' },
  { id: 'case_cn_mawangdui_zajin_love_charm', bridgeId: 'SYZ-308', cluster: 'sid_witch' },
  { id: 'case_cn_yunnan_wamao_roof_guardian', bridgeId: 'SYZ-309', cluster: 'sid_crypt' },
  { id: 'case_cn_puzhou_iron_ox_flood_ward', bridgeId: 'SYZ-310', cluster: 'sid_myth' },
  { id: 'case_cn_han_mawangdui_feiyi_soul_banner', bridgeId: 'SYZ-311', cluster: 'sid_myth' },
  { id: 'case_cn_eastern_wu_hunping_maidiquan', bridgeId: 'SYZ-312', cluster: 'sid_crypt' },
  { id: 'case_cn_minnan_wangchuan_plague_ship', bridgeId: 'SYZ-313', cluster: 'sid_hag' },
];

const ALL_PHASE5_IDS = [
  ...PHASE5_L4_IDS,
  ...PHASE5_L3_HUB_IDS,
  ...PHASE5_L2_CORPUS_IDS,
  ...PHASE5_L1_CASES.map((item) => item.id),
];

const EXPECTED_HUB_LEXICON_COUNTS = {
  motif_cn_wugu_poison_complex: 26,
  motif_cn_yansheng_talisman_seal: 20,
  motif_cn_zhuyou_incantation_craft: 23,
  motif_cn_household_apotropaic_guardians: 19,
  motif_cn_zhenwu_material_taxonomy: 12,
};

const EXPECTED_PHASE5_RELAY_IDS = [
  'relay-node-wugu-law',
  'relay-node-wugu-hea',
  'relay-node-yansheng-arc',
  'relay-node-yansheng-his',
  'relay-node-zhuyou-rel',
  'relay-node-zhuyou-hea',
  'relay-node-guardians-rel',
  'relay-node-guardians-arc',
  'relay-node-zhubing-gu-his',
  'relay-node-zhubing-gu-hea',
  'relay-node-suishi-rel',
  'relay-node-suishi-his',
  'relay-node-gu-scapegoat-soc',
  'relay-node-gu-scapegoat-law',
  'relay-node-boundary-seal-arc',
  'relay-node-boundary-seal-rel',
  'relay-node-poison-panic-his',
  'relay-node-poison-panic-soc',
  'relay-node-sympathetic-lit',
  'relay-node-sympathetic-rel',
  'relay-node-zhenwu-arc',
  'relay-node-zhenwu-geo',
  'relay-node-gu-statutes-law',
  'relay-node-gu-statutes-his',
  'relay-node-asc-wugu-hea',
  'relay-node-asc-wugu-soc',
  'relay-node-zhenwu-mech-rel',
  'relay-node-zhenwu-mech-lit',
];

test('compiled taxonomy.json and lexicon manifest verify 7 domains, bibliographies, 5 Wugu hubs, and >= 100 SHA-256 shard entries', async () => {
  const [graph, taxonomyBytes, manifestBytes] = await Promise.all([
    readJson('../public/data/graph_data.json'),
    readBytes('../public/syzygy/taxonomy.json'),
    readBytes('../public/syzygy/lexicon/manifest.json'),
  ]);

  const taxonomy = JSON.parse(taxonomyBytes.toString('utf8'));
  const manifest = JSON.parse(manifestBytes.toString('utf8'));
  const graphIds = new Set(graph.nodes.map((node) => node.id));

  assert.equal(taxonomy.version, 1);
  assert.equal(manifest.version, 1);
  assert.equal(taxonomy.snapshot_id, graph.snapshot_id);
  assert.equal(taxonomy.lexicon_manifest_sha256, sha256(manifestBytes));

  assert.ok(Array.isArray(taxonomy.bibliography) && taxonomy.bibliography.length >= 22);
  const bibText = taxonomy.bibliography
    .map((entry) => (typeof entry === 'string'
      ? entry
      : `${entry.id ?? ''} ${entry.title ?? ''} ${entry.citation ?? ''} ${entry.isbn ?? ''}`))
    .join('\n');
  assert.match(bibText, /978-7-5363-2780-1/, 'Missing Xu Hualong 1994 ISBN reference');
  assert.match(bibText, /deng_2025.*978-7-5598-7994-3|978-7-5598-7994-3.*deng_2025/s, 'Missing Deng Qiyao 2025 reference');
  assert.match(bibText, /tao_1998.*957-19-2210-2|957-19-2210-2.*tao_1998/s, 'Missing Tao Siyan 1998 reference');

  assert.equal(taxonomy.domains.length, 7);
  assert.deepEqual(
    taxonomy.domains.map((domain) => domain.order),
    [1, 2, 3, 4, 5, 6, 7],
  );
  assert.deepEqual(
    taxonomy.domains.map((domain) => domain.id),
    [
      'wugu_talisman',
      'underworld_bureaucracy',
      'ghost_rituals_nuo',
      'ethnic_spirit_lexicon',
      'classical_zhiguai_opera',
      'world_mythology',
      'modern_liminal',
    ],
  );

  for (const domain of taxonomy.domains) {
    assert.ok(domain.name && domain.english_name && domain.subtitle && domain.summary);
    assert.ok(Array.isArray(domain.groups) && domain.groups.length >= 3, `${domain.id}: expected >= 3 groups`);
    const resolved = new Set();
    for (const group of domain.groups) {
      for (const id of [...(group.hub_ids ?? []), ...(group.featured_nodes ?? [])]) {
        assert.ok(graphIds.has(id), `${domain.id}/${group.id}: missing graph node ${id}`);
        resolved.add(id);
      }
    }
    assert.equal(domain.node_count, resolved.size, `${domain.id}: node_count mismatch`);
  }

  const wuguDomain = taxonomy.domains[0];
  assert.equal(wuguDomain.id, 'wugu_talisman');
  assert.equal(wuguDomain.groups.length, 5);
  assert.ok(wuguDomain.lexicon_count >= 100, `Expected wugu_talisman lexicon_count >= 100, got ${wuguDomain.lexicon_count}`);
  assert.ok(wuguDomain.lexicon_shard, 'wugu_talisman must define lexicon_shard');
  assert.deepEqual(wuguDomain.lexicon_shard, {
    file: manifest.domains.wugu_talisman.file,
    sha256: manifest.domains.wugu_talisman.sha256,
    count: manifest.domains.wugu_talisman.count,
    categories: manifest.domains.wugu_talisman.categories,
    hub_ids: manifest.domains.wugu_talisman.hub_ids,
  });

  for (const [hubId, expectedCount] of Object.entries(EXPECTED_HUB_LEXICON_COUNTS)) {
    const mapped = taxonomy.hub_to_domain[hubId];
    assert.ok(mapped, `hub_to_domain missing ${hubId}`);
    assert.equal(mapped.domain_id, 'wugu_talisman');
    assert.ok(mapped.count >= expectedCount, `${hubId}: expected count >= ${expectedCount}, got ${mapped.count}`);
    assert.equal(mapped.shard.file, wuguDomain.lexicon_shard.file);
    assert.equal(mapped.shard.sha256, wuguDomain.lexicon_shard.sha256);

    const manifestHub = manifest.hub_to_domain[hubId];
    assert.equal(manifestHub?.domain_id, 'wugu_talisman');
    assert.equal(manifestHub?.domain_name, wuguDomain.name);
    assert.ok((manifestHub?.count ?? 0) >= expectedCount, `${hubId}: expected manifest count >= ${expectedCount}`);
  }

  const shardMeta = manifest.domains.wugu_talisman;
  assert.match(shardMeta.file, /^lexicon\/wugu_talisman-[a-f0-9]{12}\.json$/);
  const shardBytes = await readBytes(`../public/syzygy/${shardMeta.file}`);
  assert.equal(shardBytes.length, shardMeta.bytes);
  assert.equal(sha256(shardBytes), shardMeta.sha256);

  const shard = JSON.parse(shardBytes.toString('utf8'));
  assert.equal(shard.version, 1);
  assert.equal(shard.domain_id, 'wugu_talisman');
  assert.ok(shard.entries.length >= 100, `Expected >= 100 entries in wugu_talisman shard, got ${shard.entries.length}`);
  assert.equal(shard.entries.length, wuguDomain.lexicon_count);

  const seenIds = new Set();
  const hubCounts = {};
  for (const entry of shard.entries) {
    assert.match(entry.id, /^lex_[a-z0-9_]+$/);
    assert.ok(!seenIds.has(entry.id), `Duplicate lexicon entry id ${entry.id}`);
    seenIds.add(entry.id);
    assert.ok(entry.term?.trim() && entry.summary?.trim());
    assert.ok(Array.isArray(entry.primary_sources) && entry.primary_sources.length > 0);
    assert.ok(
      entry.primary_sources.some((src) => /^https:\/\//i.test(src.url ?? '') || (!src.url && src.locator?.trim())),
      `${entry.id}: expected an HTTPS source or a print source with a locator`,
    );
    hubCounts[entry.hub_id] = (hubCounts[entry.hub_id] ?? 0) + 1;
  }
  for (const [hubId, expectedCount] of Object.entries(EXPECTED_HUB_LEXICON_COUNTS)) {
    assert.ok(
      (hubCounts[hubId] ?? 0) >= expectedCount,
      `${hubId}: expected >= ${expectedCount} entries, got ${hubCounts[hubId] ?? 0}`,
    );
  }
});

test('lexiconShards.js loads taxonomy, verifies SHA-256 shards, rejects tampering, resolves hubs, and filters entries', async () => {
  const [taxonomyBytes, manifest] = await Promise.all([
    readBytes('../public/syzygy/taxonomy.json'),
    readJson('../public/syzygy/lexicon/manifest.json'),
  ]);
  const taxonomy = JSON.parse(taxonomyBytes.toString('utf8'));
  const shardFile = manifest.domains.wugu_talisman.file;
  const shardBytes = await readBytes(`../public/syzygy/${shardFile}`);

  const files = new Map([
    ['syzygy/taxonomy.json', taxonomyBytes],
    [`syzygy/${shardFile}`, shardBytes],
  ]);
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
    const loadedTaxAgain = await loadTaxonomy('/astraia/');
    assert.equal(loadedTax.domains.length, 7);
    assert.equal(loadedTaxAgain, loadedTax);
    assert.equal(calls.filter((item) => item === 'syzygy/taxonomy.json').length, 1);

    assert.equal(await loadTaxonomy('/missing-root/'), null);

    const hubInfo = getHubLexiconInfo(loadedTax, 'motif_cn_wugu_poison_complex');
    assert.equal(hubInfo?.domain_id, 'wugu_talisman');
    assert.equal(hubInfo?.domain_name, loadedTax.domains[0].name);
    assert.ok((hubInfo?.count ?? 0) >= 26, `Expected >= 26 entries for motif_cn_wugu_poison_complex, got ${hubInfo?.count}`);
    assert.deepEqual(hubInfo?.shard, loadedTax.domains[0].lexicon_shard);

    const zhenwuHubInfo = getHubLexiconInfo(loadedTax, 'motif_cn_zhenwu_material_taxonomy');
    assert.equal(zhenwuHubInfo?.domain_id, 'wugu_talisman');
    assert.equal(zhenwuHubInfo?.domain_name, loadedTax.domains[0].name);
    assert.ok((zhenwuHubInfo?.count ?? 0) >= 12, `Expected >= 12 entries for motif_cn_zhenwu_material_taxonomy, got ${zhenwuHubInfo?.count}`);
    assert.deepEqual(zhenwuHubInfo?.shard, loadedTax.domains[0].lexicon_shard);
    assert.equal(getHubLexiconInfo(loadedTax, 'nonexistent_hub'), null);

    const taxWithoutHubMap = { ...loadedTax, hub_to_domain: undefined };
    const fallbackHubInfo = getHubLexiconInfo(taxWithoutHubMap, 'motif_cn_zhuyou_incantation_craft');
    assert.equal(fallbackHubInfo?.domain_id, 'wugu_talisman');
    assert.ok((fallbackHubInfo?.count ?? 0) >= 100);
    assert.equal(fallbackHubInfo?.count, loadedTax.domains[0].lexicon_count);

    const loadedShard = await loadLexiconShard('/astraia/', loadedTax, 'wugu_talisman');
    const loadedShardAgain = await loadLexiconShard('/astraia/', loadedTax, 'wugu_talisman');
    assert.equal(loadedShard.domain_id, 'wugu_talisman');
    assert.ok(loadedShard.entries.length >= 100);
    assert.equal(loadedShard.entries.length, loadedTax.domains[0].lexicon_count);
    assert.equal(loadedShard.sha256, manifest.domains.wugu_talisman.sha256);
    assert.equal(loadedShardAgain, loadedShard);
    assert.equal(calls.filter((item) => item === `syzygy/${shardFile}`).length, 1);

    clearLexiconCache();
    files.set(
      `syzygy/${shardFile}`,
      Buffer.from(shardBytes.toString('utf8').replace('金蚕蛊', '篡改词条'), 'utf8'),
    );
    await assert.rejects(
      loadLexiconShard('/astraia/', loadedTax, 'wugu_talisman'),
      /校验失败/,
    );

    // Failed SHA-256 checks must not poison the cache; restoring valid bytes recovers cleanly.
    files.set(`syzygy/${shardFile}`, shardBytes);
    const recoveredShard = await loadLexiconShard('/astraia/', loadedTax, 'wugu_talisman');
    assert.equal(recoveredShard.entries.length, loadedShard.entries.length);

    assert.equal(filterLexiconEntries(recoveredShard.entries).length, recoveredShard.entries.length);
    assert.equal(filterLexiconEntries(recoveredShard.entries, '', '全部').length, recoveredShard.entries.length);

    const poisonCategory = filterLexiconEntries(recoveredShard.entries, '', '巫蛊刑狱与禁律');
    assert.ok(poisonCategory.length >= 2);
    assert.ok(poisonCategory.every((entry) => entry.category === '巫蛊刑狱与禁律'));

    const dualTrackCategory = filterLexiconEntries(recoveredShard.entries, '', '巫蛊双轨法制与蛊界');
    assert.ok(dualTrackCategory.length >= 3);
    assert.ok(dualTrackCategory.every((entry) => entry.category === '巫蛊双轨法制与蛊界'));

    const aliasHit = filterLexiconEntries(recoveredShard.entries, '嫁金蚕');
    assert.ok(aliasHit.some((entry) => entry.id === 'lex_gu_jincan'));

    const nfkcHit = filterLexiconEntries(recoveredShard.entries, '１９３５');
    assert.ok(nfkcHit.some((entry) => entry.id === 'lex_gu_chonggu'));

    const citationOnlyQuery = filterLexiconEntries(recoveredShard.entries, 'BRILL 1993');
    assert.equal(citationOnlyQuery.length, 0);
    const multiWordHit = filterLexiconEntries(recoveredShard.entries, '鲁班 厌胜');
    assert.ok(multiWordHit.some((entry) => entry.hub_id === 'motif_cn_yansheng_talisman_seal'));
  } finally {
    clearLexiconCache();
    globalThis.fetch = oldFetch;
    Object.defineProperty(globalThis, 'crypto', { value: oldCrypto, configurable: true });
  }
});

test('graph_index.json slimming reduces size and hydrateGraphIndex restores structural equivalence', async () => {
  const [rawGraphBytes, graphIndexBytes, details] = await Promise.all([
    readBytes('../public/data/graph_data.json'),
    readBytes('../public/data/graph_index.json'),
    readJson('../public/data/graph_details.json'),
  ]);

  const rawGraph = JSON.parse(rawGraphBytes.toString('utf8'));
  const rawIndex = JSON.parse(graphIndexBytes.toString('utf8'));

  assert.equal(rawIndex.compact_defaults, true);
  assert.equal(rawIndex.snapshot_id, rawGraph.snapshot_id);
  assert.equal(details.snapshot_id, rawGraph.snapshot_id);
  assert.ok(
    graphIndexBytes.length < rawGraphBytes.length * 0.5,
    `Expected graph_index.json (${graphIndexBytes.length}B) to be < 50% of graph_data.json (${rawGraphBytes.length}B)`,
  );

  const hydratedBridge = hydrateBridgeGraphIndex(structuredClone(rawIndex));
  const hydratedApp = hydrateAppGraphIndex(structuredClone(rawIndex));

  assert.equal(hydratedBridge.link_notes, undefined);
  assert.equal(hydratedApp.link_notes, undefined);
  assert.equal(hydratedBridge.nodes.length, rawGraph.nodes.length);
  assert.equal(hydratedApp.nodes.length, rawGraph.nodes.length);
  assert.equal(hydratedBridge.links.length, rawGraph.links.length);
  assert.equal(hydratedApp.links.length, rawGraph.links.length);
  assert.equal(details.nodes.length, rawGraph.nodes.length);

  for (let i = 0; i < rawGraph.nodes.length; i += 1) {
    const raw = rawGraph.nodes[i];
    const bNode = hydratedBridge.nodes[i];
    const aNode = hydratedApp.nodes[i];
    const dNode = details.nodes[i];

    assert.equal(bNode.id, raw.id);
    assert.equal(aNode.id, raw.id);
    assert.equal(dNode.id, raw.id);
    assert.equal(bNode.title, raw.title);
    assert.equal(aNode.title, raw.title);
    assert.equal(bNode.z_layer, raw.z_layer);
    assert.equal(aNode.z_layer, raw.z_layer);
    assert.equal(bNode.z, raw.z);
    assert.equal(aNode.z, raw.z);
    assert.equal(bNode.node_type, raw.node_type);
    assert.equal(aNode.node_type, raw.node_type);
    assert.equal(bNode.genre, raw.genre);
    assert.equal(aNode.genre, raw.genre);
    assert.equal(bNode.credibility_tier, raw.credibility_tier);
    assert.equal(aNode.credibility_tier, raw.credibility_tier);
    assert.equal(bNode.is_fictional_quarantine, raw.is_fictional_quarantine);
    assert.equal(aNode.is_fictional_quarantine, raw.is_fictional_quarantine);
    assert.deepEqual(bNode.aliases, raw.aliases);
    assert.deepEqual(aNode.aliases, raw.aliases);
    assert.deepEqual(bNode.spatial, raw.spatial);
    assert.deepEqual(aNode.spatial, raw.spatial);
    assert.deepEqual(bNode.temporal, raw.temporal);
    assert.deepEqual(aNode.temporal, raw.temporal);
    assert.deepEqual(bNode.standards, raw.standards);
    assert.deepEqual(aNode.standards, raw.standards);

    if (raw.reading) {
      assert.equal(bNode.reading?.kind, raw.reading.kind);
      assert.equal(aNode.reading?.kind, raw.reading.kind);
      if (raw.reading.paragraphs?.length) {
        assert.equal(bNode.reading?.paragraphs?.[0], raw.reading.paragraphs[0]);
        assert.equal(aNode.reading?.paragraphs?.[0], raw.reading.paragraphs[0]);
      }
      assert.equal(bNode.reading?.map_label, raw.reading.map_label);
      assert.equal(bNode.reading?.location_note, raw.reading.location_note);
      if (raw.reading.edition) {
        assert.equal(bNode.reading?.edition?.source_number, raw.reading.edition.source_number);
        assert.equal(aNode.reading?.edition?.source_number, raw.reading.edition.source_number);
      }
    }

    const merged = { ...bNode, ...dNode };
    assert.deepEqual(merged.sources, raw.sources);
    assert.deepEqual(merged.markdown, raw.markdown);
    assert.deepEqual(merged.source_path, raw.source_path);
    assert.deepEqual(merged.reading, raw.reading);
    assert.deepEqual(merged.audit, raw.audit);
  }

  for (let i = 0; i < rawGraph.links.length; i += 1) {
    const rawLink = rawGraph.links[i];
    const bLink = hydratedBridge.links[i];
    const aLink = hydratedApp.links[i];
    const expected = {
      source: rawLink.source,
      target: rawLink.target,
      type: rawLink.type,
      status: rawLink.status,
      note: rawLink.note,
      is_fictional_quarantine: rawLink.is_fictional_quarantine,
      matched_codes: rawLink.matched_codes,
    };
    assert.deepEqual(bLink, expected);
    assert.deepEqual(aLink, expected);
  }

  assert.equal(ALL_PHASE5_IDS.length, 40);
  const hydratedById = new Map(hydratedBridge.nodes.map((node) => [node.id, node]));
  for (const id of ALL_PHASE5_IDS) {
    const node = hydratedById.get(id);
    assert.ok(node, `Missing Phase 5/5B node ${id} in hydrated graph_index.json`);
    assert.ok(node.reading?.paragraphs?.[0]?.trim(), `${id}: expected hydrated first reading paragraph`);
    assert.equal(typeof node.genre_contract, 'string');
  }
});

test('Phase 5 + 5B Wugu & Zhenwu integration: 40 new nodes (>= 11451 total), SYZ-288..313 (>= 313 total), and >= 140 relays', async () => {
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

  assert.ok(graph.nodes.length >= 11451, `Expected >= 11451 total nodes, got ${graph.nodes.length}`);
  assert.ok(bridges.length >= 313, `Expected >= 313 total bridges, got ${bridges.length}`);
  assert.ok(relays.length >= 140, `Expected >= 140 total relay rules, got ${relays.length}`);

  for (const id of PHASE5_L4_IDS) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing L4 node ${id}`);
    assert.equal(node.z_layer, 4);
    assert.ok(['mechanism', 'theory'].includes(node.node_type));
    assert.equal(node.reading?.kind, 'research');
    assert.equal(node.reading?.paragraphs?.length, 3);
  }

  for (const id of PHASE5_L3_HUB_IDS) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing L3 hub ${id}`);
    assert.equal(node.z_layer, 3);
    assert.equal(node.node_type, 'motif_index');
    assert.equal(node.reading?.kind, 'research');
    assert.equal(node.reading?.paragraphs?.length, 3);
  }

  for (const id of PHASE5_L2_CORPUS_IDS) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing L2 corpus ${id}`);
    assert.equal(node.z_layer, 2);
    assert.equal(node.node_type, 'myth_corpus');
    assert.equal(node.reading?.kind, 'research');
    assert.equal(node.reading?.paragraphs?.length, 3);
  }

  assert.equal(PHASE5_L1_CASES.length, 26);
  for (const { id, bridgeId, cluster } of PHASE5_L1_CASES) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing L1 case ${id}`);
    assert.equal(node.z_layer, 1);
    assert.equal(node.node_type, 'case');
    assert.equal(nodeRegion(node), 'china', `${id}: expected region china`);
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
  for (const relayId of EXPECTED_PHASE5_RELAY_IDS) {
    const rule = relaysById.get(relayId);
    assert.ok(rule, `Missing Phase 5/5B relay rule ${relayId}`);
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
  assert.equal(coveredTargets.size, 14, 'All 14 new L2/L3/L4 nodes must be covered by new relay rules');
  for (const subject of ['ARC', 'GEO', 'HEA', 'HIS', 'LAW', 'LIT', 'REL', 'SOC']) {
    assert.ok(relaySubjects.has(subject), `Expected Phase 5/5B relays to cover discipline ${subject}`);
  }
});
