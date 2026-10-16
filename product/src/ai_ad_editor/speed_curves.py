"""Local speed easing compiled with a conservative source-clock error bound."""
from __future__ import annotations

import math
from typing import Any

from .errors import AppError


CLOCK_ERROR_SECONDS = .00025
MAX_SEGMENTS = 1024


class CompiledCurve(list):
    def __init__(self, segments=(), certificate=None):
        super().__init__(segments)
        self.certificate = certificate or {}


def fail(code, message):
    raise AppError(code, message, exit_code=2, path='speed_curve')


def _number(value):
    if isinstance(value, bool): fail('SPEED_CURVE_CONTROL_POINTS_INVALID', '速度曲线参数必须为有限数字')
    try: result = float(value)
    except (TypeError, ValueError): fail('SPEED_CURVE_CONTROL_POINTS_INVALID', '速度曲线参数必须为有限数字')
    if not math.isfinite(result): fail('SPEED_CURVE_CONTROL_POINTS_INVALID', '速度曲线参数必须为有限数字')
    return result


def controls_for(point):
    controls = point.get('control_points')
    if not isinstance(controls, list) or len(controls) not in {2, 4}:
        fail('SPEED_CURVE_CONTROL_POINTS_INVALID', 'Bezier 速度曲线需要 2 或 4 个 control_points')
    values = tuple(_number(v) for v in controls)
    if len(values) == 2: values = (1/3, values[0], 2/3, values[1])
    if not 0 <= values[0] <= 1 or not 0 <= values[2] <= 1:
        fail('SPEED_CURVE_CONTROL_POINT_RANGE', 'Bezier 速度曲线 x 控制点必须位于 0 到 1')
    return values


def _minimum(values):
    p, q, r, s = values
    a, b, c = -p+3*q-3*r+s, 3*(p-2*q+r), 3*(q-p)
    candidates = [p, s]
    if not all(math.isfinite(v) for v in (a, b, c)):
        fail('SPEED_CURVE_CONTROL_POINT_RANGE', 'Bezier 速度系数超出有限数字范围')
    if abs(a) < 1e-14:
        roots = [-c/(2*b)] if abs(b) > 1e-14 else []
    else:
        disc = 4*b*b-12*a*c
        if not math.isfinite(disc):
            fail('SPEED_CURVE_CONTROL_POINT_RANGE', 'Bezier 速度判别式超出有限数字范围')
        roots = [(-2*b+math.sqrt(disc))/(6*a), (-2*b-math.sqrt(disc))/(6*a)] if disc >= 0 else []
    for u in roots:
        if 0 < u < 1: candidates.append(((a*u+b)*u+c)*u+p)
    return min(candidates)


def _split(points):
    levels = [points]
    while len(levels[-1]) > 1:
        levels.append([((a[0]+b[0])/2, (a[1]+b[1])/2) for a, b in zip(levels[-1], levels[-1][1:])])
    return [level[0] for level in levels], [level[-1] for level in reversed(levels)]


