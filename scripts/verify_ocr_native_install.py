"""Install seven fixed local wheels and exercise actual shipped OCR/camera CLI."""
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


def run(bundle,work,evidence,public,english,chinese):
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False);public.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(Path(__file__),evidence/'executed-install-check.py')
    before=frozen();calls=[]
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,
            'calls':calls,'generator_sha256':sha(Path(__file__)),'network_used':False,'virtual_environment':False,
            'weights_onnxruntime_opencv_python_ffmpeg_included':False,'other_machine_accepted':False}
    env=dict(os.environ,TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1',AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    def command(args,name,timeout=180):
        args=list(map(str,args));p=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,timeout=timeout)
        stdout=evidence/(name+'.stdout.log');stderr=evidence/(name+'.stderr.log');stdout.write_bytes(p.stdout);stderr.write_bytes(p.stderr)
        calls.append({'name':name,'command':args,'exit_code':p.returncode,'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr)})
        save(evidence/'verification.json',record)
        if p.returncode:raise ValueError(name+' failed: '+p.stdout.decode('utf-8','replace')[-2000:]+p.stderr.decode('utf-8','replace')[-2000:])
        return p.stdout
    try:
        target=work/'installed'
        command([sys.executable,'-I','-B','-X','utf8',bundle/'install.py','--bundle',bundle,'--target',target,
                 '--manifest-sha256',sha(bundle/'manifest.json')],'install')
        installed={};wheel=next((bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'):continue
                paths=list(target.rglob(name))
                if len(paths)!=1 or paths[0].read_bytes()!=archive.read(name) or paths[0].read_bytes()!=(ROOT/'product/src'/name).read_bytes():raise ValueError('installed bytes differ: '+name)
                installed[name]=sha(paths[0])
        for required in ('local_ocr.py','ocr_cli.py','ocr_worker.py','ocr_geometry.py','PADDLE_OCR_LICENSE.txt','PADDLE_OCR_NOTICE.txt'):
            if 'ai_ad_editor/'+required not in installed:raise ValueError('missing installed OCR file: '+required)
        caps=json.loads(command([sys.executable,'-I','-S','-B','-X','utf8',target/'run.py','capabilities'],'capabilities'))
        if 'ppocr-v4-onnx-cpu-local-v1' not in json.dumps(caps):raise ValueError('installed capability missing')
        command([sys.executable,'-I','-S','-B','-X','utf8',target/'run.py','schema','show'],'schema')
        comparisons=[]
        for kind,source in (('english',english),('chinese',chinese)):
            output=public/kind
            command([sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_local_ocr.py','--kind',kind,
                     '--work',work/kind,'--output',output,'--installed-root',target],kind+'-native',timeout=1200)
            receipt=json.loads((output/'verification.json').read_bytes())
            if receipt['status']!='passed_native_scan' or not receipt['frozen_equal'] or receipt['frozen_after']!=before:raise ValueError('installed native case failed')
            for call in receipt['calls']:
                if call['kind']=='cli' and str(target/'run.py') not in call['command']:raise ValueError('native case did not use installed isolated CLI')
            actual=json.loads((output/'ocr-report.json').read_bytes());expected=json.loads((source/'ocr-report.json').read_bytes())
            if actual['frames']!=expected['frames']:raise ValueError('installed OCR predictions differ from source')
            worker=next(a['path'] for a in actual['request']['adapter']['artifacts'] if a['role']=='ocr_worker.py')
            if not Path(worker).is_relative_to(target):raise ValueError('installed scan ran development worker')
            comparisons.append({'kind':kind,'frames_equal_to_source':True,'sampled_frames':len(actual['frames']),
                'detector_forwards':actual['response']['detector_forwards'],'recognizer_forwards':actual['response']['recognizer_forwards'],
                'worker_path':worker,'worker_sha256':sha(Path(worker)),'verification_sha256':sha(output/'verification.json')})
        command([sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/audit_local_ocr_media.py','--english',public/'english',
                 '--chinese',public/'chinese','--output',evidence/'installed-media'],'installed-media',timeout=600)
        for name,path in [('agent-video-kit-cp313-win_amd64.zip',bundle.with_suffix('.zip')),
                          ('release-manifest.json',bundle/'manifest.json'),('install-receipt.json',target/'receipt.json')]:shutil.copyfile(path,public/name)
        if before!=frozen():raise ValueError('product changed during installed verification')
        record.update(status='passed_native_isolated_install_ocr_and_encoded_camera',installed_package_files=len(installed),
            installed_files=installed,package_bytes_equal_to_wheel_and_source=True,isolated_cli_calls=2,
            native_comparisons=comparisons,release_zip_sha256=sha(public/'agent-video-kit-cp313-win_amd64.zip'),
            manifest_sha256=sha(public/'release-manifest.json'),installed_media_sha256=sha(evidence/'installed-media/verification.json'))
    except BaseException as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
    finally:
        after=frozen();record.update(frozen_after=after,frozen_equal=after==before,finished_at_utc=datetime.now(timezone.utc).isoformat());save(evidence/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('status','installed_package_files','isolated_cli_calls')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','work','evidence','public','english','chinese'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(**{k:v.resolve() for k,v in vars(a).items()})
