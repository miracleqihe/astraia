(() => {
  'use strict';
  const filename='korea_aks_dobong_detail_review_2026-11-23.csv';
  const hash='698263e776654508ffdc75f85108d15d26ddd6a82e5b348c1848f8a5927d4f33';
  const columns=['目录题名','馆方检索题名','目录讲述者','目录采录地原字段','馆方详情采录地点',
                 '馆方调查日期（非叙事年代）','待核问题','候选单条页面'];
  const labels=['目录题名','馆方检索题名','讲述者','目录采录地','馆方详情采录地','调查日期','待核问题','单条候选'];
  const status=document.querySelector('#status'),tbody=document.querySelector('#rows');
  const search=document.querySelector('#search'),filter=document.querySelector('#filter');
  const previous=document.querySelector('#previous'),next=document.querySelector('#next'),pageLabel=document.querySelector('#page');
  let items=[],shown=[],currentPage=0;const pageSize=20;

  function parseCsv(text) {
    const rows=[];let quoted=false,field='',row=[];
    for(let i=0;i<text.length;i++){
      const char=text[i];
      if(char==='"'){if(quoted&&text[i+1]==='"'){field+='"';i++;}else quoted=!quoted;}
      else if(char===','&&!quoted){row.push(field);field='';}
      else if(char==='\n'&&!quoted){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}
      else field+=char;
    }
    if(quoted||row.length||field)throw new Error('对照清单的 CSV 格式不完整。');
    return rows;
  }
  function render(){
    const pages=Math.max(1,Math.ceil(shown.length/pageSize));currentPage=Math.min(currentPage,pages-1);
    tbody.replaceChildren();
    for(const item of shown.slice(currentPage*pageSize,(currentPage+1)*pageSize)){
      const row=document.createElement('tr');
      for(const [index,name] of columns.entries()){
        const cell=document.createElement('td'),value=item[name]||'';cell.dataset.label=labels[index];
        if(name==='候选单条页面'&&value){
          const url=new URL(value);
          if(url.protocol!=='https:'||url.hostname!=='kdp.aks.ac.kr'||url.pathname!=='/inde/gubi')throw new Error('候选链接与馆方地址不符。');
          const link=document.createElement('a');link.href=value;link.target='_blank';link.rel='noopener noreferrer';link.textContent='待核链接 ↗';cell.append(link);
        } else if(name==='馆方详情采录地点'&&!value&&item['候选单条页面'])cell.textContent='尚未回查';
        else cell.textContent=value||'—';
        row.append(cell);
      }
      tbody.append(row);
    }
    status.textContent=`显示 ${shown.length.toLocaleString('zh-CN')} 对照行 / 原目录 172 行 · 尚未签核`;
    pageLabel.textContent=`${currentPage+1} / ${pages}`;previous.disabled=currentPage===0;next.disabled=currentPage+1>=pages;
  }
  function applyFilter(){
    const query=search.value.trim().toLocaleLowerCase(),mode=filter.value;
    shown=items.filter(item=>{
      const matchesText=!query||['目录题名','馆方检索题名','目录讲述者','馆方编号','目录采录地原字段']
        .some(key=>(item[key]||'').toLocaleLowerCase().includes(query));
      const candidate=!!item['候选单条页面'];
      const matchesFilter=mode==='all'||(mode==='candidate'&&candidate)||(mode==='unmatched'&&!candidate)||
        (mode==='similar'&&item['题名对照方式']==='相似待核')||
        (mode==='ambiguous'&&(Number(item['候选数'])>1||Number(item['该馆方记录的目录候选数'])>1))||
        (mode==='place'&&(item['目录与详情采录地点']==='不同'||item['目录与详情采录地点']==='无法比较'));
      return matchesText&&matchesFilter;
    });currentPage=0;render();
  }
  async function start(){
    const fontError='缺少 Microsoft YaHei 或 Malgun Gothic 的常规 / 粗体字体；请安装字体后重新打开。 Required fonts: Microsoft YaHei and Malgun Gothic (regular and bold).';
    let faces;try{faces=await Promise.all([
      document.fonts.load('400 16px "Astraia CJK"','中文'),document.fonts.load('700 16px "Astraia CJK"','中文'),
      document.fonts.load('400 16px "Astraia Korean"','한글金'),document.fonts.load('700 16px "Astraia Korean"','한글金')]);}
    catch{throw new Error(fontError);}
    if(faces.some(face=>!face.length))throw new Error(fontError);
    const response=await fetch(`./${filename}`);if(!response.ok)throw new Error('无法读取来源对照清单。');
    const bytes=await response.arrayBuffer();
    const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
    if(digest!==hash)throw new Error('对照清单与已记录的快照哈希不一致，请重新核对来源。');
    const csv=parseCsv(new TextDecoder('utf-8',{fatal:true}).decode(bytes).replace(/^\ufeff/,'')),header=csv.shift();
    if(!header||csv.length!==174||['目录数据行序号','目录题名','馆方检索题名','目录讲述者','目录采录地原字段',
       '馆方编号','候选数','该馆方记录的目录候选数','候选单条页面','待核问题','馆方详情采录地点','目录与详情采录地点'].some(name=>!header.includes(name))||
       csv.some(row=>row.length!==header.length))throw new Error('对照清单的字段或行数与快照不符。');
    if(!header.includes('目录与详情采录地点')){
      const option=filter.querySelector('option[value="place"]');option.disabled=true;option.textContent='采录地点待核（详情采集后）';
    }
    items=csv.map(row=>Object.fromEntries(header.map((name,index)=>[name,row[index]])));applyFilter();
  }
  search.addEventListener('input',applyFilter);filter.addEventListener('change',applyFilter);
  previous.addEventListener('click',()=>{currentPage--;render()});next.addEventListener('click',()=>{currentPage++;render()});
  start().catch(error=>{status.classList.add('error');status.textContent=`无法显示清单：${error.message}`;});
})();
