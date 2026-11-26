import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, dirname, join } from 'node:path';
import { test } from 'node:test';
import { buildTaxonomyLexicon } from '../scripts/build-taxonomy-lexicon.mjs';

test('a print source keeps its page visible and cannot omit its locator', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'astraia-print-source-'));
  t.after(async () => {
    const resolved = await realpath(root);
    assert.equal(dirname(resolved), await realpath(tmpdir()));
    assert.ok(basename(resolved).startsWith('astraia-print-source-'));
    await rm(resolved, { recursive: true });
  });
  const lexicons = join(root, 'lexicons');
  await mkdir(lexicons);
  const taxonomyPath = join(root, 'taxonomy.json');
  const graphPath = join(root, 'graph.json');
  const outputDir = join(root, 'output');
  await writeFile(taxonomyPath, JSON.stringify({ version: 1, domains: Array.from({ length: 7 }, (_, i) => ({
    id: `domain_${i}`, name: `专题 ${i}`, groups: [],
  })) }));
  await writeFile(graphPath, JSON.stringify({ schema_version: 1, snapshot_id: 'a'.repeat(64), nodes: [
    { id: 'hub_test' }, { id: 'case_test', z_layer: 1, spatial: { lat: 23, lng: 114 } },
  ] }));
  const bookPath = join(root, 'book.json');
  await writeFile(bookPath, JSON.stringify({ entries: [{ id: 'KNOW-1', body: '知识正文。' }] }));
  const file = join(lexicons, 'candidate.json');
  const source = { citation: '《中国镇物》', locator: '第 45 页' };
  const payload = { domain_id: 'domain_0', entries: [{ id: 'lex_test', hub_id: 'hub_test', term: '镇物',
    summary: '原创释义。', primary_sources: [source], case_id: 'case_test',
    knowledge_id: 'KNOW-1', knowledge_note: '主题对读。' }] };
  await writeFile(file, JSON.stringify(payload));
  const options = { taxonomyPath, graphPath, bookPath, lexiconDir: lexicons, outDir: outputDir, dryRun: false };
  const built = await buildTaxonomyLexicon(options);
  const shard = JSON.parse(await readFile(join(outputDir, built.manifest.domains.domain_0.file), 'utf8'));
  assert.deepEqual(shard.entries[0].primary_sources, [{ citation: '《中国镇物》', url: null, locator: '第 45 页' }]);
  assert.equal(shard.entries[0].case_id, 'case_test');
  assert.equal(shard.entries[0].knowledge_id, 'KNOW-1');

  payload.entries[0].case_id = 'case_missing';
  await writeFile(file, JSON.stringify(payload));
  await assert.rejects(buildTaxonomyLexicon({ ...options, dryRun: true }), /invalid geographic story reference/);
  payload.entries[0].case_id = 'case_test';

  delete source.locator;
  await writeFile(file, JSON.stringify(payload));
  await assert.rejects(buildTaxonomyLexicon({ ...options, dryRun: true }), /page or chapter/);
});
