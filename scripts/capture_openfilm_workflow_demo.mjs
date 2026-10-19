// Original controlled test application, captured after actual browser actions.
import {createInterface} from 'node:readline';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const lines=createInterface({input:process.stdin,crlfDelay:Infinity})[Symbol.asyncIterator]();
let browser,context,page,result={status:'running',pages_opened:0,pages_closed:0,external_requests:[],actions:[],frames:[]};
try {
  const first=await lines.next();if(first.done)throw Error('request required');
  const request=JSON.parse(first.value);
  const {chromium}=await import(pathToFileURL(resolve(request.playwright,'index.mjs')).href);
  mkdirSync(request.frames,{recursive:true});
  browser=await chromium.launch({executablePath:request.chromium,headless:true,args:[
    '--disable-gpu','--disable-background-networking','--disable-component-update','--disable-sync',
    '--no-first-run','--no-proxy-server','--host-resolver-rules=MAP * ~NOTFOUND',
    '--force-color-profile=srgb','--disable-features=MediaRouter,OptimizationHints,Translate']});
  context=await browser.newContext({viewport:{width:640,height:360},deviceScaleFactor:1,serviceWorkers:'block',acceptDownloads:false});
  await context.route('**/*',route=>{result.external_requests.push(route.request().url());return route.abort('blockedbyclient')});
  await context.routeWebSocket('**/*',socket=>socket.close());
  page=await context.newPage();result.pages_opened++;
  const embedded=readFileSync(request.font).toString('base64');
  const html=`<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; font-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'"><style>
  @font-face{font-family:fixture;src:url(data:font/ttf;base64,${embedded})}*{box-sizing:border-box}body{margin:0;background:#101b2d;color:#edf4ff;font-family:fixture}header{height:72px;padding:16px 22px;background:#20324b}h1{font-size:18px;margin:0 0 6px}small{font-size:11px;color:#c0d3ed}main{display:grid;grid-template-columns:240px 1fr;gap:18px;margin:18px 22px}section{padding:16px;border-radius:12px;background:#20324b}h2{font-size:15px;margin:0 0 12px}button,input{font:14px fixture;width:100%;border:0;border-radius:6px;padding:12px;margin:0 0 12px}button{color:#fff;background:#2e75a8;cursor:pointer}button.selected{background:#226e52}input{background:#e8eff8;color:#12243a}#status{font-size:14px;line-height:1.6;padding:14px;background:#162539;border-radius:8px}#preview{margin-top:12px;padding:18px;background:#6136a6;border-radius:8px;font-size:16px}footer{margin:0 22px;color:#b2c7e0;font-size:11px}</style></head><body><header><h1>LOCAL CAMPAIGN PLANNER</h1><small>CONTROLLED ORIGINAL TEST APP / NO EDITOR GUI CLAIM</small></header><main><section><h2>1. Configure a plan</h2><button id="select">Select local campaign</button><input id="headline" aria-label="Headline" value="DRAFT"><button id="previewButton">Preview headline</button></section><section><h2>2. Review the result</h2><div id="status">No campaign selected.</div><div id="preview" hidden></div><button id="save" style="margin-top:14px">Save plan in this page</button></section></main><footer>All fields are fixture data. Nothing is sent or downloaded.</footer><script>
  window.state={selected:false,preview:false,saved:false};
  select.onclick=()=>{state.selected=true;select.classList.add('selected');document.getElementById('status').textContent='Campaign: local launch'};
  previewButton.onclick=()=>{state.preview=true;document.getElementById('preview').hidden=false;document.getElementById('preview').textContent=headline.value;document.getElementById('status').textContent='Preview ready: '+headline.value};
  save.onclick=()=>{if(!state.selected||!state.preview)throw Error('complete the plan first');state.saved=true;document.getElementById('status').textContent='Plan saved locally in page state.';save.classList.add('selected')};
  </script></body></html>`;
  writeFileSync(request.html,html);
  await page.setContent(html,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);
  const sequence=new Map([[8,['select','click']],[16,['headline','fill']],[24,['previewButton','click']],[32,['save','click']]]);
  for(let n=0;n<48;n++){
    if(sequence.has(n)){
      const [id,kind]=sequence.get(n),element=page.locator('#'+id),box=await element.boundingBox();
      if(kind==='fill')await element.fill('OPEN LOCAL VIDEO');else await element.click();
      result.actions.push({source_frame:n,source_tick:n*11250,element_id:id,action:kind,
        bounding_box:box,state:await page.evaluate(()=>({...state,headline:headline.value,status:document.getElementById('status').textContent}))});
    }
    await page.screenshot({path:resolve(request.frames,String(n).padStart(3,'0')+'.png'),animations:'disabled'});
    result.frames.push({index:n,state:await page.evaluate(()=>({...state,headline:headline.value}))});
  }
  if(!(await page.evaluate(()=>state.saved)))throw Error('real save action did not complete');
  if(result.external_requests.length)throw Error('unexpected external request attempted');
  result.status='passed_original_test_app_action_capture';result.browser_closed=false;
}catch(error){result.status='failed';result.error=String(error.stack||error)}
finally{
  if(page){await page.close().catch(()=>{});result.pages_closed++}
  if(context)await context.close().catch(()=>{});
  if(browser){await browser.close().catch(()=>{});result.browser_closed=!browser.isConnected()}
  process.stdout.write(JSON.stringify(result)+'\n');
}
process.exit(result.status==='passed_original_test_app_action_capture'?0:1);
