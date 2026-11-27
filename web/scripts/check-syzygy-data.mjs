import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const allowMissingTaxonomy = process.argv.includes('--allow-missing-taxonomy')
  || process.argv.includes('--skip-taxonomy');
const root = fileURLToPath(new URL('../', import.meta.url));
const load = async path => JSON.parse(await readFile(path, 'utf8'));
const graph = await load(`${root}/public/data/graph_data.json`);
const index = await load(`${root}/public/data/graph_index.json`);
assert.equal(index.compact_defaults, true, 'graph_index.json must be built with compact_defaults: true');
const detailBytes = await readFile(`${root}/public/data/${index.details_file}`);
const details = JSON.parse(detailBytes.toString('utf8'));
const bookBytes = await readFile(`${root}/public/knowledge/data.json`);
const book = JSON.parse(bookBytes.toString('utf8'));
const portal = await load(`${root}/public/syzygy/data.json`);
const matchBytes = await readFile(`${root}/public/syzygy/matches.json`);
const matchIndex = JSON.parse(matchBytes.toString('utf8'));
const rules = await load(`${root}/src/syzygy/matching-rules.json`);
const concepts = await load(`${root}/src/syzygy/matching-concepts.json`);
const relays = await load(`${root}/src/syzygy/matching-relays.json`);

const digest = bytes => createHash('sha256').update(bytes).digest('hex');
assert.equal(graph.snapshot_id, index.snapshot_id);
assert.equal(graph.snapshot_id, details.snapshot_id);
assert.equal(graph.snapshot_id, portal.snapshot_id);
assert.equal(index.details_sha256, digest(detailBytes));
assert.equal(portal.handbook_sha256, digest(bookBytes));
assert.equal(portal.matches_sha256, digest(matchBytes));
assert.equal(matchIndex.snapshot_id, graph.snapshot_id);
assert.equal(matchIndex.handbook_sha256, portal.handbook_sha256);
assert.equal(graph.nodes.length, index.nodes.length);
assert.equal(graph.nodes.length, details.nodes.length);
assert.equal(new Set(graph.nodes.map(n => n.id)).size, graph.nodes.length);
assert.equal(new Set(book.entries.map(n => n.id)).size, book.entries.length);
assert.ok(index.nodes.every((n, i) => n.id === details.nodes[i].id));

const nodes = new Map(graph.nodes.map(node => [node.id, node]));
const entries = new Map(book.entries.map(entry => [entry.id, entry]));
const relaysById = new Map(relays.map(rule => [rule.id, rule]));
const normalize = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase();

let checkedLinks = 0, substantiveNodes = 0, relayNodes = 0, thematicNodes = 0, guideNodes = 0;
const substantiveEntries = new Set();
const connectedDisciplines = new Set();

