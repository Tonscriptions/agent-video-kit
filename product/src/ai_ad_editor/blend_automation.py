"""Editable opacity author curves with independent relative output clocks.

Persist author ticks and relative transforms, never compiled filter expressions.
Native commands share the root render's existing sampling/command budgets.
"""
from __future__ import annotations

from bisect import bisect_right
import copy
from fractions import Fraction
import json
import math

from .animation import keyframe_value
from .errors import AppError
from .time_mapping import compose_time, curve_source_at_elapsed

PROPERTIES = ('blend.opacity', 'blend_opacity')
MAX_STAGES = 16
MAX_POINTS = 4096
MAX_MODEL_BYTES = 1024 * 1024
MAX_TICK = 2**53 - 1


def fail(message):
    raise AppError('BLEND_AUTOMATION_INVALID', message, exit_code=2)


def _integer(value, *, minimum=0):
    if type(value) is not int or not minimum <= value <= MAX_TICK:
        fail('混合动画时钟必须使用精确范围内的整数 tick')
    return value


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def track_for(clip):
    tracks = {k.get('property'): k for k in clip.get('keyframes', []) if isinstance(k, dict)}
    return next((tracks[p] for p in PROPERTIES if p in tracks), None)


class OpacityClock:
    def __init__(self, value, settings):
        from .retime_transform import Transform
        if not isinstance(value, dict) or set(value) != {'version', 'author_duration_tick', 'keyframes', 'clock_maps'}:
            fail('opacity_animation 需要 version/author_duration_tick/keyframes/clock_maps')
        if type(value['version']) is not int or value['version'] != 1:
            fail('混合动画 version 必须为整数 1')
        duration = _integer(value['author_duration_tick'], minimum=1)
        points = value['keyframes']
        if not isinstance(points, list) or not 1 <= len(points) <= MAX_POINTS:
            fail('混合动画关键帧必须非空且不超过 4096 点')
        previous = -1
        for point in points:
            if not isinstance(point, dict) or set(point) - {'at_tick', 'value', 'interpolation', 'control_points'}:
                fail('混合动画关键帧包含未知字段')
            tick = _integer(point.get('at_tick'))
            if tick <= previous or tick > duration:
                fail('混合动画关键帧须递增且位于完整作者区间内')
            previous = tick
            amount = point.get('value')
            if not _finite(amount) or not 0 <= amount <= 1:
                fail('混合强度必须为 0..1 的有限数字')
            interpolation = point.get('interpolation', 'linear')
            if not isinstance(interpolation, str) or interpolation not in {'hold', 'linear', 'ease_in', 'ease_out', 'ease_in_out', 'bezier'}:
                fail('混合动画插值无效')
            if interpolation == 'bezier':
                control = point.get('control_points')
                if (not isinstance(control, list) or len(control) not in (2, 4)
                    or any(not _finite(x) for x in control)
                    or len(control) == 4 and not (0 <= control[0] <= 1 and 0 <= control[2] <= 1)):
                    fail('混合动画 Bezier 控制点无效')
        rows = value['clock_maps']
        if not isinstance(rows, list) or len(rows) > MAX_STAGES:
            fail('混合动画时钟不得超过 16 层')
        self.tps = settings['timebase']['ticks_per_second']
        fps = settings['timebase']['display_fps']
        self.rate = Fraction(fps['num'], fps['den'])
        self.models = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'input_duration_tick', 'transform', 'offset_tick'}:
                fail('混合动画时钟只允许 input_duration_tick/transform/offset_tick')
            size = _integer(row['input_duration_tick'], minimum=1)
            if type(row['offset_tick']) is not int or abs(row['offset_tick']) > MAX_TICK:
                fail('混合动画 offset_tick 必须为精确范围内整数')
            try:
                transform = Transform(row['transform'], size, settings)
            except AppError as exc:
                raise AppError('BLEND_AUTOMATION_INVALID', '混合动画相对时钟无效', exit_code=2,
                               cause=exc.as_dict()) from exc
            self.models.append((transform, row['offset_tick']))
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')) > MAX_MODEL_BYTES:
            fail('混合动画作者模型不得超过 1 MiB')
        self.points, self.ticks = copy.deepcopy(points), [p['at_tick'] for p in points]

    def author_tick(self, tick):
        for transform, offset in self.models:
            # Mirror the native loop's displayed hold frame and quantized hold
            # length. Unaligned requests remain covered by the renderer warning.
            if transform.hold:
                frame_tick = float(Fraction(self.tps, 1) / self.rate)
                freeze = transform.value['freeze']
                first = math.ceil(freeze['at_tick'] / frame_tick - 1e-8)
                hold_start = first * frame_tick
                count = max(1, round(transform.hold / frame_tick))
                if hold_start <= tick < hold_start + count * frame_tick:
                    tick = max(0, first - 1) * frame_tick
                elif tick >= hold_start + count * frame_tick:
                    tick -= count * frame_tick
            tick = max(0., min(float(transform.content), tick))
            if transform.value.get('reverse'):
                tick = transform.content - tick
            if transform.segments:
                elapsed = tick / transform.content * transform.elapsed
                tick = curve_source_at_elapsed(transform.segments, elapsed) * self.tps
            else:
                tick = tick / transform.content * transform.duration
            tick += offset
        return tick

    def value_at_tick(self, tick):
        tick = self.author_tick(tick)
        index = bisect_right(self.ticks, tick) - 1
        if index < 0:
            return float(self.points[0]['value'])
        if index >= len(self.points) - 1:
            return float(self.points[-1]['value'])
        return keyframe_value({'keyframes': [{'property': 'v', 'keyframes': self.points[index:index+2]}]},
                              ('v',), 0., tick)


class OpacityCurve:
    def __init__(self, animation, clip, start, tps, rate):
        self.clip, self.start, self.tps = clip, start, tps
        self.clock = clip.get('_nested_keyframe_clock')
        self.origin = clip.get('timeline_start_tick', round(start*tps)) / tps
        self.model = OpacityClock(animation, {'timebase': {'ticks_per_second': tps,
            'display_fps': {'num': rate.numerator, 'den': rate.denominator}}})

    def value(self, display):
        local = display - self.start
        if self.clock:
            local = compose_time(self.clock['maps'], local + self.origin, inverse=True) - self.clock['authored_start']
        return self.model.value_at_tick(local * self.tps)


def retimed_blend(original, host, transform, settings):
    """Detach external blending before wrapping the picture's author graph."""
    blend = copy.deepcopy(original.get('blend'))
    track = track_for(original)
    animation = (blend or {}).get('opacity_animation')
    if track is not None:
        window = original.get('presentation_window', {})
        animation = {'version': 1,
            'author_duration_tick': window.get('authored_duration_tick', original['duration_tick']),
            'keyframes': copy.deepcopy(track.get('keyframes')), 'clock_maps': []}
    if animation is None:
        return blend
    OpacityClock(animation, settings)
    animation = copy.deepcopy(animation)
    window = original.get('presentation_window', {})
    animation['clock_maps'].insert(0, {'input_duration_tick': host['duration_tick'],
        'transform': copy.deepcopy(transform.value),
        'offset_tick': host['timeline_start_tick'] - original['timeline_start_tick'] + window.get('offset_tick', 0)})
    OpacityClock(animation, settings)
    original['keyframes'] = [k for k in original.get('keyframes', []) if k.get('property') not in PROPERTIES]
    return {**(blend or {}), 'opacity_animation': animation}
