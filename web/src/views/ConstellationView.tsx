import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { constellationIndex, LAYERS, LAYER_ORDER, nodeColor, type GraphIndex, type GraphNode, type ViewSelection } from '../graph';
import { ViewControls } from './ViewControls';
import { constellationLayout, mountConstellation } from './constellationScene';

interface Props {
  graph: GraphIndex;
  allNodes: GraphNode[];
  selection: ViewSelection;
  onSelect: (id: string) => void;
}

export default function ConstellationView({ graph, allNodes, selection, onSelect }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<ReturnType<typeof mountConstellation> | null>(null);
  const labels = useRef(new Map<string, HTMLElement>());
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const scene = useMemo(() => constellationIndex(graph, selection), [graph, selection]);
  const layoutNodes = allNodes.length <= 72 ? allNodes : scene.nodes;
  const layout = useMemo(() => constellationLayout(layoutNodes), [layoutNodes]);

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
  useEffect(() => stageRef.current?.highlight(selection), [selection, scene, layout]);

  function register(id: string, element: HTMLElement | null) {
    if (element) labels.current.set(id, element);
    else labels.current.delete(id);
  }

  return (
    <>
      <div className="scene-viewport constellation-viewport" ref={hostRef} data-ready={ready} />
      {error && <div className="stage-message" role="alert">无法启动语义星图。请在支持 WebGL 的浏览器中打开。</div>}
      {ready && !error && (
        <>
          <div className="constellation-labels" aria-label="星图标记">
            {LAYER_ORDER.map((layer) => (
              <span key={layer} className="constellation-layer" ref={(element) => register(`layer:${layer}`, element)}
                style={{ '--node-color': LAYERS[layer].color } as CSSProperties}>
                <strong>L{layer}</strong><span>{LAYERS[layer].short}</span>
              </span>
            ))}
            {scene.nodes.map((node) => {
              const distance = selection.neighbors.get(node.id);
              return (
                <button key={node.id} ref={(element) => register(node.id, element)} type="button" className="constellation-node"
                  data-node-id={node.id} data-emphasis={distance === 0 ? 'selected' : distance === 1 ? 'related' : 'normal'}
                  aria-label={`星图节点 ${node.title}`} aria-pressed={distance === 0} onClick={() => onSelect(node.id)}
                  style={{ '--node-color': nodeColor(node) } as CSSProperties}>
                  <span className="constellation-node-label" aria-hidden="true">{node.title}</span>
                </button>
              );
            })}
          </div>
          <ViewControls onReset={() => stageRef.current?.reset()} onZoom={(direction) => stageRef.current?.zoom(direction)} />
          <div className="scene-footer constellation-footer">
            <span>{scene.nodes.length < graph.nodes.length ? `显示 ${scene.nodes.length} 个节点 · 其余可在节点目录定位` : '拖动旋转 · 滚轮缩放'}</span>
            <span className="evidence-legend">
              <span className="legend-confirmed"><i />已证实</span>
              <span className="legend-unverified"><i />待核实或有争议</span>
              <span className="legend-refuted"><i />已驳回</span>
            </span>
          </div>
        </>
      )}
    </>
  );
}
