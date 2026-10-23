"""Continuous basic Y'CbCr tone controls with declared code-value semantics.

The matrix, range, RGB signals and reference code axes are explicit. Pixel
values never pass through an integer image or LUT. ``native_coefficients``
rounds only the legacy filter's scalar coefficients, not the working raster;
it therefore has a declared bounded difference from native integer output.
"""
from dataclasses import dataclass
import math

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba
from .float_curves import signal
from .float_numeric_automation import number, compile_tracks, sample_tracks, raw_tracks, validate_duration
from .float_yuv import COEFFICIENTS

PROTOCOL = 'explicit-YCbCr-author-clock-continuous-float32-basic-tone-v1'
MAX_WORKING_BYTES = 768*1024*1024
ALIASES = {'brightness':'brightness','lightness':'brightness','contrast':'contrast',
    'saturation':'saturation','color':'color','gamma':'gamma','gamma_adjust':'gamma',
    'hue':'hue','hue_rotate':'hue','hsl':'hsl','hsl_adjust':'hsl',
    'grayscale':'grayscale','black_white':'grayscale','blackandwhite':'grayscale'}
SPECS = {'brightness':(0.,-1.,1.),'contrast':(1.,0.,4.),'saturation':(1.,0.,4.),
    'gamma':(1.,.1,10.),'hue':(0.,-360.,360.),'lightness':(0.,-1.,1.),'intensity':(1.,0.,1.)}
CHANNELS = {'brightness':('brightness',),'contrast':('contrast',),'saturation':('saturation',),
    'color':('brightness','contrast','saturation'),'gamma':('gamma',),'hue':('hue',),
    'hsl':('hue','saturation','lightness'),'grayscale':()}


def error(kind,message):return AppError('FLOAT_TONE_'+kind,message,exit_code=2)


def family(name):
    if not isinstance(name,str):raise error('ARGUMENT','基础调色类型须为字符串')
    normalized=name.strip().lower().replace('-','_')
    if normalized not in ALIASES:raise error('ARGUMENT','基础调色类型未知')
    return normalized,ALIASES[normalized]


def schema(kind):
    bounds={n:SPECS[n][1:] for n in (*CHANNELS[kind],'intensity')}
    aliases={}
    if kind in ('brightness','contrast','saturation','gamma'):
        aliases={'amount':kind,'value':kind}
    elif kind in ('hue','hsl'):
        aliases={'degrees':'hue','angle':'hue'}
        if kind=='hue':aliases['value']='hue'
        else:aliases['brightness']='lightness'
    return bounds,aliases


def parameter_names(name):
    _,kind=family(name);bounds,aliases=schema(kind)
    return frozenset(bounds)|frozenset(aliases)


@dataclass(frozen=True)
class TonePlan:
    effect_type:str
    values:tuple
    tracks_json:str
    input_signal:ColorSignal
    output_signal:ColorSignal
    matrix:str
    range:str
    reference_bits:int
    arithmetic:str
    output_gamut:str


def _configuration(kind,incoming,outgoing,matrix,range_value,bits,arithmetic,output):
    if not isinstance(incoming,ColorSignal) or not isinstance(outgoing,ColorSignal):
        raise error('SIGNAL','基础调色须有明确输入输出信号')
    if not isinstance(matrix,str) or matrix not in COEFFICIENTS or range_value not in ('full','limited'):
        raise error('SIGNAL','基础调色须明确受支持的YCbCr矩阵与full/limited量程')
    if type(bits) is not int or bits not in (8,10):raise error('ARGUMENT','参考码值轴仅支持8或10位')
    if arithmetic not in ('continuous','native_coefficients') or output not in ('preserve','clip'):
        raise error('ARGUMENT','基础调色运算或输出色域策略无效')
    if arithmetic=='native_coefficients' and bits!=8 and kind not in ('hue','hsl','grayscale'):
        raise error('ARGUMENT','FFmpeg eq仅有8位原生后端；10位连续扩展不能声称原生系数兼容')


