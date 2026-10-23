/* Capture the real local documentation page. Browser/server always close. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const tag = 'v0.1.0-alpha.1';
const assets = path.join(root, 'docs/assets/release-' + tag + '-r2');
const evidence = path.join(root, 'docs/validation/evidence/release-' + tag + '-r2');
const config = JSON.parse(fs.readFileSync(path.join(root, 'product/.runtime/html-motion-runtime-20261018-e2.json'), 'utf8'));
const {chromium} = require(config.playwright);
const types = {'.html':'text/html; charset=utf-8','.json':'application/json; charset=utf-8','.gif':'image/gif','.png':'image/png','.mp4':'video/mp4','.md':'text/plain; charset=utf-8'};
const receipt = {status:'running', external_requests:[], page_errors:[], checks:[], browser_closed:false, contexts_closed:false, server_closed:false, recording:'documentation replay of actual retained CLI responses, not a live terminal recording'};
let browser, context, mobileContext, page, mobilePage, videoPath;
const server = http.createServer((req,res)=>{
  let filename;
  try {filename=path.resolve(root, '.' + decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname));}catch{res.writeHead(400);res.end();return;}
  if(!filename.toLowerCase().startsWith(root.toLowerCase()+path.sep)){res.writeHead(403);res.end();return;}
  fs.stat(filename,(err,s)=>{if(err||!s.isFile()){res.writeHead(404);res.end();return;}
    res.writeHead(200,{'Content-Type':types[path.extname(filename)]||'application/octet-stream','Content-Length':s.size,'Cache-Control':'no-store'});
    fs.createReadStream(filename).pipe(res);
  });
});
const assert = (ok,label)=>{receipt.checks.push({check:label,passed:!!ok});if(!ok)throw new Error(label);};
const outputReceipt=()=>fs.writeFileSync(path.join(evidence,'browser-verification.json'),JSON.stringify(receipt,null,2)+'\n');
async function capture(){
 try{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const origin='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({executablePath:config.chromium,headless:true,args:['--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run']});
  context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1,reducedMotion:'reduce',recordVideo:{dir:path.join(root,'product/.runtime/first-release-20261024/browser-video'),size:{width:1440,height:1000}}});
  await context.route('**/*',route=>{const u=route.request().url();if(u.startsWith(origin+'/')||u.startsWith('data:'))return route.continue();receipt.external_requests.push(u);return route.abort();});
  await context.grantPermissions(['clipboard-read','clipboard-write'],{origin});
  page=await context.newPage();page.on('pageerror',e=>receipt.page_errors.push(e.message));
  await page.goto(origin+'/docs/demo/index.html',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>document.body.dataset.ready==='true');
  assert(await page.locator('#command option').count()===28,'28 real command responses available');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'desktop has no horizontal overflow');
  await page.screenshot({path:path.join(assets,'desktop.png'),fullPage:false});
  await page.locator('#case-template').click();
  assert((await page.locator('#case-title').innerText()).includes('模板'),'template tab loads actual case');
  await page.locator('#case-float').click();
  assert((await page.locator('#case-kind').innerText()).includes('HISTORICAL'),'Float32 case is labeled historical');
  await page.locator('#case-float').focus();
  await page.keyboard.press('Home');
  assert(await page.locator('#case-ad').getAttribute('aria-selected')==='true','keyboard tab navigation works');
  await page.locator('#command').selectOption('remote-refused');
  assert(await page.locator('#response-status').getAttribute('data-exit')==='2','real nonzero refusal response displayed');
  assert((await page.locator('#json-response').innerText()).includes('ARGUMENT_INVALID'),'complete actual refusal body displayed');
  await page.locator('#command').selectOption('render');
  await page.locator('#copy').click();
  assert((await page.locator('#response-status').innerText()).includes('已复制'),'copy command works');
  await page.locator('#language').click();
  assert(await page.locator('html').getAttribute('lang')==='en','English language switch works');
  await page.locator('#language').click();
  await page.locator('#responses').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(assets,'responses.png'),fullPage:false});
  await page.locator('#replay').click();
  await page.waitForTimeout(14000);
  assert((await page.locator('#command').inputValue())==='remote-refused','response replay reaches the retained refusal');
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.waitForTimeout(700);
  mobileContext=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1,reducedMotion:'reduce',isMobile:true,hasTouch:true});
  await mobileContext.route('**/*',route=>{const u=route.request().url();if(u.startsWith(origin+'/')||u.startsWith('data:'))return route.continue();receipt.external_requests.push(u);return route.abort();});
  mobilePage=await mobileContext.newPage();mobilePage.on('pageerror',e=>receipt.page_errors.push(e.message));
  await mobilePage.goto(origin+'/docs/demo/index.html',{waitUntil:'networkidle'});
  await mobilePage.waitForFunction(()=>document.body.dataset.ready==='true');
  assert(await mobilePage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'390px mobile has no horizontal overflow');
  await mobilePage.screenshot({path:path.join(assets,'mobile.png'),fullPage:true});
  await mobilePage.locator('#case-template').click();
  assert(await mobilePage.locator('#case-template').getAttribute('aria-selected')==='true','mobile tab interaction works');
  assert(receipt.page_errors.length===0,'no page JavaScript errors');
  assert(receipt.external_requests.length===0,'no external page requests');
  videoPath=await page.video().path();
  receipt.status='passed';
 }catch(e){receipt.status='failed-preserved';receipt.error=String(e);process.exitCode=1;}
 finally{
  if(mobilePage)await mobilePage.close().catch(()=>{});
  if(page)await page.close().catch(()=>{});
  if(mobileContext)await mobileContext.close().catch(()=>{});
  if(context)await context.close().catch(()=>{});
  receipt.contexts_closed=true;
  if(browser)await browser.close().then(()=>receipt.browser_closed=true).catch(()=>{});
  await new Promise(resolve=>server.close(()=>{receipt.server_closed=true;resolve();}));
  outputReceipt();
 }
 if(receipt.status==='passed'){
  const video=path.join(assets,'workflow.mp4'),gif=path.join(assets,'workflow.gif');
  function ff(args){const p=spawnSync('ffmpeg',['-v','error',...args],{encoding:'utf8',windowsHide:true,timeout:120000});if(p.status!==0)throw new Error(p.stderr);}
  // The retained source WebM is generated by Playwright, not downloaded media.
  ff(['-i',videoPath,'-an','-vf','scale=1280:-2','-c:v','libx264','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',video]);
  ff(['-i',video,'-t','20','-filter_complex','fps=5,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',gif]);
  receipt.recording_files=['workflow.mp4','workflow.gif'];outputReceipt();
 }
 console.log(JSON.stringify(receipt));
}
capture().catch(e=>{receipt.status='failed-preserved';receipt.encoding_error=String(e);outputReceipt();console.error(String(e));process.exitCode=1;});
