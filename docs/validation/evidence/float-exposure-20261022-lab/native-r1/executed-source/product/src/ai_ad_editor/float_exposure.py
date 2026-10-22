"""Native-coefficient exposure on owned linear straight Float32 RGBA tiles.

This independent NumPy implementation uses the public EV/black parameters.
No FFmpeg implementation source or online service is loaded at runtime.
"""
from dataclasses import dataclass
import math

import numpy as np

from .errors import AppError

PROTOCOL = 'linear-float32-native-coefficient-exposure-v1'
MAX_EFFECTS = 128
MAX_TILE_PIXELS = 262144
MAX_PIXELS = 16777216
MAX_WORKING_BYTES = 768*1024**2


def error(code, message):
    return AppError('FLOAT_EXPOSURE_'+code, message, exit_code=2)


def number(value, low, high):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise error('ARGUMENT', '曝光参数必须是有限数字')
    try:
        value = float(value)
    except (ValueError, OverflowError) as caught:
        raise error('ARGUMENT', '曝光参数必须是有限数字') from caught
    if not math.isfinite(value) or not low <= value <= high:
        raise error('ARGUMENT', '曝光参数超出已声明范围')
    return value


@dataclass(frozen=True)
class Exposure:
    amount: float
    black: float
    scale: float
    singular: bool


def compile_effects(effects):
    if not isinstance(effects, list) or len(effects) > MAX_EFFECTS:
        raise error('ARGUMENT', '效果链须为最多128项的数组')
    result = []
    for effect in effects:
        if not isinstance(effect, dict) or type(effect.get('enabled', True)) is not bool:
            raise error('ARGUMENT', '效果声明或enabled无效')
        if effect.get('enabled', True) is False:
            continue
        if effect.get('type') != 'exposure':
            raise AppError('FLOAT_TIMELINE_UNSUPPORTED', '该效果尚未连接浮点时间线', exit_code=2)
        allowed = {'id', 'type', 'enabled', 'parameters', 'amount', 'exposure', 'black'}
        if set(effect)-allowed:
            raise error('ARGUMENT', '浮点曝光尚不支持动态通道或其他未知字段')
        parameters = effect.get('parameters', {k:effect[k] for k in ('amount', 'exposure', 'black') if k in effect})
        if not isinstance(parameters, dict) or set(parameters)-{'amount', 'exposure', 'black'}:
            raise error('ARGUMENT', '曝光parameters包含未知字段')
        if 'parameters' in effect and any(k in effect for k in ('amount', 'exposure', 'black')):
            raise error('ARGUMENT', '曝光参数不能同时位于顶层和parameters')
        if 'amount' in parameters and 'exposure' in parameters and parameters['amount'] != parameters['exposure']:
            raise error('ARGUMENT', 'amount与exposure别名冲突')
        amount = np.float32(number(parameters.get('amount', parameters.get('exposure', 0)), -3, 3))
        black = np.float32(number(parameters.get('black', 0), -1, 1))
        white = np.float32(math.exp2(-float(amount)))
        difference = np.float32(white-black)
        singular = bool(difference == 0)
        scale = np.float32(1024 if singular else 1/float(difference))
        result.append(Exposure(float(amount), float(black), float(scale), singular))
    return tuple(result)


def apply_exposure(surface, plans, *, tile_pixels=65536, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    if cancel is not None and not callable(cancel):
        raise error('ARGUMENT', '取消回调必须可调用')
    poll = cancel if cancel is not None else lambda:None
    poll()
    if not isinstance(surface, np.ndarray) or surface.dtype != np.float32 or surface.ndim != 3 or surface.shape[-1] != 4 or not surface.flags.c_contiguous:
        raise error('SURFACE', '曝光输入须为连续H×W×4 Float32')
    height, width = surface.shape[:2]
    if min(height, width) < 1 or max(height, width) > 16384 or height*width > MAX_PIXELS:
        raise error('BUDGET', '曝光表面超过尺寸预算')
    if type(tile_pixels) is not int or not 1 <= tile_pixels <= MAX_TILE_PIXELS:
        raise error('BUDGET', '曝光分块大小无效')
    if type(max_working_bytes) is not int or not 1 <= max_working_bytes <= MAX_WORKING_BYTES:
        raise error('BUDGET', '曝光工作区预算无效')
    if not isinstance(plans, tuple) or len(plans) > MAX_EFFECTS or any(not isinstance(p, Exposure) for p in plans):
        raise error('ARGUMENT', '曝光须使用已编译计划')
    for p in plans:
        expected = compile_effects([{'type':'exposure', 'parameters':{'amount':p.amount, 'black':p.black}}])[0]
        if p != expected:
            raise error('ARGUMENT', '曝光计划系数与参数不一致')
    pixels = height*width
    estimated = 3*surface.nbytes+min(pixels, tile_pixels)*32+4096
    if estimated > max_working_bytes:
        raise error('BUDGET', '曝光工作区估算超限')
    source = surface.reshape(-1, 4)
    output = np.empty_like(source)
    for start in range(0, pixels, tile_pixels):
        poll()
        end = min(pixels, start+tile_pixels)
        value = source[start:end]
        if not np.isfinite(value).all() or np.any(value[:,3]<0) or np.any(value[:,3]>1):
            raise error('VALUES', '曝光RGB须有限且alpha须在0..1')
        target = output[start:end]
        target[:] = value
        with np.errstate(over='ignore', invalid='ignore'):
            for p in plans:
                poll()
                # Keep two binary32 operations, so the independently tested
                # native coefficient convention has no hidden integer edge.
                np.subtract(target[:,:3], np.float32(p.black), out=target[:,:3])
                np.multiply(target[:,:3], np.float32(p.scale), out=target[:,:3])
        if not np.isfinite(target).all():
            raise error('VALUES', '曝光输出超过Float32有限范围')
    poll()
    return output.reshape(surface.shape), {'protocol':PROTOCOL, 'domain':'linear-straight-RGB',
        'effects':[{'amount':p.amount, 'black':p.black, 'scale':p.scale, 'singular_gain_1024':p.singular} for p in plans],
        'alpha':'input-bits-preserved', 'clipping':'none', 'integer_quantization':False,
        'estimated_working_bytes':estimated, 'estimated_bytes_are_peak_RSS':False,
        'tile_pixels':tile_pixels, 'natural_quality_accepted':False, 'HDR_accepted':False}
