import { pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';
const [source, adapted, output, work] = process.argv.slice(2);
const load = (root, file) => import(pathToFileURL(resolve(root,'packages/openfilm',file)));
const { saveGroup, takeSaved } = await load(adapted,'studio/server/saved.mjs');
const { groupInsertOps } = await load(adapted,'studio/ui/src/lib/saved-insert.ts');
const { fieldOf, valueOf, withVar, withText, withImage } = await load(source,'studio/ui/src/lib/template-controls.ts');
const save = (name,value) => writeFileSync(join(output,name),JSON.stringify(value,null,2)+'\n');
const root=join(work,'original-project'), target=join(work,'target-project');
mkdirSync(join(root,'pages'),{recursive:true});mkdirSync(join(root,'assets'),{recursive:true});mkdirSync(target);
writeFileSync(join(root,'assets','logo.svg'),'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="teal"/></svg>');
writeFileSync(join(root,'pages','title.css'),':root { --accent: #004488; --title-size: 56px }');
writeFileSync(join(root,'pages','title.html'),'<link rel="stylesheet" href="title.css"><img src="../assets/logo.svg"><h1>本地广告</h1><script>window.film={duration:2,frame(){}}</script>');
writeFileSync(join(root,'film.html'),'<meta name="viewport" content="width=640, height=360"><section><iframe id="title" src="pages/title.html#t=0,2" at="3" data-link="pair"></iframe></section><section><img id="logo" src="assets/logo.svg#t=0,1" at="3.5" data-link="pair"></section>');
const hash=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
const originalHash=hash(join(root,'pages','title.html'));
const path=await saveGroup(root,['title','logo'],{name:'本地片头组'});
const bundle=await takeSaved(target,path);
assert.equal(bundle.clips.length,2);
assert.deepEqual(bundle.clips.map(c=>[c.track,c.at]),[[0,0],[1,.5]]);
const model=[{index:0,clips:[{id:'existing',link:'saved-pair',startMs:0,endMs:1000,inMs:0,speed:1,sourceMs:1000}]}];
const ops=groupInsertOps(bundle.clips,1.125,2,model);
assert.deepEqual(ops.map(o=>[o.at,o.track]),[[1.125,{insert:2}],[1.625,{insert:3}]]);
assert.equal(ops[0].link,ops[1].link);assert.notEqual(ops[0].link,'saved-pair');
const copied=join(target,bundle.clips[0].clip.src);
assert.equal(hash(copied),originalHash);writeFileSync(copied,'edited copy');
assert.equal(hash(join(root,'pages','title.html')),originalHash);
save('S03-saved-group.json',{source_times:[[3,5],[3.5,4.5]],library_path:path,bundle,model,ops,
 checks:{independent_copy:true,relative_offsets:true,new_link_identity:true,files_preserve_source_bytes:true},
 note:'Data and file-copy check; SVG/HTML not rendered; no audiovisual or rights claim.'});
const original=[{at:'#title',text:'原文',style:{color:'#ffffff'}}];
let overrides=withVar(original,'--accent','#00aaff');
overrides=withText(overrides,'#title',undefined,'替换标题');
overrides=withImage(overrides,{at:'#logo',kind:'img'},'../assets/new logo.svg');
assert.equal(valueOf(fieldOf('56px')),'56px');
assert.equal(overrides.find(o=>o.at===':root').style['--accent'],'#00aaff');
assert.equal(overrides.find(o=>o.at==='#title').style.color,'#ffffff');
assert.equal(original[0].text,'原文');
save('S04-template-overrides.json',{original,overrides,number_field:fieldOf('56px'),
 checks:{preserves_unmodified_style:true,source_immutable:true,units_retained:true},
 note:'Override data only; DOM rasterization, CSS layout and final video not checked.'});
console.log(JSON.stringify({saved_group:true,template_overrides:true,samples:2}));
