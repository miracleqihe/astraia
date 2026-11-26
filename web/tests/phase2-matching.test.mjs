import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

test('Phase 2 matching achieves 20/20 discipline coverage and expands substantive graph & book connectivity', async () => {
  const matches = JSON.parse(await readFile(new URL('../public/syzygy/matches.json', import.meta.url), 'utf8'));
  const book = JSON.parse(await readFile(new URL('../public/knowledge/data.json', import.meta.url), 'utf8'));
  const entrySubject = new Map(book.entries.map(entry => [entry.id, entry.subject]));
  const allSubjects = new Set(book.entries.map(entry => entry.subject));

  assert.equal(allSubjects.size, 20);
  assert.equal(matches.stats.connected_disciplines, 20);
  assert.ok(matches.stats.substantive_nodes >= 7000, `Expected >= 7000 substantive nodes, got ${matches.stats.substantive_nodes}`);
  assert.ok(matches.stats.substantive_book_entries >= 220, `Expected >= 220 substantive book entries, got ${matches.stats.substantive_book_entries}`);

  const disciplineCounts = new Map();
  for (const rows of Object.values(matches.matches)) {
    for (const row of rows) {
      assert.equal(row.status, undefined, 'Auto-matched rows must never assert evidence status');
      if (row.kind !== 'guide') {
        const subj = entrySubject.get(row.entry);
        assert.ok(subj, `Unknown entry ${row.entry}`);
        disciplineCounts.set(subj, (disciplineCounts.get(subj) ?? 0) + 1);
      }
    }
  }

  for (const subj of ['PHI', 'MAT', 'MTH', 'ECO', 'LAW', 'LAN', 'SCR']) {
    assert.ok((disciplineCounts.get(subj) ?? 0) > 0, `Previously zero-hit discipline ${subj} must be connected`);
  }
  assert.equal(disciplineCounts.size, 20);

  const zibuyu = matches.matches.case_cn_zibuyu_v03_s023 ?? [];
  assert.ok(zibuyu.some(row => row.entry === 'PHI-6-0002' && row.kind === 'theme'));
  assert.ok(zibuyu.some(row => row.kind === 'relay'));

  const berezkinM10 = matches.matches.index_berezkin_m10 ?? [];
  assert.ok(berezkinM10.some(row => row.kind === 'relay' && (row.entry === 'MTH-GAME-0002' || row.entry === 'ECO-1-0010')));

  const boot = JSON.parse(await readFile(new URL('../public/syzygy/boot.json', import.meta.url), 'utf8'));
  assert.ok(boot.match_summary, 'boot.json must include compact match_summary');
  assert.equal(boot.match_summary.stats.substantive_nodes, matches.stats.substantive_nodes);
  assert.equal(boot.match_summary.stats.connected_disciplines, 20);
  assert.equal(Object.keys(boot.match_summary.book_match_counts).length, matches.stats.substantive_book_entries);
});
