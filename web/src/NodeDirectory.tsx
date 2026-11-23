import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { isFiction, LAYERS, LAYER_ORDER, matchesQuery, nodeColor, type GraphNode } from './graph';

interface Props {
  nodes: GraphNode[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function NodeDirectory({ nodes, selectedId, onSelect }: Props) {
  const [query, setQuery] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);
  const matching = useMemo(() => nodes.filter((node) => matchesQuery(node, query)), [nodes, query]);

  useEffect(() => {
    const list = listRef.current;
    const row = selectedRef.current;
    if (!list || !row || list.scrollHeight <= list.clientHeight) return;
    const viewport = list.getBoundingClientRect();
    const item = row.getBoundingClientRect();
    if (item.top < viewport.top) list.scrollTop -= viewport.top - item.top + 8;
    if (item.bottom > viewport.bottom) list.scrollTop += item.bottom - viewport.bottom + 8;
  }, [selectedId]);

  return (
    <aside className="node-directory" aria-label="节点目录">
      <div className="directory-header">
        <div className="panel-heading">
          <h2>节点目录</h2>
          <span className="record-count" aria-live="polite">{matching.length}{query.trim() ? ` / ${nodes.length}` : ''}</span>
        </div>
        <label className="directory-search">
          <span className="search-icon" aria-hidden="true" />
          <input type="search" aria-label="搜索节点" placeholder="搜索名称、地点、年代或出处" value={query}
            onChange={(event) => setQuery(event.target.value)} />
        </label>
      </div>

      <div className="directory-scroll" ref={listRef}>
        {matching.length === 0 && <p className="directory-empty">
          {query.trim() ? '没有匹配的节点。' : '此快照暂无可见节点。'}
        </p>}
        {LAYER_ORDER.map((layer) => {
          const group = matching.filter((node) => node.z_layer === layer);
          if (!group.length) return null;
          return (
            <section className="directory-group" key={layer} aria-label={`L${layer} ${LAYERS[layer].name}`}>
              <h3><span className="layer-code">L{layer}</span>{LAYERS[layer].name}</h3>
              <ul>
                {group.map((node) => {
                  const selected = node.id === selectedId;
                  return (
                    <li key={node.id}>
                      <button type="button" className="directory-row" aria-current={selected ? 'true' : undefined}
                        ref={selected ? selectedRef : undefined} onClick={() => onSelect(node.id)}
                        style={{ '--node-color': nodeColor(node) } as CSSProperties}>
                        <span className={`node-shape shape-${layer}`} aria-hidden="true" />
                        <span className="directory-title">{node.title}</span>
                        {isFiction(node) && <span className="fiction-code" aria-label="F 级虚构">F</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>

      <div className="directory-footer"><span className="local-indicator" aria-hidden="true" />本地图谱快照</div>
    </aside>
  );
}
