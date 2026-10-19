"""Independently decode deliveries and rerun native R3 from original source PCM."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
RATE=48000
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def read(p):return json.loads(p.read_bytes())

def run(media,output,work,installed):
    for p in (output,work):p.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(Path(__file__),output/'executed-audit.py');(output/'logs').mkdir()
    before=frozen();recipe=read(media/'verification.json');calls=[];checks=[];files={}
    if not recipe['frozen_equal'] or recipe['frozen_before']!=before:raise ValueError('different frozen media')
    env=dict(os.environ,TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1')
    def command(args,label,kind='native',raw=True):
        p=subprocess.run(list(map(str,args)),cwd=ROOT,env=env,capture_output=True,timeout=300)
        stem=f'{len(calls)+1:03d}-{label}';a=output/'logs'/(stem+('.stdout.gz' if raw else '.stdout.json'));b=output/'logs'/(stem+'.stderr.log')
        a.write_bytes(gzip.compress(p.stdout,mtime=0) if raw else p.stdout);b.write_bytes(p.stderr)
        calls.append({'label':label,'kind':kind,'command':list(map(str,args)),'exit_code':p.returncode,
            'stdout':a.relative_to(output).as_posix(),'stderr':b.relative_to(output).as_posix(),'stdout_sha256':sha(a),'stderr_sha256':sha(b),
            'compressed':raw,'decoded_stdout_sha256':digest(p.stdout),'decoded_stdout_bytes':len(p.stdout)})
        if p.returncode:raise ValueError(label+': '+p.stdout.decode('utf-8','replace')[-2000:]+p.stderr.decode('utf-8','replace')[-2000:])
        return p.stdout
    def ff(args,label):return command(['ffmpeg','-nostdin','-v','error',*args],label)
    def pcm(p,label):return np.frombuffer(ff(['-i',p,'-map','0:a:0','-vn','-ac','2','-ar',str(RATE),'-f','f32le','pipe:1'],label),'<f4').reshape(-1,2)
    def bind(p):files[p.relative_to(ROOT).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
    def peaks(a):
        n=len(a);segment=a[n//8:n*7//8].astype(np.float64);freq=np.fft.rfftfreq(262144,1/RATE)
        values=np.abs(np.fft.rfft(segment*np.hanning(len(segment))[:,None],n=262144,axis=0));band=(freq>=100)&(freq<=1400)
        return freq[band][np.argmax(values[band],axis=0)].tolist()
    try:
        for case in recipe['records']:
            decoded={};rgb={};source=media/case['source_audio'];full=pcm(source,case['id']+'-original-full')
            for variant,info in case['variants'].items():
                tag=case['id']+'-'+variant;path=media/info['media'];bind(path);bind(path.with_suffix('.mkv.manifest.json'))
                a=pcm(path,tag+'-encoded');picture=ff(['-i',path,'-map','0:v:0','-an','-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],tag+'-rgb')
                frame_count=len(picture)//(512*288*3);selected=round(case['duration_seconds']*RATE)
                if len(a)!=frame_count*2000 or len(picture)!=frame_count*512*288*3 or not np.isfinite(a).all():raise ValueError(tag+' invalid native output')
                if np.any(a[selected:]):raise ValueError(tag+' audio outside author interval')
                observed=json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_entries','frame=best_effort_timestamp_time','-of','json',path],tag+'-pts',raw=False))['frames']
                pts=[float(x['best_effort_timestamp_time']) for x in observed]
                if len(pts)!=frame_count or max(abs(t-i/24) for i,t in enumerate(pts))>.001:raise ValueError(tag+' CFR PTS mismatch')
                if digest(a.tobytes())!=info['pcm_sha256'] or digest(picture)!=info['rgb_sha256']:raise ValueError(tag+' recipe hash mismatch')
                f=peaks(a[:selected]);pitch=all(abs(x-y)<=5 for x,y in zip(f,info['expected_hz']))
                if f!=info['peaks_hz'] or pitch!=info['pitch_gate_passed']:raise ValueError(tag+' spectral result changed')
                decoded[variant]=a;rgb[variant]=picture
            if rgb['zero']!=rgb['context']:raise ValueError('context changed pictures')
            if 'baseline' in decoded and (not np.array_equal(decoded['zero'],decoded['baseline']) or rgb['zero']!=rgb['baseline']):raise ValueError('actual fixed baseline differs')
            info=case['variants']['context'];job=info['audio_stretch'];c=job['source_context'];anchors=job['time_map']
            start,end=round(case['source_window_seconds'][0]*RATE),round(case['source_window_seconds'][1]*RATE)
            head=min(64*RATE//1000,start);tail=min(64*RATE//1000,len(full)-end)
            first=Fraction(anchors[1][1]-anchors[0][1],anchors[1][0]-anchors[0][0]);last=Fraction(anchors[-1][1]-anchors[-2][1],anchors[-1][0]-anchors[-2][0])
            ho,to=round(head*first),round(tail*last);selected_frames=round(case['duration_seconds']*RATE)
            expected=([(0,0)] if head else [])+[(a+head,b+ho) for a,b in anchors]+([(end-start+head+tail,selected_frames+ho+to)] if tail else [])
            if c['time_map']!=[list(x) for x in expected] or c['output_crop']!=[ho,ho+selected_frames] or c['decode_start_sample']!=start-head or c['decode_end_sample']!=end+tail:raise ValueError('rational context mapping/crop mismatch')
            d=work/case['id'];d.mkdir();inp=d/'input.wav';out=d/'output.wav';mapping=output/(case['id']+'-native-map.txt')
            ff(['-y','-i',source,'-map','0:a:0','-vn','-af',f'aresample={RATE},atrim=start_sample={start-head}:end_sample={end+tail},asetpts=N/SR/TB','-c:a','pcm_f32le',inp],case['id']+'-fresh-input')
            native_input=pcm(inp,case['id']+'-fresh-input-pcm')
            if not np.array_equal(native_input,full[start-head:end+tail]):raise ValueError('fresh native input not actual original handles')
            interior=[(a,b) for a,b in expected if 0<a<c['source_frames'] and 0<b<c['target_frames']]
            if all(a*c['target_frames']==b*c['source_frames'] for a,b in interior):interior=[]
            mapping.write_text(''.join(f'{a} {b}\n' for a,b in interior),encoding='ascii',newline='\n')
            command([job['engine']['executable'],'-3','--no-threads',*(['--centre-focus'] if case['channel_mode']=='together' else []),'-q',
                     '-t',format(c['target_frames']/c['source_frames'],'.17g'),*(['--timemap',mapping] if interior else []),inp,out],case['id']+'-fresh-r3')
            raw=pcm(out,case['id']+'-fresh-full-output')
            if len(raw)!=c['target_frames']:raise ValueError('fresh R3 native length mismatch')
            selected=raw[ho:ho+selected_frames]
            if case['reverse']:selected=selected[::-1]
            diff=float(np.max(np.abs(selected-decoded['context'][:selected_frames])))
            if diff!=0:raise ValueError('fresh native crop differs from actual encoded selected PCM')
            anti=float(np.max(np.abs(decoded['context'][:selected_frames].sum(axis=1))))
            checks.append({'id':case['id'],'fresh_source_handles_equal_original':True,'fresh_crop_pcm_max_error':diff,
                'head_source_frames':head,'tail_source_frames':tail,'output_crop':[ho,ho+selected_frames],
                'context_time_map_anchors':len(expected),'frames_each':info['frames'],'selected_sample_frames':selected_frames,
                'pitch_hz':peaks(decoded['context'][:selected_frames]),'pitch_passed':info['pitch_gate_passed'],
                'antiphase_max_abs_left_plus_right':anti if case['source_audio']=='antiphase.wav' else None,
                'antiphase_exact_cancellation_passed':anti==0 if case['source_audio']=='antiphase.wav' else None,
                'input_wav_sha256':sha(inp),'fresh_expanded_output_wav_sha256':sha(out)})
        byid={r['id']:r for r in checks}
        if not all(byid[i]['pitch_passed'] for i in ('C01','C03','C04','C05','C06','C07','C08')) or byid['C02']['pitch_passed']:raise ValueError('expected positive/negative pitch gates changed')
        if byid['C06']['antiphase_exact_cancellation_passed'] or not byid['C07']['antiphase_exact_cancellation_passed']:raise ValueError('expected phase failure/control not retained')
        # Real isolated package roundtrip of the authored nested curve setting.
        launcher=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']
        project=Path(recipe['records'][4]['variants']['context']['audio_stretch']['output']).parents[2]
        archive=output/'C05-context-project.zip';restored=work/'restored'
        for label,args in [('package-export',['convert','export','--project',project,'--target-format','package','--output',archive]),
                           ('package-import',['convert','import','--input',archive,'--output',restored]),
                           ('package-validate',['validate','--project',restored]),('package-policy',['policy','audit','--project',restored])]:
            command([*launcher,*args],label,'isolated-cli',raw=False)
        if read(restored/'project.json')['settings']['audio_stretch']['source_context_ms']!=64:raise ValueError('package lost explicit source context')
        result=restored/'outputs/roundtrip.mkv'
        command([*launcher,'render','--project',restored,'--output',result,'--profile','custom','--width','512','--height','288',
                 '--container','mkv','--audio-codec','pcm_f32le','--crf','0','--pixel-format','yuv444p'],'package-render','isolated-cli',raw=False)
        reference=recipe['records'][4]['variants']['context'];sound=pcm(result,'package-pcm');picture=ff(['-i',result,'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],'package-rgb')
        if digest(sound.tobytes())!=reference['pcm_sha256'] or digest(picture)!=reference['rgb_sha256']:raise ValueError('package restored PCM/pictures differ')
        shutil.copyfile(result,output/'C05-roundtrip.mkv');shutil.copyfile(result.with_suffix('.mkv.manifest.json'),output/'C05-roundtrip.mkv.manifest.json')
        for path in (archive,output/'C05-roundtrip.mkv',output/'C05-roundtrip.mkv.manifest.json',media/'verification.json',media/'provenance.json'):bind(path)
        if before!=frozen():raise ValueError('product changed during audit')
        record={'status':'passed_independent_source_context_media_negative_quality_retained','checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'frozen_before':before,'frozen_after':frozen(),'frozen_equal':True,'checks':checks,'calls':calls,'files':files,
            'current_final_frames':408,'current_stereo_sample_frames':816000,'baseline_frames_separate':24,'baseline_stereo_sample_frames_separate':48000,
            'fresh_r3_calls_separate':8,'package_isolated_cli_calls_separate':5,'package_frames_separate':36,'package_stereo_sample_frames_separate':72000,
            'natural_quality_accepted':False,'audio_listened':False,'continuous_playback':False,'full_capcut_parity':False,
            'generator_sha256':sha(output/'executed-audit.py')}
        save(output/'verification.json',record)
        print(json.dumps({k:record[k] for k in ('status','current_final_frames','current_stereo_sample_frames','fresh_r3_calls_separate','package_isolated_cli_calls_separate')}))
    except BaseException as exc:
        save(output/'failure.json',{'status':'failed','error':repr(exc),'calls':calls,'checks':checks,'frozen_before':before,'frozen_after':frozen()});raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('media','output','work','installed'):p.add_argument('--'+name,type=Path,required=True)
    run(**{k:v.resolve() for k,v in vars(p.parse_args()).items()})
