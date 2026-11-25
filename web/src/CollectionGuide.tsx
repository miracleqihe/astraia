import { useMemo } from 'react';
import { mapLabel, type GraphIndex } from './graph';
import { CONTENT_GROUPS, nodeContentGroup, nodeRegion, REGIONS, type ContentGroup, type Region } from './catalogueBrowse';
import { portalHref } from './portalNavigation';

const CASES = [
  'case_cn_meigu_ghost_boards_1992',
  'case_egypt_jinn_sleep_paralysis',
  'case_ph_samar_biringan_city',
];
const STORY_TRAILS = [
  { id: 'text_atlas_water_encounters', places: '洞庭湖 / 河内 / 济州 / 东南亚湖岸' },
  { id: 'text_atlas_night_travel', places: '北京 / 石卷 / 芝加哥 / 奇洛埃' },
  { id: 'text_atlas_landmark_memory', places: '三亚 / 远野 / 马基林山 / 开普敦' },
  { id: 'text_atlas_unusual_sightings', places: '长白山 / 喀纳斯 / 湄公河 / 布利亚' },
];
const PAIRS = [
  { title: '睡眠瘫痪 · 访谈与实验', description: '开罗访谈 / 东京实验', left: 'case_egypt_jinn_sleep_paralysis', right: 'case_sleep_paralysis_lab_1992' },
  { title: '妖术恐慌 · 跨地域对读', description: '塞勒姆 1692 / 中国 1768', left: 'case_salem_1692', right: 'case_china_soulstealers_1768' },
];
const SYZYGY_HIGHLIGHTS = [
  { title: '老巫婆夜访 ⇄ 睡眠与情绪', desc: '纽芬兰口述访谈 ×《格物识微》生理机制', story: 'case_old_hag_sleep_paralysis_1982', entry: 'HEA-009' },
  { title: 'H 夫人闹鬼住宅 ⇄ 一氧化碳危害', desc: '1921 年病例档案 ×《格物识微》化学毒理', story: 'case_mrs_h_co_haunting_1921', entry: 'CHE-6-0016' },
  { title: '乾隆叫魂案 ⇄ 社会关系与恐慌', desc: '1768 年清代档案 ×《格物识微》社会契约', story: 'case_china_soulstealers_1768', entry: 'SOC-1-0009' },
];

export function CollectionGuide({ graph, onRead, onCompare, onBrowse, onOpenOmnia }: {
  graph: GraphIndex;
  onRead: (id: string) => void;
  onCompare: (left: string, right: string) => void;
  onBrowse: (region: Region, content: ContentGroup) => void;
  onOpenOmnia: () => void;
}) {
  const trails = STORY_TRAILS.filter(({ id }) => graph.byId.has(id));
  const counts = useMemo(() => {
    const region = new Map<Region, number>(), content = new Map<ContentGroup, number>();
    for (const node of graph.nodes) {
      const r = nodeRegion(node), c = nodeContentGroup(node);
      region.set(r, (region.get(r) ?? 0) + 1); content.set(c, (content.get(c) ?? 0) + 1);
    }
    return { region, content };
  }, [graph.nodes]);
  return <aside id="node-inspector" className="collection-guide" aria-labelledby="collection-guide-title">
    <header>
      <span className="guide-overline">ASTRAIA / PHYSIS × MYTHOS GUIDE</span>
      <h2 id="collection-guide-title">馆藏导览</h2>
      <p>从地理舆图与四层星络读地方志怪与档案，再经朔望星门与《格物识微》五卷知识并置对读。</p>
      <ol className="guide-layers" reversed>
        <li><b>L4</b> 机制</li><li><b>L3</b> 母题</li><li><b>L2</b> 文本</li><li><b>L1</b> 个案</li>
      </ol>
    </header>
    <section aria-labelledby="guide-syzygy-title">
      <div className="guide-section-heading"><h3 id="guide-syzygy-title">心物双界 · 朔望叠影</h3><span>SYZYGY × OMNIA</span></div>
      {SYZYGY_HIGHLIGHTS.map((item) => (
        <a key={item.story} className="guide-entry guide-entry-link" href={portalHref('omnia', item.story, item.entry)}>
          <span><strong>{item.title}</strong><small>{item.desc}</small></span>
          <span aria-hidden="true">◐</span>
        </a>
      ))}
      <button className="guide-entry" type="button" onClick={onOpenOmnia}>
        <span><strong>进入 OMNIA · 万象星枢</strong><small>《格物识微》五卷 · 二十门 · 2,266 条实用科学知识</small></span>
        <span aria-hidden="true">✦</span>
      </button>
    </section>
    <section aria-labelledby="guide-regions-title">
      <div className="guide-section-heading"><h3 id="guide-regions-title">按地域探索</h3><span>{graph.nodes.length.toLocaleString()} 条资料</span></div>
      <div className="guide-categories">{REGIONS.map((item) => <button type="button" key={item.id}
        onClick={() => onBrowse(item.id, 'all')}><span><strong>{item.label}</strong><small>{item.description}</small></span>
        <b>{(counts.region.get(item.id) ?? 0).toLocaleString()}</b></button>)}</div>
    </section>
    <section aria-labelledby="guide-content-title">
      <div className="guide-section-heading"><h3 id="guide-content-title">按内容探索</h3><span>类型目录</span></div>
      <div className="guide-categories">{CONTENT_GROUPS.map((item) => <button type="button" key={item.id}
        onClick={() => onBrowse('all', item.id)}><span><strong>{item.label}</strong><small>{item.description}</small></span>
        <b>{(counts.content.get(item.id) ?? 0).toLocaleString()}</b></button>)}</div>
    </section>
    {trails.length > 0 && <section aria-labelledby="story-trails-title">
      <h3 id="story-trails-title">故事脉络</h3>
      {trails.map(({ id, places }) => <button className="guide-entry" type="button" key={id} onClick={() => onRead(id)}>
        <span><strong>{graph.byId.get(id)?.title}</strong><small>{places}</small></span>
        <span aria-hidden="true">↗</span>
      </button>)}
    </section>}
    <section>
      <h3>从一份卷宗开始</h3>
      {CASES.flatMap((id) => {
        const node = graph.byId.get(id);
        return node ? [<button className="guide-entry" type="button" key={id} onClick={() => onRead(id)}>
          <span><strong>{node.title}</strong><small>{mapLabel(node)} · {node.credibility_tier} 级信源</small></span>
          <span aria-hidden="true">↗</span>
        </button>] : [];
      })}
    </section>
    <section>
      <h3>并排取证</h3>
      {PAIRS.filter(({ left, right }) => graph.byId.has(left) && graph.byId.has(right)).map((pair) => (
        <button className="guide-entry" type="button" key={pair.left} onClick={() => onCompare(pair.left, pair.right)}>
          <span><strong>{pair.title}</strong><small>{pair.description}</small></span><span aria-hidden="true">↔</span>
        </button>
      ))}
    </section>
  </aside>;
}
