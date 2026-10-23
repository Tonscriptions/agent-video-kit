"""Copy the byte-frozen sharpening candidate without changing any live owner."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-sharpen-lab-20261022'
REL = ROOT/'docs/validation/evidence/float-keyer-20261023-lab'


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    REL.mkdir(parents=True, exist_ok=True)
    output = REL/'foundation-r1.json'
    assert not output.exists(), 'Use a fresh evidence directory'
    proof_path = PARENT/'docs/validation/evidence/float-sharpen-20261022-lab/native-r4/verification.json'
    proof = json.loads(proof_path.read_bytes())
    assert proof['status'] == 'passed' and proof['methods'] == 121 and proof['skipped'] == 0
    inputs = proof['frozen_before']
    assert inputs == proof['frozen_after'] and len(inputs) == 328
    foundation = json.loads((proof_path.parent.parent/'foundation-r1.json').read_bytes())
    dependencies, fixtures = foundation['dependency_artifact_inputs'], foundation['external_fixtures']
    assert len(dependencies) == 9 and len(fixtures) == 8
    paths = dict(inputs, **dependencies)
    paths.update({row['path']: row['sha256'] for row in fixtures})
    for name in ('run_frozen_regression.py', 'run_with_regression_fixtures.py', 'materialize_regression_fixtures.py'):
        paths['scripts/'+name] = sha(PARENT/'scripts'/name)
    for name, expected in paths.items():
        source, destination = PARENT/name, ROOT/name
        assert sha(source) == expected, name
        destination.parent.mkdir(parents=True, exist_ok=True)
        assert not destination.exists(), name
        shutil.copyfile(source, destination)
        assert sha(source) == sha(destination) == expected, name
    receipt = {'status':'copied-exact-source121-verified-sharpen328-candidate',
        'at_utc':datetime.now(timezone.utc).isoformat(), 'parent_root':str(PARENT),
        'parent_source_proof':str(proof_path), 'parent_source_proof_sha256':sha(proof_path),
        'parent_source_methods':121, 'parent_complete_suite_passed_at_copy':False,
        'parent_published_at_copy':False, 'parent_frozen_inputs':inputs,
        'copied_inputs':paths, 'copied_count':len(paths),
        'dependency_artifact_inputs':dependencies, 'external_fixtures':fixtures,
        'new_runtime_implemented':False, 'next_intent':'continuous color/chroma distance key, coverage and despill',
        'native_windows':True, 'virtualization':False, 'full_capcut_parity':False}
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    (ROOT/'product/.runtime/temp').mkdir(parents=True, exist_ok=True)
    print(json.dumps({'copied':len(paths),'products':len(inputs),'dependencies':len(dependencies),'fixtures':len(fixtures)}))


if __name__ == '__main__':
    main()
