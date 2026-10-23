"""Continuous finite-support means with subtraction-free window sums.

Average blur extends edge samples. Box blur uses half-sample symmetric edges
and repeated axis passes. Integer-radius mathematics is compared to FFmpeg's
integer filters; their quantized pixels/fixed reciprocals are not reproduced.
Fractional radius adds partial outer taps, with total weight 2*radius+1.
No FFmpeg C implementation is incorporated in this module.
"""
from dataclasses import dataclass
import json
import math

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba
from .float_curves import signal
from .float_numeric_automation import number, compile_tracks, sample_tracks, raw_tracks, validate_duration
from .float_spatial_budget import admit_spatial, MAX_WORKING_BYTES

PROTOCOL = 'explicit-signal-author-clock-continuous-float32-spatial-means-v1'
AVERAGE_ALIASES = frozenset(('avgblur', 'average_blur'))
BOX_ALIASES = frozenset(('boxblur', 'box_blur'))
ALIASES = AVERAGE_ALIASES | BOX_ALIASES
PARAMETER_ALIASES = {'size_x': 'radius_x', 'sizex': 'radius_x', 'sizeX': 'radius_x',
                     'size_y': 'radius_y', 'sizey': 'radius_y', 'sizeY': 'radius_y'}


def error(kind, message):
    return AppError('FLOAT_SPATIAL_' + kind, message, exit_code=2)


def bounds(kind):
    maximum = 1024. if kind == 'average_blur' else 128.
    return {'radius': (0., maximum), 'radius_x': (0., maximum),
            'radius_y': (0., maximum), 'intensity': (0., 1.)}


@dataclass(frozen=True)
class SpatialPlan:
    effect_type: str
    values: tuple
    tracks_json: str
    axis_overrides: tuple
    legacy_zero_y_inherits: bool
    input_signal: ColorSignal
    output_signal: ColorSignal
    power: int
    planes: int
    alpha_mode: str
    output_gamut: str


def _configuration(plan):
    if plan.effect_type not in ('average_blur', 'box_blur'):
        raise error('ARGUMENT', '空间均值计划类型无效')
    if not isinstance(plan.input_signal, ColorSignal) or not isinstance(plan.output_signal, ColorSignal):
        raise error('SIGNAL', '空间均值须明确输入输出RGB信号')
    if (type(plan.power) is not int or not 0 <= plan.power <= 4
            or plan.effect_type == 'average_blur' and plan.power != 1
            or type(plan.planes) is not int or not 0 <= plan.planes <= 15):
        raise error('ARGUMENT', 'power须为0..4整数，planes须为0..15整数；均值模糊固定一次')
    if (plan.alpha_mode not in ('straight', 'premultiplied') or plan.output_gamut not in ('preserve', 'clip')
            or plan.alpha_mode == 'premultiplied' and plan.planes != 15):
        raise error('ARGUMENT', '透明度或色域策略无效；预乘须处理全部四平面')
    if (not isinstance(plan.axis_overrides, tuple)
            or any(n not in ('radius_x', 'radius_y') for n in plan.axis_overrides)
            or tuple(sorted(set(plan.axis_overrides))) != plan.axis_overrides
            or type(plan.legacy_zero_y_inherits) is not bool
            or plan.legacy_zero_y_inherits and plan.effect_type != 'average_blur'):
        raise error('ARGUMENT', '空间均值轴覆盖或继承规则无效')


def parameter_names():
    return frozenset(bounds('average_blur')) | frozenset(PARAMETER_ALIASES)


