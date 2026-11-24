import { createHash } from 'node:crypto';
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = fileURLToPath(new URL('../', import.meta.url));
let defaultGraph = `${webRoot}/public/data/graph_data.json`;
if (process.env.VITE_PUBLIC_DEMO !== '1') {
  const local = `${webRoot}/public/data/catalogue_data.json`;
  try { await access(local); defaultGraph = local; } catch { /* Use public graph. */ }
}
const graphPath = resolve(process.argv[2] ?? defaultGraph);
const output = resolve(process.argv[3] ?? `${webRoot}/public/syzygy/matches.json`);
const metadataPath = resolve(process.argv[4] ?? `${webRoot}/public/syzygy/data.json`);
const bookBytes = await readFile(`${webRoot}/public/knowledge/data.json`);
const bookHash = createHash('sha256').update(bookBytes).digest('hex');
const rulesBytes = await readFile(`${webRoot}/src/syzygy/matching-rules.json`);
const rules = JSON.parse(rulesBytes.toString('utf8'));
const conceptsBytes = await readFile(`${webRoot}/src/syzygy/matching-concepts.json`);
const concepts = JSON.parse(conceptsBytes.toString('utf8'));
const curatedBytes = await readFile(`${webRoot}/src/syzygy/bridges.json`);
const algorithmHash = createHash('sha256').update(await readFile(fileURLToPath(import.meta.url))).update(rulesBytes).update(conceptsBytes).update(curatedBytes).digest('hex');
const graph = JSON.parse(await readFile(graphPath, 'utf8'));
const book = JSON.parse(bookBytes.toString('utf8'));
const curated = JSON.parse(curatedBytes.toString('utf8'));
if (graph.schema_version !== 1 || !Array.isArray(graph.nodes) || !Array.isArray(graph.links) || !Array.isArray(book.entries)) throw new Error('Invalid matching sources.');
const bookById = new Map(book.entries.map(entry => [entry.id,entry]));
for (const rule of rules) if (!bookById.has(rule.entry)) throw new Error(`Unknown rule entry: ${rule.id}`);
for (const rule of concepts) if (!bookById.has(rule.entry) || !bookById.get(rule.entry).title.includes(rule.target)) throw new Error(`Invalid concept target: ${rule.id}`);

