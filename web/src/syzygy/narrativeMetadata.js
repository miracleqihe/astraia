// These are explicit values already present in the catalogue, not inferences from titles or sources.
const contracts = { myth:'MYTH', fabulate:'FABULATE', folktale:'FOLKTALE', memorate:'MEMORATE',
  historical_archive:'HISTORICAL', urban_legend:'URBAN_LEGEND', creepypasta_ostension:'OSTENSION' };
export const genreLabels = { MYTH:'神话', FABULATE:'地方传说', FOLKTALE:'民间故事', MEMORATE:'亲历叙述',
  HISTORICAL:'历史个案', URBAN_LEGEND:'都市传说', OSTENSION:'数字民俗与展演', OTHER:'其他 / 未分类' };
export function genreContract(node) {
  if (Object.hasOwn(genreLabels,node?.genre_contract)) return node.genre_contract;
  return contracts[node?.genre] ?? 'OTHER';
}
export function sourceTier(node) {
  return ['S','A','B','C'].includes(node?.credibility_tier) ? node.credibility_tier : null;
}

// F describes a fictional work rather than a missing S–C source assessment.
export function narrativeDisplay(node) {
  const fiction = node?.credibility_tier === 'F' || node?.is_fictional_quarantine;
  const contract = genreContract(node);
  const rank = fiction ? 'F 级虚构' : `来源等级 ${sourceTier(node) ?? '未记录'}`;
  const genre = fiction && contract === 'FABULATE' ? '虚构作品' : genreLabels[contract];
  return `${rank} · 体裁 ${genre}`;
}
