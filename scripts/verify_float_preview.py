"""Fresh native preview/standard-render regression with immutable executed code."""
import argparse
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import shutil
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'product/src'), str(ROOT/'product/tests'), str(ROOT/'scripts')]
from ai_ad_editor.runtime import configure_local_runtime
from run_frozen_regression import frozen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--select', action='append')
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    configure_local_runtime(); before = frozen()
    sources = ['product/src/ai_ad_editor/'+name+'.py' for name in ['float_preview', 'preview', 'capabilities']]
    sources += ['product/tests/test_float_preview.py', 'scripts/verify_float_preview.py']
    for name in sources:
        target = out/'executed-source'/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT/name, target)
    preview_module = importlib.import_module('test_float_preview')
    standard = importlib.import_module('test_float_standard_render')
    suite = unittest.defaultTestLoader.loadTestsFromNames(args.select or
        ['test_float_preview.FloatPreviewTests', 'test_timeline_preview', 'test_float_standard_render.FloatStandardRenderTests'])
    record = {'status': 'running', 'pid': __import__('os').getpid(), 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'frozen_before': before, 'command': sys.argv, 'native_windows': True, 'virtualization': False, 'network': False,
        'interactive_browser_tabs': 0, 'planned_methods': suite.countTestCases()}
    def save():
        (out/'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    save(); started = time.monotonic()
    with (out/'unittest.log').open('w', encoding='utf8', newline='\n') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    after = frozen()
    record.update(status='passed' if result.wasSuccessful() and before == after and not result.skipped else 'failed',
        finished_at_utc=datetime.now(timezone.utc).isoformat(), methods=result.testsRun, seconds=time.monotonic()-started,
        failures=[(str(test), detail) for test, detail in result.failures], errors=[(str(test), detail) for test, detail in result.errors],
        skipped=[(str(test), reason) for test, reason in result.skipped], frozen_equal=before == after, frozen_after=after,
        native_calls=standard.NATIVE_CALLS, preview_receipts=preview_module.PREVIEW_RECEIPTS,
        render_receipts=standard.RENDER_RECEIPTS, render_expected_errors=standard.ERROR_RECEIPTS)
    save(); print(json.dumps({k: record[k] for k in ['status', 'methods', 'seconds', 'frozen_equal']}))
    return 0 if record['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
