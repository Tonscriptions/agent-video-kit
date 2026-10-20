"""Repeat actual 1080p native filter throughput with frame and hash evidence."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from run_frozen_regression import frozen
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.selective_hsl import compile_filter
from ai_ad_editor.hsl_native import compile_native
from ai_ad_editor.render import _effect_keyframe_expr


def sha(p):return 'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();assert not output.exists() and output.is_relative_to(ROOT/'docs')
    output.parent.mkdir(parents=True,exist_ok=True);before=frozen();binary=Path(ffmpeg_path()).resolve()
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(__file__),
        'ffmpeg_sha256':sha(binary),'frozen_before':before,'frames_per_case':60,'repetitions':3,'width':1920,'height':1080,
        'fps':'30','filter_threads':1,'network':False,'virtualization':False,'cases':[],'calls':[],
        'scope':'FFmpeg testsrc2 to null with final RGBA, includes startup; no encoding, listening, natural-footage or interactive-preview acceptance',
        'interactive_preview_accepted':False,'full_capcut_parity':False}
    def save():output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    params={'red_hue':35,'orange_saturation':.3,'yellow_lightness':-.2,'green_hue':30,
            'cyan_saturation':-.4,'blue_hue':-25,'purple_lightness':.2,'magenta_saturation':.2,'intensity':.7}
    dynamic={'type':'selective_hsl','parameters':params,'keyframes':[{'property':'intensity','keyframes':[
        {'at_tick':0,'value':0,'interpolation':'ease_in_out'},{'at_tick':90000,'value':1,'interpolation':'linear'},
        {'at_tick':180000,'value':0,'interpolation':'linear'}]}]}
    settings=[('control',None),('red-hue',{'type':'selective_hsl','parameters':{'red_hue':45}}),
        ('eight-band',{'type':'selective_hsl','parameters':params}),('animated-intensity',dynamic)]
    save()
    try:
        for label,effect in settings:
            kernel='format=rgba';metadata=None
            if effect:
                callback=lambda names,default:_effect_keyframe_expr(effect,effect['parameters'],names,default,0,90000,clip={})
                kernel,metadata=compile_filter(effect,callback);kernel,metadata=compile_native(effect,callback,kernel,metadata)
                assert metadata['backend']=='ffmpeg:frei0r'
            samples=[]
            for repetition in range(3):
                command=[str(binary),'-hide_banner','-nostdin','-v','error','-filter_threads','1','-f','lavfi','-i',
                    'testsrc2=size=1920x1080:rate=30','-vf',kernel+',format=rgba','-frames:v','60','-an','-f','null','-',
                    '-progress','pipe:1','-nostats']
                started=time.perf_counter();result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=180)
                elapsed=time.perf_counter()-started;logs={}
                for stream in ('stdout','stderr'):
                    path=output.with_name(output.stem+'-'+label+'-'+str(repetition)+'.'+stream+'.log')
                    assert not path.exists();path.write_bytes(getattr(result,stream));logs[stream]={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)}
                record['calls'].append({'name':label,'repetition':repetition,'command':command,'exit_code':result.returncode,'logs':logs})
                save();assert result.returncode==0,label
                progress=result.stdout.decode('utf8','replace');frames=int([line[6:] for line in progress.splitlines() if line.startswith('frame=')][-1])
                assert frames==60 and 'progress=end' in progress
                samples.append({'frames':frames,'wall_seconds':elapsed,'seconds_per_frame':elapsed/frames,'frames_per_wall_second':frames/elapsed})
            record['cases'].append({'name':label,'kernel_metadata':metadata,'samples':samples,
                'minimum_observed_fps':min(x['frames_per_wall_second'] for x in samples),
                'all_repeats_meet_30fps':all(x['frames_per_wall_second']>=30 for x in samples)});save()
        record['status']='passed-execution-probe'
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=before==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({'status':record['status'],'cases':[{k:v for k,v in c.items() if k!='kernel_metadata'} for c in record['cases']]}))


if __name__=='__main__':main()
