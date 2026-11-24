import * as THREE from 'three';
import { loadGraph, loadDetails, matchesGraph, suggestBookEntries } from './graphBridge';
import { handbookText } from './readable';

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
const statusLabel = status => ({ confirmed:'✓ 已证实', unverified:'? 待核实', refuted:'✕ 已驳回' })[status] || '关联';
const statusClass = status => ({ confirmed:'status-confirmed', unverified:'status-unverified', refuted:'status-refuted' })[status] || '';

/** The second view uses the same public catalogue as the original atlas. */
export function createFullAtlas({ root, book, dataset, state, cosmosGroup, starMaterial, latLonToVec3, focusNode, onSelection, onPortal, onBrowseFolklore }) {
  let graph = null, byId = new Map(), indexById = new Map(), adjacency = new Map(), detailsPromise = null, bookPromise = null;
  let geoPoints = null, semanticPoints = null, networkLines = null, limit = 60;
  const semanticPositions = [];
  const selected = () => state.selectedGraph;
  const allowed = node => state.showF || !isFiction(node);
  const classicURL = (view, nodeId) => `${root}?view=${view}${nodeId ? `&story=${encodeURIComponent(nodeId)}` : ''}${state.showF ? '&fiction=1' : ''}`;
  const bookURL = id => `${root}?view=life&entry=${encodeURIComponent(id)}`;

  function layerPosition(node, index) {
    let hash = 2166136261;
    for (const c of node.id) hash = Math.imul(hash ^ c.charCodeAt(0), 16777619);
    const u = (hash >>> 0) / 4294967296;
    const v = ((Math.imul(hash, 1597334677) >>> 0) / 4294967296);
    const layer = Math.max(1, Math.min(4, Number(node.z_layer) || 1));
    const r = 22 + Math.sqrt(u) * 158, a = v * Math.PI * 2 + index * .0001;
    return new THREE.Vector3(Math.cos(a) * r, (layer - 2.5) * 90 + Math.sin(a) * 19, Math.sin(a) * r * .58);
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
      hi[i] = allowed(node) && (mode !== 'geo' || hasCoordinates(node)) ? .72 : -1;
    });
    const geometry = new THREE.BufferGeometry();
    for (const [key, value, itemSize] of [['position',pos,3],['aColor',colors,3],['aSize',size,1],['aSpike',spike,1],['aHighlight',hi,1],['aPhase',phase,1]]) {
      geometry.setAttribute(key, new THREE.BufferAttribute(value, itemSize));
    }
    geometry.computeBoundingSphere();
    const points = new THREE.Points(geometry, starMaterial);
    points.userData.softwareStride = 1;
    points.userData.geoOcclusion = mode === 'geo';
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
          : selected()?.id === node.id ? 2.1 : query && !matchesGraph(node, query) ? .12 : .72;
      });
      attr.needsUpdate = true;
    }
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

  async function allDetails() {
    if (!detailsPromise) detailsPromise = loadDetails(root, graph).catch(error => { detailsPromise = null; throw error; });
    return detailsPromise;
  }
  async function allBooks() {
    if (!bookPromise) bookPromise = (async () => {
      const response = await fetch(`${root}knowledge/data.json?v=${book.data_sha256}`);
      if (!response.ok) throw new Error('原书资料读取失败。');
      const bytes = await response.arrayBuffer();
      if (globalThis.crypto?.subtle) {
        const digest = await crypto.subtle.digest('SHA-256',bytes);
        const hash = [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2,'0')).join('');
        if (hash !== book.data_sha256) throw new Error('原书资料版本不一致，请刷新。');
      }
      const data = JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
      if (!Array.isArray(data.entries)) throw new Error('原书资料格式错误。');
      return new Map(data.entries.map(entry => [entry.id,entry]));
    })().catch(error => { bookPromise = null; throw error; });
    return bookPromise;
  }

  function renderNode(node, loading = false) {
    const container = document.getElementById('syzygy-card-container');
    const paragraphs = node.reading?.paragraphs ?? [];
    const coords = hasCoordinates(node) ? `${node.spatial.lat.toFixed(3)}, ${node.spatial.lng.toFixed(3)}` : '未记录坐标';
    const edges = (adjacency.get(node.id) ?? []).filter(edge => allowed(byId.get(edge.source === node.id ? edge.target : edge.source) ?? {}));
    const suggestions = suggestBookEntries(node, book.entries);
    const relations = edges.slice(0,20).map(edge => {
      const other = byId.get(edge.source === node.id ? edge.target : edge.source);
      return other ? `<button class="syzygy-related" data-related="${escape(other.id)}"><span>${escape(other.title)}</span><small class="${statusClass(edge.status)}">${statusLabel(edge.status)}</small></button>` : '';
    }).join('');
    container.innerHTML = `<section class="mythos-pane syzygy-full-card"><p class="syzygy-overline">上卷 · 民俗与个案 / L${escape(node.z_layer ?? '—')} · ${escape(node.credibility_tier ?? '—')} 级</p>
      <h3>${escape(node.title)}</h3><div class="syzygy-codes">${codePills(node)}</div>
      <p class="syzygy-reference">${escape(node.spatial?.location_name || '地点未记录')} · ${escape(coords)}</p>
      <div class="syzygy-prose">${paragraphs.length ? paragraphs.map(p=>`<p>${escape(p)}</p>`).join('') : '<p>本条暂无站内正文，请查阅出处。</p>'}</div>
      <h4>出处</h4>${loading ? '<p class="syzygy-reference">正在读取完整正文与出处…</p>' : sourceList(node)}
      <div class="syzygy-read-links"><a href="${classicURL('map',node.id)}">在经典地图查看</a><a href="${classicURL('graph',node.id)}">在经典星络查看</a></div></section>
      <section class="prism-pane syzygy-full-card"><p class="syzygy-overline">跨层关联 · 原图谱记录 ${edges.length}</p>
      ${relations || '<p class="syzygy-reference">暂无关联节点。</p>'}${edges.length>20 ? `<p class="syzygy-reference">展示前 20 条，完整关系请在经典星络中查看。</p>` : ''}</section>
      <section class="physis-pane syzygy-full-card"><p class="syzygy-overline">✦ 穿界星门 · 格物主题对读</p>
      <p class="syzygy-reference">选择任一格物条目，与此卷宗并排阅读。关键词建议只表示主题相近。</p>
      ${suggestions.map(entry=>`<button class="syzygy-related" data-book="${escape(entry.id)}"><span>${escape(entry.title)}</span><small>${escape(entry.id)} · 主题建议</small></button>`).join('')}
      <label class="syzygy-reference" for="portal-book-search">搜索全部 ${book.entries.length.toLocaleString()} 条格物资料</label>
      <input id="portal-book-search" class="syzygy-portal-search" type="search" placeholder="标题、主题或编号" autocomplete="off"><div id="portal-book-results"></div></section>`;
    container.querySelectorAll('[data-related]').forEach(button => button.addEventListener('click', () => { const next=byId.get(button.dataset.related); if (next) select(next,true); }));
    container.querySelectorAll('[data-book]').forEach(button => button.addEventListener('click', () => openPortal(node,button.dataset.book)));
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
  }

  async function select(node, fly = true) {
    if (!node || !allowed(node)) return;
    if (state.pendingBook) { const pending = state.pendingBook; state.pendingBook = null; return openPortal(node,pending.id); }
    state.selectedGraph = node; state.selectedBridge = null; state.selectedBook = null;
    renderNode(node, !!graph.details_file); updatePoints(); drawNeighborhood(node); onSelection();
    if (state.scopeTab === 'supplement' || state.dimension !== 'omnia' || state.searchQuery) renderDirectory();
    if (fly) focusNode(node, hasCoordinates(node) ? latLonToVec3(node.spatial.lat,node.spatial.lng,165) : null, semanticPositions[indexById.get(node.id)]);
    try {
      const details = await allDetails();
      if (selected()?.id === node.id) renderNode(details.get(node.id) ?? node, false);
    } catch (error) {
      if (selected()?.id === node.id) {
        renderNode(node, false);
        const p = document.createElement('p'); p.className='syzygy-reference'; p.textContent=`正文读取失败：${error.message}，请重新点击条目重试。`;
        document.getElementById('syzygy-card-container').append(p);
      }
    }
  }

  async function selectBook(id) {
    const entry = book.entries.find(item => item.id === id);
    if (!entry) return;
    state.selectedGraph = null; state.selectedBridge = null; state.selectedBook = entry; clearNeighborhood(); onSelection(); updatePoints();
    const container = document.getElementById('syzygy-card-container');
    const render = (body, loading) => {
      container.innerHTML = `<section class="physis-pane syzygy-full-card"><p class="syzygy-overline">下卷 · 格物识微 / ${escape(entry.volume)}</p><h3>${escape(entry.title)}</h3><p class="syzygy-reference">${escape(entry.id)} · PDF 第 ${escape(entry.page)} 页</p><div class="syzygy-prose syzygy-book-body">${loading ? '正在读取原书正文…' : handbookText(body)}</div><div class="syzygy-read-links"><a href="${bookURL(entry.id)}">在经典万象星枢阅读</a><a href="${root}knowledge/handbook.pdf#page=${encodeURIComponent(entry.page)}" target="_blank" rel="noopener">打开原书</a><button id="portal-choose-story" class="ctl-btn">✦ 选择民俗条目对读</button></div></section>`;
      container.querySelector('#portal-choose-story').addEventListener('click',()=>{state.pendingBook=entry; onBrowseFolklore(); renderDirectory();});
    };
    render('',true);
    try { const all=await allBooks(); if (state.selectedBook?.id === id) render(all.get(id)?.body,false); }
    catch (error) { if(state.selectedBook?.id === id) render(`正文读取失败：${error.message}，请重新选择条目。`,false); }
  }

  async function openPortal(node, id) {
    const entry = book.entries.find(item => item.id === id);
    if (!node || !entry || !allowed(node)) return;
    state.selectedGraph = node; state.selectedBridge = null; state.selectedBook = entry; state.pendingBook = null;
    onSelection(); updatePoints(); onPortal(node,entry);
    const container = document.getElementById('syzygy-card-container');
    const render = (story, body, loading) => {
      container.innerHTML = `<section class="mythos-pane syzygy-full-card"><p class="syzygy-overline">上卷 · ${escape(story.credibility_tier ?? '—')} 级 / L${escape(story.z_layer ?? '—')}</p>
        <h3>${escape(story.title)}</h3><p class="syzygy-reference">${escape(story.spatial?.location_name || '地点未记录')}</p><div class="syzygy-prose">${(story.reading?.paragraphs ?? []).map(p=>`<p>${escape(p)}</p>`).join('') || '<p>本条暂无站内正文。</p>'}</div>
        <h4>出处</h4>${loading ? '<p class="syzygy-reference">正在读取…</p>' : sourceList(story)}<div class="syzygy-read-links"><a href="${classicURL('map',story.id)}">经典地图</a><a href="${classicURL('graph',story.id)}">经典星络</a></div></section>
        <section class="prism-pane syzygy-full-card"><p class="syzygy-overline">◐ 穿界星门 · 自选主题对读</p><p class="syzygy-reference">两条资料可对照阅读；自选星桥不表示已证实因果关系。</p></section>
        <section class="physis-pane syzygy-full-card"><p class="syzygy-overline">下卷 · 格物识微 / ${escape(entry.volume)}</p><h3>${escape(entry.title)}</h3><p class="syzygy-reference">${escape(entry.id)} · PDF 第 ${escape(entry.page)} 页</p><div class="syzygy-prose syzygy-book-body">${loading ? '正在读取原书正文…' : handbookText(body)}</div><div class="syzygy-read-links"><a href="${bookURL(entry.id)}">经典万象星枢阅读</a><a href="${root}knowledge/handbook.pdf#page=${encodeURIComponent(entry.page)}" target="_blank" rel="noopener">打开原书</a><button id="portal-change-book" class="ctl-btn">更换对读</button></div></section>`;
      container.querySelector('#portal-change-book').addEventListener('click',()=>select(node,false));
    };
    render(node,'',true);
    try {
      const [allNodes,allEntries] = await Promise.all([allDetails(),allBooks()]);
      if (state.selectedGraph?.id === node.id && state.selectedBook?.id === id) render(allNodes.get(node.id) ?? node,allEntries.get(id)?.body,false);
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

  return {
    async start() {
      graph = await loadGraph(root, import.meta.env.VITE_PUBLIC_DEMO === '1');
      if (graph.snapshot_id !== dataset.snapshot_id) throw new Error('朔望数据与民俗目录版本不一致，请刷新。');
      byId = new Map(graph.nodes.map(node=>[node.id,node])); indexById = new Map(graph.nodes.map((node,i)=>[node.id,i]));
      graph.links.forEach(edge => { for (const id of [edge.source,edge.target]) { if (!adjacency.has(id)) adjacency.set(id,[]); adjacency.get(id).push(edge); } });
      graph.nodes.forEach((node,i) => semanticPositions.push(layerPosition(node,i)));
      geoPoints = makePoints('geo'); semanticPoints = makePoints('semantic'); updateDimension();
      rendererCount();
      return graph;
    },
    renderDirectory, updatePoints, updateDimension, hit, select, selectBook, openPortal, clearNeighborhood,
    searchChanged() { limit = 60; updatePoints(); },
    getNode(id) { return byId.get(id); },
    visibleCount() { return graph?.nodes.filter(allowed).length ?? 0; },
  };
  function rendererCount() {
    const canvas = document.querySelector('#webgl-viewport canvas');
    if (canvas) { canvas.dataset.graphCount = String(graph.nodes.length); canvas.dataset.geoCount = String(graph.nodes.filter(hasCoordinates).length); canvas.dataset.knowledgeCount = String(book.entries.length); }
  }
}
