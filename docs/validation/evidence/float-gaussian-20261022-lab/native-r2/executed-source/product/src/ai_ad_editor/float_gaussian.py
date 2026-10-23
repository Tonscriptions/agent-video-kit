"""Continuous normalized recursive Gaussian on the original author clock.

The recurrence uses bounded convex sweeps rather than an unnormalized image
and one final tiny scale. See float_gaussian_NOTICE.txt for the numerical
reference and attribution. No integer raster, table or per-frame subprocess
is used. The caller declares RGB signals and straight/premultiplied handling.
"""
from dataclasses import dataclass
import json
import math

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal,convert_rgba
from .float_curves import signal
from .float_numeric_automation import number,compile_tracks,sample_tracks,raw_tracks,validate_duration

PROTOCOL='explicit-signal-author-clock-normalized-float32-Gaussian-v1'
ALIASES=frozenset(('blur','gaussian_blur','gblur'))
BOUNDS={'radius':(0.,128.),'radius_x':(0.,128.),'radius_y':(0.,128.),'intensity':(0.,1.)}
PARAMETER_ALIASES={'sigma':'radius','sigma_x':'radius_x','sigma_y':'radius_y','sigmaV':'radius_y','sigmav':'radius_y'}
MAX_WORKING_BYTES=768*1024*1024


def error(kind,message):return AppError('FLOAT_GAUSSIAN_'+kind,message,exit_code=2)


@dataclass(frozen=True)
class GaussianPlan:
    values:tuple
    tracks_json:str
    axis_overrides:tuple
    input_signal:ColorSignal
    output_signal:ColorSignal
    steps:int
    planes:int
    alpha_mode:str
    output_gamut:str


def _configuration(plan):
    if not isinstance(plan.input_signal,ColorSignal) or not isinstance(plan.output_signal,ColorSignal):
        raise error('SIGNAL','高斯模糊须明确输入输出RGB信号')
    if type(plan.steps) is not int or not 1<=plan.steps<=6 or type(plan.planes) is not int or not 0<=plan.planes<=15:
        raise error('ARGUMENT','steps须为1..6整数，planes须为0..15整数')
    if plan.alpha_mode not in ('straight','premultiplied') or plan.output_gamut not in ('preserve','clip'):
        raise error('ARGUMENT','高斯模糊透明度或输出色域策略无效')
    if plan.alpha_mode=='premultiplied' and plan.planes!=15:
        raise error('ARGUMENT','预乘模糊须同时处理RGB和alpha全部四平面')
    if not isinstance(plan.axis_overrides,tuple) or any(n not in ('radius_x','radius_y') for n in plan.axis_overrides) or tuple(sorted(set(plan.axis_overrides)))!=plan.axis_overrides:
        raise error('ARGUMENT','高斯模糊轴覆盖计划无效')


def parameter_names():return frozenset(BOUNDS)|frozenset(PARAMETER_ALIASES)


def compile_gaussian(effect):
    if not isinstance(effect,dict) or set(effect)-{'id','type','enabled','parameters','keyframes'}:
        raise error('ARGUMENT','高斯模糊含未知字段；参数须置于parameters')
    name=str(effect.get('type','')).strip().lower().replace('-','_')
    if name not in ALIASES or type(effect.get('enabled',True)) is not bool:raise error('ARGUMENT','高斯模糊类型或enabled无效')
    p=effect.get('parameters',{})
    extras={'input_signal','output_signal','steps','planes','alpha_mode','output_gamut','keyframes'}
    if not isinstance(p,dict) or set(p)-(set(BOUNDS)|set(PARAMETER_ALIASES)|extras):raise error('ARGUMENT','高斯模糊参数未知')
    incoming,outgoing=signal(p.get('input_signal')),signal(p.get('output_signal'))
    values={'radius':4.,'radius_x':4.,'radius_y':4.,'intensity':1.};seen=set()
    for name,value in p.items():
        canonical=PARAMETER_ALIASES.get(name,name)
        if canonical not in BOUNDS:continue
        if canonical in seen:raise error('ARGUMENT','高斯模糊静态通道重复声明别名')
        seen.add(canonical);values[canonical]=number(value,*BOUNDS[canonical])
    tracks=compile_tracks(raw_tracks(effect,p),BOUNDS,PARAMETER_ALIASES,str(effect['type']).strip().lower().replace('-','_'))
    overridden=(seen|{t['property'] for t in json.loads(tracks)}) & {'radius_x','radius_y'}
    plan=GaussianPlan(tuple(sorted(values.items())),tracks,tuple(sorted(overridden)),incoming,outgoing,
        p.get('steps',1),p.get('planes',15),p.get('alpha_mode','straight'),p.get('output_gamut','preserve'))
    _configuration(plan)
    return plan


