"""Continuous eight-band HSL with explicit signals, gamut policy and author time.

The bounded HSL operator extends the existing eight-bit band semantics without
an integer raster or LUT. Original hue supplies all triangular band weights.
Negative/superwhite RGB requires a declared policy; residual preservation is a
creative extension, not an HDR appearance model. Alpha never enters HSL math.
"""
from dataclasses import dataclass

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba
from .float_curves import signal
from .float_numeric_automation import number, compile_tracks, sample_tracks, raw_tracks, validate_duration
from .selective_hsl import ALIASES, BANDS, SPECS

PROTOCOL = 'explicit-signal-author-clock-continuous-float32-eight-band-hsl-v1'
BOUNDS = {name: (spec[2], spec[3]) for name, spec in SPECS.items()}
MAX_WORKING_BYTES = 768*1024*1024


def error(kind, message):
    return AppError('FLOAT_SELECTIVE_HSL_'+kind, message, exit_code=2)


@dataclass(frozen=True)
class SelectiveHSLPlan:
    values: tuple
    tracks_json: str
    input_signal: ColorSignal
    output_signal: ColorSignal
    input_gamut: str
    output_gamut: str


def compile_hsl(effect):
    if not isinstance(effect, dict) or set(effect)-{'id','type','enabled','parameters','keyframes'}:
        raise error('ARGUMENT','分色HSL含未知字段；参数须置于parameters')
    name=str(effect.get('type','')).strip().lower().replace('-','_')
    if name not in ALIASES or type(effect.get('enabled',True)) is not bool:
        raise error('ARGUMENT','分色HSL类型或enabled无效')
    p=effect.get('parameters',{})
    extra={'input_signal','output_signal','input_gamut','output_gamut','keyframes'}
    if not isinstance(p,dict) or set(p)-(set(BOUNDS)|extra):
        raise error('ARGUMENT','分色HSL参数含未知字段')
    incoming,outgoing=signal(p.get('input_signal')),signal(p.get('output_signal'))
    policy=p.get('input_gamut','reject');output=p.get('output_gamut','preserve')
    if not isinstance(policy,str) or policy not in ('reject','clip','preserve_residual'):
        raise error('ARGUMENT','分色HSL输入色域策略须为reject/clip/preserve_residual')
    if not isinstance(output,str) or output not in ('preserve','clip'):
        raise error('ARGUMENT','分色HSL输出色域策略须为preserve/clip')
    values={n:number(p.get(n,s[1]),*BOUNDS[n]) for n,s in SPECS.items()}
    tracks=compile_tracks(raw_tracks(effect,p),BOUNDS,{},name)
    return SelectiveHSLPlan(tuple(sorted(values.items())),tracks,incoming,outgoing,policy,output)


def state_at(plan,tick):
    if not isinstance(plan,SelectiveHSLPlan) or not isinstance(plan.values,tuple):
        raise error('ARGUMENT','分色HSL须使用不可变编译计划')
    if not isinstance(plan.input_signal,ColorSignal) or not isinstance(plan.output_signal,ColorSignal):
        raise error('SIGNAL','分色HSL计划须有明确输入输出信号')
    if plan.input_gamut not in ('reject','clip','preserve_residual') or plan.output_gamut not in ('preserve','clip'):
        raise error('ARGUMENT','分色HSL计划的色域策略无效')
    values={}
    for item in plan.values:
        if not isinstance(item,tuple) or len(item)!=2 or item[0] not in BOUNDS or item[0] in values:
            raise error('ARGUMENT','分色HSL计划参数无效或重复')
        values[item[0]]=number(item[1],*BOUNDS[item[0]])
    if values.keys()!=BOUNDS.keys():raise error('ARGUMENT','分色HSL计划缺少参数')
    values.update(sample_tracks(plan.tracks_json,BOUNDS,{},'selective_hsl',tick))
    return values


def validate_hsl(effect,*,duration_tick=None):
    if effect.get('enabled',True) is False:return []
    try:
        plan=compile_hsl(effect);validate_duration(plan.tracks_json,duration_tick)
    except AppError as exc:return [{'code':exc.code,'message':str(exc),'suffix':'.parameters'}]
    return []


