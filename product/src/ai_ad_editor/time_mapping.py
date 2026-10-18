"""Monotone, source-attached clocks for nested local timeline rendering.

The persisted project keeps authored clips. These JSON-safe maps are render
plan data, in seconds, and compose without replacing ramps by average rates.
"""
from __future__ import annotations

import math
from typing import Any

from .errors import AppError


def curve_elapsed(segments, source_seconds: float) -> float:
    target = max(0., float(source_seconds))
    elapsed = 0.
    for start, end, left, right in segments:
        if target <= start:
            break
        span = end - start
        local = min(target, end) - start
        if span <= 1e-12 or local <= 0:
            continue
        slope = (right - left) / span
        elapsed += local / left if right == left else math.log1p(slope * local / left) / slope
        if target <= end:
            break
    return max(0., elapsed)


def curve_source_at_elapsed(segments, elapsed_seconds: float) -> float:
    remaining = max(0., float(elapsed_seconds))
    for start, end, left, right in segments:
        span = end - start
        if span <= 1e-12:
            continue
        slope = (right - left) / span
        duration = span / left if right == left else math.log1p((right-left)/left) / slope
        if remaining > duration + 1e-10:
            remaining -= duration
            continue
        local = remaining * left if right == left else left * math.expm1(slope * remaining) / slope
        return min(end, max(start, start + local))
    return float(segments[-1][1]) if segments else 0.


def make_map(clip: dict[str, Any], segments, tps: int) -> dict[str, Any]:
    source_start = int(clip.get('source_in_tick', 0)) / tps
    source_end = int(clip.get('source_out_tick', 1)) / tps
    duration = max(1, int(clip.get('duration_tick', 1))) / tps
    curve_total = curve_elapsed(segments, source_end - source_start) if segments else None
    result = {
        'source_start': source_start, 'source_end': source_end,
        'timeline_start': int(clip.get('timeline_start_tick', 0)) / tps,
        'timeline_duration': duration, 'speed': max(.01, float(clip.get('speed', 1.))),
        'reverse': bool(clip.get('reverse')), 'segments': [list(item) for item in segments],
        'curve_scale': duration / max(1e-12, curve_total) if curve_total is not None else 1.,
    }
    certificate = getattr(segments, 'certificate', {})
    if certificate.get('adaptive'):
        result['curve_compilation'] = {**certificate,
            'normalized_clock_error_bound_seconds': 2 * certificate['source_clock_error_bound_seconds'] * result['curve_scale']}
    return result


def map_time(mapping: dict[str, Any], source: float) -> float:
    local = max(0., min(mapping['source_end'] - mapping['source_start'], source - mapping['source_start']))
    segments = mapping['segments']
    elapsed = curve_elapsed(segments, local) * mapping['curve_scale'] if segments else local / mapping['speed']
    return mapping['timeline_start'] + (mapping['timeline_duration'] - elapsed if mapping['reverse'] else elapsed)


def unmap_time(mapping: dict[str, Any], timeline: float) -> float:
    elapsed = timeline - mapping['timeline_start']
    if mapping['reverse']:
        elapsed = mapping['timeline_duration'] - elapsed
    segments = mapping['segments']
    local = curve_source_at_elapsed(segments, elapsed / mapping['curve_scale']) if segments else elapsed * mapping['speed']
    return max(mapping['source_start'], min(mapping['source_end'], mapping['source_start'] + local))


def compose_time(mappings, value: float, *, inverse: bool = False) -> float:
    for mapping in reversed(mappings) if inverse else mappings:
        value = unmap_time(mapping, value) if inverse else map_time(mapping, value)
    return value


def _n(value: float) -> str:
    return f'{float(value):.14g}'


def _curve_expression(segments, clock: str, *, inverse: bool = False) -> str:
    elapsed = 0.
    branches = []
    for start, end, left, right in segments:
        span = end - start
        if span <= 1e-12:
            continue
        slope = (right - left) / span
        duration = span / left if right == left else math.log1p((right-left)/left) / slope
        if inverse:
            local = f'(({clock})-{_n(elapsed)})'
            if right == left:
                offset = f'({local}*{_n(left)})'
            elif abs((right-left)/left) <= 1e-5:
                z = f'({_n(slope)}*{local})'
                offset = f'({_n(left)}*{local}*(1+({z})/2+pow({z},2)/6+pow({z},3)/24+pow({z},4)/120))'
            else:
                offset = f'({_n(left / slope)}*(exp({_n(slope)}*{local})-1))'
            branches.append((elapsed + duration, f'({_n(start)}+{offset})'))
        else:
            local = f'(({clock})-{_n(start)})'
            if right == left:
                offset = f'({local}/{_n(left)})'
            elif abs((right-left)/left) <= 1e-5:
                z = f'({_n(slope/left)}*{local})'
                offset = f'({local}/{_n(left)}*(1-({z})/2+pow({z},2)/3-pow({z},3)/4+pow({z},4)/5))'
            else:
                offset = f'(log(1+{_n(slope / left)}*{local})/{_n(slope)})'
            branches.append((end, f'({_n(elapsed)}+{offset})'))
        elapsed += duration
    def select(items):
        if len(items) == 1: return items[0][1]
        middle = len(items)//2
        return f'if(lt(({clock}),{_n(items[middle-1][0])}),{select(items[:middle])},{select(items[middle:])})'
    return select(branches) if branches else '0'


