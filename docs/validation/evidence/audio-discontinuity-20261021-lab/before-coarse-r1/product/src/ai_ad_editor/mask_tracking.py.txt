"""Turn an explicitly selected encoded mask into source-clock bbox observations."""
from __future__ import annotations

from bisect import bisect_left
from fractions import Fraction
import math
from pathlib import Path

from .errors import AppError, argument_error
from .mask_review import prepare as prepare_review, review
from .media import probe_media
from .policy import resolve_local_path
from .utils import atomic_write_json, sha256_file

ENGINE = 'local-mask-bbox-tracking-v1'


def _finite(value):
    try:
        return type(value) in {int, float} and math.isfinite(value)
    except OverflowError:
        return False


def _source_geometry(stream):
    sar = stream.get('sample_aspect_ratio')
    ratio = Fraction(sar.replace(':', '/')) if sar not in (None, 'N/A', '0:1') else Fraction(1)
    rotation = float(next((s['rotation'] for s in stream.get('side_data_list', []) if 'rotation' in s), stream.get('tags', {}).get('rotate', 0)))
    width, height = int(stream['width']) * float(ratio), float(stream['height'])
    if ratio <= 0 or not math.isfinite(rotation) or rotation % 90 or min(width, height) <= 0:
        raise ValueError('invalid source display geometry')
    return (height, width) if abs(rotation) % 180 == 90 else (width, height)


def prepare(root, source_asset, mask_asset, *, start_seconds=0., end_seconds=None, source_start_seconds=0.,
            channel='alpha', threshold=127, max_edge=1280, max_frames=4096, budget_mib=256,
            expectations=None, scene_cuts=(), step_frames=4, max_samples=600, ticks_per_second=90000):
    if source_asset.get('kind') != 'video' or mask_asset.get('kind') != 'video':
        raise argument_error('蒙版跟踪需要已登记的源视频和蒙版视频', 'asset-id/mask-asset-id')
    source = resolve_local_path(root, source_asset['uri'], field='asset.uri')
    if not source.is_file() or 'sha256:' + sha256_file(source) != source_asset['sha256']:
        raise AppError('MASK_TRACK_SOURCE_CHANGED', '跟踪源与登记摘要不符', exit_code=6, path=str(source))
    if not _finite(start_seconds) or start_seconds < 0 or not _finite(source_start_seconds) or source_start_seconds < 0:
        raise argument_error('源起点与蒙版对应源时刻须为非负有限数字', 'start-seconds/mask-source-start-seconds')
    if type(step_frames) is not int or not 1 <= step_frames <= 10000 or type(max_samples) is not int or not 2 <= max_samples <= 10000 or type(ticks_per_second) is not int or ticks_per_second < 1:
        raise argument_error('step-frames=1..10000，max-samples=2..10000，timebase>0', 'step-frames/max-samples')
    probe = probe_media(source)
    try:
        stream = next(s for s in probe['streams'] if s.get('codec_type') == 'video')
        source_width, source_height = _source_geometry(stream)
        duration = float(stream.get('duration') or probe['duration_seconds'])
        end = duration if end_seconds is None else end_seconds
        if not _finite(end) or not _finite(duration) or not 0 <= start_seconds < end <= duration + 1e-8:
            raise ValueError('source range exceeds duration')
    except (ValueError, KeyError, TypeError, StopIteration, OverflowError, ZeroDivisionError) as exc:
        raise AppError('MASK_TRACK_SOURCE_INVALID', '源画面或范围无效', exit_code=2, cause=str(exc)) from exc
    mask = prepare_review(root, mask_asset, channel=channel, threshold=threshold, max_edge=max_edge,
                          max_frames=max_frames, budget_mib=budget_mib, expectations=expectations, scene_cuts=scene_cuts)
    geometry = mask['source_geometry']
    mask_width = geometry['width'] * float(Fraction(geometry['sar']))
    mask_height = float(geometry['height'])
    if abs(geometry['rotation']) % 180 == 90:
        mask_width, mask_height = mask_height, mask_width
    aspect_error = abs(mask_width - mask_height * source_width / source_height)
    if aspect_error > 1.000001:
        raise AppError('MASK_TRACK_ASPECT_MISMATCH', '源和蒙版显示纵横比不同，不能隐式对齐裁切', exit_code=2)
    rate = Fraction(mask['video']['fps'])
    covered_end = source_start_seconds + min(mask['source_duration_seconds'], mask['video']['frames'] / float(rate))
    if start_seconds < source_start_seconds - 1e-8 or end > covered_end + 1e-8:
        raise AppError('MASK_TRACK_RANGE_UNCOVERED', '蒙版时钟未覆盖请求的源范围', exit_code=2)
    if any(start_seconds + 1e-8 < source_start_seconds + frame / float(rate) < end - 1e-8 for frame in mask['scene_cut_frames']):
        raise AppError('MASK_TRACK_SCENE_CUT', '跟踪范围不能跨显式切点，请分段执行', exit_code=2)
    rights = []
    for asset in (source_asset, mask_asset):
        reference = asset.get('rights_ref')
        if not reference:
            raise AppError('RIGHTS_RECORD_MISSING', '源/蒙版缺少权利引用', exit_code=7)
        item = {'rights_ref': reference, 'sha256': asset['sha256']}
        if item not in rights:
            rights.append(item)
    return {'engine': ENGINE, 'source': str(source), 'source_sha256': source_asset['sha256'],
            'asset_id': source_asset['id'], 'mask_asset_id': mask_asset['id'], 'mask_source_start_seconds': source_start_seconds,
            'source_display': {'width': source_width, 'height': source_height},
            'source_coded': {'width': int(stream['width']), 'height': int(stream['height'])}, 'aspect_error_mask_pixels': aspect_error,
            'range': {'start_seconds': start_seconds, 'end_seconds': end}, 'step_frames': step_frames,
            'max_samples': max_samples, 'ticks_per_second': ticks_per_second, 'rights_dependencies': rights, 'mask_plan': mask,
            'confidence_semantics': 'nonempty-selection-availability; not-model-confidence-or-accuracy', 'network': 'disabled'}


