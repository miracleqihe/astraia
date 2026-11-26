export const DEFAULT_MEMBRANE_DEPTH = 0.5;
export const BEYOND_MEMBRANE_THRESHOLD = 0.75;
export const OBS_STORAGE_KEY = 'astraia-syzygy-observer-v1';

const SYNODIC_MONTH_DAYS = 29.53058867;
const KNOWN_NEW_MOON_MS = Date.UTC(2000, 0, 6, 18, 14, 0);

export const REALMS = [
  {
    id: 'human',
    depth: 0.0,
    rank: 'Ⅰ',
    char: '人',
    label: '人 · 实存物界',
    latin: 'PHYSIS · REALM I',
    subtitle: '实证坐标、物理规律与典籍原页：可观、可触、可涉。',
    classicalQuote: '立身实测之境，格物以明其形；隔膜微澜处，可见彼岸投影。',
    canInterfere: true,
    whisper: '形器可触，物界应手而动',
    accentColor: '#d6b678',
    membraneAlpha: 0.24,
  },
  {
    id: 'threshold',
    depth: 0.5,
    rank: '◐',
    char: '膜',
    label: '界膜 · 朔望临界',
    latin: 'SYZYGY · MEMBRANE',
    subtitle: '悬停于心物交界之波动薄翳：两界相映，移动光标可隔膜窥见彼岸。',
    classicalQuote: '朔隐望显，一线相叠；此身犹在两界之间，既可回手定物，亦可穿膜而观。',
    canInterfere: true,
    whisper: '立于界膜之上，心物微澜相映',
    accentColor: '#f0d79c',
    membraneAlpha: 0.62,
  },
  {
    id: 'ghost',
    depth: 1.0,
    rank: 'Ⅱ',
    char: '鬼',
    label: '鬼 · 人死为鬼',
    latin: 'MYTHOS · REALM II',
    subtitle: '紧贴物界背面的亲历、执念与夜谈：可隔膜窥视物质地球，却不可改写一毫。',
    classicalQuote: '人死为鬼。他者不见，惟亲历者见之；唯余风声微澜，不可干涉实存。',
    canInterfere: false,
    whisper: '搏之不得，唯余微澜',
    accentColor: '#b0c6e0',
    membraneAlpha: 0.78,
  },
  {
    id: 'jian',
    depth: 2.0,
    rank: 'Ⅲ',
    char: '聻',
    label: '聻 · 鬼死为聻',
    latin: 'SIDERA · REALM III',
    subtitle: '个体名姓与具体地望消融之后，跨洲共鸣的纯母题星络。',
    classicalQuote: '鬼死为聻。形骸与街巷俱远，唯有跨文化原型仍在星络中长久游荡。',
    canInterfere: false,
    whisper: '形骸已远，物界自转',
    accentColor: '#bec2d8',
    membraneAlpha: 0.84,
  },
  {
    id: 'xi',
    depth: 3.0,
    rank: 'Ⅳ',
    char: '希',
    label: '希 · 聻死为希',
    latin: 'LOGOS · REALM IV',
    subtitle: '听之不闻名曰希：剥落恐怖叙事后显露的物理、毒理、认识论与社会秩序。',
    classicalQuote: '听之不闻名曰希。机理无声而自运，不因人的惊怖或祈愿而改变轨迹。',
    canInterfere: false,
    whisper: '律动无声，不因凝视而改',
    accentColor: '#63c7a7',
    membraneAlpha: 0.72,
  },
  {
    id: 'yi',
    depth: 4.0,
    rank: 'Ⅴ',
    char: '夷',
    label: '夷 · 希死为夷',
    latin: 'OBSERVER · REALM V',
    subtitle: '视之不见名曰夷：悬于两界之上反观自身——屏幕本身，即是最后一张膜。',
    classicalQuote: '视之不见名曰夷。两界皆在画中自转，唯一跨越界膜的载体，正是此刻凝视屏幕的你。',
    canInterfere: false,
    whisper: '你在膜外，一切如常',
    accentColor: '#efe9dc',
    membraneAlpha: 0.9,
  },
];

