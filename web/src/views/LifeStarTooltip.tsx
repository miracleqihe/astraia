import type { LifeHover } from './lifeSceneTypes';

/** Gemini's star reticle and micro-card, populated only with actual book metadata. */
export default function LifeStarTooltip({ hover }: { hover: LifeHover | null }) {
  if (!hover) return null;
  return <>
    <div className="life-reticle" style={{ left: hover.x, top: hover.y }} aria-hidden="true">
      <svg viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="18" strokeDasharray="4 3" />
        <circle cx="24" cy="24" r="11" /><path d="M24 1v7 M24 40v7 M1 24h7 M40 24h7" /></svg>
    </div>
    <div className="life-tooltip" style={{ left: `clamp(4px, ${hover.x + 18}px, max(4px, 100% - 275px))`, top: hover.y + 14 }}>
      <div className="life-tooltip-meta"><span>{hover.id ?? 'DISCIPLINE'}</span>{hover.volume && <span>{hover.volume}</span>}</div>
      <strong>{hover.title}</strong><small>{hover.detail ?? '点击查看原书条目'}</small>
    </div>
  </>;
}
