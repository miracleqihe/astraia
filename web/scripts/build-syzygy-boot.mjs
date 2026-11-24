import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const publicDir = fileURLToPath(new URL('../public/', import.meta.url));
const input = resolve(process.argv[2] ?? `${publicDir}/syzygy/data.json`);
const output = resolve(process.argv[3] ?? `${publicDir}/syzygy/boot.json`);
const dataset = JSON.parse(await readFile(input,'utf8'));
if (dataset.schema_version !== 1 || !Array.isArray(dataset.bridges) || !/^[a-f0-9]{64}$/.test(dataset.matches_sha256 ?? '')) {
  throw new Error('Generate the bridge and matching data before the boot package.');
}
const preview = text => {
  const chars = [...String(text ?? '')];
  return chars.length > 160 ? chars.slice(0,160).join('') + '…' : chars.join('');
};
const compact = node => !node ? null : ({
  id:node.id, title:node.title, z_layer:node.z_layer, genre:node.genre, credibility_tier:node.credibility_tier,
  spatial:node.spatial ? {lat:node.spatial.lat,lng:node.spatial.lng,location_name:node.spatial.location_name} : null,
  standards:node.standards, sources:(node.sources ?? []).slice(0,1),
  reading:node.reading ? {kind:node.reading.kind, paragraphs:(node.reading.paragraphs ?? []).slice(0,1).map(preview)} : null,
});
const boot = { ...dataset, bridges:dataset.bridges.map(bridge => ({...bridge,
  mythos:compact(bridge.mythos), related:compact(bridge.related),
  physis:{id:bridge.physis.id,title:bridge.physis.title,topic:bridge.physis.topic,subject:bridge.physis.subject,
    volume:bridge.physis.volume,page:bridge.physis.page,volId:bridge.physis.volId,discId:bridge.physis.discId,body:'',figure_refs:[]},
})) };
const content = JSON.stringify(boot) + '\n';
let previous=''; try { previous = await readFile(output,'utf8'); } catch { /* First build. */ }
if (previous !== content) await writeFile(output,content,'utf8');
console.log(`Syzygy boot: ${boot.bridges.length} previews (${Buffer.byteLength(content)} bytes).`);
