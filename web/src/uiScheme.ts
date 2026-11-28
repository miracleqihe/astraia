export type UIScheme = 'cosmos' | 'shanhai';

const UI_SCHEME_KEY = 'astraia-ui-mode-v1';

export const UI_SCHEME_META: Record<UIScheme, { short: string; full: string }> = {
  cosmos: { short: '星野', full: '星野界膜 · 流体星轨玻璃' },
  shanhai: { short: '山海', full: '山海绘卷 · 古刻泥金星图' },
};

function normalizeScheme(raw: string | null): UIScheme | null {
  if (raw === 'cosmos' || raw === '1' || raw === '2') return 'cosmos';
  if (raw === 'shanhai' || raw === '3') return 'shanhai';
  return null;
}

export function readUIScheme(): UIScheme {
  try {
    const param = normalizeScheme(new URL(window.location.href).searchParams.get('scheme'));
    if (param) {
      localStorage.setItem(UI_SCHEME_KEY, param);
      return param;
    }
    const stored = normalizeScheme(localStorage.getItem(UI_SCHEME_KEY));
    if (stored) return stored;
  } catch {
    // Ignore storage or URL errors in non-browser environments.
  }
  return 'shanhai';
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

export function subscribeUIScheme(onChange: (scheme: UIScheme) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const sync = (event: StorageEvent) => {
    if (event.key !== UI_SCHEME_KEY || (event.newValue !== 'cosmos' && event.newValue !== 'shanhai')) return;
    onChange(applyUIScheme(event.newValue));
  };
  window.addEventListener('storage', sync);
  return () => window.removeEventListener('storage', sync);
}