def _grade(base,values):
    """Bounded RGB -> original HSL -> simultaneous bands -> bounded RGB.

    Binary64 scratch avoids cancellation for very small Float32 chroma. The
    persistent working raster and result remain Float32; no integer rounding
    or epsilon floor erases near-black chroma.
    """
    rgb=base.astype(np.float64)
    maximum,minimum=rgb.max(axis=1),rgb.min(axis=1)
    delta=maximum-minimum;level=(maximum+minimum)*.5;active=delta>0
    hue=np.zeros_like(level);saturation=np.zeros_like(level)
    denominator=np.where(level<=.5,maximum+minimum,2-maximum-minimum)
    np.divide(delta,denominator,out=saturation,where=active & (denominator>0))
    red=active & (maximum==rgb[:,0])
    green=active & ~red & (maximum==rgb[:,1]);blue=active & ~red & ~green
    hue[red]=60*np.remainder((rgb[red,1]-rgb[red,2])/delta[red],6)
    hue[green]=60*((rgb[green,2]-rgb[green,0])/delta[green]+2)
    hue[blue]=60*((rgb[blue,0]-rgb[blue,1])/delta[blue]+4)
    shifts=np.zeros((len(rgb),3),np.float64)
    centers=list(BANDS.values());names=list(BANDS)
    for i,band in enumerate(names):
        controls=[values[band+'_'+axis] for axis in ('hue','saturation','lightness')]
        if not any(controls):continue
        center=centers[i];left=(center-centers[i-1])%360;right=(centers[(i+1)%len(centers)]-center)%360
        distance=np.remainder(hue-center,360)
        weight=np.where(distance<=right,1-distance/right,
            np.where(distance>=360-left,(distance-(360-left))/left,0))
        weight[~active]=0
        shifts+=weight[:,None]*np.asarray(controls,np.float64)
    changed=np.any(shifts!=0,axis=1)
    hue=np.remainder(hue+shifts[:,0],360)/60
    saturation=np.clip(np.where(shifts[:,1]>=0,saturation+(1-saturation)*shifts[:,1],
        saturation*(1+shifts[:,1])),0,1)
    level=np.clip(np.where(shifts[:,2]>=0,level+(1-level)*shifts[:,2],level*(1+shifts[:,2])),0,1)
    chroma=2*np.minimum(level,1-level)*saturation
    secondary=chroma*(1-np.abs(np.remainder(hue,2)-1));offset=level-chroma*.5
    result=np.empty_like(rgb)
    result[:,0]=np.select((hue<1,hue<2,hue<4,hue<5),(chroma,secondary,0,secondary),default=chroma)
    result[:,1]=np.select((hue<1,hue<3,hue<4),(secondary,chroma,secondary),default=0)
    result[:,2]=np.select((hue<2,hue<3,hue<5),(0,secondary,chroma),default=secondary)
    result+=offset[:,None]
    # Exact unselected/achromatic identity also avoids near-black cancellation
    # in the HSL reconstruction; selected pixels retain continuous values.
    result[~changed]=rgb[~changed]
    return result,changed


