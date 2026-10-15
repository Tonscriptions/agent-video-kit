from __future__ import annotations

import json
import mimetypes
import shutil
from pathlib import Path
from typing import Any

from .errors import AppError, dependency_error, missing_asset
from .captions import parse_caption_file
from .project import TICKS_PER_SECOND
from .utils import executable, run_process, safe_filename, sha256_file


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mxf", ".ts", ".m4v"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".aac", ".flac", ".m4a", ".ogg", ".opus"}
SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass", ".ssa", ".ttml", ".dfxp", ".xml"}
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}
MAX_INPUT_BYTES = 2 * 1024 * 1024 * 1024
MAX_DURATION_SECONDS = 2 * 60 * 60
MAX_DIMENSION = 8192


def ffprobe_path() -> str:
    value = executable("ffprobe")
    if not value:
        raise dependency_error("找不到 ffprobe", "安装原生 FFmpeg 并确保 ffprobe.exe 在 PATH")
    return value


def ffmpeg_path() -> str:
    value = executable("ffmpeg")
    if not value:
        raise dependency_error("找不到 ffmpeg", "安装原生 FFmpeg 并确保 ffmpeg.exe 在 PATH")
    return value


def ffmpeg_version() -> str:
    try:
        result = run_process([ffmpeg_path(), "-version"], timeout=10)
    except AppError:
        return "unavailable"
    first = (result.stdout or result.stderr).splitlines()
    return first[0] if first else "unknown"


