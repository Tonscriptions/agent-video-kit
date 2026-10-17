"""Reproduce an offline source audit against an already acquired OpenFilm tree.

Runs selected upstream tests without package installation. The original UI
planning dependency failure is retained, then only its React timecode hook is
removed in a separate copy to check whether the planners can run without UI.
No Studio, browser, media provider, Docker or WSL is started.
"""
from __future__ import annotations
import argparse,difflib,hashlib,json,os,re,shutil,subprocess,time
from datetime import datetime,timezone
from pathlib import Path

PURE_TESTS=[
 'packages/openfilm/src/film-doc.test.mjs',
 'packages/openfilm/studio/server/ops.test.mjs',
 'packages/openfilm/studio/server/subtitle-segments.test.mjs',
 'packages/openfilm/studio/server/jianying.test.mjs',
 'packages/openfilm/studio/server/closure.test.mjs',
]
PLANNER_TESTS=[
 'packages/openfilm/studio/ui/src/lib/timeline-edit.test.ts',
 'packages/openfilm/studio/ui/src/lib/transitions.test.ts',
]
HOOK='packages/openfilm/studio/ui/src/lib/timecode.ts'

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def freeze(root):return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file()}

def run(source,output,work,node):
    if output.exists() or work.exists():raise ValueError('Use fresh output and work directories')
    output.mkdir(parents=True);work.mkdir(parents=True);before=freeze(source)
    env=os.environ.copy()
    for key in ('TEMP','TMP','TMPDIR'):env[key]=str(work)
    node_version=subprocess.run([node,'--version'],capture_output=True,text=True,check=True).stdout.strip()
    started=datetime.now(timezone.utc).isoformat();runs=[]
    def execute(name,tree,files,strip=False,expected=0):
        command=[node,*(['--experimental-strip-types'] if strip else []),'--test','--test-concurrency=1',*[str(tree/f) for f in files]]
        began=time.monotonic();p=subprocess.run(command,cwd=work,env=env,capture_output=True,timeout=180)
        stdout=output/(name+'.stdout.log');stderr=output/(name+'.stderr.log');stdout.write_bytes(p.stdout);stderr.write_bytes(p.stderr)
        text=p.stdout.decode('utf-8','replace')
        def count(key):
            value=re.findall(r'^# '+key+r' (\d+)\s*$',text,re.M);return int(value[-1]) if value else None
        record={'id':name,'command':command,'exit_code':p.returncode,'expected_exit_code':expected,'wall_seconds':time.monotonic()-began,
          'test_count':count('tests'),'passed':count('pass'),'failed':count('fail'),'cancelled':count('cancelled'),'skipped':count('skipped'),
          'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr),'scope':'upstream selected tests, not agent-video-kit product regression or encoded media validation'}
        runs.append(record);save(output/(name+'.json'),record)
        print(json.dumps({k:record[k] for k in ('id','exit_code','test_count','passed','failed')},ensure_ascii=False),flush=True)
        assert p.returncode==expected,record
        return record
    execute('O01-upstream-pure',source,PURE_TESTS)
    failed=execute('O02-original-planners-dependency',source,PLANNER_TESTS,strip=True,expected=1)
    assert 'Cannot find package \'react\'' in (output/'O02-original-planners-dependency.stdout.log').read_text(encoding='utf-8')
    adapted=work/'adapted-source';shutil.copytree(source,adapted)
    original=(adapted/HOOK).read_text(encoding='utf-8')
    text,n=re.subn(r"^import \{ useSyncExternalStore \} from 'react';\r?\n",'',original,flags=re.M);assert n==1
    text,n=re.subn(r'^export function useTimecodeFps\(\): number \{.*?^\}\r?\n','',text,flags=re.M|re.S);assert n==1
    (adapted/HOOK).write_text(text,encoding='utf-8',newline='\n')
    diff=''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='upstream/'+HOOK,tofile='without-react-hook/'+HOOK))
    (output/'planner-react-hook-removal.patch').write_text(diff,encoding='utf-8',newline='\n')
    adapted_hashes=freeze(adapted)
    changed=[p for p in before if before[p]!=adapted_hashes[p]];assert changed==[HOOK] and set(before)==set(adapted_hashes)
    execute('O03-extracted-planners',adapted,PLANNER_TESTS,strip=True)
    # Concrete data outputs, kept apart from test counts and render evidence.
    sample_worker=work/'samples.mjs'
    sample_worker.write_text(r'''import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const [source, adapted, output] = process.argv.slice(2);
const load = (root, file) => import(pathToFileURL(resolve(root, file)));
const { segmentLine, subtitleEnd } = await load(source, 'packages/openfilm/studio/server/subtitle-segments.mjs');
const { planRemove } = await load(adapted, 'packages/openfilm/studio/ui/src/lib/timeline-edit.ts');
const { applyOps } = await load(source, 'packages/openfilm/studio/server/ops.mjs');
const save = (name, value) => writeFileSync(resolve(output, name), JSON.stringify(value, null, 2) + '\n');
const line = {text: '这是一条本地广告，展示 Agent Video Kit，所有媒体在本机处理。', startMs: 0, endMs: 7000};
const pieces = segmentLine(line);
assert.ok(pieces.length >= 2);
for (let i = 0; i < pieces.length; i++) {
  assert.equal(pieces[i].text, line.text.slice(pieces[i].from, pieces[i].to));
  assert.ok(pieces[i].endMs > pieces[i].startMs);
  if (i) assert.ok(pieces[i].startMs >= pieces[i-1].endMs);
}
save('S01-subtitle-input.json', line);
save('S01-subtitle-output.json', {pieces, display_text: pieces.map(p => subtitleEnd(p.text)), timing_source: 'estimated from supplied line range, no ASR or TTS execution', checks: 'source spans, positive duration, no overlap'});
const clip = (id, a, b) => ({id, startMs:a*1000, endMs:b*1000, inMs:0, speed:1, sourceMs:60000});
const model = [
  {index:0, clips:[clip('intro',0,1), clip('remove',1,3), clip('outro',3,5)]},
  {index:1, role:'audio', clips:[clip('voice',3,5)]},
  {index:2, locked:true, role:'audio', clips:[clip('bed',0,5)]},
];
const film = {stage:{w:320,h:180}, tracks:model.map(t => ({...(t.locked?{locked:true}:{}), clips:t.clips.map(c => ({id:c.id, src:c.id+'.mp4', at:c.startMs/1000, time:[0,(c.endMs-c.startMs)/1000]}))}))};
const plan = planRemove(model, ['remove'], {ripple:true,sync:true});
const result = applyOps(structuredClone(film), plan.ops);
const actual = result.tracks.map(t => t.clips.map(c => [c.id,c.at??0,(c.at??0)+(c.time[1]-c.time[0])/(c.speed??1)]));
const expected = [[['intro',0,1],['outro',1,3]],[['voice',1,3]],[['bed',0,5]]];
assert.deepEqual(actual,expected);
assert.equal(plan.shortMs,0);
save('S02-ripple-input.json', {model,film,remove:['remove'],options:{ripple:true,sync:true}});
save('S02-ripple-output.json', {plan,result,actual,expected,checks:'exact expected intervals, synced voice moves by 2s, locked bed unchanged'});
console.log(JSON.stringify({subtitle_pieces:pieces.length,ripple_exact:true}));
''',encoding='utf-8',newline='\n')
    sample_cmd=[node,'--experimental-strip-types',str(sample_worker),str(source),str(adapted),str(output)]
    p=subprocess.run(sample_cmd,cwd=work,env=env,capture_output=True,timeout=30)
    (output/'O04-data-samples.stdout.log').write_bytes(p.stdout);(output/'O04-data-samples.stderr.log').write_bytes(p.stderr)
    assert p.returncode==0,p.stderr.decode('utf-8','replace')
    sample_summary=json.loads(p.stdout.decode('utf-8'))
    after=freeze(source);assert before==after
    code=[]
    for path in source.rglob('*'):
        if not path.is_file() or path.suffix not in {'.ts','.tsx','.mjs','.js'}:continue
        content=path.read_text(encoding='utf-8',errors='replace');relative=path.relative_to(source).as_posix()
        code.append({'path':relative,'lines':len(content.splitlines()),'bytes':path.stat().st_size,
                     'test_file':bool(re.search(r'\.(?:test|spec)\.',path.name)),'react_runtime_import':bool(re.search(r"from ['\"]react(?:/[^'\"]*)?['\"]",content))})
    record={'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'node_version':node_version,
      'source_file_count':len(before),'source_unchanged':True,'source_sha256':before,'runs':runs,
      'adapted_changed_files':changed,'original_hook_sha256':before[HOOK],'adapted_hook_sha256':adapted_hashes[HOOK],
      'modified_pure_planner_algorithms':False,'removed_react_hook_only':True,'public_scope':'Research extraction POC, no product runtime integration',
      'upstream_full_suite_run':False,'upstream_build_run':False,'browser_opened':False,'gui_opened':False,'provider_calls':0,
      'new_dependencies_installed':0,'node_engine_note':'MJS and experimental TS subset ran with the recorded Node; repository development baseline is >=22.18. This is not full compatibility acceptance.',
      'data_samples':{'command':sample_cmd,'exit_code':p.returncode,'sample_count':2,'summary':sample_summary,'worker_sha256':sha(sample_worker),
       'artifacts':{f.name:sha(f) for f in sorted(output.glob('S0*.json'))}},
      'source_statistics':{'code_files':len(code),'code_lines':sum(p['lines'] for p in code),'test_files':sum(p['test_file'] for p in code),
       'test_lines':sum(p['lines'] for p in code if p['test_file']),'runtime_react_importing_files':sum(p['react_runtime_import'] for p in code)},'code_inventory':code}
    save(output/'verification.json',record)
    print(json.dumps({'source_unchanged':True,'tests':[(r['id'],r['test_count'],r['passed'],r['failed']) for r in runs],'source_statistics':record['source_statistics']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','work'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--node',default='node');args=parser.parse_args()
    run(args.source.resolve(),args.output.resolve(),args.work.resolve(),args.node)
