"""Record the test-only correction after a deliberately retained failed full run."""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
import re

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
REL = 'docs/validation/evidence/vfr-reverse-test-oracle-20261021-r1'
FULL = 'docs/validation/evidence/vfr-reverse-chunks-20261021-v82'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = ROOT / REL
    output = base / 'bridge-r1.json'
    assert not output.exists()
    before = read(base / 'before-r1.json')
    after = read(base / 'after-r1.json')
    old = before['frozen_before']
    current = frozen()
    assert len(current) == len(old) == 249
    assert before['frozen_before'] == before['frozen_after']
    assert after['frozen_before'] == after['frozen_after'] == current
    assert before['methods'] == after['methods'] == 1
    assert before['exit_code'] == 1 and not before['terminal_ok']
    assert after['exit_code'] == 0 and after['terminal_ok']
    assert before['case'] == after['case']
    changed = [name for name in current if current[name] != old[name]]
    assert changed == ['product/tests/test_cli.py'], changed
    old_file = base / 'before-test_cli.py'
    new_file = ROOT / changed[0]
    assert sha(old_file) == old[changed[0]]
    assert sha(new_file) == current[changed[0]]
    diff = ''.join(difflib.unified_diff(
        old_file.read_text(encoding='utf-8').splitlines(keepends=True),
        new_file.read_text(encoding='utf-8').splitlines(keepends=True),
        fromfile='before/product/tests/test_cli.py',
        tofile='after/product/tests/test_cli.py'))
    assert diff.count('@@') == 2  # One hunk; its header contains two markers.
    assert '-            self.assertIn("setpts=(PTS-STARTPTS)/1.25000000"' in diff
    assert '+            self.assertIn("/1.25000000"' in diff
    assert 'reversed-native-source-intervals' in diff
    patch = base / 'test-only.patch'
    patch.write_text(diff, encoding='utf-8', newline='\n')
    failed = read(ROOT / FULL / 'full-r1.json')
    inner = read(ROOT / FULL / 'full-r1.source.json')
    assert failed['status'] == 'failed' and not failed['terminal_ok']
    assert failed['frozen_before'] == failed['frozen_after'] == old
    assert inner['frozen_before'] == inner['frozen_after'] == old
    assert failed['external_fixtures_equal'] and failed['verification_scripts_equal']
    log = (ROOT / FULL / 'full-r1.source.log').read_text(encoding='utf-8')
    failures = re.findall(r'^test\S+ \(([^)]+)\) \.\.\. FAIL$', log, re.M)
    assert failures == [before['case']], failures
    assert not re.findall(r'^test\S+ \([^)]+\) \.\.\. ERROR$', log, re.M)
    stop = read(base / 'full-r1-stop.json')
    assert stop['active_children'] == 0 and stop['wrapper_preserved'] and stop['publisher_preserved']
    publisher_path = ROOT / 'product/.runtime/reverse-chunks-20261021-v82/publication-r1/run.json'
    publisher = read(publisher_path)
    assert publisher['status'] == 'failed' and publisher['calls'] == []
    publisher_receipt = base / 'publication-r1-failure.json'
    publisher_receipt.write_text(json.dumps({
        'status': publisher['status'], 'calls': publisher['calls'],
        'error': publisher['error'], 'original_receipt_sha256': sha(publisher_path),
        'main_files_copied': False,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    receipts = [base / name for name in (
        'before-r1.json', 'before-r1.log', 'after-r1.json', 'after-r1.log',
        'before-test_cli.py', 'full-r1-stop.json', 'test-only.patch',
        'publication-r1-failure.json')]
    output.write_text(json.dumps({
        'status': 'passed-test-only-bridge',
        'before_inputs': old, 'after_inputs': current,
        'changed_inputs': changed, 'unchanged_inputs': 248,
        'runtime_bytes_unchanged': True,
        'named_case': before['case'], 'before_failed': True,
        'after_passed_with_actual_render': True,
        'full_r1_partial_ok_lines': len(re.findall(r' \.\.\. ok$', log, re.M)),
        'full_r1_fail_markers': failures,
        'full_r1_completed': False,
        'full_r1_stop_reason': stop['reason'],
        'failed_publication_copied_main': False,
        'receipts': {p.relative_to(ROOT).as_posix(): sha(p) for p in receipts},
        'generator_sha256': sha(Path(__file__)),
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed-test-only-bridge',
                      'changed_inputs': changed, 'unchanged_inputs': 248}))


if __name__ == '__main__':
    main()
