"""Local encoded-mask correction with immutable editable geometry and lossless proof."""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time

from .artifact_locks import artifact_entry, verification_scope, verification_summary
from .errors import AppError, argument_error
from .mask_edit_geometry import checked, edit_frame, finite, work_estimate
from .mask_review import prepare as prepare_review
from .media import ffmpeg_path, ffprobe_path, probe_media
from .policy import resolve_local_path
from .utils import run_process, sha256_file

ENGINE = 'agent-local-mask-edit-v1'


def plan_digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('MASK_EDIT_DUPLICATE_JSON_KEY')
        out[key] = value
    return out


def prepare(root, asset, *, edits_path=None, embedded=None, channel='alpha', fps=None,
            max_frames=4096, storage_budget_mib=512, buffer_budget_mib=256, work_budget_million=200):
    if (bool(edits_path) == (embedded is not None) or type(storage_budget_mib) is not int or not 1 <= storage_budget_mib <= 4096
            or type(buffer_budget_mib) is not int or not 1 <= buffer_budget_mib <= 2048
            or type(work_budget_million) is not int or not 1 <= work_budget_million <= 10000):
        raise argument_error('要求唯一编辑计划来源及有效的显式存储/缓冲/工作预算', 'edits/budget')
    proof = None
    try:
        if edits_path:
            source = resolve_local_path(root, edits_path, field='edits')
            if not source.is_file() or source.is_symlink() or not 0 < source.stat().st_size <= 512*1024:
                raise ValueError('MASK_EDIT_JSON_BUDGET_INVALID')
            raw = source.read_bytes()
            if len(raw) > 512*1024:
                raise ValueError('MASK_EDIT_JSON_BUDGET_INVALID')
            def reject_constant(value):
                raise ValueError('MASK_EDIT_JSON_NONFINITE')
            value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_pairs, parse_constant=reject_constant)
            proof = {'path': str(source), 'sha256': 'sha256:' + hashlib.sha256(raw).hexdigest()}
        else:
            value = copy.deepcopy(embedded)
            if len(json.dumps(value, allow_nan=False).encode('utf-8')) > 512*1024:
                raise ValueError('MASK_EDIT_JSON_BUDGET_INVALID')
        if not isinstance(value, dict) or not isinstance(value.get('mask'), dict) or type(value['mask'].get('fps')) is not str or len(value['mask']['fps']) > 64:
            raise ValueError('MASK_EDIT_BINDING_INVALID')
        value['mask']['fps'] = str(Fraction(value['mask']['fps']))
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, ZeroDivisionError, RecursionError) as exc:
        raise AppError('MASK_EDIT_PLAN_INVALID', '蒙版编辑计划格式无效', exit_code=2, cause=str(exc)) from exc
    review = prepare_review(root, asset, channel=channel, fps=fps, max_edge=0,
                            max_frames=max_frames, budget_mib=min(storage_budget_mib, 1024))
    info = review['video']
    rate = Fraction(info['fps'])
    if max(rate.numerator, rate.denominator) > 2**31-1:
        raise argument_error('帧率分数必须能由原生编码器的有符号 32 位有理数表示', 'fps')
    binding = {'asset_id': asset['id'], 'sha256': asset['sha256'], 'channel': channel,
               'width': info['width'], 'height': info['height'], 'frames': info['frames'], 'fps': str(Fraction(info['fps']))}
    try:
        edits = checked(value, binding)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise AppError('MASK_EDIT_PLAN_INVALID', '蒙版编辑几何、源绑定或切点无效', exit_code=2, cause=str(exc)) from exc
    pixel_bytes = info['width']*info['height']
    storage, buffers, work = 5*pixel_bytes*info['frames'], 12*pixel_bytes, work_estimate(edits)
    if storage > storage_budget_mib*1024**2 or buffers > buffer_budget_mib*1024**2 or work > work_budget_million*1_000_000:
        raise AppError('MASK_EDIT_BUDGET_EXCEEDED', '蒙版编辑超过显式原始存储、像素缓冲或形状工作预算', exit_code=2,
            cause=json.dumps({'raw_storage_bytes': storage, 'pixel_buffer_bytes': buffers, 'geometry_work_units': work}))
    implementation = {p.name: 'sha256:'+sha256_file(p) for p in (Path(__file__), Path(__file__).with_name('mask_edit_geometry.py'))}
    return {'engine': ENGINE, 'mask_plan': review, 'editable_plan': edits, 'plan_sha256': plan_digest(edits),
            'edit_file': proof, 'implementation_sha256': implementation,
            'budget': {'raw_storage_bytes': storage, 'owned_pixel_buffer_bytes': buffers,
                'geometry_work_units': work, 'storage_budget_mib': storage_budget_mib,
                'buffer_budget_mib': buffer_budget_mib, 'work_budget_million': work_budget_million,
                'scope': 'temporary-raw-files-owned-pixel-buffers-and-conservative-work-estimates-excludes-python-objects-ffmpeg-encoded-output-and-total-ram'},
            'network': 'disabled', 'warnings': [{'code': 'MASK_EDIT_SEMANTIC_REVIEW_REQUIRED',
                'message': '显式形状修正只改变给定选区，不证明完整对象、遮挡身份或修复纹理与时序质量'}]}


