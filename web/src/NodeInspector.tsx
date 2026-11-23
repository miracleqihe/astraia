import { useEffect, useRef, useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  coordinatesOf, EVIDENCE, isFiction, LAYERS, linkKey, locationPrecision, mapLabel, otherEnd, READING_LABELS, RELATIONS, STANDARDS,
  type Citation, type CodeFocus, type GraphIndex, type GraphNode,
} from './graph';

const RELATION_PAGE_SIZE = 80;

const SOURCE_TYPES: Record<string, string> = {
  primary_archive: '原始档案', archival_catalogue: '档案目录', scholarly_database: '学术数据库',
  gazetteer: '地名录', peer_reviewed: '同行评议论文', monograph: '学术专著', official_standard: '官方索引',
  research_dataset: '研究数据', user_supplied_outline: '用户提供的研究提纲',
  historical_reference: '调查库登记的史料线索',
  newspaper_report: '报刊报道', field_report: '现场采访', interview: '人物访谈',
  institutional_account: '机构资料', community_retelling: '网络流传版本',
  zibuyu_revision_link: '维基文库固定版本', historical_text_transcription: '古籍转录',
  pdf: 'PDF 资料', web_page: '网页资料', plain_text: '纯文本资料',
  pangloss_na_catalogue: '馆藏目录', pangloss_na_detail: '馆方录音详情',
  pangloss_na_selection: '录音选取索引', pangloss_annotation_index: '馆方分句结构索引',
  pangloss_na_context_previous: '首轮选取对照', pangloss_na_context_manifest: '口述背景详情清单',
  pangloss_japhug_catalogue: '嘉绒语馆藏目录', pangloss_japhug_detail: '馆方录音详情',
  pangloss_japhug_original: '馆方单条录音', pangloss_japhug_selection: '详情选取索引',
  pangloss_japhug_supplement_detail: '后续录音详情', pangloss_japhug_supplement_selection: '补充选取清单',
  pangloss_japhug_supplement_manifest: '补充快照清单',
  pangloss_khmu_catalogue: 'Khmu 馆藏目录', pangloss_khmu_detail: '馆方录音详情',
  pangloss_khmu_original: '馆方单条录音', pangloss_khmu_selection: '详情选取索引',
  pangloss_khmu_comparison: '目录待核对照',
  pangloss_khmu_supplement_detail: '后续录音详情', pangloss_khmu_supplement_selection: '补充选取清单',
  pangloss_khmu_supplement_manifest: '补充快照清单',
  korea_aks_catalogue: '韩国公共数据目录', korea_aks_receipt: '目录下载凭据',
  korea_aks_search_manifest: '馆方检索索引清单', korea_aks_detail_manifest: '馆方详情索引清单',
  korea_aks_crosswalk_base: '目录候选对照', korea_aks_crosswalk_detail: '候选详情对照',
  korea_aks_search_index: '馆方检索字段', korea_aks_detail_index: '馆方单条字段与原文链接',
  lanna_manifest: '北泰手稿馆检索清单', lanna_search: '北泰手稿馆检索字段', lanna_viewer: '馆方手稿原图',
  sinica_catalogue: '馆藏目录', sinica_original: '馆方详情页',
  sinica_detail_metadata: '馆方描述字段', sinica_community_gis: '社区地标对照',
  bl_khmer_catalogue: '大英图书馆馆藏目录', lowell_sea_catalogue: '洛厄尔馆藏目录字段',
  nitean_catalogue: '高棉文转录目录', nitean_chapter: '高棉文单篇出处索引',
  wikisource_catalogue: '跨版本卷册目录对照', heritage_register_2011: '2011 年国家级非遗名录',
  heritage_register_2008: '2008 年国家级非遗名录', heritage_register_2014: '2014 年国家级非遗名录',
  heritage_register_2021_pdf: '2021 年国务院公报名录原表', heritage_register_2021_index: '2021 年公报字段索引',
  cole_scan_link: '原书候选扫描', cole_toc_index: '原书目录字段索引', cole_ocr: '原始分页 OCR',
  cole_page_index: 'OCR 页边界索引', cole_ocr_segments: '逐页 OCR 候选', cole_ocr_segments_manifest: '逐页范围清单',
  na_tone_book: '纳语出版专著', na_tone_table_source: '专著目录源码', na_tone_crosswalk: '书中链接对照',
  na_tone_datacite_manifest: 'DOI 登记快照', na_tone_catalogue: '馆方录音目录',
  na_tone_new_selection: '专著新增候选', na_tone_catalogue_candidate: '馆方录音原页',
};

function webUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' || url.protocol === 'http:') return url.href;
  } catch {
    return undefined;
  }
  return undefined;
}

function yearLabel(year: number): string {
  return year < 0 ? `公元前 ${-year} 年` : `${year} 年`;
}

function temporalLabel(temporal: NonNullable<GraphNode['temporal']>): string {
  const { year_start: start, year_end: end, era_label: era } = temporal;
  if (era === '资料出版' && start !== null && start === end) return `资料出版 · ${yearLabel(start)}`;
  if (era === '学校采录' && start !== null && end !== null) {
    return start === end ? `学校采录 · ${yearLabel(start)}` : `学校采录 · ${start}–${end} 年`;
  }
  if (start === null) return end === null ? era : `截至 ${yearLabel(end)}`;
  if (end === null) return `${yearLabel(start)}起`;
  if (start === end) return yearLabel(start);
  if (start < 0 && end < 0) return `公元前 ${-start}–${-end} 年`;
  return start >= 0 ? `${start}–${end} 年` : `${yearLabel(start)}至 ${yearLabel(end)}`;
}

function Sources({ citations }: { citations: Citation[] }) {
  if (!citations.length) return <p className="inspector-empty">这张卡片暂无出处。</p>;
  return (
    <ol className="source-list">
      {citations.map((source, index) => {
        const url = webUrl(source.url) ?? webUrl(source.doi ? `https://doi.org/${source.doi}` : null);
        return (
          <li key={`${source.citation}-${index}`} data-source-number={index + 1}>
            <span className="source-type">{SOURCE_TYPES[source.type] ?? source.type}</span>
            <p>{source.citation}</p>
            {source.locator && <p className="source-locator">{source.locator}</p>}
            {source.local_path && <p className="source-locator"><code>{source.local_path}</code></p>}
            {url && <a href={url} target="_blank" rel="noopener noreferrer" aria-label={`查看第 ${index + 1} 条来源`}>查看来源</a>}
          </li>
        );
      })}
    </ol>
  );
}

function CatalogueOverview({ node }: { node: GraphNode }) {
  const source = node.sources[0];
  const place = node.spatial?.location_name.replace(/\s+/g, ' ');
  if (!source && !place) return null;
  return <section className="reading-section" data-section="reading">
    <h4>目录提要</h4>
    {place && <p>{place}</p>}
    {source && <p className="catalogue-source">{source.citation}{source.locator && <> · {source.locator}</>}</p>}
  </section>;
}

