"""Validate completed local observations independently of the failed optional doc download."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/openfilm-reuse-20261022-r17'
OUT = REL / 'tests-r3'


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT/'executed-finalizer.py.txt').write_bytes(Path(__file__).read_bytes())
    receipts={name:json.loads((REL/name).read_bytes()) for name in [
        'capture-r1/verification.json','tests-r1/verification.json','tests-r2/verification.json']}
    capture,first,second=receipts.values()
    assert capture['status']=='passed-pinned-source-capture'
    assert first['status']==second['status']=='failed-preserved'
    assert first['error']=='AssertionError()' and 'ConnectionResetError' in second['error']
    spec=importlib.util.spec_from_file_location('r17_original_freeze',ROOT/'scripts/verify_openfilm_r17.py')
    original=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    inputs=original.freeze()
    assert len(inputs)==311
    for value in receipts.values():
        assert value['frozen_before']==value['frozen_after']==inputs
    for call in first['calls']:
        for stream in ['stdout','stderr']:
            assert sha((REL/'tests-r1'/f"{call['label']}.{stream}.txt").read_bytes())==call[f'{stream}_sha256']
    pool=next(x for x in first['calls'] if x['label']=='unmodified-mock-browser-pool')
    launcher=next(x for x in first['calls'] if x['label']=='unmodified-openfilm-command')
    assert (pool['summary']['pass'],pool['summary']['fail'],pool['summary']['skipped'])==(4,0,0)
    assert (launcher['summary']['pass'],launcher['summary']['fail'],launcher['summary']['skipped'])==(1,1,0)
    worker=json.loads((REL/'tests-r1/pinned-worker-probe.stdout.txt').read_bytes())
    assert worker==first['worker_observations']
    assert worker['status']=='passed-pinned-worker-with-fake-renderer'
    rows=worker['observations']
    assert len(rows)==20 and len({(x['mode'],x['scenario']) for x in rows})==20
    expected=dict(success=('done',1),browser_once=('done',2),buffers_once=('done',2),
                  browser_always=('failed',2),missing_file=('failed',1),page_error=('failed',1),
                  busy_loop=('failed',1),encoder=('failed',1),non_error=('failed',1),cancelled=('failed',1))
    for row in rows:
        kind,attempts=expected[row['scenario']]
        assert row['terminal']['type']==kind and row['attempts']==list(range(1,attempts+1))
        assert row['exit']==dict(code=0 if row['mode']=='pool' or kind=='done' else 1,signal=None)
    common=second['native_commonjs_main_observations']
    assert len(common)==2
    for index,row in enumerate(common):
        assert row['result']==dict(main=bool(index),args=['--audit'],runAsNode=None) and row['exit_code']==0
        for stream in ['stdout','stderr']:
            assert sha((REL/'tests-r2'/f"{row['label']}.{stream}.txt").read_bytes())==row[f'{stream}_sha256']
    tree=json.loads((REL/'capture-r1/source-tree.json').read_bytes())
    source=ROOT/'product/.runtime/openfilm-r17-source'
    actual={p.relative_to(source).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
            for p in source.rglob('*') if p.is_file()}
    assert actual==tree and len(actual)==790
    assert sha((ROOT/'sources/upstream/openfilm-025-20261022-r17/repo.zip').read_bytes())==capture['archive_sha256']
    record=dict(status='completed-scoped-research-with-preserved-native-Node-failure',
        completed_at_utc=datetime.now(timezone.utc).isoformat(),fixed_head=capture['fixed_head'],
        input_receipts={name:sha((REL/name).read_bytes()) for name in receipts},
        actual_upstream_test_totals={'tests':6,'pass':5,'fail':1,'cancelled':0,'skipped':0,'todo':0},
        actual_worker_probe_cases=20,actual_commonjs_probe_cases=2,
        additional_test_executions_by_finalizer=0,local_Node=first['node'],
        retained_execution_failures=['tests-r1: absent private R16 extraction','tests-r2: optional raw documentation TLS connection reset'],
        Node_primary_reference=dict(url='https://raw.githubusercontent.com/nodejs/node/v22.18.0/doc/api/esm.md',
            section='import.meta.main',node_22_added='v22.18.0',access='text web reader; optional native HTTP failure retained',
            newer_Node_or_Electron_executed=False),
        source_unchanged=True,source_files_verified=790,frozen_before=inputs,frozen_after=original.freeze(),
        new_product_tests=0,product_code_adopted=False,new_media=0,actual_browser_launched=False,
        browser_tabs_opened=0,virtualization=False,provider_or_model_called=False,
        upstream_agents_full_test_executed=False,upstream_browser_kill_test_executed=False,
        full_upstream_suite_executed=False,production_retry_integrated=False,full_capcut_parity=False)
    assert record['frozen_before']==record['frozen_after']
    (OUT/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:record[k] for k in ['status','actual_upstream_test_totals','actual_worker_probe_cases','actual_commonjs_probe_cases','source_files_verified']},ensure_ascii=False))


if __name__=='__main__':
    main()