def compile_tone(effect):
    if not isinstance(effect,dict) or set(effect)-{'id','type','enabled','parameters','keyframes'}:
        raise error('ARGUMENT','基础调色含未知字段；参数须置于parameters')
    name,kind=family(effect.get('type'))
    if type(effect.get('enabled',True)) is not bool:raise error('ARGUMENT','enabled须为布尔值')
    p=effect.get('parameters',{});bounds,aliases=schema(kind)
    extra={'input_signal','output_signal','matrix','range','reference_bits','arithmetic','output_gamut','keyframes'}
    if not isinstance(p,dict) or set(p)-(set(bounds)|set(aliases)|extra):raise error('ARGUMENT','基础调色参数未知')
    incoming,outgoing=signal(p.get('input_signal')),signal(p.get('output_signal'))
    matrix,range_value=p.get('matrix'),p.get('range');bits=p.get('reference_bits',8)
    arithmetic,output=p.get('arithmetic','continuous'),p.get('output_gamut','preserve')
    _configuration(kind,incoming,outgoing,matrix,range_value,bits,arithmetic,output)
    values={n:SPECS[n][0] for n in bounds};seen=set()
    for key,value in p.items():
        canonical=aliases.get(key,key)
        if canonical not in bounds:continue
        if canonical in seen:raise error('ARGUMENT','基础调色静态参数重复声明别名')
        seen.add(canonical);values[canonical]=number(value,*bounds[canonical])
    tracks=compile_tracks(raw_tracks(effect,p),bounds,aliases,name)
    return TonePlan(kind,tuple(sorted(values.items())),tracks,incoming,outgoing,matrix,range_value,bits,arithmetic,output)


def state_at(plan,tick):
    if not isinstance(plan,TonePlan) or plan.effect_type not in CHANNELS or not isinstance(plan.values,tuple):
        raise error('ARGUMENT','基础调色须使用完整不可变编译计划')
    _configuration(plan.effect_type,plan.input_signal,plan.output_signal,plan.matrix,plan.range,
        plan.reference_bits,plan.arithmetic,plan.output_gamut)
    bounds,aliases=schema(plan.effect_type);values={}
    for row in plan.values:
        if not isinstance(row,tuple) or len(row)!=2 or row[0] not in bounds or row[0] in values:
            raise error('ARGUMENT','基础调色计划通道无效或重复')
        values[row[0]]=number(row[1],*bounds[row[0]])
    if values.keys()!=bounds.keys():raise error('ARGUMENT','基础调色计划缺少通道')
    values.update(sample_tracks(plan.tracks_json,bounds,aliases,plan.effect_type,tick))
    return values


def validate_tone(effect,*,duration_tick=None):
    if effect.get('enabled',True) is False:return []
    try:
        plan=compile_tone(effect);validate_duration(plan.tracks_json,duration_tick)
    except AppError as exc:return [{'code':exc.code,'message':str(exc),'suffix':'.parameters'}]
    return []


def _axes(plan):
    maximum=(1<<plan.reference_bits)-1;scale=1<<(plan.reference_bits-8)
    return (maximum,16*scale,219*scale,128*scale,224*scale) if plan.range=='limited' else (maximum,0,maximum,128*scale,maximum)


def _to_codes(rgb,plan):
    kr,kb=COEFFICIENTS[plan.matrix];kg=1-kr-kb
    maximum,offset,yrange,center,crange=_axes(plan)
    x=rgb.astype(np.float64);y=kr*x[:,0]+kg*x[:,1]+kb*x[:,2]
    return np.column_stack((y*yrange+offset,(x[:,2]-y)*crange/(2*(1-kb))+center,
        (x[:,0]-y)*crange/(2*(1-kr))+center))


