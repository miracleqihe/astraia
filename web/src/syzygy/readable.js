const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);

/** Render a safe, readable subset of the original handbook's Markdown. */
export function handbookText(value, root = '/') {
  return escape(value || '本条暂无站内正文。')
    .replace(/⟦anchor:[^⟧]+⟧/g, '')
    .replace(/!\[([^\]]*)\]\(((?:inline-figures|figures)\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+\.svg)\)/g,
      (_, alt, path) => `<figure class="syzygy-book-figure"><button type="button" class="syzygy-figure-open" aria-label="放大原书图表"><img src="${escape(root)}knowledge/${path}" alt="${alt || '原书图表'}" loading="lazy"></button><figcaption>${alt || '原书图表'} · 点击放大</figcaption></figure>`)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1 ↗</a>')
    .replace(/\[([^\]]+)\]\(#[^)]+\)/g, '$1')
    .replace(/^#{1,6}\s+(.+)$/gm, '$1');
}

/** Previous/next are restricted to the same subject and follow the book's original order. */
export function bookNavigation(entry, entries) {
  const neighbors = entries.filter(item => item.subject === entry.subject);
  const at = neighbors.findIndex(item => item.id === entry.id);
  if (at < 0) return '';
  return `<nav class="syzygy-book-nav" aria-label="同学科条目翻阅">${[-1,1].map((offset,index) => {
    const item = neighbors[at + offset];
    return item ? `<button type="button" data-book-neighbor="${escape(item.id)}"><small>${index ? '下一篇' : '上一篇'}</small><span>${escape(item.title)}</span></button>`
      : `<button type="button" disabled><small>${index ? '下一篇' : '上一篇'}</small><span>已到边界</span></button>`;
  }).join('')}</nav>`;
}

export function bindBookNavigation(container, select) {
  container.querySelectorAll('[data-book-neighbor]').forEach(button => button.addEventListener('click', () => select(button.dataset.bookNeighbor)));
  container.querySelectorAll('.syzygy-figure-open').forEach(button => button.addEventListener('click', () => {
    const image = button.querySelector('img');
    const dialog = document.createElement('dialog');
    dialog.className = 'syzygy-figure-dialog';
    dialog.setAttribute('aria-label','原书图表大图');
    const header = document.createElement('div'), title = document.createElement('strong'), close = document.createElement('button');
    title.textContent = image.alt || '原书图表'; close.type = 'button'; close.textContent = '关闭 ×';
    close.addEventListener('click',()=>dialog.close());
    header.append(title,close);
    const enlarged = document.createElement('img'); enlarged.src = image.src; enlarged.alt = image.alt;
    dialog.append(header,enlarged); document.body.append(dialog);
    dialog.addEventListener('close',()=>{dialog.remove(); if (button.isConnected) button.focus();},{once:true});
    dialog.addEventListener('click',event=>{if (event.target === dialog) dialog.close();});
    dialog.showModal(); close.focus();
  }));
}
