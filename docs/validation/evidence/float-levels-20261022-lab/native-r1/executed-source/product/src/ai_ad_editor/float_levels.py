"""Independent native-coefficient RGBA levels and animated linear exposure.

No integer lookup table, network service or FFmpeg filter is used at runtime.
The public normalized endpoints and preserve metrics are evaluated on owned
Float32 tiles; automatic endpoints scan the complete incoming surface.
"""
from dataclasses import dataclass
import math

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal,convert_rgba
from .float_curves import signal
from .float_exposure import compile_effects as static_exposure,apply_exposure
from .float_numeric_automation import (number,compile_tracks,sample_tracks,raw_tracks,validate_duration)

PROTOCOL = 'explicit-signal-author-clock-float32-rgba-levels-v1'
EXPOSURE_PROTOCOL = 'author-clock-native-coefficient-float32-exposure-v1'
ALIASES = frozenset(('color_levels','levels','colorlevels'))
CHANNELS = ('red','green','blue','alpha')
ENDPOINTS = ('input_black','input_white','output_black','output_white')
DEFAULTS = dict(zip(ENDPOINTS,(0.,1.,0.,1.)))
BOUNDS = {**{n:(-1.,1.) if n.startswith('input') else (0.,1.) for n in ENDPOINTS},
    **{c+'_'+n:(-1.,1.) if n.startswith('input') else (0.,1.) for c in CHANNELS for n in ENDPOINTS},
    'intensity':(0.,1.)}
# Preserve the pre-existing rimin/rimax/romin/romax shared-RGB author aliases.
# Explicit red_* fields provide independent red endpoints without ambiguity.
PARAMETER_ALIASES = dict(zip(('rimin','rimax','romin','romax'),ENDPOINTS))
PARAMETER_ALIASES.update({prefix+suffix:c+'_'+n for c,prefix in (('green','g'),('blue','b'),('alpha','a'))
    for n,suffix in zip(ENDPOINTS,('imin','imax','omin','omax'))})
PARAMETER_NAMES = frozenset(BOUNDS)|frozenset(PARAMETER_ALIASES)
EXPOSURE_BOUNDS = {'amount':(-3.,3.),'black':(-1.,1.)}
PRESERVE = frozenset(('none','lum','max','avg','sum','nrm','pwr'))
MAX_WORKING_BYTES = 768*1024*1024


def error(kind,message):
    return AppError('FLOAT_LEVELS_'+kind,message,exit_code=2)


def preserve(value):
    text = str(value).strip().lower()
    text = {'false':'none','0':'none','off':'none','':'none','true':'lum','1':'lum'}.get(text,text)
    if text not in PRESERVE: raise error('ARGUMENT','保留模式须为none/lum/max/avg/sum/nrm/pwr')
    return text


@dataclass(frozen=True)
class LevelPlan:
    values: tuple
    tracks_json: str
    input_signal: ColorSignal
    output_signal: ColorSignal
    preserve: str
    zero_span: str


@dataclass(frozen=True)
class ExposureAnimation:
    amount: float
    black: float
    tracks_json: str


def compile_levels(effect):
    if not isinstance(effect,dict) or set(effect)-{'id','type','enabled','parameters','keyframes'}:
        raise error('ARGUMENT','色阶包含未知字段；参数须置于parameters')
    name = str(effect.get('type','')).strip().lower().replace('-','_')
    if name not in ALIASES or type(effect.get('enabled',True)) is not bool: raise error('ARGUMENT','色阶类型或enabled无效')
    p = effect.get('parameters',{})
    if not isinstance(p,dict) or set(p)-(PARAMETER_NAMES|{'input_signal','output_signal','preserve','preserve_color','zero_span','keyframes'}):
        raise error('ARGUMENT','色阶参数包含未知字段')
    incoming,outgoing = signal(p.get('input_signal')),signal(p.get('output_signal'))
    mode = preserve(p.get('preserve',p.get('preserve_color','none')))
    if 'preserve' in p and 'preserve_color' in p and mode!=preserve(p['preserve_color']):
        raise error('ARGUMENT','保留模式别名冲突')
    zero = p.get('zero_span','reject')
    if zero not in ('reject','output_black'): raise error('ARGUMENT','零输入跨度须明确为reject或output_black')
    values = dict(DEFAULTS,intensity=1.)
    authored = {}
    for key,value in p.items():
        prop = PARAMETER_ALIASES.get(key,key)
        if prop not in BOUNDS: continue
        value = number(value,*BOUNDS[prop])
        if prop in authored and authored[prop]!=value: raise error('ARGUMENT','色阶端点别名冲突')
        authored[prop] = value
    values.update(authored)
    tracks = compile_tracks(raw_tracks(effect,p),BOUNDS,PARAMETER_ALIASES,name)
    return LevelPlan(tuple(sorted(values.items())),tracks,incoming,outgoing,mode,zero)


