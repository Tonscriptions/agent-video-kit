"""Continuous RGB/chroma distance key, coverage feather and local despill.

RGB remains straight. A key is coverage and multiplies the incoming alpha;
it never resurrects transparent pixels. Spatial neighbourhoods replicate
endpoints deterministically and do not inherit native scanline history.
"""
from dataclasses import dataclass
import math
import re

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba
from .float_curves import signal
from .float_numeric_automation import number, compile_tracks, sample_tracks, raw_tracks, validate_duration
from .float_spatial_budget import admit_spatial, MAX_WORKING_BYTES
from .float_yuv import COEFFICIENTS

PROTOCOL = 'explicit-signal-author-clock-continuous-float32-color-key-v1'
ALIASES = frozenset(('chroma_key', 'chromakey', 'green_screen', 'colorkey', 'color_key'))
BOUNDS = {'key_red': (0., 1.), 'key_green': (0., 1.), 'key_blue': (0., 1.),
          'similarity': (0., 1.), 'blend': (0., 1.), 'feather': (0., 32.),
          'despill': (0., 1.), 'intensity': (0., 1.)}
PARAMETER_ALIASES = {'red': 'key_red', 'green': 'key_green', 'blue': 'key_blue'}
NAMED_COLORS = {'black': '000000', 'white': 'ffffff', 'red': 'ff0000', 'green': '008000',
                'lime': '00ff00', 'blue': '0000ff', 'yellow': 'ffff00', 'cyan': '00ffff',
                'magenta': 'ff00ff'}


def error(kind, message):
    return AppError('FLOAT_KEYER_'+kind, message, exit_code=2)


@dataclass(frozen=True)
class KeyerPlan:
    author_name: str
    values: tuple
    tracks_json: str
    input_signal: ColorSignal
    metric: str
    matrix: str | None
    range: str | None
    chroma_radius: int
    arithmetic: str
    invert: bool
    spill_axis: str
    despill_edges: bool
    input_gamut: str
    output_gamut: str


def parameter_names():
    return frozenset(BOUNDS) | frozenset(PARAMETER_ALIASES)


def _color(value):
    if isinstance(value, str):
        text = NAMED_COLORS.get(value.lower(), value)
        if text.startswith(('#', '0x', '0X')):
            text = text[1:] if text[0] == '#' else text[2:]
        if not re.fullmatch('[0-9a-fA-F]{6}', text):
            raise error('ARGUMENT', '键色须为RGB六位十六进制、支持的颜色名或三个归一化数值')
        return tuple(int(text[i:i+2], 16)/255. for i in (0, 2, 4))
    if not isinstance(value, list) or len(value) != 3:
        raise error('ARGUMENT', '归一化键色须为三个数值的JSON数组')
    return tuple(number(item, 0., 1.) for item in value)


def _configuration(plan):
    if not isinstance(plan.author_name, str) or plan.author_name not in ALIASES:
        raise error('ARGUMENT', '抠像作者类型无效')
    if not isinstance(plan.input_signal, ColorSignal):
        raise error('SIGNAL', '抠像须明确键色与距离计算的RGB信号')
    if plan.metric not in ('rgb', 'chroma'):
        raise error('ARGUMENT', '抠像距离须为rgb或chroma')
    if plan.metric == 'chroma':
        if not isinstance(plan.matrix, str) or plan.matrix not in COEFFICIENTS or plan.range not in ('full', 'limited'):
            raise error('SIGNAL', 'chroma距离须明确矩阵与full/limited量程')
    elif plan.matrix is not None or plan.range is not None:
        raise error('ARGUMENT', 'RGB距离不接受未使用的YCbCr矩阵或量程')
    if type(plan.chroma_radius) is not int or not 0 <= plan.chroma_radius <= 4:
        raise error('ARGUMENT', 'chroma邻域半径须为0..4整数')
    if plan.metric == 'rgb' and plan.chroma_radius != 0:
        raise error('ARGUMENT', 'RGB距离不接受chroma邻域')
    if plan.arithmetic not in ('continuous', 'native_coefficients'):
        raise error('ARGUMENT', '抠像标量运算模式未知')
    if type(plan.invert) is not bool or type(plan.despill_edges) is not bool:
        raise error('ARGUMENT', '遮罩反转与边缘去溢色须为布尔值')
    if (plan.spill_axis not in ('auto', 'red', 'green', 'blue')
            or plan.input_gamut not in ('preserve', 'clip') or plan.output_gamut not in ('preserve', 'clip')):
        raise error('ARGUMENT', '去溢色轴或色域策略未知')


