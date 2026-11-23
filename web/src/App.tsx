import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type CSSProperties, type Dispatch, type SetStateAction } from 'react';
import { NodeDirectory } from './NodeDirectory';
import { NodeInspector } from './NodeInspector';
import { Chronology, ControlRail, QuickSearch, ViewportFrame } from './WorkbenchControls';
import {
  coordinatesOf, evidenceGroup, firstSelection, indexGraph, loadSnapshot, otherEnd, relatedNodes,
  type CodeFocus, type EvidenceGroup, type GraphNode, type GraphSnapshot, type Layer, type Tier, type ViewMode,
} from './graph';

const GeoView = lazy(() => import('./views/GeoView'));
const ConstellationView = lazy(() => import('./views/ConstellationView'));
const publicSite = import.meta.env.VITE_PUBLIC_DEMO === '1';
const ALL_TIERS: Tier[] = ['S', 'A', 'B', 'C', 'F'];
const ALL_LAYERS: Layer[] = [1, 2, 3, 4];
const ALL_EVIDENCE: EvidenceGroup[] = ['confirmed', 'unverified', 'refuted'];

function Brand() {
  return <div className="wordmark"><span className="brand-orbit" aria-hidden="true"><span /></span>
    <span className="brand-name">Astraia</span></div>;
}

function CompareSummary({ left, right, graph }: { left: GraphNode; right: GraphNode; graph: ReturnType<typeof indexGraph> }) {
  const sharedCodes = Object.entries(left.standards).flatMap(([system, values]) => {
    const other = right.standards[system as keyof GraphNode['standards']];
    if (!Array.isArray(values) || !Array.isArray(other)) return [];
    return values.filter((value) => other.includes(value)).map((value) => `${system === 'atu_types' ? 'ATU' : system === 'ocm_codes' ? 'OCM' : system === 'thompson_motifs' ? 'Thompson' : 'Berezkin'} ${value}`);
  });
  const leftNeighbors = new Set((graph.adjacency.get(left.id) ?? []).map((link) => otherEnd(link, left.id)));
  const hubs = (graph.adjacency.get(right.id) ?? []).map((link) => graph.byId.get(otherEnd(link, right.id)))
    .filter((node): node is GraphNode => !!node && node.z_layer >= 3 && leftNeighbors.has(node.id));
  const date = (node: GraphNode) => node.temporal
    ? [node.temporal.era_label, node.temporal.year_start, node.temporal.year_end].filter((value) => value !== null).join(' · ')
    : '年代未标注';
  return <div className="compare-summary"><strong>共性与差异</strong>
    <span>共享编码：{sharedCodes.join('、') || '—'}</span>
    <span>共同枢纽：{hubs.map((node) => node.title).slice(0, 4).join('、') || '—'}</span>
    <span>信源：{left.credibility_tier} / {right.credibility_tier} · {date(left)} / {date(right)}</span>
    <span>地点：{left.spatial?.location_name || '—'} / {right.spatial?.location_name || '—'}</span></div>;
}

