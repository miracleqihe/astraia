import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, basename, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { genreContract, sourceTier } from '../src/syzygy/narrativeMetadata.js';

// Keep all geometry, links and the first reading paragraph in the initial
// graph. Detailed citations and full text are loaded separately afterwards.
async function build(input, required = true) {
  let bytes;
  try { bytes = await readFile(input); } catch (error) {
    if (!required && error.code === 'ENOENT') return;
    throw error;
  }
  const graph = JSON.parse(bytes.toString('utf8'));
  if (graph.schema_version !== 1 || !graph.snapshot_id || !Array.isArray(graph.nodes) || !Array.isArray(graph.links)) {
    throw new Error(`Invalid graph snapshot: ${input}`);
  }
  const prefix = basename(input).replace(/_data\.json$/, '');
  if (!prefix || prefix === basename(input)) throw new Error(`Invalid graph filename: ${input}`);
  const ids = new Set();
  const details = { snapshot_id: graph.snapshot_id, nodes: graph.nodes.map((node) => {
    if (!node.id || ids.has(node.id)) throw new Error(`Invalid graph node: ${node.id}`);
    ids.add(node.id);
    const { id, sources, audit, markdown, source_path, reading } = node;
    return { id, sources, audit, markdown, source_path, ...(reading ? { reading } : {}) };
  }) };
  const detailedText = JSON.stringify(details) + '\n';
  const index = {
    schema_version: 1, snapshot_id: graph.snapshot_id,
    details_file: `${prefix}_details.json`,
    details_sha256: createHash('sha256').update(detailedText, 'utf8').digest('hex'),
    ...(graph.stats ? { stats: graph.stats } : {}), ...(graph.visibility ? { visibility: graph.visibility } : {}),
    nodes: graph.nodes.map((node) => {
      const { id, title, aliases, z_layer, z, genre, credibility_tier, is_fictional_quarantine, spatial, temporal, standards } = node;
      const reading = node.reading && { ...node.reading, paragraphs: node.reading.paragraphs.slice(0, 1),
        ...(node.reading.edition ? { edition: { text: '', source_number: node.reading.edition.source_number } } : {}) };
      return { id, title, aliases, z_layer, z, genre, genre_contract: genreContract(node), source_tier: sourceTier(node), credibility_tier, is_fictional_quarantine, spatial, temporal, standards,
        sources: [], markdown: '', source_path: '', audit: { reviewed_by_human: false, is_sample: false }, ...(reading ? { reading } : {}) };
    }),
    links: graph.links.map(({ source, target, type, status, note, is_fictional_quarantine, matched_codes }) =>
      ({ source, target, type, status, note, is_fictional_quarantine, matched_codes })),
  };
  for (const [path, content] of [[join(dirname(input), `${prefix}_details.json`), detailedText],
    [join(dirname(input), `${prefix}_index.json`), JSON.stringify(index) + '\n']]) {
    let previous = '';
    try { previous = await readFile(path, 'utf8'); } catch { /* First build. */ }
    if (previous !== content) await writeFile(path, content, 'utf8');
  }
  console.log(`Graph index ${prefix}: ${ids.size} nodes, ${graph.links.length} links`);
}
const dataDir = fileURLToPath(new URL('../public/data/', import.meta.url));
if (process.argv[2]) await build(resolve(process.argv[2]));
else await build(join(dataDir, 'graph_data.json'), false);
