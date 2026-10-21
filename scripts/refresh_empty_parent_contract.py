"""Inherit the exact upstream CLI assertion refresh without changing runtime."""
from __future__ import annotations
from datetime import datetime, timezone
import difflib
from pathlib import Path
from run_frozen_regression import frozen
from run_empty_native_after_nested import read, save, sha, SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT.parent / 'nested-native-clock-lab-20261021'
REL = ROOT / 'docs/validation/evidence/native-empty-window-20261021-lab'
UPSTREAM_REL = UPSTREAM / 'docs/validation/evidence/nested-native-clock-20261021-lab'
TEST = 'product/tests/test_cli.py'


def main():
    output = REL / 'parent-contract-refresh-r1.json'
    assert not output.exists()
    before = frozen()
    audit = read(REL / 'audit-r1.json')
    foundation = read(REL / 'foundation-r1.json')
    upstream = read(UPSTREAM_REL / 'contract-refresh-r1.json')
    assert len(before) == 256 and before == audit['frozen_inputs']
    assert foundation['source_inputs'] == upstream['frozen_before']
    assert before[TEST] == upstream['frozen_before'][TEST]
    assert upstream['runtime_inputs_changed'] is False
    parent = upstream['frozen_after']
    assert len(parent) == 255
    assert all(sha(UPSTREAM / name) == digest for name, digest in parent.items())
    snapshots = REL / 'before-parent-contract-refresh-r1'
    snapshots.mkdir()
    preserved = {}
    for name in SCRIPTS:
        path = ROOT / 'scripts' / name
        target = snapshots / (name + '.txt')
        target.write_bytes(path.read_bytes())
        preserved['scripts/' + name] = {'snapshot': target.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
    target = ROOT / TEST
    old = target.read_text('utf8')
    snapshot = snapshots / 'test_cli.py.txt'
    snapshot.write_bytes(target.read_bytes())
    target.write_bytes((UPSTREAM / TEST).read_bytes())
    after = frozen()
    assert set(after) == set(before) and {name for name in before if before[name] != after[name]} == {TEST}
    assert after[TEST] == parent[TEST]
    updated_snapshot = snapshots / 'test_cli.after.py.txt'
    updated_snapshot.write_bytes(target.read_bytes())
    (REL / 'parent-contract-refresh-r1.patch').write_text(''.join(difflib.unified_diff(
        old.splitlines(True), target.read_text('utf8').splitlines(True), fromfile=TEST+'@prior', tofile=TEST+'@upstream-refresh')),
        encoding='utf8', newline='\n')
    updated_foundation = dict(foundation)
    updated_foundation.update(source_inputs=parent, prior_foundation_sha256=sha(REL / 'foundation-r1.json'),
        upstream_contract_refresh_sha256=sha(UPSTREAM_REL / 'contract-refresh-r1.json'),
        upstream_current_audit_sha256=sha(UPSTREAM_REL / 'audit-r2.json'),
        upstream_runtime_modified=False, status='copied-parent-with-exact-test-only-contract-refresh')
    save(REL / 'foundation-r2.json', updated_foundation)
    save(output, {'status': 'inherited-upstream-test-only-refresh-awaiting-controls',
        'runtime_inputs_changed': False, 'only_modified_input': TEST, 'frozen_before': before, 'frozen_after': after,
        'prior_audit_sha256': sha(REL / 'audit-r1.json'), 'upstream_contract_refresh_sha256': sha(UPSTREAM_REL / 'contract-refresh-r1.json'),
        'upstream_parent_inputs': parent, 'foundation_r2_sha256': sha(REL / 'foundation-r2.json'),
        'before_test_snapshot': snapshot.relative_to(ROOT).as_posix(), 'after_test_snapshot': updated_snapshot.relative_to(ROOT).as_posix(),
        'preserved_preflight_scripts': preserved, 'generator_sha256': sha(__file__), 'at_utc': datetime.now(timezone.utc).isoformat()})
    source = UPSTREAM / 'scripts/run_nested_contract_controls.py'
    prepared = ROOT / 'scripts/run_empty_parent_contract_controls.py'
    assert not prepared.exists()
    text = source.read_text('utf8')
    text = text.replace('from run_nested_native_after_index import read, save, sha', 'from run_empty_native_after_nested import read, save, sha')
    text = text.replace('nested-native-clock-20261021-lab', 'native-empty-window-20261021-lab')
    text = text.replace('contract-refresh-r1.json', 'parent-contract-refresh-r1.json')
    compile(text, prepared.name, 'exec')
    prepared.write_text(text, encoding='utf8', newline='\n')
    save(REL / 'parent-controls-runner-reuse-r1.json', {'status': 'prepared', 'source': str(source),
        'source_sha256': sha(source), 'prepared_sha256': sha(prepared), 'methods': 4})
    print('inherited one CLI test assertion; all 161 runtime resources unchanged')


if __name__ == '__main__':
    main()
