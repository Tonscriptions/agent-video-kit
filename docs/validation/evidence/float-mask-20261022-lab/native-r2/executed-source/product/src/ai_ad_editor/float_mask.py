"""Bounded floating alpha masks for the author-clock frame host.

Independent NumPy geometry and box averages; no native filter source is copied.
Integer pixel centres, even/odd polygon filling and sampled cubic paths retain
the authored mask contract. RGB stays straight and bit-preserved here.
"""
from dataclasses import dataclass
import json
import math

import numpy as np

from .animation import keyframe_value
from .errors import AppError

PROTOCOL = 'author-clock-float32-alpha-mask-v1'
MAX_PIXELS = 16777216
MAX_WORKING_BYTES = 768*1024**2
MAX_TILE_PIXELS = 262144
FIELDS = {
    'rectangle': [('x', 'position.x'), ('y', 'position.y'), ('width', 'w'), ('height', 'h')],
    'circle': [('cx', 'center_x'), ('cy', 'center_y'), ('radius',)],
    'ellipse': [('cx', 'center_x'), ('cy', 'center_y'), ('rx', 'radius_x'), ('ry', 'radius_y')],
}
LINE_POINTS = (('from', 'p0', 'start'), ('to', 'p1', 'end'))
CUBIC_POINTS = (LINE_POINTS[0], ('control1', 'p1', 'c1'), ('control2', 'p2', 'c2'), ('to', 'p3', 'end'))


def error(code, message):
    return AppError('FLOAT_MASK_'+code, message, exit_code=2)


def number(value, high=1):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise error('ARGUMENT', '蒙版参数必须为有限数字')
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= high:
        raise error('ARGUMENT', '蒙版参数超出声明范围')
    return value


def names(values):
    return tuple('mask.'+v for v in values)


def point(value):
    if isinstance(value, dict) and set(value) == {'x', 'y'}:
        return [number(value['x']), number(value['y'])]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [number(v) for v in value]
    raise error('ARGUMENT', '路径点须为归一化[x,y]或{x,y}')


@dataclass(frozen=True)
class MaskPlan:
    # Immutable JSON prevents later edits to the author's dictionaries from
    # changing a compiled frame operation or its recorded identity.
    payload: str
    properties: frozenset[str]