def compose_expression(mappings, clock: str, *, inverse: bool = False, scratch_register: int | None = None) -> str:
    """Build register-free arithmetic, or a dedicated setpts-local program."""
    if scratch_register is not None:
        # Only use this in a dedicated setpts expression. Geometry expressions
        # retain the register-free path because geq owns all ten registers.
        if not 0 <= scratch_register <= 9: raise ValueError('Invalid FFmpeg expression register')
        steps = [f'st({scratch_register},{clock})']
        for mapping in reversed(mappings) if inverse else mappings:
            value = compose_expression([mapping], f'ld({scratch_register})', inverse=inverse)
            steps.append(f'st({scratch_register},{value})')
        return '('+';'.join([*steps, f'ld({scratch_register})'])+')'
    for mapping in reversed(mappings) if inverse else mappings:
        span = mapping['source_end'] - mapping['source_start']
        segments = mapping['segments']
        if inverse:
            local = f'(({clock})-{_n(mapping["timeline_start"])})'
            if mapping['reverse']:
                local = f'({_n(mapping["timeline_duration"])}-({local}))'
            if segments:
                total = curve_elapsed(segments, span)
                local = f'clip(({local})/{_n(mapping["curve_scale"])},0,{_n(total)})'
                local = _curve_expression(segments, local, inverse=True)
            else:
                local = f'(({local})*{_n(mapping["speed"])})'
            clock = f'({_n(mapping["source_start"])}+clip(({local}),0,{_n(span)}))'
        else:
            local = f'clip((({clock})-{_n(mapping["source_start"])}),0,{_n(span)})'
            if segments:
                local = f'({_curve_expression(segments, local)}*{_n(mapping["curve_scale"])})'
            else:
                local = f'(({local})/{_n(mapping["speed"])})'
            if mapping['reverse']:
                local = f'({_n(mapping["timeline_duration"])}-({local}))'
            clock = f'({_n(mapping["timeline_start"])}+({local}))'
        if len(clock) > 4*1024*1024:
            raise AppError('TIME_MAPPING_EXPRESSION_LIMIT', '组合时钟表达式超过 4 MiB；请拆分动画/曲线层级', exit_code=2)
    return clock


def audio_windows(mappings, source_start: float, source_end: float):
    """Constant atempo windows with exact integrated cumulative boundaries.

    This preserves the existing explicit phase/continuous-tempo limitation.
    The caller applies a source-order reversal after concatenating windows.
    """
    count = max(1, int(math.ceil((source_end - source_start) * 8)))
    if count > 16384:
        raise ValueError('nested audio mapping exceeds 16384 tempo windows')
    cuts = {source_start + (source_end-source_start)*i/count for i in range(count+1)}
    # Preserve every authored speed knot in the original source clock. A
    # uniform sample interval may straddle a hold discontinuity; averaging it
    # moves content and unnecessarily restarts the native tempo processor.
    for index, mapping in enumerate(mappings):
        for segment in mapping['segments']:
            for local in segment[:2]:
                knot = compose_time(mappings[:index], mapping['source_start']+local, inverse=True)
                if source_start+1e-10 < knot < source_end-1e-10:
                    cuts.add(knot)
    cuts = sorted(cuts)
    if len(cuts)-1 > 16384:
        raise ValueError('nested audio mapping exceeds 16384 tempo windows')
    base = compose_time(mappings, source_start)
    parts = []
    for left, right in zip(cuts,cuts[1:]):
        if right-left < 1e-10:
            continue
        output_left = compose_time(mappings, left)
        output_right = compose_time(mappings, right)
        duration = abs(output_right - output_left)
        if duration * 48000 < 1:
            raise ValueError('nested audio tempo window is shorter than one 48 kHz sample')
        part = (left-source_start,right-source_start,(right-left)/duration,abs(output_right-base))
        if parts and math.isclose(parts[-1][2],part[2],rel_tol=1e-10,abs_tol=1e-12):
            first = parts.pop()[0]
            elapsed = abs(output_right-compose_time(mappings,source_start+first))
            part = (first,right-source_start,(right-source_start-first)/elapsed,abs(output_right-base))
        parts.append(part)
    return parts