def compile_keyer(effect):
    if not isinstance(effect, dict) or set(effect)-{'id', 'type', 'enabled', 'parameters', 'keyframes'}:
        raise error('ARGUMENT', '抠像含未知字段；参数须放在parameters')
    name = str(effect.get('type', '')).strip().lower().replace('-', '_')
    if name not in ALIASES or type(effect.get('enabled', True)) is not bool:
        raise error('ARGUMENT', '抠像类型或enabled无效')
    p = effect.get('parameters', {})
    extra = {'color', 'input_signal', 'metric', 'matrix', 'range', 'chroma_radius', 'arithmetic',
             'invert', 'spill_axis', 'despill_edges', 'input_gamut', 'output_gamut', 'keyframes'}
    if not isinstance(p, dict) or set(p)-(set(BOUNDS) | set(PARAMETER_ALIASES) | extra):
        raise error('ARGUMENT', '抠像参数未知')
    rgb = _color(p.get('color', '0x00ff00'))
    values = dict(zip(('key_red', 'key_green', 'key_blue'), rgb))
    values.update(similarity=.1, blend=0., feather=0., despill=0., intensity=1.)
    seen = set()
    for key, value in p.items():
        canonical = PARAMETER_ALIASES.get(key, key)
        if canonical not in BOUNDS:
            continue
        if canonical in seen:
            raise error('ARGUMENT', '抠像参数重复声明别名')
        seen.add(canonical)
        values[canonical] = number(value, *BOUNDS[canonical])
    tracks = compile_tracks(raw_tracks(effect, p), BOUNDS, PARAMETER_ALIASES, name)
    metric = p.get('metric', 'rgb')
    plan = KeyerPlan(name, tuple(sorted(values.items())), tracks, signal(p.get('input_signal')),
        metric, p.get('matrix'), p.get('range'), p.get('chroma_radius', 1 if metric == 'chroma' else 0),
        p.get('arithmetic', 'continuous'), p.get('invert', False), p.get('spill_axis', 'auto'),
        p.get('despill_edges', False), p.get('input_gamut', 'preserve'), p.get('output_gamut', 'preserve'))
    _configuration(plan)
    return plan


def state_at(plan, tick):
    if not isinstance(plan, KeyerPlan) or not isinstance(plan.values, tuple):
        raise error('ARGUMENT', '须使用完整不可变抠像计划')
    _configuration(plan)
    values = {}
    for row in plan.values:
        if (not isinstance(row, tuple) or len(row) != 2 or not isinstance(row[0], str)
                or row[0] not in BOUNDS or row[0] in values):
            raise error('ARGUMENT', '抠像计划通道未知或重复')
        values[row[0]] = number(row[1], *BOUNDS[row[0]])
    if values.keys() != BOUNDS.keys():
        raise error('ARGUMENT', '抠像计划缺少通道')
    values.update(sample_tracks(plan.tracks_json, BOUNDS, PARAMETER_ALIASES, plan.author_name, tick))
    return values


def validate_keyer(effect, *, duration_tick=None):
    if isinstance(effect, dict) and effect.get('enabled', True) is False:
        return []
    try:
        plan = compile_keyer(effect)
        validate_duration(plan.tracks_json, duration_tick)
    except AppError as exc:
        return [{'code':exc.code, 'message':str(exc), 'suffix':'.parameters'}]
    return []


def _mean_axis(value, radius, axis, poll):
    """An alias-safe line prefix sum; fractional radii blend adjacent boxes."""
    if radius == 0:
        return
    n = math.floor(radius)
    fraction = radius-n
    halo = n+bool(fraction)
    lines = np.moveaxis(value, axis, -1)
    length = lines.shape[-1]
    for index in range(lines.shape[0]):
        poll()
        padded = np.pad(lines[index], (halo, halo), mode='edge')
        prefix = np.empty(len(padded)+1, np.float64)
        prefix[0] = 0.
        np.cumsum(padded, out=prefix[1:])
        offset, count = halo-n, 2*n+1
        result = (prefix[offset+count:offset+count+length]-prefix[offset:offset+length])/count
        if fraction:
            wide = (prefix[2*halo+1:2*halo+1+length]-prefix[:length])/(2*halo+1)
            result = (1-fraction)*result+fraction*wide
        lines[index] = result


