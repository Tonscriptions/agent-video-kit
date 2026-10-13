from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from .media import probe_media
from .projects import load_manifest
from .schemas import PLATFORM_DIMENSIONS, Platform


# ── Low-level FFmpeg probes ────────────────────────────────────────────────────


def _run_ffmpeg_null(args: list[str]) -> tuple[bool, str]:
    """Run an FFmpeg command that writes to null output. Returns (success, combined stderr)."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner"] + args + ["-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return True, result.stderr
    except FileNotFoundError:
        return False, "ffmpeg not found"
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out"


def _check_fps(stream_r_frame_rate: str | None, expected_fps: float = 30.0, tolerance: float = 1.0) -> bool:
    if not stream_r_frame_rate:
        return False
    try:
        num, den = stream_r_frame_rate.split("/")
        fps = int(num) / int(den)
        return abs(fps - expected_fps) <= tolerance
    except (ValueError, ZeroDivisionError):
        return False


def _check_not_black(path: str | Path, sample_duration: float = 5.0) -> dict[str, Any]:
    """Detect if the video is entirely black using FFmpeg blackdetect."""
    ok, stderr = _run_ffmpeg_null([
        "-t", str(sample_duration),
        "-i", str(path),
        "-vf", "blackdetect=d=0:pix_th=0.10",
        "-an",
    ])
    if not ok:
        return {"skipped": True, "reason": stderr}
    # blackdetect emits lines like "black_start:0 black_end:5 black_duration:5"
    matches = re.findall(r"black_duration:([\d.]+)", stderr)
    total_black = sum(float(m) for m in matches)
    return {
        "skipped": False,
        "passed": total_black < sample_duration * 0.95,
        "total_black_seconds": total_black,
    }


def _check_not_silent(path: str | Path, sample_duration: float = 5.0) -> dict[str, Any]:
    """Detect if the audio track is entirely silent using FFmpeg silencedetect."""
    ok, stderr = _run_ffmpeg_null([
        "-t", str(sample_duration),
        "-i", str(path),
        "-vn",
        "-af", "silencedetect=n=-50dB:d=0.1",
    ])
    if not ok:
        return {"skipped": True, "reason": stderr}
    matches = re.findall(r"silence_duration:([\d.]+)", stderr)
    total_silence = sum(float(m) for m in matches)
    return {
        "skipped": False,
        "passed": total_silence < sample_duration * 0.95,
        "total_silence_seconds": total_silence,
    }


def _check_not_frozen(path: str | Path, freeze_threshold: float = 2.0) -> dict[str, Any]:
    """Detect long frozen frames using FFmpeg freezedetect."""
    ok, stderr = _run_ffmpeg_null([
        "-i", str(path),
        "-vf", f"freezedetect=n=0.001:d={freeze_threshold}",
        "-an",
    ])
    if not ok:
        return {"skipped": True, "reason": stderr}
    freeze_events = re.findall(r"freeze_duration:([\d.]+)", stderr)
    has_freeze = len(freeze_events) > 0
    return {
        "skipped": False,
        "passed": not has_freeze,
        "freeze_events": len(freeze_events),
        "longest_freeze": max((float(f) for f in freeze_events), default=0.0),
    }


# ── Public validation functions ───────────────────────────────────────────────


def validate_render(
    path: str | Path,
    platform: Platform,
    expected_duration: float | None = None,
    expected_fps: float = 30.0,
    check_black: bool = True,
    check_silent: bool = True,
    check_frozen: bool = True,
) -> dict[str, Any]:
    """Comprehensive validation of a single rendered video file."""
    probe = probe_media(path)

    checks: dict[str, bool] = {
        "exists": probe.exists,
        "probe_ok": probe.ok,
        "has_video": probe.has_video,
    }

    video_stream = next((s for s in probe.streams if s.codec_type == "video"), None)
    expected_width, expected_height = PLATFORM_DIMENSIONS[platform]
    checks["resolution_matches"] = bool(
        video_stream and video_stream.width == expected_width and video_stream.height == expected_height
    )
    checks["fps_correct"] = bool(
        video_stream and _check_fps(video_stream.r_frame_rate, expected_fps)
    )

    if expected_duration is not None and probe.duration is not None:
        checks["duration_close"] = abs(probe.duration - expected_duration) <= 1.0
    else:
        checks["duration_close"] = probe.duration is not None and probe.duration > 0

    advanced: dict[str, Any] = {}
    if probe.exists and probe.ok:
        if check_black:
            advanced["black_check"] = _check_not_black(path)
            if not advanced["black_check"].get("skipped"):
                checks["not_black"] = advanced["black_check"]["passed"]

        if check_silent and probe.has_audio:
            advanced["silence_check"] = _check_not_silent(path)
            if not advanced["silence_check"].get("skipped"):
                checks["not_silent"] = advanced["silence_check"]["passed"]

        if check_frozen:
            advanced["freeze_check"] = _check_not_frozen(path)
            if not advanced["freeze_check"].get("skipped"):
                checks["not_frozen"] = advanced["freeze_check"]["passed"]

    return {
        "ok": all(checks.values()),
        "path": probe.path,
        "platform": platform.value,
        "checks": checks,
        "duration": probe.duration,
        "has_audio": probe.has_audio,
        "error": probe.error,
        "advanced": advanced,
    }


def validate_audio(
    path: str | Path,
    expected_duration: float | None = None,
) -> dict[str, Any]:
    """Audio-focused validation of a rendered file."""
    probe = probe_media(path)

    checks: dict[str, bool] = {
        "exists": probe.exists,
        "probe_ok": probe.ok,
        "has_audio": probe.has_audio,
    }

    audio_stream = next((s for s in probe.streams if s.codec_type == "audio"), None)
    checks["audio_stream_valid"] = audio_stream is not None

    if expected_duration is not None and probe.duration is not None:
        checks["duration_close"] = abs(probe.duration - expected_duration) <= 1.0
    else:
        checks["duration_close"] = probe.duration is not None and probe.duration > 0

    advanced: dict[str, Any] = {}
    if probe.exists and probe.has_audio:
        advanced["silence_check"] = _check_not_silent(path)
        if not advanced["silence_check"].get("skipped"):
            checks["not_silent"] = advanced["silence_check"]["passed"]

    return {
        "ok": all(checks.values()),
        "path": probe.path,
        "checks": checks,
        "duration": probe.duration,
        "codec": audio_stream.codec_name if audio_stream else None,
        "error": probe.error,
        "advanced": advanced,
    }


def validate_platform_outputs(project_id: str) -> dict[str, Any]:
    """Validate all rendered platform outputs for a project."""
    manifest = load_manifest(project_id)

    if not manifest.outputs:
        return {
            "ok": False,
            "project_id": project_id,
            "error": "no rendered outputs found in project manifest",
            "suggested_fix": "Run render_project or render_all_variants first",
            "results": {},
        }

    results: dict[str, Any] = {}
    all_ok = True
    for platform_key, rendered in manifest.outputs.items():
        platform = Platform(platform_key)
        timeline = manifest.timelines.get(platform_key)
        expected_duration = timeline.target_duration if timeline else None
        result = validate_render(
            rendered.path,
            platform,
            expected_duration=expected_duration,
        )
        results[platform_key] = result
        if not result["ok"]:
            all_ok = False

    return {
        "ok": all_ok,
        "project_id": project_id,
        "platforms_checked": len(results),
        "results": results,
    }


def validate_delivery_package(project_id: str) -> dict[str, Any]:
    """Full delivery validation: outputs, OTIO exports, and manifest consistency."""
    manifest = load_manifest(project_id)
    issues: list[dict[str, Any]] = []
    checks: dict[str, bool] = {}

    # Check rendered outputs exist
    checks["has_outputs"] = len(manifest.outputs) > 0
    if not checks["has_outputs"]:
        issues.append({
            "code": "no_outputs",
            "message": "Project has no rendered outputs.",
            "suggested_fix": "Run render_all_variants before validating delivery.",
        })

    # Check all declared platforms have outputs
    missing_platforms = [p.value for p in manifest.platforms if p.value not in manifest.outputs]
    checks["all_platforms_rendered"] = len(missing_platforms) == 0
    if missing_platforms:
        issues.append({
            "code": "missing_platform_outputs",
            "message": f"Missing renders for platforms: {missing_platforms}",
            "suggested_fix": "Run render_all_variants to produce all platform outputs.",
        })

    # Check OTIO exports exist for all timelines
    missing_otio: list[str] = []
    for platform_key, timeline in manifest.timelines.items():
        otio_path = timeline.otio_path
        if not otio_path or not Path(otio_path).exists():
            missing_otio.append(platform_key)
    checks["otio_exported"] = len(missing_otio) == 0
    if missing_otio:
        issues.append({
            "code": "missing_otio_export",
            "message": f"OTIO file missing for platforms: {missing_otio}",
            "suggested_fix": "Run export_timeline to produce OTIO files.",
        })

    # Validate each rendered output file
    output_results: dict[str, Any] = {}
    for platform_key, rendered in manifest.outputs.items():
        platform = Platform(platform_key)
        timeline = manifest.timelines.get(platform_key)
        expected_duration = timeline.target_duration if timeline else None
        result = validate_render(rendered.path, platform, expected_duration=expected_duration)
        output_results[platform_key] = result
        checks[f"output_ok_{platform_key}"] = result["ok"]
        if not result["ok"]:
            issues.append({
                "code": "output_validation_failed",
                "message": f"Output validation failed for {platform_key}: {rendered.path}",
                "checks": result["checks"],
            })

    # Check manifest has essential fields
    checks["manifest_has_name"] = bool(manifest.name)
    checks["manifest_has_assets"] = len(manifest.assets) > 0
    if not checks["manifest_has_assets"]:
        issues.append({
            "code": "no_assets",
            "message": "Project manifest has no scanned assets.",
            "suggested_fix": "Run scan_project_assets before delivery.",
        })

    return {
        "ok": all(checks.values()) and not issues,
        "project_id": project_id,
        "project_name": manifest.name,
        "checks": checks,
        "issues": issues,
        "output_results": output_results,
        "platforms": [p.value for p in manifest.platforms],
        "timelines_count": len(manifest.timelines),
        "outputs_count": len(manifest.outputs),
    }
