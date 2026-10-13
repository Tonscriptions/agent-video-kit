from __future__ import annotations

import re
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from .config import output_dir
from .diagnostics import command_failed
from .media import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, probe_media, require_binary, scan_assets
from .projects import load_manifest, project_dir
from .schemas import MediaProbe, MediaStream, as_path


def _fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None


def _aspect_ratio(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    ratio = Fraction(width, height)
    return f"{ratio.numerator}:{ratio.denominator}"


def _primary_stream(probe: MediaProbe, codec_type: str) -> MediaStream | None:
    return next((stream for stream in probe.streams if stream.codec_type == codec_type), None)


def _probe_failure(probe: MediaProbe) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": probe.error_code or "probe_failed",
            "message": probe.error or "Media probe failed.",
            "suggested_fix": probe.suggested_fix,
            "details": probe.details,
        },
        "probe": probe.model_dump(),
    }


def analyze_video_metadata(path: str | Path) -> dict[str, Any]:
    probe = probe_media(path)
    if not probe.ok:
        return _probe_failure(probe)

    video = _primary_stream(probe, "video")
    if video is None:
        return {
            "ok": False,
            "error": {
                "code": "no_video_stream",
                "message": f"No video stream found in {probe.path}.",
                "suggested_fix": "Use a file that contains at least one video stream.",
                "details": {"path": probe.path},
            },
            "probe": probe.model_dump(),
        }

    return {
        "ok": True,
        "path": probe.path,
        "duration": probe.duration or video.duration,
        "format_name": probe.format_name,
        "bit_rate": probe.bit_rate,
        "width": video.width,
        "height": video.height,
        "aspect_ratio": _aspect_ratio(video.width, video.height),
        "fps": _fps(video.r_frame_rate),
        "codec_name": video.codec_name,
        "has_audio": probe.has_audio,
        "stream_count": len(probe.streams),
        "probe": probe.model_dump(),
    }


def analyze_audio_metadata(path: str | Path) -> dict[str, Any]:
    probe = probe_media(path)
    if not probe.ok:
        return _probe_failure(probe)

    audio = _primary_stream(probe, "audio")
    if audio is None:
        return {
            "ok": False,
            "error": {
                "code": "no_audio_stream",
                "message": f"No audio stream found in {probe.path}.",
                "suggested_fix": "Use a file that contains at least one audio stream.",
                "details": {"path": probe.path},
            },
            "probe": probe.model_dump(),
        }

    return {
        "ok": True,
        "path": probe.path,
        "duration": probe.duration or audio.duration,
        "format_name": probe.format_name,
        "bit_rate": probe.bit_rate,
        "codec_name": audio.codec_name,
        "has_video": probe.has_video,
        "stream_count": len(probe.streams),
        "probe": probe.model_dump(),
    }


def scan_project_assets(input_dir: str | Path = "data/input", include_audio: bool = True) -> dict[str, Any]:
    root = as_path(input_dir)
    assets = scan_assets(root, include_audio=include_audio)
    video_count = sum(1 for asset in assets if asset.ok and asset.has_video)
    audio_count = sum(1 for asset in assets if asset.ok and asset.has_audio)
    failed_count = sum(1 for asset in assets if not asset.ok)

    return {
        "ok": True,
        "input_dir": str(root),
        "exists": root.exists(),
        "supported_extensions": sorted(VIDEO_EXTENSIONS | (AUDIO_EXTENSIONS if include_audio else set())),
        "summary": {
            "asset_count": len(assets),
            "video_count": video_count,
            "audio_count": audio_count,
            "failed_count": failed_count,
        },
        "assets": [asset.model_dump() for asset in assets],
    }


def detect_scenes(path: str | Path, threshold: float = 0.35, min_scene_gap: float = 0.5) -> dict[str, Any]:
    media_path = as_path(path)
    probe = probe_media(media_path)
    if not probe.ok:
        return _probe_failure(probe)
    if not probe.has_video:
        return {
            "ok": False,
            "error": {
                "code": "no_video_stream",
                "message": f"No video stream found in {probe.path}.",
                "suggested_fix": "Use a video file for scene detection.",
                "details": {"path": probe.path},
            },
        }

    ffmpeg = require_binary("ffmpeg")
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-i",
        str(media_path),
        "-filter:v",
        f"select='gt(scene,{threshold})',showinfo",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise command_failed("detect_scenes", cmd, exc) from exc

    scene_times: list[float] = []
    for match in re.finditer(r"pts_time:([0-9.]+)", result.stderr):
        scene_time = float(match.group(1))
        if not scene_times or scene_time - scene_times[-1] >= min_scene_gap:
            scene_times.append(scene_time)

    return {
        "ok": True,
        "path": str(media_path),
        "threshold": threshold,
        "min_scene_gap": min_scene_gap,
        "scene_count": len(scene_times),
        "scene_times": scene_times,
    }


def generate_thumbnails(
    path: str | Path,
    output_directory: str | Path | None = None,
    count: int = 5,
) -> dict[str, Any]:
    media_path = as_path(path)
    probe = probe_media(media_path)
    if not probe.ok:
        return _probe_failure(probe)
    if not probe.has_video:
        return {
            "ok": False,
            "error": {
                "code": "no_video_stream",
                "message": f"No video stream found in {probe.path}.",
                "suggested_fix": "Use a video file for thumbnail generation.",
                "details": {"path": probe.path},
            },
        }

    ffmpeg = require_binary("ffmpeg")
    duration = probe.duration or 0
    if duration <= 0:
        timestamps = [0.0]
    else:
        safe_count = max(1, min(count, 20))
        step = duration / (safe_count + 1)
        timestamps = [round(step * index, 3) for index in range(1, safe_count + 1)]

    output_root = as_path(output_directory) if output_directory else output_dir() / "thumbnails" / media_path.stem
    output_root.mkdir(parents=True, exist_ok=True)
    thumbnail_paths: list[str] = []

    for index, timestamp in enumerate(timestamps, start=1):
        output_path = output_root / f"thumb_{index:03d}.jpg"
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            str(timestamp),
            "-i",
            str(media_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as exc:
            raise command_failed("generate_thumbnail", cmd, exc) from exc
        thumbnail_paths.append(str(output_path))

    return {
        "ok": True,
        "path": str(media_path),
        "output_directory": str(output_root),
        "count": len(thumbnail_paths),
        "timestamps": timestamps,
        "thumbnails": thumbnail_paths,
    }


def inspect_project(project_id: str) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    assets = manifest.assets
    usable_videos = [asset for asset in assets if asset.ok and asset.has_video]
    failed_assets = [asset for asset in assets if not asset.ok]

    return {
        "ok": True,
        "project_id": manifest.project_id,
        "name": manifest.name,
        "prompt": manifest.prompt,
        "input_dir": manifest.input_dir,
        "music_path": manifest.music_path,
        "platforms": [platform.value for platform in manifest.platforms],
        "summary": {
            "asset_count": len(assets),
            "usable_video_count": len(usable_videos),
            "failed_asset_count": len(failed_assets),
            "timeline_count": len(manifest.timelines),
            "output_count": len(manifest.outputs),
        },
        "assets": [asset.model_dump() for asset in assets],
        "timelines": {key: timeline.model_dump() for key, timeline in manifest.timelines.items()},
        "outputs": {key: output.model_dump() for key, output in manifest.outputs.items()},
    }
