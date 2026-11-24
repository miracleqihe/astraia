import { shardKey } from './shardKey.js';

const hashPattern = /^[a-f0-9]{64}$/;
const decode = bytes => JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));

/** Load only the full-text buckets requested by the reader; coalesce requests and verify their bytes. */
export function createReadingShards(root, graph, book) {
  if (!hashPattern.test(graph.snapshot_id ?? '') || !hashPattern.test(book.data_sha256 ?? '')) throw new Error('资料版本无效。');
  const graphIds = new Set(graph.nodes.map(node => node.id));
  const bookIds = new Set(book.entries.map(entry => entry.id));
  const manifestName = `manifest-${graph.snapshot_id.slice(0, 12)}-${book.data_sha256.slice(0, 12)}.json`;
  let manifestPromise;
  const cache = new Map();
  const loadManifest = () => {
    if (!manifestPromise) manifestPromise = (async () => {
      const response = await fetch(`${root}syzygy/shards/${manifestName}`, { cache:'no-cache' });
      if (!response.ok) throw new Error(`正文目录读取失败 (${response.status})`);
      const manifest = decode(await response.arrayBuffer());
      if (manifest.schema_version !== 1 || manifest.snapshot_id !== graph.snapshot_id || manifest.handbook_sha256 !== book.data_sha256
        || manifest.buckets !== 64 || manifest.graph?.count !== graphIds.size || manifest.book?.count !== bookIds.size)
        throw new Error('正文目录与图谱版本不一致，请刷新。');
      for (const kind of ['graph','book']) {
        if (!Array.isArray(manifest[kind].parts) || manifest[kind].parts.length !== manifest.buckets) throw new Error('正文分片目录无效。');
        for (const part of manifest[kind].parts) {
          if (!/^(graph|book)-[a-f0-9]{12}-\d{2}-[a-f0-9]{16}\.json$/.test(part.file ?? '')
            || !part.file.startsWith(`${kind}-`) || !hashPattern.test(part.sha256 ?? '') || !Number.isInteger(part.count) || part.count < 0)
            throw new Error('正文分片目录无效。');
        }
      }
      return manifest;
    })().catch(error => { manifestPromise = null; throw error; });
    return manifestPromise;
  };
  async function load(kind, id) {
    const allowedIds = kind === 'graph' ? graphIds : bookIds;
    if (!allowedIds.has(id)) throw new Error('正文条目不存在。');
    const manifest = await loadManifest(), bucket = shardKey(id, manifest.buckets);
    const key = `${kind}:${bucket}`;
    if (!cache.has(key)) {
      const pending = (async () => {
        const part = manifest[kind].parts[bucket];
        const response = await fetch(`${root}syzygy/shards/${part.file}`);
        if (!response.ok) throw new Error(`正文读取失败 (${response.status})`);
        const bytes = await response.arrayBuffer();
        if (!globalThis.crypto?.subtle) throw new Error('当前浏览器无法校验正文，请使用安全连接或更新浏览器。');
        const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2,'0')).join('');
        if (hash !== part.sha256) throw new Error('正文分片校验失败，请刷新。');
        const data = decode(bytes), source = kind === 'graph' ? graph.snapshot_id : book.data_sha256;
        if (data.schema_version !== 1 || data.kind !== kind || data.source !== source || data.bucket !== bucket
          || !Array.isArray(data.records) || data.records.length !== part.count) throw new Error('正文分片与目录不一致。');
        const records = new Map();
        for (const record of data.records) {
          if (!allowedIds.has(record.id) || records.has(record.id) || shardKey(record.id, manifest.buckets) !== bucket)
            throw new Error('正文分片含未知或重复条目。');
          records.set(record.id, record);
        }
        return records;
      })().catch(error => { cache.delete(key); throw error; });
      cache.set(key, pending);
    }
    const value = (await cache.get(key)).get(id);
    if (!value) throw new Error('正文条目不在预期分片中。');
    return value;
  }
  return { graph: id => load('graph', id), book: id => load('book', id) };
}
