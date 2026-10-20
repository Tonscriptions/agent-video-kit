"""Measure complete 1080p CLI renders separately from the native filter probe."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();work=args.work.resolve();evidence=args.evidence.resolve();assets=args.assets.resolve()
    assert not any(p.exists() for p in (work,evidence,assets))
    assert work.is_relative_to(ROOT/'product/.runtime') and evidence.is_relative_to(ROOT/'docs') and assets.is_relative_to(ROOT/'docs/assets')
    for p in (work,evidence,assets):p.mkdir(parents=True)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(__file__),
        'frozen_before':frozen(),'calls':[],'cases':[],'network':False,'virtualization':False,
        'width':1920,'height':1080,'frames_per_render':60,'fps':30,'repetitions':3,
        'concurrent_load':'full-r2 native regression was running during these measurements',
        'scope':'complete source CLI launch, project validation, decode, HSL, composition, libx264 medium CRF18 yuv420p, AAC and manifest; no GUI or interactive preview',
        'source_scope':'original generated FFmpeg moving testsrc2 and sine, not natural footage',
        'continuous_playback_reviewed':False,'audio_reviewed':False,'natural_quality_accepted':False,'full_capcut_parity':False}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def run(label,command,cli=False):
        command=list(map(str,command));env=dict(os.environ);temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
        env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1',AI_AD_EDITOR_HSL_BACKEND='native')
        start=time.perf_counter();result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=600);elapsed=time.perf_counter()-start
        for stream in ('stdout','stderr'):(evidence/(label+'.'+stream+'.log')).write_bytes(getattr(result,stream))
        record['calls'].append({'label':label,'command':command,'cli':cli,'exit_code':result.returncode,'wall_seconds':elapsed,
            'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':'sha256:'+hashlib.sha256(result.stderr).hexdigest()});save()
        assert result.returncode==0,label+': '+result.stderr[-1200:].decode('utf8','replace')+result.stdout[-800:].decode('utf8','replace')
        return result.stdout,elapsed
    bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    prefix=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,ROOT/'product/src']
    def cli(label,*argv):
        raw,elapsed=run(label,[*prefix,*argv],cli=True);return json.loads(raw),elapsed
    try:
        exe=shutil.which('ffmpeg');probe=shutil.which('ffprobe');assert exe and probe
        record.update(ffmpeg_sha256=sha(exe),ffprobe_sha256=sha(probe))
        source=assets/'source-testsrc2.mp4'
        run('generate-source',[exe,'-v','error','-f','lavfi','-i','testsrc2=size=1920x1080:rate=30',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2','-c:v','libx264','-preset','medium','-crf','18',
            '-pix_fmt','yuv420p','-c:a','aac','-ac','2',source])
        project=work/'project';cli('init','project','init',project)
        cli('ingest','media','ingest','--project',project,'--input',source,'--asset-id','pattern',
            '--license-spdx','CC0-1.0','--license-url','local://v77-cli-original/CC0-1.0','--verification-status','verified',
            '--permitted-use','commercial_ad','--creator','agent-video-kit','--source-url','local://v77-cli-original/source-testsrc2.mp4',
            '--evidence','Original FFmpeg testsrc2 and generated sine from scripts/probe_native_hsl_cli.py; no third-party media')
        data=json.loads((project/'project.json').read_bytes());data['settings']['canvas']={'width':1920,'height':1080,'background':'#000000'}
        data['settings']['timebase']={'ticks_per_second':90000,'display_fps':{'num':30,'den':1}}
        write(project/'project.json',data)
        request={'operations':[{'op':'append_clip','id':cid,'asset_id':'pattern','track_id':lane,
            'timeline_start_tick':0,'duration_tick':180000,'source_in_tick':0,'source_out_tick':180000}
            for cid,lane in [('picture','track_video_1'),('sound','track_audio_1')]]}
        write(assets/'timeline-request.json',request);cli('compose','timeline','compose','--project',project,'--input',assets/'timeline-request.json')
        baseline=json.loads((project/'project.json').read_bytes())
        params={'red_hue':35,'orange_saturation':.3,'yellow_lightness':-.2,'green_hue':30,'cyan_saturation':-.4,
            'blue_hue':-25,'purple_lightness':.2,'magenta_saturation':.2,'intensity':.7}
        effects=[('control',[]),('eight-band',[{'type':'selective_hsl','parameters':params}]),
            ('animated-intensity',[{'type':'selective_hsl','parameters':params,'keyframes':[{'property':'intensity','keyframes':[
                {'at_tick':0,'value':0,'interpolation':'ease_in_out'},{'at_tick':90000,'value':1,'interpolation':'linear'},
                {'at_tick':180000,'value':0,'interpolation':'linear'}]}]}])]
        for label,effect in effects:
            write(project/'project.json',copy.deepcopy(baseline))
            edit={'operations':[{'op':'update_clip','clip_id':'picture','patch':{'effects':effect}}]}
            write(assets/(label+'-request.json'),edit);cli(label+'-edit','timeline','compose','--project',project,'--input',assets/(label+'-request.json'))
            samples=[];kernels=None
            for i in range(3):
                output=project/'renders'/(label+'-'+str(i)+'.mp4')
                result,elapsed=cli(label+'-render-'+str(i),'render','--project',project,'--output',output,'--profile','custom','--width','1920','--height','1080')
                manifest=json.loads(Path(result['data']['manifest']).read_bytes());kernels=[x for x in manifest['inputs'] if x.get('kind')=='selective-hsl']
                assert (not kernels) if label=='control' else (len(kernels)==1 and kernels[0]['backend']=='ffmpeg:frei0r' and kernels[0]['sampled_frames']==60)
                shutil.copyfile(result['data']['manifest'],evidence/(label+'-'+str(i)+'-manifest.json'))
                observed=json.loads(run(label+'-probe-'+str(i),[probe,'-v','error','-select_streams','v:0','-show_streams','-show_frames',
                    '-show_entries','stream=width,height,avg_frame_rate:frame=pts_time','-of','json',output])[0])
                times=[float(f['pts_time']) for f in observed['frames']]
                assert len(times)==60 and all(abs(t-j/30)<.000002 for j,t in enumerate(times))
                assert observed['streams'][0]['width']==1920 and observed['streams'][0]['height']==1080
                samples.append({'wall_seconds':elapsed,'frames':60,'frames_per_wall_second':60/elapsed,'every_PTS_checked':True,
                    'video_sha256':sha(output)})
                if i==0:shutil.copyfile(output,assets/(label+'.mp4'))
            record['cases'].append({'name':label,'samples':samples,'kernel_metadata':kernels,
                'minimum_observed_fps':min(x['frames_per_wall_second'] for x in samples),
                'all_repeats_meet_30fps':all(x['frames_per_wall_second']>=30 for x in samples)});save()
        (assets/'LICENSE.txt').write_text('CC0-1.0: original generated FFmpeg testsrc2 and sine and rendered derivatives, generated by scripts/probe_native_hsl_cli.py. This moving test pattern is not natural footage. Software licenses remain with their respective tools.\n',encoding='utf8',newline='\n')
        record['public_files']={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(assets.iterdir()) if p.is_file()}
        record.update(status='passed-execution-probe',cli_calls=sum(c['cli'] for c in record['calls']))
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({'status':record['status'],'cases':[{k:v for k,v in c.items() if k!='kernel_metadata'} for c in record['cases']]}))

if __name__=='__main__':main()
