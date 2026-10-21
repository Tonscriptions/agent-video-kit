"""Explicit local face-model registry, bounded scans and immutable recipes."""
from __future__ import annotations
import copy
import json
import math
import os
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from .artifact_locks import artifact_entry, verification_scope
from .errors import AppError
from .face_geometry import controls, validate_face, TRANSFERS
from .face_landmarks import DETECTOR, LANDMARKS, TOPOLOGY
from .media import ffmpeg_path, ffprobe_path, probe_media
from .policy import resolve_local_path
from .runtime import configure_local_runtime
from .utils import atomic_write_json, assert_id, now_iso, sha256_file

ENGINE = 'openseeface-66-onnx-cpu-local-v1'
PROTOCOL = 'agent-video-local-face-v1'
RETOUCH = 'landmark-retouch-cpu-v1'
MAX_REPORT_BYTES = 32 * 1024**2
IMPLEMENTATION = ('local_face.py','face_cli.py','face_worker.py','face_landmarks.py','face_geometry.py',
                  'OPENSEEFACE_LICENSE.txt','OPENSEEFACE_NOTICE.txt','browser_process.py','artifact_locks.py',
                  'policy.py','runtime.py','media.py','utils.py','errors.py','yolo_worker.py')


def fail(code, message, *, exit_code=2, cause=None):
    return AppError(code,message,exit_code=exit_code,cause=cause)


def digest(value):
    from hashlib import sha256
    return 'sha256:'+sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def registry(project):
    value = project.get('extensions',{}).get('local_face',{})
    if not isinstance(value,dict) or not isinstance(value.get('adapters',[]),list) or any(not isinstance(x,dict) for x in value.get('adapters',[])):
        raise fail('FACE_REGISTRY_INVALID','人脸适配器登记无效')
    return value


def adapter_for(project, identifier):
    rows = [a for a in registry(project).get('adapters',[]) if a.get('adapter_id') == identifier]
    if len(rows) != 1:
        raise fail('FACE_ADAPTER_NOT_FOUND','找不到唯一的本地人脸适配器',exit_code=3)
    return rows[0]


def adapter_hash(record):
    return digest({k:record[k] for k in ('adapter_id','engine','protocol','model_path','python_executable','threads','artifacts','rights_ref','network')})


def prepare_adapter(root, *, adapter_id, model_path, python_executable, evidence, threads=4,
                    license_spdx='LicenseRef-UNVERIFIED',license_url='',creator='unknown',status='unverified',uses=None):
    assert_id(adapter_id,'adapter_id')
    if type(threads) is not int or not 1 <= threads <= 16 or status not in ('unverified','verified','restricted'):
        raise fail('FACE_ADAPTER_OPTIONS_INVALID','threads 为 1..16；核验状态必须有效')
    model = resolve_local_path(root,model_path,field='model_path')
    python = resolve_local_path(root,python_executable,field='python_executable')
    proof = resolve_local_path(root,evidence,field='evidence')
    if not model.is_dir() or python.suffix.lower() != '.exe':
        raise fail('FACE_LOCAL_ARTIFACT_REQUIRED','需要两个现有本地 ONNX 和原生 Python .exe',exit_code=10)
    paths = [(model/DETECTOR,'detector'),(model/LANDMARKS,'landmarks'),(python,'python'),(proof,'evidence')]
    paths += [(Path(__file__).with_name(n),n) for n in IMPLEMENTATION]
    entries = [artifact_entry(p,role) for p,role in paths]
    if any(e['bytes'] > 64*1024**2 for e in entries):
        raise fail('FACE_ARTIFACT_BUDGET','单个登记文件不能超过 64 MiB',exit_code=10)
    record = {'adapter_id':adapter_id,'engine':ENGINE,'protocol':PROTOCOL,'model_path':str(model),
              'python_executable':str(python),'threads':threads,'artifacts':entries,
              'network':'disabled','rights_ref':'face_adapter_'+adapter_id,'registered_at':now_iso()}
    record['sha256'] = adapter_hash(record)
    rights = {'asset_id':record['rights_ref'],'kind':'model-adapter','sha256':record['sha256'],
              'source_url':'local://face-adapter/'+adapter_id,'source_version':ENGINE,'retrieved_at':record['registered_at'],
              'creator':creator,'license_spdx':license_spdx,'license_url':license_url,'attribution':'',
              'permitted_uses':uses or ['internal'],'permitted_channels':[],'restrictions':[],'derived_from':[],
              'evidence':str(proof),'verification_status':status,'verified_by':'ai-ad-editor' if status == 'verified' else '',
              'takedown_status':'clear','notes':'OpenSeeFace 66-point geometry is not skin segmentation or identity. Source/model rights need review.'}
    return record,rights


