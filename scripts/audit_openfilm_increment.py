"""Run selected fixed OpenFilm 0.2.0 data modules; no install, CLI or browser.

Keep original missing-React/Playwright failures. In an independent copy remove
the timecode React hook and defer the host import until open() is called.
Then exercise group insertion, file bundles and template parameters.
These are research checks, never product regression or encoded-media checks.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def freeze(root):
    return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file()}


def run(args):
    source, output, work = args.source.resolve(),args.output.resolve(),args.work.resolve()
    output.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    before=freeze(source)
    env=dict(os.environ)
    for key in ('TEMP','TMP','TMPDIR'):
        env[key]=str(work)
    for key in ('HOME','LIBRARY','EXPORTS','SAVED'):
        env['OPENFILM_'+key]=str(work/key.lower())
    runs=[]
    def execute(name,tree,files,expected=0):
        command=[args.node,'--experimental-strip-types','--test','--test-concurrency=1',
                 *[str(tree/file) for file in files]]
        begin=time.monotonic()
        result=subprocess.run(command,env=env,cwd=work,capture_output=True,timeout=120)
        (output/(name+'.stdout.log')).write_bytes(result.stdout)
        (output/(name+'.stderr.log')).write_bytes(result.stderr)
        text=result.stdout.decode('utf-8','replace')
        def count(key):
            matches=re.findall(r'^# '+key+r' (\d+)\s*$',text,re.M)
            return int(matches[-1]) if matches else None
        record={'id':name,'command':command,'exit_code':result.returncode,'expected_exit_code':expected,
                'test_count':count('tests'),'passed':count('pass'),'failed':count('fail'),
                'skipped':count('skipped'),'cancelled':count('cancelled'),'seconds':time.monotonic()-begin,
                'stdout_sha256':sha(output/(name+'.stdout.log')),'stderr_sha256':sha(output/(name+'.stderr.log'))}
        runs.append(record);save(output/(name+'.json'),record)
        print(json.dumps({k:record[k] for k in ('id','exit_code','test_count','passed','failed')},ensure_ascii=False),flush=True)
        assert result.returncode==expected,record
        return text
    base='packages/openfilm/'
    selected=[base+'studio/server/saved.test.mjs',base+'studio/ui/src/lib/template-controls.test.ts',
              base+'src/overrides.test.mjs',base+'src/official-skills.test.mjs']
    text=execute('N01-original-data',source,selected,expected=1)
    assert "Cannot find package 'playwright-core'" in text
    text=execute('N02-original-group-dependency',source,[base+'studio/ui/src/lib/saved-insert.test.ts'],expected=1)
    assert "Cannot find package 'react'" in text
    adapted=work/'adapted-source';shutil.copytree(source,adapted)
    hook=base+'studio/ui/src/lib/timecode.ts'
    original=(adapted/hook).read_text(encoding='utf-8')
    text,n=re.subn(r"^import \{ useSyncExternalStore \} from 'react';\r?\n",'',original,flags=re.M);assert n==1
    text,n=re.subn(r'^export function useTimecodeFps\(\): number \{.*?^\}\r?\n','',text,flags=re.M|re.S);assert n==1
    (adapted/hook).write_text(text,encoding='utf-8',newline='\n')
    patch=''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='original/'+hook,tofile='without-hook/'+hook))
    (output/'react-hook-only.patch').write_text(patch,encoding='utf-8',newline='\n')
    shared=base+'src/shared.mjs'
    original_shared=(adapted/shared).read_text(encoding='utf-8')
    declaration="import { FilmPage, FrameError, launch, serve } from './host.mjs';\n"
    assert original_shared.count(declaration)==1
    revised=original_shared.replace(declaration,'').replace('export async function open(target, opts = {}) {',
        "export async function open(target, opts = {}) {\n  const { FilmPage, FrameError, launch, serve } = await import('./host.mjs');")
    (adapted/shared).write_text(revised,encoding='utf-8',newline='\n')
    patch=''.join(difflib.unified_diff(original_shared.splitlines(True),revised.splitlines(True),
              fromfile='original/'+shared,tofile='lazy-host/'+shared))
    (output/'lazy-host-import.patch').write_text(patch,encoding='utf-8',newline='\n')
    adapted_hashes=freeze(adapted)
    changed=sorted(p for p in before if before[p]!=adapted_hashes[p])
    assert changed==sorted([hook,shared]) and before.keys()==adapted_hashes.keys()
    execute('N03-extracted-data',adapted,[*selected,base+'studio/ui/src/lib/saved-insert.test.ts'])
    worker=output/'data-samples.mjs'
    worker.write_text(SAMPLES,encoding='utf-8',newline='\n')
    command=[args.node,'--experimental-strip-types',str(worker),str(source),str(adapted),str(output),str(work)]
    result=subprocess.run(command,env=env,cwd=work,capture_output=True,timeout=60)
    (output/'N04-data-samples.stdout.log').write_bytes(result.stdout)
    (output/'N04-data-samples.stderr.log').write_bytes(result.stderr)
    assert result.returncode==0,result.stderr.decode('utf-8','replace')
    after=freeze(source);assert before==after
    evidence={'finished_at_utc':datetime.now(timezone.utc).isoformat(),
              'node':subprocess.run([args.node,'--version'],capture_output=True,text=True,check=True).stdout.strip(),
              'source_files':len(before),'source_before':before,'source_after':after,'source_unchanged':True,
              'adapted_changed_files':changed,'runs':runs,'samples_command':command,
              'samples':json.loads(result.stdout),'product_regression_run':False,'browser_started':False,
              'gui_started':False,'upstream_cli_started':False,'new_dependencies_installed':0,
              'encoded_video_frames':0,'asr_or_model_calls':0,
              'scope':'Selected source/data checks only; not whole upstream suite, product integration, rendered quality, rights clearance or time saved.'}
    evidence['artifacts']={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(output.iterdir()) if p.is_file()}
    save(output/'verification.json',evidence)
    print(json.dumps({'source_unchanged':True,'source_files':len(before),'samples':evidence['samples']},ensure_ascii=False))


SAMPLES=r'''import { pathToFileURL } from 'node:url';
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
'''


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('source','output','work'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--node',default='node')
    run(parser.parse_args())
