"""Generate licensed local video and exercise real CPU face CLI operations."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import traceback
import wave

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def owned_direct_children(parent_pid):
    """Read native ancestry only; never inspect/terminate unrelated processes."""
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),
                  ('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),
                  ('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',wintypes.LONG),('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];api.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    api.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)];api.Process32NextW.argtypes=api.Process32FirstW.argtypes
    api.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=api.CreateToolhelp32Snapshot(2,0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    children=[]
    try:
        entry=Entry();entry.dwSize=ctypes.sizeof(entry)
        ok=api.Process32FirstW(handle,ctypes.byref(entry))
        while ok:
            if entry.th32ParentProcessID == parent_pid:
                children.append(int(entry.th32ProcessID))
            ok=api.Process32NextW(handle,ctypes.byref(entry))
    finally:
        api.CloseHandle(handle)
    return children


def run(args):
    import numpy as np
    import cv2
    for key in ('work','evidence','public','upstream','image','controller_python'):
        setattr(args,key,getattr(args,key).resolve())
    if args.installed:
        args.installed=args.installed.resolve()
    sys.path.insert(0,str(ROOT/'product/src'))
    sys.path.insert(0,str(ROOT/'scripts'))
    from run_frozen_regression import frozen
    for path in (args.work,args.evidence,args.public):
        path.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(Path(__file__),args.evidence/'executed-generator.py')
    receipt = {'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
               'frozen_before':frozen(),'calls':[],'checks':[],'quality_accepted':False,'full_capcut_parity':False,
               'continuous_playback_reviewed':False,'audio_listening_reviewed':False,'mediapipe_executed':False}
    receipt['installed']=str(args.installed) if args.installed else None
    save(args.evidence/'verification.json',receipt)
    env = dict(os.environ)
    env.update(TEMP=str(args.work),TMP=str(args.work),TMPDIR=str(args.work),AI_AD_EDITOR_RUNTIME_DIR=str(args.work/'runtime'),PYTHONDONTWRITEBYTECODE='1')
    def check(name,condition):
        receipt['checks'].append({'name':name,'passed':bool(condition)});save(args.evidence/'verification.json',receipt)
        if not condition:
            raise ValueError(name)
    def command(command,name,*,data=None,expected=0,binary=False,cancel_after_child=None):
        started = time.monotonic()
        cancellation={}
        if cancel_after_child is None:
            result = subprocess.run(list(map(str,command)),cwd=ROOT,env=env,input=data,capture_output=True,timeout=900)
        else:
            process=subprocess.Popen(list(map(str,command)),cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            def cancel_owned_worker():
                while process.poll() is None:
                    children=owned_direct_children(process.pid)
                    if children:
                        cancellation.update(cli_pid=process.pid,observed_owned_children=children)
                        time.sleep(.05)
                        cancel_after_child.write_text('cancel',encoding='utf-8')
                        cancellation['written']=True
                        return
                    time.sleep(.02)
            monitor=threading.Thread(target=cancel_owned_worker,daemon=True);monitor.start()
            out,err=process.communicate(timeout=900);monitor.join(timeout=2)
            result=subprocess.CompletedProcess(command,process.returncode,out,err)
        stdout,stderr = args.evidence/(name+'.stdout.log'),args.evidence/(name+'.stderr.log')
        if not binary:
            stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        receipt['calls'].append({'name':name,'command':list(map(str,command)),'exit_code':result.returncode,'expected_exit':expected,
                                'seconds':time.monotonic()-started,'stdout_bytes':len(result.stdout),
                                'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
                                'stdout_file':stdout.name if not binary else None,'stderr_file':stderr.name,'stderr_sha256':sha(stderr),
                                'cancellation_trigger':cancellation or None})
        save(args.evidence/'verification.json',receipt)
        if result.returncode != expected:
            raise RuntimeError(name+' returned '+str(result.returncode)+'; see exact logs')
        return result.stdout
    prefix = [args.controller_python,'-E','-B','-X','utf8','-c',
              'import sys;sys.path.insert(0,'+repr(str(ROOT/'product/src'))+');from ai_ad_editor.cli import main;raise SystemExit(main())']
    if args.installed:
        prefix=[args.controller_python,'-I','-S','-B','-X','utf8',args.installed/'run.py']
    def cli(argv,name,expected=0,**kwargs):
        return json.loads(command([*prefix,*argv],name,expected=expected,**kwargs))
    def decoded(path,name):
        raw = command(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',path,
                       '-map','0:v:0','-an','-pix_fmt','rgba','-fps_mode','passthrough','-f','rawvideo','pipe:1'],name,binary=True)
        return np.frombuffer(raw,np.uint8).reshape(-1,512,512,4)
    try:
        fixture = cv2.imread(str(args.image),cv2.IMREAD_COLOR)
        check('existing_local_nasa_fixture_512_rgb',fixture is not None and fixture.shape == (512,512,3))
        shutil.copyfile(args.image,args.public/'original-nasa.png')
        origins = {'credit':'NASA / Eileen Collins portrait; fixture distributed by scikit-image',
                   'source_sha256':sha(args.image),'fixture_documentation':'https://scikit-image.org/docs/0.25.x/api/skimage.data.html#skimage.data.astronaut',
                   'original_nasa_archive_reference':'https://flic.kr/p/r9qvLn',
                   'usage':'Technical geometry/retouch demonstration; no endorsement or advertisement using the subject.'}
        save(args.public/'source-origin.json',origins)
        proof = args.work/'source-proof.json'
        save(proof,{'kind':'local-existing-public-domain-nasa-fixture','source_sha256':sha(args.image),'origin_record_sha256':sha(args.public/'source-origin.json')})
        models = args.upstream/'models'
        model_proof = args.work/'model-proof.json'
        save(model_proof,{'upstream_commit':'50c09741897010faad721a218b2bbe14ecad6251','license_spdx':'BSD-2-Clause',
                          'license_sha256':sha(args.upstream/'LICENSE'),'readme_sha256':sha(args.upstream/'README.md'),
                          'models':[{k:v for k,v in {'name':p.name,'sha256':sha(p),'bytes':p.stat().st_size}.items()} for p in sorted(models.glob('*.onnx'))]})
        y,x = np.indices((512,512));frames=[]
        for index in range(24):
            if 10 <= index < 14:
                rgb = np.empty((512,512,3),np.uint8);rgb[:]=[42,67,91]
            else:
                shift = index*.7 if index < 10 else (23-index)*.7
                matrix = np.array([[1,0,shift],[0,1,0]],np.float32)
                bgr = cv2.warpAffine(fixture,matrix,(512,512),borderMode=cv2.BORDER_REFLECT_101)
                rgb = bgr[:,:,::-1]
            alpha = np.full((512,512),255,np.uint8)
            alpha[-32:,:] = ((x[-32:,:]+y[-32:,:]+index)%256).astype(np.uint8)
            frames.append(np.dstack((rgb,alpha)))
        original = np.asarray(frames,np.uint8)
        wav = args.public/'source.wav'
        samples = np.arange(144000)/48000
        audio = np.stack((np.sin(2*np.pi*220*samples),np.sin(2*np.pi*330*samples)),axis=1)
        audio = np.rint(audio*1000).astype('<i2')
        with wave.open(str(wav),'wb') as stream:
            stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(48000);stream.writeframes(audio.tobytes())
        source = args.public/'source.mov'
        command(['ffmpeg','-nostdin','-v','error','-f','rawvideo','-pixel_format','rgba','-video_size','512x512',
                 '-framerate','8','-i','pipe:0','-i',wav,'-map','0:v:0','-map','1:a:0','-c:v','ffv1',
                 '-level','3','-pix_fmt','bgra','-c:a','pcm_s16le',source],'generate-source',data=original.tobytes())
        check('encoded_source_equals_all_24_generated_rgba_frames',np.array_equal(decoded(source,'source-decode'),original))
        project = args.work/'project'
        cli(['project','init',str(project)],'project-init')
        ingested = cli(['media','ingest','--project',project,'--input',source,'--license-spdx','LicenseRef-NASA-Public-Domain',
                        '--permitted-use','internal','--evidence',proof],'source-ingest')['data']['asset']
        cli(['face','adapter','register','--project',project,'--adapter-id','face_local','--model-path',models,
             '--python-executable',sys.executable,'--threads','2','--evidence',model_proof,'--license-spdx','BSD-2-Clause','--creator','Emiliana'],'adapter-register')
        cli(['face','adapter','inspect','--project',project,'--adapter-id','face_local'],'adapter-inspect')
        scan_args = ['face','scan','--project',project,'--asset-id',ingested['id'],'--adapter-id','face_local',
                     '--max-frames','24','--cut-frame','10','--cut-frame','14','--output','validation/face.json']
        cli([*scan_args,'--dry-run'],'scan-dry-run')
        check('scan_dry_run_writes_no_report',not (project/'validation/face.json').exists())
        scan = cli(scan_args,'scan')
        report = json.loads((project/'validation/face.json').read_text(encoding='utf-8'))
        shutil.copyfile(project/'validation/face.json',args.evidence/'scan-report.json')
        observed = report['response']['frames']
        check('24_real_detector_forwards',scan['data']['detector_forwards'] == 24)
        check('24_real_frames_no_missing_or_repeated_indices',[f['frame_index'] for f in observed] == list(range(24)))
        check('blank_frames_keep_no_borrowed_landmarks',all(not f['faces'] for f in observed[10:14]))
        before = {f['face_id'] for row in observed[:10] for f in row['faces']}
        after = {f['face_id'] for row in observed[14:] for f in row['faces']}
        check('cut_and_absence_reset_track_ids',bool(before) and bool(after) and not before & after)
        base = ['face','retouch','--project',project,'--asset-id',ingested['id'],'--python-executable',sys.executable]
        neutral = cli([*base,'--report','validation/face.json','--all-detected','--derived-asset-id','neutral'],'retouch-neutral')
        neutral_path = Path(neutral['data']['output'])
        check('neutral_output_equals_all_original_rgba',np.array_equal(decoded(neutral_path,'neutral-decode'),original))
        options = [*base,'--report','validation/face.json','--all-detected','--skin-smooth','.6','--exposure-ev','.25',
                   '--face-slim','.45','--eye-enlarge','.5','--derived-asset-id','retouched','--idempotency-key','local-face-sample']
        edited = cli(options,'retouch-controls')
        edited_path = Path(edited['data']['output'])
        pixels = decoded(edited_path,'retouched-decode')
        check('all_original_alpha_samples_preserved',np.array_equal(pixels[:,:,:,3],original[:,:,:,3]))
        check('missing_face_frames_are_byte_identical',np.array_equal(pixels[10:14],original[10:14]))
        check('visible_controls_change_face_frames',all(np.any(pixels[i] != original[i]) for i in (*range(10),*range(14,24))))
        check('unrelated_lower_half_rgb_preserved',np.array_equal(pixels[:,300:,:,:3],original[:,300:,:,:3]))
        project_before = sha(project/'project.json');rights_before = sha(project/'rights-ledger.json')
        cli(options,'retouch-idempotent-replay')
        check('idempotent_replay_preserves_author_files',sha(project/'project.json') == project_before and sha(project/'rights-ledger.json') == rights_before)
        replay = cli([*base,'--recipe-from-asset','retouched','--derived-asset-id','recipe_replay'],'retouch-saved-recipe')
        check('saved_recipe_replays_without_model_forwards',replay['data']['model_forwards'] == 0 and np.array_equal(decoded(Path(replay['data']['output']),'recipe-replay-decode'),pixels))
        before_bad_selection = (sha(project/'project.json'),sha(project/'rights-ledger.json'))
        bad = cli([*base,'--report','validation/face.json','--face-id','face_9999','--derived-asset-id','bad_selection'],'bad-selection',2)
        check('bad_selection_rejected',not bad['ok'])
        check('bad_selection_restores_author_bytes',(sha(project/'project.json'),sha(project/'rights-ledger.json')) == before_bad_selection)
        check('bad_selection_leaves_no_partial_output',not (project/'assets/derived/bad_selection.mkv').exists())
        for name,extra,expected in (('precancel',['--cancel-file',str(args.work/'precancel')],8),('timeout',['--timeout','.1'],6)):
            if name == 'precancel':
                (args.work/'precancel').touch()
            author_before=(sha(project/'project.json'),sha(project/'rights-ledger.json'))
            failure=cli([*base,'--recipe-from-asset','retouched','--derived-asset-id',name,*extra],name,expected)
            error=failure['errors'][0]
            check(name+'_keeps_original_code',error['code'] == ('CANCELLED' if name == 'precancel' else 'FACE_TIMEOUT'))
            check(name+'_owned_processes_reaped',error['diagnostics']['process_cleanup']['all_children_reaped'])
            check(name+'_author_bytes_restored',(sha(project/'project.json'),sha(project/'rights-ledger.json')) == author_before)
            check(name+'_no_partial_media',not (project/f'assets/derived/{name}.mkv').exists())
        author_before=(sha(project/'project.json'),sha(project/'rights-ledger.json'))
        cancel=args.work/'cancel-after-worker'
        cancelled=cli([*scan_args[:-2],'--output','validation/cancelled.json','--cancel-file',cancel],
                      'scan-cancel-owned-worker',8,cancel_after_child=cancel)
        check('inflight_cancel_original_code_and_all_children_reaped',cancelled['errors'][0]['code'] == 'CANCELLED' and cancelled['errors'][0]['diagnostics']['process_cleanup']['all_children_reaped'])
        check('inflight_cancel_trigger_after_observed_owned_worker',bool(receipt['calls'][-1]['cancellation_trigger']['observed_owned_children']))
        check('inflight_cancel_no_partial_report',not (project/'validation/cancelled.json').exists())
        check('inflight_cancel_author_bytes_restored',(sha(project/'project.json'),sha(project/'rights-ledger.json')) == author_before)
        cli(['validate','--project',project],'project-validate')
        cli(['policy','audit','--project',project],'policy-audit')
        for name,path in (('neutral',neutral_path),('retouched',edited_path),('recipe-replay',Path(replay['data']['output']))):
            shutil.copyfile(path,args.public/(name+'.mkv'))
            command(['ffmpeg','-nostdin','-v','error','-i',path,'-map','0:v:0','-map','0:a:0?','-c:v','libx264','-pix_fmt','yuv420p',
                     '-crf','16','-c:a','aac','-movflags','+faststart',args.public/(name+'.mp4')],name+'-preview')
        command(['ffmpeg','-nostdin','-v','error','-i',source,'-c:v','libx264','-pix_fmt','yuv420p','-crf','16','-c:a','aac',
                 '-movflags','+faststart',args.public/'source.mp4'],'source-preview')
        for index in (0,9,10,14,23):
            pair = np.concatenate((original[index,:,:,:3],pixels[index,:,:,:3]),axis=1)
            ok,encoded = cv2.imencode('.png',pair[:,:,::-1])
            check('comparison_png_encoded_'+str(index),ok)
            destination = args.public/f'comparison-{index:02d}.png'
            destination.write_bytes(encoded.tobytes())
            check('comparison_png_written_'+str(index),destination.is_file() and destination.stat().st_size == len(encoded))
        command(['ffmpeg','-nostdin','-v','error','-i',source,'-i',edited_path,'-filter_complex',
                 '[0:v]crop=160:140:150:55,scale=480:420[a];[1:v]crop=160:140:150:55,scale=480:420[b];[a][b]hstack,fps=8,split[x][y];[x]palettegen[p];[y][p]paletteuse',
                 '-an','-loop','0',args.public/'comparison.gif'],'comparison-gif')
        receipt['media'] = [{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(args.public.iterdir()) if p.is_file()]
        receipt['detector_forwards'] = report['response']['detector_forwards'];receipt['landmark_forwards'] = report['response']['landmark_forwards']
        receipt['process_cleanup'] = report['process_cleanup']
        receipt['status'] = 'passed_native_cli_contract_quality_separate'
    except BaseException as exc:
        receipt.update(status='failed',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
        raise
    finally:
        receipt['frozen_after'] = frozen();receipt['frozen_equal'] = receipt['frozen_before'] == receipt['frozen_after']
        receipt['finished_at_utc'] = datetime.now(timezone.utc).isoformat();save(args.evidence/'verification.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','detector_forwards','landmark_forwards','frozen_equal','quality_accepted')},ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('work','evidence','public','upstream','image','controller-python'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--installed',type=Path)
    run(parser.parse_args())
