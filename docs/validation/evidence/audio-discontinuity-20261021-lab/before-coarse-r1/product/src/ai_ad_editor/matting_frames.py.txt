"""Validated recurrent inference and straight-alpha packing, independent of ORT."""
from __future__ import annotations

import hashlib
from typing import BinaryIO, Callable

import numpy as np


def read_frame(stream: BinaryIO, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        part = stream.read(size - len(chunks))
        if not part:
            break
        chunks.extend(part)
    if len(chunks) != size:
        raise ValueError('MATTING_INPUT_FRAME_INCOMPLETE')
    return bytes(chunks)


def pack_rgba(foreground, alpha, original_alpha: np.ndarray) -> np.ndarray:
    h, w = original_alpha.shape
    for value, shape in ((foreground, (1, 3, h, w)), (alpha, (1, 1, h, w))):
        if not isinstance(value, np.ndarray) or value.dtype != np.float32 or value.shape != shape or not np.isfinite(value).all():
            raise ValueError('MATTING_MODEL_OUTPUT_INVALID')
        if value.min() < -.001 or value.max() > 1.001:
            raise ValueError('MATTING_MODEL_OUTPUT_RANGE_INVALID')
    result = np.empty((h, w, 4), dtype=np.uint8)
    result[:, :, :3] = np.rint(np.clip(foreground[0].transpose(1, 2, 0), 0, 1) * 255).astype(np.uint8)
    # Foreground is straight RGB. Multiplying RGB here would apply alpha twice.
    result[:, :, 3] = np.rint(np.clip(alpha[0, 0], 0, 1) * original_alpha.astype(np.float32)).astype(np.uint8)
    return result


def process_frames(source: BinaryIO, destination: BinaryIO, *, width: int, height: int,
                   frames: int, infer: Callable, progress: Callable | None = None) -> dict:
    if type(frames) is not int or frames < 1 or min(width, height) < 1 or width * height > 16_777_216:
        raise ValueError('MATTING_FRAME_BUDGET_INVALID')
    states = [np.zeros((1, 1, 1, 1), dtype=np.float32) for _ in range(4)]
    digest = hashlib.sha256()
    transparent = opaque = alpha_sum = state_peak = 0
    alpha_min, alpha_max = 255, 0
    for index in range(frames):
        rgba = np.frombuffer(read_frame(source, width * height * 4), dtype=np.uint8).reshape(height, width, 4)
        rgb = np.ascontiguousarray(rgba[:, :, :3].transpose(2, 0, 1)[None], dtype=np.float32) / 255
        outputs = infer(rgb, states)
        if not isinstance(outputs, (list, tuple)) or len(outputs) != 6:
            raise ValueError('MATTING_MODEL_OUTPUT_CONTRACT_INVALID')
        foreground, alpha, *states = outputs
        for state in states:
            if not isinstance(state, np.ndarray) or state.dtype != np.float32 or state.ndim != 4 or state.shape[0] != 1 or min(state.shape) < 1 or state.nbytes > 128 * 1024 * 1024 or not np.isfinite(state).all():
                raise ValueError('MATTING_RECURRENT_STATE_INVALID')
        state_bytes = sum(s.nbytes for s in states)
        if state_bytes > 256 * 1024 * 1024:
            raise ValueError('MATTING_RECURRENT_STATE_BUDGET_EXCEEDED')
        state_peak = max(state_peak, state_bytes)
        output = pack_rgba(foreground, alpha, rgba[:, :, 3])
        a = output[:, :, 3]
        transparent += int(np.count_nonzero(a == 0))
        opaque += int(np.count_nonzero(a == 255))
        alpha_sum += int(a.sum(dtype=np.uint64))
        alpha_min, alpha_max = min(alpha_min, int(a.min())), max(alpha_max, int(a.max()))
        raw = output.tobytes()
        digest.update(raw)
        destination.write(raw)
        if progress:
            progress(index + 1)
    if source.read(1):
        raise ValueError('MATTING_INPUT_EXTRA_FRAMES')
    destination.flush()
    pixels = width * height * frames
    return {'frames': frames, 'width': width, 'height': height, 'rgba_sha256': 'sha256:' + digest.hexdigest(),
            'rgba_bytes': pixels * 4, 'state_updates': frames, 'state_peak_bytes': state_peak,
            'alpha_min': alpha_min, 'alpha_max': alpha_max, 'alpha_mean': alpha_sum / pixels / 255,
            'transparent_pixels': transparent, 'opaque_pixels': opaque, 'soft_alpha_pixels': pixels - transparent - opaque,
            'alpha_mode': 'straight', 'input_alpha': 'multiply', 'state_reset': 'per-job'}
