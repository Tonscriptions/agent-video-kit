"""Bounded framewise masked repair, preserving outside RGB and source alpha."""
from __future__ import annotations

import hashlib
from typing import BinaryIO, Callable

import numpy as np
from PIL import Image, ImageFilter

from .matting_frames import read_frame


def repair_frame(source: np.ndarray, mask_rgba: np.ndarray, *, options: dict, channel: str,
                 infer: Callable, budget: int) -> tuple[np.ndarray, dict]:
    if source.dtype != np.uint8 or source.ndim != 3 or source.shape[2] != 4 or mask_rgba.shape != source.shape or mask_rgba.dtype != np.uint8:
        raise ValueError('INPAINT_FRAME_SHAPE_INVALID')
    if channel == 'alpha':
        values = mask_rgba[:, :, 3].astype(np.float32)
    elif channel == 'luma':
        values = np.einsum('ijk,k->ij', mask_rgba[:, :, :3], np.array([.2126, .7152, .0722], dtype=np.float32))
    else:
        raise ValueError('INPAINT_MASK_CHANNEL_INVALID')
    selected = values > options['threshold'] * 255
    if options['grow']:
        selected = np.asarray(Image.fromarray(selected.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(options['grow'] * 2 + 1))) != 0
    count = int(np.count_nonzero(selected))
    output = source.copy()
    owned = source.size * 2 + mask_rgba.size + values.nbytes + selected.nbytes + output.nbytes
    if owned > budget:
        raise ValueError('INPAINT_FRAME_BUFFER_BUDGET_EXCEEDED')
    info = {'mask_pixels': count, 'model_calls': 0, 'resized': False, 'model_pixels': 0,
            'state_bytes': owned, 'roi': None, 'outside_mask_changed_pixels': 0}
    if count == 0:
        return output, info
    ys, xs = np.flatnonzero(selected.any(axis=1)), np.flatnonzero(selected.any(axis=0))
    h, w = selected.shape
    context = options['context']
    x1, y1 = max(0, int(xs.min()) - context), max(0, int(ys.min()) - context)
    x2, y2 = min(w, int(xs.max()) + 1 + context), min(h, int(ys.max()) + 1 + context)
    roi_w, roi_h = x2 - x1, y2 - y1
    scale = min(1., options['model_max_edge'] / max(roi_w, roi_h))
    mw, mh = max(1, round(roi_w * scale)), max(1, round(roi_h * scale))
    pw, ph = max(64, (mw + 7) // 8 * 8), max(64, (mh + 7) // 8 * 8)
    # Account for owned frame arrays, model inputs/output and resized blending
    # buffers. This is a buffer budget, not total Torch RAM/VRAM or model memory.
    owned += pw * ph * 7 * 4 + roi_w * roi_h * 7 * 4 + w * h * 4 + xs.nbytes + ys.nbytes
    if owned > budget:
        raise ValueError('INPAINT_FRAME_BUFFER_BUDGET_EXCEEDED')
    rgb = np.asarray(Image.fromarray(source[y1:y2, x1:x2, :3]).resize((mw, mh), Image.Resampling.BILINEAR))
    mask = np.asarray(Image.fromarray(selected[y1:y2, x1:x2].astype(np.uint8) * 255).resize((mw, mh), Image.Resampling.NEAREST))
    if not np.any(mask):
        raise ValueError('INPAINT_MASK_LOST_DURING_RESIZE_INCREASE_MODEL_MAX_EDGE_OR_REDUCE_CONTEXT')
    rgb = np.pad(rgb, ((0, ph - mh), (0, pw - mw), (0, 0)), mode='edge')
    mask = np.pad(mask, ((0, ph - mh), (0, pw - mw)), mode='edge')
    image_tensor = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None], dtype=np.float32) / 255
    mask_tensor = np.ascontiguousarray(mask[None, None], dtype=np.float32) / 255
    predicted = infer(image_tensor, mask_tensor)
    if not isinstance(predicted, np.ndarray) or predicted.dtype != np.float32 or predicted.shape != (1, 3, ph, pw) or not np.isfinite(predicted).all():
        raise ValueError('INPAINT_MODEL_OUTPUT_INVALID')
    # LaMa may overshoot 0..1 slightly; clipping is explicit and counted.
    clipped = int(np.count_nonzero((predicted < 0) | (predicted > 1)))
    generated = np.rint(np.clip(predicted[0, :, :mh, :mw].transpose(1, 2, 0), 0, 1) * 255).astype(np.uint8)
    generated = np.asarray(Image.fromarray(generated).resize((roi_w, roi_h), Image.Resampling.BILINEAR))
    weight = selected[y1:y2, x1:x2].astype(np.float32)
    if options['feather']:
        feathered = np.asarray(Image.fromarray(selected.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(options['feather'])), dtype=np.float32) / 255
        weight *= feathered[y1:y2, x1:x2]
    original = source[y1:y2, x1:x2, :3].astype(np.float32)
    output[y1:y2, x1:x2, :3] = np.rint(original * (1 - weight[:, :, None]) + generated.astype(np.float32) * weight[:, :, None]).astype(np.uint8)
    changed_outside = int(np.count_nonzero(np.any(output[:, :, :3] != source[:, :, :3], axis=2) & ~selected))
    if changed_outside or not np.array_equal(output[:, :, 3], source[:, :, 3]):
        raise ValueError('INPAINT_UNMASKED_OR_ALPHA_CHANGED')
    info.update(model_calls=1, resized=scale < 1, model_pixels=pw * ph, state_bytes=owned,
                roi=[x1, y1, x2, y2], clipped_model_values=clipped, outside_mask_changed_pixels=changed_outside)
    return output, info


