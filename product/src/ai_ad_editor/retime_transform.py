"""A bounded relative output-clock transform shared by retime clip groups."""
from __future__ import annotations

import copy
from fractions import Fraction
import math

from .edit_planner import _error, _integer
from .speed_curves import compile_curve
from .time_mapping import curve_elapsed


def number(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(float(value)) and float(value) >= .01
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        _error('EDIT_RETIME_REQUEST_INVALID', '速度必须为不低于 0.01 的有限数字')
    return float(value)


class Transform:
    def __init__(self, value, duration, settings):
        fields = {'speed', 'speed_curve', 'reverse', 'freeze'}
        if not isinstance(value, dict) or not value or set(value)-fields:
            _error('EDIT_RETIME_REQUEST_INVALID', 'transform 只接受非空 speed/speed_curve/reverse/freeze')
        self.value = copy.deepcopy(value)
        self.tps = settings['timebase']['ticks_per_second']
        self.duration = duration
        speed = number(value.get('speed', 1.))
        if 'reverse' in value and type(value['reverse']) is not bool:
            _error('EDIT_RETIME_REQUEST_INVALID', 'reverse 必须为布尔值')
        if 'speed_curve' in value:
            raw = value['speed_curve']
            keys = raw.get('keyframes') if isinstance(raw, dict) and set(raw)=={'keyframes'} else raw if isinstance(raw, list) else None
            if not isinstance(keys, list) or not keys:
                _error('EDIT_RETIME_REQUEST_INVALID', 'speed_curve 必须包含非空 keyframes')
            for point in keys:
                if not isinstance(point, dict) or set(point)-{'at_tick','speed','value','interpolation','control_points'}:
                    _error('EDIT_RETIME_REQUEST_INVALID', '速度关键帧包含未知字段')
                number(point.get('speed', point.get('value', speed)))
        self.segments = compile_curve(value, duration, self.tps)
        if any(min(a,b)<.01-1e-12 for _,_,a,b in self.segments):
            _error('EDIT_RETIME_REQUEST_INVALID', '曲线内部速度低于原生 0.01 下界；未静默抬升')
        self.elapsed = curve_elapsed(self.segments, duration/self.tps) if self.segments else duration/self.tps/speed
        self.content = round(self.elapsed*self.tps)
        if self.content <= 0 or self.content > 2**53-1:
            _error('EDIT_RETIME_CLOCK_RANGE', '变速后长度为零或超出精确整数时钟')
        freeze = value.get('freeze')
        self.hold = 0
        self.anchor = None
        if 'freeze' in value:
            if not isinstance(freeze, dict) or set(freeze)-{'at_tick','duration_tick','audio_mode'}:
                _error('EDIT_RETIME_REQUEST_INVALID', 'freeze 字段无效')
            at = _integer(freeze.get('at_tick', self.content), 'transform.freeze.at_tick', 0)
            self.hold = _integer(freeze.get('duration_tick'), 'transform.freeze.duration_tick', 1)
            mode = freeze.get('audio_mode', 'silence')
            if at > self.content or mode not in ('silence','continue'):
                _error('EDIT_RETIME_REQUEST_INVALID', 'freeze 时刻必须位于新内容内，audio_mode 为 silence/continue')
            self.value['freeze'] = {'at_tick': at, 'duration_tick': self.hold, 'audio_mode': mode}
            fps = settings['timebase']['display_fps']
            rate = Fraction(fps['num'], fps['den'])
            frame = max(0, math.ceil(Fraction(at, self.tps)*rate)-1)
            self.anchor = Fraction(frame*self.tps, 1)/rate
        self.output = self.content+self.hold
        if self.output > 2**53-1:
            _error('EDIT_RETIME_CLOCK_RANGE', '定格后长度超出精确整数时钟')

    def point(self, tick):
        if self.segments:
            value = curve_elapsed(self.segments, tick/self.tps)/self.elapsed*self.content
        else:
            value = tick/self.duration*self.content
        if self.value.get('reverse'):
            value = self.content-value
        if self.hold and value > float(self.anchor)+1e-8:
            value += self.hold
        return min(self.output, max(0, round(value)))

    def interval(self, first, last):
        a, b = sorted((self.point(first), self.point(last)))
        if a == b:
            _error('EDIT_RETIME_EMPTY_INTERVAL', '关联选区在整数时钟量化后为空；未丢弃该素材')
        return a, b

    def report(self):
        return {'input_duration_tick': self.duration, 'content_duration_tick': self.content,
                'output_duration_tick': self.output, 'transform': copy.deepcopy(self.value),
                'curve_compilation': getattr(self.segments, 'certificate', {}),
                'freeze_hold_frame_tick': float(self.anchor) if self.anchor is not None else None,
                'interval_clock': 'shared-compiled-host-output-clock-rounded-to-integer-ticks'}