def compile_curve(clip: dict[str, Any], source_span_tick: int, tps: int) -> CompiledCurve:
    curve = clip.get('speed_curve')
    raw = curve.get('keyframes', []) if isinstance(curve, dict) else curve
    if not isinstance(raw, list) or not raw or source_span_tick <= 0: return CompiledCurve()
    base = max(.01, _number(clip.get('speed', 1.)))
    points = []
    for item in raw:
        if not isinstance(item, dict): fail('SPEED_CURVE_INVALID', '速度曲线关键帧必须为对象')
        at = item.get('at_tick', 0)
        if isinstance(at, bool) or not isinstance(at, int) or not 0 <= at <= source_span_tick:
            fail('SPEED_CURVE_RANGE', '速度曲线 at_tick 必须为源范围内的整数')
        speed = _number(item.get('speed', item.get('value', base)))
        if speed <= 0: fail('SPEED_CURVE_SPEED_INVALID', '速度曲线 speed 必须为正数')
        mode = str(item.get('interpolation', 'linear'))
        if mode not in {'hold', 'linear', 'ease_in', 'ease_out', 'ease_in_out', 'bezier'}:
            fail('SPEED_CURVE_INTERPOLATION_INVALID', '速度曲线插值类型无效')
        controls = controls_for(item) if mode == 'bezier' else None
        points.append((at, max(.01, speed), mode, controls))
    # Preserve the established last-keyframe-wins behavior at equal ticks.
    points = sorted({p[0]: p for p in points}.values())
    if points[0][0] > 0: points.insert(0, (0, base, 'hold', None))
    if points[-1][0] < source_span_tick: points.append((source_span_tick, points[-1][1], 'hold', None))
    segments = []
    errors = []
    adaptive = False
    source_span = source_span_tick/tps

    def append(segment, error=0.):
        if len(segments) >= MAX_SEGMENTS:
            fail('SPEED_CURVE_COMPLEXITY_LIMIT', '速度曲线超过 1024 个有界编译段；请拆分时间线')
        segments.append(segment); errors.append(error)

    def subdivide(control, depth=0):
        x0, v0 = control[0]; x3, v3 = control[-1]
        width = x3-x0
        if width <= 0 or depth > 28:
            fail('SPEED_CURVE_COMPLEXITY_LIMIT', '速度曲线无法在深度/浮点预算内达到时钟精度')
        low = min(v for _, v in control)
        line_low = min(v0, v3)
        deviation = max(abs(v-(v0+(v3-v0)*(x-x0)/width)) for x, v in control)
        bound = width*deviation/(low*line_low) if low > 0 and line_low > 0 else math.inf
        if bound <= CLOCK_ERROR_SECONDS*width/source_span:
            append((x0, x3, v0, v3), bound)
        else:
            left, right = _split(control)
            subdivide(left, depth+1); subdivide(right, depth+1)

    for left, right in zip(points, points[1:]):
        start, end = left[0]/tps, right[0]/tps
        a, b, mode = left[1], right[1], left[2]
        if mode in {'hold', 'linear'}:
            append((start, end, a, a if mode == 'hold' else b)); continue
        adaptive = True
        groups = [(start, end, a, b, left[3])]
        if mode == 'ease_in': groups = [(start, end, a, b, (1/3, 0., 2/3, 1/3))]
        elif mode == 'ease_out': groups = [(start, end, a, b, (1/3, 2/3, 2/3, 1.))]
        elif mode == 'ease_in_out':
            mid, v = (start+end)/2, (a+b)/2
            groups = [(start, mid, a, v, (1/3, 0., 2/3, 1/3)), (mid, end, v, b, (1/3, 2/3, 2/3, 1.))]
        for lo, hi, va, vb, handles in groups:
            x1, y1, x2, y2 = handles
            control = [(lo, va), (lo+(hi-lo)*x1, va+(vb-va)*y1),
                       (lo+(hi-lo)*x2, va+(vb-va)*y2), (hi, vb)]
            if not all(math.isfinite(v) for p in control for v in p):
                fail('SPEED_CURVE_CONTROL_POINT_RANGE', 'Bezier 速度控制点超出有限数字范围')
            if _minimum([v for _, v in control]) <= 0:
                fail('SPEED_CURVE_NONPOSITIVE', 'Bezier 速度曲线内部必须保持正速度；未自动截断曲线')
            subdivide(control)
    return CompiledCurve(segments, {
        'version': '1', 'adaptive': adaptive, 'method': 'bernstein-bounded-linear-speed',
        'source_clock_error_bound_seconds': math.fsum(errors), 'requested_max_error_seconds': CLOCK_ERROR_SECONDS,
        'segment_count': len(segments), 'maximum_segments': MAX_SEGMENTS,
        'authored_interpolations': sorted({point[2] for point in points}),
        'source_endpoint_speed_floor': .01,
    })
