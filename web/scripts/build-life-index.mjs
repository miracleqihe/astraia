import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';

// This file is deliberately generated from the same source as the full text.
// The hash lets the client detect a partial deployment or stale cache.
const input = new URL('../public/knowledge/data.json', import.meta.url);
const output = new URL('../public/knowledge/index.json', import.meta.url);
const raw = await readFile(input);
const book = JSON.parse(raw.toString('utf8'));
if (!Array.isArray(book.entries) || !Array.isArray(book.subjects) || !book.source_sha256) {
  throw new Error('Invalid knowledge book: cannot build its index.');
}
const ids = new Set();
const entries = book.entries.map(({ id, title, topic, subject, volume, page, links }) => {
  if (!id || ids.has(id) || !Array.isArray(links)) throw new Error(`Invalid knowledge entry: ${id}`);
  ids.add(id);
  return { id, title, topic, subject, volume, page, links, figure_refs: [], body: '' };
});
const index = {
  title: book.title, edition: book.edition, source_sha256: book.source_sha256,
  data_sha256: createHash('sha256').update(raw).digest('hex'),
  anchors: {}, figures: {}, subjects: book.subjects, entries,
};
const content = JSON.stringify(index) + '\n';
let previous = '';
try { previous = await readFile(output, 'utf8'); } catch { /* First build. */ }
if (previous !== content) await writeFile(output, content, 'utf8');
console.log(`Knowledge index: ${entries.length} entries, ${Buffer.byteLength(content)} bytes`);
