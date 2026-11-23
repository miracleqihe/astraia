export type Layer = 1 | 2 | 3 | 4;
export type Tier = 'S' | 'A' | 'B' | 'C' | 'F';
export type ViewMode = 'geo' | 'graph';
export type Coordinates = [longitude: number, latitude: number];
export type EvidenceStatus = 'confirmed' | 'contested' | 'unverified' | 'refuted';

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
  };
  sources: Citation[];
  audit: { reviewed_by_human: boolean; is_sample: boolean; reviewer?: string | null;
    reviewed_at?: string | null; review_note?: string | null; public_release?: boolean;
    public_rights_note?: string | null };
  markdown: string;
  source_path: string;
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
  snapshot_id: string;
  nodes: GraphNode[];
  links: GraphLink[];
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
export function evidenceGroup(status: EvidenceStatus | null): EvidenceGroup {
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
  confirmed: { label: '已证实', color: '#89AD9D' },
  contested: { label: '有争议', color: '#C29D59' },
  unverified: { label: '待核实', color: '#C29D59' },
  refuted: { label: '已驳回', color: '#B84E4F' },
};

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
  return (nodes.length > 72 ? available.find((node) => node.id === 'case_cn_yongning_na_0004341')?.id : undefined)
    ?? available.find((node) => node.id === 'case_salem_1692')?.id
    ?? available.find((node) => coordinatesOf(node))?.id
    ?? available[0]?.id ?? null;
}

export function matchesQuery(node: GraphNode, query: string): boolean {
  const normalized = query.normalize('NFKC').trim().toLocaleLowerCase();
  if (!normalized) return true;
  const fields = [node.title, node.id, ...node.aliases, node.spatial?.location_name,
    node.temporal?.era_label, node.temporal?.year_start, node.temporal?.year_end,
    ...Object.values(node.standards).flat(), ...node.sources.flatMap(({ citation, locator, doi }) => [citation, locator, doi])];
  const text = fields.filter((field) => field != null).join(' ').normalize('NFKC').toLocaleLowerCase();
  return normalized.split(/\s+/).every((word) => text.includes(word));
}

export async function loadSnapshot(signal: AbortSignal): Promise<GraphSnapshot> {
  const candidates = import.meta.env.VITE_PUBLIC_DEMO === '1'
    ? ['graph_data.json'] : ['catalogue_data.json', 'graph_data.json'];
  let response: Response | null = null;
  for (const filename of candidates) {
    const current = await fetch(`${import.meta.env.BASE_URL}data/${filename}`, { signal, cache: 'no-store' });
    if (current.ok && current.headers.get('content-type')?.includes('json')) { response = current; break; }
    if (!current.ok && current.status !== 404) throw new Error('读取图谱快照失败。');
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
  return data as GraphSnapshot;
}
