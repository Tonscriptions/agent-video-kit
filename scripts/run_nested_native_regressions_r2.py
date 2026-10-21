"""Serial related regressions with frozen core and committed external fixtures."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
REL = Path('docs/validation/evidence/nested-native-clock-20261021-lab')
FAMILIES = [('index', 'test_native_video_index*.py', 37),
            ('reverse', 'test_reverse_*.py', 50),
            ('sequence', 'test_sequence*.py', 63),
            ('preview', 'test_timeline_preview.py', 22),
            ('nested', 'test_nested*.py', 105)]


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'rubberband', 'html-runtime'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    assert work.is_relative_to(ROOT / 'product/.runtime') and not work.exists()
    work.mkdir(parents=True)
    output = ROOT / REL / 'related-r2.json'
    assert not output.exists()
    scripts = {name: sha(ROOT / 'scripts' / name) for name in
               ('run_nested_native_regressions_r2.py', 'run_with_regression_fixtures.py',
                'run_frozen_regression.py', 'materialize_regression_fixtures.py')}
    before = frozen()
    native = json.loads((ROOT / REL / 'final-native-clock-r1.json').read_bytes())
    assert len(before) == 255 and native['terminal_ok'] and native['methods'] == 32
    refresh = json.loads((ROOT / REL / 'contract-refresh-r1.json').read_bytes())
    assert native['frozen_before'] == native['frozen_after'] == refresh['frozen_before']
    assert before == refresh['frozen_after'] and refresh['runtime_inputs_changed'] is False
    state = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
             'native_windows': sys.platform == 'win32', 'virtualization': False, 'network': False,
             'frozen_before': before, 'script_hashes': scripts, 'expected_distinct_methods': 277,
             'families': {}, 'method_ids': []}
    def save():
        output.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    try:
        for label, pattern, count in FAMILIES:
            state['current_family'] = label
            save()
            target = ROOT / REL / (label + '-final-r2.json')
            assert not target.exists()
            command = [sys.executable, '-E', '-B', '-X', 'utf8',
                       str(ROOT / 'scripts/run_with_regression_fixtures.py'),
                       '--fixture-manifest', str(ROOT / REL / 'external-fixtures-r1.json'),
                       '--pattern', pattern, '--output', str(target),
                       '--rubberband', str(args.rubberband.resolve(strict=True)),
                       '--html-runtime', str(args.html_runtime.resolve(strict=True))]
            with (work / (label + '.launcher.log')).open('wb') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=3600)
            item = json.loads(target.read_bytes())
            assert result.returncode == 0 and item['status'] == 'passed' and item['terminal_ok'], label
            assert item['methods'] == count and item['skipped'] == 0, label
            assert item['frozen_before'] == item['frozen_after'] == before, label
            assert item['external_fixture_count'] == 8 and item['external_fixtures_equal'], label
            assert item['verification_scripts_equal'] and item['external_fixture_manifest_unchanged'], label
            text = target.with_name(target.stem + '.source.log').read_text('utf8', errors='replace')
            names = re.findall(r'^test_\w+ \(([^)\r\n]+)\)', text, flags=re.M)
            assert len(names) == len(set(names)) == count and not set(names) & set(state['method_ids']), label
            state['method_ids'].extend(names)
            state['families'][label] = {'pattern': pattern, 'methods': count,
                                        'suite_seconds': item['suite_seconds'], 'evidence_sha256': sha(target)}
            assert frozen() == before
            assert all(sha(ROOT / 'scripts' / name) == digest for name, digest in scripts.items())
            save()
        assert len(state['method_ids']) == 277
        state.update(status='passed-related-regressions', distinct_methods=277, skipped=0)
    except BaseException as caught:
        state.update(status='failed', error={'type': type(caught).__name__, 'message': str(caught)})
        raise
    finally:
        state.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen())
        state['frozen_equal'] = state['frozen_after'] == before
        save()
        print(json.dumps({k: state.get(k) for k in ('status', 'distinct_methods', 'current_family', 'frozen_equal', 'error')}), flush=True)


if __name__ == '__main__':
    main()