for (const [nodeId, rows] of Object.entries(matchIndex.matches)) {
  const node = nodes.get(nodeId);
  assert.ok(node, `Unknown match node ${nodeId}`);
  assert.equal(new Set(rows.map(row => row.entry)).size, rows.length, `Duplicate match for ${nodeId}`);
  const hasCurated = rows.some(row => row.kind === 'curated');
  const hasRelay = rows.some(row => row.kind === 'relay');
  const hasTheme = rows.some(row => row.kind === 'theme');
  const hasGuide = rows.some(row => row.kind === 'guide');
  if (hasCurated || hasRelay || hasTheme) substantiveNodes++;
  if (hasRelay) relayNodes++;
  if (hasTheme) thematicNodes++;
  if (hasGuide) guideNodes++;

  for (const row of rows) {
    checkedLinks++;
    const entry = entries.get(row.entry);
    assert.ok(entry, `Unknown handbook entry ${row.entry}`);
    assert.ok(['curated', 'relay', 'theme', 'guide'].includes(row.kind));
    assert.equal(row.status, undefined, 'Automatic recommendations must not claim evidence status.');

    if (row.kind !== 'guide') {
      substantiveEntries.add(row.entry);
      connectedDisciplines.add(entry.subject);
    }

    if (row.kind === 'guide') {
      const rule = rules.find(item => item.id === row.rule);
      assert.ok(rule);
      assert.equal(rule.entry, row.entry);
      assert.equal(rule.reason, row.reason);
      if (rule.id_prefix) assert.ok(node.id.startsWith(rule.id_prefix));
      assert.ok((node.sources ?? []).some(source => rule.source_types.includes(source.type)
        && (!rule.source_contains || `${source.url ?? ''} ${source.doi ?? ''} ${source.citation ?? ''}`.includes(rule.source_contains))));
    }

    if (row.kind === 'relay') {
      const rule = relaysById.get(row.rule);
      assert.ok(rule, `Unknown relay rule ${row.rule}`);
      assert.equal(rule.entry, row.entry);
      assert.equal(rule.reason, row.reason);
      if (row.via) {
        assert.ok(nodes.has(row.via), `Unknown relay via node ${row.via}`);
        assert.equal(rule.propagate_edges, true);
      }
    }

    if (row.kind === 'theme') {
      assert.ok(Array.isArray(row.terms) && row.terms.length);
      for (const term of row.terms) {
        const source = term.source === '题名' ? node.title
          : term.source === '别名' ? (node.aliases ?? []).join(' ')
            : term.source === '正文' ? (node.reading?.paragraphs ?? []).join(' ')
              : term.source === '原文' ? (node.reading?.edition?.text ?? '')
                : `${node.title} ${(node.aliases ?? []).join(' ')}`;
        assert.ok(normalize(source).includes(normalize(term.term)), `${nodeId}: missing source term ${term.term} in ${term.source}`);
        const target = term.target === '题名' ? entry.title : term.target === '主题' ? entry.topic : entry.title;
        const targetTerm = ['题名', '主题'].includes(term.target) ? term.term : term.target;
        assert.ok(normalize(target).includes(normalize(targetTerm)), `${row.entry}: missing target term ${targetTerm}`);
      }
      if (row.method === 'concept') {
        const rule = concepts.find(item => item.id === row.rule);
        assert.ok(rule);
        assert.equal(rule.entry, row.entry);
        if (row.terms.some(term => term.source === '正文')) {
          assert.equal(rule.include_reading, true);
          assert.equal(node.z_layer, 1);
          assert.ok(row.terms.every(term => !(rule.title_only_words ?? []).includes(term.term)));
        }
        if (row.terms.some(term => term.source === '原文')) {
          assert.equal(rule.include_edition, true);
          assert.equal(node.z_layer, 1);
          assert.ok(row.terms.every(term => !(rule.title_only_words ?? []).includes(term.term)));
        }
      }
    }

    if (row.kind === 'curated') {
      assert.ok(portal.bridges.some(bridge => bridge.id === row.bridge_id && bridge.mythos.id === nodeId && bridge.physis.id === row.entry && bridge.rationale === row.reason));
    }
  }
}

assert.equal(matchIndex.stats.matched_nodes, Object.keys(matchIndex.matches).length);
assert.equal(matchIndex.stats.substantive_nodes, substantiveNodes);
assert.equal(matchIndex.stats.relay_nodes, relayNodes);
assert.equal(matchIndex.stats.theme_nodes, thematicNodes);
assert.equal(matchIndex.stats.guide_nodes, guideNodes);
assert.equal(matchIndex.stats.substantive_book_entries, substantiveEntries.size);
assert.equal(matchIndex.stats.connected_disciplines, connectedDisciplines.size);
assert.equal(matchIndex.stats.links, checkedLinks);
assert.equal(connectedDisciplines.size, 20, `Expected all 20 disciplines connected, got ${connectedDisciplines.size}`);

