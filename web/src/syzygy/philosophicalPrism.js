import { realmForDepth } from './realms.js';

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[c]);

export const PRISM_THEMES = {
  sensory_boundary: {
    id: 'sensory_boundary',
    title: '感官即边界',
    latin: 'LIMEN SENSUS',
    phiEntryId: 'PHI-2-0005',
    secondaryEntryId: 'BIO-3-0004',
    defaultExperiment: 'afterimage',
    statement: '肉体并不是无色透明的窗户，而是有频宽限制的滤网。在听阈之下与视觉边缘，未被觉察的物理刺激常被意识翻译成“在场者”。',
    question: '当感官把真实却幽微的信号编织成幽影，错觉究竟发生在物体里，还是发生在观察者的神经回路中？',
  },
  naming_chaos: {
    id: 'naming_chaos',
    title: '命名即秩序',
    latin: 'NOMEN ET ORDO',
    phiEntryId: 'PHI-5-0001',
    secondaryEntryId: 'PHI-6-0002',
    defaultExperiment: null,
    statement: '面对洪水、地动、日月蚀变与无常天象，神话以神格命名失控之力，科学以模型近似可测之律——两者都在为混沌划出可理解的岸线。',
    question: '模型与神话皆非世界本身；当我们用方程替换龙王，究竟消除了未知，还是换了一套语言来安放敬畏？',
  },
  other_and_panic: {
    id: 'other_and_panic',
    title: '他者与恐慌',
    latin: 'METUS ALTERIUS',
    phiEntryId: 'PHI-2-0006',
    secondaryEntryId: 'SOC-5-0002',
    defaultExperiment: null,
    statement: '叫魂、猎巫与夜间传言很少只关乎超自然本身；它们往往是一座社群在焦虑时刻，把无名恐惧投射到“异类面孔”上的集体显影。',
    question: '当“人人皆言有之”成为唯一证据时，是谁失去了在证言体系中被当作可信人的资格？',
  },
  memory_sediment: {
    id: 'memory_sediment',
    title: '场所与记忆沉积',
    latin: 'LOCUS MEMORIAE',
    phiEntryId: 'PHI-2-0004',
    secondaryEntryId: 'HIS-6-0007',
    defaultExperiment: null,
    statement: '空楼、旧隧道、灾后街区之所以长出“魂魄”，是因为物质空间不仅承载砖瓦坐标，也沉积着未能完成哀悼的历史记忆。',
    question: '当建筑本身已无物理异常，为什么人走过那扇门时，仍会听见历史留下的回声？',
  },
  fiction_ostension: {
    id: 'fiction_ostension',
    title: '虚构反噬现实（展演）',
    latin: 'OSTENSIO LIMINALIS',
    phiEntryId: 'LIT-2-0004',
    secondaryEntryId: 'PHI-2-0003',
    defaultExperiment: 'pareidolia',
    statement: '神鬼无法推开现实里的一扇门，但人类可以因为相信一个虚构文本而真正走入夜色。故事通过读者的模仿与重述，反向穿过了界膜。',
    question: '如果连明确标为 F 级的数字造物都能引发现实寻访，虚构与现实之间的界碑究竟立在哪里？',
  },
  model_and_abyss: {
    id: 'model_and_abyss',
    title: '模型与深渊（知识边界）',
    latin: 'FINES COGNITIONIS',
    phiEntryId: 'PHI-2-0008',
    secondaryEntryId: 'PHI-6-0007',
    defaultExperiment: null,
    statement: '格物丈量机理的边界，志怪记录经验的形状；揭开毒理或声学触发条件后，机制解释了“为何发生”，却往往不能替亲历者抚平“曾那样看见过”的重量。',
    question: '在已证实、待核实与不可知之间保持诚实的沉默，是否比强行给出一个万能答案更接近清醒？',
  },
  ghosts_in_machine: {
    id: 'ghosts_in_machine',
    title: '技术盲区与媒介幽灵',
    latin: 'SPECTRUM IN MACHINA',
    phiEntryId: 'PHI-5-0008',
    secondaryEntryId: 'FOR-6-0015',
    defaultExperiment: 'pareidolia',
    statement: '从铜镜、留声机、监控视野缺口到当代算法与压缩噪点，每一代新媒介的成像盲区，都会立刻生长出属于那个时代的鬼魂。',
    question: '此刻在你面前的屏幕像素与光学成像之外，有多少“理所当然的缺失”正被大脑自动补全？',
  },
  life_death_scale: {
    id: 'life_death_scale',
    title: '生死刻度：人、鬼、聻、希、夷',
    latin: 'SCALA EXISTENTIAE',
    phiEntryId: 'PHI-6-0002',
    secondaryEntryId: 'PHI-6-0006',
    defaultExperiment: 'afterimage',
    statement: '人死为鬼，鬼死为聻，聻死为希，希死为夷：古人以逐层抽离之名，推演意识如何从具体肉身退入纯然无声无形的高维观测态。',
    question: '当形骸、姓名与恐惧层层剥落到只剩纯粹凝视时，观者与所观之界，究竟还隔着什么？',
  },
};

