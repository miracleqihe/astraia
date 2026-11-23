import { useState, type ReactNode } from 'react';
import { DossierCodes, type CodeInteractions } from './DossierCodes';
import { DossierOriginal, hasOriginal, Sources, temporalLabel } from './NodeInspector';
import { codeKey, dossierCodes, EVIDENCE, isFiction, LAYERS, linkKey, mapLabel, otherEnd, shortNodeLabel,
  type GraphIndex, type GraphNode } from './graph';

const GENRES: Record<string, string> = {
  memorate: '个人经历', fabulate: '定型传说', folktale: '民间故事', myth: '神话',
  historical_archive: '历史档案', academic_model: '学术研究', creepypasta_ostension: '数字虚构展演',
};

function Row({ heading, children }: { heading: ReactNode; children: ReactNode }) {
  return <section className="comparison-section">
    <div className="comparison-section-heading">{heading}</div>
    <div className="comparison-pair">{children}</div>
  </section>;
}

interface Props {
  left: GraphNode;
  right: GraphNode;
  graph: GraphIndex;
  hubs: GraphNode[];
  codeInteraction: CodeInteractions;
  onRead: (id: string) => void;
  onChange: () => void;
  onHover: (id: string | null) => void;
}

export function DossierComparison({ left, right, graph, hubs, codeInteraction, onRead, onChange, onHover }: Props) {
  const [expanded, setExpanded] = useState(false);
  const records = [left, right];
  const rightCodes = new Set(dossierCodes(right).map(codeKey));
  const sharedCodes = dossierCodes(left).filter((code) => rightCodes.has(codeKey(code)));
  const time = (node: GraphNode) => node.temporal ? temporalLabel(node.temporal) : '暂无年代';
  const summary = (node: GraphNode) => node.reading?.paragraphs ?? [];
  const links = (node: GraphNode, mechanism: boolean) => (graph.adjacency.get(node.id) ?? []).flatMap((link) => {
    const related = graph.byId.get(otherEnd(link, node.id));
    return related && (related.z_layer === 4) === mechanism ? [{ link, related }] : [];
  });
  function connections(node: GraphNode, mechanism: boolean) {
    const rows = links(node, mechanism);
    if (!rows.length) return <p className="comparison-missing">{mechanism ? '暂无登记机制' : '暂无登记关联'}</p>;
    return <ul className="comparison-relations">
      {rows.slice(0, 6).map(({ link, related }) => (
        <li key={linkKey(link)}>
          <button type="button" title={related.title} data-refuted={link.status === 'refuted'}
            className="comparison-relation" onMouseEnter={() => onHover(related.id)} onMouseLeave={() => onHover(null)}
            onFocus={() => onHover(related.id)} onBlur={() => onHover(null)} onClick={() => onRead(related.id)}>
            {link.status && <span className="evidence-stamp" data-status={link.status}>{EVIDENCE[link.status].label}</span>}
            <span>L{related.z_layer} · {shortNodeLabel(related.title, 22)}</span>
          </button>
        </li>
      ))}
      {rows.length > 6 && <li><button type="button" className="quiet-button" onClick={() => onRead(node.id)}>查看全部 {rows.length} 项</button></li>}
    </ul>;
  }

  return <aside id="node-inspector" className="comparison-dossier" aria-label="双卷宗对读">
    <header className="comparison-summary">
      <div className="comparison-summary-head">
        <h2>共性与差异</h2>
        <button type="button" className="compare-button" onClick={onChange}>更换右卷</button>
      </div>
      <div className="comparison-intersection">
        <span>交集</span>
        {hubs.slice(0, 3).map((node) => <button type="button" className="comparison-hub" title={node.title}
          key={node.id} onMouseEnter={() => onHover(node.id)} onMouseLeave={() => onHover(null)}
          onFocus={() => onHover(node.id)} onBlur={() => onHover(null)} onClick={() => onRead(node.id)}>
          L{node.z_layer} · {shortNodeLabel(node.title, 23)}
        </button>)}
        {sharedCodes.length > 0 && <DossierCodes codes={sharedCodes} interaction={codeInteraction} />}
        {!hubs.length && !sharedCodes.length && <span className="comparison-missing">暂无共同枢纽或编码</span>}
      </div>
      <div className="comparison-difference">
        <span>差异</span>
        <span>{left.credibility_tier} / {right.credibility_tier} 级 · {time(left)} / {time(right)}</span>
      </div>
    </header>
    <div className="comparison-scroll" tabIndex={0} aria-label="同步滚动对读内容">
      <div className="comparison-pair comparison-titles">
        {records.map((node, index) => <div key={node.id} className="comparison-heading">
          <div className="comparison-side">
            <span>{index === 0 ? '左卷' : '右卷'}</span>
            <span className="layer-code">L{node.z_layer} {LAYERS[node.z_layer].short}</span>
            <span className="tier-label" data-fiction={isFiction(node)}>{isFiction(node) ? 'F 级虚构' : `${node.credibility_tier} 级`}</span>
          </div>
          <h3 title={node.title}>{node.title}</h3>
          <button type="button" className="comparison-read" aria-label={`单独阅读 ${node.title}`} onClick={() => onRead(node.id)}>单独阅读 ↗</button>
        </div>)}
      </div>
      <Row heading={<h4>田野时空</h4>}>
        {records.map((node) => <dl key={node.id} className="comparison-facts">
          <dt>地点</dt><dd title={node.spatial?.location_name}>{node.spatial ? mapLabel(node) : '暂无地点'}</dd>
          <dt>年代</dt><dd>{time(node)}</dd>
          <dt>体裁</dt><dd>{GENRES[node.genre] ?? node.genre}</dd>
        </dl>)}
      </Row>
      <Row heading={<h4>编码</h4>}>
        {records.map((node) => <div key={node.id}>{dossierCodes(node).length
          ? <DossierCodes codes={dossierCodes(node)} interaction={codeInteraction} />
          : <p className="comparison-missing">暂无登记编码</p>}</div>)}
      </Row>
      <Row heading={<h4>L4 机制核验</h4>}>
        {records.map((node) => <div key={node.id}>{connections(node, true)}</div>)}
      </Row>
      <Row heading={<h4>跨层与相关卷宗</h4>}>
        {records.map((node) => <div key={node.id}>{connections(node, false)}</div>)}
      </Row>
      <Row heading={<><h4>叙事与原文</h4>
        <button type="button" className="compare-button" aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}>{expanded ? '收起全文' : '展开全文对读'}</button></>}>
        {records.map((node) => <div className="comparison-narrative" key={node.id}>
          {expanded ? <>
            {summary(node).map((text, index) => <p key={index}>{text}</p>)}
            <DossierOriginal node={node} />
            {!summary(node).length && !hasOriginal(node) && <p className="comparison-missing">暂无站内叙事正文</p>}
          </> : <p className="comparison-excerpt">{summary(node).join(' ') || (hasOriginal(node)
            ? node.markdown.trim() : '暂无站内叙事正文')}</p>}
        </div>)}
      </Row>
      <Row heading={<h4>文献出处</h4>}>
        {records.map((node) => <div key={node.id}><Sources citations={node.sources} /></div>)}
      </Row>
    </div>
  </aside>;
}
