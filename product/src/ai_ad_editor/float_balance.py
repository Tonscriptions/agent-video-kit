"""Continuous, explicitly signalled three-way balance on author-time Float32 RGB.

No integer conversion or LUT is used. The legacy shadow-only balance and
Kelvin-to-shadow creative mapping are retained. This is not chromatic
adaptation, a black-body temperature model or an HDR appearance operator.
Native HSL lightness preservation is an explicitly bounded SDR operation;
the separate midrange method supports negative and superwhite RGB.
"""
from dataclasses import dataclass

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba
from .float_curves import signal
from .float_numeric_automation import number, compile_tracks, sample_tracks, raw_tracks, validate_duration

PROTOCOL = 'explicit-signal-author-clock-float32-three-way-balance-v1'
TYPE_ALIASES = {'color_balance':'color_balance', 'colorbalance':'color_balance',
                'color_wheel':'color_wheel', 'three_way_color':'color_wheel', 'three_way_wheel':'color_wheel',
                'color_temperature':'color_temperature', 'temperature':'color_temperature', 'warmth':'color_temperature'}
ALIASES = frozenset(TYPE_ALIASES)
CHANNELS = ('red','green','blue')
TONES = ('shadows','midtones','highlights')
WHEEL = tuple(t+'_'+c for t in TONES for c in CHANNELS)
WHEEL_ALIASES = {c[0]+suffix:t+'_'+c for t,suffix in zip(TONES,('s','m','h')) for c in CHANNELS}
BALANCE_ALIASES = {'rs':'red','gs':'green','bs':'blue'}
MAX_WORKING_BYTES = 768*1024*1024

def error(kind, message):
    return AppError('FLOAT_BALANCE_'+kind, message, exit_code=2)

def specs(kind):
    if kind=='color_temperature':
        return {'kelvin':(1000.,40000.), 'intensity':(0.,1.)}, {}, {'kelvin':6500.,'intensity':1.}
    names = CHANNELS if kind=='color_balance' else WHEEL
    return {**{n:(-1.,1.) for n in names},'intensity':(0.,1.)}, (BALANCE_ALIASES if kind=='color_balance' else WHEEL_ALIASES), {**dict.fromkeys(names,0.),'intensity':1.}

def parameter_names(name):
    kind = TYPE_ALIASES.get(name)
    if kind is None:return frozenset()
    bounds,aliases,_ = specs(kind)
    return frozenset(bounds)|frozenset(aliases)

def lightness(value):
    if value is True or type(value) is int and value==1:return 'native_hsl'
    if value is False or type(value) is int and value==0:return 'none'
    if not isinstance(value,str):raise error('ARGUMENT','亮度保留须为none/native_hsl/midrange或明确布尔值')
    text=value.strip().lower()
    text={'true':'native_hsl','1':'native_hsl','yes':'native_hsl','on':'native_hsl','lum':'native_hsl',
          'false':'none','0':'none','no':'none','off':'none'}.get(text,text)
    if text not in ('none','native_hsl','midrange'):raise error('ARGUMENT','亮度保留模式未知')
    return text

@dataclass(frozen=True)
class BalancePlan:
    effect_type: str
    values: tuple
    tracks_json: str
    input_signal: ColorSignal
    output_signal: ColorSignal
    output_gamut: str
    preserve_lightness: str

