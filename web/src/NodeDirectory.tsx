import { useDeferredValue, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { coordinatesOf, isEditorialReading, isFiction, LAYERS, LAYER_ORDER, mapLabel, matchesQuery,
  nodeColor, READING_LABELS, type GraphNode } from './graph';
import { CONTENT_GROUPS, nodeContentGroup, nodeRegion, REGIONS, type ContentGroup, type Region } from './catalogueBrowse';

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
  region: Region;
  content: ContentGroup;
  onRegion: (region: Region) => void;
  onContent: (content: ContentGroup) => void;
  detailsReady: boolean;
  detailsError: string;
  onNeedDetails: () => void;
  onRetryDetails: () => void;
}

export function NodeDirectory({ nodes, selectedId, scope, onScope, onClose, onSelect, region, content, onRegion, onContent, detailsReady, detailsError, onNeedDetails, onRetryDetails }: Props) {
  const [query, setQuery] = useState('');
  const deferredQuery = useDeferredValue(query);
  const [limits, setLimits] = useState<Record<number, number>>({});
  const [layerFilter, setLayerFilter] = useState('all');
  const listRef = useRef<HTMLDivElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);
  const scoped = useMemo(() => nodes.filter((node) => {
    if (region !== 'all' && nodeRegion(node) !== region) return false;
    if (content !== 'all' && nodeContentGroup(node) !== content) return false;
    if (layerFilter !== 'all' && String(node.z_layer) !== layerFilter) return false;
    if (scope === 'modern') return nodeContentGroup(node) === 'modern';
    if (scope === 'stories') return isEditorialReading(node) || !!node.reading?.edition;
    if (scope === 'research') return node.reading?.kind === 'research';
    return true;
  }), [nodes, scope, region, content, layerFilter]);
  const matching = useMemo(() => {
    const readable: GraphNode[] = [], other: GraphNode[] = [];
    for (const node of scoped) if (matchesQuery(node, deferredQuery)) {
      (isEditorialReading(node) || node.reading?.edition ? readable : other).push(node);
    }
    return [...readable, ...other];
  }, [scoped, deferredQuery]);
  useEffect(() => setLimits({}), [scope, region, content, layerFilter, deferredQuery]);

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
          <h2>资料目录</h2>
          <span className="record-count" aria-live="polite">{matching.length}{query.trim() ? ` / ${scoped.length}` : ''}</span>
          <button type="button" className="directory-close" aria-label="关闭节点目录" onClick={onClose}>×</button>
        </div>
        <div className="directory-scopes" aria-label="阅读范围">
          {SCOPES.map(([value, label]) => <button type="button" key={value}
            aria-pressed={scope === value} onClick={() => { onScope(value); onContent('all'); if (listRef.current) listRef.current.scrollTop = 0; }}>{label}</button>)}
        </div>
        <div className="directory-filters">
          <label>地域<select aria-label="筛选地域" value={region} onChange={(event) => { onRegion(event.target.value as Region); if (listRef.current) listRef.current.scrollTop = 0; }}>
            <option value="all">所有地域</option>{REGIONS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <label>内容<select aria-label="筛选内容类型" value={content} onChange={(event) => { onContent(event.target.value as ContentGroup); onScope('all'); if (listRef.current) listRef.current.scrollTop = 0; }}>
            <option value="all">所有内容</option>{CONTENT_GROUPS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <label>层级<select aria-label="筛选图谱层级" value={layerFilter} onChange={(event) => { setLayerFilter(event.target.value); if (listRef.current) listRef.current.scrollTop = 0; }}>
            <option value="all">全部层级</option>{LAYER_ORDER.map((layer) => <option key={layer} value={layer}>L{layer} {LAYERS[layer].short}</option>)}</select></label>
        </div>
        <label className="directory-search">
          <span className="search-icon" aria-hidden="true" />
          <input type="search" aria-label="搜索节点" placeholder="搜索名称、地点、年代或出处" value={query} onFocus={onNeedDetails}
            onChange={(event) => setQuery(event.target.value)} />
        </label>
        {!!query.trim() && !detailsReady && <p className="directory-loading">{detailsError
          ? <>出处未能载入。<button type="button" onClick={onRetryDetails}>重试</button></>
          : '正在载入出处，搜索结果将自动补全。'}</p>}
      </div>

      <div className="directory-scroll" ref={listRef}>
        {matching.length === 0 && <p className="directory-empty">
          {query.trim() ? '没有匹配的节点。' : '此快照暂无可见节点。'}
        </p>}
        {LAYER_ORDER.map((layer) => {
          const all = matching.filter((node) => node.z_layer === layer);
          const group = all.slice(0, limits[layer] ?? 60);
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
                          {(scope !== 'all' || region !== 'all' || content !== 'all') && node.reading && <span className="directory-preview">
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
              {all.length > group.length && <button className="directory-more" type="button"
                onClick={() => setLimits((previous) => ({ ...previous, [layer]: (previous[layer] ?? 60) + 100 }))}>
                显示更多 · 还有 {(all.length - group.length).toLocaleString()} 条</button>}
            </section>
          );
        })}
      </div>

    </aside>
  );
}
