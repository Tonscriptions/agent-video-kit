from __future__ import annotations

import math
from typing import Any

from .errors import AppError, argument_error


BEAT_CUT_VERSION = "0.1.0"


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        converted = float(value)
    except (TypeError, ValueError):
        return default
    return converted if math.isfinite(converted) else default


def _duration_ticks(asset: dict[str, Any], ticks_per_second: int) -> int:
    probe = asset.get("probe") if isinstance(asset.get("probe"), dict) else {}
    raw_ticks = probe.get("duration_tick")
    try:
        ticks = int(raw_ticks)
    except (TypeError, ValueError):
        ticks = 0
    if ticks <= 0:
        seconds = _finite(probe.get("duration_seconds"), 0.0)
        ticks = int(round(seconds * ticks_per_second))
    return max(0, ticks)


def _normalise_anchors(raw: Any, *, start: float, end: float) -> tuple[list[float], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return [], warnings
    values: list[float] = []
    for index, item in enumerate(raw):
        value = _finite(item, math.nan)
        if not math.isfinite(value):
            warnings.append({"code": "BEAT_ANCHOR_INVALID", "message": f"第 {index} 个节拍锚点不是有限数字，已忽略"})
            continue
        if value < start or value > end:
            warnings.append({"code": "BEAT_ANCHOR_OUT_OF_RANGE", "message": f"节拍锚点 {value:.3f}s 不在分析区间内，已忽略", "seconds": round(value, 6)})
            continue
        values.append(round(value, 6))
    ordered = sorted(set(values))
    if ordered != values:
        warnings.append({"code": "BEAT_ANCHORS_NORMALIZED", "message": "节拍锚点已排序并去重"})
    return ordered, warnings


def build_beat_cut_plan(
    analysis: dict[str, Any],
    source_assets: list[dict[str, Any]],
    *,
    ticks_per_second: int = 90_000,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    min_segment_seconds: float = 0.2,
    max_clips: int = 128,
    source_mode: str = "cycle",
) -> dict[str, Any]:
    """Build a deterministic beat-aligned timeline plan from local evidence.

    The planner deliberately uses only beat timestamps supplied by the local
    analysis layer.  It never calls a hosted music service or downloads a model.
    Each generated clip starts at source time zero and is shortened or slowed to
    fit its beat interval, so source ranges remain inside the registered asset.
    """
    if not isinstance(analysis, dict):
        raise argument_error("节拍分析必须是 JSON 对象", "analysis")
    if not isinstance(source_assets, list) or not source_assets:
        raise argument_error("按节拍剪辑至少需要一个本地视频素材", "source_assets")
    if source_mode not in {"cycle", "ordered"}:
        raise argument_error("source_mode 只支持 cycle 或 ordered", "source_mode")
    try:
        ticks = int(ticks_per_second)
    except (TypeError, ValueError) as exc:
        raise argument_error("ticks_per_second 必须是正整数", "ticks_per_second") from exc
    if ticks <= 0:
        raise argument_error("ticks_per_second 必须是正整数", "ticks_per_second")
    start = _finite(start_seconds, 0.0)
    if start < 0:
        raise argument_error("start_seconds 不能为负数", "start_seconds")
    probe = analysis.get("probe") if isinstance(analysis.get("probe"), dict) else {}
    duration = _finite(probe.get("duration_seconds"), _finite(analysis.get("duration_seconds"), 0.0))
    if duration <= 0:
        raise AppError("BEAT_AUDIO_DURATION_MISSING", "节拍分析缺少正的音频时长", exit_code=2, path="analysis.probe.duration_seconds")
    end = duration if end_seconds is None else _finite(end_seconds, duration)
    if end <= start or end > duration + 1e-6:
        raise argument_error("end_seconds 必须大于 start_seconds 且不能越过音频时长", "end_seconds")
    minimum = _finite(min_segment_seconds, 0.2)
    if minimum <= 0:
        raise argument_error("min_segment_seconds 必须大于 0", "min_segment_seconds")
    try:
        limit = int(max_clips)
    except (TypeError, ValueError) as exc:
        raise argument_error("max_clips 必须是正整数", "max_clips") from exc
    if limit <= 0:
        raise argument_error("max_clips 必须是正整数", "max_clips")

    anchors_payload = analysis.get("beat_anchors")
    if isinstance(anchors_payload, dict):
        anchors_payload = anchors_payload.get("anchors", [])
    anchors, warnings = _normalise_anchors(anchors_payload, start=start, end=end)
    boundaries = [round(start, 6), *anchors, round(end, 6)]
    boundaries = sorted(set(boundaries))
    ranges = [(left, right) for left, right in zip(boundaries, boundaries[1:]) if right - left >= minimum]
    if not ranges:
        ranges = [(start, end)]
        warnings.append({"code": "BEAT_NO_VALID_INTERVAL", "message": "没有满足最小时长的节拍区间，使用整个分析区间"})
    if not anchors:
        warnings.append({"code": "BEAT_NO_ANCHORS", "message": "本地能量分析没有检测到节拍，计划退化为单段或整段切分"})
    truncated = len(ranges) > limit
    if truncated:
        ranges = ranges[:limit]
        warnings.append({"code": "BEAT_PLAN_TRUNCATED", "message": f"节拍区间超过 max_clips={limit}，已保留前 {limit} 段", "max_clips": limit})

    normalised_assets: list[dict[str, Any]] = []
    for index, asset in enumerate(source_assets):
        if not isinstance(asset, dict) or not str(asset.get("id", "")).strip():
            raise argument_error(f"第 {index} 个源素材缺少 id", f"source_assets[{index}].id")
        duration_tick = _duration_ticks(asset, ticks)
        if duration_tick <= 0:
            raise AppError("BEAT_SOURCE_DURATION_MISSING", f"源素材没有可用时长: {asset.get('id')}", exit_code=2, path=f"source_assets[{index}].probe")
        normalised_assets.append({"id": str(asset["id"]), "duration_tick": duration_tick, "kind": asset.get("kind", "video")})

    clips: list[dict[str, Any]] = []
    segment_offset = 0
    source_reuse = False
    slowdown = False
    for index, (left, right) in enumerate(ranges):
        duration_tick = max(1, int(round((right - left) * ticks)))
        if source_mode == "cycle":
            asset_index = index % len(normalised_assets)
        else:
            asset_index = min(index, len(normalised_assets) - 1)
        asset = normalised_assets[asset_index]
        source_span = min(asset["duration_tick"], duration_tick)
        if source_span <= 0:
            raise AppError("BEAT_SOURCE_RANGE_INVALID", f"源素材无法覆盖节拍区间: {asset['id']}", exit_code=2, path="source_assets")
        speed = source_span / duration_tick
        if speed < 0.999999:
            slowdown = True
        if index >= len(normalised_assets):
            source_reuse = True
        speed_value = 1.0 if abs(speed - 1.0) < 1e-6 else round(speed, 6)
        clips.append(
            {
                "index": index,
                "beat_index": index if index < len(anchors) else None,
                "beat_start_seconds": round(left, 6),
                "beat_end_seconds": round(right, 6),
                "timeline_start_tick": segment_offset,
                "duration_tick": duration_tick,
                "asset_id": asset["id"],
                "source_in_tick": 0,
                "source_out_tick": source_span,
                "speed": speed_value,
                "source_duration_tick": asset["duration_tick"],
            }
        )
        segment_offset += duration_tick
    if source_reuse:
        warnings.append({"code": "BEAT_SOURCE_REUSED", "message": "节拍段数量超过源素材数量，按 source_mode 重复使用素材"})
    if slowdown:
        warnings.append({"code": "BEAT_SOURCE_SLOWED", "message": "部分节拍段长于源素材，使用常速以下 speed 保持源范围合法；请复核音画质量"})
    return {
        "beat_cut_version": BEAT_CUT_VERSION,
        "engine": "ffmpeg-local-energy-beat-v1",
        "network": "disabled",
        "parameters": {
            "ticks_per_second": ticks,
            "start_seconds": round(start, 6),
            "end_seconds": round(end, 6),
            "min_segment_seconds": round(minimum, 6),
            "max_clips": limit,
            "source_mode": source_mode,
        },
        "analysis": {
            "status": analysis.get("beat_anchors", {}).get("status") if isinstance(analysis.get("beat_anchors"), dict) else None,
            "bpm": analysis.get("beat_anchors", {}).get("bpm") if isinstance(analysis.get("beat_anchors"), dict) else None,
            "anchors": anchors,
            "source_sha256": analysis.get("source_sha256"),
        },
        "duration_seconds": round(segment_offset / ticks, 6),
        "duration_tick": segment_offset,
        "clips": clips,
        "source_assets": normalised_assets,
        "warnings": warnings,
        "changed": bool(clips),
    }
