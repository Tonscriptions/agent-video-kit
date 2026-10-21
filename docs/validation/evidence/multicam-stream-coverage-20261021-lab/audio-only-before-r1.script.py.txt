"""Run the exact two analysis-only/authoring controls, retaining their actual outcome."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from run_frozen_regression import frozen


ROOT = Path(__file__).resolve().parents[1]
NAMES = ['test_multicam_stream_coverage.NativeMulticamStreamCoverageTests.' + name for name in (
    'test_unknown_video_eof_still_returns_audio_only_sync_diagnostics',
    'test_unknown_video_eof_still_refuses_requested_switch_without_writes')]


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'docs/validation/evidence') and not output.exists() and not output.with_suffix('.log').exists()
    before = frozen()
    bootstrap = 'import sys,unittest;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();unittest.main(module=None)'
    command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, str(ROOT / 'product/src'), str(ROOT / 'product/tests'), '-v', *NAMES]
    temporary = ROOT / 'product/.runtime/temp'
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary), PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT / 'product/src'))
    with output.with_suffix('.log').open('xb') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
    text = output.with_suffix('.log').read_text('utf8')
    match = re.search(r'Ran (\d+) tests? in ([\d.]+)s', text)
    after = frozen()
    ids = re.findall(r'^test_\w+ \(([^)\r\n]+)\)', text, re.M)
    ok = result.returncode == 0 and bool(re.search(r'\bOK\s*$', text)) and match is not None and int(match[1]) == 2
    record = {'status': 'passed' if ok else 'failed', 'terminal_ok': ok, 'exit_code': result.returncode,
        'methods': int(match[1]) if match else None, 'suite_seconds': float(match[2]) if match else None,
        'skipped': text.count(' ... skipped'), 'method_ids': ids, 'distinct_methods': len(set(ids)),
        'command': command, 'frozen_before': before, 'frozen_after': after, 'frozen_equal': before == after,
        'log_sha256': sha(output.with_suffix('.log')), 'script_sha256': sha(__file__), 'virtualization': False, 'network': False}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    output.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({key: record[key] for key in ('status', 'methods', 'suite_seconds', 'frozen_equal')}))
    assert before == after and len(ids) == len(set(ids)) == 2
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
