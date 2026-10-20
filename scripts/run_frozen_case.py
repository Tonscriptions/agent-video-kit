"""Run one named native unittest with complete before/after input receipts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from run_frozen_regression import ROOT, frozen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
assert re.fullmatch(r'test_[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.test_[A-Za-z0-9_]+', args.case)
output = args.output.resolve(); log = output.with_suffix('.log')
assert output.is_relative_to(ROOT / 'docs') and not output.exists() and not log.exists()
output.parent.mkdir(parents=True, exist_ok=True)
bootstrap = ('import sys,unittest;sys.path.insert(0,sys.argv.pop(1));'
             'sys.path.insert(0,sys.argv.pop(1));'
             'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
             'unittest.main(module=None)')
command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap,
           str(ROOT / 'product/src'), str(ROOT / 'product/tests'), args.case, '-v']
record = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'case': args.case,
          'command': command, 'frozen_before': frozen(), 'native_windows': sys.platform == 'win32',
          'virtualization': False, 'generator_sha256': 'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
def save():
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
save(); env = dict(os.environ); temp = ROOT / 'product/.runtime/temp'; temp.mkdir(parents=True, exist_ok=True)
env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT / 'product/src'))
started = time.monotonic()
with log.open('wb') as stream:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
text = log.read_text(encoding='utf8'); match = re.search(r'Ran (\d+) tests? in ([\d.]+)s', text)
record.update(exit_code=result.returncode, methods=int(match[1]) if match else None,
              suite_seconds=float(match[2]) if match else None, wall_seconds=time.monotonic()-started,
              skipped=len(re.findall(r'\.\.\. skipped ', text)), terminal_ok=bool(re.search(r'\bOK\s*$', text)),
              frozen_after=frozen(), log_sha256='sha256:'+hashlib.sha256(log.read_bytes()).hexdigest(),
              finished_at_utc=datetime.now(timezone.utc).isoformat())
record['frozen_equal'] = record['frozen_before'] == record['frozen_after']; save()
print(json.dumps({k:record[k] for k in ('exit_code','methods','suite_seconds','skipped','frozen_equal','terminal_ok')}))
raise SystemExit(0 if result.returncode == 0 and record['terminal_ok'] and record['frozen_equal'] else 1)
