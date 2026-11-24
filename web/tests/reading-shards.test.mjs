import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import { test } from 'node:test';
import { createReadingShards } from '../src/syzygy/readingShards.js';
import { shardKey } from '../src/syzygy/shardKey.js';

const snapshot = 'a'.repeat(64), bookHash = 'b'.repeat(64);
const nodeId = 'case_cn_故事', entryId = 'LIF-TOPIC-0001';
const graph = { snapshot_id:snapshot, nodes:[{id:nodeId}] };
const book = { data_sha256:bookHash, entries:[{id:entryId}] };
const sha = bytes => createHash('sha256').update(bytes).digest('hex');

function fixture() {
  const files = new Map(), calls = [];
  function makeParts(kind, source, record) {
    return Array.from({length:64}, (_,bucket) => {
      const records = bucket === shardKey(record.id) ? [record] : [];
      const content = JSON.stringify({schema_version:1,kind,source,bucket,records}) + '\n';
      const hash = sha(content), file = `${kind}-${source.slice(0,12)}-${String(bucket).padStart(2,'0')}-${hash.slice(0,16)}.json`;
      files.set(file,content);
      return {file,sha256:hash,count:records.length};
    });
  }
  const manifest={schema_version:1,snapshot_id:snapshot,handbook_sha256:bookHash,buckets:64,
    graph:{count:1,parts:makeParts('graph',snapshot,{id:nodeId,reading:{paragraphs:['中文正文']}})},
    book:{count:1,parts:makeParts('book',bookHash,{id:entryId,body:'原书正文'})}};
  const manifestFile=`manifest-${snapshot.slice(0,12)}-${bookHash.slice(0,12)}.json`;
  files.set(manifestFile,JSON.stringify(manifest));
  const oldFetch=globalThis.fetch, oldCrypto=globalThis.crypto;
  Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
  globalThis.fetch=async url=>{
    const name=new URL(url,'http://localhost').pathname.split('/').pop();
    calls.push(name);
    return files.has(name) ? new Response(files.get(name),{status:200}) : new Response('',{status:404});
  };
  return {files,calls,manifest,manifestFile,restore(){globalThis.fetch=oldFetch;Object.defineProperty(globalThis,'crypto',{value:oldCrypto,configurable:true});}};
}

test('loads only selected UTF-8 buckets, deduplicates requests, and preserves full text', async()=>{
  const f=fixture();
  try {
    const reader=createReadingShards('/astraia/',graph,book);
    const [a,b,c]=await Promise.all([reader.graph(nodeId),reader.graph(nodeId),reader.book(entryId)]);
    assert.equal(a.reading.paragraphs[0],'中文正文'); assert.equal(b.id,nodeId); assert.equal(c.body,'原书正文');
    assert.equal(f.calls.length,3); assert.equal(f.calls.filter(x=>x.startsWith('graph-')).length,1);
    await assert.rejects(reader.graph('not-in-catalogue'),/不存在/);
  } finally {f.restore();}
});

test('rejects corrupt or mismatched shards and allows retry after a failed request', async()=>{
  const f=fixture();
  try {
    const reader=createReadingShards('/astraia/',graph,book), file=f.manifest.graph.parts[shardKey(nodeId)].file;
    const original=f.files.get(file); f.files.set(file,original.replace('中文正文','错误正文'));
    await assert.rejects(reader.graph(nodeId),/校验失败/);
    f.files.set(file,original); assert.equal((await reader.graph(nodeId)).reading.paragraphs[0],'中文正文');
    const stale={...f.manifest,snapshot_id:'c'.repeat(64)};
    f.files.set(f.manifestFile,JSON.stringify(stale));
    await assert.rejects(createReadingShards('/astraia/',graph,book).graph(nodeId),/版本不一致/);
  } finally {f.restore();}
});
