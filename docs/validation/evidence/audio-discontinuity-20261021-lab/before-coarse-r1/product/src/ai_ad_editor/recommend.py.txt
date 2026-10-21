from __future__ import annotations

from typing import Any, Iterable


def _overlap_seconds(start: float, end: float, intervals: Iterable[tuple[float, float]]) -> float:
    total = 0.0
    for left, right in intervals:
        total += max(0.0, min(end, right) - max(start, left))
    return total


def recommend_highlights(analysis: dict[str, Any], *, top_k: int = 5, min_duration: float = 1.0, max_duration: float = 8.0) -> dict[str, Any]:
    """Rank deterministic local highlight candidates from scene, silence, and beat evidence."""
    top_k = max(1, min(100, int(top_k)))
    min_duration = max(0.1, float(min_duration))
    max_duration = max(min_duration, float(max_duration))
    silence = analysis.get("silence") if isinstance(analysis.get("silence"), dict) else {}
    starts = [float(value) for value in silence.get("starts", [])]
    ends = [float(value) for value in silence.get("ends", [])]
    silence_intervals = list(zip(starts, ends))
    beats = analysis.get("beat_anchors") if isinstance(analysis.get("beat_anchors"), dict) else {}
    beat_points = [float(value) for value in beats.get("anchors", [])]
    raw_segments = analysis.get("segments") if isinstance(analysis.get("segments"), list) else []
    candidates: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_segments, start=1):
        try:
            start = float(raw.get("start_seconds", raw.get("start", 0.0)))
            end = float(raw.get("end_seconds", raw.get("end", 0.0)))
        except (TypeError, ValueError):
            continue
        duration = end - start
        if duration <= 0:
            continue
        if duration > max_duration:
            end = start + max_duration
            duration = max_duration
        if duration < min_duration:
            continue
        silence_overlap = _overlap_seconds(start, end, silence_intervals)
        active_ratio = max(0.0, min(1.0, 1.0 - silence_overlap / max(duration, 1e-9)))
        beat_count = sum(1 for point in beat_points if start <= point <= end)
        center = (start + end) / 2
        # Prefer active, medium-length scenes and reward a beat landing without
        # making the score depend on a cloud model or hidden random seed.
        length_score = 1.0 - abs(duration - min(4.0, max_duration)) / max(max_duration, 1.0)
        score = round(max(0.0, active_ratio * 0.65 + max(0.0, length_score) * 0.2 + min(1.0, beat_count / 2) * 0.15), 6)
        candidates.append({
            "id": f"highlight_{index:04d}",
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "duration_seconds": round(duration, 3),
            "score": score,
            "active_ratio": round(active_ratio, 6),
            "beat_count": beat_count,
            "reason": "active_scene_with_beat" if beat_count and active_ratio >= 0.5 else "active_scene",
        })
    candidates.sort(key=lambda item: (-float(item["score"]), float(item["start_seconds"]), str(item["id"])))
    selected: list[dict[str, Any]] = []
    for candidate in candidates:
        if any(candidate["start_seconds"] < item["end_seconds"] and item["start_seconds"] < candidate["end_seconds"] for item in selected):
            continue
        selected.append(candidate)
        if len(selected) >= top_k:
            break
    return {
        "engine": "local-heuristic",
        "network": "disabled",
        "top_k": top_k,
        "candidate_count": len(candidates),
        "candidates": selected,
        "scoring": {"active_ratio": 0.65, "length_fit": 0.2, "beat_presence": 0.15},
    }