def compile_spatial(effect):
    if not isinstance(effect, dict) or set(effect) - {'id', 'type', 'enabled', 'parameters', 'keyframes'}:
        raise error('ARGUMENT', '空间均值含未知字段；参数须置于parameters')
    name = str(effect.get('type', '')).strip().lower().replace('-', '_')
    if name not in ALIASES or type(effect.get('enabled', True)) is not bool:
        raise error('ARGUMENT', '空间均值类型或enabled无效')
    kind = 'average_blur' if name in AVERAGE_ALIASES else 'box_blur'
    limits = bounds(kind)
    aliases = PARAMETER_ALIASES if kind == 'average_blur' else {}
    p = effect.get('parameters', {})
    extras = {'input_signal', 'output_signal', 'planes', 'alpha_mode', 'output_gamut', 'keyframes'}
    if kind == 'box_blur': extras.add('power')
    if not isinstance(p, dict) or set(p) - (set(limits) | set(aliases) | extras):
        raise error('ARGUMENT', '空间均值参数未知')
    default = 2. if kind == 'average_blur' else 4.
    values = {'radius': default, 'radius_x': default, 'radius_y': default, 'intensity': 1.}
    seen = set()
    for key, value in p.items():
        canonical = aliases.get(key, key)
        if canonical not in limits: continue
        if canonical in seen: raise error('ARGUMENT', '空间均值静态通道重复声明别名')
        seen.add(canonical); values[canonical] = number(value, *limits[canonical])
    raw = raw_tracks(effect, p)
    tracks = compile_tracks(raw, limits, aliases, name)
    overrides = (seen | {t['property'] for t in json.loads(tracks)}) & {'radius_x', 'radius_y'}
    legacy_y = any(k in p for k in ('size_y', 'sizeY', 'sizey'))
    if isinstance(raw, list):
        for t in raw:
            prop = t['property'].strip().lower().replace('-', '_')
            for prefix in ('effect.', 'parameters.', name + '.'):
                if prop.startswith(prefix): prop = prop[len(prefix):]; break
            legacy_y |= prop in ('size_y', 'sizey')
    plan = SpatialPlan(kind, tuple(sorted(values.items())), tracks, tuple(sorted(overrides)), legacy_y,
        signal(p.get('input_signal')), signal(p.get('output_signal')), p.get('power', 1), p.get('planes', 15),
        p.get('alpha_mode', 'straight'), p.get('output_gamut', 'preserve'))
    _configuration(plan)
    return plan


def state_at(plan, tick):
    if not isinstance(plan, SpatialPlan) or not isinstance(plan.values, tuple):
        raise error('ARGUMENT', '须使用不可变空间均值计划')
    _configuration(plan); limits = bounds(plan.effect_type); values = {}
    for row in plan.values:
        if not isinstance(row, tuple) or len(row) != 2 or row[0] not in limits or row[0] in values:
            raise error('ARGUMENT', '空间均值计划参数无效或重复')
        values[row[0]] = number(row[1], *limits[row[0]])
    if values.keys() != limits.keys(): raise error('ARGUMENT', '空间均值计划缺少通道')
    aliases = PARAMETER_ALIASES if plan.effect_type == 'average_blur' else {}
    values.update(sample_tracks(plan.tracks_json, limits, aliases, plan.effect_type, tick))
    for axis in ('radius_x', 'radius_y'):
        if axis not in plan.axis_overrides: values[axis] = values['radius']
    if plan.legacy_zero_y_inherits and values['radius_y'] == 0:
        values['radius_y'] = values['radius_x']
    return values


def validate_spatial(effect, *, duration_tick=None):
    if effect.get('enabled', True) is False: return []
    try:
        plan = compile_spatial(effect); validate_duration(plan.tracks_json, duration_tick)
    except AppError as exc:
        return [{'code': exc.code, 'message': str(exc), 'suffix': '.parameters'}]
    return []


def _window_sums(padded, start, length, width, poll):
    """Compose disjoint power-of-two ranges without subtracting large prefixes.

    Positive tiny coverage far after opaque pixels must not disappear through
    prefix cancellation. Intermediate arrays are bounded to one padded line.
    """
    sums = np.zeros((length, padded.shape[1]), np.float64)
    block = padded
    offset = 0
    span = 1
    while span <= width:
        poll()
        if width & span:
            sums += block[start+offset:start+offset+length]
            offset += span
        if span*2 > width: break
        block = block[:-span] + block[span:]
        span *= 2
    return sums


