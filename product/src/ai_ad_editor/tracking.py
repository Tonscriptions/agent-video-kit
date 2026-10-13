from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .errors import AppError, dependency_error
from .media import ffmpeg_path, probe_media
from .utils import run_process


def _fraction(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fps_value(raw: Any) -> float:
    text = str(raw or "30/1")
    if "/" in text:
        left, right = text.split("/", 1)
        try:
            return max(1.0, float(left) / max(1.0, float(right)))
        except (TypeError, ValueError):
            return 30.0
    return max(1.0, _fraction(text, 30.0))


def _parse_roi(roi: str | dict[str, Any] | list[float] | tuple[float, ...]) -> tuple[float, float, float, float]:
    if isinstance(roi, str):
        try:
            values = [float(item.strip()) for item in roi.split(",")]
        except ValueError as exc:
            raise AppError("TRACK_ROI_INVALID", "ROI 必须是 x,y,width,height 数字", exit_code=2, path="roi") from exc
    elif isinstance(roi, dict):
        values = [_fraction(roi.get("x"), -1), _fraction(roi.get("y"), -1), _fraction(roi.get("width", roi.get("w")), -1), _fraction(roi.get("height", roi.get("h")), -1)]
    else:
        values = [float(item) for item in roi]
    if len(values) != 4 or values[2] <= 0 or values[3] <= 0 or values[0] < 0 or values[1] < 0 or values[0] + values[2] > 1 or values[1] + values[3] > 1:
        raise AppError("TRACK_ROI_INVALID", "ROI 必须位于 0..1 且包含正宽高", exit_code=2, path="roi")
    return tuple(values)  # type: ignore[return-value]


def _resize_gray(image: Any, size: tuple[int, int]) -> Any:
    from PIL import Image

    return image.convert("L").resize(size, Image.Resampling.BILINEAR)


def track_media(
    source: Path,
    roi: str | dict[str, Any] | list[float] | tuple[float, ...],
    *,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    step_frames: int = 4,
    search_radius: int = 48,
    max_width: int = 640,
    max_samples: int = 600,
    ticks_per_second: int = 90_000,
) -> dict[str, Any]:
    """Track a local ROI with deterministic template matching.

    This is intentionally a local, explainable fallback for Agent workflows:
    it emits transform keyframes and confidence values, never calls a cloud
    vision API, and lets a later render stage decide whether to accept the
    approximation.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError as exc:
        raise dependency_error("对象跟踪需要本地 Pillow 和 numpy", "安装本地 Pillow/numpy；不会自动联网安装") from exc
    if not source.exists() or not source.is_file():
        raise AppError("TRACK_SOURCE_MISSING", f"跟踪输入不存在: {source}", exit_code=3, path=str(source))
    probe = probe_media(source)
    video = probe.get("video", {})
    width = int(video.get("width", 0) or 0)
    height = int(video.get("height", 0) or 0)
    if not width or not height:
        raise AppError("TRACK_VIDEO_MISSING", "对象跟踪需要视频流", exit_code=4, path=str(source))
    start_seconds = max(0.0, float(start_seconds))
    duration = float(probe.get("duration_seconds", 0.0) or 0.0)
    end_seconds = duration if end_seconds is None else min(duration, max(start_seconds, float(end_seconds)))
    if end_seconds <= start_seconds:
        raise AppError("TRACK_RANGE_INVALID", "跟踪时间范围必须为正", exit_code=2, path="end_seconds")
    step_frames = max(1, int(step_frames))
    search_radius = max(4, min(256, int(search_radius)))
    max_width = max(160, min(2048, int(max_width)))
    max_samples = max(2, min(10_000, int(max_samples)))
    ticks_per_second = max(1, int(ticks_per_second))
    roi_values = _parse_roi(roi)
    fps = _fps_value(video.get("fps"))
    requested_sample_fps = min(30.0, fps / step_frames)
    sample_fps = min(requested_sample_fps, (max_samples - 1) / (end_seconds - start_seconds))
    with tempfile.TemporaryDirectory(prefix="ai-ad-editor-track-") as raw:
        frames_dir = Path(raw)
        output_pattern = frames_dir / "%06d.png"
        result = run_process(
            [
                ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start_seconds:.6f}", "-to", f"{end_seconds:.6f}",
                "-i", str(source), "-vf", f"fps={sample_fps:.6f},scale=w='min({max_width},iw)':h=-2:force_original_aspect_ratio=decrease",
                "-frames:v", str(max_samples), "-q:v", "2", str(output_pattern),
            ],
            timeout=1800,
        )
        frames = sorted(frames_dir.glob("*.png"))
        if result.returncode != 0 or not frames:
            raise AppError("TRACK_FRAME_EXTRACTION_FAILED", "无法提取对象跟踪帧", exit_code=6, retryable=True, cause=result.stderr[-3000:])
        with Image.open(frames[0]) as first_frame:
            first_image = first_frame.convert("RGB")
        frame_width, frame_height = first_image.size
        x, y, roi_width, roi_height = roi_values
        left = max(0, min(frame_width - 2, int(round(x * frame_width))))
        top = max(0, min(frame_height - 2, int(round(y * frame_height))))
        box_width = min(frame_width - left, max(8, int(round(roi_width * frame_width))))
        box_height = min(frame_height - top, max(8, int(round(roi_height * frame_height))))
        template_size = (32, 32)
        template = np.asarray(_resize_gray(first_image.crop((left, top, left + box_width, top + box_height)), template_size), dtype=np.float32)
        first_image.close()
        positions: list[dict[str, Any]] = []
        previous_left, previous_top = left, top
        for frame_index, frame_path in enumerate(frames):
            with Image.open(frame_path) as raw_image:
                image = raw_image.convert("RGB")
            if frame_index:
                best_error = float("inf")
                best_left, best_top = previous_left, previous_top
                min_left = max(0, previous_left - search_radius)
                max_left = min(frame_width - box_width, previous_left + search_radius)
                min_top = max(0, previous_top - search_radius)
                max_top = min(frame_height - box_height, previous_top + search_radius)
                candidate_tops = sorted(set(range(min_top, max_top + 1, 4)) | {previous_top})
                candidate_lefts = sorted(set(range(min_left, max_left + 1, 4)) | {previous_left})
                for candidate_top in candidate_tops:
                    for candidate_left in candidate_lefts:
                        candidate = np.asarray(_resize_gray(image.crop((candidate_left, candidate_top, candidate_left + box_width, candidate_top + box_height)), template_size), dtype=np.float32)
                        error = float(np.mean(np.abs(candidate - template)))
                        if error < best_error - 1e-6 or (abs(error - best_error) <= 1e-6 and abs(candidate_left - previous_left) + abs(candidate_top - previous_top) < abs(best_left - previous_left) + abs(best_top - previous_top)):
                            best_error = error
                            best_left, best_top = candidate_left, candidate_top
                previous_left, previous_top = best_left, best_top
                current = np.asarray(_resize_gray(image.crop((previous_left, previous_top, previous_left + box_width, previous_top + box_height)), template_size), dtype=np.float32)
                template = (template * 0.65) + (current * 0.35)
            else:
                best_error = 0.0
            timestamp = start_seconds + frame_index / sample_fps
            positions.append({
                "at_seconds": round(timestamp, 6),
                "at_tick": int(round((timestamp - start_seconds) * ticks_per_second)),
                "x": round((previous_left + box_width / 2) / frame_width, 6),
                "y": round((previous_top + box_height / 2) / frame_height, 6),
                "width": round(box_width / frame_width, 6),
                "height": round(box_height / frame_height, 6),
                "confidence": round(max(0.0, min(1.0, 1.0 - best_error / 255.0)), 6),
            })
            image.close()
    return {
        "engine": "local-template-matching",
        "source": str(source),
        "source_sha256": None,
        "range": {"start_seconds": start_seconds, "end_seconds": end_seconds, "sample_fps": sample_fps, "requested_sample_fps": requested_sample_fps, "step_frames": step_frames, "max_samples": max_samples},
        "ticks_per_second": ticks_per_second,
        "roi": {"x": roi_values[0], "y": roi_values[1], "width": roi_values[2], "height": roi_values[3]},
        "frames": positions,
        "keyframes": [
            {"property": "transform.position.x", "keyframes": [{"at_tick": item["at_tick"], "value": item["x"], "interpolation": "linear"} for item in positions]},
            {"property": "transform.position.y", "keyframes": [{"at_tick": item["at_tick"], "value": item["y"], "interpolation": "linear"} for item in positions]},
        ],
        "warnings": ["template_matching_can_drift_on_occlusion_or_large_scale_change"] + (["sampling_rate_reduced_to_sample_budget"] if sample_fps < requested_sample_fps else []),
    }
