import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type CSSProperties, type Dispatch, type SetStateAction } from 'react';
import { CollectionGuide } from './CollectionGuide';
import { nodeContentGroup, type ContentGroup, type Region } from './catalogueBrowse';
import { DossierComparison } from './DossierComparison';
import { NodeDirectory, type DirectoryScope } from './NodeDirectory';
import { NodeInspector } from './NodeInspector';
import { Chronology, ControlRail, QuickSearch, ViewportFrame } from './WorkbenchControls';
import {
  codeKey, coordinatesOf, dossierCodes, evidenceGroup, firstSelection, indexGraph, isFiction, isModernReading, loadGraphDetails, loadSnapshot, relatedNodes, STANDARDS,
  type CodeFocus, type EvidenceGroup, type GraphDetails, type GraphNode, type GraphSnapshot, type Layer, type Tier, type ViewMode,
} from './graph';
import { loadOverviewMapFonts } from './views/geoFonts';

let geoPromise: Promise<typeof import('./views/GeoView')> | undefined;
let constellationPromise: Promise<typeof import('./views/ConstellationView')> | undefined;
function loadGeoView() { return geoPromise ??= import('./views/GeoView').catch((error) => { geoPromise = undefined; throw error; }); }
function loadConstellationView() { return constellationPromise ??= import('./views/ConstellationView').catch((error) => { constellationPromise = undefined; throw error; }); }
const GeoView = lazy(loadGeoView);
const ConstellationView = lazy(loadConstellationView);
const LifeKnowledge = lazy(() => import('./LifeKnowledge'));
const publicSite = import.meta.env.VITE_PUBLIC_DEMO === '1';
const ALL_TIERS: Tier[] = ['S', 'A', 'B', 'C', 'F'];
const ALL_LAYERS: Layer[] = [1, 2, 3, 4];
const ALL_EVIDENCE: EvidenceGroup[] = ['confirmed', 'unverified', 'refuted'];
const EMPTY_SNAPSHOT: GraphSnapshot = { schema_version: 1, snapshot_id: '', nodes: [], links: [] };

function Brand() {
  return <div className="wordmark"><span className="brand-orbit" aria-hidden="true"><span /></span>
    <span className="brand-name">Astraia</span></div>;
}

function SyzygyLink({ dimension, story, showFiction }: { dimension: 'umbra' | 'sidera' | 'omnia'; story?: string | null; showFiction?: boolean }) {
  const query = new URLSearchParams({ dim: dimension });
  const initialStory = dimension === 'omnia' ? null : story || new URL(window.location.href).searchParams.get('story');
  if (initialStory) query.set('story', initialStory);
  if (showFiction ?? new URL(window.location.href).searchParams.get('fiction') === '1') query.set('fiction', '1');
  return <a className="syzygy-entry" href={`${import.meta.env.BASE_URL}syzygy/?${query}`} aria-label="切换到朔望叠影视图" onClick={(event) => {
    const current = new URL(window.location.href);
    const destination = new URL(event.currentTarget.href);
    if (dimension === 'omnia') {
      const entry = current.searchParams.get('entry');
      if (entry) destination.searchParams.set('entry', entry);
    } else {
      const currentStory = story || current.searchParams.get('story');
      if (currentStory) destination.searchParams.set('story', currentStory);
    }
    event.currentTarget.href = destination.toString();
  }}>
    ◐ <span className="syzygy-entry-full">朔望叠影</span><span className="syzygy-entry-short" aria-hidden="true">叠影</span></a>;
}

function ViewSwitch({ mode, lifeMode, onSwitch }: { mode: ViewMode; lifeMode: boolean; onSwitch: (next: ViewMode | 'life') => void }) {
  return <nav className="view-switch" aria-label="图谱视图">
    <button type="button" aria-label="UMBRA 坤舆异志" aria-pressed={!lifeMode && mode === 'geo'} onClick={() => onSwitch('geo')}>
      <span className="mode-icon globe-icon" aria-hidden="true" /><span className="mode-full">UMBRA · 坤舆异志</span><span className="mode-short" aria-hidden="true">UMBRA</span></button>
    <button type="button" aria-label="SIDERA 玄象星络" aria-pressed={!lifeMode && mode === 'graph'} onClick={() => onSwitch('graph')}>
      <span className="mode-icon constellation-icon" aria-hidden="true" /><span className="mode-full">SIDERA · 玄象星络</span><span className="mode-short" aria-hidden="true">SIDERA</span></button>
    <button type="button" aria-label="OMNIA 万象星枢" aria-pressed={lifeMode} onClick={() => onSwitch('life')}>
      <span className="mode-icon constellation-icon" aria-hidden="true" /><span className="mode-life-full">OMNIA · 万象星枢</span>
      <span className="mode-life-short" aria-hidden="true">OMNIA</span>
    </button>
  </nav>;
}

