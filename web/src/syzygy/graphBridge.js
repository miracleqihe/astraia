import { publicAssetUrl } from '../publicAssetUrl.js';
const normalize = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase();
const textCache = new WeakMap();

export function graphText(node) {
  let value = textCache.get(node);
  if (!value) {
    value = normalize([node.id, node.title, ...(node.aliases ?? []), node.spatial?.location_name,
      node.spatial?.culture_region, ...Object.values(node.standards ?? {}).flat(), ...(node.reading?.paragraphs ?? [])].join(' '));
    textCache.set(node, value);
  }
  return value;
}

export function matchesGraph(node, query) {
  const words = normalize(query).trim().split(/\s+/).filter(Boolean);
  return !words.length || words.every(word => graphText(node).includes(word));
}

export async function loadGraph(root, publicSite, expectedSnapshotId = null) {
  const names = publicSite ? ['graph_index.json', 'graph_data.json'] : ['graph_index.json', 'catalogue_data.json', 'graph_data.json'];
  for (const name of names) {
    const response = await fetch(publicAssetUrl(root, `data/${name}`), { cache: 'no-cache' });
    if (!response.ok || !response.headers.get('content-type')?.includes('json')) continue;
    const graph = await response.json();
    if (graph.schema_version !== 1 || !Array.isArray(graph.nodes) || !Array.isArray(graph.links)) throw new Error('图谱数据格式不匹配。');
    if (expectedSnapshotId && graph.snapshot_id !== expectedSnapshotId && name === 'graph_index.json') continue;
    return graph;
  }
  throw new Error('未找到图谱数据。');
}

export async function loadDetails(root, graph) {
  if (!graph.details_file) return new Map(graph.nodes.map(node => [node.id, node]));
  if (!/^(graph|catalogue)_details\.json$/.test(graph.details_file) || !/^[a-f0-9]{64}$/.test(graph.details_sha256 ?? '')) throw new Error('图谱正文索引无效。');
  const response = await fetch(`${publicAssetUrl(root, `data/${graph.details_file}`)}?v=${graph.details_sha256}`);
  if (!response.ok) throw new Error(`图谱正文读取失败 (${response.status})。`);
  const bytes = await response.arrayBuffer();
  if (globalThis.crypto?.subtle) {
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    const hash = [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join('');
    if (hash !== graph.details_sha256) throw new Error('图谱正文与索引版本不一致。');
  }
  const details = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  if (details.snapshot_id !== graph.snapshot_id || !Array.isArray(details.nodes) || details.nodes.length !== graph.nodes.length
    || details.nodes.some((node, index) => node.id !== graph.nodes[index].id)) throw new Error('图谱正文与索引不匹配。');
  return new Map(graph.nodes.map((node, index) => [node.id, { ...node, ...details.nodes[index] }]));
}

const segmenter = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter('zh', { granularity: 'word' }) : null;
const stop = new Set(['一位','一个','一名','故事','传说','当地','记录','研究','中国','日本','东南亚','有关','事件','报告','人们','地方','以及','这类','文化','现场','资料','比较']);
function tokens(text) {
  const normalized = normalize(text);
  const words = segmenter ? [...segmenter.segment(normalized)].filter(x => x.isWordLike).map(x => x.segment)
    : normalized.match(/[a-z0-9-]{3,}|[\u3400-\u9fff]{2,}/g) ?? [];
  return [...new Set(words.filter(word => word.length >= 2 && !stop.has(word)))];
}

/** Suggestions are lexical comparisons, never a claim that a causal edge exists. */
export function suggestBookEntries(node, entries, count = 4) {
  const terms = tokens(`${node.title} ${node.reading?.paragraphs?.[0] ?? ''}`).slice(0, 32);
  if (!terms.length) return [];
  return entries.map(entry => {
    const title = normalize(`${entry.title} ${entry.topic}`);
    const score = terms.reduce((sum, term) => sum + (title.includes(term) ? Math.min(term.length, 6) : 0), 0);
    return { entry, score };
  }).filter(row => row.score >= 3).sort((a,b) => b.score - a.score).slice(0,count).map(row => row.entry);
}
