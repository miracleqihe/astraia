import { useEffect, useMemo, useRef, useState } from 'react';
import type { LifeBook, LifeEntry } from './life';
import { lifeSearchExcerpt, lifeSearchTerms, rankLifeResults } from './lifeExplore';

interface Props { book: LifeBook; onChoose: (id: string) => void; onEvidence: (ids: string[]) => void; }

/** Extracts evidence from the book and identifies only its existing links. */
export default function LifeInquiry({ book, onChoose, onEvidence }: Props) {
  const [input, setInput] = useState('');
  const [question, setQuestion] = useState('');
  const cache = useMemo(() => new Map<string, string>(), [book]);
  const notify = useRef(onEvidence); notify.current = onEvidence;
  const curated = question.includes('熵') && /生命|演化|进化|生物/.test(question) ? {
    text: '生命的生长和演化并不违反热力学第二定律。生物体是与外界交换物质和能量的开放系统：局部结构可以在摄取能量的过程中形成或维持，同时向环境释放热量和代谢产物。计算熵变时需要连同环境一起考虑。演化则涉及可遗传差异及其在多代群体中的变化，不能把“熵增”直接当作自然选择的机制。',
    ids: ['PHY-2-0003', 'BIO-2-0001', 'BIO-3-0012'],
    source: 'OpenStax · 生命与热力学第二定律', url: 'https://openstax.org/books/college-physics-2e/pages/15-6-entropy-and-the-second-law-of-thermodynamics-disorder-and-the-unavailability-of-energy',
  } : /光合/.test(question) && /地球|环境|氧|碳/.test(question) ? {
    text: '植物和部分微生物利用光能，把二氧化碳中的碳固定到有机物中；产氧光合作用还会释放氧气。单个生物的代谢与地球尺度的碳循环、海洋和大气变化相互联系，但一个地区的二氧化碳变化不能仅凭某一种过程判断。',
    ids: ['BIO-2-0001', 'CHE-3-0004', 'BIO-5-0006'],
    source: 'NASA · 碳循环', url: 'https://science.nasa.gov/earth/earth-observatory/the-carbon-cycle/',
  } : null;
  const evidence = useMemo(() => {
    if (!question) return [];
    const terms = lifeSearchTerms(question);
    if (!terms.length) return [];
    const found: LifeEntry[] = [], used = new Set<string>(), subjects = new Set<string>();
    const take = (entry: LifeEntry | undefined) => {
      if (entry && !used.has(entry.id)) { found.push(entry); used.add(entry.id); subjects.add(entry.subject); }
    };
    for (const id of curated?.ids ?? []) take(book.entries.find((entry) => entry.id === id));
    // Cover each recognizable concept first, then prefer other chapters.
    for (const term of terms.slice(0, 5)) { if (found.length >= 5) break; take(rankLifeResults(book.entries, book, term, cache)[0]); }
    const candidates = rankLifeResults(book.entries, book, question, cache);
    for (const candidate of candidates) {
      if (found.length >= 5) break;
      if (!subjects.has(candidate.subject)) take(candidate);
    }
    for (const candidate of candidates) { if (found.length >= 5) break; take(candidate); }
    return found;
  }, [book, cache, question]);
  useEffect(() => { if (question) notify.current(evidence.map((entry) => entry.id)); }, [question, evidence]);
  const crossReferences = evidence.flatMap((entry, i) => evidence.slice(i + 1).flatMap((other) =>
    entry.links.includes(other.id) || other.links.includes(entry.id) ? [[entry, other] as const] : []));

  function ask(value: string) { const next = value.trim(); setInput(value); if (next && next === question) notify.current(evidence.map((entry) => entry.id)); setQuestion(next); }
  return <details className="life-inquiry">
    <summary>跨章节问答 <span>QUESTION / EVIDENCE</span></summary>
    <form onSubmit={(event) => { event.preventDefault(); ask(input); }}>
      <label htmlFor="life-question">提出问题，查找相关章节</label>
      <div className="life-question-row"><input id="life-question" value={input}
        onChange={(event) => setInput(event.target.value)} placeholder="例如：光合作用与地球环境" />
        <button type="submit">查找</button></div>
    </form>
    {!question && <div className="life-question-examples"><span>试一试：</span>
      <button type="button" onClick={() => ask('光合作用与地球环境')}>光合作用与地球环境</button>
      <button type="button" onClick={() => ask('地质年代与放射性定年')}>地质年代与放射性定年</button></div>}
    {!!question && <div className="life-answer" aria-live="polite">
      <p>关于“{question}”</p>
      {evidence.length ? <>
        {curated && <><p className="life-answer-synthesis">{curated.text}</p>
          <p><a href={curated.url} target="_blank" rel="noreferrer">{curated.source} ↗</a></p></>}
        <p>{curated ? '相关原书章节：' : '以下是原书中相关章节的摘录，可以逐条打开阅读。'}</p>
        {evidence.map((entry) => <button className="life-answer-evidence" type="button" key={entry.id} onClick={() => onChoose(entry.id)}>
          <strong>{entry.title}</strong><span>《格物识微》· {entry.volume} · 第 {entry.page} 页</span>
          <em>{lifeSearchExcerpt(entry, question)}</em></button>)}
        {!!crossReferences.length && <p>原书交叉索引：{crossReferences.map(([a, b]) => `${a.title} ↔ ${b.title}`).join('；')}。</p>}
        {!crossReferences.length && <p>这些摘录可供对照；当前未发现它们之间的原书交叉引用。</p>}
      </> : <p>没有找到相关章节，请尝试换用更具体的词。</p>}
    </div>}
  </details>;
}
