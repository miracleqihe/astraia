import overviewPlaces from './overviewPlaces.json';

let overviewFonts: Promise<unknown> | undefined;
/** Load all locally supplied Chinese glyph shards before MapLibre lays out labels. */
export function loadOverviewMapFonts(): Promise<unknown> {
  const labels = overviewPlaces.map(([name]) => name).join('') + '0123456789';
  return overviewFonts ??= document.fonts.load('400 14px "Noto Sans SC"', labels).catch(() => {});
}
