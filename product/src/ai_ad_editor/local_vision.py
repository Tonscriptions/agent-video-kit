"""Registered native YOLO inference; all executables and weights are inputs."""
from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .media import ffmpeg_path, probe_media
from .policy import resolve_local_path
from .utils import assert_id, now_iso, sha256_bytes, sha256_file

YOLO_ENGINE = 'yolov10-onnx-cpu-tracking-v1'
YOLO_PROTOCOL = 'agent-video-object-tracking-v2'


def settings(*, threads: int = 4, confidence: float = .35, low_confidence: float = .10, match_iou: float = .10, max_gap_seconds: float = .8, class_ids: list[int] | None = None) -> dict[str, Any]:
    values = (confidence, low_confidence, match_iou, max_gap_seconds)
    if not all(math.isfinite(float(v)) for v in values) or not 1 <= threads <= 32 or not 0 < low_confidence <= confidence <= 1 or not 0 < match_iou <= 1 or not 0 < max_gap_seconds <= 30:
        raise argument_error('YOLO threads=1..32, 0<low-confidence<=confidence<=1, match-iou=0..1, max-gap-seconds=0..30', 'settings')
    classes = sorted(set([0] if class_ids is None else class_ids))
    if not classes or any(type(v) is not int or not 0 <= v < 80 for v in classes):
        raise argument_error('YOLO class-id 必须是 COCO 0..79', 'class_ids')
    return {'threads': int(threads), 'confidence': float(confidence), 'low_confidence': float(low_confidence), 'match_iou': float(match_iou), 'max_gap_seconds': float(max_gap_seconds), 'class_ids': classes, 'device': 'cpu', 'association': 'constant-velocity-hungarian-two-stage-v1'}


