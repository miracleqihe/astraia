import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { createHash, webcrypto } from 'node:crypto';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { createReadingShards } from '../src/syzygy/readingShards.js';
import { shardKey } from '../src/syzygy/shardKey.js';

const snapshot = 'a'.repeat(64), bookHash = 'b'.repeat(64);
const nodeId = 'case_cn_故事', entryId = 'LIF-TOPIC-0001';
const graph = { snapshot_id:snapshot, nodes:[{id:nodeId}] };
const book = { data_sha256:bookHash, entries:[{id:entryId}] };
const sha = bytes => createHash('sha256').update(bytes).digest('hex');

function fixture(graphVersion=1) {
  const files = new Map(), calls = [];
  function makeParts(kind, source, record) {
    return Array.from({length:64}, (_,bucket) => {
      const records = bucket === shardKey(record.id) ? [record] : [];
      const content = JSON.stringify(kind === 'graph' && graphVersion === 2
        ? {schema_version:2,kind,bucket,records} : {schema_version:1,kind,source,bucket,records}) + '\n';
      const hash = sha(content), prefix = kind === 'graph' && graphVersion === 2 ? hash.slice(0,12) : source.slice(0,12);
      const suffix = kind === 'graph' && graphVersion === 2 ? hash.slice(12,28) : hash.slice(0,16);
      const file = `${kind}-${prefix}-${String(bucket).padStart(2,'0')}-${suffix}.json`;
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

test('loads content-addressed graph buckets and still verifies their bytes', async()=>{
  const f=fixture(2);
  try {
    const reader=createReadingShards('/astraia/',graph,book), file=f.manifest.graph.parts[shardKey(nodeId)].file;
    const original=f.files.get(file); f.files.set(file,original.replace('中文正文','错误正文'));
    await assert.rejects(reader.graph(nodeId),/校验失败/);
    f.files.set(file,original); assert.equal((await reader.graph(nodeId)).reading.paragraphs[0],'中文正文');
    assert.equal((await reader.book(entryId)).body,'原书正文');
  } finally {f.restore();}
});

test('reuses unchanged graph buckets across snapshots and replaces only changed buckets', async()=>{
  const dir=await mkdtemp(join(tmpdir(),'astraia-shard-reuse-'));
  try {
    const input=join(dir,'graph.json'), handbook=join(dir,'book.json');
    const original={schema_version:1,snapshot_id:'a'.repeat(64),nodes:[
      {id:'case_one',reading:{paragraphs:['第一段']}}, {id:'case_two',reading:{paragraphs:['另一段']}}
    ]};
    const bookData={entries:[{id:'book_one',body:'知识正文'}]};
    await writeFile(handbook,JSON.stringify(bookData),'utf8');
    const build=async (output,data)=>{
      await writeFile(input,JSON.stringify(data),'utf8');
      await promisify(execFile)(process.execPath,[fileURLToPath(new URL('../scripts/build-syzygy-shards.mjs',import.meta.url)),input,output,handbook]);
      const bookSha=sha(JSON.stringify(bookData));
      return JSON.parse(await readFile(join(output,`manifest-${data.snapshot_id.slice(0,12)}-${bookSha.slice(0,12)}.json`),'utf8'));
    };
    const a=await build(join(dir,'a'),original);
    const b=await build(join(dir,'b'),{...original,snapshot_id:'b'.repeat(64)});
    const changed=structuredClone(original);changed.snapshot_id='c'.repeat(64);changed.nodes[0].reading.paragraphs[0]='更新的正文';
    const c=await build(join(dir,'c'),changed);
    assert.deepEqual(a.graph.parts,b.graph.parts);
    assert.deepEqual(a.book.parts,b.book.parts);
    assert.equal(b.graph.parts.filter((part,i)=>part.file!==c.graph.parts[i].file).length,1);
    assert.deepEqual(b.book.parts,c.book.parts);
    assert.equal(c.snapshot_id,'c'.repeat(64));
  } finally {await rm(dir,{recursive:true,force:true});}
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
