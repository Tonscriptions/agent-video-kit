"""Index preserved color-animation failures and early controls without overwriting raw evidence."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'docs/validation/evidence/effect-automation-20261019-v58'

def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_bytes())
def run():
    output = EVIDENCE/'development/index.json'; assert not output.exists()
    first = read(EVIDENCE/'targeted-first.json'); original = EVIDENCE/'development/targeted-first-test.py'
    assert first['exit_code'] == 1 and first['methods'] == 28 and not first['terminal_ok']
    assert sha(original) == first['frozen_before']['product/tests/test_effect_automation.py']
    files = []; runs = []
    roots = []
    for ordinal in range(1, 7):
        path = ROOT/f'docs/assets/color-automation-r{ordinal}-20261019-v58'
        receipt = path/('verification.json' if ordinal == 4 else 'failure.json'); record = read(receipt)
        assert record['generator_sha256'] == sha(path/'executed-generator.py')
        if ordinal == 4: assert record['status'] == 'passed' and len(record['cases']) == 14
        else: assert record['partials_preserved'] and record['error']
        runs.append({'path': path.relative_to(ROOT).as_posix(), 'receipt': receipt.name,
                     'receipt_sha256': sha(receipt), 'role': 'earlier_alpha_only_pass' if ordinal == 4 else 'failed_development',
                     'error': record.get('error'), 'promoted_to_final': False})
        roots.append(path)
    for suffix in ('color-native-release-20261019-v58', 'color-native-release-r2-20261019-v58'):
        path = ROOT/'docs/validation/evidence'/suffix
        receipt = path/('failure.json' if suffix == 'color-native-release-20261019-v58' else 'verification.json')
        record = read(receipt)
        if receipt.name == 'verification.json':
            assert record['generator_sha256'] == sha(path/'executed-generator.py')
            assert record['isolated_cli_calls'] == 65
        else: assert len(record['calls']) == 2 and record['error'] == 'AssertionError()'
        runs.append({'path': path.relative_to(ROOT).as_posix(), 'receipt': receipt.name,
            'receipt_sha256': sha(receipt), 'role': 'early_native_check', 'promoted_to_final': False})
        roots.append(path)
    for path in roots:
        for p in sorted(path.rglob('*')):
            if p.is_file(): files.append({'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)})
    interrupted = read(EVIDENCE/'full-interruption-observation.json')
    assert interrupted['status'] == 'interrupted_not_passed'
    for name in ('targeted-first.json', 'targeted-first.log', 'targeted-second.json', 'targeted-second.log',
                 'full-interrupted.json', 'full-interrupted.log', 'full-interruption-observation.json',
                 'precision-diagnostic.json', 'precision-encoded-static-diagnostic.json', 'text-shadow-range-diagnostic.json',
                 'development/targeted-first-test.py'):
        p = EVIDENCE/name; files.append({'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)})
    record = {'status': 'preserved_and_verified', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'generator_sha256': sha(Path(__file__)), 'runs': runs, 'files': files, 'file_count': len(files),
        'total_bytes': sum(f['bytes'] for f in files), 'interrupted_full_suite_not_passed': True,
        'raw_bytes_unchanged': True, 'partial_pass_counts_merged': False,
        'scope': 'Preserved raw data and exact executed generators; no claim to have reproduced every first-version source beyond its frozen map.'}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: record[k] for k in ('status', 'file_count', 'total_bytes')}))

if __name__ == '__main__': run()