def public_plan(plan):
    return {**plan, 'mask_plan': {k: v for k, v in plan['mask_plan'].items() if k != 'events'}}


def observations(report, plan):
    """Interpolate only encoded box geometry; never invent an occluded object."""
    rate = float(Fraction(plan['mask_plan']['video']['fps']))
    origin = plan['mask_source_start_seconds']
    start, end = plan['range']['start_seconds'], plan['range']['end_seconds']
    records = report['frames']; times = [origin + r['frame'] / rate for r in records]
    left = max(0, bisect_left(times, start) - (start not in times))
    right = min(len(records) - 1, bisect_left(times, end))
    cuts = set(plan['mask_plan']['scene_cut_frames'])
    if right in cuts and end <= times[right] + 1e-8:
        right -= 1
    empty = [records[i]['frame'] for i in range(left, right + 1) if not records[i]['selected_pixels']]
    if empty:
        raise AppError('MASK_TRACK_EMPTY_SELECTION', '请求范围或插值相邻帧存在空选区，无法伪造连续对象', exit_code=2, cause=str(empty))
    samples = [start]
    samples += [t for i, t in enumerate(times) if start < t < end and (i - left) % plan['step_frames'] == 0]
    samples.append(end)
    # Endpoints can include interpolation or a terminal hold; preserve both.
    reduced = len(samples) > plan['max_samples']
    if reduced:
        count = plan['max_samples']
        samples = [samples[round(i * (len(samples) - 1) / (count - 1))] for i in range(count)]
    frames = []; interpolated = held = scene_holds = 0; seen_ticks = set()
    for second in samples:
        index = bisect_left(times, second)
        if index >= len(times):
            box = records[-1]['bbox_normalized']; method = 'terminal-hold'; held += 1
        elif index in cuts and (second < times[index] - 1e-8 or second > start) and second <= times[index] + 1e-8:
            box = records[index-1]['bbox_normalized']; method = 'scene-boundary-hold'; scene_holds += 1
        elif abs(times[index] - second) < 1e-8:
            box = records[index]['bbox_normalized']; method = 'observed'
        else:
            if index == 0:
                raise AppError('MASK_TRACK_RANGE_UNCOVERED', '没有边界插值观测', exit_code=2)
            a, b = records[index-1]['bbox_normalized'], records[index]['bbox_normalized']
            fraction = (second - times[index-1]) / (times[index] - times[index-1])
            box = [x + (y - x) * fraction for x, y in zip(a, b)]
            method = 'linear-boundary-interpolation'; interpolated += 1
        tick = round((second - start) * plan['ticks_per_second'])
        if tick in seen_ticks:
            raise AppError('MASK_TRACK_TIMEBASE_COLLISION', '采样时刻在项目 timebase 中重合', exit_code=2)
        seen_ticks.add(tick)
        x0, y0, x1, y1 = box
        frames.append({'at_seconds': second, 'at_tick': tick, 'x': (x0+x1)/2, 'y': (y0+y1)/2,
                       'width': x1-x0, 'height': y1-y0, 'confidence': 1., 'measurement': method})
    return frames, {'boundary_interpolations': interpolated, 'terminal_holds': held, 'scene_boundary_holds': scene_holds, 'sampling_reduced_to_budget': reduced,
                    'selection_frames_checked': right-left+1, 'total_encoded_frames_reviewed': len(records)}


def execute(root, plan, *, failure_report):
    result = None
    try:
        result = review(root, plan['mask_plan'])
        if not result['ok']:
            raise AppError('MASK_TRACK_EXPECTATION_FAILED', '明确蒙版检查点失败，未应用跟踪', exit_code=2)
        frames, metrics = observations(result, plan)
        if 'sha256:' + sha256_file(Path(plan['source'])) != plan['source_sha256']:
            raise AppError('MASK_TRACK_SOURCE_CHANGED', '执行期间源媒体摘要改变', exit_code=6)
    except AppError as exc:
        atomic_write_json(failure_report, {'report_version': '0.1.0', 'status': 'failed', 'engine': ENGINE,
                                          'error': {'code': exc.code, 'message': str(exc)}, 'plan': public_plan(plan), 'mask_review': result})
        exc.path = str(failure_report)
        raise
    return {'engine': ENGINE, 'method': 'encoded-mask-bbox-center', 'source': plan['source'], 'source_sha256': plan['source_sha256'],
            'asset_id': plan['asset_id'], 'mask_asset_id': plan['mask_asset_id'], 'mask_source_start_seconds': plan['mask_source_start_seconds'],
            'source_display': plan['source_display'], 'range': {**plan['range'], 'mask_fps': plan['mask_plan']['video']['fps'],
               'step_frames': plan['step_frames'], 'max_samples': plan['max_samples']}, 'ticks_per_second': plan['ticks_per_second'],
            'frames': frames, 'keyframes': [{'property': 'transform.position.' + axis,
                'keyframes': [{'at_tick': f['at_tick'], 'value': f[axis], 'interpolation': 'linear'} for f in frames]} for axis in ('x', 'y')],
            'mask_review': result, 'metrics': metrics, 'rights_dependencies': plan['rights_dependencies'],
            'confidence_semantics': plan['confidence_semantics'], 'network': 'disabled',
            'warnings': ['mask_selection_identity_and_extent_require_review', 'bbox_geometry_is_not_pose_or_model_accuracy']}