def _from_codes(codes,plan):
    kr,kb=COEFFICIENTS[plan.matrix];kg=1-kr-kb
    maximum,offset,yrange,center,crange=_axes(plan)
    y=(codes[:,0]-offset)/yrange;u=(codes[:,1]-center)/crange;v=(codes[:,2]-center)/crange
    return np.column_stack((y+2*(1-kr)*v,y-2*kb*(1-kb)*u/kg-2*kr*(1-kr)*v/kg,y+2*(1-kb)*u))


def _grade(rgb,plan,values):
    kind=plan.effect_type;maximum,_,_,center,_=_axes(plan)
    codes=_to_codes(rgb,plan);changed=[False,False,False];clipped=0
    quantized=plan.arithmetic=='native_coefficients'
    p={k:float(np.float32(v)) if quantized else v for k,v in values.items()}
    if kind in ('hue','hsl','grayscale'):
        hue=p.get('hue',0.);saturation=0. if kind=='grayscale' else p.get('saturation',1.)
        angle=hue*math.pi/180
        if quantized:angle=float(np.float32(angle))
        sine,cosine=math.sin(angle)*saturation,math.cos(angle)*saturation
        if quantized:sine,cosine=float(np.rint(sine*65536))/65536,float(np.rint(cosine*65536))/65536
        if hue%360!=0 or saturation!=1:
            u,v=codes[:,1]-center,codes[:,2]-center
            codes[:,1]=cosine*u-sine*v+center;codes[:,2]=sine*u+cosine*v+center
            changed[1]=changed[2]=True
        lightness=p.get('lightness',0.)
        if lightness:
            codes[:,0]+=lightness*(25.5 if plan.reference_bits==8 else 102.4);changed[0]=True
    else:
        brightness,contrast,gamma=p.get('brightness',0.),p.get('contrast',1.),p.get('gamma',1.)
        saturation=min(3.,p.get('saturation',1.))
        for plane,c,b,g in ((0,contrast,brightness,gamma),(1,saturation,0.,1.),(2,saturation,0.,1.)):
            if c==1 and b==0 and g==1:continue
            changed[plane]=True
            if quantized and g==1:
                coefficient=math.trunc(c*4096)
                offset=math.trunc(math.trunc(100*b+100)*511/200)-128-math.trunc(coefficient/32)
                codes[:,plane]=codes[:,plane]*coefficient/4096+offset
            else:
                x=c*(codes[:,plane]/maximum-.5)+.5+b
                # Bound the changed plane before fractional gamma. The working
                # RGB can still contain headroom after the inverse matrix.
                clipped+=int(np.count_nonzero((x<0)|(x>1)))
                np.clip(x,0,1,out=x)
                codes[:,plane]=np.power(x,1/g)*maximum
    for plane,active in enumerate(changed):
        if active:
            clipped+=int(np.count_nonzero((codes[:,plane]<0)|(codes[:,plane]>maximum)))
            np.clip(codes[:,plane],0,maximum,out=codes[:,plane])
    if not any(changed):return rgb.astype(np.float64),0,True
    return _from_codes(codes,plan),clipped,False