function Atlas({ snapshot, loading, details, detailsError, onNeedDetails, onRetryDetails, onEnterLifeWhileLoading }: {
  snapshot: GraphSnapshot; loading: boolean; details: GraphDetails | null; detailsError: string;
  onNeedDetails: () => void; onRetryDetails: () => void; onEnterLifeWhileLoading: () => void;
}) {
  const [entry] = useState(() => {
    const url = new URL(window.location.href);
    const requested = snapshot.nodes.find((node) => node.id === url.searchParams.get('story'));
    const compared = requested && snapshot.nodes.find((node) => node.id !== requested.id && node.id === url.searchParams.get('compare'));
    const view = url.searchParams.get('view');
    const mode: ViewMode = view === 'map' ? 'geo' : view === 'graph' ? 'graph'
      : loading || snapshot.nodes.some(isModernReading) ? 'geo' : 'graph';
    return { mode, selectedId: requested?.id ?? null, compareId: compared?.id ?? null,
      showFiction: url.searchParams.get('fiction') === '1' || (requested && isFiction(requested)) || (compared && isFiction(compared)),
      focus: requested && coordinatesOf(requested) ? { id: requested.id } : null };
  });
  const [mode, setMode] = useState<ViewMode>(entry.mode);
  const [lifeMode, setLifeMode] = useState(() => new URL(window.location.href).searchParams.get('view') === 'life');
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [directoryScope, setDirectoryScope] = useState<DirectoryScope>('all');
  const [directoryRegion, setDirectoryRegion] = useState<Region>('all');
  const [directoryContent, setDirectoryContent] = useState<ContentGroup>('all');
  const [searchOpen, setSearchOpen] = useState(false);
  const [tiers, setTiers] = useState(() => new Set<Tier>(ALL_TIERS.filter((tier) => tier !== 'F' || entry.showFiction)));
  const [layers, setLayers] = useState(() => new Set<Layer>(ALL_LAYERS));
  const [evidence, setEvidence] = useState(() => new Set<EvidenceGroup>(ALL_EVIDENCE));
  const [activeLayer, setActiveLayer] = useState<Layer | null>(null);
  const [soloLayer, setSoloLayer] = useState<Layer | null>(null);
  const [spread, setSpread] = useState(120);
  const [selectedId, setSelectedId] = useState(entry.selectedId);
  const [mapFocus, setMapFocus] = useState(entry.focus);
  const [compareId, setCompareId] = useState<string | null>(entry.compareId);
  const [comparePicking, setComparePicking] = useState(false);
  const [drawer, setDrawer] = useState<'collapsed' | 'single' | 'compare'>(entry.compareId ? 'compare' : 'single');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [codeFocus, setCodeFocus] = useState<CodeFocus | null>(null);
  const [pinnedCode, setPinnedCode] = useState<CodeFocus | null>(null);
  const [years, setYears] = useState<[number, number] | null>(null);
  const [entryResolved, setEntryResolved] = useState(!loading);

  // The globe can initialize while the graph index is downloading. Resolve
  // deep links once the real records arrive without remounting the scene.
  useEffect(() => {
    if (loading || entryResolved) return;
    const url = new URL(window.location.href);
    const requested = snapshot.nodes.find((node) => node.id === url.searchParams.get('story'));
    const compared = requested && snapshot.nodes.find((node) => node.id !== requested.id && node.id === url.searchParams.get('compare'));
    if (requested) {
      setSelectedId(requested.id);
      setCompareId(compared?.id ?? null);
      setDrawer(compared ? 'compare' : 'single');
      if (coordinatesOf(requested)) setMapFocus({ id: requested.id });
      if (isFiction(requested) || (compared && isFiction(compared))) setTiers(new Set(ALL_TIERS));
    }
    if (!url.searchParams.has('view') && !snapshot.nodes.some(isModernReading)) setMode('graph');
    setEntryResolved(true);
  }, [entryResolved, loading, snapshot.nodes]);

  const timeline = useMemo(() => {
    const values = snapshot.nodes.filter((node) => node.z_layer === 1 && tiers.has(node.credibility_tier))
      .map((node) => node.temporal?.year_start ?? node.temporal?.year_end)
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
    if (!values.length) return { bounds: null, ticks: [] } as { bounds: [number, number] | null; ticks: number[] };
    const min = Math.min(...values), max = Math.max(...values);
    const bins = new Map<number, number>();
    for (const value of values) bins.set(Math.round((value - min) / Math.max(1, max - min) * 120), value);
    return { bounds: [min, max] as [number, number], ticks: [...bins.values()] };
  }, [snapshot.nodes, tiers]);
  const currentYears = useMemo(() => {
    const bounds = timeline.bounds;
    return bounds && years ? years.map((year) => Math.max(bounds[0], Math.min(bounds[1], year))) as [number, number] : bounds;
  }, [timeline.bounds, years]);
  const graph = useMemo(() => {
    const nodes = snapshot.nodes.filter((node) => {
      if (!tiers.has(node.credibility_tier) || (mode === 'graph' && !layers.has(node.z_layer))) return false;
      if (node.z_layer !== 1 || !currentYears || !node.temporal) return true;
      const start = node.temporal.year_start, end = node.temporal.year_end;
      if (start === null && end === null) return true;
      return (end ?? start ?? currentYears[1]) >= currentYears[0] && (start ?? end ?? currentYears[0]) <= currentYears[1];
    });
    return indexGraph({ nodes, links: snapshot.links }, false);
  }, [snapshot, tiers, layers, mode, currentYears]);
  const renderedGraph = useMemo(() => {
    if (mode === 'geo' || evidence.size === ALL_EVIDENCE.length) return graph;
    const links = graph.links.filter((link) => {
      const status = evidenceGroup(link.status);
      return status === null || evidence.has(status);
    });
    return indexGraph({ nodes: graph.nodes, links }, false);
  }, [graph, evidence, mode]);
  const selected = graph.byId.get(selectedId ?? '') ?? null;
  const comparison = graph.byId.get(compareId ?? '') ?? null;
  const activeComparison = drawer === 'compare' ? comparison : null;
  const detailedNodes = useMemo(() => {
    if (!details) return null;
    return new Map(snapshot.nodes.map((node, index) => [node.id, { ...node, ...details.nodes[index] }]));
  }, [snapshot.nodes, details]);
  const detailsReady = !snapshot.details_file || !!detailedNodes;
  const selectedDetail = selected ? detailedNodes?.get(selected.id) ?? selected : null;
  const comparisonDetail = activeComparison ? detailedNodes?.get(activeComparison.id) ?? activeComparison : null;
  const directoryNodes = useMemo(() => detailedNodes ? graph.nodes.map((node) => detailedNodes.get(node.id) ?? node) : graph.nodes,
    [graph.nodes, detailedNodes]);
  const showGuide = selectedId === null && drawer !== 'collapsed';
  const sceneSelection = useMemo(() => {
    const neighbors = relatedNodes(renderedGraph, selected, 1);
    for (const [id, distance] of relatedNodes(renderedGraph, activeComparison, 1)) {
      neighbors.set(id, Math.min(neighbors.get(id) ?? 2, distance));
    }
    return { node: selected, compareNode: activeComparison, neighbors };
  }, [renderedGraph, selected, activeComparison]);
  const selection = useMemo(() => {
    const hovered = hoveredId ? graph.byId.get(hoveredId) : undefined;
    if (!hovered) return sceneSelection;
    const neighbors = relatedNodes(renderedGraph, hovered, 1);
    if (activeComparison) for (const [id, distance] of sceneSelection.neighbors) {
      neighbors.set(id, Math.min(neighbors.get(id) ?? 2, distance));
    }
    return { node: hovered, compareNode: activeComparison, neighbors };
  }, [graph, renderedGraph, hoveredId, activeComparison, sceneSelection]);
  const codeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of snapshot.nodes) for (const code of dossierCodes(node)) {
      const key = codeKey(code);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return counts;
  }, [snapshot.nodes]);
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
  const commonHubs = [...commonIds].flatMap((id) => graph.byId.get(id) ?? []);
  const mappedCount = useMemo(() => graph.nodes.filter(coordinatesOf).length, [graph]);
  const modernCount = useMemo(() => graph.nodes.filter((node) => nodeContentGroup(node) === 'modern').length, [graph]);
  const searchableNodes = useMemo(() => {
    const nodes = detailedNodes ? [...detailedNodes.values()] : snapshot.nodes;
    return tiers.has('F') ? nodes : nodes.filter((node) => !isFiction(node));
  }, [snapshot.nodes, detailedNodes, tiers]);

  const selectNode = useCallback((id: string, asCompare = false) => {
    if (!graph.byId.has(id)) return;
    onNeedDetails();
    if (id !== selectedId) setMapFocus(null);
    if ((asCompare || comparePicking) && selectedId && id !== selectedId) {
      setCompareId(id); setComparePicking(false); setDrawer('compare');
    } else {
      if (id === compareId && drawer === 'compare') setCompareId(selectedId);
      setSelectedId(id);
      if (drawer === 'collapsed') setDrawer('single');
    }
    setHoveredId(null);
    if (window.matchMedia('(max-width: 760px)').matches) {
      window.requestAnimationFrame(() => document.getElementById('node-inspector')?.scrollIntoView({ block: 'start' }));
    }
  }, [graph.byId, comparePicking, selectedId, compareId, drawer, onNeedDetails]);

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (!loading && !lifeMode && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [lifeMode, loading]);

  function toggle<T>(setter: Dispatch<SetStateAction<Set<T>>>, value: T) {
    setter((old) => { const next = new Set(old); if (next.has(value)) next.delete(value); else next.add(value); return next; });
  }
  function toggleSolo(layer: Layer) { setActiveLayer(layer); setSoloLayer((previous) => previous === layer ? null : layer); }
  function openDirectory(scope: DirectoryScope) {
    setDirectoryOpen(!directoryOpen || directoryScope !== scope);
    setDirectoryScope(scope); setDirectoryRegion('all'); setDirectoryContent('all');
  }
  function browseCollection(region: Region, content: ContentGroup) {
    setDirectoryRegion(region); setDirectoryContent(content); setDirectoryScope('all'); setDirectoryOpen(true);
  }
  function locate(id: string) {
    setMapFocus({ id });
    setMode('geo');
    if (window.matchMedia('(max-width: 760px)').matches) {
      window.requestAnimationFrame(() => document.getElementById('visual-stage')?.scrollIntoView({ block: 'start' }));
    }
  }
  function readRecord(id: string) {
    const node = graph.byId.get(id);
    if (!node) return;
    onNeedDetails();
    setSelectedId(id); setDrawer('single'); setComparePicking(false); setHoveredId(null);
    setMapFocus(coordinatesOf(node) && mode === 'geo' ? { id } : null);
  }
  function startComparison(left: string, right: string) {
    onNeedDetails();
    setSelectedId(left); setCompareId(right); setDrawer('compare'); setMode('graph');
    setComparePicking(false); setMapFocus(null); setHoveredId(null);
  }
  const codeInteraction = {
    counts: codeCounts, pinned: pinnedCode, onFocus: setCodeFocus,
    onPin: (code: CodeFocus) => setPinnedCode((current) => current && codeKey(current) === codeKey(code) ? null : code),
  };
  const width = drawer === 'collapsed' || (!loading && !selected && !showGuide) ? 40 : drawer === 'compare' ? 680 : 420;
  function switchView(next: 'geo' | 'graph' | 'life') {
    setLifeMode(next === 'life'); setSearchOpen(false);
    if (next !== 'life') setMode(next);
    const url = new URL(window.location.href);
    url.searchParams.set('view', next === 'geo' ? 'map' : next);
    if (next !== 'life') url.searchParams.delete('entry');
    window.history.replaceState({}, '', url);
    if (loading && next === 'life') onEnterLifeWhileLoading();
  }

  return <div className={`app-shell${lifeMode ? ' app-shell-life' : ''}`}>
    <header className="topbar">
      <Brand />
      <ViewSwitch mode={mode} lifeMode={lifeMode} onSwitch={switchView} />
      <div className="top-actions">
      <SyzygyLink dimension={lifeMode ? 'omnia' : mode === 'geo' ? 'umbra' : 'sidera'} story={lifeMode ? null : selectedId} showFiction={tiers.has('F')} />
        {lifeMode && <span className="life-header-slot" />}
        {!lifeMode && <>
        {!publicSite && <a className="review-link" href={`${import.meta.env.BASE_URL}review/index.html`}>资料复核</a>}
        <button className="directory-toggle" type="button" disabled={loading} aria-expanded={directoryOpen && directoryScope !== 'modern'}
          onClick={() => openDirectory('all')}>资料目录 <span>{loading ? '…' : graph.nodes.length}</span></button>
        <button className="fiction-switch" type="button" role="switch" aria-label="隐藏 F 级虚构" aria-checked={!tiers.has('F')} onClick={() => toggle<Tier>(setTiers, 'F')}>
          <span>隐藏 F 级虚构</span><span className="switch-track" aria-hidden="true" /></button>
        </>}
      </div>
    </header>
    {lifeMode ? <Suspense fallback={<div className="life-status">正在载入知识星图…</div>}><LifeKnowledge /></Suspense> : <div className="workspace workbench" style={{ '--drawer-width': `${width}px` } as CSSProperties}>
      <main id="visual-stage" className="visual-stage" aria-label="图谱主视图">
        <ViewportFrame />
        <div className="stage-heading">
          <span className="stage-eyebrow">{mode === 'geo' ? 'ASTRAIA / 3D FOLKLORE & ANOMALY GLOBE' : 'ASTRAIA / SEMANTIC MOTIF CONSTELLATION'}</span>
          <h1>{mode === 'geo' ? '坤舆异志' : '玄象星络'}</h1>
          <p>{mode === 'geo' ? '全球灵异与民俗三维舆图' : '跨文化母题与语义演化星络'}</p>
          <p className="stage-count">{loading ? '正在载入资料…' : mode === 'geo' ? `图谱有坐标资料 ${mappedCount.toLocaleString()} 条` : `${graph.nodes.length.toLocaleString()} 个节点 · ${graph.links.length.toLocaleString()} 条关系`}</p></div>
        {modernCount > 0 && <button type="button" className="modern-shortcut"
          aria-expanded={directoryOpen && directoryScope === 'modern'} onClick={() => openDirectory('modern')}>现代异闻 <span>{modernCount}</span></button>}
        <ControlRail mode={mode} layers={layers} tiers={tiers} activeLayer={activeLayer} soloLayer={soloLayer} spread={spread}
          onLayer={(layer) => setActiveLayer((previous) => previous === layer ? null : layer)} onToggleLayer={(layer) => toggle(setLayers, layer)}
          onSolo={toggleSolo} onTier={(tier) => toggle(setTiers, tier)} onSpread={setSpread} onSearch={() => { if (!loading) setSearchOpen(true); }} />
        <Suspense fallback={<div className="stage-message" role="status">正在载入三维视图…</div>}>
          {mode === 'geo'
            ? <GeoView graph={graph} selection={sceneSelection} codeIds={codeIds} focus={mapFocus}
              onSelect={selectNode} onOpenGraph={() => setMode('graph')} />
            : <ConstellationView graph={renderedGraph} evidenceGraph={graph} allNodes={snapshot.nodes} selection={selection} sceneSelection={sceneSelection}
              hoveredId={hoveredId} spread={spread} soloLayer={soloLayer} activeLayer={activeLayer} codeIds={codeIds} commonIds={commonIds} evidence={evidence}
              onSelect={selectNode} onHover={setHoveredId} onLayer={setActiveLayer} onSolo={toggleSolo} onEvidence={(status) => toggle(setEvidence, status)} />}
        </Suspense>
        {pinnedCode && <div className="code-filter-banner" role="status">
          <span>同码星座 <strong>{STANDARDS[pinnedCode.system] ?? pinnedCode.system} {pinnedCode.code}</strong> · {codeCounts.get(codeKey(pinnedCode)) ?? 0} 项</span>
          <button type="button" onClick={() => { setPinnedCode(null); setCodeFocus(null); }}>清除 ×</button>
        </div>}
        <Chronology bounds={timeline.bounds} value={currentYears} ticks={timeline.ticks} onChange={setYears} />
        {drawer === 'compare' && comparePicking && <div className="compare-hint" role="status">请选择第二个节点，或 Shift + 点击节点。</div>}
        {directoryOpen && <div className="directory-drawer" onKeyDown={(event) => { if (event.key === 'Escape') setDirectoryOpen(false); }}>
          <NodeDirectory nodes={directoryNodes} selectedId={selected?.id ?? null}
            scope={directoryScope} onScope={setDirectoryScope} onClose={() => setDirectoryOpen(false)}
            region={directoryRegion} content={directoryContent} onRegion={setDirectoryRegion} onContent={setDirectoryContent}
            detailsReady={detailsReady} detailsError={detailsError} onNeedDetails={onNeedDetails} onRetryDetails={onRetryDetails}
            onSelect={(id) => {
              const node = graph.byId.get(id);
              selectNode(id);
              if (mode === 'geo' && node && coordinatesOf(node)) setMapFocus({ id });
              setDirectoryOpen(false);
            }} /></div>}
      </main>
      {drawer === 'collapsed' || (!loading && !selected && !showGuide) ? <aside className="inspector-spine" aria-label="收起的卷宗">
        <button type="button" onClick={() => { if (!selected && selectedId) setSelectedId(firstSelection(graph.nodes)); setDrawer('single'); }}>展开卷宗</button></aside>
        : <div className="inspector-drawer">
          <div className="drawer-modes" aria-label="卷宗宽度">
            <button type="button" onClick={() => { setDrawer('collapsed'); setComparePicking(false); }}>收起</button>
            <button type="button" aria-pressed={drawer === 'single'} onClick={() => { setDrawer('single'); setComparePicking(false); }}>单卷宗</button>
            {selected && <button type="button" aria-pressed={drawer === 'compare'} onClick={() => { setDrawer('compare'); if (!comparison) setComparePicking(true); }}>双卷宗</button>}
          </div>
          {loading ? <div className="inspector-loading" role="status"><h2>馆藏导览</h2><p>正在载入故事与图谱资料…</p></div>
            : showGuide ? <CollectionGuide graph={graph} onRead={readRecord} onCompare={startComparison} onBrowse={browseCollection} />
            : selected && !detailsReady ? <div className="inspector-loading" role="status"><h2>{selected.title}</h2>
              {selected.reading?.paragraphs[0] && <p>{selected.reading.paragraphs[0]}</p>}
              <p>{detailsError ? `正文与出处暂未载入：${detailsError}` : '正在载入完整正文与出处…'}</p>
              {detailsError && <button type="button" className="quiet-button" onClick={onRetryDetails}>重试</button>}</div>
            : selectedDetail && comparisonDetail ? <DossierComparison key={`${selectedDetail.id}:${comparisonDetail.id}`} left={selectedDetail} right={comparisonDetail}
              graph={graph} hubs={commonHubs} codeInteraction={codeInteraction} onRead={readRecord} onChange={() => setComparePicking(true)} onHover={setHoveredId} />
            : selectedDetail && <div className={`inspector-columns${drawer === 'compare' ? ' comparing' : ''}`}>
              <NodeInspector node={selectedDetail} graph={graph} onSelect={selectNode} onLocate={locate} onClose={() => { setDrawer('collapsed'); setComparePicking(false); }}
                onCompare={() => { setDrawer('compare'); setComparePicking(true); }} onNodeHover={setHoveredId} codeInteraction={codeInteraction} />
              {drawer === 'compare' && <div className="compare-empty">请选择第二个节点。</div>}
            </div>}
        </div>}
    </div>}
    {!lifeMode && searchOpen && <QuickSearch nodes={searchableNodes} onClose={() => setSearchOpen(false)} onSelect={(id) => {
      onNeedDetails();
      setTiers(new Set(ALL_TIERS.filter((tier) => tier !== 'F' || tiers.has('F')))); setLayers(new Set(ALL_LAYERS)); setYears(null);
      if (comparePicking && selected && id !== selected.id) {
        setCompareId(id); setDrawer('compare');
      } else {
        setSelectedId(id); setDrawer('single');
        if (mode === 'geo') setMapFocus({ id });
      }
      setHoveredId(null); setComparePicking(false);
    }} />}
  </div>;
}

