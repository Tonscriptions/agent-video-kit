"""Native CLI audio buses against fixed V28 and independently authored PCM.

Requires local FFmpeg and native NumPy/Pillow. All input media is generated
CC0 material. No production renderer is imported by the reference evaluator.
Lossless float MKV samples are the acceptance signal; AAC MP4 is a preview.
"""
from __future__ import annotations
import argparse,copy,hashlib,io,json,os,shutil,subprocess,sys,time,wave,zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASELINE='3c200b5aefa8f3b6551e6a74e42a06e2a55d4c22'
TPS,SR,FPS,W,H=90000,48000,12,320,160
SECONDS=2;N=SECONDS*SR

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def frozen():return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/tests').rglob('*.py'),ROOT/'docs/specs/agent-project.schema.json'])}

TITLES=['additive root mix','gain after child sum','deep bus gains','sample gain across offset window',
        'stereo balance','container audio mute','solo stays inside its sequence','container compressor after sum',
        'track compressor after sum','container sample fades','one-tick audio placement','container EQ and filters']

def operations(code):
    ops=[{'op':'update_track','track_id':'track_video_1','patch':{'overlap_policy':'allow'}},
         {'op':'append_clip','track_id':'track_video_1','id':'background','asset_id':'frames',
          'source_in_tick':0,'source_out_tick':SECONDS*TPS,'duration_tick':SECONDS*TPS,'timeline_start_tick':0}]
    def sequence(name):ops.append({'op':'add_sequence','id':name,'duration_tick':SECONDS*TPS})
    def track(seq,name,**audio):ops.append({'op':'add_track','sequence_id':seq,'id':name,'kind':'audio','order':1,'audio':audio})
    def tone(seq,track,name,**extra):ops.append({'op':'append_clip','sequence_id':seq,'track_id':track,'id':'leaf_'+str(len(ops)),
        'asset_id':name,'source_in_tick':0,'source_out_tick':SECONDS*TPS,'duration_tick':SECONDS*TPS,'timeline_start_tick':0,**extra})
    def group(child,**extra):
        target=extra.pop('target','seq_main')
        ops.append({'op':'append_sequence_clip','sequence_id':target,'track_id':'track_video_1' if target=='seq_main' else target+'_video_1',
            'id':'group_'+str(len(ops)),'nested_sequence_id':child,'source_in_tick':0,'source_out_tick':SECONDS*TPS,
            'duration_tick':SECONDS*TPS,'timeline_start_tick':0,**extra})
    if code in {'B01','B09','B11'}:
        if code=='B01':tone('seq_main','track_audio_1','tone_a');track('seq_main','second');tone('seq_main','second','tone_b')
        elif code=='B09':
            ops.append({'op':'update_track','track_id':'track_audio_1','patch':{'overlap_policy':'allow','audio':{'compressor':{'threshold':.1,'ratio':4,'attack':1,'release':50}}}})
            tone('seq_main','track_audio_1','tone_a');tone('seq_main','track_audio_1','negative',audio={'volume':.5})
        else:tone('seq_main','track_audio_1','tone_a',timeline_start_tick=1,source_out_tick=TPS,duration_tick=TPS)
        return ops
    sequence('child');tone('child','child_audio_1','tone_a')
    if code in {'B02','B12'}:
        track('child','second');tone('child','second','tone_b')
    if code=='B02':group('child',audio={'volume':.5})
    elif code=='B03':sequence('middle');group('child',target='middle',audio={'volume':.5});group('middle',audio={'volume':.5})
    elif code=='B04':group('child',source_out_tick=TPS*3//2,duration_tick=TPS*3//2,timeline_start_tick=TPS//4,
             audio={'volume':0},keyframes=[{'property':'audio.volume','keyframes':[{'at_tick':0,'value':0,'interpolation':'linear'},
                                                                          {'at_tick':TPS*3//2,'value':1,'interpolation':'linear'}]}])
    elif code=='B05':group('child',audio={'pan':.5})
    elif code=='B06':group('child',audio={'muted':True})
    elif code=='B07':
        track('child','solo_selected',solo=True);tone('child','solo_selected','tone_b')
        group('child');tone('seq_main','track_audio_1','tone_a')
    elif code=='B08':
        track('child','cancel');tone('child','cancel','negative',audio={'volume':.5})
        group('child',audio={'compressor':{'threshold':.1,'ratio':4,'attack':1,'release':50}})
    elif code=='B10':group('child',audio={'fade_in':.5,'fade_out':.5})
    elif code=='B12':group('child',audio={'equalizer':{'frequency':400,'gain':-6,'width':1},'highpass':80,'lowpass':5000})
    return ops

def reference(code,sources,ff,np):
    a,b=sources['tone_a'].astype(np.float64),sources['tone_b'].astype(np.float64)
    t=np.arange(N,dtype=np.float64)/SR
    if code in {'B01','B07'}:return (a+b).astype(np.float32)
    if code=='B02':return ((a+b)*.5).astype(np.float32)
    if code=='B03':return (a*.25).astype(np.float32)
    if code=='B04':
        out=np.zeros((N,2),np.float32);count=SR*3//2;out[SR//4:SR//4+count]=a[:count]*(np.arange(count)/count)[:,None];return out
    if code=='B05':return (a*np.array([.5,1.])).astype(np.float32)
    if code=='B06':return np.zeros((N,2),np.float32)
    if code in {'B08','B09'}:
        # The effect algorithm is native FFmpeg on an independently summed
        # float buffer. This proves placement, not compressor perceptual quality.
        raw=ff(['-f','f32le','-ar',SR,'-ac',2,'-i','pipe:0','-af','acompressor=threshold=0.1:ratio=4:attack=1:release=50',
                '-f','f32le','-c:a','pcm_f32le','pipe:1'],(a*.5).astype(np.float32).tobytes())
        return np.frombuffer(raw,np.float32).reshape(-1,2).copy()
    if code=='B10':return (a*(np.minimum(1,t/.5)*np.minimum(1,(2-t)/.5))[:,None]).astype(np.float32)
    if code=='B11':
        out=np.zeros((N,2),np.float32);out[1:SR+1]=a[:SR];return out
    if code=='B12':
        raw=ff(['-f','f32le','-ar',SR,'-ac',2,'-i','pipe:0','-af','equalizer=f=400:t=q:w=1:g=-6,highpass=f=80,lowpass=f=5000',
                '-f','f32le','-c:a','pcm_f32le','pipe:1'],(a+b).astype(np.float32).tobytes())
        return np.frombuffer(raw,np.float32).reshape(-1,2).copy()
    raise ValueError(code)

def run(output,work,font,font_license):
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    assert not output.exists() and not work.exists(),'Use fresh output/work paths'
    assert font.is_file() and font_license.is_file()
    output.mkdir(parents=True);work.mkdir(parents=True);freeze=frozen();began=datetime.now(timezone.utc).isoformat()
    def ff(args,raw=None):return subprocess.run(['ffmpeg','-v','error',*map(str,args)],input=raw,capture_output=True,check=True).stdout
    def pcm(path):return np.frombuffer(ff(['-i',path,'-map','0:a:0','-f','f32le','-c:a','pcm_f32le','pipe:1']),np.float32).reshape(-1,2).copy()
    def video(path):return np.frombuffer(ff(['-i',path,'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3).copy()
    def probe(path):return json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)],capture_output=True,check=True).stdout)
    raw=subprocess.run(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT,capture_output=True,check=True).stdout
    baseline=work/'baseline'
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for item in archive.infolist():
            if item.is_dir():continue
            p=(baseline/item.filename).resolve();assert p.is_relative_to(baseline.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.read(item))
    frames=np.zeros((FPS*SECONDS,H,W,3),np.uint8);frames[:]=(52,84,120)
    for i,frame in enumerate(frames):
        frame[H-22:H-10,8+i*10:32+i*10]=(238,238,238)
        for bit in range(5):frame[4:16,8+bit*18:20+bit*18]=235 if i&(1<<bit) else 15
    ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264rgb','-preset','ultrafast','-crf',0,output/'source.mp4'],frames.tobytes())
    assert np.array_equal(video(output/'source.mp4'),frames)
    t=np.arange(N,dtype=np.float64)/SR;sources={}
    for name,freqs,amp in (('tone_a',(400,800),.24),('tone_b',(1200,1600),.13),('negative',(400,800),-.24)):
        values=np.rint(np.stack([np.sin(2*np.pi*f*t) for f in freqs],axis=1)*amp*32767).astype('<i2')
        path=output/f'{name}.wav'
        with wave.open(str(path),'wb') as h:h.setparams((2,2,SR,0,'NONE','not compressed'));h.writeframes(values.tobytes())
        sources[name]=pcm(path);assert np.array_equal(sources[name],values.astype(np.float32)/32768)
    shutil.copyfile(font_license,output/'font-license.txt')
    provenance={'license_spdx':'CC0-1.0','description':'Generated moving frame-code video and 48-kHz stereo sinusoids, two seconds; no human, stock or model input',
                'generator':'scripts/smoke_audio_buses.py','generator_sha256':sha(Path(__file__)),'baseline_ref':BASELINE,
                'font':{'sha256':sha(font),'license_sha256':sha(font_license),'binary_distributed':False},
                'sources':{p.name:{'sha256':sha(p),'probe':probe(p)} for p in sorted(output.iterdir()) if p.suffix in {'.wav','.mp4'}},
                'new_model_inference':0,'third_party_binaries_distributed':False}
    save(output/'fixture-provenance.json',provenance)
    calls=[];bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args,old=False,allow_failure=False):
        command=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(baseline/'product/src' if old else ROOT/'product/src'),*map(str,args)]
        start=time.monotonic();p=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=300);number=len(calls)
        (work/f'call-{number:03}.stdout.log').write_bytes(p.stdout);(work/f'call-{number:03}.stderr.log').write_bytes(p.stderr)
        value=json.loads(p.stdout.decode('utf-8-sig'));calls.append({'args':list(map(str,args)),'old':old,'exit_code':p.returncode,'seconds':time.monotonic()-start,'result':value});save(work/'partial-calls.json',calls)
        if p.returncode and not allow_failure:raise RuntimeError(value)
        return value
    cases=[];decoded={};references={};videos={}
    for ordinal,title in enumerate(TITLES,1):
        code=f'B{ordinal:02}';project=work/code;cli('project','init',project);ops=operations(code)
        names=sorted({v['asset_id'] for v in ops if v.get('asset_id')})
        for name in names:
            path=output/'source.mp4' if name=='frames' else output/f'{name}.wav'
            cli('media','ingest','--project',project,'--input',path,'--asset-id',name,
                '--verification-status','verified','--permitted-use','commercial_ad','--source-url','local://generated-audio-buses',
                '--license-spdx','CC0-1.0','--evidence','local://scripts/smoke_audio_buses.py')
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['settings']['canvas'].update(width=W,height=H)
        p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        p['settings']['output']={'container':'mkv','video':{'codec':'libx264','preset':'ultrafast','crf':0,'pixel_format':'yuv444p'},'audio':{'codec':'pcm_f32le','bitrate':'192k'}}
        save(project/'project.json',p);changes=project/'changes.json';save(changes,{'operations':ops});cli('timeline','compose','--project',project,'--input',changes)
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=SECONDS*TPS;save(project/'project.json',p)
        before=json.dumps({k:p[k] for k in ('settings','assets','sequences')},sort_keys=True);ledger=(project/'rights-ledger.json').read_bytes();results={}
        for old in (True,False):
            name='before' if old else 'after';path=project/f'renders/{name}.mkv'
            results[name]=cli('render','--project',project,'--output',path,'--publish',old=old)
            dest=output/f'{code}-{name}.mkv';shutil.copyfile(path,dest);shutil.copyfile(path.with_suffix('.mkv.manifest.json'),dest.with_suffix('.mkv.manifest.json'))
            ff(['-i',dest,'-map','0:v:0','-map','0:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',output/f'{code}-{name}.mp4'])
            decoded[(code,name)]=pcm(dest);videos[(code,name)]=video(dest)
        quality=cli('quality','check','--project',project,'--input',project/'renders/after.mkv','--expensive',allow_failure=True)
        policy=cli('policy','audit','--project',project)
        after=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        assert before==json.dumps({k:after[k] for k in ('settings','assets','sequences')},sort_keys=True) and ledger==(project/'rights-ledger.json').read_bytes()
        expected=reference(code,sources,ff,np);assert expected.shape==(N,2);references[code]=expected
        ff(['-f','f32le','-ar',SR,'-ac',2,'-i','pipe:0','-c:a','pcm_f32le',output/f'{code}-reference.wav'],expected.tobytes())
        assert np.array_equal(pcm(output/f'{code}-reference.wav'),expected)
        comparisons={}
        for name in ('before','after'):
            actual=decoded[(code,name)];assert actual.shape==expected.shape and np.isfinite(actual).all()
            error=np.abs(actual.astype(np.float64)-expected.astype(np.float64))
            comparisons[name]={'max_sample_error':float(error.max()),'rms_sample_error':float(np.sqrt(np.mean(error**2))),
               'sample_values_over_2e_6':int(np.count_nonzero(error>2e-6)),'peak_per_channel':np.max(np.abs(actual),axis=0).tolist(),
               'decoded_float32_sha256':digest(actual.tobytes()),'per_10ms_max_sample_error':error.reshape(200,480,2).max(axis=(1,2)).tolist()}
        vbefore,vafter=videos[(code,'before')],videos[(code,'after')]
        assert vbefore.shape==vafter.shape==frames.shape
        video_equal=np.array_equal(vbefore,vafter);assert video_equal
        record={'id':code,'title':title,'sample_rate':SR,'channels':2,'sample_frames_per_variant':N,'video_frames_per_variant':len(vafter),
          'operations':ops,'comparisons':comparisons,'audio_gate_passed':comparisons['after']['sample_values_over_2e_6']==0,
          'new_old_video_pixels_equal':video_equal,'decoded_video_sha256':digest(vafter.tobytes()),'reference_float32_sha256':digest(expected.tobytes()),
          'quality_result':quality,'policy_result':policy,'render_results':results,'authored_project_and_ledger_unchanged':True,
          'reference_scope':'Independent NumPy authored mixing/envelopes; B08/B09/B12 use native FFmpeg effect algorithms on independently pre-summed PCM; not perceptual quality',
          'acceptance_media':'lossless float32 MKV; AAC MP4 is a separate lossy playback preview and is not used for sample equality',
          'outputs':{p.name:{'sha256':sha(p),'probe':probe(p)} for p in sorted(output.glob(code+'-*')) if p.suffix in {'.mkv','.mp4','.wav'}}}
        save(output/f'{code}-verification.json',record);cases.append(record)
        print(json.dumps({'case':code,'old_error':comparisons['before']['max_sample_error'],'new_error':comparisons['after']['max_sample_error'],
                          'accepted':record['audio_gate_passed'],'quality_ok':quality['ok']},ensure_ascii=False),flush=True)
    # Three rows of actual decoded PCM, same amplitude and time scale. A moving
    # cursor makes the preview clock explicit; all comparison previews are silent.
    chosen=['B01','B04','B08'];font_label=ImageFont.truetype(str(font),17)
    font_title=ImageFont.truetype(str(font),13);font_note=ImageFont.truetype(str(font),12);previews=[]
    row_height=340
    for i in range(FPS*SECONDS):
        image=Image.new('RGB',(3*W,54+len(chosen)*row_height),(20,24,32));draw=ImageDraw.Draw(image)
        for col,title in enumerate(('V28 before','Current actual','Independent PCM')):draw.text((col*W+10,12),title,font=font_label,fill='white')
        for row,code in enumerate(chosen):
            y=54+row*row_height
            for col,name in enumerate(('before','after','reference')):
                x=col*W;title=code+' '+TITLES[int(code[1:])-1];title_font=font_title
                while draw.textbbox((0,0),title,font=title_font)[2]>W-16:
                    title_font=ImageFont.truetype(str(font),title_font.size-1)
                draw.text((x+8,y+5),title,font=title_font,fill='white')
                image.paste(Image.fromarray(videos[(code,'after' if name=='reference' else name)][i]),(x,y+30))
                samples=references[code] if name=='reference' else decoded[(code,name)]
                # Extrema bins keep narrow events visible, unlike picking one
                # sample. Channels occupy separate lanes at the same scale.
                for ch,color in ((0,(65,220,145)),(1,(80,140,255))):
                    cy=y+224+ch*52;draw.line((x,cy,x+W-1,cy),fill=(80,86,94))
                    for px in range(W):
                        piece=samples[px*N//W:(px+1)*N//W]
                        lo,hi=float(piece[:,ch].min()),float(piece[:,ch].max())
                        draw.line((x+px,cy-46*hi,x+px,cy-46*lo),fill=color)
                    draw.text((x+4,cy-23),'L' if ch==0 else 'R',font=font_note,fill='white')
                    cursor=x+round(i/(FPS*SECONDS)*W);draw.line((cursor,cy-23,cursor,cy+23),fill='white')
                draw.text((x+8,y+310),'2 s | separate L/R | +/-0.5',font=font_note,fill='white')
                draw.line((x,y+row_height-1,x+W-1,y+row_height-1),fill=(70,76,86))
        previews.append(image)
    previews[0].save(output/'comparison-first.png');previews[-1].save(output/'comparison-last.png')
    gif=previews[::2];durations=[170,160,170]*4
    gif[0].save(output/'comparison.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False,disposal=2)
    pw,ph=previews[0].size
    ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{pw}x{ph}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264','-crf',16,'-pix_fmt','yuv444p',output/'comparison.mp4'],b''.join(im.tobytes() for im in previews))
    final=frozen();assert final==freeze
    gif_probe=[]
    with Image.open(output/'comparison.gif') as im:
        for i in range(im.n_frames):im.seek(i);gif_probe.append(im.info.get('duration',0))
    record={'started_at_utc':began,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,
        'frozen_before':freeze,'frozen_after':final,'frozen_file_count':len(freeze),'case_count':len(cases),'cli_count':len(calls),'cli_calls':calls,'cases':cases,
        'new_main_video_frames':sum(c['video_frames_per_variant'] for c in cases),'old_video_frames_separately_counted':sum(c['video_frames_per_variant'] for c in cases),
        'new_audio_sample_frames':len(cases)*N,'old_audio_sample_frames_separately_counted':len(cases)*N,'reference_sample_frames_separately_counted':len(cases)*N,
        'content_passed_cases':sum(c['audio_gate_passed'] and c['new_old_video_pixels_equal'] for c in cases),
        'old_failed_cases':sum(c['comparisons']['before']['sample_values_over_2e_6']>0 for c in cases),
        'preview':{'mp4_probe':probe(output/'comparison.mp4'),'gif_encoded_frames':len(gif_probe),'gif_duration_ms':sum(gif_probe),'gif_frame_durations_ms':gif_probe},
        'continuous_playback_accepted':False,'listening_accepted':False,'natural_audio_quality_accepted':False,'provenance':provenance,
        'public_files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}}
    save(output/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('case_count','cli_count','content_passed_cases','old_failed_cases','new_main_video_frames','new_audio_sample_frames','frozen_file_count')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','work','font','font-license'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.work.resolve(),args.font.resolve(),args.font_license.resolve())
