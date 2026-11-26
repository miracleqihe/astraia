import { isModernReading, type GraphNode } from './graph';

export const REGIONS = [
  { id: 'china', label: '中国及港澳台', description: '地方志、民俗与都市异闻' },
  { id: 'east-asia', label: '东亚其他地区', description: '日本、朝鲜半岛与蒙古等' },
  { id: 'southeast-asia', label: '东南亚', description: '群岛与大陆地区的传说' },
  { id: 'south-asia', label: '南亚', description: '印度次大陆、喜马拉雅南麓与斯里兰卡' },
  { id: 'middle-east', label: '中东与西亚', description: '两河流域、黎凡特、伊朗高原与阿拉伯半岛' },
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
  if (/china|chinese|taiwan|hong kong|macau|tibet|xinjiang|dunhuang|yunnan|sichuan|guangdong|fujian|zhejiang|jiangsu|shandong|henan|hebei|hunan|hubei|shaanxi|shanxi|gansu|qinghai|inner mongolia|\bqinan\b|中国|中华|台湾|香港|澳门|西藏|新疆|敦煌|云南|四川|广东|福建|浙江|江苏|山东|河南|河北|湖南|湖北|陕西|山西|甘肃|青海|内蒙古|秦安/i.test(text)) return 'china';
  if (/east asia|japan|japanese|korea|korean|mongolia|ryukyu|okinawa|ainu|manchu|东亚|日本|韩国|朝鲜|蒙古|琉球|冲绳|阿伊努|满洲/i.test(text)) return 'east-asia';
  if (/south asia|\bindia\b|\bindian\b|pakistan|bangladesh|sri lanka|nepal|bhutan|vedic|hindu|南亚|印度|巴基斯坦|孟加拉|斯里兰卡|尼泊尔|不丹|吠陀/i.test(text)) return 'south-asia';
  if (/middle east|west asia|mesopotamia|anatolia|levant|arabia|persia|\biran(?:ian)?\b|\biraq|syria|lebanon|israel|palestine|jordan|\bturkey\b|turkish|yemen|\boman\b|saudi|\buae\b|babylon|sumer|akkad|hittite|zoroastrian|中东|(?:^|[^\u4e00-\u9fff]|[与及和])西亚|美索不达米亚|两河|苏美尔|巴比伦|阿卡德|赫梯|(?:^|[^\u4e00-\u9fff]|[古与及和])波斯(?![尼亚特])|伊朗|伊拉克|叙利亚|黎巴嫩|以色列|巴勒斯坦|约旦|土耳其|安纳托利亚|阿拉伯|也门/i.test(text)) return 'middle-east';
  if (/europe|scotland|scottish|ireland|irish|england|britain|united kingdom|germany|france|poland|polish|serbia|serbian|bosnia|greek|greece|roman|italy|italian|norse|nordic|iceland|icelandic|finnish|finland|baltic|slavic|russia|russian|ukraine|ukrainian|czech|hungary|hungarian|romania|romanian|spain|spanish|portugal|portuguese|celtic|welsh|wales|sweden|swedish|norway|norwegian|北欧|挪威|冰岛|(?:^|[^纽])芬兰|波罗的海|斯拉夫|俄罗斯|乌克兰|捷克|匈牙利|罗马尼亚|罗马|希腊|西班牙(?!港)|葡萄牙|凯尔特|(?<!新南)威尔士|瑞典|意大利|欧洲|苏格兰|爱尔兰|英格兰|英国|德国|法国|波兰|塞尔维亚|波黑|波斯尼亚/i.test(text)) return 'europe';
  if (/south america|latin america|argentina|bolivia|brazil|chile|colombia|ecuador|paraguay|peru|uruguay|venezuela|andes|andean|amazon|inca|mapuche|patagonia|南美|阿根廷|玻利维亚|巴西|智利|哥伦比亚(?!省)|厄瓜多尔|巴拉圭|秘鲁|乌拉圭|委内瑞拉|安第斯|亚马孙|亚马逊|印加|马普切|巴塔哥尼亚/i.test(text)) return 'south-america';
  if (/oceania|australia|new zealand|polynesia|melanesia|micronesia|\b(?:maori|hawai[ʻ']?i|hawaiian|fiji|fijian|samoa|samoan|tonga|tongan|tahiti|tahitian|papua|papuan)\b|大洋洲|澳大利亚|新西兰|波利尼西亚|美拉尼西亚|密克罗尼西亚|毛利|夏威夷|斐济|萨摩亚|汤加|塔希提|大溪地|巴布亚/i.test(text)) return 'oceania';
  if (/north america|central america|caribbean|canada|united states|\busa\b|mexico|maya|mayan|aztec|navajo|inuit|appalachia|appalachian|new england|quebec|北美|中美洲|加勒比|加拿大|美国|墨西哥|玛雅|阿兹特克|纳瓦霍|因纽特|阿巴拉契亚|新英格兰|魁北克/i.test(text)) return 'north-america';
  if (/africa|egypt|nigeria|kenya|south africa|yoruba|west africa|east africa|ethiopia|\bmali\b|ghana|morocco|congo|zulu|maasai|非洲|埃及|尼日利亚|肯尼亚|南非|约鲁巴|西非|东非|埃塞俄比亚|马里|加纳|摩洛哥|刚果|祖鲁|马赛/i.test(text)) return 'africa';
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