const examples = [
  ['case_mrs_h_co_haunting_1921', 'LIF-EMERG-0002', 'theme'],
  ['scot_a_egd_1611', 'HIS-6-0001', 'guide'],
  ['case_cn_zibuyu_v01_s002', 'HIS-6-0005', 'guide'],
  ['case_cn_zibuyu_v03_s023', 'PHI-6-0002', 'theme'],
];
for (const [id, entry, kind] of examples) {
  if (nodes.has(id) && entries.has(entry)) {
    assert.ok((matchIndex.matches[id] ?? []).some(row => row.entry === entry && row.kind === kind), `Expected ${kind} for ${id} -> ${entry}`);
  }
}
if (nodes.has('case_cn_beijing_palace_well_online_2022')) {
  assert.ok(!(matchIndex.matches.case_cn_beijing_palace_well_online_2022 ?? []).some(row => row.entry === 'FOR-4-0037'), 'A shared location must not be treated as a phenol match.');
}
for (const [id, target, status] of [
  ['case_mrs_h_co_haunting_1921', 'mech_co_poisoning', 'confirmed'],
  ['case_salem_1692', 'mech_salem_ergotism', 'refuted'],
  ['case_old_hag_sleep_paralysis_1982', 'mech_sleep_paralysis', 'unverified'],
]) {
  if (nodes.has(id) && nodes.has(target)) {
    assert.ok(graph.links.some(link => link.source === id && link.target === target && link.type === 'EXPLAINED_BY' && link.status === status));
  }
}
for (const bridge of portal.bridges) {
  const story = nodes.get(bridge.mythos.id), entry = entries.get(bridge.physis.id);
  assert.ok(story && entry, `Missing real node: ${bridge.id}`);
  assert.ok(bridge.rationale?.trim(), `Missing reading rationale: ${bridge.id}`);
  assert.ok((matchIndex.matches[story.id] ?? []).some(row => row.kind === 'curated'
    && row.bridge_id === bridge.id && row.entry === entry.id && row.reason === bridge.rationale),
    `Curated bridge missing from the bidirectional index: ${bridge.id}`);
  assert.equal(bridge.mythos.title, story.title);
  assert.deepEqual(bridge.mythos.spatial, story.spatial);
  assert.deepEqual(bridge.mythos.reading, story.reading);
  assert.equal(bridge.fiction, story.credibility_tier === 'F' || !!story.is_fictional_quarantine);
  assert.equal(bridge.physis.body, entry.body);
  assert.equal(bridge.physis.page, entry.page);
  if (bridge.related) {
    assert.ok(nodes.has(bridge.related.id));
    const edge = graph.links.find(link => (link.source === story.id && link.target === bridge.related.id)
      || (link.target === story.id && link.source === bridge.related.id));
    assert.equal(bridge.edge?.status ?? null, edge?.status ?? null);
    assert.equal(bridge.edge?.type ?? null, edge?.type ?? null);
  }
}

const taxonomyPath = `${root}/public/syzygy/taxonomy.json`;
const lexiconManifestPath = `${root}/public/syzygy/lexicon/manifest.json`;
let taxonomyBytes = null;
try {
  taxonomyBytes = await readFile(taxonomyPath);
} catch (error) {
  if (error.code !== 'ENOENT' || !allowMissingTaxonomy) {
    throw new Error(`Missing syzygy/taxonomy.json (${error.message}). Run build-taxonomy-lexicon.mjs first.`);
  }
}
function assertNonEmptyString(value, message) {
  assert.ok(typeof value === 'string' && value.trim().length > 0, message);
}

const normalizeLexiconTerm = value => {
  const compact = String(value ?? '').normalize('NFKC').trim().toLocaleLowerCase().replace(/[\s\p{P}\p{S}]+/gu, '');
  return compact || String(value ?? '').normalize('NFKC').trim().toLocaleLowerCase();
};

function validateEditorialPreface(preface) {
  assert.ok(preface && typeof preface === 'object' && !Array.isArray(preface),
    'taxonomy.editorial_preface must be an object');
  assertNonEmptyString(preface.title, 'editorial_preface.title must be a non-empty string');
  assertNonEmptyString(preface.subtitle, 'editorial_preface.subtitle must be a non-empty string');
  assert.ok(
    Array.isArray(preface.paragraphs)
      && preface.paragraphs.length >= 2
      && preface.paragraphs.every(p => typeof p === 'string' && p.trim().length > 0),
    'editorial_preface.paragraphs must contain >= 2 non-empty strings',
  );
  assert.ok(
    Array.isArray(preface.principles) && preface.principles.length >= 3,
    'editorial_preface.principles must contain >= 3 items',
  );
  for (const [idx, item] of preface.principles.entries()) {
    assert.ok(item && typeof item === 'object' && !Array.isArray(item),
      `editorial_preface.principles[${idx}] must be an object`);
    assertNonEmptyString(item.label, `editorial_preface.principles[${idx}].label must be a non-empty string`);
    assertNonEmptyString(item.text, `editorial_preface.principles[${idx}].text must be a non-empty string`);
  }
}

