"""Explicit native YCbCr to straight Float32 RGB, without integer RGB stages.

This boundary decodes YCbCr code values and upsamples chroma. Its RGB remains
in the source's nonlinear transfer and primaries; it does not infer either,
perform a display EOTF, convert a gamut, tone map or claim HDR acceptance.
Coefficients/ranges follow ITU-R BT.709/BT.601/BT.2020 NCL. Chroma pixel
centres follow the explicitly selected FFmpeg chroma-location convention.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import numpy as np
from .errors import AppError

PROTOCOL='native-YCbCr-to-straight-float32-v1'
MAX_DIMENSION=16384
MAX_PIXELS=16777216
MAX_RAW_BYTES=512*1024*1024
MAX_WORKING_BYTES=768*1024*1024
TILE_PIXELS=65536
COEFFICIENTS={'bt709':(.2126,.0722),'smpte170m':(.299,.114),
              'bt470bg':(.299,.114),'bt2020nc':(.2627,.0593)}
LOCATIONS={'left','center','topleft','top','bottomleft','bottom'}

def error(suffix,message):return AppError('FLOAT_YUV_'+suffix,message,exit_code=2)

@dataclass(frozen=True)
class YUVSpec:
    matrix:str
    range:str
    chroma_location:str

    def __post_init__(self):
        if not all(isinstance(value,str) for value in (self.matrix,self.range,self.chroma_location)):
            raise error('COLOR','矩阵、量程和采样位置须为明确字符串')
        if self.matrix not in COEFFICIENTS:raise error('COLOR','YCbCr矩阵须明确且受支持')
        if self.range not in ('limited','full'):raise error('COLOR','YCbCr量程须明确为limited或full')
        if self.chroma_location not in LOCATIONS:raise error('COLOR','色度采样位置须明确且受支持')

@dataclass(frozen=True)
class YUVLayout:
    pixel_format:str
    bits:int
    storage_bits:int
    sub_x:int
    sub_y:int
    alpha:bool=False
    endian:str='le'
    interleaved:bool=False
    swap_uv:bool=False
    msb_shift:int=0

    @property
    def dtype(self):return np.dtype('u1' if self.storage_bits==8 else ('<' if self.endian=='le' else '>')+'u2')

def layout(pixel_format):
    if not isinstance(pixel_format,str):raise error('FORMAT','原生YCbCr格式须为字符串')
    match=re.fullmatch(r'(yuv|yuva)(420|422|444)p(?:(9|10|12|14|16)(le|be))?',pixel_format)
    if match:
        prefix,sampling,bits,endian=match.groups();bits=int(bits or 8)
        sx,sy={'420':(2,2),'422':(2,1),'444':(1,1)}[sampling]
        return YUVLayout(pixel_format,bits,8 if bits==8 else 16,sx,sy,prefix=='yuva',endian or 'le')
    if pixel_format in ('nv12','nv21'):
        return YUVLayout(pixel_format,8,8,2,2,interleaved=True,swap_uv=pixel_format=='nv21')
    match=re.fullmatch(r'p(010|012|016)(le|be)',pixel_format)
    if match:
        bits={'010':10,'012':12,'016':16}[match[1]]
        return YUVLayout(pixel_format,bits,16,2,2,endian=match[2],interleaved=True,msb_shift=16-bits)
    raise error('FORMAT','原生YCbCr格式需要明确适配，禁止静默转为8位RGB')

def _dimensions(width,height):
    for value in (width,height):
        if isinstance(value,bool) or not isinstance(value,(int,np.integer)) or not 1<=value<=MAX_DIMENSION:
            raise error('DIMENSIONS','YCbCr宽高须在有效整数范围')
    width,height=int(width),int(height)
    if width*height>MAX_PIXELS:raise error('BUDGET','YCbCr帧超过像素预算')
    return width,height

def frame_bytes(pixel_format,width,height):
    info=layout(pixel_format);width,height=_dimensions(width,height)
    chroma=((width+info.sub_x-1)//info.sub_x)*((height+info.sub_y-1)//info.sub_y)
    size=(width*height*(2 if info.alpha else 1)+chroma*2)*(info.storage_bits//8)
    if size>MAX_RAW_BYTES:raise error('BUDGET','YCbCr原生帧超过字节预算')
    return size

def _chroma_offset(info,location):
    x=0. if location.endswith('left') or location=='left' else (info.sub_x-1)/2
    y=0. if location.startswith('top') else info.sub_y-1. if location.startswith('bottom') else (info.sub_y-1)/2
    return x,y

def _sample(plane,x,y,offset,info):
    # Clamp coordinates before flooring: edge samples are replicated, including
    # odd-sized native planes. No transparent border is appropriate for chroma.
    sx=np.clip((x-offset[0])/info.sub_x,0,plane.shape[1]-1)
    sy=np.clip((y-offset[1])/info.sub_y,0,plane.shape[0]-1)
    x0=np.floor(sx).astype(np.int64);y0=np.floor(sy).astype(np.int64)
    dx=sx-x0;dy=sy-y0;x1=np.minimum(x0+1,plane.shape[1]-1);y1=np.minimum(y0+1,plane.shape[0]-1)
    def values(xx,yy):
        value=plane[yy,xx]
        if info.msb_shift:value=np.right_shift(value,info.msb_shift)
        return value.astype(np.float64)
    return ((values(x0,y0)*(1-dx)+values(x1,y0)*dx)*(1-dy)
        +(values(x0,y1)*(1-dx)+values(x1,y1)*dx)*dy)

def decode_frame(raw,pixel_format,width,height,*,spec,alpha_association='straight',cancel=None,
                 max_working_bytes=MAX_WORKING_BYTES):
    """Native YUV/alpha bytes to owned HWC RGBA Float32, bilinear chroma.

    The caller must provide matrix/range/siting. Above-white and below-black
    RGB survive; alpha is full-range coverage, independent of luma range.
    Only progressive frame chroma is supported, not field-based siting.
    """
    if not isinstance(spec,YUVSpec):raise error('COLOR','须提供明确YCbCr色彩说明')
    if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调无效')
    poll=cancel if cancel is not None else lambda:None;poll()
    info=layout(pixel_format);width,height=_dimensions(width,height);size=frame_bytes(pixel_format,width,height)
    if alpha_association not in ('straight','premultiplied'):raise error('ALPHA','须明确源RGB的alpha表示')
    if isinstance(max_working_bytes,bool) or not isinstance(max_working_bytes,(int,np.integer)) or not 1<=max_working_bytes<=MAX_WORKING_BYTES:
        raise error('BUDGET','YCbCr浮点工作区预算无效')
    pixels=width*height;estimated=size+pixels*16+min(TILE_PIXELS,pixels)*384+4096
    if estimated>max_working_bytes:raise error('BUDGET','YCbCr浮点转换超过工作区估算')
    try:
        view=memoryview(raw)
        if not view.c_contiguous or view.nbytes!=size:raise ValueError('noncontiguous or wrong native length')
        values=np.frombuffer(view,dtype=info.dtype)
    except (TypeError,ValueError,BufferError) as exc:raise error('BYTES','YCbCr原生帧字节长度或连续性无效') from exc
    maximum=(1<<info.bits)-1
    if not info.msb_shift:
        for start in range(0,len(values),TILE_PIXELS):
            poll()
            if np.any(values[start:start+TILE_PIXELS]>maximum):raise error('VALUES','YCbCr原生码值超出声明位深')
    cw,ch=(width+info.sub_x-1)//info.sub_x,(height+info.sub_y-1)//info.sub_y
    chroma=cw*ch;yplane=values[:pixels]
    if info.interleaved:
        pair=values[pixels:pixels+chroma*2].reshape(ch,cw,2)
        uplane=pair[...,1 if info.swap_uv else 0];vplane=pair[...,0 if info.swap_uv else 1]
    else:
        uplane=values[pixels:pixels+chroma].reshape(ch,cw)
        vplane=values[pixels+chroma:pixels+chroma*2].reshape(ch,cw)
    aplane=values[-pixels:] if info.alpha else None
    scale=1<<(info.bits-8)
    y_offset,y_range,c_offset,c_range=(16*scale,219*scale,128*scale,224*scale) if spec.range=='limited' else (0,maximum,1<<(info.bits-1),maximum)
    kr,kb=COEFFICIENTS[spec.matrix];kg=1-kr-kb;offset=_chroma_offset(info,spec.chroma_location)
    output=np.empty((pixels,4),dtype=np.float32)
    for start in range(0,pixels,TILE_PIXELS):
        poll();end=min(start+TILE_PIXELS,pixels);ids=np.arange(start,end,dtype=np.int64);y,x=np.divmod(ids,width)
        yy=yplane[start:end]
        if info.msb_shift:yy=np.right_shift(yy,info.msb_shift)
        yy=(yy.astype(np.float64)-y_offset)/y_range
        u=(_sample(uplane,x,y,offset,info)-c_offset)/c_range
        v=(_sample(vplane,x,y,offset,info)-c_offset)/c_range
        out=output[start:end];out[:,0]=yy+2*(1-kr)*v
        out[:,2]=yy+2*(1-kb)*u
        out[:,1]=yy-2*kb*(1-kb)/kg*u-2*kr*(1-kr)/kg*v
        if aplane is None:out[:,3]=1
        else:np.divide(aplane[start:end],maximum,out=out[:,3],dtype=np.float32)
        if info.alpha and alpha_association=='premultiplied':
            np.divide(out[:,:3],out[:,3:4],out=out[:,:3],where=out[:,3:4]>0)
            out[out[:,3]==0,:3]=0
    poll()
    return output.reshape(height,width,4),{
        'protocol':PROTOCOL,'native_pixel_format':pixel_format,'frame_bytes':size,'component_bits':info.bits,
        'matrix':spec.matrix,'range':spec.range,'chroma_location':spec.chroma_location,'chroma_filter':'bilinear-edge-replicated',
        'chroma_offsets_in_luma_pixels':list(offset),'subsampling':[info.sub_x,info.sub_y],
        'source_has_alpha':info.alpha,'alpha_association':alpha_association,'alpha_range':'full',
        'RGB':'source-transfer-and-primaries;no-clipping','colour_transfer_transform':'none',
        'estimated_working_bytes':estimated,'estimated_bytes_are_peak_RSS':False,
        'progressive_only':True,'HDR_accepted':False,'editor_integrated':False}
