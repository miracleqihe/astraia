import assert from 'node:assert/strict';
import { test } from 'node:test';
import { handbookText, bookNavigation } from '../src/syzygy/readable.js';
import { genreContract, sourceTier } from '../src/syzygy/narrativeMetadata.js';
import { originalPageButton } from '../src/syzygy/originalPages.js';

test('handbook text keeps Chinese and renders only local, safe original figures',()=>{
  const html=handbookText('⟦anchor:focus⟧\n中文正文 ![原书图表](inline-figures/abc.svg)\n![跨目录](figures/sub/diagram.svg)\n![恶意](../../evil.svg) <script>坏</script>','/astraia/');
  assert.match(html,/中文正文/); assert.match(html,/src="\/astraia\/knowledge\/inline-figures\/abc\.svg"/);
  assert.match(html,/src="\/astraia\/knowledge\/figures\/sub\/diagram\.svg"/);
  assert.doesNotMatch(html,/<script>/); assert.doesNotMatch(html,/src="[^"]*evil/); assert.doesNotMatch(html,/⟦anchor:/);
});

test('book navigation stays within the original subject and escapes titles',()=>{
  const entries=[{id:'a',subject:'X',title:'甲'},{id:'b',subject:'Y',title:'乙'},{id:'c',subject:'X',title:'丙<script>'}];
  const html=bookNavigation(entries[0],entries);
  assert.match(html,/data-book-neighbor="c"/); assert.doesNotMatch(html,/data-book-neighbor="b"/);
  assert.match(html,/丙&lt;script&gt;/); assert.match(html,/已到边界/);
});

test('genre is never inferred from source rank or title, and F remains a fiction marker',()=>{
  assert.equal(genreContract({genre:'memorate',credibility_tier:'A'}),'MEMORATE');
  assert.equal(genreContract({genre:'folktale',credibility_tier:'A'}),'FOLKTALE');
  assert.equal(genreContract({genre:'historical_archive',credibility_tier:'A'}),'HISTORICAL');
  assert.equal(genreContract({genre:'unclassified',title:'都市传说'}),'OTHER');
  assert.equal(genreContract({genre:'creepypasta_ostension',credibility_tier:'F'}),'OSTENSION');
  assert.equal(sourceTier({credibility_tier:'F'}),null);
  assert.equal(sourceTier({credibility_tier:'A'}),'A');
});

test('original page controls accept only positive physical PDF pages',()=>{
  assert.match(originalPageButton(7),/data-original-page="7"/);
  for (const value of [0,-1,1.5,'7','<script>']) assert.equal(originalPageButton(value),'');
});
