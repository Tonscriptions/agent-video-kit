"""Actual local CLI tempo context, fixed V29, PCM gates and silent GIF preview.

Native NumPy/Pillow and FFmpeg are required. Generated media is CC0. No
renderer/time-mapping implementation is imported by the independent checker.
Full active-interval failures remain failures even if an interior gate passes.
"""
from __future__ import annotations
import argparse, hashlib, io, json, math, os, shutil, subprocess, sys, time, wave, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASELINE='d7acaa2933be8d8d6ac77fa54b0f9a1d9982cdf4'
TPS,SR,FPS,W,H=90000,48000,12,320,160
SECONDS=3;N=SECONDS*SR
TITLES=['nested ramp DC','reverse ramp DC','direct ramp DC','nested 2x DC','slow ramp DC',
        'selected DC, loud outside','authored silent interval','stereo antiphase','silent right channel','unity exact samples','slow retained tail marker']

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def frozen():return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/tests').rglob('*.py'),ROOT/'docs/specs/agent-project.schema.json'])}

def operations(code):
    source={'T06':'selection','T07':'gap','T08':'antiphase','T09':'left_only','T10':'stereo','T11':'tail_marker'}.get(code,'dc')
    ops=[{'op':'update_track','track_id':'track_video_1','patch':{'overlap_policy':'allow'}},
         {'op':'append_clip','track_id':'track_video_1','id':'background','asset_id':'frames',
          'source_in_tick':0,'source_out_tick':SECONDS*TPS,'duration_tick':SECONDS*TPS,'timeline_start_tick':0}]
    low,high=(.5,1) if code in ('T05','T11') else (1,2)
    source_start,source_end=(TPS//2,3*TPS//2) if code=='T06' else (0,2*TPS)
    span=(source_end-source_start)/TPS
    duration=round(span*math.log(high/low)/(high-low)*TPS)
    curve={'keyframes':[{'at_tick':0,'speed':low},{'at_tick':source_end-source_start,'speed':high}]}
    if code=='T03':
        ops.append({'op':'append_clip','track_id':'track_audio_1','id':'direct','asset_id':source,
                    'source_in_tick':0,'source_out_tick':2*TPS,'duration_tick':duration,'timeline_start_tick':0,'speed_curve':curve})
    else:
        ops.extend([{'op':'add_sequence','id':'child','duration_tick':2*TPS},
                    {'op':'append_clip','sequence_id':'child','track_id':'child_audio_1','id':'leaf','asset_id':source,
                     'source_in_tick':0,'source_out_tick':2*TPS,'duration_tick':2*TPS,'timeline_start_tick':0}])
        group={'op':'append_sequence_clip','track_id':'track_video_1','id':'container','nested_sequence_id':'child',
               'source_in_tick':source_start,'source_out_tick':source_end,'duration_tick':duration,'timeline_start_tick':0,'speed_curve':curve}
        if code=='T02':group['reverse']=True
        if code in ('T04','T10'):
            group.pop('speed_curve');group['speed']=2 if code=='T04' else 1
            duration=TPS if code=='T04' else 2*TPS;group['duration_tick']=duration
        ops.append(group)
    return ops,source,duration

def longest_zero(samples,np):
    indices=np.flatnonzero(np.all(samples==0,axis=1))
    if not len(indices):return {'sample_frames':0,'longest_run':0,'first':None,'last':None,'longest_start':None}
    cuts=np.flatnonzero(np.diff(indices)!=1)+1;groups=np.split(indices,cuts);best=max(groups,key=len)
    return {'sample_frames':int(len(indices)),'longest_run':int(len(best)),
            'first':int(indices[0]),'last':int(indices[-1]),'longest_start':int(best[0])}

def metrics(code,samples,duration,source,np):
    active=math.ceil(duration*SR/TPS)
    # This interval is independently authored; it is not moved to avoid a
    # failed output. Full active/tail metrics are retained separately below.
    start,end=(.2,1.8) if code in ('T05','T11') else ((.1,.5) if code=='T06' else ((.1,.9) if code=='T04' else (.2,1.)))
    checked=samples[round(start*SR):round(end*SR)]
    result={'sample_frames':len(samples),'finite':bool(np.isfinite(samples).all()),'active_sample_frames':active,
            'checked_half_open_seconds':[start,end],'checked_sample_frames':len(checked),
            'active_literal_zero':longest_zero(samples[:active],np),
            'interior_literal_zero':longest_zero(checked,np),'peak_per_channel':np.max(np.abs(samples),axis=0).tolist(),
            'decoded_float32_sha256':digest(samples.tobytes()),'per_10ms_peak':np.max(np.abs(samples.reshape(300,480,2)),axis=1).tolist()}
    if code in {'T01','T02','T03','T04','T05','T06'}:
        expected=10000/32768
        error=np.abs(checked.astype(np.float64)-expected)
        all_error=np.abs(samples[:active].astype(np.float64)-expected)
        result.update(scope='DC sample amplitude, including a separate full active interval gate',
          dc_tolerance=.001,dc_max_interior_deviation=float(error.max()),dc_max_active_deviation=float(all_error.max()),
          interior_gate_passed=bool(error.max()<=.001),active_gate_passed=bool(all_error.max()<=.001),
          active_sample_values_over_tolerance=int(np.count_nonzero(all_error>.001)),
          active_zero_sample_frames_per_10ms=[int(np.count_nonzero(np.all(samples[i:min(i+480,active)]==0,axis=1))) for i in range(0,active,480)])
    elif code=='T07':
        quiet=samples[round(.6*SR):round(.9*SR)]
        peak=float(np.max(np.abs(quiet)));result.update(scope='authored silence interior and retained audible region, transient edges unaccepted',
          authored_silent_source_half_open_seconds=[.5,1.5],independent_mapped_silence_half_open_seconds=[2*math.log1p(.25),2*math.log1p(.75)],
          checked_half_open_seconds=[.6,.9],checked_sample_frames=len(quiet),silent_interior_peak=peak,
          interior_gate_passed=bool(peak==0 and np.max(np.abs(samples[:4800]))>.25),active_gate_passed=None)
    elif code=='T08':
        cancellation=float(np.max(np.abs(samples[:,0]+samples[:,1])))
        result.update(scope='exact antiphase cancellation and audible peak; does not accept pitch or general stereo phase',
          max_abs_left_plus_right=cancellation,interior_gate_passed=bool(cancellation==0 and np.max(np.abs(samples))>.25),active_gate_passed=None)
    elif code=='T09':
        right=float(np.max(np.abs(samples[:,1])))
        result.update(scope='silent right channel and audible left; pitch unaccepted',right_channel_peak=right,
          interior_gate_passed=bool(right==0 and np.max(np.abs(samples[:,0]))>.25),active_gate_passed=None)
    elif code=='T10':
        reference=np.zeros((N,2),np.float32);reference[:len(source)]=source
        result.update(scope='every authored unity sample and the declared trailing silence',
          max_sample_error=float(np.max(np.abs(samples-reference))),
          interior_gate_passed=bool(np.array_equal(samples,reference)),active_gate_passed=bool(np.array_equal(samples,reference)))
    else:
        tail=samples[active-512:active]
        terminal_error=float(np.max(np.abs(tail.astype(np.float64)-25000/32768)))
        body_error=float(np.max(np.abs(checked.astype(np.float64)-10000/32768)))
        trailing_peak=float(np.max(np.abs(samples[active:])))
        result.update(scope='actual terminal source marker, independent DC body and authored trailing silence; transient edge timing unaccepted',
          terminal_sample_frames_checked=512,terminal_max_deviation=terminal_error,body_max_deviation=body_error,
          trailing_authored_silence_peak=trailing_peak,interior_gate_passed=bool(terminal_error<=.001 and body_error<=.001 and trailing_peak==0),
          active_gate_passed=None)
    return result

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
        frame[H-22:H-10,8+i*7:32+i*7]=(238,238,238)
        for bit in range(6):frame[4:16,8+bit*18:20+bit*18]=235 if i&(1<<bit) else 15
    ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264rgb','-preset','ultrafast','-crf',0,output/'source.mp4'],frames.tobytes())
    assert np.array_equal(video(output/'source.mp4'),frames)
    t=np.arange(2*SR,dtype=np.float64)/SR;sources={}
    for name in ('dc','selection','gap','antiphase','left_only','stereo','tail_marker'):
        values=np.full((2*SR,2),10000,dtype='<i2')
        if name=='selection':values[:SR//2]=-25000;values[3*SR//2:]=25000
        if name=='gap':values[SR//2:3*SR//2]=0
        if name=='tail_marker':values[2*SR-4800:]=25000
        if name in ('antiphase','left_only','stereo'):
            values[:,0]=np.rint(10000*np.sin(2*np.pi*400*t))
            values[:,1]=-values[:,0] if name=='antiphase' else (0 if name=='left_only' else np.rint(7500*np.sin(2*np.pi*800*t)))
        path=output/f'{name}.wav'
        with wave.open(str(path),'wb') as h:h.setparams((2,2,SR,0,'NONE','not compressed'));h.writeframes(values.tobytes())
        sources[name]=pcm(path);assert np.array_equal(sources[name],values.astype(np.float32)/32768)
    shutil.copyfile(font_license,output/'font-license.txt')
    provenance={'license_spdx':'CC0-1.0','description':'Generated 3-s moving frame-code video and 2-s 48-kHz stereo PCM16; no human, stock, model or external content',
        'generator':'scripts/smoke_audio_tempo_context.py','generator_sha256':sha(Path(__file__)),'baseline_ref':BASELINE,
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
    cases=[];decoded={};videos={}
    for ordinal,title in enumerate(TITLES,1):
        code=f'T{ordinal:02}';project=work/code;ops,source,duration=operations(code);cli('project','init',project)
        for name in ('frames',source):
            path=output/'source.mp4' if name=='frames' else output/f'{name}.wav'
            cli('media','ingest','--project',project,'--input',path,'--asset-id',name,
                '--verification-status','verified','--permitted-use','commercial_ad','--source-url','local://generated-audio-tempo-context',
                '--license-spdx','CC0-1.0','--evidence','local://scripts/smoke_audio_tempo_context.py')
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['settings']['canvas'].update(width=W,height=H)
        p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        p['settings']['output']={'container':'mkv','video':{'codec':'libx264','preset':'ultrafast','crf':0,'pixel_format':'yuv444p'},'audio':{'codec':'pcm_f32le','bitrate':'192k'}}
        save(project/'project.json',p);changes=project/'changes.json';save(changes,{'operations':ops});cli('timeline','compose','--project',project,'--input',changes)
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=SECONDS*TPS;save(project/'project.json',p)
        before=json.dumps({k:p[k] for k in ('settings','assets','sequences')},sort_keys=True);ledger=(project/'rights-ledger.json').read_bytes();results={};measurements={}
        for old in (True,False):
            name='before' if old else 'after';path=project/f'renders/{name}.mkv'
            results[name]=cli('render','--project',project,'--output',path,'--publish',old=old)
            dest=output/f'{code}-{name}.mkv';shutil.copyfile(path,dest);shutil.copyfile(path.with_suffix('.mkv.manifest.json'),dest.with_suffix('.mkv.manifest.json'))
            ff(['-i',dest,'-map','0:v:0','-map','0:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',output/f'{code}-{name}.mp4'])
            ff(['-i',dest,'-map','0:a:0','-c:a','pcm_f32le',output/f'{code}-{name}.wav'])
            decoded[(code,name)]=pcm(dest);videos[(code,name)]=video(dest)
            assert decoded[(code,name)].shape==(N,2) and np.isfinite(decoded[(code,name)]).all()
            assert np.array_equal(pcm(output/f'{code}-{name}.wav'),decoded[(code,name)])
            measurements[name]=metrics(code,decoded[(code,name)],duration,sources[source],np)
        quality=cli('quality','check','--project',project,'--input',project/'renders/after.mkv','--expensive',allow_failure=True)
        policy=cli('policy','audit','--project',project)
        after=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        assert before==json.dumps({k:after[k] for k in ('settings','assets','sequences')},sort_keys=True) and ledger==(project/'rights-ledger.json').read_bytes()
        vbefore,vafter=videos[(code,'before')],videos[(code,'after')]
        assert vbefore.shape==vafter.shape==frames.shape and np.array_equal(vbefore,vafter)
        record={'id':code,'title':title,'operations':ops,'active_duration_tick':duration,'metrics':measurements,
          'new_old_video_pixels_equal':True,'decoded_video_sha256':digest(vafter.tobytes()),'sample_rate':SR,'channels':2,
          'video_frames_per_variant':len(vafter),'sample_frames_per_variant':N,'quality_result':quality,'policy_result':policy,
          'render_results':results,'authored_project_and_ledger_unchanged':True,
          'content_scope':'Case-specific interior/control gate; full active DC gate is separately retained, not listening or general time-stretch acceptance',
          'acceptance_media':'float32 PCM MKV/WAV; AAC MP4 is lossy playback only',
          'outputs':{p.name:{'sha256':sha(p),'probe':probe(p)} for p in sorted(output.glob(code+'-*')) if p.suffix in {'.mkv','.mp4','.wav'}}}
        save(output/f'{code}-verification.json',record);cases.append(record)
        print(json.dumps({'case':code,'old_interior_passed':measurements['before']['interior_gate_passed'],
              'new_interior_passed':measurements['after']['interior_gate_passed'],'new_active_passed':measurements['after']['active_gate_passed'],
              'new_active_zero':measurements['after']['active_literal_zero']['sample_frames'],'quality_ok':quality['ok']},ensure_ascii=False),flush=True)
    formal_calls=list(calls)
    # Separate preflight limit, not a twelfth media delivery or an actual
    # hours-long render. Its expected error is preserved, not suppressed.
    budget_project=work/'S01-budget';cli('project','init',budget_project)
    for name,path in (('frames',output/'source.mp4'),('dc',output/'dc.wav')):
        cli('media','ingest','--project',budget_project,'--input',path,'--asset-id',name,
            '--verification-status','verified','--permitted-use','commercial_ad',
            '--source-url','local://generated-audio-tempo-context','--license-spdx','CC0-1.0',
            '--evidence','local://scripts/smoke_audio_tempo_context.py')
    budget_ops,_,_=operations('T01');budget_ops.pop()
    budget_ops.extend([{'op':'add_sequence','id':'middle','duration_tick':200*TPS},
        {'op':'append_sequence_clip','sequence_id':'middle','track_id':'middle_video_1','id':'slow_inner',
         'nested_sequence_id':'child','source_in_tick':0,'source_out_tick':2*TPS,'duration_tick':200*TPS,
         'timeline_start_tick':0,'speed':.01},
        {'op':'append_sequence_clip','track_id':'track_video_1','id':'slow_outer','nested_sequence_id':'middle',
         'source_in_tick':0,'source_out_tick':200*TPS,'duration_tick':round(20000*math.log(2)*TPS),'timeline_start_tick':0,
         'speed_curve':{'keyframes':[{'at_tick':0,'speed':.01},{'at_tick':200*TPS,'speed':.02}]}}])
    save(budget_project/'changes.json',{'operations':budget_ops})
    cli('timeline','compose','--project',budget_project,'--input',budget_project/'changes.json')
    def authored_budget():
        p=json.loads((budget_project/'project.json').read_text(encoding='utf-8-sig'))
        return json.dumps({k:p[k] for k in ('settings','assets','sequences')},sort_keys=True),sha(budget_project/'rights-ledger.json')
    before_budget=authored_budget();budget_output=budget_project/'renders/never-created.mkv'
    budget=cli('render','--project',budget_project,'--output',budget_output,'--dry-run',allow_failure=True)
    assert calls[-1]['exit_code']==2 and budget['errors'][0]['code']=='AUDIO_TEMPO_CONTEXT_LIMIT'
    assert not budget_output.exists() and before_budget==authored_budget()
    cli('policy','audit','--project',budget_project)
    budget_calls=calls[len(formal_calls):];assert len(budget_calls)==6
    save(output/'S01-budget-verification.json',{'scope':'Separate dry-run preflight, no render/decode delivery or performance acceptance',
       'operations':budget_ops,'cli_count':len(budget_calls),'cli_calls':budget_calls,'expected_rejection':budget,
       'expected_exit_code':2,'authored_project_and_ledger_unchanged':True,'output_not_created':True})
    old=decoded[('T01','before')];zero=longest_zero(old[9600:48000],np)
    center=(9600+zero['longest_start']+zero['longest_run']/2)/SR
    zoom=(center-.03,center+.03)
    label=ImageFont.truetype(str(font),17);small=ImageFont.truetype(str(font),12)
    preview=[];height=544
    def wave_lane(draw,samples,x,cy,interval,color,channel,cursor=None,reference=True,gain=58):
        start,end=interval
        draw.line((x+4,cy,x+W-5,cy),fill=(75,80,90))
        # Independent DC amplitude is visible only over the selected active
        # interval; no production tempo helper is used for this reference.
        if reference:
            yy=cy-gain*(10000/32768)/.35
            for px in range(4,W-5,6):draw.line((x+px,yy,x+px+2,yy),fill=(120,120,230))
        for px in range(W-8):
            a=round((start+(end-start)*px/(W-8))*SR)
            b=round((start+(end-start)*(px+1)/(W-8))*SR)
            values=samples[max(0,a):min(len(samples),max(a+1,b)),channel]
            if not len(values):continue
            low,high=float(values.min()),float(values.max())
            draw.line((x+px+4,cy-gain*high/.35,x+px+4,cy-gain*low/.35),fill=color)
        if cursor is not None and start<=cursor<end:
            xx=x+4+round((cursor-start)/(end-start)*(W-8));draw.line((xx,cy-60,xx,cy+10),fill='white')
        draw.text((x+8,cy+5),'L' if channel==0 else 'R',font=small,fill='white')
    for i in range(FPS*SECONDS):
        image=Image.new('RGB',(W*3,height),(20,24,32));draw=ImageDraw.Draw(image)
        for col,(name,title) in enumerate((('source','Original DC / video'),('before','V29 reset windows'),('after','Current context + end'))):
            x=col*W;draw.text((x+8,10),title,font=label,fill='white')
            image.paste(Image.fromarray(frames[i] if name=='source' else videos[('T01',name)][i]),(x,40))
            samples=sources['dc'] if name=='source' else decoded[('T01',name)]
            draw.text((x+8,208),'0..3 s | source audio ends at 2 s' if name=='source' else '0..3 s | retimed audio ends at 1.386 s',font=small,fill='white')
            for channel,color in ((0,(65,220,145)),(1,(80,175,255))):
                wave_lane(draw,samples,x,290+channel*78,(0,3),color,channel,i/FPS,False)
            draw.text((x+8,398),f'Zoom {zoom[0]:.4f}..{zoom[1]:.4f} s, L/R',font=small,fill='white')
            for channel,color in ((0,(65,220,145)),(1,(80,175,255))):
                # Zoom lanes use a smaller gain so their traces cannot cover
                # headings. A shared exact DC guide is not a CLI output.
                cy=450+channel*42
                wave_lane(draw,samples,x,cy,zoom,color,channel,None,True,gain=20)
            draw.text((x+8,522),'Actual extrema bins | silent preview',font=small,fill='white')
        preview.append(image)
    preview[0].save(output/'comparison-first.png');preview[-1].save(output/'comparison-last.png')
    gif=preview[::2];durations=[170,160,170]*6
    gif[0].save(output/'comparison.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False,disposal=2)
    ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{3*W}x{height}','-r',FPS,'-i','pipe:0','-an',
        '-c:v','libx264','-crf',16,'-pix_fmt','yuv444p',output/'comparison.mp4'],b''.join(im.tobytes() for im in preview))
    # A separate actual decoded tail checks the complete selected end.
    tail=Image.new('RGB',(W*3,300),(20,24,32));draw=ImageDraw.Draw(tail)
    duration=cases[4]['active_duration_tick']/TPS;interval=(duration-.03,duration+.005)
    for col,(name,title) in enumerate((('reference','Independent DC interval'),('before','V29 actual slow tail'),('after','Current selected end'))):
        x=col*W;draw.text((x+8,10),title,font=label,fill='white')
        samples=decoded[('T05',name)] if name!='reference' else np.zeros((N,2),np.float32)
        if name=='reference':samples[:math.ceil(duration*SR)]=10000/32768
        for ch,color in ((0,(65,220,145)),(1,(80,175,255))):wave_lane(draw,samples,x,125+ch*100,interval,color,ch,None,False)
        draw.text((x+8,275),f'{interval[0]:.6f}..{interval[1]:.6f} s',font=small,fill='white')
    tail.save(output/'slow-tail-comparison.png')
    final=frozen();assert final==freeze
    assert sha(Path(__file__))==provenance['generator_sha256']
    assert sha(font)==provenance['font']['sha256'] and sha(font_license)==provenance['font']['license_sha256']
    gif_durations=[]
    with Image.open(output/'comparison.gif') as im:
        for i in range(im.n_frames):im.seek(i);gif_durations.append(im.info.get('duration',0))
    record={'started_at_utc':began,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,
        'frozen_before':freeze,'frozen_after':final,'frozen_file_count':len(freeze),
        'case_count':len(cases),'cli_count':len(formal_calls),'cli_calls':formal_calls,'cases':cases,
        'supplemental_budget_cli_separately_counted':len(budget_calls),'supplemental_budget_expected_error_code':'AUDIO_TEMPO_CONTEXT_LIMIT',
        'new_main_video_frames':sum(c['video_frames_per_variant'] for c in cases),
        'old_video_frames_separately_counted':sum(c['video_frames_per_variant'] for c in cases),
        'new_audio_sample_frames':len(cases)*N,'old_audio_sample_frames_separately_counted':len(cases)*N,
        'new_controlled_interior_or_specific_gate_passed_cases':sum(c['metrics']['after']['interior_gate_passed'] for c in cases),
        'old_controlled_interior_or_specific_gate_failed_cases':sum(not c['metrics']['before']['interior_gate_passed'] for c in cases),
        'full_active_dc_failed_cases':[c['id'] for c in cases if c['metrics']['after']['active_gate_passed'] is False],
        'preview':{'width':W*3,'height':height,'mp4_probe':probe(output/'comparison.mp4'),
            'gif_encoded_frames':len(gif_durations),'gif_duration_ms':sum(gif_durations),'gif_frame_durations_ms':gif_durations,
            'zoom_half_open_seconds':list(zoom),'zoom_selected_from':'longest fixed-baseline zero run within [0.2,1.0) s',
            'reference_scope':'dotted DC amplitude and separate slow-tail reference; no independent video render'},
        'continuous_playback_accepted':False,'listening_accepted':False,'natural_audio_quality_accepted':False,
        'full_time_stretch_quality_accepted':False,'provenance':provenance,
        'public_files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}}
    save(output/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('case_count','cli_count','new_main_video_frames','new_audio_sample_frames',
        'new_controlled_interior_or_specific_gate_passed_cases','old_controlled_interior_or_specific_gate_failed_cases','full_active_dc_failed_cases','frozen_file_count')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','work','font','font-license'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.work.resolve(),args.font.resolve(),args.font_license.resolve())
