"""Explicit local PP-OCRv4 registration, bounded scans and report integrity."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import os
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from .artifact_locks import artifact_entry, verification_scope
from .errors import AppError
from .media import ffmpeg_path, ffprobe_path, probe_media
from .policy import resolve_local_path
from .runtime import configure_local_runtime
from .utils import atomic_write_json, assert_id, now_iso, sha256_file

ENGINE = 'ppocr-v4-onnx-cpu-local-v1'
PROTOCOL = 'agent-video-local-ocr-v1'
DET = 'ch_PP-OCRv4_det_infer.onnx'
REC = 'ch_PP-OCRv4_rec_infer.onnx'
IMPLEMENTATION = ('local_ocr.py', 'ocr_worker.py', 'ocr_geometry.py', 'yolo_worker.py', 'browser_process.py')
MAX_REPORT_BYTES = 16 * 1024**2


def fail(code, message, *, exit_code=2, cause=None):
    return AppError(code, message, exit_code=exit_code, cause=cause)


def digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def adapter_hash(record):
    return digest({k: record[k] for k in ('adapter_id', 'engine', 'protocol', 'model_path', 'python_executable', 'threads', 'artifacts', 'network', 'rights_ref')})


def registry(project):
    value = project.get('extensions', {}).get('local_ocr', {})
    if not isinstance(value, dict) or not isinstance(value.get('adapters', []), list) or any(not isinstance(a, dict) for a in value.get('adapters', [])):
        raise fail('OCR_REGISTRY_INVALID', 'extensions.local_ocr.adapters 必须为对象数组')
    return value


def adapter_for(project, adapter_id):
    rows = [a for a in registry(project).get('adapters', []) if a.get('adapter_id') == adapter_id]
    if len(rows) != 1:
        raise fail('OCR_ADAPTER_NOT_FOUND', '找不到唯一的本地 OCR 登记', exit_code=3)
    return rows[0]


def prepare_adapter(root, *, adapter_id, model_path, python_executable, evidence, threads=4,
                    license_spdx='LicenseRef-UNVERIFIED', creator='unknown', status='unverified', uses=None):
    assert_id(adapter_id, 'adapter_id')
    if type(threads) is not int or not 1 <= threads <= 16 or status not in {'unverified', 'verified', 'restricted'}:
        raise fail('OCR_ADAPTER_OPTIONS_INVALID', 'threads 为 1..16；verification-status 必须有效')
    model = resolve_local_path(root, model_path, field='model_path')
    python = resolve_local_path(root, python_executable, field='python_executable')
    proof = resolve_local_path(root, evidence, field='evidence')
    if not model.is_dir() or python.suffix.lower() != '.exe':
        raise fail('OCR_LOCAL_ARTIFACT_REQUIRED', '需完整本地 PP-OCRv4 目录与原生 Python .exe', exit_code=10)
    paths = [(model / DET, 'detector'), (model / REC, 'recognizer'), (python, 'python'), (proof, 'evidence')]
    paths += [(Path(__file__).with_name(n), n) for n in IMPLEMENTATION]
    entries = [artifact_entry(p, role) for p, role in paths]
    if any(row['bytes'] > 64*1024**2 for row in entries):
        raise fail('OCR_ARTIFACT_BUDGET', '单项 OCR 登记文件不能超过 64 MiB', exit_code=10)
    record = {'adapter_id': adapter_id, 'engine': ENGINE, 'protocol': PROTOCOL, 'model_path': str(model),
              'python_executable': str(python), 'threads': threads, 'network': 'disabled',
              'artifacts': entries, 'rights_ref': 'ocr_adapter_'+adapter_id, 'registered_at': now_iso()}
    record['sha256'] = adapter_hash(record)
    rights = {'asset_id': record['rights_ref'], 'kind': 'model-adapter', 'sha256': record['sha256'],
              'source_url': 'local://ocr-adapter/'+adapter_id, 'source_version': ENGINE,
              'retrieved_at': record['registered_at'], 'creator': creator, 'license_spdx': license_spdx,
              'license_url': '', 'attribution': '', 'permitted_uses': uses or ['internal'],
              'permitted_channels': [], 'restrictions': [], 'derived_from': [], 'evidence': str(proof),
              'verification_status': status, 'verified_by': 'ai-ad-editor' if status == 'verified' else '',
              'takedown_status': 'clear', 'notes': 'OCR source/model terms require independent review'}
    return record, rights


def verify_adapter(record):
    findings = []
    try:
        if record['engine'] != ENGINE or record['protocol'] != PROTOCOL or record['network'] != 'disabled' or adapter_hash(record) != record['sha256']:
            raise ValueError('OCR_MANIFEST_INVALID')
        if type(record['threads']) is not int or not 1 <= record['threads'] <= 16:
            raise ValueError('OCR_THREADS_INVALID')
        paths = {'detector': Path(record['model_path'])/DET, 'recognizer': Path(record['model_path'])/REC,
                 'python': Path(record['python_executable'])}
        paths.update({n: Path(__file__).with_name(n) for n in IMPLEMENTATION})
        artifacts = record['artifacts']
        if len(artifacts) != len(paths)+1 or set(a['role'] for a in artifacts) != set(paths)|{'evidence'}:
            raise ValueError('OCR_MANIFEST_INCOMPLETE')
        for row in artifacts:
            path = Path(row['path'])
            if row['role'] in paths and path.resolve() != paths[row['role']].resolve():
                raise ValueError('OCR_MANIFEST_PATH_MISMATCH')
            if not 0 < row['bytes'] <= 64*1024**2 or artifact_entry(path, row['role']) != row:
                raise ValueError('OCR_ARTIFACT_CHANGED')
    except (AppError, KeyError, ValueError, TypeError, OSError) as error:
        findings.append({'code': getattr(error, 'code', 'OCR_INTEGRITY_FAILED'), 'message': str(error)})
    return {'ok': not findings, 'adapter_id': record.get('adapter_id'), 'findings': findings}


def source_plan(root, asset, *, start_frame=0, end_frame=None, step_frames=8, max_frames=120):
    if asset.get('kind') not in {'image', 'video'}:
        raise fail('OCR_SOURCE_UNSUPPORTED', 'OCR 需要已登记视频或图片', exit_code=4)
    source = resolve_local_path(root, asset['uri'], field='asset.uri')
    if 'sha256:'+sha256_file(source) != asset['sha256']:
        raise fail('OCR_SOURCE_CHANGED', '素材字节已变化', exit_code=10)
    info = probe_media(source)
    stream = next(s for s in info['streams'] if s.get('codec_type') == 'video')
    width, height = int(stream['width']), int(stream['height'])
    if min(width, height) < 16 or width*height > 16_000_000 or stream.get('sample_aspect_ratio') not in (None, 'N/A', '0:1', '1:1') or abs(float(stream.get('start_time') or 0)) > 1e-6 or float(stream.get('tags', {}).get('rotate', 0)) % 360 or any(float(s.get('rotation', 0)) % 360 for s in stream.get('side_data_list', [])):
        raise fail('OCR_SOURCE_GEOMETRY_UNSUPPORTED', '需要 ≤16M 像素、方形像素、零起始 PTS/旋转源', exit_code=4)
    image = asset['kind'] == 'image'
    fps = Fraction(1) if image else Fraction(stream.get('avg_frame_rate') or '0')
    if not image and (not 0 < fps <= 60 or not 0 < info['duration_seconds'] <= 600):
        raise fail('OCR_SOURCE_CLOCK_UNSUPPORTED', '视频需已知 CFR≤60 fps、长度≤600秒', exit_code=4)
    count = 1 if image else round(float(info['duration_seconds'])*fps)
    if type(start_frame) is not int or type(step_frames) is not int or type(max_frames) is not int or not 1 <= step_frames <= 36000 or not 1 <= max_frames <= 120 or not 0 <= start_frame < count:
        raise fail('OCR_FRAME_BUDGET', '显式源帧范围/步长/最多120帧无效')
    end_frame = min(count, start_frame+step_frames*max_frames) if end_frame is None else end_frame
    if type(end_frame) is not int or not start_frame < end_frame <= count:
        raise fail('OCR_FRAME_RANGE_INVALID', 'end-frame 是源帧的排他上界')
    indices = list(range(start_frame, end_frame, step_frames))
    if len(indices) > max_frames:
        raise fail('OCR_FRAME_BUDGET', '请求帧数超过显式 max-frames')
    return {'asset_id': asset['id'], 'path': str(source), 'sha256': asset['sha256'], 'kind': asset['kind'],
            'width': width, 'height': height, 'fps': str(fps), 'source_frames': count,
            'frame_indices': indices, 'clock': 'original-source-frame-index-and-verified-PTS'}


def scan_plan(root, asset, adapter, **options):
    if not verify_adapter(adapter)['ok']:
        raise fail('OCR_INTEGRITY_FAILED', 'OCR 登记摘要不符，请新 ID 重新登记', exit_code=10)
    source = source_plan(root, asset, **options)
    programs = [artifact_entry(Path(p()).resolve(), role) for p, role in ((ffmpeg_path, 'ffmpeg'), (ffprobe_path, 'ffprobe'))]
    return {'protocol': PROTOCOL, 'engine': ENGINE, 'network': 'disabled', 'source': source,
            'adapter': adapter, 'programs': programs,
            'limits': {'det_max_edge': 1536, 'max_boxes': 128, 'rec_max_width': 2048,
                       'max_report_bytes': MAX_REPORT_BYTES}, 'rights_dependencies': [asset['id'], adapter['rights_ref']]}


def validate_response(value, plan):
    try:
        if value.get('protocol') != PROTOCOL or value.get('engine') != ENGINE or value.get('status') != 'succeeded' or value.get('network') != 'disabled' or value.get('blocked_network_events') != [] or value.get('request_sha256') != digest(plan) or value.get('adapter_sha256') != plan['adapter']['sha256'] or value.get('source_sha256') != plan['source']['sha256']:
            raise ValueError('integrity/status')
        frames = value['frames']; indices = plan['source']['frame_indices']
        if not isinstance(frames, list) or len(frames) != len(indices):
            raise ValueError('frame coverage')
        fps = float(Fraction(plan['source']['fps']))
        for frame, expected in zip(frames, indices):
            if frame['frame_index'] != expected or not math.isfinite(frame['pts_seconds']) or abs(frame['pts_seconds']-expected/fps) > .0015 or not isinstance(frame['boxes'], list) or len(frame['boxes']) > 128:
                raise ValueError('source frame clock')
            for box in frame['boxes']:
                if not isinstance(box['text'], str) or not 1 <= len(box['text']) <= 4096:
                    raise ValueError('text length')
                if not all(type(box[k]) in (int, float) and math.isfinite(box[k]) and 0 <= box[k] <= 1 for k in ('confidence', 'detection_score')):
                    raise ValueError('confidence')
                polygon = box['polygon']; bounds = box['bbox']
                if not isinstance(polygon, list) or len(polygon) != 4 or any(not isinstance(p, list) or len(p) != 2 for p in polygon) or len(bounds) != 4:
                    raise ValueError('polygon')
                width, height = plan['source']['width'], plan['source']['height']
                if any(type(v) not in (int, float) or not math.isfinite(v) for p in polygon for v in p) or any(not 0 <= x <= width or not 0 <= y <= height for x,y in polygon):
                    raise ValueError('polygon bounds')
                xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
                actual = [min(xs)/width, min(ys)/height, (max(xs)-min(xs))/width, (max(ys)-min(ys))/height]
                if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v-a) > 1e-7 for v,a in zip(bounds, actual)) or min(actual[2:]) <= 0:
                    raise ValueError('box projection')
        if value.get('device') != 'cpu' or value.get('providers') != ['CPUExecutionProvider']:
            raise ValueError('device')
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise fail('OCR_WORKER_OUTPUT_INVALID', 'OCR worker 输出/范围/完整性不符', exit_code=6, cause=str(exc)) from exc


def execute_scan(root, plan, *, timeout=600, cancel_file=None):
    from .browser_process import BrowserProcessJob
    if not math.isfinite(timeout) or not .1 <= timeout <= 3600:
        raise fail('OCR_TIMEOUT_INVALID', 'timeout 范围 0.1..3600 秒')
    runtime = Path(configure_local_runtime()['root'])
    with verification_scope():
        if not verify_adapter(plan['adapter'])['ok']:
            raise fail('OCR_INTEGRITY_FAILED', 'OCR 模型登记发生变化', exit_code=10)
        for row in [*plan['programs'], {'path': plan['source']['path'], 'sha256': plan['source']['sha256']}]:
            if artifact_entry(Path(row['path']), 'ocr-execution')['sha256'] != row['sha256']:
                raise fail('OCR_INPUT_CHANGED', 'OCR 媒体/工具已变化', exit_code=10)
        with tempfile.TemporaryDirectory(prefix='ocr-', dir=runtime/'temp') as scratch:
            folder = Path(scratch); request = folder/'request.json'; response = folder/'response.json'
            atomic_write_json(request, {'plan': plan, 'response': str(response), 'runtime_root': str(runtime)})
            command = [plan['adapter']['python_executable'], '-I', '-B', '-X', 'utf8',
                       str(Path(__file__).with_name('ocr_worker.py')), str(request)]
            job = BrowserProcessJob(timeout, cancel_file)
            try:
                with (folder/'stdout.log').open('wb') as stdout, (folder/'stderr.log').open('wb') as stderr:
                    process = job.spawn(command, root, dict(os.environ), stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
                    process.stdin.write(b'run\n'); process.stdin.flush(); process.stdin.close()
                    process.wait(); job.check()
                if not response.exists() or not 0 < response.stat().st_size <= MAX_REPORT_BYTES:
                    raise fail('OCR_WORKER_FAILED', 'OCR worker 未返回有界 JSON', exit_code=6,
                               cause=(folder/'stderr.log').read_text(encoding='utf-8', errors='replace')[-4000:])
                value = json.loads(response.read_text(encoding='utf-8'))
                if process.returncode:
                    raise fail('OCR_WORKER_FAILED', '本地 OCR 执行失败', exit_code=6, cause=json.dumps(value, ensure_ascii=False)[-5000:])
                validate_response(value, plan)
            except AppError as exc:
                if exc.code.startswith('HTML_'):
                    raise fail('OCR_TIMEOUT' if exc.code == 'HTML_TIMEOUT' else 'OCR_PROCESS_FAILED', 'OCR 执行期限/进程约束失败', exit_code=6, cause=str(exc)) from exc
                raise
            finally:
                cleanup = job.close()
            if not cleanup['all_children_reaped']:
                raise fail('OCR_CLEANUP_FAILED', 'OCR 子进程未回收', exit_code=6)
            if not verify_adapter(plan['adapter'])['ok']:
                raise fail('OCR_INPUT_CHANGED', '执行中 OCR 登记发生变化', exit_code=10)
            return {'report_version': '0.1.0', 'engine': ENGINE, 'source': copy.deepcopy(plan['source']),
                    'adapter_id': plan['adapter']['adapter_id'], 'adapter_sha256': plan['adapter']['sha256'],
                    'rights_dependencies': plan['rights_dependencies'], 'request': plan, 'response': value,
                    'frames': value['frames'], 'process_cleanup': cleanup,
                    'warnings': ['OCR_REVIEW_REQUIRED', 'SAMPLED_TEXT_NOT_COMPLETE_PRIVACY_OR_UI_ACTION_DETECTION']}


def seal_report(report):
    result = copy.deepcopy(report)
    result['sha256'] = digest({k:v for k,v in result.items() if k != 'sha256'})
    return result


def load_report(root, project, path):
    path = resolve_local_path(root, path, field='report')
    if not path.is_file() or not path.is_relative_to(root/'validation') or not 0 < path.stat().st_size <= MAX_REPORT_BYTES:
        raise fail('OCR_REPORT_INVALID', '需要项目 validation 内的有界 OCR 报告')
    try:
        registered = [r for r in registry(project).get('reports', []) if r.get('path') == path.relative_to(root).as_posix()]
        if len(registered) != 1 or registered[0]['file_sha256'] != 'sha256:'+sha256_file(path):
            raise ValueError('registered report hash')
        value = json.loads(path.read_text(encoding='utf-8'))
        if value['sha256'] != seal_report(value)['sha256']:
            raise ValueError('report hash')
        adapter = adapter_for(project, value['adapter_id'])
        if not verify_adapter(adapter)['ok'] or value['adapter_sha256'] != adapter['sha256'] or value['request']['adapter'] != adapter or value['source'] != value['request']['source'] or value['frames'] != value['response']['frames']:
            raise ValueError('adapter/source/response mismatch')
        validate_response(value['response'], value['request'])
        assets = [a for a in project['assets'] if a['id'] == value['source']['asset_id']]
        if len(assets) != 1 or assets[0]['sha256'] != value['source']['sha256'] or 'sha256:'+sha256_file(resolve_local_path(root, assets[0]['uri'], field='source')) != value['source']['sha256']:
            raise ValueError('source changed')
    except (KeyError, ValueError, TypeError, OSError) as exc:
        raise fail('OCR_REPORT_INTEGRITY_FAILED', 'OCR 报告或来源已变化', exit_code=10, cause=str(exc)) from exc
    return path, value
