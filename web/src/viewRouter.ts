/** Keep the existing classic and Syzygy renderers alive while switching views. */
type Mode = 'classic' | 'syzygy';
type RouteMessage = { type: 'astraia:navigate' | 'astraia:state' | 'astraia:ready' | 'astraia:visibility'; url?: string; active?: boolean };
const origin = window.location.origin;
const base = new URL(import.meta.env.BASE_URL, origin).pathname.replace(/\/?$/, '/');
const embedded = window.parent !== window && window.name === 'astraia-view';
const modeOf = (url: URL): Mode | null => url.origin !== origin ? null
  : [base, `${base}index.html`].includes(url.pathname) ? 'classic'
  : [`${base}syzygy/`, `${base}syzygy/index.html`].includes(url.pathname) ? 'syzygy' : null;
const hostMode = modeOf(new URL(location.href));
const replace = history.replaceState.bind(history);
const push = history.pushState.bind(history);
let initialized = false, ready = false, pending: string | null = null;

function active(value: boolean) {
  document.documentElement.dataset.astraiaActive = String(value);
  window.dispatchEvent(new CustomEvent('astraia:visibility', { detail: value }));
}
function dispatch(url: string) { window.dispatchEvent(new CustomEvent('astraia:navigate', { detail: url })); }
function sendParent(message: RouteMessage) { if (embedded) window.parent.postMessage(message, origin); }

export function announceViewReady() {
  ready = true;
  if (pending) { const url = pending; pending = null; dispatch(url); }
  sendParent({type:'astraia:ready'});
}

export function initViewRouter() {
  if (initialized || !hostMode) return;
  initialized = true; active(true);
  if (embedded) window.addEventListener('load',()=>{ if (ready) sendParent({type:'astraia:ready'}); },{once:true});
  let frame: HTMLIFrameElement | null = null, frameReady = false, shown = false, desired: string | null = null;
  history.replaceState = (data: unknown, unused: string, url?: string | URL | null) => {
    // A hidden parent must not overwrite the active child's address.
    if (!embedded && shown) return;
    replace(data,unused,url);
    if (embedded) sendParent({type:'astraia:state',url:location.href});
  };
  const sendFrame = (message: RouteMessage) => frame?.contentWindow?.postMessage(message,origin);
  const ensureFrame = (url: string) => {
    if (frame) return;
    frame = document.createElement('iframe'); frame.name = 'astraia-view'; frame.title = 'Astraia 图谱视图';
    Object.assign(frame.style, {position:'fixed',inset:'0',width:'100%',height:'100%',border:'0',zIndex:'10000',background:'#080d18'});
    frame.src=url;
    frame.addEventListener('load',()=>{frameReady=false;});
    document.body.append(frame);
  };
  const switchTo = (href: string, addHistory: boolean) => {
    const target=new URL(href,location.href), mode=modeOf(target);
    if (!mode) return;
    if (addHistory) push({astraiaView:true},'',target.href);
    if (mode === hostMode) {
      shown=false; desired=null;
      if (frame) { frame.hidden=true; sendFrame({type:'astraia:visibility',active:false}); }
      active(true); dispatch(target.href);
    } else {
      shown=true; desired=target.href; active(false);
      ensureFrame(target.href);
      if (frame) frame.hidden=false;
      if (frameReady) { sendFrame({type:'astraia:visibility',active:true}); sendFrame({type:'astraia:navigate',url:target.href}); }
    }
  };
  document.addEventListener('click',event=>{
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const target=event.target instanceof Element ? event.target.closest('a[href]') : null;
    if (!(target instanceof HTMLAnchorElement) || target.hasAttribute('download') || (target.target && target.target !== '_self')) return;
    const destination=new URL(target.href,location.href), mode=modeOf(destination);
    if (!mode || mode === hostMode) return;
    event.preventDefault();
    if (embedded) sendParent({type:'astraia:navigate',url:destination.href});
    else switchTo(destination.href,true);
  },true);
  window.addEventListener('message',event=>{
    const message=event.data as RouteMessage | null;
    if (event.origin !== origin || !message || typeof message.type !== 'string') return;
    if (embedded && event.source === window.parent) {
      if (message.type === 'astraia:visibility') active(message.active === true);
      if (message.type === 'astraia:navigate' && typeof message.url === 'string') {
        const target=new URL(message.url,location.href);
        if (modeOf(target) !== hostMode) return;
        replace(history.state,'',target.href);
        if (ready) dispatch(target.href); else pending=target.href;
      }
      return;
    }
    if (!embedded && frame && event.source === frame.contentWindow) {
      if (message.type === 'astraia:ready') {
        frameReady=true;
        sendFrame({type:'astraia:visibility',active:shown});
        if (shown && desired) sendFrame({type:'astraia:navigate',url:desired});
      }
      if (message.type === 'astraia:navigate' && typeof message.url === 'string') {
        const target=new URL(message.url,location.href);
        if (modeOf(target) === hostMode) switchTo(target.href,true);
      }
      if (message.type === 'astraia:state' && shown && typeof message.url === 'string') {
        const target=new URL(message.url,location.href);
        if (modeOf(target) && modeOf(target) !== hostMode) { desired=target.href; replace(history.state,'',target.href); }
      }
    }
  });
  if (!embedded) window.addEventListener('popstate',()=>switchTo(location.href,false));
}
