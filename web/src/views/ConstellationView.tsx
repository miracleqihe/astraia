import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { constellationIndex, indexGraph, LAYERS, LAYER_ORDER, nodeColor, shortNodeLabel, type EvidenceGroup,
  type GraphIndex, type GraphNode, type Layer, type ViewSelection } from '../graph';
import { ViewControls } from './ViewControls';
import { constellationLayout, mountConstellation } from './constellationScene';

interface Props {
  graph: GraphIndex;
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

export default function ConstellationView({ graph, allNodes, selection, sceneSelection, hoveredId, spread, activeLayer, soloLayer,
  codeIds, commonIds, evidence, onSelect, onHover, onLayer, onSolo, onEvidence }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<ReturnType<typeof mountConstellation> | null>(null);
  const labels = useRef(new Map<string, HTMLElement>());
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const scene = useMemo(() => soloLayer
    ? indexGraph({ nodes: graph.nodes.filter((node) => node.z_layer === soloLayer).slice(0, 600), links: graph.links }, false)
    : constellationIndex(graph, sceneSelection), [graph, sceneSelection, soloLayer]);
  const layoutNodes = allNodes.length <= 72 ? allNodes : scene.nodes;
  const layout = useMemo(() => constellationLayout(layoutNodes, spread), [layoutNodes, spread]);

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

  useEffect(() => stageRef.current?.updateGraph(scene), [scene, layout]);
  useEffect(() => stageRef.current?.interactions(onHover, onSelect), [onHover, onSelect, layout]);
  useEffect(() => { stageRef.current?.solo(soloLayer); }, [soloLayer, layout]);
  useEffect(() => stageRef.current?.highlight(selection, hoveredId, codeIds, commonIds, activeLayer), [selection, scene, layout, hoveredId, codeIds, commonIds, soloLayer, activeLayer]);

  function register(id: string, element: HTMLElement | null) {
    if (element) labels.current.set(id, element);
    else labels.current.delete(id);
    stageRef.current?.invalidate();
  }

  return (
    <>
      <div className="scene-viewport constellation-viewport" ref={hostRef} data-ready={ready} data-point-count={scene.nodes.length} />
      {error && <div className="stage-message" role="alert">无法启动语义星图。请在支持 WebGL 的浏览器中打开。</div>}
      {ready && !error && (
        <>
          <div className="constellation-labels" aria-label="星图标记" data-solo={Boolean(soloLayer)}>
            {LAYER_ORDER.map((layer) => (
              <button type="button" key={layer} className="constellation-layer" ref={(element) => register(`layer:${layer}`, element)}
                onClick={() => onLayer(layer)} onDoubleClick={() => onSolo(layer)}
                style={{ '--node-color': LAYERS[layer].color } as CSSProperties}>
                <strong>L{layer}</strong><span>{LAYERS[layer].short}</span>
              </button>
            ))}
            {scene.nodes.filter((node, index) => index < 80 || node.id === selection.node?.id
              || node.id === sceneSelection.compareNode?.id || node.id === hoveredId).map((node, index) => {
              const distance = selection.neighbors.get(node.id);
              return (
                <button key={node.id} ref={(element) => register(node.id, element)} type="button" className="constellation-node"
                  data-node-id={node.id} data-common={commonIds.has(node.id)} data-code-highlight={codeIds.has(node.id)}
                  data-emphasis={distance === 0 ? 'selected' : distance === 1 ? 'related' : 'normal'}
                  aria-label={`星图节点 ${node.title}`} aria-pressed={distance === 0}
                  onMouseEnter={() => onHover(node.id)} onMouseLeave={() => onHover(null)}
                  onFocus={() => onHover(node.id)} onBlur={() => onHover(null)}
                  onClick={(event) => onSelect(node.id, event.shiftKey)}
                  style={{ '--node-color': nodeColor(node), '--label-offset': `${(index % 5 - 2) * 14}px` } as CSSProperties}>
                  <span className="constellation-node-label" aria-hidden="true"><b>L{node.z_layer}</b> {shortNodeLabel(node.title)}</span>
                </button>
              );
            })}
          </div>
          <ViewControls onReset={() => stageRef.current?.reset()} onZoom={(direction) => stageRef.current?.zoom(direction)} />
          <div className="scene-footer constellation-footer">
            <span>{scene.nodes.length < graph.nodes.length ? `显示 ${scene.nodes.length} 个节点 · 其余可在节点目录定位` : '拖动旋转 · 滚轮缩放'}</span>
            <span className="evidence-legend">
              <button type="button" className="legend-confirmed" aria-pressed={evidence.has('confirmed')} onClick={() => onEvidence('confirmed')}><i />已证实</button>
              <button type="button" className="legend-unverified" aria-pressed={evidence.has('unverified')} onClick={() => onEvidence('unverified')}><i />待核实或有争议</button>
              <button type="button" className="legend-refuted" aria-pressed={evidence.has('refuted')} onClick={() => onEvidence('refuted')}><i />已驳回</button>
            </span>
          </div>
        </>
      )}
    </>
  );
}
