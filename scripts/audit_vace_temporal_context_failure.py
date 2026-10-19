"""Retain actual VACE admission rejection, original diagnostics and rollback scope."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/vace-temporal-context-20261020-v68/previous-r1'
PROJECT=ROOT/'product/.runtime/vace-temporal-context-20261020-v68/previous-r1/project'


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def author_metadata():
    paths=[PROJECT/'project.json',PROJECT/'rights-ledger.json',PROJECT/'models/visual-adapters.json']
    return {p.relative_to(PROJECT).as_posix():sha(p) for p in paths if p.exists()}


def main():
    out=BASE/'failure-r1';out.mkdir(exist_ok=False)
    shutil.copyfile(__file__,out/'executed-failure-audit.py')
    original=read(BASE/'outpaint.stdout.log');run=read(BASE/'verification.json')
    assert run['status']=='failed' and next(c for c in run['calls'] if c['name']=='outpaint')['exit_code']==6
    error=original['errors'][0];ref=error['diagnostics']
    assert error['code']=='MATTING_PIPELINE_FAILED' and ref['status']=='stored'
    source=PROJECT/ref['manifest'];assert sha(source)==ref['manifest_sha256']
    manifest=read(source);response_path=source.parent/'response.json';response=read(response_path)
    assert response['fields']['status']=='failed'
    assert response['worker_error']=='worker error - CudaAdmissionError: CUDA_ADMISSION_INSUFFICIENT_PHYSICAL_FREE'
    # The bounded response summary deliberately omits arbitrary nested fields.
    # Preserve its schema; recover only the complete object retained in the
    # original CLI's diagnostic cause, never fabricate a missing worker report.
    cause=error['cause'];marker=cause.index('"gpu_admission_failure"')
    start=cause.index('{',marker);failure,used=json.JSONDecoder().raw_decode(cause[start:])
    assert failure['error_code']=='CUDA_ADMISSION_INSUFFICIENT_PHYSICAL_FREE'
    assert failure['stage']=='text-weights' and failure['status']=='rejected'
    assert failure['required_free_bytes']==(7168+768)*1024**2
    assert failure['physical_free_bytes']<failure['required_free_bytes']
    assert failure['effective_free_bytes']==min(failure['torch_free_bytes'],failure['physical_free_bytes'])
    assert manifest['operation_id']==original['operation_id']
    target=out/'record';shutil.copytree(source.parent,target)
    for name,item in manifest['files'].items():
        assert sha(target/name)==item['sha256'] and (target/name).stat().st_size==item['bytes']
    before=author_metadata();calls=[]
    prefix=[sys.executable,'-E','-B','-X','utf8','-c',
        'import sys;sys.path.insert(0,'+repr(str(ROOT/'product/src'))+');from ai_ad_editor.cli import main;raise SystemExit(main())']
    for label,argv in (
        ('list',['diagnostics','list','--project',str(PROJECT),'--operation-id',original['operation_id']]),
        ('show',['diagnostics','show','--project',str(PROJECT),'--diagnostic-id',ref['diagnostic_id'],
            '--expected-manifest-sha256',ref['manifest_sha256'],'--include-logs']),
        ('export',['diagnostics','export','--project',str(PROJECT),'--diagnostic-id',ref['diagnostic_id'],
            '--output',str(out/'failure.zip')]),
        ('policy',['policy','audit','--project',str(PROJECT)])):
        argv=[*prefix,*argv];result=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=180)
        stdout=out/(label+'.stdout.log');stderr=out/(label+'.stderr.log')
        stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
        calls.append({'name':label,'command':argv,'exit_code':result.returncode,'stdout':stdout.name,
            'stderr':stderr.name,'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr)})
        if result.returncode:
            save(out/'failed-audit.json',{'calls':calls,'last_exit':result.returncode})
            raise RuntimeError(label+' rejected; original logs retained')
    with zipfile.ZipFile(out/'failure.zip') as archive:
        assert set(archive.namelist())=={'manifest.json',*manifest['files']}
        for name in archive.namelist():assert archive.read(name)==(target/name).read_bytes()
    project=read(PROJECT/'project.json')
    expanded=[a for a in project['assets'] if a['id']=='expanded']
    output_exists=(PROJECT/'assets/derived/expanded.mov').exists()
    cache_empty=not list((PROJECT/'cache/inpainting').iterdir())
    assert not expanded and not output_exists and cache_empty
    assert not (PROJECT/'operations/project-transaction.json').exists()
    after=author_metadata();assert before==after
    value={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'actual original admission rejection and post-failure read-only diagnostics; no model rerun',
        'calls':calls,'original_cli_exit':6,'original_cli_sha256':sha(BASE/'outpaint.stdout.log'),
        'operation_id':original['operation_id'],'diagnostic':ref,'worker_error':response['worker_error'],
        'gpu_admission_failure':failure,'admission_source':'complete retained object in original errors[0].cause',
        'admission_object_sha256':'sha256:'+hashlib.sha256(cause[start:start+used].encode('utf8')).hexdigest(),
        'accepted_vace_forwards':0,'generated_output_exists':output_exists,
        'expanded_asset_registered':bool(expanded),'cache_empty':cache_empty,
        'metadata_before_diagnostic_queries':before,'metadata_after_diagnostic_queries':after,
        'metadata_before_outpaint_captured':False,
        'rollback_limit':'checks absence of failed asset/output/cache/journal; pre-outpaint author bytes were not captured',
        'processes':manifest['processes'],'first_failure_roles':manifest['trigger']['first_failure_roles'],
        'root_cause_field':manifest['root_cause'],'archive_sha256':sha(out/'failure.zip'),
        'record_bytes':sum(p.stat().st_size for p in target.iterdir()),'archive_bytes':(out/'failure.zip').stat().st_size,
        'budget_or_sampling_lowered':False,'other_gpu_tasks_stopped':False,'native_crash_reproduced':False,
        'natural_quality_accepted':False,'full_capcut_parity':False}
    save(out/'verification.json',value)
    print(json.dumps({k:value[k] for k in ('status','worker_error','accepted_vace_forwards','cache_empty','archive_bytes')}))


if __name__=='__main__':main()
