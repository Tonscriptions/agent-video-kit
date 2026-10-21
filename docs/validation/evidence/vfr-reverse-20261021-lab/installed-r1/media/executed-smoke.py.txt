"""Public native CLI proof for reversed original display intervals; retain every failure."""
from __future__ import annotations
import argparse
from bisect import bisect_left
import copy
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave
from PIL import Image, ImageDraw
import smoke_cfr_boundaries as shared
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
TPS, W, H, RATE = shared.TPS, shared.W, shared.H, shared.RATE
COUNT, SIZE = shared.COUNT, shared.FRAME_BYTES

def sha(path):
    return 'sha256:'+hashlib.file_digest(Path(path).open('rb'), 'sha256').hexdigest()

def digest(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()

def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--installed',type=Path)
    args=parser.parse_args()
    work,evidence,assets=(getattr(args,n).resolve() for n in ('work','evidence','assets'))
    assert not any(p.exists() for p in (work,evidence,assets))
    assert work.is_relative_to(ROOT/'product/.runtime')
    assert evidence.is_relative_to(ROOT/'docs') and assets.is_relative_to(ROOT/'docs/assets')
    for p in (work,evidence,assets): p.mkdir(parents=True)
    for name,path in [('executed-smoke.py.txt',Path(__file__)),('executed-geometry-helper.py.txt',Path(shared.__file__))]:
        (evidence/name).write_bytes(path.read_bytes())
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(__file__),'geometry_helper_sha256':sha(shared.__file__),
        'frozen_before':frozen(),'calls':[],'checks':[],'cases':[],
        'native_windows':sys.platform=='win32','virtualization':False,'network':False,
        'reverse_audio_accepted':False,'nested_VFR_reverse_accepted':False,
        'long_clip_performance_accepted':False,'continuous_playback_reviewed':False,
        'audio_reviewed':False,'natural_quality_accepted':False,'full_capcut_parity':False}
    def save(): write(evidence/'verification.json',record)
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save();assert ok,name
    def run(label,command,*,data=None,cwd=ROOT,cli=False):
        command=list(map(str,command));env=dict(os.environ)
        temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
        env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
        value=subprocess.run(command,input=data,capture_output=True,cwd=cwd,env=env,timeout=900)
        (evidence/(label+'.stderr.log')).write_bytes(value.stderr)
        if not label.startswith('decode-'): (evidence/(label+'.stdout.log')).write_bytes(value.stdout)
        record['calls'].append({'label':label,'command':command,'exit_code':value.returncode,'cli':cli,
            'stdout_bytes':len(value.stdout),'stdout_sha256':digest(value.stdout),'stderr_sha256':digest(value.stderr)})
        save();assert value.returncode==0,label+': '+value.stderr[-1600:].decode('utf8','replace')+value.stdout[-900:].decode('utf8','replace')
        return value.stdout
    if args.installed:
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',args.installed.resolve()/'run.py']
    else:
        bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
        prefix=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,ROOT/'product/src']
    def cli(label,*argv): return json.loads(run(label,[*prefix,*argv],cli=True))
    exe,probe=shutil.which('ffmpeg'),shutil.which('ffprobe');assert exe and probe
    record.update(ffmpeg_sha256=sha(exe),ffprobe_sha256=sha(probe))
    def decode(label,path,audio=False):
        opts=['-map','0:a:0','-f','s16le','-acodec','pcm_s16le'] if audio else ['-map','0:v:0','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba']
        return run('decode-'+label,[exe,'-v','error','-i',path,*opts,'pipe:1'])
    def lossless(label,project,plan,path):
        command=plan['command'];inputs=command[1:command.index('-filter_complex')]
        if '-progress' in inputs:
            pos=inputs.index('-progress');del inputs[pos:pos+2]
        run(label,[exe,*inputs,'-filter_complex',plan['filter_complex'],'-map','[vout]','-map','[aout]',
            '-fps_mode','passthrough','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_s16le',path],cwd=project)
    try:
        images=[shared.source_frame(i) for i in range(55)]
        original=[i.tobytes() for i in images];composite=[shared.over_background(f) for f in original]
        blank=bytes(shared.BACKGROUND)*(W*H);source_pts={}
        for kind,count,irregular in [('cfr',55,None),('vfr',12,shared.IRREGULAR_MS)]:
            output=assets/('source-'+kind+'.nut')
            cmd=[exe,'-v','error','-filter_threads','1','-f','rawvideo','-pixel_format','rgba',
                '-video_size',f'{W}x{H}','-framerate','25','-i','pipe:0']
            if irregular:
                expression=str(irregular[-1])
                for i in range(len(irregular)-2,-1,-1): expression=f'if(eq(N,{i}),{irregular[i]},{expression})'
                cmd+=['-vf',"settb=1/1000,setpts='"+expression+"'",'-fps_mode','passthrough','-enc_time_base','filter']
            run('source-'+kind,[*cmd,'-c:v','ffv1','-pix_fmt','bgra',output],data=b''.join(original[:count]))
            result=json.loads(run('source-'+kind+'-pts',[probe,'-v','error','-select_streams','v:0','-show_frames','-show_streams',
                '-show_entries','frame=pts,duration:stream=time_base','-of','json',output]))
            tb=Fraction(result['streams'][0]['time_base']);pts=[int(f['pts'])*tb for f in result['frames']]
            expected=[Fraction(t,1000) for t in irregular] if irregular else [Fraction(i,25) for i in range(count)]
            check('source-'+kind+'-native-PTS',pts==expected,PTS=list(map(str,pts)))
            check('source-'+kind+'-RGBA',decode('source-'+kind,output)==b''.join(original[:count]))
            source_pts[kind]=pts
            run('source-'+kind+'-preview',[exe,'-v','error','-i',output,'-an','-c:v','libx264','-crf','18',
                '-pix_fmt','yuv420p','-fps_mode','passthrough','-movflags','+faststart',assets/('source-'+kind+'-preview.mp4')])
        run('source-offset',[exe,'-v','error','-i',assets/'source-vfr.nut','-output_ts_offset','5.117123',
            '-fps_mode','passthrough','-enc_time_base','filter','-c:v','ffv1','-pix_fmt','bgra',assets/'source-offset.nut'])
        # A valid asset can outlast its video stream. Keep the real 2.2-second
        # picture unchanged and mux three seconds of explicitly silent PCM.
        run('source-short-video-long-audio',[exe,'-v','error','-i',assets/'source-cfr.nut',
            '-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-map','0:v:0','-map','1:a:0',
            '-t','3','-c:v','copy','-c:a','pcm_s16le',assets/'source-short-video-long-audio.mkv'])
        source_pts['short']=source_pts['cfr']
        pcm=b''.join(struct.pack('<hh',round(5000*math.sin(2*math.pi*333*i/48000)),round(4000*math.sin(2*math.pi*509*i/48000))) for i in range(72000))
        with wave.open(str(assets/'independent-soundtrack.wav'),'wb') as stream:
            stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(48000);stream.writeframes(pcm)
        project=work/'project';cli('init','project','init',project)
        rights=['--license-spdx','CC0-1.0','--license-url','local://reverse-original/CC0-1.0',
            '--verification-status','verified','--permitted-use','commercial_ad','--creator','agent-video-kit',
            '--evidence','Original generated indexed geometry and synthesized sine PCM; scripts/smoke_reverse_video_clock.py']
        for aid,name in [('cfr','source-cfr.nut'),('vfr','source-vfr.nut'),('offset','source-offset.nut'),
                         ('short','source-short-video-long-audio.mkv'),('sound','independent-soundtrack.wav')]:
            cli('ingest-'+aid,'media','ingest','--project',project,'--input',assets/name,'--asset-id',aid,
                '--source-url','local://reverse-original/'+name,*rights)
        p=json.loads((project/'project.json').read_bytes());p['settings']['canvas']={'width':W,'height':H}
        p['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':30000,'den':1001}}
        write(project/'project.json',p)
        initial={'operations':[{'op':'append_clip','id':'picture','asset_id':'cfr','track_id':'track_video_1',
            'timeline_start_tick':2970,'duration_tick':TPS,'source_in_tick':0,'source_out_tick':TPS,'reverse':True},
            {'op':'append_clip','id':'soundtrack','asset_id':'sound','track_id':'track_audio_1','timeline_start_tick':0,
             'duration_tick':135000,'source_in_tick':0,'source_out_tick':135000}]}
        write(assets/'initial-request.json',initial)
        cli('initial-compose','timeline','compose','--project',project,'--input',assets/'initial-request.json')
        baseline=json.loads((project/'project.json').read_bytes())
        specs=[('reverse-vfr','vfr',0,TPS,Fraction(1),2970,False),
            ('fractional-cfr','cfr',10170,100170,Fraction(1),2970,False),
            ('fractional-vfr-speed','vfr',10170,100170,Fraction(3,2),2970,False),
            ('nonzero-demux-origin','offset',10170,100170,Fraction(1),2970,False),
            ('one-frame-partial-hold','vfr',10800,16200,Fraction(1),2970,False),
            ('one-tick-window','cfr',45000,45001,Fraction(1),3003,False),
            ('short-source-leading-gap','short',0,225000,Fraction(1),2970,False),
            ('nonlinear-vfr','vfr',10170,100170,Fraction(1),2970,True)]
        pages=[]
        for name,source,first,last,speed,start,curve in specs:
            write(project/'project.json',copy.deepcopy(baseline))
            duration=round(Fraction(last-first)/speed)
            patch={'asset_id':source,'source_in_tick':first,'source_out_tick':last,
                   'timeline_start_tick':start,'duration_tick':duration,'speed':float(speed),'reverse':True}
            if curve:
                duration=round(Fraction(str(math.log(3)))*(last-first));patch['duration_tick']=duration
                patch['speed_curve']={'keyframes':[{'at_tick':0,'speed':.5},{'at_tick':last-first,'speed':1.5}]}
            request={'operations':[{'op':'update_clip','clip_id':'picture','patch':patch},
                {'op':'set_sequence_duration','duration_tick':135000,'trim':True}]}
            write(assets/(name+'-request.json'),request)
            cli(name+'-compose','timeline','compose','--project',project,'--input',assets/(name+'-request.json'))
            cli(name+'-validate','validate','--project',project)
            output=project/'renders'/(name+'.mp4')
            argv=['render','--project',project,'--output',output,'--profile','custom','--width',W,'--height',H]
            before=(project/'project.json').read_bytes();plan=cli(name+'-plan',*argv,'--dry-run')['data']['plan']
            check(name+'-plan-read-only',before==(project/'project.json').read_bytes())
            result=cli(name+'-render',*argv)['data'];shutil.copyfile(output,assets/(name+'.mp4'))
            shutil.copyfile(result['manifest'],evidence/(name+'-manifest.json'))
            manifest=json.loads(Path(result['manifest']).read_bytes())
            clocks=[row['video_frame_clock'] for row in shared.walk(manifest['inputs']) if 'video_frame_clock' in row]
            check(name+'-actual-reverse-interval-protocol',any(c.get('reverse_frame_intervals',{}).get('protocol')=='reverse-native-video-intervals-v1' for c in clocks),clocks=clocks)
            loss=assets/(name+'-lossless.nut');lossless(name+'-lossless',project,plan,loss)
            actual=decode(name,loss);audio=decode(name+'-pcm',loss,audio=True)
            check(name+'-count',len(actual)==COUNT*SIZE,frames=len(actual)//SIZE)
            check(name+'-independent-forward-soundtrack-PCM',audio==pcm,frames=len(audio)//4,sha256=digest(audio))
            times=source_pts['vfr' if source=='offset' else source];native_end=times[-1]+Fraction(1,25)
            ids=[];expected_frames=[]
            for i in range(COUNT):
                now=Fraction(i)/RATE;index=-1;origin=Fraction(start,TPS)
                if origin<=now<Fraction(start+duration,TPS):
                    elapsed=now-origin;source_time=Fraction(last,TPS)-elapsed*speed
                    if curve:
                        with localcontext() as context:
                            context.prec=50;span=Decimal(last-first)/TPS;time=Decimal(elapsed.numerator)/elapsed.denominator
                            source_time=Decimal(last)/TPS-span*Decimal('.5')*((time/span).exp()-1)
                    if source_time<=native_end: index=bisect_left(times,source_time)-1
                ids.append(index);expected_frames.append(composite[index] if index>=0 else blank)
            expected=b''.join(expected_frames)
            error=max(abs(a-b) for i,(a,b) in enumerate(zip(actual,expected)) if i%4!=3)
            check(name+'-all-RGB-independent-intervals',error<=2,max_error=error,source_indices=ids)
            check(name+'-every-alpha-byte',actual[3::4]==expected[3::4])
            for suffix,path in [('lossless',loss),('mp4',assets/(name+'.mp4'))]:
                observed=json.loads(run(name+'-'+suffix+'-pts',[probe,'-v','error','-select_streams','v:0','-show_frames','-show_streams',
                    '-show_entries','frame=pts:stream=time_base','-of','json',path]))
                tb=Fraction(observed['streams'][0]['time_base']);pts=[int(f['pts'])*tb for f in observed['frames']]
                check(name+'-'+suffix+'-every-PTS',pts==[Fraction(i)/RATE for i in range(COUNT)])
            views=[Image.frombytes('RGBA',(W,H),actual[i*SIZE:(i+1)*SIZE]).convert('RGB') for i in range(COUNT)]
            delays=[(round(float(Fraction(i+1)/RATE)*100)-round(float(Fraction(i)/RATE)*100))*10 for i in range(COUNT)]
            views[0].save(assets/(name+'.gif'),save_all=True,append_images=views[1:],duration=delays,loop=0)
            page=Image.new('RGB',(W*2,H+24),'#101820');selected=next(i for i,v in enumerate(ids) if v>=0)
            page.paste(Image.frombytes('RGBA',(W,H),expected_frames[selected]).convert('RGB'),(0,24));page.paste(views[selected],(W,24))
            ImageDraw.Draw(page).text((8,5),f'{name} frame {selected}: expected | actual',fill='white')
            page.save(assets/(name+'-comparison.png'));pages.append(page)
            record['cases'].append({'name':name,'frames':COUNT,'source_indices':ids,'max_rgb_error':error,
                'actual_RGBA_sha256':digest(actual),'reference_RGBA_sha256':digest(expected),'PCM_equal':audio==pcm})
            save()
        package=work/'editable-reverse.zip';cli('package','convert','export','--project',project,'--output',package,'--target-format','package')
        destination=work/'imported';cli('import','convert','import','--input',package,'--output',destination)
        replay=cli('package-replay-plan','render','--project',destination,'--output',destination/'renders/replay.mp4',
            '--profile','custom','--width',W,'--height',H,'--dry-run')['data']['plan']
        loss=work/'package-replay.nut';lossless('package-replay',destination,replay,loss)
        check('package-isolated-root-rebuild-equal',decode('package-replay',loss)==actual and decode('package-replay-pcm',loss,audio=True)==pcm)
        strip=Image.new('RGB',(W*2,(H+24)*len(pages)))
        for i,page in enumerate(pages):strip.paste(page,(0,i*(H+24)))
        strip.save(assets/'comparison.png');record['status']='passed'
    except BaseException as error:
        record.update(status='failed',error={'type':type(error).__name__,'message':str(error)});raise
    finally:
        (assets/'LICENSE.txt').write_text('CC0-1.0: original indexed geometric RGBA frames, synthesized independent stereo sine PCM, and derivatives generated by scripts/smoke_reverse_video_clock.py with the retained geometry helper. No third-party media or model. MP4/GIF are viewing copies; numerical comparisons use original source PTS and FFV1 NUT. Reverse audio and continuous perceptual review are not accepted.\n',encoding='utf8')
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after']
        record['cli_calls']=sum(c['cli'] for c in record['calls'])
        record['public_files']={p.relative_to(assets).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(assets.rglob('*')) if p.is_file() and p.name!='files.json'}
        write(assets/'files.json',record['public_files']);save()
    assert record['frozen_equal'];print(json.dumps({k:record[k] for k in ('status','cli_calls','frozen_equal')}))

if __name__=='__main__':main()
