import type { LifeEntry } from './life';

export const LIFE_DIMENSIONS = [
  { id: 'all', title: '全部星域' }, { id: 'practice', title: '生存实操' },
  { id: 'nature', title: '自然机理' }, { id: 'engineering', title: '工程逻辑' },
  { id: 'society', title: '社会契约' }, { id: 'meaning', title: '精神哲思' },
] as const;
export type LifeDimension = typeof LIFE_DIMENSIONS[number]['id'];

/** Subject-based navigation categories, not inferred relations or claims. */
export function lifeDimension(entry: LifeEntry): Exclude<LifeDimension, 'all'> {
  if (['LIF', 'HEA'].includes(entry.subject)) return 'practice';
  if (['GEO', 'PHY', 'CHE', 'BIO'].includes(entry.subject)) return 'nature';
  if (['MAT', 'ARC', 'TEC', 'FOR', 'MTH'].includes(entry.subject)) return 'engineering';
  if (['ECO', 'SOC', 'LAW'].includes(entry.subject)) return 'society';
  return 'meaning';
}
