"""Run four existing native CLI clock controls with exact frozen evidence."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from run_frozen_regression import frozen
from run_empty_native_after_nested import read, save, sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/native-empty-window-20261021-lab'
METHODS = ['test_cli.P0CliTests.' + name for name in (
    'test_nested_sequence_speed_curve_renders_locally',
    'test_nested_sequence_speed_curve_maps_source_boundaries',
    'test_nested_sequence_reverse_preserves_temporal_order',
    'test_nested_sequence_speed_and_parent_rotation_are_composed')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(REL) and not output.exists() and not output.with_suffix('.log').exists()
    before = frozen()
    assert before == read(REL / 'parent-contract-refresh-r1.json')['frozen_after']
    bootstrap = ('import sys,unittest;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];'
                 'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
                 'unittest.main(module=None)')
    command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap,
               str(ROOT / 'product/src'), str(ROOT / 'product/tests'), '-v', *METHODS]
    temporary = ROOT / 'product/.runtime/temp'
    temporary.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
               PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT / 'product/src'))
    record = {'status': 'running', 'command': command, 'method_ids': METHODS,
              'frozen_before': before, 'native_windows': sys.platform == 'win32', 'virtualization': False,
              'started_at_utc': datetime.now(timezone.utc).isoformat(), 'generator_sha256': sha(__file__)}
    save(output, record)
    output.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
    with output.with_suffix('.log').open('xb') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    text = output.with_suffix('.log').read_text('utf8')
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
    after = frozen()
    ok = result.returncode == 0 and bool(re.search(r'\bOK\s*$', text))
    record.update(status='passed' if ok else 'failed', terminal_ok=ok, exit_code=result.returncode,
                  methods=int(match[1]) if match else None, suite_seconds=float(match[2]) if match else None,
                  skipped=text.count(' ... skipped'), frozen_after=after, frozen_equal=before == after,
                  log_sha256=sha(output.with_suffix('.log')), finished_at_utc=datetime.now(timezone.utc).isoformat())
    save(output, record)
    print(json.dumps({k: record[k] for k in ('status', 'methods', 'suite_seconds', 'frozen_equal')}))
    assert ok and record['methods'] == 4 and record['skipped'] == 0 and record['frozen_equal']


if __name__ == '__main__':
    main()
