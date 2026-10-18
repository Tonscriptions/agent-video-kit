"""Real native offline install and detached CLI editing/render/package evidence."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,time,wave,zipfile
from pathlib import Path
from smoke_fragments import frozen,save,sha
ROOT=Path(__file__).resolve().parents[1]
W,H,FPS,SR,TPS=240,136,10,48000,90000


def run(work,public,evidence):
    import numpy as np
    from PIL import Image,ImageDraw
    for folder in (work,public,evidence):folder.mkdir(parents=True,exist_ok=False)
    before=frozen();calls=[];env=dict(os.environ);env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1')
    save(evidence/'state.json',{'status':'started','frozen_before':before})
    def process(label,command,*,cwd=None,expected=0):
        started=time.monotonic();result=subprocess.run(list(map(str,command)),cwd=cwd or work,env=env,capture_output=True,timeout=240)
        row={'label':label,'command':list(map(str,command)),'cwd':str(cwd or work),'exit_code':result.returncode,'expected_exit_code':expected,'seconds':time.monotonic()-started,'stdout':result.stdout.decode('utf-8','replace'),'stderr':result.stderr.decode('utf-8','replace')}
        calls.append(row);save(evidence/'calls'/f'{len(calls):03}-{label}.json',row)
        assert result.returncode==expected,(label,row)
        return json.loads(result.stdout) if result.stdout.strip() else None
    build=process('build',[sys.executable,'-I','-B','-X','utf8',ROOT/'product/offline/build.py','--output',work/'bundle'],cwd=ROOT)
    bundle=work/'bundle';install=work/'independent-install';digest=build['manifest_sha256']
    base=[sys.executable,'-I','-B','-X','utf8',bundle/'install.py','--target',install,'--manifest-sha256',digest]
    preview=process('install-preview',base+['--dry-run']);assert not install.exists()
    installation=process('install',base);assert installation['ok']
    # All required modules originate here. Each invocation is a fresh isolated
    # process and blocks optional analysis/model libraries and Python networking.
    boot="""import sys,os,pathlib,importlib.abc,importlib,runpy
root=pathlib.Path(sys.argv[1]).resolve();site=root/'site'
sys.path[:]=[str(site),*[p for p in sys.path if not {'site-packages','dist-packages'} & set(pathlib.Path(p).parts)]]
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'numpy','PIL','torch','requests','httpx'}:raise ModuleNotFoundError('offline optional-library guard: '+fullname)
sys.meta_path.insert(0,Block())
def guard(event,args):
 if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'}:raise RuntimeError('offline network guard: '+event)
sys.addaudithook(guard)
for module in ('ai_ad_editor','jsonschema','attrs','jsonschema_specifications','referencing','rpds'):
 m=importlib.import_module(module);assert pathlib.Path(m.__file__).resolve().is_relative_to(site),module
