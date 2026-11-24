export type PortalDimension = 'umbra' | 'sidera' | 'omnia';

/** Preserve a selected pair only while the classic view still shows one of its endpoints. */
export function portalHref(dimension: PortalDimension, story?: string | null, entry?: string | null, showFiction?: boolean, tiers?: readonly string[]): string {
  const current = new URL(window.location.href);
  const query = new URLSearchParams({ dim: dimension, return: dimension === 'umbra' ? 'map' : dimension === 'sidera' ? 'graph' : 'life' });
  const pairStory = current.searchParams.get('bridge_story');
  const pairEntry = current.searchParams.get('bridge_entry');
  if (dimension === 'omnia') {
    const selectedEntry = entry || current.searchParams.get('entry');
    if (selectedEntry) query.set('entry', selectedEntry);
    if (selectedEntry && selectedEntry === pairEntry && pairStory) query.set('story', pairStory);
  } else {
    const selectedStory = story || current.searchParams.get('story');
    if (selectedStory) query.set('story', selectedStory);
    if (selectedStory && selectedStory === pairStory && pairEntry) query.set('entry', pairEntry);
  }
  if (showFiction ?? current.searchParams.get('fiction') === '1') query.set('fiction','1');
  if (tiers) query.set('tiers',tiers.join(','));
  else if (current.searchParams.has('tiers')) query.set('tiers',current.searchParams.get('tiers')!);
  return `${import.meta.env.BASE_URL}syzygy/?${query}`;
}
