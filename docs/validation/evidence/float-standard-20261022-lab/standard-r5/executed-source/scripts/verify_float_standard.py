"""Run a fresh native standard-render experiment; retain failures and sources."""
import argparse
import hashlib
import importlib
import json
import shutil
import sys
import time
import traceback
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'product/src'), str(ROOT/'product/tests'), str(ROOT/'scripts')]
from ai_ad_editor.runtime import configure_local_runtime
from run_frozen_regression import frozen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--select', action='append')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    configure_local_runtime()
    before = frozen()
    selected_sources = ['product/src/ai_ad_editor/' + p + '.py' for p in
        ['float_standard_render', 'float_stream', 'float_timeline', 'render', 'validator', 'schema_contract', 'capabilities']]
    selected_sources += ['product/src/ai_ad_editor/agent-project.schema.json', 'docs/specs/agent-project.schema.json',
                         'product/tests/test_float_standard_render.py', 'scripts/verify_float_standard.py']
    for name in selected_sources:
        dest = out/'executed-source'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dest)
    test_module = importlib.import_module('test_float_standard_render')
    suite = unittest.defaultTestLoader.loadTestsFromNames(args.select or ['test_float_standard_render'])
    started = time.monotonic()
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'frozen_before': before, 'command': sys.argv, 'native_windows': sys.platform == 'win32',
        'virtualization': False, 'network': False, 'interactive_browser_tabs': 0}
    def save():
        (out/'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    save()
    with (out/'unittest.log').open('w', encoding='utf8', newline='\n') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    after = frozen()
    record.update(status='passed' if result.wasSuccessful() and before == after and not result.skipped else 'failed',
        finished_at_utc=datetime.now(timezone.utc).isoformat(), methods=result.testsRun, seconds=time.monotonic()-started,
        failures=[(str(test), text) for test, text in result.failures],
        errors=[(str(test), text) for test, text in result.errors],
        skipped=[(str(test), reason) for test, reason in result.skipped],
        frozen_equal=before == after, frozen_after=after, native_calls=test_module.NATIVE_CALLS,
        renders=test_module.RENDER_RECEIPTS, expected_errors=test_module.ERROR_RECEIPTS)
    save()
    print(json.dumps({k: record[k] for k in ['status', 'methods', 'seconds', 'frozen_equal']}, ensure_ascii=False))
    return 0 if record['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
