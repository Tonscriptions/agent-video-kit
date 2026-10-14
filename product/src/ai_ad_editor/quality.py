from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .media import ffmpeg_path, probe_media
from .utils import run_process, sha256_bytes, sha256_file


BLACK_RE = re.compile(r"black_start:([0-9.]+).*?black_end:([0-9.]+)")
LOUDNESS_RE = re.compile(r"\bI:\s*(-?[0-9.]+) LUFS")
TRUE_PEAK_RE = re.compile(r"\bPeak:\s*(-?[0-9.]+) dBFS")
GOLDEN_VERSION = "0.1.0"
GOLDEN_METRIC_KEYS = (
    "duration_seconds",
    "width",
    "height",
    "audio_codec",
    "video_duration_seconds",
    "audio_duration_seconds",
    "av_duration_delta_seconds",
    "black_intervals",
    "integrated_lufs",
    "lufs_deviation",
    "true_peak_dbfs",
)
GOLDEN_METRIC_TOLERANCES = {
    "duration_seconds": 0.001,
    "video_duration_seconds": 0.001,
    "audio_duration_seconds": 0.001,
    "av_duration_delta_seconds": 0.001,
    "integrated_lufs": 0.1,
    "lufs_deviation": 0.1,
    "true_peak_dbfs": 0.1,
}
GOLDEN_CONSTRAINT_DEFAULTS = {
    "require_audio": False,
    "expensive": False,
    "max_av_sync_ms": 80.0,
    "target_lufs": None,
    "lufs_tolerance": 2.0,
    "fail_on_black": False,
    "max_true_peak_dbfs": None,
}


def normalize_golden_constraints(base: dict[str, Any] | None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    constraints = dict(GOLDEN_CONSTRAINT_DEFAULTS)
    if isinstance(base, dict):
        constraints.update({key: base[key] for key in constraints if key in base})
    if isinstance(overrides, dict):
        constraints.update({key: overrides[key] for key in constraints if key in overrides and overrides[key] is not None})
    return constraints


def validate_golden_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if manifest.get("golden_version") != GOLDEN_VERSION:
        errors.append({"code": "QUALITY_GOLDEN_VERSION_UNSUPPORTED", "expected": GOLDEN_VERSION, "actual": manifest.get("golden_version")})
    artifact = manifest.get("artifact")
    if not isinstance(artifact, dict) or not isinstance(artifact.get("sha256"), str) or not artifact.get("sha256", "").startswith("sha256:"):
        errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": "golden artifact.sha256 缺失或格式无效"})
    if not isinstance(manifest.get("settings_sha256"), str) or not manifest.get("settings_sha256", "").startswith("sha256:"):
        errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": "golden settings_sha256 缺失或格式无效"})
    if not isinstance(manifest.get("metrics"), dict):
        errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": "golden metrics 必须是对象"})
    constraints = manifest.get("constraints")
    if not isinstance(constraints, dict):
        errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": "golden constraints 必须是对象"})
    else:
        for key in ("require_audio", "expensive", "fail_on_black"):
            if key in constraints and not isinstance(constraints[key], bool):
                errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": f"golden constraints.{key} 必须是布尔值"})
        for key in ("max_av_sync_ms", "lufs_tolerance"):
            value = constraints.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0):
                errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": f"golden constraints.{key} 必须是非负数字或 null"})
        for key in ("target_lufs", "max_true_peak_dbfs"):
            value = constraints.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))):
                errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": f"golden constraints.{key} 必须是数字或 null"})
    tolerances = manifest.get("metric_tolerances")
    if tolerances is not None:
        if not isinstance(tolerances, dict):
            errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": "golden metric_tolerances 必须是对象"})
        else:
            for key, value in tolerances.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
                    errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": f"golden metric_tolerances.{key} 必须是非负数字"})
    if manifest.get("expected_duration_seconds") is not None:
        value = manifest.get("expected_duration_seconds")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
            errors.append({"code": "QUALITY_GOLDEN_MANIFEST_INVALID", "message": "golden expected_duration_seconds 必须是非负数字或 null"})
    return errors


