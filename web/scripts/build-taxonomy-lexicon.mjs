import { createHash } from 'node:crypto';
import { lstat, mkdir, readFile, readdir, unlink, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = fileURLToPath(new URL('../../', import.meta.url));
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');

function parseArgs(argv) {
  const options = {
    taxonomyPath: resolve(repoRoot, 'reference/thematic_taxonomy.json'),
    lexiconDir: resolve(repoRoot, 'reference/lexicon'),
    graphPath: resolve(repoRoot, 'web/public/data/graph_data.json'),
    outDir: resolve(repoRoot, 'web/public/syzygy'),
    dryRun: false,
    allowMissing: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--input' || arg === '--taxonomy') {
      options.taxonomyPath = resolve(argv[++i]);
    } else if (arg === '--lexicon-dir') {
      options.lexiconDir = resolve(argv[++i]);
    } else if (arg === '--graph') {
      options.graphPath = resolve(argv[++i]);
    } else if (arg === '--out-dir' || arg === '--out') {
      options.outDir = resolve(argv[++i]);
    } else if (arg === '--dry-run') {
      options.dryRun = true;
    } else if (arg === '--allow-missing') {
      options.allowMissing = true;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return options;
}

async function saveIfChanged(path, bytes) {
  let previous;
  try {
    previous = await readFile(path);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  if (!previous || !previous.equals(bytes)) {
    await writeFile(path, bytes);
  }
}

const STANDARD_DOMAIN_ORDER = [
  'wugu_talisman',
  'underworld_bureaucracy',
  'ghost_rituals_nuo',
  'ethnic_spirit_lexicon',
  'classical_zhiguai_opera',
  'world_mythology',
  'modern_liminal',
];

export function normalizeLexiconTerm(term) {
  const raw = String(term ?? '').normalize('NFKC').trim().toLocaleLowerCase();
  const stripped = raw.replace(/[\s\p{P}\p{S}]+/gu, '');
  return stripped || raw;
}

function clampGist(text, maxChars = 36) {
  const cleaned = String(text ?? '')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[，、：；,;:\s]+$/, '');
  if (!cleaned) return '';
  if (cleaned.length <= maxChars) return cleaned;
  const chars = Array.from(cleaned);
  if (chars.length <= maxChars) return cleaned;
  let sliced = chars.slice(0, maxChars - 1).join('');
  while (sliced.length > maxChars - 1) {
    sliced = Array.from(sliced).slice(0, -1).join('');
  }
  return `${sliced.replace(/[，、：；,;:\s]+$/, '')}…`;
}

export function autoGist(summary, maxChars = 36) {
  const flat = String(summary ?? '')
    .replace(/\r?\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!flat) return '';
  const sentences = flat.split(/(?<=[。！？!?；;])/).map((part) => part.trim()).filter(Boolean);
  const first = (sentences[0] ?? flat).replace(/[。！？!?；;，、：:]+$/, '').trim() || flat;
  if (first.length <= maxChars) return first;

  const clauses = first.split(/[，、：；,;]+/).map((part) => part.trim()).filter(Boolean);
  if (clauses.length > 1) {
    let acc = '';
    for (const clause of clauses) {
      const candidate = acc ? `${acc}，${clause}` : clause;
      if (candidate.length <= maxChars) {
        acc = candidate;
      } else {
        break;
      }
    }
    if (acc && acc.length >= 12) return acc;
  }
  return clampGist(first, maxChars);
}

const DOMAIN_DEFAULT_READING_TAGS = {
  wugu_talisman: '巫蛊与镇护',
  underworld_bureaucracy: '冥界制度',
  ghost_rituals_nuo: '傩仪丧俗',
  ethnic_spirit_lexicon: '精怪博物',
  classical_zhiguai_opera: '志怪戏曲',
  world_mythology: '比较神话',
  modern_liminal: '当代异闻',
};

export function deriveReadingTag(entry, domainId) {
  if (typeof entry?.reading_tag === 'string' && entry.reading_tag.trim()) {
    return entry.reading_tag.trim();
  }
  // An inferred topic must not claim that a source is an oral account,
  // archival record, or material object without evidence in the entry.
  return DOMAIN_DEFAULT_READING_TAGS[domainId] ?? '专题阅读';
}

function validateLexiconEntry(entry, fileDomainId, seenIds, validDomainIds, seenTermsByDomain, filename = '<unknown>') {
  if (!entry || typeof entry !== 'object') {
    throw new Error('Lexicon entry must be an object.');
  }
  for (const key of ['id', 'hub_id', 'term', 'summary', 'primary_sources']) {
    if (!(key in entry)) {
      throw new Error(`Lexicon entry ${entry.id ?? '<unknown>'} is missing required key "${key}".`);
    }
  }
  if (typeof entry.id !== 'string' || !entry.id.trim()) {
    throw new Error('Lexicon entry "id" must be a non-empty string.');
  }
  if (seenIds.has(entry.id)) {
    throw new Error(`Duplicate lexicon entry id: ${entry.id}`);
  }
  seenIds.add(entry.id);

  if (typeof entry.hub_id !== 'string' || !entry.hub_id.trim()) {
    throw new Error(`Lexicon entry ${entry.id} has invalid "hub_id".`);
  }
  if (typeof entry.term !== 'string' || !entry.term.trim()) {
    throw new Error(`Lexicon entry ${entry.id} has invalid "term".`);
  }
  if (typeof entry.summary !== 'string' || !entry.summary.trim()) {
    throw new Error(`Lexicon entry ${entry.id} has invalid "summary".`);
  }
  for (const key of ['case_id', 'knowledge_id', 'knowledge_note']) {
    if (entry[key] != null && (typeof entry[key] !== 'string' || !entry[key].trim())) {
      throw new Error(`Lexicon entry ${entry.id} has invalid "${key}".`);
    }
  }
  if (!Array.isArray(entry.primary_sources) || entry.primary_sources.length === 0) {
    throw new Error(`Lexicon entry ${entry.id} must have a non-empty "primary_sources" array.`);
  }
  let hasHttps = false;
  let hasLocatedPrintSource = false;
  for (const src of entry.primary_sources) {
    if (!src || typeof src !== 'object' || typeof src.citation !== 'string' || !src.citation.trim()) {
      throw new Error(`Lexicon entry ${entry.id} has invalid primary_sources item.`);
    }
    const url = typeof src.url === 'string' ? src.url.trim() : '';
    const locator = typeof src.locator === 'string' ? src.locator.trim() : '';
    if (url && !/^https?:\/\//i.test(url)) {
      throw new Error(`Lexicon entry ${entry.id} has invalid source URL.`);
    }
    if (!url && !locator) {
      throw new Error(`Lexicon entry ${entry.id} needs a page or chapter for an offline source.`);
    }
    if (/^https:\/\//i.test(url)) hasHttps = true;
    if (!url && locator) hasLocatedPrintSource = true;
  }
  if (!hasHttps && !hasLocatedPrintSource) {
    throw new Error(`Lexicon entry ${entry.id} needs an HTTPS source or a located print source.`);
  }

  const domainId = entry.domain_id ?? fileDomainId;
  if (typeof domainId !== 'string' || !validDomainIds.has(domainId)) {
    throw new Error(`Lexicon entry ${entry.id} references unknown domain_id "${domainId}".`);
  }

  const trimmedTerm = entry.term.trim();
  const normTerm = normalizeLexiconTerm(trimmedTerm);
  if (!seenTermsByDomain.has(domainId)) {
    seenTermsByDomain.set(domainId, new Map());
  }
  const domainTerms = seenTermsByDomain.get(domainId);
  if (domainTerms.has(normTerm)) {
    const prev = domainTerms.get(normTerm);
    throw new Error(
      `Duplicate normalized term in domain "${domainId}": "${trimmedTerm}" (${entry.id} in ${filename}) `
      + `collides with "${prev.term}" (${prev.id} in ${prev.file}).`,
    );
  }
  domainTerms.set(normTerm, { id: entry.id.trim(), term: trimmedTerm, file: filename });

  const trimmedSummary = entry.summary.trim();
  const rawGist = typeof entry.gist === 'string' ? entry.gist.trim() : '';
  const gist = rawGist ? clampGist(rawGist, 36) : autoGist(trimmedSummary, 36);
  if (!gist) {
    throw new Error(`Lexicon entry ${entry.id} failed to produce a non-empty gist.`);
  }
  const readingTag = deriveReadingTag(entry, domainId);
  if (!readingTag) {
    throw new Error(`Lexicon entry ${entry.id} failed to produce a non-empty reading_tag.`);
  }

  return {
    id: entry.id.trim(),
    hub_id: entry.hub_id.trim(),
    term: trimmedTerm,
    aliases: Array.isArray(entry.aliases) ? entry.aliases.map((a) => String(a)) : [],
    category: typeof entry.category === 'string' ? entry.category.trim() : '',
    region: typeof entry.region === 'string' ? entry.region.trim() : '',
    era: typeof entry.era === 'string' ? entry.era.trim() : '',
    gist,
    reading_tag: readingTag,
    summary: trimmedSummary,
    ...(entry.reviewed_by_human === false ? { reviewed_by_human: false } : {}),
    primary_sources: entry.primary_sources.map((src) => ({
      citation: src.citation.trim(),
      url: typeof src.url === 'string' && src.url.trim() ? src.url.trim() : null,
      ...(typeof src.locator === 'string' && src.locator.trim() ? { locator: src.locator.trim() } : {}),
    })),
    ...(entry.secondary_ref != null ? { secondary_ref: String(entry.secondary_ref) } : {}),
    ...(entry.case_id != null ? { case_id: String(entry.case_id).trim() } : {}),
    ...(entry.knowledge_id != null ? { knowledge_id: String(entry.knowledge_id).trim() } : {}),
    ...(entry.knowledge_note != null ? { knowledge_note: String(entry.knowledge_note).trim() } : {}),
  };
}

function normalizeEditorialPreface(preface) {
  if (preface == null) return null;
  if (typeof preface !== 'object' || Array.isArray(preface)) {
    throw new Error('Invalid taxonomy editorial_preface (expected an object).');
  }
  const title = typeof preface.title === 'string' ? preface.title.trim() : '';
  const subtitle = typeof preface.subtitle === 'string' ? preface.subtitle.trim() : '';
  const paragraphs = Array.isArray(preface.paragraphs)
    ? preface.paragraphs.map((item) => String(item ?? '').trim()).filter(Boolean)
    : [];
  const principles = Array.isArray(preface.principles)
    ? preface.principles.map((item, idx) => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) {
          throw new Error(`Invalid editorial_preface.principles[${idx}] (expected an object).`);
        }
        return {
          ...item,
          label: typeof item.label === 'string' ? item.label.trim() : '',
          text: typeof item.text === 'string' ? item.text.trim() : '',
        };
      })
    : [];
  return {
    ...preface,
    title,
    subtitle,
    paragraphs,
    principles,
  };
}

function normalizeEditorialIntro(intro, domainId) {
  if (intro == null) return null;
  if (typeof intro !== 'object' || Array.isArray(intro)) {
    throw new Error(`Invalid editorial_intro on domain ${domainId} (expected an object).`);
  }
  const heading = typeof intro.heading === 'string' ? intro.heading.trim() : '';
  const epigraphThesis = typeof intro.epigraph_thesis === 'string' ? intro.epigraph_thesis.trim() : '';
  const paragraphs = Array.isArray(intro.paragraphs)
    ? intro.paragraphs.map((item) => String(item ?? '').trim()).filter(Boolean)
    : [];
  const lenses = Array.isArray(intro.lenses)
    ? intro.lenses.map((item) => String(item ?? '').trim()).filter(Boolean)
    : [];
  return {
    ...intro,
    heading,
    epigraph_thesis: epigraphThesis,
    paragraphs,
    lenses,
  };
}

function normalizeQuickOverview(quickOverview, domainId) {
  if (quickOverview == null) return null;
  if (typeof quickOverview !== 'object' || Array.isArray(quickOverview)) {
    throw new Error(`Invalid quick_overview on domain ${domainId} (expected an object).`);
  }
  const threeBookAnchor = typeof quickOverview.three_book_anchor === 'string'
    ? quickOverview.three_book_anchor.trim()
    : '';
  const coreQuestion = typeof quickOverview.core_question === 'string'
    ? quickOverview.core_question.trim()
    : '';
  const keyTakeaways = Array.isArray(quickOverview.key_takeaways)
    ? quickOverview.key_takeaways.map((item) => String(item ?? '').trim()).filter(Boolean)
    : [];
  return {
    ...quickOverview,
    three_book_anchor: threeBookAnchor,
    core_question: coreQuestion,
    key_takeaways: keyTakeaways,
  };
}

function normalizeTaxonomyGroup(group, domainId) {
  if (!group || typeof group !== 'object') return group;
  const next = { ...group };
  if (group.chapter_intro != null) {
    if (typeof group.chapter_intro !== 'string') {
      throw new Error(`Invalid chapter_intro on ${domainId}/${group.id ?? '<unknown>'} (expected a string).`);
    }
    next.chapter_intro = group.chapter_intro.trim();
  }
  if (group.tldr != null) {
    if (typeof group.tldr !== 'string') {
      throw new Error(`Invalid tldr on ${domainId}/${group.id ?? '<unknown>'} (expected a string).`);
    }
    next.tldr = group.tldr.trim();
  }
  return next;
}

function resolveTargetDomainIds(domains) {
  const byId = new Map(domains.map((domain) => [domain.id, domain]));
  const ordered = [...domains].sort((a, b) => (a.order ?? 999) - (b.order ?? 999));
  return STANDARD_DOMAIN_ORDER.map((stdId, idx) => {
    if (byId.has(stdId)) return stdId;
    return ordered[idx]?.id ?? domains[idx]?.id ?? domains[0]?.id;
  });
}

function classifyUnwiredNode(node, slotIds) {
  const [d1, d2, d3, d4, d5, d6, d7] = slotIds;
  const id = String(node?.id ?? '').toLowerCase();
  const title = String(node?.title ?? '');
  const aliases = Array.isArray(node?.aliases) ? node.aliases.join(' ') : '';
  const genre = String(node?.genre ?? '').toLowerCase();
  const loc = String(node?.spatial?.location_name ?? '');
  const text = `${id} ${title} ${aliases} ${loc}`.toLowerCase();

  // Domain 1: Wugu / Zhenwu / Talisman / Apotropaic Seals
  if (
    id.startsWith('case_cn_tao_')
    || id.startsWith('case_cn_wugu_')
    || id === 'index_ocm_754'
    || /(wugu|zhenwu|yansheng|zhuyou|taofu|talisman|shigandang|bagua_mirror|luban|maogui|jincan|poison_panic|apotropaic|sympathetic_contagious|gu_sorcery|ushinokoku|villain_hitting|巫蛊|放蛊|蓄蛊|蛊毒|厌胜|镇物|镇煞|镇水|铁牛|风狮爷|瓦猫|符箓|祝由|桃符|门神|石敢当|八卦镜|鲁班|打小人|五毒|叫魂|收惊|喊惊|辟邪|符咒|压胜|上梁|镇河|丑时参拜|草人钉树)/.test(text)
  ) {
    return d1;
  }

  // Domain 2: Underworld / Chenghuang / Yama / Ten Courts / Spirit Contracts / Tomb Contracts
  if (
    /(underworld|chenghuang|fengdu|yama|ten_courts|diyu|panguan|mengpo|naihe|weighing_heart|spirit_contract|dreams_relatives|maidiquan|hunping|城隍|十殿|阎罗|阎王|酆都|丰都|冥府|阴司|冥司|地府|判官|崔府君|黑白无常|牛头马面|孟婆|奈何桥|生死簿|孽镜|东岳|泰山府君|买地券|冥契|纸钱|受生债|冥币|阴间|幽冥|冥界|地狱|冥婚|魂瓶|托梦|入梦)/.test(text)
  ) {
    return d2;
  }

  // Domain 3: Nuo / Funeral / Ghost Festival / Zhongyuan / Bereavement
  if (
    /(^|_)nuo(_|$)|fangxiang|zhongyuan|pudu|funeral|funerary|soul_recall|ganshi|jiangshi|bereavement|grief|liminality|rites_passage|water_lantern|ancestor_returns|living_dead|ghosts_of_war|day_dead|banshee_wake|gozan_okuribi|dongjing|eap012|大傩|傩戏|傩舞|傩仪|地戏|五猖|关索戏|方相氏|中元|盂兰|普度|普渡|放水灯|水灯|送火|招魂|复礼|丧葬|做七|头七|回煞|赶尸|僵尸|镇墓兽|镇尸|殡葬|亡灵节|守灵|战后记忆|归访|洞经|祭祖|葬礼/.test(text)
  ) {
    return d3;
  }

  // Domain 7: Modern / SCP / Backrooms / Liminal / Internet / Quarantine / Sensory Mechanism
  if (
    genre === 'creepypasta_ostension'
    || genre === 'urban_legend'
    || node?.is_fictional_quarantine === true
    || /(scp_|backrooms|liminal|poolrooms|dreamcore|weirdcore|local58|mandela|slender_man|marble_hornets|flesh_pit|house_of_leaves|uvb76|hasshakusama|kuchisake|kisaragi|sugisawa|polybius|dead_internet|dishisanceng|blanke_robot|amityville|hydesville|sauchie_poltergeist|spr_|ostension|pareidolia|apophenia|mass_psychogenic|optical_mirage|infrasound|weak_complex_field|tpj_|seismic_groundwater|co_poisoning|hypnagogic|suggestibility_bias|rspk_poltergeist|toilet_yokai|vanishing_hitchhiker|campus|empty_house|empty_buildings|night_transit|night_places|night_noises|roads_and_warnings|familiar_figures|city_rumor|urban_rumor|haunted_tour|teachers_school|school_story|school_oral|oily_man|airport_ferguson|taipei_xinhai|beiyi_fog|blake_garden|city_lore|ghostlore_solovyova|everyday_objects_2024|contemporary_exorcism|corpus_hk_|后室|泳池空间|梦核|怪核|规则怪谈|模拟恐怖|都市传说|空楼|废校|末班车|电梯|宿舍|校园|监控|地铁|隧道|高速公路|导航|蜂鸣器|阈限|示现|空想性错视|海市蜃楼|群体心因|次声|弱磁场|花子|裂口女|如月车站|杉泽村|死网|商场|工作场所|办公室|校舍|城市更新)/.test(text)
    || /^case_cn_(beijing|shanghai|shenzhen|qingdao|shenyang|changchun|chongqing|hangzhou|harbin|jinan|gaochun|guangzhou|chengdu|nanjing|wuhan|xian|tianjin|suzhou)_/.test(id)
    || ((id.startsWith('case_cn_hk_') || id.startsWith('case_cn_tw_') || id.startsWith('case_tw_'))
      && !id.startsWith('case_tw_sinica_')
      && /(19\d\d|20\d\d|校园|隧道|电梯|宿舍|地铁|废|楼|传闻|夜声|导航)/.test(text))
  ) {
    return d7;
  }

  // Domain 5: Classical Chinese Zhiguai / Zibuyu / Liaozhai / Opera / Tale Catalogues
  if (
    id.startsWith('case_cn_zibuyu_')
    || id.startsWith('corpus_cn_zibuyu_')
    || id.startsWith('case_zibuyu_')
    || id.startsWith('case_cn_dict')
    || id.startsWith('case_cn_sd_')
    || id.startsWith('corpus_cn_sd_')
    || id.startsWith('case_cn_yuhuan_')
    || id.startsWith('corpus_cn_yuhuan_')
    || id.startsWith('case_asia_liaozhai_')
    || id.startsWith('corpus_asia_liaozhai_')
    || id.startsWith('case_asia_jade_')
    || id.startsWith('corpus_asia_jade_')
    || id.startsWith('corpus_chinese_')
    || id.startsWith('corpus_asia_korean_tales_')
    || id.startsWith('corpus_asian_')
    || id.startsWith('corpus_east_asia_')
    || id.startsWith('text_atlas_')
    || /(zhiguai|zibuyu|liaozhai|soushen|yijian|yuewei|opera|gezaixi|judicial|bascom|mulian|dou_e|wupenji|mudanting|lintoujie|子不语|聊斋|搜神记|夷坚志|阅微|志怪|传奇|笔记|鬼戏|戏曲|宝卷|说部|公案|包公|窦娥|乌盆|牡丹亭|林投姐|白蛇传|梁祝|孟姜女|董永|方志|民间故事|传说故事)/.test(text)
  ) {
    return d5;
  }

  // Domain 4: Ethnic / Shanhai / Fox / Spirit / Yokai / Asian Oral Folklore
  if (
    id.startsWith('case_cn_japhug_')
    || id.startsWith('case_cn_yongning_')
    || id.startsWith('case_cn_pumi_')
    || id.startsWith('case_cn_minyag_')
    || id.startsWith('case_cn_bl_')
    || id.startsWith('corpus_cn_bl_')
    || id.startsWith('case_tw_sinica_')
    || id.startsWith('corpus_tw_sinica_')
    || id.startsWith('case_nichibun_')
    || id.startsWith('corpus_nichibun_')
    || id.startsWith('case_kr_aks_')
    || id.startsWith('corpus_kr_aks_')
    || id.startsWith('corpus_lao_dllm_')
    || id.startsWith('case_sea_')
    || id.startsWith('corpus_sea_')
    || id.startsWith('case_thai_')
    || id.startsWith('corpus_thai_')
    || id.startsWith('corpus_th_')
    || id.startsWith('case_th_')
    || id.startsWith('case_kh_')
    || id.startsWith('corpus_kh_')
    || id.startsWith('case_ph_')
    || id.startsWith('corpus_ph_')
    || id.startsWith('case_vietnam_')
    || id.startsWith('corpus_vietnam_')
    || id.startsWith('case_vn_')
    || id.startsWith('corpus_vn_')
    || id.startsWith('case_mm_')
    || id.startsWith('corpus_mm_')
    || id.startsWith('case_id_')
    || id.startsWith('corpus_id_')
    || id.startsWith('case_my_')
    || id.startsWith('corpus_my_')
    || id.startsWith('case_la_')
    || id.startsWith('corpus_la_')
    || id.startsWith('corpus_seasia_')
    || id.startsWith('corpus_cambodia_')
    || id.startsWith('corpus_malay_')
    || id.startsWith('case_a37b_')
    || id.startsWith('corpus_cn_ich_')
    || /(shanhai|山海|九尾狐|狐仙|白泽|山魈|精怪|妖怪|河童|天狗|山姥|魔神仔|番婆鬼|付丧神|水鬼|水猴|树灵|物怪|花妖|龙王|龙女|创世古歌|格萨尔|阿诗玛|布洛陀|东巴|毕摩|署神|非遗|yokai|kappa|tengu|pontianak)/.test(text)
  ) {
    return d4;
  }

  // Remaining Chinese / Taiwan / Singapore regional tales -> Domain 5
  if (/^(case|corpus|text)_(cn|tw|sg|asia)_/.test(id) && !/(sleep_paralysis|witch|pangu|gonggong)/.test(text)) {
    return d5;
  }

  // Remaining Japanese folkloric -> Domain 4; myth -> Domain 6
  if (/^(case|corpus|text)_jp_/.test(id)) {
    return genre === 'myth' || /(izanagi|kojiki|yomi)/.test(text) ? d6 : d4;
  }

  // Domain 6: Global myth / Berezkin / Thompson / Bible / Greek / Norse / Global witch hunts
  return d6;
}

function scoreRepresentativeNode(node) {
  let pts = 0;
  if (node.z_layer === 2) pts += 40;
  else if (node.z_layer === 4) pts += 36;
  else if (node.z_layer === 3) pts += 32;
  else if (node.z_layer === 1) pts += 28;
  if (/[\u4e00-\u9fff]/.test(node.title ?? '')) pts += 25;
  if (!/^(scot_[ac]_|index_berezkin_|corpus_berezkin_region_|case_tw_sinica_|case_cn_japhug_|case_sea_|corpus_lao_|case_kr_aks_)/.test(node.id ?? '')) {
    pts += 32;
  }
  if (node.genre && node.genre !== 'unclassified') pts += 15;
  if (node.reading?.paragraphs?.length) pts += 10;
  return pts;
}

export function classifyCorpusNodes(graph, domains) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const validDomains = Array.isArray(domains) ? domains : [];
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const slotIds = resolveTargetDomainIds(validDomains);

  const domainClassified = new Map(validDomains.map((domain) => [domain.id, new Set()]));
  const domainExplicit = new Map(validDomains.map((domain) => [domain.id, new Set()]));
  const explicitlyWiredAny = new Set();

  for (const domain of validDomains) {
    const clsSet = domainClassified.get(domain.id);
    const expSet = domainExplicit.get(domain.id);
    for (const group of domain.groups ?? []) {
      for (const id of [...(group.hub_ids ?? []), ...(group.featured_nodes ?? [])]) {
        if (nodeById.has(id)) {
          clsSet.add(id);
          expSet.add(id);
          explicitlyWiredAny.add(id);
        }
      }
    }
  }

  for (const node of nodes) {
    if (!node?.id || explicitlyWiredAny.has(node.id)) continue;
    const targetDomainId = classifyUnwiredNode(node, slotIds);
    domainClassified.get(targetDomainId)?.add(node.id);
  }

  const allClassifiedUnique = new Set();
  const byDomain = new Map();

  for (const domain of validDomains) {
    const clsSet = domainClassified.get(domain.id);
    const expSet = domainExplicit.get(domain.id);
    for (const id of clsSet) allClassifiedUnique.add(id);

    const nonFeatured = [];
    for (const id of clsSet) {
      if (!expSet.has(id)) {
        const node = nodeById.get(id);
        if (node) nonFeatured.push(node);
      }
    }
    nonFeatured.sort((a, b) => scoreRepresentativeNode(b) - scoreRepresentativeNode(a) || a.id.localeCompare(b.id, 'en'));

    const sampleClassifiedNodes = nonFeatured.slice(0, 16).map((node) => ({
      id: node.id,
      title: node.title || node.id,
      z_layer: node.z_layer ?? 1,
      genre: node.genre ?? 'unclassified',
    }));

    byDomain.set(domain.id, {
      classifiedNodeCount: clsSet.size,
      classifiedNodeIds: [...clsSet],
      sampleClassifiedNodes,
    });
  }

  return {
    byDomain,
    coverage: {
      total_graph_nodes: nodes.length,
      total_classified_unique: allClassifiedUnique.size,
    },
  };
}

