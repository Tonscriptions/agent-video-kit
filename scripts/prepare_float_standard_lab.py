"""Isolate standard CLI integration from the frozen native-window release."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'float-render-lab-20261022'


def main():
    assert not (ROOT / 'product/src').exists()
    spec = importlib.util.spec_from_file_location('native_parent_freeze', PARENT / 'scripts/run_frozen_regression.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    current = module.frozen()
    assert len(current) == 296
    base = PARENT / 'docs/validation/evidence/float-render-20261022-lab'
    focus = json.loads((base / 'native-r2.json').read_bytes())
    installed = json.loads((base / 'installed-r1/verification.json').read_bytes())
    assert focus['result']['successful'] and focus['result']['methods'] == 21
    assert installed['status'] == 'passed-fresh-eight-wheel-178-resources-real-media-and-203-methods'
    assert focus['frozen_before'] == focus['frozen_after'] == installed['frozen_before'] == installed['frozen_after'] == current
    foundation = json.loads((base / 'foundation-r1.json').read_bytes())
    names = set(current) | set(foundation['dependency_artifact_inputs']) | {v['path'] for v in foundation['external_fixtures']} | {
        'scripts/run_frozen_regression.py', 'scripts/run_with_regression_fixtures.py', 'scripts/materialize_regression_fixtures.py'}
    assert len(names) == 316
    copied = {}
    for name in sorted(names):
        source, target = PARENT / name, ROOT / name
        assert source.is_file() and not target.exists()
        digest = module.sha(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert module.sha(target) == digest
        copied[name] = digest
    assert module.frozen() == current
    out = ROOT / 'docs/validation/evidence/float-standard-20261022-lab/foundation-r1.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    value = {'status': 'isolated-tested-native-window296-foundation', 'at_utc': datetime.now(timezone.utc).isoformat(),
        'parent_root': str(PARENT), 'parent_frozen_inputs': current, 'copied_files': copied, 'copied_count': len(copied),
        'parent_installed_methods': 203, 'parent_installed_receipt_sha256': module.sha(base / 'installed-r1/verification.json'),
        'parent_full_passed': False, 'parent_published': False, 'dependency_artifact_inputs': foundation['dependency_artifact_inputs'],
        'external_fixtures': foundation['external_fixtures'], 'generator_sha256': module.sha(Path(__file__)),
        'native_windows': True, 'virtualization': False, 'network': False}
    out.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'status': value['status'], 'copied': len(copied)}))


if __name__ == '__main__':
    main()