def compile_animated_exposure(effect):
    p = effect.get('parameters',{k:effect[k] for k in ('amount','exposure','black') if k in effect})
    if not isinstance(p,dict): raise error('ARGUMENT','曝光参数须为对象')
    raw = raw_tracks(effect,p)
    base = dict(effect);base.pop('keyframes',None);base['parameters'] = {k:v for k,v in p.items() if k!='keyframes'}
    plan = static_exposure([base])[0]
    tracks = compile_tracks(raw,EXPOSURE_BOUNDS,{'exposure':'amount'},'exposure')
    return ExposureAnimation(plan.amount,plan.black,tracks)


def exposure_at(plan,tick):
    if not isinstance(plan,ExposureAnimation): raise error('ARGUMENT','曝光须使用已编译动态计划')
    values = {'amount':plan.amount,'black':plan.black}
    values.update(sample_tracks(plan.tracks_json,EXPOSURE_BOUNDS,{'exposure':'amount'},'exposure',tick))
    return static_exposure([{'type':'exposure','parameters':values}])[0]


def apply_animated_exposure(surface,plan,tick,**options):
    sampled = exposure_at(plan,tick)
    output,metadata = apply_exposure(surface,(sampled,),**options)
    return output,dict(metadata,protocol=EXPOSURE_PROTOCOL,author_tick=str(tick),
        keyframes_evaluated='original-author-clock-direct-easing',static_protocol=metadata['protocol'])


def validate_native(effect,*,duration_tick=None):
    if effect.get('enabled',True) is False:return []
    try:
        if str(effect.get('type','')).strip().lower().replace('-','_') in ALIASES:
            plan = compile_levels(effect)
        else:
            p = effect.get('parameters',{})
            if 'keyframes' in effect or isinstance(p,dict) and 'keyframes' in p:
                plan = compile_animated_exposure(effect)
            else: static_exposure([effect]);return []
        validate_duration(plan.tracks_json,duration_tick)
    except AppError as exc:return [{'code':exc.code,'message':str(exc),'suffix':'.parameters'}]
    return []


def state_at(plan,tick):
    if not isinstance(plan,LevelPlan) or not isinstance(plan.values,tuple): raise error('ARGUMENT','色阶须使用不可变编译计划')
    if plan.preserve not in PRESERVE or plan.zero_span not in ('reject','output_black'):
        raise error('ARGUMENT','色阶计划模式无效')
    values = {}
    for item in plan.values:
        if not isinstance(item,tuple) or len(item)!=2 or item[0] not in BOUNDS or item[0] in values:
            raise error('ARGUMENT','色阶计划端点无效')
        values[item[0]] = number(item[1],*BOUNDS[item[0]])
    if not set(DEFAULTS)|{'intensity'}<=values.keys(): raise error('ARGUMENT','色阶计划缺少共享端点')
    values.update(sample_tracks(plan.tracks_json,BOUNDS,PARAMETER_ALIASES,'color_levels',tick))
    channels = {c:{n:values.get(c+'_'+n,values[n] if c!='alpha' else DEFAULTS[n]) for n in ENDPOINTS} for c in CHANNELS}
    alpha = any(k.startswith('alpha_') for k in values)
    return channels,values['intensity'],alpha


