import { publicAssetUrl } from './publicAssetUrl.js';
export type Layer = 1 | 2 | 3 | 4;
export type Tier = 'S' | 'A' | 'B' | 'C' | 'F';
export type ViewMode = 'geo' | 'graph';
export type Coordinates = [longitude: number, latitude: number];
export type EvidenceStatus = 'confirmed' | 'contested' | 'unverified' | 'refuted';
export type ReadingKind = 'story' | 'legend' | 'report' | 'history' | 'research' | 'archive' | 'edition';

export interface ReadingNote {
  kind: ReadingKind;
  paragraphs: string[];
  source_numbers: number[];
  map_label?: string;
  location_note?: string;
  edition?: { text: string; source_number: number };
}

export interface Citation {
  citation: string;
  type: string;
  url: string | null;
  doi: string | null;
  locator?: string | null;
  local_path?: string | null;
}

export interface GraphNode {
  id: string;
  title: string;
  aliases: string[];
  node_type?: string;
  z_layer: Layer;
  z: number;
  genre: string;
  credibility_tier: Tier;
  is_fictional_quarantine: boolean;
  spatial: {
    lat: number | null;
    lng: number | null;
    location_name: string;
    precision: string;
    culture_region: string | null;
  } | null;
  temporal: {
    year_start: number | null;
    year_end: number | null;
    era_label: string;
    uncertainty_note: string | null;
  } | null;
  standards: {
    atu_types: string[];
    thompson_motifs: string[];
    berezkin_codes: string[];
    ocm_codes: string[];
    macro_phylogeny?: string | null;
  };
  sources: Citation[];
  audit: { reviewed_by_human: boolean; is_sample: boolean; reviewer?: string | null;
    reviewed_at?: string | null; review_note?: string | null; public_release?: boolean;
    public_rights_note?: string | null };
  markdown: string;
  source_path: string;
  reading?: ReadingNote;
  motifs?: string[];
  mechanisms?: unknown[];
  tags?: string[];
  relations?: unknown[];
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
  status: EvidenceStatus | null;
  note: string | null;
  is_fictional_quarantine: boolean;
  matched_codes: Array<{ system: string; code: string }>;
}

export interface GraphSnapshot {
  schema_version: 1;
  compact_defaults?: boolean;
  snapshot_id: string;
  nodes: GraphNode[];
  links: GraphLink[];
  details_file?: string;
  details_sha256?: string;
  link_notes?: string[];
}

export interface GraphDetails {
  snapshot_id: string;
  nodes: Array<Pick<GraphNode, 'id' | 'sources' | 'audit' | 'markdown' | 'source_path' | 'reading'>>;
}

export interface GraphIndex {
  nodes: GraphNode[];
  links: GraphLink[];
  byId: Map<string, GraphNode>;
  adjacency: Map<string, GraphLink[]>;
}

export interface ViewSelection {
  node: GraphNode | null;
  compareNode?: GraphNode | null;
  neighbors: ReadonlyMap<string, number>;
}

export type EvidenceGroup = 'confirmed' | 'unverified' | 'refuted';
export type CodeFocus = { system: string; code: string };
export function codeKey({ system, code }: CodeFocus): string { return `${system}:${code}`; }

export function dossierCodes(node: GraphNode) {
  return Object.entries(STANDARDS).flatMap(([system, label]) => {
    const values = node.standards[system as 'atu_types' | 'thompson_motifs' | 'berezkin_codes' | 'ocm_codes'];
    return Array.isArray(values) ? values.map((code) => ({ system, code, label: `${label} ${code}` })) : [];
  });
}

export function geographicCases(graph: GraphIndex, node: GraphNode | null): GraphNode[] {
  if (!node || node.z_layer === 1 || coordinatesOf(node)) return [];
  return [...relatedNodes(graph, node, 2).keys()].flatMap((id) => {
    const item = graph.byId.get(id);
    return item?.z_layer === 1 && coordinatesOf(item) ? [item] : [];
  });
}

export function evidenceGroup(status: EvidenceStatus | null): EvidenceGroup | null {
  if (!status) return null;
  return status === 'confirmed' ? 'confirmed' : status === 'refuted' ? 'refuted' : 'unverified';
}

