export interface LifeEntry {
  id: string;
  title: string;
  topic: string;
  subject: string;
  volume: string;
  page: number;
  links: string[];
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
  subjects: LifeSubject[];
  entries: LifeEntry[];
}
