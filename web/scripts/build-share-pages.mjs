import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { deflateSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';

// Build social previews from the *published* snapshot. The abstract stars are
// decorative; they do not represent observations or asserted relationships.
const [graphPath, outputRoot, publicBase = 'https://miracleqihe.github.io/astraia/', limit] = process.argv.slice(2);
if (!graphPath || !outputRoot || !/^https:\/\//.test(publicBase) || !publicBase.endsWith('/')) {
  throw new Error('Usage: node build-share-pages.mjs GRAPH OUTPUT_ROOT [PUBLIC_BASE] [LIMIT]');
}
const graphBytes=await readFile(resolve(graphPath));
const graph = JSON.parse(graphBytes.toString('utf8'));
if (graph.schema_version !== 1 || !Array.isArray(graph.nodes)) throw new Error('Invalid graph snapshot.');
let nodes = graph.nodes.filter(node => node.z_layer === 1);
if (limit) nodes = nodes.slice(0,Number(limit));
const ids=new Set();
for (const node of nodes) {
  if (!/^[A-Za-z0-9_-]+$/.test(node.id ?? '') || ids.has(node.id.toLowerCase())) throw new Error(`Invalid or duplicate story id: ${node.id}`);
  ids.add(node.id.toLowerCase());
}
const out=resolve(outputRoot), W=1200, H=630, stride=W+1;
await mkdir(`${out}/s`,{recursive:true}); await mkdir(`${out}/og`,{recursive:true});
const esc = text => String(text ?? '').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[char]);

// Indexed-color PNGs keep 7,732 individual cards inexpensive to store and transfer.
const crcTable=Uint32Array.from({length:256},(_,n)=>{for(let k=0;k<8;k++)n=n&1?0xedb88320^(n>>>1):n>>>1;return n>>>0;});
function crc(bytes) { let n=0xffffffff; for(const b of bytes)n=crcTable[(n^b)&255]^(n>>>8); return (n^0xffffffff)>>>0; }
function chunk(type,data) { const name=Buffer.from(type), length=Buffer.alloc(4), check=Buffer.alloc(4); length.writeUInt32BE(data.length); check.writeUInt32BE(crc(Buffer.concat([name,data]))); return Buffer.concat([length,name,data,check]); }
const header=Buffer.alloc(13); header.writeUInt32BE(W,0); header.writeUInt32BE(H,4); header[8]=8; header[9]=3;
const template=await readFile(fileURLToPath(new URL('./share-template.bin',import.meta.url)));
if(template.length !== 768+stride*H)throw new Error('Invalid share-card template.');
const palette=template.subarray(0,768), base=template.subarray(768);
function nearest(r,g,b){let best=0,distance=Infinity;for(let i=0;i<256;i++){const d=(palette[i*3]-r)**2+(palette[i*3+1]-g)**2+(palette[i*3+2]-b)**2;if(d<distance){best=i;distance=d;}}return best;}
const gold=nearest(194,157,89), ivory=nearest(239,236,230);
function dot(pixels,x,y,color) { x=Math.round(x);y=Math.round(y); if(x>=0&&x<W&&y>=0&&y<H)pixels[y*stride+1+x]=color; }
function image(id) {
  const pixels=Buffer.from(base), hash=createHash('sha256').update(id).digest(); let state=hash.readUInt32LE(0);
  const rand=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296;};
  for(let i=0;i<27;i++) {const radius=Math.sqrt(rand())*213,angle=rand()*Math.PI*2,x=895+radius*Math.cos(angle),y=315+radius*Math.sin(angle),size=i<4?4:2;
    for(let d=-size;d<=size;d++){dot(pixels,x+d,y,gold);dot(pixels,x,y+d,gold);} dot(pixels,x,y,ivory);
  }
  return Buffer.concat([Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',header),chunk('PLTE',palette),chunk('IDAT',deflateSync(pixels,{level:6})),chunk('IEND',Buffer.alloc(0))]);
}
async function make(node) {
  const title=String(node.title ?? node.id), text=(node.reading?.paragraphs ?? []).find(p=>typeof p==='string'&&p.trim());
  const description=[...(text ? text.replace(/\s+/g,' ').trim() : `${title}：在 Astraia 阅读这条资料及其出处。`)].slice(0,180).join('');
  const route=`${publicBase}s/${node.id}/`, og=`${publicBase}og/${node.id}.png`;
  const dim=Number.isFinite(node.spatial?.lat)&&Number.isFinite(node.spatial?.lng)?'umbra':'sidera';
  const isFiction=node.credibility_tier==='F'||node.is_fictional_quarantine;
  const qs=new URLSearchParams({dim,story:node.id}); if(isFiction){qs.set('fiction','1');qs.set('tiers','S,A,B,C,F');}
  const target=`../../syzygy/?${qs}`, targetJson=JSON.stringify(target);
  const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)} · ASTRAIA</title><meta name="description" content="${esc(description)}"><meta property="og:type" content="article"><meta property="og:title" content="${esc(title)} · ASTRAIA"><meta property="og:description" content="${esc(description)}"><meta property="og:url" content="${esc(route)}"><meta property="og:image" content="${esc(og)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="${esc(title)} · Astraia 星图"><meta name="twitter:card" content="summary_large_image"><script>const target=new URL(${targetJson},location.href);for(const [k,v] of new URLSearchParams(location.search))if(k!=='story')target.searchParams.set(k,v);location.replace(target.href);</script></head><body><p>正在打开 ${esc(title)}。<a href="${esc(target)}">点击阅读</a></p></body></html>\n`;
  await mkdir(`${out}/s/${node.id}`,{recursive:true});
  await Promise.all([writeFile(`${out}/s/${node.id}/index.html`,html,'utf8'),writeFile(`${out}/og/${node.id}.png`,image(node.id))]);
}
for(let i=0;i<nodes.length;i+=32) await Promise.all(nodes.slice(i,i+32).map(make));
const manifest={schema_version:1,snapshot_id:graph.snapshot_id,graph_sha256:createHash('sha256').update(graphBytes).digest('hex'),
  count:nodes.length,ids_sha256:createHash('sha256').update(nodes.map(node=>node.id).join('\n'),'utf8').digest('hex')};
await writeFile(`${out}/og/manifest.json`,JSON.stringify(manifest)+'\n','utf8');
console.log(`Share pages: ${nodes.length} story entries, each with metadata and a decorative 1200×630 PNG.`);
