import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, dirname, join } from 'node:path';
import { test } from 'node:test';
import {
  autoGist,
  buildTaxonomyLexicon,
  classifyCorpusNodes,
  deriveReadingTag,
  normalizeLexiconTerm,
} from '../scripts/build-taxonomy-lexicon.mjs';
import {
  renderTaxonomyExplorerView,
  renderTaxonomyLexiconEntriesView,
} from '../src/syzygy/taxonomyExplorer.js';

const readJson = async (relPath) => JSON.parse(await readFile(new URL(relPath, import.meta.url), 'utf8'));
const readText = async (relPath) => readFile(new URL(relPath, import.meta.url), 'utf8');

function createMockElement(tagName = 'div', attrs = {}, innerText = '') {
  const listeners = new Map();
  const children = [];
  const el = {
    tagName: tagName.toUpperCase(),
    attrs: { ...attrs },
    dataset: {},
    hidden: false,
    value: attrs.value ?? '',
    _innerHTML: '',
    textContent: innerText,
    children,
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(fn);
    },
    click() {
      this.dispatchEvent({ type: 'click', currentTarget: this, target: this });
    },
    dispatchEvent(event) {
      const evt = { currentTarget: this, target: this, ...event };
      for (const fn of listeners.get(evt.type) ?? []) fn(evt);
    },
    setAttribute(name, value) {
      this.attrs[name] = String(value);
      if (name.startsWith('data-')) {
        const camel = name.slice(5).replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
        this.dataset[camel] = String(value);
      }
    },
    getAttribute(name) {
      return Object.hasOwn(this.attrs, name) ? this.attrs[name] : null;
    },
    scrollIntoView() {
      this._scrolled = true;
    },
    querySelector(selector) {
      return this.querySelectorAll(selector)[0] ?? null;
    },
    querySelectorAll(selector) {
      return queryMockElements(this, selector);
    },
    set innerHTML(html) {
      this._innerHTML = String(html);
      this.children.length = 0;
      const parsed = parseMockChildren(this._innerHTML);
      this.children.push(...parsed);
    },
    get innerHTML() {
      return this._innerHTML;
    },
  };
  for (const [k, v] of Object.entries(attrs)) {
    el.setAttribute(k, v);
  }
  return el;
}

function parseMockChildren(html) {
  const root = { children: [] };
  const stack = [root];
  const voidTags = new Set(['input', 'img', 'br', 'hr']);
  const tokenRe = /<\/?([a-z0-9-]+)([^>]*)>/gi;
  let match;
  while ((match = tokenRe.exec(html)) !== null) {
    const full = match[0];
    const tag = match[1].toLowerCase();
    if (full.startsWith('</')) {
      for (let i = stack.length - 1; i >= 1; i -= 1) {
        if (stack[i].tagName.toLowerCase() === tag) {
          stack.length = i;
          break;
        }
      }
      continue;
    }
    const rawAttrs = match[2] ?? '';
    const attrs = {};
    const attrRe = /([a-z0-9:-]+)(?:="([^"]*)")?/gi;
    let am;
    while ((am = attrRe.exec(rawAttrs)) !== null) {
      attrs[am[1]] = am[2] ?? '';
    }
    const el = createMockElement(tag, attrs);
    stack[stack.length - 1].children.push(el);
    if (!voidTags.has(tag) && !full.endsWith('/>')) {
      stack.push(el);
    }
  }
  return root.children;
}

