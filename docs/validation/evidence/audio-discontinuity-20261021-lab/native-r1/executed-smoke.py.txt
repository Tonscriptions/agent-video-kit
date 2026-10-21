"""Real CLI previews/renders of original PCM gaps/overlaps, with complete frame/sample checks."""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image,ImageDraw
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
W,H,FPS,TPS,RATE=192,108,25,90000,48000
SOURCE_FRAMES,SELECTED_FRAMES,PACKET,PACKETS=130,120,9600,20

def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def draw_number(draw,number,x,y,scale=2):
    digits=('abcdef','bc','abdeg','abcdg','bcfg','acdfg','acdefg','abc','abcdefg','abcdfg')
    shapes={'a':(1,0,5,1),'b':(5,1,6,5),'c':(5,6,6,10),'d':(1,10,5,11),'e':(0,6,1,10),'f':(0,1,1,5),'g':(1,5,5,6)}
    for place,character in enumerate(f'{number:05d}'):
        for segment in digits[int(character)]:
            a,b,c,d=shapes[segment];left=x+place*8*scale
            draw.rectangle((left+a*scale,y+b*scale,left+c*scale-1,y+d*scale-1),fill=(240,245,250))
def picture(index):
    image=Image.new('RGBA',(W,H),(18+(index//25)*16,45,95,255));draw=ImageDraw.Draw(image)
    draw_number(draw,index,12,10);draw_number(draw,index*40,12,40)
    for bit in range(16):
        x=8+bit*11;draw.rectangle((x,88,x+7,95),fill=(255,255,255,255) if index&(1<<bit) else (0,0,0,255))
    return image
def source_PCM():
    t=np.arange(PACKET*PACKETS,dtype=np.float64)/RATE;block=np.arange(len(t))//PACKET
    gain=.09+.02*(block%13)
    return np.stack((gain*np.sin(2*np.pi*433*t),gain*.79*np.sin(2*np.pi*739*t+.27)),axis=1).astype('<f4')
def placed_PCM():
    result=np.zeros((SELECTED_FRAMES*RATE//FPS,2),dtype='<f4');original=source_PCM()
    for i in range(PACKETS):
        left=i*PACKET+(24000 if i>=5 else 0)-(4800 if i>=10 else 0)
        result[left:left+PACKET]=original[i*PACKET:(i+1)*PACKET]
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--installed',type=Path);parser.add_argument('--reuse-sources',type=Path);args=parser.parse_args()
    work,evidence,assets=(getattr(args,name).resolve() for name in ('work','evidence','assets'))
    assert work.is_relative_to(ROOT/'product/.runtime') and evidence.is_relative_to(ROOT/'docs/validation') and assets.is_relative_to(ROOT/'docs/assets')
    assert not any(p.exists() for p in (work,evidence,assets))
    for path in (work,evidence,assets):path.mkdir(parents=True)
    (evidence/'executed-smoke.py.txt').write_bytes(Path(__file__).read_bytes());current=frozen();assert len(current)==267
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':current,
        'generator_sha256':sha(__file__),'calls':[],'checks':[],'cases':{},'native_windows':True,'virtualization':False,'network':False,
        'installed':str(args.installed) if args.installed else None,'audio_listened':False,'continuous_playback_reviewed':False,
        'natural_quality_accepted':False,'full_capcut_parity':False,'scope':'Original synthetic clock media; no natural footage or acoustic quality acceptance.'}
    def save():write(evidence/'verification.json',record)
    def check(name,condition,**details):
        record['checks'].append({'name':name,'ok':bool(condition),**details});save();assert condition,name
    env=dict(os.environ,TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1')
    bootstrap=('import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())')
    prefix=([sys.executable,'-I','-S','-B','-X','utf8',args.installed.resolve()/'run.py'] if args.installed else
        [sys.executable,'-E','-B','-X','utf8','-c',bootstrap,ROOT/'product/src'])
    baseline_root=ROOT.parent/'multicam-affine-clock-lab-20261021'
    baseline=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,baseline_root/'product/src']
    exe=shutil.which('ffmpeg');probe=shutil.which('ffprobe');assert exe and probe
    record.update(ffmpeg={'path':exe,'sha256':sha(exe)},ffprobe={'path':probe,'sha256':sha(probe)})
    def run(label,command,*,cli=False,binary=False):
        command=list(map(str,command));start=time.monotonic();result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
        (evidence/(label+'.stderr.log')).write_bytes(result.stderr)
        if not binary:(evidence/(label+'.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label':label,'command':command,'exit_code':result.returncode,'cli':cli,'wall_seconds':time.monotonic()-start,
            'stdout_bytes':len(result.stdout),'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest()});save()
        assert result.returncode==0,(label,(result.stdout+result.stderr)[-4000:].decode('utf8','replace'));return result.stdout
    def cli(label,*argv,old=False):return json.loads(run(label,[*(baseline if old else prefix),*argv],cli=True))
    def video(label,path):return run(label,[exe,'-v','error','-i',path,'-map','0:v:0','-an','-fps_mode','passthrough','-pix_fmt','rgba','-f','rawvideo','pipe:1'],binary=True)
    def audio(label,path):return run(label,[exe,'-v','error','-i',path,'-map','0:a:0','-vn','-ar',RATE,'-ac','2','-f','f32le','pipe:1'],binary=True)
    def gif(path,raw):
        size=W*H*4;frames=[Image.frombytes('RGBA',(W,H),raw[i:i+size]).convert('RGB') for i in range(0,len(raw),size)]
        frames[0].save(path,save_all=True,append_images=frames[1:],duration=40,loop=0,disposal=2,optimize=False)
        with Image.open(path) as image:
            check(path.stem+'-GIF-frame-count',image.n_frames==len(frames));duration=0
            for i in range(image.n_frames):image.seek(i);duration+=image.info.get('duration',0)
            check(path.stem+'-GIF-duration',duration==40*len(frames))
    try:
        if args.reuse_sources:
            source_manifest=json.loads(args.reuse_sources.read_bytes());source=Path(source_manifest['source']['path'])
            check('reused-original-source-exact-SHA256',sha(source)==source_manifest['source']['sha256'])
        else:
            raw_video=work/'original.rgba';raw_video.write_bytes(b''.join(picture(i).tobytes() for i in range(SOURCE_FRAMES)))
            raw_audio=work/'original.f32';raw_audio.write_bytes(source_PCM().tobytes());source=assets/'original.nut'
            command=[exe,'-v','error','-f','rawvideo','-pixel_format','rgba','-video_size',f'{W}x{H}','-framerate',FPS,'-i',raw_video,
                '-f','f32le','-ar',RATE,'-ac','2','-i',raw_audio,'-af',"asetnsamples=n=9600:p=0,asetpts='N+if(gte(N,48000),24000,0)-if(gte(N,96000),4800,0)'",
                '-map','0:v:0','-map','1:a:0','-c:v','ffv1','-level','3','-pix_fmt','bgra','-c:a','pcm_f32le',source]
            run('generate-original',command)
            native=json.loads(run('original-audio-native-frames',[probe,'-v','error','-select_streams','a:0','-show_frames','-show_streams',
                '-show_entries','frame=pts,nb_samples:stream=time_base','-of','json',source]))
            tb=Fraction(native['streams'][0]['time_base']);expected=[i*PACKET+(24000 if i>=5 else 0)-(4800 if i>=10 else 0) for i in range(PACKETS)]
            check('original-native-frame-PTS-and-counts',[(Fraction(row['pts'])*tb*RATE,int(row['nb_samples'])) for row in native['frames']]==[(x,PACKET) for x in expected])
            check('original-decodes-to-all-original-PCM-in-decode-order',audio('original-raw-PCM',source)==source_PCM().tobytes())
            source_manifest={'status':'validated-original-native-clock','source':{'path':str(source),'sha256':sha(source)},
                'frames':SOURCE_FRAMES,'fps':FPS,'rate':RATE,'channels':2,'decoded_order_samples_per_channel':PACKET*PACKETS,
                'selected_frames':SELECTED_FRAMES,'selected_samples_per_channel':SELECTED_FRAMES*RATE//FPS,
                'native_audio_frames':native,'generated_RGBA_sha256':sha(raw_video),'generated_float_PCM_sha256':sha(raw_audio),
                'generation_command':list(map(str,command)),'rights':'Original CC0 PCM and font-free geometric frame counters.'}
        write(evidence/'source-manifest.json',source_manifest);record['original_source']=source_manifest['source'];truth=placed_PCM()
        original_frames=video('original-RGBA',source)
        check('all-original-video-frames-exact-independent-RGBA',original_frames==b''.join(picture(i).tobytes() for i in range(SOURCE_FRAMES)))
        if not args.reuse_sources:
            original_mp4=assets/'original-video-only.mp4'
            run('original-video-only-browser-copy',[exe,'-v','error','-i',source,'-map','0:v:0','-an','-c:v','libx264','-preset','ultrafast','-crf','0','-pix_fmt','yuv444p',original_mp4])
            gif(assets/'original.gif',video('original-MP4-RGBA',original_mp4))
        caps=cli('capabilities','capabilities')['data']['capabilities']
        check('agent-discovery-clock-protocols-agree',caps['native_audio_source_clock']['protocol']==caps['media']['source_audio_clock']['protocol']==caps['media']['multicam_source_coverage']['audio_source_clock']=='native-decoded-audio-interval-clock-v1')
        baseline_pcm={};candidate_pcm={}
        modes=[('before-forward',True,False,False),('before-reverse',True,True,False)] if not args.installed else []
        modes+=[('forward',False,False,False),('reverse',False,True,False),('R3',False,False,True)]
        for name,old,reverse,r3 in modes:
            project=work/('project-'+name);cli(name+'-init','project','init',project,old=old)
            cli(name+'-ingest','media','ingest','--project',project,'--input',source,'--asset-id','original',
                '--source-url','local://native-audio-clock/CC0','--license-spdx','CC0-1.0','--license-url','local://native-audio-clock/CC0',
                '--verification-status','verified','--permitted-use','commercial_ad','--creator','agent-video-kit',
                '--evidence','Original generated signal, native PTS and source manifest retained.',old=old)
            data=json.loads((project/'project.json').read_bytes());data['settings']['canvas'].update(width=W,height=H,fps=FPS)
            data['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':FPS,'den':1}}
            speed=1.25 if r3 else 1.;seconds=SELECTED_FRAMES/FPS/speed;frames=round(seconds*FPS)
            if r3:
                executable=ROOT.parent/'rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
                license=executable.with_name('COPYING.txt');dll=executable.with_name('sndfile.dll')
                data['settings']['audio_stretch']={'engine':'rubberband-r3-offline-v1','executable':str(executable),'sha256':sha(executable),
                    'license_path':str(license),'license_sha256':sha(license),'license_spdx':'GPL-2.0-or-later','dependencies':[{'path':str(dll),'sha256':sha(dll)}]}
            write(project/'project.json',data)
            operations=[{'op':'append_clip','track_id':track,'id':kind,'asset_id':'original','timeline_start_tick':0,
                'source_in_tick':0,'source_out_tick':round(4.8*TPS),'duration_tick':round(seconds*TPS),'speed':speed,'reverse':reverse}
                for track,kind in (('track_video_1','picture'),('track_audio_1','sound'))]
            operations.append({'op':'set_sequence_duration','sequence_id':'seq_main','duration_tick':round(seconds*TPS),'trim':False})
            request=project/'compose.json';write(request,{'operations':operations});cli(name+'-compose','timeline','compose','--project',project,'--input',request,old=old)
            preview=cli(name+'-preview','preview','range','--project',project,'--start-frame','0','--end-frame',frames,'--height',H,old=old)['data']
            master=assets/(name+'-lossless.nut');shutil.copyfile(Path(preview['master']),master)
            raw=video(name+'-master-RGBA',master);pcm=audio(name+'-master-PCM',master)
            expected_indices=[SELECTED_FRAMES-1-i for i in range(frames)] if reverse else [math.floor(i*speed+1e-8) for i in range(frames)]
            check(name+'-all-lossless-frames-match-independent-originals',raw==b''.join(picture(i).tobytes() for i in expected_indices),frames=frames,RGBA_bytes=len(raw))
            if not r3:
                expected_pcm=(truth[::-1] if reverse else truth).tobytes();equal=pcm==expected_pcm
                check(name+'-PCM-contract',equal is (not old),equal_to_independent_truth=equal,PCM_bytes=len(pcm),samples_per_channel=len(pcm)//8)
                (baseline_pcm if old else candidate_pcm)[name.replace('before-','')]=np.frombuffer(pcm,dtype='<f4').reshape(-1,2)
            else:
                receipt=json.loads(Path(preview['manifest']).read_bytes())
                execution=next(row['audio_stretch']['execution'] for row in receipt['inputs'] if row.get('audio_stretch'))
                check('R3-received-complete-clock-and-authored-EOF-silence',execution['input_pcm']['frames']==230400
                    and execution['output_pcm']['frames']==184320 and execution['source_clock_bound']['padding_samples']==19200)
                check('R3-master-sample-count',len(pcm)==184320*8)
            if old:continue
            if not r3:
                again=cli(name+'-verified-preview-hit','preview','range','--project',project,'--start-frame','0','--end-frame',frames,'--height',H)['data']
                check(name+'-preview-cache-hit',again['cache_hit'] and sha(again['master'])==sha(master))
            listing=cli(name+'-cache-list','cache','list','--project',project,'--kind','native-audio-clock')['data']
            check(name+'-discover-protected-source-cache',len(listing['entries'])==1 and listing['entries'][0]['protected_source_reference'])
            removed=cli(name+'-cache-prune','cache','prune','--project',project,'--kind','native-audio-clock')['data']
            check(name+'-registered-source-cache-survives-prune',not removed['removed'] and len(removed['protected_reference_keys'])==1)
            output=project/'renders'/(name+'.mp4')
            rendered=cli(name+'-render','render','--project',project,'--output',output,'--profile','custom','--width',W,'--height',H,'--crf','0','--pixel-format','yuv444p')['data']
            shutil.copyfile(output,assets/output.name);shutil.copyfile(rendered['manifest'],evidence/(name+'-render-manifest.json'))
            encoded=video(name+'-MP4-RGBA',output)
            pts=json.loads(run(name+'-MP4-PTS',[probe,'-v','error','-select_streams','v:0','-show_frames','-show_streams','-show_entries','frame=pts:stream=time_base','-of','json',output]))
            tb=Fraction(pts['streams'][0]['time_base'])
            check(name+'-every-MP4-frame-PTS',len(encoded)==len(raw) and [int(row['pts'])*tb for row in pts['frames']]==[Fraction(i,FPS) for i in range(frames)])
            array=np.frombuffer(encoded,dtype=np.uint8).reshape(frames,H,W,4)
            check(name+'-every-MP4-binary-frame-ID',all(sum((int(array[i,90,10+bit*11,0])>=128)<<bit for bit in range(16))==expected_indices[i] for i in range(frames)))
            gif(assets/(name+'.gif'),encoded);record['cases'][name]={'master_PCM_sha256':'sha256:'+hashlib.sha256(pcm).hexdigest(),
                'master_RGBA_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'frames':frames,'samples_per_channel':len(pcm)//8,'MP4_sha256':sha(output)};save()
        if baseline_pcm:
            diagram=Image.new('RGB',(768,312),(16,21,31));draw=ImageDraw.Draw(diagram)
            for row,values in enumerate((truth,baseline_pcm['forward'],candidate_pcm['forward'])):
                center=55+row*100;draw.line((64,center,748,center),fill=(70,85,100));draw_number(draw,row,7,center-12,1)
                gain=np.max(np.abs(values),axis=1);edges=np.linspace(0,len(gain),685,dtype=int)
                for x,(left,right) in enumerate(zip(edges,edges[1:])):
                    amplitude=float(gain[left:max(left+1,right)].max());height=round(amplitude*100)
                    draw.line((64+x,center-height,64+x,center+height),fill=(70,220,150) if row!=1 else (245,160,65))
            diagram.save(assets/'actual-PCM-comparison.png')
            frames=[]
            for i in range(SELECTED_FRAMES):
                frame=diagram.copy();d=ImageDraw.Draw(frame);x=64+round(i/SELECTED_FRAMES*684);d.line((x,4,x,307),fill=(240,245,250),width=2);frames.append(frame)
            frames[0].save(assets/'actual-PCM-comparison.gif',save_all=True,append_images=frames[1:],duration=40,loop=0,disposal=2,optimize=False)
            record['diagnostic_figure']={'rows':['independent_author_placement','actual_published_V90_master','actual_candidate_master'],
                'derivation':'per-column max absolute decoded samples; animated cursor is time only; this is an audio diagnostic, not an effect render'}
        record.update(status='passed',cli_calls=sum(row['cli'] for row in record['calls']),other_native_commands=sum(not row['cli'] for row in record['calls']))
    except BaseException as exc:record.update(status='failed-preserved',error=repr(exc));raise
    finally:
        record.update(frozen_after=frozen(),finished_at_utc=datetime.now(timezone.utc).isoformat());record['frozen_equal']=current==record['frozen_after'];save()
    assert record['frozen_equal'];print(json.dumps({k:record[k] for k in ('status','cli_calls','other_native_commands','frozen_equal')}))

if __name__=='__main__':main()
