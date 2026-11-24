import { useEffect, useMemo, useRef, useState } from 'react';
import type { LifeEntry, LifeSubject } from '../life';
import { LIFE_PALETTES, lifeGalaxyLayout } from './lifeGalaxyLayout';
import { animateLifeGravity, createLifeGravity } from './lifeGravity';
import { createLifePortal } from './lifePortal';
import type { LifeHover } from './lifeSceneTypes';

interface Props {
  entries: LifeEntry[];
  subjects: LifeSubject[];
  selectedId: string | null;
  subjectId: string | null;
  volumeId: string | null;
  highlightIds: readonly string[];
  connectHighlights: boolean;
  resetSerial: number;
  onSelect: (id: string) => void;
  onSubject: (id: string) => void;
}

/** Flat, orthographic projection of the same precomputed positions as the 3D scene. */
export default function LifeAstrolabe(props: Props) {
  const { entries, subjects, selectedId, subjectId, volumeId, highlightIds, resetSerial } = props;
  const host = useRef<HTMLDivElement>(null);
  const layout = useMemo(() => lifeGalaxyLayout(entries, subjects), [entries, subjects]);
  const current = useRef(props); current.current = props;
  const repaint = useRef<() => void>(() => {});
  const navigate = useRef<(selected: string | null, subject: string | null, volume: string | null) => void>(() => {});
  const reset = useRef<() => void>(() => {});
  const [hover, setHover] = useState<LifeHover | null>(null);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const canvas = document.createElement('canvas'); canvas.dataset.renderer = 'astrolabe';
    const context = canvas.getContext('2d', { alpha: false });
    if (!context) throw new Error('无法创建星盘画布');
    const ctx: CanvasRenderingContext2D = context;
    element.prepend(canvas);
    const portal = createLifePortal(element, entries, layout, (id) => current.current.onSelect(id));
    let width = 1, height = 1, zoom = 1, panX = 0, panY = 0, frame = 0;
    let downX = 0, downY = 0, previousX = 0, previousY = 0, dragging = false, moved = false, lastHover = '';
    let gravityTimer = 0, gravityHeld = false;
    const gravity = createLifeGravity(entries, layout);
    const gravityAnimation = animateLifeGravity(gravity, schedule);
    const byId = new Map(entries.map((entry) => [entry.id, entry]));
    const entryIndex = new Map(entries.map((entry, index) => [entry.id, index]));
    const volumeIndex = new Map(layout.volumes.map((volume, index) => [volume, index]));
    const volumeCenters = layout.volumes.map((volume) => {
      const points = subjects.filter((subject) => subject.volume === volume).flatMap((subject) => layout.centers.get(subject.id) ?? []);
      return { volume, x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
        y: points.reduce((sum, point) => sum + point.y, 0) / points.length };
    });
    const scale = () => Math.min(width, height) / 1040 * zoom;
    const screenOffset = () => width > 1100 ? 108 : width > 760 ? 90 : 0;
    const project = (x: number, y: number) => [width / 2 - screenOffset() + panX + x * scale(), height / 2 + panY - y * scale()];
    function schedule() { if (!frame) frame = requestAnimationFrame(draw); }
    function draw() {
      frame = 0;
      const state = current.current;
      const highlighted = new Set(state.highlightIds);
      const chosen = state.selectedId ? byId.get(state.selectedId) : undefined;
      portal.select(state.selectedId);
      const related = new Set(chosen?.links ?? []);
      if (chosen) for (const entry of entries) if (entry.links.includes(chosen.id)) related.add(entry.id);
      ctx.fillStyle = '#04060c'; ctx.fillRect(0, 0, width, height);
      const [centerX, centerY] = project(0, 0);
      ctx.strokeStyle = 'rgba(225,215,193,.12)'; ctx.lineWidth = 1;
      for (const radius of [90, 200, 320, 445]) {
        ctx.beginPath(); ctx.arc(centerX, centerY, radius * scale(), 0, Math.PI * 2); ctx.stroke();
      }
      const edges: Array<[string, string]> = chosen
        ? [...related].map((id) => [chosen.id, id])
        : state.connectHighlights ? state.highlightIds.slice(1).map((id, index) => [state.highlightIds[index], id]) : [];
      ctx.strokeStyle = 'rgba(227,190,120,.66)'; ctx.lineWidth = 1;
      ctx.beginPath();
      for (const [a, b] of edges) {
        const from = layout.locations.get(a), to = layout.locations.get(b);
        if (!from || !to) continue;
        const [x1, y1] = project(from.x, from.y), [x2, y2] = project(to.x, to.y);
        ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
      }
      ctx.stroke();
      // Batch all stars by color and visibility to keep the flat view responsive
      // even when the browser has no accelerated graphics context.
      for (let volume = 0; volume < layout.volumes.length; volume++) for (const dim of [true, false]) {
        ctx.fillStyle = LIFE_PALETTES[volume % LIFE_PALETTES.length]; ctx.globalAlpha = dim ? .22 : .92;
        ctx.beginPath();
        entries.forEach((entry, index) => {
          if (volumeIndex.get(entry.volume) !== volume) return;
          const faded = !!(state.subjectId && entry.subject !== state.subjectId)
            || !!(state.volumeId && entry.volume !== state.volumeId)
            || !!(chosen && entry.id !== chosen.id && !related.has(entry.id))
            || !!(!chosen && highlighted.size && !highlighted.has(entry.id));
          if (faded !== dim) return;
          const [x, y] = project(layout.positions[index * 3], layout.positions[index * 3 + 1]);
          if (x >= -3 && x <= width + 3 && y >= -3 && y <= height + 3) ctx.rect(x - 1.15, y - 1.15, 2.3, 2.3);
        });
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      for (const subject of subjects) {
        const point = layout.centers.get(subject.id); if (!point) continue;
        const [x, y] = project(point.x, point.y);
        ctx.strokeStyle = '#edc989'; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x - 5, y); ctx.lineTo(x + 5, y); ctx.moveTo(x, y - 5); ctx.lineTo(x, y + 5); ctx.stroke();
        if (state.subjectId === subject.id) {
          ctx.font = '12px "Noto Sans SC", sans-serif'; ctx.fillStyle = '#efece6'; ctx.fillText(subject.title, x + 9, y - 7);
        }
      }
      if (!state.subjectId && !chosen && zoom < 1.8) for (const group of volumeCenters) {
        const [x, y] = project(group.x, group.y);
        ctx.font = '11px "Noto Sans SC", sans-serif'; ctx.fillStyle = 'rgba(239,236,230,.72)';
        ctx.fillText(group.volume, x + 9, y - 12);
      }
      if (chosen) {
        const point = layout.locations.get(chosen.id);
        if (point) { const [x, y] = project(point.x, point.y); ctx.strokeStyle = '#fff1cf';
          ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI * 2); ctx.stroke(); portal.position(x + 10, y + 10, x >= 0 && x < width && y >= 0 && y < height); }
      }
    }
    const resize = () => {
      width = Math.max(1, element.clientWidth); height = Math.max(1, element.clientHeight);
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5, Math.sqrt(1_500_000 / (width * height)));
      canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0); schedule();
    };
    const observer = new ResizeObserver(resize); observer.observe(element); resize();
    const hit = (x: number, y: number) => {
      const selected = current.current.selectedId;
      const selectedPoint = selected ? layout.locations.get(selected) : undefined;
      const selectedIndex = selected ? entryIndex.get(selected) : undefined;
      if (selectedPoint && selectedIndex !== undefined) {
        const [px, py] = project(selectedPoint.x, selectedPoint.y);
        if ((px - x) ** 2 + (py - y) ** 2 < 36) return { kind: 'node' as const, index: selectedIndex };
      }
      let distance = 10 * 10, target: { kind: 'hub' | 'node'; index: number } | null = null;
      subjects.forEach((subject, index) => {
        const point = layout.centers.get(subject.id); if (!point) return;
        const [px, py] = project(point.x, point.y), d = (px - x) ** 2 + (py - y) ** 2;
        if (d < distance) { distance = d; target = { kind: 'hub', index }; }
      });
      if (target) return target;
      entries.forEach((_, index) => {
        const [px, py] = project(layout.positions[index * 3], layout.positions[index * 3 + 1]);
        const d = (px - x) ** 2 + (py - y) ** 2;
        if (d < distance) { distance = d; target = { kind: 'node', index }; }
      });
      return target as { kind: 'hub' | 'node'; index: number } | null;
    };
    const restoreGravity = () => {
      window.clearTimeout(gravityTimer); gravityTimer = 0;
      if (gravityHeld) { gravityHeld = false; gravityAnimation.release(); }
    };
    const pointerDown = (event: PointerEvent) => {
      dragging = true; moved = false; downX = previousX = event.clientX; downY = previousY = event.clientY;
      canvas.setPointerCapture(event.pointerId); setHover(null);
      const box = canvas.getBoundingClientRect(), target = hit(event.clientX - box.left, event.clientY - box.top);
      if (target?.kind === 'node') gravityTimer = window.setTimeout(() => {
        const id = entries[target.index].id; gravityHeld = true; gravityAnimation.pull(id); current.current.onSelect(id); schedule();
      }, 480);
    };
    const pointerMove = (event: PointerEvent) => {
      if (dragging) {
        panX += event.clientX - previousX; panY += event.clientY - previousY;
        previousX = event.clientX; previousY = event.clientY;
        moved ||= Math.hypot(event.clientX - downX, event.clientY - downY) > 5;
        if (moved) restoreGravity();
        schedule(); return;
      }
      const box = canvas.getBoundingClientRect(), x = event.clientX - box.left, y = event.clientY - box.top;
      const target = hit(x, y), key = target ? `${target.kind}:${target.index}` : '';
      canvas.style.cursor = target ? 'pointer' : 'grab';
      if (key !== lastHover) {
        lastHover = key;
        setHover(target ? { x, y, title: target.kind === 'hub' ? `学科 · ${subjects[target.index].title}` : entries[target.index].title } : null);
      }
    };
    const pointerUp = (event: PointerEvent) => {
      if (!dragging) return;
      dragging = false;
      const wasHeld = gravityHeld; restoreGravity();
      if (wasHeld) return;
      if (moved) return;
      const box = canvas.getBoundingClientRect(), target = hit(event.clientX - box.left, event.clientY - box.top);
      if (target?.kind === 'hub') current.current.onSubject(subjects[target.index].id);
      else if (target) current.current.onSelect(entries[target.index].id);
    };
    const pointerCancel = () => { dragging = false; restoreGravity(); };
    const leave = () => { lastHover = ''; setHover(null); };
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const box = canvas.getBoundingClientRect(), x = event.clientX - box.left - width / 2 + screenOffset(), y = event.clientY - box.top - height / 2;
      const next = Math.max(.65, Math.min(6, zoom * Math.exp(-event.deltaY * .001)));
      const factor = next / zoom; panX = x - (x - panX) * factor; panY = y - (y - panY) * factor;
      zoom = next; schedule();
    };
    canvas.addEventListener('pointerdown', pointerDown); canvas.addEventListener('pointermove', pointerMove);
    canvas.addEventListener('pointerup', pointerUp); canvas.addEventListener('pointercancel', pointerCancel);
    canvas.addEventListener('pointerleave', leave); canvas.addEventListener('wheel', wheel, { passive: false });
    repaint.current = schedule;
    navigate.current = (selected, subject, volume) => {
      const point = selected ? layout.locations.get(selected) : subject ? layout.centers.get(subject) : volume ? layout.volumeCenters.get(volume) : undefined;
      if (point) { zoom = selected ? 2.8 : subject ? 1.8 : 1.4; panX = -point.x * scale(); panY = point.y * scale(); }
      schedule();
    };
    reset.current = () => { zoom = 1; panX = panY = 0; schedule(); };
    navigate.current(current.current.selectedId, current.current.subjectId, current.current.volumeId);
    return () => {
      restoreGravity(); gravityAnimation.dispose(); portal.dispose(); cancelAnimationFrame(frame); observer.disconnect();
      canvas.removeEventListener('pointerdown', pointerDown); canvas.removeEventListener('pointermove', pointerMove);
      canvas.removeEventListener('pointerup', pointerUp); canvas.removeEventListener('pointercancel', pointerCancel);
      canvas.removeEventListener('pointerleave', leave); canvas.removeEventListener('wheel', wheel); canvas.remove();
      repaint.current = () => {}; navigate.current = () => {}; reset.current = () => {};
    };
  }, [entries, subjects, layout]);
  useEffect(() => { navigate.current(selectedId, subjectId, volumeId); }, [selectedId, subjectId, volumeId]);
  useEffect(() => { repaint.current(); }, [highlightIds, selectedId, subjectId, volumeId]);
  useEffect(() => { if (resetSerial) reset.current(); }, [resetSerial]);
  return <div className="life-scene life-astrolabe" ref={host} aria-label="二维知识星盘：拖动平移，滚轮缩放，点击星点或学科">
    {hover && <div className="life-tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>{hover.title}</div>}
  </div>;
}