export async function buildTaxonomyLexicon(options) {
  let taxonomyBytes;
  try {
    taxonomyBytes = await readFile(options.taxonomyPath);
  } catch (error) {
    if (options.allowMissing && error.code === 'ENOENT') {
      console.log(`Taxonomy source missing (${options.taxonomyPath}); skipped due to --allow-missing.`);
      return null;
    }
    throw error;
  }

  const taxonomy = JSON.parse(taxonomyBytes.toString('utf8'));
  if (!taxonomy || typeof taxonomy !== 'object' || !Array.isArray(taxonomy.domains) || taxonomy.domains.length !== 7) {
    throw new Error(`Invalid thematic taxonomy (expected 7 domains): ${options.taxonomyPath}`);
  }

  const domainMap = new Map();
  for (const [idx, domain] of taxonomy.domains.entries()) {
    if (!domain || typeof domain.id !== 'string' || !domain.id.trim() || !domain.name) {
      throw new Error(`Invalid domain at index ${idx}`);
    }
    if (domainMap.has(domain.id)) {
      throw new Error(`Duplicate taxonomy domain id: ${domain.id}`);
    }
    domainMap.set(domain.id, domain);
  }

  const graph = JSON.parse(await readFile(options.graphPath, 'utf8'));
  if (graph.schema_version !== 1 || !Array.isArray(graph.nodes)) {
    throw new Error(`Invalid graph snapshot: ${options.graphPath}`);
  }
  const graphNodeIds = new Set(graph.nodes.map((node) => node.id));
  const graphById = new Map(graph.nodes.map((node) => [node.id, node]));
  let bookById = null;

  let lexiconFiles = [];
  try {
    const entries = await readdir(options.lexiconDir, { withFileTypes: true });
    lexiconFiles = entries
      .filter((item) => item.isFile() && item.name.endsWith('.json'))
      .map((item) => item.name)
      .sort((a, b) => a.localeCompare(b, 'en'));
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }

  const entriesByDomain = new Map([...domainMap.keys()].map((id) => [id, []]));
  const seenIds = new Set();
  const seenTermsByDomain = new Map();

  for (const filename of lexiconFiles) {
    const filePath = join(options.lexiconDir, filename);
    const payload = JSON.parse(await readFile(filePath, 'utf8'));
    if (!payload || typeof payload !== 'object' || !Array.isArray(payload.entries)) {
      throw new Error(`Invalid lexicon shard source: ${filePath}`);
    }
    const fileDomainId = payload.domain_id;
    for (const rawEntry of payload.entries) {
      const normalized = validateLexiconEntry(
        rawEntry,
        fileDomainId,
        seenIds,
        new Set(domainMap.keys()),
        seenTermsByDomain,
        filename,
      );
      if (normalized.case_id) {
        const story = graphById.get(normalized.case_id);
        if (!story || story.z_layer !== 1 || !Number.isFinite(story.spatial?.lat) || !Number.isFinite(story.spatial?.lng)) {
          throw new Error(`Lexicon entry ${normalized.id} has an invalid geographic story reference.`);
        }
      }
      if (normalized.knowledge_id) {
        if (!bookById) {
          const bookPath = options.bookPath ?? resolve(repoRoot, 'web/public/knowledge/data.json');
          const book = JSON.parse(await readFile(bookPath, 'utf8'));
          bookById = new Map((book.entries ?? []).map((item) => [item.id, item]));
        }
        if (!bookById.get(normalized.knowledge_id)?.body?.trim() || !normalized.knowledge_note) {
          throw new Error(`Lexicon entry ${normalized.id} has an invalid thematic knowledge reference.`);
        }
      } else if (normalized.knowledge_note) {
        throw new Error(`Lexicon entry ${normalized.id} has a thematic note without a knowledge reference.`);
      }
      const domainId = rawEntry.domain_id ?? fileDomainId;
      entriesByDomain.get(domainId).push(normalized);
    }
  }

  const shardPayloads = new Map();
  const manifestDomains = {};
  const manifestHubToDomain = {};
  const taxonomyHubToDomain = {};

  for (const domain of taxonomy.domains) {
    const domainEntries = entriesByDomain.get(domain.id) ?? [];
    if (domainEntries.length === 0) continue;

    const shardObj = {
      version: 1,
      domain_id: domain.id,
      title: domain.name,
      entries: domainEntries,
    };
    const shardBytes = Buffer.from(JSON.stringify(shardObj) + '\n', 'utf8');
    const sha256 = digest(shardBytes);
    const sha12 = sha256.slice(0, 12);
    const fileName = `${domain.id}-${sha12}.json`;
    const relativeFile = `lexicon/${fileName}`;

    const categories = [];
    const seenCategories = new Set();
    const hubIds = [];
    const hubCounts = new Map();
    for (const entry of domainEntries) {
      if (entry.category && !seenCategories.has(entry.category)) {
        seenCategories.add(entry.category);
        categories.push(entry.category);
      }
      if (!hubCounts.has(entry.hub_id)) hubIds.push(entry.hub_id);
      hubCounts.set(entry.hub_id, (hubCounts.get(entry.hub_id) ?? 0) + 1);
    }

    const shardRef = {
      file: relativeFile,
      sha256,
      count: domainEntries.length,
      categories,
      hub_ids: hubIds,
    };
    shardPayloads.set(fileName, { domainId: domain.id, bytes: shardBytes, meta: shardRef });
    manifestDomains[domain.id] = {
      file: relativeFile,
      sha256,
      count: domainEntries.length,
      bytes: shardBytes.length,
      categories,
      hub_ids: hubIds,
    };

    for (const [hubId, count] of hubCounts.entries()) {
      manifestHubToDomain[hubId] = {
        domain_id: domain.id,
        domain_name: domain.name,
        count,
      };
      taxonomyHubToDomain[hubId] = {
        domain_id: domain.id,
        domain_name: domain.name,
        count,
        shard: shardRef,
      };
    }
  }

  const manifestObj = {
    version: 1,
    domains: manifestDomains,
    hub_to_domain: manifestHubToDomain,
  };
  const manifestBytes = Buffer.from(JSON.stringify(manifestObj) + '\n', 'utf8');
  const manifestSha256 = digest(manifestBytes);

  const corpusClassification = classifyCorpusNodes(graph, taxonomy.domains);

  const enrichedDomains = taxonomy.domains.map((domain, index) => {
    const groups = (Array.isArray(domain.groups) ? domain.groups : []).map((group) =>
      normalizeTaxonomyGroup(group, domain.id),
    );
    const resolvedNodes = new Set();
    for (const group of groups) {
      for (const id of [...(group.hub_ids ?? []), ...(group.featured_nodes ?? [])]) {
        if (graphNodeIds.has(id)) resolvedNodes.add(id);
      }
    }
    const manifestEntry = manifestDomains[domain.id];
    const lexiconShard = manifestEntry
      ? {
          file: manifestEntry.file,
          sha256: manifestEntry.sha256,
          count: manifestEntry.count,
          categories: manifestEntry.categories,
          hub_ids: manifestEntry.hub_ids,
        }
      : null;
    const editorialIntro = normalizeEditorialIntro(domain.editorial_intro, domain.id);
    const quickOverview = normalizeQuickOverview(domain.quick_overview, domain.id);
    const domainClassification = corpusClassification.byDomain.get(domain.id);

    return {
      ...domain,
      order: domain.order ?? index + 1,
      ...(editorialIntro ? { editorial_intro: editorialIntro } : {}),
      ...(quickOverview ? { quick_overview: quickOverview } : {}),
      node_count: resolvedNodes.size,
      classified_node_count: domainClassification
        ? domainClassification.classifiedNodeCount
        : resolvedNodes.size,
      sample_classified_nodes: domainClassification
        ? domainClassification.sampleClassifiedNodes
        : [],
      lexicon_count: manifestEntry ? manifestEntry.count : 0,
      lexicon_shard: lexiconShard,
      groups,
    };
  });

  const editorialPreface = normalizeEditorialPreface(taxonomy.editorial_preface);
  const taxonomyOut = {
    version: taxonomy.version ?? 1,
    snapshot_id: graph.snapshot_id,
    lexicon_manifest_sha256: manifestSha256,
    corpus_classification_coverage: corpusClassification.coverage,
    ...(taxonomy.bibliography ? { bibliography: taxonomy.bibliography } : {}),
    ...(editorialPreface ? { editorial_preface: editorialPreface } : {}),
    domains: enrichedDomains,
    hub_to_domain: taxonomyHubToDomain,
  };
  const taxonomyBytesOut = Buffer.from(JSON.stringify(taxonomyOut) + '\n', 'utf8');

  if (!options.dryRun) {
    const lexiconOutDir = join(options.outDir, 'lexicon');
    await mkdir(lexiconOutDir, { recursive: true });
    if ((await lstat(lexiconOutDir)).isSymbolicLink()) {
      throw new Error(`Lexicon output directory must not be a symbolic link: ${lexiconOutDir}`);
    }

    const activeFileNames = new Set([...shardPayloads.keys(), 'manifest.json']);
    const domainPrefixes = taxonomy.domains.map((domain) => `${domain.id}-`);
    for (const name of await readdir(lexiconOutDir)) {
      const isShardLike = domainPrefixes.some((prefix) => name.startsWith(prefix)) && name.endsWith('.json');
      if (isShardLike && !activeFileNames.has(name)) {
        const stalePath = join(lexiconOutDir, name);
        if (!(await lstat(stalePath)).isFile()) {
          throw new Error(`Unexpected lexicon path: ${stalePath}`);
        }
        await unlink(stalePath);
      }
    }

    for (const [fileName, item] of shardPayloads.entries()) {
      await saveIfChanged(join(lexiconOutDir, fileName), item.bytes);
    }
    await saveIfChanged(join(lexiconOutDir, 'manifest.json'), manifestBytes);
    await saveIfChanged(join(options.outDir, 'taxonomy.json'), taxonomyBytesOut);
  }

  const totalEntries = seenIds.size;
  const activeShards = Object.keys(manifestDomains).length;
  console.log(
    `${options.dryRun ? '[dry-run] ' : ''}Taxonomy lexicon: ${enrichedDomains.length} domains, `
    + `${activeShards} active shard(s), ${totalEntries} entries, ${Object.keys(taxonomyHubToDomain).length} mapped hubs.`,
  );

  return {
    taxonomy: taxonomyOut,
    manifest: manifestObj,
    manifestSha256,
    totalEntries,
    activeShards,
  };
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  await buildTaxonomyLexicon(parseArgs(process.argv.slice(2)));
}
