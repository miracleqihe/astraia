import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { promisify } from 'node:util';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

test('static social previews retain story metadata and fiction settings while sharing bounded images',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'astraia-share-'));
  try {
    const graph={schema_version:1,nodes:[
      {id:'case_one',z_layer:1,title:'中文 & <标题>',credibility_tier:'A',spatial:{lat:31,lng:121},reading:{paragraphs:['第一段 "原文"。']}},
      {id:'case_two',z_layer:1,title:'后室',credibility_tier:'F',spatial:{},reading:{paragraphs:['数字故事。']}},
      {id:'motif_three',z_layer:3,title:'母题'},
      ...Array.from({length:32},(_,i)=>({id:`case_extra_${i}`,z_layer:1,title:`第 ${i} 条`})),
    ]};
    const path=join(dir,'graph.json'); await writeFile(path,JSON.stringify(graph),'utf8');
    await promisify(execFile)(process.execPath,[fileURLToPath(new URL('../scripts/build-share-pages.mjs',import.meta.url)),path,dir,'https://example.org/astraia/']);
    const one=await readFile(join(dir,'s/case_one/index.html'),'utf8'),two=await readFile(join(dir,'s/case_two/index.html'),'utf8');
    assert.match(one,/中文 &amp; &lt;标题&gt;/);assert.match(one,/第一段 &quot;原文&quot;/);
    assert.match(one,/og:image/);assert.match(one,/https:\/\/example\.org\/astraia\/og\/shared-[0-7]\.png/);
    assert.match(two,/fiction=1/);assert.match(two,/tiers=S%2CA%2CB%2CC%2CF/);
    const names=await readdir(join(dir,'og'));const shared=names.filter(name=>/^shared-[0-7]\.png$/.test(name));
    assert.ok(shared.length > 0 && shared.length <= 8);
    const imageName=one.match(/og\/shared-[0-7]\.png/)[0];
    const png=await readFile(join(dir,imageName));
    assert.equal(png.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
    assert.equal(png.readUInt32BE(16),1200);assert.equal(png.readUInt32BE(20),630);
    assert.ok(!names.includes('case_one.png') && !names.includes('case_two.png'));
    await assert.rejects(readFile(join(dir,'s/motif_three/index.html')));
  } finally {
    if (!resolve(dir).startsWith(resolve(tmpdir()) + sep)) throw new Error('Temporary path escaped its parent directory.');
    await rm(dir,{recursive:true,force:true});
  }
});
