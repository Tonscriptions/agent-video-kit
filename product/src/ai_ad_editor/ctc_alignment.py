"""Local CTC alignment: source-preserving tokenization, sample grids and Viterbi.

No model or optional numerical library is imported by command discovery.
"""
from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable

from .errors import AppError

SAMPLE_RATE = 16000
MAX_SAMPLES = SAMPLE_RATE * 1800
MAX_CHARACTERS = 16384
MAX_TOKENS = 8192
MAX_STATES = 64000000
MAX_EMISSION_BYTES = 512 * 1024 * 1024


def fail(code: str, message: str, *, exit_code: int = 2) -> AppError:
    return AppError(code, message, exit_code=exit_code)


def read_transcript(path: Path) -> dict[str, Any]:
    if not path.is_file() or not 0 < path.stat().st_size <= 1024 * 1024:
        raise fail('ALIGNMENT_TRANSCRIPT_INVALID', '逐字稿须为不超过 1 MiB 的本地 UTF-8 文本')
    try:
        raw = path.read_text(encoding='utf-8-sig')
    except UnicodeError as exc:
        raise fail('ALIGNMENT_TRANSCRIPT_INVALID', '逐字稿须为有效 UTF-8') from exc
    if path.suffix.lower() not in {'.srt', '.txt'}:
        raise fail('ALIGNMENT_TRANSCRIPT_INVALID', '逐字稿仅支持 .txt 或严格 SRT')
    segments: list[dict[str, Any]] = []
    if path.suffix.lower() == '.srt':
        original: list[str] = []
        cursor = 0
        previous = 0
        clock = r'(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})'
        timing = re.compile(r'^' + clock + r'\s+-->\s+' + clock + r'$')
        for block in re.split(r'\n[ \t]*\n', raw.replace('\r\n', '\n').replace('\r', '\n').strip()):
            lines = block.split('\n')
            if lines and lines[0].strip().isdigit():
                lines = lines[1:]
            match = timing.fullmatch(lines[0].strip()) if lines else None
            if not match or len(lines) < 2:
                raise fail('ALIGNMENT_TRANSCRIPT_INVALID', 'SRT 存在无效或被忽略的段落')
            values = [int(v) for v in match.groups()]
            def sample(v: list[int]) -> int:
                return ((v[0] * 3600 + v[1] * 60 + v[2]) * 1000 + v[3]) * 16
            start, end = sample(values[:4]), sample(values[4:])
            text = '\n'.join(lines[1:])
            if not text.strip() or start < previous or end <= start or end > MAX_SAMPLES:
                raise fail('ALIGNMENT_TRANSCRIPT_INVALID', 'SRT 文本为空、时间重叠或超出资源范围')
            if original:
                cursor += 1
            segments.append({'text': text, 'start_char': cursor, 'end_char': cursor + len(text),
                             'start_sample': start, 'end_sample': end})
            original.append(text)
            cursor += len(text)
            previous = end
        text = '\n'.join(original)
    else:
        text = raw
        segments = [{'text': text, 'start_char': 0, 'end_char': len(text),
                     'start_sample': 0, 'end_sample': None}]
    if not text.strip() or len(text) > MAX_CHARACTERS or len(segments) > 256:
        raise fail('ALIGNMENT_TEXT_BUDGET_EXCEEDED', '逐字稿最多 16384 码点、256 个 SRT 段落，且不能为空')
    return {'original_text': text, 'original_file_text': raw, 'format': path.suffix[1:].lower(),
            'index_basis': 'original_text-unicode-codepoints', 'segments': segments}


