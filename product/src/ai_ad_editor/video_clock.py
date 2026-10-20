"""A bounded rational working clock for video PTS before CFR sampling.

The working grid represents original stream timestamps, author tick offsets
and the output frame grid exactly. It does not normalize a VFR input or pad
missing frames. Arbitrary nonlinear expressions retain an explicit sub-tick
resolution; derived clocks never rewrite the author project.
"""
from __future__ import annotations

from fractions import Fraction
import math

from .errors import AppError

MAX_DENOMINATOR = 2**31-1
PROTOCOL = 'rational-local-video-clock-v1'


def _positive_rational(value):
    if not isinstance(value, str) or len(value)>64:
        raise ValueError('time base is not a bounded rational string')
    result=Fraction(value)
    if result<=0 or result.numerator>MAX_DENOMINATOR or result.denominator>MAX_DENOMINATOR:
        raise ValueError('time base is outside native AVRational limits')
    return result


def registered_time_base(asset, path, *, normalized_rate=None):
    if normalized_rate is not None:
        return 1/Fraction(normalized_rate), 'compiler-CFR-surface'
    probe=asset.get('probe') if isinstance(asset.get('probe'),dict) else {}
    streams=probe.get('streams') if isinstance(probe.get('streams'),list) else []
    stream=next((s for s in streams if isinstance(s,dict) and s.get('codec_type')=='video'),{})
    try:
        return _positive_rational(stream.get('time_base')), 'registered-native-stream'
    except (ValueError,ZeroDivisionError):
        # Older or externally constructed projects may lack the full native
        # stream metadata. Probe the actual local input rather than guessing.
        from .media import probe_media
        actual=probe_media(path)
        stream=next((s for s in actual.get('streams',[]) if s.get('codec_type')=='video'),{})
        try:
            return _positive_rational(stream.get('time_base')), 'local-native-probe'
        except (ValueError,ZeroDivisionError) as error:
            raise AppError('VIDEO_CLOCK_TIMEBASE_INVALID','本地视频流缺少可用的正有理数时间基',exit_code=3,path=str(path),cause=str(error)) from error


def working_clock(input_base, fps, tps):
    rate=Fraction(fps);base=Fraction(input_base)
    if base<=0 or rate<=0 or isinstance(tps,bool) or not isinstance(tps,int) or tps<=0:
        raise AppError('VIDEO_CLOCK_TIMEBASE_INVALID','视频工作时钟需要正的时间基、帧率与作者 TPS',exit_code=2)
    denominator=math.lcm(base.denominator,tps,rate.numerator)
    if denominator>MAX_DENOMINATOR:
        raise AppError('VIDEO_CLOCK_TIMEBASE_UNREPRESENTABLE','输入 PTS、作者 tick 与 CFR 格点的共同时间基超出本机 AVRational 分母范围',exit_code=6,
                       cause=f'input={base}; fps={rate}; tps={tps}; required_denominator={denominator}')
    # A multiple of the exact common grid also reduces rounding in nonlinear
    # setpts expressions. This is bounded by the native rational denominator.
    denominator*=MAX_DENOMINATOR//denominator
    value=Fraction(1,denominator)
    return 'settb=expr=1/'+str(denominator), {
        'protocol':PROTOCOL,'input_time_base':str(base),'working_time_base':str(value),
        'fps':str(rate),'ticks_per_second':tps,'input_pts_and_author_offsets_exact':True,
        'nonlinear_retime_resolution_seconds':str(value),'input_VFR_normalized':False,
        'native_denominator_limit':MAX_DENOMINATOR}


def frame_interval(start_tick,duration_tick,tps,fps):
    rate=Fraction(fps)
    first=math.ceil(Fraction(start_tick,tps)*rate)
    stop=math.ceil(Fraction(start_tick+duration_tick,tps)*rate)
    return first,max(first,stop)
