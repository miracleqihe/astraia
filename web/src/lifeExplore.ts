import type { LifeBook, LifeEntry } from './life';

export type ObservationNotes = Record<string, string>;
export const OBSERVATION_KEY = 'astraia-omnia-observations-v1';

/** Keep private annotations in this browser only. Invalid stored data is ignored. */
export function readObservations(): ObservationNotes {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(OBSERVATION_KEY) ?? '{}');
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).filter(([id, note]) =>
      /^[A-Z0-9-]+$/.test(id) && typeof note === 'string')) as ObservationNotes;
  } catch { return {}; }
}

type SegmenterConstructor = new (locale: string, options: { granularity: 'word' }) => {
  segment: (input: string) => Iterable<{ segment: string; isWordLike?: boolean }>;
};
const Segmenter = (Intl as unknown as { Segmenter?: SegmenterConstructor }).Segmenter;
const segmenter = Segmenter ? new Segmenter('zh', { granularity: 'word' }) : null;
const STOP = new Set(['什么', '如何', '怎样', '关系', '之间', '有关', '哪些', '为什么', '一个', '以及', '相关']);

/** Tokenize question-like input for search; this does not invent an answer or edges. */
export function lifeSearchTerms(query: string): string[] {
  const normalized = query.normalize('NFKC').toLocaleLowerCase().trim();
  if (!normalized) return [];
  const words = segmenter ? [...segmenter.segment(normalized)]
    .filter((part) => part.isWordLike).map((part) => part.segment)
    : normalized.match(/[a-z0-9-]+|[\u3400-\u9fff]{2,}/g) ?? [];
  return [...new Set(words.filter((word) => word.length > 1 && !STOP.has(word)))];
}

/** Short excerpt drawn from the handbook entry, not a generated synthesis. */
export function lifeSearchExcerpt(entry: LifeEntry, query: string): string {
  const text = entry.body.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/⟦anchor:[^⟧]+⟧/g, '')
    .replace(/`[^`]*`\{=typst\}/g, '').replace(/\$\$[\s\S]*?\$\$|\$[^$\n]*\$/g, '')
    .replace(/\\([\\`*_{}\[\]()#+.!>-])/g, '$1')
    .replace(/[#*_`|>]/g, '').replace(/\s+/g, ' ').trim();
  const lowered = text.toLocaleLowerCase();
  const term = lifeSearchTerms(query).find((word) => lowered.includes(word));
  const match = term ? lowered.indexOf(term) : 0;
  const start = Math.max(0, match - 36);
  return `${start ? '…' : ''}${text.slice(start, start + 115)}${start + 115 < text.length ? '…' : ''}`;
}

export function rankLifeResults(entries: LifeEntry[], book: LifeBook, query: string,
  cache: Map<string, string>): LifeEntry[] {
  const normalized = query.normalize('NFKC').toLocaleLowerCase().trim();
  if (!normalized) return entries;
  const words = lifeSearchTerms(normalized);
  const ranked: Array<{ entry: LifeEntry; score: number; index: number }> = [];
  entries.forEach((entry, index) => {
    let text = cache.get(entry.id);
    if (text === undefined) {
      const figures = (entry.figure_refs ?? []).map((name) => book.figures?.[name]?.text ?? '').join(' ');
      text = `${entry.title} ${entry.id} ${entry.topic} ${entry.body} ${figures}`.normalize('NFKC').toLocaleLowerCase();
      cache.set(entry.id, text);
    }
    const title = `${entry.title} ${entry.id} ${entry.topic}`.normalize('NFKC').toLocaleLowerCase();
    let score = title.includes(normalized) ? 100 : text.includes(normalized) ? 30 : 0;
    for (const word of words) if (text.includes(word)) score += title.includes(word) ? 8 : 1;
    if (score) ranked.push({ entry, score, index });
  });
  return ranked.sort((a, b) => b.score - a.score || a.index - b.index).map(({ entry }) => entry);
}
