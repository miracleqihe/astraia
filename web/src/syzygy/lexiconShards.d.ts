export interface LexiconPrimarySource {
  citation: string;
  url: string | null;
  locator?: string;
}

export interface LexiconEntry {
  id: string;
  hub_id: string;
  term: string;
  aliases: string[];
  category: string;
  region: string;
  era: string;
  summary: string;
  primary_sources: LexiconPrimarySource[];
  secondary_ref?: string;
  case_id?: string;
  knowledge_id?: string;
  knowledge_note?: string;
}

export interface LexiconShardRef {
  file: string;
  sha256: string;
  count: number;
  categories?: string[];
  hub_ids?: string[];
}

export interface TaxonomyGroup {
  id: string;
  title: string;
  description: string;
  hub_ids: string[];
  featured_nodes: string[];
  lexicon_categories?: string[];
}

export interface TaxonomyDomain {
  id: string;
  order: number;
  name: string;
  english_name: string;
  subtitle: string;
  accent: string;
  sidera_id: string;
  disciplines: string[];
  summary: string;
  node_count: number;
  lexicon_count: number;
  lexicon_shard: LexiconShardRef | null;
  groups: TaxonomyGroup[];
}

export interface HubLexiconInfo {
  domain_id: string;
  domain_name: string;
  count: number;
  shard: LexiconShardRef | null;
}

export interface TaxonomyData {
  version: number;
  bibliography?: Array<{ citation?: string; title?: string; isbn?: string; note?: string } | string>;
  domains: TaxonomyDomain[];
  hub_to_domain?: Record<string, { domain_id: string; domain_name?: string; count?: number; shard?: LexiconShardRef | null }>;
  lexicon_manifest_sha256?: string;
}

export interface LoadedLexiconShard {
  domain_id: string;
  sha256: string;
  count: number;
  entries: LexiconEntry[];
}

export function clearLexiconCache(): void;
export function loadTaxonomy(root?: string): Promise<TaxonomyData | null>;
export function loadLexiconShard(
  root: string,
  taxonomyOrManifest: TaxonomyData | { domains: Record<string, LexiconShardRef> } | TaxonomyDomain | LexiconShardRef,
  domainId: string,
): Promise<LoadedLexiconShard>;
export function getHubLexiconInfo(taxonomy: TaxonomyData | null | undefined, nodeId: string): HubLexiconInfo | null;
export function filterLexiconEntries(
  entries: readonly LexiconEntry[],
  query?: string,
  category?: string,
): LexiconEntry[];
