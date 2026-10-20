"""Native CPU CLI demo with a full-frame independent LUT-strength oracle."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image,ImageDraw
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--installed',type=Path)
    args=parser.parse_args();work=args.work.resolve();evidence=args.evidence.resolve();assets=args.assets.resolve()
    assert not any(p.exists() for p in (work,evidence,assets))
    assert work.is_relative_to(ROOT/'product/.runtime') and evidence.is_relative_to(ROOT/'docs') and assets.is_relative_to(ROOT/'docs/assets')
    for p in (work,evidence,assets):p.mkdir(parents=True)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
            'script_sha256':sha(__file__),'frozen_before':frozen(),'native_windows':sys.platform=='win32',
            'network':False,'virtualization':False,'new_model_inference':0,'calls':[],'checks':[],
            'continuous_playback_reviewed':False,'audio_reviewed':False,'full_capcut_parity':False}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save()
        assert ok,name
    def run(label,command,*,cwd=ROOT,data=None,cli=False):
        command=list(map(str,command));env=dict(os.environ)
        temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
        env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run(command,input=data,capture_output=True,cwd=cwd,env=env,timeout=900)
        # Binary raw pixels are hashed, not dumped into a text log.
        (evidence/(label+'.stderr.log')).write_bytes(result.stderr)
        if not label.startswith('decode-'):(evidence/(label+'.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label':label,'cli':cli,'command':command,'exit_code':result.returncode,
            'stdout_bytes':len(result.stdout),'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
            'stderr_sha256':'sha256:'+hashlib.sha256(result.stderr).hexdigest()});save()
        assert result.returncode==0,label+': '+result.stderr[-1200:].decode('utf8','replace')+result.stdout[-800:].decode('utf8','replace')
        return result.stdout
    if args.installed:
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',args.installed.resolve()/'run.py']
    else:
        bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
        prefix=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,ROOT/'product/src']
    def cli(label,*argv):return json.loads(run(label,[*prefix,*argv],cli=True))
    exe=shutil.which('ffmpeg');probe=shutil.which('ffprobe');assert exe and probe
    record['ffmpeg_sha256']=sha(exe);record['ffprobe_sha256']=sha(probe)
    W,H,FPS,COUNT=320,180,12,24
    try:
        frames=[]
        for i in range(COUNT):
            im=Image.new('RGB',(W,H));p=im.load()
            for y in range(H):
                for x in range(W):p[x,y]=(20+x*100//W,35+y*115//H,100+x*100//W)
            d=ImageDraw.Draw(im);d.rounded_rectangle((22,24,298,156),radius=16,fill=(220,220,205))
            d.rectangle((36,126,286,142),fill=(40,90,130));d.text((37,37),'AGENT VIDEO KIT',fill=(25,35,50))
            d.text((37,56),'LOCAL LUT / EDITABLE KEYFRAMES',fill=(35,50,70))
            d.ellipse((80+round(80*math.sin(i/COUNT*math.tau)),78,120+round(80*math.sin(i/COUNT*math.tau)),118),fill=(60,155,210))
            for j,color in enumerate(((32,96,192),(180,60,40),(90,180,100),(128,128,128),(230,210,70))):
                d.rectangle((195+j*16,82,207+j*16,112),fill=color)
            frames.append(im)
        # NUT keeps the exact 1/12 author clock. A millisecond Matroska input
        # rounds frame 2 to .167, so round-up sampling legitimately selects
        # the preceding source frame at 2/12; that is a different oracle.
        source=assets/'source-original.nut'
        run('encode-source',[exe,'-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}',
            '-framerate',str(FPS),'-i','pipe:0','-c:v','rawvideo','-pix_fmt','rgb24','-fflags','+bitexact',source],data=b''.join(im.tobytes() for im in [*frames,frames[-1]]))
        record['source_endpoint_guard']={'frames':COUNT+1,'last_pts_seconds':2.,'edited_half_open_frame_count':COUNT,
            'reason':'NUT reports the last PTS as duration; one explicit duplicate endpoint makes the 0..2s source range valid without bypassing validation'}
        lut=assets/'warm.cube'
        lut.write_text('TITLE "Original generated warm look CC0"\nLUT_3D_SIZE 2\n'+''.join(
            f'{.9*r+.1:.8f} {.65*g+.1*r:.8f} {.45*b:.8f}\n' for b in (0,1) for g in (0,1) for r in (0,1)),encoding='utf8')
        project=work/'project';cli('init','project','init',project)
        rights=['--license-spdx','CC0-1.0','--license-url','local://v73-original-generated/CC0-1.0',
            '--verification-status','verified','--permitted-use','commercial_ad','--creator','agent-video-kit',
            '--evidence','Original geometric frames and affine LUT generated by scripts/smoke_lut_automation.py; no external media']
        result=cli('ingest','media','ingest','--project',project,'--input',source,'--asset-id','original',
            '--source-url','local://v73-original-geometric-demo',*rights)
        cli('lut-register','lut','register','--project',project,'--input',lut,'--lut-id','warm',*rights)
        p=json.loads((project/'project.json').read_bytes());p['settings']['canvas']={'width':W,'height':H,'background':'#000000'}
        p['settings']['timebase']={'ticks_per_second':90000,'display_fps':{'num':FPS,'den':1}}
        (project/'project.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        effect={'type':'lut3d','parameters':{'lut_id':'warm','intensity':0},'keyframes':[{'property':'intensity','keyframes':[
            {'at_tick':0,'value':0,'interpolation':'ease_in_out'},
            {'at_tick':90000,'value':1,'interpolation':'ease_in_out'},
            {'at_tick':180000,'value':0,'interpolation':'linear'}]}]}
        request=assets/'timeline-request.json';request.write_text(json.dumps({'operations':[{'op':'append_clip',
            'track_id':'track_video_1','asset_id':'original','id':'graded','source_in_tick':0,'source_out_tick':180000,
            'duration_tick':180000,'effects':[effect]}]},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        cli('compose','timeline','compose','--project',project,'--input',request)
        cli('validate','validate','--project',project)
        preview=project/'renders/edited-cli.mp4'
        options=['render','--project',project,'--output',preview,'--profile','custom','--width',W,'--height',H]
        plan=cli('plan',*options,'--dry-run')['data']['plan']
        result=cli('render',*options)['data']
        manifest=json.loads(Path(result['manifest']).read_bytes())
        shutil.copyfile(preview,assets/'edited-cli.mp4')
        shutil.copyfile(result['manifest'],evidence/'render-manifest.json')
        meta=[m for m in manifest['inputs'] if m.get('kind')=='effect-automation']
        check('real-cli-binds-one-lut-and-exact-source-hash',len(meta)==1 and meta[0]['resource_context']['lut_sha256']==sha(lut),metadata=meta)
        command=plan['command'];idx=command.index('-filter_complex');inputs=command[1:idx]
        if '-progress' in inputs:
            position=inputs.index('-progress');del inputs[position:position+2]
        lossless=assets/'edited-lossless.mkv'
        run('render-plan-lossless',[exe,*inputs,'-filter_complex',plan['filter_complex'],'-map','[vout]',
            '-fps_mode','passthrough','-c:v','ffv1','-pix_fmt','bgra',lossless,'-map','[aout]','-f','null','NUL'],cwd=project)
        full=work/'fully-graded.mkv'
        # Reference uses native lut3d only; strength interpolation/mixing is
        # independently computed below, without command files or product Curve.
        run('full-lut-reference',[exe,'-v','error','-filter_threads','1','-i',source,'-vf',f"format=gbrap,lut3d=file='{str(lut).replace(chr(92),'/').replace(':',chr(92)+':')}'",
            '-t','2','-an','-c:v','ffv1','-pix_fmt','bgra',full])
        def decode(label,path):return run('decode-'+label,[exe,'-v','error','-i',path,'-t','2','-f','rawvideo','-pix_fmt','rgba','pipe:1'])
        original=decode('original',source);graded=decode('reference',full);actual=decode('actual',lossless)
        size=W*H*4;check('exact-frame-count',len(original)==len(graded)==len(actual)==size*COUNT,frames=COUNT,fps=FPS)
        errors=[];alpha_equal=True;expected_frames=[]
        for i in range(COUNT):
            t=i/FPS;u=t if t<=1 else t-1;ease=2*u*u if u<.5 else 1-2*(1-u)**2
            strength=round(ease if t<=1 else 1-ease,6)
            a=original[i*size:(i+1)*size];b=graded[i*size:(i+1)*size];c=actual[i*size:(i+1)*size]
            expected=bytes(v if j%4==3 else round(v*(1-strength)+b[j]*strength) for j,v in enumerate(a))
            expected_frames.append(expected);errors.append(max(abs(x-y) for x,y in zip(c,expected)))
            alpha_equal &= c[3::4]==a[3::4]
        check('all-frame-rgb-independent-arithmetic',max(errors)<=1,max_error_8bit=max(errors),frame_errors=errors,precision='8-bit-encoded-RGB')
        check('all-frame-alpha-byte-equal',alpha_equal)
        record['decoded_sha256']={k:'sha256:'+hashlib.sha256(v).hexdigest() for k,v in {'original':original,'full_reference':graded,'actual':actual,'independent_reference':b''.join(expected_frames)}.items()}
        run('encode-original-preview',[exe,'-v','error','-i',source,'-t','2','-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',assets/'source-preview.mp4'])
        panels=[]
        for i in range(COUNT):
            panel=Image.new('RGB',(W*2,H+24),(18,25,35));panel.paste(frames[i],(0,24))
            panel.paste(Image.frombytes('RGBA',(W,H),actual[i*size:(i+1)*size]).convert('RGB'),(W,24))
            d=ImageDraw.Draw(panel);d.text((12,7),'ORIGINAL',fill='white');d.text((W+12,7),'ANIMATED LUT  0 > 1 > 0',fill='white');panels.append(panel)
        panels[0].save(assets/'comparison.gif',save_all=True,append_images=panels[1:],duration=[83,83,84]*8,loop=0,optimize=False,disposal=2)
        panels[12].save(assets/'comparison-frame12.png')
        run('encode-comparison',[exe,'-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W*2}x{H+24}',
            '-framerate',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',assets/'comparison.mp4'],data=b''.join(im.tobytes() for im in panels))
        cli('package','convert','export','--project',project,'--output',work/'editable-project.zip','--target-format','package')
        record['video_probes']={}
        for name in ('source-original.nut','edited-lossless.mkv','edited-cli.mp4','source-preview.mp4','comparison.mp4'):
            value=json.loads(run('probe-'+name,[probe,'-v','error','-select_streams','v:0','-show_streams','-show_frames',
                '-show_entries','stream=width,height,pix_fmt,avg_frame_rate,duration:frame=pts_time','-of','json',assets/name]))
            times=[float(f['pts_time']) for f in value['frames']]
            expected_count=COUNT+1 if name=='source-original.nut' else COUNT
            check(name+'-clock',len(times)==expected_count and all(abs(t-i/FPS)<.0011 for i,t in enumerate(times)),frame_count=len(times),last_pts=times[-1])
            record['video_probes'][name]=value
        (assets/'LICENSE.txt').write_text('Original geometric frames, warm.cube, and their rendered derivatives generated by scripts/smoke_lut_automation.py: CC0-1.0. No third-party media or models. Preview MP4/GIF are lossy; exact RGB/alpha checks use lossless MKV. No audio.\n',encoding='utf8')
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
