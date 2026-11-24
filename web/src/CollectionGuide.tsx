import { useMemo } from 'react';
import { mapLabel, type GraphIndex } from './graph';
import { CONTENT_GROUPS, nodeContentGroup, nodeRegion, REGIONS, type ContentGroup, type Region } from './catalogueBrowse';

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

export function CollectionGuide({ graph, onRead, onCompare, onBrowse }: {
  graph: GraphIndex;
  onRead: (id: string) => void;
  onCompare: (left: string, right: string) => void;
  onBrowse: (region: Region, content: ContentGroup) => void;
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
      <span className="guide-overline">ASTRAIA / COLLECTION GUIDE</span>
      <h2 id="collection-guide-title">馆藏导览</h2>
      <p>先按地域或内容寻找故事，打开卷宗阅读梗概和出处；从地点进入地图，再沿关联探索文本、母题与机制。</p>
      <ol className="guide-layers" reversed>
        <li><b>L4</b> 机制</li><li><b>L3</b> 母题</li><li><b>L2</b> 文本</li><li><b>L1</b> 个案</li>
      </ol>
    </header>
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