def process_frames(source: BinaryIO, destination: BinaryIO, *, width: int, height: int,
                   frames: int, infer: Callable, options: dict, channel: str,
                   budget: int = 512 * 1024**2, progress: Callable | None = None) -> dict:
    if any(type(v) is not int or v < 1 for v in (width, height, frames, budget)) or width * height > 16_777_216:
        raise ValueError('INPAINT_FRAME_BUDGET_INVALID')
    digest, source_digest, mask_digest = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
    original_alpha, output_alpha = hashlib.sha256(), hashlib.sha256()
    calls = masked = resized = model_peak = state_peak = transparent = opaque = alpha_sum = clipped = 0
    alpha_min, alpha_max = 255, 0
    samples = []
    for index in range(frames):
        pair = np.frombuffer(read_frame(source, width * 2 * height * 4), dtype=np.uint8).reshape(height, width * 2, 4)
        original, mask = pair[:, :width], pair[:, width:]
        output, metrics = repair_frame(original, mask, options=options, channel=channel, infer=infer, budget=budget)
        raw = output.tobytes()
        digest.update(raw); source_digest.update(original.tobytes()); mask_digest.update(mask.tobytes())
        original_alpha.update(original[:, :, 3].tobytes()); output_alpha.update(output[:, :, 3].tobytes())
        calls += metrics['model_calls']; masked += metrics['mask_pixels']; resized += int(metrics['resized'])
        clipped += metrics.get('clipped_model_values', 0)
        model_peak = max(model_peak, metrics['model_pixels']); state_peak = max(state_peak, metrics['state_bytes'])
        if len(samples) < 16: samples.append({'frame': index, **metrics})
        a = output[:, :, 3]
        transparent += int(np.count_nonzero(a == 0)); opaque += int(np.count_nonzero(a == 255)); alpha_sum += int(a.sum(dtype=np.uint64))
        alpha_min, alpha_max = min(alpha_min, int(a.min())), max(alpha_max, int(a.max()))
        destination.write(raw)
        if progress: progress(index + 1)
    if source.read(1): raise ValueError('INPAINT_INPUT_EXTRA_FRAMES')
    destination.flush()
    pixels = width * height * frames
    return {'frames': frames, 'width': width, 'height': height, 'rgba_sha256': 'sha256:' + digest.hexdigest(),
            'rgba_bytes': pixels * 4, 'source_rgba_sha256': 'sha256:' + source_digest.hexdigest(), 'decoded_mask_rgba_sha256': 'sha256:' + mask_digest.hexdigest(),
            'state_updates': frames, 'state_peak_bytes': state_peak, 'state_reset': 'per-frame',
            'buffer_budget_scope': 'conservative-owned-frame-and-input-output-arrays-excludes-model-and-torch-temporaries',
            'input_alpha': 'preserve', 'alpha_mode': 'straight', 'alpha_min': alpha_min, 'alpha_max': alpha_max, 'alpha_mean': alpha_sum / pixels / 255,
            'transparent_pixels': transparent, 'opaque_pixels': opaque, 'soft_alpha_pixels': pixels - transparent - opaque,
            'input_alpha_sha256': 'sha256:' + original_alpha.hexdigest(), 'output_alpha_sha256': 'sha256:' + output_alpha.hexdigest(),
            'model_calls': calls, 'empty_mask_frames': frames - calls, 'mask_pixels': masked, 'resized_model_frames': resized,
            'model_peak_pixels': model_peak, 'outside_mask_changed_pixels': 0, 'clipped_model_values': clipped, 'roi_samples': samples}
