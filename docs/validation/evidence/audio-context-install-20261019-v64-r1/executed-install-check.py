"""Install fixed local wheels, run the shipped CLI, and compare decoded media."""
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
def read(path):return json.loads(path.read_bytes())
def save(path,v):path.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def run(bundle,work,evidence,public,source,rubberband):
    for p in (work,evidence,public):p.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(Path(__file__),evidence/'executed-install-check.py')
    before=frozen();calls=[]
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
            'frozen_before':before,'calls':calls,'network':'disabled','virtual_environment':False,
            'other_machine_accepted':False,'native_python_ffmpeg_r3_models_included':False}
    env=dict(os.environ,TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1',
             AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    def command(args,name,timeout=180):
        args=list(map(str,args));p=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,timeout=timeout)
        out=evidence/(name+'.stdout.log');err=evidence/(name+'.stderr.log')
        out.write_bytes(p.stdout);err.write_bytes(p.stderr)
        calls.append({'name':name,'command':args,'exit_code':p.returncode,'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        save(evidence/'verification.json',record)
        if p.returncode:raise ValueError(name+' failed: '+p.stdout.decode('utf-8','replace')[-3000:]+p.stderr.decode('utf-8','replace')[-3000:])
        return p.stdout
    try:
        target=work/'installed'
        command([sys.executable,'-I','-B','-X','utf8',bundle/'install.py','--bundle',bundle,
                 '--target',target,'--manifest-sha256',sha(bundle/'manifest.json')],'install')
        installed={};wheel=next((bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'):continue
                candidates=list(target.rglob(name))
                if len(candidates)!=1 or candidates[0].read_bytes()!=archive.read(name) or archive.read(name)!=(ROOT/'product/src'/name).read_bytes():
                    raise ValueError('installed/source/wheel bytes differ: '+name)
                installed[name]=sha(candidates[0])
        caps=json.loads(command([sys.executable,'-I','-S','-B','-X','utf8',target/'run.py','capabilities'],'capabilities'))
        if 'explicit_r3_real_source_context' not in json.dumps(caps):raise ValueError('installed source context capability missing')
        schema=json.loads(command([sys.executable,'-I','-S','-B','-X','utf8',target/'run.py','schema','show'],'schema'))
        if 'source_context_ms' not in json.dumps(schema):raise ValueError('installed schema lacks context field')
        command([sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_audio_source_context.py',
                 '--work',work/'media','--output',public/'media','--installed',target,'--rubberband',rubberband],
                'installed-media',timeout=1800)
        actual=read(public/'media/verification.json');expected=read(source/'verification.json')
        if actual['frozen_before']!=before or not actual['frozen_equal']:raise ValueError('installed verification not same frozen product')
        for c in actual['calls']:
            if c['kind']=='cli' and str(target/'run.py') not in c['command']:raise ValueError('installed case used source CLI')
        comparisons=[]
        for a,b in zip(actual['records'],expected['records'],strict=True):
            if a['id']!=b['id']:raise ValueError('case IDs differ')
            for variant in ('zero','context'):
                x,y=a['variants'][variant],b['variants'][variant]
                for field in ('frames','stereo_sample_frames','rgb_sha256','pcm_sha256','source_context','peaks_hz'):
                    if x[field]!=y[field]:raise ValueError(a['id']+' installed differs: '+field)
                comparisons.append({'id':a['id'],'variant':variant,'rgb_equal':True,'pcm_equal':True,
                                    'frames':x['frames'],'stereo_sample_frames':x['stereo_sample_frames']})
        for name,path in [('agent-video-kit-cp313-win_amd64.zip',bundle.with_suffix('.zip')),
                          ('release-manifest.json',bundle/'manifest.json'),('install-receipt.json',target/'receipt.json')]:
            shutil.copyfile(path,public/name)
        record.update(status='passed_isolated_install_and_decoded_audio_context',installed_package_files=len(installed),
            installed_files=installed,package_bytes_equal_to_wheel_and_source=True,isolated_control_cli_calls=2,
            isolated_media_cli_calls=sum(x['kind']=='cli' for x in actual['calls']),comparisons=comparisons,
            baseline_cli_calls_separate=sum(x['kind']=='baseline-cli' for x in actual['calls']),
            release_zip_sha256=sha(public/'agent-video-kit-cp313-win_amd64.zip'),
            manifest_sha256=sha(public/'release-manifest.json'),installed_media_receipt_sha256=sha(public/'media/verification.json'))
    except BaseException as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
    finally:
        after=frozen();record.update(frozen_after=after,frozen_equal=before==after,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(evidence/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('status','installed_package_files','isolated_control_cli_calls','isolated_media_cli_calls')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','work','evidence','public','source','rubberband'):p.add_argument('--'+name,type=Path,required=True)
    run(**{k:v.resolve() for k,v in vars(p.parse_args()).items()})
