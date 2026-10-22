"""Copy the exact frozen exposure candidate without changing its live owners."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-exposure-lab-20261022'
REL = ROOT/'docs/validation/evidence/float-mask-20261022-lab'


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    REL.mkdir(parents=True, exist_ok=True)
    assert not (REL/'foundation-r2.json').exists()
    owner_path = PARENT/'product/.runtime/float-exposure-20261022/complete-r1/run.json'
    owner = json.loads(owner_path.read_bytes())
    inputs = owner['frozen_inputs']
    dependencies = owner['dependency_artifact_inputs']
    foundation = json.loads((PARENT/'docs/validation/evidence/float-exposure-20261022-lab/foundation-r1.json').read_bytes())
    fixtures = foundation['external_fixtures']
    fixture_paths = [item['path'] for item in fixtures]
    assert len(inputs) == 302 and len(dependencies) == 9 and len(fixture_paths) == 8
    paths = dict(inputs, **dependencies)
    paths.update({item['path']: item['sha256'] for item in fixtures})
    for name in ['run_frozen_regression.py', 'run_with_regression_fixtures.py', 'materialize_regression_fixtures.py']:
        name = 'scripts/'+name
        paths[name] = sha(PARENT/name)
    for name, expected in paths.items():
        source = PARENT/name
        assert sha(source) == expected, name
        destination = ROOT/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        assert not destination.exists(), name
        shutil.copyfile(source, destination)
        assert sha(source) == expected == sha(destination), name
    (REL/'foundation-r2.json').write_text(json.dumps({
        'status':'copied-exact-frozen-exposure302-candidate',
        'at_utc':datetime.now(timezone.utc).isoformat(), 'parent_root':str(PARENT),
        'parent_owner_status_at_copy':owner['status'], 'parent_complete_suite_passed_at_copy':False,
        'parent_published_at_copy':False, 'parent_frozen_inputs':inputs,
        'copied_inputs':paths, 'copied_count':len(paths),
        'native_windows':True, 'virtualization':False, 'full_capcut_parity':False,
    }, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    (ROOT/'product/.runtime/temp').mkdir(parents=True, exist_ok=True)
    print(json.dumps({'copied_count':len(paths),'products':len(inputs),'fixtures':len(fixture_paths),'dependencies':len(dependencies)}))


if __name__ == '__main__':
    main()