def verify_adapter(record):
    findings = []
    try:
        if record['engine'] != ENGINE or record['protocol'] != PROTOCOL or record['network'] != 'disabled' or record['sha256'] != adapter_hash(record) or type(record['threads']) is not int or not 1 <= record['threads'] <= 16:
            raise ValueError('FACE_ADAPTER_MANIFEST_INVALID')
        paths = {'detector':Path(record['model_path'])/DETECTOR,'landmarks':Path(record['model_path'])/LANDMARKS,
                 'python':Path(record['python_executable'])}
        paths.update({n:Path(__file__).with_name(n) for n in IMPLEMENTATION})
        entries = record['artifacts']
        if len(entries) != len(paths)+1 or set(e['role'] for e in entries) != set(paths)|{'evidence'}:
            raise ValueError('FACE_ADAPTER_MANIFEST_INCOMPLETE')
        for e in entries:
            if e['role'] in paths and Path(e['path']).resolve() != paths[e['role']].resolve():
                raise ValueError('FACE_ADAPTER_ARTIFACT_PATH_INVALID')
            if artifact_entry(Path(e['path']),e['role']) != e or e['bytes'] > 64*1024**2:
                raise ValueError('FACE_ADAPTER_ARTIFACT_CHANGED')
    except (KeyError,TypeError,ValueError,OSError,AppError) as exc:
        findings.append({'code':getattr(exc,'code','FACE_ADAPTER_INVALID'),'message':str(exc)})
    return {'adapter_id':record.get('adapter_id'),'ok':not findings,'findings':findings}


def source_plan(root,asset,*,max_frames=1800):
    if asset.get('kind') not in ('image','video') or type(max_frames) is not int or not 1 <= max_frames <= 1800:
        raise fail('FACE_SOURCE_OPTIONS_INVALID','需要图片/视频和 1..1800 的 max-frames')
    path = resolve_local_path(root,asset['uri'],field='source')
    if 'sha256:'+sha256_file(path) != asset['sha256']:
        raise fail('FACE_SOURCE_CHANGED','来源字节已变更',exit_code=10)
    info = probe_media(path)
    stream = next((s for s in info['streams'] if s.get('codec_type') == 'video'),{})
    width,height = int(stream.get('width',0)),int(stream.get('height',0))
    if min(width,height) < 16 or width*height > 2073600 or stream.get('sample_aspect_ratio') not in (None,'N/A','0:1','1:1') or abs(float(stream.get('start_time') or 0)) > 1e-6 or float(stream.get('tags',{}).get('rotate',0)) % 360 or any(float(v.get('rotation',0)) % 360 for v in stream.get('side_data_list',[])):
        raise fail('FACE_SOURCE_GEOMETRY_UNSUPPORTED','需要 ≤2073600 像素、方形像素、零起始 PTS/旋转源',exit_code=4)
    pixel_formats = {'rgba','bgra','argb','abgr','rgb24','bgr24','gbrp','gbrap','gray','ya8','pal8',
                     'yuv420p','yuv422p','yuv444p','yuvj420p','yuvj422p','yuvj444p',
                     'yuva420p','yuva422p','yuva444p','nv12','nv21','yuyv422','uyvy422'}
    trc = stream.get('color_transfer')
    transfer = {'bt709':'bt709','smpte170m':'bt709','iec61966-2-1':'srgb','gamma22':'gamma22','gamma28':'gamma28',
                None:'srgb','unknown':'srgb','unspecified':'srgb'}.get(trc)
    if stream.get('pix_fmt') not in pixel_formats or transfer is None:
        raise fail('FACE_SOURCE_COLOR_UNSUPPORTED','只接受已支持的 8 bit SDR 像素/传递函数；不静默降位深或处理 HDR',exit_code=4)
    try:
        fps = Fraction(1) if asset['kind'] == 'image' else Fraction(stream.get('avg_frame_rate') or '0')
        if not 0 < fps <= 60 or (asset['kind'] == 'video' and not 0 < info['duration_seconds'] <= 600):
            raise ValueError('fps/duration')
        count = 1 if asset['kind'] == 'image' else (int(stream['nb_frames']) if str(stream.get('nb_frames','')).isdigit() else round(info['duration_seconds']*fps))
    except (KeyError,TypeError,ValueError,ZeroDivisionError) as exc:
        raise fail('FACE_SOURCE_CLOCK_UNSUPPORTED','需要已知 CFR≤60fps/600秒的源',exit_code=4,cause=str(exc)) from exc
    if not 1 <= count <= max_frames:
        raise fail('FACE_FRAME_BUDGET','完整源超出显式最多帧数，请先显式分段')
    return {'asset_id':asset['id'],'path':str(path),'sha256':asset['sha256'],'kind':asset['kind'],
            'width':width,'height':height,'fps':str(fps),'frame_count':count,'color_transfer':transfer,
            'transfer_assumed':trc in (None,'unknown','unspecified'),'color_primaries':stream.get('color_primaries')}


