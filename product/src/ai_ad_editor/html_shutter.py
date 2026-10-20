"""Explicit centered subframe sampling and native Pillow integer alpha sums.

OpenFilm's MIT render.mjs organizes repeated shutter-time redraws. This sampler
uses midpoint times and premultiplied encoded-sRGB sums, with separate evidence.
No browser, network or model is started by this module.
"""
from __future__ import annotations
from bisect import bisect_right
import copy
from fractions import Fraction
import hashlib
import io
import math
from pathlib import Path

from .artifact_locks import artifact_entry
from .errors import AppError

MAX_SAMPLES=16
MAX_CUTS=256
MAX_WORK_PIXELS=2_000_000_000
PHASE='midpoint_centered'
DOMAIN='premultiplied_encoded_srgb_8bit'


def fail(message):
    raise AppError('HTML_SHUTTER_INVALID',message,exit_code=2,path='shutter')


def configuration(saved=None,*,samples=None,fraction=None,cut_ticks=None,clear_cuts=False,duration_tick):
    value={'version':1,'samples':1,'fraction':.5,'cut_ticks':[],
           'sampling_phase':PHASE,'composite_domain':DOMAIN}
    if saved is not None:
        if not isinstance(saved,dict) or set(saved)!=set(value):fail('快门配方字段不完整或未知')
        value.update(copy.deepcopy(saved))
    if samples is not None:value['samples']=samples
    if fraction is not None:value['fraction']=fraction
    if clear_cuts and cut_ticks is not None:fail('切点与清空切点不能同时指定')
    if clear_cuts:value['cut_ticks']=[]
    elif cut_ticks is not None:value['cut_ticks']=copy.deepcopy(cut_ticks)
    if type(value['version']) is not int or value['version']!=1 or value['sampling_phase']!=PHASE or value['composite_domain']!=DOMAIN:
        fail('不支持的快门版本、采样相位或合成域')
    if type(value['samples']) is not int or not 1<=value['samples']<=MAX_SAMPLES:fail('快门采样数为 1..16 整数')
    if type(value['fraction']) not in (int,float) or not math.isfinite(value['fraction']) or not 0<=value['fraction']<=1:
        fail('快门比例必须为 0..1 有限数')
    cuts=value['cut_ticks']
    if not isinstance(cuts,list) or len(cuts)>MAX_CUTS or any(type(c) is not int or not 0<c<duration_tick for c in cuts):
        fail('切点必须为源时长内部的整数 tick，最多 256 个')
    if cuts!=sorted(set(cuts)):fail('切点必须严格递增且不重复')
    value['fraction']=float(value['fraction'])
    return value


def profile(spec,frame_count,config,*,layout_check='off'):
    effective=config['samples'] if config['samples']>1 and config['fraction']>0 else 1
    enabled=effective>1;captures=frame_count*effective
    passes=3+(2 if layout_check=='strict' else 0)
    work=spec['width']*spec['height']*captures*passes
    if enabled and work>MAX_WORK_PIXELS:
        raise AppError('HTML_SHUTTER_BUDGET','子帧、三次渲染重绘及布局检查合计超过 20 亿像素',exit_code=2,path='shutter')
    return {'config':copy.deepcopy(config),'enabled':enabled,'effective_samples':effective,
        'output_frames':frame_count,'capture_count':captures,'render_passes':3,
        'layout_passes':passes-3,'work_pixels':work,'budget_applied':enabled,
        'internal_cuts':'explicit_anchors_only_no_automatic_scene_detection',
        'working_storage':'one_RGBA_capture_and_four_int32_accumulation_planes_plus_native_temporaries; not a process RAM cap'}


