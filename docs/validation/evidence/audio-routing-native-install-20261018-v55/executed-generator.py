"""Install seven local wheels, then exercise routing through isolated CLI jobs."""
from __future__ import annotations
import argparse
import array
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]


def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def decode(path):
    return subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-f','f32le','-c:a','pcm_f32le','pipe:1'],
                          capture_output=True,check=True,timeout=120).stdout


def run(bundle, work, public, evidence):
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before=frozen();smoke=json.loads((public/'verification.json').read_bytes())
    assert smoke['status']=='passed_scoped_audio_routing' and smoke['frozen_after']==before
    target=work/'installed';start=time.monotonic();calls=[];outputs=[]
    env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1')
    install=subprocess.run([sys.executable,'-I','-B','-X','utf8',str(bundle/'install.py'),'--bundle',str(bundle),
        '--target',str(target),'--manifest-sha256',sha(bundle/'manifest.json')],env=env,capture_output=True,timeout=180)
    (evidence/'install.stdout.json').write_bytes(install.stdout);(evidence/'install.stderr.log').write_bytes(install.stderr)

    def cli(*args, expected=0):
        command=[sys.executable,'-I','-S','-B','-X','utf8',str(target/'run.py'),*map(str,args)]
        begin=time.monotonic();result=subprocess.run(command,cwd=work,env=env,capture_output=True,timeout=180)
        i=len(calls)+1
        out,err=evidence/f'{i:02}.stdout.json',evidence/f'{i:02}.stderr.log'
        out.write_bytes(result.stdout);err.write_bytes(result.stderr)
        calls.append({'index':i,'command':command,'exit_code':result.returncode,'expected_exit_code':expected,
                      'seconds':time.monotonic()-begin,'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        assert result.returncode==expected,(i,result.stdout,result.stderr)
        return json.loads(result.stdout)

    def compare(project, name, reference, *, gain=1):
        output=project/'renders'/name
        result=cli('render','--project',project,'--output',output,'--publish')
        actual,expected=decode(output),decode(public/reference)
        if gain==1:
            assert actual==expected
            error=0
        else:
            a,b=array.array('f'),array.array('f');a.frombytes(actual);b.frombytes(expected)
            assert len(a)==len(b)
            error=max(abs(x-y*gain) for x,y in zip(a,b))
            assert error<=2e-6
        shutil.copyfile(Path(result['data']['manifest']),evidence/(name+'.manifest.json'))
        probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(output)],capture_output=True,check=True).stdout)
        frames=int(next(s for s in probe['streams'] if s['codec_type']=='video')['nb_read_frames'])
        outputs.append({'name':name,'reference':reference,'gain':gain,'max_pcm_error':error,
                        'frames':frames,'stereo_sample_frames':len(actual)//8,'decoded_pcm_sha256':digest(actual),'output_sha256':sha(output)})

    try:
        assert install.returncode==0,(install.stdout,install.stderr)
        schema=cli('schema','show');capabilities=cli('capabilities')
        assert 'agent-audio-routing-v1' in json.dumps(capabilities)
        exported=work/'schema.json';cli('schema','export','--output',exported)
        assert exported.read_bytes()==(ROOT/'docs/specs/agent-project.schema.json').read_bytes()
        for row in smoke['cases']:
            project=work/row['id']
            cli('convert','import','--input',public/row['source_package'],'--output',project)
            cli('validate','--project',project,'--strict-rights')
            compare(project,row['id']+'.mkv',row['lossless_output'])
        project=work/'AR01';path=project/'project.json';original=path.read_bytes()
        request=work/'change.json';p=json.loads(original)
        routing=p['sequences'][0]['audio_routing'];routing['master']={'audio':{'volume':.5}}
        save(request,{'operations':[{'op':'update_sequence','patch':{'audio_routing':routing}}]})
        cli('timeline','compose','--project',project,'--input',request,'--dry-run')
        assert path.read_bytes()==original
        command=['timeline','compose','--project',project,'--input',request,'--idempotency-key','native-v55-routing-gain']
        first=cli(*command);after=path.read_bytes();replay=cli(*command)
        assert first['operation_id']==replay['operation_id'] and path.read_bytes()==after
        compare(project,'changed-master.mkv','AR01.mkv',gain=.5)
        save(request,{'operations':[{'op':'update_sequence','patch':{'audio_routing':{'version':1,'buses':[
            {'id':'a','output':'b'},{'id':'b','output':'a'}]}}}]})
        rejected=cli('timeline','compose','--project',project,'--input',request,expected=2)
        assert 'AUDIO_ROUTING_CYCLE' in json.dumps(rejected) and path.read_bytes()==after
        cli('policy','audit','--project',project)
        archive=work/'changed.zip'
        cli('convert','export','--project',project,'--target-format','package','--output',archive)
        restored=work/'restored';cli('convert','import','--input',archive,'--output',restored)
        compare(restored,'restored-master.mkv','AR01.mkv',gain=.5)
        files={};wheel=next((bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'):continue
                installed=list(target.rglob(name));assert len(installed)==1
                assert installed[0].read_bytes()==z.read(name)==(ROOT/'product/src'/name).read_bytes(),name
                files[name]=sha(installed[0])
        assert 'ai_ad_editor/audio_routing.py' in files and before==frozen()
        for name,source in [('agent-video-kit-cp313-win_amd64.zip',bundle.with_suffix('.zip')),
                            ('release-manifest.json',bundle/'manifest.json'),('install-receipt.json',target/'receipt.json')]:
            shutil.copyfile(source,public/name)
        record={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'native_windows':sys.platform=='win32',
            'virtualization':False,'virtual_environment':False,'installer_exit_code':install.returncode,'network_used':False,
            'isolated_cli_calls':len(calls),'calls':calls,'outputs':outputs,'installed_package_files':len(files),'installed_files':files,
            'package_bytes_equal_to_wheel_and_source':True,'frozen_before':before,'frozen_after':frozen(),
            'actual_new_frames':sum(o['frames'] for o in outputs),'actual_new_stereo_sample_frames':sum(o['stereo_sample_frames'] for o in outputs),
            'manifest_sha256':sha(public/'release-manifest.json'),'release_zip_sha256':sha(public/'agent-video-kit-cp313-win_amd64.zip'),
            'generator_sha256':sha(Path(__file__)),'seconds':time.monotonic()-start,
            'new_model_forwards':0,'browser_invocations':0,'continuous_playback':False,'listening_review':False,'other_machine_accepted':False}
        save(evidence/'verification.json',record)
        print(json.dumps({k:record[k] for k in ('status','isolated_cli_calls','installed_package_files','actual_new_frames','actual_new_stereo_sample_frames')}))
    except BaseException as exc:
        save(evidence/'failure.json',{'error':repr(exc),'calls':calls,'partials_preserved':True});raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','work','public','evidence'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();run(*(getattr(args,k).resolve() for k in ('bundle','work','public','evidence')))
