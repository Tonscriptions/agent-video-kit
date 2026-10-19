"""Exercise real registered local LaMa/VACE canvas extension and independent media checks."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import wave
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
PROMPT=('A static studio background, a softly lit blue-gray wall above a pale gray tabletop. '
        'Extend the same textures and straight horizontal tabletop edge. The camera stays fixed.')

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def background(np,x_offset=0,y_offset=0):
    y,x=np.indices((160,256));x=x+x_offset;y=y+y_offset
    wall=np.stack([90+.09*x+.07*y,115+.07*x+.05*y,145+.05*x+.03*y],axis=2)
    floor=np.stack([145+.08*x-.04*y,151+.06*x-.04*y,158+.04*x-.03*y],axis=2)
    pixels=np.where((y<90)[...,None],wall,floor)
    pixels+=2*np.sin(x[...,None]*.27)+1.5*np.cos(y[...,None]*.22)
    return np.clip(np.rint(pixels),0,255).astype(np.uint8)


def run(args):
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    for p in (args.work,args.evidence,args.public):p.mkdir(parents=True,exist_ok=False)
    before=frozen();calls=[];checks=[]
    shutil.copyfile(Path(__file__),args.evidence/'executed-generator.py')
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,
        'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'engine':args.engine,'blend':args.blend,'installed':bool(args.launcher),'calls':calls,'checks':checks,
        'temporal_context':args.temporal_context or 'none',
        'text_weight_budgets_mib':{'gpu':args.text_gpu_budget_mib,'cpu':args.text_cpu_budget_mib} if args.engine=='vace' else None,
        'generator_sha256':sha(Path(__file__)),'controlled_psnr_gate_db':30.,'natural_quality_accepted':False,
        'full_capcut_parity':False,'continuous_playback_reviewed':False,'audio_listening_reviewed':False}
    save(args.evidence/'verification.json',record)
    env=dict(os.environ);env.update(TEMP=str(args.work),TMP=str(args.work),TMPDIR=str(args.work),
        AI_AD_EDITOR_RUNTIME_DIR=str(args.work/'runtime'),PYTHONDONTWRITEBYTECODE='1')
    def command(argv,name,*,expected=0,data=None,binary=False,timeout=5400):
        started=time.monotonic();p=subprocess.run(list(map(str,argv)),cwd=ROOT,env=env,capture_output=True,input=data,timeout=timeout)
        out=args.evidence/(name+('.stdout.bin.gz' if binary else '.stdout.log'));err=args.evidence/(name+'.stderr.log')
        out.write_bytes(gzip.compress(p.stdout,mtime=0) if binary else p.stdout);err.write_bytes(p.stderr)
        calls.append({'name':name,'command':list(map(str,argv)),'exit_code':p.returncode,'expected_exit':expected,
            'seconds':time.monotonic()-started,'stdout':out.name,'stderr':err.name,'stdout_sha256':sha(out),
            'stderr_sha256':sha(err),'stdout_encoding':'gzip-raw' if binary else 'raw',
            'decoded_stdout_sha256':digest(p.stdout),'decoded_stdout_bytes':len(p.stdout)})
        save(args.evidence/'verification.json',record)
        if p.returncode!=expected:raise RuntimeError(name+' returned '+str(p.returncode)+'; see original logs')
        return p.stdout
    def check(name,passed):
        checks.append({'name':name,'passed':bool(passed)});save(args.evidence/'verification.json',record)
        if not passed:raise ValueError(name)
    prefix=([sys.executable,'-I','-S','-B','-X','utf8',str(args.launcher)] if args.launcher else
        [sys.executable,'-E','-B','-X','utf8','-c',
         'import sys;sys.path.insert(0,'+repr(str(ROOT/'product/src'))+');from ai_ad_editor.cli import main;raise SystemExit(main())'])
    def cli(argv,name,expected=0):return json.loads(command([*prefix,*argv],name,expected=expected))
    def decode(path,width,height,name):
        raw=command(['ffmpeg','-nostdin','-v','error','-i',path,'-map','0:v:0','-an','-pix_fmt','rgba',
            '-fps_mode','passthrough','-f','rawvideo','pipe:1'],name,binary=True)
        return np.frombuffer(raw,np.uint8).reshape(-1,height,width,4)
    try:
        if args.source_assets:
            for name in ('source.mov','source.wav','source-evidence.json'):
                shutil.copyfile(args.source_assets/name,args.public/name)
        else:
            frames=np.empty((8,128,192,4),np.uint8)
            for i in range(8):
                frames[i,...,:3]=background(np)[16:144,32:224];frames[i,...,3]=255
                frames[i,40:62,55+i*4:79+i*4,:3]=[185,50,35]
                frames[i,4:10,4:12,:3]=[20+i*25,220-i*12,80+i*15]
                frames[i,70:82,105:121,3]=np.arange(16,dtype=np.uint8)[None]*17
            t=np.arange(48000)/48000
            pcm=np.rint(np.stack([.2*np.sin(2*np.pi*440*t),.17*np.sin(2*np.pi*659.255*t)],axis=1)*32767).astype('<i2')
            with wave.open(str(args.public/'source.wav'),'wb') as wav:
                wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(48000);wav.writeframes(pcm.tobytes())
            command(['ffmpeg','-nostdin','-v','error','-n','-f','rawvideo','-pix_fmt','rgba','-s','192x128','-r','8','-i','pipe:0',
                '-i',args.public/'source.wav','-map','0:v:0','-map','1:a:0','-c:v','qtrle','-pix_fmt','argb','-c:a','pcm_s16le',
                '-t','1',args.public/'source.mov'],'create-source',data=frames.tobytes())
            save(args.public/'source-evidence.json',{'license_spdx':'CC0-1.0','creator':'Agent Video Kit original procedural fixture',
                'source':'analytic studio wall/tabletop, moving authored block, frame marker, alpha ramp and stereo sine waves',
                'generator_sha256':sha(Path(__file__)),'natural_footage':False,'frames':8,'fps':'8/1'})
        source=decode(args.public/'source.mov',192,128,'decode-source')
        check('eight_original_source_frames',len(source)==8)
        project=args.work/'project';cli(['project','init',str(project)],'project-init')
        ingested=cli(['media','ingest','--project',str(project),'--input',str(args.public/'source.mov'),
            '--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','commercial_ad',
            '--evidence',str(args.public/'source-evidence.json')],'source-ingest')['data']['asset']
        model_python=(args.model_python if args.model_python else
            Path(json.loads((ROOT/'workspace/vace-smoke-20261016-controlled-v2/summary.json').read_bytes())['adapter']['executable']))
        model=ROOT/'product/.runtime/models'/('inpainting/big-lama.pt' if args.engine=='lama' else 'generative/wan2.1-vace-1.3b')
        original_evidence=ROOT/'product/.runtime/models'/('inpainting/lama-evidence.json' if args.engine=='lama' else 'generative/vace-evidence.json')
        # Historical retrieval references stay in an exact out-of-project copy.
        # Portable runtime proof contains their hashes, preserving all license
        # states and weight identities without embedding network references.
        archived_evidence=args.evidence/'original-model-evidence.json'
        shutil.copyfile(original_evidence,archived_evidence);reference_fields=[]
        def offline_proof(value,path='$'):
            if isinstance(value,dict):return {k:offline_proof(v,path+'.'+k) for k,v in value.items()}
            if isinstance(value,list):return [offline_proof(v,path+'['+str(i)+']') for i,v in enumerate(value)]
            if isinstance(value,str) and re.search(r'(?i)\bhttps?://',value):
                identity=digest(value.encode('utf8'));reference_fields.append({'field':path,'original_value_sha256':identity})
                return {'historical_reference_sha256':identity,'role':'retrieval-history-only'}
            return value
        proof=offline_proof(json.loads(archived_evidence.read_bytes()))
        proof['original_evidence']={'path':str(archived_evidence),'sha256':sha(archived_evidence)}
        evidence=args.evidence/'local-model-evidence.json';save(evidence,proof)
        record['model_evidence']={'original_sha256':sha(archived_evidence),'local_sha256':sha(evidence),
            'historical_reference_fields':reference_fields,'license_status_changed':False}
        engine='torchscript-lama-local-v1' if args.engine=='lama' else 'diffusers-wan-vace-local-v1'
        registration=['media','adapter','register','--project',str(project),'--adapter-id','outpaint_local','--engine',engine,
            '--model-path',str(model),'--executable',str(model_python),'--evidence',str(evidence),
            '--device','cpu' if args.engine=='lama' else 'cuda']
        if args.engine=='vace':registration+=['--text-gpu-budget-mib',str(args.text_gpu_budget_mib),'--text-cpu-budget-mib',str(args.text_cpu_budget_mib)]
        adapter=cli(registration,'model-register')['data']['adapter']
        argv=['media','outpaint','--project',str(project),'--asset-id',ingested['id'],'--adapter-id','outpaint_local',
            '--derived-asset-id','expanded','--width','256','--height','160','--offset-x',str(args.offset_x),'--offset-y',str(args.offset_y),
            '--repair-blend',args.blend,'--model-max-edge','256','--apply','--track-id','track_video_1','--audio-track-id','track_audio_1',
            '--idempotency-key','real-expand']
        if args.engine=='vace':argv+=['--prompt',PROMPT,'--negative-prompt','text, watermark, camera motion, artifacts',
            '--seed','0','--inference-steps','30','--window-frames','5','--window-overlap','2']
        if args.temporal_context is not None:argv+=['--temporal-context',args.temporal_context]
        # Expensive VACE preflights repeat complete multi-GB hashes. Their control
        # paths are exercised by the separate portable tests and actual LaMa case.
        if args.engine=='lama':
            planned=cli([*argv,'--dry-run'],'dry-run');check('dry_run_planned_no_video',planned['status']=='planned' and not (project/'assets/derived/expanded.mov').exists())
            marker=args.work/'cancel';marker.write_text('cancel')
            cli([*argv,'--cancel-file',str(marker)],'pre-cancel',expected=8);marker.unlink()
        generated=cli(argv,'outpaint')['data'];result=generated['outpainting']
        save(args.evidence/'actual-result.json',generated)
        check('actual_model_loaded',result['worker']['model_loaded'] and result['worker']['metrics']['model_calls']>0)
        check('runtime_network_disabled',result['worker']['network']=='disabled' and not result['worker']['blocked_network_events'])
        if args.engine=='vace':
            sys.path.insert(0,str(ROOT/'product/src'))
            from ai_ad_editor.vace_model import validate_weight_reads
            validate_weight_reads(result['worker']['model_execution'].get('local_weight_reads'))
            check('all_six_native_weight_files_use_pread',True)
            if args.temporal_context=='previous':
                context=result['worker']['metrics']['temporal_context']
                check('actual_model_and_controller_conditioning_trace_equal',context['input_trace']==result['worker']['model_execution']['conditioning_trace'])
                check('actual_model_used_two_previous_emitted_frames',context['frames_conditioned']==2 and context['windows_conditioned']==1)
                check('context_prefix_not_blended_or_declared_ground_truth',result['worker']['metrics']['overlap_frames_blended']==0 and context['generated_context_is_ground_truth'] is False)
        check('rgba_encoding_roundtrip',result['rgba_roundtrip_verified'])
        output=project/generated['asset']['uri'];shutil.copyfile(output,args.public/'expanded.mov')
        decoded=decode(args.public/'expanded.mov',256,160,'decode-expanded')
        check('eight_output_frames',len(decoded)==8)
        x,y=args.offset_x,args.offset_y
        check('all_original_rgba_exact',np.array_equal(decoded[:,y:y+128,x:x+192],source))
        selected=np.ones((160,256),bool);selected[y:y+128,x:x+192]=False
        check('new_region_alpha_opaque',np.all(decoded[:,selected,3]==255))
        truth=np.empty_like(decoded);truth[...,:3]=background(np,32-x,16-y);truth[...,3]=255;truth[:,y:y+128,x:x+192]=source
        error=decoded[...,:3].astype(np.float64)-truth[...,:3].astype(np.float64)
        mse=float(np.square(error[:,selected]).mean());psnr=100. if mse==0 else float(10*np.log10(255**2/mse))
        quality={'scope':'only the newly generated region of this procedural studio fixture','pixels_per_frame':int(selected.sum()),
            'psnr_db':psnr,'predeclared_gate_db':30.,'passed':psnr>=30.,
            'consecutive_error_delta_mae':float(np.abs(np.diff(error,axis=0))[:,selected].mean()),'natural_quality_accepted':False}
        np.savez_compressed(args.public/'ground-truth.npz',frames=truth)
        pcm=[];pts=[]
        for name,path in (('source',args.public/'source.mov'),('expanded',args.public/'expanded.mov')):
            pcm.append(command(['ffmpeg','-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-ac','2','-ar','48000',
                '-f','f32le','pipe:1'],'pcm-'+name,binary=True))
            p=json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',path],'pts-'+name))
            stream=p['streams'][0];pts.append([Fraction(f['best_effort_timestamp'])*Fraction(stream['time_base']) for f in p['frames']])
        check('all_stereo_pcm_samples_exact',pcm[0]==pcm[1] and len(pcm[0])==48000*2*4)
        check('source_and_output_every_pts_exact',pts[0]==pts[1]==[Fraction(i,8) for i in range(8)])
        cli(['validate','--project',str(project)],'validate');cli(['policy','audit','--project',str(project)],'policy')
        cli(['rights','check','--project',str(project)],'rights',expected=7)
        replay=cli(argv,'idempotent-replay');check('idempotent_replay_has_no_new_model_execution',any(w['code']=='IDEMPOTENT_REPLAY' for w in replay['warnings']))
        manifest=project/'project.json';payload=json.loads(manifest.read_bytes());payload['settings']['canvas'].update(width=256,height=160)
        payload['settings']['timebase']['display_fps']={'num':8,'den':1};save(manifest,payload)
        video=project/'renders/expanded.mp4';render=cli(['render','--project',str(project),'--output',str(video),'--profile','custom','--width','256','--height','160','--crf','12'],'render')
        shutil.copyfile(Path(render['data']['manifest']),args.evidence/'render-manifest.json')
        shutil.copyfile(video,args.public/'expanded.mp4')
        cli(['quality','check','--project',str(project),'--input',str(video),'--width','256','--height','160','--require-audio'],'quality')
        package=args.public/'project.aevpkg.zip';cli(['convert','export','--project',str(project),'--target-format','package','--output',str(package)],'package-export')
        target=args.work/'imported';cli(['convert','import','--input',str(package),'--output',str(target)],'package-import')
        restored=json.loads((target/'project.json').read_bytes());restored_asset=next(a for a in restored['assets'] if a['id']=='expanded')
        check('packaged_output_bytes_exact',sha(target/restored_asset['uri'])==sha(output))
        check('editable_recipe_package_roundtrip',restored_asset['source']['outpainting']==generated['asset']['source']['outpainting'])
        cli(['validate','--project',str(target)],'import-validate')
        library=args.work/'fragment-library';request=args.work/'fragment.json'
        save(request,{'id':'expanded','version':1,'sequence_id':'seq_main'})
        cli(['fragment','save','--project',str(project),'--library',str(library),'--input',str(request)],'fragment-save')
        cli(['fragment','inspect','--library',str(library),'--id','expanded','--version','1'],'fragment-inspect')
        fragment_target=args.work/'fragment-target';cli(['project','init',str(fragment_target)],'fragment-target-init')
        target_project=json.loads((fragment_target/'project.json').read_bytes());target_project['settings']=payload['settings']
        save(fragment_target/'project.json',target_project)
        save(request,{'id':'expanded','version':1,'sequence_id':'seq_main','track_id':'track_video_1',
                      'at_tick':0,'instance_id':'real-reuse'})
        fragargv=['fragment','apply','--project',str(fragment_target),'--library',str(library),'--input',str(request)]
        cli([*fragargv,'--dry-run'],'fragment-apply-plan');cli(fragargv,'fragment-apply')
        rebound_project=json.loads((fragment_target/'project.json').read_bytes())
        rebound=next(a for a in rebound_project['assets'] if a.get('source',{}).get('outpainting'))
        rebound_recipe=rebound['source']['outpainting'];old_recipe=generated['asset']['source']['outpainting']
        check('fragment_recipe_source_rebound',rebound_recipe['source_asset_id']!=old_recipe['source_asset_id'] and
              rebound_recipe['source_sha256']==old_recipe['source_sha256'] and rebound_recipe['geometry']==old_recipe['geometry'] and
              rebound_recipe['sha256']!=old_recipe['sha256'])
        check('fragment_output_bytes_exact',sha(fragment_target/rebound['uri'])==sha(output))
        cli(['validate','--project',str(fragment_target)],'fragment-validate')
        cli(['policy','audit','--project',str(fragment_target)],'fragment-policy')
        cli(['rights','check','--project',str(fragment_target)],'fragment-rights',expected=7)
        pads=np.full_like(decoded,127);pads[...,3]=255;pads[:,y:y+128,x:x+192]=source
        panels=[];font=ImageFont.load_default(size=14)
        checker=np.where((np.indices((160,256)).sum(axis=0)//12%2)[...,None],205,155).astype(np.float32)
        for i in range(8):
            panel=Image.new('RGB',(768,184),'#101722');draw=ImageDraw.Draw(panel)
            mode_label=(' '+args.temporal_context) if args.temporal_context else ''
            for j,(title,values) in enumerate([('Input pad / no generation',pads),('Actual '+args.engine+mode_label+' '+args.blend,decoded),('Controlled truth',truth)]):
                alpha=values[i,...,3:4].astype(np.float32)/255
                rgb=np.rint(values[i,...,:3]*alpha+checker*(1-alpha)).astype(np.uint8)
                panel.paste(Image.fromarray(rgb),(j*256,24));draw.text((j*256+4,4),title,fill='white',font=font)
            panels.append(panel)
        panels[0].save(args.public/'comparison.gif',save_all=True,append_images=panels[1:],duration=[120,130]*4,loop=0,disposal=2)
        for index in (0,3,4,7):panels[index].save(args.public/('frame-'+str(index)+'.png'))
        contact=Image.new('RGB',(768,832),'#101722');draw=ImageDraw.Draw(contact)
        for row,index in enumerate((0,3,4,7)):
            draw.text((4,row*208+4),'Frame '+str(index)+' / PTS '+str(Fraction(index,8))+' s',fill='white',font=font)
            contact.paste(panels[index],(0,row*208+24))
        contact.save(args.public/'contact-sheet.png')
        command(['ffmpeg','-nostdin','-v','error','-i',args.public/'source.mov','-c:v','libx264','-pix_fmt','yuv420p','-crf','14',
            '-c:a','aac','-movflags','+faststart',args.public/'source.mp4'],'source-preview')
        source_info=json.loads((args.public/'source-evidence.json').read_bytes())
        save(args.public/'provenance.json',{'source_license':'CC0-1.0','source_generator_sha256':source_info['generator_sha256'],
            'model_result':'actual offline '+engine,'commercial_model_license_accepted':False,'frames':8,'fps':'8/1','duration_seconds':1,
            'temporal_context':args.temporal_context or 'none',
            'gif_durations_ms':[120,130]*4,'gif_has_audio':False,'mp4_is_lossy_preview':True,'quality':quality,
            'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in args.public.iterdir() if p.is_file()}})
        save(args.evidence/'actual-result.json',generated)
        after=frozen();check('frozen_product_unchanged',before==after)
        record.update(status='passed_execution_quality_separate',frozen_after=after,frozen_equal=before==after,
            quality=quality,frames=8,stereo_sample_frames=48000,cli_calls=len([c for c in calls if c['command'][:len(prefix)]==prefix]),
            model_calls=result['worker']['metrics']['model_calls'],gpu_admission=result['worker'].get('model_execution',{}).get('gpu_admission'),
            decoded_rgba_sha256=digest(decoded.tobytes()),decoded_pcm_sha256=digest(pcm[1]),
            files={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in args.public.iterdir() if p.is_file()})
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
    finally:
        record['frozen_after']=frozen();record['frozen_equal']=before==record['frozen_after']
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(args.evidence/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('status','engine','blend','frames','model_calls','cli_calls','quality')},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','public'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--engine',choices=['lama','vace'],required=True);parser.add_argument('--blend',choices=['direct','harmonic'],default='direct')
    parser.add_argument('--launcher',type=Path);parser.add_argument('--source-assets',type=Path)
    parser.add_argument('--model-python',type=Path,help='existing native model Python; historical local receipt is the default')
    parser.add_argument('--temporal-context',choices=['none','previous'],default=None)
    parser.add_argument('--text-gpu-budget-mib',type=int,default=7168)
    parser.add_argument('--text-cpu-budget-mib',type=int,default=8192)
    parser.add_argument('--offset-x',type=int,default=32);parser.add_argument('--offset-y',type=int,default=16)
    args=parser.parse_args()
    if args.temporal_context is not None and args.engine!='vace':parser.error('--temporal-context requires --engine vace')
    for name in ('work','evidence','public','launcher','source_assets','model_python'):
        if getattr(args,name) is not None:setattr(args,name,getattr(args,name).resolve())
    run(args)
