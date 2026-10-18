// Agent Video Kit offline host with pinned MIT clock and DOM override functions.
import {createInterface} from 'node:readline';
import {readFileSync, realpathSync} from 'node:fs';
import {resolve, sep, extname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
import {FILM_CLOCK} from './openfilm_frame_clock.mjs';
import {TEMPLATE_DOM} from './html_template_dom.mjs';
const TEMPLATE_HOST = '(()=>{\n'+['openfilm_template_fields.mjs','openfilm_overrides.mjs'].map(name =>
  readFileSync(new URL(name, import.meta.url), 'utf8').replace(/^export /gm, '')).join('\n')+'\n'+TEMPLATE_DOM+'\n})();';

const lines = createInterface({input: process.stdin, crlfDelay: Infinity})[Symbol.asyncIterator]();
const send = async value => { if (!process.stdout.write(JSON.stringify(value)+'\n')) await once(process.stdout, 'drain'); };
const sha = bytes => 'sha256:'+createHash('sha256').update(bytes).digest('hex');
const problem = (code, message) => Object.assign(new Error(message), {code});
let browser, contexts = [], receipt = {pages_opened: 0, pages_closed: 0, local_requests: 0, denied_requests: 0};
let outcome, failure;
try {
  // Parent assigns the waiting Node process to a native Job before sending input.
  const first = await lines.next();
  if (first.done) throw problem('HTML_PROTOCOL_INVALID', 'Missing request');
  const request = JSON.parse(first.value);
  const {chromium} = await import(pathToFileURL(resolve(request.playwright, 'index.mjs')).href);
  const root = realpathSync(request.root), files = new Map();
  const types = {'.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8',
    '.mjs':'text/javascript; charset=utf-8', '.json':'application/json', '.svg':'image/svg+xml', '.png':'image/png',
    '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.webp':'image/webp', '.ttf':'font/ttf', '.otf':'font/otf', '.woff':'font/woff', '.woff2':'font/woff2'};
  for (const item of request.files) {
    const file = realpathSync(resolve(root, item.path));
    if (!file.startsWith(root+sep)) throw problem('HTML_RESOURCE_INVALID', 'File escaped source root');
    const body = readFileSync(file);
    if (sha(body) !== item.sha256) throw problem('HTML_RESOURCE_CHANGED', 'Source file hash changed');
    files.set('/'+item.path, {body, type: types[extname(item.path).toLowerCase()] ?? 'application/octet-stream'});
  }
  const origin = 'http://agent-video-kit.invalid'; // synthetic route, no DNS/server/listening socket
  const spec = request.spec, params = request.params, frameCount = request.frame_count;
  browser = await chromium.launch({executablePath: request.chromium, headless:true, timeout:15000,
    args:['--disable-gpu', '--disable-background-networking', '--disable-component-update', '--disable-sync', '--log-file='+request.log_file,
      '--no-first-run', '--metrics-recording-only', '--no-proxy-server', '--host-resolver-rules=MAP * ~NOTFOUND',
      '--force-color-profile=srgb', '--disable-features=MediaRouter,OptimizationHints,Translate',
      '--force-webrtc-ip-handling-policy=disable_non_proxied_udp']});

  async function pageForPass() {
    const errors = [];
    const note = (code, message) => { if (errors.length < 30) errors.push({code, message:String(message).slice(0,1000)}); };
    const context = await browser.newContext({viewport:{width:spec.width, height:spec.height}, deviceScaleFactor:1,
      serviceWorkers:'block', locale:'en-US', timezoneId:'UTC', reducedMotion:'no-preference', colorScheme:'light',
      acceptDownloads:false, bypassCSP:false});
    contexts.push(context);
    await context.route('**/*', async route => {
      receipt.local_requests++;
      const req = route.request(), url = new URL(req.url());
      let path;
      try {path = decodeURIComponent(url.pathname);} catch {path = '';}
      const allowed = url.origin === origin && req.method() === 'GET' && !url.search && files.has(path)
        && (!req.isNavigationRequest() || (req.frame() === context.pages()[0]?.mainFrame() && path === '/'+spec.entry))
        && receipt.local_requests <= 10000;
      if (!allowed) {
        receipt.denied_requests++;
        note('HTML_REQUEST_DENIED', 'Unlisted/external request '+sha(Buffer.from(req.url())));
        return route.abort('blockedbyclient');
      }
      const item = files.get(path);
      return route.fulfill({status:200, contentType:item.type, body:item.body, headers:{
        'Content-Security-Policy': "default-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'none'; frame-src 'none'; object-src 'none'; media-src 'none'; base-uri 'self'",
        'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'}});
    });
    await context.routeWebSocket('**/*', socket => {note('HTML_REQUEST_DENIED', 'WebSocket denied'); socket.close();});
    await context.exposeBinding('__motionDenied', (_source, kind) => {note('HTML_FEATURE_DENIED', kind);});
    await context.addInitScript({content:`window.filmHost={version:'0.1',name:'agent-video-kit'};\n${FILM_CLOCK}\n`+
      `window.motionParams=Object.freeze(${JSON.stringify(params)});\n`+
      `(()=>{const deny=k=>function(){window.__motionDenied(k);throw new Error(k+' disabled in local HTML motion')};
      for(const k of ['WebSocket','WebTransport','Worker','SharedWorker','RTCPeerConnection','webkitRTCPeerConnection','EventSource']){
        try{Object.defineProperty(window,k,{value:deny(k),writable:false,configurable:false})}catch{}}
      window.open=deny('popup');navigator.sendBeacon=deny('beacon');
      for(const proto of [HTMLCanvasElement.prototype,typeof OffscreenCanvas==='function'?OffscreenCanvas.prototype:null]){
        if(!proto)continue;const get=proto.getContext;proto.getContext=function(kind,...args){
          if(String(kind).includes('webgl')||String(kind)==='webgpu')return deny('WebGL/WebGPU')();return get.call(this,kind,...args)}}
      })();`});
    const page = await context.newPage();
    receipt.pages_opened++;
    page.on('pageerror', e => note('HTML_PAGE_ERROR', e.message));
    page.on('console', m => {if (m.type()==='error') note('HTML_PAGE_ERROR', m.text());});
    page.on('popup', p => {note('HTML_FEATURE_DENIED','popup'); void p.close();});
    page.on('download', d => {note('HTML_FEATURE_DENIED','download'); void d.cancel();});
    page.on('framenavigated', frame => {if(frame!==page.mainFrame())note('HTML_FEATURE_DENIED','subframe');});
    const cdp = await context.newCDPSession(page);
    await cdp.send('Emulation.setDefaultBackgroundColorOverride',{color:{r:0,g:0,b:0,a:0}});
    await page.goto(origin+'/'+spec.entry,{waitUntil:'load',timeout:request.frame_timeout_ms});
    await page.waitForFunction(()=>typeof window.film?.frame==='function', null,{timeout:request.frame_timeout_ms});
    await limited(page.evaluate(async () => {
      await (typeof window.film.ready==='function' ? window.film.ready() : window.film.ready);
      await document.fonts.ready;
      return true;
    }), request.frame_timeout_ms);
    const meta = await page.evaluate(()=>({width:window.film.width,height:window.film.height,duration:window.film.duration}));
    for (const [key, value] of Object.entries(meta)) {
      const expected = key==='duration'?spec.duration_tick/request.ticks_per_second:spec[key];
      if (value!=null && (!Number.isFinite(value) || Math.abs(value-expected)>1e-8))
        throw problem('HTML_META_MISMATCH','Page '+key+' differs from manifest');
    }
    function requireClean() { if(errors.length) throw problem(errors[0].code,JSON.stringify(errors)); }
    requireClean();
    await page.addScriptTag({content:TEMPLATE_HOST});
    return {context, page, requireClean};
  }

  async function limited(promise, ms) {
    let timer;
    try {return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(problem('HTML_FRAME_TIMEOUT','Page/frame timeout')),ms);})]);}
    finally {clearTimeout(timer);}
  }
  async function draw(host, index) {
    const t = index*spec.fps.den/spec.fps.num;
    const template = await limited(host.page.evaluate(async ({t, params, overrides, collect}) => {
      if(document.querySelector('iframe,frame,video,audio,object,embed'))throw new Error('Media/subframe tags are unsupported');
      window.__agentVideoTemplate.restore();
      window.filmHost.time(t);
      await window.film.frame(t, params);
      window.filmHost.settle(t);
      await document.fonts.ready;
      const controls = collect ? window.__agentVideoTemplate.collect() : null;
      const applied = await window.__agentVideoTemplate.apply(overrides);
      await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      return {controls, applied, effective_controls:collect ? window.__agentVideoTemplate.collect() : null};
    },{t,params,overrides:request.overrides || [],collect:request.task === 'controls' || index === 0}),request.frame_timeout_ms);
    host.requireClean();
    const png = await host.page.screenshot({type:'png',omitBackground:true,timeout:request.frame_timeout_ms,scale:'css'});
    host.requireClean();
    return {png, hash:sha(png), ...template};
  }
  async function closePage(host) {
    await host.context.close();
    contexts=contexts.filter(c=>c!==host.context);
    receipt.pages_closed++;
  }
  if(request.task === 'controls') {
    const samples = [];
    for(let pass=0;pass<2;pass++) {
      const host = await pageForPass();
      const {hash, controls, applied, effective_controls} = await draw(host, request.sample_frame_index);
      samples.push({sha256:hash, controls, applied, effective_controls}); await closePage(host);
    }
    if(JSON.stringify(samples[0]) !== JSON.stringify(samples[1]))
      throw problem('HTML_FRAME_NONDETERMINISTIC','Template inspection differs between fresh contexts');
    outcome = {inspection_only:true, sample_frame_index:request.sample_frame_index, sample:samples[0],
      fresh_contexts_equal:true, browser_version:browser.version()};
  } else {
  const hashes = []; let controls, applied, effective_controls;
  const primary = await pageForPass();
  await send({type:'ready',page_opened:true});
  for(let i=0;i<frameCount;i++) {
    const value=await draw(primary,i); const {png,hash}=value;hashes.push(hash);
    if(i === 0) {controls=value.controls; applied=value.applied; effective_controls=value.effective_controls;}
    await send({type:'frame',index:i,sha256:hash,png:png.toString('base64')});
    const ack=await lines.next();
    if(ack.done||JSON.parse(ack.value).ack!==i)throw problem('HTML_PROTOCOL_INVALID','Missing frame acknowledgement');
  }
  await closePage(primary);
  const reverse=Array.from({length:frameCount},(_,i)=>frameCount-1-i);
  const parity=[...Array.from({length:frameCount},(_,i)=>i).filter(i=>i%2),...Array.from({length:frameCount},(_,i)=>i).filter(i=>!(i%2)).reverse()];
  const verification=[];
  for (const [name,order] of [['reverse',reverse],['odd_then_reverse_even',parity]]) {
    const host=await pageForPass(), observed=[];
    for(const i of order){
      const {hash}=await draw(host,i);observed.push({index:i,sha256:hash});
      if(hash!==hashes[i])throw problem('HTML_FRAME_NONDETERMINISTIC','Frame differs on fresh-context '+name+' pass at '+i);
    }
    await closePage(host);
    verification.push({name,frames:observed});
  }
  outcome={frame_hashes:hashes,verification,browser_version:browser.version(),all_frame_orders_equal:true,
    template_controls:controls, template_applied:applied, effective_template_controls:effective_controls};
  }
} catch(error) {
  const templateCode = /\b(HTML_OVERRIDE_[A-Z_]+|HTML_CONTROL_BUDGET)\b/.exec(String(error.message))?.[1];
  failure={code:error.code??templateCode??'HTML_WORKER_FAILED',message:'HTML worker diagnostic; '+String(error.message).replace(/(?:https?|wss?):\/\/[^\s"'<>]+/g, value=>sha(Buffer.from(value))).slice(0,6000)};
} finally {
  for(const context of contexts){try{await context.close();receipt.pages_closed++;}catch{}}
  try{if(browser)await browser.close();receipt.browser_closed=true;}catch{receipt.browser_closed=false;}
  await send(failure?{type:'error',...failure,cleanup:receipt}:{type:'done',...outcome,cleanup:receipt});
  process.stdin.destroy();
}
