"""Explicit local LaMa registration, mask clock/geometry and paired RGBA input."""
from __future__ import annotations

import json
import math
import zipfile
from fractions import Fraction
from pathlib import Path

from .errors import AppError, argument_error
from .local_matting import _entry, manifest_hash
from .media import probe_media
from .policy import resolve_local_path
from .utils import assert_id, now_iso, sha256_bytes, sha256_file

INPAINT_ENGINE = 'torchscript-lama-local-v1'
INPAINT_PROTOCOL = 'agent-video-lama-inpainting-v1'
IMPLEMENTATIONS = {'worker': 'lama_worker.py', 'frames': 'inpainting_frames.py', 'controller': 'local_inpainting.py',
                   'pipeline': 'local_matting.py', 'rgba': 'matting_frames.py', 'guard': 'rvm_worker.py'}


def settings(*, device='cpu', threads=4):
    if device not in {'cpu', 'cuda'} or type(threads) is not int or not 1 <= threads <= 32:
        raise argument_error('LaMa 要求 cpu/cuda 和 1..32 个线程', 'device/threads')
    return {'device': device, 'threads': threads, 'precision': 'float32', 'state_budget_bytes': 512 * 1024**2}


def check_model(path: Path):
    try:
        if path.suffix.lower() not in {'.pt', '.torchscript'} or not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= 2 * 1024**3:
            raise ValueError('local TorchScript file required')
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = [i.filename for i in entries]
            if not 1 <= len(entries) <= 20000 or sum(i.file_size for i in entries) > 4 * 1024**3 or len(names) != len(set(names)):
                raise ValueError('TorchScript archive budget or duplicate')
            if any(n.startswith('/') or '\\' in n or ':' in n or '..' in n.split('/') for n in names):
                raise ValueError('invalid TorchScript archive path')
            if not any('/code/' in n for n in names) or not any(n.endswith('/constants.pkl') for n in names):
                raise ValueError('raw pickle/checkpoint is not TorchScript')
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        raise AppError('INPAINT_MODEL_INVALID', '需要已有本地 LaMa TorchScript；不接受原始 pickle/checkpoint', exit_code=10, cause=str(exc)) from exc


def prepare_adapter(root: Path, *, adapter_id, model_path, executable, evidence, creator, license_spdx,
                    license_url, permitted_uses, verification_status, options):
    assert_id(adapter_id, 'adapter_id')
    if verification_status not in {'unverified', 'verified', 'restricted'}:
        raise argument_error('未知模型核验状态', 'verification_status')
    model = resolve_local_path(root, model_path, field='model_path')
    python = resolve_local_path(root, executable, field='executable')
    proof = resolve_local_path(root, evidence, field='evidence') if evidence else None
    if python.suffix.lower() != '.exe' or proof is None:
        raise argument_error('LaMa 需要原生 Python .exe 和本地证据', 'executable/evidence')
    check_model(model)
    artifacts = [_entry(model, 'model'), _entry(python, 'python'), _entry(proof, 'evidence')]
    artifacts += [_entry(Path(__file__).with_name(name), role) for role, name in IMPLEMENTATIONS.items()]
    record = {'adapter_id': adapter_id, 'kind': 'video-inpainting', 'engine': INPAINT_ENGINE, 'protocol': INPAINT_PROTOCOL,
              'output_contract': 'rgba_video_v1', 'model_path': str(model), 'model_sha256': artifacts[0]['sha256'],
              'model_kind': 'file', 'model_file_count': 1, 'executable': str(python), 'executable_sha256': artifacts[1]['sha256'],
              'rights_ref': 'visual_adapter_' + adapter_id, 'capabilities': ['masked_frame_inpainting', 'native_torch_cpu_or_cuda', 'roi_inference'],
              'settings': settings(**options), 'artifacts': artifacts, 'network': 'disabled', 'registered_at': now_iso(), 'verification_status': verification_status}
    record['sha256'] = manifest_hash(record)
    rights = {'asset_id': record['rights_ref'], 'kind': 'model-adapter', 'sha256': record['sha256'],
              'source_url': 'local://visual-adapter/' + adapter_id, 'source_version': INPAINT_ENGINE, 'retrieved_at': record['registered_at'],
              'creator': creator, 'license_spdx': license_spdx, 'license_url': license_url, 'attribution': '',
              'permitted_uses': list(dict.fromkeys(permitted_uses)), 'permitted_channels': [], 'restrictions': [], 'derived_from': [],
              'evidence': str(proof), 'verification_status': verification_status, 'verified_by': 'explicit-local-registration' if verification_status == 'verified' else '',
              'takedown_status': 'clear', 'notes': 'Local framewise LaMa; source, mask, weights and code rights remain separate'}
    return record, rights