export function resolvePrismForPair({ node, entry, bridge, depth = 0.5 } = {}) {
  const title = `${node?.title ?? ''} ${bridge?.shortLabel ?? ''} ${entry?.title ?? ''}`;
  const nodeId = String(node?.id ?? '');
  const entryId = String(entry?.id ?? '');
  const trail = bridge?.trail ?? '';
  const cluster = bridge?.sideraCluster ?? '';
  const relation = bridge?.relation ?? '';
  const genre = String(node?.genre ?? '');
  const isFiction = node?.credibility_tier === 'F' || !!node?.is_fictional_quarantine || genre === 'creepypasta_ostension';

  let theme = PRISM_THEMES.model_and_abyss;
  if (nodeId.includes('zibuyu_v03_s023') || title.includes('聻') || entryId === 'PHI-6-0002' || entryId.startsWith('FOR-3') || entryId === 'REL-5-0003') {
    theme = PRISM_THEMES.life_death_scale;
  } else if (isFiction || relation === 'LIMINAL_SPAWNS' || /后室|如月|瘦长|规则|网络|虚构/.test(title)) {
    theme = PRISM_THEMES.fiction_ostension;
  } else if (trail === 'trail1' || trail === 'trail3' || entryId === 'HEA-009' || entryId === 'BIO-3-0004' || /次声|压床|在场|声|响|振动|睡眠|夜视/.test(title)) {
    theme = PRISM_THEMES.sensory_boundary;
  } else if (/监控|照片|影像|录像|镜头|招牌|信号|机器/.test(title) || entryId === 'FOR-6-0015' || entryId === 'FOR-2-0008') {
    theme = PRISM_THEMES.ghosts_in_machine;
  } else if (trail === 'trail4' || cluster === 'sid_witch' || /叫魂|猎巫|谣言|恐慌|油鬼|阿斯旺|传闻/.test(title) || entryId.startsWith('SOC-5-001') || entryId === 'SOC-1-0009') {
    theme = PRISM_THEMES.other_and_panic;
  } else if (entryId === 'HIS-6-0007' || /纪念|灾后|墓|事故|空楼|古厝|隧道|建筑|医院|矿/.test(title)) {
    theme = PRISM_THEMES.memory_sediment;
  } else if (cluster === 'sid_myth' || genre === 'myth' || relation === 'MYTHIC_PROJECTION' || /创世|洪水|太阳|日月|地震|火山|海啸|雷电|彩虹/.test(title)) {
    theme = PRISM_THEMES.naming_chaos;
  } else if (relation === 'EMPIRICAL_EXPLAINS' || entryId.startsWith('PHY-') || entryId.startsWith('CHE-')) {
    theme = PRISM_THEMES.sensory_boundary;
  } else if (entryId.startsWith('PHI-')) {
    theme = PRISM_THEMES.model_and_abyss;
  }

  let experimentId = theme.defaultExperiment;
  if (/次声|声|响|振动|铃|歌|耳|听/.test(title) || entryId.startsWith('PHY-4') || entryId === 'ARC-1-0006') {
    experimentId = 'infrasound';
  } else if (/监控|照片|影像|录像|镜头|招牌|黑点|雾|噪/.test(title) || entryId === 'FOR-6-0015') {
    experimentId = 'pareidolia';
  } else if (/压床|夜|幻|影|在场|聻|眠/.test(title) || entryId === 'HEA-009' || entryId === 'BIO-3-0004') {
    experimentId = 'afterimage';
  }

  const realm = realmForDepth(depth);
  const realmNotes = {
    human: '此刻你身处「人界」实存坐标：可调节格物与信源尺度，也可随时潜入膜背对读体验之形。',
    threshold: '此刻你立于「界膜」临界点：一侧是物理与史学之可证，一侧是亲历与传说之不可尽言。',
    ghost: '此刻你处于「鬼阶」彼岸：如同《子不语》中所记“他人不见，惟亲历者见之”，你可望见膜外物界，却触之唯余微澜。',
    jian: '此刻你潜入「聻阶」深络：个体执念已褪为跨文化母题星丝，地名与年份消融为结构共振。',
    xi: '此刻你凝望「希阶」无声之律：惊怖之外，只有物理、认知与传播规律在静默自转。',
    yi: '此刻你悬置于「夷阶」第四面墙外：这组对读并不存在于真空中——真正连接两者的，是正在屏幕前凝视它的你。',
  };

  return {
    ...theme,
    experimentId,
    realm,
    realmNote: realmNotes[realm.id] || realmNotes.threshold,
  };
}