def quality_settings_hash(settings: dict[str, Any]) -> str:
    payload = json.dumps(settings, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256_bytes(payload)}"


def _golden_value(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 6)
    if isinstance(value, list):
        return [_golden_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _golden_value(item) for key, item in value.items()}
    return value


def golden_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: _golden_value(metrics[key]) for key in GOLDEN_METRIC_KEYS if key in metrics}


def build_golden_manifest(
    path: Path,
    *,
    project_id: str,
    sequence_id: str | None,
    expected_duration: float | None,
    settings: dict[str, Any],
    profile: str | None,
    result: dict[str, Any],
    constraints: dict[str, Any],
) -> dict[str, Any]:
    return {
        "golden_version": GOLDEN_VERSION,
        "project_id": project_id,
        "sequence_id": sequence_id,
        "profile": profile,
        "canvas": dict(settings.get("canvas", {})),
        "artifact": {
            "path": str(path),
            "sha256": f"sha256:{sha256_file(path)}",
            "bytes": path.stat().st_size,
        },
        "settings_sha256": quality_settings_hash(settings),
        "expected_duration_seconds": expected_duration,
        "constraints": constraints,
        "metrics": golden_metrics(result.get("metrics", {})),
        "quality": {"ok": bool(result.get("ok")), "errors": result.get("errors", []), "warnings": result.get("warnings", [])},
        "metric_tolerances": dict(GOLDEN_METRIC_TOLERANCES),
    }


def compare_golden_manifest(
    manifest: dict[str, Any],
    path: Path,
    *,
    project_id: str,
    settings: dict[str, Any],
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    if manifest.get("golden_version") != GOLDEN_VERSION:
        mismatches.append({"code": "QUALITY_GOLDEN_VERSION_UNSUPPORTED", "expected": GOLDEN_VERSION, "actual": manifest.get("golden_version")})
    if manifest.get("project_id") != project_id:
        mismatches.append({"code": "QUALITY_GOLDEN_PROJECT_MISMATCH", "expected": project_id, "actual": manifest.get("project_id")})
    artifact = manifest.get("artifact") if isinstance(manifest.get("artifact"), dict) else {}
    try:
        actual_hash = f"sha256:{sha256_file(path)}"
    except OSError as exc:
        return [{"code": "QUALITY_GOLDEN_INPUT_UNREADABLE", "message": str(exc)}]
    if artifact.get("sha256") != actual_hash:
        mismatches.append({"code": "QUALITY_GOLDEN_HASH_MISMATCH", "expected": artifact.get("sha256"), "actual": actual_hash})
    expected_settings_hash = manifest.get("settings_sha256")
    actual_settings_hash = quality_settings_hash(settings)
    if expected_settings_hash != actual_settings_hash:
        mismatches.append({"code": "QUALITY_GOLDEN_SETTINGS_MISMATCH", "expected": expected_settings_hash, "actual": actual_settings_hash})
    if not result.get("ok"):
        mismatches.extend({"code": "QUALITY_GOLDEN_QUALITY_CHECK_FAILED", "detail": item} for item in result.get("errors", []))
    expected_metrics = manifest.get("metrics") if isinstance(manifest.get("metrics"), dict) else {}
    actual_metrics = golden_metrics(result.get("metrics", {}))
    tolerances = manifest.get("metric_tolerances") if isinstance(manifest.get("metric_tolerances"), dict) else GOLDEN_METRIC_TOLERANCES
    for key, expected in expected_metrics.items():
        if key not in actual_metrics:
            mismatches.append({"code": "QUALITY_GOLDEN_METRIC_MISSING", "metric": key, "expected": expected})
            continue
        actual = actual_metrics[key]
        tolerance = float(tolerances.get(key, 0.0) or 0.0)
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if abs(float(actual) - float(expected)) > tolerance:
                mismatches.append({"code": "QUALITY_GOLDEN_METRIC_MISMATCH", "metric": key, "expected": expected, "actual": actual, "tolerance": tolerance})
        elif actual != expected:
            mismatches.append({"code": "QUALITY_GOLDEN_METRIC_MISMATCH", "metric": key, "expected": expected, "actual": actual})
    return mismatches


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
