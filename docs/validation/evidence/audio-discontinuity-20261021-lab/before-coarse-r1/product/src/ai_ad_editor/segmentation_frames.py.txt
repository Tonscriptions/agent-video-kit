"""Streaming mask union and RGBA packing, independent of Torch."""
from __future__ import annotations

import hashlib
import numpy as np

from .matting_frames import pack_rgba, read_frame


def mask_union(logits: np.ndarray, ids: list[int], selected: list[int], *, mode: str, threshold: float, height: int, width: int) -> np.ndarray:
    if not isinstance(logits, np.ndarray) or logits.dtype != np.float32 or logits.shape != (len(ids), height, width) or not np.isfinite(logits).all() or len(set(ids)) != len(ids):
        raise ValueError('SEGMENTATION_MASK_OUTPUT_INVALID')
    indices = [i for i, oid in enumerate(ids) if oid in selected]
    if not indices:
        return np.zeros((1, 1, height, width), np.float32)
    maximum = logits[indices].max(axis=0) - threshold
    alpha = (maximum > 0).astype(np.float32) if mode == 'binary' else (1 / (1 + np.exp(-np.clip(maximum, -60, 60)))).astype(np.float32)
    return alpha[None, None]


def process_frames(source, destination, *, width: int, height: int, frames: int, prompts: dict, infer, state_budget: int, progress=None) -> dict:
    events = {e['frame']: e for e in prompts['frames']}
    digest = hashlib.sha256()
    transparent = opaque = alpha_sum = state_peak = 0
    alpha_min, alpha_max = 255, 0
    for index in range(frames):
        rgba = np.frombuffer(read_frame(source, width * height * 4), np.uint8).reshape(height, width, 4)
        logits, ids, state_bytes = infer(rgba[:, :, :3], index, events.get(index))
        if type(state_bytes) is not int or not 0 < state_bytes <= state_budget:
            raise ValueError('SEGMENTATION_STATE_BUDGET_EXCEEDED')
        state_peak = max(state_peak, state_bytes)
        alpha = mask_union(logits, ids, prompts['object_ids'], mode=prompts['mask_mode'], threshold=prompts['logit_threshold'], height=height, width=width)
        foreground = np.ascontiguousarray(rgba[:, :, :3].transpose(2, 0, 1)[None], dtype=np.float32) / 255
        packed = pack_rgba(foreground, alpha, rgba[:, :, 3])
        a = packed[:, :, 3]
        transparent += int(np.count_nonzero(a == 0)); opaque += int(np.count_nonzero(a == 255)); alpha_sum += int(a.sum(dtype=np.uint64))
        alpha_min, alpha_max = min(alpha_min, int(a.min())), max(alpha_max, int(a.max()))
        raw = packed.tobytes(); digest.update(raw); destination.write(raw)
        if progress:
            progress(index + 1)
    if source.read(1):
        raise ValueError('SEGMENTATION_INPUT_EXTRA_FRAMES')
    destination.flush()
    pixels = width * height * frames
    return {'frames': frames, 'width': width, 'height': height, 'rgba_sha256': 'sha256:' + digest.hexdigest(), 'rgba_bytes': pixels * 4,
            'state_updates': frames, 'state_peak_bytes': state_peak, 'alpha_min': alpha_min, 'alpha_max': alpha_max, 'alpha_mean': alpha_sum / pixels / 255,
            'transparent_pixels': transparent, 'opaque_pixels': opaque, 'soft_alpha_pixels': pixels - transparent - opaque,
            'alpha_mode': 'straight', 'input_alpha': 'multiply', 'state_reset': 'per-job-and-explicit-frames',
            'prompt_events': len(events), 'explicit_resets': sum(e['reset'] for e in events.values())}
