import { publicAssetUrl } from '../publicAssetUrl.js';
import { isCompactViewport } from '../compactViewport';
import * as THREE from 'three';
import { loadGraph, matchesGraph } from './graphBridge';
import { loadPortalMatches } from './portalMatches';
import { handbookText, bookNavigation, bindBookNavigation } from './readable';
import { createReadingShards } from './readingShards';
import { loadTaxonomy, loadLexiconShard, getHubLexiconInfo, filterLexiconEntries } from './lexiconShards.js';
import { genreContract, narrativeDisplay } from './narrativeMetadata';
import { storyShare, bindStoryShare } from './sharing';
import { originalPageButton, bindOriginalPages } from './originalPages';
import { engravingHeader, engravingBeam, engravingFrieze, engravingPatternForVolume, bindEngravingBeam } from '../engraving';
import { resolvePrismForPair, renderPrismPhilosophyHTML, bindSensoryLabs } from './philosophicalPrism';

const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const hasCoordinates = node => Number.isFinite(node.spatial?.lat) && Number.isFinite(node.spatial?.lng)
  && Math.abs(node.spatial.lat) <= 90 && Math.abs(node.spatial.lng) <= 180;
const isFiction = node => node.credibility_tier === 'F' || node.is_fictional_quarantine;
const sourceList = node => {
  const sources = node?.sources ?? [];
  if (!sources.length) return '<p class="syzygy-reference">本条暂无可展示的出处。</p>';
  return `<ul class="syzygy-source-list">${sources.map(source => {
    const label = escape(source.citation || source.url || source.doi || source.type || '出处');
    const url = /^https?:\/\//i.test(source.url ?? '') ? source.url : null;
    return `<li>${url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${label} ↗</a>` : label}${source.locator ? ` · ${escape(source.locator)}` : ''}</li>`;
  }).join('')}</ul>`;
};
const codePills = node => Object.entries({ atu_types:'ATU', thompson_motifs:'汤普森', berezkin_codes:'别列兹金', ocm_codes:'OCM' })
  .flatMap(([key, label]) => (node.standards?.[key] ?? []).map(code => `<span class="syzygy-code">${label} ${escape(code)}</span>`)).join('');
const statusLabel = status => ({ confirmed:'✓ 已证实', unverified:'? 待核实', contested:'? 有争议', refuted:'✕ 已驳回' })[status] || '关联';
const statusClass = status => ({ confirmed:'status-confirmed', unverified:'status-unverified', contested:'status-unverified', refuted:'status-refuted' })[status] || '';
const readingText = node => {
  const paragraphs = (node.reading?.paragraphs ?? []).map(p=>`<p>${escape(p)}</p>`).join('');
  const edition = node.reading?.edition?.text;
  const original = edition ? `<h4>古籍原文</h4>${String(edition).split(/\n{2,}/).map(p=>`<p lang="zh-Hant">${escape(p)}</p>`).join('')}` : '';
  return paragraphs || original ? paragraphs + original : '<p>本条暂无站内正文，请查阅出处。</p>';
};
const matchLabel = row => ({ curated: '精选对读', relay: '母题/结构传导', theme: '主题关联', guide: '阅读指引' })[row?.kind] ?? '自选对读';
const matchReason = (row, byId) => {
  if (row?.kind === 'theme') {
    return `共同主题词：${(row.terms ?? []).map(item => `${item.term}${item.source === '正文' ? '（正文）' : item.source === '原文' ? '（原文）' : ''}${item.source === '题名或别名' && item.term.toLocaleLowerCase() !== item.target.toLocaleLowerCase() ? ` / ${item.target}` : ''}`).join('、')}`;
  }
  if (row?.kind === 'relay') {
    const viaNode = row.via && byId?.get?.(row.via);
    return viaNode ? `${row.reason}（经由 ${viaNode.title}）` : row.reason;
  }
  return row?.kind === 'guide' || row?.kind === 'curated' ? row.reason : '由用户选择的对读';
};

/** The second view uses the same public catalogue as the original atlas. */
export function createFullAtlas({ root, book, dataset, state, cosmosGroup, starMaterial, latLonToVec3, focusNode, onSelection, onPortal, onBrowseFolklore, audio, getMembraneDepth, onObserve, onMatchesReady, onMatchesUpdated, software = false }) {
  const deferMatches = isCompactViewport();
  let graph = null, byId = new Map(), indexById = new Map(), adjacency = new Map(), shards = null;
  const detailedNodes = new Map();
  let matchIndex = null, matchPromise = null, matchError = '';
  let substantiveCount = dataset.match_summary?.stats?.substantive_nodes ?? null;
  let prefetchedMatchBytes = null;
  let startPromise = null;
  let reverseEntryId = null, reverseQuery = '';
  let hubLexiconNodeId = null, hubLexiconQuery = '';
  const safeLexiconUrl = value => (/^https?:\/\//i.test(value ?? '') ? value : null);
  let geoPoints = null, semanticPoints = null, networkLines = null, limit = 60;
  const semanticPositions = [];
  const selected = () => state.selectedGraph;
  const allowed = node => state.tiers.has(node.credibility_tier) && (state.showF || !isFiction(node))
    && (state.genre === 'ALL' || genreContract(node) === state.genre);
  const classicURL = (view, nodeId) => {
    const query = new URLSearchParams({view});
    if (nodeId) query.set('story',nodeId);
    if (state.showF) query.set('fiction','1');
    if (state.genre !== 'ALL') query.set('genre',state.genre);
    query.set('tiers',[...state.tiers].join(','));
    if (nodeId && state.selectedGraph?.id === nodeId && state.selectedBook) {
      query.set('bridge_story',nodeId); query.set('bridge_entry',state.selectedBook.id);
    }
    return `${root}?${query}`;
  };
  const bookURL = id => {
    const query = new URLSearchParams({view:'life',entry:id});
    if (state.showF) query.set('fiction','1');
    if (state.genre !== 'ALL') query.set('genre',state.genre);
    query.set('tiers',[...state.tiers].join(','));
    if (state.selectedGraph && state.selectedBook?.id === id) {
      query.set('bridge_story',state.selectedGraph.id); query.set('bridge_entry',id);
    }
    return `${root}?${query}`;
  };

  function updateMatchCount() {
    const label = document.getElementById('stats-matches');
    if (!label || !matchIndex) return;
    const count = Object.entries(matchIndex.matches)
      .filter(([id, rows]) => byId.has(id) && allowed(byId.get(id)) && rows.some(row => row.kind !== 'guide')).length;
    substantiveCount = count;
    label.textContent = count.toLocaleString();
    const canvas = document.querySelector('#webgl-viewport canvas');
    if (canvas) canvas.dataset.matchCount = String(count);
    onMatchesUpdated?.(count);
  }

  function ensureMatches() {
    if (!matchPromise) {
      matchError = '';
      const bytesPromise = prefetchedMatchBytes;
      matchPromise = loadPortalMatches(root, dataset, book, graph, bytesPromise).then(index => {
        matchIndex = index;
        updateMatchCount();
        onMatchesReady?.(index);
        return index;
      }).catch(error => {
        matchPromise = null;
        prefetchedMatchBytes = null;
        matchError = error.message;
        throw error;
      });
    }
    return matchPromise;
  }

  function layerPosition(node, index) {
    let hash = 2166136261;
    for (const c of node.id) hash = Math.imul(hash ^ c.charCodeAt(0), 16777619);
    // Scatter real catalogue nodes through a volume rather than compressing
    // thousands of different records into four horizontal stripes.
    const mix = value => {
      value = Math.imul(value ^ (value >>> 16), 0x7feb352d);
      value = Math.imul(value ^ (value >>> 15), 0x846ca68b);
      return ((value ^ (value >>> 16)) >>> 0) / 4294967296;
    };
    const u = mix(hash), v = mix(hash ^ 0x9e3779b9), w = mix(hash ^ 0x85ebca6b);
    const layer = Math.max(1, Math.min(4, Number(node.z_layer) || 1));
    const r = 26 + Math.sqrt(u) * 164, a = v * Math.PI * 2 + index * .0001;
    return new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r * .94, (w - .5) * 105 + (layer - 2.5) * 28);
  }

  function makePoints(mode) {
    const count = graph.nodes.length;
    const pos = new Float32Array(count * 3), colors = new Float32Array(count * 3), size = new Float32Array(count),
      spike = new Float32Array(count), hi = new Float32Array(count), phase = new Float32Array(count);
    const palette = ['#d6b678','#e2d6c7','#b692f6','#6dc9ba'].map(color => new THREE.Color(color));
    graph.nodes.forEach((node, i) => {
      const vector = mode === 'geo' ? (hasCoordinates(node) ? latLonToVec3(node.spatial.lat, node.spatial.lng, 165) : new THREE.Vector3()) : semanticPositions[i];
      vector.toArray(pos, i * 3);
      palette[Math.max(0, Math.min(3, (Number(node.z_layer) || 1) - 1))].toArray(colors, i * 3);
      size[i] = mode === 'geo' ? 4.2 : 2.3; spike[i] = .03; phase[i] = i * .37;
      hi[i] = allowed(node) && (mode !== 'geo' || hasCoordinates(node)) ? (mode === 'geo' ? .72 : .24) : -1;
    });
    const geometry = new THREE.BufferGeometry();
    for (const [key, value, itemSize] of [['position',pos,3],['aColor',colors,3],['aSize',size,1],['aSpike',spike,1],['aHighlight',hi,1],['aPhase',phase,1]]) {
      geometry.setAttribute(key, new THREE.BufferAttribute(value, itemSize));
    }
    geometry.computeBoundingSphere();
    const points = new THREE.Points(geometry, starMaterial);
    points.userData.softwareStride = software ? (mode === 'semantic' ? 3 : 2) : 1;
    points.userData.geoOcclusion = mode === 'geo';
    points.userData.geographicMarkers = mode === 'geo';
    points.visible = false; cosmosGroup.add(points);
    return points;
  }

  function updatePoints() {
    if (!graph) return;
    const query = state.searchQuery.trim();
    for (const [points, geo] of [[geoPoints,true],[semanticPoints,false]]) {
      const attr = points.geometry.getAttribute('aHighlight');
      graph.nodes.forEach((node,i) => {
        attr.array[i] = !allowed(node) || (geo && !hasCoordinates(node)) ? -1
          : selected()?.id === node.id ? 2.1 : query && !matchesGraph(node, query) ? .12 : (geo ? .72 : .24);
      });
      attr.needsUpdate = true;
    }
    updateMatchCount();
  }

  function updateDimension() {
    if (!graph) return;
    geoPoints.visible = state.dimension === 'umbra';
    semanticPoints.visible = state.dimension === 'sidera';
    if (networkLines) networkLines.visible = state.dimension === 'sidera';
  }

  function drawNeighborhood(node) {
    clearNeighborhood();
    const index = indexById.get(node.id) ?? -1;
    if (index < 0) return;
    const positions = [];
    for (const edge of (adjacency.get(node.id) ?? []).slice(0, 200)) {
      const other = byId.get(edge.source === node.id ? edge.target : edge.source);
      if (!other || !allowed(other)) continue;
      semanticPositions[index].toArray(positions, positions.length);
      semanticPositions[indexById.get(other.id)].toArray(positions, positions.length);
    }
    if (!positions.length) return;
    const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions,3));
    networkLines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: '#d6b678', transparent:true, opacity:.48, depthWrite:false }));
    networkLines.visible = state.dimension === 'sidera'; cosmosGroup.add(networkLines);
  }
  function clearNeighborhood() {
    if (networkLines) { cosmosGroup.remove(networkLines); networkLines.geometry.dispose(); networkLines.material.dispose(); networkLines = null; }
  }

  function renderDirectory() {
    const container = document.getElementById('atlas-tree');
    if (!graph) { container.innerHTML = '<p class="syzygy-reference">正在载入完整民俗目录…</p>'; return; }
    const query = state.searchQuery.trim();
    const nodes = graph.nodes.filter(node => allowed(node) && matchesGraph(node,query));
    const header = document.createElement('div');
    header.className = 'syzygy-directory-heading';
    header.textContent = `民俗与图谱条目 · ${nodes.length.toLocaleString()} 条${query ? '匹配' : ''}`;
    container.innerHTML = ''; container.append(header);
    if (state.pendingBook) {
      const pending = document.createElement('p'); pending.className = 'syzygy-reference';
      pending.textContent = `选择一个民俗节点，与「${state.pendingBook.title}」对读。`; container.append(pending);
    }
    if (query) {
      const q = query.normalize('NFKC').toLocaleLowerCase();
      const books = book.entries.filter(entry => `${entry.id} ${entry.title} ${entry.topic}`.normalize('NFKC').toLocaleLowerCase().includes(q));
      if (books.length) {
        const heading = document.createElement('p'); heading.className='syzygy-reference'; heading.textContent=`格物识微 · ${books.length} 条匹配`;
        container.append(heading);
        books.slice(0,12).forEach(entry => {
          const button = document.createElement('button'); button.className = 'syzygy-directory-row';
          button.innerHTML = `<b>${escape(entry.title)}</b><span>${escape(entry.id)} · 第 ${escape(entry.page)} 页</span>`;
          button.addEventListener('click', () => selectBook(entry.id)); container.append(button);
        });
      }
    }
    nodes.slice(0,limit).forEach(node => {
      const button = document.createElement('button'); button.className = 'syzygy-directory-row';
      button.dataset.nodeId = node.id;
      if (selected()?.id === node.id) button.classList.add('is-selected');
      button.innerHTML = `<b>${escape(node.title)}</b><span>L${escape(node.z_layer ?? '—')} · ${escape(node.spatial?.location_name || node.credibility_tier || '图谱资料')}</span>`;
      button.addEventListener('click', () => select(node, true)); container.append(button);
    });
    if (nodes.length > limit) {
      const button = document.createElement('button'); button.className='syzygy-load-more';
      button.textContent = `显示更多 · ${Math.min(limit,nodes.length).toLocaleString()} / ${nodes.length.toLocaleString()}`;
      button.addEventListener('click', () => { limit += 60; renderDirectory(); }); container.append(button);
    } else if (!nodes.length) {
      const p = document.createElement('p'); p.className='syzygy-reference'; p.textContent='没有匹配的民俗条目。'; container.append(p);
    }
  }

  async function detail(node) {
    if (detailedNodes.has(node.id)) return detailedNodes.get(node.id);
    const record = { ...node, ...await shards.graph(node.id) };
    detailedNodes.set(node.id, record);
    return record;
  }
  function loadMechanisms(node, update) {
    const needed = mechanismsFor(node).map(item => item.related).filter(item => !detailedNodes.has(item.id));
    if (needed.length) Promise.allSettled(needed.map(detail)).then(update);
  }

  function mechanismsFor(node) {
    return (adjacency.get(node.id) ?? []).filter(edge => edge.type === 'EXPLAINED_BY'
      && ['confirmed','unverified','contested','refuted'].includes(edge.status))
      .map(edge => ({edge, related:byId.get(edge.source === node.id ? edge.target : edge.source)}))
      .filter(item=>item.related && allowed(item.related));
  }
  function mechanismMarkup(node) {
    const mechanisms=mechanismsFor(node);
    if (!mechanisms.length) return '';
    return `<div class="syzygy-mechanism"><p class="syzygy-overline">个案与机制 · 原图谱证据状态</p>${mechanisms.map(({edge,related})=>{
      const full=detailedNodes?.get(related.id) ?? related;
      return `<p><span class="${statusClass(edge.status)}">${escape(statusLabel(edge.status))}</span> · <a class="syzygy-evidence-link" href="${classicURL('graph',related.id)}">${escape(related.title)} ↗</a></p>
        ${edge.note ? `<p class="syzygy-reference">${escape(edge.note)}</p>` : ''}${full.sources?.length ? sourceList({sources:full.sources.slice(0,2)}) : ''}`;
    }).join('')}</div>`;
  }
  function paintSuggestions(node, slot, excludeEntry = null) {
    if (!slot?.isConnected) return;
    if (!matchIndex) {
      slot.innerHTML = matchError ? `<p class="syzygy-reference">对照索引暂未载入。<button data-match-retry class="syzygy-inline-button">重试</button></p>`
        : '<p class="syzygy-reference">正在载入自动对照…</p>';
      slot.querySelector('[data-match-retry]')?.addEventListener('click',()=>{matchError='';paintSuggestions(node,slot,excludeEntry);});
      if (!matchError) ensureMatches().then(()=>paintSuggestions(node,slot,excludeEntry)).catch(()=>paintSuggestions(node,slot,excludeEntry));
      return;
    }
    const rows=(matchIndex.matches[node.id] ?? []).filter(row=>row.entry !== excludeEntry);
    const topics=rows.filter(row=>row.kind !== 'guide'), guides=rows.filter(row=>row.kind === 'guide');
    const renderRows = list => list.map(row=> {
      const entry=book.entries.find(item=>item.id === row.entry);
      if (!entry) return '';
      return `<button class="syzygy-related" data-match-entry="${escape(entry.id)}"><span>${escape(entry.title)}</span><small class="syzygy-match-label" data-kind="${escape(row.kind)}">${escape(matchLabel(row))} · ${escape(matchReason(row, byId))}</small></button>`;
    }).join('');
    slot.innerHTML = `${topics.length ? `<p class="syzygy-match-heading">星桥对照（精选 · 传导 · 主题）· ${topics.length}</p>${renderRows(topics)}` : ''}
      ${guides.length ? `<details class="syzygy-guide-group"><summary>资料类型参考指引 · ${guides.length}</summary>${renderRows(guides)}</details>` : ''}
      ${!rows.length ? '<p class="syzygy-reference">暂无合适的自动对照，可以自行搜索原书。</p>' : ''}`;
    slot.querySelectorAll('[data-match-entry]').forEach(button=>button.addEventListener('click',()=>openPortal(node,button.dataset.matchEntry)));
  }
  function paintReverse(entry, slot) {
    if (!slot?.isConnected) return;
    if (!matchIndex) {
      slot.innerHTML=matchError ? '<p class="syzygy-reference">对照索引暂未载入。<button data-match-retry class="syzygy-inline-button">重试</button></p>' : '<p class="syzygy-reference">正在载入关联民俗…</p>';
      slot.querySelector('[data-match-retry]')?.addEventListener('click',()=>{matchError='';paintReverse(entry,slot);});
      if (!matchError) ensureMatches().then(()=>paintReverse(entry,slot)).catch(()=>paintReverse(entry,slot));
      return;
    }
    const all=(matchIndex.reverse.get(entry.id) ?? []).filter(row=>byId.has(row.nodeId) && allowed(byId.get(row.nodeId)));
    slot.innerHTML=`<p class="syzygy-match-heading">关联民俗与资料 · ${all.length.toLocaleString()}</p>
      ${all.length ? '<input class="syzygy-portal-search" data-reverse-search type="search" placeholder="筛选标题、地点或编号" autocomplete="off"><div data-reverse-list></div>' : '<p class="syzygy-reference">暂无自动对照；也可以从目录选择民俗条目。</p>'}`;
    if (!all.length) return;
    const input=slot.querySelector('[data-reverse-search]'), list=slot.querySelector('[data-reverse-list]'); let shown=10;
    input.value=reverseEntryId === entry.id ? reverseQuery : '';
    const paint=()=>{
      const filtered=all.filter(row=>matchesGraph(byId.get(row.nodeId),input.value));
      list.innerHTML=filtered.slice(0,shown).map(row=>{const node=byId.get(row.nodeId);return `<button class="syzygy-related" data-reverse-node="${escape(node.id)}"><span>${escape(node.title)}</span><small class="syzygy-match-label" data-kind="${escape(row.kind)}">${escape(matchLabel(row))} · ${escape(matchReason(row, byId))}</small></button>`;}).join('')
        + (filtered.length>shown ? `<button class="syzygy-load-more" data-more-reverse>显示更多 · ${shown} / ${filtered.length.toLocaleString()}</button>` : '')
        + (!filtered.length ? '<p class="syzygy-reference">没有匹配条目。</p>' : '');
      list.querySelectorAll('[data-reverse-node]').forEach(button=>button.addEventListener('click',()=>openPortal(byId.get(button.dataset.reverseNode),entry.id)));
      list.querySelector('[data-more-reverse]')?.addEventListener('click',()=>{shown+=10;paint();});
    };
    input.addEventListener('input',()=>{reverseEntryId=entry.id;reverseQuery=input.value;shown=10;paint();}); paint();
  }

  async function paintHubLexicon(node, slot) {
    if (!slot?.isConnected) return;
    const taxonomy = await loadTaxonomy(root);
    if (!slot.isConnected || selected()?.id !== node.id) return;
    const info = getHubLexiconInfo(taxonomy, node.id);
    if (!info) {
      slot.hidden = true;
      slot.innerHTML = '';
      return;
    }

    slot.hidden = false;
    if (!info.shard) {
      slot.innerHTML = `<div class="syzygy-lexicon-head"><p class="syzygy-overline">专题辞条汇典 · ${escape(info.domain_name)}</p><span class="syzygy-badge syzygy-badge-context">规划分片</span></div>
        <p class="syzygy-reference" style="margin-top:6px">该专题辞条分片已列入后续编纂波次，可先浏览上方跨层关联条目。</p>`;
      return;
    }

    slot.innerHTML = `<div class="syzygy-lexicon-head"><p class="syzygy-overline">专题辞条汇典 · ${escape(info.domain_name)}</p><span class="syzygy-badge syzygy-badge-context" data-hub-lexicon-count>${escape(info.count)} 辞条</span></div>
      <details class="syzygy-lexicon-drawer" open>
        <summary>展开检索本枢纽辞条</summary>
        <input class="syzygy-portal-search" data-hub-lexicon-search type="search" placeholder="检索辞条、别名、地域或释义" autocomplete="off">
        <div class="syzygy-lexicon-cards" data-hub-lexicon-list><p class="syzygy-reference">正在校验并载入辞条分片…</p></div>
      </details>`;

    const searchInput = slot.querySelector('[data-hub-lexicon-search]');
    const listEl = slot.querySelector('[data-hub-lexicon-list]');
    const countEl = slot.querySelector('[data-hub-lexicon-count]');
    if (searchInput) searchInput.value = hubLexiconNodeId === node.id ? hubLexiconQuery : '';

    try {
      const shard = await loadLexiconShard(root, taxonomy, info.domain_id);
      if (!slot.isConnected || selected()?.id !== node.id) return;
      const hubEntries = shard.entries.filter(entry => entry.hub_id === node.id);
      if (countEl) countEl.textContent = `${hubEntries.length} 辞条`;

      const renderCards = () => {
        if (!listEl?.isConnected) return;
        const filtered = filterLexiconEntries(hubEntries, searchInput?.value ?? '');
        if (!filtered.length) {
          listEl.innerHTML = `<p class="syzygy-reference">${hubEntries.length ? '没有匹配的专题辞条。' : '本枢纽暂无对应辞条。'}</p>`;
          return;
        }
        listEl.innerHTML = filtered.map(entry => {
          const aliases = Array.isArray(entry.aliases) && entry.aliases.length
            ? `<p class="syzygy-reference">别称：${escape(entry.aliases.join('、'))}</p>`
            : '';
          const meta = [entry.category, entry.region, entry.era].filter(Boolean).join(' · ');
          const readingTagHTML = entry.reading_tag
            ? `<span class="taxonomy-reading-tag">${escape(entry.reading_tag)}</span>`
            : '';
          const gistHTML = entry.gist
            ? `<span class="taxonomy-lexicon-gist">${escape(entry.gist)}</span>`
            : '';
          const sources = (entry.primary_sources ?? []).map(src => {
            const url = safeLexiconUrl(src?.url);
            const citation = String(src?.citation || src?.url || '原典出处').trim();
            const locator = String(src?.locator ?? '').trim();
            if (url) {
              return `<li><span class="taxonomy-source-kind is-public">来源链接</span> <a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(citation)} ↗</a>${locator ? `<span class="taxonomy-locator-note">定位：${escape(locator)}</span>` : ''}</li>`;
            }
            return `<li><span class="taxonomy-source-kind">出处信息</span> ${escape(citation)}${locator ? `<span class="taxonomy-locator-note">定位：${escape(locator)}</span>` : ''}</li>`;
          }).join('');
          const secondary = entry.secondary_ref ? `<p class="syzygy-reference" style="margin-top:6px">参考资料：${escape(entry.secondary_ref)}</p>` : '';
          return `<details class="syzygy-lexicon-card">
            <summary>
              <div class="taxonomy-lexicon-summary-main">
                <div class="taxonomy-lexicon-title-row"><span>${escape(entry.term)}</span>${readingTagHTML}${entry.reviewed_by_human === false ? '<span class="taxonomy-reading-tag">待人工复核</span>' : ''}</div>
                ${gistHTML}
              </div>
              <small>${escape(meta)}</small>
            </summary>
            <div class="syzygy-lexicon-card-body">
              ${aliases}
              ${entry.summary.split(/\n\s*\n/).filter(Boolean).map(paragraph => `<p>${escape(paragraph)}</p>`).join('')}
              ${entry.case_id ? `<p><a class="syzygy-evidence-link" href="${classicURL('map', entry.case_id)}">查看地图故事 ↗</a></p>` : ''}
              ${entry.knowledge_id ? `<p><a class="syzygy-evidence-link" href="${root}?view=life&amp;entry=${encodeURIComponent(entry.knowledge_id)}">知识对读 · 主题关联 ↗</a> ${escape(entry.knowledge_note || '')}</p>` : ''}
              ${sources ? `<ul class="syzygy-source-list">${sources}</ul>` : ''}
              ${secondary}
            </div>
          </details>`;
        }).join('');
      };

      searchInput?.addEventListener('input', () => {
        hubLexiconNodeId = node.id;
        hubLexiconQuery = searchInput.value;
        renderCards();
      });
      renderCards();
    } catch (error) {
      if (!slot.isConnected || selected()?.id !== node.id || !listEl) return;
      listEl.innerHTML = `<p class="syzygy-reference">辞条分片载入失败：${escape(error.message)} <button type="button" class="syzygy-inline-button" data-hub-lexicon-retry>重试</button></p>`;
      listEl.querySelector('[data-hub-lexicon-retry]')?.addEventListener('click', () => paintHubLexicon(node, slot));
    }
  }

  function renderNode(node, loading = false) {
    const container = document.getElementById('syzygy-card-container');
    const searchDraft=container.dataset.nodeId === node.id ? container.querySelector('#portal-book-search')?.value ?? '' : '';
    if (hubLexiconNodeId !== node.id) {
      hubLexiconNodeId = node.id;
      hubLexiconQuery = '';
    }
    container.dataset.nodeId=node.id;
    const coords = hasCoordinates(node) ? `${node.spatial.lat.toFixed(3)}, ${node.spatial.lng.toFixed(3)}` : '未记录坐标';
    const edges = (adjacency.get(node.id) ?? []).filter(edge => allowed(byId.get(edge.source === node.id ? edge.target : edge.source) ?? {}));
    const relations = edges.slice(0,20).map(edge => {
      const other = byId.get(edge.source === node.id ? edge.target : edge.source);
      return other ? `<button class="syzygy-related" data-related="${escape(other.id)}"><span>${escape(other.title)}</span><small class="${statusClass(edge.status)}">${statusLabel(edge.status)}</small></button>` : '';
    }).join('');
    container.innerHTML = `<article class="engraving-codex">${engravingHeader('民俗与个案',node.spatial?.location_name || '地点未记录',node.credibility_tier)}<section class="mythos-pane syzygy-full-card"><p class="syzygy-overline">上卷 · 民俗与个案 / L${escape(node.z_layer ?? '—')}</p>
      <h3>${escape(node.title)}</h3><div class="syzygy-codes">${codePills(node)}</div>
      <p class="syzygy-reference">${escape(narrativeDisplay(node))}</p>
      <p class="syzygy-reference">${escape(node.spatial?.location_name || '地点未记录')} · ${escape(coords)}</p>
      <div class="syzygy-prose">${readingText(node)}</div>
      <h4>出处</h4>${loading ? '<p class="syzygy-reference">正在读取完整正文与出处…</p>' : sourceList(node)}
      <div class="syzygy-read-links"><a href="${classicURL('map',node.id)}">精查地图</a><a href="${classicURL('graph',node.id)}">精查星络</a></div>${storyShare(root,node)}</section>
      ${engravingBeam(false)}<section class="prism-pane syzygy-full-card"><p class="syzygy-overline">跨层关联 · 原图谱记录 ${edges.length}</p>
      ${mechanismMarkup(node)}${relations || '<p class="syzygy-reference">暂无关联节点。</p>'}${edges.length>20 ? `<p class="syzygy-reference">展示前 20 条，完整关系请在精查星络中查看。</p>` : ''}</section>
      <section class="physis-pane syzygy-full-card syzygy-hub-lexicon" data-hub-lexicon hidden></section>
      <section class="physis-pane syzygy-full-card"><p class="syzygy-overline">✦ 穿界星门 · 格物主题对读</p>
      <p class="syzygy-reference">主题候选依据共同词汇；阅读指引依据资料类型。</p><div data-portal-suggestions></div>
      <label class="syzygy-reference" for="portal-book-search">搜索全部 ${book.entries.length.toLocaleString()} 条格物资料</label>
      <input id="portal-book-search" class="syzygy-portal-search" type="search" placeholder="标题、主题或编号" autocomplete="off"><div id="portal-book-results"></div></section></article>`;
    container.querySelectorAll('[data-related]').forEach(button => button.addEventListener('click', () => { const next=byId.get(button.dataset.related); if (next) select(next,true); }));
    bindStoryShare(container);
    paintSuggestions(node,container.querySelector('[data-portal-suggestions]'));
    void paintHubLexicon(node, container.querySelector('[data-hub-lexicon]'));
    const input = container.querySelector('#portal-book-search'), results = container.querySelector('#portal-book-results');
    input.addEventListener('input', () => {
      const q = input.value.trim().normalize('NFKC').toLocaleLowerCase(); results.innerHTML = '';
      if (!q) return;
      const matches = book.entries.filter(entry=>`${entry.id} ${entry.title} ${entry.topic} ${entry.volume}`.normalize('NFKC').toLocaleLowerCase().includes(q));
      const note=document.createElement('p'); note.className='syzygy-reference'; note.textContent=`${matches.length} 条匹配${matches.length > 20 ? ' · 显示前 20 条' : ''}`; results.append(note);
      matches.slice(0,20).forEach(entry=>{ const button=document.createElement('button'); button.className='syzygy-related'; button.dataset.portalResult=entry.id;
        button.innerHTML=`<span>${escape(entry.title)}</span><small>${escape(entry.id)} · ${escape(entry.volume)}</small>`;
        button.addEventListener('click',()=>openPortal(node,entry.id)); results.append(button); });
    });
    if (searchDraft) { input.value=searchDraft; input.dispatchEvent(new Event('input')); }
  }

  async function select(node, fly = true) {
    if (!node || !allowed(node)) return;
    if (state.pendingBook) { const pending = state.pendingBook; state.pendingBook = null; return openPortal(node,pending.id); }
    state.selectedGraph = node; state.selectedBridge = null; state.selectedBook = null;
    onObserve?.({ type: 'mythos', id: node.id, label: node.title });
    renderNode(node, !!graph.details_file); updatePoints(); drawNeighborhood(node); onSelection();
    if (state.scopeTab === 'supplement' || state.dimension !== 'omnia' || state.searchQuery) renderDirectory();
    if (fly) focusNode(node, hasCoordinates(node) ? latLonToVec3(node.spatial.lat,node.spatial.lng,165) : null, semanticPositions[indexById.get(node.id)]);
    try {
      const full = await detail(node);
      if (selected()?.id === node.id && !state.selectedBook) renderNode(full, false);
      loadMechanisms(node, () => { if (selected()?.id === node.id && !state.selectedBook) renderNode(full, false); });
    } catch (error) {
      if (selected()?.id === node.id && !state.selectedBook) {
        renderNode(node, false);
        const p = document.createElement('p'); p.className='syzygy-reference'; p.textContent=`正文读取失败：${error.message}，请重新点击条目重试。`;
        document.getElementById('syzygy-card-container').append(p);
      }
    }
  }

  async function selectBook(id) {
    const entry = book.entries.find(item => item.id === id);
    if (!entry) return;
    if (reverseEntryId !== id) { reverseEntryId=id; reverseQuery=''; }
    state.selectedGraph = null; state.selectedBridge = null; state.selectedBook = entry; clearNeighborhood(); onSelection(); updatePoints();
    onObserve?.({ type: 'physis', id: entry.id, label: entry.title });
    const container = document.getElementById('syzygy-card-container');
    const render = (body, loading) => {
      container.innerHTML = `<article class="engraving-codex">${engravingHeader('格物识微',entry.volume,undefined,engravingPatternForVolume(entry.volume))}<section class="physis-pane syzygy-full-card"><p class="syzygy-overline">下卷 · 格物识微 / ${escape(entry.volume)}</p><h3>${escape(entry.title)}</h3><p class="syzygy-reference">${escape(entry.id)} · PDF 第 ${escape(entry.page)} 页</p><div class="syzygy-read-links">${originalPageButton(entry.page)}</div><div class="syzygy-prose syzygy-book-body">${loading ? '正在读取原书正文…' : handbookText(body,root)}</div>${bookNavigation(entry,book.entries)}<div class="syzygy-read-links"><a href="${bookURL(entry.id)}">精查万象星枢</a><a href="${publicAssetUrl(root, 'knowledge/handbook.pdf')}#page=${encodeURIComponent(entry.page)}" target="_blank" rel="noopener">打开原书 PDF</a><button id="portal-choose-story" class="ctl-btn">✦ 选择民俗条目对读</button></div><div data-portal-reverse></div></section></article>`;
      container.querySelector('#portal-choose-story').addEventListener('click',()=>{state.pendingBook=entry; onBrowseFolklore(); renderDirectory();});
      bindBookNavigation(container,selectBook);
      bindOriginalPages(container,root,book);
      paintReverse(entry,container.querySelector('[data-portal-reverse]'));
    };
    render('',true);
    try { await start(); const full=await shards.book(id); if (state.selectedBook?.id === id && !state.selectedGraph) render(full.body,false); }
    catch (error) { if(state.selectedBook?.id === id && !state.selectedGraph) render(`正文读取失败：${error.message}，请重新选择条目。`,false); }
  }

  async function openPortal(node, id) {
    const entry = book.entries.find(item => item.id === id);
    if (!node || !entry || !allowed(node)) return;
    state.selectedGraph = node; state.selectedBridge = null; state.selectedBook = entry; state.pendingBook = null;
    onObserve?.({ type: 'bridge', id: `${node.id}:${entry.id}`, label: `${node.title} ⇄ ${entry.title}` });
    onSelection(); updatePoints(); onPortal(node,entry);
    const container = document.getElementById('syzygy-card-container');
    const render = (story, body, loading) => {
      const row=(matchIndex?.matches[node.id] ?? []).find(item=>item.entry === entry.id);
      const label=matchIndex ? matchLabel(row) : matchError ? '对照依据暂不可用' : '正在读取对照依据';
      const reason=matchIndex ? matchReason(row, byId) : matchError ? '可继续阅读两侧资料，或稍后重试自动对照。' : '正在载入自动对照索引。';
      const prism = resolvePrismForPair({ node: story, entry, depth: getMembraneDepth?.() ?? 0.5 });
      container.innerHTML = `<article class="engraving-codex">${engravingHeader('民俗与格物对读',story.spatial?.location_name || '地点未记录',story.credibility_tier)}
        <div class="syzygy-overview-strip">
          <div class="syzygy-overview-pair">
            <div class="syzygy-overview-node"><small>上卷 · 玄象志怪</small><strong title="${escape(story.title)}">${escape(story.title)}</strong></div>
            <span class="syzygy-overview-link" aria-hidden="true">⇄</span>
            <div class="syzygy-overview-node"><small>下卷 · 格物识微</small><strong title="${escape(entry.title)}">${escape(entry.title)}</strong></div>
          </div>
          <div class="syzygy-overview-meta">
            <span class="syzygy-badge syzygy-badge-context">◇ ${escape(label)}</span>
            <span class="syzygy-reference">✦ 穿界自选对读</span>
          </div>
          <div class="syzygy-jump-tabs" role="navigation" aria-label="对读锚点">
            <button type="button" data-codex-jump="mythos">上卷 · 志怪</button>
            <button type="button" data-codex-jump="prism">◐ 折光依据</button>
            <button type="button" data-codex-jump="physis">下卷 · 格物</button>
          </div>
        </div>
        ${engravingBeam(true)}
        <section class="prism-pane syzygy-full-card" data-codex-section="prism"><p class="syzygy-overline">◐ 穿界星门 · ${escape(label)}</p><p class="syzygy-reference">${escape(reason)}</p>${mechanismMarkup(story)}${renderPrismPhilosophyHTML(prism, book.entries)}</section>
        <div class="syzygy-dual-body">
          <section class="mythos-pane syzygy-full-card" data-codex-section="mythos"><p class="syzygy-overline">上卷 · L${escape(story.z_layer ?? '—')}</p>
            <h3>${escape(story.title)}</h3><p class="syzygy-reference">${escape(narrativeDisplay(story))}</p><p class="syzygy-reference">${escape(story.spatial?.location_name || '地点未记录')}</p><div class="syzygy-prose">${readingText(story)}</div>
            <h4>文献出处</h4>${loading ? '<p class="syzygy-reference">正在读取…</p>' : sourceList(story)}<div class="syzygy-read-links"><a href="${classicURL('map',story.id)}">精查地图</a><a href="${classicURL('graph',story.id)}">精查星络</a></div>${storyShare(root,story)}</section>
          <section class="physis-pane syzygy-full-card" data-codex-section="physis"><div class="engraving-reading-band">${engravingFrieze(engravingPatternForVolume(entry.volume),'engraving-reading-band')}</div><p class="syzygy-overline">下卷 · 格物识微 / ${escape(entry.volume)}</p><h3>${escape(entry.title)}</h3><p class="syzygy-reference">${escape(entry.id)} · PDF 第 ${escape(entry.page)} 页</p><div class="syzygy-read-links">${originalPageButton(entry.page)}</div><div class="syzygy-prose syzygy-book-body">${loading ? '正在读取原书正文…' : handbookText(body,root)}</div>${bookNavigation(entry,book.entries)}<div class="syzygy-read-links"><a href="${bookURL(entry.id)}">精查万象星枢</a><a href="${publicAssetUrl(root, 'knowledge/handbook.pdf')}#page=${encodeURIComponent(entry.page)}" target="_blank" rel="noopener">打开原书 PDF</a><button id="portal-change-book" class="ctl-btn">更换对读</button></div></section>
        </div></article>`;
      container.querySelectorAll('[data-codex-jump]').forEach(button => button.addEventListener('click', () => {
        container.querySelector(`[data-codex-section="${button.dataset.codexJump}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }));
      container.querySelector('#portal-change-book').addEventListener('click',()=>select(node,false));
      bindStoryShare(container);
      bindBookNavigation(container,next => openPortal(node,next));
      bindOriginalPages(container,root,book);
      bindEngravingBeam(container);
      bindSensoryLabs(container, { audio, onOpenBook: (bookId) => openPortal(node, bookId) });
    };
    render(node,'',true);
    try {
      const [fullNode,fullEntry] = await Promise.all([detail(node),shards.book(id)]);
      await ensureMatches().catch(()=>null);
      if (state.selectedGraph?.id === node.id && state.selectedBook?.id === id) render(fullNode,fullEntry.body,false);
      loadMechanisms(node, () => { if (state.selectedGraph?.id === node.id && state.selectedBook?.id === id) render(fullNode,fullEntry.body,false); });
    } catch (error) {
      if (state.selectedGraph?.id === node.id && state.selectedBook?.id === id) render(node,`正文读取失败：${error.message}，请重新打开对读。`,false);
    }
  }

  function hit(raycaster) {
    if (!graph) return null;
    const points = state.dimension === 'umbra' ? geoPoints : state.dimension === 'sidera' ? semanticPoints : null;
    if (!points?.visible) return null;
    const hits = raycaster.intersectObject(points);
    const localEye = state.dimension === 'umbra' ? points.worldToLocal(raycaster.ray.origin.clone()) : null;
    const match = hits.find(item => {
      const node = graph.nodes[item.index];
      if (!allowed(node) || (state.dimension === 'umbra' && !hasCoordinates(node))) return false;
      return !localEye || latLonToVec3(node.spatial.lat,node.spatial.lng,165).dot(localEye) > 165 * 165;
    });
    if (!match) return null;
    const node = graph.nodes[match.index];
    const position = state.dimension === 'umbra' ? latLonToVec3(node.spatial.lat,node.spatial.lng,165) : semanticPositions[match.index];
    return { kind:'graph', node, worldPos:position.clone().applyMatrix4(cosmosGroup.matrixWorld), coord:node.spatial?.location_name || `L${node.z_layer ?? '—'}`, tag:'ASTRAIA / GRAPH', title:node.title, sub:'点击阅读原图谱卷宗' };
  }

  function start() {
    if (!startPromise) startPromise = (async () => {
      if (!deferMatches && !prefetchedMatchBytes && /^[a-f0-9]{64}$/.test(dataset.matches_sha256 ?? '')) {
        const url = `${publicAssetUrl(root, 'syzygy/matches.json')}?v=${dataset.matches_sha256}`;
        prefetchedMatchBytes = fetch(url).then(r => r.ok ? r.arrayBuffer() : null).catch(() => null);
      }
      graph = await loadGraph(root, import.meta.env.VITE_PUBLIC_DEMO === '1', dataset.snapshot_id);
      if (graph.snapshot_id !== dataset.snapshot_id) throw new Error('朔望数据与民俗目录版本不一致，请刷新。');
      shards = createReadingShards(root, graph, book);
      byId = new Map(graph.nodes.map(node=>[node.id,node])); indexById = new Map(graph.nodes.map((node,i)=>[node.id,i]));
      graph.links.forEach(edge => { for (const id of [edge.source,edge.target]) { if (!adjacency.has(id)) adjacency.set(id,[]); adjacency.get(id).push(edge); } });
      graph.nodes.forEach((node,i) => semanticPositions.push(layerPosition(node,i)));
      geoPoints = makePoints('geo'); semanticPoints = makePoints('semantic'); updateDimension();
      rendererCount();
      if (!deferMatches) ensureMatches().catch(error => { console.warn('Automatic portal matches unavailable:', error); });
      return graph;
    })().catch(error=>{startPromise=null;throw error;});
    return startPromise;
  }
  return {
    start,
    renderDirectory, updatePoints, updateDimension, hit, select, selectBook, openPortal, clearNeighborhood,
    async hydrateCurated(bridge) {
      if (!graph || !shards || !bridge || bridge.readingLoaded) return !!bridge?.readingLoaded;
      if (!bridge.readingPromise) bridge.readingPromise = (async () => {
        const node=byId.get(bridge.mythos.id), related=bridge.related && byId.get(bridge.related.id);
        if (!node) throw new Error('未找到星桥对应的图谱条目。');
        const [story,entry,relatedDetail]=await Promise.all([detail(node),shards.book(bridge.physis.id),related ? detail(related) : null]);
        Object.assign(bridge.mythos,{reading:story.reading,sources:story.sources,markdown:story.markdown});
        if (relatedDetail) Object.assign(bridge.related,{reading:relatedDetail.reading,sources:relatedDetail.sources,markdown:relatedDetail.markdown});
        Object.assign(bridge.physis,{body:entry.body,figure_refs:entry.figure_refs});
        bridge.readingLoaded=true; return true;
      })().catch(error=>{bridge.readingPromise=null;throw error;});
      return bridge.readingPromise;
    },
    refreshFilters() {
      updatePoints();
      const slot=document.querySelector('[data-portal-reverse]');
      if (slot && state.selectedBook && !state.selectedGraph) paintReverse(state.selectedBook,slot);
      document.querySelectorAll('[data-related]').forEach(button=>{
        const related=byId.get(button.dataset.related); button.hidden=!!related && !allowed(related);
      });
    },
    attachCuratedSuggestions(bridge) {
      if (!graph || !bridge) return;
      const node=byId.get(bridge.mythos.id), slot=document.querySelector('[data-curated-suggestions]');
      if (node && slot) paintSuggestions(node,slot,bridge.physis.id);
    },
    searchChanged() { limit = 60; updatePoints(); },
    getNode(id) { return byId.get(id); },
    getMatchIndex() { return matchIndex; },
    getSubstantiveCount() { return substantiveCount; },
    isVisible(node) { return !!node && allowed(node); },
    visibleCount() { return graph?.nodes.filter(allowed).length ?? 0; },
  };
  function rendererCount() {
    const canvas = document.querySelector('#webgl-viewport canvas');
    if (canvas) { canvas.dataset.graphCount = String(graph.nodes.length); canvas.dataset.geoCount = String(graph.nodes.filter(hasCoordinates).length); canvas.dataset.knowledgeCount = String(book.entries.length); }
  }
}
