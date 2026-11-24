import { Children, lazy, Suspense, useDeferredValue, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ViewportFrame } from './WorkbenchControls';
import type { LifeBook, LifeEntry } from './life';
import { lifeSearchExcerpt, OBSERVATION_KEY, rankLifeResults, readObservations } from './lifeExplore';
import LifeTimeline from './LifeTimeline';
import LifeInquiry from './LifeInquiry';
import { LIFE_MILESTONES } from './lifeMilestones';
import './life.css';

const LifeScene = lazy(() => import('./views/LifeScene'));
const LifeAstrolabe = lazy(() => import('./views/LifeAstrolabe'));
const base = import.meta.env.BASE_URL;

function headingParts(children: ReactNode) {
  const parts = Children.toArray(children);
  const last = parts[parts.length - 1];
  const match = typeof last === 'string' ? last.match(/\s*⟦anchor:([a-z0-9-]+)⟧\s*$/) : null;
  if (match && typeof last === 'string') parts[parts.length - 1] = last.slice(0, match.index);
  return { id: match?.[1], parts };
}

// Some handbook anchors are immediately followed by prose on the next line.
// Give the marker its own Markdown paragraph so it becomes a real, invisible
// navigation target instead of appearing as raw syntax in the text.
function separateAnchorMarkers(body: string) {
  return body.replace(/(^|\n)(⟦anchor:[a-z0-9-]+⟧)(?=\n|$)/g, '$1\n$2\n');
}

