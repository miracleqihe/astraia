const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);

/** Render a safe, readable subset of the original handbook's Markdown. */
export function handbookText(value) {
  return escape(value || '本条暂无站内正文。')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1 ↗</a>')
    .replace(/\[([^\]]+)\]\(#[^)]+\)/g, '$1')
    .replace(/^#{1,6}\s+(.+)$/gm, '$1');
}
