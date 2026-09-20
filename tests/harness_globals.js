const vm = require('vm'); const fs = require('fs');
function makeWindow() {
  const noop = () => {};
  const el = { style:{}, classList:{add:noop,remove:noop,toggle:noop,contains:()=>false},
               addEventListener:noop, setAttribute:noop, getAttribute:()=>null, appendChild:noop,
               insertBefore:noop, focus:noop, select:noop, textContent:'', innerHTML:'', value:'' };
  const document = { readyState:'complete', addEventListener:noop, removeEventListener:noop,
    getElementById:()=>el, querySelector:()=>el, querySelectorAll:()=>[], createElement:()=>el,
    body:el, documentElement:el, visibilityState:'visible' };
  const store = {};
  const storage = { getItem:k=>store[k]??null, setItem:(k,v)=>{store[k]=String(v)}, removeItem:k=>{delete store[k]} };
  const win = { document, localStorage:storage, sessionStorage:storage,
    fetch: async () => ({ ok:true, status:200, json: async()=>[], text: async()=>'' }),
    setTimeout, clearTimeout, setInterval, clearInterval, navigator:{}, alert:noop, confirm:()=>true,
    addEventListener:noop, removeEventListener:noop, Telegram: undefined, console };
  win.window = win; win.globalThis = win;
  return win;
}
const ctx = vm.createContext(makeWindow());
const files = ['logger.js','telegram.js','api.js','avatars.js','pull_refresh.js','dossier.js','views.js','modals.js','app.js'];
for (const f of files) {
  try { vm.runInContext(fs.readFileSync(f,'utf8'), ctx, {filename:f}); }
  catch(e){ console.log('THROW in', f, '->', e.message); }
}
const check = ['API','Views','Modals','TGBridge','Dossier','PullRefresh','AvatarRenderer','App','MHLog','escapeHtml','safeUrl'];
const res = {};
for (const k of check) res[k] = vm.runInContext(`typeof window.${k}`, ctx);
console.log(JSON.stringify(res, null, 1));