def verify_adapter(record):
    findings = []
    try:
        if record.get('engine') != INPAINT_ENGINE or record.get('protocol') != INPAINT_PROTOCOL or record.get('kind') != 'video-inpainting' or record.get('network') != 'disabled' or record.get('output_contract') != 'rgba_video_v1' or record.get('capabilities') != ['masked_frame_inpainting', 'native_torch_cpu_or_cuda', 'roi_inference']:
            raise ValueError('INPAINT_REGISTRY_CONTRACT_INVALID')
        config = record['settings']
        if config != settings(device=config['device'], threads=config['threads']) or manifest_hash(record) != record['sha256'] or record['rights_ref'] != 'visual_adapter_' + record['adapter_id']:
            raise ValueError('INPAINT_MANIFEST_INVALID')
        model = Path(record['model_path']); check_model(model)
        expected = {(str(model.resolve()), 'model'), (str(Path(record['executable']).resolve()), 'python')}
        expected |= {(str(Path(__file__).with_name(name).resolve()), role) for role, name in IMPLEMENTATIONS.items()}
        actual = {(a['path'], a['role']) for a in record['artifacts']}
        if len(actual) != len(record['artifacts']) or not expected.issubset(actual) or len(actual - expected) != 1 or next(iter(actual - expected))[1] != 'evidence':
            raise ValueError('INPAINT_MANIFEST_INVENTORY_CHANGED')
        roles = {a['role']: a for a in record['artifacts']}
        if record['model_kind'] != 'file' or record['model_file_count'] != 1 or roles['model']['sha256'] != record['model_sha256'] or roles['python']['sha256'] != record['executable_sha256']:
            raise ValueError('INPAINT_MODEL_HASH_INVALID')
        if any(_entry(Path(a['path']), a['role']) != a for a in record['artifacts']):
            raise ValueError('INPAINT_ARTIFACT_CHANGED')
    except (AppError, ValueError, TypeError, OSError, KeyError, StopIteration) as exc:
        findings.append({'code': getattr(exc, 'code', 'INPAINT_REGISTRY_INVALID'), 'message': str(exc)})
    return {'adapter_id': record.get('adapter_id'), 'engine': record.get('engine'), 'network': 'disabled', 'ok': not findings, 'findings': findings}


def normalize_options(*, threshold=.5, grow=4, feather=0., context=64, model_max_edge=1024):
    if type(threshold) not in {int, float} or not math.isfinite(threshold) or not 0 <= threshold <= 1 or type(feather) not in {int, float} or not math.isfinite(feather) or not 0 <= feather <= 32:
        raise argument_error('蒙版 threshold 须为 0..1，feather 为 0..32', 'mask_threshold/mask_feather')
    if any(type(v) is not int or not lo <= v <= hi for v, lo, hi in ((grow, 0, 64), (context, 0, 1024), (model_max_edge, 64, 2048))):
        raise argument_error('grow/context/model-max-edge 超出整数预算', 'mask_grow/context_pixels/model_max_edge')
    return {'threshold': float(threshold), 'grow': grow, 'feather': float(feather), 'context': context, 'model_max_edge': model_max_edge}


