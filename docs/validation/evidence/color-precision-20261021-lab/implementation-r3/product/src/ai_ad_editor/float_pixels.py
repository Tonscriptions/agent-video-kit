"""Decode native RGB/gray raw planes without implicit alpha or colour conversion.

This is a pixel boundary, not a demuxer, colour manager or editor integration.
The caller supplies the actual software-decoded pixel format and association.
Integer codes through 16 bits and binary16/binary32 colour values are retained
at Float32 precision. YUV, bit-packed RGB and 32-bit integer codes need separate
explicit adapters; they cannot silently enter an 8-bit fallback here.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import numpy as np
from .errors import AppError

PROTOCOL='native-RGB-gray-to-straight-float32-v1'
MAX_DIMENSION=16384
MAX_PIXELS=16777216
MAX_RAW_BYTES=512*1024*1024
MAX_WORKING_BYTES=768*1024*1024
TILE_PIXELS=65536

def error(suffix,message):return AppError('FLOAT_PIXELS_'+suffix,message,exit_code=2)

@dataclass(frozen=True)
class Layout:
    pixel_format:str
    channels:tuple[str,...]
    planar:bool
    storage_bits:int
    component_bits:int
    floating:bool=False
    endian:str='le'
    msb_shift:int=0

    @property
    def dtype(self):
        return np.dtype(('<' if self.endian=='le' else '>')+('f' if self.floating else 'u')+str(self.storage_bits//8))

    @property
    def has_alpha(self):return 'a' in self.channels

def layout(pixel_format):
    if not isinstance(pixel_format,str):raise error('FORMAT','像素格式须是实际探测的字符串')
    name=pixel_format.lower()
    planar=re.fullmatch(r'gbr(a?)p(?:(f?)(9|10|12|14|16|32)(msb)?(le|be))?',name)
    if planar:
        alpha,floating,bits,msb,endian=planar.groups();bits=int(bits or 8);floating=bool(floating)
        if bits==32 and not floating:raise error('PRECISION','32位整数码值不能全部精确表示为Float32')
        if floating and (bits not in (16,32) or msb):raise error('FORMAT','浮点像素格式不受支持')
        if msb and (alpha or bits not in (10,12)):raise error('FORMAT','MSB像素格式不受支持')
        storage=bits if floating else 8 if bits==8 else 16
        return Layout(name,tuple('gbra' if alpha else 'gbr'),True,storage,bits,floating,endian or 'le',storage-bits if msb else 0)
    packed8={'rgb24':'rgb','bgr24':'bgr','rgba':'rgba','bgra':'bgra','argb':'argb','abgr':'abgr',
        'rgb0':'rgbx','bgr0':'bgrx','0rgb':'xrgb','0bgr':'xbgr','gray':'y','ya8':'ya'}
    if name in packed8:return Layout(name,tuple(packed8[name]),False,8,8)
    packed16=re.fullmatch(r'(rgb48|bgr48|rgba64|bgra64|ya16)(le|be)',name)
    if packed16:
        order={'rgb48':'rgb','bgr48':'bgr','rgba64':'rgba','bgra64':'bgra','ya16':'ya'}[packed16[1]]
        return Layout(name,tuple(order),False,16,16,endian=packed16[2])
    gray=re.fullmatch(r'gray(f?)(9|10|12|14|16|32)(le|be)',name)
    if gray:
        floating,bits,endian=gray.groups();bits=int(bits)
        if bits==32 and not floating:raise error('PRECISION','32位整数码值不能全部精确表示为Float32')
        if floating and bits not in (16,32):raise error('FORMAT','浮点灰度格式不受支持')
        return Layout(name,('y',),False,bits if floating else 16,bits,bool(floating),endian)
    packed_float=re.fullmatch(r'(rgb|rgba|ya)f(16|32)(le|be)',name)
    if packed_float:
        order,bits,endian=packed_float.groups()
        return Layout(name,tuple(order),False,int(bits),int(bits),True,endian)
    raise error('FORMAT','像素格式需要明确的高精度适配器，不能静默降为8位')

def frame_bytes(pixel_format,width,height):
    info=layout(pixel_format)
    for name,value in (('宽度',width),('高度',height)):
        if isinstance(value,bool) or not isinstance(value,(int,np.integer)) or not 1<=value<=MAX_DIMENSION:
            raise error('DIMENSIONS',name+'须在有效整数范围')
    pixels=int(width)*int(height);size=pixels*len(info.channels)*(info.storage_bits//8)
    if pixels>MAX_PIXELS or size>MAX_RAW_BYTES:raise error('BUDGET','原生表面超过像素或字节预算')
    return size

def decode_frame(raw,pixel_format,width,height,*,alpha_association='straight',cancel=None,
                 max_working_bytes=MAX_WORKING_BYTES):
    """Return an owned straight RGBA Float32 array and explicit boundary metadata."""
    if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调无效')
    poll=cancel if cancel is not None else lambda:None;poll()
    info=layout(pixel_format);size=frame_bytes(pixel_format,width,height);pixels=int(width)*int(height)
    if alpha_association not in ('straight','premultiplied'):
        raise error('ALPHA','必须明确源RGB是straight还是premultiplied')
    if isinstance(max_working_bytes,bool) or not isinstance(max_working_bytes,(int,np.integer)) or not 1<=max_working_bytes<=MAX_WORKING_BYTES:
        raise error('BUDGET','工作区预算无效')
    estimated=size+pixels*24+4096
    if estimated>max_working_bytes:raise error('BUDGET','原生转浮点表面超过工作区估算')
    try:
        view=memoryview(raw)
        if not view.c_contiguous or view.nbytes!=size:raise ValueError('length or noncontiguous buffer')
        values=np.frombuffer(view,dtype=info.dtype)
    except (TypeError,ValueError,BufferError) as exc:
        raise error('BYTES','原生帧必须有精确字节长度且连续') from exc
    data=values.reshape(len(info.channels),pixels).T if info.planar else values.reshape(pixels,len(info.channels))
    output=np.empty((pixels,4),dtype=np.float32)
    order={name:index for index,name in enumerate(info.channels)}
    maximum=(1<<info.component_bits)-1 if not info.floating else None
    for start in range(0,pixels,TILE_PIXELS):
        poll();sample=data[start:start+TILE_PIXELS];out=output[start:start+len(sample)]
        if info.floating:
            if not np.isfinite(sample).all():raise error('VALUES','浮点源含NaN或无穷值')
        elif not info.msb_shift and np.any(sample>maximum):
            raise error('VALUES','整数源超出声明的分量码值范围')
        for target,channel in enumerate('rgba'):
            source_channel='y' if channel in 'rgb' and 'y' in order else channel
            if source_channel not in order:
                if channel!='a':raise error('FORMAT','原生表面缺少颜色通道')
                out[:,target]=1
                continue
            component=sample[:,order[source_channel]]
            if info.msb_shift:component=np.right_shift(component,info.msb_shift)
            if info.floating:out[:,target]=component
            else:np.divide(component,maximum,out=out[:,target],dtype=np.float32)
        if np.any(out[:,3]<0) or np.any(out[:,3]>1):raise error('ALPHA','浮点源覆盖率须在0到1范围')
        if alpha_association=='premultiplied' and info.has_alpha:
            with np.errstate(over='ignore',invalid='ignore'):
                np.divide(out[:,:3],out[:,3:4],out=out[:,:3],where=out[:,3:4]>0)
            out[out[:,3]==0,:3]=0
            if not np.isfinite(out).all():raise error('VALUES','解除预乘后颜色超出Float32有限范围')
    poll()
    return output.reshape(int(height),int(width),4),{
        'protocol':PROTOCOL,'native_pixel_format':info.pixel_format,'frame_bytes':size,
        'component_bits':info.component_bits,'storage_bits':info.storage_bits,'native_floating':info.floating,
        'native_alpha_association':alpha_association,'source_has_alpha':info.has_alpha,
        'output':'straight-float32-RGBA','colour_transform':'none;source-numeric-values-only',
        'estimated_working_bytes':estimated,'estimated_bytes_are_peak_RSS':False,
        'hidden_straight_RGB':'retained;premultiplied-zero-alpha-canonicalized',
        'HDR_accepted':False,'editor_integrated':False}
