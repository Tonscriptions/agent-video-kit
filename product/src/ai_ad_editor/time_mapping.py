"""Monotone, source-attached clocks for nested local timeline rendering.

The persisted project keeps authored clips. These JSON-safe maps are render
plan data, in seconds, and compose without replacing ramps by average rates.
"""
from __future__ import annotations

import math
from typing import Any


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
        elapsed += local / left if abs(right - left) < 1e-8 else math.log1p(slope * local / left) / slope
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
        duration = span / left if abs(right - left) < 1e-8 else math.log(right / left) / slope
        if remaining > duration + 1e-10:
            remaining -= duration
            continue
        local = remaining * left if abs(right - left) < 1e-8 else left * math.expm1(slope * remaining) / slope
        return min(end, max(start, start + local))
    return float(segments[-1][1]) if segments else 0.


def make_map(clip: dict[str, Any], segments, tps: int) -> dict[str, Any]:
    source_start = int(clip.get('source_in_tick', 0)) / tps
    source_end = int(clip.get('source_out_tick', 1)) / tps
    duration = max(1, int(clip.get('duration_tick', 1))) / tps
    curve_total = curve_elapsed(segments, source_end - source_start) if segments else None
    return {
        'source_start': source_start, 'source_end': source_end,
        'timeline_start': int(clip.get('timeline_start_tick', 0)) / tps,
        'timeline_duration': duration, 'speed': max(.01, float(clip.get('speed', 1.))),
        'reverse': bool(clip.get('reverse')), 'segments': [list(item) for item in segments],
        'curve_scale': duration / max(1e-12, curve_total) if curve_total is not None else 1.,
    }


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
        duration = span / left if abs(right - left) < 1e-8 else math.log(right / left) / slope
        if inverse:
            local = f'(({clock})-{_n(elapsed)})'
            offset = f'({local}*{_n(left)})' if abs(right - left) < 1e-8 else f'({_n(left / slope)}*(exp({_n(slope)}*{local})-1))'
            branches.append((elapsed + duration, f'({_n(start)}+{offset})'))
        else:
            local = f'(({clock})-{_n(start)})'
            offset = f'({local}/{_n(left)})' if abs(right - left) < 1e-8 else f'(log(1+{_n(slope / left)}*{local})/{_n(slope)})'
            branches.append((end, f'({_n(elapsed)}+{offset})'))
        elapsed += duration
    result = _n(segments[-1][1] if inverse else elapsed) if segments else '0'
    for boundary, expression in reversed(branches):
        result = f'if(lt(({clock}),{_n(boundary)}),{expression},{result})'
    return result


def compose_expression(mappings, clock: str, *, inverse: bool = False) -> str:
    """Build ordinary FFmpeg arithmetic; use no shared expression registers."""
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
    return clock


def audio_windows(mappings, source_start: float, source_end: float):
    """Constant atempo windows with exact integrated cumulative boundaries.

    This preserves the existing explicit phase/continuous-tempo limitation.
    The caller applies a source-order reversal after concatenating windows.
    """
    count = max(1, int(math.ceil((source_end - source_start) * 8)))
    if count > 16384:
        raise ValueError('nested audio mapping exceeds 16384 tempo windows')
    base = compose_time(mappings, source_start)
    parts = []
    for index in range(count):
        left = source_start + (source_end - source_start) * index / count
        right = source_start + (source_end - source_start) * (index + 1) / count
        output_left = compose_time(mappings, left)
        output_right = compose_time(mappings, right)
        duration = abs(output_right - output_left)
        if duration * 48000 < 1:
            raise ValueError('nested audio tempo window is shorter than one 48 kHz sample')
        parts.append((left - source_start, right - source_start, (right - left) / duration, abs(output_right - base)))
    return parts
