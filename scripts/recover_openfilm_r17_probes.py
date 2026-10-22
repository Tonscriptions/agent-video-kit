"""Complete the two native probes after a missing private R16 extraction; retain all original results."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/openfilm-reuse-20261022-r17'
OUT = REL / 'tests-r2'
TEMP = ROOT / 'product/.runtime/openfilm-r17-main-probes-r2'
SOURCE = ROOT / 'product/.runtime/openfilm-r17-source'


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    TEMP.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('r17_verifier_original', ROOT/'scripts/verify_openfilm_r17.py')
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    record = dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),
                  frozen_before=original.freeze(),new_upstream_test_executions=0,
                  browser_tabs_opened=0,virtualization=False,actual_browser_launched=False,
                  provider_or_model_called=False,new_product_tests=0,new_media=0,
                  actual_commonjs_probe_cases=0)
    (OUT/'executed-recovery.py.txt').write_bytes(Path(__file__).read_bytes())
    save(OUT/'verification.json',record)
    try:
        prior_path=REL/'tests-r1/verification.json'
        prior=json.loads(prior_path.read_bytes())
        assert prior['status']=='failed-preserved' and prior['error']=='AssertionError()'
        assert sha((ROOT/'scripts/verify_openfilm_r17.py').read_bytes()) == sha((REL/'tests-r1/executed-verifier.py.txt').read_bytes())
        assert prior['frozen_before']==prior['frozen_after']==record['frozen_before']
        for call in prior['calls']:
            for stream in ['stdout','stderr']:
                assert sha((REL/'tests-r1'/f"{call['label']}.{stream}.txt").read_bytes())==call[f'{stream}_sha256']
        calls={row['label']:row for row in prior['calls']}
        assert calls['unmodified-mock-browser-pool']['summary']==dict(tests=4,**{'pass':4,'fail':0,'cancelled':0,'skipped':0,'todo':0})
        assert calls['unmodified-openfilm-command']['summary']==dict(tests=2,**{'pass':1,'fail':1,'cancelled':0,'skipped':0,'todo':0})
        assert calls['pinned-worker-probe']['exit_code']==0
        worker=json.loads((REL/'tests-r1/pinned-worker-probe.stdout.txt').read_bytes())
        assert worker['status']=='passed-pinned-worker-with-fake-renderer' and len(worker['observations'])==20
        assert worker==prior['worker_observations']
        error=(REL/'tests-r1/r16-dynamic-import.stderr.txt').read_text('utf8')
        assert 'MODULE_NOT_FOUND' in error and 'openfilm-r16-source' in error
        record['retained_failure']=dict(path='tests-r1/verification.json',sha256=sha(prior_path.read_bytes()),
            reason='The optional comparison used a private R16 extraction absent in main; fixed by reading the pinned R16 ZIP',
            original_upstream_test_failure_unchanged=True)
        record['reused_actual_observations']=dict(worker_cases=20,source_receipt_sha256=sha(prior_path.read_bytes()),
            upstream_test_summary={ 'tests':6,'pass':5,'fail':1,'cancelled':0,'skipped':0,'todo':0})
        old_tree=json.loads((ROOT/'docs/validation/evidence/openfilm-reuse-20261022-r16/capture-r2/source-tree.json').read_bytes())
        old_capture=json.loads((ROOT/'docs/validation/evidence/openfilm-reuse-20261022-r16/capture-r2/verification.json').read_bytes())
        archive=ROOT/'sources/upstream/openfilm-025-20261022-r16/repo.zip'
        assert sha(archive.read_bytes())==old_capture['archive_sha256']
        old=TEMP/'old'
        old.mkdir()
        prefix='openfilm-'+old_capture['fixed_head']+'/'
        with zipfile.ZipFile(archive) as z:
            for name in ['as-node.mjs','hidden-windows.mjs']:
                relative='apps/desktop/src/'+name
                data=z.read(prefix+relative)
                assert sha(data)==old_tree[relative]['sha256']
                (old/name).write_bytes(data)
        commonjs=TEMP/'main-probe.cjs'
        commonjs.write_text("console.log(JSON.stringify({main:require.main===module,args:process.argv.slice(2),runAsNode:process.env.ELECTRON_RUN_AS_NODE??null}));\n",encoding='utf8')
        (OUT/'main-probe.cjs.txt').write_bytes(commonjs.read_bytes())
        node=prior['node']['path']
        assert sha(Path(node).read_bytes())==prior['node']['sha256']
        record['node']=prior['node']
        env=dict(os.environ,TEMP=str(TEMP),TMP=str(TEMP),ELECTRON_RUN_AS_NODE='1')
        record['native_commonjs_main_observations']=[]
        for label,wrapper,args in [
            ('r16-dynamic-import',old/'as-node.mjs',[old/'as-node.mjs',commonjs,'--audit']),
            ('r17-native-main',SOURCE/'apps/desktop/src/as-node.mjs',[
                '--import',(SOURCE/'apps/desktop/src/as-node.mjs').as_uri(),commonjs,'--audit'])]:
            command=[node,*map(str,args)]
            result=subprocess.run(command,cwd=TEMP,env=env,capture_output=True,timeout=20,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            (OUT/(label+'.stdout.txt')).write_bytes(result.stdout)
            (OUT/(label+'.stderr.txt')).write_bytes(result.stderr)
            assert result.returncode==0,result.stderr.decode(errors='replace')
            value=json.loads(result.stdout)
            assert value==dict(main=label=='r17-native-main',args=['--audit'],runAsNode=None)
            record['native_commonjs_main_observations'].append(dict(label=label,command=command,
                exit_code=0,result=value,wrapper_sha256=sha(wrapper.read_bytes()),
                stdout_sha256=sha(result.stdout),stderr_sha256=sha(result.stderr)))
        # Record the primary upstream runtime documentation and the actual feature probe separately.
        url='https://raw.githubusercontent.com/nodejs/node/v22.18.0/doc/api/esm.md'
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'agent-video-kit-reuse-audit'}),timeout=45) as r:
            raw=r.read(1<<20)
        text=raw.decode('utf8')
        section=text.split('### `import.meta.main`',1)[1].split('### ',1)[0]
        assert 'v22.18.0' in section
        record['node_primary_documentation']=dict(url=url,sha256=sha(raw),received_at_utc=datetime.now(timezone.utc).isoformat(),
            section='import.meta.main',added_in_node_22='v22.18.0',local_node='v22.14.0',runtime_compatibility_failure_preserved=True)
        expected=json.loads((REL/'capture-r1/source-tree.json').read_bytes())
        actual={p.relative_to(SOURCE).as_posix():dict(sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
                for p in SOURCE.rglob('*') if p.is_file()}
        assert actual==expected
        record['frozen_after']=original.freeze()
        assert record['frozen_before']==record['frozen_after']
        record.update(status='completed-scoped-research-with-preserved-native-Node-failure',
            finished_at_utc=datetime.now(timezone.utc).isoformat(),source_files_verified=len(expected),source_unchanged=True,
            actual_commonjs_probe_cases=2,actual_worker_probe_cases=20,
            actual_upstream_test_totals={'tests':6,'pass':5,'fail':1,'cancelled':0,'skipped':0,'todo':0},
            upstream_browser_kill_test_executed=False,upstream_agents_full_test_executed=False,
            full_upstream_suite_executed=False,product_code_adopted=False,native_encoding_executed=False)
    except BaseException as exc:
        record.update(status='failed-preserved',error=repr(exc),frozen_after=original.freeze())
        raise
    finally:
        save(OUT/'verification.json',record)
        print(json.dumps({k:record.get(k) for k in ['status','actual_commonjs_probe_cases','actual_worker_probe_cases','actual_upstream_test_totals','error']},ensure_ascii=False))


if __name__=='__main__':
    main()
