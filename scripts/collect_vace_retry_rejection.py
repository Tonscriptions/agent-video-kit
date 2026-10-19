"""Extract the real V63 GPU rejection from preserved logs; do not run a model."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/vace-delivery-20261019-v63-r1'
WORK=ROOT/'product/.runtime/cuda-admission-vace-20261019-v63-r1/actual/project'
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    target=BASE/'admission-and-cleanup.json'
    if target.exists():raise ValueError('preserve prior observation; choose a new receipt')
    raw=(BASE/'actual-vace.stderr.log').read_text(encoding='utf-8')
    outer=json.loads(raw.rsplit('RuntimeError: ',1)[1].strip())
    error=outer['errors'][0];cause=error['cause']
    start=cause.index('{',cause.index('"gpu_admission_failure"'))
    admission=json.JSONDecoder().raw_decode(cause[start:])[0]
    if admission['status']!='rejected' or admission['stage']!='text-weights':raise ValueError('expected actual text gate rejection missing')
    project=json.loads((WORK/'project.json').read_bytes())
    command="Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','ffmpeg.exe') -and ($_.CommandLine -like '*cuda-admission-vace-20261019-v63-r1*' -or $_.CommandLine -like '*joint-video-worker-*') } | Select-Object ProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Depth 4 -Compress"
    p=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,check=True,timeout=30)
    (BASE/'owned-process-snapshot.stdout.json').write_bytes(p.stdout)
    (BASE/'owned-process-snapshot.stderr.log').write_bytes(p.stderr)
    observed=json.loads(p.stdout.decode('utf-8-sig')) if p.stdout.strip() else []
    if isinstance(observed,dict):observed=[observed]
    if observed:raise ValueError('matching worker remains; inspect before claiming cleanup')
    assets=project.get('assets',{});sequences=project.get('sequences',{})
    if isinstance(sequences,dict):sequences=sequences.values()
    elif isinstance(sequences,list):pass
    else:raise ValueError('unknown sequence structure')
    tracks=[t for s in sequences for t in (s.get('tracks',{}).values() if isinstance(s.get('tracks'),dict) else s.get('tracks',[]))]
    clips=sum(len(t.get('clips',[])) for t in tracks)
    outputs=[p for p in (WORK/'outputs').rglob('*') if p.is_file()]
    shutil.copyfile(WORK/'project.json',BASE/'project-after-rejection.json')
    record={'status':'observed_real_v63_admission_rejection_no_delivery','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'outer_error_code':error['code'],'gpu_admission_failure':admission,'actual_worker_elapsed_seconds':835.8593301000001,
        'source_log_sha256':sha(BASE/'actual-vace.stderr.log'),'extraction':'JSON envelope then raw_decode of complete embedded gpu_admission_failure object',
        'original_response_retained_as_separate_file':False,'original_worker_cause_truncated_by_outer_envelope':True,
        'source_assets':len(assets),'timeline_clips':clips,'registered_output_files':len(outputs),
        'project_after_sha256':sha(BASE/'project-after-rejection.json'),'repaired_video':False,'model_forwards':0,
        'no_model_forward_basis':'text-weights admission precedes tokenizer and from_pretrained in unchanged vace_model.py',
        'owned_process_snapshot':{'query':command,'matching_processes':observed,'matched_count':0,
            'continuous_process_monitor':False,'observed_after_terminal_exit':True,'unrelated_processes_terminated':False,
            'stdout_sha256':sha(BASE/'owned-process-snapshot.stdout.json'),'stderr_sha256':sha(BASE/'owned-process-snapshot.stderr.log')},
        'natural_quality_accepted':False,'full_capcut_parity':False,'generator_sha256':sha(Path(__file__))}
    if clips or outputs:raise ValueError('unexpected registered edit/output after rejection')
    save(target,record)
    print(json.dumps({'status':record['status'],'physical_free_mib':admission['physical_free_bytes']/1048576,
                      'required_free_mib':admission['required_free_bytes']/1048576,'matching_processes':0}))

if __name__=='__main__':main()