export function clampDepth(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return DEFAULT_MEMBRANE_DEPTH;
  return Math.max(0, Math.min(4, Math.round(numeric * 100) / 100));
}

export function realmById(id) {
  return REALMS.find((item) => item.id === id) ?? null;
}

export function realmForDepth(depth) {
  const d = clampDepth(depth);
  let best = REALMS[0];
  let bestDist = Infinity;
  for (const realm of REALMS) {
    const dist = Math.abs(d - realm.depth);
    if (dist < bestDist) {
      bestDist = dist;
      best = realm;
    }
  }
  return best;
}

export function isBeyondMembrane(depth) {
  return clampDepth(depth) >= BEYOND_MEMBRANE_THRESHOLD;
}

export function membraneIntensity(depth) {
  const d = clampDepth(depth);
  if (d <= 0.5) return 0.25 + (d / 0.5) * 0.75;
  if (d <= 2.0) return 1.0 - (d - 0.5) * 0.14;
  return 0.79 + ((d - 2.0) / 2.0) * 0.18;
}

/**
 * Compute continuous astronomical synodic lunar phase from UTC timestamp.
 * phase = 0 (New Moon / 朔) -> 0.5 (Full Moon / 望) -> 1.0 (Next New Moon / 朔).
 */
export function computeLunarSyzygy(date = new Date()) {
  const ms = date instanceof Date ? date.getTime() : Number(date);
  const daysSince = ((Number.isFinite(ms) ? ms : Date.now()) - KNOWN_NEW_MOON_MS) / 86400000;
  const rawAge = daysSince % SYNODIC_MONTH_DAYS;
  const ageDays = rawAge < 0 ? rawAge + SYNODIC_MONTH_DAYS : rawAge;
  const phase = ageDays / SYNODIC_MONTH_DAYS;
  const illumination = 0.5 * (1 - Math.cos(phase * Math.PI * 2));
  const syzygyProximity = Math.abs(Math.cos(phase * Math.PI));

  let phaseName = '朔月';
  if (ageDays < 1.2 || ageDays >= SYNODIC_MONTH_DAYS - 1.2) phaseName = '朔月';
  else if (phase < 0.22) phaseName = '蛾眉月';
  else if (phase < 0.28) phaseName = '上弦月';
  else if (phase < 0.47) phaseName = '盈凸月';
  else if (phase < 0.53) phaseName = '望月';
  else if (phase < 0.72) phaseName = '亏凸月';
  else if (phase < 0.78) phaseName = '下弦月';
  else phaseName = '残月';

  const syzygyLabel = phase < 0.06 || phase > 0.94
    ? '朔日 · 合隐之刻'
    : Math.abs(phase - 0.5) < 0.06
      ? '望日 · 满照之刻'
      : `${phaseName} · 月龄 ${ageDays.toFixed(1)} 日`;

  return {
    ageDays,
    phase,
    illumination,
    phaseName,
    syzygyLabel,
    syzygyProximity,
  };
}

function defaultTrace() {
  return {
    physisCount: 0,
    mythosCount: 0,
    bridgeCount: 0,
    crossingCount: 0,
    rippleCount: 0,
    lastDepth: DEFAULT_MEMBRANE_DEPTH,
    trail: [],
  };
}

function getStorage(storageOverride) {
  if (storageOverride !== undefined) return storageOverride;
  try {
    return typeof globalThis !== 'undefined' ? globalThis.localStorage ?? null : null;
  } catch {
    return null;
  }
}

