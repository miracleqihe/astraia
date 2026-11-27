import { filterLexiconEntries } from './lexiconShards.js';

function defaultEscapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char]);
}

function defaultFormatBibliographyNote(taxonomy) {
  const items = Array.isArray(taxonomy?.bibliography) ? taxonomy.bibliography : [];
  const citations = items
    .map((item) => (typeof item === 'string' ? item : (item?.citation || item?.title || '')))
    .filter(Boolean);
  const baseNote = '辞条按所列资料整理；出处与定位见各条，部分材料仍待进一步核对。';
  return citations.length ? `${baseNote} 书目参照：${citations.join('；')}。` : baseNote;
}

function safeAccent(value) {
  const trimmed = String(value ?? '').trim();
  return /^#[0-9a-fA-F]{3,8}$/.test(trimmed) ? trimmed : '#cfa962';
}

function safeExtUrl(value) {
  const trimmed = String(value ?? '').trim();
  return /^https?:\/\//i.test(trimmed) ? trimmed : null;
}

function ensureExpandedGroupsSet(state) {
  if (!state || typeof state !== 'object') return new Set();
  if (!(state.taxonomyExpandedGroups instanceof Set)) {
    state.taxonomyExpandedGroups = new Set();
  }
  return state.taxonomyExpandedGroups;
}

function extractFirstSentence(text, maxLen = 58) {
  const flat = String(text ?? '').replace(/\s+/g, ' ').trim();
  if (!flat) return '';
  const first = flat.split(/(?<=[。！？!?；;])/).map((s) => s.trim()).find(Boolean) || flat;
  return first.length <= maxLen ? first : `${first.slice(0, maxLen - 1)}…`;
}

function resolveQuickOverview(domain) {
  const q = domain?.quick_overview;
  if (q && typeof q === 'object' && !Array.isArray(q)) {
    const anchor = typeof q.three_book_anchor === 'string' ? q.three_book_anchor.trim() : '';
    const question = typeof q.core_question === 'string' ? q.core_question.trim() : '';
    const takeaways = Array.isArray(q.key_takeaways)
      ? q.key_takeaways.map((item) => String(item ?? '').trim()).filter(Boolean).slice(0, 3)
      : [];
    if (anchor || question || takeaways.length) {
      return {
        threeBookAnchor: anchor || domain.subtitle || domain.name,
        coreQuestion: question || domain.editorial_intro?.epigraph_thesis || domain.summary || '',
        keyTakeaways: takeaways.length
          ? takeaways
          : (domain.editorial_intro?.lenses ?? []).slice(0, 3),
      };
    }
  }
  const intro = domain?.editorial_intro && typeof domain.editorial_intro === 'object'
    ? domain.editorial_intro
    : null;
  const groupTitles = (domain?.groups ?? []).slice(0, 3).map((g) => g.title).filter(Boolean);
  const lenses = Array.isArray(intro?.lenses) ? intro.lenses.filter(Boolean) : [];
  return {
    threeBookAnchor: domain?.subtitle || domain?.english_name || domain?.name || '',
    coreQuestion: intro?.epigraph_thesis || extractFirstSentence(domain?.summary, 72),
    keyTakeaways: (lenses.length >= 2 ? lenses : groupTitles).slice(0, 3),
  };
}

function parseGroupFilterId(categoryValue) {
  const text = String(categoryValue ?? '');
  return text.startsWith('__group__:') ? text.slice('__group__:'.length) : '';
}

function filterEntriesForDomainView(entries, domain, query, categoryOrGroup) {
  const groupId = parseGroupFilterId(categoryOrGroup);
  if (!groupId) {
    return filterLexiconEntries(entries, query, categoryOrGroup);
  }
  const base = filterLexiconEntries(entries, query, '');
  const groups = Array.isArray(domain?.groups) ? domain.groups : [];
  const targetGroup = groups.find((g) => g.id === groupId);
  if (!targetGroup) return base;

  const targetCats = new Set((targetGroup.lexicon_categories ?? []).map((c) => c.trim()).filter(Boolean));
  const targetHubs = new Set((targetGroup.hub_ids ?? []).filter(Boolean));
  const otherGroupCats = new Set();
  for (const grp of groups) {
    if (grp.id === groupId) continue;
    for (const cat of grp.lexicon_categories ?? []) {
      if (cat && !targetCats.has(cat)) otherGroupCats.add(cat.trim());
    }
  }

  return base.filter((entry) => {
    const cat = String(entry.category ?? '').trim();
    if (targetCats.has(cat)) return true;
    if (targetHubs.has(entry.hub_id) && !otherGroupCats.has(cat)) return true;
    return false;
  });
}