def metric(rgb,mode):
    r,g,b = rgb[:,0],rgb[:,1],rgb[:,2]
    if mode=='lum': return np.maximum(np.maximum(r,g),b)+np.minimum(np.minimum(r,g),b)
    if mode=='max': return np.maximum(np.maximum(r,g),b)
    total = (r+g)+b
    if mode=='avg': return (total+np.float32(1))/np.float32(3)
    if mode=='sum': return total
    if mode=='nrm': return np.sqrt((r*r+g*g)+b*b)
    return np.cbrt(((r*r)*r+(g*g)*g)+(b*b)*b)


def apply_levels(surface,plan,author_tick,*,working_signal,tile_pixels=65536,
                 retained_table_bytes=0,max_working_bytes=MAX_WORKING_BYTES,cancel=None):
    if cancel is not None and not callable(cancel): raise error('ARGUMENT','取消回调须可调用')
    def poll():
        if cancel and cancel(): raise AppError('RENDER_CANCELLED','浮点色阶已取消',exit_code=6)
    poll()
    if not isinstance(working_signal,ColorSignal) or working_signal.transfer!='linear':
        raise error('SIGNAL','色阶须使用明确线性工作信号')
    channels,strength,alpha = state_at(plan,author_tick)
    if not isinstance(plan.input_signal,ColorSignal) or not isinstance(plan.output_signal,ColorSignal):
        raise error('SIGNAL','色阶计划须提供明确输入输出信号')
    if not isinstance(surface,np.ndarray) or surface.dtype!=np.float32 or surface.ndim!=3 or surface.shape[-1]!=4 or not surface.flags.c_contiguous:
        raise error('SURFACE','色阶输入须为连续H×W×4 Float32')
    h,w = surface.shape[:2];pixels = h*w
    if min(h,w)<1 or max(h,w)>16384 or pixels>16777216: raise error('BUDGET','色阶表面超过尺寸预算')
    if type(tile_pixels) is not int or not 1<=tile_pixels<=262144: raise error('BUDGET','色阶分块大小无效')
    if type(max_working_bytes) is not int or not 1<=max_working_bytes<=MAX_WORKING_BYTES or type(retained_table_bytes) is not int or retained_table_bytes<0:
        raise error('BUDGET','色阶工作区预算无效')
    actual_tile = min(tile_pixels,16384)
    estimate = 3*surface.nbytes+retained_table_bytes+min(pixels,actual_tile)*2048+4*len(plan.tracks_json.encode('utf8'))+524288
    if estimate>max_working_bytes: raise error('BUDGET','色阶输入/输出、保留LUT和分块工作区估算超限')
    source = surface.reshape(-1,4)
    active = list(CHANNELS if alpha else CHANNELS[:3])
    endpoints = {c:{n:np.float32(v) for n,v in channels[c].items()} for c in active}
    automatic = {c:[n for n in ENDPOINTS[:2] if endpoints[c][n]<0] for c in active}
    extrema = {c:{'input_black':np.float32(1),'input_white':np.float32(0)} for c in active}
    need_auto = strength!=0 and any(automatic.values())
    # Whole-surface validation also precedes identity/intensity-zero returns.
    for start in range(0,pixels,actual_tile):
        poll();value = source[start:start+actual_tile]
        if not np.isfinite(value).all() or np.any(value[:,3]<0) or np.any(value[:,3]>1):
            raise error('VALUES','色阶RGB须有限且alpha须在0..1')
        if need_auto:
            encoded,_ = convert_rgba(value.reshape(1,len(value),4),working_signal,plan.input_signal,
                tile_pixels=actual_tile,max_working_bytes=max_working_bytes,cancel=cancel)
            for c in active:
                i = CHANNELS.index(c)
                for n in automatic[c]:
                    extrema[c][n] = np.minimum(extrema[c][n],encoded[...,i].min()) if n=='input_black' else np.maximum(extrema[c][n],encoded[...,i].max())
    coeffs = {}
    for c in active:
        e = endpoints[c]
        for n in automatic[c]:
            if need_auto:e[n] = extrema[c][n]
        if strength==0:continue
        denominator = np.float32(e['input_white']-e['input_black'])
        if denominator==0:
            if plan.zero_span=='reject':raise error('ZERO_SPAN','色阶输入黑白点重合；可显式选择output_black平坦画面策略')
            coefficient = np.float32(0)
        else:
            with np.errstate(over='ignore',invalid='ignore'):
                coefficient = np.float32(float(np.float32(e['output_white']-e['output_black']))/float(denominator))
            if not np.isfinite(coefficient):raise error('VALUES','色阶端点系数超出Float32有限范围')
        coeffs[c] = coefficient
    output = np.empty_like(source)
    for start in range(0,pixels,actual_tile):
        poll();value = source[start:start+actual_tile];target = output[start:start+len(value)];target[:] = value
        if strength==0:continue
        encoded,_ = convert_rgba(value.reshape(1,len(value),4),working_signal,plan.input_signal,
            tile_pixels=actual_tile,max_working_bytes=max_working_bytes,cancel=cancel)
        flat = encoded.reshape(-1,4);original = flat[:,:3].copy()
        with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
            for c in active:
                i = CHANNELS.index(c);e = endpoints[c]
                flat[:,i] = (flat[:,i]-e['input_black'])*coeffs[c]+e['output_black']
            if plan.preserve!='none':
                before,after = metric(original,plan.preserve),metric(flat[:,:3],plan.preserve)
                ratio = np.ones_like(after);np.divide(before,after,out=ratio,where=after>0)
                flat[:,:3] *= ratio[:,None]
        if not np.isfinite(flat).all():raise error('VALUES','色阶输出超出Float32有限范围')
        # Alpha is coverage, independent from the RGB transfer conversion. Keep
        # original alpha in convert_rgba and apply the explicit endpoint result
        # afterwards; a partial-intensity blend may rescue an out-of-range map.
        mapped_alpha = flat[:,3].copy() if alpha else None
        flat[:,3] = value[:,3]
        graded,_ = convert_rgba(encoded,plan.output_signal,working_signal,
            tile_pixels=actual_tile,max_working_bytes=max_working_bytes,cancel=cancel)
        rgb = graded.reshape(-1,4)[:,:3]
        with np.errstate(over='ignore',invalid='ignore'):
            target[:,:3] = rgb if strength==1 else value[:,:3].astype(np.float64)*(1-strength)+rgb.astype(np.float64)*strength
            if alpha:target[:,3] = mapped_alpha if strength==1 else value[:,3].astype(np.float64)*(1-strength)+mapped_alpha.astype(np.float64)*strength
        if not np.isfinite(target).all() or np.any(target[:,3]<0) or np.any(target[:,3]>1):
            raise error('VALUES','色阶结果RGB须有限且alpha须在0..1；不会静默裁切覆盖率')
    poll()
    return output.reshape(surface.shape),{'protocol':PROTOCOL,'author_tick':str(author_tick),'intensity':strength,
        'preserve':plan.preserve,'zero_span':plan.zero_span,'sampled_channels':channels,
        'effective_endpoints':{c:{n:float(v) for n,v in e.items()} for c,e in endpoints.items()},
        'coefficients':{c:float(v) for c,v in coeffs.items()},'automatic_endpoints':automatic,
        'auto_scope':'complete-incoming-surface-including-hidden-RGB','auto_min_seed':1,'auto_max_seed':0,
        'input_signal':vars(plan.input_signal),'output_signal':vars(plan.output_signal),'working_signal':vars(working_signal),
        'mix_domain':'linear-working-straight-RGB-and-explicit-alpha','RGB_clipping':'none',
        'alpha':'explicit-endpoint-map-otherwise-input-bits-preserved' if alpha else 'input-bits-preserved',
        'integer_intermediate':False,'estimated_working_bytes':estimate,'estimated_bytes_are_peak_RSS':False,
        'actual_tile_pixels_limit':actual_tile,'natural_quality_accepted':False,'HDR_accepted':False}
