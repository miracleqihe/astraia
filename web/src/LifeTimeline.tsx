import { useEffect, useState } from 'react';
import type { LifeEntry } from './life';
import { LIFE_MILESTONES } from './lifeMilestones';

interface Props {
  index: number | null;
  entries: Map<string, LifeEntry>;
  onChange: (index: number | null) => void;
  onChoose: (id: string) => void;
}

export default function LifeTimeline({ index, entries, onChange, onChoose }: Props) {
  const [playing, setPlaying] = useState(false);
  const event = index === null ? null : LIFE_MILESTONES[index];
  useEffect(() => {
    if (!playing) return;
    if (index === null) { setPlaying(false); return; }
    if (index === LIFE_MILESTONES.length - 1) { setPlaying(false); return; }
    const timer = window.setTimeout(() => onChange(index + 1), 2500);
    return () => window.clearTimeout(timer);
  }, [playing, index, onChange]);
  return <section className="life-timeline" aria-label="宇宙演化时间轴">
    {event && <div className="life-timeline-detail" aria-live="polite">
      <button type="button" className="life-timeline-close" aria-label="关闭时间轴事件" onClick={() => { setPlaying(false); onChange(null); }}>×</button>
      <small>{event.age}</small><strong>{event.title}</strong><p>{event.description}</p>
      <a href={event.url} target="_blank" rel="noreferrer">{event.source} ↗</a>
      <div className="life-timeline-reading"><span>延伸阅读</span>{event.entries.flatMap((id) => {
        const entry = entries.get(id);
        return entry ? [<button type="button" key={id} onClick={() => onChoose(id)}>{entry.title} →</button>] : [];
      })}</div>
    </div>}
    <div className="life-timeline-head"><span>宇宙演化时间轴 <button type="button" className="life-timeline-play"
      onClick={() => { if (!playing && (index === null || index === LIFE_MILESTONES.length - 1)) onChange(0); setPlaying(!playing); }}>{playing ? '暂停' : '播放'}</button></span>
      <span>{event ? `${index! + 1} / ${LIFE_MILESTONES.length} · ${event.age}` : '代表节点 · 非等距'}</span></div>
    <input className="life-timeline-slider" aria-label="选择宇宙演化节点" type="range" min="0" max={LIFE_MILESTONES.length - 1}
      step="1" value={index ?? 0} aria-valuetext={event ? `${event.age}，${event.title}` : '尚未选择'}
      onChange={(change) => { setPlaying(false); onChange(Number(change.target.value)); }} />
    <div className="life-timeline-track">
      {LIFE_MILESTONES.map((item, i) => <button key={item.title} type="button"
        aria-label={`${item.age}：${item.title}`} aria-pressed={index === i}
        title={`${item.age} · ${item.title}`} onClick={() => { setPlaying(false); onChange(i); }}><span /></button>)}
    </div>
    <div className="life-timeline-ends"><span>宇宙初期</span><span>{event ? event.title : '选择一个时间节点'}</span><span>人类与地球</span></div>
  </section>;
}
