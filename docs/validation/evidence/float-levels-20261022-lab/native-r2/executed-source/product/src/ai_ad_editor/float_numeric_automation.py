"""Bounded immutable numeric author channels for native Float32 operators."""
from fractions import Fraction
import json
import math
from numbers import Integral,Real

from .errors import AppError
from .float_curves import author_value

MAX_KEYS = 16384
MAX_BYTES = 4*1024*1024


def error(message):
    return AppError('FLOAT_NUMERIC_AUTOMATION_ARGUMENT',message,exit_code=2)


def number(value, low=None, high=None):
    if type(value) not in (int,float):
        raise error('作者数值须为有限JSON数字')
    try: result = float(value)
    except (OverflowError,ValueError): raise error('作者数值超出有限范围')
    if not math.isfinite(result) or (low is not None and result<low) or (high is not None and result>high):
        raise error('作者数值超出声明范围')
    return result


def compile_tracks(raw, bounds, aliases, effect_name):
    if not isinstance(raw,list) or len(raw)>len(bounds):
        raise error('数值轨道数量超过可执行通道数量')
    tracks,seen,total = [],set(),0
    for track in raw:
        if not isinstance(track,dict) or set(track)!={'property','keyframes'} or not isinstance(track['property'],str):
            raise error('数值轨道格式无效')
        prop = track['property'].strip().lower().replace('-','_')
        for prefix in ('effect.','parameters.',effect_name+'.'):
            if prop.startswith(prefix): prop = prop[len(prefix):]; break
        prop = aliases.get(prop,prop)
        if prop not in bounds or prop in seen: raise error('数值通道未知或重复声明别名')
        seen.add(prop)
        keys = track['keyframes']
        if not isinstance(keys,list) or not 1<=len(keys)<=1024: raise error('每轨道须有1到1024个关键帧')
        total += len(keys)
        if total>MAX_KEYS: raise error('数值关键帧总数超过16384')
        previous = -1
        for key in keys:
            if not isinstance(key,dict) or set(key)-{'at_tick','value','interpolation','control_points'}:
                raise error('数值关键帧含未知字段')
            if type(key.get('at_tick')) is not int or key['at_tick']<=previous:
                raise error('关键帧时钟须为严格递增非负整数')
            previous = key['at_tick'];number(key.get('value'),*bounds[prop])
            mode = key.get('interpolation','linear')
            if mode not in ('linear','hold','ease_in','ease_out','ease_in_out','bezier'):
                raise error('关键帧时间插值未知')
            if mode=='bezier':
                cp = key.get('control_points')
                if not isinstance(cp,list) or len(cp) not in (2,4): raise error('Bezier须提供2或4个控制值')
                cp = [number(v) for v in cp]
                if len(cp)==4 and not (0<=cp[0]<=1 and 0<=cp[2]<=1): raise error('Bezier横向控制值须在0..1')
        tracks.append({'property':prop,'keyframes':keys})
    result = json.dumps(tracks,sort_keys=True,allow_nan=False,separators=(',',':'))
    if len(result.encode('utf8'))>MAX_BYTES: raise error('关键帧序列化预算超限')
    return result


def sample_tracks(serialized, bounds, aliases, effect_name, tick):
    if isinstance(tick,Fraction):
        if tick<0: raise error('作者时钟须非负')
    elif isinstance(tick,Integral) and not isinstance(tick,bool):
        if tick<0: raise error('作者时钟须非负')
        tick = int(tick)
    elif isinstance(tick,Real) and not isinstance(tick,bool):
        tick = number(float(tick),0)
    else: raise error('作者时钟须为非负有限实数或有理数')
    if not isinstance(serialized,str) or len(serialized)>MAX_BYTES: raise error('数值计划关键帧无效')
    try: tracks = json.loads(serialized)
    except (ValueError,TypeError,RecursionError) as caught: raise error('数值计划关键帧无效') from caught
    if compile_tracks(tracks,bounds,aliases,effect_name)!=serialized: raise error('数值计划关键帧不是规范不可变形式')
    return {t['property']:min(bounds[t['property']][1],max(bounds[t['property']][0],
        number(author_value(t['keyframes'],tick)))) for t in tracks}


def raw_tracks(effect, parameters):
    if 'keyframes' in effect and 'keyframes' in parameters: raise error('关键帧只能声明在一个层级')
    return effect.get('keyframes',parameters.get('keyframes',[]))


def validate_duration(serialized,duration_tick):
    if duration_tick is not None and any(k['at_tick']>duration_tick for t in json.loads(serialized) for k in t['keyframes']):
        raise error('关键帧超过原作者时长')
