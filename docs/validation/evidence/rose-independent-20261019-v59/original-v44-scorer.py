"""Native, offline FGT candidate measurement against a predeclared contract.

Requires explicitly acquired, pinned local upstream sources and author weights.
No product adapter is registered. Private natural pixels never enter docs.
"""
from __future__ import annotations
import argparse
import difflib
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from smoke_fragments import frozen, save, sha


def command(args, *, data=None, timeout=120):
    result = subprocess.run(list(map(str, args)), input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
    return result.stdout


def decode(path, frames, height, width):
    import numpy as np
    raw = command(['ffmpeg','-v','error','-i',path,'-an','-pix_fmt','rgba',
                   '-fps_mode','passthrough','-f','rawvideo','pipe:1'])
    return np.frombuffer(raw, np.uint8).reshape(frames, height, width, 4).copy()


def encode(path, rgba, *, audio=None):
    n, h, w, _ = rgba.shape
    args = ['ffmpeg','-nostdin','-v','error','-f','rawvideo','-pix_fmt','rgba',
            '-video_size',f'{w}x{h}','-framerate','8','-i','pipe:0']
    if audio:
        args += ['-i',str(audio),'-map','0:v:0','-map','1:a:0?','-c:a','pcm_s16le']
    args += ['-c:v','qtrle','-pix_fmt','argb','-video_track_timescale','8','-t',str(n/8),str(path)]
    command(args, data=rgba.tobytes())
    import numpy as np
    actual = decode(path, n, h, w)
    if not np.array_equal(actual, rgba):
        raise RuntimeError('FGT_FINAL_LOSSLESS_ROUNDTRIP_FAILED')
    probe = json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_frames',
                               '-show_entries','frame=pts_time','-of','json',path]))
    from fractions import Fraction
    if [Fraction(x['pts_time']) for x in probe['frames']] != [Fraction(i,8) for i in range(n)]:
        raise RuntimeError('FGT_OUTPUT_PTS_MISMATCH')


def prepare_source(work, upstream, weights):
    source = work/'source'
    shutil.copytree(upstream/'source', source)
    target = source/'tool/video_inpainting.py'
    before = target.read_text(encoding='utf-8')
    replacements = [
        ('import cvbase\n', '# Optional cvbase visualization is not used by this research invocation.\n'),
        ('if k in args:', 'if hasattr(args, k):'),
        ('            except:\n', "            except Exception as exc:\n                raise RuntimeError('FGT_POISSON_STAGE_FAILED') from exc\n"),
        ('    imageio.mimwrite(\n        os.path.join(args.outroot, "result.mp4"), comp_frames, fps=30, quality=8\n    )',
         '    np.save(os.path.join(args.outroot, "raw-result.npy"), np.stack(comp_frames), allow_pickle=False)')]
    after = before
    for old, new in replacements:
        if after.count(old) != 1:
            raise RuntimeError('FGT_PATCH_CONTEXT_MISMATCH: ' + old)
        after = after.replace(old, new)
    target.write_text(after, encoding='utf-8', newline='\n')
    patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                       fromfile='upstream/tool/video_inpainting.py', tofile='research/tool/video_inpainting.py'))
    (work/'compatibility.patch').write_text(patch, encoding='utf-8', newline='\n')
    checkpoints = {}
    for label, model, config in [('lafc','lafc.pth.tar','LAFC_config.yaml'),('fgt','fgt.pth.tar','FGT_config.yaml')]:
        directory = work/(label+'-checkpoint'); directory.mkdir()
        for name in (model, config):
            shutil.copyfile(weights/name, directory/name)
        checkpoints[label] = directory
    # Explicit equivalent output selection: caller supplied the already grown mask.
    options = work/'options.yaml'
    options.write_text('mode: object_removal\nconsistencyThres: 5\nalpha: 0.1\nflow_mask_dilates: 12\nframe_dilates: 0\ngpu: 0\n', encoding='ascii')
    return source, checkpoints, options


