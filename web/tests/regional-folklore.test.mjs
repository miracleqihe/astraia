import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), 'utf8'));
const [manifest, graph, handbook] = await Promise.all([
  read('../src/syzygy/bridges.json'), read('../public/data/graph_data.json'), read('../public/knowledge/data.json')
]);
const nodes = new Map(graph.nodes.map(node => [node.id, node]));
const entries = new Map(handbook.entries.map(entry => [entry.id, entry]));
const regional = manifest.filter(bridge => /^SYZ-\d+$/.test(bridge.id)
  && Number(bridge.id.slice(4)) >= 74 && Number(bridge.id.slice(4)) <= 100);

test('regional bridges retain readable stories, source links, map context and honest relation types', () => {
  assert.equal(regional.length, 27);
  assert.equal(new Set(regional.map(bridge => bridge.case)).size, 27);
  for (const bridge of regional) {
    const node = nodes.get(bridge.case), entry = entries.get(bridge.entry);
    assert.ok(node && entry?.body?.trim(), `${bridge.id}: missing story or reading`);
    assert.ok(node.reading?.paragraphs?.length >= 2, `${bridge.id}: missing story summary`);
    assert.ok(node.reading.source_numbers.some(number => /^https?:\/\//.test(node.sources[number - 1]?.url ?? '')),
      `${bridge.id}: source link missing`);
    assert.ok(Number.isFinite(node.spatial?.lat) && Number.isFinite(node.spatial?.lng), `${bridge.id}: missing location`);
    assert.ok(node.spatial?.location_name && node.spatial?.precision, `${bridge.id}: missing location context`);
    assert.equal(bridge.relation, 'THEMATIC');
    assert.equal(bridge.related, null);
    assert.ok(bridge.rationale.length >= 15, `${bridge.id}: missing explanation of comparison`);
    assert.equal(node.audit.reviewed_by_human, false, `${bridge.id}: review must not be implied`);
  }
});

test('new records use coordinates within the intended country and distinguish reference points', () => {
  const boxes = {
    ba: [42.5, 45.3, 15.7, 19.7], rs: [42.2, 46.3, 18.8, 23.1],
    pl: [49, 55, 14, 25], br: [-34, 6, -74, -34], ve: [0, 13, -74, -59],
    ec: [-5.2, 1.6, -81.1, -75], py: [-28, -19, -63, -54], uy: [-35.2, -30, -59, -53],
    co: [-5, 13, -79, -66], pe: [-19, 0, -82, -68], cl: [-56, -17, -76, -66],
  };
  for (const bridge of regional.slice(0, 16)) {
    const node = nodes.get(bridge.case), country = bridge.case.split('_')[1];
    const [south, north, west, east] = boxes[country];
    assert.ok(node.spatial.lat >= south && node.spatial.lat <= north
      && node.spatial.lng >= west && node.spatial.lng <= east, `${bridge.id}: unexpected country coordinates`);
    assert.ok(node.reading.location_note, `${bridge.id}: missing coordinate precision note`);
    assert.deepEqual(node.standards.atu_types, []);
    assert.deepEqual(node.standards.ocm_codes, []);
  }
});
