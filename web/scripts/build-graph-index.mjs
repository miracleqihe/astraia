import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, basename, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const LAYER_DEFAULT_NODE_TYPE = {
  1: 'case',
  2: 'myth_corpus',
  3: 'motif_index',
  4: 'mechanism',
};

function compactSpatial(spatial) {
  if (!spatial || typeof spatial !== 'object') return undefined;
  const out = {
    precision: spatial.precision,
    location_name: spatial.location_name,
  };
  if (spatial.lat != null) out.lat = spatial.lat;
  if (spatial.lng != null) out.lng = spatial.lng;
  if (spatial.culture_region) out.culture_region = spatial.culture_region;
  return out;
}

function compactTemporal(temporal) {
  if (!temporal || typeof temporal !== 'object') return undefined;
  const out = { era_label: temporal.era_label };
  if (temporal.year_start != null) out.year_start = temporal.year_start;
  if (temporal.year_end != null) out.year_end = temporal.year_end;
  if (temporal.uncertainty_note) out.uncertainty_note = temporal.uncertainty_note;
  return out;
}

function compactStandards(standards) {
  if (!standards || typeof standards !== 'object') return undefined;
  const out = {};
  for (const key of ['atu_types', 'thompson_motifs', 'berezkin_codes', 'ocm_codes']) {
    if (Array.isArray(standards[key]) && standards[key].length > 0) {
      out[key] = standards[key];
    }
  }
  if (standards.macro_phylogeny) out.macro_phylogeny = standards.macro_phylogeny;
  return Object.keys(out).length > 0 ? out : undefined;
}

function compactReading(reading) {
  if (!reading || typeof reading !== 'object') return undefined;
  const out = { kind: reading.kind };
  const paragraphs = Array.isArray(reading.paragraphs)
    ? reading.paragraphs.slice(0, 1).filter((p) => typeof p === 'string' && p.length > 0)
    : [];
  if (paragraphs.length > 0) out.paragraphs = paragraphs;
  const sourceNumbers = Array.isArray(reading.source_numbers) ? reading.source_numbers : [];
  if (sourceNumbers.length > 0 && !(sourceNumbers.length === 1 && sourceNumbers[0] === 1)) {
    out.source_numbers = sourceNumbers;
  }
  if (reading.map_label) out.map_label = reading.map_label;
  if (reading.location_note) out.location_note = reading.location_note;
  if (reading.edition) out.edition = { source_number: reading.edition.source_number };
  return out;
}

function compactNode(node) {
  const out = {
    id: node.id,
    title: node.title,
    z_layer: node.z_layer,
    genre: node.genre,
    credibility_tier: node.credibility_tier,
  };
  if (node.node_type && node.node_type !== LAYER_DEFAULT_NODE_TYPE[node.z_layer]) {
    out.node_type = node.node_type;
  }
  if (Array.isArray(node.aliases) && node.aliases.length > 0) out.aliases = node.aliases;
  if (node.is_fictional_quarantine) out.is_fictional_quarantine = true;
  const spatial = compactSpatial(node.spatial);
  if (spatial) out.spatial = spatial;
  const temporal = compactTemporal(node.temporal);
  if (temporal) out.temporal = temporal;
  const standards = compactStandards(node.standards);
  if (standards) out.standards = standards;
  const reading = compactReading(node.reading);
  if (reading) out.reading = reading;
  return out;
}

function compactLinks(rawLinks) {
  const noteCounts = new Map();
  for (const link of rawLinks) {
    if (typeof link.note === 'string' && link.note.length > 0) {
      noteCounts.set(link.note, (noteCounts.get(link.note) ?? 0) + 1);
    }
  }
  const linkNotes = [...noteCounts.entries()]
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([note]) => note);
  const noteIndex = new Map(linkNotes.map((note, idx) => [note, idx]));

  const links = rawLinks.map(({ source, target, type, status, note, is_fictional_quarantine, matched_codes }) => {
    const out = { source, target, type };
    if (status != null) out.status = status;
    if (typeof note === 'string' && note.length > 0) {
      out.note = noteIndex.has(note) ? noteIndex.get(note) : note;
    }
    if (is_fictional_quarantine) out.is_fictional_quarantine = true;
    if (Array.isArray(matched_codes) && matched_codes.length > 0) {
      out.matched_codes = matched_codes;
    }
    return out;
  });

  return { linkNotes, links };
}

// Keep all geometry, links and the first reading paragraph in the initial
// graph while compacting trivial defaults losslessly for first-paint slimming.
// Detailed citations and full text are loaded separately afterwards.
export async function build(input, required = true) {
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
  const { linkNotes, links } = compactLinks(graph.links);
  const index = {
    schema_version: 1,
    compact_defaults: true,
    snapshot_id: graph.snapshot_id,
    details_file: `${prefix}_details.json`,
    details_sha256: createHash('sha256').update(detailedText, 'utf8').digest('hex'),
    ...(graph.stats ? { stats: graph.stats } : {}),
    ...(graph.visibility ? { visibility: graph.visibility } : {}),
    ...(linkNotes.length > 0 ? { link_notes: linkNotes } : {}),
    nodes: graph.nodes.map(compactNode),
    links,
  };
  for (const [path, content] of [[join(dirname(input), `${prefix}_details.json`), detailedText],
    [join(dirname(input), `${prefix}_index.json`), JSON.stringify(index) + '\n']]) {
    let previous = '';
    try { previous = await readFile(path, 'utf8'); } catch { /* First build. */ }
    if (previous !== content) await writeFile(path, content, 'utf8');
  }
  console.log(`Graph index ${prefix}: ${ids.size} nodes, ${graph.links.length} links (compact_defaults=true)`);
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const dataDir = fileURLToPath(new URL('../public/data/', import.meta.url));
  if (process.argv[2]) await build(resolve(process.argv[2]));
  else await build(join(dataDir, 'graph_data.json'), false);
}