export function App() {
  const [directLife, setDirectLife] = useState(() => new URL(window.location.href).searchParams.get('view') === 'life');
  const [pendingMode, setPendingMode] = useState<ViewMode>(() => new URL(window.location.href).searchParams.get('view') === 'graph' ? 'graph' : 'geo');
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null);
  const [details, setDetails] = useState<GraphDetails | null>(null);
  const [detailsRequested, setDetailsRequested] = useState(false);
  const [detailsError, setDetailsError] = useState('');
  const [detailsAttempt, setDetailsAttempt] = useState(0);
  const needDetails = useCallback(() => setDetailsRequested(true), []);
  const retryDetails = useCallback(() => { setDetailsRequested(true); setDetailsAttempt((value) => value + 1); }, []);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (directLife) return;
    const controller = new AbortController();
    void (pendingMode === 'graph' ? loadConstellationView() : loadGeoView()).catch(() => {});
    if (pendingMode === 'geo') void loadOverviewMapFonts();
    loadSnapshot(controller.signal).then(setSnapshot).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '读取图谱失败。');
    });
    return () => controller.abort();
  }, [attempt, directLife, pendingMode]);
  useEffect(() => {
    if (!snapshot?.details_file || detailsRequested) return;
    const timer = window.setTimeout(() => setDetailsRequested(true),
      new URL(window.location.href).searchParams.has('story') ? 0 : 4000);
    return () => window.clearTimeout(timer);
  }, [snapshot, detailsRequested]);
  useEffect(() => {
    if (!snapshot?.details_file || !detailsRequested || details) return;
    const controller = new AbortController();
    setDetailsError('');
    loadGraphDetails(snapshot, controller.signal).then(setDetails).catch((reason: unknown) => {
      if (!controller.signal.aborted) setDetailsError(reason instanceof Error ? reason.message : '无法载入正文。');
    });
    return () => controller.abort();
  }, [snapshot, detailsRequested, detailsAttempt, details]);
  if (directLife) return <div className="app-shell app-shell-life">
    <header className="topbar"><Brand /><ViewSwitch mode="geo" lifeMode onSwitch={(next) => {
      if (next === 'life') return;
      const url = new URL(window.location.href);
      url.searchParams.set('view', next === 'geo' ? 'map' : 'graph'); url.searchParams.delete('entry'); url.hash = '';
      window.history.replaceState({}, '', url); setPendingMode(next); setDirectLife(false);
    }} /><div className="top-actions"><SyzygyLink dimension="omnia" /><span className="life-header-slot" /></div></header>
    <Suspense fallback={<div className="life-status">正在载入知识星图…</div>}><LifeKnowledge /></Suspense>
  </div>;
  if (snapshot || !error) return <Atlas snapshot={snapshot ?? EMPTY_SNAPSHOT} loading={!snapshot} details={details} detailsError={detailsError}
    onNeedDetails={needDetails} onRetryDetails={retryDetails} onEnterLifeWhileLoading={() => setDirectLife(true)} />;
  return <div className="app-shell"><header className="topbar"><Brand /><ViewSwitch mode={pendingMode} lifeMode={false} onSwitch={(next) => {
    const url = new URL(window.location.href); url.searchParams.set('view', next === 'geo' ? 'map' : next);
    if (next !== 'life') url.searchParams.delete('entry');
    window.history.replaceState({}, '', url);
    if (next === 'life') setDirectLife(true); else setPendingMode(next);
  }} /><div className="top-actions"><SyzygyLink dimension={pendingMode === 'geo' ? 'umbra' : 'sidera'} /></div></header><main className="loading-shell"><div className="loading-message" role={error ? 'alert' : 'status'}>
    <h1>{error ? '图谱暂未加载' : '正在读取图谱'}</h1>{error && <p>{error}</p>}
    {error && <button type="button" className="quiet-button" onClick={() => { setError(null); setAttempt((value) => value + 1); }}>重试</button>}
  </div></main></div>;
}
