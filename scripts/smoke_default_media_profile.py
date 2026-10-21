"""Actually build/install using the default tracked wheelhouse; no explicit wheelhouse option."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from run_frozen_regression import frozen
from run_offline_media_after_parent import dependency_inputs

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/offline-media-profile-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    work=ROOT/'product/.runtime/offline-media-profile-20261021/default-profile-r1'
    evidence=REL/'default-profile-r1';assert not work.exists() and not evidence.exists()
    work.mkdir(parents=True);evidence.mkdir()
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_before':frozen(),'dependency_inputs_before':dependency_inputs(),'calls':[],'checks':[],
        'native_windows':sys.platform=='win32','virtualization':False,'network':False,'host_numpy_copied':False}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok,**details):record['checks'].append({'name':name,'ok':bool(ok),**details});save();assert ok,name
    def run(label,command):
        command=list(map(str,command));temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
        env=dict(os.environ,TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=600)
        for stream in ('stdout','stderr'):(evidence/(label+'.'+stream+'.log')).write_bytes(getattr(result,stream))
        record['calls'].append({'label':label,'command':command,'exit_code':result.returncode,
            'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
            'stderr_sha256':'sha256:'+hashlib.sha256(result.stderr).hexdigest()});save()
        assert result.returncode==0,result.stderr[-3000:].decode('utf8','replace')+result.stdout[-3000:].decode('utf8','replace')
        return json.loads(result.stdout)
    try:
        assert len(record['frozen_before'])==260
        bundle=work/'bundle'
        built=run('default-build',[sys.executable,'-I','-B','-X','utf8',ROOT/'product/offline/build.py','--output',bundle])
        manifest=json.loads((bundle/'manifest.json').read_bytes());record['bundle']=built
        check('default-uses-complete-eight-wheel-media-profile',manifest['runtime_profile']=='media-analysis-v1'
            and built['wheels']==8 and len(manifest['wheels'])==8)
        check('build-did-not-pass-wheelhouse-option','--wheelhouse' not in record['calls'][0]['command'])
        numpy=next(row for row in manifest['wheels'] if row['name']=='numpy')
        check('default-numpy-is-exact-pinned-official-wheel',numpy['version']=='2.4.2'
            and sha(bundle/numpy['path'])=='sha256:7df2de1e4fba69a51c06c28f5a3de36731eb9639feb8e1cf7e4a7b0daf4cf622')
        installed=work/'installed'
        result=run('default-install',[sys.executable,'-I','-B','-X','utf8',bundle/'install.py',
            '--target',installed,'--manifest-sha256',built['manifest_sha256']]);record['installation']=result
        check('default-install-really-completed',result['status']=='installed' and result['wheels']==8)
        audit=result['audit'];check('eight-dependencies-audited-in-fresh-native-process',len(audit['modules'])==8 and audit['modules']['numpy']['version']=='2.4.2')
        check('native-numpy-dot-solve-and-FFT-ran',audit['numpy_native']['dot']==285.0
            and max(abs(a-b) for a,b in zip(audit['numpy_native']['solve'],[2.,3.]))<=1e-12
            and audit['numpy_native']['fft_impulse_real']==[1.,1.,1.] and audit['numpy_native']['fft_impulse_imag']==[0.,0.,0.])
        check('both-native-extensions-shipped-locally',len(audit['numpy_native']['extensions'])==2
            and all((installed/'site'/p).is_file() for p in audit['numpy_native']['extensions'].values()))
        capabilities=run('default-installed-capabilities',[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py','capabilities'])
        check('default-installed-CLI-runs-without-host-site',capabilities['ok']
            and capabilities['data']['capabilities']['media']['multicam_source_coverage']['version']=='0.4.0')
        record.update(status='passed-default-wheelhouse-offline-bootstrap',native_build_install_calls=2,isolated_cli_calls=1,
            generator_sha256=sha(__file__))
    except BaseException as error:record.update(status='failed',error={'type':type(error).__name__,'message':str(error)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen(),dependency_inputs_after=dependency_inputs())
        record['frozen_equal']=record['frozen_before']==record['frozen_after']
        record['dependency_inputs_equal']=record['dependency_inputs_before']==record['dependency_inputs_after'];save()
        (evidence/'executed-default-smoke.py.txt').write_bytes(Path(__file__).read_bytes())
    assert record['frozen_equal'] and record['dependency_inputs_equal']
    print(json.dumps({'status':record['status'],'wheels':8,'checks':len(record['checks']),
        'native_build_install_calls':2,'isolated_cli_calls':1,'frozen_equal':record['frozen_equal']}))


if __name__=='__main__':main()
