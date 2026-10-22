"""Bounded NumPy CPU compositing for a streaming Float32 timeline renderer.

Public surfaces are owned straight RGBA Float32. Each tile evaluates in
Float64, then rounds at its public surface boundary. No media I/O or colour
conversion is performed here. Display blend modes require overlap RGB 0..1;
normal source-over retains finite negative and over-one RGB.
"""
from __future__ import annotations
import math
import numpy as np
from .errors import AppError
from .float_raster import mode_name

PROTOCOL='float32-tiled-CPU-straight-compositing-v1'
MAX_DIMENSION=16384
MAX_PIXELS=16777216
MAX_TILE_PIXELS=262144
MAX_WORKING_BYTES=768*1024**2

def error(code,message):return AppError('FLOAT_COMPOSITE_'+code,message,exit_code=2)

def _lum(c):return c[:,0:1]*.3+c[:,1:2]*.59+c[:,2:3]*.11

def _sat(c,target):
    low=np.min(c,axis=1,keepdims=True);span=np.max(c,axis=1,keepdims=True)-low
    return np.divide(c-low,span,out=np.zeros_like(c),where=span>0)*target

def _luminosity(c,target):
    value=c+target-_lum(c);low=np.min(value,axis=1,keepdims=True)
    if np.any(low<0):
        moved=target+np.divide((value-target)*target,target-low,out=np.zeros_like(value),where=target!=low)
        value=np.where(low<0,moved,value)
    high=np.max(value,axis=1,keepdims=True)
    if np.any(high>1):
        moved=target+np.divide((value-target)*(1-target),high-target,out=np.zeros_like(value),where=high!=target)
        value=np.where(high>1,moved,value)
    return value

def _blend(mode,a,b):
    with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
        if mode=='normal':return b
        if mode=='multiply':return a*b
        if mode=='screen':return a+b-a*b
        if mode=='overlay':return np.where(a<=.5,2*a*b,1-2*(1-a)*(1-b))
        if mode=='darken':return np.minimum(a,b)
        if mode=='lighten':return np.maximum(a,b)
        if mode=='burn':return np.where(a==1,1,np.where(b==0,0,1-np.minimum(1,(1-a)/b)))
        if mode=='dodge':return np.where(a==0,0,np.where(b==1,1,np.minimum(1,a/(1-b))))
        if mode=='hardlight':return np.where(b<=.5,2*a*b,1-2*(1-a)*(1-b))
        if mode=='softlight':
            d=np.where(a<=.25,((16*a-12)*a+4)*a,np.sqrt(a))
            return np.where(b<=.5,a-(1-2*b)*a*(1-a),a+(2*b-1)*(d-a))
        if mode=='difference':return np.abs(a-b)
        if mode=='exclusion':return a+b-2*a*b
        if mode=='addition':return np.minimum(1,a+b)
        if mode=='addition128':return np.clip(a+b-.5,0,1)
        if mode=='average':return (a+b)/2
        if mode=='subtract':return np.maximum(0,a-b)
        if mode=='divide':return np.where(b==0,1,np.minimum(1,a/b))
        if mode=='negation':return 1-np.abs(1-a-b)
        if mode=='phoenix':return np.minimum(a,b)-np.maximum(a,b)+1
        if mode=='pinlight':return np.where(b<=.5,np.minimum(a,2*b),np.maximum(a,2*b-1))
        if mode=='reflect':return np.where(b==1,1,np.minimum(1,a*a/(1-b)))
        if mode=='glow':return np.where(a==1,1,np.minimum(1,b*b/(1-a)))
        if mode=='freeze':return np.where(b==0,0,np.maximum(0,1-(1-a)*(1-a)/b))
        if mode=='vivid':return np.where(b<=.5,np.where(b==0,0,np.maximum(0,1-(1-a)/(2*b))),np.where(b==1,1,np.minimum(1,a/(2*(1-b)))))
        if mode=='hard_mix':return (a+b>=1).astype(np.float64)
        if mode in ('and','or','xor'):
            qa=np.floor(a*65535+.5).astype(np.uint16);qb=np.floor(b*65535+.5).astype(np.uint16)
            operation={'and':np.bitwise_and,'or':np.bitwise_or,'xor':np.bitwise_xor}[mode]
            return operation(qa,qb).astype(np.float64)/65535
        if mode=='hue':return _luminosity(_sat(b,np.ptp(a,axis=1,keepdims=True)),_lum(a))
        if mode=='saturation':return _luminosity(_sat(a,np.ptp(b,axis=1,keepdims=True)),_lum(a))
        if mode=='color':return _luminosity(b,_lum(a))
        if mode=='luminosity':return _luminosity(a,_lum(b))
    raise error('MODE','浮点混合模式未实现')

