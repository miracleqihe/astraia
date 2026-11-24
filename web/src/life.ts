export interface LifeEntry {
  id: string;
  title: string;
  topic: string;
  subject: string;
  volume: string;
  page: number;
  links: string[];
  figure_refs: string[];
  body: string;
}

export interface LifeSubject {
  id: string;
  title: string;
  volume: string;
  count: number;
}

export interface LifeBook {
  title: string;
  edition: string;
  source_sha256: string;
  data_sha256?: string;
  anchors: Record<string, string>;
  figures: Record<string, { text: string; links: string[] }>;
  subjects: LifeSubject[];
  entries: LifeEntry[];
}
