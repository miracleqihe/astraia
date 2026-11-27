import { isCompactViewport } from '../compactViewport';

// Wire the small, useful parts of the observatory before the 3D scene loads.
let shell;

export function initSyzygyShell() {
  if (shell) return shell;
  const left = document.getElementById('left-drawer');
  const right = document.getElementById('right-drawer');
  const openLeft = document.getElementById('btn-open-left');
  const openRight = document.getElementById('btn-open-right');
  const toolsButton = document.getElementById('btn-mobile-tools');
  const toolsPanel = document.getElementById('syzygy-extra-tools');
  let onChange = () => {};
  let ready = false;
  const pending = [];
  const initialParams = new URL(window.location.href).searchParams;
  const requestedDimension = initialParams.get('dim');
  if (['umbra', 'sidera', 'omnia'].includes(requestedDimension)) {
    document.body.dataset.dimension = requestedDimension;
    document.querySelectorAll('[data-dim]').forEach(button => {
      button.classList.toggle('active', button.dataset.dim === requestedDimension);
    });
    const initialLabels = {
      umbra: ['UMBRA / 3D CELESTIAL FOLKLORE & ANOMALY GLOBE', 'UMBRA · 坤舆异志', '按真实坐标展示全球民俗与个案 · 可在目录中检索全部图谱条目'],
      sidera: ['SIDERA / NON-EUCLIDEAN MOTIF CONSTELLATION', 'SIDERA · 玄象星络', '原图谱四层条目的星域投影 · 点击星点阅读卷宗与真实关联'],
    }[requestedDimension];
    if (initialLabels) ['banner-eyebrow', 'banner-title', 'banner-desc'].forEach((id, i) => { document.getElementById(id).textContent = initialLabels[i]; });
  }
  // The return link is usable even before the 3D renderer has initialized.
  const initialView = ['map', 'graph', 'life'].includes(initialParams.get('return'))
    ? initialParams.get('return')
    : requestedDimension === 'umbra' ? 'map' : requestedDimension === 'sidera' ? 'graph' : 'life';
  const classicURL = new URL('../', window.location.href);
  classicURL.searchParams.set('view', initialView);
  const story = initialParams.get('story'), entry = initialParams.get('entry');
  if (initialView === 'life' && entry) classicURL.searchParams.set('entry', entry);
  if (initialView !== 'life' && story) classicURL.searchParams.set('story', story);
  if (story && entry) { classicURL.searchParams.set('bridge_story', story); classicURL.searchParams.set('bridge_entry', entry); }
  for (const key of ['tiers', 'genre', 'fiction']) if (initialParams.has(key)) classicURL.searchParams.set(key, initialParams.get(key));
  document.getElementById('btn-classic-view').href = classicURL.href;

  function apply(drawer, button, side, collapsed) {
    drawer.classList.toggle(`drawer-${side}-hidden`, collapsed);
    drawer.inert = collapsed;
    drawer.setAttribute('aria-hidden', String(collapsed));
    button.classList.toggle('hidden', !collapsed);
    button.classList.toggle('inline-flex', collapsed);
    button.setAttribute('aria-expanded', String(!collapsed));
    if (side === 'left') document.body.dataset.leftOpen = String(!collapsed);
  }
  function setLeftCollapsed(collapsed) {
    if (!collapsed && isCompactViewport()) apply(right, openRight, 'right', true);
    apply(left, openLeft, 'left', collapsed);
    onChange();
  }
  function setRightCollapsed(collapsed) {
    if (!collapsed && isCompactViewport()) apply(left, openLeft, 'left', true);
    apply(right, openRight, 'right', collapsed);
    onChange();
  }
  function setToolsOpen(open) {
    toolsButton.setAttribute('aria-expanded', String(open));
    toolsPanel.dataset.open = String(open);
  }

  // Keep the HTML's initial state; never undo an early tap when the scene is ready.
  apply(left, openLeft, 'left', left.classList.contains('drawer-left-hidden'));
  apply(right, openRight, 'right', right.classList.contains('drawer-right-hidden'));
  openLeft.addEventListener('click', () => setLeftCollapsed(false));
  openRight.addEventListener('click', () => setRightCollapsed(false));
  document.getElementById('btn-close-left').addEventListener('click', () => setLeftCollapsed(true));
  document.getElementById('btn-close-right').addEventListener('click', () => setRightCollapsed(true));
  toolsButton.addEventListener('click', () => setToolsOpen(toolsPanel.dataset.open !== 'true'));
  toolsPanel.addEventListener('click', event => {
    if (event.target.closest('button')) setToolsOpen(false);
  });
  document.addEventListener('pointerdown', event => {
    if (!toolsPanel.contains(event.target) && !toolsButton.contains(event.target)) setToolsOpen(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    setToolsOpen(false);
    if (isCompactViewport()) {
      if (!left.inert) setLeftCollapsed(true);
      if (!right.inert) setRightCollapsed(true);
    }
  });

  // Retain actions made during scene initialization instead of dropping taps.
  const deferredButtons = '[data-dim], [data-scope], [data-tier], [data-trail], [data-observatory-panel], [data-realm], [data-v3-focus], [data-v3-tempo], [data-v3-bridge], #btn-taxonomy-dock, #btn-syzygy-toggle, #btn-proj-toggle, #btn-reset-cam, #btn-spread-codex, #theme-btn-dark, #theme-btn-parchment';
  document.addEventListener('click', event => {
    if (ready) return;
    const target = event.target.closest?.(deferredButtons);
    if (!target) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (pending.length < 20) pending.push({ target, type: 'click' });
    if (toolsPanel.contains(target)) setToolsOpen(false);
    const status = document.getElementById('syzygy-loading');
    if (status && status.getAttribute('role') !== 'alert') status.textContent = '正在载入星图，所选操作将在完成后执行…';
  }, true);
  for (const type of ['input', 'change']) document.addEventListener(type, event => {
    if (ready || !event.target.matches?.('#codex-search, #genre-filter, #membrane-depth-slider')) return;
    if (!pending.some(item => item.target === event.target && item.type === type)) pending.push({ target: event.target, type });
  }, true);

  shell = {
    setLeftCollapsed,
    setRightCollapsed,
    setOnChange(callback) { onChange = callback; onChange(); },
    markReady() {
      ready = true;
      for (const { target, type } of pending.splice(0)) {
        if (!target.isConnected || target.disabled) continue;
        if (type === 'click') target.click();
        else target.dispatchEvent(new Event(type, { bubbles: true }));
      }
    },
  };
  return shell;
}
