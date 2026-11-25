import { isModernReading, type GraphNode } from './graph';

export const REGIONS = [
  { id: 'china', label: '中国及港澳台', description: '地方志、民俗与都市异闻' },
  { id: 'east-asia', label: '东亚其他地区', description: '日本、朝鲜半岛与蒙古等' },
  { id: 'southeast-asia', label: '东南亚', description: '群岛与大陆地区的传说' },
  { id: 'europe', label: '欧洲', description: '地方故事与历史档案' },
  { id: 'south-america', label: '南美洲', description: '安第斯、亚马孙与南方地区' },
  { id: 'north-america', label: '北美洲', description: '北美、中美及加勒比地区' },
  { id: 'africa', label: '非洲', description: '各地民间叙事与文化记忆' },
  { id: 'oceania', label: '大洋洲', description: '澳大利亚与太平洋群岛' },
  { id: 'other', label: '其他地区', description: '其余地区与跨地域资料' },
  { id: 'unspecified', label: '未注明地域', description: '母题、文本与未标地点的资料' },
] as const;
export type Region = typeof REGIONS[number]['id'] | 'all';

export const CONTENT_GROUPS = [
  { id: 'modern', label: '现代异闻', description: '都市传说与事件报道' },
  { id: 'stories', label: '民俗故事', description: '故事、神话与地方传说' },
  { id: 'archive', label: '历史与地方档案', description: '地方记载与历史个案' },
  { id: 'texts', label: '文献与研究', description: '原典、文本与研究资料' },
  { id: 'motifs', label: '母题与索引', description: '跨文化母题和分类条目' },
  { id: 'mechanisms', label: '机制与解释', description: '科学机制与解释路径' },
  { id: 'other', label: '其他个案', description: '尚未归入以上类型的资料' },
] as const;
export type ContentGroup = typeof CONTENT_GROUPS[number]['id'] | 'all';

/** Group by the existing geographic metadata, never by inferred coordinates. */
export function nodeRegion(node: GraphNode): Exclude<Region, 'all'> {
  const geo = node.spatial;
  const text = `${geo?.culture_region ?? ''} ${geo?.location_name ?? ''}`.trim();
  if (!text) return 'unspecified';
  if (/southeast asia|东南亚|indonesia|indonesian|laos|lao|cambodia|khmer|vietnam|philippines|filipino|thailand|thai|malaysia|singapore|myanmar|burma|brunei|timor|印尼|印度尼西亚|老挝|柬埔寨|越南|菲律宾|泰国|马来西亚|新加坡|缅甸|文莱|东帝汶/i.test(text)) return 'southeast-asia';
  if (/china|chinese|taiwan|hong kong|macau|tibet|中国|中华|台湾|香港|澳门|西藏/i.test(text)) return 'china';
  if (/east asia|japan|japanese|korea|korean|mongolia|东亚|日本|韩国|朝鲜|蒙古/i.test(text)) return 'east-asia';
  if (/europe|scotland|scottish|ireland|irish|england|britain|united kingdom|germany|france|poland|polish|serbia|serbian|bosnia|意大利|欧洲|苏格兰|爱尔兰|英格兰|英国|德国|法国|波兰|塞尔维亚|波黑|波斯尼亚/i.test(text)) return 'europe';
  if (/south america|latin america|argentina|bolivia|brazil|chile|colombia|ecuador|paraguay|peru|uruguay|venezuela|南美|阿根廷|玻利维亚|巴西|智利|哥伦比亚(?!省)|厄瓜多尔|巴拉圭|秘鲁|乌拉圭|委内瑞拉/i.test(text)) return 'south-america';
  if (/north america|central america|caribbean|canada|united states|usa|mexico|北美|中美洲|加勒比|加拿大|美国|墨西哥/i.test(text)) return 'north-america';
  if (/africa|egypt|nigeria|kenya|south africa|非洲|埃及|尼日利亚|肯尼亚|南非/i.test(text)) return 'africa';
  if (/oceania|australia|new zealand|polynesia|melanesia|micronesia|大洋洲|澳大利亚|新西兰|波利尼西亚|美拉尼西亚|密克罗尼西亚/i.test(text)) return 'oceania';
  return 'other';
}

/** Each node has one primary browsing category; the four graph layers remain unchanged. */
export function nodeContentGroup(node: GraphNode): Exclude<ContentGroup, 'all'> {
  if (node.z_layer === 3) return 'motifs';
  if (node.z_layer === 4) return 'mechanisms';
  if (isModernReading(node) || node.genre === 'urban_legend' || node.genre === 'creepypasta_ostension') return 'modern';
  if (node.z_layer === 2 || node.reading?.kind === 'research' || node.reading?.kind === 'edition') return 'texts';
  if (node.reading?.kind === 'story' || ['folktale', 'myth', 'fabulate'].includes(node.genre)) return 'stories';
  if (node.reading?.kind === 'archive' || node.reading?.kind === 'history' || node.genre === 'historical_archive') return 'archive';
  return 'other';
}