function matchesMockSelector(el, selector) {
  if (selector.startsWith('#')) {
    return el.attrs.id === selector.slice(1);
  }
  if (selector.startsWith('.')) {
    const cls = selector.slice(1);
    return String(el.attrs.class ?? '').split(/\s+/).includes(cls);
  }
  const attrMatch = selector.match(/^\[([a-z0-9-]+)(?:="([^"]*)")?\]$/i);
  if (attrMatch) {
    const [, attrName, attrVal] = attrMatch;
    if (!Object.hasOwn(el.attrs, attrName)) return false;
    return attrVal == null ? true : el.attrs[attrName] === attrVal;
  }
  return el.tagName.toLowerCase() === selector.toLowerCase();
}

function queryMockElements(root, selector) {
  const results = [];
  for (const child of root.children ?? []) {
    if (matchesMockSelector(child, selector)) results.push(child);
    results.push(...queryMockElements(child, selector));
  }
  return results;
}

test('classifyCorpusNodes deterministically partitions synthetic nodes without within-domain duplicates', () => {
  const domains = [
    {
      id: 'wugu_talisman',
      order: 1,
      groups: [{ id: 'g1', hub_ids: ['hub_wugu'], featured_nodes: ['hub_wugu', 'case_explicit_wugu'] }],
    },
    { id: 'underworld_bureaucracy', order: 2, groups: [{ id: 'g2', hub_ids: ['hub_yama'], featured_nodes: [] }] },
    { id: 'ghost_rituals_nuo', order: 3, groups: [{ id: 'g3', hub_ids: [], featured_nodes: [] }] },
    { id: 'ethnic_spirit_lexicon', order: 4, groups: [{ id: 'g4', hub_ids: [], featured_nodes: [] }] },
    { id: 'classical_zhiguai_opera', order: 5, groups: [{ id: 'g5', hub_ids: [], featured_nodes: [] }] },
    { id: 'world_mythology', order: 6, groups: [{ id: 'g6', hub_ids: [], featured_nodes: [] }] },
    { id: 'modern_liminal', order: 7, groups: [{ id: 'g7', hub_ids: [], featured_nodes: [] }] },
  ];

  const extraWugu = Array.from({ length: 20 }, (_, i) => ({
    id: `case_cn_tao_sample_${String(i).padStart(2, '0')}`,
    title: `镇物示例 ${i}`,
    z_layer: i % 2 === 0 ? 2 : 1,
    genre: 'historical_archive',
  }));

  const graph = {
    schema_version: 1,
    nodes: [
      { id: 'hub_wugu', title: '巫蛊枢纽', z_layer: 3, genre: 'academic_model' },
      { id: 'case_explicit_wugu', title: '显式镇物案例', z_layer: 1, genre: 'folktale' },
      { id: 'hub_yama', title: '十殿枢纽', z_layer: 3, genre: 'academic_model' },
      { id: 'case_cn_chenghuang_test', title: '城隍夜巡案', z_layer: 1, genre: 'folktale' },
      { id: 'case_cn_nuo_mask_test', title: '大傩面具仪', z_layer: 1, genre: 'folktale' },
      { id: 'case_cn_shanhai_fox_test', title: '山海经九尾狐', z_layer: 1, genre: 'myth' },
      { id: 'case_cn_zibuyu_v99_s001', title: '《子不语》示例', z_layer: 1, genre: 'folktale' },
      { id: 'index_berezkin_test_1', title: 'Berezkin Motif', z_layer: 3, genre: 'academic_model' },
      { id: 'scot_a_egd_test_1', title: '苏格兰猎巫档案', z_layer: 1, genre: 'historical_archive' },
      { id: 'case_scp_9999_liminal', title: '后室阈限走廊', z_layer: 1, genre: 'creepypasta_ostension', is_fictional_quarantine: true },
      ...extraWugu,
    ],
  };

  const result = classifyCorpusNodes(graph, domains);
  assert.equal(result.coverage.total_graph_nodes, graph.nodes.length);
  assert.equal(result.coverage.total_classified_unique, graph.nodes.length);

  const wugu = result.byDomain.get('wugu_talisman');
  assert.equal(wugu.classifiedNodeCount, 22);
  assert.equal(new Set(wugu.classifiedNodeIds).size, wugu.classifiedNodeCount);
  assert.equal(wugu.sampleClassifiedNodes.length, 16);
  assert.ok(wugu.sampleClassifiedNodes.every((n) => n.id !== 'hub_wugu' && n.id !== 'case_explicit_wugu'));

  assert.ok(result.byDomain.get('underworld_bureaucracy').classifiedNodeIds.includes('case_cn_chenghuang_test'));
  assert.ok(result.byDomain.get('ghost_rituals_nuo').classifiedNodeIds.includes('case_cn_nuo_mask_test'));
  assert.ok(result.byDomain.get('ethnic_spirit_lexicon').classifiedNodeIds.includes('case_cn_shanhai_fox_test'));
  assert.ok(result.byDomain.get('classical_zhiguai_opera').classifiedNodeIds.includes('case_cn_zibuyu_v99_s001'));
  assert.ok(result.byDomain.get('world_mythology').classifiedNodeIds.includes('index_berezkin_test_1'));
  assert.ok(result.byDomain.get('world_mythology').classifiedNodeIds.includes('scot_a_egd_test_1'));
  assert.ok(result.byDomain.get('modern_liminal').classifiedNodeIds.includes('case_scp_9999_liminal'));
});

test('buildTaxonomyLexicon normalizes gist/reading_tag, forwards quick_overview/tldr, and rejects duplicate normalized terms', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'astraia-p7-lexicon-'));
  t.after(async () => {
    const resolved = await realpath(root);
    assert.equal(dirname(resolved), await realpath(tmpdir()));
    assert.ok(basename(resolved).startsWith('astraia-p7-lexicon-'));
    await rm(resolved, { recursive: true });
  });

  const lexicons = join(root, 'lexicons');
  await mkdir(lexicons);
  const taxonomyPath = join(root, 'taxonomy.json');
  const graphPath = join(root, 'graph.json');
  const bookPath = join(root, 'book.json');
  const outputDir = join(root, 'output');

  const domains = [
    {
      id: 'wugu_talisman',
      order: 1,
      name: '巫蛊与镇物',
      quick_overview: {
        three_book_anchor: '三书锚点：邓启耀《巫蛊》、陶思炎《中国镇物》。',
        core_question: '器物与流言如何重构日常边界？',
        key_takeaways: ['双轨法制', '心化器物', '心理暗示'],
      },
      groups: [
        {
          id: 'grp_1',
          title: '分组一',
          tldr: '一句话看懂：这是巫蛊与镇物的核心谱系。',
          chapter_intro: '导读正文。',
          description: '描述。',
          hub_ids: ['hub_wugu'],
          featured_nodes: ['case_wugu'],
        },
      ],
    },
    { id: 'underworld_bureaucracy', order: 2, name: '冥府官僚', groups: [] },
    { id: 'ghost_rituals_nuo', order: 3, name: '傩仪丧俗', groups: [] },
    { id: 'ethnic_spirit_lexicon', order: 4, name: '民俗精灵', groups: [] },
    { id: 'classical_zhiguai_opera', order: 5, name: '志怪鬼戏', groups: [] },
    { id: 'world_mythology', order: 6, name: '世界神话', groups: [] },
    { id: 'modern_liminal', order: 7, name: '现代异闻', groups: [] },
  ];

  await writeFile(taxonomyPath, JSON.stringify({ version: 1, domains }));
  await writeFile(graphPath, JSON.stringify({
    schema_version: 1,
    snapshot_id: 'b'.repeat(64),
    nodes: [
      { id: 'hub_wugu', title: '巫蛊枢纽', z_layer: 3, genre: 'academic_model' },
      { id: 'case_wugu', title: '镇物案例', z_layer: 1, spatial: { lat: 24, lng: 102 }, genre: 'folktale' },
      { id: 'case_cn_tao_extra', title: '额外镇水铁牛', z_layer: 1, genre: 'historical_archive' },
    ],
  }));
  await writeFile(bookPath, JSON.stringify({ entries: [{ id: 'HIS-1', body: '史学研读正文。' }] }));

  const candidatePath = join(lexicons, 'entries.json');
  const entriesPayload = {
    version: 1,
    domain_id: 'wugu_talisman',
    entries: [
      {
        id: 'lex_auto_1',
        hub_id: 'hub_wugu',
        term: '金蚕蛊',
        category: '巫蛊刑狱与禁律',
        reviewed_by_human: false,
        summary: '宋元以来福建等地流传的蓄蛊致富传闻，官府律令严禁造畜蛊毒并设重刑制裁，反映乡土社会对突发疾疫与异常致富的猜忌与替罪心理。',
        primary_sources: [{ citation: '《宋史》', locator: '卷二百一', url: 'https://zh.wikisource.org/' }],
        secondary_ref: '参照文献',
        case_id: 'case_wugu',
        knowledge_id: 'HIS-1',
        knowledge_note: '主题对读。',
      },
      {
        id: 'lex_manual_2',
        hub_id: 'hub_wugu',
        term: '泰山石敢当',
        gist: '街口巷冲镇煞立石民俗',
        reading_tag: '器物民俗',
        category: '屋脊门庭镇煞之器',
        summary: '立于街巷冲射之处的传统镇宅石碑。',
        primary_sources: [{ citation: '陶思炎：《中国镇物》', locator: '第 88 页' }],
      },
    ],
  };
  await writeFile(candidatePath, JSON.stringify(entriesPayload));

  const built = await buildTaxonomyLexicon({
    taxonomyPath,
    graphPath,
    bookPath,
    lexiconDir: lexicons,
    outDir: outputDir,
    dryRun: false,
  });

  const wuguOut = built.taxonomy.domains[0];
  assert.equal(wuguOut.node_count, 2);
  assert.equal(wuguOut.classified_node_count, 3);
  assert.equal(wuguOut.sample_classified_nodes.length, 1);
  assert.equal(wuguOut.sample_classified_nodes[0].id, 'case_cn_tao_extra');
  assert.deepEqual(wuguOut.quick_overview, domains[0].quick_overview);
  assert.equal(wuguOut.groups[0].tldr, '一句话看懂：这是巫蛊与镇物的核心谱系。');
  assert.equal(built.taxonomy.corpus_classification_coverage.total_graph_nodes, 3);
  assert.equal(built.taxonomy.corpus_classification_coverage.total_classified_unique, 3);

  const shard = JSON.parse(await readFile(join(outputDir, built.manifest.domains.wugu_talisman.file), 'utf8'));
  assert.ok(shard.entries[0].gist.length > 0 && shard.entries[0].gist.length <= 36);
  assert.equal(shard.entries[0].reading_tag, '巫蛊与镇护');
  assert.equal(shard.entries[0].reviewed_by_human, false);
  assert.equal(shard.entries[0].case_id, 'case_wugu');
  assert.equal(shard.entries[0].knowledge_id, 'HIS-1');
  assert.equal(shard.entries[0].knowledge_note, '主题对读。');
  assert.equal(shard.entries[0].secondary_ref, '参照文献');
  assert.equal(shard.entries[1].gist, '街口巷冲镇煞立石民俗');
  assert.equal(shard.entries[1].reading_tag, '器物民俗');

  // Verify duplicate normalized term guard within same domain
  entriesPayload.entries.push({
    id: 'lex_dup_term',
    hub_id: 'hub_wugu',
    term: ' 金 蚕 · 蛊 ',
    summary: '重复词条测试。',
    primary_sources: [{ citation: '《宋史》', url: 'https://zh.wikisource.org/' }],
  });
  await writeFile(candidatePath, JSON.stringify(entriesPayload));
  await assert.rejects(
    buildTaxonomyLexicon({ taxonomyPath, graphPath, bookPath, lexiconDir: lexicons, outDir: outputDir, dryRun: true }),
    /Duplicate normalized term/,
  );

  assert.equal(normalizeLexiconTerm('  Test—Term! '), 'testterm');
  assert.ok(autoGist('第一句非常长，需要截断成不超过三十六个汉字的精简导读句，用来验证自动摘要长度控制。').length <= 36);
  assert.equal(deriveReadingTag({ category: '当代都市传闻' }, 'modern_liminal'), '当代异闻');
  assert.equal(deriveReadingTag({ category: '放蛊流言', era: '唐代文献' }, 'wugu_talisman'), '巫蛊与镇护');
});