def schedule(spec,ticks,shutter):
    """Keep exact intended times plus the actual binary64 time sent to HTML."""
    fps=Fraction(spec['fps']['num'],spec['fps']['den']);config=shutter['config']
    n=shutter['effective_samples'];exposure=Fraction(str(config['fraction']))
    bounds=[Fraction(0),*(Fraction(c,ticks) for c in config['cut_ticks']),Fraction(spec['duration_tick'],ticks)]
    result=[]
    for index in range(shutter['output_frames']):
        anchor=Fraction(index,1)/fps;segment=bisect_right(bounds,anchor)-1
        low,high=bounds[segment:segment+2]
        guard=min(Fraction(1,1_000_000),(high-low)/2)
        for k in range(n):
            requested=anchor+(Fraction(2*k+1,2*n)-Fraction(1,2))*exposure/fps if n>1 else anchor
            actual=min(max(requested,low),high-guard) if n>1 else anchor
            seconds=float(actual)
            if seconds>=float(high):seconds=math.nextafter(float(high),-math.inf)
            if seconds<float(low):seconds=float(low)
            result.append({'capture_index':len(result),'output_frame':index,'sample_index':k,
                'requested_seconds_rational':str(requested),'clamped_seconds_rational':str(actual),
                'worker_time_seconds':seconds,'worker_time_binary64_rational':str(Fraction.from_float(seconds)),
                'segment_start_rational':str(low),'segment_end_rational':str(high),
                'clamped':actual!=requested})
    return result


def implementation():
    import PIL
    from PIL import ImageMath,_imaging,_imagingmath
    files=[Path(__file__),Path(ImageMath.__file__),Path(_imaging.__file__),Path(_imagingmath.__file__)]
    return {'engine':'agent-native-html-shutter-v1','pillow_version':PIL.__version__,
        'files':[artifact_entry(p.resolve(),'html-shutter-runtime') for p in files],
        'scope':'sampler, Pillow ImageMath and native core/math modules; not every system DLL'}


def verify_implementation(expected):
    for row in expected['files']:
        if artifact_entry(Path(row['path']),'html-shutter-runtime')['sha256']!=row['sha256']:
            raise AppError('HTML_SHUTTER_RUNTIME_CHANGED','子帧合成运行实现字节变化',exit_code=10,path=row['path'])


class AlphaAccumulator:
    """One output frame; uint32-safe sums using Pillow's native int32 kernels."""
    def __init__(self,size,samples):
        from PIL import Image
        if type(samples) is not int or not 2<=samples<=MAX_SAMPLES:fail('合成器需要 2..16 个实际子帧')
        self.size=size;self.samples=samples;self.count=0
        self.sums=[Image.new('I',size,0) for _ in range(4)]

    def push(self,png):
        from PIL import Image,ImageMath
        if self.count>=self.samples:fail('子帧数量超过声明')
        with Image.open(io.BytesIO(png)) as image:
            if image.size!=self.size:fail('子帧尺寸与声明不一致')
            frame=image.convert('RGBA')
        colors=frame.split();alpha=colors[3]
        for i in range(3):
            self.sums[i]=ImageMath.lambda_eval(lambda a:a['old']+a['c']*a['alpha'],
                old=self.sums[i],c=colors[i],alpha=alpha)
        self.sums[3]=ImageMath.lambda_eval(lambda a:a['old']+a['alpha'],old=self.sums[3],alpha=alpha)
        self.count+=1

    def finish(self):
        from PIL import Image,ImageMath
        if self.count!=self.samples:fail('子帧数量不完整')
        alpha=self.sums[3]
        # Integer division with doubled numerator implements positive half-up.
        denominator=ImageMath.lambda_eval(lambda a:a['alpha']+(a['alpha']==0),alpha=alpha)
        colors=[ImageMath.lambda_eval(lambda a:(2*a['color']+a['alpha'])/(2*a['den']),
                    color=color,alpha=alpha,den=denominator).convert('L') for color in self.sums[:3]]
        coverage=ImageMath.lambda_eval(lambda a:(2*a['alpha']+a['n'])/(2*a['n']),alpha=alpha,n=self.samples).convert('L')
        frame=Image.merge('RGBA',(*colors,coverage));self.sums=[]
        data=io.BytesIO();frame.save(data,format='PNG',compress_level=1)
        return data.getvalue(),{'rgba_sha256':'sha256:'+hashlib.sha256(frame.tobytes()).hexdigest(),
            'alpha_extrema':list(coverage.getextrema()),'samples':self.count,
            'rounding':'positive_integer_half_up; RGB zero when summed alpha is zero',
            'composite_domain':DOMAIN}