def scan_plan(root,asset,adapter,*,max_frames=1800,max_faces=1,detection_threshold=.6,landmark_threshold=.6,cuts=None):
    if not verify_adapter(adapter)['ok']:
        raise fail('FACE_INTEGRITY_FAILED','适配器已变更，需新 ID 重新登记',exit_code=10)
    if type(max_faces) is not int or not 1 <= max_faces <= 4 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0 < v <= 1 for v in (detection_threshold,landmark_threshold)):
        raise fail('FACE_SCAN_OPTIONS_INVALID','max-faces 为 1..4；阈值为 0..1')
    source = source_plan(root,asset,max_frames=max_frames)
    cuts = [] if cuts is None else cuts
    if not isinstance(cuts,list) or any(type(v) is not int or not 0 < v < source['frame_count'] for v in cuts) or cuts != sorted(set(cuts)):
        raise fail('FACE_CUTS_INVALID','切点必须是升序、唯一、源范围内的非零帧号')
    estimated_report = source['frame_count']*(1024+max_faces*66*3*24*2)
    if estimated_report > MAX_REPORT_BYTES:
        raise fail('FACE_REPORT_BUDGET','逐帧报告估算超出 32 MiB，请显式分段/减少 max-faces')
    return {'protocol':PROTOCOL,'engine':ENGINE,'mode':'scan','network':'disabled','source':source,'adapter':adapter,
            'programs':[artifact_entry(Path(f()).resolve(),r) for f,r in ((ffmpeg_path,'ffmpeg'),(ffprobe_path,'ffprobe'))],
            'settings':{'max_faces':max_faces,'detection_threshold':float(detection_threshold),'landmark_threshold':float(landmark_threshold),'cuts':cuts},
            'limits':{'max_report_bytes':MAX_REPORT_BYTES,'estimated_report_bytes':estimated_report,'owned_frame_array_bytes':source['width']*source['height']*96},
            'rights_dependencies':[{'rights_ref':asset.get('rights_ref',asset['id']),'sha256':asset['sha256']},
                                   {'rights_ref':adapter['rights_ref'],'sha256':adapter['sha256']}]}


def validate_frames(frames,source,*,max_faces=4):
    if not isinstance(frames,list) or len(frames) != source['frame_count']:
        raise ValueError('FACE_FRAME_COVERAGE_INVALID')
    fps = float(Fraction(source['fps']))
    for index,frame in enumerate(frames):
        if not isinstance(frame,dict) or set(frame) != {'frame_index','pts_seconds','decoded_rgba_sha256','faces'} or type(frame['frame_index']) is not int or frame['frame_index'] != index or type(frame['pts_seconds']) not in (int,float) or not math.isfinite(frame['pts_seconds']) or abs(frame['pts_seconds']-index/fps) > .0015:
            raise ValueError('FACE_FRAME_CLOCK_INVALID')
        if not isinstance(frame['decoded_rgba_sha256'],str) or not __import__('re').fullmatch(r'sha256:[a-f0-9]{64}',frame['decoded_rgba_sha256']):
            raise ValueError('FACE_DECODE_HASH_INVALID')
        faces = frame['faces']
        if not isinstance(faces,list) or len(faces) > max_faces or len({f['face_id'] for f in faces}) != len(faces):
            raise ValueError('FACE_FRAME_COUNT_INVALID')
        for face in faces:
            validate_face(face,source['width'],source['height'])


