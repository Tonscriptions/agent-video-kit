"""Install existing offline wheels and repeat actual CPU face CLI checks."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import zipfile
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('bundle','work','evidence','public','development-evidence','native-python','upstream','image'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    for key,value in vars(args).items():
        setattr(args,key,value.resolve())
    for path in (args.work,args.evidence,args.public):
        path.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(__file__,args.evidence/'executed-install-check.py')
    before=frozen();calls=[];files={}
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,
            'calls':calls,'installed_product_files':files,'quality_accepted':False,'full_capcut_parity':False,
            'different_machine_accepted':False,'model_weights_bundled':False,'network':'disabled','virtualization':False}
    save(args.evidence/'verification.json',record)
    env=dict(os.environ,TEMP=str(args.work),TMP=str(args.work),TMPDIR=str(args.work),PYTHONDONTWRITEBYTECODE='1')
    def command(values,name,timeout=240):
        values=list(map(str,values));result=subprocess.run(values,cwd=ROOT,env=env,capture_output=True,timeout=timeout)
        out=args.evidence/(name+'.stdout.log');err=args.evidence/(name+'.stderr.log')
        out.write_bytes(result.stdout);err.write_bytes(result.stderr)
        calls.append({'name':name,'command':values,'exit_code':result.returncode,'stdout':out.name,'stderr':err.name,
                      'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        save(args.evidence/'verification.json',record)
        if result.returncode:
            raise RuntimeError(name+' failed; see original logs')
        return result.stdout
    try:
        target=args.work/'installed'
        command([sys.executable,'-I','-B','-X','utf8',args.bundle/'install.py','--bundle',args.bundle,
                 '--target',target,'--manifest-sha256',sha(args.bundle/'manifest.json')],'install')
        wheel=next((args.bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'):
                    continue
                matches=list(target.rglob(name));payload=archive.read(name)
                if len(matches) != 1 or matches[0].read_bytes() != payload or payload != (ROOT/'product/src'/name).read_bytes():
                    raise ValueError('Installed/wheel/source bytes differ: '+name)
                files[name]=sha(matches[0])
        source_files={p.relative_to(ROOT/'product/src').as_posix() for p in (ROOT/'product/src/ai_ad_editor').rglob('*')
                      if p.is_file() and p.suffix not in ('.pyc','.pyo') and '__pycache__' not in p.parts}
        if set(files) != source_files:
            raise ValueError('Product resource set differs')
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',target/'run.py']
        caps=json.loads(command([*prefix,'capabilities'],'capabilities'))
        if caps['data']['capabilities']['face_retouch']['engine'] != 'openseeface-66-onnx-cpu-local-v1':
            raise ValueError('Missing face capability')
        command([*prefix,'schema','show'],'schema')
        help_text=command([*prefix,'face','retouch','--help'],'face-help').decode('utf8')
        if '--recipe-from-asset' not in help_text or '--all-detected' not in help_text:
            raise ValueError('Missing installed face arguments')
        site=next(target.rglob('ai_ad_editor/local_face.py')).parent.parent
        probe="""import json,sys
from pathlib import Path
site=Path(sys.argv[1]);sys.path.insert(0,str(site))
from ai_ad_editor import local_face,face_landmarks,face_geometry,face_worker,face_cli
modules=(local_face,face_landmarks,face_geometry,face_worker,face_cli)
assert all(Path(m.__file__).resolve().is_relative_to(site) for m in modules)
print(json.dumps({'status':'passed','module_files':[str(Path(m.__file__).relative_to(site)) for m in modules]}))
"""
        command([sys.executable,'-I','-S','-B','-X','utf8','-c',probe,site],'installed-module-origins')
        command([args.native_python,'-I','-B','-X','utf8',ROOT/'scripts/smoke_local_face.py',
                 '--work',args.work/'media','--evidence',args.evidence/'media','--public',args.public/'media',
                 '--upstream',args.upstream,'--image',args.image,'--controller-python',sys.executable,'--installed',target],
                'actual-installed-face',timeout=1800)
        actual=json.loads((args.evidence/'media/verification.json').read_bytes())
        expected=json.loads((args.development_evidence/'verification.json').read_bytes())
        if any(r['status'] != 'passed_native_cli_contract_quality_separate' or not r['frozen_equal'] or r['frozen_before'] != before for r in (actual,expected)):
            raise ValueError('Native checks failed or source closure changed')
        cli_calls=[c for c in actual['calls'] if str(target/'run.py') in c['command']]
        if any('-I' not in c['command'] or '-S' not in c['command'] for c in cli_calls):
            raise ValueError('Installed CLI isolation flags absent')
        for name in ('source-decode','neutral-decode','retouched-decode','recipe-replay-decode'):
            a=next(c for c in actual['calls'] if c['name']==name);b=next(c for c in expected['calls'] if c['name']==name)
            if (a['stdout_sha256'],a['stdout_bytes']) != (b['stdout_sha256'],b['stdout_bytes']):
                raise ValueError('Every decoded RGBA byte must equal development: '+name)
        for name in ('retouch-neutral','retouch-controls','retouch-saved-recipe'):
            proofs=[]
            for base,run in ((args.evidence/'media',actual),(args.development_evidence,expected)):
                call=next(c for c in run['calls'] if c['name']==name)
                output=json.loads((base/call['stdout_file']).read_bytes())
                report=json.loads(Path(output['data']['report']).read_bytes())
                proofs.append(report['response']['audio_pcm'])
            if proofs[0] != proofs[1]:
                raise ValueError('PCM proof differs: '+name)
        release=args.public/'release';release.mkdir()
        for name,path in (('agent-video-kit-cp313-win_amd64.zip',args.bundle.with_suffix('.zip')),
                          ('manifest.json',args.bundle/'manifest.json'),('install-receipt.json',target/'receipt.json')):
            shutil.copyfile(path,release/name)
        record.update(status='passed',packaged_files=len(files),isolated_cli_calls=len(cli_calls)+3,
                      isolated_module_calls=1,detector_forwards=actual['detector_forwards'],landmark_forwards=actual['landmark_forwards'],
                      all_rgba_and_pcm_equal_development=True,release={p.name:sha(p) for p in release.iterdir()},
                      media_receipt_sha256=sha(args.evidence/'media/verification.json'),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after']
        if not record['frozen_equal']:
            raise ValueError('Source changed during installed checks')
    except BaseException as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
        raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(args.evidence/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('status','packaged_files','isolated_cli_calls','frozen_equal')}))


if __name__=='__main__':
    main()
