"""Copy byte-exact candidate inputs for independent native camera clock work."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'offline-media-profile-lab-20261021'
REL = ROOT / 'docs/validation/evidence/multicam-affine-clock-20261021-lab'


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    output = REL / 'foundation-r1.json'
    assert not output.exists() and not (ROOT / 'product/src').exists()
    ready_path = PARENT / 'docs/validation/evidence/offline-media-profile-20261021-lab/readiness-r2.json'
    ready = read(ready_path)
    assert ready['revision'] == 'r2' and len(ready['frozen_inputs']) == 260
    fixture_path = PARENT / 'docs/validation/evidence/offline-media-profile-20261021-lab/external-fixtures-r1.json'
    fixture = read(fixture_path)
    assert fixture['status'] == 'passed' and fixture['fixture_count'] == 8
    expected = dict(ready['frozen_inputs'])
    expected.update(ready['dependency_artifact_inputs'])
    expected.update({row['path']: row['sha256'] for row in fixture['fixtures']})
    for name in ('run_frozen_regression.py', 'run_with_regression_fixtures.py', 'materialize_regression_fixtures.py'):
        path = 'scripts/' + name
        expected[path] = sha(PARENT / path)
    assert len(expected) == 280
    for name, digest in expected.items():
        source, target = PARENT / name, ROOT / name
        assert source.is_file() and not source.is_symlink() and source.resolve().is_relative_to(PARENT)
        assert target.resolve().is_relative_to(ROOT) and not target.exists()
        assert sha(source) == digest
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(target) == digest
    assert all(sha(PARENT / name) == digest for name, digest in expected.items())
    (ROOT / 'product/.runtime/temp').mkdir(parents=True)
    REL.mkdir(parents=True)
    record = {
        'status': 'copied-exact-candidate-parent-not-implemented-or-tested',
        'at_utc': datetime.now(timezone.utc).isoformat(), 'source_root': str(PARENT),
        'source_inputs': ready['frozen_inputs'], 'parent_readiness_sha256': sha(ready_path),
        'dependency_artifact_inputs': ready['dependency_artifact_inputs'],
        'external_fixture_manifest_sha256': sha(fixture_path), 'external_fixtures': fixture['fixtures'],
        'copied_files': expected, 'native_windows': True, 'virtualization': False, 'network': False,
        'main_integrated': False, 'full_suite_started': False, 'parent_is_published': False,
        'publication_requires_actual_parent_full2043_and_commit': True,
        'generator_sha256': sha(Path(__file__))}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    (REL / 'foundation-r1.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status': record['status'], 'parent_inputs': 260,
                      'copied_files': len(expected), 'parent_modified': False}))


if __name__ == '__main__':
    main()
