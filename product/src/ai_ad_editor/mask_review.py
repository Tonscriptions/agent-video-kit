"""Bounded local mask measurements and explicit spatial assertions, no NumPy."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import tempfile

from .errors import AppError, argument_error
from .media import ffmpeg_path, ffmpeg_version, probe_media
from .policy import resolve_local_path
from .utils import run_process, sha256_file

VERSION = '0.1.0'


def number(value):
    try:
        return type(value) in {int, float} and math.isfinite(value)
    except OverflowError:
        return False


def load_expectations(root, path, frames):
    if path is None:
        return None, {}
    source = resolve_local_path(root, path, field='expectations')
    if not source.is_file() or source.is_symlink() or not 0 < source.stat().st_size <= 128*1024:
        raise argument_error('检查点须为最多 128 KiB 的本地 JSON', 'expectations')
    raw = source.read_bytes()
    try:
        value = json.loads(raw.decode('utf-8-sig'))
        if not isinstance(value, dict) or set(value) != {'version', 'coordinate_space', 'frames'} or value['version'] != '1.0.0' or value['coordinate_space'] != 'normalized-output':
            raise ValueError('invalid expectation header')
        if not isinstance(value['frames'], list) or not 1 <= len(value['frames']) <= 256:
            raise ValueError('1..256 frame events required')
        previous, events = -1, {}
        for event in value['frames']:
            if not isinstance(event, dict) or set(event) != {'frame', 'points'} or type(event['frame']) is not int or not previous < event['frame'] < frames:
                raise ValueError('frame events must increase within output range')
            previous = event['frame']
            if not isinstance(event['points'], list) or not 1 <= len(event['points']) <= 32:
                raise ValueError('1..32 points per frame required')
            points = []
            for point in event['points']:
                if not isinstance(point, dict) or not {'x', 'y', 'expected'} <= set(point) or set(point)-{'x', 'y', 'expected', 'radius_pixels', 'minimum_fraction'}:
                    raise ValueError('invalid point fields')
                if any(not number(point[k]) or not 0 <= point[k] <= 1 for k in ('x', 'y')) or point['expected'] not in {'selected', 'clear'}:
                    raise ValueError('invalid point coordinates or selection')
                radius, minimum = point.get('radius_pixels', 0), point.get('minimum_fraction', 1.)
                if type(radius) is not int or not 0 <= radius <= 64 or not number(minimum) or not 0 < minimum <= 1:
                    raise ValueError('invalid point radius or required fraction')
                points.append({**point, 'radius_pixels': radius, 'minimum_fraction': minimum})
            events[event['frame']] = points
        return {'path': str(source), 'sha256': 'sha256:'+hashlib.sha256(raw).hexdigest()}, events
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise AppError('ARGUMENT_INVALID', '蒙版检查点格式无效', exit_code=2, path='expectations', cause=str(exc)) from exc


def prepare(root, asset, *, channel='alpha', threshold=127, fps=None, max_edge=1280, max_frames=4096, budget_mib=256, expectations=None, scene_cuts=()):
    if channel not in {'alpha', 'luma'} or type(threshold) is not int or not 0 <= threshold <= 254:
        raise argument_error('channel 或 threshold 无效', 'channel/threshold')
    if type(max_edge) is not int or not 0 <= max_edge <= 8192 or type(max_frames) is not int or not 1 <= max_frames <= 10000 or type(budget_mib) is not int or not 1 <= budget_mib <= 1024:
        raise argument_error('蒙版解码边长、帧数或预算无效', 'max-edge/max-frames/budget-mib')
    if asset.get('kind') not in {'image', 'video'}:
        raise argument_error('蒙版须为已登记图像或视频', 'asset-id')
    if asset['kind'] == 'image' and fps is not None:
        raise argument_error('静态图像只检查一帧，不接受 fps', 'fps')
    source = resolve_local_path(root, asset['uri'], field='asset.uri')
    if not source.is_file() or 'sha256:'+sha256_file(source) != asset['sha256']:
        raise AppError('MASK_REVIEW_SOURCE_CHANGED', '蒙版素材缺失或哈希已变化', exit_code=6, path=str(source))
    probe = probe_media(source)
    stream = next((s for s in probe['streams'] if s.get('codec_type') == 'video'), None)
    if stream is None:
        raise argument_error('素材没有视频流', 'asset-id')
    alpha = str(stream.get('pix_fmt', '')).startswith(('rgba', 'bgra', 'argb', 'abgr', 'yuva', 'gbrap', 'ya')) or stream.get('pix_fmt') == 'pal8' or str(stream.get('tags', {}).get('alpha_mode', '')) == '1'
    if channel == 'alpha' and not alpha:
        raise argument_error('素材未声明 alpha；黑白蒙版请显式选 luma', 'channel')
    try:
        sar_text = stream.get('sample_aspect_ratio')
        sar = Fraction(sar_text.replace(':', '/')) if sar_text not in (None, 'N/A', '0:1') else Fraction(1)
        rotation = float(next((s['rotation'] for s in stream.get('side_data_list', []) if 'rotation' in s), stream.get('tags', {}).get('rotate', 0)))
        sw, sh = int(stream['width']), int(stream['height'])
        if sar <= 0 or not math.isfinite(rotation) or rotation % 90 or min(sw, sh) < 1 or max(sw, sh) > 8192:
            raise ValueError('invalid display geometry')
        width, height = sw*float(sar), float(sh)
        if abs(rotation) % 180 == 90:
            width, height = height, width
        scale = min(1., max_edge/max(width, height)) if max_edge else 1.
        width, height = max(2, round(width*scale)), max(2, round(height*scale))
        rate = Fraction(fps if fps is not None else stream.get('avg_frame_rate') or stream.get('r_frame_rate') or '0') if asset['kind'] == 'video' else Fraction(1)
        duration = float(stream.get('duration') or probe['duration_seconds']) if asset['kind'] == 'video' else 1.
        if not 0 < rate <= 240 or not math.isfinite(duration) or not 0 < duration <= 7200 or width*height > 8192**2:
            raise ValueError('invalid clock or size')
        frames = math.ceil(duration*float(rate)-1e-8) if asset['kind'] == 'video' else 1
        if not 1 <= frames <= max_frames or width*height*frames > budget_mib*1024*1024:
            raise ValueError('decoded frame/storage budget exceeded')
        cuts = sorted(scene_cuts)
        if len(set(cuts)) != len(cuts) or any(type(v) is not int or not 1 <= v < frames for v in cuts):
            raise ValueError('invalid scene cut frames')
    except (ValueError, TypeError, OverflowError, ZeroDivisionError, KeyError, AttributeError) as exc:
        raise AppError('ARGUMENT_INVALID', '蒙版输出时钟、尺寸或解码预算无效', exit_code=2, path='mask-review', cause=str(exc)) from exc
    proof, events = load_expectations(root, expectations, frames)
    return {'version': VERSION, 'source': {'path': str(source), 'sha256': asset['sha256'], 'asset_id': asset['id']},
            'channel': channel, 'threshold': threshold, 'video': {'width': width, 'height': height, 'frames': frames, 'fps': str(rate)},
            'source_geometry': {'width': sw, 'height': sh, 'sar': str(sar), 'rotation': rotation}, 'source_duration_seconds': duration,
            'clock': 'single-image' if asset['kind'] == 'image' else 'cfr-display-origin-with-last-frame-padding-at-most-one-output-frame',
            'source_stream_index': int(stream['index']), 'decoder': ('libvpx-vp9' if stream.get('codec_name') == 'vp9' else 'libvpx' if stream.get('codec_name') == 'vp8' else None) if channel == 'alpha' else None,
            'decoded_storage_bytes': width*height*frames, 'decoded_storage_budget_bytes': budget_mib*1024*1024,
            'budget_scope': 'temporary-decoded-gray-storage; excludes-ffmpeg-and-total-process-ram', 'expectations': proof,
            'scene_cut_frames': cuts, 'events': events}


def analyze_frames(source, plan):
    video = plan['video']; width, height, count = video['width'], video['height'], video['frames']
    lookup = bytes(int(i > plan['threshold']) for i in range(256))
    previous = None; previous_count = 0; records = []; failures = []; flags = {}
    digest = hashlib.sha256()
    for index in range(count):
        raw = source.read(width*height)
        if len(raw) != width*height:
            raise AppError('MASK_REVIEW_DECODE_INVALID', '蒙版解码帧不完整', exit_code=6)
        digest.update(raw); binary = raw.translate(lookup); selected = binary.count(1)
        min_x, min_y, max_x, max_y = width, height, -1, -1
        for y in range(height):
            row = binary[y*width:(y+1)*width]
            first = row.find(b'\x01')
            if first >= 0:
                min_x, min_y = min(min_x, first), min(min_y, y)
                max_x, max_y = max(max_x, row.rfind(b'\x01')), y
        bbox = [min_x, min_y, max_x+1, max_y+1] if selected else None
        iou = ratio = None; notes = []
        if not selected: notes.append('MASK_EMPTY')
        if bbox and (min_x == 0 or min_y == 0 or max_x == width-1 or max_y == height-1): notes.append('MASK_TOUCHES_CANVAS_EDGE')
        if previous is not None and index not in plan['scene_cut_frames']:
            changed = sum(a != b for a, b in zip(previous, binary))
            intersection = (selected+previous_count-changed)//2
            union = (selected+previous_count+changed)//2
            iou = intersection/union if union else None
            ratio = selected/previous_count if previous_count else None
            if selected and previous_count and (ratio > 3 or ratio < 1/3): notes.append('MASK_AREA_JUMP')
            if bool(selected) != bool(previous_count): notes.append('MASK_PRESENCE_CHANGED')
        for note in notes: flags.setdefault(note, []).append(index)
        checks = []
        for point in plan['events'].get(index, []):
            cx, cy = min(width-1, int(point['x']*width)), min(height-1, int(point['y']*height))
            radius = point['radius_pixels']
            x0, y0, x1, y1 = max(0, cx-radius), max(0, cy-radius), min(width, cx+radius+1), min(height, cy+radius+1)
            foreground = sum(binary[y*width+x0:y*width+x1].count(1) for y in range(y0, y1))
            pixels = (x1-x0)*(y1-y0)
            fraction = foreground/pixels if point['expected'] == 'selected' else (pixels-foreground)/pixels
            check = {**point, 'window_pixels': [x0, y0, x1, y1], 'selected_pixels': foreground, 'pixels': pixels,
                     'observed_fraction': fraction, 'passed': fraction >= point['minimum_fraction']}
            checks.append(check)
            if not check['passed']: failures.append({'frame': index, **check})
        records.append({'frame': index, 'seconds': index/float(Fraction(video['fps'])), 'selected_pixels': selected,
                        'selected_fraction': selected/(width*height), 'bbox_pixels': bbox,
                        'bbox_normalized': [min_x/width, min_y/height, (max_x+1)/width, (max_y+1)/height] if selected else None,
                        'alpha_min': min(raw), 'alpha_max': max(raw), 'alpha_mean': sum(raw)/(width*height*255),
                        'previous_frame_iou': iou, 'previous_frame_area_ratio': ratio, 'review_flags': notes, 'checks': checks})
        previous, previous_count = binary, selected
    if source.read(1):
        raise AppError('MASK_REVIEW_DECODE_INVALID', '蒙版解码含多余帧或字节', exit_code=6)
    return {'ok': not failures, 'expectations_checked': plan['expectations'] is not None,
            'semantic_quality_accepted': False, 'gray_sha256': 'sha256:'+digest.hexdigest(), 'frames': records,
            'checked_points': sum(len(r['checks']) for r in records), 'failed_points': failures,
            'warnings': [{'code': 'MASK_SEMANTIC_REVIEW_REQUIRED', 'message': '像素范围和检查点不证明完整对象、身份或自然分割质量'}] +
                        [{'code': code, 'frames': frames, 'message': '仅供复核，可能由正常运动、遮挡或画面边缘造成'} for code, frames in flags.items()],
            'errors': [{'code': 'MASK_EXPECTATION_FAILED', 'message': f'{len(failures)} 个明确检查点未通过'}] if failures else []}


def review(root: Path, plan: dict):
    info = plan['video']; source = Path(plan['source']['path'])
    work = root/'cache'/'mask-review'; work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='decode-', dir=work) as raw_dir:
        target = Path(raw_dir)/'mask.gray'
        argv = [ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-y']
        if plan['decoder']: argv += ['-c:v', plan['decoder']]
        filters = ['setpts=PTS-STARTPTS']
        if plan['clock'] != 'single-image': filters.append('fps='+info['fps'])
        filters += [f"scale={info['width']}:{info['height']}:flags=neighbor", 'setsar=1']
        filters += ['format=rgba', 'alphaextract'] if plan['channel'] == 'alpha' else ['format=gray']
        if plan['clock'] != 'single-image':
            filters += [f"tpad=stop_mode=clone:stop_duration={1/float(Fraction(info['fps'])):.12f}"]
        argv += ['-protocol_whitelist', 'file,pipe', '-i', str(source), '-map', '0:'+str(plan['source_stream_index']), '-an', '-sn', '-dn', '-vf', ','.join(filters),
                 '-frames:v', str(info['frames']), '-f', 'rawvideo', '-pix_fmt', 'gray', str(target)]
        completed = run_process(argv, timeout=180)
        if completed.returncode:
            raise AppError('MASK_REVIEW_DECODE_FAILED', '本地 FFmpeg 蒙版解码失败', exit_code=6, cause=completed.stderr[-2000:])
        if target.stat().st_size != plan['decoded_storage_bytes']:
            raise AppError('MASK_REVIEW_DECODE_INVALID', '实际蒙版字节数与声明输出时钟不符', exit_code=6)
        with target.open('rb') as handle: result = analyze_frames(handle, plan)
    for proof in (plan['source'], plan['expectations']):
        if proof and ('sha256:'+sha256_file(Path(proof['path'])) != proof['sha256']):
            raise AppError('MASK_REVIEW_INPUT_CHANGED', '蒙版或检查点在执行期间变化', exit_code=6)
    return {'report_version': VERSION, 'plan': {k: v for k, v in plan.items() if k != 'events'},
            'ffmpeg': ffmpeg_version(), 'network': 'disabled', **result}
