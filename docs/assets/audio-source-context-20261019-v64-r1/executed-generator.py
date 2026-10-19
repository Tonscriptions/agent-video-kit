"""Real CLI audio-context deliveries, original controls and explicit failures."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import io

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'c4fa46096021ee2fb25548c31fbdf9bef1821ef5'
RATE, TPS = 48000, 90000


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def run(output, work, binary, installed=None):
    import numpy as np

    for path in (output, work):
        path.mkdir(parents=True, exist_ok=False)
    logs=output/'logs';logs.mkdir()
    shutil.copyfile(Path(__file__),output/'executed-generator.py')
    before=frozen();calls=[];writes=[];started=datetime.now(timezone.utc).isoformat()
    env=dict(os.environ,TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1')
    bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;sys.exit(main())'
    baseline=work/'baseline'
    archived=subprocess.run(['git','archive','--format=zip',BASELINE,'product/src'],cwd=ROOT,capture_output=True,check=True,timeout=120).stdout
    (work/'baseline-source.zip').write_bytes(archived)
    with zipfile.ZipFile(io.BytesIO(archived)) as archive:
        for name in archive.namelist():
            if name.endswith('/'):continue
            target=(baseline/name).resolve()
            if not target.is_relative_to(baseline):raise ValueError('archive escaped baseline')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(name))

    def command(args, kind, label, expected=0, raw=False):
        index=len(calls)+1;stem=f'{index:03d}-{label}'
        result=subprocess.run(list(map(str,args)),cwd=ROOT,env=env,capture_output=True,timeout=300)
        stdout=logs/(stem+('.stdout.gz' if raw else '.stdout.json'))
        stderr=logs/(stem+'.stderr.log')
        stdout.write_bytes(gzip.compress(result.stdout,mtime=0) if raw else result.stdout)
        stderr.write_bytes(result.stderr)
        row={'kind':kind,'label':label,'command':list(map(str,args)),'exit_code':result.returncode,'expected_exit_code':expected,
             'stdout':stdout.relative_to(output).as_posix(),'stderr':stderr.relative_to(output).as_posix(),
             'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr),'raw_compressed':raw,
             'decoded_stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),'decoded_stdout_bytes':len(result.stdout)}
        calls.append(row)
        if result.returncode!=expected:raise RuntimeError(label+': '+result.stderr.decode('utf-8','replace')[-4000:]+' '+result.stdout.decode('utf-8','replace')[-4000:])
        return result.stdout if raw else json.loads(result.stdout)

    def cli(args,label,old=False,expected=0):
        if installed and not old:
            prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']
        else:
            prefix=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,(baseline if old else ROOT)/'product/src']
        return command([*prefix,*args],'baseline-cli' if old else 'cli',label,expected)

    def ff(args,label):
        return command(['ffmpeg','-nostdin','-v','error',*args],'native',label,raw=True)

    def probe(path,label):
        return command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path],'native-probe',label)

    engine={'engine':'rubberband-r3-offline-v1','executable':str(binary),'sha256':sha(binary),
            'dependencies':[{'path':str(binary.with_name('sndfile.dll')),'sha256':sha(binary.with_name('sndfile.dll'))}],
            'license_path':str(binary.with_name('COPYING.txt')),'license_sha256':sha(binary.with_name('COPYING.txt')),
            'license_spdx':'GPL-2.0-or-later'}
    originals={'source.mp4':ROOT/'docs/assets/offline-audio-stretch-20261017/source.mp4',
               'stereo-tones.wav':ROOT/'docs/assets/offline-audio-stretch-20261017/stereo-tones.wav',
               'pulses.wav':ROOT/'docs/assets/offline-audio-stretch-20261017/pulses.wav',
               'antiphase.wav':ROOT/'docs/assets/audio-channel-modes-20261017/antiphase.wav'}
    for name,path in originals.items():shutil.copyfile(path,output/name)
    shutil.copyfile(binary.with_name('COPYING.txt'),output/'rubberband-license.txt')
    cases=[('C01','tiny-double-apart','stereo-tones.wav',.201,.205,.25,'apart',False,None),
           ('C02','tiny-double-together','stereo-tones.wav',.201,.205,.25,'together',False,None),
           ('C03','pulse-forward','pulses.wav',.201,.205,.25,'together',False,None),
           ('C04','pulse-reverse','pulses.wav',.201,.205,.25,'together',True,None),
           ('C05','nested-curve','stereo-tones.wav',.2,2.8,1.5,'apart',False,{'keyframes':[
               {'at_tick':0,'speed':.6,'interpolation':'bezier','control_points':[.15,.05,.85,.7]},
               {'at_tick':234000,'speed':2.8}]}),
           ('C06','antiphase-apart','antiphase.wav',.25,.375,.25,'apart',False,None),
           ('C07','antiphase-together','antiphase.wav',.25,.375,.25,'together',False,None),
           ('C08','source-head-edge','stereo-tones.wav',0.,.004,.25,'apart',False,None)]
    records=[]
    try:
        for case_id,name,audio,left,right,duration,mode,reverse,curve in cases:
            variants={}
            for label,context,old in [('zero',0,False),('context',64,False),*([('baseline',0,True)] if case_id=='C01' else [])]:
                tag=case_id+'-'+label;project=work/tag
                cli(['project','init',project],tag+'-init',old)
                for asset_id,filename in [('frames','source.mp4'),('sound_asset',audio)]:
                    cli(['media','ingest','--project',project,'--input',output/filename,'--asset-id',asset_id],tag+'-ingest-'+asset_id,old)
                p=project/'project.json';value=json.loads(p.read_bytes());previous=sha(p)
                value['settings']['canvas'].update(width=512,height=288)
                value['settings']['timebase']['display_fps']={'num':24,'den':1}
                value['settings']['audio_stretch']={**engine,'channel_mode':mode,**({} if old else {'source_context_ms':context})}
                save(p,value);writes.append({'path':str(p),'purpose':'authored project settings JSON input','before_sha256':previous,'after_sha256':sha(p)})
                ops=[{'op':'append_clip','sequence_id':'seq_main','track_id':'track_video_1','id':'picture','asset_id':'frames',
                      'timeline_start_tick':0,'source_in_tick':0,'source_out_tick':TPS,'duration_tick':TPS}]
                if curve:
                    ops += [{'op':'add_sequence','id':'child','duration_tick':3*TPS},
                            {'op':'add_track','sequence_id':'child','track_id':'child_audio','kind':'audio','order':1},
                            {'op':'append_clip','sequence_id':'child','track_id':'child_audio','id':'leaf','asset_id':'sound_asset',
                             'timeline_start_tick':0,'source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS},
                            {'op':'append_sequence_clip','sequence_id':'seq_main','track_id':'track_audio_1','id':'sound',
                             'nested_sequence_id':'child','timeline_start_tick':0,'source_in_tick':round(left*TPS),'source_out_tick':round(right*TPS),
                             'duration_tick':round(duration*TPS),'speed_curve':curve,'speed':(right-left)/duration,'reverse':reverse}]
                else:
                    ops.append({'op':'append_clip','sequence_id':'seq_main','track_id':'track_audio_1','id':'sound','asset_id':'sound_asset',
                                'timeline_start_tick':0,'source_in_tick':round(left*TPS),'source_out_tick':round(right*TPS),
                                'duration_tick':round(duration*TPS),'speed':(right-left)/duration,'reverse':reverse})
                request=work/(tag+'-compose.json');save(request,{'operations':ops})
                cli(['timeline','compose','--project',project,'--input',request],tag+'-compose',old)
                media=output/(tag+'.mkv')
                cli(['render','--project',project,'--output',media,'--profile','custom','--width','512','--height','288',
                     '--container','mkv','--audio-codec','pcm_f32le','--crf','0','--pixel-format','yuv444p'],tag+'-render',old)
                manifest=json.loads(media.with_suffix('.mkv.manifest.json').read_bytes())
                stretch=next(row['audio_stretch'] for row in manifest['inputs'] if row.get('audio_stretch'))
                pixels=ff(['-i',media,'-map','0:v:0','-an','-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],tag+'-rgb')
                raw=ff(['-i',media,'-map','0:a:0','-vn','-ar',str(RATE),'-ac','2','-f','f32le','pipe:1'],tag+'-pcm')
                pcm=np.frombuffer(raw,'<f4').reshape(-1,2)
                selected=pcm[:round(duration*RATE)]
                n=len(selected);segment=selected[n//8:n*7//8].astype(np.float64)
                power=np.abs(np.fft.rfft(segment*np.hanning(len(segment))[:,None],n=262144,axis=0))
                hz=np.fft.rfftfreq(262144,1/RATE);search=(hz>=100)&(hz<=1400)
                peaks=hz[search][np.argmax(power[search],axis=0)].tolist()
                expected=[400,400] if audio in ('pulses.wav','antiphase.wav') else [400,800]
                frame_count=len(pixels)//(512*288*3)
                if len(pixels)!=frame_count*512*288*3 or len(pcm)!=frame_count*2000 or not np.isfinite(pcm).all():
                    raise ValueError(tag+' native frame/sample/finite check failed')
                if np.any(pcm[len(selected):]):raise ValueError(tag+' context escaped the authored audio interval')
                derived=ff(['-i',stretch['output'],'-f','f32le','-ac','2','-ar',str(RATE),'pipe:1'],tag+'-derived-pcm')
                cache=np.frombuffer(derived,'<f4').reshape(-1,2)
                if reverse:cache=cache[::-1]
                if not np.array_equal(selected,cache):raise ValueError(tag+' encoded selection differs from actual derived PCM')
                expected_times=[i/24 for i in range(frame_count)]
                times=command(['ffprobe','-v','error','-select_streams','v:0','-show_entries','frame=best_effort_timestamp_time','-of','json',media],'native-probe',tag+'-pts')
                observed=[float(f['best_effort_timestamp_time']) for f in times['frames']]
                if len(observed)!=frame_count or max(abs(a-b) for a,b in zip(expected_times,observed))>.001:
                    raise ValueError(tag+' encoded PTS failed')
                cli(['quality','check','--project',project,'--input',media,'--width','512','--height','288','--require-audio'],tag+'-quality',old)
                cli(['validate','--project',project],tag+'-validate',old)
                cli(['policy','audit','--project',project],tag+'-policy',old)
                cli(['rights','check','--project',project],tag+'-rights',old,expected=7)
                variants[label]={'media':media.name,'frames':frame_count,'stereo_sample_frames':len(pcm),'selected_sample_frames':len(selected),
                                 'rgb_sha256':'sha256:'+hashlib.sha256(pixels).hexdigest(),'pcm_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),
                                 'peaks_hz':peaks,'expected_hz':expected,'pitch_gate_passed':all(abs(a-b)<=5 for a,b in zip(peaks,expected)),
                                 'maximum_abs_left_plus_right':float(np.max(np.abs(selected[:,0]+selected[:,1]))),
                                 'source_context':stretch.get('source_context'),'audio_stretch':stretch,'probe':probe(media,tag+'-probe')}
            if variants['zero']['rgb_sha256']!=variants['context']['rgb_sha256']:raise ValueError(case_id+' video changed with audio context')
            if 'baseline' in variants and any(variants['baseline'][k]!=variants['zero'][k] for k in ('rgb_sha256','pcm_sha256')):
                raise ValueError('zero context differs from actual fixed V62 baseline')
            records.append({'id':case_id,'name':name,'source_audio':audio,'source_window_seconds':[left,right],'duration_seconds':duration,
                            'channel_mode':mode,'reverse':reverse,'variants':variants})
            save(output/'in-progress.json',{'status':'running','records':records,'calls':calls,'frozen_before':before})
            print(json.dumps({'case':case_id,'pitch_zero':variants['zero']['pitch_gate_passed'],'pitch_context':variants['context']['pitch_gate_passed']},ensure_ascii=False),flush=True)
        result={'status':'passed_real_cli_invariants_quality_failures_retained','started_at_utc':started,
                'finished_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,'frozen_after':frozen(),'frozen_equal':before==frozen(),
                'generator_sha256':sha(output/'executed-generator.py'),'baseline_ref':BASELINE,'baseline_zip_sha256':sha(work/'baseline-source.zip'),
                'records':records,'calls':calls,'authored_json_writes':writes,'installed_launcher':str(installed) if installed else None,
                'source_provenance':'same original CC0 procedural source and audio from V25/V26/V27; no new natural scene',
                'new_model_inference':0,'network':'disabled','virtualization':False,'browser_started':False,
                'natural_quality_accepted':False,'continuous_playback_reviewed':False,'audio_listening_reviewed':False,'full_capcut_parity':False}
        if not result['frozen_equal']:raise ValueError('product changed during actual media verification')
        save(output/'verification.json',result)
        save(output/'provenance.json',{'source_files':[{'path':n,'sha256':sha(output/n),'source':str(p.relative_to(ROOT))} for n,p in originals.items()],
             'source_license':'CC0-1.0 original procedural fixtures','model_inference':False,'commercial_publish_gate':'unverified records rejected exit 7',
             'continuous_listening':False,'generator_sha256':sha(output/'executed-generator.py')})
        print(json.dumps({'status':result['status'],'cases':len(records),'cli_calls':sum(x['kind']=='cli' for x in calls),'baseline_cli_calls':sum(x['kind']=='baseline-cli' for x in calls)},ensure_ascii=False),flush=True)
    except Exception as exc:
        save(output/'failure.json',{'status':'failed','error':type(exc).__name__+': '+str(exc),'records':records,'calls':calls,'frozen_before':before,'frozen_after':frozen()})
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output','work','rubberband'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--installed',type=Path)
    a=p.parse_args();run(a.output.resolve(),a.work.resolve(),a.rubberband.resolve(strict=True),a.installed.resolve(strict=True) if a.installed else None)