export const LAYERS = {
  1: { name: '实景个案', short: '个案', color: '#C29D59' },
  2: { name: '神话与档案组', short: '文本', color: '#D5CCBA' },
  3: { name: '母题与索引', short: '母题', color: '#EFECE6' },
  4: { name: '机制与理论', short: '机制', color: '#A9B9BA' },
} satisfies Record<Layer, { name: string; short: string; color: string }>;

export const LAYER_ORDER = [1, 2, 3, 4] as const;

export const EVIDENCE: Record<EvidenceStatus, { label: string; color: string }> = {
  confirmed: { label: '已证实', color: '#38B2AC' },
  contested: { label: '有争议', color: '#C29D59' },
  unverified: { label: '待核实', color: '#C29D59' },
  refuted: { label: '已驳回', color: '#D9534F' },
};

export const READING_LABELS: Record<ReadingKind, string> = {
  story: '故事梗概', legend: '都市传说', report: '事件报道', history: '历史个案',
  research: '研究提要', archive: '档案提要', edition: '古籍正文',
};

export function readingLabel(node: GraphNode): string {
  if (!node.reading) return '资料';
  if (node.reading.kind === 'legend') {
    const explicit: Record<string, string> = {
      folktale: '民间故事', fabulate: '地方传说', myth: '神话故事',
      memorate: '亲历叙述', historical_archive: '历史个案',
    };
    if (explicit[node.genre]) return explicit[node.genre];
  }
  return READING_LABELS[node.reading.kind];
}

export function isModernReading(node: GraphNode): boolean {
  if (node.reading?.kind === 'report') return true;
  return node.reading?.kind === 'legend'
    && !['folktale', 'fabulate', 'myth', 'historical_archive'].includes(node.genre);
}

export function isEditorialReading(node: GraphNode): boolean {
  return !!node.reading?.paragraphs.length && node.reading.kind !== 'archive';
}

export const RELATIONS: Record<string, string> = {
  INSTANCE_OF: '归属',
  HAS_MOTIF: '共享母题',
  ATTESTS_MOTIF: '研究地区分布',
  TAGGED_OCM: 'OCM 标引',
  MIGRATED_TO: '跨区传播',
  EVOLVED_INTO: '历时演变',
  VARIANT_OF: '变体',
  COMPARED_WITH: '对照',
  EXPLAINED_BY: '机制解释',
  DEBUNKED_BY: '被驳斥',
  PART_OF_MACRO_TREND: '归入档案组',
  OSTENSION_OF: '现实模仿',
};

export const STANDARDS: Record<string, string> = {
  atu_types: 'ATU',
  thompson_motifs: '汤普森',
  berezkin_codes: '别列兹金',
  ocm_codes: 'OCM',
};

export function isFiction(node: GraphNode): boolean {
  return node.credibility_tier === 'F' || node.is_fictional_quarantine;
}

export function nodeColor(node: GraphNode): string {
  return isFiction(node) ? '#C5756D' : LAYERS[node.z_layer].color;
}

export function shortNodeLabel(title: string, limit = 18): string {
  const cleaned = title.replace(/\s*[（(][^（）()]*[）)]\s*$/u, '').trim();
  const chars = [...(cleaned || title)];
  return chars.length > limit ? `${chars.slice(0, limit).join('')}…` : chars.join('');
}

export function mapLabel(node: GraphNode): string {
  const place = node.reading?.map_label ?? node.spatial?.location_name;
  return shortNodeLabel(place?.split(/[：:]/u).at(-1)?.trim() || node.title, 16);
}

export function locationPrecision(node: GraphNode): string {
  switch (node.spatial?.precision) {
    case 'exact': return '地标';
    case 'city': return '城区参考点';
    case 'province': return '省域参考点';
    default: return '区域参考点';
  }
}

export function coordinatesOf(node: GraphNode): Coordinates | null {
  const lat = node.spatial?.lat;
  const lng = node.spatial?.lng;
  return typeof lat === 'number' && Math.abs(lat) <= 90
    && typeof lng === 'number' && Math.abs(lng) <= 180 ? [lng, lat] : null;
}

