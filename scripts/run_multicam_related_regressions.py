"""Run the camera candidate with native clocks, empty ranges and media CLI controls."""
from datetime import datetime, timezone
import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from run_frozen_regression import frozen
from smoke_multicam_source_range import sha, write

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/multicam-source-range-20261021-lab'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rubberband', 'html-runtime'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    output = REL / 'related-r1.json'
    assert not output.exists() and not output.with_suffix('.log').exists()
    read = lambda path: json.loads(Path(path).read_bytes())
    before = frozen()
    assert before == read(REL / 'parent-contract-refresh-r1.json')['frozen_after'] and len(before) == 257
    fixtures = read(REL / 'external-fixtures-r1.json')
    assert fixtures['status'] == 'passed' and fixtures['fixture_count'] == 8
    fixture_inputs = {row['path']: row['sha256'] for row in fixtures['fixtures']}
    assert all(sha(ROOT / name) == digest for name, digest in fixture_inputs.items())
    tree = ast.parse((ROOT / 'product/tests/test_cli.py').read_text('utf8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'P0CliTests')
    media = [node.name for node in cls.body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')
             and any(word in node.name for word in ('multicam', 'beat_cut', 'smart_cut', 'highlight'))]
    assert len(media) == 6
    clocks = ['test_nested_sequence_speed_curve_renders_locally', 'test_nested_sequence_speed_curve_maps_source_boundaries',
              'test_nested_sequence_reverse_preserves_temporal_order', 'test_nested_sequence_speed_and_parent_rotation_are_composed']
    names = ['test_multicam_source_range', 'test_native_empty_window', 'test_nested_native_clock',
             *['test_cli.P0CliTests.' + name for name in [*media, *clocks]]]
    bootstrap = ('import sys,unittest;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];'
        'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();unittest.main(module=None)')
    command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap,
               str(ROOT / 'product/src'), str(ROOT / 'product/tests'), '-v', *names]
    temporary = ROOT / 'product/.runtime/temp'
    temporary.mkdir(parents=True, exist_ok=True)
    binary = args.rubberband.resolve(strict=True)
    html = args.html_runtime.resolve(strict=True)
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
        PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT / 'product/src'),
        AI_AD_EDITOR_TEST_RUBBERBAND=str(binary), AI_AD_EDITOR_TEST_HTML_RUNTIME=str(html))
    scripts = {name: sha(ROOT / 'scripts' / name) for name in ('run_multicam_related_regressions.py',
        'run_frozen_regression.py', 'materialize_regression_fixtures.py', 'refresh_multicam_parent_contract.py')}
    record = {'status': 'running', 'expected_methods': 80, 'selected_test_names': names, 'command': command,
        'frozen_before': before, 'fixture_inputs': fixture_inputs, 'fixture_manifest_sha256': sha(REL / 'external-fixtures-r1.json'),
        'script_hashes': scripts, 'native_windows': sys.platform == 'win32', 'virtualization': False, 'network': False,
        'rubberband_sha256': sha(binary), 'html_runtime_sha256': sha(html), 'started_at_utc': datetime.now(timezone.utc).isoformat()}
    write(output, record)
    output.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
    with output.with_suffix('.log').open('xb') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=3600)
    text = output.with_suffix('.log').read_text('utf8')
    match = re.search(r'Ran (\d+) tests? in ([\d.]+)s', text)
    ids = re.findall(r'^test_\w+ \(([^)\r\n]+)\)', text, flags=re.M)
    ok = result.returncode == 0 and bool(re.search(r'\bOK\s*$', text)) and match is not None and int(match[1]) == 80
    record.update(status='passed-related-regressions' if ok else 'failed', terminal_ok=ok, exit_code=result.returncode,
        methods=int(match[1]) if match else None, suite_seconds=float(match[2]) if match else None,
        skipped=text.count(' ... skipped'), method_ids=ids, distinct_methods=len(set(ids)),
        frozen_after=frozen(), log_sha256=sha(output.with_suffix('.log')), finished_at_utc=datetime.now(timezone.utc).isoformat())
    record['frozen_equal'] = record['frozen_before'] == record['frozen_after']
    record['fixtures_unchanged'] = all(sha(ROOT / name) == digest for name, digest in fixture_inputs.items())
    record['fixture_manifest_unchanged'] = sha(REL / 'external-fixtures-r1.json') == record['fixture_manifest_sha256']
    record['scripts_unchanged'] = all(sha(ROOT / 'scripts' / name) == digest for name, digest in scripts.items())
    write(output, record)
    print(json.dumps({key: record[key] for key in ('status', 'methods', 'distinct_methods', 'suite_seconds', 'frozen_equal')}))
    assert ok and len(ids) == len(set(ids)) == 80 and record['skipped'] == 0
    assert record['frozen_equal'] and record['fixtures_unchanged'] and record['fixture_manifest_unchanged'] and record['scripts_unchanged']


if __name__ == '__main__':
    main()