function Atlas({ snapshot }: { snapshot: GraphSnapshot }) {
  const [mode, setMode] = useState<ViewMode>('graph');
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [tiers, setTiers] = useState(() => new Set<Tier>(ALL_TIERS));
  const [layers, setLayers] = useState(() => new Set<Layer>(ALL_LAYERS));
  const [evidence, setEvidence] = useState(() => new Set<EvidenceGroup>(ALL_EVIDENCE));
  const [activeLayer, setActiveLayer] = useState<Layer | null>(null);
  const [soloLayer, setSoloLayer] = useState<Layer | null>(null);
  const [spread, setSpread] = useState(120);
  const [selectedId, setSelectedId] = useState(() => firstSelection(snapshot.nodes));
  const [compareId, setCompareId] = useState<string | null>(null);
  const [comparePicking, setComparePicking] = useState(false);
  const [drawer, setDrawer] = useState<'collapsed' | 'single' | 'compare'>('single');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [codeFocus, setCodeFocus] = useState<CodeFocus | null>(null);
  const [pinnedCode, setPinnedCode] = useState<CodeFocus | null>(null);
  const [years, setYears] = useState<[number, number] | null>(null);

  const timeline = useMemo(() => {
    const values = snapshot.nodes.filter((node) => node.z_layer === 1)
      .map((node) => node.temporal?.year_start ?? node.temporal?.year_end)
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
    if (!values.length) return { bounds: null, ticks: [] } as { bounds: [number, number] | null; ticks: number[] };
    const min = Math.min(...values), max = Math.max(...values);
    const bins = new Map<number, number>();
    for (const value of values) bins.set(Math.round((value - min) / Math.max(1, max - min) * 120), value);
    return { bounds: [min, max] as [number, number], ticks: [...bins.values()] };
  }, [snapshot.nodes]);
  const currentYears = years ?? timeline.bounds;
  const graph = useMemo(() => {
    const nodes = snapshot.nodes.filter((node) => {
      if (!tiers.has(node.credibility_tier) || (mode === 'graph' && !layers.has(node.z_layer))) return false;
      if (node.z_layer !== 1 || !currentYears || !node.temporal) return true;
      const start = node.temporal.year_start, end = node.temporal.year_end;
      if (start === null && end === null) return true;
      return (end ?? start ?? currentYears[1]) >= currentYears[0] && (start ?? end ?? currentYears[0]) <= currentYears[1];
    });
    return indexGraph({ nodes, links: snapshot.links.filter((link) => evidence.has(evidenceGroup(link.status))) }, false);
  }, [snapshot, tiers, layers, evidence, mode, currentYears]);
  const selected = graph.byId.get(selectedId ?? '') ?? null;
  const comparison = graph.byId.get(compareId ?? '') ?? null;
  const activeComparison = drawer === 'compare' ? comparison : null;
  const sceneSelection = useMemo(() => {
    const neighbors = relatedNodes(graph, selected, 1);
    for (const [id, distance] of relatedNodes(graph, activeComparison, 1)) {
      neighbors.set(id, Math.min(neighbors.get(id) ?? 2, distance));
    }
    return { node: selected, compareNode: activeComparison, neighbors };
  }, [graph, selected, activeComparison]);
  const selection = useMemo(() => {
    const hovered = hoveredId ? graph.byId.get(hoveredId) : undefined;
    return hovered ? { node: hovered, compareNode: activeComparison, neighbors: relatedNodes(graph, hovered, 1) } : sceneSelection;
  }, [graph, hoveredId, activeComparison, sceneSelection]);
  const codeIds = useMemo(() => {
    const focus = codeFocus ?? pinnedCode;
    if (!focus) return new Set<string>();
    const key = focus.system as keyof GraphNode['standards'];
    return new Set(graph.nodes.filter((node) => {
      const values = node.standards[key];
      return Array.isArray(values) && values.includes(focus.code);
    }).map((node) => node.id));
  }, [graph.nodes, codeFocus, pinnedCode]);
  const commonIds = useMemo(() => {
    if (!selected || !activeComparison) return new Set<string>();
    const left = relatedNodes(graph, selected, 1), right = relatedNodes(graph, activeComparison, 1);
    return new Set([...left.keys()].filter((id) => right.has(id) && (graph.byId.get(id)?.z_layer ?? 0) >= 3));
  }, [graph, selected, activeComparison]);
  const mappedCount = useMemo(() => graph.nodes.filter(coordinatesOf).length, [graph]);

  const selectNode = useCallback((id: string, asCompare = false) => {
    if (!graph.byId.has(id)) return;
    if ((asCompare || comparePicking) && selectedId && id !== selectedId) {
      setCompareId(id); setComparePicking(false); setDrawer('compare');
    } else { setSelectedId(id); if (drawer === 'collapsed') setDrawer('single'); }
    setHoveredId(null);
    if (window.matchMedia('(max-width: 760px)').matches) window.requestAnimationFrame(() => document.getElementById('node-inspector')?.scrollIntoView({ block: 'start' }));
  }, [graph.byId, comparePicking, selectedId, drawer]);

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, []);

  function toggle<T>(setter: Dispatch<SetStateAction<Set<T>>>, value: T) {
    setter((old) => { const next = new Set(old); if (next.has(value)) next.delete(value); else next.add(value); return next; });
  }
  function toggleSolo(layer: Layer) { setActiveLayer(layer); setSoloLayer((previous) => previous === layer ? null : layer); }
  const width = drawer === 'collapsed' || !selected ? 40 : drawer === 'compare' ? 680 : 420;

  return <div className="app-shell">
    <header className="topbar">
      <Brand />
      <nav className="view-switch" aria-label="图谱视图">
        <button type="button" aria-pressed={mode === 'geo'} onClick={() => setMode('geo')}><span className="mode-icon globe-icon" aria-hidden="true" />3D 地图</button>
        <button type="button" aria-pressed={mode === 'graph'} onClick={() => setMode('graph')}><span className="mode-icon constellation-icon" aria-hidden="true" />语义星图</button>
      </nav>
      <div className="top-actions">
        {!publicSite && <a className="review-link" href={`${import.meta.env.BASE_URL}review/index.html`}>资料复核</a>}
        <button className="directory-toggle" type="button" aria-expanded={directoryOpen} onClick={() => setDirectoryOpen((open) => !open)}>节点目录 <span>{graph.nodes.length}</span></button>
        <button className="fiction-switch" type="button" role="switch" aria-checked={!tiers.has('F')} onClick={() => toggle<Tier>(setTiers, 'F')}>
          <span>隐藏 F 级虚构</span><span className="switch-track" aria-hidden="true" /></button>
      </div>
    </header>
    <div className="workspace workbench" style={{ '--drawer-width': `${width}px` } as CSSProperties}>
      <main id="visual-stage" className="visual-stage" aria-label="图谱主视图">
        <ViewportFrame />
        <div className="stage-heading"><h1>{mode === 'geo' ? '全球地理分布' : '四层语义星图'}</h1>
          <p>{mode === 'geo' ? `${mappedCount.toLocaleString()} 个地点` : `${graph.nodes.length.toLocaleString()} 个节点 · ${graph.links.length.toLocaleString()} 条关系`}</p></div>
        <ControlRail mode={mode} layers={layers} tiers={tiers} activeLayer={activeLayer} soloLayer={soloLayer} spread={spread}
          onLayer={(layer) => setActiveLayer((previous) => previous === layer ? null : layer)} onToggleLayer={(layer) => toggle(setLayers, layer)}
          onSolo={toggleSolo} onTier={(tier) => toggle(setTiers, tier)} onSpread={setSpread} onSearch={() => setSearchOpen(true)} />
        <Suspense fallback={<div className="stage-message" role="status">正在载入三维视图…</div>}>
          {mode === 'geo'
            ? <GeoView graph={graph} selection={sceneSelection} codeIds={codeIds} onSelect={selectNode} onOpenGraph={() => setMode('graph')} />
            : <ConstellationView graph={graph} allNodes={snapshot.nodes} selection={selection} sceneSelection={sceneSelection}
              hoveredId={hoveredId} spread={spread} soloLayer={soloLayer} activeLayer={activeLayer} codeIds={codeIds} commonIds={commonIds} evidence={evidence}
              onSelect={selectNode} onHover={setHoveredId} onLayer={setActiveLayer} onSolo={toggleSolo} onEvidence={(status) => toggle(setEvidence, status)} />}
        </Suspense>
        <Chronology bounds={timeline.bounds} value={currentYears} ticks={timeline.ticks} onChange={setYears} />
        {comparePicking && <div className="compare-hint" role="status">请选择第二个节点，或 Shift + 点击节点。</div>}
        {directoryOpen && <div className="directory-drawer" onKeyDown={(event) => { if (event.key === 'Escape') setDirectoryOpen(false); }}>
          <NodeDirectory nodes={graph.nodes} selectedId={selected?.id ?? null} onSelect={selectNode} /></div>}
      </main>
      {drawer === 'collapsed' || !selected ? <aside className="inspector-spine" aria-label="收起的卷宗">
        <button type="button" onClick={() => { if (!selected && graph.nodes.length) setSelectedId(graph.nodes[0].id); setDrawer('single'); }}>展开卷宗</button></aside>
        : <div className="inspector-drawer">
          <div className="drawer-modes" aria-label="卷宗宽度">
            <button type="button" onClick={() => setDrawer('collapsed')}>收起</button>
            <button type="button" aria-pressed={drawer === 'single'} onClick={() => setDrawer('single')}>单卷宗</button>
            <button type="button" aria-pressed={drawer === 'compare'} onClick={() => { setDrawer('compare'); if (!comparison) setComparePicking(true); }}>双卷宗</button>
          </div>
          {drawer === 'compare' && comparison && <CompareSummary left={selected} right={comparison} graph={graph} />}
          <div className={`inspector-columns${drawer === 'compare' ? ' comparing' : ''}`}>
            <NodeInspector node={selected} graph={graph} onSelect={selectNode} onClose={() => setDrawer('collapsed')}
              onCompare={() => { setDrawer('compare'); setComparePicking(true); }} onNodeHover={setHoveredId} onCodeFocus={setCodeFocus}
              onCodePin={(code) => setPinnedCode((old) => old?.system === code.system && old.code === code.code ? null : code)} />
            {drawer === 'compare' && (comparison
              ? <NodeInspector secondary node={comparison} graph={graph} onSelect={(id) => selectNode(id, true)} onClose={() => { setCompareId(null); setDrawer('single'); }}
                onCompare={() => setComparePicking(true)} onNodeHover={setHoveredId} onCodeFocus={setCodeFocus}
                onCodePin={(code) => setPinnedCode((old) => old?.system === code.system && old.code === code.code ? null : code)} />
              : <div className="compare-empty">请选择第二个节点。</div>)}
          </div>
        </div>}
    </div>
    {searchOpen && <QuickSearch nodes={snapshot.nodes} onClose={() => setSearchOpen(false)} onSelect={(id) => {
      setTiers(new Set(ALL_TIERS)); setLayers(new Set(ALL_LAYERS)); setYears(null); setHoveredId(null); setSelectedId(id); setDrawer('single');
    }} />}
  </div>;
}

export function App() {
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    loadSnapshot(controller.signal).then(setSnapshot).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '读取图谱失败。');
    });
    return () => controller.abort();
  }, [attempt]);
  if (snapshot) return <Atlas snapshot={snapshot} />;
  return <main className="loading-shell"><Brand /><div className="loading-message" role={error ? 'alert' : 'status'}>
    <h1>{error ? '图谱暂未加载' : '正在读取图谱'}</h1>{error && <p>{error}</p>}
    {error && <button type="button" className="quiet-button" onClick={() => { setError(null); setAttempt((value) => value + 1); }}>重试</button>}
  </div></main>;
}
