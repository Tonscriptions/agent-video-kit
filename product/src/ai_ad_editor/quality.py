from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .media import ffmpeg_path, probe_media
from .utils import run_process


BLACK_RE = re.compile(r"black_start:([0-9.]+).*?black_end:([0-9.]+)")
LOUDNESS_RE = re.compile(r"\bI:\s*(-?[0-9.]+) LUFS")
TRUE_PEAK_RE = re.compile(r"\bPeak:\s*(-?[0-9.]+) dBFS")


def check_output(
    path: Path,
    settings: dict[str, Any],
    expected_duration: float | None = None,
    *,
    require_audio: bool = False,
    run_expensive: bool = True,
    max_av_sync_ms: float | None = 80.0,
    target_lufs: float | None = None,
    lufs_tolerance: float = 2.0,
    fail_on_black: bool = False,
    max_true_peak_dbfs: float | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not path.exists() or not path.is_file():
        return {"ok": False, "errors": [{"code": "OUTPUT_MISSING", "message": f"输出不存在: {path}"}], "warnings": [], "metrics": {}}
    try:
        probe = probe_media(path)
    except Exception as exc:  # probe errors are converted into a structured quality failure
        return {"ok": False, "errors": [{"code": "OUTPUT_UNREADABLE", "message": str(exc)}], "warnings": [], "metrics": {}}
    canvas = settings.get("canvas", {})
    width = int(canvas.get("width", 0) or 0)
    height = int(canvas.get("height", 0) or 0)
    video = probe.get("video", {})
    if width and int(video.get("width", 0) or 0) != width:
        errors.append({"code": "OUTPUT_WIDTH_MISMATCH", "expected": width, "actual": video.get("width")})
    if height and int(video.get("height", 0) or 0) != height:
        errors.append({"code": "OUTPUT_HEIGHT_MISMATCH", "expected": height, "actual": video.get("height")})
    if not video.get("codec"):
        errors.append({"code": "OUTPUT_VIDEO_STREAM_MISSING", "message": "输出没有有效视频流"})
    if require_audio and not probe.get("audio", {}).get("codec"):
        errors.append({"code": "OUTPUT_AUDIO_STREAM_MISSING", "message": "该样例要求音频流，但输出没有音频"})
    actual_duration = float(probe.get("duration_seconds", 0.0))
    audio = probe.get("audio", {})
    video_duration = float(video.get("duration_seconds", 0.0) or actual_duration)
    audio_duration = float(audio.get("duration_seconds", 0.0) or 0.0)
    if video.get("codec") and audio.get("codec") and audio_duration and max_av_sync_ms is not None:
        av_sync_delta = abs(video_duration - audio_duration)
        if av_sync_delta * 1000.0 > max(0.0, float(max_av_sync_ms)):
            errors.append({"code": "OUTPUT_AV_SYNC_OUT_OF_RANGE", "expected_max_ms": max_av_sync_ms, "actual_ms": round(av_sync_delta * 1000.0, 3)})
    if expected_duration is not None:
        fps = settings.get("timebase", {}).get("display_fps", {"num": 30, "den": 1})
        frame_tolerance = max(1.0 / max(1, int(fps.get("num", 30))), 0.001) * 1.5
        if abs(actual_duration - expected_duration) > frame_tolerance:
            errors.append({"code": "OUTPUT_DURATION_MISMATCH", "expected": expected_duration, "actual": actual_duration, "tolerance": frame_tolerance})
    metrics: dict[str, Any] = {"duration_seconds": actual_duration, "width": video.get("width"), "height": video.get("height"), "audio_codec": probe.get("audio", {}).get("codec"), "video_duration_seconds": video_duration, "audio_duration_seconds": audio_duration or None, "av_duration_delta_seconds": abs(video_duration - audio_duration) if audio_duration else None, "probe": probe}
    if run_expensive:
        black = run_process([ffmpeg_path(), "-hide_banner", "-nostats", "-i", str(path), "-vf", "blackdetect=d=0.1:pix_th=0.1", "-an", "-f", "null", "-"], timeout=600)
        black_intervals = [{"start": float(start), "end": float(end)} for start, end in BLACK_RE.findall(black.stderr)]
        metrics["black_intervals"] = black_intervals
        if black_intervals:
            item = {"code": "BLACK_INTERVAL_DETECTED", "message": "检测到黑帧区间；可能是有意留白，请人工确认", "intervals": black_intervals}
            (errors if fail_on_black else warnings).append(item)
        loudness = run_process([ffmpeg_path(), "-hide_banner", "-nostats", "-i", str(path), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"], timeout=600)
        loudness_matches = LOUDNESS_RE.findall(loudness.stderr)
        true_peak_matches = TRUE_PEAK_RE.findall(loudness.stderr)
        if true_peak_matches:
            metrics["true_peak_dbfs"] = float(true_peak_matches[-1])
            if max_true_peak_dbfs is not None and metrics["true_peak_dbfs"] > float(max_true_peak_dbfs):
                errors.append({"code": "OUTPUT_TRUE_PEAK_OUT_OF_RANGE", "max_true_peak_dbfs": max_true_peak_dbfs, "actual_true_peak_dbfs": metrics["true_peak_dbfs"]})
        elif max_true_peak_dbfs is not None:
            errors.append({"code": "OUTPUT_TRUE_PEAK_UNAVAILABLE", "message": "无法从 ebur128 结果读取 true peak"})
        if loudness_matches:
            metrics["integrated_lufs"] = float(loudness_matches[-1])
            if target_lufs is not None:
                deviation = abs(metrics["integrated_lufs"] - float(target_lufs))
                metrics["lufs_deviation"] = deviation
                if deviation > max(0.0, float(lufs_tolerance)):
                    errors.append({"code": "OUTPUT_LOUDNESS_OUT_OF_RANGE", "target_lufs": target_lufs, "actual_lufs": metrics["integrated_lufs"], "tolerance": lufs_tolerance})
        elif target_lufs is not None:
            errors.append({"code": "OUTPUT_LOUDNESS_UNAVAILABLE", "message": "无法从 ebur128 结果读取 integrated LUFS"})
    return {"ok": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}
