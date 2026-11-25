/** Shared two-dimensional ornaments, brand seal, and source-tier metadata. */
export const BRAND_MARK_SVG = `<svg class="engraving-brand-mark" viewBox="0 0 64 64" aria-hidden="true" focusable="false"><rect x="3" y="3" width="58" height="58" fill="none" stroke="currentColor" stroke-width="1.3"/><rect x="8" y="8" width="48" height="48" fill="none" stroke="currentColor" stroke-width=".85"/><path d="M12 12 Q32 27 52 12 Q37 32 52 52 Q32 37 12 52 Q27 32 12 12Z M3 32H61 M32 3V61" fill="none" stroke="currentColor" stroke-width="1.15"/><path d="M32 26.5L37.5 32L32 37.5L26.5 32Z" fill="currentColor"/></svg>`;

export const TIER_META: Record<string, { label: string; title: string; summary: string }> = {
  S: { label: 'S 级信源', title: 'S 级 · 原始档案与同行评议', summary: '原始档案、田野一手记录或同行评议研究' },
  A: { label: 'A 级信源', title: 'A 级 · 学术专著与权威记录', summary: '学术数据库、权威专著或官方名录' },
  B: { label: 'B 级信源', title: 'B 级 · 地方文献与公开报道', summary: '地方志、古籍转录或可查证报刊报道' },
  C: { label: 'C 级信源', title: 'C 级 · 口述采集与流传线索', summary: '民间口述转述、社群记录或待核线索' },
  F: { label: 'F 级虚构', title: 'F 级 · 虚构隔离区', summary: '数字都市传说、文学虚构或显式创作文本' },
};

const sealPaths: Record<string, string> = {
  S: `<rect x="2" y="2" width="64" height="64" fill="none" stroke="currentColor" stroke-width="2.1"/><path d="M6 14V6H14 M54 6H62V14 M6 54V62H14 M54 62H62V54" fill="none" stroke="currentColor" stroke-width="1.9"/><rect x="9" y="9" width="50" height="50" fill="none" stroke="currentColor" stroke-width="1.15"/><path d="M13 13 Q34 29 55 13 Q39 34 55 55 Q34 39 13 55 Q29 34 13 13Z" fill="currentColor" fill-opacity=".14" stroke="currentColor" stroke-width="1.6"/><path d="M2 34H66 M34 2V66" fill="none" stroke="currentColor" stroke-width="1.1"/><rect x="24" y="24" width="20" height="20" fill="var(--seal-ground,#0c121e)" stroke="currentColor" stroke-width="1.35"/>`,
  A: `<rect x="3" y="3" width="62" height="62" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M7 13V7H13 M55 7H61V13 M7 55V61H13 M55 61H61V55" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M14 14 Q34 29 54 14 Q39 34 54 54 Q34 39 14 54 Q29 34 14 14Z" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M3 34H65 M34 3V65" fill="none" stroke="currentColor" stroke-width="1.05"/><circle cx="34" cy="34" r="10.5" fill="var(--seal-ground,#0c121e)" stroke="currentColor" stroke-width="1.5"/>`,
  B: `<rect x="4" y="4" width="60" height="60" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="9" y="9" width="50" height="50" fill="none" stroke="currentColor" stroke-width="1.0"/><path d="M15 15 Q34 28 53 15 Q40 34 53 53 Q34 40 15 53 Q28 34 15 15Z" fill="none" stroke="currentColor" stroke-width="1.35"/><polygon points="34,20.5 47.5,34 34,47.5 20.5,34" fill="var(--seal-ground,#0c121e)" stroke="currentColor" stroke-width="1.45"/>`,
  C: `<path d="M14 6 C26 3 42 3 54 6 C65 14 65 54 54 62 C42 65 26 65 14 62 C3 54 3 14 14 6Z" fill="none" stroke="currentColor" stroke-width="1.75"/><path d="M18 12 Q34 24 50 12 Q44 34 50 56 Q34 44 18 56 Q24 34 18 12Z" fill="none" stroke="currentColor" stroke-width="1.25" stroke-dasharray="4 2"/><circle cx="14" cy="14" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="54" cy="14" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="14" cy="54" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="54" cy="54" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/>`,
  F: `<path d="M40 5H5V63H63V29" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M36 9H9V59H59V33" fill="none" stroke="currentColor" stroke-width="1.05" stroke-dasharray="3 3"/><path d="M34 34 C38 22 46 18 56 12 C62 8 65 3 60 2 C55 1 51 7 55 11 M47 18 C52 21 59 20 65 15 M15 53 Q29 38 34 34 Q26 28 15 15" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="23" y="24" width="20" height="20" fill="var(--seal-ground,#0c121e)" stroke="currentColor" stroke-width="1.45" stroke-dasharray="4 2"/>`,
};

