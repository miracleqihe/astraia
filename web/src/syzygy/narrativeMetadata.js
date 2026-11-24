// These are explicit values already present in the catalogue, not inferences from titles or sources.
const contracts = { myth:'MYTH', fabulate:'FABULATE', memorate:'MEMORATE', urban_legend:'URBAN_LEGEND', creepypasta_ostension:'OSTENSION' };
export const genreLabels = { MYTH:'神话', FABULATE:'地方传说', MEMORATE:'亲历叙述', URBAN_LEGEND:'都市传说', OSTENSION:'数字民俗与展演', OTHER:'其他 / 未分类' };
export function genreContract(node) {
  if (Object.hasOwn(genreLabels,node?.genre_contract)) return node.genre_contract;
  return contracts[node?.genre] ?? 'OTHER';
}
export function sourceTier(node) {
  return ['S','A','B','C'].includes(node?.credibility_tier) ? node.credibility_tier : null;
}
