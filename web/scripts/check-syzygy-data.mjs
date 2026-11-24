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
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
assert.equal(graph.snapshot_id,index.snapshot_id);
assert.equal(graph.snapshot_id,details.snapshot_id);
assert.equal(graph.snapshot_id,portal.snapshot_id);
assert.equal(index.details_sha256,digest(detailBytes));
assert.equal(portal.handbook_sha256,digest(bookBytes));
assert.equal(graph.nodes.length,index.nodes.length);
assert.equal(graph.nodes.length,details.nodes.length);
assert.equal(new Set(graph.nodes.map(n=>n.id)).size,graph.nodes.length);
assert.equal(new Set(book.entries.map(n=>n.id)).size,book.entries.length);
assert.ok(index.nodes.every((n,i)=>n.id === details.nodes[i].id));
const nodes = new Map(graph.nodes.map(node=>[node.id,node]));
const entries = new Map(book.entries.map(entry=>[entry.id,entry]));
for (const bridge of portal.bridges) {
  const story = nodes.get(bridge.mythos.id), entry = entries.get(bridge.physis.id);
  assert.ok(story && entry,`Missing real node: ${bridge.id}`);
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
console.log(JSON.stringify({nodes:graph.nodes.length,links:graph.links.length,book_entries:book.entries.length,curated:portal.bridges.length,snapshot:graph.snapshot_id}));
