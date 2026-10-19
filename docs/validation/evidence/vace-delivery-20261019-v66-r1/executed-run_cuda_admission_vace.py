"""Repeat the existing controlled VACE scene through the actual guarded CLI."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(work,evidence,public):
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False);public.mkdir(parents=True,exist_ok=False)
    before=frozen();calls=[]
    for path in (Path(__file__),ROOT/'scripts/smoke_lama_local.py',ROOT/'scripts/create_lama_fixture.py'):
        shutil.copyfile(path,evidence/('executed-'+path.name))
    historical=ROOT/'workspace/vace-smoke-20261016-controlled-v2/summary.json'
    old=json.loads(historical.read_bytes());old_plan=old['inpainting'];generation=old_plan['generation']
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,
        'calls':calls,'historical_summary_sha256':sha(historical),'new_source_scenes':0,'natural_quality_accepted':False,
        'broad_quality_accepted':False,'full_capcut_parity':False,'generator_sha256':sha(Path(__file__))}
    env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),
        AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'),PYTHONDONTWRITEBYTECODE='1')
    def command(args,name,timeout=180,data=None):
        result=subprocess.run(list(map(str,args)),cwd=ROOT,env=env,capture_output=True,timeout=timeout,input=data)
        (evidence/(name+'.stdout.log')).write_bytes(result.stdout)
        (evidence/(name+'.stderr.log')).write_bytes(result.stderr)
        calls.append({'name':name,'command':list(map(str,args)),'exit_code':result.returncode,
            'stdout_sha256':sha(evidence/(name+'.stdout.log')),'stderr_sha256':sha(evidence/(name+'.stderr.log'))})
        save(evidence/'verification.json',record)
        if result.returncode:raise RuntimeError(name+' failed; see preserved logs')
        return result.stdout
    try:
        fixture=work/'fixture'
        command([sys.executable,'-B','-X','utf8',ROOT/'scripts/create_lama_fixture.py','--output-root',fixture],'fixture')
        if sha(fixture/'source.mov')!=old['source_sha256'] or sha(fixture/'mask.mov')!=old['mask_sha256']:
            raise ValueError('original VACE fixture bytes changed; do not mislabel as the same source')
        command([sys.executable,'-B','-X','utf8',ROOT/'scripts/smoke_lama_local.py',
            '--source',fixture/'source.mov','--mask',fixture/'mask.mov','--ground-truth',fixture/'ground-truth.npz',
            '--model',old['adapter']['model_path'],'--python',old['adapter']['executable'],
            '--evidence',next(a['path'] for a in old['adapter']['artifacts'] if a['role']=='evidence'),
            '--output-root',work/'actual','--engine','vace','--device','cuda','--execution-only',
            '--prompt',generation['prompt'],'--negative-prompt',generation['negative_prompt'],
            '--seed',generation['seed'],'--inference-steps',generation['inference_steps'],
            '--window-frames',generation['window_frames'],'--window-overlap',generation['window_overlap'],
            '--mask-grow',old_plan['inpainting']['grow'],'--model-max-edge',old_plan['inpainting']['model_max_edge'],
            '--repair-blend',old_plan['inpainting'].get('blend_mode','direct')],'actual-vace',timeout=3600)
        summary=json.loads((work/'actual/summary.json').read_bytes())
        shutil.copyfile(work/'actual/summary.json',evidence/'actual-summary.json')
        result=summary['inpainting'];execution=result['worker']['model_execution']
        from ai_ad_editor.cuda_admission import validate_execution
        validate_execution(execution,text_gpu_budget_mib=summary['adapter']['settings']['text_gpu_budget_mib'],
                           model_calls=result['worker']['metrics']['model_calls'])
        if not summary['independent_pixel_checks']['source_alpha_exact'] or summary['independent_pixel_checks']['outside_mask_changed_pixels']:
            raise ValueError('actual output pixel preservation failed')
        if summary['rights_expected_exit']!=7 or result['worker']['blocked_network_events']:
            raise ValueError('actual rights or offline execution scope changed')
        files={'source.mov':fixture/'source.mov','mask.mov':fixture/'mask.mov',
            'ground-truth.npz':fixture/'ground-truth.npz',
            'repaired.mov':work/'actual/project/assets/derived/repaired.mov',
            'repaired.mp4':work/'actual/project/renders/repaired.mp4',
            'contact.png':work/'actual/contact-sheet.png'}
        for name,path in files.items():shutil.copyfile(path,public/name)
        def decode(path):
            raw=command(['ffmpeg','-nostdin','-v','error','-i',path,'-map','0:v:0','-an','-fps_mode','passthrough',
                '-pix_fmt','rgba','-f','rawvideo','pipe:1'],'decode-'+path.stem)
            return np.frombuffer(raw,np.uint8).reshape(8,128,192,4)
        source=decode(fixture/'source.mov');repaired=decode(public/'repaired.mov');mask=decode(fixture/'mask.mov')
        truth=np.load(fixture/'ground-truth.npz',allow_pickle=False)['frames']
        selected=mask[...,3]>127
        if not np.array_equal(source[~selected],repaired[~selected]) or not np.array_equal(source[...,3],repaired[...,3]):
            raise ValueError('independent public decode preservation failed')
        pcm=[]
        for name in ('source','repaired'):
            value=command(['ffmpeg','-nostdin','-v','error','-i',public/(name+'.mov'),'-map','0:a:0','-vn',
                '-ar','48000','-ac','1','-f','s16le','pipe:1'],'pcm-'+name)
            pcm.append(value)
        if pcm[0]!=pcm[1]:raise ValueError('actual original audio PCM differs')
        font=ImageFont.load_default(size=14);panels=[]
        for index in range(8):
            frame=Image.new('RGB',(192*4,152),'#101722');draw=ImageDraw.Draw(frame)
            for column,(label,values) in enumerate([('Source',source),('Mask',mask),('Actual VACE',repaired),('Truth',truth)]):
                draw.text((column*192+5,3),label,fill='white',font=font)
                pixels=values[index,:,:,:3] if label!='Mask' else np.repeat(values[index,:,:,3:4],3,axis=2)
                frame.paste(Image.fromarray(pixels),(column*192,24))
            panels.append(frame)
        durations=[120,130]*4
        panels[0].save(public/'comparison.gif',save_all=True,append_images=panels[1:],duration=durations,loop=0,disposal=2)
        command(['ffmpeg','-nostdin','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size','768x152',
            '-framerate','8','-i','pipe:0','-an','-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',
            public/'comparison.mp4'],'comparison-encode',data=np.stack([np.asarray(p) for p in panels]).tobytes())
        command(['ffmpeg','-nostdin','-v','error','-i',public/'source.mov','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
            '-c:a','aac','-movflags','+faststart',public/'source.mp4'],'source-preview')
        provenance={'source_and_truth':'same original procedural VACE fixture; CC0-1.0',
            'model_output':'actual local VACE; technical evidence, not commercial-content acceptance',
            'frames':8,'fps':'8/1','duration_seconds':1,'display_rgb_only':True,
            'soft_alpha_proof':'original/repaired QTRLE MOV, not GIF/MP4',
            'gif_frame_durations_ms':durations,'continuous_playback_reviewed':False,'audio_listening_reviewed':False,
            'generator_sha256':sha(Path(__file__))}
        save(public/'provenance.json',provenance)
        if frozen()!=before:raise ValueError('product changed during actual VACE verification')
        reconstruction=summary['controlled_reconstruction']
        record.update(status='passed_actual_vace_resource_and_delivery_checks_quality_separate',
            frozen_after=frozen(),frames=8,fps='8/1',window_calls=result['worker']['metrics']['model_calls'],
            inference_steps=generation['inference_steps'],gpu_admission=execution['gpu_admission'],
            original_alpha_exact=True,outside_rgb_changed_pixels=0,audio_pcm_bytes=len(pcm[0]),audio_pcm_exact=True,
            audio_pcm_sha256='sha256:'+hashlib.sha256(pcm[0]).hexdigest(),
            controlled_reconstruction=reconstruction,controlled_psnr_at_least_30=reconstruction['masked_psnr_after_db']>=30,
            rgba_roundtrip_verified=result['rgba_roundtrip_verified'],runtime_network='disabled',
            commercial_publish_blocked=True,model_commercial_license_accepted=False,
            continuous_playback_reviewed=False,audio_listening_reviewed=False,
            files=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.iterdir()) if p.is_file()])
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(evidence/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('status','frames','window_calls','controlled_psnr_at_least_30')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','public'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(ROOT/'product/src'))
    run(**{key:value.resolve() for key,value in vars(args).items()})