os.environ['AI_AD_EDITOR_RUNTIME_DIR']=str(root/'runtime')
from ai_ad_editor.cli import main
raise SystemExit(main(sys.argv[2:]))
"""
    def cli(label,*args,expected=0,root=None,check_origins=True):
        selected=root or install
        # Missing dependency negative intentionally cannot import all modules.
        code=boot if check_origins else boot[:boot.index('for module in (')]+"os.environ['AI_AD_EDITOR_RUNTIME_DIR']=str(root/'runtime')\nfrom ai_ad_editor.cli import main\nraise SystemExit(main(sys.argv[2:]))\n"
        return process(label,[sys.executable,'-I','-S','-B','-X','utf8','-c',code,selected,*args],expected=expected)
    version=cli('version','version');assert version['data']['schema_validation']['ok']
    doctor=cli('doctor','doctor');assert doctor['data']['checks']['schema_validation']['source']=='bundled'
    schema=cli('schema-show','schema','show');assert schema['data']['contract']['sha256']==installation['audit']['schema']['sha256']
    exported=work/'exported-contract.json';cli('schema-export','schema','export','--output',exported)
    assert exported.read_bytes()==(ROOT/'docs/specs/agent-project.schema.json').read_bytes()
    cli('schema-export-existing','schema','export','--output',exported,expected=2)
    # Exercise the generated user launcher, beyond the guarded test bootstrap.
    launched=process('generated-launcher',[sys.executable,'-I','-S','-B','-X','utf8',install/'run.py','version'])
    assert launched['data']['schema_validation']['ok']
    original=ROOT/'docs/assets/source-transitions-20261017'
    provenance={'license_spdx':'CC0-1.0','source':'Original V35 procedural video counter/moving blocks plus new original nonperiodic stereo chirp/amplitude probe','original_provenance':'docs/assets/source-transitions-20261017/fixture-provenance.json','original_provenance_sha256':sha(original/'fixture-provenance.json'),'new_model_inference':0,'virtualization':False,'browser_invocations':0,'generator':'scripts/smoke_offline_release.py','generator_sha256':sha(Path(__file__)),'inputs':{}}
    shutil.copyfile(original/'source-a.mp4',public/'source-a.mp4')
    provenance['inputs']['source-a.mp4']={'sha256':sha(public/'source-a.mp4'),'original':(original/'source-a.mp4').relative_to(ROOT).as_posix()}
    t=np.arange(8*SR,dtype=np.float64)/SR
    left=.2*(.6+.3*np.cos(.7*t))*np.sin(2*np.pi*(223*t+17*t*t+.07*np.sin(.7*t)))
    right=.17*(.6+.25*np.sin(.9*t))*np.sin(2*np.pi*(337*t+11*t*t))
    samples=np.round(np.stack([left,right],axis=1)*32760).astype('<i2')
    with wave.open(str(public/'sound-a.wav'),'wb') as output:
        output.setparams((2,2,SR,0,'NONE','not compressed'));output.writeframes(samples.tobytes())
    provenance['inputs']['sound-a.wav']={'sha256':sha(public/'sound-a.wav'),'original':'new original deterministic stereo chirp/amplitude probe','sample_rate':SR,'channels':2,'sample_frames':8*SR,'format':'PCM s16le'}
    save(public/'fixture-provenance.json',provenance)
    project=work/'edited-project';cli('project-init','project','init',project)
    for aid,name in [('video','source-a.mp4'),('audio','sound-a.wav')]:
        cli('media-'+aid,'media','ingest','--project',project,'--input',public/name,'--asset-id',aid,'--verification-status','verified','--license-spdx','CC0-1.0','--permitted-use','commercial_ad','--evidence',public/'fixture-provenance.json')
    payload=json.loads((project/'project.json').read_bytes());payload['settings']['canvas'].update(width=W,height=H)
    payload['settings']['timebase']['display_fps']={'num':FPS,'den':1};sequence=payload['sequences'][0];sequence['duration_tick']=3*TPS
    for track,aid,cid in zip(sequence['tracks'],('video','audio'),('v','a')):
        track['clips']=[{'id':cid,'asset_id':aid,'link_id':'av','timeline_start_tick':0,'duration_tick':3*TPS,'source_in_tick':TPS,'source_out_tick':4*TPS}]
    # Explicit original author fixture; subsequent edits use the real installed CLI.
    save(project/'project.json',payload);save(public/'before-project.json',payload)
    def ff(args):
        result=subprocess.run(['ffmpeg','-v','error','-nostdin','-y',*map(str,args)],capture_output=True,timeout=180)
        assert result.returncode==0,result.stderr.decode('utf-8','replace');return result.stdout
    def decode(path):
        rgb=np.frombuffer(ff(['-i',path,'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
        audio=np.frombuffer(ff(['-i',path,'-map','0:a:0','-vn','-ac','2','-ar',str(SR),'-f','f32le','pipe:1']),'<f4').reshape(-1,2)
        return rgb,audio
    def render(root,name):
        output=root/'renders'/(name+'.mkv')
        cli('render-'+name,'render','--project',root,'--output',output,'--container','mkv','--crf','0','--pixel-format','yuv444p','--audio-codec','pcm_f32le','--publish')
        shutil.copyfile(output,public/(name+'.mkv'));ff(['-i',output,'-c:v','copy','-c:a','aac','-b:a','128k',public/(name+'.mp4')])
        return decode(output)
    cli('validate-before','validate','--project',project);prior=render(project,'before')
    request=work/'slip.json';save(request,{'action':'slip','clip_id':'v','delta_source_tick':TPS});state=(project/'project.json').read_bytes()
    plan=cli('slip-preview','timeline','edit','--project',project,'--input',request,'--dry-run');assert state==(project/'project.json').read_bytes()
    cli('slip-apply','timeline','edit','--project',project,'--input',request,'--expected-project-sha256',plan['data']['plan']['base_project_sha256'])
    after=json.loads((project/'project.json').read_bytes());save(public/'after-project.json',after)
    for track in after['sequences'][0]['tracks']:
        assert track['clips'][0]['source_in_tick']==2*TPS and track['clips'][0]['source_out_tick']==5*TPS
    cli('validate-after','validate','--project',project);edited=render(project,'after')
    package=work/'edited-project.zip';cli('package-export','convert','export','--project',project,'--target-format','package','--output',package)
    restored=work/'restored-project';cli('package-import','convert','import','--input',package,'--output',restored)
    cli('validate-restored','validate','--project',restored);roundtrip=render(restored,'restored')
    assert np.array_equal(edited[0],roundtrip[0]) and np.array_equal(edited[1],roundtrip[1])
    source_rgb=np.frombuffer(ff(['-i',public/'source-a.mp4','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
    source_pcm=np.frombuffer(ff(['-i',public/'sound-a.wav','-ac','2','-ar',str(SR),'-f','f32le','pipe:1']),'<f4').reshape(-1,2)
    comparisons=[]
    for label,actual,offset in [('before',prior,1),('after',edited,2)]:
        frames,samples=actual;assert frames.shape[0]==30 and samples.shape==(3*SR,2)
        identities=[]
        for frame in frames:
            errors=np.mean(np.abs(source_rgb.astype(np.int16)-frame.astype(np.int16)),axis=(1,2,3));identities.append(int(np.argmin(errors)))
        assert identities==list(range(offset*FPS,(offset+3)*FPS)),identities
        difference=np.abs(frames.astype(np.int16)-source_rgb[offset*FPS:(offset+3)*FPS].astype(np.int16))
        pcm=np.max(np.abs(samples-source_pcm[offset*SR:(offset+3)*SR]));assert pcm<=1e-7,pcm
        assert np.max(difference)<=4 and np.mean(difference)<=0.8,(np.max(difference),np.mean(difference))
        comparisons.append({'label':label,'frames':len(frames),'expected_source_frame_ids':identities,'rgb_max_difference':int(difference.max()),'rgb_mean_difference':float(difference.mean()),'stereo_sample_frames':len(samples),'independent_pcm_max_difference':float(pcm),'pcm_sha256':'sha256:'+hashlib.sha256(samples.tobytes()).hexdigest()})
    assert comparisons[0]['pcm_sha256']!=comparisons[1]['pcm_sha256'],'Audio fixture must distinguish the one-second source slip'
    # Actual declared field and state preservation on the standalone installation.
    saved=(project/'project.json').read_bytes();invalid=json.loads(saved);invalid['project']['created_at']='this-is-not-a-date';save(project/'project.json',invalid)
    rejected=cli('invalid-date','validate','--project',project,expected=2)
    assert any(x['path']=='project.created_at' and x['code']=='SCHEMA_VALIDATION_FAILED' for x in rejected['errors'])
    assert json.loads((project/'project.json').read_bytes())==invalid;(project/'project.json').write_bytes(saved)
    # Real installation trees exercise missing resource, changed bytes and absent
    # executor, with host/user site removed so absence cannot be masked.
    for label,mode,expected_code in [('missing-schema','missing','SCHEMA_RESOURCE_MISSING'),('changed-schema','changed','SCHEMA_RESOURCE_CHANGED'),('missing-executor','executor','SCHEMA_EXECUTOR_UNAVAILABLE')]:
        variant=work/label;(variant/'site').mkdir(parents=True)
        if mode=='executor':shutil.copytree(install/'site/ai_ad_editor',variant/'site/ai_ad_editor')
        else:
            for file in (install/'site').iterdir():
                if file.is_dir():shutil.copytree(file,variant/'site'/file.name)
                else:shutil.copyfile(file,variant/'site'/file.name)
            resource=variant/'site/ai_ad_editor/agent-project.schema.json'
            if mode=='missing':resource.unlink()
            else:resource.write_bytes(resource.read_bytes()+b' ')
        result=cli(label,'validate','--project',project,expected=2,root=variant,check_origins=mode!='executor')
        assert any(x['code']==expected_code for x in result['errors']),result
    process('existing-install',base,expected=2);assert (install/'receipt.json').is_file()
    cancelled=work/'cancelled-install';flag=work/'cancel';flag.touch()
    process('pre-cancel',[*base[:base.index('--target')+1],cancelled,'--manifest-sha256',digest,'--cancel-file',flag],expected=8);assert not cancelled.exists()
    tampered=work/'tampered-bundle';shutil.copytree(bundle,tampered);wheel=next((tampered/'wheels').glob('*.whl'));wheel.write_bytes(wheel.read_bytes()+b'x');bad_target=work/'bad-install'
    process('tampered-bundle',[sys.executable,'-I','-B','-X','utf8',tampered/'install.py','--target',bad_target,'--manifest-sha256',digest],expected=2);assert not bad_target.exists()
    assert not list(work.glob('.agent-video-kit-install-*'))
    # Package inventory includes original MIT notices and exact canonical Schema.
    manifest=json.loads((bundle/'manifest.json').read_bytes());own=next(x for x in manifest['wheels'] if x['name']=='ai-ad-editor')
    with zipfile.ZipFile(bundle/own['path']) as archive:
        names=[n for n in archive.namelist() if n.startswith('ai_ad_editor/')]
        for name in names:assert archive.read(name)==(ROOT/'product/src'/name).read_bytes(),name
        assert len(names)==108,len(names)
    # Public archive is the exact tested installer/wheels, not a separately built copy.
    public_archive=public/'agent-video-kit-cp313-win_amd64.zip';shutil.copyfile(work/'bundle.zip',public_archive)
    shutil.copyfile(bundle/'manifest.json',public/'release-manifest.json')
    shutil.copyfile(install/'receipt.json',public/'install-receipt.json')
    image=Image.new('RGB',(2*W,3*H+24),'#101829');draw=ImageDraw.Draw(image);draw.text((8,5),'BEFORE: source +1s       AFTER: source +2s',fill='white')
    for row,index in enumerate((0,15,29)):
        image.paste(Image.fromarray(prior[0][index]),(0,24+row*H));image.paste(Image.fromarray(edited[0][index]),(W,24+row*H))
    image.save(public/'contact.png')
    ff(['-i',public/'before.mp4','-i',public/'after.mp4','-filter_complex','[0:v][1:v]hstack=inputs=2,fps=10,scale=480:136:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer','-an','-loop','0',public/'comparison.gif'])
    probes={}
    for file in sorted(public.iterdir()):
        if file.suffix not in {'.mkv','.mp4','.wav','.gif'}:continue
        result=subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(file)],capture_output=True,check=True,timeout=90)
        probes[file.name]=json.loads(result.stdout)
    save(evidence/'media-probes.json',probes)
    after_frozen=frozen();assert before==after_frozen,'Product source changed during real release check'
    record={'status':'passed','frozen_before':before,'frozen_after':after_frozen,'frozen_equal':True,'bundle':build,'installation':installation,'packaged_source_files':len(names),'guarded_native_cli_calls':len([x for x in calls if '-c' in x['command']]),'process_calls':len(calls),'calls':calls,'comparisons':comparisons,'nonperiodic_audio_distinguishes_slip':True,'package_roundtrip_rgb_exact':True,'package_roundtrip_pcm_exact':True,'encoded_primary_frames':90,'new_stereo_sample_frames':3*3*SR,'models_executed':0,'browser_tabs_opened':0,'continuous_playback_review':False,'listening_review':False,'static_review':'pending separate contact inspection','same_machine_detached_install':True,'other_clean_machine_accepted':False,'python_network_guard':True,'blocked_optional_modules':['numpy','PIL','torch','requests','httpx'],'all_core_modules_from_installed_site':True,'pip_wheel_only_no_index_no_deps_require_hashes':True,'no_unowned_install_target_touched':True,'public_files':{file.relative_to(public).as_posix():{'sha256':sha(file),'bytes':file.stat().st_size} for file in sorted(public.rglob('*')) if file.is_file()},'generator_sha256':sha(Path(__file__))}
    save(evidence/'verification.json',record);save(evidence/'state.json',{'status':'passed','frozen_equal':True,'calls':len(calls)})
    print(json.dumps({k:record[k] for k in ('status','packaged_source_files','guarded_native_cli_calls','process_calls','encoded_primary_frames','new_stereo_sample_frames')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--public',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args();run(a.work.resolve(),a.public.resolve(),a.evidence.resolve())