def map_text(text: str, vocab: dict[str, int], blank: int, *, case: str = 'upper', offset: int = 0) -> dict[str, Any]:
    if case not in {'upper', 'lower', 'preserve'}:
        raise fail('ALIGNMENT_CASE_INVALID', 'case 只能为 upper/lower/preserve')
    tokens, ignored = [], []
    for i, char in enumerate(text):
        if char.isspace() or unicodedata.category(char).startswith('P'):
            ignored.append({'start_char': offset + i, 'end_char': offset + i + 1,
                            'text': char, 'reason': 'whitespace' if char.isspace() else 'punctuation'})
            continue
        token = getattr(char, case)() if case != 'preserve' else char
        if len(token) != 1 or token not in vocab or vocab[token] == blank:
            raise fail('ALIGNMENT_OOV_CHARACTER', f'原文码点 {offset + i} 的字符不在词表内: {char!r}')
        tokens.append({'text': char, 'token': token, 'token_id': vocab[token],
                       'start_char': offset + i, 'end_char': offset + i + 1})
    if not tokens or len(tokens) > MAX_TOKENS:
        raise fail('ALIGNMENT_TOKEN_BUDGET_EXCEEDED', '有效声学 token 必须为 1–8192 个')
    return {'tokens': tokens, 'ignored': ignored}


def conv_grid(config: dict[str, Any]) -> tuple[int, int]:
    kernels, strides = config.get('conv_kernel'), config.get('conv_stride')
    if not isinstance(kernels, list) or not isinstance(strides, list) or not 1 <= len(kernels) == len(strides) <= 16:
        raise fail('ALIGNMENT_MODEL_GRID_INVALID', '缺少明确的 Wav2Vec2 卷积时钟', exit_code=10)
    stride, receptive = 1, 1
    for k, s in zip(kernels, strides):
        if type(k) is not int or type(s) is not int or not 1 <= k <= 64 or not 1 <= s <= 64:
            raise fail('ALIGNMENT_MODEL_GRID_INVALID', '卷积时钟参数无效', exit_code=10)
        receptive += (k - 1) * stride
        stride *= s
    if stride > 16000 or receptive > 16000 or receptive < stride or config.get('add_adapter'):
        raise fail('ALIGNMENT_MODEL_GRID_INVALID', '不支持额外下采样或大于一秒的卷积时钟', exit_code=10)
    return stride, receptive


