"""Continuous Y'CbCr unsharp with independent binomial convolution.

No integer image or FFmpeg implementation is used. Integer radii select a
normalized Pascal kernel; fractional radii blend the two adjacent kernels.
The optional native_coefficients mode copies scalar coefficient semantics,
including the native uint16 path's extra eight-bit shift, not pixel rounding.
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
from .float_yuv import COEFFICIENTS

PROTOCOL = 'explicit-YCbCr-author-clock-continuous-float32-unsharp-v1'
ALIASES = frozenset(('sharpen', 'unsharp'))
AXES = tuple(f'{plane}_radius_{axis}' for plane in ('luma', 'chroma', 'alpha') for axis in ('x', 'y'))
BOUNDS = {**{f'{plane}_amount': (-2., 10.) for plane in ('luma', 'chroma', 'alpha')},
          'radius': (0., 11.), **{name: (0., 11.) for name in AXES}, 'intensity': (0., 1.)}
PARAMETER_ALIASES = {'amount': 'luma_amount', 'la': 'luma_amount', 'ca': 'chroma_amount', 'aa': 'alpha_amount',
                     'radius_x': 'luma_radius_x', 'radius_y': 'luma_radius_y'}
SIZE_ALIASES = {f'{plane}_msize_{axis}': f'{plane}_radius_{axis}'
                for plane in ('luma', 'chroma', 'alpha') for axis in ('x', 'y')}
SIZE_ALIASES.update({short + axis: plane + '_radius_' + axis
                     for short, plane in (('l', 'luma'), ('c', 'chroma'), ('a', 'alpha')) for axis in ('x', 'y')})


def error(kind, message):
    return AppError('FLOAT_SHARPEN_' + kind, message, exit_code=2)


@dataclass(frozen=True)
class SharpenPlan:
    author_name: str
    values: tuple
    tracks_json: str
    axis_overrides: tuple
    input_signal: ColorSignal
    output_signal: ColorSignal
    matrix: str
    range: str
    reference_bits: int
    arithmetic: str
    code_gamut: str
    output_gamut: str


def parameter_names():
    return frozenset(BOUNDS) | frozenset(PARAMETER_ALIASES)


def _configuration(plan):
    if not isinstance(plan.author_name, str) or plan.author_name not in ALIASES:
        raise error('ARGUMENT', '锐化计划的作者类型无效')
    if not isinstance(plan.input_signal, ColorSignal) or not isinstance(plan.output_signal, ColorSignal):
        raise error('SIGNAL', '锐化须明确输入和输出RGB信号')
    if (not isinstance(plan.matrix, str) or plan.matrix not in COEFFICIENTS
            or plan.range not in ('full', 'limited')):
        raise error('SIGNAL', '锐化须明确YCbCr矩阵与full/limited量程')
    if type(plan.reference_bits) is not int or plan.reference_bits not in (8, 9, 10, 12, 14, 16):
        raise error('ARGUMENT', '参考码值轴须为8/9/10/12/14/16位')
    if (plan.arithmetic not in ('continuous', 'native_coefficients')
            or plan.code_gamut not in ('preserve', 'clip') or plan.output_gamut not in ('preserve', 'clip')):
        raise error('ARGUMENT', '锐化运算或色域策略无效')
    if (not isinstance(plan.axis_overrides, tuple)
            or any(not isinstance(name, str) or name not in AXES for name in plan.axis_overrides)
            or tuple(sorted(set(plan.axis_overrides))) != plan.axis_overrides):
        raise error('ARGUMENT', '锐化轴覆盖规则无效')


def compile_sharpen(effect):
    if not isinstance(effect, dict) or set(effect) - {'id', 'type', 'enabled', 'parameters', 'keyframes'}:
        raise error('ARGUMENT', '锐化含未知字段；参数须置于parameters')
    name = str(effect.get('type', '')).strip().lower().replace('-', '_')
    if name not in ALIASES or type(effect.get('enabled', True)) is not bool:
        raise error('ARGUMENT', '锐化类型或enabled无效')
    p = effect.get('parameters', {})
    extra = {'input_signal', 'output_signal', 'matrix', 'range', 'reference_bits',
             'arithmetic', 'code_gamut', 'output_gamut', 'keyframes'}
    if not isinstance(p, dict) or set(p) - (set(BOUNDS) | set(PARAMETER_ALIASES) | set(SIZE_ALIASES) | extra):
        raise error('ARGUMENT', '锐化参数未知')
    values = {name: (2. if name == 'radius' or name in AXES else 0.) for name in BOUNDS}
    values['luma_amount'] = values['intensity'] = 1.
    seen = set()
    for key, value in p.items():
        canonical = PARAMETER_ALIASES.get(key, SIZE_ALIASES.get(key, key))
        if canonical not in BOUNDS:
            continue
        if canonical in seen:
            raise error('ARGUMENT', '锐化静态参数重复声明别名')
        seen.add(canonical)
        if key in SIZE_ALIASES:
            if type(value) is not int or not 3 <= value <= 23 or value % 2 != 1:
                raise error('ARGUMENT', '原生矩阵尺寸须为3..23的奇数整数；动态大小请使用radius通道')
            value = (value - 1) / 2
        values[canonical] = number(value, *BOUNDS[canonical])
    tracks = compile_tracks(raw_tracks(effect, p), BOUNDS, PARAMETER_ALIASES, name)
    overrides = (seen | {t['property'] for t in json.loads(tracks)}) & set(AXES)
    plan = SharpenPlan(name, tuple(sorted(values.items())), tracks, tuple(sorted(overrides)),
        signal(p.get('input_signal')), signal(p.get('output_signal')), p.get('matrix'), p.get('range'),
        p.get('reference_bits', 8), p.get('arithmetic', 'continuous'), p.get('code_gamut', 'preserve'),
        p.get('output_gamut', 'preserve'))
    _configuration(plan)
    return plan


def state_at(plan, tick):
    if not isinstance(plan, SharpenPlan) or not isinstance(plan.values, tuple):
        raise error('ARGUMENT', '须使用完整不可变锐化计划')
    _configuration(plan)
    values = {}
    for row in plan.values:
        if (not isinstance(row, tuple) or len(row) != 2 or not isinstance(row[0], str)
                or row[0] not in BOUNDS or row[0] in values):
            raise error('ARGUMENT', '锐化计划通道无效或重复')
        values[row[0]] = number(row[1], *BOUNDS[row[0]])
    if values.keys() != BOUNDS.keys():
        raise error('ARGUMENT', '锐化计划缺少通道')
    values.update(sample_tracks(plan.tracks_json, BOUNDS, PARAMETER_ALIASES, plan.author_name, tick))
    for name in AXES:
        if name not in plan.axis_overrides:
            values[name] = values['radius']
    return values


def validate_sharpen(effect, *, duration_tick=None):
    if isinstance(effect, dict) and effect.get('enabled', True) is False:
        return []
    try:
        plan = compile_sharpen(effect)
        validate_duration(plan.tracks_json, duration_tick)
    except AppError as exc:
        return [{'code': exc.code, 'message': str(exc), 'suffix': '.parameters'}]
    return []


def _kernel(radius):
    whole = math.floor(radius)
    fraction = radius - whole
    halo = whole + bool(fraction)
    weights = np.zeros(2*halo+1, np.float64)
    for order, mix in ((whole, 1-fraction), (whole+1, fraction)):
        if mix == 0:
            continue
        row = np.array([math.comb(2*order, k) for k in range(2*order+1)], np.float64)
        row *= mix / (2.**(2*order))
        start = halo - order
        weights[start:start+len(row)] += row
    return weights


def _axis(source, target, axis, weights, poll):
    """Replicated finite kernels; alias-safe by copying only one input line."""
    halo = len(weights) // 2
    incoming, outgoing = np.moveaxis(source, axis, -1), np.moveaxis(target, axis, -1)
    for index in range(incoming.shape[0]):
        if index % 16 == 0:
            poll()
        padded = np.pad(incoming[index], (halo, halo), mode='edge')
        out = outgoing[index]
        out.fill(0.)
        for offset, weight in enumerate(weights):
            poll()
            if weight:
                out += padded[offset:offset+len(out)] * weight


def _amount(value, plan):
    if plan.arithmetic == 'continuous':
        return value
    # Native options are stored as float before truncating the scalar 16.16 coefficient.
    return math.trunc(float(np.float32(value))*65536.) / (65536. if plan.reference_bits == 8 else 16777216.)


def _axes(plan):
    maximum = (1 << plan.reference_bits) - 1
    scale = 1 << (plan.reference_bits - 8)
    return (maximum, 16*scale, 219*scale, 128*scale, 224*scale) if plan.range == 'limited' else (
        maximum, 0, maximum, 128*scale, maximum)


def _to_codes(rgb, plan):
    kr, kb = COEFFICIENTS[plan.matrix]
    _, offset, yrange, center, crange = _axes(plan)
    y = kr*rgb[:, 0] + (1-kr-kb)*rgb[:, 1] + kb*rgb[:, 2]
    return np.column_stack((y*yrange+offset, (rgb[:, 2]-y)*crange/(2*(1-kb))+center,
                            (rgb[:, 0]-y)*crange/(2*(1-kr))+center))


def _from_codes(codes, plan):
    kr, kb = COEFFICIENTS[plan.matrix]
    kg = 1-kr-kb
    _, offset, yrange, center, crange = _axes(plan)
    y = (codes[:, 0]-offset)/yrange
    u, v = (codes[:, 1]-center)/crange, (codes[:, 2]-center)/crange
    return np.column_stack((y+2*(1-kr)*v, y-2*kb*(1-kb)*u/kg-2*kr*(1-kr)*v/kg, y+2*(1-kb)*u))


def _sharpen_codes(encoded, plan, values, active, tile, poll):
    """Own all full-size Float64 scratch here; return no view retaining it."""
    h, w = encoded.shape[:2]
    work = encoded.astype(np.float64)
    code_clips = alpha_clips = 0
    rgb_active = any(active[:3])
    flat = work.reshape(-1, 4)
    if rgb_active:
        for start in range(0, len(flat), tile):
            poll()
            part = flat[start:start+tile]
            part[:, :3] = _to_codes(part[:, :3], plan)
    blurred = np.empty((h, w), np.float64)
    maximum = _axes(plan)[0]
    for channel, plane in enumerate(('luma', 'chroma', 'chroma', 'alpha')):
        if not active[channel]:
            continue
        rx, ry = values[plane+'_radius_x'], values[plane+'_radius_y']
        _axis(work[..., channel], blurred, 1, _kernel(rx), poll)
        _axis(blurred, blurred, 0, _kernel(ry), poll)
        amount = _amount(values[plane+'_amount'], plan)
        for y in range(h):
            if y % 16 == 0:
                poll()
            row = work[y, :, channel]
            row += amount*(row-blurred[y])
            if channel == 3:
                alpha_clips += int(np.count_nonzero((row < 0) | (row > 1)))
                np.clip(row, 0., 1., out=row)
            elif plan.code_gamut == 'clip':
                code_clips += int(np.count_nonzero((row < 0) | (row > maximum)))
                np.clip(row, 0., maximum, out=row)
    target = encoded.reshape(-1, 4)
    for start in range(0, len(flat), tile):
        poll()
        part = flat[start:start+tile]
        with np.errstate(over='ignore', invalid='ignore'):
            if rgb_active:
                target[start:start+len(part), :3] = _from_codes(part[:, :3], plan)
            if active[3]:
                target[start:start+len(part), 3] = part[:, 3]
        if not np.isfinite(target[start:start+len(part)]).all():
            raise error('VALUES', '锐化中间值超出Float32有限范围')
    return code_clips, alpha_clips


def apply_sharpen(surface, plan, author_tick, *, working_signal, tile_pixels=65536,
                  retained_table_bytes=0, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    if cancel is not None and not callable(cancel):
        raise error('ARGUMENT', '取消回调须可调用')
    def poll():
        if cancel and cancel():
            raise AppError('RENDER_CANCELLED', '浮点锐化已取消', exit_code=6)
    poll()
    values = state_at(plan, author_tick)
    if not isinstance(working_signal, ColorSignal) or working_signal.transfer != 'linear':
        raise error('SIGNAL', '锐化须使用明确线性工作信号')
    if (not isinstance(surface, np.ndarray) or surface.dtype != np.float32 or surface.ndim != 3
            or surface.shape[-1] != 4 or not surface.flags.c_contiguous):
        raise error('SURFACE', '锐化输入须为连续H×W×4 Float32')
    h, w = surface.shape[:2]
    pixels = h*w
    if min(h, w) < 1 or max(h, w) > 16384 or pixels > 16777216:
        raise error('BUDGET', '锐化表面超过尺寸预算')
    tile, estimate, admission = admit_spatial(surface_bytes=int(surface.nbytes), pixels=pixels,
        tile_pixels=tile_pixels, tracks_bytes=len(plan.tracks_json.encode('utf8')),
        retained_table_bytes=retained_table_bytes, max_working_bytes=max_working_bytes,
        error=error, line_scratch_bytes=(max(h, w)+23)*8*6)
    source = surface.reshape(-1, 4)
    for start in range(0, pixels, tile):
        poll()
        part = source[start:start+tile]
        if not np.isfinite(part).all() or np.any(part[:, 3] < 0) or np.any(part[:, 3] > 1):
            raise error('VALUES', 'RGB须有限且alpha须在0..1')
    active = tuple(bool(_amount(values[plane+'_amount'], plan)) and (
        values[plane+'_radius_x'] != 0 or values[plane+'_radius_y'] != 0)
        for plane in ('luma', 'chroma', 'chroma', 'alpha'))
    strength = values['intensity']
    bypass_rgb = not any(active[:3]) and plan.input_signal == plan.output_signal and plan.output_gamut == 'preserve'
    code_clips = alpha_clips = output_clips = 0
    if strength == 0 or not any(active) and plan.input_signal == plan.output_signal and plan.output_gamut == 'preserve':
        result = surface.copy()
    else:
        if bypass_rgb:
            encoded = surface.copy()
        else:
            encoded, _ = convert_rgba(surface, working_signal, plan.input_signal, tile_pixels=tile,
                                      max_working_bytes=max_working_bytes, cancel=poll)
        if any(active):
            code_clips, alpha_clips = _sharpen_codes(encoded, plan, values, active, tile, poll)
        flat = encoded.reshape(-1, 4)
        if plan.output_gamut == 'clip':
            for start in range(0, pixels, tile):
                poll()
                part = flat[start:start+tile, :3]
                output_clips += int(np.count_nonzero((part < 0) | (part > 1)))
                np.clip(part, 0., 1., out=part)
        if bypass_rgb:
            graded = encoded
        else:
            graded, _ = convert_rgba(encoded, plan.output_signal, working_signal, tile_pixels=tile,
                                     max_working_bytes=max_working_bytes, cancel=poll)
        result = np.empty_like(surface)
        target, flat = result.reshape(-1, 4), graded.reshape(-1, 4)
        for start in range(0, pixels, tile):
            poll()
            part, value = source[start:start+tile], flat[start:start+tile]
            out = target[start:start+len(part)]
            with np.errstate(over='ignore', invalid='ignore'):
                out[:] = value if strength == 1 else part.astype(np.float64)*(1-strength)+value.astype(np.float64)*strength
            if not active[3]:
                out[:, 3] = part[:, 3]
            if bypass_rgb:
                out[:, :3] = part[:, :3]
            if not np.isfinite(out).all() or np.any(out[:, 3] < 0) or np.any(out[:, 3] > 1):
                raise error('VALUES', '锐化输出超出有限值或alpha范围')
    poll()
    eligible = {}
    for plane in ('luma', 'chroma', 'alpha'):
        rx, ry = values[plane+'_radius_x'], values[plane+'_radius_y']
        eligible[plane] = (rx.is_integer() and ry.is_integer() and min(rx, ry) >= 1
                           and 2*(rx+ry) <= 25 and values[plane+'_amount'] <= 5)
    return result, {'protocol': PROTOCOL, 'effect_type': 'sharpen', 'author_tick': str(author_tick),
        'sampled_values': values, 'effective_amounts': {p: _amount(values[p+'_amount'], plan) for p in eligible},
        'input_signal': vars(plan.input_signal), 'output_signal': vars(plan.output_signal),
        'working_signal': vars(working_signal), 'operator_domain': 'declared-signal-YCbCr',
        'matrix': plan.matrix, 'range': plan.range, 'reference_bits': plan.reference_bits,
        'arithmetic': plan.arithmetic, 'native_storage_shift': 16 if plan.reference_bits == 8 else 24,
        'native_kernel_and_amount_option_eligible': eligible,
        'native_accumulator_safe_at_reference_max': {p: plan.reference_bits+2*(
            values[p+'_radius_x']+values[p+'_radius_y']) <= 32 for p in eligible},
        'reference_bits_native_format_supported': plan.reference_bits != 14,
        'native_fixedpoint_overflow_reproduced': False,
        'code_gamut': plan.code_gamut, 'clipped_code_components': code_clips,
        'alpha': 'explicit-unsharp-coverage-mapping' if active[3] and strength != 0 else 'input-bits-preserved',
        'alpha_mode': 'straight-independent-coverage-clipped-0-1', 'clipped_alpha_pixels': alpha_clips,
        'alpha_only_RGB_conversion_bypassed': bypass_rgb,
        'output_gamut': plan.output_gamut, 'output_clipped_components': output_clips,
        'raster_dtype': 'float32', 'spatial_scratch_dtype': 'float64', 'integer_intermediate': False,
        'kernel': 'normalized-binomial-Pascal', 'fractional_radius': 'convex-adjacent-integer-kernels',
        'boundary': 'replicated-endpoints', 'RGB_mix_domain': 'linear-working-straight-RGB',
        'alpha_mix': 'linear-coverage', 'full_scratch_released_before_output_conversion': True,
        'estimated_working_bytes': estimate, 'workspace_admission': admission,
        'estimated_bytes_are_peak_RSS': False, 'native_bit_equivalence': False,
        'natural_quality_accepted': False, 'HDR_accepted': False}
