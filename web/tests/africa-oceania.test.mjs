import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), 'utf8'));
const [manifest, graph, handbook] = await Promise.all([
  read('../src/syzygy/bridges.json'), read('../public/data/graph_data.json'), read('../public/knowledge/data.json')
]);
const nodes = new Map(graph.nodes.map(node => [node.id, node]));
const entries = new Map(handbook.entries.map(entry => [entry.id, entry]));
const bridges = manifest.filter(bridge => /^SYZ-\d+$/.test(bridge.id)
  && Number(bridge.id.slice(4)) >= 101 && Number(bridge.id.slice(4)) <= 132);

test('African and Oceanian bridges connect readable, sourced stories to existing knowledge', () => {
  assert.equal(bridges.length, 32);
  assert.equal(new Set(bridges.map(bridge => bridge.case)).size, 32);
  for (const bridge of bridges) {
    const node = nodes.get(bridge.case), entry = entries.get(bridge.entry);
    assert.ok(node && entry?.body?.trim(), `${bridge.id}: missing story or reading`);
    assert.ok(node.reading?.paragraphs?.length >= 2, `${bridge.id}: missing summary`);
    assert.ok(node.reading.source_numbers.some(number => /^https?:\/\//.test(node.sources[number - 1]?.url ?? '')),
      `${bridge.id}: source link missing`);
    assert.ok(Number.isFinite(node.spatial?.lat) && Number.isFinite(node.spatial?.lng), `${bridge.id}: missing location`);
    assert.equal(bridge.relation, 'THEMATIC');
    assert.ok(bridge.rationale.length >= 15, `${bridge.id}: missing reading context`);
    assert.equal(typeof node.audit.reviewed_by_human, 'boolean', `${bridge.id}: review status must be explicit`);
  }
  const cairo = bridges.find(bridge => bridge.case === 'case_egypt_jinn_sleep_paralysis');
  assert.equal(cairo.related, 'mech_sleep_paralysis');
  assert.ok(graph.links.some(link => link.source === cairo.case && link.target === cairo.related
    && link.status === 'unverified'), 'existing mechanism link must retain its unverified status');
  assert.ok(bridges.filter(bridge => bridge !== cairo).every(bridge => bridge.related === null));
});

test('new regional records use country-level coordinates and preserve the source-card status', async () => {
  const boxes = {
    tz: [-12, 0, 29, 41], ma: [20, 37, -18, -1], ng: [4, 14, 2, 15],
    gh: [4, 12, -4, 2], gm: [13, 14, -17, -13], ke: [-5, 6, 33, 42],
    za: [-35, -22, 16, 33], so: [-2, 13, 40, 52], et: [3, 15, 32, 48],
    au: [-45, -10, 112, 154], nz: [-48, -34, 165, 179], fj: [-21, -15, 175, 180],
    pg: [-12, 0, 140, 156],
  };
  for (const bridge of bridges.slice(0, 16)) {
    const node = nodes.get(bridge.case), country = bridge.case.split('_')[1];
    const [south, north, west, east] = boxes[country];
    assert.ok(node.spatial.lat >= south && node.spatial.lat <= north
      && node.spatial.lng >= west && node.spatial.lng <= east, `${bridge.id}: unexpected coordinates`);
    assert.ok(node.reading.location_note, `${bridge.id}: missing location context`);
    assert.deepEqual(node.standards.atu_types, []);
    assert.deepEqual(node.standards.ocm_codes, []);
    const card = await readFile(new URL(`../../vault/01_cases/${bridge.case}.md`, import.meta.url), 'utf8');
    const reviewed = card.match(/^  reviewed_by_human: (true|false)$/m);
    const tier = card.match(/^credibility_tier: ([SABCF])$/m);
    assert.ok(reviewed && tier, `${bridge.id}: missing source-card audit or tier`);
    assert.equal(node.audit.reviewed_by_human, reviewed[1] === 'true');
    assert.equal(node.credibility_tier, tier[1]);
  }
});