export default function LifeKnowledge() {
  const [book, setBook] = useState<LifeBook | null>(null);
  const [error, setError] = useState('');
  const [subject, setSubject] = useState<string | null>(null);
  const [volume, setVolume] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState(() => new URL(window.location.href).searchParams.get('entry'));
  const [query, setQuery] = useState('');
  const [sceneMode, setSceneMode] = useState<'galaxy' | 'astrolabe'>('galaxy');
  const [motionEnabled, setMotionEnabled] = useState(() => !window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [milestoneIndex, setMilestoneIndex] = useState<number | null>(null);
  const [inquiryIds, setInquiryIds] = useState<string[]>([]);
  const [renderer, setRenderer] = useState<'software' | 'webgl' | null>(null);
  const [observations, setObservations] = useState(readObservations);
  const [observationsOnly, setObservationsOnly] = useState(false);
  const [storageUnavailable, setStorageUnavailable] = useState(false);
  const [limit, setLimit] = useState(40);
  const [resetSerial, setResetSerial] = useState(0);
  const [showPdf, setShowPdf] = useState(false);
  const [enlargedFigure, setEnlargedFigure] = useState<{ src: string; alt: string } | null>(null);
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());
  const searchRef = useRef<HTMLInputElement>(null);
  const inspectorRef = useRef<HTMLElement>(null);

  useEffect(() => {
    try { localStorage.setItem(OBSERVATION_KEY, JSON.stringify(observations)); setStorageUnavailable(false); }
    catch { setStorageUnavailable(true); }
  }, [observations]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${base}knowledge/data.json`, { signal: controller.signal }).then((response) => {
      if (!response.ok) throw new Error(`读取失败 (${response.status})`);
      return response.json() as Promise<LifeBook>;
    }).then(setBook).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '无法载入知识库');
    });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setEnlargedFigure(null);
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault(); setSelectedId(null); searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, []);
  const byId = useMemo(() => new Map((book?.entries ?? []).map((entry) => [entry.id, entry])), [book]);
  // The full handbook is searchable, including figure captions. Cache each
  // normalized string lazily so successive keystrokes do not repeatedly join
  // and lowercase thousands of long entries on the rendering thread.
  const searchText = useMemo(() => new Map<string, string>(), [book]);
  const selected = selectedId ? byId.get(selectedId) : undefined;
  useEffect(() => {
    const anchor = window.location.hash.slice(1);
    if (selected && anchor && book?.anchors[anchor] === selected.id) {
      const timer = window.setTimeout(() => document.getElementById(anchor)?.scrollIntoView({ block: 'start' }), 100);
      return () => window.clearTimeout(timer);
    }
  }, [book, selected]);
  const results = useMemo(() => {
    if (!book) return [];
    const scope = book.entries.filter((entry) => (!subject || entry.subject === subject) && (!volume || entry.volume === volume)
      && (!observationsOnly || Object.hasOwn(observations, entry.id)));
    return rankLifeResults(scope, book, deferredQuery, searchText);
  }, [book, subject, volume, deferredQuery, searchText, observations, observationsOnly]);
  const highlightIds = useMemo(() => milestoneIndex !== null ? [...new Set(LIFE_MILESTONES.slice(0, milestoneIndex + 1).flatMap((event) => event.entries))].filter((id) => byId.has(id))
    : inquiryIds.length ? inquiryIds : deferredQuery || observationsOnly ? results.slice(0, 30).map((entry) => entry.id) : [],
  [milestoneIndex, byId, inquiryIds, deferredQuery, observationsOnly, results]);
  const related = useMemo(() => {
    if (!selected || !book) return [];
    const ids = new Set(selected.links);
    for (const entry of book.entries) if (entry.links.includes(selected.id)) ids.add(entry.id);
    return [...ids].flatMap((id) => byId.get(id) ?? []);
  }, [book, byId, selected]);

  function choose(id: string, anchor?: string) {
    if (!byId.has(id)) return;
    const entry = byId.get(id)!;
    if (subject && subject !== entry.subject) setSubject(null);
    if (volume && volume !== entry.volume) setVolume(null);
    setSelectedId(id); setShowPdf(false);
    const url = new URL(window.location.href);
    url.searchParams.set('view', 'life'); url.searchParams.set('entry', id);
    url.hash = anchor ?? '';
    window.history.replaceState({}, '', url);
    if (inspectorRef.current) inspectorRef.current.scrollTop = 0;
    if (window.matchMedia('(max-width: 760px)').matches) {
      requestAnimationFrame(() => inspectorRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }));
    }
    if (anchor) window.setTimeout(() => document.getElementById(anchor)?.scrollIntoView({ block: 'start' }), 100);
  }
  function clearSelection() {
    setSelectedId(null); setShowPdf(false);
    const url = new URL(window.location.href); url.searchParams.delete('entry'); url.hash = '';
    window.history.replaceState({}, '', url);
  }
  function chooseSubject(id: string | null) {
    setSubject(id); setVolume(null); setSelectedId(null); setQuery(''); setLimit(40); setShowPdf(false); setObservationsOnly(false); setMilestoneIndex(null); setInquiryIds([]);
    const url = new URL(window.location.href); url.searchParams.delete('entry');
    url.hash = '';
    window.history.replaceState({}, '', url);
  }
  function chooseVolume(id: string) {
    chooseSubject(null); setVolume(id);
  }
  if (error) return <div className="life-status" role="alert">知识星图加载失败：{error}</div>;
  if (!book) return <div className="life-status" role="status">正在载入知识星图…</div>;
  const pdfUrl = `${base}knowledge/handbook.pdf#page=${selected?.page ?? 1}`;
  const subjectLabel = book.subjects.find((item) => item.id === subject)?.title ?? volume ?? '全部学科';
  const volumes = [...new Set(book.subjects.map((item) => item.volume))];
  const isSaved = selected ? Object.hasOwn(observations, selected.id) : false;

  function toggleObservation(id: string) {
    setObservations((previous) => {
      const next = { ...previous };
      if (Object.hasOwn(next, id)) delete next[id]; else next[id] = '';
      return next;
    });
  }

  return <div className="life-workspace" data-low-power={sceneMode === 'astrolabe' || renderer === 'software' ? 'true' : undefined}>
    <aside className="life-sidebar" aria-label="知识学科">
      <div className="life-side-heading"><span>OMNIA / KNOWLEDGE ATLAS</span><strong>知识目录</strong><small>五卷 · 二十门</small></div>
      <button className="life-subject-all" type="button" aria-pressed={!subject && !volume} onClick={() => chooseSubject(null)}>
        <span>全部条目</span><b>{book.entries.length.toLocaleString()}</b></button>
      {volumes.map((volume) => <div className="life-volume" key={volume}>
        <button type="button" className="life-volume-name" aria-pressed={volume === subjectLabel && !subject} onClick={() => chooseVolume(volume)}>{volume} <span>↗</span></button>
        {book.subjects.filter((item) => item.volume === volume).map((item) => <button key={item.id} type="button"
          aria-pressed={subject === item.id} onClick={() => chooseSubject(item.id)}>
          <span>{item.title}</span><small>{item.count}</small></button>)}
      </div>)}
    </aside>
    <main className="life-map" aria-label="知识星图">
      <ViewportFrame />
      <svg className="life-celestial-hud" aria-hidden="true" viewBox="0 0 600 600">
        <circle cx="300" cy="300" r="244"/><circle cx="300" cy="300" r="233" strokeDasharray="2 8"/>
        <circle cx="300" cy="300" r="160" strokeDasharray="3 11"/><circle cx="300" cy="300" r="72"/>
        <path d="M300 44v30 M300 526v30 M44 300h30 M526 300h30 M119 119l20 20 M461 461l20 20 M481 119l-20 20 M139 461l-20 20"/>
        <path d="M300 140 438 380 162 380Z M300 460 162 220 438 220Z"/>
        <circle cx="300" cy="300" r="5"/><path d="M286 300h28 M300 286v28"/>
      </svg>
      <div className="life-map-heading"><span>ASTRAIA / KNOWLEDGE ATLAS</span><h1>OMNIA <small>万象星枢</small></h1>
        <p>《格物识微》 · {book.entries.length.toLocaleString()} 个知识节点</p></div>
      <div className="life-view-controls" aria-label="知识星图视角">
        <button type="button" aria-pressed={sceneMode === 'galaxy'} onClick={() => setSceneMode('galaxy')}>3D 星系</button>
        <button type="button" aria-pressed={sceneMode === 'astrolabe'} onClick={() => setSceneMode('astrolabe')}>2D 星盘</button>
        {sceneMode === 'galaxy' && <button type="button" aria-pressed={motionEnabled} onClick={() => setMotionEnabled((value) => !value)}>
          {motionEnabled ? '暂停星动' : '恢复星动'}</button>}
        <button type="button" className="life-reset" onClick={() => { chooseSubject(null); setResetSerial((value) => value + 1); }}>
          ◇ 总览</button>
      </div>
      <Suspense fallback={<div className="stage-message">正在绘制知识星图…</div>}>
        {sceneMode === 'galaxy'
          ? <LifeScene entries={book.entries} subjects={book.subjects} selectedId={selected?.id ?? null} subjectId={subject} volumeId={volume}
              highlightIds={highlightIds} connectHighlights={milestoneIndex === null} motionEnabled={motionEnabled} resetSerial={resetSerial} onSelect={choose} onSubject={chooseSubject} onVolume={chooseVolume} onRenderer={setRenderer} />
          : <LifeAstrolabe entries={book.entries} subjects={book.subjects} selectedId={selected?.id ?? null} subjectId={subject}
              volumeId={volume} highlightIds={highlightIds} connectHighlights={milestoneIndex === null} resetSerial={resetSerial} onSelect={choose} onSubject={chooseSubject} />}
      </Suspense>
      <LifeTimeline index={milestoneIndex} entries={byId} onChoose={choose} onChange={(index) => {
        setMilestoneIndex(index);
        if (index !== null) { setSubject(null); setVolume(null); setQuery(''); setInquiryIds([]); setObservationsOnly(false); clearSelection(); }
      }} />
      <div className="life-map-footer"><span>{highlightIds.length ? `✦　点亮 ${highlightIds.length} 项${milestoneIndex !== null ? '延伸阅读' : observationsOnly ? '观测' : '搜索'}轨迹` : '✦　五卷星臂 · 明星为学科'}</span>
        <span>{sceneMode === 'galaxy' ? '拖动旋转' : '拖动平移'} · 滚轮缩放 · 长按聚拢关联</span></div>
    </main>
    <aside className="life-inspector" ref={inspectorRef} aria-label="知识卷宗">
      <div className="life-search"><label htmlFor="life-search">检索知识库 <span>⌘ K</span></label>
        <input id="life-search" ref={searchRef} value={query} placeholder="搜索关键词、编号或问题" onChange={(event) => {
          setQuery(event.target.value); setMilestoneIndex(null); setInquiryIds([]); clearSelection(); setLimit(40);
        }} />
        <div className="life-reading-modes"><button type="button" aria-pressed={!observationsOnly} onClick={() => {
          setObservationsOnly(false); clearSelection(); setLimit(40);
        }}>全部知识</button><button type="button" aria-pressed={observationsOnly} onClick={() => {
          setObservationsOnly(true); setSubject(null); setVolume(null); setQuery(''); clearSelection(); setLimit(40);
        }}>观测列表 <span>{Object.keys(observations).length}</span></button></div>
      </div>
      <LifeInquiry book={book} onChoose={choose} onEvidence={(ids) => {
        setInquiryIds(ids); setMilestoneIndex(null); setSubject(null); setVolume(null); setQuery(''); setObservationsOnly(false); clearSelection();
      }} />
      {selected ? <article className="life-article">
        <button className="life-back" type="button" onClick={clearSelection}>← 返回条目目录</button>
        <div className="life-overline">{selected.volume} / {book.subjects.find((s) => s.id === selected.subject)?.title}</div>
        <h2>{selected.title}</h2>
        <button className="life-save" type="button" aria-pressed={isSaved} onClick={() => toggleObservation(selected.id)}>
          {isSaved ? '★ 已加入观测列表' : '☆ 加入观测列表'}</button>
        {isSaved && <label className="life-observation-note">个人笔记 <span>{storageUnavailable ? '浏览器未允许保存' : '保存在此浏览器'}</span>
          <textarea value={observations[selected.id]} maxLength={4000} placeholder="写下你的观察…" onChange={(event) => {
            const value = event.target.value;
            setObservations((previous) => ({ ...previous, [selected.id]: value }));
          }} /></label>}
        <div className="life-id">{selected.id} <span>{selected.topic}</span></div>
        <div className="life-source"><span>来源：《格物识微》{book.edition}</span><strong>PDF 第 {selected.page} 页</strong></div>
        <div className="life-prose"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
          a: ({ href, children }) => {
            if (href?.startsWith('#entry-')) {
              const id = href.slice(7).toUpperCase();
              return <a href={`?view=life&entry=${encodeURIComponent(id)}`} onClick={(event) => {
                if (byId.has(id)) { event.preventDefault(); choose(id); }
              }}>{children}</a>;
            }
            if (href?.startsWith('#')) {
              const anchor = href.slice(1), owner = book.anchors[anchor];
              if (owner) return <a href={`?view=life&entry=${encodeURIComponent(owner)}#${anchor}`} onClick={(event) => {
                event.preventDefault(); choose(owner, anchor);
              }}>{children}</a>;
            }
            return <a href={href} target={href?.startsWith('http') ? '_blank' : undefined} rel="noreferrer">{children}</a>;
          },
          img: ({ src, alt }) => {
            if (src?.startsWith('inline-figures/')) {
              const figure = book.figures?.[src.slice('inline-figures/'.length)];
              return <span className="life-figure" role="group" aria-label="原书图表及说明">
                <button className="life-figure-open" type="button" aria-label="放大原书图表"
                  onClick={() => setEnlargedFigure({ src, alt: alt ?? '原书图表' })}>
                  <img src={`${base}knowledge/${src}`} alt={alt ?? '原书图表'} loading="lazy" />
                  <span>查看大图 ↗</span>
                </button>
                {figure?.text && <span className="life-figure-text">{figure.text}</span>}
                {!!figure?.links.length && <span className="life-figure-links">{figure.links.map((href, index) =>
                  <a key={href} href={href} target="_blank" rel="noreferrer">图源与许可 {index + 1} ↗</a>)}</span>}
              </span>;
            }
            if (src?.startsWith('figures/')) return <span className="life-figure" role="group" aria-label="原书图表及说明">
              <button className="life-figure-open" type="button" aria-label="放大原书图表"
                onClick={() => setEnlargedFigure({ src, alt: alt ?? '原书图表' })}>
                <img src={`${base}knowledge/${src}`} alt={alt ?? ''} loading="lazy" />
                <span>查看大图 ↗</span>
              </button>
              {alt && <span className="life-figure-text">{alt}</span>}
            </span>;
            return <img src={src} alt={alt ?? ''} loading="lazy" />;
          },
          p: ({ children }) => {
            const parts = Children.toArray(children);
            const marker = parts.length === 1 && typeof parts[0] === 'string' ? parts[0].match(/^⟦anchor:([a-z0-9-]+)⟧$/) : null;
            return marker ? <span className="life-anchor" id={marker[1]} /> : <p>{children}</p>;
          },
          h4: ({ children }) => { const h = headingParts(children); return <h4 id={h.id}>{h.parts}</h4>; },
          h5: ({ children }) => { const h = headingParts(children); return <h5 id={h.id}>{h.parts}</h5>; },
          h6: ({ children }) => { const h = headingParts(children); return <h6 id={h.id}>{h.parts}</h6>; },
        }}>{separateAnchorMarkers(selected.body)}</ReactMarkdown></div>
        {related.length > 0 && <section className="life-related"><h3>原书交叉索引</h3>
          <p>以下连接来自手册原有的条目引用。</p>
          {related.map((entry: LifeEntry) => <button type="button" key={entry.id} onClick={() => choose(entry.id)}>
            <span>{entry.title}</span><small>{entry.volume !== selected.volume ? '跨卷 · ' : ''}{entry.id} →</small></button>)}
        </section>}
        <section className="life-original"><h3>原书图文</h3><p>原版保留全部图表、图注及页内版式。</p>
          <div className="life-original-actions"><button type="button" onClick={() => setShowPdf((value) => !value)}>
            {showPdf ? '收起原书' : '展开原书图文'}</button><a href={pdfUrl} target="_blank" rel="noreferrer">在新窗口打开 ↗</a></div>
          {showPdf && <iframe title={`格物识微：${selected.title}，第 ${selected.page} 页`} src={pdfUrl} />}
        </section>
      </article> : <div className="life-directory">
        <div className="life-overline">格物识微 / 全书增绘版</div><h2>{observationsOnly ? '观测列表' : subjectLabel}</h2>
        <p className="life-directory-intro">{observationsOnly ? '收藏的知识与个人笔记保存在此浏览器。'
          : '选择学科，或搜索、点击星点，阅读原书条目与图文。'}</p>
        <div className="life-results-heading"><span>{deferredQuery ? `搜索结果 · ${results.length}` : `条目目录 · ${results.length}`}</span><span>INDEX</span></div>
        {!!deferredQuery && results.length > 0 && <p className="life-search-context">按原书关键词匹配 · 星图点亮前 {Math.min(results.length, 30)} 项</p>}
        {results.slice(0, limit).map((entry) => <button type="button" className="life-result" key={entry.id} onClick={() => choose(entry.id)}>
          <span>{entry.title}</span><small>{entry.id} · 第 {entry.page} 页 · {entry.topic || entry.volume}</small>
          {!!deferredQuery && <em>{lifeSearchExcerpt(entry, deferredQuery)}</em>}</button>)}
        {!results.length && <p className="life-empty">{observationsOnly && !deferredQuery ? '打开知识条目，加入你的观测列表。' : '没有找到匹配的条目。'}</p>}
        {limit < results.length && <button className="life-more" type="button" onClick={() => setLimit((value) => value + 60)}>
          显示更多 · 还有 {results.length - limit} 条</button>}
      </div>}
    </aside>
    {enlargedFigure && <div className="life-zoom-backdrop" role="presentation" onClick={(event) => {
      if (event.target === event.currentTarget) setEnlargedFigure(null);
    }}>
      <section className="life-zoom-sheet" role="dialog" aria-modal="true" aria-label="原书图表大图">
        <div className="life-zoom-head"><strong>原书图表</strong>
          <button type="button" autoFocus onClick={() => setEnlargedFigure(null)}>关闭 ×</button></div>
        <img src={`${base}knowledge/${enlargedFigure.src}`} alt="原书图表放大图" />
        <p>{book.figures?.[enlargedFigure.src.slice('inline-figures/'.length)]?.text ?? enlargedFigure.alt}</p>
        <div className="life-figure-links">{book.figures?.[enlargedFigure.src.slice('inline-figures/'.length)]?.links.map((href, index) =>
          <a key={href} href={href} target="_blank" rel="noreferrer">图源与许可 {index + 1} ↗</a>)}</div>
      </section>
    </div>}
  </div>;
}
