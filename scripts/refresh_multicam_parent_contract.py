"""Inherit the upstream test-only clock contract into the multicam candidate."""
from datetime import datetime, timezone
import json
from pathlib import Path
from run_frozen_regression import frozen
from smoke_multicam_source_range import sha, write

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT.parent / 'native-empty-window-lab-20261021'
REL = ROOT / 'docs/validation/evidence/multicam-source-range-20261021-lab'


def main():
    output = REL / 'parent-contract-refresh-r1.json'
    assert not output.exists()
    read = lambda path: json.loads(Path(path).read_bytes())
    before = frozen()
    audit = read(REL / 'audit-r1.json')
    foundation = read(REL / 'foundation-r1.json')
    upstream = read(UPSTREAM / 'docs/validation/evidence/native-empty-window-20261021-lab/parent-contract-refresh-r1.json')
    assert before == audit['frozen_inputs'] and len(before) == 257
    assert foundation['source_inputs'] == upstream['frozen_before']
    parent = upstream['frozen_after']
    assert len(parent) == 256 and all(sha(UPSTREAM / name) == digest for name, digest in parent.items())
    name = 'product/tests/test_cli.py'
    target = ROOT / name
    assert sha(target) == upstream['frozen_before'][name]
    snapshots = REL / 'before-parent-contract-refresh-r1'
    snapshots.mkdir()
    (snapshots / 'test_cli.py.txt').write_bytes(target.read_bytes())
    target.write_bytes((UPSTREAM / name).read_bytes())
    (snapshots / 'test_cli.after.py.txt').write_bytes(target.read_bytes())
    after = frozen()
    assert set(before) == set(after) and {key for key in before if before[key] != after[key]} == {name}
    assert after[name] == parent[name]
    updated = dict(foundation)
    updated.update(source_inputs=parent, prior_foundation_sha256=sha(REL / 'foundation-r1.json'),
        upstream_contract_refresh_sha256=sha(UPSTREAM / 'docs/validation/evidence/native-empty-window-20261021-lab/parent-contract-refresh-r1.json'),
        upstream_runtime_modified=False)
    write(REL / 'foundation-r2.json', updated)
    write(output, {'status': 'inherited-parent-test-refresh-awaiting-related-suite', 'runtime_inputs_changed': False,
        'only_modified_input': name, 'frozen_before': before, 'frozen_after': after,
        'parent_inputs': parent, 'before_test_snapshot': (snapshots / 'test_cli.py.txt').relative_to(ROOT).as_posix(),
        'after_test_snapshot': (snapshots / 'test_cli.after.py.txt').relative_to(ROOT).as_posix(),
        'prior_audit_sha256': sha(REL / 'audit-r1.json'), 'foundation_r2_sha256': sha(REL / 'foundation-r2.json'),
        'generator_sha256': sha(__file__), 'at_utc': datetime.now(timezone.utc).isoformat()})
    print('one inherited CLI test refreshed; multicam runtime resources unchanged')


if __name__ == '__main__':
    main()