const digest = bytes => createHash('sha256').update(bytes).digest('hex');
async function updateMetadata(bytes) {
  const original = await readFile(metadataPath, 'utf8');
  const metadata = JSON.parse(original);
  if (metadata.snapshot_id !== graph.snapshot_id || metadata.handbook_sha256 !== bookHash) throw new Error('Portal index and Syzygy data do not share a snapshot.');
  metadata.matches_sha256 = digest(bytes);
  const next = JSON.stringify(metadata) + '\n';
  if (next !== original) await writeFile(metadataPath, next, 'utf8');
}
try {
  const previousBytes = await readFile(output);
  const previous = JSON.parse(previousBytes.toString('utf8'));
  if (previous.snapshot_id === graph.snapshot_id && previous.handbook_sha256 === bookHash && previous.algorithm_sha256 === algorithmHash) {
    await updateMetadata(previousBytes);
    console.log(`Portal matches cached: ${previous.stats.theme_nodes} thematic, ${previous.stats.guide_nodes} guided nodes.`);
    process.exit(0);
  }
} catch (error) {
  if (error.code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error;
}

const segmenter = new Intl.Segmenter('zh', { granularity:'word' });
const stop = new Set(`一个 一位 一名 一些 这些 这种 那些 那种 以及 或者 相关 具体 记录 研究 资料 文献 记载 可能 可以 需要 没有 其中 这是 通过 作为 根据 比较 使用 进行 认为 指出 描述 发现 存在 当时 之后 之间 一般 包括 例如 同时 不同 共同 版本 记录者 讲述 故事 传说 地方 当地 中国 日本 韩国 泰国 越南 老挝 美国 英国 苏格兰 加拿大 民俗 民间 文化 传统 社会 历史 人物 社区 学者 信息 时间 场景 材料 来源 一种 两种 自己 一家 人们 原文 档案 网站 目录 图谱 主题 个案 行为 结果 过程 方法 原始 解释 叙事 叙述 名录 项目 新增 国家 两者 如何 声音 响声 声响 房间 室内 住宅 这个 那个 一半 一一 一条 有人 地点 网络 数据 分析 参考 同题 文化区 馆藏 民间故事 事件 白色 反复 起源 之一 之二 类型 转录 世界 空间 原因 办公 跟进 古老 日文 信仰 the and for with from that this their there have about between which into its when were been those their more after before where would another used here also only some such under many other people person life what task white old story stories folklore myth legends archive archival database study research chapter records document edition historical history narrative tradition cultural social based example original details index material materials version unknown`.split(/\s+/));
const normalize = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase().replace(/https?:\/\/\S+/g,' ');
// Single-word matches are restricted to concrete, distinctive topics. A
// similar-sounding name, location, or generic narrative word is insufficient.
const safeSingletons = new Set(['一氧化碳','火山','海啸','地震','洪水','雷电','台风','毒蛇','鳄鱼','麦角','次声','甲烷','日食','月食','电梯','祖先','口述史','毛发','遗骨','溺水','睡眠瘫痪']);
function terms(value, limit = 220) {
  const out = new Set();
  const text = normalize(value).slice(0, 2200);
  for (const part of segmenter.segment(text)) {
    const token = part.segment;
    if (!part.isWordLike || token.length < 2 || token.length > 20 || stop.has(token) || /^\d+$/.test(token) || /^[a-z]{1,3}$/.test(token) || !/[\p{L}]/u.test(token)) continue;
    out.add(token);
    if (out.size >= limit) break;
  }
  return out;
}
const postings = new Map();
book.entries.forEach((entry,index) => {
  const fields = new Map();
  const add = (text, weight, label) => terms(text).forEach(token => {
    const existing = fields.get(token);
    if (!existing || existing.weight < weight) fields.set(token,{weight,label});
  });
  add(entry.title, 4, '题名'); add(entry.topic, 2, '主题'); add(entry.body, 1, '正文');
  for (const [token, field] of fields) {
    let list = postings.get(token); if (!list) postings.set(token,list=[]);
    list.push({ index, ...field });
  }
});
const idf = token => Math.log((book.entries.length + 1) / ((postings.get(token)?.length ?? 0) + 1)) + 1;
const curatedByNode = new Map();
for (const bridge of curated) {
  if (!curatedByNode.has(bridge.case)) curatedByNode.set(bridge.case,[]);
  curatedByNode.get(bridge.case).push(bridge);
}

function sourceMatches(rule, node) {
  if (rule.id_prefix && !node.id.startsWith(rule.id_prefix)) return false;
  return (node.sources ?? []).some(source => rule.source_types.includes(source.type)
    && (!rule.source_contains || `${source.url ?? ''} ${source.doi ?? ''} ${source.citation ?? ''}`.includes(rule.source_contains)));
}
function conceptWord(rule,node) {
  const fields=[['题名或别名',`${node.title ?? ''} ${(node.aliases ?? []).join(' ')}`]];
  if (rule.include_reading && node.z_layer === 1) fields.push(['正文',(node.reading?.paragraphs ?? []).join(' ')]);
  for (const [source,text] of fields) {
    const value=normalize(text);
    for (const word of rule.words) {
      if (source === '正文' && (rule.title_only_words ?? []).includes(word)) continue;
      const target=normalize(word);
      if (/^[a-z ]+$/.test(target)) {
        for (let index=value.indexOf(target); index >= 0; index=value.indexOf(target,index+target.length)) {
          if (!/[a-z]/.test(value[index-1] ?? '') && !/[a-z]/.test(value[index+target.length] ?? '')) return {word,source};
        }
      } else if (value.includes(target)) return {word,source};
    }
  }
  return null;
}
function distinctTerms(hits) {
  const chosen=[];
  for (const hit of hits.sort((a,b)=>b.value-a.value || b.term.length-a.term.length || a.term.localeCompare(b.term))) {
    if (chosen.some(other => other.term.includes(hit.term) || hit.term.includes(other.term))) continue;
    chosen.push(hit); if (chosen.length === 4) break;
  }
  return chosen;
}
function matchNode(node) {
  const query = new Map();
  const add = (value,weight,field) => terms(value).forEach(term => {
    const prior=query.get(term); if (!prior || prior.weight < weight) query.set(term,{weight,field});
  });
  const geographical = terms(`${node.spatial?.location_name ?? ''} ${node.spatial?.culture_region ?? ''}`);
  const focusTitle = String(node.title ?? '').split(/[｜|·]/).map(part=>part.trim()).filter(Boolean).at(-1) ?? node.title;
  add(focusTitle,4,'题名');
  for (const alias of (node.aliases ?? []).slice(0,8)) add(alias,3,'别名');
  add((node.reading?.paragraphs ?? []).slice(0,3).join(' '),1,'正文');
  add(node.reading?.edition?.text,1,'原文');
  add(node.markdown,1,'正文');
  for (const term of geographical) query.delete(term);
  const candidates=new Map();
  for (const [term,q] of query) {
    const list=postings.get(term); if (!list || list.length > 380) continue;
    const rarity=idf(term);
    for (const post of list) {
      let item=candidates.get(post.index);
      if (!item) candidates.set(post.index,item={score:0,hits:[]});
      const value=rarity*q.weight*post.weight;
      item.score+=value; item.hits.push({term,source:q.field,target:post.label,value,rarity});
    }
  }
  const thematic=[];
  for (const [index,item] of candidates) {
    const core = item.hits.filter(hit => (hit.source === '题名' || hit.source === '别名') && (hit.target === '题名' || hit.target === '主题'));
    const coreHits=distinctTerms(core);
    const directTitle=coreHits.some(hit => hit.target === '题名' && hit.rarity >= 3.2
      && (safeSingletons.has(hit.term) || (/\p{Script=Han}/u.test(hit.term) ? hit.term.length >= 4 : hit.term.length >= 8)));
    const multi=coreHits.filter(hit=>/\p{Script=Han}/u.test(hit.term) ? hit.term.length >= 3 : hit.term.length >= 6).length >= 2
      && coreHits.reduce((sum,hit)=>sum+hit.rarity,0) >= 6;
    if (!directTitle && !multi) continue;
    thematic.push({ entry:book.entries[index].id, kind:'theme', score:Math.round(coreHits.reduce((sum,hit)=>sum+hit.value,0)*100)/100,
      terms:coreHits.map(hit=>({term:hit.term,source:hit.source,target:hit.target})) });
  }
  thematic.sort((a,b)=>b.score-a.score || a.entry.localeCompare(b.entry));
  const output=[]; const seen=new Set();
  for (const bridge of curatedByNode.get(node.id) ?? []) {
    if (!bookById.has(bridge.entry)) throw new Error(`Unknown curated entry: ${bridge.id}`);
    output.push({ entry:bridge.entry, kind:'curated', bridge_id:bridge.id, reason:bridge.rationale }); seen.add(bridge.entry);
  }
  for (const rule of concepts) {
    const found=conceptWord(rule,node);
    if (!found || seen.has(rule.entry)) continue;
    output.push({entry:rule.entry,kind:'theme',method:'concept',rule:rule.id,
      terms:[{term:found.word,source:found.source,target:rule.target}]}); seen.add(rule.entry);
  }
  for (const item of thematic) {
    if (seen.has(item.entry)) continue;
    output.push(item); seen.add(item.entry); if (output.filter(row=>row.kind==='theme').length >= 5) break;
  }
  for (const rule of rules) {
    if (!seen.has(rule.entry) && sourceMatches(rule,node)) {
      output.push({entry:rule.entry,kind:'guide',rule:rule.id,reason:rule.reason}); seen.add(rule.entry);
    }
  }
  return output;
}

const matches=Object.create(null); let thematicNodes=0,guidedNodes=0,curatedNodes=0,links=0;
for (const node of graph.nodes) {
  const rows=matchNode(node);
  if (!rows.length) continue;
  matches[node.id]=rows; links+=rows.length;
  if (rows.some(row=>row.kind==='theme')) thematicNodes++;
  if (rows.some(row=>row.kind==='guide')) guidedNodes++;
  if (rows.some(row=>row.kind==='curated')) curatedNodes++;
}
const stats={nodes:graph.nodes.length,book_entries:book.entries.length,matched_nodes:Object.keys(matches).length,theme_nodes:thematicNodes,guide_nodes:guidedNodes,curated_nodes:curatedNodes,links};
const result={schema_version:1,snapshot_id:graph.snapshot_id,handbook_sha256:bookHash,algorithm:'local-concepts-lexical-and-source-guides-v1',algorithm_sha256:algorithmHash,stats,matches};
const bytes=Buffer.from(JSON.stringify(result)+'\n','utf8');
await mkdir(dirname(output),{recursive:true}); await writeFile(output,bytes);
await updateMetadata(bytes);
console.log(`Portal matches: ${stats.matched_nodes}/${stats.nodes} nodes; ${thematicNodes} thematic, ${guidedNodes} guided; ${links} links (${bytes.length} bytes).`);