function validateEditorialIntro(intro, domainId) {
  assert.ok(intro && typeof intro === 'object' && !Array.isArray(intro),
    `${domainId}: editorial_intro must be an object`);
  assertNonEmptyString(intro.heading, `${domainId}: editorial_intro.heading must be a non-empty string`);
  assertNonEmptyString(intro.epigraph_thesis, `${domainId}: editorial_intro.epigraph_thesis must be a non-empty string`);
  assert.ok(
    Array.isArray(intro.paragraphs)
      && intro.paragraphs.length >= 2
      && intro.paragraphs.every(p => typeof p === 'string' && p.trim().length > 0),
    `${domainId}: editorial_intro.paragraphs must contain >= 2 non-empty strings`,
  );
  assert.ok(
    Array.isArray(intro.lenses)
      && intro.lenses.length >= 1
      && intro.lenses.every(tag => typeof tag === 'string' && tag.trim().length > 0),
    `${domainId}: editorial_intro.lenses must be a non-empty array of non-empty strings`,
  );
}

let taxonomySummary = null;
if (taxonomyBytes) {
  const taxonomy = JSON.parse(taxonomyBytes.toString('utf8'));
  const manifestBytes = await readFile(lexiconManifestPath);
  const manifest = JSON.parse(manifestBytes.toString('utf8'));
  assert.equal(taxonomy.version, 1);
  assert.equal(manifest.version, 1);
  assert.equal(taxonomy.lexicon_manifest_sha256, digest(manifestBytes));
  if (taxonomy.snapshot_id) assert.equal(taxonomy.snapshot_id, graph.snapshot_id);
  assert.ok(Array.isArray(taxonomy.domains) && taxonomy.domains.length === 7,
    `Expected 7 taxonomy domains, got ${taxonomy.domains?.length}`);
  const domainIds = new Set(taxonomy.domains.map(domain => domain.id));
  assert.equal(domainIds.size, 7, 'Duplicate taxonomy domain ids');

  const manifestEntries = Object.entries(manifest.domains ?? {});
  assert.ok(manifestEntries.length >= 1 && manifestEntries.length <= taxonomy.domains.length,
    `Expected 1..${taxonomy.domains.length} active shards in lexicon manifest, got ${manifestEntries.length}`);

  const hasEditorialPreface = taxonomy.editorial_preface != null;
  const hasAnyDomainIntro = taxonomy.domains.some(domain => domain?.editorial_intro != null);
  const hasAnyChapterIntro = taxonomy.domains.some(domain =>
    Array.isArray(domain?.groups) && domain.groups.some(group => group?.chapter_intro != null),
  );
  const requireEditorial = hasEditorialPreface
    || hasAnyDomainIntro
    || hasAnyChapterIntro
    || manifestEntries.length > 1
    || process.argv.includes('--require-editorial');

  if (hasEditorialPreface || requireEditorial) {
    validateEditorialPreface(taxonomy.editorial_preface);
  }

  for (const domain of taxonomy.domains) {
    assert.ok(domain.id && domain.name && Array.isArray(domain.groups), `Invalid domain ${domain?.id}`);
    assert.ok(Number.isInteger(domain.node_count) && domain.node_count >= 0, `Invalid node_count on ${domain.id}`);
    assert.ok(
      Number.isInteger(domain.classified_node_count) && domain.classified_node_count >= domain.node_count,
      `classified_node_count (${domain.classified_node_count}) must be >= node_count (${domain.node_count}) on ${domain.id}`,
    );
    if (domain.sample_classified_nodes != null) {
      assert.ok(
        Array.isArray(domain.sample_classified_nodes) && domain.sample_classified_nodes.length <= 16,
        `${domain.id}: sample_classified_nodes must be an array of at most 16 items`,
      );
      for (const sample of domain.sample_classified_nodes) {
        assertNonEmptyString(sample?.id, `${domain.id}: sample_classified_nodes item missing id`);
        assert.ok(nodes.has(sample.id), `${domain.id}: unknown sample_classified_nodes id ${sample.id}`);
        assertNonEmptyString(sample?.title, `${domain.id}: sample_classified_nodes ${sample.id} missing title`);
      }
    }
    assert.ok(Number.isInteger(domain.lexicon_count) && domain.lexicon_count >= 0, `Invalid lexicon_count on ${domain.id}`);
    if (domain.editorial_intro != null || requireEditorial) {
      validateEditorialIntro(domain.editorial_intro, domain.id);
    }
    for (const [groupIdx, group] of domain.groups.entries()) {
      assert.ok(group && typeof group === 'object', `${domain.id}: invalid group at index ${groupIdx}`);
      assertNonEmptyString(group.id, `${domain.id}: group[${groupIdx}].id must be a non-empty string`);
      assertNonEmptyString(group.title, `${domain.id}/${group.id}: title must be a non-empty string`);
      assertNonEmptyString(group.description, `${domain.id}/${group.id}: description must be a non-empty string`);
      if (group.chapter_intro != null || requireEditorial) {
        assertNonEmptyString(group.chapter_intro, `${domain.id}/${group.id}: chapter_intro must be a non-empty string`);
      }
    }
    const manifestShard = manifest.domains?.[domain.id];
    if (domain.lexicon_shard || manifestShard) {
      assert.ok(domain.lexicon_shard && manifestShard, `Mismatched shard metadata for ${domain.id}`);
      assert.equal(domain.lexicon_shard.file, manifestShard.file);
      assert.equal(domain.lexicon_shard.sha256, manifestShard.sha256);
      assert.equal(domain.lexicon_shard.count, manifestShard.count);
      assert.deepEqual(domain.lexicon_shard.categories, manifestShard.categories);
      assert.deepEqual(domain.lexicon_shard.hub_ids, manifestShard.hub_ids);
      assert.equal(domain.lexicon_count, manifestShard.count);
    }
  }

  if (taxonomy.corpus_classification_coverage != null) {
    const cov = taxonomy.corpus_classification_coverage;
    assert.equal(cov.total_graph_nodes, graph.nodes.length, 'corpus_classification_coverage.total_graph_nodes mismatch');
    assert.ok(
      Number.isInteger(cov.total_classified_unique)
        && cov.total_classified_unique >= 0
        && cov.total_classified_unique <= graph.nodes.length,
      'Invalid corpus_classification_coverage.total_classified_unique',
    );
  }

  let totalLexiconEntries = 0;
  const seenLexiconIds = new Set();
  for (const [domainId, shardMeta] of manifestEntries) {
    assert.ok(domainIds.has(domainId), `Unknown domain in lexicon manifest: ${domainId}`);
    assert.match(shardMeta.file ?? '', /^lexicon\/[a-z0-9_]+-[a-f0-9]{12}\.json$/);
    const shardBytes = await readFile(`${root}/public/syzygy/${shardMeta.file}`);
    assert.equal(shardBytes.length, shardMeta.bytes, `Byte size mismatch for ${shardMeta.file}`);
    assert.equal(digest(shardBytes), shardMeta.sha256, `SHA-256 mismatch for ${shardMeta.file}`);
    const shard = JSON.parse(shardBytes.toString('utf8'));
    assert.equal(shard.version, 1, `Invalid shard version for ${shardMeta.file}`);
    assert.equal(shard.domain_id, domainId);
    assert.ok(Array.isArray(shard.entries) && shard.entries.length > 0 && shard.entries.length === shardMeta.count,
      `Entry count mismatch for ${shardMeta.file}`);

    const shardCategories = [];
    const seenShardCategories = new Set();
    const seenShardTerms = new Set();
    const shardHubCounts = new Map();
    for (const entry of shard.entries) {
      assert.match(entry?.id ?? '', /^lex_[a-z0-9_]+$/, `Invalid lexicon entry id: ${entry?.id}`);
      assertNonEmptyString(entry.hub_id, `Invalid hub_id on ${entry.id}`);
      assertNonEmptyString(entry.term, `Invalid term on ${entry.id}`);
      const normTerm = normalizeLexiconTerm(entry.term);
      assert.ok(!seenShardTerms.has(normTerm), `Duplicate normalized term "${entry.term}" in shard ${shardMeta.file}`);
      seenShardTerms.add(normTerm);
      assertNonEmptyString(entry.gist, `Missing non-empty gist on ${entry.id}`);
      assert.ok(entry.gist.length <= 36, `gist exceeds 36 chars on ${entry.id}: ${entry.gist}`);
      assertNonEmptyString(entry.reading_tag, `Missing non-empty reading_tag on ${entry.id}`);
      assertNonEmptyString(entry.summary, `Invalid summary on ${entry.id}`);
      assert.ok(Array.isArray(entry.primary_sources) && entry.primary_sources.length > 0,
        `Missing primary_sources on ${entry.id}`);
      let hasHttps = false;
      let hasLocatedPrintSource = false;
      for (const src of entry.primary_sources) {
        assert.ok(src && typeof src === 'object', `Invalid primary_sources item on ${entry.id}`);
        assertNonEmptyString(src.citation, `Missing primary_sources.citation on ${entry.id}`);
        if (src.url) {
          assert.match(src.url, /^https?:\/\//i, `Invalid primary_sources.url on ${entry.id}`);
          if (/^https:\/\//i.test(src.url.trim())) hasHttps = true;
        } else {
          assertNonEmptyString(src.locator, `Missing page or chapter on ${entry.id}`);
          hasLocatedPrintSource = true;
        }
      }
      assert.ok(hasHttps || hasLocatedPrintSource, `${entry.id} needs an HTTPS or located print source`);
      if (entry.case_id) {
        const story = nodes.get(entry.case_id);
        assert.ok(story?.z_layer === 1 && Number.isFinite(story?.spatial?.lat) && Number.isFinite(story?.spatial?.lng),
          `${entry.id} references a missing or unlocated story`);
      }
      if (entry.knowledge_id) {
        assert.ok(entries.get(entry.knowledge_id)?.body?.trim(), `${entry.id} references missing knowledge text`);
        assertNonEmptyString(entry.knowledge_note, `Missing thematic reading note on ${entry.id}`);
      } else {
        assert.ok(!entry.knowledge_note, `${entry.id} has a note without a knowledge reference`);
      }
      assert.ok(!seenLexiconIds.has(entry.id), `Duplicate lexicon entry ${entry.id}`);
      seenLexiconIds.add(entry.id);

      const category = typeof entry.category === 'string' ? entry.category.trim() : '';
      if (category && !seenShardCategories.has(category)) {
        seenShardCategories.add(category);
        shardCategories.push(category);
      }
      shardHubCounts.set(entry.hub_id, (shardHubCounts.get(entry.hub_id) ?? 0) + 1);
    }

    assert.deepEqual(shardMeta.categories, shardCategories, `Category index mismatch in ${shardMeta.file}`);
    assert.deepEqual(shardMeta.hub_ids, [...shardHubCounts.keys()], `Hub index mismatch in ${shardMeta.file}`);
    for (const [hubId, count] of shardHubCounts.entries()) {
      const mHub = manifest.hub_to_domain?.[hubId];
      const tHub = taxonomy.hub_to_domain?.[hubId];
      assert.ok(mHub && mHub.domain_id === domainId && mHub.count === count,
        `manifest.hub_to_domain mismatch for ${hubId}`);
      assert.ok(tHub && tHub.domain_id === domainId && tHub.count === count && tHub.shard?.file === shardMeta.file,
        `taxonomy.hub_to_domain mismatch for ${hubId}`);
    }
    totalLexiconEntries += shard.entries.length;
  }
  taxonomySummary = {
    domains: taxonomy.domains.length,
    shards: manifestEntries.length,
    lexicon_entries: totalLexiconEntries,
    editorial_preface: Boolean(taxonomy.editorial_preface),
  };
}

console.log(JSON.stringify({ nodes: graph.nodes.length, links: graph.links.length, book_entries: book.entries.length, curated: portal.bridges.length, matches: matchIndex.stats, taxonomy: taxonomySummary, snapshot: graph.snapshot_id }));
