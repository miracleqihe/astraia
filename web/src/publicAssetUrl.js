const configuration = (() => {
  if (typeof document === 'undefined') return {};
  const text = document.getElementById('astraia-r2-assets')?.textContent;
  return text ? JSON.parse(text) : {};
})();

export function publicAssetUrl(root, path) {
  const file = configuration.files && Object.hasOwn(configuration.files, path) && configuration.files[path];
  return file ? `${configuration.origin}/assets/${file}` : `${root}${path}`;
}