function Edition({ node }: { node: GraphNode }) {
  const edition = node.reading?.edition;
  if (!edition) return null;
  const url = webUrl(node.sources[edition.source_number - 1]?.url);
  return <section data-section="text" className="inspector-section">
    <h4>古籍正文</h4>
    <article className="classical-reading" lang="zh-Hant">
      {edition.text.split(/\n{2,}/u).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
    </article>
    <p className="edition-credit">袁枚《子不语》 · {url && <a href={url} target="_blank" rel="noopener noreferrer">维基文库贡献者转录</a>}
      {' · '}<a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a>
    </p>
  </section>;
}

interface Props {
  node: GraphNode;
  graph: GraphIndex;
  onSelect: (id: string) => void;
  onClose: () => void;
  onCompare: () => void;
  onNodeHover: (id: string | null) => void;
  onCodeFocus: (code: CodeFocus | null) => void;
  onCodePin: (code: CodeFocus) => void;
  onLocate: (id: string) => void;
  secondary?: boolean;
}

export function NodeInspector({ node, graph, onSelect, onClose, onCompare, onNodeHover, onCodeFocus, onCodePin, onLocate, secondary = false }: Props) {
  const [relationLimit, setRelationLimit] = useState(RELATION_PAGE_SIZE);
  const contentRef = useRef<HTMLDivElement>(null);
  const links = graph.adjacency.get(node.id) ?? [];
  const layer = LAYERS[node.z_layer];
  const yearSuffix = node.title.match(/（\d{4}(?:[–-]\d{4})?）$/)?.[0];
  const coordinates = coordinatesOf(node);
  const reading = node.reading;
  const paragraphs = reading?.paragraphs ?? [];
  const hasEdition = !!reading?.edition;
  const hasMarkdown = !!node.markdown.trim() && !node.markdown.startsWith('### 资料目录');
  const hasText = hasEdition || hasMarkdown;
  const hasOverview = paragraphs.length > 0 || (!hasText && (!!node.spatial || node.sources.length > 0));
  const codes = Object.entries(STANDARDS).flatMap(([key, label]) => (
    node.standards[key as keyof GraphNode['standards']].map((code) => ({ system: key, code, label: `${label} ${code}` }))
  ));

  useEffect(() => {
    if (contentRef.current) contentRef.current.scrollTop = 0;
  }, [node.id]);
  useEffect(() => setRelationLimit(RELATION_PAGE_SIZE), [node.id]);
  const orderedLinks = [...links].sort((left, right) => {
    const a = graph.byId.get(otherEnd(left, node.id))?.z_layer === 4 ? 0 : 1;
    const b = graph.byId.get(otherEnd(right, node.id))?.z_layer === 4 ? 0 : 1;
    return a - b;
  });
  const jump = (section: string) => contentRef.current?.querySelector(section)?.scrollIntoView({
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start',
  });

  return (
    <aside id={secondary ? undefined : 'node-inspector'} className="inspector" aria-label={secondary ? '对比节点详情' : '节点详情'}>
      <div className="inspector-head">
        <div className="panel-heading">
          <h2>节点卷宗</h2>
          <div className="inspector-actions"><button type="button" className="compare-button" onClick={onCompare}>＋ 加入对比</button>
            <button type="button" className="icon-button close-inspector" aria-label="关闭节点详情" onClick={onClose}>×</button></div>
        </div>
        <div className="record-meta">
          <span className={`node-shape shape-${node.z_layer}`} aria-hidden="true" />
          <span>L{node.z_layer} {layer.short}</span>
          <span className="meta-divider" />
          <span className="tier-label" data-fiction={isFiction(node)}>{isFiction(node) ? 'F 级虚构' : `${node.credibility_tier} 级信源`}</span>
        </div>
        <h3 className="record-title">{yearSuffix
          ? <>{node.title.slice(0, -yearSuffix.length)}<wbr /><span className="record-year">{yearSuffix}</span></>
          : node.title}</h3>
        {node.aliases[0] && node.aliases[0] !== node.title && <p className="record-alias">{node.aliases[0]}</p>}
        {coordinates && <div className="record-location">
          <span title={node.spatial?.location_name}>{mapLabel(node)}</span>
          <button type="button" onClick={() => onLocate(node.id)}>在地图定位 <span aria-hidden="true">↗</span></button>
        </div>}
      </div>

      <nav className="inspector-nav" aria-label="节点详情分区">
        {hasOverview && <button type="button" onClick={() => jump('[data-section="reading"]')}>阅读</button>}
        {hasText && <button type="button" onClick={() => jump('[data-section="text"]')}>原文</button>}
        <button type="button" onClick={() => jump('[data-section="facts"]')}>概况</button>
        <button type="button" onClick={() => jump('[data-section="sources"]')}>出处 <span>{node.sources.length}</span></button>
        {links.length > 0 && <button type="button" onClick={() => jump('[data-section="relations"]')}>关联 <span>{links.length}</span></button>}
      </nav>

      <div className="inspector-content" ref={contentRef}>
        {reading && paragraphs.length > 0
          ? <section className="reading-section" data-section="reading" data-reading-kind={reading.kind}>
            <h4>{READING_LABELS[reading.kind]}</h4>
            {paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}
            <div className="reading-citations" aria-label="提要出处">
              <span>出处</span>
              {reading.source_numbers.map((number) => <button key={number} type="button" aria-label={`查看出处 ${number}`}
                onClick={() => jump(`[data-source-number="${number}"]`)}>{number}</button>)}
            </div>
          </section>
          : !hasText && <CatalogueOverview node={node} />}
        {hasEdition && <Edition node={node} />}
        {!hasEdition && hasMarkdown && <section data-section="text" className="inspector-section"><h4>资料正文</h4>
          <article className="markdown-body" aria-label="Markdown 原文">
            <Markdown skipHtml remarkPlugins={[remarkGfm]} components={{
              a: ({ href, children }) => {
                const url = webUrl(href);
                return url ? <a href={url} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>;
              },
              img: ({ alt, src }) => {
                const url = webUrl(typeof src === 'string' ? src : undefined);
                return url ? <a href={url} target="_blank" rel="noopener noreferrer">{alt || '查看原图'}</a>
                  : <span>{alt || '本地图片'}</span>;
              },
            }}>{node.markdown}</Markdown>
          </article>
        </section>}
        <dl className="record-facts" data-section="facts">
          {node.spatial && <div><dt>地点</dt><dd>{node.spatial.location_name}</dd></div>}
          {coordinates && <div><dt>点位</dt><dd><span className="numeric">{coordinates[1].toFixed(node.spatial?.precision === 'exact' ? 5 : 2)}°, {coordinates[0].toFixed(node.spatial?.precision === 'exact' ? 5 : 2)}°</span>
            {' · '}{locationPrecision(node)}{reading?.location_note && <small>{reading.location_note}</small>}</dd></div>}
          {node.temporal && <div><dt>时间</dt><dd title={node.temporal.uncertainty_note ?? undefined}>{temporalLabel(node.temporal)}</dd></div>}
          {!node.audit.reviewed_by_human && <div><dt>复核</dt><dd>待人工复核{node.audit.is_sample ? ' · 样例' : ''}</dd></div>}
          {node.audit.reviewed_by_human && node.audit.reviewer && <div><dt>复核人</dt><dd>{node.audit.reviewer}</dd></div>}
          {node.audit.review_note && <div><dt>复核说明</dt><dd>{node.audit.review_note}</dd></div>}
          {node.audit.public_release && node.audit.public_rights_note && <div><dt>公开依据</dt><dd>{node.audit.public_rights_note}</dd></div>}
        </dl>
        {codes.length > 0 && <div className="code-plates" aria-label="标准码">{codes.map((code) => <button key={`${code.system}-${code.code}`}
          type="button" onMouseEnter={() => onCodeFocus(code)} onMouseLeave={() => onCodeFocus(null)}
          onFocus={() => onCodeFocus(code)} onBlur={() => onCodeFocus(null)} onClick={() => onCodePin(code)}>{code.label}</button>)}</div>}
        <section data-section="sources" className="inspector-section"><h4>文献出处</h4><Sources citations={node.sources} /></section>
        {links.length > 0 && <section data-section="relations" className="inspector-section">
          <h4>机制核验与跨层关联</h4>
          <ul className="relation-list">
            {orderedLinks.slice(0, relationLimit).map((link) => {
              const related = graph.byId.get(otherEnd(link, node.id));
              if (!related) return null;
              const evidence = link.status ? EVIDENCE[link.status] : null;
              return <li key={linkKey(link)} data-refuted={link.status === 'refuted'}>
                <div className="relation-meta"><span>L{related.z_layer} · {RELATIONS[link.type] ?? link.type}</span>
                  {evidence && <span className="evidence-stamp" data-status={link.status}>{link.status === 'confirmed' ? '✓ ' : link.status === 'refuted' ? '✕ ' : '? '}{evidence.label}</span>}</div>
                <button type="button" className="relation-node" onMouseEnter={() => onNodeHover(related.id)}
                  onMouseLeave={() => onNodeHover(null)} onFocus={() => onNodeHover(related.id)} onBlur={() => onNodeHover(null)}
                  onClick={() => onSelect(related.id)}>{related.title}</button>
                {link.matched_codes.length > 0 && <p>{link.matched_codes.map(({ system, code }) => `${STANDARDS[system] ?? system} ${code}`).join(' · ')}</p>}
                {link.note && <p>{link.note}</p>}
              </li>;
            })}
            {links.length > relationLimit && <li><button type="button" className="relation-node"
              onClick={() => setRelationLimit((limit) => limit + RELATION_PAGE_SIZE)}>显示更多关联（{relationLimit} / {links.length}）</button></li>}
          </ul>
        </section>}
      </div>
      {node.sources.some((source) => source.local_path) && <div className="inspector-footer" title={`vault/${node.source_path}`}>vault/{node.source_path}</div>}
    </aside>
  );
}