def _mean_axis(values, axis, radius, power, boundary, poll):
    """One padded line at a time; no image-sized sum table or wide kernel."""
    if radius == 0 or power == 0: return
    whole = math.floor(radius); fraction = radius - whole
    halo = whole + bool(fraction)
    view = np.moveaxis(values, axis, 1)
    length = view.shape[1]
    for _ in range(power):
        poll()
        for index in range(view.shape[0]):
            if index % 16 == 0: poll()
            padded = np.pad(view[index], ((halo, halo), (0, 0)), mode=boundary)
            start = halo - whole
            sums = _window_sums(padded, start, length, 2*whole+1, poll)
            if fraction:
                sums += fraction * (padded[:length] + padded[-length:])
            sums /= 2 * radius + 1
            view[index] = sums


def apply_spatial(surface, plan, author_tick, *, working_signal, tile_pixels=65536,
                  retained_table_bytes=0, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    if cancel is not None and not callable(cancel): raise error('ARGUMENT', '取消回调须可调用')
    def poll():
        if cancel and cancel(): raise AppError('RENDER_CANCELLED', '浮点空间均值已取消', exit_code=6)
    poll(); values = state_at(plan, author_tick); strength = values['intensity']
    if not isinstance(working_signal, ColorSignal) or working_signal.transfer != 'linear':
        raise error('SIGNAL', '空间均值须使用明确线性工作信号')
    if (not isinstance(surface, np.ndarray) or surface.dtype != np.float32 or surface.ndim != 3
            or surface.shape[-1] != 4 or not surface.flags.c_contiguous):
        raise error('SURFACE', '空间均值输入须为连续H×W×4 Float32')
    h, w = surface.shape[:2]; pixels = h*w
    if min(h, w) < 1 or max(h, w) > 16384 or pixels > 16777216:
        raise error('BUDGET', '空间均值表面超过尺寸预算')
    rx, ry = values['radius_x'], values['radius_y']
    if plan.effect_type == 'average_blur': rx, ry = min(rx, w//2), min(ry, h//2)
    channels = tuple(i for i, bit in enumerate((4, 1, 2, 8)) if plan.planes & bit)
    # Four simultaneous padded-line/sum/result buffers, independent of tile size.
    line_bytes = (max(h, w) + 2*math.ceil(max(rx, ry)) + 1) * max(1, len(channels)) * 8 * 4
    tile, estimate, admission = admit_spatial(surface_bytes=int(surface.nbytes), pixels=pixels,
        tile_pixels=tile_pixels, tracks_bytes=len(plan.tracks_json.encode('utf8')),
        retained_table_bytes=retained_table_bytes, max_working_bytes=max_working_bytes,
        error=error, line_scratch_bytes=line_bytes)
    source = surface.reshape(-1, 4)
    for start in range(0, pixels, tile):
        poll(); part = source[start:start+tile]
        if not np.isfinite(part).all() or np.any(part[:, 3] < 0) or np.any(part[:, 3] > 1):
            raise error('VALUES', 'RGB须有限且alpha须在0..1')
    active = bool(channels) and bool(plan.power) and (rx != 0 or ry != 0) and strength != 0
    no_RGB_conversion = not any(i < 3 for i in channels) and plan.input_signal == plan.output_signal and plan.output_gamut == 'preserve'
    boundary = 'edge' if plan.effect_type == 'average_blur' else 'symmetric'
    clips = zero_coverage = 0
    if strength == 0 or not active and plan.input_signal == plan.output_signal and plan.output_gamut == 'preserve':
        result = surface.copy()
    else:
        if no_RGB_conversion: encoded = surface.copy()
        else: encoded, _ = convert_rgba(surface, working_signal, plan.input_signal, tile_pixels=tile, max_working_bytes=max_working_bytes, cancel=poll)
        if active:
            work = np.take(encoded, channels, axis=2).astype(np.float64)
            if plan.alpha_mode == 'premultiplied': work[..., :3] *= work[..., 3:4]
            _mean_axis(work, 1, rx, plan.power, boundary, poll)
            _mean_axis(work, 0, ry, plan.power, boundary, poll)
            if plan.alpha_mode == 'premultiplied':
                density = work[..., 3:4]; positive = density > 0
                np.divide(work[..., :3], density, out=work[..., :3], where=positive)
                work[..., :3][~positive[..., 0]] = 0
                zero_coverage = int(np.count_nonzero(~positive))
            flat = work.reshape(-1, len(channels)); target = encoded.reshape(-1, 4)
            for start in range(0, pixels, tile):
                poll(); part = flat[start:start+tile]
                with np.errstate(over='ignore', invalid='ignore'): target[start:start+len(part), channels] = part
            del work
        flat = encoded.reshape(-1, 4)
        for start in range(0, pixels, tile):
            poll(); part = flat[start:start+tile]
            if not np.isfinite(part).all(): raise error('VALUES', '空间均值中间值超出Float32范围')
            if active and 3 in channels: np.clip(part[:, 3], 0, 1, out=part[:, 3])
            if plan.output_gamut == 'clip':
                clips += int(np.count_nonzero((part[:, :3] < 0) | (part[:, :3] > 1)))
                np.clip(part[:, :3], 0, 1, out=part[:, :3])
        if no_RGB_conversion: graded = encoded
        else: graded, _ = convert_rgba(encoded, plan.output_signal, working_signal, tile_pixels=tile, max_working_bytes=max_working_bytes, cancel=poll)
        result = np.empty_like(surface); target = result.reshape(-1, 4); flat = graded.reshape(-1, 4)
        for start in range(0, pixels, tile):
            poll(); part = source[start:start+tile]; value = flat[start:start+tile]; out = target[start:start+len(part)]
            with np.errstate(over='ignore', invalid='ignore'):
                out[:] = value if strength == 1 else part.astype(np.float64)*(1-strength) + value.astype(np.float64)*strength
            if not active or 3 not in channels: out[:, 3] = part[:, 3]
            if no_RGB_conversion: out[:, :3] = part[:, :3]
            if not np.isfinite(out).all() or np.any(out[:, 3] < 0) or np.any(out[:, 3] > 1):
                raise error('VALUES', '空间均值输出超出有限值或alpha范围')
    poll()
    return result, {'protocol': PROTOCOL, 'effect_type': plan.effect_type, 'author_tick': str(author_tick),
        'sampled_values': values, 'effective_radii': {'radius_x': rx, 'radius_y': ry},
        'input_signal': vars(plan.input_signal), 'output_signal': vars(plan.output_signal), 'working_signal': vars(working_signal),
        'power': plan.power, 'planes_GBRA_bits': plan.planes, 'selected_RGBA_indices': list(channels), 'alpha_mode': plan.alpha_mode,
        'alpha': 'explicit-spatial-coverage-mapping' if active and 3 in channels else 'input-bits-preserved',
        'zero_blurred_coverage_pixels': zero_coverage, 'alpha_only_RGB_conversion_bypassed': no_RGB_conversion,
        'output_gamut': plan.output_gamut, 'output_clipped_components': clips, 'integer_intermediate': False,
        'raster_dtype': 'float32', 'spatial_scratch_dtype': 'float64', 'boundary': boundary,
        'window_sum': 'subtraction-free-disjoint-power-of-two-ranges',
        'fractional_radius': 'unit-inner-taps-and-fractional-outer-taps-divided-by-2r+1',
        'axis_order': 'all-horizontal-passes-then-all-vertical-passes', 'legacy_zero_y_inherits': plan.legacy_zero_y_inherits,
        'RGB_mix_domain': 'linear-working-straight-RGB', 'alpha_mix': 'linear-coverage',
        'estimated_working_bytes': estimate, 'estimated_bytes_are_peak_RSS': False,
        'actual_tile_pixels_limit': tile, 'workspace_admission': admission,
        'native_bit_equivalence': False, 'natural_quality_accepted': False, 'HDR_accepted': False}
