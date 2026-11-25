import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), 'utf8'));
const [manifest, graph, handbook] = await Promise.all([
  read('../src/syzygy/bridges.json'), read('../public/data/graph_data.json'), read('../public/knowledge/data.json')
]);
const nodes = new Map(graph.nodes.map(node => [node.id, node]));
const entries = new Map(handbook.entries.map(entry => [entry.id, entry]));
const batch = manifest.filter(bridge => /^SYZ-\d+$/.test(bridge.id)
  && Number(bridge.id.slice(4)) >= 133 && Number(bridge.id.slice(4)) <= 158);

test('world folklore stories retain readable summaries, provenance, places and thematic knowledge', async () => {
  assert.equal(batch.length,26);
  assert.equal(new Set(batch.map(bridge => bridge.case)).size,26);
  for (const bridge of batch) {
    const node=nodes.get(bridge.case), entry=entries.get(bridge.entry);
    assert.ok(node && entry?.body?.trim(), `${bridge.id}: missing story or knowledge`);
    assert.ok(node.reading?.paragraphs?.length>=3 && node.reading.paragraphs.every(text=>text.trim().length>=30), `${bridge.id}: short or missing reading`);
    assert.ok(node.reading.source_numbers.length && node.reading.source_numbers.every(number=>/^https?:\/\//.test(node.sources[number-1]?.url ?? '')), `${bridge.id}: source missing`);
    assert.ok(Number.isFinite(node.spatial?.lat) && Number.isFinite(node.spatial?.lng) && node.reading.location_note, `${bridge.id}: location missing`);
    assert.deepEqual(node.standards.atu_types,[]);
    assert.deepEqual(node.standards.ocm_codes,[]);
    assert.equal(bridge.relation,'THEMATIC');assert.equal(bridge.related,null);
    const directory=node.is_fictional_quarantine ? '05_quarantine_fiction' : '01_cases';
    const card=await readFile(new URL(`../../vault/${directory}/${node.id}.md`,import.meta.url),'utf8');
    const status=card.match(/^  reviewed_by_human: (true|false)$/m), tier=card.match(/^credibility_tier: ([SABCF])$/m);
    assert.ok(status && tier, `${node.id}: source card status missing`);
    assert.equal(node.audit.reviewed_by_human,status[1]==='true');assert.equal(node.credibility_tier,tier[1]);
  }
});

test('fiction is quarantined and thematic comparisons do not assert causation', () => {
  const fiction=nodes.get('case_cn_shanghai_jingan_digital_archive_fiction');
  assert.equal(fiction.credibility_tier,'F');assert.equal(fiction.is_fictional_quarantine,true);
  assert.equal(fiction.genre,'creepypasta_ostension');assert.match(fiction.reading.location_note,/数字原生/);
  const ids=new Set(batch.map(bridge=>bridge.case));
  const comparisons=graph.links.filter(edge=>ids.has(edge.source) && edge.type==='COMPARED_WITH');
  assert.equal(comparisons.length,8);
  assert.ok(comparisons.every(edge=>edge.status===null && /非已证实/.test(edge.note)));
  assert.ok(comparisons.some(edge=>edge.source===fiction.id && edge.is_fictional_quarantine));
});