def compile_mask(clip):
    mask = clip.get('mask')
    if mask is None or mask == {}:
        return None
    if not isinstance(mask, dict):
        raise error('ARGUMENT', '蒙版须为对象')
    kind = mask.get('type', 'rectangle')
    if kind not in (*FIELDS, 'path', 'polygon', 'none', 'off'):
        raise AppError('FLOAT_TIMELINE_UNSUPPORTED', '该蒙版类型尚未接入浮点宿主', exit_code=2)
    if kind in ('none', 'off'):
        if mask.get('keyframes'):
            raise error('ARGUMENT', '关闭的蒙版不能携带执行关键帧')
        return None
    if type(mask.get('invert', False)) is not bool:
        raise error('ARGUMENT', 'invert须为布尔值')
    allowed_fields = {'type', 'invert', 'feather', 'keyframes'}
    allowed_names = {'mask.feather'}
    record = {'kind':kind, 'invert':mask.get('invert', False), 'feather':number(mask.get('feather', 0), .5),
              'fields':[], 'points':[], 'segments':[], 'tracks':[]}
    if kind in FIELDS:
        defaults = {'x':0, 'y':0, 'width':1, 'height':1, 'cx':.5, 'cy':.5, 'radius':.5, 'rx':.5, 'ry':.5}
        for aliases in FIELDS[kind]:
            static = tuple(v for v in aliases if not v.startswith('position.'))
            allowed_fields.update(static)
            present = [number(mask[n]) for n in static if n in mask]
            if len(set(present)) > 1:
                raise error('ARGUMENT', '蒙版几何别名冲突')
            default = present[0] if present else defaults[aliases[0]]
            if kind == 'ellipse' and aliases[0] in ('rx', 'ry'):
                default = max(.001, default)
            record['fields'].append([names(aliases), default])
            allowed_names.update(names(aliases))
    else:
        allowed_fields.update(('points', 'segments', 'curve_segments', 'curves'))
        segment_fields = [n for n in ('segments', 'curve_segments', 'curves') if n in mask]
        if len(segment_fields) > 1 or ('points' in mask and segment_fields):
            raise error('ARGUMENT', '路径点和曲线段不能同时声明')
        if 'points' in mask:
            raw = mask['points']
            if not isinstance(raw, list) or not 3 <= len(raw) <= 32:
                raise error('ARGUMENT', '多边形须有3到32个点')
            for i, p in enumerate(raw):
                p = point(p)
                axes = [names(tuple(f'{field}{index}.{axis}' for field in ('points', 'point')
                    for index in (f'.{i}', f'[{i}]'))) for axis in ('x', 'y')]
                record['points'].append([axes, p])
                for a in axes:
                    allowed_names.update(a)
        elif segment_fields:
            raw_field = segment_fields[0]
            segments = mask[raw_field]
            if not isinstance(segments, list) or not 1 <= len(segments) <= 8:
                raise error('ARGUMENT', '曲线段数须为1到8')
            for i, segment in enumerate(segments):
                if not isinstance(segment, dict):
                    raise error('ARGUMENT', '曲线段须为对象')
                segment_type = segment.get('type', 'cubic')
                if segment_type in ('line', 'linear'):
                    controls, samples = LINE_POINTS, 1
                elif segment_type in ('cubic', 'bezier', 'cubic_bezier'):
                    controls, samples = CUBIC_POINTS, segment.get('samples', 8)
                    if type(samples) is not int or not 2 <= samples <= 16:
                        raise error('ARGUMENT', '三次曲线采样数须为2到16')
                else:
                    raise error('ARGUMENT', '未知曲线段类型')
                if set(segment)-{'type', 'samples', *(v for a in controls for v in a)}:
                    raise error('ARGUMENT', '曲线段包含未知字段')
                compiled = []
                for aliases in controls:
                    present = [point(segment[n]) for n in aliases if n in segment]
                    if not present or any(p != present[0] for p in present):
                        raise error('ARGUMENT', '曲线控制点缺少或别名冲突')
                    axes = [names(tuple(dict.fromkeys(f'{field}.{i}.{alias}.{axis}'
                        for field in (raw_field, 'segments', 'curve_segments', 'curves') for alias in aliases)))
                        for axis in ('x', 'y')]
                    compiled.append([axes, present[0]])
                    for a in axes:
                        allowed_names.update(a)
                record['segments'].append([samples, compiled])
            if sum(s[0]+1 for s in record['segments']) > 32:
                raise error('ARGUMENT', '曲线全部采样候选点不得超过32，不能静默截断')
        else:
            raise error('ARGUMENT', '路径须有合法点或曲线段')
    if set(mask)-allowed_fields:
        raise error('ARGUMENT', '蒙版包含未执行字段')
    raw_properties = set()
    for local, tracks in ((False, clip.get('keyframes', [])), (True, mask.get('keyframes', []))):
        if not isinstance(tracks, list) or len(tracks) > 128:
            raise error('ARGUMENT', '蒙版关键帧轨道须为最多128项数组')
        seen = set()
        for track in tracks:
            if not isinstance(track, dict) or not isinstance(track.get('property'), str):
                raise error('ARGUMENT', '关键帧轨道须有属性名')
            raw_name = track['property']
            canonical = raw_name if raw_name.startswith('mask.') else 'mask.'+raw_name
            if canonical not in allowed_names:
                if local or raw_name.startswith('mask.'):
                    raise error('ARGUMENT', '蒙版关键帧属性与实际几何不匹配')
                continue
            if canonical in seen:
                raise error('ARGUMENT', '同一层蒙版关键帧属性重复')
            seen.add(canonical)
            keys = track.get('keyframes')
            if set(track)-{'property', 'keyframes'} or not isinstance(keys, list) or not 1 <= len(keys) <= 1024:
                raise error('ARGUMENT', '蒙版关键帧须为1到1024项')
            previous = -1
            for key in keys:
                if not isinstance(key, dict) or set(key)-{'at_tick', 'value', 'interpolation', 'control_points'}:
                    raise error('ARGUMENT', '蒙版关键帧包含未知字段')
                at = key.get('at_tick')
                if type(at) is not int or at <= previous:
                    raise error('ARGUMENT', '蒙版关键帧时钟须为递增非负整数')
                previous = at
                number(key.get('value'), .5 if canonical == 'mask.feather' else 1)
                mode = key.get('interpolation', 'linear')
                if mode not in ('linear', 'hold', 'ease_in', 'ease_out', 'ease_in_out', 'bezier'):
                    raise error('ARGUMENT', '蒙版关键帧插值未知')
                if mode == 'bezier':
                    cp = key.get('control_points')
                    if not isinstance(cp, list) or len(cp) not in (2, 4) or any(type(v) not in (int, float) or not math.isfinite(v) for v in cp):
                        raise error('ARGUMENT', 'Bezier须为2或4个有限控制值')
                    if len(cp) == 4 and (not 0 <= cp[0] <= 1 or not 0 <= cp[2] <= 1):
                        raise error('ARGUMENT', 'Bezier横向控制值须在0到1')
            record['tracks'].append({'property':canonical, 'keyframes':keys})
            if not local:
                raw_properties.add(raw_name)
    return MaskPlan(json.dumps(record, allow_nan=False, sort_keys=True, separators=(',', ':')), frozenset(raw_properties))