def public_plan(plan):
    return {**plan, 'mask_plan': {k: v for k, v in plan['mask_plan'].items() if k != 'events'}}


def execute(root, plan, output, *, timeout=1800., cancel_file=None, progress=None):
    if not finite(timeout) or not 0 < timeout <= 604800:
        raise argument_error('timeout-seconds 必须为 0..604800 的有限正数', 'timeout-seconds')
    started = time.monotonic()
    def checkpoint():
        if cancel_file and cancel_file.exists():
            raise AppError('CANCELLED', '蒙版编辑已取消', exit_code=8)
        if time.monotonic()-started >= timeout:
            raise AppError('TIMEOUT', '蒙版编辑超过显式时间预算', exit_code=8)
    def process(command):
        checkpoint()
        result = run_process(command, timeout=max(.001, timeout-(time.monotonic()-started)), cancel_file=cancel_file)
        if result.returncode:
            raise AppError('MASK_EDIT_NATIVE_FAILED', '蒙版编辑原生编码/解码核验失败', exit_code=6, cause=result.stderr[-3000:])
        checkpoint()
        return result
    checkpoint()
    review, edits = plan['mask_plan'], plan['editable_plan']
    info = review['video']; width, height, frames = info['width'], info['height'], info['frames']
    rate = Fraction(info['fps']); frame_size = width*height
    expected_suffix = '.png' if review['clock'] == 'single-image' else '.mov'
    output = output.resolve()
    if not output.is_relative_to(root.resolve()) or output.suffix.lower() != expected_suffix or output.exists():
        raise argument_error('蒙版输出必须是项目内全新的 PNG 图像或 MOV 视频', 'output')
    cache = root/'cache/mask-edit'; cache.mkdir(parents=True, exist_ok=True)
    with verification_scope():
        proofs = [review['source'], *([plan['edit_file']] if plan['edit_file'] else [])]
        for proof in proofs:
            if artifact_entry(Path(proof['path']), 'mask-edit-input')['sha256'] != proof['sha256']:
                raise AppError('MASK_EDIT_INPUT_CHANGED', '蒙版或编辑文件与预检摘要不一致', exit_code=6)
        for name, expected in plan['implementation_sha256'].items():
            if artifact_entry(Path(__file__).with_name(name), 'mask-edit-implementation')['sha256'] != expected:
                raise AppError('MASK_EDIT_IMPLEMENTATION_CHANGED', '蒙版编辑实现与预检摘要不同', exit_code=6)
        tools = [artifact_entry(Path(ffmpeg_path()), 'ffmpeg'), artifact_entry(Path(ffprobe_path()), 'ffprobe')]
        with tempfile.TemporaryDirectory(prefix='edit-', dir=cache) as directory:
            work = Path(directory); decoded, authored = work/'input.gray', work/'authored.rgba'
            staged = work/('staged'+expected_suffix)
            command = [ffmpeg_path(), '-v', 'error', '-nostdin', '-n']
            if review['decoder']:
                command += ['-c:v', review['decoder']]
            filters = ['setpts=PTS-STARTPTS']
            if review['clock'] != 'single-image':
                filters.append('fps='+info['fps'])
            filters += [f'scale={width}:{height}:flags=neighbor', 'setsar=1']
            filters += ['format=rgba', 'alphaextract'] if review['channel'] == 'alpha' else ['format=gray']
            if review['clock'] != 'single-image':
                filters.append(f'tpad=stop_mode=clone:stop_duration={1/float(rate):.12f}')
            command += ['-protocol_whitelist', 'file,pipe', '-i', review['source']['path'], '-map', '0:'+str(review['source_stream_index']),
                        '-an', '-sn', '-dn', '-vf', ','.join(filters), '-frames:v', str(frames),
                        '-f', 'rawvideo', '-pix_fmt', 'gray', str(decoded)]
            process(command)
            if decoded.stat().st_size != frames*frame_size:
                raise AppError('MASK_EDIT_DECODE_INVALID', '实际蒙版帧数或字节数与绑定时钟不一致', exit_code=6)
            records = []; source_hash, alpha_hash, rgba_hash = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
            with decoded.open('rb') as source, authored.open('xb') as destination:
                for frame in range(frames):
                    checkpoint()
                    base = source.read(frame_size)
                    alpha, record = edit_frame(base, edits, frame, checkpoint)
                    rgba = bytearray(b'\xff\xff\xff\xff')*frame_size
                    rgba[3::4] = alpha
                    source_hash.update(base); alpha_hash.update(alpha); rgba_hash.update(rgba)
                    destination.write(rgba); records.append(record)
                    if progress:
                        progress(frame+1, frames)
            command = [ffmpeg_path(), '-v', 'error', '-nostdin', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba',
                       '-video_size', f'{width}x{height}', '-framerate', str(rate), '-i', str(authored), '-an']
            command += ['-frames:v', '1', '-c:v', 'png', '-pix_fmt', 'rgba'] if expected_suffix == '.png' else [
                       '-frames:v', str(frames), '-fps_mode', 'passthrough', '-c:v', 'qtrle', '-pix_fmt', 'argb',
                       '-video_track_timescale', str(rate.numerator)]
            process(command+[str(staged)])
            expected_hash = 'sha256:'+rgba_hash.hexdigest()
            decoded_hash = process([ffmpeg_path(), '-v', 'error', '-nostdin', '-i', str(staged), '-map', '0:v:0',
                '-an', '-pix_fmt', 'rgba', '-fps_mode', 'passthrough', '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
            if decoded_hash.stdout.strip().lower() != 'sha256='+expected_hash[7:]:
                raise AppError('MASK_EDIT_ROUNDTRIP_FAILED', '蒙版实际编码 RGBA 与作者数组不符', exit_code=6)
            clocks = process([ffprobe_path(), '-v', 'error', '-show_frames', '-show_streams', '-show_entries',
                'frame=best_effort_timestamp:stream=codec_type,width,height,time_base,avg_frame_rate,pix_fmt,codec_name', '-of', 'json', str(staged)])
            timing = json.loads(clocks.stdout)
            streams = timing['streams']; decoded_frames = timing.get('frames', [])
            if (len(streams) != 1 or streams[0]['codec_type'] != 'video' or streams[0]['width'] != width
                    or streams[0]['height'] != height or len(decoded_frames) != frames
                    or any(int(item['best_effort_timestamp'])*Fraction(streams[0]['time_base']) != Fraction(i, 1)/rate
                           for i, item in enumerate(decoded_frames))):
                raise AppError('MASK_EDIT_CLOCK_INVALID', '蒙版帧、几何或逐帧 PTS 不符合绑定网格', exit_code=6)
            result_probe = probe_media(staged)
            digest = 'sha256:'+sha256_file(staged)
            checkpoint()
            output.parent.mkdir(parents=True, exist_ok=True)
            # Windows rename refuses an externally created destination. POSIX
            # uses a no-replace hard link on the same project filesystem.
            if os.name == 'nt':
                staged.rename(output)
            else:
                os.link(staged, output)
                staged.unlink()
            return {'engine': ENGINE, 'plan': public_plan(plan), 'sha256': digest, 'probe': result_probe,
                'rgba_sha256': expected_hash, 'alpha_sha256': 'sha256:'+alpha_hash.hexdigest(),
                'source_gray_sha256': 'sha256:'+source_hash.hexdigest(), 'frames': records,
                'changed_pixels': sum(r['changed_pixels'] for r in records),
                'rgba_roundtrip_verified': True, 'every_pts_exact': True, 'output_rgb': 'constant-white',
                'audio': 'none-mask-coverage-only', 'network': 'disabled', 'model_runs': 0,
                'artifact_verification': verification_summary(), 'toolchain': tools,
                'semantic_quality_accepted': False, 'seconds': time.monotonic()-started,
                'warnings': plan['warnings']}
