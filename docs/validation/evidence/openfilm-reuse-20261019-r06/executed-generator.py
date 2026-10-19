"""Fixed R06 source review: selected upstream tests and pure row allocation only."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from run_frozen_regression import frozen
from audit_openfilm_refresh import contents

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(refresh,output):
    output.mkdir(parents=True,exist_ok=False);(output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before=frozen();r=json.loads(refresh.read_bytes());source=Path(r['unpacked_source']).resolve(strict=True)
    record={'status':'running','frozen_before':before,'generator_sha256':sha(Path(__file__)),'refresh_sha256':sha(refresh),
            'browser_started':False,'upstream_gui_started':False,'provider_called':False,'dependencies_installed':False,
            'product_adopted':False,'neural_forwards':0,'runtime_network_used':False,'virtualization':False}
    def tree():return {p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}
    try:
        if r['head']!='91b4e90c13be6285b03534dfbafe1f028b29d5cc' or r['old_file_count']!=727 or r['new_file_count']!=731 or tree()!=r['head_hashes']:raise ValueError('wrong fixed source')
        if sha(Path(r['source_archive']))!=r['source_archive_sha256']:raise ValueError('source archive changed')
        old=contents(Path(r['fixed_archive']).read_bytes());new=contents(Path(r['source_archive']).read_bytes())
        if old['LICENSE']!=new['LICENSE'] or new['LICENSE']!=(ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes():raise ValueError('license bytes changed')
        selected=['packages/openfilm/studio/server/fcpxml.test.mjs','packages/openfilm/studio/server/film-subtitle.test.mjs',
            'packages/openfilm/studio/server/subtitle-segments.test.mjs','packages/openfilm/src/overrides.test.mjs',
            'packages/openfilm/studio/ui/src/lib/template-controls.test.ts','apps/desktop/src/window-lifecycle.test.mjs',
            'apps/desktop/src/page-presentation.test.mjs','packages/openfilm/studio/ui/src/lib/context-length.test.ts']
        command=['D:/Program Files/nodejs/node.exe','--experimental-strip-types','--test','--test-concurrency=1','--test-reporter=tap',*[str(source/n) for n in selected]]
        env=dict(os.environ,TEMP=str(output),TMP=str(output),TMPDIR=str(output));started=time.monotonic()
        p=subprocess.run(command,cwd=source,env=env,capture_output=True,timeout=120)
        (output/'upstream-selected.stdout.log').write_bytes(p.stdout);(output/'upstream-selected.stderr.log').write_bytes(p.stderr)
        text=p.stdout.decode('utf-8','replace');totals={}
        for key in ('tests','pass','fail','skipped'):
            match=re.search(r'^# '+key+r' (\d+)\s*$',text,re.M);totals[key]=int(match[1]) if match else None
        if p.returncode or totals['fail']!=0 or totals['skipped']!=1 or totals['tests']!=totals['pass']+totals['skipped']:raise ValueError('scoped original tests failed: '+str(totals))
        # Separate independent table of inputs, no GUI state or provider code.
        probe="""import assert from 'node:assert/strict';import {pathToFileURL} from 'node:url';
const m=await import(pathToFileURL(process.argv[1]).href);
assert.deepEqual(m.rowBadges(['mg','video','mg','audio','video','audio']),['P2','V2','P1','A1','V1','A2']);
assert.equal(m.trackKind({clips:[{src:'a.mp4',sound:true}]}),'audio');
assert.equal(m.trackKind({clips:[{src:'a.html'}]}),'mg');
assert.equal(m.trackKind({clips:[{src:'a.png'},{src:'b.wav'}]}),'video');
const blocks=[{id:'c',startMs:500,endMs:1200},{id:'b',startMs:1000,endMs:2000},{id:'a',startMs:0,endMs:1000}];
const original=structuredClone(blocks);assert.deepEqual(m.layerBlocks(blocks).map(r=>r.map(x=>x.id)),[['a','b'],['c']]);assert.deepEqual(blocks,original);
assert.deepEqual(m.layerBlocks([{id:'a',startMs:0,endMs:1000},{id:'b',startMs:999,endMs:2000}]).map(r=>r.map(x=>x.id)),[['a','b']]);
assert.deepEqual(m.layerBlocks([{id:'a',startMs:0,endMs:1000},{id:'b',startMs:998,endMs:2000}]).map(r=>r.map(x=>x.id)),[['a'],['b']]);
console.log(JSON.stringify({status:'passed_pure_row_fixtures',cases:8,one_millisecond_tolerance_explicit:true}));"""
        probe_path=output/'row-fixtures.mjs';probe_path.write_text(probe,encoding='utf-8',newline='\n')
        row_command=['D:/Program Files/nodejs/node.exe','--input-type=module','-e',probe,str(source/'packages/openfilm/studio/server/track-layout.mjs')]
        q=subprocess.run(row_command,cwd=source,env=env,capture_output=True,timeout=30)
        (output/'rows.stdout.log').write_bytes(q.stdout);(output/'rows.stderr.log').write_bytes(q.stderr)
        if q.returncode:raise ValueError(q.stderr.decode('utf-8','replace'))
        if tree()!=r['head_hashes'] or frozen()!=before:raise ValueError('source/product changed during research')
        core=[p for p in r['fixed_hashes'] if p.startswith('packages/openfilm/src/')]
        record.update(status='passed_scoped_r06_source_research',checked_at_utc=datetime.now(timezone.utc).isoformat(),
            source_before=r['head_hashes'],source_after=tree(),head=r['head'],stars=r['stars'],forks=r['forks'],
            source_files=r['new_file_count'],added=r['added'],changed=[x['path'] for x in r['changed']],unchanged=r['unchanged_file_count'],
            cli_src_files_unchanged=len(core),all_cli_src_files_unchanged=all(r['fixed_hashes'][p]==r['head_hashes'][p] for p in core),
            selected_test_files=selected,command=command,exit_code=p.returncode,totals=totals,seconds=time.monotonic()-started,
            upstream_stdout_sha256=sha(output/'upstream-selected.stdout.log'),upstream_stderr_sha256=sha(output/'upstream-selected.stderr.log'),
            row_command=row_command,row_probe=json.loads(q.stdout),row_stdout_sha256=sha(output/'rows.stdout.log'),row_stderr_sha256=sha(output/'rows.stderr.log'),
            skip='optional local Final Cut Pro DTD unavailable; actual NLE import and target software not run',
            window_scope='original EventEmitter/VM mocks, no real GUI lifecycle acceptance',license_original_bytes_preserved=True)
    except BaseException as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
    finally:
        after=frozen();record.update(frozen_after=after,frozen_equal=before==after);save(output/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('status','head','source_files','cli_src_files_unchanged','totals','row_probe')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--refresh',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.refresh.resolve(),a.output.resolve())