def validate_response(value,plan):
    try:
        if value['protocol'] != PROTOCOL or value['status'] != 'succeeded' or value['network'] != 'disabled' or value['blocked_network_events'] != [] or value['request_sha256'] != digest(plan) or value['source_sha256'] != plan['source']['sha256'] or value['device'] != 'cpu':
            raise ValueError('FACE_RESPONSE_INTEGRITY_INVALID')
        if plan['mode'] == 'scan':
            validate_frames(value['frames'],plan['source'],max_faces=plan['settings']['max_faces'])
            if value['engine'] != ENGINE or value['adapter_sha256'] != plan['adapter']['sha256'] or value['providers'] != ['CPUExecutionProvider'] or type(value['detector_forwards']) is not int or value['detector_forwards'] != plan['source']['frame_count'] or type(value['landmark_forwards']) is not int or not sum(len(f['faces']) for f in value['frames']) <= value['landmark_forwards'] <= plan['source']['frame_count']*plan['settings']['max_faces']:
                raise ValueError('FACE_FORWARD_COUNTS_INVALID')
        else:
            count = plan['source']['frame_count']; pixels = plan['source']['width']*plan['source']['height']
            if value['engine'] != RETOUCH or any(type(value[k]) is not int for k in ('model_forwards','output_frames','protected_pixel_mismatches','alpha_mismatches')) or value['model_forwards'] != 0 or value['output_frames'] != count or value['protected_pixel_mismatches'] != 0 or value['alpha_mismatches'] != 0:
                raise ValueError('FACE_RETOUCH_RESPONSE_INVALID')
            for key in ('changed_rgb_pixels','affected_pixels'):
                if not isinstance(value[key],list) or len(value[key]) != count or any(type(n) is not int or not 0 <= n <= pixels for n in value[key]):
                    raise ValueError('FACE_RETOUCH_PIXEL_COUNTS_INVALID')
            if any(a > b for a,b in zip(value['changed_rgb_pixels'],value['affected_pixels'])) or not isinstance(value['output_rgba_sha256'],list) or len(value['output_rgba_sha256']) != count or any(not isinstance(v,str) or not __import__('re').fullmatch(r'sha256:[a-f0-9]{64}',v) for v in value['output_rgba_sha256']):
                raise ValueError('FACE_RETOUCH_PIXEL_PROOF_INVALID')
        if type(value['source_clock_frames_checked']) is not int or value['source_clock_frames_checked'] != plan['source']['frame_count']:
            raise ValueError('FACE_CLOCK_CHECK_COUNT_INVALID')
    except (KeyError,ValueError,TypeError,OverflowError,ZeroDivisionError) as exc:
        raise fail('FACE_WORKER_OUTPUT_INVALID','本地人脸 worker 的输出/来源/范围无效',exit_code=6,cause=str(exc)) from exc