def state_at(plan,tick):
    if not isinstance(plan,GaussianPlan) or not isinstance(plan.values,tuple):raise error('ARGUMENT','须使用不可变高斯模糊计划')
    _configuration(plan);values={}
    for row in plan.values:
        if not isinstance(row,tuple) or len(row)!=2 or row[0] not in BOUNDS or row[0] in values:
            raise error('ARGUMENT','高斯模糊计划参数无效或重复')
        values[row[0]]=number(row[1],*BOUNDS[row[0]])
    if values.keys()!=BOUNDS.keys():raise error('ARGUMENT','高斯模糊计划缺少通道')
    values.update(sample_tracks(plan.tracks_json,BOUNDS,PARAMETER_ALIASES,'blur',tick))
    for axis in ('radius_x','radius_y'):
        if axis not in plan.axis_overrides:values[axis]=values['radius']
    return values


def validate_gaussian(effect,*,duration_tick=None):
    if effect.get('enabled',True) is False:return []
    try:
        plan=compile_gaussian(effect);validate_duration(plan.tracks_json,duration_tick)
    except AppError as exc:return [{'code':exc.code,'message':str(exc),'suffix':'.parameters'}]
    return []


def _sweep(values,axis,radius,steps,poll):
    if radius==0:return
    variance=radius*radius/(2*steps)
    # Rationalized small-root expression avoids cancellation near zero.
    q=2*variance/(1+2*variance+math.sqrt(1+4*variance));a=1-q
    view=np.moveaxis(values,axis,0);length=view.shape[0]
    for _ in range(steps):
        poll()
        for index in range(1,length):
            if index%32==0:poll()
            view[index]=a*view[index]+q*view[index-1]
        for index in range(length-2,-1,-1):
            if index%32==0:poll()
            view[index]=a*view[index]+q*view[index+1]


