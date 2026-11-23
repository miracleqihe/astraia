import { useEffect, useMemo, useState } from 'react';
import { LAYERS, matchesQuery, type GraphNode, type Layer, type Tier, type ViewMode } from './graph';

const TIERS: Tier[] = ['S', 'A', 'B', 'C', 'F'];
const LAYERS_DESC: Layer[] = [4, 3, 2, 1];

export function ViewportFrame() {
  return <div className="viewport-frame" aria-hidden="true">
    <i className="frame-corner nw">+</i><i className="frame-corner ne">+</i>
    <i className="frame-corner sw">+</i><i className="frame-corner se">+</i>
    <span className="frame-ticks frame-ticks-top" /><span className="frame-ticks frame-ticks-bottom" />
    <span className="frame-ticks frame-ticks-left" /><span className="frame-ticks frame-ticks-right" />
  </div>;
}

interface RailProps {
  mode: ViewMode;
  layers: Set<Layer>;
  tiers: Set<Tier>;
  activeLayer: Layer | null;
  soloLayer: Layer | null;
  spread: number;
  onLayer: (layer: Layer) => void;
  onToggleLayer: (layer: Layer) => void;
  onSolo: (layer: Layer) => void;
  onTier: (tier: Tier) => void;
  onSpread: (value: number) => void;
  onSearch: () => void;
}

export function ControlRail(props: RailProps) {
  return <aside className="control-rail" aria-label="图层与信源筛选">
    <button type="button" className="rail-search" onClick={props.onSearch} title="搜索节点 (Ctrl/⌘ K)" aria-label="搜索节点">⌕ <small>⌘K</small></button>
    {props.mode === 'graph' && <>
      <span className="rail-caption">LAYERS</span>
      {LAYERS_DESC.map((layer) => <div className="rail-layer" key={layer}>
        <button type="button" className="rail-layer-name" aria-pressed={props.activeLayer === layer || props.soloLayer === layer}
          onClick={() => props.onLayer(layer)} onDoubleClick={() => props.onSolo(layer)} title="点击聚焦，双击平铺">
          <b>L{layer}</b><span>{LAYERS[layer].short}</span></button>
        <button type="button" className="rail-layer-visibility" aria-label={`${props.layers.has(layer) ? '隐藏' : '显示'} L${layer}`}
          aria-pressed={props.layers.has(layer)} onClick={() => props.onToggleLayer(layer)}>{props.layers.has(layer) ? '■' : '□'}</button>
      </div>)}
      <button type="button" className="rail-solo" onClick={() => props.onSolo(props.activeLayer || 1)}>
        {props.soloLayer ? '恢复分层' : '平铺当前层'}
      </button>
      <label className="rail-spread"><span>层距</span><input type="range" min="60" max="220" step="10" value={props.spread}
        aria-label="Z 轴层距" onChange={(event) => props.onSpread(Number(event.target.value))} /></label>
    </>}
    <span className="rail-caption">SOURCE</span>
    <div className="rail-tiers">{TIERS.map((tier) => <button key={tier} type="button" aria-label={`${tier} 级信源`}
      aria-pressed={props.tiers.has(tier)} onClick={() => props.onTier(tier)}>{tier}</button>)}</div>
  </aside>;
}

interface TimelineProps {
  bounds: [number, number] | null;
  value: [number, number] | null;
  ticks: number[];
  onChange: (value: [number, number]) => void;
}

export function Chronology({ bounds, value, ticks, onChange }: TimelineProps) {
  if (!bounds || !value || bounds[0] === bounds[1]) return null;
  const [minimum, maximum] = bounds;
  return <div className="chronology" aria-label="年代筛选">
    <span className="chronology-title">年代</span>
    <div className="chronology-track">
      <div className="chronology-ticks" aria-hidden="true">{ticks.map((year) => <i key={year}
        style={{ left: `${((year - minimum) / (maximum - minimum)) * 100}%` }} />)}</div>
      <input aria-label="起始年份" type="range" min={minimum} max={maximum} value={value[0]}
        onChange={(event) => onChange([Math.min(Number(event.target.value), value[1]), value[1]])} />
      <input aria-label="结束年份" type="range" min={minimum} max={maximum} value={value[1]}
        onChange={(event) => onChange([value[0], Math.max(Number(event.target.value), value[0])])} />
    </div>
    <span className="chronology-value">{value[0]} — {value[1]}</span>
  </div>;
}

export function QuickSearch({ nodes, onClose, onSelect }: {
  nodes: GraphNode[]; onClose: () => void; onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState('');
  const matching = useMemo(() => {
    const text = query.trim();
    if (!text) return nodes.slice(0, 20);
    const result: GraphNode[] = [];
    for (const node of nodes) {
      if (matchesQuery(node, text)) result.push(node);
      if (result.length === 50) break;
    }
    return result;
  }, [nodes, query]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [onClose]);
  return <div className="search-backdrop" onMouseDown={onClose}>
    <section className="quick-search" role="dialog" aria-modal="true" aria-label="搜索图谱" onMouseDown={(event) => event.stopPropagation()}>
      <div className="quick-search-head"><label htmlFor="quick-search-input">搜索图谱</label>
        <button type="button" aria-label="关闭搜索" onClick={onClose}>×</button></div>
      <input id="quick-search-input" autoFocus type="search" value={query} placeholder="标题、ATU / OCM、地点"
        onChange={(event) => setQuery(event.target.value)} />
      <div className="quick-search-results">{matching.map((node) => <button key={node.id} type="button"
        onClick={() => { onSelect(node.id); onClose(); }}><b>L{node.z_layer}</b><span>{node.title}</span></button>)}
        {!matching.length && <p>没有找到匹配资料。</p>}</div>
    </section>
  </div>;
}
