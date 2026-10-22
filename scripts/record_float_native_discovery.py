"""Record actual test discovery separately from any executed complete suite."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from run_frozen_regression import frozen, sha
ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / 'docs/validation/evidence/float-render-20261022-lab/discovery-r1.json'
    assert not out.exists()
    before = frozen()
    command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c',
        'import sys,unittest;sys.path.insert(0,sys.argv[1]);from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();print(unittest.defaultTestLoader.discover(sys.argv[2]).countTestCases())',
        str(ROOT / 'product/src'), str(ROOT / 'product/tests')]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    count = int(result.stdout.strip()) if result.returncode == 0 else None
    record = {'status': 'passed-discovery-only' if count == 2320 else 'failed-preserved',
        'at_utc': datetime.now(timezone.utc).isoformat(), 'command': command,
        'exit_code': result.returncode, 'stdout': result.stdout.decode('utf8', 'replace'),
        'stderr': result.stderr.decode('utf8', 'replace'), 'discovered_methods': count,
        'executed_full_methods': 0, 'frozen_before': before, 'frozen_after': frozen(),
        'generator_sha256': sha(Path(__file__)), 'native_windows': True, 'network': False,
        'virtualization': False}
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    assert result.returncode == 0 and count == 2320 and frozen() == before and len(before) == 296
    print(json.dumps({'status': record['status'], 'discovered': count, 'executed_full': 0}))


if __name__ == '__main__':
    main()
