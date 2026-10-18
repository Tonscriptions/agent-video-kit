"""Record one read-only global GPU snapshot alongside a research worker phase."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work', type=Path, required=True)
args = parser.parse_args()
work = args.work.resolve()
command = ['nvidia-smi', '--query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu',
           '--format=csv,noheader,nounits']
started = datetime.now(timezone.utc).isoformat()
result = subprocess.run(command, capture_output=True, check=True, timeout=20)
rows = list(csv.reader(result.stdout.decode('utf-8').splitlines()))
assert len(rows) == 1
name, total, free, used, utilization = [value.strip() for value in rows[0]]
response = json.loads((work/'worker-response.json').read_bytes())
record = {'query_started_at_utc': started, 'query_ended_at_utc': datetime.now(timezone.utc).isoformat(),
    'command': command, 'stdout': result.stdout.decode('utf-8'), 'name': name,
    'total_mib': int(total), 'free_mib': int(free), 'used_mib': int(used),
    'utilization_percent': int(utilization), 'worker_status': response['status'],
    'worker_last_recorded_phase': response['phases'][-1]['phase'],
    'read_only': True, 'model_forward_calls_during_sampling': 0,
    'sampler_sha256': 'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (work/'gpu-resource-snapshots.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write(json.dumps(record, ensure_ascii=False)+'\n')
(work/'executed-gpu-sampler.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(record, ensure_ascii=False))