export function loadObserverTrace(storageOverride) {
  const storage = getStorage(storageOverride);
  if (!storage) return defaultTrace();
  try {
    const raw = storage.getItem(OBS_STORAGE_KEY);
    if (!raw) return defaultTrace();
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return defaultTrace();
    return {
      physisCount: Math.max(0, Number(parsed.physisCount) || 0),
      mythosCount: Math.max(0, Number(parsed.mythosCount) || 0),
      bridgeCount: Math.max(0, Number(parsed.bridgeCount) || 0),
      crossingCount: Math.max(0, Number(parsed.crossingCount) || 0),
      rippleCount: Math.max(0, Number(parsed.rippleCount) || 0),
      lastDepth: clampDepth(parsed.lastDepth ?? DEFAULT_MEMBRANE_DEPTH),
      trail: Array.isArray(parsed.trail) ? parsed.trail.slice(0, 12) : [],
    };
  } catch {
    return defaultTrace();
  }
}

export function recordObservation(trace, event, storageOverride) {
  const next = {
    ...defaultTrace(),
    ...(trace || {}),
    trail: Array.isArray(trace?.trail) ? [...trace.trail] : [],
  };
  const kind = event?.type;
  if (kind === 'physis') next.physisCount += 1;
  else if (kind === 'mythos') next.mythosCount += 1;
  else if (kind === 'bridge') next.bridgeCount += 1;
  else if (kind === 'cross') next.crossingCount += 1;
  else if (kind === 'ripple') next.rippleCount += 1;

  if (event?.depth !== undefined) next.lastDepth = clampDepth(event.depth);
  if (event?.label) {
    const entry = {
      type: String(kind || 'observe'),
      id: event.id ? String(event.id) : '',
      label: String(event.label).slice(0, 64),
      realm: event.realm ? String(event.realm) : realmForDepth(next.lastDepth).id,
      at: Number.isFinite(event.at) ? event.at : Date.now(),
    };
    if (!next.trail.length || next.trail[0].label !== entry.label || next.trail[0].type !== entry.type) {
      next.trail.unshift(entry);
      if (next.trail.length > 12) next.trail.length = 12;
    }
  }

  const storage = getStorage(storageOverride);
  if (storage) {
    try {
      storage.setItem(OBS_STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* Ignore quota or private mode errors. */
    }
  }
  return next;
}

export function summarizeObserverBalance(trace) {
  const p = Number(trace?.physisCount) || 0;
  const m = Number(trace?.mythosCount) || 0;
  const b = Number(trace?.bridgeCount) || 0;
  const c = Number(trace?.crossingCount) || 0;
  const r = Number(trace?.rippleCount) || 0;
  const totalWeighted = p + m + b * 2;
  if (!totalWeighted && !c && !r) {
    return {
      physisRatio: 0.5,
      label: '初临界膜 · 尚待观测',
      reflection: '你正立于物界与精神界的临界线；每一次点读与穿膜，都会在星图上留下只属于你的观测折痕。',
    };
  }
  const physisRatio = totalWeighted ? (p + b) / (p + m + b * 2) : 0.5;
  if (r >= 3 && physisRatio < 0.48) {
    return {
      physisRatio,
      label: '隔膜凝视者 · 执念与边界',
      reflection: `你在彼岸尝试触及物质世界 ${r} 次，唯见膜面微澜——正应“可观而不可涉”之理。`,
    };
  }
  if (physisRatio >= 0.62) {
    return {
      physisRatio,
      label: '格物偏重 · 寻律之眼',
      reflection: '你的视线多停留在物界的机理与实证索引，不妨潜入鬼、聻两阶，看看理性之外经验如何存活。',
    };
  }
  if (physisRatio <= 0.38) {
    return {
      physisRatio,
      label: '玄象偏重 · 巡影之眼',
      reflection: '你久行于传说与幽影之间，可随时返膜入人界，以《格物识微》的物理与史学尺度再照前路。',
    };
  }
  return {
    physisRatio,
    label: '朔望平衡 · 双界穿行者',
    reflection: `已累积 ${b} 次心物对读、${c} 次穿膜渡越；你既见过经验的幽微，也丈量过机制的边界。`,
  };
}
