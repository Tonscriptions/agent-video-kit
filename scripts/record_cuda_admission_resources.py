"""Read one UUID-bound driver snapshot and redact unrelated process details."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def run(output):
    if output.exists():raise ValueError('fresh resource observation required')
    earlier=ROOT/'docs/validation/evidence/cuda-admission-20261019-v60/native-r1.json'
    identity=json.loads(earlier.read_bytes())['before_allocation']['device_uuid']
    if not re.fullmatch(r'GPU-[0-9a-f-]{36}',identity):raise ValueError('previously measured full UUID required')
    command=[shutil.which('nvidia-smi'),'--id='+identity,'--query-gpu=uuid,memory.total,memory.free,memory.used','--format=csv,noheader,nounits']
    response=subprocess.run(command,capture_output=True,check=True,timeout=10)
    rows=list(csv.reader(response.stdout.decode('ascii').strip().splitlines()))
    if len(rows)!=1 or len(rows[0])!=4 or rows[0][0].strip()!=identity:raise ValueError('unexpected driver identity')
    total,free,used=(int(value.strip())*1024**2 for value in rows[0][1:])
    if min(total,free,used)<0 or free>total or used>total:raise ValueError('invalid driver counters')
    # These PIDs were separately inspected during this run. Only dates and IDs
    # leave this diagnostic; unrelated titles, command lines and paths are redacted.
    script="""[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$items=@(Get-CimInstance Win32_Process -Filter 'ProcessId=14924 OR ProcessId=31072 OR ProcessId=17556 OR ProcessId=21520 OR ProcessId=17580' | ForEach-Object {
  [ordered]@{pid=$_.ProcessId; started_at_utc=$_.CreationDate.ToUniversalTime().ToString('o'); matches_first_run_workdir=[bool]($_.CommandLine -match 'cuda-admission-vace-real-20261019-v60(?![-\\w])')}
})
ConvertTo-Json -InputObject $items -Compress
"""
    shell=shutil.which('pwsh') or shutil.which('powershell')
    processes=subprocess.run([shell,'-NoLogo','-NoProfile','-NonInteractive','-Command',script],capture_output=True,check=True,timeout=30)
    items=json.loads(processes.stdout.decode('utf-8-sig'))
    record={'status':'observed_shared_gpu_resources_no_mutation','observed_at_utc':datetime.now(timezone.utc).isoformat(),
        'device_uuid':identity,'identity_source_sha256':sha(earlier),'driver_command':command,
        'physical_total_bytes':total,'physical_free_bytes':free,'physical_used_bytes':used,
        'original_run_pid_observations':[row for row in items if row['pid'] in (14924,31072,17556)],
        'separately_observed_native_processes':[row for row in items if row['pid'] in (21520,17580)],
        'external_process_titles_paths_and_command_lines_redacted':True,'per_process_gpu_bytes_attributed':False,
        'runtime_admission':False,'cuda_context_created':False,'torch_imported':False,'allocations_performed':0,
        'processes_modified':False,'virtualization':False,'browser':False,'generator_sha256':sha(Path(__file__))}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':record['status'],'physical_free_mib':free//1024**2,'other_native_processes':len(record['separately_observed_native_processes'])}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve())