function renderLabMarkup(experimentId) {
  if (experimentId === 'afterimage') {
    return `<details class="syzygy-sensory-lab" data-lab="afterimage">
      <summary>◐ 感官边界微实验 · 视网膜余像（无中生影）</summary>
      <div class="syzygy-lab-body">
        <p class="syzygy-reference">凝视中心铜十字 10 秒勿动，随后画面消退——你将在空白处亲眼看见视网膜自发生成的“反色幽影”。</p>
        <div class="syzygy-afterimage-stage" data-afterimage-stage="idle">
          <div class="syzygy-afterimage-target">
            <span class="syzygy-afterimage-halo"></span>
            <span class="syzygy-afterimage-cross">+</span>
          </div>
          <p class="syzygy-afterimage-caption" data-afterimage-status>准备就绪 · 点击开始凝视</p>
        </div>
        <div class="syzygy-lab-actions">
          <button type="button" class="ctl-btn" data-lab-action="start-afterimage">开始 10 秒凝视</button>
          <button type="button" class="ctl-btn" data-lab-action="reveal-afterimage">直接显影</button>
          <button type="button" class="ctl-btn" data-lab-action="reset-afterimage">重置</button>
        </div>
      </div>
    </details>`;
  }
  if (experimentId === 'infrasound') {
    return `<details class="syzygy-sensory-lab" data-lab="infrasound">
      <summary>◐ 感官边界微实验 · 声学听阈与 19Hz 临界波形</summary>
      <div class="syzygy-lab-body">
        <p class="syzygy-reference">人耳听觉下限约 20 Hz。“听之不闻”的 19 Hz 依然具有真实声压与机械振动，却在听觉阈值之外。</p>
        <canvas class="syzygy-lab-canvas" data-lab-wave width="320" height="74" aria-label="声波示波器"></canvas>
        <div class="syzygy-lab-actions">
          <button type="button" class="ctl-btn active" data-lab-freq="19">19 Hz 临界</button>
          <button type="button" class="ctl-btn" data-lab-freq="44">44 Hz 低频</button>
          <button type="button" class="ctl-btn" data-lab-freq="110">110 Hz 基准</button>
          <button type="button" class="ctl-btn" data-lab-action="toggle-tone">试听波形</button>
        </div>
        <p class="syzygy-reference" data-wave-note>当前 19 Hz：示波器持续振动，接近人类听觉下限，常只感压迫而不闻其声。</p>
      </div>
    </details>`;
  }
  if (experimentId === 'pareidolia') {
    return `<details class="syzygy-sensory-lab" data-lab="pareidolia">
      <summary>◐ 感官边界微实验 · 空想性错视与噪点阈值</summary>
      <div class="syzygy-lab-body">
        <p class="syzygy-reference">拖动对比度滑杆：底层只是一组随机灰度噪点，观察大脑如何在高对比与留白之间“认出”原本不存在的轮廓。</p>
        <canvas class="syzygy-lab-canvas syzygy-noise-canvas" data-lab-noise width="280" height="92" aria-label="随机噪点错视实验"></canvas>
        <label class="syzygy-lab-slider">
          <span>阈值对比度 <strong data-noise-val>1.0×</strong></span>
          <input type="range" min="0.6" max="3.4" step="0.1" value="1.0" data-lab-noise-range />
        </label>
      </div>
    </details>`;
  }
  return '';
}

