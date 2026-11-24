import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), 'utf8'));
const [manifest, graph, handbook] = await Promise.all([
  read('../src/syzygy/bridges.json'), read('../public/data/graph_data.json'), read('../public/knowledge/data.json')
]);
const nodes = new Map(graph.nodes.map(node => [node.id, node]));
const entries = new Map(handbook.entries.map(entry => [entry.id, entry]));
const urbanBatch = manifest.filter(bridge => /^SYZ-\d+$/.test(bridge.id)
  && Number(bridge.id.slice(4)) >= 38 && Number(bridge.id.slice(4)) <= 73);

test('new urban reading paths retain real narratives, cited sources and geographic precision', () => {
  assert.equal(urbanBatch.length, 36);
  assert.equal(new Set(urbanBatch.map(bridge => bridge.id)).size, urbanBatch.length);
  assert.equal(new Set(urbanBatch.map(bridge => bridge.case)).size, urbanBatch.length);
  for (const bridge of urbanBatch) {
    const node = nodes.get(bridge.case), entry = entries.get(bridge.entry);
    assert.ok(node && entry, `${bridge.id}: missing graph or knowledge entry`);
    assert.notEqual(node.credibility_tier, 'F');
    assert.ok(node.reading?.paragraphs?.length >= 2, `${bridge.id}: missing readable narrative`);
    assert.ok(node.reading.source_numbers.some(index => /^https?:\/\//i.test(node.sources[index - 1]?.url ?? '')),
      `${bridge.id}: no cited source link`);
    assert.ok(Number.isFinite(node.spatial?.lat) && Math.abs(node.spatial.lat) <= 90);
    assert.ok(Number.isFinite(node.spatial?.lng) && Math.abs(node.spatial.lng) <= 180);
    assert.ok(node.spatial.location_name && node.spatial.precision, `${bridge.id}: missing location context`);
    assert.ok(entry.body?.trim() && bridge.rationale?.trim().length >= 15, `${bridge.id}: missing reading path`);
    assert.equal(bridge.related, null);
    assert.equal(bridge.status, undefined, `${bridge.id}: thematic reading is not an evidence claim`);
  }
});

test('new urban paths cover China, East Asia and Southeast Asia', () => {
  const counts = Object.create(null);
  for (const bridge of urbanBatch) {
    const region = bridge.case.split('_')[1];
    counts[region] = (counts[region] ?? 0) + 1;
  }
  assert.deepEqual({...counts}, {cn:15, jp:4, kr:3, sg:3, my:2, th:3, vn:2, id:3, ph:1});
});