test('compiled live taxonomy.json and all 7 shards satisfy full-corpus coverage and readability invariants', async () => {
  const [graph, taxonomy, manifest] = await Promise.all([
    readJson('../public/data/graph_data.json'),
    readJson('../public/syzygy/taxonomy.json'),
    readJson('../public/syzygy/lexicon/manifest.json'),
  ]);

  assert.equal(taxonomy.corpus_classification_coverage?.total_graph_nodes, graph.nodes.length);
  assert.equal(taxonomy.corpus_classification_coverage?.total_classified_unique, graph.nodes.length);

  for (const domain of taxonomy.domains) {
    assert.ok(domain.classified_node_count >= domain.node_count, `${domain.id}: classified_node_count < node_count`);
    assert.ok(Array.isArray(domain.sample_classified_nodes) && domain.sample_classified_nodes.length === 16);
    const curatedIds = new Set(
      domain.groups.flatMap((g) => [...(g.hub_ids ?? []), ...(g.featured_nodes ?? [])]),
    );
    for (const sample of domain.sample_classified_nodes) {
      assert.ok(!curatedIds.has(sample.id), `${domain.id}: sample_classified_nodes must exclude curated node ${sample.id}`);
    }

    const shard = await readJson(`../public/syzygy/${manifest.domains[domain.id].file}`);
    const seenTerms = new Set();
    for (const entry of shard.entries) {
      assert.ok(typeof entry.gist === 'string' && entry.gist.trim().length > 0 && entry.gist.length <= 36);
      assert.ok(typeof entry.reading_tag === 'string' && entry.reading_tag.trim().length > 0);
      const norm = normalizeLexiconTerm(entry.term);
      assert.ok(!seenTerms.has(norm), `Duplicate term in ${domain.id}: ${entry.term}`);
      seenTerms.add(norm);
    }
  }
});