def _distance(rgb, key, plan):
    difference = rgb.astype(np.float64)-key
    if plan.metric == 'rgb':
        return np.sqrt(np.sum(difference*difference, axis=1)/3.)
    kr, kb = COEFFICIENTS[plan.matrix]
    y = difference[:, 0]*kr+difference[:, 1]*(1-kr-kb)+difference[:, 2]*kb
    u = (difference[:, 2]-y)/(2*(1-kb))
    v = (difference[:, 0]-y)/(2*(1-kr))
    scale = 1. if plan.range == 'full' else 224./255.
    return np.sqrt((u*u+v*v)/2.)*scale


def _coverage(distance, values, plan):
    similarity, blend = values['similarity'], values['blend']
    if plan.arithmetic == 'native_coefficients':
        similarity, blend = float(np.float32(similarity)), float(np.float32(blend))
        if plan.metric == 'rgb':
            inverse = float(np.float32(1.)/np.float32(blend)) if blend else math.inf
            return np.clip((distance-similarity)*inverse, 0, 1) if inverse < 10000. else (distance > similarity).astype(np.float64)
        blend_active = blend > .0001
    else:
        blend_active = blend > 0
    return np.clip((distance-similarity)/blend, 0, 1) if blend_active else (distance > similarity).astype(np.float64)