def execute(root,plan,*,python_executable=None,timeout=600,cancel_file=None):
    from .browser_process import BrowserProcessJob
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not .1 <= timeout <= 3600:
        raise fail('FACE_TIMEOUT_INVALID','timeout 为 0.1..3600 秒')
    runtime = Path(configure_local_runtime()['root'])
    python = plan['adapter']['python_executable'] if plan['mode'] == 'scan' else python_executable
    def verify():
        if plan['mode'] == 'scan' and not verify_adapter(plan['adapter'])['ok']:
            raise fail('FACE_INTEGRITY_FAILED','人脸模型登记已变更',exit_code=10)
        for e in [*plan['programs'],plan['source'],*plan.get('implementation',[])]:
            if artifact_entry(Path(e['path']),'face-execution')['sha256'] != e['sha256']:
                raise fail('FACE_INPUT_CHANGED','来源/工具/实现字节已变更',exit_code=10)
    with verification_scope():
        verify()
        with tempfile.TemporaryDirectory(prefix='face-',dir=runtime/'temp') as scratch:
            folder = Path(scratch); response = folder/'response.json'; request = folder/'request.json'
            atomic_write_json(request,{'plan':plan,'response':str(response),'runtime_root':str(runtime)})
            job = BrowserProcessJob(timeout,cancel_file)
            error = None
            try:
                with (folder/'stdout.log').open('wb') as stdout,(folder/'stderr.log').open('wb') as stderr:
                    process = job.start([python,'-I','-B','-X','utf8',str(Path(__file__).with_name('face_worker.py')),str(request)],
                                        cwd=root,env=dict(os.environ),stdin=subprocess.PIPE,stdout=stdout,stderr=stderr)
                    process.stdin.write(b'run\n');process.stdin.flush();process.stdin.close()
                    process.wait();job.check()
                if not response.is_file() or not 0 < response.stat().st_size <= MAX_REPORT_BYTES:
                    raise fail('FACE_WORKER_FAILED','本地人脸 worker 未返回有界 JSON',exit_code=6,cause=(folder/'stderr.log').read_text(encoding='utf-8',errors='replace')[-4000:])
                value = json.loads(response.read_text(encoding='utf-8'))
                if process.returncode:
                    raise fail('FACE_WORKER_FAILED','本地人脸 worker 执行失败',exit_code=6,cause=json.dumps(value,ensure_ascii=False)[-5000:])
                validate_response(value,plan)
            except AppError as exc:
                if exc.code.startswith('HTML_'):
                    error = fail('FACE_TIMEOUT' if exc.code == 'HTML_TIMEOUT' else 'FACE_PROCESS_FAILED','人脸任务执行期限/进程约束失败',exit_code=6,cause=exc.code+': '+str(exc))
                elif exc.code == 'CANCELLED':
                    error = fail('CANCELLED','人脸任务已取消',exit_code=8,cause=exc.code)
                else:
                    error = exc
                raise error from exc
            except (OSError,ValueError) as exc:
                error = fail('FACE_WORKER_FAILED','本地人脸 worker 文件/响应失败',exit_code=6,cause=type(exc).__name__+': '+str(exc))
                raise error from exc
            finally:
                cleanup = job.close()
                if error is not None:
                    error.diagnostics = {'engine':plan['engine'],'mode':plan['mode'],'process_cleanup':cleanup}
            if not cleanup['all_children_reaped']:
                raise fail('FACE_CLEANUP_FAILED','本次人脸子进程未完全回收',exit_code=6)
            verify()
            return {'report_version':'0.1.0','engine':plan['engine'],'source':copy.deepcopy(plan['source']),
                    'request':plan,'response':value,'process_cleanup':cleanup}


def seal(value):
    result = copy.deepcopy(value)
    result['sha256'] = digest({k:v for k,v in result.items() if k != 'sha256'})
    return result


def load_report(root,project,path):
    path = resolve_local_path(root,path,field='report')
    if not path.is_file() or not path.is_relative_to(root/'validation') or not 0 < path.stat().st_size <= MAX_REPORT_BYTES:
        raise fail('FACE_REPORT_INVALID','需要项目 validation 内已登记的有界报告')
    try:
        rows = [r for r in registry(project).get('reports',[]) if r.get('path') == path.relative_to(root).as_posix()]
        if len(rows) != 1 or rows[0]['file_sha256'] != 'sha256:'+sha256_file(path):
            raise ValueError('registered report hash')
        value = json.loads(path.read_text(encoding='utf-8'))
        if seal(value)['sha256'] != value['sha256'] or value['source'] != value['request']['source'] or value['engine'] != ENGINE:
            raise ValueError('report hash/source')
        adapter = adapter_for(project,value['request']['adapter']['adapter_id'])
        if not verify_adapter(adapter)['ok'] or adapter != value['request']['adapter']:
            raise ValueError('adapter changed')
        validate_response(value['response'],value['request'])
        assets = [a for a in project['assets'] if a['id'] == value['source']['asset_id']]
        if len(assets) != 1 or source_plan(root,assets[0]) != value['source']:
            raise ValueError('source changed')
    except (KeyError,TypeError,ValueError,OSError) as exc:
        raise fail('FACE_REPORT_INTEGRITY_FAILED','报告或其来源已变更',exit_code=10,cause=str(exc)) from exc
    return path,value


