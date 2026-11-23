(() => {
  'use strict';
  const hash = 'd89cdfae92dc11e8c88b1accb14ca94f8f8e22189468a63a5f17c97301b461d9';
  const columns = ['目录题名','讲述者原字段','采录地原字段','馆方类别','待核问题','候选单条页面'];
  const labels = ['目录题名','讲述者','采录地原字段','馆方类别','待核问题','单条候选'];
  const status = document.querySelector('#status'), tbody = document.querySelector('#rows');
  const search = document.querySelector('#search'), filter = document.querySelector('#filter');
  const previous = document.querySelector('#previous'), next = document.querySelector('#next'), pageLabel = document.querySelector('#page');
  let items = [], shown = [], currentPage = 0;
  const pageSize = 30;

  function parseCsv(text) {
    const rows = []; let quoted = false, field = '', row = [];
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      if (char === '"') { if (quoted && text[i+1] === '"') { field += '"'; i++; } else quoted = !quoted; }
      else if (char === ',' && !quoted) { row.push(field); field = ''; }
      else if (char === '\n' && !quoted) { row.push(field.replace(/\r$/, '')); rows.push(row); row = []; field = ''; }
      else field += char;
    }
    if (quoted || row.length || field) throw new Error('目录清单的 CSV 格式不完整。');
    return rows;
  }

  function render() {
    const pages = Math.max(1, Math.ceil(shown.length / pageSize));
    currentPage = Math.min(currentPage, pages - 1);
    tbody.replaceChildren();
    for (const item of shown.slice(currentPage * pageSize, (currentPage + 1) * pageSize)) {
      const row = document.createElement('tr');
      for (const [index, name] of columns.entries()) {
        const cell = document.createElement('td'), value = item[name];
        cell.dataset.label = labels[index];
        if (name === '候选单条页面' && value) {
          const link = document.createElement('a'); link.href = value; link.target = '_blank';
          link.rel = 'noopener noreferrer'; link.textContent = '待核链接 ↗'; cell.append(link);
        } else cell.textContent = value || '—';
        row.append(cell);
      }
      tbody.append(row);
    }
    status.textContent = `符合 ${shown.length.toLocaleString('zh-CN')} 行 / 目录 ${items.length.toLocaleString('zh-CN')} 行 · 尚未入库`;
    pageLabel.textContent = `${currentPage + 1} / ${pages}`;
    previous.disabled = currentPage === 0; next.disabled = currentPage + 1 >= pages;
  }

  function applyFilter() {
    const query = search.value.trim().toLocaleLowerCase(), mode = filter.value;
    shown = items.filter(item => {
      const matchesText = !query || ['目录题名','讲述者原字段','采录地原字段','馆方类别','文本字段原值']
        .some(key => item[key].toLocaleLowerCase().includes(query));
      const matchesFilter = mode === 'all' || (mode === 'duplicates' && !!item['字段完全相同的行数']) ||
        (mode === 'speaker' && !item['讲述者原字段'].trim()) || (mode === 'text' && !item['文本字段原值'].trim()) ||
        (mode === 'candidate' && !!item['候选单条页面']) || (mode === 'unlinked' && !item['候选单条页面']);
      return matchesText && matchesFilter;
    });
    currentPage = 0; render();
  }

  async function start() {
    const fontError = '缺少 Microsoft YaHei 或 Malgun Gothic 的常规 / 粗体字体；请安装字体后重新打开。 Required fonts: Microsoft YaHei and Malgun Gothic (regular and bold).';
    let faces;
    try {
      faces = await Promise.all([
        document.fonts.load('400 16px "Astraia CJK"', '中文'),
        document.fonts.load('700 16px "Astraia CJK"', '中文'),
        document.fonts.load('400 16px "Astraia Korean"', '한글金'),
        document.fonts.load('700 16px "Astraia Korean"', '한글金'),
      ]);
    } catch { throw new Error(fontError); }
    if (faces.some(result => !result.length)) throw new Error(fontError);
    const response = await fetch('./korea_aks_oral_review_inventory.csv');
    if (!response.ok) throw new Error('无法读取目录清单，请先确认本地文件存在。');
    const bytes = await response.arrayBuffer();
    const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(value => value.toString(16).padStart(2,'0')).join('');
    if (digest !== hash) throw new Error('目录清单与已记录的快照哈希不一致，请重新核对来源。');
    const csv = parseCsv(new TextDecoder('utf-8', {fatal:true}).decode(bytes).replace(/^\ufeff/,''));
    const header = csv.shift();
    if (!header || csv.length !== 22836 || [...columns,'字段完全相同的行数','文本字段原值'].some(name => !header.includes(name)) ||
        csv.some(row => row.length !== header.length)) throw new Error('目录清单的字段或行数与快照不符。');
    items = csv.map(row => Object.fromEntries(header.map((name,index) => [name,row[index]])));
    applyFilter();
  }

  search.addEventListener('input',applyFilter); filter.addEventListener('change',applyFilter);
  previous.addEventListener('click',() => { currentPage--; render(); });
  next.addEventListener('click',() => { currentPage++; render(); });
  start().catch(error => { status.classList.add('error'); status.textContent = `无法显示清单：${error.message}`; });
})();
