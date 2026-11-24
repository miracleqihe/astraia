import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

test('four reading paths refer to 68 distinct real handbook entries', async()=>{
  const paths=JSON.parse(await readFile(new URL('../src/syzygy/reading-paths.json',import.meta.url),'utf8'));
  const book=JSON.parse(await readFile(new URL('../public/knowledge/data.json',import.meta.url),'utf8'));
  const ids=paths.flatMap(path=>path.entries), actual=new Set(book.entries.map(entry=>entry.id));
  assert.equal(paths.length,4);assert.ok(paths.every(path=>path.title && path.entries.length===17));
  assert.equal(new Set(ids).size,68);assert.ok(ids.every(id=>actual.has(id)));
});
