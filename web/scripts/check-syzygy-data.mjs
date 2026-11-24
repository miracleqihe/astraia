import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../',import.meta.url));
const load = async path => JSON.parse(await readFile(path,'utf8'));
const graph = await load(`${root}/public/data/graph_data.json`);
const index = await load(`${root}/public/data/graph_index.json`);
const detailBytes = await readFile(`${root}/public/data/${index.details_file}`);
const details = JSON.parse(detailBytes.toString('utf8'));
const bookBytes = await readFile(`${root}/public/knowledge/data.json`);
const book = JSON.parse(bookBytes.toString('utf8'));
const portal = await load(`${root}/public/syzygy/data.json`);
const matchBytes = await readFile(`${root}/public/syzygy/matches.json`);
const matchIndex = JSON.parse(matchBytes.toString('utf8'));
const rules = await load(`${root}/src/syzygy/matching-rules.json`);
const concepts = await load(`${root}/src/syzygy/matching-concepts.json`);
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
assert.equal(graph.snapshot_id,index.snapshot_id);
assert.equal(graph.snapshot_id,details.snapshot_id);
assert.equal(graph.snapshot_id,portal.snapshot_id);
assert.equal(index.details_sha256,digest(detailBytes));
assert.equal(portal.handbook_sha256,digest(bookBytes));
assert.equal(portal.matches_sha256,digest(matchBytes));
assert.equal(matchIndex.snapshot_id,graph.snapshot_id);
assert.equal(matchIndex.handbook_sha256,portal.handbook_sha256);
assert.equal(graph.nodes.length,index.nodes.length);
assert.equal(graph.nodes.length,details.nodes.length);
assert.equal(new Set(graph.nodes.map(n=>n.id)).size,graph.nodes.length);
assert.equal(new Set(book.entries.map(n=>n.id)).size,book.entries.length);
assert.ok(index.nodes.every((n,i)=>n.id === details.nodes[i].id));
const nodes = new Map(graph.nodes.map(node=>[node.id,node]));
const entries = new Map(book.entries.map(entry=>[entry.id,entry]));
const normalize = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase();
let checkedLinks = 0, thematicNodes = 0, guideNodes = 0;
for (const [nodeId, rows] of Object.entries(matchIndex.matches)) {
  const node=nodes.get(nodeId); assert.ok(node,`Unknown match node ${nodeId}`);
  assert.equal(new Set(rows.map(row=>row.entry)).size,rows.length,`Duplicate match for ${nodeId}`);
  if (rows.some(row=>row.kind==='theme')) thematicNodes++;
  if (rows.some(row=>row.kind==='guide')) guideNodes++;
  for (const row of rows) {
    checkedLinks++;
    const entry=entries.get(row.entry); assert.ok(entry,`Unknown handbook entry ${row.entry}`);
    assert.ok(['curated','theme','guide'].includes(row.kind));
    assert.equal(row.status,undefined,'Automatic recommendations must not claim evidence status.');
    if (row.kind === 'guide') {
      const rule=rules.find(item=>item.id === row.rule); assert.ok(rule);
      assert.equal(rule.entry,row.entry); assert.equal(rule.reason,row.reason);
      if (rule.id_prefix) assert.ok(node.id.startsWith(rule.id_prefix));
      assert.ok((node.sources ?? []).some(source=>rule.source_types.includes(source.type)
        && (!rule.source_contains || `${source.url ?? ''} ${source.doi ?? ''} ${source.citation ?? ''}`.includes(rule.source_contains))));
    }
    if (row.kind === 'theme') {
      assert.ok(Array.isArray(row.terms) && row.terms.length);
      for (const term of row.terms) {
        const source = term.source === '题名' ? node.title : term.source === '别名' ? (node.aliases ?? []).join(' ') : `${node.title} ${(node.aliases ?? []).join(' ')}`;
        assert.ok(normalize(source).includes(normalize(term.term)),`${nodeId}: missing source term ${term.term}`);
        const target = term.target === '题名' ? entry.title : term.target === '主题' ? entry.topic : entry.title;
        const targetTerm = ['题名','主题'].includes(term.target) ? term.term : term.target;
        assert.ok(normalize(target).includes(normalize(targetTerm)),`${row.entry}: missing target term ${targetTerm}`);
      }
      if (row.method === 'concept') {
        const rule=concepts.find(item=>item.id === row.rule); assert.ok(rule);
        assert.equal(rule.entry,row.entry);
      }
    }
    if (row.kind === 'curated') assert.ok(portal.bridges.some(bridge=>bridge.id === row.bridge_id && bridge.mythos.id === nodeId && bridge.physis.id === row.entry && bridge.rationale === row.reason));
  }
}
assert.equal(matchIndex.stats.matched_nodes,Object.keys(matchIndex.matches).length);
assert.equal(matchIndex.stats.theme_nodes,thematicNodes);
assert.equal(matchIndex.stats.guide_nodes,guideNodes);
assert.equal(matchIndex.stats.links,checkedLinks);
const examples = [
  ['case_mrs_h_co_haunting_1921','LIF-EMERG-0002','theme'],
  ['scot_a_egd_1611','HIS-6-0001','guide'],
  ['case_cn_zibuyu_v01_s002','HIS-6-0005','guide'],
];
for (const [id,entry,kind] of examples) {
  if (nodes.has(id) && entries.has(entry)) assert.ok((matchIndex.matches[id] ?? []).some(row=>row.entry === entry && row.kind === kind),`Expected ${kind} for ${id}`);
}
if (nodes.has('case_cn_beijing_palace_well_online_2022')) {
  assert.ok(!(matchIndex.matches.case_cn_beijing_palace_well_online_2022 ?? []).some(row=>row.entry === 'FOR-4-0037'), 'A shared location must not be treated as a phenol match.');
}
for (const [id,target,status] of [
  ['case_mrs_h_co_haunting_1921','mech_co_poisoning','confirmed'],
  ['case_salem_1692','mech_salem_ergotism','refuted'],
  ['case_old_hag_sleep_paralysis_1982','mech_sleep_paralysis','unverified'],
]) {
  if (nodes.has(id) && nodes.has(target)) assert.ok(graph.links.some(link=>link.source === id && link.target === target && link.type === 'EXPLAINED_BY' && link.status === status));
}
for (const bridge of portal.bridges) {
  const story = nodes.get(bridge.mythos.id), entry = entries.get(bridge.physis.id);
  assert.ok(story && entry,`Missing real node: ${bridge.id}`);
  assert.ok(bridge.rationale?.trim(),`Missing reading rationale: ${bridge.id}`);
  assert.ok((matchIndex.matches[story.id] ?? []).some(row => row.kind === 'curated'
    && row.bridge_id === bridge.id && row.entry === entry.id && row.reason === bridge.rationale),
  `Curated bridge missing from the bidirectional index: ${bridge.id}`);
  assert.equal(bridge.mythos.title,story.title);
  assert.deepEqual(bridge.mythos.spatial,story.spatial);
  assert.deepEqual(bridge.mythos.reading,story.reading);
  assert.equal(bridge.fiction,story.credibility_tier === 'F' || !!story.is_fictional_quarantine);
  assert.equal(bridge.physis.body,entry.body);
  assert.equal(bridge.physis.page,entry.page);
  if (bridge.related) {
    assert.ok(nodes.has(bridge.related.id));
    const edge = graph.links.find(link => (link.source === story.id && link.target === bridge.related.id)
      || (link.target === story.id && link.source === bridge.related.id));
    assert.equal(bridge.edge?.status ?? null,edge?.status ?? null);
    assert.equal(bridge.edge?.type ?? null,edge?.type ?? null);
  }
}
console.log(JSON.stringify({nodes:graph.nodes.length,links:graph.links.length,book_entries:book.entries.length,curated:portal.bridges.length,matches:matchIndex.stats,snapshot:graph.snapshot_id}));
