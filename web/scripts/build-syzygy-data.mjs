import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, access } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = fileURLToPath(new URL('../', import.meta.url));
let defaultGraph = `${webRoot}/public/data/graph_data.json`;
if (process.env.VITE_PUBLIC_DEMO !== '1') {
  const catalogue = `${webRoot}/public/data/catalogue_data.json`;
  try { await access(catalogue); defaultGraph = catalogue; } catch { /* Public graph is the fallback. */ }
}
const graphPath = resolve(process.argv[2] ?? defaultGraph);
const output = resolve(process.argv[3] ?? `${webRoot}/public/syzygy/data.json`);
const bookBytes = await readFile(`${webRoot}/public/knowledge/data.json`);
const book = JSON.parse(bookBytes.toString('utf8'));
const graph = JSON.parse(await readFile(graphPath, 'utf8'));
const manifest = JSON.parse(await readFile(`${webRoot}/src/syzygy/bridges.json`, 'utf8'));
const readingPaths = JSON.parse(await readFile(`${webRoot}/src/syzygy/reading-paths.json`, 'utf8'));
if (graph.schema_version !== 1 || !Array.isArray(graph.nodes) || !Array.isArray(graph.links)
  || !Array.isArray(book.entries) || !Array.isArray(book.subjects)) throw new Error('Syzygy sources are invalid.');
const graphById = new Map(graph.nodes.map((node) => [node.id, node]));
const bookById = new Map(book.entries.map((entry) => [entry.id, entry]));
const readingIds = readingPaths.flatMap(path => path.entries);
if (readingPaths.length !== 4 || readingPaths.some(path => !path.title || path.entries.length !== 17)
  || new Set(readingIds).size !== 68 || readingIds.some(id => !bookById.has(id))) throw new Error('Invalid cross-disciplinary reading paths.');
if (new Set(manifest.map(item => item.id)).size !== manifest.length
  || new Set(manifest.map(item => `${item.case}\u0000${item.entry}`)).size !== manifest.length)
  throw new Error('Duplicate curated bridge or story/knowledge pair.');
const volumeIds = [...new Set(book.subjects.map((subject) => subject.volume))];
const safeSources = (node) => (node?.sources ?? []).map(({ citation, type, url, doi, locator }) =>
  ({ citation, type, url: /^https?:\/\//i.test(url ?? '') ? url : null, doi, locator }));
const compact = (node) => node && ({
  id: node.id, title: node.title, z_layer: node.z_layer, genre: node.genre, credibility_tier: node.credibility_tier,
  spatial: node.spatial, standards: node.standards, sources: safeSources(node),
  reading: node.reading ?? null, markdown: node.markdown ?? '',
});
const bridges = manifest.map((item) => {
  const story = graphById.get(item.case), related = item.related ? graphById.get(item.related) : null;
  const entry = bookById.get(item.entry);
  if (!story || !entry || (item.related && !related)) throw new Error(`Missing real node for ${item.id}.`);
  if (!story.reading?.paragraphs?.length) throw new Error(`Missing narrative for ${item.id}.`);
  if (!item.rationale?.trim() || !(story.sources ?? []).some(source => source.citation || source.url || source.doi)
    || !entry.body?.trim()) throw new Error(`Missing reading context or source for ${item.id}.`);
  if (!['all','trail1','trail2','trail3','trail4','trail5'].includes(item.trail)
    || !['sid_myth','sid_hag','sid_witch','sid_crypt','sid_liminal'].includes(item.cluster)
    || !['EMPIRICAL_EXPLAINS','MYTHIC_PROJECTION','SOCIAL_MIRROR','LIMINAL_SPAWNS','THEMATIC'].includes(item.relation))
    throw new Error(`Invalid curated bridge classification: ${item.id}.`);
  const edge = related && graph.links.find((link) => (link.source === story.id && link.target === related.id)
    || (link.target === story.id && link.source === related.id));
  const volumeIndex = volumeIds.indexOf(entry.volume);
  if (volumeIndex < 0 || !book.subjects.some((subject) => subject.id === entry.subject)) throw new Error(`Invalid subject for ${item.id}.`);
  return { id: item.id, trail: item.trail, shortLabel: item.label, rationale: item.rationale, relation: item.relation, sideraCluster: item.cluster,
    fiction: story.credibility_tier === 'F' || !!story.is_fictional_quarantine,
    mythos: compact(story), related: compact(related),
    edge: edge ? { type: edge.type, status: edge.status, note: edge.note } : null,
    physis: { ...entry, volId: `vol${volumeIndex + 1}`, discId: entry.subject.toLowerCase() } };
});
const data = { schema_version: 1, snapshot_id: graph.snapshot_id, handbook_sha256: createHash('sha256').update(bookBytes).digest('hex'), bridges };
await mkdir(dirname(output), { recursive: true });
const text = JSON.stringify(data) + '\n';
let previous = '';
try { previous = await readFile(output, 'utf8'); } catch { /* First build. */ }
if (previous !== text) await writeFile(output, text, 'utf8');
console.log(`Syzygy: ${bridges.length} source-linked bridges (${Buffer.byteLength(text)} bytes).`);
