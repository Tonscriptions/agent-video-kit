"""Retain actual local native window tests and byte-frozen source receipts."""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', required=True)
    parser.add_argument('--source-root', type=Path)
    args = parser.parse_args()
    base = ROOT / 'docs/validation/evidence/float-render-20261022-lab'
    output = base / ('native-' + args.revision + '.json')
    child = output.with_suffix('.child.json')
    log = output.with_suffix('.log')
    assert not any(p.exists() for p in (output, child, log))
    before = frozen()
    assert len(before) == 296
    source = args.source_root.resolve(strict=True) if args.source_root else ROOT / 'product/src'
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'frozen_before': before, 'generator_sha256': sha(Path(__file__)),
        'native_windows': True, 'virtualization': False, 'network': False,
        'source_root': str(source), 'published': False, 'default_renderer_integrated': False}
    def save():
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    bootstrap = '''import sys,unittest,json,pathlib,time,re
sys.path[:0]=[sys.argv[1],sys.argv[2]]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
calls=[]
def audit(event,args):
    if event=='subprocess.Popen':
        executable,command=args[:2]
        first=str(executable or '')
        if not first:
            if isinstance(command,(list,tuple)):first=str(command[0])
            else:
                match=re.match(r'^\\s*(?:"([^"]+)"|([^\\s]+))',str(command));first=next((s for s in match.groups() if s), '') if match else ''
        if pathlib.Path(first).name.lower() in ('ffmpeg.exe','ffprobe.exe','ffmpeg','ffprobe'):
            calls.append({'executable':executable,'command':command})
sys.addaudithook(audit)
import test_float_native_pipe as p,test_float_native_source as s
suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(m) for m in (p,s)])
start=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(suite)
origins={name:module.__file__ for name,module in tuple(sys.modules.items()) if name.startswith('ai_ad_editor') and getattr(module,'__file__',None)}
value={'methods':result.testsRun,'seconds':time.monotonic()-start,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'successful':result.wasSuccessful(),'script_native_calls':s.NATIVE_CALLS,'native_pipe_receipts':p.NATIVE_RECEIPTS,'native_source_receipts':s.SOURCE_RECEIPTS,'audited_native_launches':calls,'runtime_module_origins':origins}
pathlib.Path(sys.argv[3]).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\\n',encoding='utf8')
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
'''
    command = list(map(str, [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap,
                            source, ROOT / 'product/tests', child]))
    record['command'] = command
    save()
    env = dict(os.environ, TEMP=str(ROOT / 'product/.runtime/temp'), TMP=str(ROOT / 'product/.runtime/temp'))
    try:
        with log.open('xb') as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        record.update(exit_code=result.returncode, result=json.loads(child.read_bytes()), log_sha256=sha(log))
        assert result.returncode == 0 and record['result']['successful'] and record['result']['skipped'] == 0
        assert frozen() == before
        assert len(record['result']['audited_native_launches']) > 20
        record['status'] = 'passed-native-clock-window-source-and-owned-pipe'
    except BaseException as caught:
        record.update(status='failed-preserved', error=repr(caught))
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen())
        save()
        output.with_suffix('.executed.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k: record.get(k) for k in ('status', 'exit_code', 'error')}), flush=True)


if __name__ == '__main__':
    main()
