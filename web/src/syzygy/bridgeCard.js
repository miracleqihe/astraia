import { handbookText, bookNavigation, bindBookNavigation } from './readable';
import { storyShare, bindStoryShare } from './sharing';
import { originalPageButton, bindOriginalPages } from './originalPages';
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

export function renderBridgeCard(bridge, { root, onJump, onSelectRelated, onReadBook, book, bookEntries, confidence, relation, showF, tiers, genre }) {
  const wrap = document.getElementById('syzygy-card-container');
  if (!bridge) { wrap.innerHTML = ''; return; }
  const node = bridge.mythos, knowledge = bridge.physis;
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
  const codes = node.taxonomies.map(code=>`<span class="syzygy-code">${esc(code)}</span>`).join('');
  wrap.innerHTML = `<div class="space-y-2.5">
    <section class="mythos-pane syzygy-full-card"><p class="syzygy-overline">上卷 · 玄象志怪 / ${esc(node.genre)} · ${esc(node.credibility_tier ?? '—')} 级</p>
      <h3>${esc(node.title)}</h3><div class="syzygy-codes">${codes}</div>
      <p class="syzygy-reference">${esc(bridge.umbraGeo.place)}${bridge.hasCoordinates ? ` · ${bridge.umbraGeo.lat.toFixed(3)}, ${bridge.umbraGeo.lon.toFixed(3)}` : ' · 未记录坐标'}</p>
      <div class="syzygy-prose">${paragraphs(node)}</div><h4>出处</h4>${sources(node)}${bridge.readingLoaded ? '' : '<p class="syzygy-reference" role="status">正在补全全文与出处…</p>'}
      <div class="syzygy-read-links"><a href="${classic('map')}">经典地图</a><a href="${classic('graph')}">经典星络</a></div>${storyShare(root,node)}
    </section>
    <section class="prism-pane syzygy-full-card"><p class="syzygy-overline">◐ ${esc(relation[bridge.relation]?.label || '主题对读')}</p>
      <p class="syzygy-reference">${esc(bridge.rationale)}</p>
      ${bridge.related ? `<p class="syzygy-reference"><span class="${badge.cls}">${esc(badge.badge)}</span> · 个案与下列节点的原有关系</p><button class="syzygy-related" data-bridge-related><span>${esc(bridge.related.title)}</span><small>查看节点 ↗</small></button><div class="syzygy-prose">${paragraphs(bridge.related)}</div>${sources(bridge.related)}` : '<p class="syzygy-reference">依照共同主题组织的阅读线索。</p>'}
      ${bridge.related ? '<p class="syzygy-reference">下卷为主题对读；上述状态仅描述原图谱中的个案关联。</p>' : ''}
    </section>
    <section class="physis-pane syzygy-full-card"><p class="syzygy-overline">下卷 · 格物识微 / ${esc(knowledge.volLabel)}</p><h3>${esc(knowledge.title)}</h3>
      <p class="syzygy-reference">${esc(knowledge.id)} · PDF 第 ${esc(knowledge.page)} 页</p>
      <div class="syzygy-read-links">${originalPageButton(knowledge.page)}</div>
      <div class="syzygy-prose syzygy-book-body">${knowledge.body ? handbookText(knowledge.body,root) : '正在读取原书正文…'}</div>${bookNavigation(knowledge,bookEntries)}
      <div class="syzygy-read-links"><a href="${bookLink}">经典万象星枢阅读</a><a href="${root}knowledge/handbook.pdf#page=${encodeURIComponent(knowledge.page)}" target="_blank" rel="noopener">打开原书</a></div>
      <div class="syzygy-read-links"><button class="action-pill ctl-btn" data-jump="omnia">✦ 格物星点</button><button class="action-pill ctl-btn" data-jump="sidera">+ 玄象星络</button><button class="action-pill ctl-btn" data-jump="umbra" ${bridge.hasCoordinates ? '' : 'disabled title="该条目没有坐标"'}>◇ 坤舆坐标</button></div>
      <p class="syzygy-match-heading">此材料的其他知识对照</p><div data-curated-suggestions></div>
    </section></div>`;
  wrap.querySelectorAll('[data-jump]').forEach(button => button.addEventListener('click',()=>onJump(button.dataset.jump,bridge)));
  wrap.querySelector('[data-bridge-related]')?.addEventListener('click',()=>onSelectRelated(bridge.related.id));
  bindBookNavigation(wrap,onReadBook);
  bindStoryShare(wrap);
  bindOriginalPages(wrap,root,book);
}