def composite_rgba(backdrop,source,*,mode='normal',opacity=1.,coverage=None,
                   tile_pixels=65536,max_working_bytes=MAX_WORKING_BYTES,cancel=None):
    """Return an owned composed surface and explicit arithmetic/domain metadata.

    Coverage and opacity affect source alpha only. The caller supplies matched
    geometry and colour/transfer semantics. Cancellation callbacks must raise;
    inputs are never changed, including on cancellation or invalid late tiles.
    """
    mode=mode_name(mode)
    if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调须可调用')
    poll=cancel if cancel is not None else lambda:None;poll()
    for value in (backdrop,source):
        if not isinstance(value,np.ndarray) or value.dtype!=np.dtype('float32') or value.ndim!=3 or value.shape[-1]!=4 or not value.flags.c_contiguous:
            raise error('SURFACE','输入须为连续H×W×4 Float32表面')
    if source.shape!=backdrop.shape:raise error('SURFACE','两表面尺寸须一致')
    height,width=source.shape[:2];pixels=width*height
    if min(width,height)<1 or max(width,height)>MAX_DIMENSION or pixels>MAX_PIXELS:raise error('BUDGET','浮点表面超过尺寸预算')
    if isinstance(opacity,(bool,np.bool_)):
        raise error('OPACITY','覆盖率须为0..1有限数值')
    try:opacity=float(opacity)
    except (TypeError,ValueError,OverflowError) as caught:raise error('OPACITY','覆盖率须为0..1有限数值') from caught
    if not math.isfinite(opacity) or not 0<=opacity<=1:raise error('OPACITY','覆盖率须为0..1有限数值')
    for value,limit in ((tile_pixels,MAX_TILE_PIXELS),(max_working_bytes,MAX_WORKING_BYTES)):
        if isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,np.integer)) or not 1<=value<=limit:raise error('BUDGET','分块或工作区预算无效')
    tile_pixels=int(tile_pixels);mask=None
    if coverage is not None:
        if not isinstance(coverage,np.ndarray) or coverage.dtype!=np.dtype('float32') or coverage.shape!=(height,width) or not coverage.flags.c_contiguous:
            raise error('MASK','蒙版须为同尺寸连续Float32覆盖率')
        mask=coverage.reshape(-1,1)
    estimated=3*source.nbytes+(coverage.nbytes if coverage is not None else 0)+min(pixels,tile_pixels)*1024+4096
    if estimated>max_working_bytes:raise error('BUDGET','合成工作区估算超限')
    bottom=backdrop.reshape(-1,4);top=source.reshape(-1,4);result=np.empty_like(bottom)
    for start in range(0,pixels,tile_pixels):
        poll();end=min(pixels,start+tile_pixels)
        a=bottom[start:end].astype(np.float64);b=top[start:end].astype(np.float64)
        if not np.isfinite(a).all() or not np.isfinite(b).all() or np.any(a[:,3]<0) or np.any(a[:,3]>1) or np.any(b[:,3]<0) or np.any(b[:,3]>1):
            raise error('VALUES','RGB须有限，alpha须在0..1范围')
        ab=a[:,3:4];asource=b[:,3:4]*opacity
        if mask is not None:
            m=mask[start:end]
            if not np.isfinite(m).all() or np.any(m<0) or np.any(m>1):raise error('MASK','蒙版覆盖率须为0..1有限值')
            asource=asource*m
        cb=a[:,:3];cs=b[:,:3]
        # Hidden RGB cannot influence the blend function or its domain checks.
        cb[ab[:,0]==0]=0;cs[asource[:,0]==0]=0
        alpha=ab+asource*(1-ab)
        if mode=='normal':premultiplied=cs*asource+cb*ab*(1-asource)
        else:
            overlap=(ab[:,0]>0)&(asource[:,0]>0)
            ca,cs_overlap=cb[overlap],cs[overlap]
            if np.any(ca<0) or np.any(ca>1) or np.any(cs_overlap<0) or np.any(cs_overlap>1):
                raise error('DOMAIN','当前显示混合模式要求重叠RGB在0..1；不隐式截断HDR或负色值')
            mixed=np.zeros_like(cb)
            if np.any(overlap):mixed[overlap]=_blend(mode,ca,cs_overlap)
            premultiplied=cb*ab*(1-asource)+cs*asource*(1-ab)+mixed*asource*ab
        rgb=np.divide(premultiplied,alpha,out=np.zeros_like(premultiplied),where=alpha>0)
        output=result[start:end];output[:,:3]=rgb;output[:,3:4]=alpha
        if not np.isfinite(output).all():raise error('VALUES','合成结果超过Float32有限范围')
    poll()
    return result.reshape(height,width,4),{'protocol':PROTOCOL,'mode':mode,'opacity':opacity,
        'coverage_mask':coverage is not None,'alpha':'straight;zero-alpha-RGB-canonicalized',
        'arithmetic':'Float64 tiled;public Float32 round-to-nearest boundary',
        'RGB_domain':'finite-negative-and-over-one' if mode=='normal' else 'normalized-0..1-in-overlap;nonoverlap-extended',
        'logical_modes':'and/or/xor use explicit unsigned-16-bit code grid',
        'colour_conversion':False,'clipping':'none;unsupported-display-domain-rejects',
        'tile_pixels':tile_pixels,'estimated_working_bytes':estimated,'estimated_bytes_are_peak_RSS':False,
        'ordinary_timeline_integrated':False,'HDR_accepted':False}
