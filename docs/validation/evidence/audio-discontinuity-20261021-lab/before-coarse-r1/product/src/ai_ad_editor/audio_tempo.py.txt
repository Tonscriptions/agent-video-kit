"""Source-contained context for the approximate, native FFmpeg tempo path.

The integrated output anchors stay unchanged. Context warms up each WSOLA
instance before selecting its core; it is never taken outside the authored
source selection. This is not a continuous phase or perceptual-quality claim.
"""
from __future__ import annotations

import math
from .errors import AppError

SAMPLE_RATE = 48000
# At 48 kHz native atempo uses a 2048-sample window. Four windows bound the
# chosen context policy, scaled on the input side for accelerated chains.
# This is a policy, not a proof that arbitrary/extremely short content can
# provide sufficient WSOLA history or preserve pitch and phase.
CONTEXT_FRAMES = 8192
MAX_TERMINAL_CONTEXT_PCM_BYTES = 64 * 1024 * 1024


def context_windows(parts, source_frames: int, *, target_samples: int | None = None,
                    channels: int = 2) -> list[dict]:
    parts = list(parts)
    windows = []
    previous_output_end = 0
    for index, (left, right, speed, cumulative_end) in enumerate(parts):
        speed = float(speed)
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError('audio tempo must be finite and positive')
        core_start = max(0, min(source_frames, round(left * SAMPLE_RATE)))
        core_end = max(core_start, min(source_frames, round(right * SAMPLE_RATE)))
        output_end = round(cumulative_end * SAMPLE_RATE)
        if index == len(parts)-1 and target_samples is not None:
            output_end = target_samples
        output_frames = max(1, output_end - previous_output_end)
        # Unity is an actual identity: do not insert a WSOLA stage just to
        # trim context, including the retained 4-ms regression fixture.
        guard = 0 if abs(speed - 1.) <= 1e-9 else math.ceil(CONTEXT_FRAMES * max(1., speed))
        start = max(0, core_start - guard)
        end = min(source_frames, core_end + guard)
        trim_start = round((core_start - start) / speed)
        end_aligned = index == len(parts)-1 and guard > 0
        estimated_bytes = (math.ceil((end-start)/speed)+CONTEXT_FRAMES)*max(1,channels)*4 if end_aligned else 0
        if estimated_bytes > MAX_TERMINAL_CONTEXT_PCM_BYTES:
            raise AppError('AUDIO_TEMPO_CONTEXT_LIMIT',
                           '末端变速上下文的预估 float32 PCM 超过 64 MiB；请拆分选区或减少嵌套慢速倍率',
                           exit_code=2, path='audio_tempo_context',
                           cause=f'estimated_terminal_pcm_bytes={estimated_bytes}; budget_bytes={MAX_TERMINAL_CONTEXT_PCM_BYTES}')
        windows.append({
            'core_start_sample': core_start, 'core_end_sample': core_end,
            'context_start_sample': start, 'context_end_sample': end,
            'requested_guard_samples': guard, 'tempo': speed,
            'output_selection': 'last-retimed-samples' if end_aligned else 'nominal-source-offset',
            'estimated_terminal_pcm_bytes': estimated_bytes,
            'nominal_retimed_core_start_sample': trim_start,
            'nominal_retimed_core_end_sample': trim_start + output_frames,
            # Native WSOLA may return a slightly different total length.
            # The final core retains its actual terminal signal instead of
            # starting at a guessed offset and padding a discarded tail.
            'retimed_trim_start_sample': None if end_aligned else trim_start,
            'retimed_trim_end_sample': None if end_aligned else trim_start + output_frames,
            'output_start_sample': previous_output_end,
            'output_end_sample': previous_output_end + output_frames,
            'output_samples': output_frames,
        })
        previous_output_end += output_frames
    return windows