export function otherEnd(link: GraphLink, nodeId: string): string {
  return link.source === nodeId ? link.target : link.source;
}

export function linkKey(link: GraphLink): string {
  return `${link.source}/${link.target}/${link.type}`;
}

export function indexGraph(snapshot: Pick<GraphSnapshot, 'nodes' | 'links'>, hideFiction: boolean): GraphIndex {
  const nodes = hideFiction ? snapshot.nodes.filter((node) => !isFiction(node)) : snapshot.nodes;
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const adjacency = new Map(nodes.map((node) => [node.id, [] as GraphLink[]]));
  const links = snapshot.links.filter((link) => (
    byId.has(link.source) && byId.has(link.target) && !(hideFiction && link.is_fictional_quarantine)
  ));
  for (const link of links) {
    adjacency.get(link.source)?.push(link);
    adjacency.get(link.target)?.push(link);
  }
  return { nodes, links, byId, adjacency };
}

export function constellationIndex(graph: GraphIndex, selection: ViewSelection): GraphIndex {
  if (graph.nodes.length <= 72) return graph;
  const focus = graph.nodes.filter((node) => (selection.neighbors.get(node.id) ?? 3) <= 1)
    .sort((left, right) => (selection.neighbors.get(left.id) ?? 3) - (selection.neighbors.get(right.id) ?? 3));
  const picked = new Map(focus.slice(0, 600).map((node) => [node.id, node]));
  if (picked.size < 72) for (const layer of LAYER_ORDER) {
    for (const node of graph.nodes.filter((item) => item.z_layer === layer).slice(0, layer === 1 ? 42 : 10)) {
      if (picked.size >= 72) break;
      picked.set(node.id, node);
    }
  }
  const nodes = [...picked.values()];
  return indexGraph({ nodes, links: graph.links }, false);
}

export function relatedNodes(graph: GraphIndex, node: GraphNode | null, depthLimit = 2): Map<string, number> {
  const distances = new Map<string, number>();
  if (!node) return distances;
  distances.set(node.id, 0);
  let frontier = [node.id];
  for (let depth = 1; depth <= depthLimit; depth++) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const link of graph.adjacency.get(id) ?? []) {
        if (depth > 1 && link.type === 'ATTESTS_MOTIF') continue;
        const neighbor = otherEnd(link, id);
        if (distances.has(neighbor)) continue;
        distances.set(neighbor, depth);
        next.push(neighbor);
      }
    }
    frontier = next;
  }
  return distances;
}

export function firstSelection(nodes: readonly GraphNode[]): string | null {
  const available = nodes.filter((node) => !isFiction(node));
  return available.find((node) => node.id === 'case_cn_forbidden_city_palace_shadows')?.id
    ?? (nodes.length > 72 ? available.find((node) => node.id === 'case_cn_yongning_na_0004341')?.id : undefined)
    ?? available.find((node) => node.id === 'case_salem_1692')?.id
    ?? available.find((node) => coordinatesOf(node))?.id
    ?? available[0]?.id ?? null;
}

export function matchesQuery(node: GraphNode, query: string): boolean {
  const normalized = query.normalize('NFKC').trim().toLocaleLowerCase();
  if (!normalized) return true;
  const formattedCodes = Object.entries(STANDARDS).flatMap(([system, label]) => {
    const values = node.standards[system as keyof GraphNode['standards']];
    return Array.isArray(values) ? values.map((code) => `${label} ${code}`) : [];
  });
  const fields = [node.title, node.id, ...node.aliases, node.spatial?.location_name,
    node.reading?.map_label, node.reading ? readingLabel(node) : undefined,
    node.temporal?.era_label, node.temporal?.year_start, node.temporal?.year_end,
    ...Object.values(node.standards).flat(), ...formattedCodes,
    ...node.sources.flatMap(({ citation, locator, doi }) => [citation, locator, doi])];
  const text = fields.filter((field) => field != null).join(' ').normalize('NFKC').toLocaleLowerCase();
  return normalized.split(/\s+/).every((word) => text.includes(word));
}

