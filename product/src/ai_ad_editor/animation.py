"""Shared numeric easing samples for the renderer and coordinate compiler."""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=256)
def _samples(controls: tuple[float, ...]) -> tuple[float, ...]:
    x1, y1, x2, y2 = controls if len(controls) == 4 else (1/3, controls[0], 2/3, controls[1])
    def cubic(a: float, b: float, u: float) -> float:
        return 3*(1-u)**2*u*a + 3*(1-u)*u*u*b + u**3
    result = []
    for index in range(33):
        low, high = 0.0, 1.0
        for _ in range(20):
            middle = (low+high)/2
            if cubic(x1, x2, middle) < index/32:
                low = middle
            else:
                high = middle
        result.append(cubic(y1, y2, (low+high)/2))
    return tuple(result)


def bezier_samples(controls: Any) -> tuple[float, ...] | None:
    if not isinstance(controls, (list, tuple)):
        return None
    values = []
    for value in controls:
        if isinstance(value, dict):
            value = value.get('y', value.get('value'))
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    return _samples(tuple(values[:4] if len(values) >= 4 else values[:2])) if len(values) >= 2 else None


def keyframe_value(clip: dict[str, Any], names: tuple[str, ...], default: float, at_tick: float) -> float:
    tracks = {str(t.get('property')): t for t in clip.get('keyframes', []) if isinstance(t, dict)}
    track = next((tracks[n] for n in names if n in tracks), None)
    points = sorted(track.get('keyframes', []), key=lambda k: k['at_tick']) if track else []
    if not points:
        return default
    if at_tick < points[0]['at_tick']:
        return float(points[0]['value'])
    for left, right in zip(points, points[1:]):
        if at_tick >= right['at_tick']:
            continue
        p = max(0.0, min(1.0, (at_tick-left['at_tick'])/max(1e-9, right['at_tick']-left['at_tick'])))
        easing = left.get('interpolation', 'linear')
        if easing == 'hold':
            p = 0.0
        elif easing == 'ease_in':
            p *= p
        elif easing == 'ease_out':
            p = 1-(1-p)**2
        elif easing == 'ease_in_out':
            p = 2*p*p if p < .5 else 1-(-2*p+2)**2/2
        elif easing == 'bezier':
            samples = bezier_samples(left.get('control_points'))
            if samples:
                index = min(31, int(p*32))
                # Match the renderer's serialized eight-decimal lookup.
                start = float(f'{samples[index]:.8f}')
                slope = float(f'{(samples[index+1]-samples[index])*32:.8f}')
                p = start+slope*(p-index/32)
        return float(left['value'])+(float(right['value'])-float(left['value']))*p
    return float(points[-1]['value'])