def compile_balance(effect):
    if not isinstance(effect,dict) or set(effect)-{'id','type','enabled','parameters','keyframes'}:
        raise error('ARGUMENT','色彩平衡包含未知字段；参数须置于parameters')
    name=str(effect.get('type','')).strip().lower().replace('-','_')
    kind=TYPE_ALIASES.get(name)
    if kind is None or type(effect.get('enabled',True)) is not bool:raise error('ARGUMENT','色彩平衡类型或enabled无效')
    bounds,aliases,values=specs(kind)
    p=effect.get('parameters',{})
    extra={'input_signal','output_signal','output_gamut','preserve_lightness','preserve_luma','pl','keyframes'}
    if not isinstance(p,dict) or set(p)-(set(bounds)|set(aliases)|extra):raise error('ARGUMENT','色彩平衡参数包含未知字段')
    incoming,outgoing=signal(p.get('input_signal')),signal(p.get('output_signal'))
    gamut=p.get('output_gamut','preserve')
    if not isinstance(gamut,str) or gamut not in ('preserve','clip'):raise error('ARGUMENT','输出色域策略须为preserve或clip')
    modes=[lightness(p[k]) for k in ('preserve_lightness','preserve_luma','pl') if k in p]
    if len(set(modes))>1:raise error('ARGUMENT','亮度保留别名冲突')
    authored={}
    for key,value in p.items():
        prop=aliases.get(key,key)
        if prop not in bounds:continue
        value=number(value,*bounds[prop])
        if prop in authored and authored[prop]!=value:raise error('ARGUMENT','色彩平衡参数别名冲突')
        authored[prop]=value
    values.update(authored)
    tracks=compile_tracks(raw_tracks(effect,p),bounds,aliases,name)
    return BalancePlan(kind,tuple(sorted(values.items())),tracks,incoming,outgoing,gamut,modes[0] if modes else 'none')

def state_at(plan,tick):
    if not isinstance(plan,BalancePlan) or plan.effect_type not in TYPE_ALIASES or TYPE_ALIASES[plan.effect_type]!=plan.effect_type:
        raise error('ARGUMENT','色彩平衡须使用已编译规范计划')
    if plan.output_gamut not in ('preserve','clip') or plan.preserve_lightness not in ('none','native_hsl','midrange'):
        raise error('ARGUMENT','色彩平衡计划模式无效')
    if not isinstance(plan.input_signal,ColorSignal) or not isinstance(plan.output_signal,ColorSignal):
        raise error('SIGNAL','色彩平衡计划须提供明确输入输出信号')
    bounds,aliases,defaults=specs(plan.effect_type)
    values={}
    if not isinstance(plan.values,tuple):raise error('ARGUMENT','色彩平衡参数须不可变')
    for item in plan.values:
        if not isinstance(item,tuple) or len(item)!=2 or item[0] not in bounds or item[0] in values:
            raise error('ARGUMENT','色彩平衡参数无效或重复')
        values[item[0]]=number(item[1],*bounds[item[0]])
    if values.keys()!=defaults.keys():raise error('ARGUMENT','色彩平衡计划缺少参数')
    values.update(sample_tracks(plan.tracks_json,bounds,aliases,plan.effect_type,tick))
    controls=dict.fromkeys(WHEEL,0.)
    if plan.effect_type=='color_temperature':
        delta=max(-1.,min(1.,(values['kelvin']-6500.)/6500.))
        controls.update(zip(('shadows_red','shadows_green','shadows_blue'),(-delta*.30,-delta*.05,delta*.30)))
    elif plan.effect_type=='color_balance':
        controls.update({'shadows_'+c:values[c] for c in CHANNELS})
    else:controls.update({n:values[n] for n in WHEEL})
    return values,controls

def validate_balance(effect,*,duration_tick=None):
    if effect.get('enabled',True) is False:return []
    try:
        plan=compile_balance(effect)
        validate_duration(plan.tracks_json,duration_tick)
    except AppError as exc:return [{'code':exc.code,'message':str(exc),'suffix':'.parameters'}]
    return []

