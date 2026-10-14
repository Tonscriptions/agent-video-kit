from __future__ import annotations

import copy
import math
from typing import Any

from .errors import AppError, argument_error


SMART_CUT_VERSION = "0.1.0"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _merge_ranges(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if merged and start <= merged[-1][1] + 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def build_smart_cut_plan(
    analysis: dict[str, Any],
    *,
    duration_seconds: float,
    min_silence_seconds: float = 0.6,
    keep_padding_seconds: float = 0.12,
    min_segment_seconds: float = 0.2,
) -> dict[str, Any]:
    """Build a deterministic silence-removal plan from local FFmpeg evidence.

    The plan removes only silence intervals that exceed the configured minimum,
    keeps a small amount of room tone at both edges, and never calls a hosted
    VAD or language service.  The returned ranges use the source clip clock.
    """
    duration = max(0.0, _number(duration_seconds))
    minimum_silence = max(0.05, _number(min_silence_seconds, 0.6))
    padding = max(0.0, _number(keep_padding_seconds, 0.12))
    minimum_segment = max(0.0, _number(min_segment_seconds, 0.2))
    silence = analysis.get("silence") if isinstance(analysis.get("silence"), dict) else {}
    starts = silence.get("starts") if isinstance(silence.get("starts"), list) else []
    ends = silence.get("ends") if isinstance(silence.get("ends"), list) else []
    candidates: list[tuple[float, float]] = []
    unmatched_end = False
    for index, raw_start in enumerate(starts):
        start = max(0.0, min(duration, _number(raw_start)))
        if index < len(ends):
            end = max(start, min(duration, _number(ends[index], duration)))
        else:
            end = duration
            unmatched_end = True
        if end - start < minimum_silence:
            continue
        cut_start = min(duration, start + padding)
        cut_end = max(0.0, end - padding)
        if cut_end - cut_start >= max(0.01, minimum_segment):
            candidates.append((cut_start, cut_end))
    cuts = _merge_ranges(candidates)
    kept: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in cuts:
        if start - cursor > 1e-6:
            kept.append((cursor, start))
        cursor = max(cursor, end)
    if duration - cursor > 1e-6:
        kept.append((cursor, duration))
    kept = [(start, end) for start, end in kept if end - start >= max(1.0 / 90000.0, minimum_segment)]
    if not kept and duration > 0:
        kept = [(0.0, duration)]
        cuts = []
    removed_seconds = sum(end - start for start, end in cuts)
    warnings: list[dict[str, Any]] = []
    if unmatched_end:
        warnings.append({
            "code": "SMART_CUT_UNCLOSED_SILENCE",
            "message": "FFmpeg 只报告了 silence_start，末尾静音按素材结束时间闭合",
        })
    if not cuts:
        warnings.append({
            "code": "SMART_CUT_NO_REMOVABLE_SILENCE",
            "message": "没有满足最小时长和保留边界的静音区间，保持原片段",
        })
    return {
        "smart_cut_version": SMART_CUT_VERSION,
        "engine": "ffmpeg-local-silencedetect-v1",
        "network": "disabled",
        "duration_seconds": round(duration, 6),
        "parameters": {
            "min_silence_seconds": round(minimum_silence, 6),
            "keep_padding_seconds": round(padding, 6),
            "min_segment_seconds": round(minimum_segment, 6),
        },
        "kept_ranges": [
            {"start_seconds": round(start, 6), "end_seconds": round(end, 6), "duration_seconds": round(end - start, 6)}
            for start, end in kept
        ],
        "removed_ranges": [
            {"start_seconds": round(start, 6), "end_seconds": round(end, 6), "duration_seconds": round(end - start, 6)}
            for start, end in cuts
        ],
        "removed_seconds": round(removed_seconds, 6),
        "output_duration_seconds": round(max(0.0, duration - removed_seconds), 6),
        "changed": bool(cuts),
        "warnings": warnings,
        "source_analysis": {
            "analysis_version": analysis.get("analysis_version"),
            "source_sha256": analysis.get("source_sha256"),
            "silence_noise_db": silence.get("noise_db"),
        },
    }


def _sample_keyframes(points: list[dict[str, Any]], at_tick: int) -> Any:
    ordered = sorted(
        [item for item in points if isinstance(item, dict)],
        key=lambda item: int(item.get("at_tick", 0)),
    )
    if not ordered:
        return None
    if at_tick <= int(ordered[0].get("at_tick", 0)):
        return copy.deepcopy(ordered[0].get("value"))
    if at_tick >= int(ordered[-1].get("at_tick", 0)):
        return copy.deepcopy(ordered[-1].get("value"))
    for left, right in zip(ordered, ordered[1:]):
        left_at = int(left.get("at_tick", 0))
        right_at = int(right.get("at_tick", left_at))
        if left_at <= at_tick <= right_at:
            left_value = left.get("value")
            right_value = right.get("value")
            try:
                ratio = (at_tick - left_at) / max(1, right_at - left_at)
                return float(left_value) + (float(right_value) - float(left_value)) * ratio
            except (TypeError, ValueError):
                return copy.deepcopy(left_value)
    return copy.deepcopy(ordered[-1].get("value"))


def _slice_keyframes(keyframe_tracks: Any, start_tick: int, end_tick: int) -> list[dict[str, Any]]:
    if not isinstance(keyframe_tracks, list):
        return []
    sliced: list[dict[str, Any]] = []
    for track in keyframe_tracks:
        if not isinstance(track, dict) or not isinstance(track.get("keyframes"), list):
            continue
        points = [item for item in track["keyframes"] if isinstance(item, dict)]
        if not points:
            continue
        selected = [copy.deepcopy(item) for item in points if start_tick <= int(item.get("at_tick", 0)) <= end_tick]
        for boundary in (start_tick, end_tick):
            if not any(int(item.get("at_tick", 0)) == boundary for item in points):
                value = _sample_keyframes(points, boundary)
                if value is not None:
                    selected.append({"at_tick": boundary, "value": value, "interpolation": "linear"})
        selected.sort(key=lambda item: int(item.get("at_tick", 0)))
        deduplicated: list[dict[str, Any]] = []
        seen: set[int] = set()
        for item in selected:
            absolute = int(item.get("at_tick", 0))
            if absolute in seen:
                continue
            seen.add(absolute)
            mapped = copy.deepcopy(item)
            mapped["at_tick"] = absolute - start_tick
            deduplicated.append(mapped)
        if deduplicated:
            mapped_track = copy.deepcopy(track)
            mapped_track["keyframes"] = deduplicated
            sliced.append(mapped_track)
    return sliced


def slice_clip(clip: dict[str, Any], ranges: list[dict[str, Any]], *, ticks_per_second: int) -> list[dict[str, Any]]:
    """Create source-bounded clip pieces while preserving local automation."""
    if clip.get("sequence_id"):
        raise AppError("SMART_CUT_NESTED_UNSUPPORTED", "智能剪口播当前只允许直接媒体片段，不会隐式改写嵌套序列", exit_code=2, path="clip.sequence_id")
    if clip.get("speed_curve") is not None:
        raise AppError("SMART_CUT_SPEED_CURVE_UNSUPPORTED", "智能剪口播当前不对 speed_curve 片段做近似切片，请先烘焙或改为常速片段", exit_code=2, path="clip.speed_curve")
    if clip.get("freeze") is not None:
        raise AppError("SMART_CUT_FREEZE_UNSUPPORTED", "智能剪口播当前不对含 freeze 的片段做近似切片", exit_code=2, path="clip.freeze")
    original_duration = max(1, int(clip.get("duration_tick", 1)))
    source_in = int(clip.get("source_in_tick", 0))
    source_out = int(clip.get("source_out_tick", source_in + original_duration))
    source_span = max(1, source_out - source_in)
    speed = _number(clip.get("speed", 1.0), 1.0)
    if speed <= 0:
        raise argument_error("智能剪口播要求 speed 大于 0", "clip.speed")
    clip_start = int(clip.get("timeline_start_tick", 0))
    pieces: list[dict[str, Any]] = []
    output_offset = 0
    for index, value in enumerate(ranges, start=1):
        start_seconds = max(0.0, _number(value.get("start_seconds")))
        end_seconds = max(start_seconds, _number(value.get("end_seconds")))
        start_tick = max(0, min(original_duration, int(round(start_seconds * ticks_per_second))))
        end_tick = max(start_tick, min(original_duration, int(round(end_seconds * ticks_per_second))))
        if end_tick <= start_tick:
            continue
        source_delta_start = int(round(start_tick * speed))
        source_delta_end = int(round(end_tick * speed))
        if bool(clip.get("reverse")):
            piece_source_in = source_out - source_delta_end
            piece_source_out = source_out - source_delta_start
        else:
            piece_source_in = source_in + source_delta_start
            piece_source_out = source_in + source_delta_end
        piece_source_in = max(source_in, min(source_out - 1, piece_source_in))
        piece_source_out = max(piece_source_in + 1, min(source_out, piece_source_out))
        piece = copy.deepcopy(clip)
        piece["id"] = f"{clip.get('id', 'clip')}.smart{index}"
        piece["timeline_start_tick"] = clip_start + output_offset
        piece["duration_tick"] = end_tick - start_tick
        piece["source_in_tick"] = piece_source_in
        piece["source_out_tick"] = piece_source_out
        piece["keyframes"] = _slice_keyframes(clip.get("keyframes"), start_tick, end_tick)
        if index > 1:
            piece.pop("transition_in", None)
        pieces.append(piece)
        output_offset += piece["duration_tick"]
    if pieces:
        pieces[0].pop("transition_in", None)
        pieces[-1].pop("transition_out", None)
    return pieces


def replace_clip_with_smart_cut(track: dict[str, Any], clip_id: str, plan: dict[str, Any], *, ticks_per_second: int) -> list[dict[str, Any]]:
    clips = track.get("clips") if isinstance(track.get("clips"), list) else []
    index = next((index for index, item in enumerate(clips) if str(item.get("id")) == str(clip_id)), None)
    if index is None:
        raise argument_error(f"找不到智能剪口播目标片段: {clip_id}", "clip_id")
    clip = clips[index]
    ranges = plan.get("kept_ranges") if isinstance(plan.get("kept_ranges"), list) else []
    pieces = slice_clip(clip, ranges, ticks_per_second=ticks_per_second)
    if not pieces:
        raise AppError("SMART_CUT_EMPTY_RESULT", "智能剪口播没有保留任何有效片段", exit_code=2, path="kept_ranges")
    existing = {str(item.get("id")) for item in clips if item is not clip}
    if any(str(piece.get("id")) in existing for piece in pieces):
        raise AppError("SMART_CUT_ID_CONFLICT", "智能剪口播生成的片段 ID 与现有片段冲突", exit_code=2, path="clip_id")
    clips[index : index + 1] = pieces
    track["clips"] = clips
    return pieces