def _resolved(plan, tick):
    if not isinstance(plan, MaskPlan) or isinstance(tick, bool):
        raise error('ARGUMENT', '蒙版须使用编译计划和有限作者时钟')
    try:
        tick = float(tick)
    except (ValueError, TypeError, OverflowError) as caught:
        raise error('ARGUMENT', '蒙版作者时钟无效') from caught
    if not math.isfinite(tick):
        raise error('ARGUMENT', '蒙版作者时钟无效')
    record = json.loads(plan.payload)
    clip = {'keyframes':record['tracks']}
    def value(aliases, default, maximum=1):
        v = keyframe_value(clip, tuple(aliases), default, tick)
        if not math.isfinite(v):
            raise error('VALUES', '蒙版动画计算结果不是有限数字')
        return min(maximum, max(0., v))
    fields = [value(a, d) for a, d in record['fields']]
    def p(control):
        aliases, defaults = control
        return tuple(value(a, d) for a, d in zip(aliases, defaults))
    points = [p(c) for c in record['points']]
    for samples, controls in record['segments']:
        controls = [p(c) for c in controls]
        for index in range(samples+1):
            u = index/samples
            weights = (1-u, u) if len(controls) == 2 else ((1-u)**3, 3*(1-u)**2*u, 3*(1-u)*u*u, u**3)
            candidate = tuple(sum(weight*c[axis] for weight, c in zip(weights, controls)) for axis in (0, 1))
            if not points or candidate != points[-1]:
                points.append(candidate)
    if record['kind'] in ('path', 'polygon') and len(points) < 3:
        raise error('VALUES', '当前作者时钟上的路径少于3个不同相邻采样点')
    feather = value(('mask.feather',), record['feather'], .5)
    dynamic = any(t['property'] == 'mask.feather' for t in record['tracks'])
    return record['kind'], fields, points, feather, dynamic, record['invert']


def _coverage(kind, fields, points, x, y, width, height, feather, dynamic):
    if kind == 'rectangle':
        left, top, right, bottom = fields[0]*width, fields[1]*height, (fields[0]+fields[2])*width, (fields[1]+fields[3])*height
        inside = (x >= left) & (x <= min(width, right)) & (y >= top) & (y <= min(height, bottom))
        distance = np.minimum(np.minimum(x-left, right-x), np.minimum(y-top, bottom-y)) if dynamic else None
    elif kind in ('circle', 'ellipse'):
        cx, cy = fields[0]*width, fields[1]*height
        if kind == 'circle':
            radius = fields[2]*min(width, height)
            radial = np.hypot(x-cx, y-cy)
            inside, distance = radial <= radius, radius-radial
        else:
            rx, ry = max(fields[2], 1e-6)*width, max(fields[3], 1e-6)*height
            radial = np.hypot((x-cx)/rx, (y-cy)/ry)
            inside, distance = radial <= 1, (1-radial)*min(rx, ry)
    else:
        inside = np.zeros(x.shape, bool)
        distance = np.full(x.shape, np.inf, np.float64) if dynamic else None
        for i, (a, b) in enumerate(points):
            c, d = points[(i+1) % len(points)]
            a, b, c, d = a*width, b*height, c*width, d*height
            dx, dy = c-a, d-b
            if dy:
                crossed = ((b >= y) & (d < y)) | ((b < y) & (d >= y))
                inside ^= crossed & (x < a+dx*(y-b)/dy)
            if dynamic:
                length = max(dx*dx+dy*dy, 1e-6)
                u = np.clip(((x-a)*dx+(y-b)*dy)/length, 0, 1)
                np.minimum(distance, np.hypot(x-a-u*dx, y-b-u*dy), out=distance)
        if dynamic:
            distance = np.where(inside, distance, -1.)
    if dynamic and feather > 0:
        return np.clip(distance/max(1e-6, min(width, height)*feather), 0, 1)
    return inside.astype(np.float64)