def _native_hsl(rgb,original_double_lightness):
    """Native bounded HSL behaviour, including its zero-chroma boundary rule."""
    maximum,minimum=rgb.max(axis=1),rgb.min(axis=1)
    delta=maximum-minimum
    hue=np.zeros_like(maximum)
    red=(delta!=0)&(maximum==rgb[:,0])
    green=(delta!=0)&~red&(maximum==rgb[:,1])
    blue=(delta!=0)&~red&~green
    hue[red]=np.float32(60)*((rgb[red,1]-rgb[red,2])/delta[red])
    hue[green]=np.float32(60)*(np.float32(2)+(rgb[green,2]-rgb[green,0])/delta[green])
    hue[blue]=np.float32(60)*(np.float32(4)+(rgb[blue,0]-rgb[blue,1])/delta[blue])
    hue[hue<0]+=np.float32(360)
    level=original_double_lightness*np.float32(.5)
    denominator=np.float32(1)-np.abs(np.float32(2)*level-np.float32(1))
    saturation=np.zeros_like(level)
    active=(maximum!=np.float32(1))&(minimum!=np.float32(0))
    # Bounded black/white sources can yield a zero denominator only after an
    # adjustment away from a boundary. Native arithmetic would be undefined;
    # the original lightness uniquely defines black/white, so keep them exact.
    np.divide(delta,denominator,out=saturation,where=active&(denominator!=0))
    amplitude=saturation*np.minimum(level,np.float32(1)-level)
    out=np.empty_like(rgb)
    for channel,offset in enumerate((0.,8.,4.)):
        k=np.fmod(np.float32(offset)+hue/np.float32(30),np.float32(12))
        wave=np.maximum(np.minimum(np.minimum(k-np.float32(3),np.float32(9)-k),np.float32(1)),np.float32(-1))
        out[:,channel]=np.clip(level-amplitude*wave,0,1)
    return out

def _grade(rgb,controls,plan):
    original=rgb.copy()
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        level=original.max(axis=1)+original.min(axis=1)
        b=np.float32(.333);a=np.float32(4);scale=np.float32(.7)
        shadow=np.clip((b-level)*a+np.float32(.5),0,1)*scale
        middle=(np.clip((level-b)*a+np.float32(.5),0,1)*
                np.clip((np.float32(1)-level-b)*a+np.float32(.5),0,1))*scale
        high=np.clip((level+b-np.float32(1))*a+np.float32(.5),0,1)*scale
        result=original.copy()
        for i,c in enumerate(CHANNELS):
            result[:,i]+=np.float32(controls['shadows_'+c])*shadow
            result[:,i]+=np.float32(controls['midtones_'+c])*middle
            result[:,i]+=np.float32(controls['highlights_'+c])*high
        if plan.output_gamut=='clip' or plan.preserve_lightness=='native_hsl':np.clip(result,0,1,out=result)
        if plan.preserve_lightness=='native_hsl':result=_native_hsl(result,level)
        elif plan.preserve_lightness=='midrange':
            old=original.max(axis=1).astype(np.float64)*.5+original.min(axis=1).astype(np.float64)*.5
            new=result.max(axis=1).astype(np.float64)*.5+result.min(axis=1).astype(np.float64)*.5
            result=(result.astype(np.float64)+(old-new)[:,None]).astype(np.float32)
            if plan.output_gamut=='clip':np.clip(result,0,1,out=result)
    return result

