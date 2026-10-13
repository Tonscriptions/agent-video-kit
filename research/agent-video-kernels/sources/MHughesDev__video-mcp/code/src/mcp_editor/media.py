from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .diagnostics import command_failed, media_not_found, missing_dependency
from .schemas import MediaProbe, MediaStream, as_path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def require_binary(name: str) -> str:
    binary = shutil.which(name)
    if not binary:
        raise missing_dependency(name)
    return binary


def _float_or_none(value: object) -> float | None:
    try:
        if value in (None, "N/A"):
            return None
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        if value in (None, "N/A"):
            return None
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def probe_media(path: str | Path) -> MediaProbe:
    media_path = as_path(path)
    if not media_path.exists():
        issue = media_not_found(str(media_path))
        return MediaProbe(
            path=str(media_path),
            exists=False,
            ok=False,
            error=issue.message,
            error_code=issue.code,
            suggested_fix=issue.suggested_fix,
            details=issue.details,
        )

    try:
        ffprobe = require_binary("ffprobe")
    except Exception as exc:
        issue = getattr(exc, "issue", None)
        return MediaProbe(
            path=str(media_path),
            exists=True,
            ok=False,
            error=str(exc),
            error_code=getattr(issue, "code", "dependency_error"),
            suggested_fix=getattr(issue, "suggested_fix", None),
            details=getattr(issue, "details", {}),
        )

    cmd = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(media_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)
    except subprocess.CalledProcessError as exc:
        issue = command_failed("ffprobe", cmd, exc).issue
        return MediaProbe(
            path=str(media_path),
            exists=True,
            ok=False,
            error=issue.message,
            error_code=issue.code,
            suggested_fix=issue.suggested_fix,
            details=issue.details,
        )
    except json.JSONDecodeError as exc:
        return MediaProbe(
            path=str(media_path),
            exists=True,
            ok=False,
            error="ffprobe returned invalid JSON",
            error_code="invalid_probe_output",
            suggested_fix="Run ffprobe manually for this file and inspect the output.",
            details={"exception": str(exc), "command": cmd},
        )

    streams = [
        MediaStream(
            index=int(stream.get("index", 0)),
            codec_type=str(stream.get("codec_type", "")),
            codec_name=stream.get("codec_name"),
            width=_int_or_none(stream.get("width")),
            height=_int_or_none(stream.get("height")),
            duration=_float_or_none(stream.get("duration")),
            r_frame_rate=stream.get("r_frame_rate"),
        )
        for stream in payload.get("streams", [])
    ]
    fmt = payload.get("format", {})
    return MediaProbe(
        path=str(media_path),
        exists=True,
        ok=True,
        duration=_float_or_none(fmt.get("duration")),
        format_name=fmt.get("format_name"),
        bit_rate=_int_or_none(fmt.get("bit_rate")),
        streams=streams,
    )


def scan_assets(input_dir: str | Path, include_audio: bool = True) -> list[MediaProbe]:
    root = as_path(input_dir)
    if not root.exists():
        return []

    extensions = VIDEO_EXTENSIONS | (AUDIO_EXTENSIONS if include_audio else set())
    paths = sorted(path for path in root.rglob("*") if path.suffix.lower() in extensions)
    return [probe_media(path) for path in paths]