def _box_pass(alpha, radius, axis, tile_pixels, poll):
    """One normalized symmetric-edge box average using bounded row strips."""
    rows = alpha if axis == 1 else alpha.T
    length = rows.shape[1]
    block = max(1, tile_pixels//(length+2*radius+1))
    for start in range(0, len(rows), block):
        poll()
        end = min(len(rows), start+block)
        padded = np.pad(rows[start:end], ((0, 0), (radius, radius)), mode='symmetric')
        prefix = np.empty((end-start, padded.shape[1]+1), np.float64)
        prefix[:, 0] = 0
        np.cumsum(padded, axis=1, dtype=np.float64, out=prefix[:, 1:])
        rows[start:end] = (prefix[:, 2*radius+1:]-prefix[:, :length])/(2*radius+1)


def apply_mask(surface, plan, tick, *, tile_pixels=65536, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    if cancel is not None and not callable(cancel):
        raise error('ARGUMENT', '蒙版取消回调须可调用')
    poll = cancel if cancel is not None else lambda:None
    poll()
    if not isinstance(surface, np.ndarray) or surface.dtype != np.float32 or surface.ndim != 3 or surface.shape[-1] != 4 or not surface.flags.c_contiguous:
        raise error('SURFACE', '蒙版须为连续H×W×4 Float32表面')
    height, width = surface.shape[:2]
    pixels = height*width
    if min(height, width) < 1 or max(height, width) > 16384 or pixels > MAX_PIXELS:
        raise error('BUDGET', '蒙版表面尺寸超限')
    if type(tile_pixels) is not int or not 1 <= tile_pixels <= MAX_TILE_PIXELS or type(max_working_bytes) is not int or not 1 <= max_working_bytes <= MAX_WORKING_BYTES:
        raise error('BUDGET', '蒙版工作区或分块预算无效')
    kind, fields, points, feather, dynamic, invert = _resolved(plan, tick)
    estimated = pixels*40+max(min(pixels, tile_pixels), 4*max(width, height))*256+16384
    if estimated > max_working_bytes:
        raise error('BUDGET', '蒙版工作区估算超限')
    source = surface.reshape(-1, 4)
    alpha = np.empty(pixels, np.float64)
    for start in range(0, pixels, tile_pixels):
        poll()
        end = min(start+tile_pixels, pixels)
        chunk = source[start:end]
        if not np.isfinite(chunk).all() or np.any(chunk[:, 3] < 0) or np.any(chunk[:, 3] > 1):
            raise error('VALUES', '蒙版RGB须有限，alpha须在0到1')
        index = np.arange(start, end, dtype=np.int64)
        x, y = (index % width).astype(np.float64), (index//width).astype(np.float64)
        coverage = _coverage(kind, fields, points, x, y, width, height, feather, dynamic)
        if invert:
            coverage = 1-coverage
        alpha[start:end] = chunk[:, 3].astype(np.float64)*coverage
    radius = int(min(width, height)*feather) if not dynamic else 0
    alpha = alpha.reshape(height, width)
    if radius:
        for axis in (1, 1, 0, 0):
            _box_pass(alpha, radius, axis, tile_pixels, poll)
    poll()
    output = surface.copy()
    # Only alpha roundoff is bounded. RGB, including negative/extended values
    # and hidden RGB, is never clipped or filtered by this operation.
    flat_alpha = alpha.reshape(-1)
    flat_output = output.reshape(-1, 4)
    for start in range(0, pixels, tile_pixels):
        poll()
        end = min(pixels, start+tile_pixels)
        np.clip(flat_alpha[start:end], 0, 1, out=flat_alpha[start:end])
        flat_output[start:end, 3] = flat_alpha[start:end]
    poll()
    return output, {'protocol':PROTOCOL, 'kind':kind, 'points':points, 'author_tick':str(tick),
        'feather':feather, 'feather_mode':'animated-inner-distance' if dynamic else 'static-alpha-box2',
        'box_radius_pixels':radius, 'box_edge':'symmetric-inclusive', 'invert':invert,
        'alpha_order':'source-alpha-times-mask-then-static-blur', 'RGB':'input-bits-preserved',
        'ellipse_distance':'normalized-radial-times-minimum-radius', 'cubic_path':'fixed-segment-sampled-polyline',
        'integer_quantization':False, 'estimated_working_bytes':estimated, 'estimated_bytes_are_peak_RSS':False,
        'natural_quality_accepted':False, 'HDR_accepted':False}