def _entry(path: Path, role: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or str(path).startswith('\\\\') or not path.stat().st_size:
        raise AppError('VISION_LOCAL_ARTIFACT_INVALID', '需要非空本地普通文件', exit_code=10, path=str(path))
    return {'path': str(path.resolve()), 'role': role, 'bytes': path.stat().st_size, 'sha256': 'sha256:'+sha256_file(path)}


def manifest_hash(record: dict[str, Any]) -> str:
    data = {key: record.get(key) for key in ('adapter_id', 'engine', 'protocol', 'output_contract', 'model_path', 'model_sha256', 'executable', 'executable_sha256', 'rights_ref', 'settings', 'artifacts', 'network')}
    return 'sha256:'+sha256_bytes(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def prepare_adapter(root: Path, *, adapter_id: str, model_path: str, executable: str, evidence: str, creator: str, license_spdx: str, license_url: str, permitted_uses: list[str], verification_status: str, options: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    assert_id(adapter_id, 'adapter_id')
    if verification_status not in {'unverified', 'verified', 'restricted'}:
        raise argument_error('未知视觉模型核验状态', 'verification_status')
    model = resolve_local_path(root, model_path, field='model_path')
    python = resolve_local_path(root, executable, field='executable')
    proof = resolve_local_path(root, evidence, field='evidence') if evidence else None
    if model.suffix.lower() != '.onnx' or python.suffix.lower() != '.exe' or proof is None:
        raise argument_error('YOLO 需要本地 .onnx、原生 Python .exe 和现有 evidence 文件', 'model_path/executable/evidence')
    entries = [_entry(model, 'model'), _entry(python, 'python'), _entry(proof, 'evidence')]
    entries += [_entry(Path(__file__).with_name(name), role) for name, role in [('yolo_worker.py', 'worker'), ('vision_tracker.py', 'tracker'), ('local_vision.py', 'controller')]]
    config = settings(**options)
    record = {'adapter_id': adapter_id, 'kind': 'object-tracking', 'engine': YOLO_ENGINE, 'model_path': str(model), 'model_sha256': entries[0]['sha256'], 'model_kind': 'file', 'model_file_count': 1, 'executable': str(python), 'executable_sha256': entries[1]['sha256'], 'protocol': YOLO_PROTOCOL, 'output_contract': 'tracking_objects_v1', 'capabilities': ['multi_object_bbox', 'native_onnx_cpu'], 'settings': config, 'artifacts': entries, 'rights_ref': f'visual_adapter_{adapter_id}', 'network': 'disabled', 'registered_at': now_iso(), 'verification_status': verification_status}
    record['sha256'] = manifest_hash(record)
    rights = {'asset_id': record['rights_ref'], 'kind': 'model-adapter', 'sha256': record['sha256'], 'source_url': f'local://visual-adapter/{adapter_id}', 'source_version': YOLO_ENGINE, 'retrieved_at': record['registered_at'], 'creator': creator, 'license_spdx': license_spdx, 'license_url': license_url, 'attribution': '', 'permitted_uses': list(dict.fromkeys(permitted_uses)), 'permitted_channels': [], 'restrictions': [], 'derived_from': [], 'evidence': str(proof), 'verification_status': verification_status, 'verified_by': 'ai-ad-editor' if verification_status == 'verified' else '', 'takedown_status': 'clear', 'notes': 'Explicit local CPU ONNX model; metadata labels do not verify model licensing'}
    return record, rights


def verify_adapter(record: dict[str, Any]) -> dict[str, Any]:
    findings = []
    try:
        if record.get('engine') != YOLO_ENGINE or record.get('protocol') != YOLO_PROTOCOL or record.get('network') != 'disabled' or record.get('output_contract') != 'tracking_objects_v1':
            raise ValueError('VISION_REGISTRY_CONTRACT_INVALID')
        config = dict(record['settings'])
        config.pop('device', None)
        config.pop('association', None)
        if settings(**config) != record['settings']:
            raise ValueError('VISION_SETTINGS_INVALID')
        if manifest_hash(record) != record.get('sha256'):
            raise ValueError('VISION_MANIFEST_HASH_MISMATCH')
        roles = {x['role']: x for x in record['artifacts']}
        if len(roles) != 6 or len(record['artifacts']) != 6 or set(roles) != {'model','python','evidence','worker','tracker','controller'}:
            raise ValueError('VISION_MANIFEST_INCOMPLETE')
        for role, expected in [('model', record['model_path']), ('python', record['executable']), ('worker', str(Path(__file__).with_name('yolo_worker.py'))), ('tracker', str(Path(__file__).with_name('vision_tracker.py'))), ('controller', str(Path(__file__)))]:
            if Path(roles[role]['path']).resolve() != Path(expected).resolve():
                raise ValueError('VISION_MANIFEST_PATH_MISMATCH')
        if roles['model']['sha256'] != record['model_sha256'] or roles['python']['sha256'] != record['executable_sha256']:
            raise ValueError('VISION_ARTIFACT_HASH_MISMATCH')
        for artifact in record['artifacts']:
            if _entry(Path(artifact['path']), artifact['role']) != artifact:
                findings.append({'code': 'VISION_ARTIFACT_HASH_MISMATCH', 'role': artifact['role']})
    except (AppError, ValueError, TypeError, KeyError, OSError) as exc:
        findings.append({'code': getattr(exc, 'code', 'VISION_REGISTRY_INVALID'), 'message': str(exc)})
    return {'adapter_id': record.get('adapter_id'), 'engine': record.get('engine'), 'network': record.get('network'), 'ok': not findings, 'findings': findings}


def prepare_request(source: Path, adapter: dict[str, Any], request: dict[str, Any]) -> list[str]:
    if not verify_adapter(adapter)['ok']:
        raise AppError('MODEL_ADAPTER_HASH_INVALID', 'YOLO 登记完整性检查失败', exit_code=10)
    probe = probe_media(source)
    stream = next((s for s in probe.get('streams', []) if s.get('codec_type') == 'video'), {})
    try:
        width, height = int(stream['width']), int(stream['height'])
        fps = float(Fraction(stream.get('avg_frame_rate') or stream.get('r_frame_rate') or '0'))
        duration = float(stream.get('duration') or probe['duration_seconds'])
        rotation = float(stream.get('tags', {}).get('rotate', 0))
        rotations = [float(v.get('rotation', 0)) for v in stream.get('side_data_list', [])]
        sar = stream.get('sample_aspect_ratio', '1:1')
        start_pts = float(stream.get('start_time') or 0)
        if not 0 < fps <= 240 or not math.isfinite(duration) or duration <= 0 or not 0 < width <= 8192 or not 0 < height <= 8192 or rotation % 360 or any(r % 360 for r in rotations) or sar not in {'1:1', '0:1', 'N/A', None} or abs(start_pts) > .001:
            raise ValueError('unsupported raster, clock or duration')
    except (TypeError, ValueError, ZeroDivisionError, KeyError) as exc:
        raise AppError('VISION_SOURCE_UNSUPPORTED', 'YOLO 需要方形像素、零旋转/起始 PTS、已知时长和帧率的视频', exit_code=4, cause=str(exc)) from exc
    start = request['range']['start_seconds']
    end = request['range']['end_seconds']
    end = duration if end is None else float(end)
    if not 0 <= start < end <= duration + .001:
        raise argument_error('跟踪范围超出视频时长', 'range')
    interval = request['range']['step_frames'] / fps
    count = math.ceil((end-start)/interval - 1e-8)
    if not 1 <= count <= min(4000, request['limits']['max_samples']) or not 1 <= request['limits']['max_objects'] <= 64 or interval > adapter['settings']['max_gap_seconds'] + 1e-8:
        raise AppError('VISION_SAMPLE_BUDGET_EXCEEDED', '采样范围/对象数量超预算，或采样间隔超过 max-gap-seconds；请显式调整范围、step 或登记配置', exit_code=2)
    edge = min(640, request['limits']['max_width'], max(width, height))
    ratio = edge / max(width, height)
    dw, dh = max(1, round(width*ratio)), max(1, round(height*ratio))
    from .runtime import configure_local_runtime
    runtime = configure_local_runtime()['root']
    ffmpeg = Path(ffmpeg_path()).resolve()
    request['engine'] = YOLO_ENGINE
    request['range']['end_seconds'] = end
    request['native'] = {'adapter': adapter, 'video': {'width': width, 'height': height, 'fps': fps, 'duration_seconds': duration, 'sample_interval_seconds': interval, 'expected_samples': count, 'decode_width': dw, 'decode_height': dh, 'clock': 'ffmpeg-fps-resampled-source-seconds'}, 'ffmpeg': {'path': str(ffmpeg), 'sha256': 'sha256:'+sha256_file(ffmpeg)}, 'runtime_root': runtime}
    request['request_sha256'] = request_hash(request)
    return [adapter['executable'], '-I', '-B', '-X', 'utf8', str(Path(__file__).with_name('yolo_worker.py'))]


def request_hash(request: dict[str, Any]) -> str:
    return 'sha256:'+sha256_bytes(json.dumps({k:v for k,v in request.items() if k != 'request_sha256'}, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def validate_response(response: dict[str, Any], request: dict[str, Any]) -> None:
    native, adapter = request['native'], request['native']['adapter']
    if response.get('engine') != YOLO_ENGINE or response.get('network') != 'disabled' or response.get('blocked_network_events') != [] or response.get('request_sha256') != request['request_sha256'] or response.get('adapter_sha256') != adapter['sha256'] or response.get('source_sha256') != request['source']['sha256']:
        raise AppError('VISION_WORKER_INTEGRITY_INVALID', 'YOLO worker 网络或输入/登记/请求摘要不匹配', exit_code=6)
    info = native['video']
    metadata = response.get('metadata')
    if not isinstance(metadata, dict) or not isinstance(response.get('objects'), list) or any(not isinstance(o, dict) or not isinstance(o.get('frames'), list) or any(not isinstance(f, dict) for f in o['frames']) for o in response['objects']):
        raise AppError('VISION_WORKER_OUTPUT_INVALID', 'YOLO worker 输出类型无效', exit_code=6)
    sampled = metadata.get('sampled_frames')
    if type(sampled) is not int or sampled < max(1, info['expected_samples']-1) or sampled > info['expected_samples']:
        raise AppError('VISION_SAMPLING_INCOMPLETE', 'YOLO worker 未覆盖请求采样范围', exit_code=6)
    for obj in response.get('objects', []):
        previous = -1
        for frame in obj.get('frames', []):
            try:
                at = float(frame['at_seconds'])
                index = round((at-request['range']['start_seconds'])/info['sample_interval_seconds'])
                if not math.isfinite(at) or not 0 <= index < sampled or index <= previous or abs(at - (request['range']['start_seconds'] + index*info['sample_interval_seconds'])) > 2e-6:
                    raise ValueError('sample clock')
                if 'at_tick' in frame and abs(int(frame['at_tick']) - round((at-request['range']['start_seconds'])*request['ticks_per_second'])) > 1:
                    raise ValueError('tick clock')
                x, y, w, h = (float(frame[k]) for k in ('x','y','width','height'))
                if x-w/2 < -1e-6 or y-h/2 < -1e-6 or x+w/2 > 1+1e-6 or y+h/2 > 1+1e-6:
                    raise ValueError('bbox extent')
                previous = index
            except (ValueError, TypeError, KeyError) as exc:
                raise AppError('VISION_TRAJECTORY_INVALID', 'YOLO 轨迹采样时钟或边界无效', exit_code=6, cause=str(exc)) from exc
    if 'sha256:'+sha256_file(Path(request['source']['path'])) != request['source']['sha256'] or not verify_adapter(adapter)['ok']:
        raise AppError('VISION_INPUT_CHANGED', '推理期间输入或模型组件发生变更', exit_code=10)
