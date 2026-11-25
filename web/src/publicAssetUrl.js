const configuration = (() => {
  if (typeof document === 'undefined') return {};
  const text = document.getElementById('astraia-r2-assets')?.textContent;
  return text ? JSON.parse(text) : {};
})();

export function publicAssetUrl(root, path) {
  const fallback = `${root}${path}`;
  const files = configuration.files;
  if (!files) return fallback;

  let key = path;
  if (!Object.hasOwn(files, key) && key.includes('%')) {
    // Markdown image URLs may encode Unicode filenames before reaching here.
    try { key = decodeURIComponent(key); } catch { return fallback; }
  }
  return Object.hasOwn(files, key) ? `${configuration.origin}/assets/${files[key]}` : fallback;
}