export function tierSeal(tier: string): string {
  const path = Object.hasOwn(sealPaths, tier) ? sealPaths[tier] : null;
  if (!path) return '';
  return `<svg class="engraving-seal engraving-seal-${tier.toLowerCase()}" viewBox="0 0 68 68" aria-hidden="true" focusable="false">${path}<text x="34" y="40" text-anchor="middle" fill="currentColor" font-family="Cinzel,Georgia,serif" font-weight="600" font-size="16.5">${tier}</text></svg>`;
}

type EngravingPattern = 'cloud' | 'lattice' | 'orbit';
const motif: Record<EngravingPattern, string> = {
  cloud: `<path d="M0 22 C14 7 28 7 38 22 C48 37 66 37 78 22 C90 7 106 7 120 22 M18 14 C24 14 27 20 22 24 C17 27 13 22 16 18 M56 30 C63 30 66 23 61 19 C56 16 52 21 55 25 M96 14 C103 14 106 20 101 24 C96 27 92 22 95 18 M6 34 Q22 26 36 34 M44 10 Q60 18 74 10 M84 34 Q100 26 114 34" fill="none" stroke="currentColor" stroke-width="1.1"/>`,
  lattice: `<path d="M4 9H44V35H12V15H36V29H20V21H28 M52 35H92V9H60V29H84V15H68V23H76 M48 5V39" fill="none" stroke="currentColor" stroke-width="1.2"/>`,
  orbit: `<ellipse cx="30" cy="22" rx="22" ry="12" fill="none" stroke="currentColor" stroke-width="1.15"/><ellipse cx="30" cy="22" rx="12" ry="6.5" fill="none" stroke="currentColor"/><circle cx="30" cy="22" r="2" fill="currentColor"/><ellipse cx="90" cy="22" rx="22" ry="12" fill="none" stroke="currentColor" stroke-width="1.15"/><ellipse cx="90" cy="22" rx="12" ry="6.5" fill="none" stroke="currentColor"/><circle cx="90" cy="22" r="2" fill="currentColor"/><path d="M0 22H120" stroke="currentColor" stroke-width=".7" stroke-dasharray="3 3"/>`,
};
export function engravingPatternForVolume(volume: string | number | undefined): EngravingPattern {
  if (volume === 0 || volume === 2 || volume === '生存卷' || volume === '造物卷' || volume === 'vol1' || volume === 'vol3') return 'lattice';
  if (volume === 1 || volume === 3 || volume === '世界卷' || volume === '数与人卷' || volume === 'vol2' || volume === 'vol4') return 'orbit';
  return 'cloud';
}
export function engravingFrieze(pattern: EngravingPattern, id: string): string {
  if (!/^[a-z0-9-]+$/.test(id)) throw new Error('Invalid engraving identifier');
  const width = pattern === 'lattice' ? 96 : 120;
  return `<svg class="engraving-frieze" aria-hidden="true" focusable="false" preserveAspectRatio="xMinYMid slice"><defs><pattern id="${id}" width="${width}" height="44" patternUnits="userSpaceOnUse"><path d="M0 2H${width} M0 5H${width} M0 39H${width} M0 42H${width}" fill="none" stroke="currentColor" stroke-width=".8"/>${motif[pattern]}</pattern></defs><rect width="100%" height="44" fill="url(#${id})"/></svg>`;
}

