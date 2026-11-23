export function ViewControls({ onZoom, onReset }: {
  onZoom: (direction: -1 | 1) => void;
  onReset: () => void;
}) {
  return (
    <div className="scene-controls" aria-label="视角控制" role="group">
      <button type="button" aria-label="还原视角" title="还原视角" onClick={onReset}>
        <span className="focus-icon" aria-hidden="true" />
      </button>
      <button type="button" aria-label="放大" title="放大" onClick={() => onZoom(1)}>+</button>
      <button type="button" aria-label="缩小" title="缩小" onClick={() => onZoom(-1)}>−</button>
    </div>
  );
}

export function motionDuration(duration: number): number {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : duration;
}
