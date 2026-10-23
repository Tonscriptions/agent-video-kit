"""Fork the accepted keyer source and retain failed predecessor lineage as data."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
PARENT = ROOT.parent/'float-keyer-lab-20261023'
REL = ROOT/'docs/validation/evidence/pipeline-recovery-20261023'


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def main():
    REL.mkdir(parents=True, exist_ok=True)
    output = REL/'foundation-r1.json'
    assert not output.exists()
    proof_path = PARENT/'docs/validation/evidence/float-keyer-20261023-lab/native-r2/verification.json'
    proof = read(proof_path)
    assert proof['status'] == 'passed' and proof['methods'] == 177 and proof['skipped'] == 0
    inputs = proof['frozen_before']
    assert inputs == proof['frozen_after'] and len(inputs) == 330
    foundation = read(proof_path.parent.parent/'foundation-r1.json')
    dependencies, fixtures = foundation['dependency_artifact_inputs'], foundation['external_fixtures']
    assert len(dependencies) == 9 and len(fixtures) == 8
    spec = importlib.util.spec_from_file_location('keyer_source_inputs', PARENT/'scripts/run_frozen_regression.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    assert helper.frozen() == inputs
    paths = dict(inputs, **dependencies)
    paths.update({row['path']:row['sha256'] for row in fixtures})
    for name in ('run_frozen_regression.py','run_with_regression_fixtures.py','materialize_regression_fixtures.py'):
        paths['scripts/'+name] = sha(PARENT/'scripts'/name)
    for name, digest in paths.items():
        source, destination = PARENT/name, ROOT/name
        assert sha(source) == digest and not destination.exists(), name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        assert sha(destination) == sha(source) == digest, name
    old_full = MAIN/'product/.runtime/float-levels-lab-20261022/docs/validation/evidence/float-levels-20261022-lab/full-r1.source.json'
    failed = read(old_full)
    assert failed['methods'] == 2537 and not failed['terminal_ok']
    receipt = dict(status='copied-exact-accepted-keyer330-for-diagnostic-recovery',
        at_utc=datetime.now(timezone.utc).isoformat(), parent_root=str(PARENT),
        parent_source_proof=str(proof_path), parent_source_proof_sha256=sha(proof_path),
        parent_source_methods=177, parent_frozen_inputs=inputs, copied_inputs=paths,
        copied_count=len(paths), dependency_artifact_inputs=dependencies, external_fixtures=fixtures,
        prior_full_failure={'path':str(old_full), 'sha256':sha(old_full), 'methods':2537,
            'failures':1, 'errors':1, 'skipped':0, 'passed':False},
        parent_installed796_run=False, parent_full2891_run=False, parent_published=False,
        new_runtime_implemented=False, native_windows=True, virtualization=False,
        full_capcut_parity=False, purpose='Reproduce preparation-time HTML diagnostics and cancellation fixture startup races before a new combined full regression.')
    output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    (ROOT/'product/.runtime/temp').mkdir(parents=True,exist_ok=True)
    print(json.dumps({'copied':len(paths),'products':len(inputs),'previous_full_passed':False}))


if __name__ == '__main__':
    main()