def apply_tone(surface,plan,author_tick,*,working_signal,tile_pixels=65536,
               retained_table_bytes=0,max_working_bytes=MAX_WORKING_BYTES,cancel=None):
    if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调须可调用')
    def poll():
        if cancel and cancel():raise AppError('RENDER_CANCELLED','浮点基础调色已取消',exit_code=6)
    poll()
    if not isinstance(working_signal,ColorSignal) or working_signal.transfer!='linear':
        raise error('SIGNAL','基础调色须有明确线性工作信号')
    values=state_at(plan,author_tick);strength=values['intensity']
    if not isinstance(surface,np.ndarray) or surface.dtype!=np.float32 or surface.ndim!=3 or surface.shape[-1]!=4 or not surface.flags.c_contiguous:
        raise error('SURFACE','基础调色输入须为连续H×W×4 Float32')
    h,w=surface.shape[:2];pixels=h*w
    if min(h,w)<1 or max(h,w)>16384 or pixels>16777216:raise error('BUDGET','基础调色表面超过尺寸预算')
    if type(tile_pixels) is not int or not 1<=tile_pixels<=262144:raise error('BUDGET','分块大小无效')
    if type(max_working_bytes) is not int or not 1<=max_working_bytes<=MAX_WORKING_BYTES or type(retained_table_bytes) is not int or retained_table_bytes<0:
        raise error('BUDGET','工作区预算无效')
    tile=min(tile_pixels,16384)
    estimate=3*surface.nbytes+retained_table_bytes+min(tile,pixels)*2048+4*len(plan.tracks_json.encode('utf8'))+524288
    if estimate>max_working_bytes:raise error('BUDGET','基础调色表面、保留表及分块工作区估算超限')
    source=surface.reshape(-1,4)
    for start in range(0,pixels,tile):
        poll();part=source[start:start+tile]
        if not np.isfinite(part).all() or np.any(part[:,3]<0) or np.any(part[:,3]>1):
            raise error('VALUES','基础调色RGB须有限且alpha须在0..1')
    output=np.empty_like(source);plane_clips=rgb_clips=0
    for start in range(0,pixels,tile):
        poll();part=source[start:start+tile];target=output[start:start+len(part)];target[:]=part
        if strength==0:continue
        encoded,_=convert_rgba(part.reshape(1,len(part),4),working_signal,plan.input_signal,
            tile_pixels=tile,max_working_bytes=max_working_bytes,cancel=poll)
        rgb=encoded.reshape(-1,4)[:,:3]
        graded,count,identity=_grade(rgb,plan,values);plane_clips+=count
        if plan.output_gamut=='clip':
            clipped=(graded<0)|(graded>1);rgb_clips+=int(np.count_nonzero(clipped))
            identity=identity and not np.any(clipped);np.clip(graded,0,1,out=graded)
        if identity and plan.input_signal==plan.output_signal:continue
        with np.errstate(over='ignore',invalid='ignore'):rgb[:]=graded
        if not np.isfinite(rgb).all():raise error('VALUES','基础调色中间量超出Float32范围')
        converted,_=convert_rgba(encoded,plan.output_signal,working_signal,
            tile_pixels=tile,max_working_bytes=max_working_bytes,cancel=poll)
        graded=converted.reshape(-1,4)[:,:3]
        with np.errstate(over='ignore',invalid='ignore'):
            target[:,:3]=graded if strength==1 else part[:,:3].astype(np.float64)*(1-strength)+graded.astype(np.float64)*strength
        if not np.isfinite(target).all():raise error('VALUES','基础调色输出超出Float32范围')
    poll()
    return output.reshape(surface.shape),{'protocol':PROTOCOL,'author_tick':str(author_tick),'sampled_values':values,
        'input_signal':vars(plan.input_signal),'output_signal':vars(plan.output_signal),'working_signal':vars(working_signal),
        'matrix':plan.matrix,'range':plan.range,'reference_bits':plan.reference_bits,'arithmetic':plan.arithmetic,
        'effective_eq_saturation':min(3.,values.get('saturation',1.)) if plan.effect_type not in ('hue','hsl','grayscale') else None,
        'changed_plane_clipped_components':plane_clips,'output_gamut':plan.output_gamut,'output_clipped_components':rgb_clips,
        'mix_domain':'linear-working-straight-RGB','alpha':'input-bits-preserved','integer_intermediate':False,
        'coefficient_quantization':plan.arithmetic=='native_coefficients','raster_quantization':False,
        'global_HSL_model':'YCbCr-hue-rotation-not-RGB-HSL','hue_lightness_code_scale':25.5 if plan.reference_bits==8 else 102.4,
        'eq_plane_center':'half-code-maximum-not-neutral-chroma','native_integer_output_bit_equivalence':False,
        'ten_bit_eq':'continuous-extension-no-native-eq10-backend',
        'estimated_working_bytes':estimate,'estimated_bytes_are_peak_RSS':False,'actual_tile_pixels_limit':tile,
        'natural_quality_accepted':False,'HDR_accepted':False}
