"""Real local CLI effects, native static-frame oracles, PCM and encoded PTS."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
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
from PIL import Image,ImageDraw
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
TPS,FPS,W,H=90000,12,320,180


def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rawsha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--installed',type=Path)
    args=parser.parse_args();work=args.work.resolve();evidence=args.evidence.resolve();assets=args.assets.resolve()
    assert not any(p.exists() for p in (work,evidence,assets))
    assert work.is_relative_to(ROOT/'product/.runtime') and evidence.is_relative_to(ROOT/'docs') and assets.is_relative_to(ROOT/'docs/assets')
    for p in (work,evidence,assets):p.mkdir(parents=True)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(__file__),
        'frozen_before':frozen(),'network':False,'virtualization':False,'native_windows':sys.platform=='win32',
        'new_model_inference':0,'continuous_playback_reviewed':False,'audio_reviewed':False,
        'natural_quality_accepted':False,'full_capcut_parity':False,'calls':[],'checks':[],'cases':[]}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save();assert ok,name
    def run(label,command,*,data=None,cwd=ROOT,cli=False):
        command=list(map(str,command));env=dict(os.environ);temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
        env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run(command,input=data,capture_output=True,cwd=cwd,env=env,timeout=900)
        (evidence/(label+'.stderr.log')).write_bytes(result.stderr)
        if not label.startswith(('decode-','oracle-')):(evidence/(label+'.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label':label,'command':command,'cli':cli,'exit_code':result.returncode,
            'stdout_bytes':len(result.stdout),'stdout_sha256':rawsha(result.stdout),'stderr_sha256':rawsha(result.stderr)});save()
        assert result.returncode==0,label+': '+result.stderr[-1600:].decode('utf8','replace')+result.stdout[-800:].decode('utf8','replace')
        return result.stdout
    if args.installed:prefix=[sys.executable,'-I','-S','-B','-X','utf8',args.installed.resolve()/'run.py']
    else:
        bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
        prefix=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,ROOT/'product/src']
    def cli(label,*argv):return json.loads(run(label,[*prefix,*argv],cli=True))
    exe,probe=shutil.which('ffmpeg'),shutil.which('ffprobe');assert exe and probe
    record.update(ffmpeg_sha256=sha(exe),ffprobe_sha256=sha(probe))
    def write(path,v):path.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def lossless(label,project,plan,path):
        command=plan['command'];idx=command.index('-filter_complex');inputs=command[1:idx]
        if '-progress' in inputs:
            pos=inputs.index('-progress');del inputs[pos:pos+2]
        run(label,[exe,*inputs,'-filter_complex',plan['filter_complex'],'-map','[vout]','-map','[aout]',
            '-fps_mode','passthrough','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_s16le',path],cwd=project)
    def pixels(label,path):return run('decode-'+label,[exe,'-v','error','-i',path,'-map','0:v:0','-f','rawvideo','-pix_fmt','rgba','pipe:1'])
    def points(values):return [{'at_tick':round(at*TPS),'value':v,'interpolation':'linear'} for at,v in values]
    def effect(kind,prop,params,values):return {'type':kind,'parameters':params,'keyframes':[{'property':prop,'keyframes':points(values)}]}
    def opaque_over(front,back):
        out=bytearray(len(back))
        for i in range(0,len(back),4):
            a=front[i+3]/255
            for c in range(3):out[i+c]=round(back[i+c]*(1-a)+front[i+c]*a)
            out[i+3]=255
        return bytes(out)
    try:
        back=Image.new('RGBA',(W,H));bp=back.load()
        for y in range(H):
            for x in range(W):
                v=40 if (x//16+y//16)%2 else 85;bp[x,y]=(v,v+8,v+18,255)
        back.save(assets/'background-original.png');bg=back.tobytes()
        source=Image.new('RGBA',(W,H),(0,255,0,255));draw=ImageDraw.Draw(source)
        for i,color in enumerate([(8,245,10,255),(25,215,35,255),(55,180,70,255)]):
            draw.rectangle((i*W//3,140,(i+1)*W//3,179),fill=color)
        draw.rounded_rectangle((60,27,260,130),radius=20,fill=(35,90,205,255))
        draw.ellipse((110,42,210,125),fill=(230,80,125,255))
        draw.text((80,14),'LOCAL / EDITABLE KEYFRAMES',fill=(255,245,225,255))
        draw.rectangle((0,0,15,139),fill=(240,155,40,128));draw.rectangle((305,0,319,139),fill=(50,135,210,0))
        source.save(assets/'foreground-original.png');raw=source.tobytes();size=len(raw)
        check('source-has-clear-partial-and-opaque-coverage',all(a in raw[3::4] for a in (0,128,255)))
        preview=Image.frombytes('RGBA',(W,H),opaque_over(raw,bg)).convert('RGB');preview.save(assets/'source-preview.png')
        pcm=b''.join(struct.pack('<hh',round(6000*math.sin(2*math.pi*440*i/48000)),
            round(5000*math.sin(2*math.pi*660*i/48000))) for i in range(96000))
        with wave.open(str(assets/'audio-original.wav'),'wb') as stream:
            stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(48000);stream.writeframes(pcm)
        project=work/'project';cli('init','project','init',project)
        rights=['--license-spdx','CC0-1.0','--license-url','local://v75-original/CC0-1.0',
            '--verification-status','verified','--permitted-use','commercial_ad','--creator','agent-video-kit',
            '--evidence','Original geometric PNG, checker background and synthesized stereo PCM generated by scripts/smoke_spatial_automation.py']
        for aid,name in [('foreground','foreground-original.png'),('background','background-original.png'),('sound','audio-original.wav')]:
            cli('ingest-'+aid,'media','ingest','--project',project,'--input',assets/name,'--asset-id',aid,
                '--source-url','local://v75-original/'+name,*rights)
        p=json.loads((project/'project.json').read_bytes());p['settings']['canvas']={'width':W,'height':H,'background':'#000000'}
        p['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':FPS,'den':1}};write(project/'project.json',p)
        def append(cid,aid,lane):return {'op':'append_clip','id':cid,'asset_id':aid,'track_id':lane,
            'timeline_start_tick':0,'duration_tick':2*TPS,'source_in_tick':0,'source_out_tick':2*TPS}
        timeline={'operations':[{'op':'add_track','track_id':'foreground-layer','kind':'video','order':10},
            append('background-clip','background','track_video_1'),append('foreground-clip','foreground','foreground-layer'),
            append('audio-clip','sound','track_audio_1')]}
        write(assets/'timeline-request.json',timeline);cli('compose','timeline','compose','--project',project,'--input',assets/'timeline-request.json')
        baseline=json.loads((project/'project.json').read_bytes())
        specs=[('blur-focus',effect('blur','radius',{},[(0,0),(1,12),(2,0)]),
                lambda t:f'gblur=sigma={12*(t if t<=1 else 2-t):.6f}:sigmaV={12*(t if t<=1 else 2-t):.6f}'),
            ('lens-ramp',effect('lens_correction','k1',{'k2':.08,'cx':.5,'cy':.5},[(0,-.45),(2,.45)]),
                lambda t:f'lenscorrection=k1={-.45+.45*t:.6f}:k2=0.080000:cx=0.500000:cy=0.500000'),
            ('key-ramp',effect('chroma_key','similarity',{'color':'0x00ff00','blend':.12},[(0,.00001),(2,.5)]),
                lambda t:f'colorkey=color=0x00ff00:similarity={.00001+(.5-.00001)*t/2:.6f}:blend=0.120000'),
            ('contrast-ramp',effect('color_contrast','red',{'green':.3,'blue':-.4,'red_weight':.7,'green_weight':.5,'blue_weight':.9,'preserve_luma':.4},[(0,-.8),(2,.8)]),
                lambda t:f'colorcontrast=rc={-.8+.8*t:.6f}:gm=0.300000:by=-0.400000:rcw=0.700000:gmw=0.500000:byw=0.900000:pl=0.400000')]
        comparisons=[];record['video_probes']={}
        for label,v,oracle in specs:
            p=copy.deepcopy(baseline);write(project/'project.json',p)
            request={'operations':[{'op':'update_clip','clip_id':'foreground-clip','patch':{'effects':[v]}}]}
            write(assets/(label+'-request.json'),request)
            cli(label+'-edit','timeline','compose','--project',project,'--input',assets/(label+'-request.json'))
            cli(label+'-validate','validate','--project',project)
            output=project/'renders'/(label+'.mp4');options=['render','--project',project,'--output',output,'--profile','custom','--width',W,'--height',H]
            original_project=(project/'project.json').read_bytes();plan=cli(label+'-plan',*options,'--dry-run')['data']['plan']
            check(label+'-dry-run-read-only',(project/'project.json').read_bytes()==original_project)
            result=cli(label+'-render',*options)['data'];shutil.copyfile(output,assets/(label+'.mp4'))
            shutil.copyfile(result['manifest'],evidence/(label+'-manifest.json'))
            manifest=json.loads(Path(result['manifest']).read_bytes());controls=[x for x in manifest['inputs'] if x.get('kind')=='effect-automation']
            check(label+'-actual-native-control',len(controls)==1 and controls[0]['effect']==v['type'] and controls[0]['sampled_frames']==24,metadata=controls)
            coverage=[x for x in manifest['inputs'] if x.get('kind')=='colorkey-alpha-coverage']
            if v['type']=='chroma_key':
                check(label+'-input-coverage-preserved',len(coverage)==1 and coverage[0]['input_coverage_preserved'],metadata=coverage)
            loss=assets/(label+'-lossless.mkv');lossless(label+'-lossless',project,plan,loss);actual=pixels(label,loss)
            audio=run('decode-'+label+'-pcm',[exe,'-v','error','-i',loss,'-map','0:a:0','-f','s16le','-acodec','pcm_s16le','pipe:1'])
            check(label+'-every-stereo-PCM-sample',audio==pcm,sample_frames=len(audio)//4,sha256=rawsha(audio))
            check(label+'-root-frame-count',len(actual)==24*size,frames=len(actual)//size)
            errors=[];expected_frames=[];alpha_equal=True
            for i in range(24):
                filtered=run('oracle-'+label+f'-{i:02}',[exe,'-v','error','-filter_threads','1','-f','rawvideo',
                    '-pixel_format','rgba','-video_size',f'{W}x{H}','-framerate',FPS,'-i','pipe:0',
                    '-vf',oracle(i/FPS),'-f','rawvideo','-pix_fmt','rgba','pipe:1'],data=raw)
                assert len(filtered)==size
                if v['type']=='chroma_key':
                    corrected=bytearray(filtered)
                    corrected[3::4]=bytes(round(a*b/255) for a,b in zip(raw[3::4],filtered[3::4]))
                    filtered=bytes(corrected)
                expected=opaque_over(filtered,bg);got=actual[i*size:(i+1)*size]
                errors.append(max(abs(a-b) for j,(a,b) in enumerate(zip(got,expected)) if j%4!=3))
                alpha_equal &= got[3::4]==expected[3::4];expected_frames.append(expected)
            check(label+'-independent-all-frame-static-oracle',max(errors)<=2,threshold_8bit=2,max_error_8bit=max(errors),per_frame_errors=errors,
                oracle='independent explicit native static options at each frame plus integer RGB source-over; no renderer or command parser')
            check(label+'-opaque-alpha',alpha_equal)
            if v['type']=='chroma_key':
                clear=[j for j in range(0,size,4) if raw[j+3]==0]
                check(label+'-originally-clear-pixels-stay-background',
                    all(actual[i*size+j:i*size+j+3]==bg[j:j+3] for i in range(24) for j in clear),pixels_per_frame=len(clear))
            expected=b''.join(expected_frames)
            record['cases'].append({'name':label,'effect':v,'frames':24,'fps':FPS,'max_rgb_error':max(errors),
                'alpha_byte_equal':alpha_equal,'PCM_byte_equal':audio==pcm,'actual_decoded_sha256':rawsha(actual),
                'independent_reference_sha256':rawsha(expected),'command_metadata':controls,'coverage_metadata':coverage});save()
            pages=[]
            for i in range(24):
                page=Image.new('RGB',(2*W,H+24),(18,25,38));page.paste(preview,(0,24))
                page.paste(Image.frombytes('RGBA',(W,H),actual[i*size:(i+1)*size]).convert('RGB'),(W,24))
                d=ImageDraw.Draw(page);d.text((8,7),'SOURCE ON CHECKER',fill='white');d.text((W+8,7),label.upper(),fill='white');pages.append(page)
            pages[0].save(assets/(label+'.gif'),save_all=True,append_images=pages[1:],duration=[80,80,90]*8,loop=0,optimize=False,disposal=2)
            pages[12].save(assets/(label+'-frame12.png'));comparisons.append(pages[12])
            for name in (label+'.mp4',label+'-lossless.mkv'):
                observed=json.loads(run('probe-'+name,[probe,'-v','error','-select_streams','v:0','-show_streams','-show_frames',
                    '-show_entries','stream=width,height,pix_fmt,avg_frame_rate:frame=pts_time','-of','json',assets/name]))
                times=[float(f['pts_time']) for f in observed['frames']]
                check(name+'-every-PTS',len(times)==24 and all(abs(t-i/FPS)<.0011 for i,t in enumerate(times)),frames=len(times),last_pts=times[-1])
                record['video_probes'][name]=observed
        package=work/'editable-project.zip';cli('package','convert','export','--project',project,'--output',package,'--target-format','package')
        target=work/'imported';cli('import','convert','import','--input',package,'--output',target)
        replay_plan=cli('replay-plan','render','--project',target,'--output',target/'renders/replay.mp4',
            '--profile','custom','--width',W,'--height',H,'--dry-run')['data']['plan']
        replay=work/'replay.mkv';lossless('replay-lossless',target,replay_plan,replay)
        check('package-last-case-decoded-byte-equal',pixels('replay',replay)==actual)
        run('source-preview',[exe,'-v','error','-loop','1','-framerate',FPS,'-i',assets/'source-preview.png',
            '-i',assets/'audio-original.wav','-t','2','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac',assets/'source-preview.mp4'])
        strip=Image.new('RGB',(2*W,(H+24)*4))
        for i,page in enumerate(comparisons):strip.paste(page,(0,i*(H+24)))
        strip.save(assets/'comparison.png')
        (assets/'LICENSE.txt').write_text('CC0-1.0: original generated geometric PNGs, checker background, synthesized stereo sine PCM and rendered derivatives. Generated by scripts/smoke_spatial_automation.py; no third-party media or model. Source-preview is a still-image video, not natural footage. MP4/GIF previews are lossy; numeric checks use FFV1 RGBA/PCM. Software licenses remain with their respective tools.\n',encoding='utf8',newline='\n')
        record['public_files']={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(assets.iterdir()) if p.is_file()}
        record.update(status='passed',cli_calls=sum(c['cli'] for c in record['calls']))
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({k:record[k] for k in ('status','cli_calls','frozen_equal')}))


if __name__=='__main__':main()