const LAYER_DEFAULT_NODE_TYPE: Record<number, string> = {
  1: 'case',
  2: 'myth_corpus',
  3: 'motif_index',
  4: 'mechanism',
};

export function hydrateGraphIndex(snapshot: GraphSnapshot): GraphSnapshot {
  if (!snapshot || typeof snapshot !== 'object' || !Array.isArray(snapshot.nodes) || !Array.isArray(snapshot.links)) {
    return snapshot;
  }
  const linkNotes = Array.isArray(snapshot.link_notes) ? snapshot.link_notes : null;
  const nodes: GraphNode[] = snapshot.nodes.map((raw) => {
    const node = raw as unknown as Record<string, unknown>;
    const rawLayer = Number(node.z_layer) || 1;
    const zLayer = (rawLayer >= 1 && rawLayer <= 4 ? rawLayer : 1) as Layer;
    const rawSpatial = node.spatial as GraphNode['spatial'] | null | undefined;
    const rawTemporal = node.temporal as GraphNode['temporal'] | null | undefined;
    const rawStandards = (node.standards ?? {}) as Partial<GraphNode['standards']>;
    const rawAudit = (node.audit && typeof node.audit === 'object' ? node.audit : {}) as Partial<GraphNode['audit']>;
    const rawReading = node.reading as Partial<ReadingNote> | undefined;
    const reading: ReadingNote | undefined = rawReading && typeof rawReading === 'object' ? {
      ...rawReading,
      kind: (rawReading.kind ?? 'archive') as ReadingKind,
      paragraphs: Array.isArray(rawReading.paragraphs) ? rawReading.paragraphs : [],
      source_numbers: Array.isArray(rawReading.source_numbers) ? rawReading.source_numbers : [1],
      ...(rawReading.edition ? {
        edition: {
          text: typeof rawReading.edition.text === 'string' ? rawReading.edition.text : '',
          source_number: rawReading.edition.source_number,
        },
      } : {}),
    } : undefined;
    const tier = (node.credibility_tier ?? 'B') as Tier;
    return {
      ...(node as unknown as GraphNode),
      z_layer: zLayer,
      z: typeof node.z === 'number' ? node.z : (zLayer - 1) * 120,
      node_type: typeof node.node_type === 'string' ? node.node_type : (LAYER_DEFAULT_NODE_TYPE[zLayer] ?? 'case'),
      aliases: Array.isArray(node.aliases) ? (node.aliases as string[]) : [],
      credibility_tier: tier,
      is_fictional_quarantine: typeof node.is_fictional_quarantine === 'boolean'
        ? node.is_fictional_quarantine
        : tier === 'F',
      spatial: rawSpatial && typeof rawSpatial === 'object' ? {
        lat: rawSpatial.lat ?? null,
        lng: rawSpatial.lng ?? null,
        precision: rawSpatial.precision,
        location_name: rawSpatial.location_name,
        culture_region: rawSpatial.culture_region ?? null,
      } : null,
      temporal: rawTemporal && typeof rawTemporal === 'object' ? {
        year_start: rawTemporal.year_start ?? null,
        year_end: rawTemporal.year_end ?? null,
        era_label: rawTemporal.era_label,
        uncertainty_note: rawTemporal.uncertainty_note ?? null,
      } : null,
      standards: {
        atu_types: Array.isArray(rawStandards.atu_types) ? rawStandards.atu_types : [],
        thompson_motifs: Array.isArray(rawStandards.thompson_motifs) ? rawStandards.thompson_motifs : [],
        berezkin_codes: Array.isArray(rawStandards.berezkin_codes) ? rawStandards.berezkin_codes : [],
        ocm_codes: Array.isArray(rawStandards.ocm_codes) ? rawStandards.ocm_codes : [],
        macro_phylogeny: rawStandards.macro_phylogeny ?? null,
      },
      sources: Array.isArray(node.sources) ? (node.sources as Citation[]) : [],
      markdown: typeof node.markdown === 'string' ? node.markdown : '',
      source_path: typeof node.source_path === 'string' ? node.source_path : '',
      audit: {
        reviewed_by_human: false,
        is_sample: false,
        ...rawAudit,
      },
      motifs: Array.isArray(node.motifs) ? (node.motifs as string[]) : [],
      mechanisms: Array.isArray(node.mechanisms) ? (node.mechanisms as unknown[]) : [],
      tags: Array.isArray(node.tags) ? (node.tags as string[]) : [],
      relations: Array.isArray(node.relations) ? (node.relations as unknown[]) : [],
      ...(reading ? { reading } : {}),
    };
  });
  const links: GraphLink[] = snapshot.links.map((raw) => {
    const link = raw as unknown as Record<string, unknown>;
    return {
      ...(link as unknown as GraphLink),
      status: (link.status ?? null) as EvidenceStatus | null,
      note: typeof link.note === 'number' && linkNotes
        ? (linkNotes[link.note] ?? null)
        : ((link.note as string | null | undefined) ?? null),
      is_fictional_quarantine: Boolean(link.is_fictional_quarantine),
      matched_codes: Array.isArray(link.matched_codes)
        ? (link.matched_codes as Array<{ system: string; code: string }>)
        : [],
    };
  });
  const { link_notes: _linkNotes, ...rest } = snapshot;
  return { ...rest, nodes, links };
}