def apply_keyer(surface, plan, author_tick, *, working_signal, tile_pixels=65536,
                retained_table_bytes=0, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    if cancel is not None and not callable(cancel):
        raise error('ARGUMENT', '取消回调须可调用')
    def poll():
        if cancel and cancel():
            raise AppError('RENDER_CANCELLED', '浮点色度抠像已取消', exit_code=6)
    poll()
    values = state_at(plan, author_tick)
    if not isinstance(working_signal, ColorSignal) or working_signal.transfer != 'linear':
        raise error('SIGNAL', '抠像须使用明确的线性工作信号')
    if (not isinstance(surface, np.ndarray) or surface.dtype != np.float32 or surface.ndim != 3
            or surface.shape[-1] != 4 or not surface.flags.c_contiguous):
        raise error('SURFACE', '抠像输入须为连续H×W×4 Float32')
    h, w = surface.shape[:2]
    pixels = h*w
    if min(h, w) < 1 or max(h, w) > 16384 or pixels > 16777216:
        raise error('BUDGET', '抠像表面超过尺寸预算')
    tile, estimate, admission = admit_spatial(surface_bytes=int(surface.nbytes), pixels=pixels,
        tile_pixels=tile_pixels, tracks_bytes=len(plan.tracks_json.encode('utf8')),
        retained_table_bytes=retained_table_bytes, max_working_bytes=max_working_bytes,
        error=error, line_scratch_bytes=(max(h, w)+67)*8*8)
    source = surface.reshape(-1, 4)
    for start in range(0, pixels, tile):
        poll()
        part = source[start:start+tile]
        if not np.isfinite(part).all() or np.any(part[:, 3] < 0) or np.any(part[:, 3] > 1):
            raise error('VALUES', 'RGB须有限且alpha须在0..1')
    key = np.array([values['key_'+channel] for channel in ('red', 'green', 'blue')], np.float64)
    axis = {'red':0, 'green':1, 'blue':2}.get(plan.spill_axis)
    if plan.spill_axis == 'auto' and np.ptp(key) > 1e-12:
        axis = int(np.argmax(key))
    strength = values['intensity']
    clipped_input = clipped_output = changed_rgb = 0
    minimum, maximum, partial, zero = 1., 0., 0, 0
    if strength == 0:
        result = surface.copy()
        minimum = maximum = 1.
    else:
        encoded, _ = convert_rgba(surface, working_signal, plan.input_signal, tile_pixels=tile,
                                  max_working_bytes=max_working_bytes, cancel=poll)
        flat = encoded.reshape(-1, 4)
        matte = np.empty((h, w), np.float64)
        mask = matte.reshape(-1)
        for start in range(0, pixels, tile):
            poll()
            rgb = flat[start:start+tile, :3]
            if plan.input_gamut == 'clip':
                clipped_input += int(np.count_nonzero((rgb < 0) | (rgb > 1)))
                rgb = np.clip(rgb, 0., 1.)
            mask[start:start+len(rgb)] = _distance(rgb, key, plan)
        if plan.metric == 'chroma':
            for dimension in (1, 0):
                _mean_axis(matte, plan.chroma_radius, dimension, poll)
        for start in range(0, pixels, tile):
            poll()
            part = mask[start:start+tile]
            part[:] = _coverage(part, values, plan)
            if plan.invert:
                part[:] = 1-part
        for dimension in (1, 0):
            _mean_axis(matte, values['feather'], dimension, poll)
        np.clip(matte, 0., 1., out=matte)
        rgb_operation = values['despill'] != 0 and axis is not None or plan.output_gamut == 'clip'
        if rgb_operation:
            other = [i for i in range(3) if i != axis] if axis is not None else []
            for start in range(0, pixels, tile):
                poll()
                rgb = flat[start:start+tile, :3]
                if values['despill'] and axis is not None:
                    reduction = np.maximum(rgb[:, axis].astype(np.float64)-np.max(rgb[:, other], axis=1), 0.)*values['despill']
                    if plan.despill_edges:
                        reduction *= 1-mask[start:start+len(rgb)]
                    changed_rgb += int(np.count_nonzero(reduction))
                    rgb[:, axis] = rgb[:, axis].astype(np.float64)-reduction
                if plan.output_gamut == 'clip':
                    clipped_output += int(np.count_nonzero((rgb < 0) | (rgb > 1)))
                    np.clip(rgb, 0., 1., out=rgb)
        del rgb
        if changed_rgb or clipped_output:
            graded, _ = convert_rgba(encoded, plan.input_signal, working_signal, tile_pixels=tile,
                                     max_working_bytes=max_working_bytes, cancel=poll)
        else:
            graded = None
        del encoded, flat
        result = surface.copy()
        target = result.reshape(-1, 4)
        for start in range(0, pixels, tile):
            poll()
            part = source[start:start+tile]
            coverage = mask[start:start+len(part)]
            out = target[start:start+len(part)]
            factor = np.clip(1-strength+strength*coverage, 0., 1.)
            out[:, 3] = part[:, 3].astype(np.float64)*factor
            unchanged = factor == 1.
            out[unchanged, 3] = part[unchanged, 3]
            if graded is not None:
                colors = graded.reshape(-1, 4)[start:start+len(part), :3]
                with np.errstate(over='ignore', invalid='ignore'):
                    out[:, :3] = colors if strength == 1 else part[:, :3].astype(np.float64)*(1-strength)+colors.astype(np.float64)*strength
            if not np.isfinite(out).all() or np.any(out[:, 3] < 0) or np.any(out[:, 3] > part[:, 3]):
                raise error('VALUES', '抠像输出须有限且不可增加输入覆盖')
            minimum = min(minimum, float(coverage.min()))
            maximum = max(maximum, float(coverage.max()))
            partial += int(np.count_nonzero((coverage > 0) & (coverage < 1)))
            zero += int(np.count_nonzero(coverage == 0))
    poll()
    return result, {'protocol':PROTOCOL, 'effect_type':'chroma_key', 'author_tick':str(author_tick),
        'sampled_values':values, 'working_signal':vars(working_signal), 'input_signal':vars(plan.input_signal),
        'metric':plan.metric, 'matrix':plan.matrix, 'range':plan.range, 'chroma_radius':plan.chroma_radius,
        'chroma_neighbourhood':'mean-of-distances-before-coverage', 'boundary':'replicated-endpoints',
        'native_scanline_edge_history_reproduced':False, 'arithmetic':plan.arithmetic,
        'continuous_softness_below_native_threshold':plan.arithmetic == 'continuous',
        'invert':plan.invert, 'feather_kernel':'convex-adjacent-integer-boxes',
        'alpha':'explicit-input-coverage-times-key-matte', 'alpha_mix':'input_alpha*(1-intensity+intensity*matte)',
        'incoming_coverage_preserved':True, 'coverage_minimum':minimum, 'coverage_maximum':maximum,
        'partial_matte_pixels':partial, 'zero_matte_pixels':zero,
        'RGB_bits_preserved':not changed_rgb and not clipped_output,
        'despill_axis':axis, 'despill_edges':plan.despill_edges, 'despill_changed_pixels':changed_rgb,
        'input_gamut':plan.input_gamut, 'input_clipped_for_distance_components':clipped_input,
        'output_gamut':plan.output_gamut, 'output_clipped_components':clipped_output,
        'RGB_mix_domain':'linear-working-straight-RGB', 'integer_intermediate':False,
        'raster_dtype':'float32', 'distance_and_matte_dtype':'float64',
        'estimated_working_bytes':estimate, 'workspace_admission':admission,
        'estimated_bytes_are_peak_RSS':False, 'native_bit_equivalence':False,
        'semantic_matting':False, 'natural_quality_accepted':False, 'HDR_accepted':False}