def classify_path(path: Path, probe: dict[str, Any] | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix in FONT_EXTENSIONS:
        return "font"
    if suffix in SUBTITLE_EXTENSIONS:
        return "subtitle"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if probe:
        streams = probe.get("streams", [])
        if any(item.get("codec_type") == "video" for item in streams):
            return "video"
        if any(item.get("codec_type") == "audio" for item in streams):
            return "audio"
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and guessed.startswith("image/"):
        return "image"
    if guessed and guessed.startswith("audio/"):
        return "audio"
    return "video"


def _duration_seconds(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _timestamp_seconds(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def probe_media(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise missing_asset(f"媒体文件不存在: {path}", str(path))
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise AppError("MEDIA_TOO_LARGE", f"媒体超过单文件限制 {MAX_INPUT_BYTES} 字节: {path}", exit_code=3, path=str(path))
    if path.suffix.lower() in FONT_EXTENSIONS:
        try:
            from PIL import ImageFont
        except ImportError as exc:
            raise dependency_error("字体导入需要本地 Pillow/FreeType", "使用已安装的本地依赖，不会自动安装") from exc
        try:
            font = ImageFont.truetype(str(path), size=32)
            family, style = font.getname()
        except (OSError, ValueError) as exc:
            raise AppError("FONT_PROBE_FAILED", "本地 FreeType 无法读取字体", exit_code=3, path=str(path), cause=str(exc)) from exc
        return {"duration_seconds": 0.0, "duration_tick": 0, "format": path.suffix.lower().lstrip("."), "format_long_name": "local font", "streams": [], "font": {"family": family, "style": style, "face_index": 0, "engine": "pillow-freetype"}, "video": {"codec": None}, "audio": {"codec": None, "sample_rate": 0, "channels": 0}}
    if path.suffix.lower() in SUBTITLE_EXTENSIONS:
        cues = parse_caption_file(path)
        duration = max((float(cue.get("end", 0.0)) for cue in cues), default=0.0)
        return {
            "duration_seconds": duration,
            "duration_tick": int(round(duration * TICKS_PER_SECOND)),
            "format": path.suffix.lower().lstrip("."),
            "format_long_name": "local subtitle",
            "streams": [{"codec_type": "subtitle", "codec_name": path.suffix.lower().lstrip(".")}],
            "video": {"codec": None, "width": None, "height": None, "pix_fmt": None, "fps": None, "color_space": None},
            "audio": {"codec": None, "sample_rate": 0, "channels": 0},
            "subtitle": {"format": path.suffix.lower().lstrip("."), "cue_count": len(cues)},
        }
    result = run_process(
        [ffprobe_path(), "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json", str(path)],
        timeout=60,
    )
    if result.returncode != 0:
        raise AppError("MEDIA_PROBE_FAILED", f"ffprobe 无法读取媒体: {path}", exit_code=3, path=str(path), cause=result.stderr[-2000:])
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AppError("MEDIA_PROBE_INVALID", f"ffprobe 输出不是 JSON: {path}", exit_code=3, cause=str(exc)) from exc
    streams = raw.get("streams", [])
    duration = _duration_seconds(raw.get("format", {}).get("duration"))
    if not duration:
        durations = [_duration_seconds(item.get("duration")) for item in streams]
        duration = max(durations, default=0.0)
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
    if duration > MAX_DURATION_SECONDS:
        raise AppError("MEDIA_DURATION_TOO_LONG", f"媒体超过 {MAX_DURATION_SECONDS} 秒限制: {path}", exit_code=3, path=str(path))
    if max(int(video.get("width", 0) or 0), int(video.get("height", 0) or 0)) > MAX_DIMENSION:
        raise AppError("MEDIA_DIMENSION_TOO_LARGE", f"媒体分辨率超过 {MAX_DIMENSION} 像素限制: {path}", exit_code=3, path=str(path))
    return {
        "duration_seconds": duration,
        "duration_tick": int(round(duration * TICKS_PER_SECOND)),
        "format": raw.get("format", {}).get("format_name"),
        "format_long_name": raw.get("format", {}).get("format_long_name"),
        "streams": streams,
        "video": {
            "codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "pix_fmt": video.get("pix_fmt"),
            "fps": video.get("r_frame_rate"),
            "color_space": video.get("color_space"),
            "duration_seconds": _duration_seconds(video.get("duration")),
            "start_time_seconds": _timestamp_seconds(video.get("start_time")),
        },
        "audio": {
            "codec": audio.get("codec_name"),
            "sample_rate": int(audio.get("sample_rate", 0) or 0),
            "channels": int(audio.get("channels", 0) or 0),
            "duration_seconds": _duration_seconds(audio.get("duration")),
            "start_time_seconds": _timestamp_seconds(audio.get("start_time")),
        },
    }


def _run_media_tool(args: list[str], *, output: Path, operation: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    result = run_process(args, timeout=1800)
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        raise AppError("MEDIA_PREPARE_FAILED", f"{operation} 生成失败: {output}", exit_code=6, retryable=True, path=str(output), cause=(result.stderr or result.stdout)[-4000:])


def generate_proxy(source: Path, output: Path, *, width: int = 1280) -> Path:
    if width < 160:
        raise AppError("PROXY_WIDTH_INVALID", "代理宽度必须不小于 160", exit_code=2, path="proxy_width")
    probe = probe_media(source)
    if not probe.get("video", {}).get("codec"):
        raise AppError("PROXY_VIDEO_MISSING", "只有包含视频流的素材可以生成视频代理", exit_code=4, path=str(source))
    _run_media_tool(
        [
            ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-vf", f"scale=w='min({int(width)},iw)':h=-2:force_original_aspect_ratio=decrease",
            "-c:v", "libx264", "-preset", "fast", "-crf", "26", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(output),
        ],
        output=output,
        operation="proxy",
    )
    return output


def generate_thumbnail(source: Path, output: Path, *, at_seconds: float = 0.0, width: int = 640) -> Path:
    if width < 64:
        raise AppError("THUMBNAIL_WIDTH_INVALID", "缩略图宽度必须不小于 64", exit_code=2, path="thumbnail_width")
    _run_media_tool(
        [
            ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{max(0.0, at_seconds):.3f}", "-i", str(source),
            "-frames:v", "1", "-vf", f"scale=w='min({int(width)},iw)':h=-2:force_original_aspect_ratio=decrease",
            "-q:v", "3", str(output),
        ],
        output=output,
        operation="thumbnail",
    )
    return output


def generate_waveform(source: Path, output: Path, *, width: int = 1600, height: int = 320) -> Path:
    if width < 128 or height < 64:
        raise AppError("WAVEFORM_SIZE_INVALID", "波形尺寸过小", exit_code=2, path="waveform")
    _run_media_tool(
        [
            ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-filter_complex", f"aformat=channel_layouts=stereo,showwavespic=s={int(width)}x{int(height)}:colors=0x4fd1c5",
            "-frames:v", "1", str(output),
        ],
        output=output,
        operation="waveform",
    )
    return output


def _stabilization_filter_path(path: Path) -> str:
    """Encode a local Windows path for an FFmpeg filter option."""
    # The transform pass runs with its working directory set to the cache
    # folder, so callers normally pass a short relative path.  Keep this
    # helper strict for the rare absolute path case and never accept a URL.
    value = str(path).replace("\\", "/").replace("'", "\\'")
    return value.replace(":", r"\\:")


def stabilize_media(
    source: Path,
    output: Path,
    transform_dir: Path,
    *,
    shakiness: int = 5,
    accuracy: int = 15,
    stepsize: int = 6,
    mincontrast: float = 0.25,
    smoothing: int = 15,
    maxshift: int = -1,
    maxangle: float = -1.0,
    crop: str = "keep",
    optzoom: int = 1,
    zoom: float = 0.0,
    interpol: str = "bilinear",
) -> dict[str, Any]:
    """Run the local two-pass vidstab pipeline and return auditable evidence."""
    probe = probe_media(source)
    if not probe.get("video", {}).get("codec"):
        raise AppError("STABILIZE_VIDEO_MISSING", "只有包含视频流的素材可以防抖", exit_code=4, path=str(source))
    filters = run_process([ffmpeg_path(), "-hide_banner", "-filters"], timeout=30)
    filter_text = f"{filters.stdout}\n{filters.stderr}"
    if "vidstabdetect" not in filter_text or "vidstabtransform" not in filter_text:
        raise dependency_error("当前 FFmpeg 未编译 vidstabdetect/vidstabtransform", "更换带 libvidstab 的本地 FFmpeg 构建")
    if not 1 <= int(shakiness) <= 10:
        raise AppError("STABILIZE_PARAMETER_INVALID", "shakiness 必须位于 1..10", exit_code=2, path="shakiness")
    if not 1 <= int(accuracy) <= 15 or int(accuracy) < int(shakiness):
        raise AppError("STABILIZE_PARAMETER_INVALID", "accuracy 必须位于 shakiness..15", exit_code=2, path="accuracy")
    if not 1 <= int(stepsize) <= 32:
        raise AppError("STABILIZE_PARAMETER_INVALID", "stepsize 必须位于 1..32", exit_code=2, path="stepsize")
    if not 0.0 <= float(mincontrast) <= 1.0:
        raise AppError("STABILIZE_PARAMETER_INVALID", "mincontrast 必须位于 0..1", exit_code=2, path="mincontrast")
    if not 0 <= int(smoothing) <= 1000:
        raise AppError("STABILIZE_PARAMETER_INVALID", "smoothing 必须位于 0..1000", exit_code=2, path="smoothing")
    if not -1 <= int(maxshift) <= 500:
        raise AppError("STABILIZE_PARAMETER_INVALID", "maxshift 必须位于 -1..500", exit_code=2, path="maxshift")
    if not -1.0 <= float(maxangle) <= 3.14:
        raise AppError("STABILIZE_PARAMETER_INVALID", "maxangle 必须位于 -1..3.14", exit_code=2, path="maxangle")
    if crop not in {"keep", "black"}:
        raise AppError("STABILIZE_PARAMETER_INVALID", "crop 只能是 keep 或 black", exit_code=2, path="crop")
    if not 0 <= int(optzoom) <= 2:
        raise AppError("STABILIZE_PARAMETER_INVALID", "optzoom 必须位于 0..2", exit_code=2, path="optzoom")
    if not -100.0 <= float(zoom) <= 100.0:
        raise AppError("STABILIZE_PARAMETER_INVALID", "zoom 必须位于 -100..100", exit_code=2, path="zoom")
    if interpol not in {"no", "linear", "bilinear", "bicubic"}:
        raise AppError("STABILIZE_PARAMETER_INVALID", "interpol 不是本地 vidstabtransform 支持的值", exit_code=2, path="interpol")
    transform_dir.mkdir(parents=True, exist_ok=True)
    transform_file = transform_dir / "transforms.trf"
    if transform_file.exists():
        transform_file.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)
    detect_filter = (
        "vidstabdetect=result=transforms.trf:"
        f"shakiness={int(shakiness)}:accuracy={int(accuracy)}:stepsize={int(stepsize)}:"
        f"mincontrast={float(mincontrast):.6f}:fileformat=2"
    )
    detected = run_process(
        [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vf", detect_filter, "-an", "-f", "null", "-"],
        timeout=1800,
        cwd=transform_dir,
    )
    if detected.returncode != 0 or not transform_file.exists() or transform_file.stat().st_size == 0:
        raise AppError("STABILIZE_DETECT_FAILED", "vidstabdetect 分析失败", exit_code=6, retryable=True, path=str(source), cause=(detected.stderr or detected.stdout)[-4000:])
    transform_filter = (
        f"vidstabtransform=input={_stabilization_filter_path(transform_file.name)}:smoothing={int(smoothing)}:"
        f"maxshift={int(maxshift)}:maxangle={float(maxangle):.6f}:crop={'0' if crop == 'keep' else '1'}:"
        f"optzoom={int(optzoom)}:zoom={float(zoom):.6f}:interpol={interpol}"
    )
    transformed = run_process(
        [
            ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-vf", transform_filter, "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output),
        ],
        timeout=1800,
        cwd=transform_dir,
    )
    if transformed.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        raise AppError("STABILIZE_TRANSFORM_FAILED", "vidstabtransform 输出失败", exit_code=6, retryable=True, path=str(output), cause=(transformed.stderr or transformed.stdout)[-4000:])
    return {
        "source": str(source),
        "output": str(output),
        "transform_file": str(transform_file),
        "source_sha256": f"sha256:{sha256_file(source)}",
        "transform_sha256": f"sha256:{sha256_file(transform_file)}",
        "output_sha256": f"sha256:{sha256_file(output)}",
        "parameters": {
            "shakiness": int(shakiness), "accuracy": int(accuracy), "stepsize": int(stepsize),
            "mincontrast": float(mincontrast), "smoothing": int(smoothing), "maxshift": int(maxshift),
            "maxangle": float(maxangle), "crop": crop, "optzoom": int(optzoom), "zoom": float(zoom), "interpol": interpol,
        },
        "probe": probe_media(output),
        "engine": "ffmpeg-local:vidstabdetect+vidstabtransform",
    }


def relink_missing_assets(root: Path, project: dict[str, Any], search_root: Path, *, match_by_name: bool = False) -> dict[str, Any]:
    """Relink missing local assets by content hash, with opt-in name fallback.

    Matching files are copied into the project so subsequent renders remain
    self-contained. Hash matches are ``Exact``; basename fallback is
    ``Approximate`` and must be reviewed before publishing.
    """
    search_root = search_root.expanduser().resolve()
    if not search_root.exists() or not search_root.is_dir():
        raise AppError("RELINK_ROOT_MISSING", f"重链接搜索目录不存在: {search_root}", exit_code=3, path=str(search_root))
    assets = project.get("assets", [])
    candidates: list[Path] = []
    for path in search_root.rglob("*"):
        if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
            continue
        if path.suffix.lower() in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | SUBTITLE_EXTENSIONS:
            candidates.append(path)
    hash_index: dict[str, list[Path]] = {}
    for path in candidates:
        try:
            digest = sha256_file(path)
        except OSError:
            continue
        hash_index.setdefault(digest, []).append(path)
    entries: list[dict[str, Any]] = []
    relinked = 0
    for asset in assets:
        uri = Path(str(asset.get("uri", "")))
        if not uri.is_absolute():
            uri = root / uri
        if uri.exists():
            entries.append({"asset_id": asset.get("id"), "status": "Skipped", "reason": "asset_exists", "current": str(uri)})
            continue
        expected = str(asset.get("sha256", "")).lower().removeprefix("sha256:")
        matches = hash_index.get(expected, []) if expected else []
        status = "Exact"
        source: Path | None = matches[0] if len(matches) == 1 else None
        if source is None and match_by_name:
            basename = uri.name or str(asset.get("source", {}).get("original_name", ""))
            named = [item for item in candidates if item.name == basename]
            if len(named) == 1:
                source = named[0]
                status = "Approximate"
        if source is None:
            entries.append({"asset_id": asset.get("id"), "status": "Failed", "reason": "no_unique_match", "expected_sha256": asset.get("sha256"), "previous_uri": str(uri)})
            continue
        destination = root / "assets" / f"relinked_{safe_filename(str(asset.get('id', 'asset')))}_{safe_filename(source.name)}"
        shutil.copy2(source, destination)
        digest = sha256_file(destination)
        asset["uri"] = str(destination.relative_to(root)).replace("\\", "/")
        asset["sha256"] = f"sha256:{digest}"
        asset["probe"] = probe_media(destination)
        asset.setdefault("source", {})["relinked_from"] = str(source)
        entries.append({"asset_id": asset.get("id"), "status": status, "source": str(source), "destination": str(destination), "sha256": asset["sha256"]})
        relinked += 1
    return {"search_root": str(search_root), "relinked": relinked, "entries": entries}
