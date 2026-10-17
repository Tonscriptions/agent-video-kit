"""Native CLI cuts against unedited projects rendered by fixed V37 sources."""
from __future__ import annotations
import argparse,copy,hashlib,io,json,shutil,subprocess,sys,time,zipfile
from pathlib import Path
from smoke_fragments import frozen,save,sha

ROOT=Path(__file__).resolve().parents[1]
BASELINE='23ca3cbcd030c7a41e4618cdcfdf0b7cf3bcbb98'
TPS,FPS,W,H,SR=90000,10,240,136,48000


def run(public,work):
    import numpy as np
    from PIL import Image
    public.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    before=frozen();calls=[];baseline=work/'fixed-v37'
    save(public/'run-state.json',{'status':'running','frozen_before':before,'fixed_original_renderer_commit':BASELINE})
    archive=subprocess.check_output(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,
        'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for item in z.infolist():
            if item.is_dir():continue
            target=(baseline/item.filename).resolve();assert target.is_relative_to(baseline.resolve())
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(item))
    old_hashes={p.relative_to(baseline).as_posix():sha(p) for p in baseline.rglob('*') if p.is_file()}
    boot='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args,old=False,expected=0):
        start=time.monotonic()
        r=subprocess.run([sys.executable,'-E','-B','-X','utf8','-c',boot,
            str(baseline/'product/src' if old else ROOT/'product/src'),*map(str,args)],cwd=ROOT,capture_output=True,timeout=300)
        index=len(calls)
        for label,raw in [('stdout',r.stdout),('stderr',r.stderr)]:
            (public/f'cli-{index:03}-{label}.log').write_bytes(raw)
        value=json.loads(r.stdout.decode('utf-8-sig')) if r.stdout.strip().startswith(b'{') else {'text':r.stdout.decode('utf-8','replace')}
        calls.append({'index':index,'args':list(map(str,args)),'fixed_v37':old,'exit_code':r.returncode,
            'expected_exit_code':expected,'seconds':time.monotonic()-start,'stdout_sha256':'sha256:'+hashlib.sha256(r.stdout).hexdigest()})
        save(work/'calls-in-progress.json',calls)
        if r.returncode!=expected:
            save(public/'run-state.json',{'status':'failed','frozen_before':before,'frozen_after':frozen(),
                'failed_cli_index':index,'exit_code':r.returncode,'expected_exit_code':expected})
        assert r.returncode==expected,value
        return value
    def ff(args):
        r=subprocess.run(['ffmpeg','-v','error','-nostdin',*map(str,args)],capture_output=True,timeout=180)
        assert r.returncode==0,r.stderr.decode('utf-8','replace')
    def decode(path):
        video=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
        audio=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vn','-ar','48000','-ac','2','-f','f32le','pipe:1'])
        return np.frombuffer(video,dtype=np.uint8).reshape(-1,H,W,3),np.frombuffer(audio,dtype='<f4').reshape(-1,2)
    fixture=ROOT/'docs/assets/source-transitions-20261017'
    for name in ('source-a.mp4','sound-a.wav'):
        shutil.copyfile(fixture/name,public/name)
    shutil.copyfile(ROOT/'docs/assets/fragments-20261018/agent-grid-cc0.ttf',public/'agent-grid-cc0.ttf')
    (public/'captions.srt').write_text('1\n00:00:01,000 --> 00:00:03,000\nCTA\n',encoding='utf-8')
    provenance={'license_spdx':'CC0-1.0','source':'original counter/audio fixtures from V35; original grid font V37; new CTA cue',
        'files':{p.name:sha(p) for p in public.iterdir() if p.is_file()},'new_model_inference':0,'network_runtime':False,'virtualization':False}
    save(public/'fixture-provenance.json',provenance)
    seed=work/'seed';cli('project','init',seed)
    rights=['--verification-status','verified','--license-spdx','CC0-1.0','--permitted-use','commercial_ad','--evidence',public/'fixture-provenance.json']
    for aid,name in [('video','source-a.mp4'),('audio','sound-a.wav'),('font','agent-grid-cc0.ttf'),('captions','captions.srt')]:
        cli('media','ingest','--project',seed,'--input',public/name,'--asset-id',aid,*rights)
    p=json.loads((seed/'project.json').read_text(encoding='utf-8'))
    p['settings']['canvas']={'width':W,'height':H};p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
    seq=p['sequences'][0];seq['duration_tick']=4*TPS
    def clip(cid,aid):return {'id':cid,'asset_id':aid,'timeline_start_tick':0,'duration_tick':4*TPS,
        'source_in_tick':TPS,'source_out_tick':5*TPS,'link_id':'linked'}
    seq['tracks'][0]['clips']=[clip('v','video')];seq['tracks'][1]['clips']=[clip('a','audio')]
    save(seed/'project.json',p)
    def render(path,name,old=False):
        movie=path/'renders'/f'{name}.mkv'
        response=cli('render','--project',path,'--output',movie,'--container','mkv','--crf',0,
            '--pixel-format','yuv444p','--audio-codec','pcm_f32le','--publish',old=old)
        shutil.copyfile(movie,public/f'{name}.mkv')
        ff(['-i',movie,'-c:v','copy','-c:a','aac','-b:a','128k',public/f'{name}.mp4'])
        save(public/f'{name}-render.json',response)
        return decode(movie)
    results=[];actuals={};expectations={};edited_paths={}
    for number in range(1,8):
        name=f'C{number:02}';path=work/name;shutil.copytree(seed,path)
        project=copy.deepcopy(p);s=project['sequences'][0];v=s['tracks'][0]['clips'][0];a=s['tracks'][1]['clips'][0]
        if number in (1,2):
            v['reverse']=a['reverse']=True
            v['keyframes']=[{'property':'transform.position.x','keyframes':[{'at_tick':0,'value':.5,'interpolation':'ease_in_out'},
                {'at_tick':4*TPS,'value':.65,'interpolation':'linear'}]}]
            a['audio']={'fade_in':.7,'fade_out':.8,'volume':.8}
        if number==2:
            for c in (v,a):c['speed_curve']={'keyframes':[{'at_tick':0,'speed':.7,'interpolation':'ease_in_out'},
                {'at_tick':4*TPS,'speed':1.3,'interpolation':'linear'}]}
        if number==3:
            for c in (v,a):c.update(duration_tick=5*TPS,freeze={'at_tick':TPS,'duration_tick':TPS,'audio_mode':'silence'})
            s['duration_tick']=5*TPS
        if number==4:
            font=next(x for x in project['assets'] if x['id']=='font')
            s['tracks'].append({'id':'subtitles','kind':'subtitle','order':2,'clips':[{'id':'sub','asset_id':'captions',
                'timeline_start_tick':0,'duration_tick':4*TPS,'source_in_tick':0,'source_out_tick':4*TPS,
                'subtitle':{'style':{'fontfile':font['uri'],'font_asset_id':'font','font_size':24},'animation':{'type':'slide_up','duration':.8}}}]})
        if number in (5,6):
            child=copy.deepcopy(s);child['id']='child'
            for i,t in enumerate(child['tracks']):
                t['id']=f'child_track{i}'
                for c in t['clips']:c['id']='child_'+c['id'];c['reverse']=True
            child['tracks'][1]['audio']={'volume':.7,'pan':-.1}
            project['sequences'].append(child)
            s['tracks'][0]['clips']=[{'id':'container','sequence_id':'child','timeline_start_tick':0,'duration_tick':4*TPS,
                'source_in_tick':0,'source_out_tick':4*TPS,'audio':{'fade_in':.8,'fade_out':.7}}]
            s['tracks'][1]['clips']=[]
            # Container fades must run before trimming, not before deleting
            # time inside its child; use neutral parent envelopes for C05.
            if number==5:s['tracks'][0]['clips'][0]['audio']={}
        save(path/'project.json',project);save(public/f'{name}-original-project.json',project)
        frames,samples=render(path,name+'-original',old=True)
        if number==1:ops=[{'op':'split_clip','clip_id':cid,'at_tick':2*TPS} for cid in ('v','a')];expected=(frames,samples)
        if number==2:ops=[{'op':'ripple_delete','at_tick':TPS,'duration_tick':TPS}];expected=(np.concatenate((frames[:10],frames[20:])),np.concatenate((samples[:SR],samples[2*SR:])))
        if number==3:
            ops=[{'op':'trim_clip','clip_id':cid,'start_tick':int(1.5*TPS),'end_tick':int(3.5*TPS),'timeline_start_tick':0} for cid in ('v','a')]
            ops.append({'op':'set_sequence_duration','duration_tick':2*TPS});expected=(frames[15:35],samples[int(1.5*SR):int(3.5*SR)])
        if number==4:ops=[{'op':'split_clip','clip_id':'sub','at_tick':2*TPS}];expected=(frames,samples)
        if number==5:
            ops=[{'op':'ripple_delete','sequence_id':'child','at_tick':TPS,'duration_tick':TPS},
                {'op':'update_clip','clip_id':'container','patch':{'duration_tick':3*TPS,'source_out_tick':3*TPS}},
                {'op':'set_sequence_duration','duration_tick':3*TPS}]
            expected=(np.concatenate((frames[:10],frames[20:])),np.concatenate((samples[:SR],samples[2*SR:])))
        if number==6:
            ops=[{'op':'trim_clip','clip_id':'container','start_tick':TPS,'end_tick':3*TPS,'timeline_start_tick':0},
                 {'op':'set_sequence_duration','duration_tick':2*TPS}];expected=(frames[10:30],samples[SR:3*SR])
        if number==7:
            ops=[{'op':'ripple_insert','at_tick':TPS,'duration_tick':TPS}]
            expected=(np.concatenate((frames[:10],np.zeros_like(frames[:10]),frames[10:])),np.concatenate((samples[:SR],np.zeros_like(samples[:SR]),samples[SR:])))
        request=work/f'{name}-request.json';save(request,{'operations':ops});save(public/f'{name}-request.json',{'operations':ops})
        original_bytes=(path/'project.json').read_bytes()
        cli('timeline','compose','--project',path,'--input',request,'--dry-run')
        assert (path/'project.json').read_bytes()==original_bytes
        cli('timeline','compose','--project',path,'--input',request,'--idempotency-key',name)
        cli('timeline','compose','--project',path,'--input',request,'--idempotency-key',name)
        cli('validate','--project',path,'--strict-rights')
        actual=render(path,name+'-actual')
        assert actual[0].shape==expected[0].shape and actual[1].shape==expected[1].shape
        pixel=np.abs(actual[0].astype(np.int16)-expected[0].astype(np.int16));pcm=np.abs(actual[1]-expected[1])
        row={'case':name,'frames':len(actual[0]),'stereo_sample_frames':len(actual[1]),
            'max_rgb_difference':int(pixel.max()),'mean_rgb_difference':float(pixel.mean()),'max_pcm_difference':float(pcm.max()),
            'rgb_sha256':'sha256:'+hashlib.sha256(actual[0].tobytes()).hexdigest(),'pcm_sha256':'sha256:'+hashlib.sha256(actual[1].tobytes()).hexdigest(),
            'raw_expectation':'slice-or-insert-decoded-fixed-v37-original','status':'passed' if not pixel.any() and not pcm.any() else 'failed'}
        save(public/f'{name}-verification.json',row);results.append(row)
        assert row['status']=='passed',row
        save(public/f'{name}-actual-project.json',json.loads((path/'project.json').read_text(encoding='utf-8')))
        actuals[name]=actual;expectations[name]=expected;edited_paths[name]=path
    # Edited takes remain editable when moved through the V37 group library.
    source=edited_paths['C02'];library=work/'library';req=work/'fragment.json'
    save(req,{'id':'windowed','version':1,'sequence_id':'seq_main','clip_ids':['v']})
    cli('fragment','save','--project',source,'--library',library,'--input',req)
    target=work/'C08';shutil.copytree(seed,target)
    project=copy.deepcopy(p)
    for t in project['sequences'][0]['tracks']:t['clips']=[]
    project['sequences'][0]['duration_tick']=1;save(target/'project.json',project)
    save(req,{'id':'windowed','version':1,'sequence_id':'seq_main','track_id':'track_video_1','at_tick':0,'instance_id':'reused'})
    cli('fragment','apply','--project',target,'--library',library,'--input',req)
    actual=render(target,'C08-actual');expected=expectations['C02']
    assert np.array_equal(actual[0],expected[0]) and np.array_equal(actual[1],expected[1])
    row={'case':'C08','frames':len(actual[0]),'stereo_sample_frames':len(actual[1]),'max_rgb_difference':0,'max_pcm_difference':0.,'status':'passed',
        'rgb_sha256':'sha256:'+hashlib.sha256(actual[0].tobytes()).hexdigest(),'pcm_sha256':'sha256:'+hashlib.sha256(actual[1].tobytes()).hexdigest()}
    save(public/'C08-verification.json',row);results.append(row)
    save(public/'C08-actual-project.json',json.loads((target/'project.json').read_text(encoding='utf-8')))
    # Opaque contain bars must not become holes over a lower video track.
    path=work/'C09';shutil.copytree(seed,path);project=copy.deepcopy(p);s=project['sequences'][0]
    v=s['tracks'][0]['clips'][0];back=copy.deepcopy(v);back['id']='background';back.pop('link_id',None)
    back['source_in_tick']=0;back['source_out_tick']=4*TPS
    s['tracks'].append({'id':'background_track','kind':'video','order':-1,'clips':[back]})
    v['crop']={'x':0,'y':0,'width':120,'height':136,'fit':'fit'}
    save(path/'project.json',project);save(public/'C09-original-project.json',project)
    expected=render(path,'C09-original',old=True)
    req=work/'C09-request.json';request={'operations':[{'op':'split_clip','clip_id':'v','at_tick':2*TPS}]}
    save(req,request);save(public/'C09-request.json',request)
    cli('timeline','compose','--project',path,'--input',req)
    actual=render(path,'C09-actual')
    assert np.array_equal(actual[0],expected[0]) and np.array_equal(actual[1],expected[1])
    row={'case':'C09','frames':len(actual[0]),'stereo_sample_frames':len(actual[1]),'max_rgb_difference':0,'max_pcm_difference':0.,'status':'passed',
        'rgb_sha256':'sha256:'+hashlib.sha256(actual[0].tobytes()).hexdigest(),'pcm_sha256':'sha256:'+hashlib.sha256(actual[1].tobytes()).hexdigest()}
    save(public/'C09-verification.json',row);results.append(row)
    save(public/'C09-actual-project.json',json.loads((path/'project.json').read_text(encoding='utf-8')))
    # A locked destructive cut rejects atomically on actual product CLI.
    rejection=work/'rejected';shutil.copytree(seed,rejection)
    project=copy.deepcopy(p);project['sequences'][0]['tracks'][0]['locked']=True;save(rejection/'project.json',project)
    req=work/'locked.json';save(req,{'operations':[{'op':'ripple_delete','at_tick':TPS,'duration_tick':TPS}]})
    original=(rejection/'project.json').read_bytes();cli('timeline','compose','--project',rejection,'--input',req,expected=2)
    assert original==(rejection/'project.json').read_bytes()
    gallery=[]
    for index in range(20):
        image=np.concatenate([np.concatenate([expectations[c][0][index],actuals[c][0][index]],axis=1) for c in ('C02','C03')],axis=0)
        gallery.append(Image.fromarray(image))
    gallery[0].save(public/'comparison.gif',save_all=True,append_images=gallery[1:],duration=100,loop=0,optimize=False,disposal=2)
    save(public/'run-state.json',{'status':'passed','frozen_before':before,'frozen_after':frozen(),'frozen_equal':before==frozen()})
    save(public/'verification.json',{'status':'passed','fixed_original_renderer_commit':BASELINE,
        'fixed_original_renderer_sha256':old_hashes,'source_before':before,'source_after':frozen(),'frozen_equal':before==frozen(),
        'cases':results,'cli_count':len(calls),'calls':calls,'expected_rejections':1,
        'new_frames':sum(r['frames'] for r in results),'new_stereo_sample_frames':sum(r['stereo_sample_frames'] for r in results),
        'new_model_inference':0,'continuous_playback_or_listening':False,'oracle_limit':'fixed same product renderer; not an independent source-time or image-quality algorithm',
        'fixture_provenance':provenance,'files':{f.name:{'bytes':f.stat().st_size,'sha256':sha(f)} for f in public.iterdir() if f.is_file()}})
    assert before==frozen()
    print(json.dumps({'status':'passed','cases':len(results),'cli_count':len(calls),'frames':sum(r['frames'] for r in results)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.work.resolve())
