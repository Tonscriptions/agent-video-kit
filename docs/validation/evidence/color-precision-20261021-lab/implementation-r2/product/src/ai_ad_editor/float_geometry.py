"""Bounded native NumPy affine sampling of straight Float32 RGBA surfaces.

Pixel centres have integer coordinates. Bilinear filtering operates on
premultiplied RGB and alpha, using transparent black outside the source. This
keeps geometric work out of FFmpeg filters that silently negotiate integers.
The caller supplies a shared colour space and an inverse matrix for each frame.
"""
from __future__ import annotations
import numpy as np
from .errors import AppError

PROTOCOL='float32-premultiplied-affine-sampling-v1'
MAX_DIMENSION=16384
MAX_PIXELS=16777216
MAX_TILE_PIXELS=262144
MAX_WORKING_BYTES=768*1024*1024

def _fail(code,message):
    return AppError(code,message,exit_code=2)

def _integer(value,minimum,maximum,name):
    if isinstance(value,bool) or not isinstance(value,(int,np.integer)) or not minimum<=value<=maximum:
        raise _fail('FLOAT_GEOMETRY_ARGUMENT',f'{name}超出整数范围')
    return int(value)

def resample_rgba(source,output_size,inverse,*,interpolation='bilinear',tile_pixels=65536,
                  max_working_bytes=MAX_WORKING_BYTES,cancel=None):
    """Return (H,W,RGBA) Float32 and budget metadata; performs no I/O.

    ``inverse`` is a finite 2x3 matrix mapping integer output pixel centres to
    input centres. Public surfaces remain straight; zero coverage is canonical
    transparent black. Sampling is point/bilinear, not an antialiasing guarantee
    for severe minification or a claim of linear-light/HDR colour management.
    """
    if cancel is not None and not callable(cancel):
        raise _fail('FLOAT_GEOMETRY_ARGUMENT','取消回调无效')
    poll=cancel if cancel is not None else lambda:None
    poll()
    if not isinstance(source,np.ndarray) or source.dtype!=np.dtype('float32') or source.ndim!=3 or source.shape[-1]!=4:
        raise _fail('FLOAT_GEOMETRY_SURFACE','输入必须是H×W×4 Float32表面')
    if not source.flags.c_contiguous:
        raise _fail('FLOAT_GEOMETRY_SURFACE','输入表面必须连续，禁止隐式整帧复制')
    height,width=source.shape[:2]
    _integer(width,1,MAX_DIMENSION,'输入宽度');_integer(height,1,MAX_DIMENSION,'输入高度')
    if width*height>MAX_PIXELS:
        raise _fail('FLOAT_GEOMETRY_BUDGET','输入表面超过像素预算')
    if not isinstance(output_size,(tuple,list)) or len(output_size)!=2:
        raise _fail('FLOAT_GEOMETRY_ARGUMENT','输出尺寸必须是宽高二元组')
    out_width=_integer(output_size[0],1,MAX_DIMENSION,'输出宽度')
    out_height=_integer(output_size[1],1,MAX_DIMENSION,'输出高度')
    pixels=out_width*out_height
    if pixels>MAX_PIXELS:
        raise _fail('FLOAT_GEOMETRY_BUDGET','输出表面超过像素预算')
    if interpolation not in {'nearest','bilinear'}:
        raise _fail('FLOAT_GEOMETRY_ARGUMENT','只支持明确的nearest或bilinear重采样')
    tile_pixels=_integer(tile_pixels,1,MAX_TILE_PIXELS,'分块像素数')
    max_working_bytes=_integer(max_working_bytes,1,MAX_WORKING_BYTES,'工作区预算')
    try:
        matrix=np.asarray(inverse)
        if matrix.dtype.kind not in 'fiu' or matrix.shape!=(2,3):
            raise ValueError('matrix shape or type')
        matrix=matrix.astype(np.float64)
    except (TypeError,ValueError,OverflowError) as exc:
        raise _fail('FLOAT_GEOMETRY_ARGUMENT','逆矩阵必须是2×3有限数值矩阵') from exc
    if not np.isfinite(matrix).all() or np.max(np.abs(matrix))>1e9:
        raise _fail('FLOAT_GEOMETRY_ARGUMENT','逆矩阵存在非有限值或超出系数预算')
    if matrix[0,0]*matrix[1,1]-matrix[0,1]*matrix[1,0]==0:
        raise _fail('FLOAT_GEOMETRY_ARGUMENT','逆矩阵不可退化')
    # Includes caller-owned input, output and a conservative bound for each
    # chunk's coordinate, gather, product and accumulated arrays. It is not RSS.
    tile=min(tile_pixels,pixels)
    estimated_bytes=int(source.nbytes+pixels*16+max(tile,min(tile_pixels,width*height))*384+4096)
    if estimated_bytes>max_working_bytes:
        raise _fail('FLOAT_GEOMETRY_BUDGET','几何表面及分块估算超过工作区预算')
    source_rows=source.reshape(-1,4)
    for start in range(0,len(source_rows),tile_pixels):
        poll();chunk=source_rows[start:start+tile_pixels]
        if not np.isfinite(chunk).all() or np.any(chunk[:,3]<0) or np.any(chunk[:,3]>1):
            raise _fail('FLOAT_GEOMETRY_SURFACE','输入RGB须有限，覆盖率须在0至1范围')
    output=np.empty((pixels,4),dtype=np.float32)
    for start in range(0,pixels,tile):
        poll();indices=np.arange(start,min(start+tile,pixels),dtype=np.int64)
        y,x=np.divmod(indices,out_width)
        sx=matrix[0,0]*x+matrix[0,1]*y+matrix[0,2]
        sy=matrix[1,0]*x+matrix[1,1]*y+matrix[1,2]
        if interpolation=='nearest':
            ix=np.floor(sx+.5).astype(np.int64);iy=np.floor(sy+.5).astype(np.int64)
            valid=(ix>=0)&(ix<width)&(iy>=0)&(iy<height)
            values=source[np.clip(iy,0,height-1),np.clip(ix,0,width-1)].copy()
            values[~valid]=0;values[values[:,3]==0]=0
            output[start:start+len(indices)]=values
            continue
        # Clip remote coordinates before integer conversion. Every neighbour
        # at these sentinel edges remains outside and contributes zero.
        sx=np.clip(sx,-2,width+1);sy=np.clip(sy,-2,height+1)
        x0=np.floor(sx).astype(np.int64);y0=np.floor(sy).astype(np.int64)
        dx=sx-x0;dy=sy-y0
        premultiplied=np.zeros((len(indices),4),dtype=np.float64)
        for ox,oy,weight in ((0,0,(1-dx)*(1-dy)),(1,0,dx*(1-dy)),
                             (0,1,(1-dx)*dy),(1,1,dx*dy)):
            ix=x0+ox;iy=y0+oy
            valid=(ix>=0)&(ix<width)&(iy>=0)&(iy<height)
            samples=source[np.clip(iy,0,height-1),np.clip(ix,0,width-1)].astype(np.float64)
            samples[:,:3]*=samples[:,3:4]
            samples*=np.where(valid,weight,0)[:,None]
            premultiplied+=samples
        np.divide(premultiplied[:,:3],premultiplied[:,3:4],out=premultiplied[:,:3],
                  where=premultiplied[:,3:4]>0)
        output[start:start+len(indices)]=premultiplied
    poll()
    return output.reshape(out_height,out_width,4),{
        'protocol':PROTOCOL,'surface':'straight-float32-RGBA','interpolation':interpolation,
        'filtering_alpha':'premultiplied-RGB-and-alpha','outside':'transparent-black',
        'pixel_centres':'integer','input_size':[width,height],'output_size':[out_width,out_height],
        'inverse':matrix.tolist(),'tile_pixels':tile,'estimated_working_bytes':estimated_bytes,
        'working_bytes_limit':max_working_bytes,'estimated_bytes_are_peak_RSS':False,
        'colour_space':'caller-supplied-common-space','HDR_accepted':False,'editor_integrated':False,
        'severe_minification_antialiasing_accepted':False}
