import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { coordinatesOf, isEditorialReading, isFiction, isModernReading, LAYERS, LAYER_ORDER, mapLabel, matchesQuery,
  nodeColor, READING_LABELS, type GraphNode } from './graph';

export type DirectoryScope = 'all' | 'stories' | 'modern' | 'research';
const SCOPES: ReadonlyArray<[DirectoryScope, string]> = [
  ['all', '全部'], ['stories', '站内阅读'], ['modern', '现代异闻'], ['research', '学术研究'],
];

interface Props {
  nodes: GraphNode[];
  selectedId: string | null;
  scope: DirectoryScope;
  onScope: (scope: DirectoryScope) => void;
  onClose: () => void;
  onSelect: (id: string) => void;
}

export function NodeDirectory({ nodes, selectedId, scope, onScope, onClose, onSelect }: Props) {
  const [query, setQuery] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);
  const scoped = useMemo(() => {
    if (scope === 'modern') return nodes.filter(isModernReading);
    if (scope === 'stories') return nodes.filter((node) => isEditorialReading(node) || node.reading?.edition);
    if (scope === 'research') return nodes.filter((node) => node.reading?.kind === 'research');
    return nodes;
  }, [nodes, scope]);
  const matching = useMemo(() => scoped.filter((node) => matchesQuery(node, query)), [scoped, query]);

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
          <span className="record-count" aria-live="polite">{matching.length}{query.trim() ? ` / ${scoped.length}` : ''}</span>
          <button type="button" className="directory-close" aria-label="关闭节点目录" onClick={onClose}>×</button>
        </div>
        <div className="directory-scopes" aria-label="阅读范围">
          {SCOPES.map(([value, label]) => <button type="button" key={value}
            aria-pressed={scope === value} onClick={() => { onScope(value); if (listRef.current) listRef.current.scrollTop = 0; }}>{label}</button>)}
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
          const all = matching.filter((node) => node.z_layer === layer);
          const group = all.slice(0, 200);
          if (!group.length) return null;
          return (
            <section className="directory-group" key={layer} aria-label={`L${layer} ${LAYERS[layer].name}`}>
              {scope !== 'modern' && <h3><span className="layer-code">L{layer}</span>{LAYERS[layer].name} · {all.length}</h3>}
              <ul>
                {group.map((node) => {
                  const selected = node.id === selectedId;
                  return (
                    <li key={node.id}>
                      <button type="button" className="directory-row" aria-current={selected ? 'true' : undefined}
                        ref={selected ? selectedRef : undefined} onClick={() => onSelect(node.id)}
                        style={{ '--node-color': nodeColor(node) } as CSSProperties}>
                        <span className={`node-shape shape-${layer}`} aria-hidden="true" />
                        <span className="directory-title">{node.title}
                          {scope !== 'all' && node.reading && <span className="directory-preview">
                            <small>{READING_LABELS[node.reading.kind]}{coordinatesOf(node) ? ` · ${mapLabel(node)}` : ''}</small>
                            {node.reading.paragraphs[0] && <span>{node.reading.paragraphs[0]}</span>}
                          </span>}
                        </span>
                        {isFiction(node) && <span className="fiction-code" aria-label="F 级虚构">F</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
              {all.length > group.length && <p className="directory-empty">显示前 {group.length} 条，可用搜索定位其余节点。</p>}
            </section>
          );
        })}
      </div>

    </aside>
  );
}
