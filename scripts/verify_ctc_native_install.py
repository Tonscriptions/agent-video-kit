"""Install a new offline wheel bundle; run actual CTC and compare encoded output."""
import argparse,hashlib,json,os,shutil,subprocess,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(4*1024*1024):h.update(data)
    return 'sha256:'+h.hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main(args):
    bundle,work,public,evidence=(getattr(args,k).resolve() for k in ('bundle','work','public','evidence'))
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    target=work/'installed';env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1')
    install=subprocess.run([sys.executable,'-I','-B','-X','utf8',str(bundle/'install.py'),'--bundle',str(bundle),
        '--target',str(target),'--manifest-sha256',sha(bundle/'manifest.json')],env=env,capture_output=True,timeout=180)
    (evidence/'install.stdout.json').write_bytes(install.stdout);(evidence/'install.stderr.log').write_bytes(install.stderr)
    assert install.returncode==0,(install.stdout,install.stderr)
    calls=[]
    def cli(*values):
        started=time.monotonic()
        command=[sys.executable,'-I','-S','-B','-X','utf8',str(target/'run.py'),*map(str,values)]
        r=subprocess.run(command,cwd=work,env=env,capture_output=True,timeout=420)
        number=len(calls)+1
        (evidence/f'{number:02}.stdout.json').write_bytes(r.stdout);(evidence/f'{number:02}.stderr.log').write_bytes(r.stderr)
        row={'command':command,'exit_code':r.returncode,'seconds':round(time.monotonic()-started,3)}
        calls.append(row);assert r.returncode==0,(number,r.stdout,r.stderr)
        print(json.dumps({'call':number,'exit_code':r.returncode,'seconds':row['seconds']}),flush=True)
        return json.loads(r.stdout)
    try:
        cli('schema','show');cap=cli('capabilities')
        assert 'transformers-wav2vec2-ctc-local-v1' in json.dumps(cap)
        project=work/'project';cli('project','init',project)
        registered=cli('asr','adapter','register','--project',project,'--adapter-id','ctc','--engine','transformers-wav2vec2-ctc-local-v1',
            '--python-executable',NATIVE,'--model-path',ROOT/'product/.runtime/models/ctc-en-runtime','--device','cuda','--threads','4',
            '--evidence',ROOT/'docs/validation/evidence/ctc-model-conversion-20261018/en-runtime.json','--license-spdx','Apache-2.0')
        implementation=[Path(r['path']) for r in registered['data']['adapter']['artifacts'] if r['role']=='implementation']
        assert implementation and all(p.is_relative_to(target) for p in implementation)
        for name,path in [('speech','input.wav'),('background','input.mp4'),('font','font.ttf')]:
            cli('media','ingest','--project',project,'--input',public/path,'--asset-id',name)
        original=json.loads((ROOT/'workspace/ctc-en-smoke-20261018-b/project.json').read_text(encoding='utf-8'))
        current=json.loads((project/'project.json').read_text(encoding='utf-8'))
        current['settings']=original['settings']
        current['sequences'][0]['duration_tick']=original['sequences'][0]['duration_tick']
        current['sequences'][0]['tracks']=original['sequences'][0]['tracks']
        current['sequences'][0]['tracks'][-1]['clips']=[]
        save(project/'project.json',current)
        result=cli('subtitle','align','--project',project,'--asset-id','speech','--adapter-id','ctc',
            '--transcript',public/'transcript.txt','--output','assets/aligned/new.json','--granularity','whitespace',
            '--apply','--track-id','captions','--font-asset-id','font')
        actual=result['data']['result']
        expected=json.loads((public/'short-alignment.json').read_text(encoding='utf-8'))
        units_equal=all([{k:u[k] for k in ('text','start_char','end_char','start_sample','end_sample')} for u in a['units']]==
            [{k:u[k] for k in ('text','start_char','end_char','start_sample','end_sample')} for u in b['units']]
            for a,b in zip(actual['segments'],expected['segments']))
        assert units_equal
        output=project/'renders/installed.mkv'
        cli('render','--project',project,'--output',output,'--profile','custom','--width','1280','--height','720',
            '--container','mkv','--audio-codec','pcm_f32le','--pixel-format','yuv444p','--crf','0')
        cli('validate','--project',project);cli('policy','audit','--project',project)
        def decoded(path,args):
            p=subprocess.Popen(['ffmpeg','-v','error','-nostdin','-i',str(path),*args,'-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            h=hashlib.sha256();size=0
            while data:=p.stdout.read(4*1024*1024):h.update(data);size+=len(data)
            error=p.stderr.read();assert p.wait(timeout=30)==0,error
            p.stdout.close();p.stderr.close();return {'bytes':size,'sha256':'sha256:'+h.hexdigest()}
        rgb_args=['-f','rawvideo','-pix_fmt','rgb24']
        audio_args=['-map','0:a:0','-f','f32le','-acodec','pcm_f32le']
        rgb=decoded(output,rgb_args);pcm=decoded(output,audio_args)
        assert rgb==decoded(public/'aligned-verified.mkv',rgb_args)
        assert pcm==decoded(public/'aligned-verified.mkv',audio_args)
        product_wheel=next((bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(product_wheel) as z:
            package=[n for n in z.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')]
            for name in package:
                candidates=list(target.rglob(name))
                assert len(candidates)==1 and candidates[0].read_bytes()==z.read(name),name
        shutil.copyfile(bundle.with_suffix('.zip'),public/'agent-video-kit-cp313-win_amd64.zip')
        shutil.copyfile(bundle/'manifest.json',public/'release-manifest.json')
        shutil.copyfile(target/'receipt.json',public/'install-receipt.json')
        save(evidence/'verification.json',{'status':'passed','native_windows':True,'virtualization':False,'virtual_environment':False,
            'installer_exit_code':install.returncode,'isolated_cli_calls':len(calls),'calls':calls,'installed_package_files':len(package),
            'package_bytes_equal_to_wheel':True,'registered_implementation_paths_inside_install':True,
            'actual_worker_processes':1,'actual_model_forward_calls':actual['worker']['model_forward_calls'],
            'word_times_equal_to_development':units_equal,'rgb_equal_to_development':True,'pcm_equal_to_development':True,
            'rgb':rgb,'pcm':pcm,'encoded_frames':rgb['bytes']//(1280*720*3),
            'release_zip_sha256':sha(public/'agent-video-kit-cp313-win_amd64.zip'),'generator_sha256':sha(Path(__file__)),
            'other_machine_accepted':False,'natural_alignment_quality_accepted':False})
        print(json.dumps({'status':'passed','isolated_cli_calls':len(calls),'package_files':len(package)}))
    except BaseException as exc:
        save(evidence/'failure.json',{'error':repr(exc),'calls':calls,'partials_preserved':True});raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('bundle','work','public','evidence'):p.add_argument('--'+key,type=Path,required=True)
    main(p.parse_args())
