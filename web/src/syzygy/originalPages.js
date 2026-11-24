const hashPattern = /^[a-f0-9]{64}$/;
const manifests = new Map();

async function loadManifest(root, bookHash) {
  if (!hashPattern.test(bookHash ?? '')) throw new Error('原书版本无效。');
  const key=`${root}:${bookHash}`;
  if (!manifests.has(key)) {
    const pending=(async()=>{
      const response=await fetch(`${root}knowledge/pages/manifest.json`,{cache:'no-cache'});
      if (!response.ok) throw new Error('原典页图暂不可用，请使用“打开原书”。');
      const manifest=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await response.arrayBuffer()));
      if (manifest.schema_version !== 1 || manifest.book_sha256 !== bookHash || !hashPattern.test(manifest.pdf_sha256 ?? '')
        || !Array.isArray(manifest.pages) || manifest.pages.length !== manifest.page_count
        || !manifest.pages.every((page,index)=>page.page === index + 1 && /^p\d{4}-[a-f0-9]{16}\.webp$/.test(page.file ?? '')
          && page.file.startsWith(`p${String(index + 1).padStart(4,'0')}-`)
          && hashPattern.test(page.sha256 ?? '') && page.file.includes(page.sha256.slice(0,16)))) throw new Error('原典页图与原书版本不一致。');
      return manifest;
    })().catch(error=>{manifests.delete(key);throw error;});
    manifests.set(key,pending);
  }
  return manifests.get(key);
}

export function originalPageButton(page) {
  return Number.isInteger(page) && page > 0 ? `<button type="button" class="ctl-btn" data-original-page="${page}">展开原典图文</button>` : '';
}

export function bindOriginalPages(container, root, book) {
  container.querySelectorAll('[data-original-page]').forEach(button=>button.addEventListener('click',()=>{
    const dialog=document.createElement('dialog'); dialog.className='syzygy-original-dialog'; dialog.setAttribute('aria-label','原典图文');
    dialog.innerHTML='<div class="syzygy-original-head"><strong>《格物识微》原典图文</strong><button type="button" data-close>关闭 ×</button></div>'
      + '<div class="syzygy-original-nav"><button type="button" data-prev>← 上一页</button><label>PDF 页码 <input type="number" min="1" inputmode="numeric" data-number></label><button type="button" data-go>转到</button><button type="button" data-next>下一页 →</button><span data-total></span></div>'
      + '<p class="syzygy-reference" data-status role="status">正在读取原典页图…</p><img data-image alt="原书页面" hidden>';
    document.body.append(dialog); dialog.showModal();
    const status=dialog.querySelector('[data-status]'), image=dialog.querySelector('[data-image]'), number=dialog.querySelector('[data-number]');
    const prev=dialog.querySelector('[data-prev]'), next=dialog.querySelector('[data-next]');
    let current=Number(button.dataset.originalPage), manifest=null, objectURL=null, request=0;
    async function show(page) {
      const serial=++request; status.textContent='正在读取原典页图…'; image.hidden=true;
      try {
        manifest ??= await loadManifest(root,book.data_sha256);
        if (serial !== request || !dialog.isConnected) return;
        current=Math.max(1,Math.min(manifest.page_count,Math.trunc(Number(page)) || 1));
        number.value=String(current); number.max=String(manifest.page_count);
        dialog.querySelector('[data-total]').textContent=`/ ${manifest.page_count}`;
        prev.disabled=current === 1; next.disabled=current === manifest.page_count;
        const item=manifest.pages[current-1], response=await fetch(`${root}knowledge/pages/${item.file}`);
        if (!response.ok) throw new Error('页图读取失败。');
        const bytes=await response.arrayBuffer();
        if (!globalThis.crypto?.subtle) throw new Error('当前浏览器无法校验页图，请使用安全连接。');
        const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
        if (hash !== item.sha256) throw new Error('原典页图校验失败。');
        if (serial !== request || !dialog.isConnected) return;
        if (objectURL) URL.revokeObjectURL(objectURL);
        objectURL=URL.createObjectURL(new Blob([bytes],{type:'image/webp'}));
        image.src=objectURL; image.alt=`《格物识微》PDF 第 ${current} 页`; image.hidden=false;
        status.textContent=`原版 PDF 第 ${current} 页 · 可逐页翻阅`;
      } catch (error) { if (serial === request && dialog.isConnected) status.textContent=error.message; }
    }
    dialog.querySelector('[data-close]').addEventListener('click',()=>dialog.close());
    prev.addEventListener('click',()=>show(current-1)); next.addEventListener('click',()=>show(current+1));
    dialog.querySelector('[data-go]').addEventListener('click',()=>show(number.value));
    number.addEventListener('keydown',event=>{if(event.key === 'Enter'){event.preventDefault();show(number.value);}});
    dialog.addEventListener('click',event=>{if(event.target === dialog) dialog.close();});
    dialog.addEventListener('close',()=>{request++;if(objectURL)URL.revokeObjectURL(objectURL);dialog.remove();if(button.isConnected)button.focus();},{once:true});
    show(current);
  }));
}