def apply_balance(surface,plan,author_tick,*,working_signal,tile_pixels=65536,
                  retained_table_bytes=0,max_working_bytes=MAX_WORKING_BYTES,cancel=None):
    if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调须可调用')
    def poll():
        if cancel and cancel():raise AppError('RENDER_CANCELLED','浮点色彩平衡已取消',exit_code=6)
    poll()
    if not isinstance(working_signal,ColorSignal) or working_signal.transfer!='linear':raise error('SIGNAL','色彩平衡须使用明确线性工作信号')
    values,controls=state_at(plan,author_tick);strength=values['intensity']
    if not isinstance(surface,np.ndarray) or surface.dtype!=np.float32 or surface.ndim!=3 or surface.shape[-1]!=4 or not surface.flags.c_contiguous:
        raise error('SURFACE','色彩平衡输入须为连续H×W×4 Float32')
    h,w=surface.shape[:2];pixels=h*w
    if min(h,w)<1 or max(h,w)>16384 or pixels>16777216:raise error('BUDGET','色彩平衡表面超过尺寸预算')
    if type(tile_pixels) is not int or not 1<=tile_pixels<=262144:raise error('BUDGET','色彩平衡分块大小无效')
    if type(max_working_bytes) is not int or not 1<=max_working_bytes<=MAX_WORKING_BYTES or type(retained_table_bytes) is not int or retained_table_bytes<0:
        raise error('BUDGET','色彩平衡工作区预算无效')
    tile=min(tile_pixels,16384)
    estimate=3*surface.nbytes+retained_table_bytes+min(pixels,tile)*2048+4*len(plan.tracks_json.encode('utf8'))+524288
    if estimate>max_working_bytes:raise error('BUDGET','色彩平衡表面、保留LUT及分块工作区估算超限')
    source=surface.reshape(-1,4)
    for start in range(0,pixels,tile):
        poll();part=source[start:start+tile]
        if not np.isfinite(part).all() or np.any(part[:,3]<0) or np.any(part[:,3]>1):raise error('VALUES','色彩平衡RGB须有限且alpha须在0..1')
    output=np.empty_like(source)
    identity=(not any(controls.values()) and plan.input_signal==plan.output_signal and
              plan.output_gamut=='preserve' and plan.preserve_lightness in ('none','midrange'))
    for start in range(0,pixels,tile):
        poll();part=source[start:start+tile];target=output[start:start+len(part)];target[:]=part
        if strength==0 or identity:continue
        encoded,_=convert_rgba(part.reshape(1,len(part),4),working_signal,plan.input_signal,
            tile_pixels=tile,max_working_bytes=max_working_bytes,cancel=poll)
        rgb=encoded.reshape(-1,4)[:,:3]
        if plan.preserve_lightness=='native_hsl' and (np.any(rgb<0) or np.any(rgb>1)):
            raise error('PRESERVE_DOMAIN','native_hsl仅接受算子输入信号中的0..1 RGB；超范围可使用none或midrange')
        rgb[:]=_grade(rgb,controls,plan)
        if not np.isfinite(rgb).all():raise error('VALUES','色彩平衡中间结果超出Float32有限范围')
        converted,_=convert_rgba(encoded,plan.output_signal,working_signal,
            tile_pixels=tile,max_working_bytes=max_working_bytes,cancel=poll)
        graded=converted.reshape(-1,4)[:,:3]
        with np.errstate(over='ignore',invalid='ignore'):
            target[:,:3]=graded if strength==1 else part[:,:3].astype(np.float64)*(1-strength)+graded.astype(np.float64)*strength
        if not np.isfinite(target).all():raise error('VALUES','色彩平衡输出超出Float32有限范围')
    poll()
    return output.reshape(surface.shape),{'protocol':PROTOCOL,'effect_type':plan.effect_type,'author_tick':str(author_tick),
        'sampled_values':values,'sampled_wheel':controls,'intensity':strength,
        'input_signal':vars(plan.input_signal),'output_signal':vars(plan.output_signal),'working_signal':vars(working_signal),
        'output_gamut':plan.output_gamut,'preserve_lightness':plan.preserve_lightness,
        'weight_domain':'input-signal-max-plus-min-not-Rec709-luma',
        'kelvin_model':'legacy-shadow-balance-not-physical-white-balance' if plan.effect_type=='color_temperature' else None,
        'mix_domain':'linear-working-straight-RGB','alpha':'input-bits-preserved','integer_intermediate':False,
        'estimated_working_bytes':estimate,'estimated_bytes_are_peak_RSS':False,'actual_tile_pixels_limit':tile,
        'native_filter_accepts_float32':False,'native_HSL_black_white_defined_explicitly':True,
        'natural_quality_accepted':False,'HDR_accepted':False}
