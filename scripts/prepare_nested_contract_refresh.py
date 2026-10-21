"""Preserve the failed full run and refresh only its retired clock assertion."""
from __future__ import annotations
import difflib
import json
from pathlib import Path
from run_frozen_regression import frozen
from run_nested_native_after_index import read, save, sha, SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/nested-native-clock-20261021-lab'
TEST = 'product/tests/test_cli.py'


def main():
    target = REL / 'contract-refresh-r1.json'
    assert not target.exists()
    failed = read(REL / 'full-r1.json')
    source = read(REL / 'full-r1.source.json')
    scheduler = read(ROOT / 'product/.runtime/nested-native-clock-20261021/full-after-index-r1/run.json')
    assert scheduler['status'] == 'failed' and failed['status'] == 'failed'
    assert failed['methods'] == 1957 and failed['skipped'] == 0 and not failed['terminal_ok']
    previous = frozen()
    assert failed['frozen_before'] == failed['frozen_after'] == previous and len(previous) == 255
    assert sha(REL / 'full-r1.source.log') == source['log_sha256']
    log = (REL / 'full-r1.source.log').read_text('utf8')
    assert log.count(' ... FAIL') == 1 and 'FAILED (failures=1)' in log
    assert "self.assertTrue(any(item.get('code') == 'NESTED_SOURCE_CFR_NORMALIZED'" in log
    directory = REL / 'before-contract-refresh-r1'
    directory.mkdir()
    preserved = {}
    for name in SCRIPTS:
        path = ROOT / 'scripts' / name
        assert sha(path) == scheduler['verification_scripts'][name]
        snapshot = directory / (name + '.txt')
        snapshot.write_bytes(path.read_bytes())
        preserved['scripts/' + name] = {'sha256': sha(path), 'snapshot': snapshot.relative_to(ROOT).as_posix()}
    path = ROOT / TEST
    before = path.read_text('utf8')
    (directory / 'test_cli.py.txt').write_bytes(path.read_bytes())
    old = "            self.assertTrue(any(item.get('code') == 'NESTED_SOURCE_CFR_NORMALIZED' for item in rendered['data']['warnings']))"
    new = """            self.assertFalse(any(item.get('code') == 'NESTED_SOURCE_CFR_NORMALIZED' for item in rendered['data']['warnings']))
            manifest = json.loads(Path(rendered['data']['manifest']).read_text(encoding='utf-8'))

            def native_clocks(value):
                if isinstance(value, dict):
                    if 'video_frame_clock' in value:
                        yield value['video_frame_clock']
                    for child in value.values():
                        yield from native_clocks(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from native_clocks(child)

            clocks = [clock for clock in native_clocks(manifest)
                      if clock.get('source_clock_anchor') == 'original-native-intervals-before-nested-author-map']
            self.assertEqual(len(clocks), 2)
            self.assertTrue(all(clock['native_source_intervals']['protocol'] == 'covering-native-source-half-open-v1'
                                for clock in clocks))"""
    assert before.count(old) == 1
    after = before.replace(old, new)
    path.write_text(after, encoding='utf8', newline='\n')
    current = frozen()
    assert set(previous) == set(current)
    assert {name for name in current if current[name] != previous[name]} == {TEST}
    (directory / 'test_cli.after.py.txt').write_bytes(path.read_bytes())
    (REL / 'contract-refresh-r1.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=TEST+'@full-r1', tofile=TEST+'@contract-refresh-r1')), encoding='utf8', newline='\n')
    save(target, {'status': 'refreshed-retired-assertion-awaiting-tests',
        'failed_full_sha256': sha(REL / 'full-r1.json'), 'failed_full_methods': 1957, 'failed_full_seconds': failed['suite_seconds'],
        'failure_count': 1, 'runtime_inputs_changed': False, 'only_modified_input': TEST,
        'frozen_before': previous, 'frozen_after': current, 'preserved_executed_scripts': preserved,
        'before_test_snapshot': (directory / 'test_cli.py.txt').relative_to(ROOT).as_posix(),
        'after_test_snapshot': (directory / 'test_cli.after.py.txt').relative_to(ROOT).as_posix(),
        'generator_sha256': sha(__file__)})
    print(json.dumps({'status': 'refreshed-test-only', 'runtime_inputs_changed': False, 'frozen_inputs': len(current)}))


if __name__ == '__main__':
    main()
