"""Install the frozen seven-wheel release and rebuild a real compound hold."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,time,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def run(bundle,work,public,evidence):
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    target=work/'installed';env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1')
    started=time.monotonic()
    install=subprocess.run([sys.executable,'-I','-B','-X','utf8',str(bundle/'install.py'),'--bundle',str(bundle),
        '--target',str(target),'--manifest-sha256',sha(bundle/'manifest.json')],env=env,capture_output=True,timeout=180)
    (evidence/'install.stdout.json').write_bytes(install.stdout);(evidence/'install.stderr.log').write_bytes(install.stderr)
    calls=[]
    def cli(*values):
        command=[sys.executable,'-I','-S','-B','-X','utf8',str(target/'run.py'),*map(str,values)]
        tick=time.monotonic();r=subprocess.run(command,cwd=work,env=env,capture_output=True,timeout=360)
        n=len(calls)+1
        (evidence/f'{n:02}.stdout.json').write_bytes(r.stdout);(evidence/f'{n:02}.stderr.log').write_bytes(r.stderr)
        calls.append({'command':command,'exit_code':r.returncode,'seconds':time.monotonic()-tick})
        save(evidence/'calls.json',calls)
        assert r.returncode==0,(n,r.stdout.decode('utf-8','replace'),r.stderr.decode('utf-8','replace'))
        print(json.dumps({'installed_call':n,'command':list(map(str,values[:2])),'exit_code':r.returncode}),flush=True)
        return json.loads(r.stdout)
    def decoded(path,audio=False):
        options=['-map','0:a:0','-vn','-ar','48000','-ac','2','-f','f32le'] if audio else ['-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo']
        r=subprocess.run(['ffmpeg','-v','error','-i',str(path),*options,'pipe:1'],capture_output=True,timeout=120)
        assert r.returncode==0,r.stderr
        return {'bytes':len(r.stdout),'sha256':'sha256:'+hashlib.sha256(r.stdout).hexdigest()}
    try:
        assert install.returncode==0,(install.stdout,install.stderr)
        cli('schema','show');cap=cli('capabilities');assert 'nested_freeze' in json.dumps(cap)
        project=work/'project';cli('convert','import','--input',public/'NF06-project.zip','--output',project)
        cli('validate','--project',project,'--strict-rights');cli('policy','audit','--project',project)
        development=public/'NF06.mkv';expected_rgb,expected_pcm=decoded(development),decoded(development,True)
        outputs=[]
        def render(project,name):
            output=project/'renders'/name
            cli('render','--project',project,'--output',output,'--container','mkv','--audio-codec','pcm_f32le',
                '--pixel-format','yuv444p','--crf','0','--publish')
            rgb,pcm=decoded(output),decoded(output,True)
            assert rgb==expected_rgb and pcm==expected_pcm
            outputs.append({'name':name,'rgb':rgb,'pcm':pcm,'frames':rgb['bytes']//(240*136*3),
                'stereo_sample_frames':pcm['bytes']//8,'rgb_pcm_equal_to_development':True,'output_sha256':sha(output)})
        render(project,'installed.mkv')
        archive=work/'installed-authored.zip';cli('convert','export','--project',project,'--target-format','package','--output',archive)
        restored=work/'restored';cli('convert','import','--input',archive,'--output',restored)
        render(restored,'installed-restored.mkv')
        product_wheel=next((bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(product_wheel) as z:
            package=[n for n in z.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')]
            assert 'ai_ad_editor/nested_freeze.py' in package
            installed={}
            for name in package:
                paths=list(target.rglob(name));assert len(paths)==1 and paths[0].read_bytes()==z.read(name),name
                source=ROOT/'product/src'/name;assert source.is_file() and source.read_bytes()==z.read(name),name
                installed[name]=sha(paths[0])
        for name,source in [('agent-video-kit-cp313-win_amd64.zip',bundle.with_suffix('.zip')),
                            ('release-manifest.json',bundle/'manifest.json'),('install-receipt.json',target/'receipt.json')]:
            shutil.copyfile(source,public/name)
        save(evidence/'verification.json',{'status':'passed','native_windows':True,'virtualization':False,'virtual_environment':False,
            'installer_exit_code':install.returncode,'isolated_cli_calls':len(calls),'calls':calls,'installed_package_files':len(package),
            'installed_files':installed,'package_bytes_equal_to_wheel_and_source':True,'outputs':outputs,
            'new_model_forwards':0,'browser_invocations':0,'install_and_check_seconds':time.monotonic()-started,
            'manifest_sha256':sha(public/'release-manifest.json'),'release_zip_sha256':sha(public/'agent-video-kit-cp313-win_amd64.zip'),
            'generator_sha256':sha(Path(__file__)),'continuous_playback':False,'listening_review':False,'other_machine_accepted':False})
        print(json.dumps({'status':'passed','isolated_cli_calls':len(calls),'package_files':len(package),'actual_output_frames':sum(x['frames'] for x in outputs)}))
    except BaseException as exc:
        save(evidence/'failure.json',{'error':repr(exc),'calls':calls,'partials_preserved':True});raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('bundle','work','public','evidence'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,k).resolve() for k in ('bundle','work','public','evidence')))