export async function loadSnapshot(signal: AbortSignal): Promise<GraphSnapshot> {
  const candidates = import.meta.env.VITE_PUBLIC_DEMO === '1'
    ? ['graph_index.json', 'graph_data.json'] : ['catalogue_data.json', 'graph_data.json'];
  let response: Response | null = null;
  for (let index = 0; index < candidates.length; index++) {
    const filename = candidates[index];
    let current: Response;
    try {
      current = await fetch(publicAssetUrl(import.meta.env.BASE_URL, `data/${filename}`), {
        signal, cache: import.meta.env.VITE_PUBLIC_DEMO === '1' ? 'no-cache' : 'no-store',
      });
    } catch (error) {
      // The optional local catalogue may not be available on a static host.
      // An interrupted fetch, however, must not start another request.
      if (signal.aborted || index === candidates.length - 1) throw error;
      continue;
    }
    if (current.ok && current.headers.get('content-type')?.includes('json')) { response = current; break; }
    if (!current.ok && current.status !== 404 && index === candidates.length - 1) {
      throw new Error('读取图谱快照失败。');
    }
  }
  if (!response || !response.headers.get('content-type')?.includes('json')) {
    throw new Error('找不到图谱快照。请先在项目根目录编译知识库。');
  }
  const data: unknown = await response.json();
  if (!data || typeof data !== 'object' || !('schema_version' in data)
    || data.schema_version !== 1 || !('nodes' in data) || !Array.isArray(data.nodes)
    || !('links' in data) || !Array.isArray(data.links)) {
    throw new Error('图谱快照格式不匹配。请用当前版本重新编译。');
  }
  return hydrateGraphIndex(data as GraphSnapshot);
}

export async function loadGraphDetails(snapshot: GraphSnapshot, signal: AbortSignal): Promise<GraphDetails> {
  if (!snapshot.details_file || !/^(graph|catalogue)_details\.json$/.test(snapshot.details_file)
    || !/^[a-f0-9]{64}$/.test(snapshot.details_sha256 ?? '')) throw new Error('图谱正文索引无效。');
  const response = await fetch(`${publicAssetUrl(import.meta.env.BASE_URL, `data/${snapshot.details_file}`)}?v=${snapshot.details_sha256}`, { signal, priority: 'low' });
  if (!response.ok) throw new Error(`读取正文失败 (${response.status})。`);
  const bytes = await response.arrayBuffer();
  if (globalThis.crypto?.subtle) {
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    const hash = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, '0')).join('');
    if (hash !== snapshot.details_sha256) throw new Error('图谱正文和索引版本不一致，请稍后重试。');
  }
  const data = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)) as GraphDetails;
  if (data.snapshot_id !== snapshot.snapshot_id || !Array.isArray(data.nodes) || data.nodes.length !== snapshot.nodes.length
    || data.nodes.some((node, index) => node.id !== snapshot.nodes[index].id)) throw new Error('图谱正文和索引不匹配，请稍后重试。');
  return data;
}
