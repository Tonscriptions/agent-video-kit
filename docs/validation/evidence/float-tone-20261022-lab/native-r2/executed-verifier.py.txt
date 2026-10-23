"""Run native RGBA balance or related regressions with frozen inputs and raw I/O."""
from datetime import datetime, timezone
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT/'docs/validation/evidence/float-tone-20261022-lab'


def save(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--revision',required=True)
    parser.add_argument('--related',action='store_true')
    args=parser.parse_args()
    assert args.revision.isascii() and args.revision.startswith('r') and args.revision[1:].isdigit()
    work=REL/('native-'+args.revision)
    work.mkdir(exist_ok=False)
    before=frozen();assert len(before)==320
    foundation=json.loads((REL/'foundation-r1.json').read_bytes())
    changed=[n for n in before if foundation['parent_frozen_inputs'].get(n)!=before[n]]
    for name in changed:
        target=work/'executed-source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    (work/'executed-verifier.py.txt').write_bytes(Path(__file__).read_bytes())
    state={'status':'running','pid':os.getpid(),'started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,
        'generator_sha256':sha(Path(__file__)),'native_windows':True,'virtualization':False,'network':False,
        'calls':[],'full_capcut_parity':False,'published':False}
    save(work/'verification.json',state)
    raw_run=subprocess.run
    def native(*positional,**kwargs):
        caught=None
        try:result=raw_run(*positional,**kwargs)
        except subprocess.CalledProcessError as exc:
            caught=exc
            result=subprocess.CompletedProcess(exc.cmd,exc.returncode,exc.stdout,exc.stderr)
        command=positional[0] if positional else kwargs.get('args')
        row={'command':[str(v) for v in command] if isinstance(command,(list,tuple)) else str(command),
            'exit_code':result.returncode}
        index=len(state['calls'])
        for key,data in [('input',kwargs.get('input')),('stdout',result.stdout),('stderr',result.stderr)]:
            if isinstance(data,bytes):
                path=work/f'call-{index:03d}.{key}.bin';path.write_bytes(data)
                row[key]={'file':path.name,'bytes':len(data),'sha256':sha(path)}
        state['calls'].append(row)
        if caught is not None:raise caught
        return result
    sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    names=['test_float_tone']
    if args.related:names+=['test_float_selective_hsl','test_float_balance','test_float_levels','test_float_curves','test_float_lut','test_float_crop','test_float_mask','test_float_exposure','test_float_preview','test_float_standard_render','test_float_timeline']
    tests=unittest.defaultTestLoader.loadTestsFromNames(names)
    state.update(modules=names,planned_methods=tests.countTestCases())
    save(work/'verification.json',state)
    start=time.monotonic()
    try:
        with (work/'unittest.log').open('w',encoding='utf8',newline='\n') as log:
            with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log),patch.object(subprocess,'run',native):
                result=unittest.TextTestRunner(stream=log,verbosity=2).run(tests)
        state.update(status='passed' if result.wasSuccessful() and not result.skipped else 'failed-preserved',
            methods=result.testsRun,seconds=time.monotonic()-start,failures=len(result.failures),errors=len(result.errors),
            skipped=len(result.skipped),log_sha256=sha(work/'unittest.log'),
            native_tone_records=getattr(sys.modules['test_float_tone'],'NATIVE_CALLS',[]))
    except BaseException as exc:
        state.update(status='failed-preserved',error=repr(exc));raise
    finally:
        state.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        state['frozen_equal']=state['frozen_before']==state['frozen_after']
        if not state['frozen_equal']:state['status']='failed-source-changed'
        save(work/'verification.json',state)
        print(json.dumps({k:state.get(k) for k in ('status','planned_methods','methods','seconds','failures','errors','skipped','frozen_equal','error')},ensure_ascii=False),flush=True)
    return 0 if state['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
