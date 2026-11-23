import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { constellationIndex, evidenceGroup, indexGraph, LAYERS, LAYER_ORDER, nodeColor, type EvidenceGroup,
  type GraphIndex, type GraphNode, type Layer, type ViewSelection } from '../graph';
import { ViewControls } from './ViewControls';
import { constellationLayout, mountConstellation } from './constellationScene';

interface Props {
  graph: GraphIndex;
  evidenceGraph: GraphIndex;
  allNodes: GraphNode[];
  selection: ViewSelection;
  sceneSelection: ViewSelection;
  hoveredId: string | null;
  spread: number;
  activeLayer: Layer | null;
  soloLayer: Layer | null;
  codeIds: ReadonlySet<string>;
  commonIds: ReadonlySet<string>;
  evidence: Set<EvidenceGroup>;
  onSelect: (id: string, compare?: boolean) => void;
  onHover: (id: string | null) => void;
  onLayer: (layer: Layer) => void;
  onSolo: (layer: Layer) => void;
  onEvidence: (status: EvidenceGroup) => void;
}

export default function ConstellationView({ graph, evidenceGraph, allNodes, selection, sceneSelection, hoveredId, spread, activeLayer, soloLayer,
  codeIds, commonIds, evidence, onSelect, onHover, onLayer, onSolo, onEvidence }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<ReturnType<typeof mountConstellation> | null>(null);
  const labels = useRef(new Map<string, HTMLElement>());
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const [narrow, setNarrow] = useState(false);
  const compact = narrow && Boolean(sceneSelection.compareNode);
  const counts = useMemo(() => {
    const result: Record<EvidenceGroup, number> = { confirmed: 0, unverified: 0, refuted: 0 };
    for (const link of evidenceGraph.links) {
      const group = evidenceGroup(link.status);
      if (group) result[group]++;
    }
    return result;
  }, [evidenceGraph.links]);
  const scene = useMemo(() => {
    if (soloLayer) return indexGraph({ nodes: graph.nodes.filter((node) => node.z_layer === soloLayer).slice(0, 600), links: graph.links }, false);
    const base = constellationIndex(graph, sceneSelection);
    if (!codeIds.size) return base;
    const focus = new Map(base.nodes.map((node) => [node.id, node]));
    for (const node of graph.nodes) {
      if (focus.size >= 600) break;
      if (codeIds.has(node.id)) focus.set(node.id, node);
    }
    return indexGraph({ nodes: [...focus.values()], links: graph.links }, false);
  }, [graph, sceneSelection, soloLayer, codeIds]);
  const layoutNodes = allNodes.length <= 72 ? allNodes : scene.nodes;
  const layout = useMemo(() => constellationLayout(layoutNodes, spread), [layoutNodes, spread]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const measure = () => setNarrow(host.clientWidth <= 760);
    const observer = new ResizeObserver(measure);
    measure();
    observer.observe(host);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!hostRef.current) return;
    try {
      const stage = mountConstellation(hostRef.current, layout, labels.current);
      stageRef.current = stage;
      setReady(true);
      return () => { stage.dispose(); stageRef.current = null; };
    } catch (reason) {
      console.warn('Unable to initialize the constellation', reason);
      setError(true);
    }
  }, [layout]);

  useEffect(() => stageRef.current?.updateGraph(scene, sceneSelection), [scene, sceneSelection, layout]);
  useEffect(() => stageRef.current?.interactions(onHover, onSelect), [onHover, onSelect, layout]);
  useEffect(() => { stageRef.current?.solo(soloLayer); }, [soloLayer, layout]);
  useEffect(() => stageRef.current?.highlight(selection, hoveredId, sceneSelection.node?.id ?? null, codeIds, commonIds, activeLayer),
    [selection, scene, layout, hoveredId, sceneSelection.node, codeIds, commonIds, soloLayer, activeLayer]);
  useEffect(() => stageRef.current?.invalidate(), [compact, selection, hoveredId]);

  function register(id: string, element: HTMLElement | null) {
    if (element) labels.current.set(id, element);
    else labels.current.delete(id);
    stageRef.current?.invalidate();
  }

  return (
    <>
      <div className="scene-viewport constellation-viewport" ref={hostRef} data-ready={ready} data-compact={compact}
        data-point-count={scene.nodes.length} data-line-count={scene.links.length} />
      {error && <div className="stage-message" role="alert">无法启动语义星图。请在支持 WebGL 的浏览器中打开。</div>}
      {ready && !error && (
        <>
          <div className="constellation-labels" aria-label="星图标记" data-solo={Boolean(soloLayer)}>
            {LAYER_ORDER.map((layer) => (
              <div key={layer} className="constellation-layer" ref={(element) => register(`layer:${layer}`, element)}
                style={{ '--node-color': LAYERS[layer].color } as CSSProperties}>
                <button type="button" onClick={() => onLayer(layer)} onDoubleClick={() => onSolo(layer)}>
                  <strong>L{layer}</strong> {LAYERS[layer].short}
                </button>
                <button type="button" className="slice-flatten" aria-pressed={soloLayer === layer}
                  aria-label={soloLayer === layer ? `切片 L${layer} 返回 3D` : `平铺切片 L${layer}`}
                  onClick={() => onSolo(layer)}>{soloLayer === layer ? '3D' : '2D'}</button>
              </div>
            ))}
            {scene.nodes.filter((node, index) => index < 80 || node.id === selection.node?.id
              || node.id === sceneSelection.compareNode?.id || node.id === hoveredId || commonIds.has(node.id)).map((node) => {
              const distance = selection.neighbors.get(node.id);
              const primary = node.id === sceneSelection.node?.id || node.id === sceneSelection.compareNode?.id;
              const showLabel = primary || commonIds.has(node.id) || node.id === hoveredId || (!compact && (distance === 1 || Boolean(soloLayer)));
              return (
                <button key={node.id} ref={(element) => register(node.id, element)} type="button" className="constellation-node"
                  data-node-id={node.id} data-common={commonIds.has(node.id)} data-code-highlight={codeIds.has(node.id)}
                  data-emphasis={primary ? 'selected' : distance === 1 ? 'related' : 'normal'}
                  data-label={showLabel} data-label-priority={primary ? 0 : commonIds.has(node.id) ? 1 : node.id === hoveredId ? 2 : 3}
                  title={node.title} aria-label={`星图节点 ${node.title}`} aria-pressed={primary}
                  onMouseEnter={() => onHover(node.id)} onMouseLeave={() => onHover(null)}
                  onFocus={() => onHover(node.id)} onBlur={() => onHover(null)}
                  onClick={(event) => onSelect(node.id, event.shiftKey)}
                  style={{ '--node-color': nodeColor(node) } as CSSProperties}>
                  <span className="constellation-node-label" aria-hidden="true"><b>L{node.z_layer}</b> {node.title}</span>
                </button>
              );
            })}
          </div>
          <ViewControls onReset={() => stageRef.current?.reset()} onZoom={(direction) => stageRef.current?.zoom(direction)} />
          <div className="scene-footer constellation-footer">
            <span className="scene-gesture">{compact ? '其余关联点悬停显名' : '拖动旋转 · 滚轮缩放'}</span>
            <div className="connection-controls">
              <span className="structure-key"><i />结构线</span>
              <div className="evidence-legend" role="group" aria-label="核验连线筛选" title="信源、年代和图层筛选后的关系数">
                {([['confirmed', '已证实'], ['unverified', '待核实'], ['refuted', '已驳回']] as const).map(([status, label]) => (
                  <button type="button" key={status} className={`legend-${status}`} aria-pressed={evidence.has(status)} onClick={() => onEvidence(status)}>
                    <span aria-hidden="true" className="legend-check">{evidence.has(status) ? '✓' : ''}</span>
                    <i aria-hidden="true" />{label} <span className="legend-count">{counts[status]}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