function renderLexiconSourceItems(primarySources, escapeHTML) {
  return (primarySources ?? []).map((src) => {
    const url = safeExtUrl(src?.url);
    const citation = String(src?.citation ?? '').trim();
    const locator = String(src?.locator ?? '').trim();
    if (url) {
      return `<div class="taxonomy-source-item">
        <span class="taxonomy-source-kind is-public">来源链接</span>
        <a class="taxonomy-source-url" href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(citation || url)} ↗</a>
        ${locator ? `<span class="taxonomy-locator-note">定位：${escapeHTML(locator)}</span>` : ''}
      </div>`;
    }
    return `<div class="taxonomy-source-item">
      <span class="taxonomy-source-kind">出处信息</span>
      <span class="taxonomy-source-citation">${escapeHTML(citation || '未注明出处')}</span>
      ${locator ? `<span class="taxonomy-locator-note">定位：${escapeHTML(locator)}</span>` : ''}
    </div>`;
  }).join('');
}

function buildGroupChipsHTML(nodeIds, expanded, resolveNodeLabel, escapeHTML) {
  const visibleIds = expanded ? nodeIds : nodeIds.slice(0, 6);
  const chipsHTML = visibleIds.map((id) => {
    const info = resolveNodeLabel(id) ?? { title: id, layer: '节点' };
    return `<button type="button" class="taxonomy-node-chip" data-taxonomy-node="${escapeHTML(id)}">
      <small>${escapeHTML(info.layer ?? '节点')}</small>
      <span>${escapeHTML(info.title ?? id)}</span>
    </button>`;
  }).join('');
  const remaining = nodeIds.length - 6;
  const toggleHTML = remaining > 0
    ? `<button type="button" class="taxonomy-group-toggle" data-taxonomy-toggle-btn aria-expanded="${String(expanded)}">${expanded ? `收起其余 ${remaining} 条` : `+ 展开其余 ${remaining} 条`}</button>`
    : '';
  return { chipsHTML, toggleHTML };
}

export function renderTaxonomyLexiconEntriesView({
  container,
  domain,
  state,
  root = './',
  bookEntries = [],
  onSelectNode,
  onRetryShard,
  resolveNodeLabel = (id) => ({ title: id, layer: '节点' }),
  escapeHTML = defaultEscapeHTML,
}) {
  if (!container || !domain) return;
  const listSlot = container.querySelector('[data-taxonomy-lexicon-list]');
  const countSlot = container.querySelector('[data-taxonomy-lexicon-count]');
  if (!listSlot) return;

  const shardState = state?.taxonomyShardState?.get(domain.id);
  if (!domain.lexicon_shard) return;
  if (!shardState || shardState.loading) {
    listSlot.innerHTML = '<p class="syzygy-reference">正在校验 SHA-256 并载入专题辞条分片…</p>';
    return;
  }
  if (shardState.error) {
    listSlot.innerHTML = `<p class="syzygy-reference">辞条分片载入失败：${escapeHTML(shardState.error)} <button type="button" class="syzygy-inline-button" data-taxonomy-retry>重试</button></p>`;
    listSlot.querySelector('[data-taxonomy-retry]')?.addEventListener('click', () => {
      onRetryShard?.(domain.id);
    });
    return;
  }

  const entries = shardState.data?.entries ?? [];
  const filtered = filterEntriesForDomainView(
    entries,
    domain,
    state?.taxonomyLexiconQuery ?? '',
    state?.taxonomyLexiconCategory ?? '',
  );

  if (countSlot) {
    countSlot.textContent = filtered.length === entries.length
      ? `${entries.length} 辞条`
      : `${filtered.length} / ${entries.length} 辞条`;
  }

  if (!filtered.length) {
    listSlot.innerHTML = '<p class="syzygy-reference">没有匹配当前筛选条件的辞条。</p>';
    return;
  }

  listSlot.innerHTML = filtered.map((entry) => {
    const meta = [entry.category, entry.region, entry.era].filter(Boolean).join(' · ');
    const readingTagHTML = entry.reading_tag
      ? `<span class="taxonomy-reading-tag">${escapeHTML(entry.reading_tag)}</span>`
      : '';
    const gistHTML = entry.gist
      ? `<span class="taxonomy-lexicon-gist">${escapeHTML(entry.gist)}</span>`
      : '';
    const aliases = Array.isArray(entry.aliases) && entry.aliases.length
      ? `<div class="taxonomy-lexicon-aliases">别称：${escapeHTML(entry.aliases.join('、'))}</div>`
      : '';
    const sourcesHTML = renderLexiconSourceItems(entry.primary_sources, escapeHTML);
    const hubChip = entry.hub_id
      ? `<button type="button" class="taxonomy-node-chip" data-taxonomy-node="${escapeHTML(entry.hub_id)}"><span>关联枢纽：${escapeHTML(resolveNodeLabel(entry.hub_id)?.title ?? entry.hub_id)}</span><small>定位</small></button>`
      : '';
    const storyChip = entry.case_id
      ? `<a class="taxonomy-node-chip" href="${escapeHTML(root)}?view=map&amp;story=${encodeURIComponent(entry.case_id)}"><span>地图故事</span><small>查看 ↗</small></a>`
      : '';
    const relatedBook = entry.knowledge_id
      ? (bookEntries ?? []).find((item) => item.id === entry.knowledge_id)
      : null;
    const knowledgeChip = relatedBook
      ? `<button type="button" class="taxonomy-node-chip" data-taxonomy-node="${escapeHTML(entry.knowledge_id)}"><span>知识对读：${escapeHTML(relatedBook.title)}</span><small>主题关联</small></button>`
      : '';
    const secondary = entry.secondary_ref
      ? `<div class="taxonomy-lexicon-secondary">参考资料：${escapeHTML(entry.secondary_ref)}</div>`
      : '';

    return `<details class="taxonomy-lexicon-card">
      <summary>
        <div class="taxonomy-lexicon-summary-main">
          <div class="taxonomy-lexicon-title-row">
            <span class="taxonomy-lexicon-term">${escapeHTML(entry.term)}</span>
            ${readingTagHTML}
            ${entry.reviewed_by_human === false ? '<span class="taxonomy-reading-tag">待人工复核</span>' : ''}
          </div>
          ${gistHTML}
        </div>
        <span class="taxonomy-lexicon-meta">${escapeHTML(meta)}</span>
      </summary>
      <div class="taxonomy-lexicon-body">
        ${aliases}
        ${String(entry.summary ?? '').split(/\n\s*\n/).filter(Boolean).map((p) => `<p>${escapeHTML(p)}</p>`).join('')}
        ${hubChip || storyChip || knowledgeChip ? `<div class="taxonomy-node-chips">${hubChip}${storyChip}${knowledgeChip}</div>` : ''}
        ${entry.knowledge_note ? `<div class="taxonomy-lexicon-secondary">${escapeHTML(entry.knowledge_note)}</div>` : ''}
        ${sourcesHTML ? `<div class="taxonomy-lexicon-sources">${sourcesHTML}</div>` : ''}
        ${secondary}
      </div>
    </details>`;
  }).join('');

  listSlot.querySelectorAll('[data-taxonomy-node]').forEach((btn) => {
    btn.addEventListener('click', () => onSelectNode?.(btn.dataset.taxonomyNode));
  });
}