test('renderTaxonomyExplorerView renders landing, quick overview, collapsed intro, expandable 6-chip groups, discovery strip, and live-filtered lexicon cards', () => {
  const container = createMockElement('section', { id: 'taxonomy-explorer' });
  const taxonomy = {
    corpus_classification_coverage: { total_graph_nodes: 11778, total_classified_unique: 11778 },
    editorial_preface: {
      title: '测试总序',
      subtitle: '总序副题',
      paragraphs: ['第一段。', '第二段。'],
      principles: [
        { label: '原则一', text: '文本一' },
        { label: '原则二', text: '文本二' },
        { label: '原则三', text: '文本三' },
      ],
    },
    bibliography: ['徐华龙：《中国鬼文化大辞典》'],
    domains: [
      {
        id: 'wugu_talisman',
        order: 1,
        name: '巫蛊与镇物',
        english_name: 'Wugu & Talismans',
        subtitle: '三载体六维谱系',
        summary: '域摘要。',
        accent: '#c86fff',
        sidera_id: 'sid_witch',
        disciplines: ['HIS', 'REL'],
        node_count: 8,
        classified_node_count: 155,
        lexicon_count: 2,
        lexicon_shard: { file: 'lexicon/wugu_talisman-abcdef123456.json', sha256: 'a'.repeat(64), count: 2, categories: ['蛊毒', '镇物'] },
        quick_overview: {
          three_book_anchor: '锚点说明',
          core_question: '核心问题说明',
          key_takeaways: ['要点一', '要点二', '要点三'],
        },
        editorial_intro: {
          heading: '导言标题',
          epigraph_thesis: '导言题旨',
          paragraphs: ['导言一', '导言二'],
          lenses: ['视域甲'],
        },
        groups: [
          {
            id: 'grp_expand',
            title: '可展开测试组',
            tldr: '一句话看懂本组内容。',
            chapter_intro: '章回导读。',
            description: '组描述。',
            hub_ids: ['n1', 'n2'],
            featured_nodes: ['n3', 'n4', 'n5', 'n6', 'n7', 'n8'],
            lexicon_categories: ['蛊毒'],
          },
          {
            id: 'grp_other',
            title: '另一专题组',
            tldr: '另一组导读。',
            chapter_intro: '二组导读。',
            description: '二组描述。',
            hub_ids: ['n2'],
            featured_nodes: [],
            lexicon_categories: ['镇物'],
          },
        ],
        sample_classified_nodes: [
          { id: 'sample_1', title: '全库既有节点甲', z_layer: 2, genre: 'academic_model' },
        ],
      },
    ],
  };

  const state = {
    scopeTab: 'taxonomy',
    taxonomyLoading: false,
    taxonomySelectedDomainId: null,
    taxonomyLexiconQuery: '',
    taxonomyLexiconCategory: '',
    taxonomyShardState: new Map([
      ['wugu_talisman', {
        loading: false,
        error: '',
        data: {
          sha256: 'a'.repeat(64),
          entries: [
            {
              id: 'lex_1',
              hub_id: 'n1',
              term: '金蚕蛊',
              reviewed_by_human: false,
              reading_tag: '史料档案',
              gist: '蓄蛊致富传闻与官律制裁',
              category: '蛊毒',
              region: '福建',
              era: '宋元',
              summary: '释义第一段。\n\n释义第二段。',
              primary_sources: [
                { citation: '《宋史》', url: 'https://zh.wikisource.org/' },
                { citation: '邓启耀：《巫蛊》', locator: '第三章', url: 'https://book.douban.com/subject/37310453/' },
              ],
            },
            {
              id: 'lex_2',
              hub_id: 'n2',
              term: '泰山石敢当',
              reading_tag: '器物民俗',
              gist: '巷口立石镇煞之俗',
              category: '镇物',
              region: '山东',
              era: '明清',
              summary: '镇煞石碑释义。',
              primary_sources: [{ citation: '陶思炎：《中国镇物》', locator: '第 88 页', url: null }],
            },
          ],
        },
      }],
    ]),
  };

  let selectedDomainCalls = [];
  let selectedNodeCalls = [];
  let searchCalls = [];

  // 1. Landing view
  renderTaxonomyExplorerView({
    container,
    taxonomy,
    state,
    onSelectDomain: (id) => selectedDomainCalls.push(id),
    onSelectNode: (id) => selectedNodeCalls.push(id),
    onSearchQuery: (q) => searchCalls.push(q),
  });
  assert.equal(container.hidden, false);
  assert.match(container.innerHTML, /11,778 \/ 11,778/);
  assert.match(container.innerHTML, /精选 8 · 自动归类 155 · 辞条 2/);
  container.querySelector('[data-taxonomy-domain="wugu_talisman"]')?.click();
  assert.deepEqual(selectedDomainCalls, ['wugu_talisman']);

  // 2. Domain view
  state.taxonomySelectedDomainId = 'wugu_talisman';
  renderTaxonomyExplorerView({
    container,
    taxonomy,
    state,
    onSelectDomain: (id) => selectedDomainCalls.push(id),
    onSelectNode: (id) => selectedNodeCalls.push(id),
    onSearchQuery: (q) => searchCalls.push(q),
    resolveNodeLabel: (id) => ({ title: `节点_${id}`, layer: 'L1' }),
  });

  assert.ok(state.taxonomyExpandedGroups instanceof Set);
  assert.match(container.innerHTML, /taxonomy-quick-overview/);
  assert.match(container.innerHTML, /展开导言与方法论总论/);
  assert.doesNotMatch(container.innerHTML, /<details class="taxonomy-editorial-card" open>/);
  assert.match(container.innerHTML, /一句话看懂/);
  assert.match(container.innerHTML, /\+ 展开其余 2 条/);
  assert.match(container.innerHTML, /筛看本组辞条 ↓/);
  assert.match(container.innerHTML, /自动归类的既有条目.*待复核/);
  const listSlot = container.querySelector('[data-taxonomy-lexicon-list]');
  assert.ok(listSlot);
  assert.match(listSlot.innerHTML, /来源链接/);
  assert.match(listSlot.innerHTML, /出处信息/);
  assert.match(listSlot.innerHTML, /定位：/);
  assert.doesNotMatch(listSlot.innerHTML, /公版一次出处/);
  assert.match(listSlot.innerHTML, /史料档案/);
  assert.match(listSlot.innerHTML, /待人工复核/);
  assert.match(listSlot.innerHTML, /蓄蛊致富传闻与官律制裁/);

  // 3. Toggle group chips expansion in-place
  const toggleBtn = container.querySelector('[data-taxonomy-toggle-btn]');
  toggleBtn.click();
  assert.equal(state.taxonomyExpandedGroups.has('grp_expand'), true);
  const chipsSlot = container.querySelector('[data-taxonomy-group-chips="grp_expand"]');
  assert.equal(chipsSlot.querySelectorAll('[data-taxonomy-node]').length, 8);

  // 4. Filter by group in-place
  const groupFilterBtn = container.querySelector('[data-taxonomy-group-filter="grp_expand"]');
  groupFilterBtn.click();
  assert.equal(state.taxonomyLexiconCategory, '__group__:grp_expand');
  assert.match(listSlot.innerHTML, /金蚕蛊/);
  assert.doesNotMatch(listSlot.innerHTML, /泰山石敢当/);

  // 5. Live search input updates list without replacing container
  const searchInput = container.querySelector('#taxonomy-lexicon-search');
  searchInput.value = '石敢当';
  state.taxonomyLexiconCategory = '';
  searchInput.dispatchEvent({ type: 'input' });
  assert.deepEqual(searchCalls, ['石敢当']);
  renderTaxonomyLexiconEntriesView({
    container,
    domain: taxonomy.domains[0],
    state,
    onSelectNode: (id) => selectedNodeCalls.push(id),
  });
  assert.match(listSlot.innerHTML, /泰山石敢当/);
  assert.doesNotMatch(listSlot.innerHTML, /金蚕蛊/);
});

test('fullAtlas.js and overrides.css include Phase 7 readability classes and source distinction', async () => {
  const [fullAtlasSrc, cssSrc] = await Promise.all([
    readText('../src/syzygy/fullAtlas.js'),
    readText('../src/syzygy/overrides.css'),
  ]);
  for (const token of ['reading_tag', 'gist', 'taxonomy-reading-tag', 'taxonomy-lexicon-gist', 'taxonomy-locator-note', '来源链接', '出处信息']) {
    assert.ok(fullAtlasSrc.includes(token), `fullAtlas.js missing readability token ${token}`);
  }
  for (const selector of [
    '.taxonomy-quick-overview',
    '.taxonomy-tldr-bar',
    '.taxonomy-reading-tag',
    '.taxonomy-lexicon-gist',
    '.taxonomy-classified-strip',
    '.taxonomy-locator-note',
    '.taxonomy-group-toggle',
  ]) {
    assert.ok(cssSrc.includes(selector), `overrides.css missing selector ${selector}`);
  }
});