def prepare_mask(root: Path, path: str, *, kind: str, video: dict, channel='alpha', start_seconds=0., resize='reject'):
    source = resolve_local_path(root, path, field='mask')
    if channel not in {'alpha', 'luma'} or resize not in {'reject', 'nearest'} or type(start_seconds) not in {int, float} or not math.isfinite(start_seconds) or start_seconds < 0 or kind not in {'image', 'video'}:
        raise argument_error('蒙版类型、通道、缩放或起点无效', 'mask')
    probe = probe_media(source)
    stream = next((s for s in probe['streams'] if s.get('codec_type') == 'video'), {})
    try:
        width, height = int(stream['width']), int(stream['height'])
        sar_text = stream.get('sample_aspect_ratio')
        sar = Fraction(str(sar_text).replace(':', '/')) if sar_text not in (None, 'N/A', '0:1') else Fraction(1)
        rotation = float(next((s['rotation'] for s in stream.get('side_data_list', []) if 'rotation' in s), stream.get('tags', {}).get('rotate', 0)))
        display_w, display_h = width * float(sar), height
        if abs(rotation) % 180 == 90: display_w, display_h = display_h, display_w
        if not 0 < display_w <= 16384 or not 0 < display_h <= 16384 or not math.isfinite(rotation) or rotation % 90:
            raise ValueError('unsupported mask display geometry')
    except (ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        raise argument_error('蒙版没有可用显示尺寸/SAR/方向', 'mask') from exc
    alpha = str(stream.get('pix_fmt', '')).startswith(('rgba', 'bgra', 'argb', 'abgr', 'yuva', 'gbrap', 'ya')) or str(stream.get('tags', {}).get('alpha_mode', '')) == '1'
    if channel == 'alpha' and not alpha:
        raise argument_error('蒙版没有 alpha；黑白蒙版须指定 --mask-channel luma', 'mask_channel')
    if abs(display_w - video['width']) > .01 or abs(display_h - video['height']) > .01:
        if resize == 'reject' or abs(display_w / display_h / (video['width'] / video['height']) - 1) > .02:
            raise argument_error('蒙版尺寸不同；相同比例才可显式 --mask-resize nearest', 'mask_resize')
    if kind == 'image' and start_seconds:
        raise argument_error('静态蒙版起点必须为 0', 'mask_start_seconds')
    if kind == 'video':
        duration = float(stream.get('duration') or probe.get('duration_seconds') or 0)
        if not math.isfinite(duration) or duration + .002 < start_seconds + video['duration_seconds']:
            raise argument_error('视频蒙版时长不足；不自动延长缺失蒙版', 'mask_start_seconds')
    result = {'path': str(source), 'sha256': 'sha256:' + sha256_file(source), 'kind': kind, 'channel': channel,
              'start_seconds': float(start_seconds), 'resize': resize, 'source_stream_index': int(stream['index']),
              'source_width': width, 'source_height': height, 'display_width': display_w, 'display_height': display_h,
              'source_sar': str(sar), 'source_rotation': rotation, 'source_fps': (probe.get('video') or {}).get('fps'),
              'alpha_decoder': 'libvpx-vp9' if channel == 'alpha' and stream.get('codec_name') == 'vp9' else 'libvpx' if channel == 'alpha' and stream.get('codec_name') == 'vp8' else None,
              'clock': 'ffmpeg-fps-resampled-mask-seconds', 'layout': 'horizontal-source-rgba-mask-rgba'}
    result['plan_sha256'] = 'sha256:' + sha256_bytes(json.dumps(result, sort_keys=True, separators=(',', ':')).encode())
    return result


def mask_unchanged(plan):
    try:
        mask = plan['mask']
        p = Path(mask['path'])
        expected = 'sha256:' + sha256_bytes(json.dumps({k: v for k, v in mask.items() if k != 'plan_sha256'}, sort_keys=True, separators=(',', ':')).encode())
        return expected == mask['plan_sha256'] and p.is_file() and not p.is_symlink() and 'sha256:' + sha256_file(p) == mask['sha256']
    except (KeyError, OSError, TypeError):
        return False


def decoder_command(base: list[str], source: Path, plan: dict, source_filter: str):
    mask, info = plan['mask'], plan['video']
    stream = next((s for s in plan['input_probe']['streams'] if s.get('index') == info['source_stream_index']), {})
    alpha_codec = stream.get('codec_name') in {'vp8', 'vp9'} and str(stream.get('tags', {}).get('alpha_mode', '')) == '1'
    command = [*base, *(['-c:v', 'libvpx-vp9' if stream['codec_name'] == 'vp9' else 'libvpx'] if alpha_codec else []), '-i', str(source)]
    if mask['kind'] == 'image': command += ['-loop', '1', '-framerate', info['fps']]
    if mask['alpha_decoder']: command += ['-c:v', mask['alpha_decoder']]
    command += ['-protocol_whitelist', 'file,pipe', '-i', mask['path']]
    start, end = mask['start_seconds'], mask['start_seconds'] + info['duration_seconds']
    mf = f"setpts=PTS-STARTPTS,trim=start={start:.12f}:end={end:.12f},setpts=PTS-STARTPTS,scale={info['width']}:{info['height']}:flags=neighbor,setsar=1,fps=fps={info['fps']}:start_time=0:round=near,format=rgba"
    graph = f"[0:{info['source_stream_index']}]{source_filter}[src];[1:{mask['source_stream_index']}]{mf}[mask];[src][mask]hstack=inputs=2:shortest=1,format=rgba[paired]"
    return [*command, '-filter_complex_threads', '1', '-filter_complex', graph, '-map', '[paired]', '-an', '-sn', '-dn',
            '-frames:v', str(info['frames']), '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1']
