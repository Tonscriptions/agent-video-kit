"""Original CC0 media, real CLI edits and independent blend/PCM/PTS checks."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
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
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
TPS,FPS,W,H=90000,10,320,180


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
        'new_model_inference':0,'continuous_playback_reviewed':False,'audio_reviewed':False,'full_capcut_parity':False,
        'calls':[],'checks':[],'cases':[]}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save();assert ok,name
    def run(label,command,*,data=None,cwd=ROOT,cli=False):
        command=list(map(str,command));env=dict(os.environ);temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
        env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run(command,input=data,capture_output=True,cwd=cwd,env=env,timeout=900)
        (evidence/(label+'.stderr.log')).write_bytes(result.stderr)
        if not label.startswith('decode-'):(evidence/(label+'.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label':label,'command':command,'cli':cli,'exit_code':result.returncode,
            'stdout_bytes':len(result.stdout),'stdout_sha256':rawsha(result.stdout),'stderr_sha256':rawsha(result.stderr)});save()
        assert result.returncode==0,label+': '+result.stderr[-1600:].decode('utf8','replace')+result.stdout[-1000:].decode('utf8','replace')
        return result.stdout
    if args.installed:prefix=[sys.executable,'-I','-S','-B','-X','utf8',args.installed.resolve()/'run.py']
    else:
        bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
        prefix=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,ROOT/'product/src']
    def cli(label,*argv):return json.loads(run(label,[*prefix,*argv],cli=True))
    exe,probe=shutil.which('ffmpeg'),shutil.which('ffprobe');assert exe and probe
    record.update(ffmpeg_sha256=sha(exe),ffprobe_sha256=sha(probe))
    def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def lossless(label,project,plan,path):
        command=plan['command'];idx=command.index('-filter_complex');inputs=command[1:idx]
        if '-progress' in inputs:
            pos=inputs.index('-progress');del inputs[pos:pos+2]
        run(label,[exe,*inputs,'-filter_complex',plan['filter_complex'],'-map','[vout]','-map','[aout]',
            '-fps_mode','passthrough','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_s16le',path],cwd=project)
    def pixels(label,path):return run('decode-'+label,[exe,'-v','error','-i',path,'-map','0:v:0','-f','rawvideo','-pix_fmt','rgba','pipe:1'])
    try:
        background=Image.new('RGB',(W,H));bp=background.load()
        for y in range(H):
            for x in range(W):bp[x,y]=(35+x*50//W,65+y*70//H,135+(x//20+y//20)%2*35)
        background.save(assets/'background-original.png')
        frames=[]
        for i in range(21):
            im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im)
            d.rounded_rectangle((30,22,290,158),radius=16,fill=(205,125,65,160))
            x=45+round(150*(i%20)/19);d.rectangle((x,60,x+40,120),fill=(65,195,150,255))
            d.text((45,35),'EDITABLE BLEND / LOCAL CLI',fill=(235,235,220,220))
            d.rectangle((45,136,275,145),fill=(55,105,210,128));frames.append(im)
        frames[-1]=frames[-2].copy()
        source=assets/'foreground-original.nut'
        run('encode-source',[exe,'-v','error','-f','rawvideo','-pixel_format','rgba','-video_size',f'{W}x{H}',
            '-framerate',FPS,'-i','pipe:0','-c:v','rawvideo','-pix_fmt','rgba','-fflags','+bitexact',source],data=b''.join(im.tobytes() for im in frames))
        frames[0].save(assets/'foreground-still-original.png')
        pcm=b''.join(struct.pack('<hh',round(7000*math.sin(2*math.pi*440*i/48000)),
            round(6000*math.sin(2*math.pi*660*i/48000))) for i in range(144000))
        with wave.open(str(assets/'audio-original.wav'),'wb') as stream:
            stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(48000);stream.writeframes(pcm)
        record['source_endpoint_guard']={'source_frames':21,'last_pts_seconds':2.,'authored_half_open_frames':20,
            'reason':'explicit duplicate endpoint permits the complete 0..2s source range in NUT'}
        check('explicit-endpoint-and-expected-source-size',source.is_file() and len(frames)==21 and frames[-1].tobytes()==frames[-2].tobytes())
        project=work/'project';cli('init','project','init',project)
        rights=['--license-spdx','CC0-1.0','--license-url','local://v74-original-generated/CC0-1.0',
            '--verification-status','verified','--permitted-use','commercial_ad','--creator','agent-video-kit',
            '--evidence','Original geometric RGBA frames, checker background and synthesized two-tone PCM generated by scripts/smoke_blend_retime.py']
        for asset,name in [('foreground','foreground-original.nut'),('background','background-original.png'),
                           ('still','foreground-still-original.png'),('sound','audio-original.wav')]:
            cli('ingest-'+asset,'media','ingest','--project',project,'--input',assets/name,'--asset-id',asset,
                '--source-url','local://v74-original/'+name,*rights)
        p=json.loads((project/'project.json').read_bytes());p['settings']['canvas']={'width':W,'height':H,'background':'#000000'}
        p['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':FPS,'den':1}}
        write(project/'project.json',p)
        keys=[{'at_tick':0,'value':.1,'interpolation':'linear'},{'at_tick':2*TPS,'value':.9,'interpolation':'linear'}]
        def append(cid,asset,lane,start,duration,**extra):return {'op':'append_clip','id':cid,'asset_id':asset,'track_id':lane,
            'timeline_start_tick':start,'duration_tick':duration,'source_in_tick':0,'source_out_tick':duration,**extra}
        timeline={'operations':[{'op':'add_track','track_id':'blend-layer','kind':'video','order':10},
            append('background-clip','background','track_video_1',0,3*TPS),
            append('foreground-clip','foreground','blend-layer',TPS//2,2*TPS,blend={'mode':'normal','opacity':.25},
                   keyframes=[{'property':'blend.opacity','keyframes':keys}]),
            append('audio-clip','sound','track_audio_1',0,3*TPS)]}
        write(assets/'timeline-request.json',timeline);cli('compose','timeline','compose','--project',project,'--input',assets/'timeline-request.json')
        baseline=json.loads((project/'project.json').read_bytes());sid=baseline['sequences'][0]['id']
        specs=[('normal-fast','normal',{'speed':2},False),
            ('screen-reverse-hold','screen',{'speed':2,'reverse':True,'freeze':{'at_tick':TPS//2,'duration_tick':TPS*3//10}},False),
            ('multiply-curve','multiply',{'speed_curve':{'keyframes':[{'at_tick':0,'speed':1,'interpolation':'linear'},
                {'at_tick':2*TPS,'speed':3,'interpolation':'linear'}]}},True)]
        original=pixels('original',source);check('source-native-RGBA-identical',original==b''.join(im.tobytes() for im in frames))
        bg=background.convert('RGBA').tobytes();size=W*H*4;comparisons=[];record['video_probes']={}
        for label,mode,transform,still in specs:
            p=copy.deepcopy(baseline);foreground=next(c for t in p['sequences'][0]['tracks'] for c in t['clips'] if c['id']=='foreground-clip')
            foreground['blend']['mode']=mode
            if still:foreground['asset_id']='still'
            write(project/'project.json',p)
            q={'action':'retime','clip_ids':['foreground-clip'],'transform':transform};write(assets/(label+'-request.json'),q)
            before=(project/'project.json').read_bytes()
            cli(label+'-dry-edit','timeline','edit','--project',project,'--sequence-id',sid,'--input',assets/(label+'-request.json'),'--dry-run')
            check(label+'-dry-run-read-only',(project/'project.json').read_bytes()==before)
            cli(label+'-edit','timeline','edit','--project',project,'--sequence-id',sid,'--input',assets/(label+'-request.json'))
            cli(label+'-validate','validate','--project',project)
            edited=json.loads((project/'project.json').read_bytes());parent=next(c for t in edited['sequences'][0]['tracks'] for c in t['clips'] if c['id']=='foreground-clip')
            check(label+'-editable-external-model',len(parent['blend']['opacity_animation']['clock_maps'])==1 and parent['blend']['opacity_animation']['keyframes']==keys,
                  duration_tick=parent['duration_tick'],blend=parent['blend'])
            output=project/'renders'/(label+'.mp4');options=['render','--project',project,'--output',output,'--profile','custom','--width',W,'--height',H]
            plan=cli(label+'-plan',*options,'--dry-run')['data']['plan'];result=cli(label+'-render',*options)['data']
            shutil.copyfile(output,assets/(label+'.mp4'));shutil.copyfile(result['manifest'],evidence/(label+'-manifest.json'))
            manifest=json.loads(Path(result['manifest']).read_bytes());controls=[x for x in manifest['inputs'] if x.get('kind')=='blend-opacity-automation']
            check(label+'-one-native-alpha-control',len(controls)==1 and controls[0]['alpha_operation']=='multiply-original-coverage-once',metadata=controls)
            loss=assets/(label+'-lossless.mkv');lossless(label+'-lossless',project,plan,loss);actual=pixels(label,loss)
            audio=run('decode-'+label+'-pcm',[exe,'-v','error','-i',loss,'-map','0:a:0','-f','s16le','-acodec','pcm_s16le','pipe:1'])
            check(label+'-full-stereo-PCM-equal',audio==pcm,samples_per_channel=len(audio)//4,sha256=rawsha(audio))
            check(label+'-exact-root-frame-count',len(actual)==30*size,frames=len(actual)//size)
            expected_frames=[];errors=[];alpha_equal=True
            for i in range(30):
                j=i-5;visible=j>=0 and j*TPS/FPS<parent['duration_tick']
                if not visible:expected=bg
                else:
                    elapsed=j/FPS
                    if label=='multiply-curve':
                        source_index=0;author_fraction=(math.exp(elapsed/(parent['duration_tick']/TPS)*math.log(3))-1)/2
                    else:
                        held=label=='screen-reverse-hold' and 5<=j<8
                        content_index=4 if held else j-3 if label=='screen-reverse-hold' and j>=8 else j
                        source_index=19-2*content_index if label=='screen-reverse-hold' else 2*content_index
                        author_fraction=1-content_index/10 if label=='screen-reverse-hold' else content_index/10
                    foreground_raw=frames[source_index].tobytes();amount=round(.1+.8*author_fraction,6);buffer=bytearray(size)
                    for pos in range(0,size,4):
                        coverage=round(foreground_raw[pos+3]*amount)/255
                        for channel in range(3):
                            b,f=bg[pos+channel],foreground_raw[pos+channel]
                            mixed=f if mode=='normal' else b*f/255 if mode=='multiply' else 255-(255-b)*(255-f)/255
                            buffer[pos+channel]=round(b*(1-coverage)+mixed*coverage)
                        buffer[pos+3]=255
                    expected=bytes(buffer)
                got=actual[i*size:(i+1)*size];errors.append(max(abs(a-b) for k,(a,b) in enumerate(zip(got,expected)) if k%4!=3))
                alpha_equal &= got[3::4]==expected[3::4];expected_frames.append(expected)
            check(label+'-independent-all-frame-RGB',max(errors)<=2,max_error_8bit=max(errors),per_frame_errors=errors,threshold_8bit=2)
            check(label+'-opaque-output-alpha-exact',alpha_equal)
            expected=b''.join(expected_frames)
            row={'name':label,'mode':mode,'transform':transform,'frames':30,'fps':FPS,'max_rgb_error':max(errors),
                'alpha_byte_equal':alpha_equal,'PCM_byte_equal':audio==pcm,'source_frames':21,
                'actual_decoded_sha256':rawsha(actual),'independent_reference_sha256':rawsha(expected),
                'author_model':parent['blend']['opacity_animation'],'command_metadata':controls};record['cases'].append(row);save()
            preview_frames=[]
            for i in range(30):
                panel=Image.new('RGB',(W*2,H+24),(20,27,38));panel.paste(frames[min(19,max(0,i-5))].convert('RGB'),(0,24))
                panel.paste(Image.frombytes('RGBA',(W,H),actual[i*size:(i+1)*size]).convert('RGB'),(W,24))
                draw=ImageDraw.Draw(panel);draw.text((10,7),'SOURCE FOREGROUND',fill='white');draw.text((W+10,7),label.upper(),fill='white');preview_frames.append(panel)
            preview_frames[0].save(assets/(label+'.gif'),save_all=True,append_images=preview_frames[1:],duration=100,loop=0,optimize=False,disposal=2)
            preview_frames[12].save(assets/(label+'-frame12.png'));comparisons.append(preview_frames[12])
            for name in (label+'.mp4',label+'-lossless.mkv'):
                value=json.loads(run('probe-'+name,[probe,'-v','error','-select_streams','v:0','-show_streams','-show_frames',
                    '-show_entries','stream=width,height,pix_fmt,avg_frame_rate:frame=pts_time','-of','json',assets/name]))
                times=[float(f['pts_time']) for f in value['frames']]
                check(name+'-native-PTS',len(times)==30 and all(abs(t-i/FPS)<.0011 for i,t in enumerate(times)),frame_count=len(times),last_pts=times[-1])
                record['video_probes'][name]=value
        package=work/'editable-project.zip';cli('package','convert','export','--project',project,'--output',package,'--target-format','package')
        imported=work/'reimported';cli('reimport','convert','import','--input',package,'--output',imported)
        plan=cli('reimport-plan','render','--project',imported,'--output',imported/'renders/replay.mp4',
            '--profile','custom','--width',W,'--height',H,'--dry-run')['data']['plan']
        replay=work/'replay.mkv';lossless('reimport-lossless',imported,plan,replay)
        check('package-decoded-last-case-byte-equal',pixels('replay',replay)==actual)
        run('source-preview',[exe,'-v','error','-i',source,'-t','2','-an','-vf','format=rgb24','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',assets/'source-preview.mp4'])
        strip=Image.new('RGB',(W*2,(H+24)*len(comparisons)))
        for i,im in enumerate(comparisons):strip.paste(im,(0,i*(H+24)))
        strip.save(assets/'comparison.png')
        (assets/'LICENSE.txt').write_text('CC0-1.0: original generated geometric RGBA frames, checker background, synthesized two-tone stereo PCM and rendered derivatives. Generated by scripts/smoke_blend_retime.py; no third-party media or model. MP4/GIF previews are lossy; independent checks use FFV1 RGBA and PCM.\n',encoding='utf8',newline='\n')
        record['public_files']={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(assets.iterdir()) if p.is_file()}
        record['cli_calls']=sum(row['cli'] for row in record['calls']);record['status']='passed'
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({k:record[k] for k in ('status','cli_calls','frozen_equal')}))


if __name__=='__main__':main()
