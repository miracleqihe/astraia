import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { NodeDirectory } from './NodeDirectory';
import { NodeInspector } from './NodeInspector';
import {
  coordinatesOf, firstSelection, indexGraph, isFiction, loadSnapshot, relatedNodes,
  type GraphSnapshot, type ViewMode,
} from './graph';

const GeoView = lazy(() => import('./views/GeoView'));
const ConstellationView = lazy(() => import('./views/ConstellationView'));
const publicDemo = import.meta.env.VITE_PUBLIC_DEMO === '1';

function Brand() {
  return (
    <div className="wordmark">
      <span className="brand-orbit" aria-hidden="true"><span /></span>
      <div>
        <span className="brand-name">Astraia</span>
      </div>
    </div>
  );
}

function revealOnNarrowScreen(section: string) {
  if (!window.matchMedia('(max-width: 760px)').matches) return;
  window.requestAnimationFrame(() => document.getElementById(section)?.scrollIntoView({ block: 'start' }));
}

function Atlas({ snapshot }: { snapshot: GraphSnapshot }) {
  const [mode, setMode] = useState<ViewMode>('graph');
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [hideFiction, setHideFiction] = useState(false);
  const [selectedId, setSelectedId] = useState(() => firstSelection(snapshot.nodes));
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const graph = useMemo(() => indexGraph(snapshot, hideFiction), [snapshot, hideFiction]);
  const selected = graph.byId.get(selectedId ?? '') ?? null;
  const selection = useMemo(() => ({ node: selected, neighbors: relatedNodes(graph, selected) }), [graph, selected]);
  const mappedCount = useMemo(() => graph.nodes.filter(coordinatesOf).length, [graph]);
  const showInspector = inspectorOpen && selected !== null;

  const selectNode = useCallback((nodeId: string) => {
    if (!graph.byId.has(nodeId)) return;
    setSelectedId(nodeId);
    setInspectorOpen(true);
    revealOnNarrowScreen('node-inspector');
  }, [graph]);

  function changeMode(next: ViewMode) {
    setMode(next);
    revealOnNarrowScreen('visual-stage');
  }

  function toggleFiction() {
    if (!hideFiction && selected && isFiction(selected)) {
      setSelectedId(null);
      setInspectorOpen(false);
    }
    setHideFiction(!hideFiction);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <Brand />
        <nav className="view-switch" aria-label="图谱视图">
          <button type="button" aria-pressed={mode === 'geo'} onClick={() => changeMode('geo')}>
            <span className="mode-icon globe-icon" aria-hidden="true" />3D 地图
          </button>
          <button type="button" aria-pressed={mode === 'graph'} onClick={() => changeMode('graph')}>
            <span className="mode-icon constellation-icon" aria-hidden="true" />语义星图
          </button>
        </nav>
        <div className="top-actions">
          {publicDemo
            ? <span className="review-link">演示数据 · 待审核</span>
            : <a className="review-link" href={`${import.meta.env.BASE_URL}review/index.html`}>资料复核</a>}
          <button className="directory-toggle" type="button" aria-expanded={directoryOpen}
            onClick={() => setDirectoryOpen((open) => !open)}>节点目录 <span>{graph.nodes.length}</span></button>
          <button className="fiction-switch" type="button" role="switch"
            aria-checked={hideFiction} onClick={toggleFiction}>
            <span>隐藏 F 级虚构</span><span className="switch-track" aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className={`workspace${showInspector ? ' with-inspector' : ''}`}>
        <main id="visual-stage" className="visual-stage" aria-label="图谱主视图">
          <div className="stage-heading">
            <h1>{mode === 'geo' ? '全球地理分布' : '四层语义星图'}</h1>
            <p>{publicDemo ? '演示数据 · ' : ''}{mode === 'geo' ? `${mappedCount} 个地点` : `${graph.nodes.length} 个节点 · ${graph.links.length} 条关系`}</p>
          </div>
          <Suspense fallback={<div className="stage-message" role="status">正在载入三维视图…</div>}>
            {mode === 'geo'
              ? <GeoView graph={graph} selection={selection} onSelect={selectNode} onOpenGraph={() => changeMode('graph')} />
              : <ConstellationView graph={graph} allNodes={snapshot.nodes} selection={selection} onSelect={selectNode} />}
          </Suspense>
          {directoryOpen && <div className="directory-drawer" onKeyDown={(event) => {
            if (event.key === 'Escape') setDirectoryOpen(false);
          }}>
            <NodeDirectory nodes={graph.nodes} selectedId={selected?.id ?? null} onSelect={selectNode} />
          </div>}
        </main>
        {showInspector && (
          <NodeInspector node={selected} graph={graph} onSelect={selectNode} onClose={() => setInspectorOpen(false)} />
        )}
      </div>
    </div>
  );
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
  return (
    <main className="loading-shell">
      <Brand />
      <div className="loading-message" role={error ? 'alert' : 'status'}>
        <h1>{error ? '图谱暂未加载' : '正在读取本地图谱'}</h1>
        {error && <p>{error}</p>}
        {error && <button type="button" className="quiet-button" onClick={() => {
          setError(null);
          setAttempt((value) => value + 1);
        }}>重试</button>}
      </div>
    </main>
  );
}
