"""Exercise all 100 presets through a newly installed, isolated native CLI."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--installed',type=Path,required=True)
    ap.add_argument('--evidence',type=Path,required=True)
    ap.add_argument('--assets',type=Path,required=True)
    args=ap.parse_args()
    work=ROOT/'product/.runtime/look-release-20261024/cases'
    for path in (work,args.evidence,args.assets):
        if path.exists():raise ValueError('Existing run is preserved: '+str(path))
        path.mkdir(parents=True)
    env=dict(os.environ)
    temp=work/'temp';temp.mkdir()
    env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'),
               HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    prefix=[sys.executable,'-I','-S','-B','-X','utf8',str(args.installed/'run.py')]
    commands=[];probes={};results=[]

    def cli(label,argv,expected=0):
        command=prefix+list(map(str,argv));started=time.monotonic()
        done=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=240,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (args.evidence/(label+'.stdout.json')).write_bytes(done.stdout)
        (args.evidence/(label+'.stderr.txt')).write_bytes(done.stderr)
        response=json.loads(done.stdout)
        commands.append({'id':label,'argv':command,'exit_code':done.returncode,'expected':expected,
                         'seconds':round(time.monotonic()-started,3),'stdout_sha256':sha(args.evidence/(label+'.stdout.json'))})
        save(args.evidence/'commands.json',commands)
        if done.returncode!=expected or response['ok']!=(expected==0):
            raise RuntimeError(label+': '+json.dumps(response,ensure_ascii=False))
        return response

    def native(label,argv):
        done=subprocess.run(list(map(str,argv)),cwd=work,env=env,capture_output=True,timeout=180,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (args.evidence/(label+'.stderr.txt')).write_bytes(done.stderr)
        if done.returncode:raise RuntimeError(label+': '+done.stderr.decode('utf-8','replace')[-1500:])
        return done.stdout

    def frame(label,video,output=None):
        raw=native(label,['ffmpeg','-v','error','-i',video,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
        im=Image.frombytes('RGB',(480,300),raw)
        if output:im.save(output)
        return im

    try:
        cli('version',['version']);cli('doctor',['doctor']);cli('capabilities',['capabilities'])
        listed=cli('look-list',['look','list'])['data'];assert listed['count']==100
        cli('look-search',['look','list','--query','黑白']);cli('look-category',['look','list','--category','cinema'])
        rows=listed['looks']
        installed_data=args.installed/'site/ai_ad_editor/look_data'
        source=args.assets/'reference.png';shutil.copyfile(installed_data/'previews/reference.png',source)
        (args.assets/'LICENSE.txt').write_text('Original synthetic RGB gradients, skin-color swatches, fictional AVK product artwork, moving test clip and synthetic 440 Hz tone: Agent Video Kit contributors, CC0-1.0.\nNo natural footage, official brand filters, font files or model outputs are included.\nLook data: João Almeida / t3mujinpack and Nixua / Striped Purple, MIT; see the catalog and preserved notices.\n',encoding='utf-8')
        original=args.assets/'original.mp4'
        native('generate-original',['ffmpeg','-v','error','-loop','1','-i',source,
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=1',
            '-vf',"zoompan=z='1+0.001*on':d=12:s=480x300:fps=12",'-af','volume=0.04',
            '-frames:v','12','-t','1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k',original])
        project=work/'project'
        cli('project-init',['project','init',project,'--name','100 look preset verification'])
        # Author the open project settings before composing; no source imports.
        doc=json.loads((project/'project.json').read_bytes())
        doc['settings']['canvas'].update(width=480,height=300)
        doc['settings']['timebase']['display_fps']={'num':12,'den':1}
        save(project/'project.json',doc)
        ingested=cli('ingest',['media','ingest','--project',project,'--input',original,
            '--source-url','local://look-preset-generated/original.mp4','--license-spdx','CC0-1.0',
            '--license-url',args.assets/'LICENSE.txt','--evidence',args.assets/'LICENSE.txt',
            '--creator','Agent Video Kit contributors','--verification-status','verified','--permitted-use','commercial_ad'])
        asset=ingested['data']['asset']['id']
        changes={'sequence_id':'seq_main','operations':[
            {'op':'append_clip','track_id':track,'asset_id':asset,'source_in_tick':0,'source_out_tick':90000,'duration_tick':90000}
            for track in ('track_video_1','track_audio_1')]}
        save(work/'changes.json',changes);save(args.evidence/'changes.json',changes)
        cli('compose',['timeline','compose','--project',project,'--input',work/'changes.json'])
        clip=json.loads((project/'project.json').read_bytes())['sequences'][0]['tracks'][0]['clips'][0]['id']
        baseline=project/'renders/baseline.mp4'
        cli('baseline',['render','--project',project,'--output',baseline,'--width',480,'--height',300,'--publish'])
        baseline_pixels=frame('baseline-frame',baseline)
        preview_dir=args.assets/'previews';preview_dir.mkdir()
        video_dir=args.assets/'videos';video_dir.mkdir()
        source_manifest=json.loads((ROOT/'sources/lut-research-20261024/look-sources.json').read_bytes())
        upstream_files={entry['upstream_path']:ROOT/entry['path'] for repo in source_manifest for entry in repo['files']}
        for index,row in enumerate(rows,1):
            look_id=row['id']
            cli('inspect-'+look_id,['look','inspect','--id',look_id])
            preview_path=preview_dir/(look_id+'.png')
            cli('preview-'+look_id,['look','preview','--id',look_id,'--output',preview_path])
            cli('apply-'+look_id,['look','apply','--project',project,'--id',look_id,'--clip-id',clip])
            video=project/'renders'/(look_id+'.mp4')
            rendered=cli('render-'+look_id,['render','--project',project,'--output',video,'--width',480,'--height',300,'--publish'])
            unexpected=[w for w in rendered.get('warnings',[]) if w.get('code') in
                        {'LUT_ID_MISSING','LUT_FILE_MISSING','LUT_ID_CONTEXT_MISSING','RENDER_FEATURE_UNSUPPORTED','EFFECT_PARAMETER_INVALID'}]
            assert not unexpected,unexpected
            shutil.copyfile(video,video_dir/video.name)
            probe=json.loads(native('probe-'+look_id,['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',video]))
            stream=next(s for s in probe['streams'] if s['codec_type']=='video')
            assert (stream['width'],stream['height'],int(stream['nb_read_frames']))==(480,300,12),stream
            native('decode-'+look_id,['ffmpeg','-v','error','-i',video,'-f','null','-'])
            im=frame('frame-'+look_id,video)
            assert im.tobytes()!=baseline_pixels.tobytes(),look_id
            # Independent upstream FFmpeg execution, not the converter's sampler.
            raw_source=upstream_files[row['source']['path']]
            source_out=work/'source-preview.png'
            source_out.unlink(missing_ok=True)
            if raw_source.suffix.lower()=='.png':
                command=['ffmpeg','-v','error','-i',source,'-i',raw_source,'-filter_complex','[0:v][1:v]haldclut=interp=tetrahedral',
                         '-frames:v','1','-update','1',source_out]
            else:
                shutil.copyfile(raw_source,work/'upstream.cube')
                command=['ffmpeg','-v','error','-i',source,'-vf',"lut3d=file='upstream.cube':interp=tetrahedral",
                         '-frames:v','1','-update','1',source_out]
            native('upstream-'+look_id,command)
            ours=np.asarray(Image.open(preview_path).convert('RGB')).astype(np.int16)
            upstream=np.asarray(Image.open(source_out).convert('RGB')).astype(np.int16)
            error=np.abs(ours-upstream)
            result={'id':look_id,'preview_sha256':sha(preview_path),'video_sha256':sha(video),
                    'decoded_first_frame_sha256':hashlib.sha256(im.tobytes()).hexdigest(),
                    'frames':12,'duration_seconds':float(stream['duration']),
                    'upstream_native_mean_abs_code_error':float(error.mean()),'upstream_native_max_abs_code_error':int(error.max()),
                    'render_warning_codes':sorted({w.get('code','') for w in rendered.get('warnings',[])})}
            results.append(result);probes[look_id]=probe
            save(args.evidence/'presets.json',results)
            print(json.dumps({'completed':index,'total':100,'id':look_id}),flush=True)
        assert len({r['preview_sha256'] for r in results})==100
        assert len({r['decoded_first_frame_sha256'] for r in results})==100
        cli('validate',['validate','--project',project]);cli('rights',['rights','check','--project',project])
        cli('policy',['policy','audit','--project',project])
        last=rows[-1]['id']
        cli('dry-run',['look','apply','--project',project,'--id',last,'--global','--strength','.65','--dry-run'])
        cli('partial-global',['look','apply','--project',project,'--id','t3-kodak-gold-200','--global','--strength','.65','--idempotency-key','global-gold'])
        cli('partial-replay',['look','apply','--project',project,'--id','t3-kodak-gold-200','--global','--strength','.65','--idempotency-key','global-gold'])
        partial=project/'renders/partial-global.mp4'
        cli('partial-render',['render','--project',project,'--output',partial,'--width',480,'--height',300,'--publish'])
        cli('quality',['quality','check','--project',project,'--input',partial,'--width',480,'--height',300,'--require-audio'])
        cli('unknown-refused',['look','inspect','--id','missing-look'],3)
        cli('bad-strength-refused',['look','apply','--project',project,'--id',last,'--global','--strength','nan'],2)
        package=work/'looks.avk.zip'
        cli('export',['convert','export','--project',project,'--target-format','package','--output',package])
        restored=work/'restored'
        cli('import',['convert','import','--input',package,'--output',restored])
        cli('restored-validate',['validate','--project',restored]);cli('restored-rights',['rights','check','--project',restored])
        restored_video=restored/'renders/restored.mp4'
        cli('restored-render',['render','--project',restored,'--output',restored_video,'--width',480,'--height',300,'--publish'])
        restored_frame=frame('restored-frame',restored_video)
        partial_frame=frame('partial-frame',partial)
        assert restored_frame.tobytes()==partial_frame.tobytes()
        shutil.copyfile(package,args.assets/'example.avk.zip')
        shutil.copyfile(partial,args.assets/'partial-global.mp4')
        save(args.evidence/'media-probes.json',probes)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
        sheet=Image.new('RGB',(1200,1800),'#101820');draw=ImageDraw.Draw(sheet)
        for i,row in enumerate(rows):
            im=Image.open(preview_dir/(row['id']+'.png')).convert('RGB');im.thumbnail((120,150))
            x=(i%10)*120;y=(i//10)*180
            sheet.paste(im,(x,y));draw.text((x+3,y+80),str(i+1).zfill(3),fill='white',font=font)
            label=row['name']
            for k in range(0,min(len(label),45),15):draw.text((x+3,y+101+k//15*17),label[k:k+15],fill='white',font=font)
        sheet.save(args.assets/'contact-sheet.jpg',quality=90)
        selected=['t3-kodak-gold-200','t3-kodak-portra-400','t3-fuji-velvia-50','t3-ilford-hp5-plus-400',
                  'sp-1950s','sp-teal-embers','sp-amber-haze','sp-lomochrome-purple','sp-infrared','sp-tiger']
        frames=[]
        ref=Image.open(source).convert('RGB')
        for look_id in selected:
            im=Image.new('RGB',(960,340),'#101820');im.paste(ref,(0,40))
            im.paste(Image.open(preview_dir/(look_id+'.png')).convert('RGB'),(480,40))
            ImageDraw.Draw(im).text((15,12),'ORIGINAL / '+look_id+' / STRENGTH 1',font=font,fill='white')
            im.thumbnail((720,255));frames.append(im)
        frames[0].save(args.assets/'comparison.gif',save_all=True,append_images=frames[1:],duration=1200,loop=0)
        pcm=native('audio-pcm',['ffmpeg','-v','error','-i',partial,'-vn','-f','f32le','-ac','1','pipe:1'])
        audio=np.frombuffer(pcm,dtype='<f4');assert len(audio)>0 and np.max(np.abs(audio))>0.001
        inventory=[{'path':p.relative_to(args.assets).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
                   for p in sorted(args.assets.rglob('*')) if p.is_file()]
        save(args.evidence/'media-manifest.json',inventory)
        summary={'status':'passed','date_utc':datetime.now(timezone.utc).isoformat(),'release':'v0.1.0-alpha.2',
                 'installed':str(args.installed),'isolated_cli_commands':len(commands),'presets_verified':100,
                 'native_still_previews':100,'rendered_videos':100,'decoded_frames_per_video':12,
                 'unique_preview_hashes':100,'unique_rendered_frame_hashes':100,'upstream_native_comparisons':100,
                 'expected_refusals':2,'package_roundtrip_decoded_pixels_equal':True,'native_windows':True,
                 'runtime_network_downloads':0,'virtual_environments_created':0,'new_model_inferences':0,
                 'synthetic_audio_peak':float(np.max(np.abs(audio))),'human_listening':False,
                 'continuous_playback_review':False,'natural_footage_acceptance':False}
        save(args.evidence/'verification.json',summary);print(json.dumps(summary,ensure_ascii=False))
    except Exception as exc:
        save(args.evidence/'failure.json',{'status':'failed','error':str(exc),'commands_completed':len(commands),'presets_completed':len(results)})
        raise


if __name__=='__main__':main()