const entities: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const escape = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, c => entities[c]);
export function engravingHeader(label: string, detail: string, tier: string | undefined, pattern: EngravingPattern = 'cloud'): string {
  const tierInfo = tier && Object.hasOwn(TIER_META, tier) ? TIER_META[tier] : null;
  const sealMarkup = tier ? `<span class="engraving-codex-seal" title="${escape(tierInfo?.title ?? `${tier} 级信源`)}">${tierSeal(tier)}</span>` : '';
  return `<header class="engraving-codex-head">${engravingFrieze(pattern, 'engraving-codex-pattern')}<div class="engraving-codex-heading"><span>ASTRAIA / SYZYGY CODEX</span><strong>${escape(label)}</strong>${detail ? `<small>${escape(detail)}</small>` : ''}</div>${sealMarkup}</header>`;
}

/** The beam controls visibility only; relationship evidence stays in its own text. */
export function engravingBeam(interactive: boolean): string {
  const svg = `<svg viewBox="0 0 600 48" aria-hidden="true" focusable="false"><g fill="none" stroke="currentColor"><rect x="2" y="11" width="54" height="26"/><path d="M7 15H27V33H11V19H22V28H16 M51 15H31V33H47V19H36V28H42"/><rect x="544" y="11" width="54" height="26"/><path d="M549 15H569V33H553V19H564V28H558 M593 15H573V33H589V19H578V28H584"/><rect x="56" y="13" width="208" height="22"/><rect x="336" y="13" width="208" height="22"/><path class="engraving-beam-flow" d="M56 24H264 M336 24H544" stroke-dasharray="8 6"/><path d="M282 2H318L322 46H278Z" fill="var(--engrave-inset,#060910)"/><rect x="264" y="10" width="72" height="28" fill="var(--engrave-surface,#0b0f18)"/><path d="M286 14 Q300 22 314 14 Q305 24 314 34 Q300 26 286 34 Q295 24 286 14Z"/><circle cx="300" cy="24" r="3.5" fill="currentColor"/></g></svg>`;
  return interactive ? `<button type="button" class="engraving-beam" data-engraved-bridge aria-pressed="true" aria-label="隐藏折光星桥">${svg}<span data-engraved-bridge-label>折光星桥 · 显示中</span></button>`
    : `<div class="engraving-beam engraving-beam-static" aria-hidden="true">${svg}</div>`;
}

export function mountEngravingCorners(element: Element): void {
  if (element.querySelector(':scope > .engraving-corner')) return;
  const corner = `<path d="M1 19V1H19 M4.5 15V4.5H15V9.5H9.5V7" fill="none" stroke="currentColor" stroke-width="1.5"/>`;
  element.insertAdjacentHTML('afterbegin', ['nw', 'ne', 'sw', 'se'].map(position =>
    `<svg class="engraving-corner engraving-corner-${position}" viewBox="0 0 20 20" aria-hidden="true" focusable="false">${corner}</svg>`).join(''));
}

export function bindEngravingBeam(container: ParentNode): void {
  const button = container.querySelector<HTMLButtonElement>('[data-engraved-bridge]');
  if (!button) return;
  button.addEventListener('click', () => document.getElementById('btn-syzygy-toggle')?.click());
  syncEngravingBeam(container);
}
export function syncEngravingBeam(container: ParentNode = document): void {
  const button = container.querySelector<HTMLButtonElement>('[data-engraved-bridge]');
  if (!button) return;
  const active = document.getElementById('btn-syzygy-toggle')?.classList.contains('active') ?? false;
  button.setAttribute('aria-pressed', String(active));
  button.setAttribute('aria-label', active ? '隐藏折光星桥' : '显示折光星桥');
  const label = button.querySelector('[data-engraved-bridge-label]');
  if (label) label.textContent = active ? '折光星桥 · 显示中' : '折光星桥 · 已隐藏';
}