def apply_gaussian(surface,plan,author_tick,*,working_signal,tile_pixels=65536,
                   retained_table_bytes=0,max_working_bytes=MAX_WORKING_BYTES,cancel=None):
    if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调须可调用')
    def poll():
        if cancel and cancel():raise AppError('RENDER_CANCELLED','浮点高斯模糊已取消',exit_code=6)
    poll();values=state_at(plan,author_tick);strength=values['intensity']
    if not isinstance(working_signal,ColorSignal) or working_signal.transfer!='linear':
        raise error('SIGNAL','高斯模糊须使用明确线性工作信号')
    if not isinstance(surface,np.ndarray) or surface.dtype!=np.float32 or surface.ndim!=3 or surface.shape[-1]!=4 or not surface.flags.c_contiguous:
        raise error('SURFACE','高斯模糊输入须为连续H×W×4 Float32')
    h,w=surface.shape[:2];pixels=h*w
    if min(h,w)<1 or max(h,w)>16384 or pixels>16777216:raise error('BUDGET','高斯模糊表面超过尺寸预算')
    if type(tile_pixels) is not int or not 1<=tile_pixels<=262144:raise error('BUDGET','分块大小无效')
    if type(max_working_bytes) is not int or not 1<=max_working_bytes<=MAX_WORKING_BYTES or type(retained_table_bytes) is not int or retained_table_bytes<0:
        raise error('BUDGET','工作区预算无效')
    tile=min(tile_pixels,16384)
    estimate=6*surface.nbytes+retained_table_bytes+min(tile,pixels)*2048+4*len(plan.tracks_json.encode('utf8'))+1048576
    if estimate>max_working_bytes:raise error('BUDGET','高斯模糊表面、递推工作区及保留表估算超限')
    source=surface.reshape(-1,4)
    for start in range(0,pixels,tile):
        poll();part=source[start:start+tile]
        if not np.isfinite(part).all() or np.any(part[:,3]<0) or np.any(part[:,3]>1):raise error('VALUES','RGB须有限且alpha须在0..1')
    channels=tuple(i for i,bit in enumerate((4,1,2,8)) if plan.planes&bit)
    active=bool(channels) and (values['radius_x']!=0 or values['radius_y']!=0) and strength!=0
    no_RGB_conversion=not any(i<3 for i in channels) and plan.input_signal==plan.output_signal and plan.output_gamut=='preserve'
    clips=zero_coverage=0
    if strength==0 or not active and plan.input_signal==plan.output_signal and plan.output_gamut=='preserve':
        result=surface.copy()
    else:
        if no_RGB_conversion:encoded=surface.copy()
        else:encoded,_=convert_rgba(surface,working_signal,plan.input_signal,tile_pixels=tile,max_working_bytes=max_working_bytes,cancel=poll)
        if active:
            work=np.take(encoded,channels,axis=2).astype(np.float64)
            if plan.alpha_mode=='premultiplied':work[...,:3]*=work[...,3:4]
            _sweep(work,1,values['radius_x'],plan.steps,poll)
            _sweep(work,0,values['radius_y'],plan.steps,poll)
            if plan.alpha_mode=='premultiplied':
                density=work[...,3:4];positive=density>0
                np.divide(work[...,:3],density,out=work[...,:3],where=positive)
                work[...,:3][~positive[...,0]]=0
                zero_coverage=int(np.count_nonzero(~positive))
            flat=work.reshape(-1,len(channels));target=encoded.reshape(-1,4)
            for start in range(0,pixels,tile):
                poll();part=flat[start:start+tile]
                with np.errstate(over='ignore',invalid='ignore'):target[start:start+len(part),channels]=part
            del work
        flat=encoded.reshape(-1,4)
        for start in range(0,pixels,tile):
            poll();part=flat[start:start+tile]
            if not np.isfinite(part).all():raise error('VALUES','高斯模糊中间值超出Float32范围')
            if active and 3 in channels:np.clip(part[:,3],0,1,out=part[:,3])
            if plan.output_gamut=='clip':
                clips+=int(np.count_nonzero((part[:,:3]<0)|(part[:,:3]>1)))
                np.clip(part[:,:3],0,1,out=part[:,:3])
        if no_RGB_conversion:graded=encoded
        else:graded,_=convert_rgba(encoded,plan.output_signal,working_signal,tile_pixels=tile,max_working_bytes=max_working_bytes,cancel=poll)
        result=np.empty_like(surface);target=result.reshape(-1,4);flat=graded.reshape(-1,4)
        for start in range(0,pixels,tile):
            poll();part=source[start:start+tile];value=flat[start:start+tile];out=target[start:start+len(part)]
            with np.errstate(over='ignore',invalid='ignore'):
                out[:]=value if strength==1 else part.astype(np.float64)*(1-strength)+value.astype(np.float64)*strength
            if not active or 3 not in channels:out[:,3]=part[:,3]
            if no_RGB_conversion:out[:,:3]=part[:,:3]
            if not np.isfinite(out).all() or np.any(out[:,3]<0) or np.any(out[:,3]>1):raise error('VALUES','高斯模糊输出超出有限值或alpha范围')
    poll()
    return result,{'protocol':PROTOCOL,'author_tick':str(author_tick),'sampled_values':values,
        'input_signal':vars(plan.input_signal),'output_signal':vars(plan.output_signal),'working_signal':vars(working_signal),
        'steps':plan.steps,'planes_GBRA_bits':plan.planes,'selected_RGBA_indices':list(channels),'alpha_mode':plan.alpha_mode,
        'alpha':'explicit-Gaussian-coverage-mapping' if active and 3 in channels else 'input-bits-preserved',
        'zero_blurred_coverage_pixels':zero_coverage,'alpha_only_RGB_conversion_bypassed':no_RGB_conversion,
        'output_gamut':plan.output_gamut,'output_clipped_components':clips,'integer_intermediate':False,
        'raster_dtype':'float32','recurrence_scratch_dtype':'float64','recurrence':'normalized-convex-forward-backward-IIR',
        'boundary':'endpoint-extended-forward-and-backward-recursive-state','RGB_mix_domain':'linear-working-straight-RGB',
        'alpha_mix':'linear-coverage','estimated_working_bytes':estimate,'estimated_bytes_are_peak_RSS':False,
        'actual_tile_pixels_limit':tile,'native_bit_equivalence':False,'natural_quality_accepted':False,'HDR_accepted':False}