export function renderPrismPhilosophyHTML(prism, bookEntries = []) {
  if (!prism) return '';
  const phiEntry = bookEntries.find((item) => item.id === prism.phiEntryId);
  const secEntry = bookEntries.find((item) => item.id === prism.secondaryEntryId);
  return `<div class="syzygy-prism-logos" data-prism-theme="${esc(prism.id)}">
    <div class="syzygy-prism-head">
      <span class="syzygy-overline">LOGOS · 折光哲思 / ${esc(prism.title)}</span>
      <span class="syzygy-prism-realm">${esc(prism.realm.rank)} ${esc(prism.realm.char)}</span>
    </div>
    <p class="syzygy-prism-statement">${esc(prism.statement)}</p>
    <blockquote class="syzygy-prism-question">「${esc(prism.question)}」</blockquote>
    <p class="syzygy-prism-wall-note">${esc(prism.realmNote)}</p>
    <div class="syzygy-prism-anchors">
      ${phiEntry ? `<button type="button" class="syzygy-related" data-prism-book="${esc(phiEntry.id)}">
        <span>✦ 哲学锚点 · ${esc(phiEntry.title)}</span>
        <small>${esc(phiEntry.id)} · 第 ${esc(phiEntry.page)} 页（点击直达格物哲思对照）</small>
      </button>` : ''}
      ${secEntry && secEntry.id !== phiEntry?.id ? `<button type="button" class="syzygy-related" data-prism-book="${esc(secEntry.id)}">
        <span>◇ 延展参照 · ${esc(secEntry.title)}</span>
        <small>${esc(secEntry.id)} · 第 ${esc(secEntry.page)} 页</small>
      </button>` : ''}
    </div>
    ${renderLabMarkup(prism.experimentId)}
  </div>`;
}

