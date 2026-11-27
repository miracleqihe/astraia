/**
 * Smooth spring-eased sliding highlight glider for segmented switchers and docks.
 * Drives CSS custom properties (--glider-x, --glider-w, --glider-opacity) on `container`.
 */
export interface GliderOptions {
  itemSelector: string;
  activeSelector: string;
  followHover?: boolean;
}

export function attachNavGlider(container: HTMLElement | null, options: GliderOptions): () => void {
  if (!container || typeof window === 'undefined') return () => {};

  let hoveredItem: HTMLElement | null = null;
  let ready = false;
  let rafId = 0;

  const isVisible = (el: HTMLElement | null): el is HTMLElement =>
    Boolean(el && el.offsetParent !== null && el.offsetWidth > 0);

  const sync = () => {
    const activeItem = container.querySelector<HTMLElement>(options.activeSelector);
    const target = (options.followHover && isVisible(hoveredItem) ? hoveredItem : null)
      ?? (isVisible(activeItem) ? activeItem : null);

    if (!target) {
      container.style.setProperty('--glider-opacity', '0');
      return;
    }

    const x = target.offsetLeft;
    const w = target.offsetWidth;
    container.style.setProperty('--glider-x', `${x}px`);
    container.style.setProperty('--glider-w', `${w}px`);
    container.style.setProperty('--glider-opacity', isVisible(activeItem) ? '1' : '0.62');

    if (!ready) {
      ready = true;
      rafId = window.requestAnimationFrame(() => {
        container.dataset.gliderReady = 'true';
      });
    }
  };

  const onPointerOver = (event: Event) => {
    if (!options.followHover) return;
    const item = (event.target as Element | null)?.closest?.<HTMLElement>(options.itemSelector) ?? null;
    if (item && container.contains(item) && isVisible(item)) {
      hoveredItem = item;
      sync();
    }
  };

  const onPointerLeave = () => {
    if (!options.followHover) return;
    hoveredItem = null;
    sync();
  };

  container.addEventListener('pointerover', onPointerOver);
  container.addEventListener('pointerleave', onPointerLeave);

  const mutationObserver = new MutationObserver((records) => {
    // Ignore the CSS properties written by sync itself, otherwise this observer loops.
    if (records.some((record) => record.target !== container || record.attributeName !== 'style')) sync();
  });
  mutationObserver.observe(container, {
    subtree: true,
    attributes: true,
    attributeFilter: ['class', 'aria-pressed', 'aria-expanded', 'hidden', 'style'],
  });

  const resizeObserver = typeof ResizeObserver !== 'undefined'
    ? new ResizeObserver(() => sync())
    : null;
  resizeObserver?.observe(container);

  const onWindowResize = () => sync();
  window.addEventListener('resize', onWindowResize);
  window.addEventListener('astraia:ui-scheme', onWindowResize);

  sync();

  return () => {
    if (rafId) window.cancelAnimationFrame(rafId);
    container.removeEventListener('pointerover', onPointerOver);
    container.removeEventListener('pointerleave', onPointerLeave);
    mutationObserver.disconnect();
    resizeObserver?.disconnect();
    window.removeEventListener('resize', onWindowResize);
    window.removeEventListener('astraia:ui-scheme', onWindowResize);
  };
}
