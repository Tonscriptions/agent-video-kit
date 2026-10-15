"""Explicit local SAM2 registration and agent-authored video prompt plans."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .errors import AppError, argument_error
from .local_matting import _entry, manifest_hash
from .policy import resolve_local_path
from .utils import assert_id, now_iso, sha256_bytes, sha256_file

SEGMENTATION_ENGINE = 'transformers-sam2-video-local-v1'
SEGMENTATION_PROTOCOL = 'agent-video-sam2-segmentation-v1'
IMPLEMENTATIONS = {'worker': 'sam2_worker.py', 'frames': 'segmentation_frames.py', 'controller': 'local_segmentation.py', 'pipeline': 'local_matting.py', 'rgba': 'matting_frames.py', 'guard': 'rvm_worker.py'}


def settings(*, device: str = 'cpu', threads: int = 4) -> dict:
    if device not in {'cpu', 'cuda'} or type(threads) is not int or not 1 <= threads <= 32:
        raise argument_error('SAM2 要求显式 cpu/cuda 和 1..32 个线程', 'device/threads')
    return {'device': device, 'threads': threads, 'precision': 'float32', 'state_budget_bytes': 512 * 1024 * 1024}


def model_files(model: Path) -> list[Path]:
    required = {'config.json', 'preprocessor_config.json', 'processor_config.json', 'video_preprocessor_config.json'}
    try:
        if not model.is_dir() or model.is_symlink():
            raise ValueError('model directory missing')
        for name in required:
            value = json.loads((model / name).read_text(encoding='utf-8'))
            if not isinstance(value, dict) or value.get('auto_map') or value.get('custom_pipelines'):
                raise ValueError('custom model code unsupported')
            if name == 'config.json' and (value.get('model_type') != 'sam2_video' or value.get('architectures') != ['Sam2VideoModel'] or value.get('image_size') != 1024 or not 1 <= value.get('num_maskmem', 0) <= 32 or not 1 <= value.get('max_object_pointers_in_encoder', 0) <= 64):
                raise ValueError('SAM2 video configuration required')
        index = model / 'model.safetensors.index.json'
        weights = set(json.loads(index.read_text(encoding='utf-8'))['weight_map'].values()) if index.exists() else {'model.safetensors'}
        if index.exists():
            required.add(index.name)
        if not weights or len(weights) > 32:
            raise ValueError('invalid weight inventory')
        for name in weights:
            if not isinstance(name, str) or Path(name).name != name or Path(name).suffix != '.safetensors':
                raise ValueError('weight shard must be local safetensors')
            required.add(name)
        files = [model / name for name in sorted(required)]
        if any(not p.is_file() or p.is_symlink() or not 0 < p.stat().st_size <= 2 * 1024**3 for p in files):
            raise ValueError('model component missing or oversized')
        if any(p.suffix.lower() in {'.py', '.pyc', '.pyd', '.dll', '.bin', '.pt', '.pth'} or p.is_symlink() for p in model.rglob('*')):
            raise ValueError('executable or unbound model component')
        return files
    except (ValueError, TypeError, KeyError, OSError, AttributeError) as exc:
        raise AppError('SEGMENTATION_MODEL_INVALID', '需要完整的本地 SAM2 视频 safetensors，禁止模型自定义代码', exit_code=10, cause=str(exc)) from exc


def model_digest(model: Path, artifacts: list[dict]) -> str:
    records = [{'name': Path(a['path']).relative_to(model).as_posix(), 'bytes': a['bytes'], 'sha256': a['sha256']} for a in artifacts if a['role'] == 'model']
    return 'sha256:' + sha256_bytes(json.dumps(records, sort_keys=True, separators=(',', ':')).encode())


def prepare_adapter(root: Path, *, adapter_id: str, model_path: str, executable: str, evidence: str, creator: str,
                    license_spdx: str, license_url: str, permitted_uses: list[str], verification_status: str, options: dict) -> tuple[dict, dict]:
    assert_id(adapter_id, 'adapter_id')
    if verification_status not in {'unverified', 'verified', 'restricted'}:
        raise argument_error('未知模型核验状态', 'verification_status')
    model = resolve_local_path(root, model_path, field='model_path')
    python = resolve_local_path(root, executable, field='executable')
    proof = resolve_local_path(root, evidence, field='evidence') if evidence else None
    if python.suffix.lower() != '.exe' or proof is None:
        raise argument_error('SAM2 需要原生 Python .exe 和本地证据', 'executable/evidence')
    artifacts = [_entry(p, 'model') for p in model_files(model)]
    artifacts.extend([_entry(python, 'python'), _entry(proof, 'evidence')])
    artifacts.extend(_entry(Path(__file__).with_name(name), role) for role, name in IMPLEMENTATIONS.items())
    record = {'adapter_id': adapter_id, 'kind': 'video-segmentation', 'engine': SEGMENTATION_ENGINE, 'protocol': SEGMENTATION_PROTOCOL, 'output_contract': 'rgba_video_v1',
              'model_path': str(model), 'model_sha256': model_digest(model, artifacts), 'model_kind': 'directory', 'model_file_count': len(model_files(model)),
              'executable': str(python), 'executable_sha256': next(a['sha256'] for a in artifacts if a['role'] == 'python'), 'rights_ref': 'visual_adapter_' + adapter_id,
              'capabilities': ['prompted_video_segmentation', 'native_torch', 'multi_object_union'], 'settings': settings(**options), 'artifacts': artifacts,
              'network': 'disabled', 'registered_at': now_iso(), 'verification_status': verification_status}
    record['sha256'] = manifest_hash(record)
    rights = {'asset_id': record['rights_ref'], 'kind': 'model-adapter', 'sha256': record['sha256'], 'source_url': 'local://visual-adapter/' + adapter_id,
              'source_version': SEGMENTATION_ENGINE, 'retrieved_at': record['registered_at'], 'creator': creator, 'license_spdx': license_spdx, 'license_url': license_url,
              'attribution': '', 'permitted_uses': list(dict.fromkeys(permitted_uses)), 'permitted_channels': [], 'restrictions': [], 'derived_from': [],
              'evidence': str(proof), 'verification_status': verification_status, 'verified_by': 'explicit-local-registration' if verification_status == 'verified' else '',
              'takedown_status': 'clear', 'notes': 'Explicit local SAM2 segmentation; model and source rights are separate'}
    return record, rights


def verify_adapter(record: dict) -> dict:
    findings = []
    try:
        if record.get('engine') != SEGMENTATION_ENGINE or record.get('kind') != 'video-segmentation' or record.get('protocol') != SEGMENTATION_PROTOCOL or record.get('output_contract') != 'rgba_video_v1' or record.get('network') != 'disabled' or record.get('capabilities') != ['prompted_video_segmentation', 'native_torch', 'multi_object_union']:
            raise ValueError('SEGMENTATION_REGISTRY_CONTRACT_INVALID')
        config = record['settings']
        if settings(device=config['device'], threads=config['threads']) != config or manifest_hash(record) != record['sha256'] or record['rights_ref'] != 'visual_adapter_' + record['adapter_id']:
            raise ValueError('SEGMENTATION_MANIFEST_INVALID')
        model = Path(record['model_path'])
        expected = {(str(p.resolve()), 'model') for p in model_files(model)} | {(str(Path(record['executable']).resolve()), 'python')}
        expected |= {(str(Path(__file__).with_name(name).resolve()), role) for role, name in IMPLEMENTATIONS.items()}
        actual = {(a['path'], a['role']) for a in record['artifacts']}
        if len(actual) != len(record['artifacts']) or not expected.issubset(actual) or len(actual - expected) != 1 or next(iter(actual - expected))[1] != 'evidence':
            raise ValueError('SEGMENTATION_MANIFEST_INVENTORY_CHANGED')
        if record['model_kind'] != 'directory' or record['model_file_count'] != len(model_files(model)) or model_digest(model, record['artifacts']) != record['model_sha256']:
            raise ValueError('SEGMENTATION_MODEL_INVENTORY_CHANGED')
        if next(a['sha256'] for a in record['artifacts'] if a['role'] == 'python') != record['executable_sha256']:
            raise ValueError('SEGMENTATION_PYTHON_HASH_MISMATCH')
        if any(_entry(Path(a['path']), a['role']) != a for a in record['artifacts']):
            raise ValueError('SEGMENTATION_ARTIFACT_CHANGED')
    except (AppError, OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        findings.append({'code': getattr(exc, 'code', 'SEGMENTATION_REGISTRY_INVALID'), 'message': str(exc)})
    return {'adapter_id': record.get('adapter_id'), 'engine': record.get('engine'), 'ok': not findings, 'network': 'disabled', 'findings': findings}


def normalize_prompts(value: dict, *, frames: int, object_ids: list[int] | None = None, mask_mode: str = 'binary', threshold: float = 0) -> dict:
    def reject(message):
        raise argument_error(message, 'prompts')
    def number(v):
        return type(v) in {int, float} and math.isfinite(v) and 0 <= v <= 1
    if not isinstance(value, dict) or set(value) != {'version', 'coordinate_space', 'frames'} or value.get('version') != '1.0.0' or value.get('coordinate_space') != 'normalized-output':
        reject('需要 version=1.0.0、normalized-output 和 frames；禁止未知字段')
    if mask_mode not in {'binary', 'probability'} or type(threshold) not in {int, float} or not math.isfinite(threshold) or not -20 <= threshold <= 20:
        reject('mask-mode 或 logit-threshold 无效')
    events = value['frames']
    if not isinstance(events, list) or not 1 <= len(events) <= 256:
        reject('提示事件须为 1..256 项')
    active, normalized, previous = set(), [], -1
    for event in events:
        if not isinstance(event, dict) or set(event) - {'frame', 'objects', 'reset'} or not {'frame', 'objects'} <= set(event):
            reject('提示事件字段无效')
        index, reset, objects = event['frame'], event.get('reset', False), event['objects']
        if type(index) is not int or not previous < index < frames or previous == -1 and index != 0 or type(reset) is not bool or not isinstance(objects, list) or not 1 <= len(objects) <= 8:
            reject('事件须从第 0 帧开始，严格递增且在输出范围内，每次 1..8 个对象')
        ids, records = set(), []
        for item in objects:
            if not isinstance(item, dict) or set(item) - {'object_id', 'points', 'box'} or 'object_id' not in item:
                reject('对象提示字段无效')
            oid = item['object_id']
            if type(oid) is not int or not 1 <= oid <= 2147483647 or oid in ids:
                reject('对象 ID 须为不重复的正整数')
            ids.add(oid)
            points, box = item.get('points', []), item.get('box')
            if not isinstance(points, list) or len(points) > 32:
                reject('每次每对象最多 32 个提示点')
            for point in points:
                if not isinstance(point, dict) or set(point) != {'x', 'y', 'label'} or not number(point['x']) or not number(point['y']) or type(point['label']) is not int or point['label'] not in {0, 1}:
                    reject('点须为归一化 x/y 和整数 label=0/1')
            if box is not None and (not isinstance(box, list) or len(box) != 4 or not all(number(v) for v in box) or not box[0] < box[2] or not box[1] < box[3]):
                reject('框须为有效归一化 x1/y1/x2/y2')
            if box is None and not any(p['label'] == 1 for p in points):
                reject('每个对象提示须有框或至少一个正点')
            records.append({'object_id': oid, 'points': points, 'box': box})
        if reset and not active.issubset(ids):
            reject('镜头重置须为所有此前激活对象重新提供提示')
        active |= ids
        if len(active) > 8:
            reject('全片最多 8 个对象')
        normalized.append({'frame': index, 'reset': reset, 'objects': records})
        previous = index
    selected = sorted(active) if object_ids is None else object_ids
    if not selected or any(type(i) is not int for i in selected) or len(set(selected)) != len(selected) or not set(selected).issubset(active):
        reject('object-id 必须是已声明且不重复的对象 ID')
    if not set(selected).intersection(r['object_id'] for r in normalized[0]['objects']):
        reject('第 0 帧须至少有一个选中对象')
    result = {'version': '1.0.0', 'coordinate_space': 'normalized-output', 'frames': normalized, 'object_ids': sorted(selected), 'mask_mode': mask_mode, 'logit_threshold': float(threshold)}
    result['sha256'] = 'sha256:' + sha256_bytes(json.dumps(result, sort_keys=True, separators=(',', ':')).encode())
    return result


def load_prompts(root: Path, path: str, *, frames: int, object_ids: list[int] | None, mask_mode: str, threshold: float) -> tuple[dict, dict]:
    source = resolve_local_path(root, path, field='prompts')
    if not source.is_file() or source.is_symlink() or not 0 < source.stat().st_size <= 128 * 1024:
        raise argument_error('提示须为最多 128 KiB 的本地普通 JSON 文件', 'prompts')
    raw = source.read_bytes()
    try:
        value = json.loads(raw.decode('utf-8-sig'))
    except (ValueError, UnicodeError) as exc:
        raise argument_error('提示 JSON 无效', 'prompts') from exc
    plan = normalize_prompts(value, frames=frames, object_ids=object_ids, mask_mode=mask_mode, threshold=threshold)
    return plan, {'path': str(source), 'sha256': 'sha256:' + sha256_bytes(raw)}


def verify_prompt_source(plan: dict) -> bool:
    try:
        source = Path(plan['prompt_source']['path'])
        return source.is_file() and 'sha256:' + sha256_file(source) == plan['prompt_source']['sha256']
    except (KeyError, TypeError, OSError):
        return False
