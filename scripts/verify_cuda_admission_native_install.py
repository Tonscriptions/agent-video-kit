"""Install local fixed wheels and execute the shipped CUDA admission code natively."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(bundle,work,evidence,public,native_python,cpu_only=False):
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    public.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(Path(__file__),evidence/'executed-installer-check.py')
    before=frozen();calls=[]
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_before':before,'model_forward_calls':0,'calls':calls,'virtual_environment':False,
        'network_used':False,'other_machine_accepted':False,'cpu_only':cpu_only,
        'cuda_probe_executed':False,'generator_sha256':sha(Path(__file__))}
    def command(args,name,timeout=180):
        result=subprocess.run(list(map(str,args)),cwd=work,env=env,capture_output=True,timeout=timeout)
        (evidence/(name+'.stdout.log')).write_bytes(result.stdout)
        (evidence/(name+'.stderr.log')).write_bytes(result.stderr)
        calls.append({'name':name,'command':list(map(str,args)),'exit_code':result.returncode,
            'stdout_sha256':sha(evidence/(name+'.stdout.log')),'stderr_sha256':sha(evidence/(name+'.stderr.log'))})
        save(evidence/'verification.json',record)
        if result.returncode:raise RuntimeError(name+' failed: '+result.stderr.decode('utf-8',errors='replace')[-1000:])
        return result
    env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),
        PYTHONDONTWRITEBYTECODE='1',AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    try:
        target=work/'installed'
        command([sys.executable,'-I','-B','-X','utf8',bundle/'install.py','--bundle',bundle,
            '--target',target,'--manifest-sha256',sha(bundle/'manifest.json')],'install')
        wheel=next((bundle/'wheels').glob('ai_ad_editor-*.whl'));installed={}
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'):continue
                paths=list(target.rglob(name))
                if len(paths)!=1 or paths[0].read_bytes()!=archive.read(name) or paths[0].read_bytes()!=(ROOT/'product/src'/name).read_bytes():
                    raise ValueError('installed source/wheel bytes differ: '+name)
                installed[name]=sha(paths[0])
        if 'ai_ad_editor/cuda_admission.py' not in installed:raise ValueError('new admission module not shipped')
        caps=json.loads(command([sys.executable,'-I','-S','-B','-X','utf8',target/'run.py','capabilities'],'capabilities').stdout)
        def find(node):
            if isinstance(node,dict):
                if node.get('engine')=='diffusers-wan-vace-local-v1' and 'cuda_admission' in node:return node['cuda_admission']
                for value in node.values():
                    result=find(value)
                    if result:return result
            elif isinstance(node,list):
                for value in node:
                    result=find(value)
                    if result:return result
        policy=find(caps)
        if not policy or policy['policy']!='cuda-uuid-physical-and-torch-free-v1' or policy['reservation'] or policy['oom_guarantee']:
            raise ValueError('installed capabilities did not expose the actual bounded policy')
        command([sys.executable,'-I','-S','-B','-X','utf8',target/'run.py','schema','show'],'schema')
        if not cpu_only:
            source=next(target.rglob('ai_ad_editor/cuda_admission.py')).parent.parent
            record['cuda_probe_executed']=True
            command([native_python,'-I','-B','-X','utf8',ROOT/'scripts/probe_vace_cuda_admission.py',
                '--source',source,'--runtime',work/'native-probe-runtime','--output',evidence/'native-installed.json',
                '--allocation-mib','0'],'native-installed',timeout=900)
            probe=json.loads((evidence/'native-installed.json').read_bytes())
            if probe['status']!='passed_native_cuda_sampling_allocation_and_loader_rejection' or probe['model_forward_calls'] or probe['model_weights_loaded']:
                raise ValueError('installed native admission probe did not pass')
            if Path(probe['imported_admission']).resolve()!=source/'ai_ad_editor/cuda_admission.py':
                raise ValueError('installed probe loaded the wrong helper')
        if frozen()!=before:raise ValueError('product inputs changed during native installation check')
        for name,path in [('agent-video-kit-cp313-win_amd64.zip',bundle.with_suffix('.zip')),
                          ('release-manifest.json',bundle/'manifest.json'),('install-receipt.json',target/'receipt.json')]:
            shutil.copyfile(path,public/name)
        record.update(status='passed_native_install_and_cli_cuda_pending' if cpu_only else 'passed_native_install_and_cuda_admission',frozen_after=frozen(),
            installed_package_files=len(installed),installed_files=installed,
            package_bytes_equal_to_wheel_and_source=True,isolated_cli_calls=2,
            installed_cuda_probe_sha256=None if cpu_only else sha(evidence/'native-installed.json'),
            release_zip_sha256=sha(public/'agent-video-kit-cp313-win_amd64.zip'),
            manifest_sha256=sha(public/'release-manifest.json'),capabilities_cuda_admission=policy)
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(evidence/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('status','installed_package_files','isolated_cli_calls')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','work','evidence','public','native-python'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--cpu-only',action='store_true',help='Verify package bytes and isolated CLI; mark CUDA verification pending explicitly')
    args=parser.parse_args();run(**{key:value.resolve() if isinstance(value,Path) else value for key,value in vars(args).items()})
