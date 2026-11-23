export function ViewControls({ onZoom, onReset, onTilt, tilted }: {
  onZoom: (direction: -1 | 1) => void;
  onReset: () => void;
  onTilt?: () => void;
  tilted?: boolean;
}) {
  return (
    <div className="scene-controls" aria-label="视角控制" role="group">
      <button type="button" aria-label="还原视角" title="还原视角" onClick={onReset}>
        <span className="focus-icon" aria-hidden="true" />
      </button>
      <button type="button" aria-label="放大" title="放大" onClick={() => onZoom(1)}>+</button>
      <button type="button" aria-label="缩小" title="缩小" onClick={() => onZoom(-1)}>−</button>
      {onTilt && <button type="button" className="pitch-button" aria-label="倾斜视角" title="倾斜视角"
        aria-pressed={tilted} onClick={onTilt}><span aria-hidden="true" /></button>}
    </div>
  );
}

export function motionDuration(duration: number): number {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : duration;
}
