import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import {
  DEFAULT_MEMBRANE_DEPTH,
  REALMS,
  clampDepth,
  computeLunarSyzygy,
  isBeyondMembrane,
  loadObserverTrace,
  membraneIntensity,
  realmById,
  realmForDepth,
  recordObservation,
  summarizeObserverBalance,
} from '../src/syzygy/realms.js';
import {
  PRISM_THEMES,
  renderPrismPhilosophyHTML,
  resolvePrismForPair,
} from '../src/syzygy/philosophicalPrism.js';

test('default membrane landing is at the critical threshold (0.5) and six realms progress cleanly', () => {
  assert.equal(DEFAULT_MEMBRANE_DEPTH, 0.5);
  assert.equal(realmForDepth(DEFAULT_MEMBRANE_DEPTH).id, 'threshold');
  assert.equal(isBeyondMembrane(0), false);
  assert.equal(isBeyondMembrane(0.5), false);
  assert.equal(isBeyondMembrane(0.75), true);
  assert.equal(isBeyondMembrane(1.0), true);
  assert.equal(isBeyondMembrane(4.0), true);

  assert.deepEqual(REALMS.map((r) => r.char), ['人', '膜', '鬼', '聻', '希', '夷']);
  assert.equal(realmForDepth(2.1).id, 'jian');
  assert.equal(realmForDepth(3.9).id, 'yi');
  assert.equal(realmById('jian').canInterfere, false);
  assert.equal(realmById('human').canInterfere, true);
  assert.equal(clampDepth(99), 4);
  assert.equal(clampDepth(-5), 0);
  assert.ok(membraneIntensity(0.5) > membraneIntensity(0));
});

test('astronomical synodic lunar phase calculation returns valid bounded phase and Chinese label', () => {
  const newMoon = computeLunarSyzygy(new Date(Date.UTC(2000, 0, 6, 18, 14, 0)));
  assert.ok(newMoon.phase < 0.01 || newMoon.phase > 0.99);
  assert.equal(newMoon.phaseName, '朔月');

  const halfCycle = computeLunarSyzygy(new Date(Date.UTC(2000, 0, 6, 18, 14, 0) + 14.765 * 86400000));
  assert.ok(Math.abs(halfCycle.phase - 0.5) < 0.02);
  assert.equal(halfCycle.phaseName, '望月');
  assert.ok(halfCycle.illumination > 0.98);
});

test('philosophical prism themes reference existing handbook entries and escape HTML safely', async () => {
  const book = JSON.parse(await readFile(new URL('../public/knowledge/data.json', import.meta.url), 'utf8'));
  const entriesById = new Map(book.entries.map((entry) => [entry.id, entry]));

  for (const theme of Object.values(PRISM_THEMES)) {
    assert.ok(entriesById.has(theme.phiEntryId), `Missing PHI entry ${theme.phiEntryId} for ${theme.id}`);
    assert.ok(entriesById.has(theme.secondaryEntryId), `Missing secondary entry ${theme.secondaryEntryId} for ${theme.id}`);
  }

  const zibuyuPrism = resolvePrismForPair({
    node: { id: 'case_cn_zibuyu_v03_s023', title: '《子不语》卷 03 · 城隍殺鬼不許為聻', genre: 'unclassified' },
    entry: entriesById.get('PHI-6-0002'),
    depth: 4.0,
  });
  assert.equal(zibuyuPrism.id, 'life_death_scale');
  assert.equal(zibuyuPrism.realm.id, 'yi');

  const infraPrism = resolvePrismForPair({
    node: { id: 'case_coventry_sword_lab_1998', title: '考文垂实验室次声异响', genre: 'memorate' },
    entry: entriesById.get('PHY-4-0002'),
    bridge: { trail: 'trail2', relation: 'EMPIRICAL_EXPLAINS' },
    depth: 1.0,
  });
  assert.equal(infraPrism.id, 'sensory_boundary');
  assert.equal(infraPrism.experimentId, 'infrasound');

  const html = renderPrismPhilosophyHTML(zibuyuPrism, book.entries);
  assert.match(html, /data-prism-book="PHI-6-0002"/);
  assert.match(html, /LOGOS · 折光哲思/);
});

test('observer trace accumulates balance and stays safe without browser storage', () => {
  const mem = new Map();
  const mockStorage = {
    getItem: (k) => mem.get(k) ?? null,
    setItem: (k, v) => mem.set(k, v),
  };
  let trace = loadObserverTrace(mockStorage);
  assert.equal(trace.rippleCount, 0);
  trace = recordObservation(trace, { type: 'ripple', label: '搏之不得，唯余微澜', depth: 1.0 }, mockStorage);
  trace = recordObservation(trace, { type: 'bridge', label: 'SYZ-01', depth: 0.5 }, mockStorage);
  trace = recordObservation(trace, { type: 'cross', label: 'Ⅴ 夷', depth: 4.0 }, mockStorage);

  const reloaded = loadObserverTrace(mockStorage);
  assert.equal(reloaded.rippleCount, 1);
  assert.equal(reloaded.bridgeCount, 1);
  assert.equal(reloaded.crossingCount, 1);
  assert.equal(reloaded.trail.length, 3);

  const summary = summarizeObserverBalance(reloaded);
  assert.ok(summary.physisRatio >= 0 && summary.physisRatio <= 1);
  assert.ok(summary.label.length > 0 && summary.reflection.length > 0);
});

test('membrane layer omits fullscreen purple crossFlash or veil wash overlays', async () => {
  const source = await readFile(new URL('../src/syzygy/membrane.js', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /\bcrossFlash\b/);
  assert.doesNotMatch(source, /\bveilAlpha\b/);
  assert.doesNotMatch(source, /fillRect\s*\(/);
  assert.doesNotMatch(source, /\bdrawWaveField\b/);
  assert.doesNotMatch(source, /\bisCentralHorizon\b/);
  assert.doesNotMatch(source, /\blineCount\b/);
  assert.doesNotMatch(source, /\bthresholdFocus\b/);
});
