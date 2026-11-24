const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);

/** Only L1 stories have generated static preview pages. */
export function storyShare(root,node) {
  if (node?.z_layer !== 1 || !/^[A-Za-z0-9_-]+$/.test(node.id ?? '')) return '';
  const fiction=node.credibility_tier === 'F' || node.is_fictional_quarantine;
  const params=new URLSearchParams({dim:'sidera',story:node.id});
  if (fiction) {params.set('fiction','1');params.set('tiers','S,A,B,C,F');}
  const href=import.meta.env?.DEV ? `${root}syzygy/?${params}` : `${root}s/${node.id}/`;
  return `<div class="syzygy-read-links"><button type="button" class="ctl-btn" data-share-story="${escape(href)}">复制故事链接</button><a href="${escape(href)}">分享页 ↗</a><span class="syzygy-reference" data-share-status aria-live="polite"></span></div>`;
}

export function bindStoryShare(container) {
  container.querySelectorAll('[data-share-story]').forEach(button=>button.addEventListener('click',async()=>{
    const value=new URL(button.dataset.shareStory,document.baseURI).href, status=button.parentElement.querySelector('[data-share-status]');
    try { await navigator.clipboard.writeText(value); status.textContent='已复制'; }
    catch { status.textContent='请打开分享页复制地址'; }
  }));
}
