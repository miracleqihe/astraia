import { publicAssetUrl } from '../publicAssetUrl.js';
import { handbookText, bookNavigation, bindBookNavigation } from './readable';
import { storyShare, bindStoryShare } from './sharing';
import { originalPageButton, bindOriginalPages } from './originalPages';
import { engravingHeader, engravingBeam, engravingFrieze, engravingPatternForVolume, bindEngravingBeam } from '../engraving';
import { resolvePrismForPair, renderPrismPhilosophyHTML, bindSensoryLabs } from './philosophicalPrism';
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);
const sources = node => {
  const items = node?.sources ?? [];
  if (!items.length) return '<p class="syzygy-reference">本条暂无可展示的出处。</p>';
  return `<ul class="syzygy-source-list">${items.map(item => {
    const label = esc(item.citation || item.url || item.doi || item.type || '出处');
    return `<li>${/^https?:\/\//i.test(item.url ?? '') ? `<a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${label} ↗</a>` : label}${item.locator ? ` · ${esc(item.locator)}` : ''}</li>`;
  }).join('')}</ul>`;
};
const paragraphs = node => (node?.reading?.paragraphs ?? []).map(p=>`<p>${esc(p)}</p>`).join('') || '<p>本条暂无站内正文。</p>';

export function renderBridgeCard(bridge, { root, onJump, onSelectRelated, onReadBook, onOpenBook, book, bookEntries, confidence, relation, showF, tiers, genre, membraneDepth = 0.5, audio }) {
  const wrap = document.getElementById('syzygy-card-container');
  if (!bridge) { wrap.innerHTML = ''; return; }
  const node = bridge.mythos, knowledge = bridge.physis;
  const prism = resolvePrismForPair({ node, entry: knowledge, bridge, depth: membraneDepth });
  const classic = view => {
    const query=new URLSearchParams({view,story:node.id,bridge_story:node.id,bridge_entry:knowledge.id});
    query.set('tiers',[...tiers].join(','));
    if (genre !== 'ALL') query.set('genre',genre);
    if (showF) query.set('fiction','1');
    return `${root}?${query}`;
  };
  const bookQuery = new URLSearchParams({view:'life',entry:knowledge.id,bridge_story:node.id,bridge_entry:knowledge.id});
  bookQuery.set('tiers',[...tiers].join(','));
  if (genre !== 'ALL') bookQuery.set('genre',genre);
  if (showF) bookQuery.set('fiction','1');
  const bookLink = `${root}?${bookQuery}`;
  const badge = confidence[bridge.confidence];
  const relLabel = relation[bridge.relation]?.label || '专题对读';
  const codes = node.taxonomies.map(code=>`<span class="syzygy-code">${esc(code)}</span>`).join('');
  wrap.innerHTML = `<article class="engraving-codex">
    ${engravingHeader('民俗与格物对读', bridge.umbraGeo.place, node.credibility_tier)}
    <div class="syzygy-overview-strip">
      <div class="syzygy-overview-pair">
        <div class="syzygy-overview-node"><small>上卷 · 玄象志怪</small><strong title="${esc(node.title)}">${esc(node.title)}</strong></div>
        <span class="syzygy-overview-link" aria-hidden="true">⇄</span>
        <div class="syzygy-overview-node"><small>下卷 · 格物识微</small><strong title="${esc(knowledge.title)}">${esc(knowledge.title)}</strong></div>
      </div>
      <div class="syzygy-overview-meta">
        <span class="syzygy-badge ${esc(badge.cls)}">${esc(badge.badge)}</span>
        <span class="syzygy-reference">◐ ${esc(relLabel)}</span>
      </div>
      <div class="syzygy-jump-tabs" role="navigation" aria-label="对读锚点">
        <button type="button" data-codex-jump="mythos">上卷 · 志怪</button>
        <button type="button" data-codex-jump="prism">◐ 折光依据</button>
        <button type="button" data-codex-jump="physis">下卷 · 格物</button>
      </div>
    </div>
    ${engravingBeam(true)}
    <section class="prism-pane syzygy-full-card" data-codex-section="prism">
      <p class="syzygy-overline">◐ ${esc(relLabel)}</p>
      <p class="syzygy-reference">${esc(bridge.rationale)}</p>
      ${bridge.related ? `<p class="syzygy-reference" style="margin-top:8px"><span class="syzygy-badge ${esc(badge.cls)}">${esc(badge.badge)}</span> · 个案与下列节点的原有关系</p><button class="syzygy-related" data-bridge-related><span>${esc(bridge.related.title)}</span><small>查看关联节点 ↗</small></button><div class="syzygy-prose">${paragraphs(bridge.related)}</div>${sources(bridge.related)}` : '<p class="syzygy-reference">依照共同主题组织的阅读线索；对读本身不构成已证实的因果关系。</p>'}
      ${bridge.related ? '<p class="syzygy-reference" style="margin-top:6px">下卷为主题对读；上述状态仅描述原图谱中的个案关联。</p>' : ''}
      ${renderPrismPhilosophyHTML(prism, bookEntries)}
    </section>
    <div class="syzygy-dual-body">
      <section class="mythos-pane syzygy-full-card" data-codex-section="mythos">
        <p class="syzygy-overline">上卷 · 玄象志怪 / ${esc(node.genre)} · ${esc(node.credibility_tier ?? '—')} 级</p>
        <h3>${esc(node.title)}</h3>
        <div class="syzygy-codes">${codes}</div>
        <p class="syzygy-reference">${esc(bridge.umbraGeo.place)}${bridge.hasCoordinates ? ` · ${bridge.umbraGeo.lat.toFixed(3)}, ${bridge.umbraGeo.lon.toFixed(3)}` : ' · 未记录坐标'}</p>
        <div class="syzygy-prose">${paragraphs(node)}</div>
        <h4>文献出处</h4>${sources(node)}
        ${bridge.readingLoaded ? '' : '<p class="syzygy-reference" role="status">正在补全全文与出处…</p>'}
        <div class="syzygy-read-links"><a href="${classic('map')}">精查地图</a><a href="${classic('graph')}">精查星络</a></div>
        ${storyShare(root, node)}
      </section>
      <section class="physis-pane syzygy-full-card" data-codex-section="physis">
        <div class="engraving-reading-band">${engravingFrieze(engravingPatternForVolume(knowledge.volume), 'engraving-reading-band')}</div>
        <p class="syzygy-overline">下卷 · 格物识微 / ${esc(knowledge.volLabel)}</p>
        <h3>${esc(knowledge.title)}</h3>
        <p class="syzygy-reference">${esc(knowledge.id)} · PDF 第 ${esc(knowledge.page)} 页</p>
        <div class="syzygy-read-links">${originalPageButton(knowledge.page)}</div>
        <div class="syzygy-prose syzygy-book-body">${knowledge.body ? handbookText(knowledge.body, root) : '正在读取原书正文…'}</div>
        ${bookNavigation(knowledge, bookEntries)}
        <div class="syzygy-read-links"><a href="${bookLink}">精查万象星枢</a><a href="${publicAssetUrl(root, 'knowledge/handbook.pdf')}#page=${encodeURIComponent(knowledge.page)}" target="_blank" rel="noopener">打开原书 PDF</a></div>
        <div class="syzygy-read-links"><button class="action-pill ctl-btn" data-jump="omnia">✦ 格物星点</button><button class="action-pill ctl-btn" data-jump="sidera">+ 玄象星络</button><button class="action-pill ctl-btn" data-jump="umbra" ${bridge.hasCoordinates ? '' : 'disabled title="该条目没有坐标"'}>◇ 坤舆坐标</button></div>
        <p class="syzygy-match-heading">此材料的其他知识对照</p><div data-curated-suggestions></div>
      </section>
    </div>
  </article>`;
  wrap.querySelectorAll('[data-codex-jump]').forEach(button => button.addEventListener('click', () => {
    wrap.querySelector(`[data-codex-section="${button.dataset.codexJump}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
  wrap.querySelectorAll('[data-jump]').forEach(button => button.addEventListener('click', () => onJump(button.dataset.jump, bridge)));
  wrap.querySelector('[data-bridge-related]')?.addEventListener('click', () => onSelectRelated(bridge.related.id));
  bindBookNavigation(wrap, onReadBook);
  bindStoryShare(wrap);
  bindOriginalPages(wrap, root, book);
  bindEngravingBeam(wrap);
  bindSensoryLabs(wrap, { audio, onOpenBook: onOpenBook || onReadBook });
}
