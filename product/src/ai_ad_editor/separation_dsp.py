"""Bounded-memory overlap/add for explicitly supplied local separation models."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Callable


def segment_ranges(samples: int, window: int, overlap: float) -> list[tuple[int,int]]:
    if type(samples) is not int or samples <= 0 or type(window) is not int or window < 1 or not math.isfinite(overlap) or not 0 <= overlap <= .75:
        raise ValueError('Invalid segmentation settings')
    hop = max(1,window-round(window*overlap))
    ranges = []
    for start in range(0,samples,hop):
        end = min(samples,start+window)
        ranges.append((start,end))
        if end == samples:
            break
    return ranges


def separate_pcm(source: Path, vocals: Path, accompaniment: Path, *, window: int, overlap: float, infer: Callable) -> dict:
    """infer accepts normalized (2, window) float32 and returns vocal estimates.

    Float32 memmaps hold the source, accumulator and output; only a segment
    and the model occupy working RAM. Accompaniment is the source residual,
    preserving mixture consistency without independent stem normalization.
    """
    import numpy as np
    size = source.stat().st_size
    if not size or size % 8:
        raise ValueError('Expected nonempty interleaved float32 stereo PCM')
    count = size//8
    ranges = segment_ranges(count,window,overlap)
    mixture = np.memmap(source,dtype='<f4',mode='r',shape=(count,2))
    # The mono reference follows the model's normalization convention. An
    # antiphase stereo signal needs a full-channel variance fallback.
    sum_ref = sum_ref2 = sum_all2 = 0.0
    peak = 0.0
    try:
        for start in range(0,count,262144):
            block = np.asarray(mixture[start:start+262144],dtype=np.float64)
            if not np.isfinite(block).all():
                raise ValueError('Nonfinite decoded audio')
            ref = block.mean(axis=1)
            sum_ref += float(ref.sum()); sum_ref2 += float((ref*ref).sum())
            sum_all2 += float((block*block).sum()); peak = max(peak,float(np.abs(block).max()))
    except BaseException:
        mixture._mmap.close()
        raise
    mean = sum_ref/count
    std = math.sqrt(max(0,sum_ref2/count-mean*mean))
    if std < 1e-8:
        std = math.sqrt(max(0,sum_all2/(count*2)-mean*mean))
    std = max(std,1e-8)
    output = weights = residual = None
    weight_path = vocals.with_suffix('.weights.f32')
    calls = 0
    try:
        output = np.memmap(vocals,dtype='<f4',mode='w+',shape=(count,2)); output[:] = 0
        weights = np.memmap(weight_path,dtype='<f4',mode='w+',shape=(count,)); weights[:] = 0
        if peak:
            indices = np.arange(window,dtype=np.float32)
            triangle = np.minimum(indices+1,window-indices)
            triangle /= triangle.max()
            for start,end in ranges:
                length = end-start
                chunk = np.zeros((2,window),dtype=np.float32)
                chunk[:,:length] = (mixture[start:end].T-mean)/std
                estimate = np.asarray(infer(chunk),dtype=np.float32)
                calls += 1
                if estimate.shape != (2,window) or not np.isfinite(estimate).all():
                    raise ValueError('Invalid model vocal shape or nonfinite samples')
                # Share removed DC equally across the four model sources.
                vocal = estimate[:,:length].T*std+mean/4
                weight = triangle[:length]
                output[start:end] += vocal*weight[:,None]
                weights[start:end] += weight
        else:
            weights[:] = 1
        residual = np.memmap(accompaniment,dtype='<f4',mode='w+',shape=(count,2))
        peaks = {'vocals':0.0,'accompaniment':0.0}
        max_error = 0.0
        for start in range(0,count,262144):
            end = min(count,start+262144)
            w = np.asarray(weights[start:end])
            if not (w > 0).all():
                raise ValueError('Uncovered samples in overlap/add')
            output[start:end] /= w[:,None]
            residual[start:end] = mixture[start:end]-output[start:end]
            for key,data in (('vocals',output[start:end]),('accompaniment',residual[start:end])):
                if not np.isfinite(data).all():
                    raise ValueError('Nonfinite separated output')
                peaks[key] = max(peaks[key],float(np.abs(data).max()))
            max_error = max(max_error,float(np.abs(output[start:end]+residual[start:end]-mixture[start:end]).max()))
        output.flush(); residual.flush()
        return {'samples':count,'channels':2,'segments':len(ranges),'model_calls':calls,'normalization_mean':mean,'normalization_std':std,'mixture_max_abs_error':max_error,'peaks':peaks,'accompaniment_method':'mixture_minus_model_vocals','silence_fast_path':peak==0}
    finally:
        # Close mappings explicitly: Windows cannot unlink an open mapping.
        for mapping in (mixture,output,weights,residual):
            if mapping is not None:
                mapping._mmap.close()
        weight_path.unlink(missing_ok=True)