def apply_hsl(surface,plan,author_tick,*,working_signal,tile_pixels=65536,
              retained_table_bytes=0,max_working_bytes=MAX_WORKING_BYTES,cancel=None):
    if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调须可调用')
    def poll():
        if cancel and cancel():raise AppError('RENDER_CANCELLED','浮点分色HSL已取消',exit_code=6)
    poll()
    if not isinstance(working_signal,ColorSignal) or working_signal.transfer!='linear':
        raise error('SIGNAL','浮点分色HSL须使用明确线性工作信号')
    values=state_at(plan,author_tick);strength=values['intensity']
    if not isinstance(surface,np.ndarray) or surface.dtype!=np.float32 or surface.ndim!=3 or surface.shape[-1]!=4 or not surface.flags.c_contiguous:
        raise error('SURFACE','分色HSL输入须为连续H×W×4 Float32')
    h,w=surface.shape[:2];pixels=h*w
    if min(h,w)<1 or max(h,w)>16384 or pixels>16777216:
        raise error('BUDGET','分色HSL表面超过尺寸预算')
    if type(tile_pixels) is not int or not 1<=tile_pixels<=262144:
        raise error('BUDGET','分色HSL分块大小无效')
    if type(max_working_bytes) is not int or not 1<=max_working_bytes<=MAX_WORKING_BYTES or type(retained_table_bytes) is not int or retained_table_bytes<0:
        raise error('BUDGET','分色HSL工作区预算无效')
    tile=min(tile_pixels,16384)
    estimate=3*surface.nbytes+retained_table_bytes+min(pixels,tile)*2048+4*len(plan.tracks_json.encode('utf8'))+524288
    if estimate>max_working_bytes:raise error('BUDGET','分色HSL表面、保留LUT及分块工作区估算超限')
    source=surface.reshape(-1,4)
    for start in range(0,pixels,tile):
        poll();part=source[start:start+tile]
        if not np.isfinite(part).all() or np.any(part[:,3]<0) or np.any(part[:,3]>1):
            raise error('VALUES','分色HSL的RGB须有限且alpha须在0..1')
    output=np.empty_like(source)
    outside_count=output_clip_count=0
    for start in range(0,pixels,tile):
        poll();part=source[start:start+tile];target=output[start:start+len(part)];target[:]=part
        if strength==0:continue
        encoded,_=convert_rgba(part.reshape(1,len(part),4),working_signal,plan.input_signal,
            tile_pixels=tile,max_working_bytes=max_working_bytes,cancel=poll)
        rgb=encoded.reshape(-1,4)[:,:3]
        outside=(rgb<0)|(rgb>1);outside_count+=int(np.count_nonzero(outside))
        if plan.input_gamut=='reject' and np.any(outside):
            raise error('INPUT_GAMUT','分色HSL算子输入超出0..1；须明确选择clip或preserve_residual')
        base=np.clip(rgb,0,1)
        graded,changed=_grade(base,values)
        if plan.input_gamut=='preserve_residual':graded+=rgb.astype(np.float64)-base.astype(np.float64)
        elif plan.input_gamut=='clip':changed|=np.any(outside,axis=1)
        if plan.output_gamut=='clip':
            clipped=(graded<0)|(graded>1);output_clip_count+=int(np.count_nonzero(clipped))
            changed|=np.any(clipped,axis=1);np.clip(graded,0,1,out=graded)
        with np.errstate(over='ignore',invalid='ignore'):rgb[:]=graded
        if not np.isfinite(rgb).all():raise error('VALUES','分色HSL中间结果超出Float32有限范围')
        converted,_=convert_rgba(encoded,plan.output_signal,working_signal,
            tile_pixels=tile,max_working_bytes=max_working_bytes,cancel=poll)
        graded=converted.reshape(-1,4)[:,:3]
        with np.errstate(over='ignore',invalid='ignore'):
            target[:,:3]=graded if strength==1 else part[:,:3].astype(np.float64)*(1-strength)+graded.astype(np.float64)*strength
        if plan.input_signal==plan.output_signal:target[~changed,:3]=part[~changed,:3]
        if not np.isfinite(target).all():raise error('VALUES','分色HSL输出超出Float32有限范围')
    poll()
    return output.reshape(surface.shape),{'protocol':PROTOCOL,'author_tick':str(author_tick),
        'sampled_values':values,'intensity':strength,'bands_degrees':dict(BANDS),
        'input_signal':vars(plan.input_signal),'output_signal':vars(plan.output_signal),'working_signal':vars(working_signal),
        'input_gamut':plan.input_gamut,'output_gamut':plan.output_gamut,
        'input_components_out_of_range':outside_count,'clipped_input_components':outside_count if plan.input_gamut=='clip' else 0,
        'preserved_residual_components':outside_count if plan.input_gamut=='preserve_residual' else 0,
        'output_clipped_components':output_clip_count,'gamut_policy_evaluated':strength!=0,
        'band_selection':'original-hue-circular-triangular-partition','achromatic_policy':'unselected-input-RGB',
        'residual_model':'bounded-HSL-plus-original-RGB-minus-bounded-RGB-not-HDR-appearance',
        'mix_domain':'linear-working-straight-RGB','alpha':'input-bits-preserved','integer_intermediate':False,
        'HSL_scratch_dtype':'float64','raster_dtype':'float32','near_black_saturation_epsilon_floor':False,
        'estimated_working_bytes':estimate,'estimated_bytes_are_peak_RSS':False,'actual_tile_pixels_limit':tile,
        'legacy_kernel_domain':'encoded-RGB-8-bit','natural_quality_accepted':False,'HDR_accepted':False}