export function renderTaxonomyExplorerView({
  container,
  taxonomy,
  state,
  root = './',
  bookEntries = [],
  onClose,
  onSelectDomain,
  onSelectNode,
  onSearchQuery,
  onSelectCategory,
  onFocusSidera,
  onRetryShard,
  resolveNodeLabel = (id) => ({ title: id, layer: '节点' }),
  escapeHTML = defaultEscapeHTML,
  formatBibliographyNote = defaultFormatBibliographyNote,
}) {
  if (!container) return;
  const hidden = state?.scopeTab !== 'taxonomy';
  container.hidden = hidden;
  if (hidden) return;

  const expandedGroups = ensureExpandedGroupsSet(state);
  const domains = Array.isArray(taxonomy?.domains)
    ? [...taxonomy.domains].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
    : [];
  const selectedDomain = domains.find((item) => item.id === state?.taxonomySelectedDomainId) ?? null;

  const headHTML = `<header class="taxonomy-explorer-head">
    <div>
      <div class="taxonomy-explorer-eyebrow">THEMATIC TAXONOMY · 七大专题谱系</div>
      <h2 class="taxonomy-explorer-title">中国鬼神与跨文化民俗专题谱系总览</h2>
    </div>
    <button type="button" id="btn-close-taxonomy" class="ctl-btn px-2.5 py-1 text-xs">✕ 返回星图</button>
  </header>`;

  if (!taxonomy && state?.taxonomyLoading) {
    container.innerHTML = `${headHTML}<div class="taxonomy-detail-pane"><p class="syzygy-reference">正在载入七大专题谱系索引…</p></div>`;
    container.querySelector('#btn-close-taxonomy')?.addEventListener('click', () => onClose?.());
    return;
  }

  if (!taxonomy || !domains.length) {
    container.innerHTML = `${headHTML}<div class="taxonomy-detail-pane"><p class="syzygy-reference">专题谱系索引暂不可用或尚未编译，请稍后重试，或继续在星图与典籍中浏览。</p></div>`;
    container.querySelector('#btn-close-taxonomy')?.addEventListener('click', () => onClose?.());
    return;
  }

  const domainCardsHTML = domains.map((domain) => {
    const isSel = selectedDomain?.id === domain.id;
    const accent = safeAccent(domain.accent);
    const groupTags = (domain.groups ?? []).map((group) => `<span class="taxonomy-tag">${escapeHTML(group.title)}</span>`).join('');
    const curatedCount = domain.node_count ?? 0;
    const classifiedCount = Number.isInteger(domain.classified_node_count)
      ? domain.classified_node_count
      : curatedCount;
    const lexText = domain.lexicon_shard
      ? `${domain.lexicon_count ?? domain.lexicon_shard.count}`
      : '待编纂';
    const countsLabel = `精选 ${curatedCount} · 自动归类 ${classifiedCount.toLocaleString()} · 辞条 ${lexText}`;
    return `<button type="button" class="taxonomy-domain-card${isSel ? ' is-selected' : ''}" data-taxonomy-domain="${escapeHTML(domain.id)}">
      <span class="taxonomy-domain-accent" style="background:${accent}"></span>
      <div class="taxonomy-domain-top">
        <span class="taxonomy-domain-order">${String(domain.order ?? '').padStart(2, '0')} · ${escapeHTML(domain.english_name)}</span>
      </div>
      <div class="taxonomy-domain-name">${escapeHTML(domain.name)}</div>
      <div class="taxonomy-domain-en">${escapeHTML(domain.subtitle || domain.english_name)}</div>
      <p class="taxonomy-domain-summary">${escapeHTML(domain.summary)}</p>
      ${groupTags ? `<div class="taxonomy-domain-tags">${groupTags}</div>` : ''}
      <div class="taxonomy-domain-metrics">
        <span class="taxonomy-metric-pill${domain.lexicon_shard ? '' : ' is-planned'}">${escapeHTML(countsLabel)}</span>
      </div>
    </button>`;
  }).join('');

  let detailHTML = '';
  if (!selectedDomain) {
    const coverage = taxonomy.corpus_classification_coverage;
    const coverageHTML = coverage && Number.isInteger(coverage.total_graph_nodes)
      ? `<div class="taxonomy-coverage-banner">
          <span class="taxonomy-metric-pill">自动归类：${escapeHTML(String(coverage.total_classified_unique?.toLocaleString() ?? coverage.total_graph_nodes.toLocaleString()))} / ${escapeHTML(coverage.total_graph_nodes.toLocaleString())} 节点 · 分类结果待复核</span>
        </div>`
      : '';
    const preface = taxonomy.editorial_preface && typeof taxonomy.editorial_preface === 'object'
      ? taxonomy.editorial_preface
      : null;
    let prefaceHTML = '';
    if (preface && (preface.title || (Array.isArray(preface.paragraphs) && preface.paragraphs.length))) {
      const prefaceParagraphsHTML = (Array.isArray(preface.paragraphs) ? preface.paragraphs : [])
        .filter((p) => typeof p === 'string' && p.trim())
        .map((p) => `<p>${escapeHTML(p.trim())}</p>`)
        .join('');
      const principlesHTML = (Array.isArray(preface.principles) ? preface.principles : [])
        .filter((item) => item && typeof item === 'object' && (item.label || item.text))
        .map((item) => `<div class="taxonomy-principle-card">
          <div class="taxonomy-principle-label">${escapeHTML(item.label ?? '')}</div>
          <p class="taxonomy-principle-text">${escapeHTML(item.text ?? '')}</p>
        </div>`)
        .join('');
      prefaceHTML = `<article class="taxonomy-preface-card">
        <div class="taxonomy-explorer-eyebrow">EDITORIAL PREFACE · 编纂总序与方法论</div>
        ${preface.title ? `<h3 class="taxonomy-preface-title">${escapeHTML(preface.title)}</h3>` : ''}
        ${preface.subtitle ? `<p class="taxonomy-preface-subtitle">${escapeHTML(preface.subtitle)}</p>` : ''}
        ${prefaceParagraphsHTML ? `<div class="taxonomy-preface-prose">${prefaceParagraphsHTML}</div>` : ''}
        ${principlesHTML ? `<div class="taxonomy-principles-grid">${principlesHTML}</div>` : ''}
      </article>`;
    }
    detailHTML = `${coverageHTML}${prefaceHTML}
    <div class="taxonomy-detail-hero">
      <div class="taxonomy-explorer-eyebrow">SELECT A DOMAIN · 择域观览</div>
      <h3>七大专题谱系与按需辞条分片</h3>
      <p>请点击左侧任意专题域，先读三栏速览与专题章回的一句话导读，再按需检索校验过 SHA-256 摘要的专题辞条分片。</p>
    </div>
    <div class="taxonomy-bibliography">${escapeHTML(formatBibliographyNote(taxonomy))}</div>`;
  } else {
    const accent = safeAccent(selectedDomain.accent);
    const discPills = (selectedDomain.disciplines ?? []).map((disc) => `<span class="taxonomy-tag">${escapeHTML(disc)}</span>`).join('');
    const quick = resolveQuickOverview(selectedDomain);
    const takeawaysHTML = (quick.keyTakeaways ?? [])
      .map((item) => `<li>${escapeHTML(item)}</li>`)
      .join('');
    const quickOverviewHTML = `<section class="taxonomy-quick-overview" style="border-top-color:${accent}">
      <div class="taxonomy-quick-col">
        <div class="taxonomy-quick-label">三书锚点与谱系坐标</div>
        <p class="taxonomy-quick-text">${escapeHTML(quick.threeBookAnchor)}</p>
      </div>
      <div class="taxonomy-quick-col">
        <div class="taxonomy-quick-label">核心问题</div>
        <p class="taxonomy-quick-text">${escapeHTML(quick.coreQuestion)}</p>
      </div>
      <div class="taxonomy-quick-col">
        <div class="taxonomy-quick-label">一读就懂要点</div>
        ${takeawaysHTML ? `<ul class="taxonomy-quick-list">${takeawaysHTML}</ul>` : '<p class="taxonomy-quick-text">详见下方各章回专题。</p>'}
      </div>
    </section>`;

    const intro = selectedDomain.editorial_intro && typeof selectedDomain.editorial_intro === 'object'
      ? selectedDomain.editorial_intro
      : null;
    let editorialIntroHTML = '';
    if (intro && (intro.heading || intro.epigraph_thesis || (Array.isArray(intro.paragraphs) && intro.paragraphs.length))) {
      const introParagraphsHTML = (Array.isArray(intro.paragraphs) ? intro.paragraphs : [])
        .filter((p) => typeof p === 'string' && p.trim())
        .map((p) => `<p>${escapeHTML(p.trim())}</p>`)
        .join('');
      const lensesHTML = (Array.isArray(intro.lenses) ? intro.lenses : [])
        .filter((tag) => typeof tag === 'string' && tag.trim())
        .map((tag) => `<span class="taxonomy-lens-pill">${escapeHTML(tag.trim())}</span>`)
        .join('');
      editorialIntroHTML = `<details class="taxonomy-editorial-card">
        <summary class="taxonomy-editorial-summary">
          <div>
            <div class="taxonomy-explorer-eyebrow">METHODOLOGICAL INTRO · 导言与方法论总论</div>
            <h4 class="taxonomy-editorial-heading">${escapeHTML(intro.heading || `${selectedDomain.name}导言`)}</h4>
          </div>
          <span class="taxonomy-editorial-toggle" aria-hidden="true">
            <span class="is-open">收起导言 ▴</span>
            <span class="is-closed">展开导言与方法论总论 ▾</span>
          </span>
        </summary>
        <div class="taxonomy-editorial-body">
          ${intro.epigraph_thesis ? `<blockquote class="taxonomy-editorial-epigraph" style="border-left-color:${accent}">${escapeHTML(intro.epigraph_thesis)}</blockquote>` : ''}
          ${introParagraphsHTML ? `<div class="taxonomy-editorial-prose">${introParagraphsHTML}</div>` : ''}
          ${lensesHTML ? `<div class="taxonomy-editorial-lenses"><span class="taxonomy-editorial-lenses-label">理论视域</span>${lensesHTML}</div>` : ''}
        </div>
      </details>`;
    }

    const groupsHTML = (selectedDomain.groups ?? []).map((group, groupIdx) => {
      const nodeIds = [...new Set([...(group.hub_ids ?? []), ...(group.featured_nodes ?? [])])];
      const expanded = expandedGroups.has(group.id);
      const { chipsHTML, toggleHTML } = buildGroupChipsHTML(nodeIds, expanded, resolveNodeLabel, escapeHTML);
      const catsHTML = (group.lexicon_categories ?? []).map((cat) => `<span class="taxonomy-tag">${escapeHTML(cat)}</span>`).join('');
      const tldrText = typeof group.tldr === 'string' && group.tldr.trim()
        ? group.tldr.trim()
        : extractFirstSentence(group.chapter_intro || group.description, 60);
      const tldrHTML = tldrText
        ? `<div class="taxonomy-tldr-bar"><span class="taxonomy-tldr-badge">一句话看懂</span><strong>${escapeHTML(tldrText)}</strong></div>`
        : '';
      const chapterIntroHTML = typeof group.chapter_intro === 'string' && group.chapter_intro.trim()
        ? `<div class="taxonomy-group-lead" style="border-left-color:${accent}">${escapeHTML(group.chapter_intro.trim())}</div>`
        : '';
      const filterBtnHTML = selectedDomain.lexicon_shard
        ? `<button type="button" class="taxonomy-group-filter-btn" data-taxonomy-group-filter="${escapeHTML(group.id)}">筛看本组辞条 ↓</button>`
        : '';

      return `<article class="taxonomy-group-card" data-taxonomy-group-card="${escapeHTML(group.id)}">
        <div class="taxonomy-group-head">
          <span class="taxonomy-group-num">${String(groupIdx + 1).padStart(2, '0')}</span>
          <h4>${escapeHTML(group.title)}</h4>
        </div>
        ${tldrHTML}
        ${chapterIntroHTML}
        <p>${escapeHTML(group.description)}</p>
        ${catsHTML ? `<div class="taxonomy-domain-tags" style="margin-top:6px">${catsHTML}</div>` : ''}
        ${nodeIds.length ? `<div class="taxonomy-node-chips" data-taxonomy-group-chips="${escapeHTML(group.id)}">${chipsHTML}</div>` : ''}
        ${toggleHTML || filterBtnHTML ? `<div class="taxonomy-group-actions">${toggleHTML}${filterBtnHTML}</div>` : ''}
      </article>`;
    }).join('');

    const sampleNodes = Array.isArray(selectedDomain.sample_classified_nodes)
      ? selectedDomain.sample_classified_nodes
      : [];
    const totalCorpusCount = taxonomy.corpus_classification_coverage?.total_graph_nodes;
    const totalLabel = Number.isInteger(totalCorpusCount)
      ? `${totalCorpusCount.toLocaleString()}`
      : '11,778+';
    const classifiedDomainCount = Number.isInteger(selectedDomain.classified_node_count)
      ? selectedDomain.classified_node_count
      : (selectedDomain.node_count ?? 0);
    const sampleStripHTML = sampleNodes.length
      ? `<section class="taxonomy-classified-strip">
          <div class="taxonomy-classified-head">
            <div>
              <div class="taxonomy-explorer-eyebrow">CORPUS DISCOVERY · 全库自动归类</div>
              <h4>自动归类的既有条目（全库 ${escapeHTML(totalLabel)} 条 · 本域 ${escapeHTML(classifiedDomainCount.toLocaleString())} 条，待复核）</h4>
            </div>
          </div>
          <div class="taxonomy-node-chips">
            ${sampleNodes.map((node) => `<button type="button" class="taxonomy-node-chip" data-taxonomy-node="${escapeHTML(node.id)}">
              <small>L${escapeHTML(String(node.z_layer ?? '—'))}</small>
              <span>${escapeHTML(node.title || node.id)}</span>
            </button>`).join('')}
          </div>
        </section>`
      : '';

    let lexiconSectionHTML = '';
    if (!selectedDomain.lexicon_shard) {
      lexiconSectionHTML = `<section class="taxonomy-lexicon-panel">
        <div class="taxonomy-lexicon-head">
          <div>
            <div class="taxonomy-explorer-eyebrow">LEXICON SHARD · 专题辞条分片</div>
            <h4 class="text-sm font-semibold text-[#f5eedc] mt-0.5">规划中波次 · 暂未载入分片</h4>
          </div>
          <span class="taxonomy-metric-pill is-planned">后续波次编纂</span>
        </div>
        <p class="syzygy-reference" style="margin-top:8px">本专题域的辞条分片尚未发布；您仍可通过上方「谱系分组」点击核心节点芯片直接跳转星图与卷宗研读。</p>
      </section>`;
    } else {
      const shardState = state?.taxonomyShardState?.get(selectedDomain.id);
      const loadedEntries = shardState?.data?.entries ?? [];
      const rawCategories = selectedDomain.lexicon_shard.categories?.length
        ? selectedDomain.lexicon_shard.categories
        : [...new Set(loadedEntries.map((item) => item.category).filter(Boolean))];
      const currentCategory = state?.taxonomyLexiconCategory ?? '';
      const activeGroupId = parseGroupFilterId(currentCategory);
      const activeGroupTitle = activeGroupId
        ? (selectedDomain.groups ?? []).find((g) => g.id === activeGroupId)?.title ?? activeGroupId
        : '';
      const activeGroupBannerHTML = activeGroupTitle
        ? `<div class="taxonomy-active-group-filter" data-taxonomy-active-group>
            <span>当前仅看专题组：<strong>${escapeHTML(activeGroupTitle)}</strong></span>
            <button type="button" class="taxonomy-cat-chip" data-taxonomy-cat="">显示全部辞条 ✕</button>
          </div>`
        : `<div class="taxonomy-active-group-filter" data-taxonomy-active-group hidden></div>`;
      const catChipsHTML = rawCategories.length
        ? `<div class="taxonomy-category-bar" role="group" aria-label="辞条分类筛选">
            <button type="button" class="taxonomy-cat-chip" data-taxonomy-cat="" aria-pressed="${currentCategory === ''}">全部</button>
            ${rawCategories.map((cat) => `<button type="button" class="taxonomy-cat-chip" data-taxonomy-cat="${escapeHTML(cat)}" aria-pressed="${currentCategory === cat}">${escapeHTML(cat)}</button>`).join('')}
          </div>`
        : '';
      const shaShort = (shardState?.data?.sha256 || selectedDomain.lexicon_shard.sha256 || '').slice(0, 12);
      lexiconSectionHTML = `<section class="taxonomy-lexicon-panel">
        <div class="taxonomy-lexicon-head">
          <div>
            <div class="taxonomy-explorer-eyebrow">LEXICON SHARD · 专题辞条分片</div>
            <h4 class="text-sm font-semibold text-[#f5eedc] mt-0.5">${escapeHTML(selectedDomain.name)} · 辞条检索</h4>
          </div>
          <div class="flex items-center gap-1.5">
            ${shaShort ? `<span class="taxonomy-tag font-mono-tech">SHA ${escapeHTML(shaShort)}</span>` : ''}
            <span class="taxonomy-metric-pill" data-taxonomy-lexicon-count>${escapeHTML(String(selectedDomain.lexicon_count ?? selectedDomain.lexicon_shard.count))} 辞条</span>
          </div>
        </div>
        <div class="taxonomy-lexicon-controls">
          <input id="taxonomy-lexicon-search" class="syzygy-portal-search" type="search" value="${escapeHTML(state?.taxonomyLexiconQuery ?? '')}" placeholder="检索辞条、别名、地域、时代或释义..." autocomplete="off">
          ${activeGroupBannerHTML}
          ${catChipsHTML}
        </div>
        <div class="taxonomy-lexicon-list" data-taxonomy-lexicon-list></div>
        <div class="taxonomy-bibliography">${escapeHTML(formatBibliographyNote(taxonomy))}</div>
      </section>`;
    }

    const curatedCount = selectedDomain.node_count ?? 0;
    const classifiedCount = Number.isInteger(selectedDomain.classified_node_count)
      ? selectedDomain.classified_node_count
      : curatedCount;
    detailHTML = `<div class="taxonomy-detail-hero" style="border-left-color:${accent}">
      <div class="taxonomy-explorer-eyebrow">${String(selectedDomain.order ?? '').padStart(2, '0')} · ${escapeHTML(selectedDomain.english_name)}</div>
      <h3>${escapeHTML(selectedDomain.name)}</h3>
      <div class="taxonomy-domain-tags" style="margin-top:6px">
        <span class="taxonomy-metric-pill">精选 ${escapeHTML(String(curatedCount))} · 自动归类 ${escapeHTML(classifiedCount.toLocaleString())} 节点</span>
        ${discPills}
        ${selectedDomain.sidera_id ? `<button type="button" class="taxonomy-node-chip" data-taxonomy-sidera="${escapeHTML(selectedDomain.sidera_id)}">定位玄象星群 ↗</button>` : ''}
      </div>
      <p>${escapeHTML(selectedDomain.summary)}</p>
    </div>
    ${quickOverviewHTML}
    ${editorialIntroHTML}
    <section>
      <div class="taxonomy-explorer-eyebrow mb-2">SPECTRAL GROUPS · 专题章回与核心节点</div>
      <div class="taxonomy-group-grid">${groupsHTML}</div>
    </section>
    ${sampleStripHTML}
    ${lexiconSectionHTML}`;
  }

  container.innerHTML = `${headHTML}
    <div class="taxonomy-explorer-body">
      <div class="taxonomy-domain-list astro-scroll">${domainCardsHTML}</div>
      <div class="taxonomy-detail-pane astro-scroll">${detailHTML}</div>
    </div>`;

  container.querySelector('#btn-close-taxonomy')?.addEventListener('click', () => onClose?.());
  container.querySelectorAll('[data-taxonomy-domain]').forEach((btn) => {
    btn.addEventListener('click', () => onSelectDomain?.(btn.dataset.taxonomyDomain));
  });
  container.querySelectorAll('[data-taxonomy-node]').forEach((btn) => {
    btn.addEventListener('click', () => onSelectNode?.(btn.dataset.taxonomyNode));
  });
  container.querySelector('[data-taxonomy-sidera]')?.addEventListener('click', (event) => {
    onFocusSidera?.(event.currentTarget.dataset.taxonomySidera);
  });

  if (selectedDomain) {
    container.querySelectorAll('[data-taxonomy-group-card]').forEach((card) => {
      const groupId = card.dataset.taxonomyGroupCard;
      const group = (selectedDomain.groups ?? []).find((g) => g.id === groupId);
      const toggleBtn = card.querySelector('[data-taxonomy-toggle-btn]');
      const chipsSlot = card.querySelector('[data-taxonomy-group-chips]');
      if (group && toggleBtn && chipsSlot) {
        const nodeIds = [...new Set([...(group.hub_ids ?? []), ...(group.featured_nodes ?? [])])];
        toggleBtn.addEventListener('click', () => {
          const nextExpanded = !expandedGroups.has(groupId);
          if (nextExpanded) expandedGroups.add(groupId);
          else expandedGroups.delete(groupId);
          const { chipsHTML } = buildGroupChipsHTML(nodeIds, nextExpanded, resolveNodeLabel, escapeHTML);
          chipsSlot.innerHTML = chipsHTML;
          const remaining = nodeIds.length - 6;
          toggleBtn.setAttribute('aria-expanded', String(nextExpanded));
          toggleBtn.textContent = nextExpanded ? `收起其余 ${remaining} 条` : `+ 展开其余 ${remaining} 条`;
          chipsSlot.querySelectorAll('[data-taxonomy-node]').forEach((btn) => {
            btn.addEventListener('click', () => onSelectNode?.(btn.dataset.taxonomyNode));
          });
        });
      }
    });
  }

  if (selectedDomain?.lexicon_shard) {
    const syncCategoryUI = (nextCat) => {
      if (state) state.taxonomyLexiconCategory = nextCat;
      container.querySelectorAll('[data-taxonomy-cat]').forEach((chip) => {
        chip.setAttribute('aria-pressed', String((chip.dataset.taxonomyCat ?? '') === nextCat));
      });
      const groupBanner = container.querySelector('[data-taxonomy-active-group]');
      const gId = parseGroupFilterId(nextCat);
      if (groupBanner) {
        if (gId) {
          const gTitle = (selectedDomain.groups ?? []).find((g) => g.id === gId)?.title ?? gId;
          groupBanner.hidden = false;
          groupBanner.innerHTML = `<span>当前仅看专题组：<strong>${escapeHTML(gTitle)}</strong></span>
            <button type="button" class="taxonomy-cat-chip" data-taxonomy-cat="">显示全部辞条 ✕</button>`;
          groupBanner.querySelector('[data-taxonomy-cat]')?.addEventListener('click', () => {
            syncCategoryUI('');
            onSelectCategory?.('');
            renderTaxonomyLexiconEntriesView({
              container, domain: selectedDomain, state, root, bookEntries,
              onSelectNode, onRetryShard, resolveNodeLabel, escapeHTML,
            });
          });
        } else {
          groupBanner.hidden = true;
          groupBanner.innerHTML = '';
        }
      }
    };

    const searchEl = container.querySelector('#taxonomy-lexicon-search');
    searchEl?.addEventListener('input', () => {
      if (state) state.taxonomyLexiconQuery = searchEl.value;
      onSearchQuery?.(searchEl.value);
      renderTaxonomyLexiconEntriesView({
        container, domain: selectedDomain, state, root, bookEntries,
        onSelectNode, onRetryShard, resolveNodeLabel, escapeHTML,
      });
    });

    container.querySelectorAll('[data-taxonomy-cat]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const clicked = btn.dataset.taxonomyCat ?? '';
        const current = state?.taxonomyLexiconCategory ?? '';
        const nextCat = current === clicked ? '' : clicked;
        syncCategoryUI(nextCat);
        onSelectCategory?.(nextCat);
        renderTaxonomyLexiconEntriesView({
          container, domain: selectedDomain, state, root, bookEntries,
          onSelectNode, onRetryShard, resolveNodeLabel, escapeHTML,
        });
      });
    });

    container.querySelectorAll('[data-taxonomy-group-filter]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const groupId = btn.dataset.taxonomyGroupFilter;
        const nextCat = `__group__:${groupId}`;
        syncCategoryUI(nextCat);
        onSelectCategory?.(nextCat);
        renderTaxonomyLexiconEntriesView({
          container, domain: selectedDomain, state, root, bookEntries,
          onSelectNode, onRetryShard, resolveNodeLabel, escapeHTML,
        });
        container.querySelector('.taxonomy-lexicon-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });

    renderTaxonomyLexiconEntriesView({
      container, domain: selectedDomain, state, root, bookEntries,
      onSelectNode, onRetryShard, resolveNodeLabel, escapeHTML,
    });
  }
}
