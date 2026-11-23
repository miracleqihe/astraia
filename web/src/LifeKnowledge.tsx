import { lazy, Suspense, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ViewportFrame } from './WorkbenchControls';
import type { LifeBook, LifeEntry } from './life';
import './life.css';

const LifeScene = lazy(() => import('./views/LifeScene'));
const base = import.meta.env.BASE_URL;

export default function LifeKnowledge() {
  const [book, setBook] = useState<LifeBook | null>(null);
  const [error, setError] = useState('');
  const [subject, setSubject] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState(() => new URL(window.location.href).searchParams.get('entry'));
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(40);
  const [showPdf, setShowPdf] = useState(false);
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());
  const searchRef = useRef<HTMLInputElement>(null);
  const inspectorRef = useRef<HTMLElement>(null);

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
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault(); setSelectedId(null); searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, []);
  const byId = useMemo(() => new Map((book?.entries ?? []).map((entry) => [entry.id, entry])), [book]);
  const selected = selectedId ? byId.get(selectedId) : undefined;
  const results = useMemo(() => (book?.entries ?? []).filter((entry) => {
    if (subject && entry.subject !== subject) return false;
    if (!deferredQuery) return true;
    return `${entry.title} ${entry.id} ${entry.topic} ${entry.body}`.toLocaleLowerCase().includes(deferredQuery);
  }), [book, subject, deferredQuery]);
  const related = useMemo(() => {
    if (!selected || !book) return [];
    const ids = new Set(selected.links);
    for (const entry of book.entries) if (entry.links.includes(selected.id)) ids.add(entry.id);
    return [...ids].flatMap((id) => byId.get(id) ?? []);
  }, [book, byId, selected]);

  function choose(id: string) {
    if (!byId.has(id)) return;
    setSelectedId(id); setShowPdf(false);
    const url = new URL(window.location.href);
    url.searchParams.set('view', 'life'); url.searchParams.set('entry', id);
    window.history.replaceState({}, '', url);
    if (inspectorRef.current) inspectorRef.current.scrollTop = 0;
    if (window.matchMedia('(max-width: 760px)').matches) {
      requestAnimationFrame(() => inspectorRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }));
    }
  }
  function chooseSubject(id: string | null) {
    setSubject(id); setSelectedId(null); setLimit(40); setShowPdf(false);
    const url = new URL(window.location.href); url.searchParams.delete('entry');
    window.history.replaceState({}, '', url);
  }
  if (error) return <div className="life-status" role="alert">知识星图加载失败：{error}</div>;
  if (!book) return <div className="life-status" role="status">正在载入知识星图…</div>;
  const pdfUrl = `${base}knowledge/handbook.pdf#page=${selected?.page ?? 1}`;
  const subjectLabel = book.subjects.find((item) => item.id === subject)?.title ?? '全部学科';
  const volumes = [...new Set(book.subjects.map((item) => item.volume))];

  return <div className="life-workspace">
    <aside className="life-sidebar" aria-label="知识学科">
      <div className="life-side-heading"><span>THE KNOWLEDGE ATLAS</span><strong>知识目录</strong><small>五卷 · 二十门</small></div>
      <button className="life-subject-all" type="button" aria-pressed={!subject} onClick={() => chooseSubject(null)}>
        <span>全部条目</span><b>{book.entries.length.toLocaleString()}</b></button>
      {volumes.map((volume) => <div className="life-volume" key={volume}>
        <p>{volume}</p>
        {book.subjects.filter((item) => item.volume === volume).map((item) => <button key={item.id} type="button"
          aria-pressed={subject === item.id} onClick={() => chooseSubject(item.id)}>
          <span>{item.title}</span><small>{item.count}</small></button>)}
      </div>)}
    </aside>
    <main className="life-map" aria-label="知识星图">
      <ViewportFrame />
      <div className="life-map-heading"><span>ASTRAIA / KNOWLEDGE ATLAS</span><h1>Life and Knowledge</h1>
        <p>格物识微 · {book.entries.length.toLocaleString()} 个知识节点</p></div>
      <Suspense fallback={<div className="stage-message">正在绘制知识星图…</div>}>
        <LifeScene entries={book.entries} subjects={book.subjects} selectedId={selected?.id ?? null} subjectId={subject} onSelect={choose} />
      </Suspense>
      <div className="life-map-footer"><span>✦　每颗星代表一个条目</span><span>拖动旋转 · 滚轮缩放 · 点击阅读</span></div>
    </main>
    <aside className="life-inspector" ref={inspectorRef} aria-label="知识卷宗">
      <div className="life-search"><label htmlFor="life-search">检索知识库 <span>⌘ K</span></label>
        <input id="life-search" ref={searchRef} value={query} placeholder="搜索标题、编号或正文" onChange={(event) => {
          setQuery(event.target.value); setSelectedId(null); setLimit(40);
        }} /></div>
      {selected ? <article className="life-article">
        <button className="life-back" type="button" onClick={() => { setSelectedId(null); setShowPdf(false); }}>← 返回条目目录</button>
        <div className="life-overline">{selected.volume} / {book.subjects.find((s) => s.id === selected.subject)?.title}</div>
        <h2>{selected.title}</h2>
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
            return <a href={href} target={href?.startsWith('http') ? '_blank' : undefined} rel="noreferrer">{children}</a>;
          },
          img: ({ src, alt }) => <img src={src?.startsWith('figures/') ? `${base}knowledge/${src}` : src} alt={alt ?? ''} loading="lazy" />,
        }}>{selected.body}</ReactMarkdown></div>
        {related.length > 0 && <section className="life-related"><h3>原书交叉索引</h3>
          <p>以下连接来自手册原有的条目引用。</p>
          {related.map((entry: LifeEntry) => <button type="button" key={entry.id} onClick={() => choose(entry.id)}>
            <span>{entry.title}</span><small>{entry.id} →</small></button>)}
        </section>}
        <section className="life-original"><h3>原书图文</h3><p>原版保留全部图表、图注及页内版式。</p>
          <div className="life-original-actions"><button type="button" onClick={() => setShowPdf((value) => !value)}>
            {showPdf ? '收起原书' : '展开原书图文'}</button><a href={pdfUrl} target="_blank" rel="noreferrer">在新窗口打开 ↗</a></div>
          {showPdf && <iframe title={`格物识微：${selected.title}，第 ${selected.page} 页`} src={pdfUrl} />}
        </section>
      </article> : <div className="life-directory">
        <div className="life-overline">格物识微 / 全书增绘版</div><h2>{subjectLabel}</h2>
        <p className="life-directory-intro">从左侧选择学科，或搜索、点击星点，阅读完整条目与原书图文。手册原稿注明为教学草稿。</p>
        <div className="life-results-heading"><span>{deferredQuery ? `搜索结果 · ${results.length}` : `条目目录 · ${results.length}`}</span><span>INDEX</span></div>
        {results.slice(0, limit).map((entry) => <button type="button" className="life-result" key={entry.id} onClick={() => choose(entry.id)}>
          <span>{entry.title}</span><small>{entry.id} · {entry.topic || entry.volume}</small></button>)}
        {!results.length && <p className="life-empty">没有找到匹配的条目。</p>}
        {limit < results.length && <button className="life-more" type="button" onClick={() => setLimit((value) => value + 60)}>
          显示更多 · 还有 {results.length - limit} 条</button>}
      </div>}
    </aside>
  </div>;
}
