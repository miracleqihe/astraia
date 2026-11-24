/** A small, sourced selection of milestones; handbook links are related readings. */
export interface LifeMilestone {
  age: string;
  title: string;
  description: string;
  source: string;
  url: string;
  entries: string[];
}

export const LIFE_MILESTONES: LifeMilestone[] = [
  { age: '约 138 亿年前', title: '宇宙早期膨胀', description: '根据目前的观测，宇宙约有 138 亿年历史。早期宇宙经历膨胀、冷却和物质结构的形成。', source: 'NASA · 宇宙概览', url: 'https://science.nasa.gov/universe/overview/', entries: ['PHY-5-0003'] },
  { age: '大爆炸后约 38 万年', title: '第一束自由传播的光', description: '宇宙冷却到原子核能够俘获电子时，光得以较自由地穿行；今天我们观测到的宇宙微波背景辐射保留了这段历史的痕迹。', source: 'NASA · 宇宙概览', url: 'https://science.nasa.gov/universe/overview/', entries: ['PHY-5-0003', 'PHY-5-0006'] },
  { age: '最初数亿年', title: '恒星与星系初成', description: '在随后的数亿年间，第一批恒星形成并聚集成早期星系。它们的确切形成过程仍在研究中。', source: 'NASA · 宇宙概览', url: 'https://science.nasa.gov/universe/overview/', entries: ['PHY-5-0006'] },
  { age: '约 46 亿年前', title: '太阳系与地球形成', description: '通过陨石与地球物质的放射性定年，研究者推算太阳系和地球约形成于 46 亿年前。', source: 'NASA · 宇宙有多古老', url: 'https://science.nasa.gov/exoplanets/what-is-the-universe/', entries: ['GEO-STRUC-0003', 'CHE-1-0010'] },
  { age: '至少约 35 亿年前', title: '早期微生物的痕迹', description: '约 35 亿年前的叠层石保存了微生物活动的证据；这些遗迹提供了观察早期地球生命的窗口。', source: 'Smithsonian · 地球生命史', url: 'https://naturalhistory.si.edu/education/teaching-resources/life-science/early-life-earth-animal-origins', entries: ['GEO-STRUC-0006', 'GEO-LAND-0002'] },
  { age: '约 24 亿年前', title: '大氧化事件', description: '产氧光合作用与地球化学过程共同改变了大气和海洋，氧气逐渐积累。其过程并非在一瞬间完成。', source: 'NASA · 早期生命与大氧化事件', url: 'https://science.nasa.gov/science-research/planetary-science/astrobiology/nasa-research-shows-early-life-relied-on-rare-metal/', entries: ['BIO-2-0001', 'CHE-3-0004'] },
  { age: '约 5.41 亿年前', title: '寒武纪生命多样化', description: '寒武纪开始后，动物形态和生态关系逐渐多样化，许多硬壳和身体结构在化石记录中出现。', source: 'Smithsonian · 地球生命史', url: 'https://naturalhistory.si.edu/education/teaching-resources/life-science/early-life-earth-animal-origins', entries: ['GEO-STRUC-0006', 'HIS-4-0001'] },
  { age: '约 6600 万年前', title: '白垩纪末生物大灭绝', description: '一次大规模灭绝发生在白垩纪末；小行星撞击及随后的环境变化是重要证据。非鸟类恐龙未能延续，鸟类则存活至今。', source: '美国地质调查局 · 中生代', url: 'https://www.usgs.gov/youth-and-education-in-science/mesozoic', entries: ['GEO-STRUC-0006', 'GEO-LAND-0002'] },
  { age: '约 30 万年前', title: '智人出现', description: '目前的人类化石证据表明，智人在非洲的历史至少可以追溯到约 30 万年前。', source: 'Smithsonian · 智人', url: 'https://humanorigins.si.edu/evidence/human-fossils/species/homo-sapiens', entries: ['HIS-4-0001', 'HIS-4-0003'] },
  { age: '约 1.2 万年前以来', title: '农业与聚落', description: '在过去约 1.2 万年间，部分人群逐渐开始种植植物和饲养动物，生活方式与聚落随之改变。', source: 'Smithsonian · 人类改变世界', url: 'https://humanorigins.si.edu/human-characteristics/humans-change-world', entries: ['HIS-4-0003', 'BIO-2-0101'] },
];
