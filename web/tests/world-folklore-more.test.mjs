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
  && Number(bridge.id.slice(4)) >= 159 && Number(bridge.id.slice(4)) <= 183);
const boxes = {
  cn:[18,54,73,135], jp:[24,46,122,147], kr:[33,39,125,130],
  id:[-11,6,95,142], my:[1,8,99,120], ph:[4,22,116,127],
  co:[-5,13,-79,-66], pe:[-19,0,-82,-68], br:[-34,6,-74,-34],
  pl:[49,55,14,25], rs:[42.2,46.3,18.8,23.1]
};

test('new world stories connect readable descriptions, sources, geographic context and knowledge', async () => {
  assert.equal(batch.length,25);
  assert.equal(new Set(batch.map(bridge => bridge.case)).size,25);
  for (const bridge of batch) {
    const node=nodes.get(bridge.case), entry=entries.get(bridge.entry);
    assert.ok(node && entry?.body?.trim(), `${bridge.id}: missing story or knowledge`);
    assert.ok(node.reading?.paragraphs?.length>=3 && node.reading.paragraphs.every(p=>p.trim().length>=30), `${bridge.id}: short reading`);
    assert.ok(node.reading.source_numbers.length && node.reading.source_numbers.every(i=>/^https?:\/\//.test(node.sources[i-1]?.url ?? '')), `${bridge.id}: missing source`);
    assert.ok(node.reading.location_note, `${bridge.id}: missing location note`);
    const [south,north,west,east]=boxes[node.id.split('_')[1]];
    assert.ok(node.spatial.lat>=south && node.spatial.lat<=north && node.spatial.lng>=west && node.spatial.lng<=east, `${bridge.id}: wrong country`);
    assert.equal(node.audit.reviewed_by_human,false);
    assert.deepEqual(node.standards.atu_types,[]);assert.deepEqual(node.standards.ocm_codes,[]);
    assert.equal(bridge.relation,'THEMATIC');assert.equal(bridge.related,null);
    const card=await readFile(new URL(`../../vault/01_cases/${node.id}.md`,import.meta.url),'utf8');
    assert.match(card,/reviewed_by_human: false/);
  }
});

test('comparisons preserve their thematic status and CC BY summaries credit their source', () => {
  const ids=new Set(batch.map(bridge=>bridge.case));
  const comparisons=graph.links.filter(edge=>ids.has(edge.source) && edge.type==='COMPARED_WITH');
  assert.equal(comparisons.length,15);
  assert.ok(comparisons.every(edge=>edge.status===null && /非已证实/.test(edge.note)));
  for(const id of ['case_cn_tw_miaoli_baguali_headless','case_cn_tw_puli_trouser_bamboo',
                    'case_cn_tw_puli_tree_experience','case_cn_tw_lieyu_skeleton_tofu']) {
    const source=nodes.get(id).sources[0];
    assert.match(source.locator,/改述/);assert.match(source.locator,/creativecommons\.org\/licenses\/by\/3\.0\/tw/);
  }
});
