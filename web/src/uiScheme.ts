export type UIScheme = '1' | '2';

const UI_SCHEME_KEY = 'astraia-ui-scheme';

export function readUIScheme(): UIScheme {
  try {
    const param = new URL(window.location.href).searchParams.get('scheme');
    if (param === '1' || param === '2') {
      localStorage.setItem(UI_SCHEME_KEY, param);
      return param;
    }
    const stored = localStorage.getItem(UI_SCHEME_KEY);
    if (stored === '1' || stored === '2') return stored;
  } catch {
    // Ignore storage or URL errors in non-browser environments.
  }
  return '2';
}

export function applyUIScheme(scheme: UIScheme): UIScheme {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.uiScheme = scheme;
    if (document.body) document.body.dataset.uiScheme = scheme;
  }
  try {
    localStorage.setItem(UI_SCHEME_KEY, scheme);
    const url = new URL(window.location.href);
    if (url.searchParams.has('scheme')) {
      url.searchParams.set('scheme', scheme);
      window.history.replaceState({}, '', url);
    }
  } catch {
    // Ignore storage or history errors.
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('astraia:ui-scheme', { detail: scheme }));
  }
  return scheme;
}

export function initUIScheme(): UIScheme {
  return applyUIScheme(readUIScheme());
}

/** Keep the classic view and its retained Syzygy frame in the same scheme. */
export function subscribeUIScheme(onChange: (scheme: UIScheme) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const sync = (event: StorageEvent) => {
    if (event.key !== UI_SCHEME_KEY || (event.newValue !== '1' && event.newValue !== '2')) return;
    onChange(applyUIScheme(event.newValue));
  };
  window.addEventListener('storage', sync);
  return () => window.removeEventListener('storage', sync);
}
