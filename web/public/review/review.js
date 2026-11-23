(() => {
  'use strict';
  const data = window.ASTRAIA_REVIEW_DATA;
  const detail = document.getElementById('detail');
  const recordsElement = document.getElementById('records');
  const search = document.getElementById('search');
  const collection = document.getElementById('collection');
  const region = document.getElementById('region');
  const batch = document.getElementById('batch');
  const issue = document.getElementById('issue');
  const status = document.getElementById('status');
  const storageKey = 'astraia-review-decisions-v1';
  const pageSize = 60;
  const stateLabels = {pending:'待复核', reviewed:'复核通过', correction:'需要修改', stale:'草稿已变化'};
  const categoryLabels = {source:'出处', coordinate:'坐标', standard:'标准码', classification:'体裁'};
  const collectionLabels = {scottish:'苏格兰猎巫', berezkin:'别列兹金母题', nichibun:'日文研馆藏',
    duchas:'Dúchas 馆藏', regional:'其他区域资料', research:'研究报告资料',
    asia:'中国与东亚、东南亚', intake:'本地入库草稿'};
  const genres = {unclassified:'待确认', myth:'神话', fabulate:'传说', memorate:'亲历叙事',
    folktale:'民间故事', creepypasta_ostension:'网络虚构', historical_archive:'历史档案', academic_model:'学术资料'};
  const standardNames = {atu_types:'ATU', thompson_motifs:'汤普森', berezkin_codes:'别列兹金', ocm_codes:'OCM'};
  const precisionLabels = {exact:'精确位置', city:'城市参考', province:'省级参考', culture_region:'文化区域', global:'全球'};
  let page = 0;
  let selectedId = null;
  let showingUnmatched = false;
  let decisions = {};
  let koreanFonts = 'loading';
  let thaiFonts = 'loading';
  const batchRegion = new Map();
  const batchNames = new Map();
  const isKoreanRecord = (record) => record.id === 'corpus_kr_aks_dobong' || record.id.startsWith('case_kr_aks_dobong_');
  const isLannaRecord = (record) => record.id.startsWith('corpus_th_lanna_');

  if (!data || !Array.isArray(data.records)) {
    detail.textContent = '复核数据未生成，请先运行资料复核清单构建命令。';
    return;
  }

  try {
    const saved = localStorage.getItem(storageKey);
    if (saved) decisions = JSON.parse(saved);
  } catch {
    showMessage('无法读取本机复核记录。请检查浏览器的站点存储设置。');
  }

  const byId = new Map(data.records.map((record) => [record.id, record]));
  fetch('./regions.json').then((response) => {
    if (!response.ok) throw new Error('地区目录不可用');
    return response.json();
  }).then((catalog) => {
    if (catalog.version !== 1 || !Array.isArray(catalog.groups)) throw new Error('地区目录格式不符');
    for (const group of catalog.groups) {
      const option = el('option', group.label);
      option.value = group.id;
      region.append(option);
      for (const [id, label] of Object.entries(group.batches)) {
        if (batchRegion.has(id)) throw new Error('地区目录包含重复批次');
        batchRegion.set(id, group.id);
        batchNames.set(id, label);
      }
    }
    region.disabled = false;
    batch.disabled = false;
    refreshBatchOptions();
  }).catch(() => showMessage('地区和批次筛选未加载；请检查本地复核资料。'));

  function refreshBatchOptions() {
    const selected = batch.value;
    const batches = [...new Set(data.records.map((record) => record.batch))]
      .filter((id) => region.value === 'all' || batchRegion.get(id) === region.value)
      .sort((left, right) => (batchNames.get(left) || left).localeCompare(batchNames.get(right) || right, 'zh-CN'));
    batch.replaceChildren();
    const all = el('option', '全部批次');
    all.value = 'all';
    batch.append(all);
    for (const id of batches) {
      const option = el('option', batchNames.get(id) || id);
      option.value = id;
      batch.append(option);
    }
    batch.value = batches.includes(selected) ? selected : 'all';
  }
  Promise.resolve().then(async () => {
    const faces = await Promise.all([
      document.fonts.load('400 16px "Astraia CJK"', '中文'),
      document.fonts.load('700 16px "Astraia CJK"', '中文'),
      document.fonts.load('400 16px "Astraia Korean"', '한글\uF90A'),
      document.fonts.load('700 16px "Astraia Korean"', '한글\uF90A'),
    ]);
    koreanFonts = faces.every((face) => face.length) ? 'ready' : 'missing';
  }).catch(() => { koreanFonts = 'missing'; }).finally(() => {
    renderList();
    const selected = byId.get(selectedId);
    if (selected && isKoreanRecord(selected) && !showingUnmatched) renderDetail(selected);
  });
  Promise.resolve().then(async () => {
    const faces = await Promise.all([
      document.fonts.load('400 16px "Astraia CJK"', '中文'),
      document.fonts.load('700 16px "Astraia CJK"', '中文'),
      document.fonts.load('400 16px "Noto Sans Thai"', 'เจ้าแสงเมิง'),
      document.fonts.load('600 16px "Noto Sans Thai"', 'เจ้าแสงเมิง'),
    ]);
    thaiFonts = faces.every((face) => face.length) ? 'ready' : 'missing';
  }).catch(() => { thaiFonts = 'missing'; }).finally(() => {
    renderList();
    const selected = byId.get(selectedId);
    if (selected && isLannaRecord(selected) && !showingUnmatched) renderDetail(selected);
  });
  const index = data.records.map((record) => ({
    record,
    text: [record.id, record.title, record.card_path, record.spatial?.location_name,
      ...record.sources.flatMap((source) => [source.citation, source.locator, source.doi]),
      ...Object.values(record.standards).flat(), JSON.stringify(record.evidence)]
      .filter(Boolean).join(' ').normalize('NFKC').toLocaleLowerCase(),
    urgent: record.issues.some((entry) => entry.urgent),
  })).sort((left, right) => Number(right.urgent) - Number(left.urgent) || left.record.id.localeCompare(right.record.id));

  function showMessage(text) {
    const element = document.getElementById('message');
    element.textContent = text;
    element.hidden = false;
    clearTimeout(showMessage.timeout);
    showMessage.timeout = setTimeout(() => { element.hidden = true; }, 6000);
  }

  function currentState(record) {
    const decision = decisions[record.id];
    if (!decision) return 'pending';
    return decision.card_sha256 === record.card_sha256 ? decision.status : 'stale';
  }

  function persist() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(decisions));
      return true;
    } catch {
      showMessage('保存失败，请检查浏览器的站点存储设置。');
      return false;
    }
  }

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }

  function addRow(list, label, value) {
    const row = el('div');
    row.append(el('dt', label), el('dd', value || '—'));
    list.append(row);
  }

  function link(url, title) {
    try {
      const parsed = new URL(url);
      if (!['http:', 'https:'].includes(parsed.protocol)) return null;
      const anchor = el('a', title);
      anchor.href = parsed.href;
      anchor.target = '_blank';
      anchor.rel = 'noopener noreferrer';
      return anchor;
    } catch {
      return null;
    }
  }

  function refreshCounts() {
    const counts = {pending:0, reviewed:0, correction:0, stale:0};
    for (const record of data.records) counts[currentState(record)] += 1;
    document.getElementById('total').textContent = `${data.records.length.toLocaleString()} 条`;
    document.getElementById('counts').textContent = `待复核 ${counts.pending} · 通过 ${counts.reviewed} · 需修改 ${counts.correction} · 草稿变化 ${counts.stale}`;
  }

  function matches() {
    const terms = search.value.normalize('NFKC').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const exactId = terms.length === 1 && byId.has(terms[0]) ? terms[0] : null;
    return index.filter(({record, text, urgent}) => {
      if (exactId && record.id !== exactId) return false;
      if (region.value !== 'all' && batchRegion.get(record.batch) !== region.value) return false;
      if (batch.value !== 'all' && record.batch !== batch.value) return false;
      if (collection.value !== 'all' && record.collection !== collection.value) return false;
      if (issue.value === 'urgent' && !urgent) return false;
      if (!['all', 'urgent'].includes(issue.value) && !record.issues.some((entry) => entry.category === issue.value)) return false;
      if (status.value !== 'all' && currentState(record) !== status.value) return false;
      return terms.every((term) => text.includes(term));
    });
  }

  function renderList() {
    refreshCounts();
    const filtered = matches();
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    page = Math.min(page, totalPages - 1);
    recordsElement.replaceChildren();
    const fragment = document.createDocumentFragment();
    for (const {record, urgent} of filtered.slice(page * pageSize, (page + 1) * pageSize)) {
      const button = el('button', null, 'record');
      button.type = 'button';
      button.dataset.nodeId = record.id;
      button.setAttribute('role', 'listitem');
      if (record.id === selectedId && !showingUnmatched) button.setAttribute('aria-current', 'true');
      const meta = el('span', null, 'record-meta');
      meta.append(el('span', record.id), el('span', stateLabels[currentState(record)]));
      if (urgent) meta.append(el('span', '优先核对', 'urgent'));
      const title = isKoreanRecord(record) && koreanFonts !== 'ready' ? 'Korean record — required fonts unavailable or loading' :
        isLannaRecord(record) && thaiFonts !== 'ready' ? 'Northern Thai record — required font unavailable or loading' : record.title;
      button.append(el('span', title, 'record-title'), meta);
      button.addEventListener('click', () => {
        selectedId = record.id;
        showingUnmatched = false;
        renderList();
        renderDetail(record);
        if (matchMedia('(max-width: 760px)').matches) detail.scrollIntoView({behavior:'smooth', block:'start'});
      });
      fragment.append(button);
    }
    recordsElement.append(fragment);
    document.getElementById('matches').textContent = `符合条件 ${filtered.length.toLocaleString()} 条`;
    document.getElementById('page-info').textContent = `${page + 1} / ${totalPages}`;
    document.getElementById('previous').disabled = page === 0;
    document.getElementById('next').disabled = page >= totalPages - 1;
  }

  function renderDetail(record) {
    detail.replaceChildren();
    if (isKoreanRecord(record) && koreanFonts !== 'ready') {
      detail.append(el('p', koreanFonts === 'loading' ? 'Checking Chinese and Korean fonts…' :
        'Required fonts are missing: Microsoft YaHei and Malgun Gothic (regular and bold). Install them and reopen this page.'));
      return;
    }
    if (isLannaRecord(record) && thaiFonts !== 'ready') {
      detail.append(el('p', thaiFonts === 'loading' ? 'Checking the Northern Thai font…' :
        'Required fonts are missing: Microsoft YaHei (regular and bold) and Noto Sans Thai. Restore the fonts and reopen this page.'));
      return;
    }
    detail.append(el('p', `${collectionLabels[record.collection]}  /  ${record.id}`, 'metadata'));
    detail.append(el('h2', record.title));
    const state = el('span', stateLabels[currentState(record)], 'state');
    state.dataset.state = currentState(record);
    detail.append(state);

    detail.append(el('h3', '需要核对'));
    const concerns = el('div', null, 'issue-list');
    if (!record.issues.length) concerns.append(el('p', '当前字段未发现自动核对项，仍需人工阅读资料。'));
    for (const entry of record.issues) {
      const line = el('p');
      line.append(el('b', `${categoryLabels[entry.category]}  `), document.createTextNode(entry.description));
      concerns.append(line);
    }
    detail.append(concerns);
    const korea = record.evidence.korea_aks_dobong;
    if (korea) {
      detail.append(el('h3', '韩国目录与馆方候选'));
      detail.append(el('p', '候选仅供人工核对，不能自动认定为同一次演述。调查日期与采录地也不等于故事发生时空。', 'muted'));
      const original = el('dl');
      addRow(original, '目录题名', korea['目录字段']['서명']);
      addRow(original, '讲述者', korea['目录字段']['구연자']);
      addRow(original, '采录地', korea['目录字段']['채록지']);
      addRow(original, '目录类别', korea['目录字段']['유형']);
      addRow(original, '目录短编号', korea['目录字段']['텍스트']);
      detail.append(original, el('p', '目录短编号不是标准码。', 'muted'));
      if (!korea['馆方候选'].length) detail.append(el('p', '本次检索未找到候选，仍需回查。'));
      for (const candidate of korea['馆方候选']) {
        const section = el('div', null, 'heritage-comparison');
        section.append(el('p', `${candidate['馆方编号']} · ${candidate['题名对照方式']} · ${candidate['题名相似度']}`));
        const fields = el('dl');
        addRow(fields, '检索题名', candidate['馆方检索题名']);
        addRow(fields, '详情题名', candidate['馆方详情题名']);
        addRow(fields, '详情讲述者', candidate['馆方详情讲述者']);
        addRow(fields, '详情采录地', candidate['馆方详情采录地点']);
        addRow(fields, '调查日期', candidate['馆方详情调查日期（非叙事年代）']);
        addRow(fields, '地点对照', candidate['目录与详情采录地点']);
        section.append(fields);
        const originalLink = link(candidate['候选单条页面'], '查看馆方候选原文 ↗');
        if (originalLink) section.append(originalLink);
        detail.append(section);
      }
    }
    const lanna = record.evidence.lanna;
    if (lanna) {
      detail.append(el('h3', '北泰手稿馆藏字段'));
      detail.append(el('p', '保留馆方原字段；馆藏地点与经纬度不自动作为故事发生地。', 'muted'));
      const fields = el('dl');
      const values = (name) => Object.values(lanna['馆藏字段'][name] || {}).flat().join(' · ');
      addRow(fields, '题名', values('title'));
      addRow(fields, '语言', values('dc:language'));
      addRow(fields, '文字', values('script'));
      addRow(fields, '馆藏地点', values('full_location_name'));
      addRow(fields, '馆藏坐标', [values('schema:latitude'), values('schema:longitude')].filter(Boolean).join(' / '));
      addRow(fields, '手稿日期', values('date_original'));
      addRow(fields, '馆藏档号', values('otherIdentifier.code_number'));
      addRow(fields, '同号候选', lanna['相同档号馆藏候选'].join(' · '));
      addRow(fields, '署名与许可', lanna['署名与许可']);
      detail.append(fields, el('p', '馆藏档号不是标准码。手稿影像和正文请在馆方页面查看。', 'muted'));
      const source = record.sources.find((item) => item.type === 'lanna_viewer');
      const sourceLink = source && link(source.url, '查看馆方手稿原图 ↗');
      if (sourceLink) detail.append(sourceLink);
    }
    const supplementary = record.evidence.pangloss_supplement;
    const supplementDetails = (record.evidence.pangloss_khmu || record.evidence.pangloss_japhug)?.['馆方详情字段'];
    if (supplementary && supplementDetails) {
      detail.append(el('h3', '后续补充的馆方详情'));
      detail.append(el('p', '保留首轮目录字段；以下为后续取得的单条详情，仍须人工核对。', 'muted'));
      const fields = el('dl');
      addRow(fields, '研究者', supplementDetails.researchers);
      addRow(fields, '讲述者', supplementDetails.speakers);
      addRow(fields, '录音日期', supplementDetails.recorded);
      addRow(fields, '录音地点', supplementDetails.recording_location);
      addRow(fields, '馆方许可原字段', supplementDetails.license);
      if (supplementDetails.alternate_titles?.length) {
        addRow(fields, '其他语言题名', supplementDetails.alternate_titles.map(item => `${item.language_as_displayed} ${item.title}`).join(' · '));
      }
      detail.append(fields);
    }
    const khmuResearch = record.evidence.khmu_research_reference;
    if (khmuResearch) {
      detail.append(el('h3', '相关研究出处'));
      detail.append(el('p', khmuResearch.note));
      const researchLink = link(khmuResearch.url, khmuResearch.citation);
      if (researchLink) detail.append(researchLink);
    }
    const heritageComparisons = record.evidence.heritage_comparisons || [];
    if (heritageComparisons.length) {
      detail.append(el('h3', '跨年度项目登记对照'));
      detail.append(el('p', '仅按同一名录序号和行政项目编号对照；名称及申报地区须复核，不能视作单篇故事或传播路线。', 'muted'));
      for (const entry of heritageComparisons) {
        const section = el('div', null, 'heritage-comparison');
        section.append(el('p', `${entry.year} · ${entry.kind} · ${entry.raw_number} · ${entry.title}${entry.availability === 'reviewed' ? ' · 已复核入图' : ''}`));
        section.append(el('p', `申报地区或单位：${entry.area}`, 'muted'));
        const links = el('div', null, 'record-links');
        const source = link(entry.url, '查看该年原表');
        if (source) links.append(source);
        const target = byId.get(entry.id);
        if (target) {
          const button = el('button', '查看该条待审卡');
          button.type = 'button';
          button.addEventListener('click', () => {
            search.value = entry.id;
            collection.value = target.collection;
            issue.value = 'all'; status.value = 'all'; page = 0;
            selectedId = entry.id; showingUnmatched = false;
            renderList(); renderDetail(target);
            if (matchMedia('(max-width: 760px)').matches) detail.scrollIntoView({behavior:'smooth', block:'start'});
          });
          links.append(button);
        }
        section.append(links); detail.append(section);
      }
    }
    const khmuComparison = record.evidence.khmu_comparison;
    if (khmuComparison) {
      detail.append(el('h3', '录音目录对照候选'));
      detail.append(el('p', `${khmuComparison.label}：${khmuComparison.note}`, 'muted'));
      const currentPlace = record.evidence.pangloss_khmu?.['馆方详情字段']?.recording_location;
      detail.append(el('p', `本条馆方录音地点：${currentPlace || '详情未取得或未列'}`, 'muted'));
      for (const entry of khmuComparison.members.filter(member => member.node_id !== record.id)) {
        const section = el('div', null, 'heritage-comparison');
        section.append(el('p', `${entry.id} · ${entry.title}`));
        section.append(el('p', `目录讲述者：${entry.speakers || '未列'} · 录音日期：${entry.recorded || '未列'}`, 'muted'));
        const target = byId.get(entry.node_id);
        const targetPlace = target?.evidence?.pangloss_khmu?.['馆方详情字段']?.recording_location;
        section.append(el('p', `馆方录音地点：${targetPlace || '详情未取得或未列'}`, 'muted'));
        const links = el('div', null, 'record-links');
        const source = link(entry.url, '查看馆方录音');
        if (source) links.append(source);
        if (target) {
          const button = el('button', '查看对照待审卡');
          button.type = 'button';
          button.addEventListener('click', () => {
            search.value = entry.node_id; collection.value = target.collection;
            issue.value = 'all'; status.value = 'all'; page = 0;
            selectedId = entry.node_id; showingUnmatched = false;
            renderList(); renderDetail(target);
            if (matchMedia('(max-width: 760px)').matches) detail.scrollIntoView({behavior:'smooth', block:'start'});
          });
          links.append(button);
        }
        section.append(links); detail.append(section);
      }
    }
    const panglossLocation = record.evidence.pangloss_location_context;
    if (panglossLocation) {
      detail.append(el('h3', '录音地点称谓对照'));
      detail.append(el('p', panglossLocation.citation));
      detail.append(el('p', panglossLocation.note, 'muted'));
      const paper = link(panglossLocation.url, '查看研究者地点说明');
      if (paper) detail.append(paper);
    }
    const crosscheck = record.evidence.catalogue_crosscheck;
    if (crosscheck) {
      detail.append(el('h3', '目录对照'));
      detail.append(el('p', crosscheck.finding));
      detail.append(el('p', crosscheck.interpretation, 'muted'));
      const reference = link(crosscheck.url, `查看目录单页 · ${crosscheck.checked_at}`);
      if (reference) detail.append(reference);
    }
    const coordinateChecks = record.evidence.coordinate_crosschecks || [];
    if (coordinateChecks.length) {
      detail.append(el('h3', '地区参考点对照'));
      for (const check of coordinateChecks) {
        detail.append(el('p', `${check.area_id} · ${check.name}  /  原值 ${check.lat}, ${check.lng}`));
        detail.append(el('p', check.finding, 'muted'));
        const links = el('div', null, 'record-links');
        for (const source of check.sources) {
          const anchor = link(source.url, source.title);
          if (anchor) links.append(anchor);
        }
        detail.append(links);
      }
      detail.append(el('p', '文化分析区可能跨越现代国界。底图和族群举例仅用于提出疑点，不能确定采录点。', 'muted'));
    }
    const identity = record.evidence.wikidata_identity;
    if (identity && (identity.entities.length || identity.map_candidates.length)) {
      detail.append(el('h3', '被告档号与地图对照'));
      detail.append(el('p', `调查库档号 ${identity.survey_id}  /  Wikidata P4478  /  快照 ${identity.retrieved_at}`));
      if (identity.ambiguous_identity) detail.append(el('p', '该档号与 Wikidata 实体不是一对一，请核对合并或重复。', 'muted'));
      const entityLinks = el('div', null, 'record-links');
      for (const entity of identity.entities) {
        const anchor = link(entity.url, `Wikidata ${entity.qid}`);
        if (anchor) entityLinks.append(anchor);
        if (entity.other_survey_ids.length) entityLinks.append(el('span', `同实体其他档号：${entity.other_survey_ids.join('、')}`));
      }
      detail.append(entityLinks);
      for (const candidate of identity.map_candidates) {
        const distance = candidate.distance_km == null ? '' : ` · 距原生成点约 ${candidate.distance_km} 公里`;
        detail.append(el('p', `${candidate.residence}  /  ${candidate.lat}, ${candidate.lng}${distance}`, 'muted'));
      }
      if (identity.map_candidates.length) {
        const mapSource = link(identity.map_url, `查看地图导出来源 · ${identity.map_locator}`);
        if (mapSource) detail.append(mapSource);
        detail.append(el('p', `${identity.map_local_path}  /  SHA-256 ${identity.map_sha256}`, 'muted'));
      }
      detail.append(el('p', '地图导出本身来自 Wikidata；编号能帮助定位人物，但不能独立证实住地。候选点需核对原始登记及地点范围。', 'muted'));
    }

    const repository = record.evidence.lao_repository_candidate;
    if (repository) {
      detail.append(el('h3', '馆藏地坐标候选'));
      detail.append(el('p', `${repository.lat}, ${repository.lng}`));
      detail.append(el('p', '馆藏目录提供的候选点尚待核对；不代表故事发生地或采录地。', 'muted'));
    }
    const communities = record.evidence.sinica_community_candidates || [];
    if (communities.length) {
      detail.append(el('h3', '采集地社区地标候选'));
      detail.append(el('p', '这些是政府资料中的社区地标，不能当作具体录音点或故事发生地；名称、坐标参考系及年代适用性仍需核对。', 'muted'));
      for (const candidate of communities) {
        detail.append(el('p', `${candidate['部落名称']} · ${candidate['地标']}  /  ${candidate['纬度']}, ${candidate['经度']}`));
        detail.append(el('p', `${candidate['县市']} ${candidate['乡镇']}  /  传统名 ${candidate['传统名']}  /  资料日期 ${candidate['登记日期']}`, 'muted'));
        if (candidate['名称对照依据']) {
          const alias = link(candidate['名称对照依据'], '查看名称对照依据');
          if (alias) detail.append(alias);
        }
      }
    }
    const laoDuplicates = record.evidence.lao_duplicate_plmp || [];
    if (laoDuplicates.length) {
      detail.append(el('h3', 'PLMP 档号对照'));
      detail.append(el('p', '同号记录的编目关系尚未确认，请逐件核对，不自动合并。', 'muted'));
      for (const other of laoDuplicates) {
        const line = el('p');
        line.append(document.createTextNode(`PLMP ${other.code}  /  ${other.dllm_id}  /  ${other.title}  `));
        const anchor = link(other.viewer, `查看馆藏 ${other.manifest}`);
        if (anchor) line.append(anchor);
        detail.append(line);
      }
    }

    detail.append(el('h3', '地点与标准码'));
    const facts = el('dl');
    const spatial = record.spatial;
    addRow(facts, '地点', spatial?.location_name);
    addRow(facts, '坐标', spatial?.lat == null ? '未登记' : `${spatial.lat}, ${spatial.lng}`);
    addRow(facts, '坐标范围', record.evidence.coordinate_scope || record.evidence.location_method || precisionLabels[spatial?.precision] || spatial?.precision);
    const standards = Object.entries(record.standards).flatMap(([system, values]) =>
      Array.isArray(values) ? values.map((value) => `${standardNames[system] || system} ${value}`) : []);
    addRow(facts, '标准码', standards.join(' · ') || '空');
    detail.append(facts);

    const zibuyu = record.evidence.zibuyu;
    if (zibuyu) {
      detail.append(el('h3', '在线转录原文'));
      detail.append(el('p', '维基文库固定修订的段落转录；古籍底本与注标待核。', 'muted'));
      const revision = link(zibuyu['固定修订原文链接'], '打开对应修订与篇题 ↗');
      if (revision) detail.append(revision);
      const match = (record.markdown || '').match(/^## 在线转录原文（待校）\r?\n\r?\n(`{3,})\r?\n([\s\S]*?)\r?\n\1[ \t]*(?=\r?$)/m);
      if (match) {
        const text = el('div', match[2], 'zibuyu-transcription');
        text.lang = 'zh-Hant';
        detail.append(text);
      } else {
        detail.append(el('p', '未能识别转录段落，请核对下方草稿正文。', 'muted'));
      }
    }

    const colePages = record.evidence.cole_ocr_pages;
    if (Array.isArray(colePages) && colePages.length) {
      detail.append(el('h3', '扫描分页 OCR · 待校'));
      detail.append(el('p', '保留识别误字、页眉与脚注；范围按候选页截取，篇章边界须逐页核对原扫描。', 'muted'));
      for (const page of colePages) {
        const block = el('details', null, 'cole-ocr-page');
        block.append(el('summary', `候选扫描页 ${page.scan} · 未校对 OCR`));
        const original = link(page.scan_url, '查看该页原扫描 ↗');
        if (original) block.append(original);
        if (page.text.trim()) block.append(el('pre', page.text));
        else block.append(el('p', '本页 OCR 未识别到文字。', 'muted'));
        detail.append(block);
      }
    }

    detail.append(el('h3', `出处 · ${record.sources.length}`));
    const sources = el('ol');
    for (const source of record.sources) {
      const item = el('li');
      item.append(el('div', source.citation));
      if (source.locator) item.append(el('div', source.locator, 'muted'));
      if (source.local_path) item.append(el('div', source.local_path, 'muted'));
      const sourceLink = link(source.url || (source.doi ? `https://doi.org/${source.doi}` : ''), '查看来源');
      if (sourceLink) item.append(sourceLink);
      sources.append(item);
    }
    detail.append(sources);
    const japhugContext = record.evidence.japhug_context;
    if (japhugContext) {
      detail.append(el('h3', '语料与版本背景'));
      detail.append(el('p', japhugContext.note));
      const contextLink = link(japhugContext.url, japhugContext.citation);
      if (contextLink) detail.append(contextLink);
    }
    const nitean = record.evidence.nitean_chapter;
    if (nitean) {
      detail.append(el('h3', '高棉文原文与脚注'));
      detail.append(el('p', `目录第 ${nitean['目录卷次']} 卷 · 第 ${nitean['目录卷内序号']} 篇`, 'muted'));
      const original = link(nitean['原文链接'], '在转录站查看原文');
      if (original) detail.append(original);
      for (const locator of nitean['页面所列卷册页码原文'] || []) detail.append(el('p', locator, 'muted'));
      const notes = el('div', null, 'record-links');
      for (const [index, anchor] of (nitean['可定位脚注'] || []).entries()) {
        if (!/^[A-Za-z0-9_-]{1,80}$/.test(anchor)) continue;
        try {
          const target = new URL(nitean['原文链接']);
          target.hash = anchor;
          const note = link(target.href, `查看原站脚注 ${index + 1}`);
          if (note) notes.append(note);
        } catch { /* Invalid original URLs are already flagged during import. */ }
      }
      if (notes.childElementCount) detail.append(notes);
    }
    const panglossAnnotations = record.evidence.pangloss_annotations;
    if (Array.isArray(panglossAnnotations)) {
      detail.append(el('h3', '馆方资源与分句定位'));
      detail.append(el('p', '本地仅保存资源关系、分句编号和时间；原语与译文请在馆方页面查看。附件许可需单独核对。', 'muted'));
      if (record.evidence.pangloss_annotation_observed_at) {
        detail.append(el('p', `馆方接口观察时间：${record.evidence.pangloss_annotation_observed_at}`, 'muted'));
      }
      if (!panglossAnnotations.length) detail.append(el('p', '本次接口未返回关联附件；其他版本仍需回查。'));
      for (const [index, annotation] of panglossAnnotations.entries()) {
        const block = el('div', null, 'sentence-resource');
        const segments = annotation.segments || [];
        block.append(el('p', `资源 ${index + 1} · ${annotation.type.toUpperCase()} · ${annotation.oai}`));
        block.append(el('p', `对应音视频：${annotation.primary_oai} · 附件单独许可：尚未核明`, 'muted'));
        if (segments.length) {
          const controls = el('div', null, 'sentence-controls');
          const label = el('label', `分句序号（1–${segments.length}）`);
          const number = el('input');
          number.type = 'number';
          number.min = '1';
          number.max = String(segments.length);
          number.step = '1';
          number.value = '1';
          number.setAttribute('aria-label', `资源 ${index + 1} 分句序号`);
          label.append(number);
          const anchor = link(annotation.viewer_url, '在原站查看本段');
          const context = el('span', null, 'muted sentence-context');
          const update = () => {
            const position = number.valueAsNumber;
            const valid = Number.isInteger(position) && position >= 1 && position <= segments.length;
            if (!valid) {
              if (anchor) { anchor.removeAttribute('href'); anchor.setAttribute('aria-disabled', 'true'); }
              context.textContent = `请输入 1 至 ${segments.length} 的整数。`;
              return;
            }
            const segment = segments[position - 1];
            if (anchor) {
              const target = new URL(annotation.viewer_url);
              target.hash = `S${position}`;
              anchor.href = target.href;
              anchor.removeAttribute('aria-disabled');
            }
            const time = segment.time_status === 'valid' ? `${segment.start}–${segment.end} 秒` : '时间未提供或待核';
            const languages = segment.translation_languages.length ? segment.translation_languages.join(' / ') : '未标注';
            context.textContent = `${time} · 译文语言：${languages}`;
          };
          number.addEventListener('input', update);
          controls.append(label);
          if (anchor) controls.append(anchor);
          controls.append(context);
          block.append(controls);
          update();
        } else {
          block.append(el('p', annotation.type === 'xml' ? '此 XML 未检出可定位分句。' : '此附件不是分句 XML。', 'muted'));
          const anchor = link(annotation.viewer_url, '查看馆方关联资源');
          if (anchor) block.append(anchor);
        }
        detail.append(block);
      }
    }
    const naTone = record.evidence.na_tone_book;
    if (naTone) {
      detail.append(el('h3', '纳语专著 · 录音引用'));
      detail.append(el('p', '下列是出版 PDF 中的原始链接；录音与附属文本可能使用不同 DOI，片段及许可仍需回查。', 'muted'));
      const bookSource = record.sources.find(source => source.type === 'na_tone_book');
      for (const item of naTone['专著叙事目录'] || []) {
        const label = `${item.topic}${item.book_version_label ? ` · 书中版本 ${item.book_version_label}` : ''} · DOI ${item.book_doi_id}`;
        detail.append(el('p', label, 'muted'));
      }
      const refs = naTone['专著中链接'] || [];
      const list = el('details', null, 'na-tone-link-list');
      list.append(el('summary', `展开 ${refs.length} 条书中链接`));
      const entries = el('ol');
      for (const ref of refs) {
        const line = el('li');
        if (bookSource?.url && Number.isInteger(ref.pdf_page)) {
          try {
            const pdf = new URL(bookSource.url); pdf.hash = `page=${ref.pdf_page}`;
            const pageLink = link(pdf.href, `PDF 第 ${ref.pdf_page} 页（印刷页 ${ref.printed_page}）`);
            if (pageLink) line.append(pageLink, document.createTextNode(' · '));
          } catch { /* Invalid source URLs are flagged by the review pipeline. */ }
        }
        const fragment = ref.fragment ? `#${ref.fragment}` : '';
        const target = link(ref.url, `DOI ${ref.doi_id}${fragment}`);
        if (target) line.append(target);
        if (ref.fragment_kind === 'unknown_fragment') line.append(el('span', ' · 片段性质待核', 'muted'));
        entries.append(line);
      }
      list.append(entries); detail.append(list);
      for (const registry of naTone['DataCite 登记对照'] || []) {
        const rights = registry['登记权利原字段'] || [];
        if (!rights.length) continue;
        detail.append(el('p', `DOI ${registry['书中 DOI 编号']} · 登记资源类型：${registry['登记类型'] || '未说明'}`, 'muted'));
        for (const right of rights) {
          const line = el('p', null, 'muted');
          if (right.rights) line.append(document.createTextNode(right.rights));
          const license = link(right.rightsUri, '查看登记许可链接 ↗');
          if (license) line.append(document.createTextNode(' '), license);
          detail.append(line);
        }
      }
    }
    if (record.collection === 'scottish') {
      detail.append(el('p', '历史史料条目由爱丁堡调查库登记，原件及卷页仍需回查。', 'muted'));
      const online = [];
      const addOnline = (kind, reference, label) => {
        if (typeof reference !== 'string' || !/^[ACT]\/[A-Z]+\/\d+$/.test(reference)) return;
        online.push(link(`https://witches.hca.ed.ac.uk/${kind}/${reference}`, `${label} ${reference}`));
      };
      addOnline('accused', record.evidence.WDB_Accused?.AccusedRef, '被告');
      for (const row of record.evidence.WDB_Case || []) addOnline('case', row.CaseRef, '案件');
      for (const row of record.evidence.WDB_Trial || []) addOnline('trial', row.Trialref, '审判');
      if (online.length) {
        const links = el('div', null, 'record-links');
        for (const anchor of online) if (anchor) links.append(anchor);
        detail.append(links);
      }
      const matches = record.evidence.matching_map_rows || [];
      if (matches.length) {
        const links = el('div', null, 'record-links');
        for (const match of matches) {
          const anchor = link(match['Wikidata Page'], `地图导出同名记录 · ${match.Name}`);
          if (anchor) links.append(anchor);
        }
        detail.append(links);
      }
    } else if (record.collection === 'berezkin' && record.evidence.study_code && /^[a-z][0-9]+[a-z0-9]*$/.test(record.evidence.study_code)) {
      const sourceLink = link(`https://www.ruthenia.ru/folklore/berezkin/${record.evidence.study_code}.html`,
        `目录单页 · ${record.evidence.study_code}`);
      if (sourceLink) detail.append(sourceLink);
    }

    detail.append(el('h3', '原始字段'));
    const displayEvidence = {...record.evidence};
    if (Array.isArray(displayEvidence.pangloss_annotations)) {
      displayEvidence.pangloss_annotations = displayEvidence.pangloss_annotations.map(({segments, ...annotation}) =>
        ({...annotation, segment_count: segments?.length || 0}));
    }
    detail.append(el('pre', JSON.stringify(displayEvidence, null, 2)));
    if (record.dependencies.length) {
      const related = el('details');
      related.append(el('summary', `关联卡片 · ${record.dependencies.length}`));
      related.append(el('p', '关联卡片须先完成复核，或与本条一起签核。', 'muted'));
      const links = el('div', null, 'record-links');
      for (const id of record.dependencies) {
        const linked = byId.get(id);
        if (!linked) {
          links.append(el('span', `${id}（不在待审清单）`));
          continue;
        }
        const button = el('button', linked.title);
        button.type = 'button';
        button.addEventListener('click', () => {
          search.value = id;
          for (const field of [region, batch, collection, issue, status]) field.value = 'all';
          refreshBatchOptions();
          selectedId = id;
          showingUnmatched = false;
          page = 0;
          renderList();
          renderDetail(linked);
          detail.scrollIntoView({behavior:'smooth', block:'start'});
        });
        links.append(button);
      }
      related.append(links);
      detail.append(related);
    }
    detail.append(el('h3', '草稿正文'));
    detail.append(el('pre', record.markdown));
    detail.append(el('p', record.card_path, 'muted'));

    const form = el('section', null, 'review-form');
    form.append(el('h3', '记录人工复核'));
    form.append(el('p', '复核记录保存在本机浏览器。确认公开时，复核人和许可依据会随卡片展示。', 'muted'));
    const previous = decisions[record.id] || {};
    const genreLabel = el('label', '体裁');
    const genre = el('select');
    genre.setAttribute('aria-label', '体裁');
    for (const [value, label] of Object.entries(genres)) {
      const option = el('option', label);
      option.value = value;
      genre.append(option);
    }
    genre.value = previous.genre || record.genre || 'unclassified';
    genreLabel.append(genre);
    const reviewerLabel = el('label', '复核人');
    const reviewer = el('input');
    reviewer.type = 'text';
    reviewer.autocomplete = 'name';
    reviewer.value = previous.reviewer || '';
    reviewerLabel.append(reviewer);
    const noteLabel = el('label', '复核备注');
    const note = el('textarea');
    note.value = previous.note || '';
    noteLabel.append(note);
    const rightsLabel = el('label', null, 'rights-confirm');
    const rights = el('input');
    rights.type = 'checkbox';
    rights.checked = previous.public_release === true;
    rightsLabel.append(rights, el('span', '已核对本卡内容及出处，可在公开网站展示'));
    const rightsNoteLabel = el('label', '公开许可依据（会随卡片公开）');
    const rightsNote = el('textarea');
    rightsNote.placeholder = '填写许可名称、权利人授权或其他可追溯依据；无法确认时请留空。';
    rightsNote.value = previous.public_rights_note || '';
    rightsNoteLabel.append(rightsNote);
    form.append(genreLabel, reviewerLabel, noteLabel, rightsLabel, rightsNoteLabel);
    const actions = el('div', null, 'review-actions');
    for (const [value, label, css] of [['reviewed','复核通过','approve'], ['correction','需要修改','correction'], ['pending','退回待复核','']]) {
      const button = el('button', label, css);
      button.type = 'button';
      button.addEventListener('click', () => {
        if (value !== 'pending' && !reviewer.value.trim()) {
          showMessage('请填写复核人。');
          reviewer.focus();
          return;
        }
        if (value === 'reviewed' && genre.value === 'unclassified') {
          showMessage('请先确认资料体裁。');
          genre.focus();
          return;
        }
        if (value === 'reviewed' && rights.checked && !rightsNote.value.trim()) {
          showMessage('公开展示前请填写可追溯的许可依据。');
          rightsNote.focus();
          return;
        }
        const old = decisions[record.id];
        if (value === 'pending') delete decisions[record.id];
        else decisions[record.id] = {id:record.id, card_sha256:record.card_sha256, status:value,
          reviewer:reviewer.value.trim(), note:note.value.trim(), reviewed_at:new Date().toISOString(),
          genre:genre.value === 'unclassified' ? null : genre.value,
          public_release:value === 'reviewed' && rights.checked,
          public_rights_note:value === 'reviewed' && rights.checked ? rightsNote.value.trim() : null};
        if (!persist()) {
          if (old) decisions[record.id] = old;
          else delete decisions[record.id];
          return;
        }
        renderList();
        renderDetail(record);
        showMessage('本条复核记录已保存。');
      });
      actions.append(button);
    }
    form.append(actions);
    detail.append(form);
  }

  function renderUnmatched() {
    showingUnmatched = true;
    selectedId = null;
    renderList();
    detail.replaceChildren(el('p', '苏格兰猎巫  /  原始数据完整性', 'metadata'),
      el('h2', `未关联史料索引 · ${data.unmatched_references.length} 条`),
      el('p', '这些 WDB_Reference 行的 CaseRef 在 WDB_Case 表中没有匹配项。保留原值，供核对数据版本和档案来源。'));
    const example = byId.get('scot_a_egd_1024');
    if (data.unmatched_references.some((row) => row.ReferenceRef === 'R/EGD/1024' && row.CaseRef === 'C/EGD/1024')
        && example?.evidence.WDB_Case?.some((row) => row.CaseRef === 'C/EGD/1035')) {
      detail.append(el('h3', '编号核对示例'));
      detail.append(el('p', '未匹配索引 R/EGD/1024 指向 C/EGD/1024；尾号相同的被告 A/EGD/1024 在调查库中实际关联 C/EGD/1035。不能仅凭数字尾号建立关联。'));
      const links = el('div', null, 'record-links');
      for (const [url, title] of [
        ['https://witches.hca.ed.ac.uk/accused/A/EGD/1024', '查看被告 A/EGD/1024'],
        ['https://witches.hca.ed.ac.uk/case/C/EGD/1035', '查看案件 C/EGD/1035'],
      ]) {
        const anchor = link(url, title);
        if (anchor) links.append(anchor);
      }
      detail.append(links);
    }
    const download = el('a', '下载未关联索引 CSV');
    download.href = './unmatched_references.csv';
    download.download = 'unmatched_references.csv';
    detail.append(download, el('pre', JSON.stringify(data.unmatched_references, null, 2)));
  }

  region.addEventListener('change', refreshBatchOptions);
  for (const field of [search, region, batch, collection, issue, status]) field.addEventListener(field === search ? 'input' : 'change', () => {
    page = 0;
    renderList();
  });
  document.getElementById('previous').addEventListener('click', () => { page -= 1; renderList(); });
  document.getElementById('next').addEventListener('click', () => { page += 1; renderList(); });
  document.getElementById('unmatched').addEventListener('click', renderUnmatched);
  document.getElementById('export-button').addEventListener('click', () => {
    const payload = {version:1, exported_at:new Date().toISOString(), decisions:Object.values(decisions)};
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type:'application/json;charset=utf-8'}));
    const anchor = el('a');
    anchor.href = url;
    anchor.download = 'astraia-review-decisions.json';
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  const importFile = document.getElementById('import-file');
  document.getElementById('import-button').addEventListener('click', () => importFile.click());
  importFile.addEventListener('change', async () => {
    try {
      const payload = JSON.parse(await importFile.files[0].text());
      if (payload.version !== 1 || !Array.isArray(payload.decisions)) throw new Error('文件格式不匹配。');
      let imported = 0;
      let skipped = 0;
      for (const entry of payload.decisions) {
        if (!byId.has(entry.id) || !['reviewed','correction'].includes(entry.status)
            || typeof entry.reviewer !== 'string' || !entry.reviewer.trim()
            || typeof entry.card_sha256 !== 'string' || typeof entry.reviewed_at !== 'string') {
          skipped += 1;
          continue;
        }
        decisions[entry.id] = entry;
        imported += 1;
      }
      if (persist()) {
        renderList();
        if (selectedId) renderDetail(byId.get(selectedId));
        showMessage(`已导入 ${imported} 条复核记录，跳过 ${skipped} 条。`);
      }
    } catch (error) {
      showMessage(`导入失败。 ${error.message}`);
    } finally {
      importFile.value = '';
    }
  });
  renderList();
})();