export function bindSensoryLabs(container, { audio, onOpenBook } = {}) {
  if (!container) return;

  container.querySelectorAll('[data-prism-book]').forEach((button) => {
    button.addEventListener('click', () => {
      onOpenBook?.(button.dataset.prismBook);
    });
  });

  // 1. Retinal Afterimage Micro-Experiment
  const afterimageLab = container.querySelector('[data-lab="afterimage"]');
  if (afterimageLab) {
    const stage = afterimageLab.querySelector('[data-afterimage-stage]');
    const status = afterimageLab.querySelector('[data-afterimage-status]');
    let timer = null;

    const clearTimer = () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };
    const showBlank = () => {
      clearTimer();
      stage.dataset.afterimageStage = 'blank';
      status.textContent = '保持视线不动，注视空白中央——是否看到一枚互补色暗影浮现？';
    };
    afterimageLab.querySelector('[data-lab-action="start-afterimage"]')?.addEventListener('click', () => {
      clearTimer();
      let left = 10;
      stage.dataset.afterimageStage = 'gaze';
      status.textContent = `请注视中心十字 · 还剩 ${left} 秒`;
      timer = setInterval(() => {
        if (!afterimageLab.isConnected) {
          clearTimer();
          return;
        }
        left -= 1;
        if (left <= 0) showBlank();
        else status.textContent = `请注视中心十字 · 还剩 ${left} 秒`;
      }, 1000);
    });
    afterimageLab.querySelector('[data-lab-action="reveal-afterimage"]')?.addEventListener('click', showBlank);
    afterimageLab.querySelector('[data-lab-action="reset-afterimage"]')?.addEventListener('click', () => {
      clearTimer();
      stage.dataset.afterimageStage = 'idle';
      status.textContent = '准备就绪 · 点击开始凝视';
    });
  }

  // 2. Acoustic Threshold & 19Hz Infrasound Oscilloscope
  const infraLab = container.querySelector('[data-lab="infrasound"]');
  if (infraLab) {
    const canvas = infraLab.querySelector('[data-lab-wave]');
    const ctx = canvas?.getContext('2d');
    const note = infraLab.querySelector('[data-wave-note]');
    const toneBtn = infraLab.querySelector('[data-lab-action="toggle-tone"]');
    let freq = 19;
    let playing = false;
    let phase = 0;
    let rafId = null;

    const notes = {
      19: '当前 19 Hz：示波器持续振动，处于人类听觉下限之外，日常常体现为无声压迫感。',
      44: '当前 44 Hz：进入可听低频区，开始产生模糊嗡鸣。',
      110: '当前 110 Hz：清晰可辨的音高——同为波动，仅因频率跨越感官边界而显隐异途。',
    };

    const drawWave = () => {
      if (!infraLab.isConnected) {
        if (playing) audio?.stopLabTone?.();
        return;
      }
      if (infraLab.open && ctx) {
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        ctx.strokeStyle = 'rgba(207, 169, 98, 0.25)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, h / 2);
        ctx.lineTo(w, h / 2);
        ctx.stroke();

        ctx.strokeStyle = freq === 19 ? '#a5b4fc' : freq === 44 ? '#63c7a7' : '#f0d79c';
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        const cycles = freq === 19 ? 2.2 : freq === 44 ? 5.2 : 11.5;
        for (let x = 0; x <= w; x += 2) {
          const nx = x / w;
          const env = Math.sin(nx * Math.PI);
          const y = h / 2 + Math.sin(nx * Math.PI * 2 * cycles - phase) * (h * 0.34) * env;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        phase += 0.08 + freq * 0.0014;
      }
      rafId = requestAnimationFrame(drawWave);
    };

    infraLab.addEventListener('toggle', () => {
      if (infraLab.open && !rafId) rafId = requestAnimationFrame(drawWave);
      if (!infraLab.open) {
        if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
        if (playing) {
          playing = false;
          audio?.stopLabTone?.();
          if (toneBtn) toneBtn.textContent = '试听波形';
        }
      }
    });

    infraLab.querySelectorAll('[data-lab-freq]').forEach((btn) => {
      btn.addEventListener('click', () => {
        freq = Number(btn.dataset.labFreq) || 19;
        infraLab.querySelectorAll('[data-lab-freq]').forEach((b) => b.classList.toggle('active', b === btn));
        if (note) note.textContent = notes[freq] || '';
        if (playing) audio?.playLabTone?.(freq, 4500);
      });
    });

    toneBtn?.addEventListener('click', async () => {
      if (playing) {
        playing = false;
        audio?.stopLabTone?.();
        toneBtn.textContent = '试听波形';
      } else {
        const ok = await audio?.playLabTone?.(freq, 4500);
        if (ok) {
          playing = true;
          toneBtn.textContent = '停止发声';
          setTimeout(() => {
            if (playing && infraLab.isConnected) {
              playing = false;
              toneBtn.textContent = '试听波形';
            }
          }, 4600);
        }
      }
    });
  }

  // 3. Pareidolia Noise Threshold Experiment
  const noiseLab = container.querySelector('[data-lab="pareidolia"]');
  if (noiseLab) {
    const canvas = noiseLab.querySelector('[data-lab-noise]');
    const ctx = canvas?.getContext('2d');
    const slider = noiseLab.querySelector('[data-lab-noise-range]');
    const valLabel = noiseLab.querySelector('[data-noise-val]');
    const w = canvas?.width || 280;
    const h = canvas?.height || 92;
    const baseNoise = new Uint8Array(w * h);
    let seed = 133742;
    for (let i = 0; i < baseNoise.length; i++) {
      seed = (seed * 1664525 + 1013904223) >>> 0;
      baseNoise[i] = (seed >>> 24) & 0xff;
    }

    const paintNoise = (contrast) => {
      if (!ctx) return;
      const img = ctx.createImageData(w, h);
      const data = img.data;
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const i = y * w + x;
          // Pure deterministic noise modulated gently by radial vignetting so eyes hunt for patterns.
          const raw = (baseNoise[i] - 128) * contrast + 128;
          const lum = Math.max(0, Math.min(255, Math.round(raw)));
          const p = i * 4;
          data[p] = Math.min(255, Math.round(lum * 1.02));
          data[p + 1] = Math.min(255, Math.round(lum * 0.98));
          data[p + 2] = Math.min(255, Math.round(lum * 0.9));
          data[p + 3] = 255;
        }
      }
      ctx.putImageData(img, 0, 0);
    };

    paintNoise(1.0);
    slider?.addEventListener('input', () => {
      const c = Number(slider.value) || 1.0;
      if (valLabel) valLabel.textContent = `${c.toFixed(1)}×`;
      paintNoise(c);
    });
  }
}
