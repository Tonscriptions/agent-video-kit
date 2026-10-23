"""Reproduce both predecessor failures with explicit preparation/import delays."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT/'docs/validation/evidence/pipeline-recovery-20261023'


def main():
    work = REL/'reproduction-r1'; work.mkdir(exist_ok=False)
    before = frozen(); assert len(before) == 330
    sys.path[:0] = [str(ROOT/'product/src'),str(ROOT/'product/tests')]
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    import test_html_motion as html_tests
    import test_pipeline_diagnostics as diag_tests
    record = dict(status='running', pid=os.getpid(), started_at_utc=datetime.now(timezone.utc).isoformat(),
        generator_sha256=sha(Path(__file__)), frozen_before=before, network=False,
        virtualization=False, browser_processes_started=0)
    output = work/'verification.json'

    def save():
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')

    save()
    try:
        case = html_tests.HTMLSourceTests('test_dry_run_no_asset_or_bundle')
        case.setUp()
        try:
            case.registered()
            original = {n:(case.root/n).read_bytes() for n in ('project.json','rights-ledger.json')}
            clock = [0.0]

            def delayed_preparation(*args):
                clock[0] = 5.0
                return {'layout_check':'none'}

            with patch.object(html_tests.html,'prepare_render',side_effect=delayed_preparation), \
                 patch.object(html_tests.html,'public_plan',return_value={'source_asset_id':'source'}), \
                 patch('time.monotonic',side_effect=lambda:clock[0]):
                code, result = html_tests.cli('motion','html-render','--project',case.root,
                    '--source-asset-id','source','--asset-id','rendered','--timeout-seconds','4')
            record['html_preparation'] = dict(exit_code=code, result=result,
                diagnostic_files=[p.name for p in (case.root/'validation').glob('html-*.json')],
                metadata_unchanged=all((case.root/n).read_bytes()==data for n,data in original.items()),
                controlled_preparation_seconds=5, total_deadline_seconds=4)
            assert code == 6 and result['errors'][0]['code'] == 'HTML_TIMEOUT'
            assert result['errors'][0]['path'] is None
            assert not record['html_preparation']['diagnostic_files']
        finally:
            case.doCleanups()
        save()
        case = diag_tests.NativeDiagnosticIntegrationTests('test_cancel_and_timeout_keep_trigger_and_original_metadata')
        case.setUp()
        try:
            cancel = case.case.base/'delayed-cancel'
            worker = case.case.worker
            worker.write_text(worker.read_text('utf8').replace('import numpy as np','time.sleep(3)\nimport numpy as np'), encoding='utf8')
            before_metadata = case.case.metadata()
            with case.case.fake_command('cancel',str(cancel)):
                code,result = diag_tests.invoke(*case.case.options_for_matting(),
                    '--cancel-file',str(cancel),'--timeout-seconds','2')
            manifest = case.inspect_failure(code,result,8)
            record['cancel_fixture'] = dict(exit_code=code,result=result,
                manifest=manifest,cancel_request_existed=cancel.exists(),
                controlled_import_delay_seconds=3,total_deadline_seconds=2,
                metadata_unchanged=case.case.metadata()==before_metadata)
            assert manifest['error']['code'] == 'TIMEOUT' and not cancel.exists()
        finally:
            case.doCleanups()
        record['status'] = 'reproduced-both-predecessor-failures-with-explicit-phase-control'
    except BaseException as exc:
        record.update(status='failed-preserved',error=repr(exc));raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal'] = record['frozen_before'] == record['frozen_after']
        save()
        (work/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k:record.get(k) for k in ('status','error','frozen_equal')},ensure_ascii=False))


if __name__ == '__main__':
    main()
