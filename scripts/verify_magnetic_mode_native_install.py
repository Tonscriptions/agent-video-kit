"""Install fixed wheels and run actual magnet/package/fragment operations in isolated native processes."""
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
import zipfile
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path):return digest(path.read_bytes())
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(bundle,work,public,evidence):
    import numpy as np
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before=frozen();smoke=json.loads((public/'verification.json').read_bytes())
    assert before==smoke['frozen_after'];calls=[];outputs=[]
    env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1')
    target=work/'installed'
    done=subprocess.run([sys.executable,'-I','-B','-X','utf8',str(bundle/'install.py'),'--bundle',str(bundle),
        '--target',str(target),'--manifest-sha256',sha(bundle/'manifest.json')],env=env,capture_output=True,timeout=180)
    (evidence/'install.stdout.json').write_bytes(done.stdout);(evidence/'install.stderr.log').write_bytes(done.stderr)

    def cli(*args,expected=0):
        cmd=[sys.executable,'-I','-S','-B','-X','utf8',str(target/'run.py'),*map(str,args)]
        r=subprocess.run(cmd,cwd=work,env=env,capture_output=True,timeout=180);i=len(calls)+1
        out,err=evidence/f'{i:02}.stdout.json',evidence/f'{i:02}.stderr.log';out.write_bytes(r.stdout);err.write_bytes(r.stderr)
        calls.append({'index':i,'command':cmd,'exit_code':r.returncode,'expected_exit_code':expected,'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        save(evidence/'calls.json',calls);assert r.returncode==expected,(i,r.stdout,r.stderr)
        return json.loads(r.stdout)

    def decode(path,kind):
        args=['ffmpeg','-v','error','-i',str(path),'-map','0:'+kind+':0']
        args+=['-an','-pix_fmt','rgb24','-f','rawvideo'] if kind=='v' else ['-vn','-ar','48000','-ac','2','-f','f32le']
        return subprocess.run([*args,'pipe:1'],capture_output=True,check=True,timeout=120).stdout

    def compare(project,name,reference,sequence=None,exact=True):
        output=project/'renders'/(name+'.mkv');args=['render','--project',project,'--output',output,'--container','mkv',
            '--audio-codec','pcm_f32le','--pixel-format','yuv444p','--crf','0','--publish']
        if sequence:args+=['--sequence-id',sequence]
        result=cli(*args);shutil.copyfile(result['data']['manifest'],evidence/(name+'.manifest.json'))
        video,audio=decode(output,'v'),decode(output,'a');rv,ra=decode(public/reference,'v'),decode(public/reference,'a')
        assert len(video)==len(rv) and len(audio)==len(ra)
        pixel=int(np.max(np.abs(np.frombuffer(video,dtype='u1').astype(np.int16)-np.frombuffer(rv,dtype='u1').astype(np.int16))))
        error=float(np.max(np.abs(np.frombuffer(audio,dtype='<f4')-np.frombuffer(ra,dtype='<f4'))))
        if exact:assert video==rv and audio==ra
        else:assert pixel<=2 and error<=2e-6
        outputs.append({'name':name,'reference':reference,'frames':len(video)//(160*64*3),'stereo_sample_frames':len(audio)//8,
            'max_rgb_error':pixel,'max_pcm_error':error,'exact':exact,'output_sha256':sha(output),
            'decoded_rgb_sha256':digest(video),'decoded_pcm_sha256':digest(audio)})

    try:
        assert done.returncode==0,(done.stdout,done.stderr)
        cli('schema','show');caps=cli('capabilities');assert 'agent-magnetic-mode-v1' in json.dumps(caps)
        for row in smoke['cases']:
            name=row['name'];project=work/name
            cli('convert','import','--input',public/(name+'.aevpkg.zip'),'--output',project)
            cli('validate','--project',project,'--strict-rights');compare(project,name,name+'.mkv')
            cli('policy','audit','--project',project)
        project=work/'MM01';q=work/'edit.json';original=(project/'project.json').read_bytes()
        save(q,{'action':'magnet','enabled':False})
        cli('timeline','edit','--project',project,'--input',q,'--dry-run');assert (project/'project.json').read_bytes()==original
        args=['timeline','edit','--project',project,'--input',q,'--idempotency-key','native-v56-off']
        one=cli(*args);changed=(project/'project.json').read_bytes();two=cli(*args)
        assert one['operation_id']==two['operation_id'] and (project/'project.json').read_bytes()==changed
        save(q,{'action':'magnet','enabled':True});cli('timeline','edit','--project',project,'--input',q)
        previous=(project/'project.json').read_bytes()
        save(q,{'operations':[{'op':'update_clip','clip_id':'c','patch':{'duration_tick':45000}}]})
        invalid=cli('timeline','compose','--project',project,'--input',q,expected=2)
        assert 'EDIT_MAGNETIC_MAIN_GAP_OR_OVERLAP' in json.dumps(invalid) and (project/'project.json').read_bytes()==previous
        source=work/'MM06';p=json.loads((source/'project.json').read_bytes());sid=p['sequences'][0]['id'];library=work/'library'
        save(q,{'id':'magnet','version':1,'name':'complete magnet closure','sequence_id':sid,'clip_ids':['a']})
        fragment=cli('fragment','save','--project',source,'--library',library,'--input',q)
        assert len(fragment['data']['fragment']['selection']['included'])==12
        destination=work/'fragment-target'
        cli('convert','import','--input',public/'MM01.aevpkg.zip','--output',destination)
        save(q,{'action':'remove','clip_ids':['a','b','c','d']});cli('timeline','edit','--project',destination,'--input',q)
        save(q,{'id':'magnet','version':1,'sequence_id':sid,'track_id':'shots','at_tick':0,'instance_id':'native_magnet'})
        cli('fragment','apply','--project',destination,'--library',library,'--input',q)
        cli('validate','--project',destination,'--strict-rights')
        after=json.loads((destination/'project.json').read_bytes())
        child=next(s for s in after['sequences'] if s['id']!=sid and s.get('editing',{}).get('magnetic'))
        compare(destination,'fragment-child','MM06.mkv',sequence=child['id'])
        compare(destination,'fragment-root','MM06.mkv',exact=False)
        cli('policy','audit','--project',destination)
        installed={};wheel=next((bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'):continue
                files=list(target.rglob(name));assert len(files)==1
                assert files[0].read_bytes()==z.read(name)==(ROOT/'product/src'/name).read_bytes()
                installed[name]=sha(files[0])
        assert len(installed)==121 and frozen()==before
        for name,source in [('agent-video-kit-cp313-win_amd64.zip',bundle.with_suffix('.zip')),('release-manifest.json',bundle/'manifest.json'),('install-receipt.json',target/'receipt.json')]:
            shutil.copyfile(source,public/name)
        record={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'installer_exit_code':done.returncode,
            'isolated_cli_calls':len(calls),'calls':calls,'outputs':outputs,'installed_package_files':len(installed),'installed_files':installed,
            'frozen_before':before,'frozen_after':frozen(),'package_bytes_equal_to_wheel_and_source':True,
            'actual_new_frames':sum(o['frames'] for o in outputs),'actual_new_stereo_sample_frames':sum(o['stereo_sample_frames'] for o in outputs),
            'release_zip_sha256':sha(public/'agent-video-kit-cp313-win_amd64.zip'),'manifest_sha256':sha(public/'release-manifest.json'),
            'generator_sha256':sha(Path(__file__)),'virtual_environment':False,'network_used':False,'other_machine_accepted':False,
            'continuous_playback':False,'human_listening':False,'full_capcut_parity':False}
        save(evidence/'verification.json',record)
        print(json.dumps({k:record[k] for k in ('status','isolated_cli_calls','installed_package_files','actual_new_frames','actual_new_stereo_sample_frames')}))
    except BaseException as exc:
        save(evidence/'failure.json',{'error':repr(exc),'calls':calls,'outputs':outputs,'source_freeze':before});raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('bundle','work','public','evidence'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(a.bundle.resolve(),a.work.resolve(),a.public.resolve(),a.evidence.resolve())