def recipe_from_report(report,*,settings,selected_ids=None):
    recipe = {'version':'0.1.0','engine':RETOUCH,'topology':TOPOLOGY,'source_sha256':report['source']['sha256'],
              'source_clock':{k:report['source'][k] for k in ('width','height','fps','frame_count','color_transfer')},
              'controls':controls(**settings),'selected_ids':None if selected_ids is None else sorted(set(selected_ids)),
              'frames':copy.deepcopy(report['response']['frames']),
              'model_provenance':{'engine':ENGINE,'adapter_sha256':report['request']['adapter']['sha256']}}
    result = seal(recipe); validate_recipe(result)
    return result


def validate_recipe(recipe):
    if not isinstance(recipe,dict) or set(recipe) != {'version','engine','topology','source_sha256','source_clock','controls','selected_ids','frames','model_provenance','sha256'} or recipe['version'] != '0.1.0' or recipe['engine'] != RETOUCH or recipe['topology'] != TOPOLOGY or seal(recipe)['sha256'] != recipe['sha256']:
        raise ValueError('FACE_RECIPE_INVALID')
    source = recipe['source_clock']
    if set(source) != {'width','height','fps','frame_count','color_transfer'} or source['color_transfer'] not in TRANSFERS or any(type(source[k]) is not int for k in ('width','height','frame_count')) or min(source['width'],source['height']) < 16 or source['width']*source['height'] > 2073600 or not 1 <= source['frame_count'] <= 1800 or type(source['fps']) is not str or not 0 < Fraction(source['fps']) <= 60:
        raise ValueError('FACE_RECIPE_SOURCE_INVALID')
    if controls(**recipe['controls']) != recipe['controls'] or set(recipe['controls']) != set(controls()):
        raise ValueError('FACE_RECIPE_CONTROLS_INVALID')
    validate_frames(recipe['frames'],source)
    selected = recipe['selected_ids']
    known = {f['face_id'] for frame in recipe['frames'] for f in frame['faces']}
    if selected is not None and (not isinstance(selected,list) or not selected or any(not isinstance(i,str) for i in selected) or selected != sorted(set(selected)) or not set(selected) <= known):
        raise ValueError('FACE_RECIPE_SELECTION_INVALID')
    if not __import__('re').fullmatch(r'sha256:[a-f0-9]{64}',str(recipe['source_sha256'])) or set(recipe['model_provenance']) != {'engine','adapter_sha256'} or recipe['model_provenance']['engine'] != ENGINE or not __import__('re').fullmatch(r'sha256:[a-f0-9]{64}',str(recipe['model_provenance']['adapter_sha256'])):
        raise ValueError('FACE_RECIPE_PROVENANCE_INVALID')
    if len(json.dumps(recipe,ensure_ascii=False).encode()) > MAX_REPORT_BYTES:
        raise ValueError('FACE_RECIPE_BUDGET')


def retouch_plan(root,asset,recipe,*,python_executable,output):
    validate_recipe(recipe)
    source = source_plan(root,asset)
    if source['sha256'] != recipe['source_sha256'] or {k:source[k] for k in recipe['source_clock']} != recipe['source_clock']:
        raise fail('FACE_RECIPE_SOURCE_CHANGED','保存配方只允许在同一来源字节/时钟重放',exit_code=10)
    python = resolve_local_path(root,python_executable,field='python_executable')
    if python.suffix.lower() != '.exe':
        raise fail('FACE_LOCAL_PYTHON_REQUIRED','需要现有原生 Python .exe',exit_code=10)
    return {'protocol':PROTOCOL,'engine':RETOUCH,'mode':'retouch','network':'disabled','source':source,'recipe':recipe,
            'output':str(output),'programs':[artifact_entry(Path(f()).resolve(),r) for f,r in ((ffmpeg_path,'ffmpeg'),(ffprobe_path,'ffprobe'))],
            'implementation':[artifact_entry(p,r) for p,r in [(python,'python')]+[(Path(__file__).with_name(n),n) for n in IMPLEMENTATION]],
            'limits':{'max_report_bytes':MAX_REPORT_BYTES,'owned_frame_array_bytes':source['width']*source['height']*96}}
