import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { test } from 'node:test';
import { loadPortalMatches } from '../src/syzygy/portalMatches.js';

const graph = {snapshot_id:'graph-1', nodes:[{id:'case-a'},{id:'case-b'},{id:'case-c'}]};
const book = {data_sha256:'book-1',entries:[{id:'HEA-1'}]};
const index = {schema_version:1,snapshot_id:'graph-1',handbook_sha256:'book-1',stats:{matched_nodes:3},matches:{
  'case-a':[{entry:'HEA-1',kind:'guide',reason:'来源类型'}],
  'case-b':[{entry:'HEA-1',kind:'theme',score:10,terms:[{term:'睡眠',source:'题名',target:'题名'}]}],
  'case-c':[{entry:'HEA-1',kind:'curated',bridge_id:'SYZ-1',reason:'精选阅读线索'}],
}};
function stub(data, hashData = data) {
  const text=JSON.stringify(data);
  const hash=createHash('sha256').update(JSON.stringify(hashData)).digest('hex');
  const previous=globalThis.fetch;
  globalThis.fetch=async()=>new Response(text,{status:200,headers:{'content-type':'application/json'}});
  return {dataset:{matches_sha256:hash}, restore:()=>{globalThis.fetch=previous;}};
}

test('valid index builds a reverse directory in evidence-safe priority order', async()=>{
  const fixture=stub(index);
  try {
    const data=await loadPortalMatches('/',fixture.dataset,book,graph);
    assert.deepEqual(data.reverse.get('HEA-1').map(row=>row.kind),['curated','theme','guide']);
    assert.deepEqual(data.reverse.get('HEA-1').map(row=>row.nodeId),['case-c','case-b','case-a']);
  } finally { fixture.restore(); }
});

test('rejects altered bytes, stale snapshots and unknown ids', async()=>{
  for (const [data, expected, hashData] of [
    [{...index,snapshot_id:'other'},/图谱版本不一致/],
    [{...index,matches:{'missing':[{entry:'HEA-1',kind:'theme'}]}},/未知节点/],
    [{...index,matches:{'case-a':[{entry:'missing',kind:'theme'}]}},/未知条目/],
    [{...index,matches:{'case-a':[{entry:'HEA-1',kind:'confirmed'}]}},/未知条目/],
    [{...index,matches:{'case-a':[{entry:'HEA-1',kind:'curated',bridge_id:'SYZ-1'}]}},/依据不完整/],
    [{...index,matches:{'case-a':[{entry:'HEA-1',kind:'theme',status:'confirmed',terms:[{term:'睡眠',source:'题名',target:'题名'}]}]}},/无效状态/],
    [{...index,stats:{matched_nodes:4}},/校验失败/,index],
  ]) {
    const fixture=stub(data,hashData ?? data);
    try { await assert.rejects(loadPortalMatches('/',fixture.dataset,book,graph),expected); }
    finally { fixture.restore(); }
  }
});
