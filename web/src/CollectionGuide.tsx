import { mapLabel, type GraphIndex } from './graph';

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

export function CollectionGuide({ graph, onRead, onCompare }: {
  graph: GraphIndex;
  onRead: (id: string) => void;
  onCompare: (left: string, right: string) => void;
}) {
  const trails = STORY_TRAILS.filter(({ id }) => graph.byId.has(id));
  return <aside id="node-inspector" className="collection-guide" aria-labelledby="collection-guide-title">
    <header>
      <h2 id="collection-guide-title">馆藏导览</h2>
      <p>从实景个案进入文本、母题和机制。神话、定型传说、个人经历及 F 级数字虚构分别标记。</p>
      <ol className="guide-layers" reversed>
        <li><b>L4</b> 机制</li><li><b>L3</b> 母题</li><li><b>L2</b> 文本</li><li><b>L1</b> 个案</li>
      </ol>
    </header>
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
