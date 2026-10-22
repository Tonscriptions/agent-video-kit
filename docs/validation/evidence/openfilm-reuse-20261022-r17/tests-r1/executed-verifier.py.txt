"""Inspect new OpenFilm retry behavior without starting its GUI, browser or provider."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'product/.runtime/openfilm-r17-source'
REL = ROOT / 'docs/validation/evidence/openfilm-reuse-20261022-r17'
OUT = REL / 'tests-r1'
TEMP = ROOT / 'product/.runtime/openfilm-r17-temp'


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def freeze():
    spec = importlib.util.spec_from_file_location('r17_product_freeze', ROOT / 'scripts/run_frozen_regression.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.frozen()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    TEMP.mkdir(parents=True, exist_ok=False)
    expected = json.loads((REL / 'capture-r1/source-tree.json').read_bytes())
    capture = json.loads((REL / 'capture-r1/verification.json').read_bytes())
    assert capture['status'] == 'passed-pinned-source-capture'

    def verify_source():
        actual = {p.relative_to(SOURCE).as_posix(): {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
                  for p in SOURCE.rglob('*') if p.is_file()}
        assert actual == expected

    verify_source()
    record = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
                  fixed_head=capture['fixed_head'], frozen_before=freeze(), calls=[],
                  browser_tabs_opened=0, virtualization=False, actual_browser_launched=False,
                  upstream_install=False, new_product_tests=0, new_media=0,
                  full_upstream_suite_executed=False, provider_or_model_called=False)
    (OUT / 'executed-verifier.py.txt').write_bytes(Path(__file__).read_bytes())
    node = shutil.which('node')
    assert node
    record['node'] = dict(path=node, sha256=sha(Path(node).read_bytes()))
    env = dict(os.environ, TEMP=str(TEMP), TMP=str(TEMP), OPENFILM_HOME=str(TEMP / 'home'))
    save(OUT / 'verification.json', record)

    def run(label, args, cwd=SOURCE, accepted_codes=(0,)):
        command = [node, *map(str, args)]
        started = time.monotonic()
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=150,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (OUT / (label + '.stdout.txt')).write_bytes(result.stdout)
        (OUT / (label + '.stderr.txt')).write_bytes(result.stderr)
        text = result.stdout.decode('utf8')
        row = dict(label=label, command=command, cwd=str(cwd), exit_code=result.returncode,
                   seconds=time.monotonic()-started, stdout_sha256=sha(result.stdout),
                   stderr_sha256=sha(result.stderr),
                   summary={k:int(v) for k,v in re.findall(r'^# (tests|pass|fail|cancelled|skipped|todo) (\d+)$',text,re.M)})
        record['calls'].append(row)
        save(OUT / 'verification.json', record)
        assert result.returncode in accepted_codes, (label,result.returncode,result.stderr.decode(errors='replace')[-2000:])
        return text, row

    try:
        record['node']['version'] = run('node-version',['--version'])[0].strip()
        seam = TEMP / 'closed-renderer-seam'
        mapping = (
            'packages/openfilm/src/browser-pool.mjs',
            'packages/openfilm/src/browser-pool.test.mjs',
            'packages/openfilm/studio/server/render-worker.mjs',
        )
        for name in mapping:
            target = seam / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SOURCE / name).read_bytes())
        stub = b"export const launch=()=>{throw new Error('Actual browser launch prohibited in this research seam')};\n"
        (seam / 'packages/openfilm/src/host.mjs').write_bytes(stub)
        (OUT / 'disabled-host.mjs.txt').write_bytes(stub)
        renderer = '''let attempts=0;
export async function render(args, opts) {
  const scenario=process.env.OPENFILM_AUDIT_SCENARIO;
  attempts++;
  process.send?.({type:'audit-attempt',attempt:attempts,scenario});
  if(scenario==='success') return {attempts};
  if(scenario==='cancelled') {
    await new Promise(resolve=>{if(opts.signal.aborted)resolve();else opts.signal.addEventListener('abort',resolve,{once:true});});
    throw new Error('Target page, context or browser has been closed');
  }
  if(scenario==='browser_once' && attempts===1) throw new Error('Target page, context or browser has been closed');
  if(scenario==='buffers_once' && attempts===1) throw new Error('page.goto: net::ERR_NO_BUFFER_SPACE at http://127.0.0.1:123/film.html');
  if(scenario==='browser_always') throw new Error('Target crashed');
  if(scenario==='missing_file') throw new Error('window.film with a frame() function did not appear within 10 s; failed to load: net::ERR_FILE_NOT_FOUND lib.js');
  if(scenario==='page_error') throw new Error('frame(1.2) threw: x is not defined');
  if(scenario==='busy_loop') throw new Error('frame(1.2) did not finish within 60 s (the page is still running code: a loop that never ends?)');
  if(scenario==='encoder') throw new Error('ffmpeg: Unknown encoder');
  if(scenario==='non_error') throw 'Target crashed';
  return {attempts};
}
'''.encode('utf8')
        (seam / 'packages/openfilm/src/render.mjs').write_bytes(renderer)
        (OUT / 'fake-renderer.mjs.txt').write_bytes(renderer)
        probe = Path(__file__).with_name('probe_openfilm_r17.mjs').read_bytes()
        (seam / 'probe.mjs').write_bytes(probe)
        (OUT / 'executed-probe.mjs.txt').write_bytes(probe)
        record['closed_renderer_seam'] = dict(
            original_files={name:expected[name]['sha256'] for name in mapping},
            host_stub_sha256=sha(stub), renderer_stub_sha256=sha(renderer),
            upstream_worker_body_modified=False, original_pool_test_modified=False)
        _, pool = run('unmodified-mock-browser-pool', ['--test','--test-reporter=tap',
                    'packages/openfilm/src/browser-pool.test.mjs'],seam)
        assert pool['summary'] == dict(tests=4, **{'pass':4,'fail':0,'cancelled':0,'skipped':0,'todo':0})
        record['worker_observations'] = json.loads(run('pinned-worker-probe',['probe.mjs'],seam)[0])
        assert len(record['worker_observations']['observations']) == 20
        # Keep the original assertion failure on older Node; never patch the upstream test into a pass.
        _, launcher = run('unmodified-openfilm-command', ['--test','--test-reporter=tap',
                         'apps/desktop/src/openfilm-command.test.mjs'],accepted_codes=(0,1))
        record['launcher_test_summary'] = launcher['summary']
        expected_launcher = dict(tests=2, **{'pass':1,'fail':1,'cancelled':0,'skipped':0,'todo':0})
        assert record['node']['version'] == 'v22.14.0' and launcher['summary'] == expected_launcher
        text = (OUT / 'unmodified-openfilm-command.stdout.txt').read_text('utf8')
        assert 'main: true' in text and 'ERR_ASSERTION' in text
        # Independently check the preload protocol with CommonJS, supported by this existing native Node.
        commonjs = TEMP / 'main-probe.cjs'
        commonjs.write_text("console.log(JSON.stringify({main:require.main===module,args:process.argv.slice(2),runAsNode:process.env.ELECTRON_RUN_AS_NODE??null}));\n",encoding='utf8')
        launcher_env = dict(env, ELECTRON_RUN_AS_NODE='1')
        rows=[]
        old = ROOT / 'product/.runtime/openfilm-r16-source/apps/desktop/src/as-node.mjs'
        new = SOURCE / 'apps/desktop/src/as-node.mjs'
        for label, args in [('r16-dynamic-import',[old,commonjs,'--audit']),
                            ('r17-native-main',['--import',new.as_uri(),commonjs,'--audit'])]:
            command=[node,*map(str,args)]
            result=subprocess.run(command,cwd=TEMP,env=launcher_env,capture_output=True,timeout=20,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            (OUT/(label+'.stdout.txt')).write_bytes(result.stdout)
            (OUT/(label+'.stderr.txt')).write_bytes(result.stderr)
            assert result.returncode == 0
            value=json.loads(result.stdout)
            assert value == dict(main=label=='r17-native-main',args=['--audit'],runAsNode=None)
            rows.append(dict(label=label,command=command,exit_code=0,result=value,
                             wrapper_sha256=sha(Path(old if label.startswith('r16') else new).read_bytes())))
        record['native_commonjs_main_observations']=rows
        verify_source()
        record['frozen_after']=freeze()
        assert record['frozen_before']==record['frozen_after']==capture['frozen_after']
        record.update(status='passed-scoped-research-with-preserved-Node-version-failure',
                      finished_at_utc=datetime.now(timezone.utc).isoformat(), source_files_verified=len(expected),
                      source_unchanged=True, actual_upstream_test_totals={
                          'tests':6,'pass':5,'fail':1,'cancelled':0,'skipped':0,'todo':0},
                      actual_worker_probe_cases=20, actual_commonjs_probe_cases=2,
                      upstream_agents_full_test_executed=False, upstream_browser_kill_test_executed=False,
                      production_behavior_adopted=False, native_encoding_executed=False)
    except BaseException as exc:
        record.update(status='failed-preserved',error=repr(exc),frozen_after=freeze())
        raise
    finally:
        save(OUT/'verification.json',record)
        print(json.dumps({k:record.get(k) for k in (
            'status','actual_upstream_test_totals','actual_worker_probe_cases','actual_commonjs_probe_cases','error')},ensure_ascii=False))


if __name__ == '__main__':
    main()