def public_fixture():
    import numpy as np
    n, h, w = 32, 240, 432
    yy, xx = np.mgrid[:h,:w]
    truth = np.empty((n,h,w,4), np.uint8); truth[:,:,:,3] = 255
    selected = np.zeros((n,h,w), bool)
    for t in range(n):
        # Separate surfaces: rigid +2 and -3 horizontal pixels/frame.
        x = np.where(yy<144, xx-2*t, xx+3*t)
        tiles = ((x//12 + yy//12)%2)*24
        rgb = np.stack([110+40*np.sin(x*.13)+18*np.cos(yy*.17)+tiles,
                        120+30*np.sin(x*.13+1)+24*np.cos(yy*.11),
                        135+36*np.cos(x*.09)+22*np.sin(yy*.13)-tiles], axis=2)
        truth[t,:,:,:3] = np.rint(np.clip(rgb,0,255)).astype(np.uint8)
        left = 192 + round(6*np.sin(t*.2))
        selected[t,80:200,left:left+48] = True
    source = truth.copy()
    for t in range(n):
        source[t,:,:,:3][selected[t]] = [230,35,65]
    return source, selected, truth


def scores(result, truth, selected):
    import numpy as np
    error = result[:,:,:,:3].astype(np.float64)-truth[:,:,:,:3].astype(np.float64)
    rows = []
    for label, lo, hi, dx in [('upper',0,144,2),('lower',144,240,-3),('overall',0,240,None)]:
        region = selected.copy(); region[:,:lo] = False; region[:,hi:] = False
        mse = float(np.mean(error[region]**2))
        psnr = 10*np.log10(255.**2/mse) if mse else 999.
        if dx is None:
            previous = np.concatenate([np.roll(error[:-1,:144],2,axis=2),np.roll(error[:-1,144:],-3,axis=2)],axis=1)
            old_mask = np.concatenate([np.roll(selected[:-1,:144],2,axis=2),np.roll(selected[:-1,144:],-3,axis=2)],axis=1)
        else:
            previous = np.roll(error[:-1],dx,axis=2)
            old_mask = np.roll(selected[:-1],dx,axis=2)
        overlap = region[1:] & old_mask
        temporal = float(np.mean(np.abs((error[1:]-previous)[overlap])))
        rows.append({'region':label,'selected_pixels':int(region.sum()),'masked_mse':mse,
                     'masked_psnr_db':float(psnr),'known_motion_residual_mae_rgb':temporal,
                     'temporal_samples_rgb':int(overlap.sum())*3})
    return rows


def lama(source, selected, model_path):
    import numpy as np
    import torch
    sys.path.insert(0,str(ROOT/'product/src'))
    from ai_ad_editor.inpainting_frames import repair_frame
    from ai_ad_editor.local_inpainting import normalize_options
    with model_path.open('rb') as handle:
        model = torch.jit.load(handle,map_location='cpu').to('cuda').eval()
    calls = 0; started = time.monotonic()
    def infer(image, mask):
        nonlocal calls
        calls += 1
        with torch.inference_mode():
            return model(torch.from_numpy(image).to('cuda'),torch.from_numpy(mask).to('cuda')).cpu().numpy()
    output = []
    for frame, mask in zip(source, selected):
        rgba = np.full(frame.shape,255,np.uint8); rgba[:,:,3] = mask.astype(np.uint8)*255
        value, _ = repair_frame(frame,rgba,channel='alpha',infer=infer,budget=512*1024**2,
                               options=normalize_options(grow=0,context=1024,model_max_edge=512))
        output.append(value)
    del model
    gc.collect(); torch.cuda.empty_cache()
    return np.stack(output), {'model_calls':calls,'seconds':time.monotonic()-started,
                             'model_sha256':sha(model_path),'grow':0,'context':1024,'model_max_edge':512,'blend':'direct'}


def run(case, work, audit):
    os.environ['AI_AD_EDITOR_RUNTIME_DIR']=str(ROOT/'product/.runtime')
    sys.path.insert(0,str(ROOT/'product/src'))
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.rvm_worker import install_network_guard
    configure_local_runtime()
    events=[]; install_network_guard(events)
    import numpy as np
    from PIL import Image, ImageFilter
    if work.exists(): raise RuntimeError('fresh work directory required')
    work.mkdir(parents=True)
    before = frozen(); save(work/'product-before.json',before)
    request = None
    try:
        if case=='public':
            source, selected, truth = public_fixture(); audio = None; historical = None
            np.save(work/'independent-truth.npy',truth,allow_pickle=False)
            baseline, detail = lama(source,selected,ROOT/'product/.runtime/models/inpainting/big-lama.pt')
            save(work/'lama.json',detail); np.save(work/'lama.npy',baseline,allow_pickle=False)
            encode(work/'source.mov',source); encode(work/'truth.mov',truth); encode(work/'lama.mov',baseline)
        else:
            project = ROOT/'product/.runtime/mask-edit-natural-20261018/project'
            content = json.loads((project/'project.json').read_text(encoding='utf-8'))
            assets = {x['id']:project/x['uri'] for x in content['assets']}
            source=decode(assets['source'],32,288,512); raw_mask=decode(assets['fixed'],32,288,512)
            selected=np.stack([np.asarray(Image.fromarray(frame[:,:,3]).filter(ImageFilter.MaxFilter(9)))>127 for frame in raw_mask])
            baseline=decode(assets['repaired'],32,288,512); audio=assets['source']; truth=None
            historical={'record':'docs/validation/evidence/mask-edits-20261018/natural.json',
                        'source_sha256':sha(assets['source']),'raw_mask_sha256':sha(assets['fixed']),
                        'lama_output_sha256':sha(assets['repaired']),'new_lama_model_calls':0}
        np.save(work/'input.npy',source,allow_pickle=False)
        np.save(work/'effective-selection.npy',selected,allow_pickle=False)
        for directory in ('frames','masks','output'): (work/directory).mkdir()
        for i,(frame,mask) in enumerate(zip(source,selected)):
            Image.fromarray(frame[:,:,:3]).save(work/f'frames/{i:04}.png')
            Image.fromarray(mask.astype(np.uint8)*255).save(work/f'masks/{i:04}.png')
        upstream = audit/'hitachinsk__FGT'; weights = audit/'fgt-weights'
        src, checkpoints, options = prepare_source(work,upstream,weights)
        models=[weights/'raft-things.pth',checkpoints['lafc']/'lafc.pth.tar',checkpoints['fgt']/'fgt.pth.tar']
        paths=[*src.rglob('*.py'),*src.rglob('LICENSE'),*models,options,
               *checkpoints['lafc'].glob('*.yaml'),*checkpoints['fgt'].glob('*.yaml'),
               *(work/'frames').glob('*.png'),*(work/'masks').glob('*.png'),
               ROOT/'research/temporal-neural/fgt_worker.py']
        request={'project_root':str(ROOT),'source_root':str(src),'options_path':str(options),
                 'frames_path':str(work/'frames'),'masks_path':str(work/'masks'),'output_path':str(work/'output'),
                 'model_files':list(map(str,models)),'lafc_root':str(checkpoints['lafc']),'fgt_root':str(checkpoints['fgt']),
                 'frames':len(source),'height':source.shape[1],'width':source.shape[2],
                 'frozen_files':[{'path':str(p),'sha256':sha(p)} for p in sorted(paths)],
                 'response':str(work/'worker-response.json'),'truth_read_by_worker':False}
        save(work/'request.json',request)
        print(json.dumps({'case':case,'stage':'starting-native-fgt-worker','frames':len(source)}),flush=True)
        with (work/'worker.log').open('wb') as log:
            process=subprocess.run([sys.executable,'-I','-B','-X','utf8',str(ROOT/'research/temporal-neural/fgt_worker.py'),
                                    str(work/'request.json')],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        worker=json.loads((work/'worker-response.json').read_text(encoding='utf-8'))
        if process.returncode or worker['status']!='succeeded':
            raise RuntimeError('FGT_WORKER_FAILED: '+worker.get('error','unknown'))
        raw=np.load(work/'output/raw-result.npy',allow_pickle=False)
        raw_outside=int(np.count_nonzero(np.any(raw!=source[:,:,:,:3],axis=3)&~selected))
        result=source.copy(); result[:,:,:,:3][selected]=raw[selected]
        outside=int(np.count_nonzero(np.any(result[:,:,:,:3]!=source[:,:,:,:3],axis=3)&~selected))
        if outside or not np.array_equal(result[:,:,:,3],source[:,:,:,3]): raise RuntimeError('FGT_COMPOSITION_INTEGRITY_FAILED')
        np.save(work/'final.npy',result,allow_pickle=False)
        encode(work/'final.mov',result,audio=audio)
        audio_record=None
        if audio:
            pcm=[command(['ffmpeg','-v','error','-i',p,'-vn','-ar','48000','-ac','2','-t','4','-f','s16le','pipe:1']) for p in (audio,work/'final.mov')]
            if pcm[0]!=pcm[1]: raise RuntimeError('FGT_AUDIO_MISMATCH')
            audio_record={'decoded_pcm_bytes':len(pcm[0]),'identical':True,'sha256':hashlib.sha256(pcm[0]).hexdigest()}
        record={'case':case,'status':'execution_verified_quality_unaccepted','frames':len(source),
                'runner_sha256':sha(Path(__file__)),'worker_sha256':sha(ROOT/'research/temporal-neural/fgt_worker.py'),
                'contract_sha256':sha(ROOT/'docs/specs/开源时序修复候选核验契约_v0.1_2026-10-18.md'),
                'parent_network':'disabled','parent_blocked_network_events':events,
                'width':source.shape[2],'height':source.shape[1],'fps':'8/1','duration_seconds':len(source)/8,
                'raw_upstream_outside_selection_changed_pixels':raw_outside,
                'final_outside_selection_changed_pixels':outside,'original_alpha_exact':True,
                'rgba_roundtrip_exact':True,'every_pts_exact':True,'worker':worker,'audio':audio_record,
                'historical_lama':historical,'product_integrated':False,'natural_quality_accepted':False,
                'continuous_playback_reviewed':False,'audio_listening_reviewed':False}
        if truth is not None:
            record['fgt_scores']=scores(result,truth,selected); record['lama_scores']=scores(baseline,truth,selected)
            gates=[]
            for fg,la in zip(record['fgt_scores'],record['lama_scores']):
                gates.append({'region':fg['region'],'psnr_30_db':fg['masked_psnr_db']>=30,
                              'psnr_no_worse_than_lama':fg['masked_psnr_db']>=la['masked_psnr_db'],
                              'motion_residual_mae_at_most_5':fg['known_motion_residual_mae_rgb']<=5,
                              'motion_residual_no_worse_than_lama':fg['known_motion_residual_mae_rgb']<=la['known_motion_residual_mae_rgb']})
            record['quality_gates']=gates
            record['controlled_quality_passed']=all(all(v for k,v in gate.items() if k!='region') for gate in gates)
        save(work/'verification.json',record)
        print(json.dumps({k:v for k,v in record.items() if k in {'case','status','quality_gates','fgt_scores','lama_scores'}}),flush=True)
    except Exception as error:
        save(work/'failure.json',{'case':case,'status':'failed','error':type(error).__name__+': '+str(error),
                                  'traceback':traceback.format_exc(),
                                  'worker_response_exists':bool(request and Path(request['response']).is_file())})
        raise
    finally:
        after=frozen(); save(work/'product-after.json',after)
        if before!=after: raise RuntimeError('PRODUCTION_BYTES_CHANGED_DURING_RESEARCH')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=['public','natural'],required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--audit',type=Path,default=ROOT/'product/.runtime/temporal-model-audit-20261018')
    args=parser.parse_args()
    run(args.case,args.work.resolve(),args.audit.resolve())