def output_frames(samples: int, stride: int, receptive: int) -> int:
    # Keep only Voronoi cells that intersect real samples. The first/last
    # cells extend to the recording edges; padding never adds a zero-size cell.
    centered_offset = (receptive - stride) // 2
    return max(1, (max(0, samples - centered_offset) + stride - 1) // stride)


def frame_windows(samples: int, stride: int, receptive: int, *, window_samples: int, context_samples: int) -> list[dict[str, int]]:
    if type(samples) is not int or not 1 <= samples <= MAX_SAMPLES:
        raise fail('ALIGNMENT_AUDIO_BUDGET_EXCEEDED', '实际音频须为 1 样本至 1800 秒')
    if not receptive <= context_samples or not 0 < window_samples <= 30 * SAMPLE_RATE:
        raise fail('ALIGNMENT_WINDOW_INVALID', '窗口最多 30 秒，上下文不得小于模型感受野')
    maximum = (window_samples - receptive) // stride + 1
    context = (context_samples + stride - 1) // stride
    core = maximum - 2 * context
    if core < 1:
        raise fail('ALIGNMENT_WINDOW_INVALID', '窗口不足以容纳两侧上下文和一个输出格')
    frames = output_frames(samples, stride, receptive)
    windows = []
    for start in range(0, frames, core):
        stop = min(frames, start + core)
        left, right = max(0, start - context), min(frames, stop + context)
        windows.append({'core_start': start, 'core_end': stop, 'frame_start': left, 'frame_end': right,
                        'sample_start': left * stride, 'sample_end': (right - 1) * stride + receptive,
                        'right_zero_pad': max(0, (right - 1) * stride + receptive - samples)})
    return windows


def frame_boundary(frame: int, frames: int, samples: int, stride: int, receptive: int) -> int:
    if frame == 0:
        return 0
    if frame == frames:
        return samples
    return min(samples, max(0, frame * stride + (receptive - stride) // 2))


def viterbi(log_probs: Any, token_ids: list[int], blank: int, *, checkpoint: Callable[[], None] = lambda: None) -> dict[str, Any]:
    """Full expanded-label CTC. uint8 predecessors bound traceback memory."""
    import numpy as np
    scores = np.asarray(log_probs)
    if scores.ndim != 2 or scores.dtype.kind != 'f' or not token_ids or len(token_ids) > MAX_TOKENS:
        raise fail('ALIGNMENT_EMISSIONS_INVALID', 'CTC 数组或目标 token 无效')
    frames, vocab_size = scores.shape
    if not 0 <= blank < vocab_size or any(type(v) is not int or not 0 <= v < vocab_size or v == blank for v in token_ids):
        raise fail('ALIGNMENT_EMISSIONS_INVALID', 'CTC token/blank 超出数组范围')
    if np.isnan(scores).any() or np.isposinf(scores).any() or np.any(scores > 1e-5):
        raise fail('ALIGNMENT_EMISSIONS_INVALID', 'CTC 必须为无 NaN/+inf 的对数后验')
    state_count = 2 * len(token_ids) + 1
    if frames * state_count > MAX_STATES or scores.nbytes > MAX_EMISSION_BYTES:
        raise fail('ALIGNMENT_DP_BUDGET_EXCEEDED', 'CTC 回溯或声学数组超过声明预算')
    if frames < len(token_ids) + sum(a == b for a, b in zip(token_ids, token_ids[1:])):
        raise fail('ALIGNMENT_UNREACHABLE', '输出格不足以对齐目标及重复字符', exit_code=6)
    labels = np.full(state_count, blank, dtype=np.int64)
    labels[1::2] = token_ids
    skip = np.zeros(state_count, dtype=bool)
    skip[2:] = (labels[2:] != blank) & (labels[2:] != labels[:-2])
    previous = np.full(state_count, -np.inf, dtype=np.float64)
    previous[:2] = scores[0, labels[:2]]
    trace = np.zeros((frames, state_count), dtype=np.uint8)
    for t in range(1, frames):
        if t % 64 == 0:
            checkpoint()
        best = previous.copy()
        one = np.r_[-np.inf, previous[:-1]]
        two = np.r_[-np.inf, -np.inf, previous[:-2]]
        use = one > best
        best[use] = one[use]
        trace[t, use] = 1
        use = skip & (two > best)
        best[use] = two[use]
        trace[t, use] = 2
        previous = best + scores[t, labels]
    last = state_count - 1 if previous[-1] >= previous[-2] else state_count - 2
    total = float(previous[last])
    if not math.isfinite(total):
        raise fail('ALIGNMENT_UNREACHABLE', '目标文本不存在可达 CTC 路径', exit_code=6)
    path = np.empty(frames, dtype=np.int32)
    for t in range(frames - 1, -1, -1):
        path[t] = last
        if t:
            last -= int(trace[t, last])
    aligned = []
    for i, token in enumerate(token_ids):
        hit = np.flatnonzero(path == 2 * i + 1)
        if not hit.size:
            raise fail('ALIGNMENT_UNREACHABLE', 'CTC 回溯未覆盖原文 token', exit_code=6)
        aligned.append({'token_id': token, 'start_frame': int(hit[0]), 'end_frame': int(hit[-1]) + 1,
                        'posterior_geometric_mean': math.exp(float(scores[hit, token].mean()))})
    return {'tokens': aligned, 'path_log_probability': total, 'frames': frames,
            'state_cells': frames * state_count, 'traceback_bytes': int(trace.nbytes)}


def timed_units(text: str, characters: list[dict[str, Any]], *, offset: int, granularity: str) -> list[dict[str, Any]]:
    if granularity == 'character':
        spans = [(c['start_char'], c['end_char']) for c in characters]
    elif granularity == 'whitespace':
        spans = [(offset + m.start(), offset + m.end()) for m in re.finditer(r'\S+', text)]
    else:
        raise fail('ALIGNMENT_GRANULARITY_INVALID', '粒度仅支持 character 或 whitespace')
    units = []
    for start, end in spans:
        members = [c for c in characters if start <= c['start_char'] < end]
        if not members:
            continue
        units.append({'text': text[start-offset:end-offset], 'start_char': start, 'end_char': end,
                      'start_sample': members[0]['start_sample'], 'end_sample': members[-1]['end_sample'],
                      'posterior_geometric_mean': math.exp(sum(math.log(max(c['posterior_geometric_mean'], 1e-300)) for c in members) / len(members))})
    return units
