/** Read only a matching index built from the exact graph and handbook. */
export async function loadPortalMatches(root, dataset, book, graph) {
  const hash = dataset.matches_sha256;
  if (!/^[a-f0-9]{64}$/.test(hash ?? '')) throw new Error('缺少自动对照索引版本。');
  const response = await fetch(`${root}syzygy/matches.json?v=${hash}`);
  if (!response.ok) throw new Error(`对照索引读取失败 (${response.status})。`);
  const bytes = await response.arrayBuffer();
  if (globalThis.crypto?.subtle) {
    const result = await crypto.subtle.digest('SHA-256',bytes);
    const actual = [...new Uint8Array(result)].map(value=>value.toString(16).padStart(2,'0')).join('');
    if (actual !== hash) throw new Error('对照索引校验失败，请刷新。');
  }
  const index = JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
  if (index.schema_version !== 1 || index.snapshot_id !== graph.snapshot_id || index.handbook_sha256 !== book.data_sha256
    || !index.matches || typeof index.matches !== 'object' || !index.stats) throw new Error('对照索引与图谱版本不一致。');
  const nodes = new Set(graph.nodes.map(node=>node.id)), entries = new Set(book.entries.map(entry=>entry.id));
  const reverse = new Map();
  for (const [nodeId,rows] of Object.entries(index.matches)) {
    if (!nodes.has(nodeId) || !Array.isArray(rows)) throw new Error('对照索引含未知节点。');
    const seen = new Set();
    for (const row of rows) {
      if (!entries.has(row.entry) || !['curated','theme','guide'].includes(row.kind)) throw new Error('对照索引含未知条目。');
      if (seen.has(row.entry) || row.status !== undefined) throw new Error('对照索引含重复或无效状态。');
      if ((row.kind === 'guide' && typeof row.reason !== 'string')
        || (row.kind === 'curated' && typeof row.bridge_id !== 'string')
        || (row.kind === 'theme' && (!Array.isArray(row.terms) || !row.terms.length || row.terms.some(term=>
          typeof term.term !== 'string' || typeof term.source !== 'string' || typeof term.target !== 'string')))) throw new Error('对照索引的匹配依据不完整。');
      seen.add(row.entry);
      if (!reverse.has(row.entry)) reverse.set(row.entry,[]);
      reverse.get(row.entry).push({nodeId, ...row});
    }
  }
  const priority={curated:0,theme:1,guide:2};
  for (const rows of reverse.values()) rows.sort((a,b)=>priority[a.kind]-priority[b.kind] || (b.score ?? 0)-(a.score ?? 0) || a.nodeId.localeCompare(b.nodeId));
  return { ...index, reverse };
}
