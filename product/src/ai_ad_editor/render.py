from __future__ import annotations

import json
import math
import os
import copy
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .errors import AppError, dependency_error
from .media import ffmpeg_path, probe_media
from .policy import resolve_local_path
from .project import asset_map
from .quality import check_output
from .text_layout import build_text_layout, graphemes, text_width, word_ranges
from .utils import atomic_write_json, new_id, now_iso, run_process, sha256_bytes, sha256_file


OUTPUT_PROFILES: dict[str, tuple[int, int]] = {
    "vertical": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
    "vertical_720": (720, 1280),
    "landscape_720": (1280, 720),
}

OUTPUT_CONTAINERS: dict[str, str] = {
    "mp4": "mp4",
    "webm": "webm",
    "mkv": "matroska",
}

OUTPUT_PIXEL_FORMATS = (
    "yuv420p",
    "yuv422p",
    "yuv444p",
    "yuv420p10le",
    "yuv422p10le",
    "yuv444p10le",
    "yuva420p",
)

ALPHA_OUTPUT_PIXEL_FORMATS = ("yuva420p",)

# Names accepted by the local FFmpeg xfade filter.  ``crossfade``/``dissolve``
# and directional ``wipe``/``slide`` are Agent-friendly aliases; the remaining
# names map one-to-one so a template can expose the same transition catalog as
# the installed FFmpeg build without a GUI-only effect registry.
XFADE_TRANSITIONS = {
    "fade", "wipeleft", "wiperight", "wipeup", "wipedown", "slideleft", "slideright", "slideup", "slidedown",
    "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite", "radial", "smoothleft", "smoothright",
    "smoothup", "smoothdown", "circleopen", "circleclose", "horzopen", "horzclose", "vertopen", "vertclose",
    "diagtl", "diagtr", "diagbl", "diagbr", "hlslice", "hrslice", "vuslice", "vdslice", "pixelize", "zoomin",
    "fadefast", "fadeslow", "hlwind", "hrwind", "vuwind", "vdwind", "coverleft", "coverright", "coverup",
    "coverdown", "revealleft", "revealright", "revealup", "revealdown", "wipetl", "wipetr", "wipebl", "wipebr",
    "hblur", "fadegrays", "squeezeh", "squeezev",
}

TONE_MAP_ALGORITHMS = {"linear", "gamma", "clip", "reinhard", "hable", "mobius"}
TONE_MAP_INPUT_TRANSFERS = {"bt2020-10", "bt2020-12", "smpte2084", "arib-std-b67"}

DEFAULT_OUTPUT: dict[str, Any] = {
    "container": "mp4",
    "video": {"codec": "libx264", "preset": "medium", "crf": 18, "pixel_format": "yuv420p"},
    "audio": {"codec": "aac", "bitrate": "192k"},
}


def output_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized, JSON-safe output encoder configuration."""
    raw = settings.get("output") if isinstance(settings.get("output"), dict) else {}
    video_raw = raw.get("video") if isinstance(raw.get("video"), dict) else {}
    audio_raw = raw.get("audio") if isinstance(raw.get("audio"), dict) else {}
    container = str(raw.get("container", DEFAULT_OUTPUT["container"])).lower()
    if container not in OUTPUT_CONTAINERS:
        raise AppError("OUTPUT_CONTAINER_UNSUPPORTED", f"不支持的输出容器: {container}", exit_code=2, path="settings.output.container")
    video_codec = str(video_raw.get("codec", DEFAULT_OUTPUT["video"]["codec"]))
    audio_codec = str(audio_raw.get("codec", DEFAULT_OUTPUT["audio"]["codec"]))
    if audio_codec == "opus":
        audio_codec = "libopus"
    if video_codec not in {"libx264", "libx265", "libvpx-vp9", "libvpx", "libaom-av1"}:
        raise AppError("OUTPUT_VIDEO_CODEC_UNSUPPORTED", f"不支持的视频编码器: {video_codec}", exit_code=2, path="settings.output.video.codec")
    if audio_codec not in {"aac", "libopus", "pcm_s16le"}:
        raise AppError("OUTPUT_AUDIO_CODEC_UNSUPPORTED", f"不支持的音频编码器: {audio_codec}", exit_code=2, path="settings.output.audio.codec")
    try:
        crf = int(video_raw.get("crf", DEFAULT_OUTPUT["video"]["crf"]))
    except (TypeError, ValueError) as exc:
        raise AppError("OUTPUT_CRF_INVALID", "视频 CRF 必须是整数", exit_code=2, path="settings.output.video.crf") from exc
    max_crf = 51 if video_codec in {"libx264", "libx265"} else 63
    if crf < 0 or crf > max_crf:
        raise AppError("OUTPUT_CRF_INVALID", f"{video_codec} 的 CRF 必须在 0 到 {max_crf} 之间", exit_code=2, path="settings.output.video.crf")
    pixel_format = str(video_raw.get("pixel_format", DEFAULT_OUTPUT["video"]["pixel_format"]))
    if pixel_format not in set(OUTPUT_PIXEL_FORMATS):
        raise AppError("OUTPUT_PIXEL_FORMAT_INVALID", f"不支持的像素格式: {pixel_format}", exit_code=2, path="settings.output.video.pixel_format")
    if pixel_format in ALPHA_OUTPUT_PIXEL_FORMATS and (container != "webm" or video_codec not in {"libvpx-vp9", "libvpx"}):
        raise AppError("OUTPUT_ALPHA_UNSUPPORTED", "透明视频当前只支持 WebM + VP9/VP8 + yuva420p", exit_code=2, path="settings.output")
    if container == "webm" and (video_codec not in {"libvpx-vp9", "libvpx", "libaom-av1"} or audio_codec not in {"libopus", "opus"}):
        raise AppError("OUTPUT_CODEC_CONTAINER_MISMATCH", "webm 需要 VP8/VP9/AV1 视频和 Opus 音频", exit_code=2, path="settings.output")
    if container == "mp4" and audio_codec in {"libopus", "opus"}:
        raise AppError("OUTPUT_CODEC_CONTAINER_MISMATCH", "mp4 当前只接受 AAC 音频", exit_code=2, path="settings.output.audio.codec")
    if container == "mp4" and audio_codec == "pcm_s16le":
        raise AppError("OUTPUT_CODEC_CONTAINER_MISMATCH", "mp4 不支持当前 PCM 音频输出，请使用 AAC 或 MKV", exit_code=2, path="settings.output.audio.codec")
    normalized = {
        "container": container,
        "video": {"codec": video_codec, "preset": str(video_raw.get("preset", DEFAULT_OUTPUT["video"]["preset"])), "crf": crf, "pixel_format": pixel_format},
        "audio": {"codec": audio_codec, "bitrate": str(audio_raw.get("bitrate", DEFAULT_OUTPUT["audio"]["bitrate"]))},
    }
    if video_raw.get("bitrate"):
        normalized["video"]["bitrate"] = str(video_raw["bitrate"])
    for branch in ("video", "audio"):
        bitrate = normalized[branch].get("bitrate")
        if bitrate is not None and not re.fullmatch(r"[1-9][0-9]*(?:\.[0-9]+)?[kKmM]?", str(bitrate)):
            raise AppError("OUTPUT_BITRATE_INVALID", "码率必须是正数及可选 k/M 后缀，例如 192k 或 8M", exit_code=2, path=f"settings.output.{branch}.bitrate")
    if normalized["video"]["preset"] not in {"ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"}:
        raise AppError("OUTPUT_PRESET_INVALID", "编码 preset 不在支持列表中", exit_code=2, path="settings.output.video.preset")
    return normalized


def _output_color_args(settings: dict[str, Any]) -> list[str]:
    """Translate project color metadata into explicit FFmpeg output flags."""
    color = settings.get("color") if isinstance(settings.get("color"), dict) else {}
    values = {
        "-color_primaries": color.get("primaries"),
        "-color_trc": color.get("transfer"),
        "-colorspace": color.get("matrix"),
    }
    raw_range = str(color.get("range", "")).strip().lower()
    if raw_range:
        values["-color_range"] = {"limited": "tv", "full": "pc"}.get(raw_range, raw_range)
    args: list[str] = []
    for flag, raw_value in values.items():
        if raw_value is None or str(raw_value).strip() == "":
            continue
        value = str(raw_value).strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise AppError("COLOR_METADATA_INVALID", f"色彩元数据值无效: {value}", exit_code=2, path="settings.color")
        args.extend([flag, value])
    return args


def _sec(tick: int, tps: int) -> float:
    return tick / float(tps)


def _quoted(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _num(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _tone_map_filters(settings: dict[str, Any], warnings: list[dict[str, Any]], clip_id: str, *, transparent: bool = False) -> list[str]:
    """Build an explicit local HDR-to-SDR tonemap chain when requested.

    The project color block describes the output metadata by default. HDR input
    details are opt-in under ``input_*`` fields so SDR projects never pay the
    zscale/float conversion cost or silently reinterpret their footage.
    """
    color = settings.get("color") if isinstance(settings.get("color"), dict) else {}
    algorithm = str(color.get("tone_map", color.get("tone_mapping", "none"))).strip().lower()
    if not algorithm or algorithm == "none":
        return []
    if algorithm not in TONE_MAP_ALGORITHMS:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "hdr_tonemap", "message": f"不支持的 HDR tone map 算法: {algorithm}"})
        return []
    if transparent:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "hdr_tonemap_with_alpha", "message": "当前 HDR tone map 不与透明 yuva 画布组合，已跳过"})
        return []
    input_transfer = str(color.get("input_transfer", "smpte2084")).strip().lower()
    input_primaries = str(color.get("input_primaries", "bt2020")).strip().lower()
    input_matrix = str(color.get("input_matrix", "bt2020nc")).strip().lower()
    input_range = str(color.get("input_range", "limited")).strip().lower()
    if input_transfer not in TONE_MAP_INPUT_TRANSFERS or input_primaries not in {"bt2020", "bt709"} or input_matrix not in {"bt2020nc", "bt2020c", "bt709"} or input_range not in {"limited", "full", "tv", "pc"}:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "hdr_tonemap", "message": "HDR 输入色彩字段无效，已跳过 tone map"})
        return []
    range_name = {"limited": "tv", "full": "pc", "tv": "tv", "pc": "pc"}[input_range]
    desat = max(0.0, _num(color.get("tone_map_desat", 2.0), 2.0))
    peak = max(0.0, _num(color.get("tone_map_peak", 0.0), 0.0))
    tonemap = f"tonemap=tonemap={algorithm}:desat={desat:.4f}"
    if peak > 0:
        tonemap += f":peak={peak:.4f}"
    return [
        f"zscale=rin={range_name}:pin={input_primaries}:tin={input_transfer}:min={input_matrix}:t=linear:m=bt2020nc:p=bt2020:r=tv",
        "format=gbrpf32le",
        tonemap,
        "zscale=t=bt709:m=bt709:p=bt709:r=tv",
        "format=rgba",
    ]


def _tick(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _expr_arg(expression: str) -> str:
    """Keep commas in a quoted FFmpeg expression inside one filter argument."""
    return "'" + expression.replace("'", "\\'") + "'"


def _drawtext_arg(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace(",", "\\,").replace("%", "\\%").replace("\n", "\\n")


def _wrap_subtitle_text(text: str, style: dict[str, Any], font_size: int, warnings: list[dict[str, Any]], clip_id: str, font_metrics: Any = None) -> str:
    """Wrap with the selected local font, disclosing the fallback explicitly."""
    layout = build_text_layout(text, style, font_metrics, font_size)
    if style.get("max_width", style.get("wrap_width")) is not None and font_metrics is None:
        warnings.append({
            "code": "RENDER_FEATURE_APPROXIMATE",
            "clip_id": clip_id,
            "feature": "subtitle_layout_wrap",
            "message": "字幕 max_width 使用本地平均字宽换行；精确字形度量仍由字体 golden render 校准",
        })
    return layout.text


def _subtitle_font_path(root: Path, style: dict[str, Any], assets: dict[str, dict[str, Any]] | None = None) -> Path | None:
    font_id = style.get("font_asset_id")
    if font_id:
        font_asset = (assets or {}).get(str(font_id))
        if not font_asset or font_asset.get("kind") != "font":
            raise AppError("SUBTITLE_FONT_REFERENCE_INVALID", "font_asset_id 必须引用本地 font 资产", exit_code=2, path=str(font_id))
        font_value = font_asset.get("uri")
    else:
        font_value = style.get("fontfile")
    if font_value:
        font = resolve_local_path(root, font_value, field="subtitle.style.fontfile")
        if not font.is_file():
            raise AppError("SUBTITLE_FONT_MISSING", "字幕字体文件不存在", exit_code=3, path=str(font))
        return font.resolve()
    windir = Path(os.environ.get("WINDIR", "C:/Windows"))
    return next((candidate for candidate in (windir / "Fonts" / "arial.ttf", windir / "Fonts" / "segoeui.ttf", windir / "Fonts" / "msyh.ttc", windir / "Fonts" / "simhei.ttf") if candidate.is_file()), None)


def _load_subtitle_font_metrics(font_path: Path | None, font_size: int) -> Any:
    """Load optional local Pillow metrics without making Pillow a hard dependency."""
    if font_path is None or not font_path.exists():
        return None
    try:
        from PIL import ImageFont

        return ImageFont.truetype(str(font_path), size=max(1, int(font_size)))
    except Exception:
        return None


def _subtitle_text_width(font_metrics: Any, text: str, font_size: int) -> float:
    return text_width(font_metrics, text, font_size)


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _mask_keyframe_expr(
    clip: dict[str, Any],
    mask: dict[str, Any],
    properties: tuple[str, ...],
    default: float,
    clip_start: float,
    tps: int,
) -> str:
    """Resolve a mask scalar from clip or mask-local keyframes.

    Mask-local tracks use the same shape as regular clip keyframes.  Keeping
    the evaluator shared makes mask motion deterministic and means Agents can
    author either ``mask.cx`` or a local ``cx`` property without another
    timing dialect.
    """
    aliases = tuple(dict.fromkeys(value if value.startswith("mask.") else f"mask.{value}" for value in properties))
    local_tracks = mask.get("keyframes") if isinstance(mask.get("keyframes"), list) else []
    clip_tracks = clip.get("keyframes") if isinstance(clip.get("keyframes"), list) else []

    def normalize(item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        name = str(item.get("property", ""))
        if name.startswith("mask.") or name.startswith("transform.") or name.startswith("audio."):
            return item
        return {**item, "property": f"mask.{name}"}

    normalized_clip = [item for raw in clip_tracks if (item := normalize(raw)) is not None]
    normalized_local = [item for raw in local_tracks if (item := normalize(raw)) is not None]
    if normalized_local or normalized_clip != clip_tracks:
        merged = dict(clip)
        merged["keyframes"] = [*normalized_clip, *normalized_local]
    else:
        merged = clip
    expression = _keyframe_expr(merged, aliases, default, clip_start, tps, time_variable="T")
    return f"clip(({expression}),0,1)"


def _mask_has_keyframe(clip: dict[str, Any], mask: dict[str, Any], properties: tuple[str, ...]) -> bool:
    """Return whether a mask scalar is animated in either keyframe location."""
    aliases = {name if name.startswith("mask.") else f"mask.{name}" for name in properties}
    tracks = []
    if isinstance(clip.get("keyframes"), list):
        tracks.extend(clip["keyframes"])
    if isinstance(mask.get("keyframes"), list):
        tracks.extend(mask["keyframes"])
    for track in tracks:
        if not isinstance(track, dict):
            continue
        name = str(track.get("property", ""))
        normalized = name if name.startswith("mask.") else f"mask.{name}"
        if normalized in aliases:
            return True
    return False


def _crop_keyframe_expr(
    clip: dict[str, Any],
    crop: dict[str, Any],
    properties: tuple[str, ...],
    default: float,
    clip_start: float,
    tps: int,
    *,
    time_variable: str = "t",
) -> str:
    """Resolve a crop scalar from clip or crop-local keyframes.

    Crop-local tracks may use short names (``x``/``y``); clip-level tracks use
    the explicit ``crop.x``/``crop.y`` namespace so they cannot collide with
    mask geometry tracks.  Native crop uses ``t`` for animated position;
    the fixed-canvas inverse sampler uses ``T`` for position and size.
    """
    aliases = tuple(dict.fromkeys(name if name.startswith("crop.") else f"crop.{name}" for name in properties))
    clip_tracks = clip.get("keyframes") if isinstance(clip.get("keyframes"), list) else []
    local_tracks = crop.get("keyframes") if isinstance(crop.get("keyframes"), list) else []
    normalized_local: list[dict[str, Any]] = []
    for item in local_tracks:
        if not isinstance(item, dict):
            continue
        name = str(item.get("property", ""))
        if not name.startswith("crop."):
            item = {**item, "property": f"crop.{name}"}
        normalized_local.append(item)
    merged = dict(clip)
    merged["keyframes"] = [*clip_tracks, *normalized_local]
    return _keyframe_expr(merged, aliases, default, clip_start, tps, time_variable=time_variable)


def _crop_has_keyframe(clip: dict[str, Any], crop: dict[str, Any], properties: tuple[str, ...]) -> bool:
    """Return whether a crop scalar is animated in either keyframe location."""
    aliases = {name if name.startswith("crop.") else f"crop.{name}" for name in properties}
    for track in clip.get("keyframes", []):
        if not isinstance(track, dict):
            continue
        if str(track.get("property", "")) in aliases:
            return True
    for track in crop.get("keyframes", []):
        if not isinstance(track, dict):
            continue
        name = str(track.get("property", ""))
        normalized = name if name.startswith("crop.") else f"crop.{name}"
        if normalized in aliases:
            return True
    return False


def _dynamic_crop_filters(
    clip: dict[str, Any],
    crop: dict[str, Any],
    canvas_width: int,
    canvas_height: int,
    source_width: int,
    source_height: int,
    clip_start: float,
    tps: int,
) -> list[str]:
    """Animate a crop window while keeping every output frame the same size.

    geq samples the original RGB and alpha planes with bilinear interpolation.
    It keeps the native raster size until the final canvas resize, so small
    crop windows do not allocate an enormous zoomed intermediate frame.  Fit
    bars are opaque black, matching the static crop/pad contract.  Each plane
    has its own expression state; registers are initialized for every pixel.
    """
    normalized = str(crop.get("unit", "pixels")).lower() in {"normalized", "relative"}
    default_width = 1.0 if normalized else float(source_width or canvas_width)
    default_height = 1.0 if normalized else float(source_height or canvas_height)

    def scalar(names: tuple[str, ...], default: float) -> str:
        return _crop_keyframe_expr(clip, crop, names, default, clip_start, tps, time_variable="T")

    window_width = scalar(("width", "w"), _num(crop.get("width", crop.get("w", default_width)), default_width))
    window_height = scalar(("height", "h"), _num(crop.get("height", crop.get("h", default_height)), default_height))
    origin_x = scalar(("x",), _num(crop.get("x", 0), 0))
    origin_y = scalar(("y",), _num(crop.get("y", 0), 0))
    if normalized:
        window_width, window_height = f"W*({window_width})", f"H*({window_height})"
        origin_x, origin_y = f"W*({origin_x})", f"H*({origin_y})"
    # Clamp size before position so overshooting easing or a moving origin
    # cannot sample beyond the source. Tiny positive windows have a two-pixel
    # floor, the same minimum as the native static crop implementation.
    setup = (
        f"st(0,min(W,max(2,({window_width}))));"
        f"st(1,min(H,max(2,({window_height}))));"
        f"st(2,clip(({origin_x}),0,W-ld(0)));"
        f"st(3,clip(({origin_y}),0,H-ld(1)));"
    )
    fit = str(crop.get("fit", crop.get("mode", "fit"))).lower()
    if fit == "stretch":
        setup += (
            "st(7,ld(2)+(X+0.5)*ld(0)/W-0.5);"
            "st(8,ld(3)+(Y+0.5)*ld(1)/H-0.5);st(9,1);"
        )
    else:
        scale_function = "max" if fit == "fill" else "min"
        destination_x = f"((X+0.5)*{canvas_width}/W)"
        destination_y = f"((Y+0.5)*{canvas_height}/H)"
        setup += (
            f"st(4,{scale_function}({canvas_width}/ld(0),{canvas_height}/ld(1)));"
            f"st(5,({canvas_width}-ld(0)*ld(4))/2);"
            f"st(6,({canvas_height}-ld(1)*ld(4))/2);"
            f"st(7,ld(2)+({destination_x}-ld(5))/ld(4)-0.5);"
            f"st(8,ld(3)+({destination_y}-ld(6))/ld(4)-0.5);"
        )
        if fit == "fill":
            setup += "st(9,1);"
        else:
            setup += (
                f"st(9,gte({destination_x},ld(5))*lt({destination_x},ld(5)+ld(0)*ld(4))"
                f"*gte({destination_y},ld(6))*lt({destination_y},ld(6)+ld(1)*ld(4)));"
            )
    sample_x = "clip(ld(7),ld(2),ld(2)+ld(0)-1)"
    sample_y = "clip(ld(8),ld(3),ld(3)+ld(1)-1)"

    def plane(name: str, outside: int) -> str:
        return _expr_arg(f"{setup}if(ld(9),{name}({sample_x},{sample_y}),{outside})")

    return [
        "format=gbrap",
        f"geq=r={plane('r', 0)}:g={plane('g', 0)}:b={plane('b', 0)}:a={plane('alpha', 255)}:interpolation=bilinear",
        f"scale={canvas_width}:{canvas_height}:flags=lanczos",
        "setsar=1",
    ]


def _mask_point(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        raw_x, raw_y = value.get("x"), value.get("y")
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        raw_x, raw_y = value[0], value[1]
    else:
        return None
    try:
        x, y = float(raw_x), float(raw_y)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))


def _sample_mask_path(mask: dict[str, Any], warnings: list[dict[str, Any]], clip_id: str) -> list[tuple[float, float]]:
    """Return polygon samples for a static line/cubic path contract.

    FFmpeg's expression evaluator can rasterize a fixed polygon efficiently,
    while it has no path primitive.  Sampling cubic segments at render-plan
    time keeps the project schema expressive and deterministic; the validator
    bounds the sample count and reports this as an explicit approximation.
    """
    raw_segments = mask.get("segments", mask.get("curve_segments", mask.get("curves")))
    if not isinstance(raw_segments, list) or not raw_segments:
        raw_points = mask.get("points")
        points: list[tuple[float, float]] = []
        if isinstance(raw_points, list):
            for raw_point in raw_points[:32]:
                point = _mask_point(raw_point)
                if point is not None:
                    points.append(point)
        return points
    points: list[tuple[float, float]] = []
    invalid = False
    for segment_index, segment in enumerate(raw_segments[:8]):
        if not isinstance(segment, dict):
            invalid = True
            continue
        segment_type = str(segment.get("type", "cubic")).lower().replace("-", "_")
        if segment_type in {"line", "linear"}:
            start = _mask_point(segment.get("from", segment.get("p0", segment.get("start"))))
            end = _mask_point(segment.get("to", segment.get("p1", segment.get("end"))))
            if start is None or end is None:
                invalid = True
                continue
            candidates = [start, end]
        elif segment_type in {"cubic", "bezier", "cubic_bezier"}:
            p0 = _mask_point(segment.get("from", segment.get("p0", segment.get("start"))))
            p1 = _mask_point(segment.get("control1", segment.get("p1", segment.get("c1"))))
            p2 = _mask_point(segment.get("control2", segment.get("p2", segment.get("c2"))))
            p3 = _mask_point(segment.get("to", segment.get("p3", segment.get("end"))))
            if any(point is None for point in (p0, p1, p2, p3)):
                invalid = True
                continue
            sample_count = max(2, min(16, int(_num(segment.get("samples", 8), 8))))
            assert p0 is not None and p1 is not None and p2 is not None and p3 is not None
            candidates = []
            for sample_index in range(sample_count + 1):
                u = sample_index / sample_count
                inv = 1.0 - u
                candidates.append((
                    inv * inv * inv * p0[0] + 3.0 * inv * inv * u * p1[0] + 3.0 * inv * u * u * p2[0] + u * u * u * p3[0],
                    inv * inv * inv * p0[1] + 3.0 * inv * inv * u * p1[1] + 3.0 * inv * u * u * p2[1] + u * u * u * p3[1],
                ))
        else:
            invalid = True
            continue
        for point in candidates:
            if points and abs(points[-1][0] - point[0]) < 1e-9 and abs(points[-1][1] - point[1]) < 1e-9:
                continue
            points.append(point)
            if len(points) >= 32:
                break
        if len(points) >= 32:
            break
    if invalid:
        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "mask:path_curve", "message": "路径曲线包含无效或未知段，已跳过无效段并使用剩余采样点"})
    return points[:32]


def _mask_has_segment_keyframe(clip: dict[str, Any], mask: dict[str, Any]) -> bool:
    pattern = re.compile(r"(?:mask\.)?(?:segments|curve_segments|curves)\.\d+\.(?:from|p0|start|control1|p1|c1|control2|p2|c2|to|p3|end)\.(?:x|y)")
    tracks: list[Any] = []
    if isinstance(clip.get("keyframes"), list):
        tracks.extend(clip["keyframes"])
    if isinstance(mask.get("keyframes"), list):
        tracks.extend(mask["keyframes"])
    return any(isinstance(track, dict) and pattern.fullmatch(str(track.get("property", ""))) for track in tracks)


def _sample_mask_path_expressions(
    mask: dict[str, Any],
    clip: dict[str, Any],
    clip_start: float,
    tps: int,
    warnings: list[dict[str, Any]],
    clip_id: str,
) -> tuple[list[tuple[str, str, float, float]], str]:
    """Sample curve segments while calculating each animated control point once."""
    raw_field = next((field for field in ("segments", "curve_segments", "curves") if isinstance(mask.get(field), list)), None)
    raw_segments = mask.get(raw_field) if raw_field else None
    if not isinstance(raw_segments, list) or not raw_segments:
        return [], ""

    registers: dict[tuple[int, str, str], int] = {}
    setup: list[str] = []
    register_limit_warning = False
    clip_tracks = clip.get("keyframes") if isinstance(clip.get("keyframes"), list) else []
    mask_tracks = mask.get("keyframes") if isinstance(mask.get("keyframes"), list) else []

    def has_component_keyframe(segment_index: int, aliases: tuple[str, ...], axis: str) -> bool:
        names = {
            f"{field}.{segment_index}.{alias}.{axis}"
            for field in ("segments", "curve_segments", "curves")
            for alias in aliases
        }
        for track in (*clip_tracks, *mask_tracks):
            if not isinstance(track, dict):
                continue
            property_name = str(track.get("property", ""))
            if property_name.removeprefix("mask.") in names:
                return True
        return False

    def raw_point(segment: dict[str, Any], aliases: tuple[str, ...]) -> tuple[float, float] | None:
        return _mask_point(next((segment[name] for name in aliases if name in segment), None))

    def component_expression(segment_index: int, aliases: tuple[str, ...], axis: str, default: float) -> str:
        nonlocal register_limit_warning
        key = (segment_index, aliases[0], axis)
        properties = tuple(
            f"mask.{field}.{segment_index}.{alias}.{axis}"
            for field in (raw_field, "segments", "curve_segments", "curves")
            for alias in aliases
        )
        if not has_component_keyframe(segment_index, aliases, axis):
            return f"{default:.8f}"
        if key not in registers:
            if len(registers) >= 10:
                register_limit_warning = True
                return _mask_keyframe_expr(clip, mask, properties, default, clip_start, tps)
            register = len(registers)
            registers[key] = register
            expression = _mask_keyframe_expr(clip, mask, properties, default, clip_start, tps)
            setup.append(f"st({register},({expression}))")
        return f"ld({registers[key]})"

    sampled: list[tuple[str, str, float, float]] = []
    invalid = False
    for segment_index, segment in enumerate(raw_segments[:8]):
        if not isinstance(segment, dict):
            invalid = True
            continue
        segment_type = str(segment.get("type", "cubic")).lower().replace("-", "_")
        if segment_type in {"line", "linear"}:
            point_aliases = (("from", "p0", "start"), ("to", "p1", "end"))
            defaults = [raw_point(segment, names) for names in point_aliases]
            if any(point is None for point in defaults):
                invalid = True
                continue
            candidates = [(0.0, point_aliases[0], defaults[0]), (1.0, point_aliases[1], defaults[1])]
        elif segment_type in {"cubic", "bezier", "cubic_bezier"}:
            point_aliases = (("from", "p0", "start"), ("control1", "p1", "c1"), ("control2", "p2", "c2"), ("to", "p3", "end"))
            defaults = [raw_point(segment, names) for names in point_aliases]
            if any(point is None for point in defaults):
                invalid = True
                continue
            sample_count = max(2, min(16, int(_num(segment.get("samples", 8), 8))))
            candidates = [(sample_index / sample_count, None, None) for sample_index in range(sample_count + 1)]
        else:
            invalid = True
            continue
        for progress, endpoint_aliases, static_value in candidates:
            if segment_type in {"line", "linear"}:
                assert static_value is not None
                x_default, y_default = static_value
                point_aliases_for_expression = endpoint_aliases if endpoint_aliases is not None else point_aliases[0]
                x_expression = component_expression(segment_index, point_aliases_for_expression, "x", x_default)
                y_expression = component_expression(segment_index, point_aliases_for_expression, "y", y_default)
            else:
                u = progress
                inv = 1.0 - u
                weights = (inv * inv * inv, 3.0 * inv * inv * u, 3.0 * inv * u * u, u * u * u)
                x_default = sum(weights[index] * defaults[index][0] for index in range(4) if defaults[index] is not None)
                y_default = sum(weights[index] * defaults[index][1] for index in range(4) if defaults[index] is not None)
                x_expression = "+".join(f"{weights[index]:.8f}*({component_expression(segment_index, point_aliases[index], 'x', defaults[index][0])})" for index in range(4) if defaults[index] is not None)
                y_expression = "+".join(f"{weights[index]:.8f}*({component_expression(segment_index, point_aliases[index], 'y', defaults[index][1])})" for index in range(4) if defaults[index] is not None)
            if sampled and abs(sampled[-1][2] - x_default) < 1e-9 and abs(sampled[-1][3] - y_default) < 1e-9:
                continue
            sampled.append((x_expression, y_expression, x_default, y_default))
            if len(sampled) >= 32:
                break
        if len(sampled) >= 32:
            break
    if invalid:
        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "mask:path_curve", "message": "路径曲线包含无效或未知段，已跳过无效段并使用剩余采样点"})
    if register_limit_warning:
        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "mask:path_curve_register_limit", "message": "路径动画控制点超过 FFmpeg 表达式寄存器上限，超出的关键帧直接展开表达式"})
    return sampled[:32], ";".join(setup)


def _mask_filter(
    mask: Any,
    warnings: list[dict[str, Any]],
    clip_id: str,
    *,
    clip: dict[str, Any] | None = None,
    clip_start: float = 0.0,
    tps: int = 90_000,
) -> str | None:
    """Compile normalized masks into an RGBA alpha expression.

    Rectangle/circle/ellipse geometry can be animated through regular clip
    keyframes or mask-local keyframes.  ``feather`` is normalized to the
    shortest output dimension and applied to alpha only, leaving colour sharp.
    """
    if not isinstance(mask, dict):
        return None
    clip_value = clip if isinstance(clip, dict) else {}
    mask_type = str(mask.get("type", "rectangle")).lower().replace("-", "_")
    if mask_type in {"none", "off"}:
        return None
    soft_edge: str | None = None
    dynamic_segment_setup = ""
    if mask_type == "rectangle":
        x = _mask_keyframe_expr(clip_value, mask, ("mask.x", "mask.position.x", "x"), _clamp(mask.get("x", 0.0), 0.0, 1.0, 0.0), clip_start, tps)
        y = _mask_keyframe_expr(clip_value, mask, ("mask.y", "mask.position.y", "y"), _clamp(mask.get("y", 0.0), 0.0, 1.0, 0.0), clip_start, tps)
        width = _mask_keyframe_expr(clip_value, mask, ("mask.width", "mask.w", "width", "w"), _clamp(mask.get("width", mask.get("w", 1.0)), 0.0, 1.0, 1.0), clip_start, tps)
        height = _mask_keyframe_expr(clip_value, mask, ("mask.height", "mask.h", "height", "h"), _clamp(mask.get("height", mask.get("h", 1.0)), 0.0, 1.0, 1.0), clip_start, tps)
        expression = (
            f"if(gte(X,W*({x}))*lte(X,W*min(1,({x})+({width})))"
            f"*gte(Y,H*({y}))*lte(Y,H*min(1,({y})+({height}))),255,0)"
        )
        soft_edge = f"min(min(X-W*({x}),W*(({x})+({width}))-X),min(Y-H*({y}),H*(({y})+({height}))-Y))"
    elif mask_type == "circle":
        cx = _mask_keyframe_expr(clip_value, mask, ("mask.cx", "mask.center_x", "cx", "center_x"), _clamp(mask.get("cx", mask.get("center_x", 0.5)), 0.0, 1.0, 0.5), clip_start, tps)
        cy = _mask_keyframe_expr(clip_value, mask, ("mask.cy", "mask.center_y", "cy", "center_y"), _clamp(mask.get("cy", mask.get("center_y", 0.5)), 0.0, 1.0, 0.5), clip_start, tps)
        radius = _mask_keyframe_expr(clip_value, mask, ("mask.radius", "radius"), _clamp(mask.get("radius", 0.5), 0.0, 1.0, 0.5), clip_start, tps)
        expression = (
            f"if(lte((X-W*({cx}))*(X-W*({cx}))+(Y-H*({cy}))*(Y-H*({cy})),"
            f"(min(W,H)*({radius}))*(min(W,H)*({radius}))),255,0)"
        )
        distance = f"sqrt((X-W*({cx}))*(X-W*({cx}))+(Y-H*({cy}))*(Y-H*({cy})))"
        soft_edge = f"(min(W,H)*({radius})-({distance}))"
    elif mask_type == "ellipse":
        cx = _mask_keyframe_expr(clip_value, mask, ("mask.cx", "mask.center_x", "cx", "center_x"), _clamp(mask.get("cx", mask.get("center_x", 0.5)), 0.0, 1.0, 0.5), clip_start, tps)
        cy = _mask_keyframe_expr(clip_value, mask, ("mask.cy", "mask.center_y", "cy", "center_y"), _clamp(mask.get("cy", mask.get("center_y", 0.5)), 0.0, 1.0, 0.5), clip_start, tps)
        rx = _mask_keyframe_expr(clip_value, mask, ("mask.rx", "mask.radius_x", "rx", "radius_x"), max(0.001, _clamp(mask.get("rx", mask.get("radius_x", 0.5)), 0.0, 1.0, 0.5)), clip_start, tps)
        ry = _mask_keyframe_expr(clip_value, mask, ("mask.ry", "mask.radius_y", "ry", "radius_y"), max(0.001, _clamp(mask.get("ry", mask.get("radius_y", 0.5)), 0.0, 1.0, 0.5)), clip_start, tps)
        rx, ry = f"max(0.000001,({rx}))", f"max(0.000001,({ry}))"
        norm_x = f"((X-W*({cx}))/(W*({rx})))"
        norm_y = f"((Y-H*({cy}))/(H*({ry})))"
        expression = f"if(lte(({norm_x})*({norm_x})+({norm_y})*({norm_y}),1),255,0)"
        distance = f"sqrt(({norm_x})*({norm_x})+({norm_y})*({norm_y}))"
        soft_edge = f"((1-({distance}))*min(W*({rx}),H*({ry})))"
    elif mask_type in {"path", "polygon"}:
        dynamic_segment_points, dynamic_segment_setup = _sample_mask_path_expressions(mask, clip_value, clip_start, tps, warnings, clip_id) if _mask_has_segment_keyframe(clip_value, mask) else ([], "")
        points = [(item[2], item[3]) for item in dynamic_segment_points] if dynamic_segment_points else _sample_mask_path(mask, warnings, clip_id)
        if len(points) < 3:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": f"mask:{mask_type}", "message": "path/polygon 遮罩至少需要三个合法点或有效曲线采样"})
            return None
        def point_expr(index: int, axis: str, default: float) -> str:
            if dynamic_segment_points:
                return dynamic_segment_points[index][0 if axis == "x" else 1]
            return _mask_keyframe_expr(
                clip_value,
                mask,
                (
                    f"mask.points.{index}.{axis}",
                    f"mask.points[{index}].{axis}",
                    f"mask.point.{index}.{axis}",
                    f"mask.point[{index}].{axis}",
                    f"points.{index}.{axis}",
                    f"points[{index}].{axis}",
                    f"point.{index}.{axis}",
                    f"point[{index}].{axis}",
                ),
                default,
                clip_start,
                tps,
            )

        crossings: list[str] = []
        for point_index, (x1, y1) in enumerate(points):
            x2, y2 = points[(point_index + 1) % len(points)]
            x1_expr = f"W*({point_expr(point_index, 'x', x1)})"
            y1_expr = f"H*({point_expr(point_index, 'y', y1)})"
            next_index = (point_index + 1) % len(points)
            x2_expr = f"W*({point_expr(next_index, 'x', x2)})"
            y2_expr = f"H*({point_expr(next_index, 'y', y2)})"
            denominator = f"({y2_expr}-{y1_expr})"
            x_intersection = f"if(eq({denominator},0),{x1_expr},({x1_expr}+({x2_expr}-{x1_expr})*(Y-({y1_expr}))/({denominator})))"
            crosses = f"((gte({y1_expr},Y)*lt({y2_expr},Y))+(lt({y1_expr},Y)*gte({y2_expr},Y)))"
            crossings.append(f"if(({crosses}*lt(X,{x_intersection})),1,0)")
        expression = f"if(eq(mod({'+'.join(crossings) or '0'},2),1),255,0)"
        # A polygon's signed distance is approximated by the minimum distance
        # to its animated line segments.  Combined with the winding result,
        # this gives a deterministic inner alpha feather without a GUI mask
        # rasterizer.  Point count stays fixed by the validator.
        edge_distances: list[str] = []
        for point_index in range(len(points)):
            next_index = (point_index + 1) % len(points)
            x1_expr = f"W*({point_expr(point_index, 'x', points[point_index][0])})"
            y1_expr = f"H*({point_expr(point_index, 'y', points[point_index][1])})"
            x2_expr = f"W*({point_expr(next_index, 'x', points[next_index][0])})"
            y2_expr = f"H*({point_expr(next_index, 'y', points[next_index][1])})"
            dx = f"({x2_expr}-{x1_expr})"
            dy = f"({y2_expr}-{y1_expr})"
            length_squared = f"max(0.000001,({dx})*({dx})+({dy})*({dy}))"
            projection = f"clip(((X-({x1_expr}))*({dx})+(Y-({y1_expr}))*({dy}))/({length_squared}),0,1)"
            closest_x = f"({x1_expr}+({projection})*({dx}))"
            closest_y = f"({y1_expr}+({projection})*({dy}))"
            edge_distances.append(f"sqrt((X-({closest_x}))*(X-({closest_x}))+(Y-({closest_y}))*(Y-({closest_y})))")
        if edge_distances:
            # Distance to a segment is positive on both sides of an edge.
            # Gate it with the winding result so pixels outside the polygon
            # remain transparent while the inner edge receives feathering.
            edge_distance = edge_distances[0]
            for candidate in edge_distances[1:]:
                edge_distance = f"min(({edge_distance}),({candidate}))"
            soft_edge = f"if(gt(({expression}),0),({edge_distance}),-1)"
    else:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": f"mask:{mask_type}", "message": "当前 FFmpeg 后端支持 rectangle、circle、ellipse 和固定点数动态 path/polygon 遮罩"})
        return None
    feather = max(0.0, min(0.5, _num(mask.get("feather", 0), 0)))
    dynamic_feather = _mask_has_keyframe(clip_value, mask, ("mask.feather", "feather"))
    if dynamic_feather and soft_edge is not None:
        feather_expr = f"min(0.5,max(0,({_mask_keyframe_expr(clip_value, mask, ('mask.feather', 'feather'), feather, clip_start, tps)})))"
        expression = f"if(gt(({feather_expr}),0),clip(({soft_edge})/max(0.000001,min(W,H)*({feather_expr})),0,1)*255,({expression}))"
    elif dynamic_feather:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "mask_dynamic_feather", "message": "当前遮罩类型没有可用的动态羽化表达式，使用静态羽化值"})
    if bool(mask.get("invert", False)):
        expression = f"(255-({expression}))"
    # Multiply by the existing alpha so transparent inputs and clip opacity
    # survive masking instead of becoming opaque inside the shape.
    alpha_expr = f"alpha(X,Y)*({expression})/255"
    if dynamic_segment_setup:
        alpha_expr = f"{dynamic_segment_setup};{alpha_expr}"
    alpha_filter = f"geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':a={_expr_arg(alpha_expr)}"
    if feather > 0 and not dynamic_feather:
        # Feather is normalized against the shortest output dimension. FFmpeg
        # evaluates this as alpha-only blur, preserving the source colour.
        radius = f"min(w,h)*{min(0.5, feather):.8f}"
        alpha_filter += f",boxblur=luma_radius=0:chroma_radius=0:alpha_radius={_expr_arg(radius)}:alpha_power=2"
    return alpha_filter


def render_fingerprints(project: dict[str, Any], sequence: dict[str, Any], settings: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Return the dependency fingerprints required for a safe render resume."""
    project_payload = {"project": project, "sequence_id": sequence.get("id"), "settings": settings}
    project_fingerprint = sha256_bytes(json.dumps(project_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    sequence_map = {str(item.get("id")): item for item in project.get("sequences", []) if item.get("id")}
    asset_ids: set[str] = set()
    local_files: set[str] = set()
    seen_sequences: set[str] = set()

    def collect(sequence_value: dict[str, Any]) -> None:
        sequence_id = str(sequence_value.get("id"))
        if sequence_id in seen_sequences:
            return
        seen_sequences.add(sequence_id)
        for track in sequence_value.get("tracks", []):
            for clip in track.get("clips", []):
                if clip.get("asset_id"):
                    asset_ids.add(str(clip.get("asset_id")))
                subtitle = clip.get("subtitle") if isinstance(clip.get("subtitle"), dict) else {}
                subtitle_style = subtitle.get("style") if isinstance(subtitle.get("style"), dict) else {}
                if subtitle_style.get("font_asset_id"):
                    asset_ids.add(str(subtitle_style.get("font_asset_id")))
                for local_value in (subtitle.get("asset_uri"), subtitle_style.get("fontfile")):
                    if local_value:
                        local_files.add(str(local_value))
                if clip.get("sequence_id") in sequence_map:
                    collect(sequence_map[str(clip.get("sequence_id"))])

    collect(sequence)
    assets = {str(asset.get("id")): asset for asset in project.get("assets", []) if asset.get("id") in asset_ids}
    input_hashes: dict[str, str | None] = {}
    for asset_id in sorted(assets):
        asset = assets[asset_id]
        digest = asset.get("sha256")
        uri = asset.get("uri")
        if uri:
            source = Path(str(uri))
            if root is not None and not source.is_absolute():
                source = root / source
            if source.exists() and source.is_file():
                digest = f"sha256:{sha256_file(source)}"
        input_hashes[asset_id] = digest
    if root is not None:
        for local_value in sorted(local_files):
            try:
                source = resolve_local_path(root, local_value, field="render.input")
            except AppError:
                continue
            digest = f"sha256:{sha256_file(source)}" if source.is_file() else None
            input_hashes[f"local:{local_value}"] = digest
    return {"project_fingerprint": project_fingerprint, "input_hashes": input_hashes}


def _bezier_progress_expr(progress: str, controls: Any) -> str:
    """Approximate a normalized cubic Bezier easing curve for FFmpeg.

    The Agent project contract accepts either ``[y1, y2]`` (fixed timing
    handles) or ``[x1, y1, x2, y2]`` (normalized CSS-style handles). FFmpeg's
    expression language has no inverse cubic solver, so solve x(u)=progress
    while building the filter graph and emit a small piecewise-linear lookup.
    This keeps the result frame-evaluable while preserving the intended value
    range exactly at both endpoints.
    """
    values: list[float] = []
    if isinstance(controls, (list, tuple)):
        for value in controls:
            if isinstance(value, dict):
                value = value.get("y", value.get("value"))
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                values.append(number)
    if len(values) >= 4:
        x1, y1, x2, y2 = values[:4]
    elif len(values) >= 2:
        x1, y1, x2, y2 = 1.0 / 3.0, values[0], 2.0 / 3.0, values[1]
    else:
        return progress

    def cubic(a: float, b: float, u: float) -> float:
        inv = 1.0 - u
        return 3.0 * inv * inv * u * a + 3.0 * inv * u * u * b + u * u * u

    def y_at(x_target: float) -> float:
        low, high = 0.0, 1.0
        for _ in range(20):
            middle = (low + high) / 2.0
            if cubic(x1, x2, middle) < x_target:
                low = middle
            else:
                high = middle
        return cubic(y1, y2, (low + high) / 2.0)

    sample_count = 32
    samples = [y_at(index / sample_count) for index in range(sample_count + 1)]
    expression = f"{samples[-1]:.8f}"
    for index in range(sample_count - 1, -1, -1):
        start = index / sample_count
        end = (index + 1) / sample_count
        slope = (samples[index + 1] - samples[index]) / (end - start)
        segment = f"({samples[index]:.8f}+({slope:.8f})*((({progress})-{start:.8f})))"
        expression = f"if(lt(({progress}),{end:.8f}),{segment},{expression})"
    return f"if(lt(({progress}),0),{samples[0]:.8f},{expression})"


def _keyframe_expr(
    clip: dict[str, Any],
    properties: tuple[str, ...],
    default: float,
    clip_start: float,
    tps: int,
    *,
    time_variable: str = "t",
) -> str:
    tracks = {str(item.get("property")): item for item in clip.get("keyframes", []) if item.get("property")}
    track = next((tracks[name] for name in properties if name in tracks), None)
    if not track:
        return f"{default:.8f}"
    pairs: list[tuple[float, float, str, Any]] = []
    for item in track.get("keyframes", []):
        try:
            # Validated project keyframes are non-negative. Internal nested
            # parent tracks may intentionally use negative local offsets so
            # each child starts at the parent's already-interpolated value.
            pairs.append((float(item.get("at_tick", 0)) / tps, float(item.get("value")), str(item.get("interpolation", "linear")), item.get("control_points")))
        except (TypeError, ValueError):
            continue
    if not pairs:
        return f"{default:.8f}"
    pairs.sort(key=lambda item: item[0])
    local = f"({time_variable}-{clip_start:.8f})"
    if len(pairs) == 1:
        return f"{pairs[0][1]:.8f}"
    expression = f"{pairs[-1][1]:.8f}"
    for index in range(len(pairs) - 2, -1, -1):
        left_t, left_v, interpolation, controls = pairs[index]
        right_t, right_v, _, _ = pairs[index + 1]
        span = max(right_t - left_t, 1e-9)
        progress = f"clip((({local}-{left_t:.8f})/{span:.8f}),0,1)"
        if interpolation == "hold":
            eased = "0"
        elif interpolation == "ease_in":
            eased = f"({progress})*({progress})"
        elif interpolation == "ease_out":
            eased = f"1-(1-({progress}))*(1-({progress}))"
        elif interpolation == "ease_in_out":
            eased = f"if(lt({progress},0.5),2*({progress})*({progress}),1-((-2*({progress})+2)*(-2*({progress})+2))/2)"
        elif interpolation == "bezier":
            eased = _bezier_progress_expr(progress, controls)
        else:
            eased = progress
        interpolated = f"({left_v:.8f}+({right_v-left_v:.8f})*({eased}))"
        expression = f"if(lt({local},{right_t:.8f}),{interpolated},{expression})"
    return f"if(lt({local},{pairs[0][0]:.8f}),{pairs[0][1]:.8f},{expression})"


def _reverse_keyframe_controls(keyframe: dict[str, Any]) -> None:
    """Reverse a normalized easing curve when its timeline plays backwards."""
    if str(keyframe.get("interpolation", "linear")) != "bezier":
        return
    controls = keyframe.get("control_points")
    if not isinstance(controls, list):
        return
    try:
        values = [float(value) for value in controls]
    except (TypeError, ValueError):
        return
    if len(values) == 2:
        keyframe["control_points"] = [1.0 - values[1], 1.0 - values[0]]
    elif len(values) == 4:
        keyframe["control_points"] = [1.0 - values[2], 1.0 - values[3], 1.0 - values[0], 1.0 - values[1]]


def _transform_exprs(clip: dict[str, Any], start: float, tps: int) -> dict[str, str]:
    transform = clip.get("transform") if isinstance(clip.get("transform"), dict) else {}
    position = transform.get("position") if isinstance(transform.get("position"), dict) else {}
    anchor = transform.get("anchor") if isinstance(transform.get("anchor"), dict) else {}
    child_exprs = {
        "scale": _keyframe_expr(clip, ("transform.scale", "scale"), _num(transform.get("scale", 1.0), 1.0), start, tps),
        "rotation": _keyframe_expr(clip, ("transform.rotation", "rotation"), _num(transform.get("rotation", 0.0), 0.0), start, tps),
        "opacity": _keyframe_expr(clip, ("transform.opacity", "opacity"), _num(transform.get("opacity", 1.0), 1.0), start, tps, time_variable="T"),
        "position_x": _keyframe_expr(clip, ("transform.position.x", "position.x", "position_x"), _num(position.get("x", transform.get("position_x", 0.5)), 0.5), start, tps),
        "position_y": _keyframe_expr(clip, ("transform.position.y", "position.y", "position_y"), _num(position.get("y", transform.get("position_y", 0.5)), 0.5), start, tps),
        "anchor_x": _keyframe_expr(clip, ("transform.anchor.x", "anchor.x", "anchor_x"), _num(anchor.get("x", transform.get("anchor_x", 0.5)), 0.5), start, tps),
        "anchor_y": _keyframe_expr(clip, ("transform.anchor.y", "anchor.y", "anchor_y"), _num(anchor.get("y", transform.get("anchor_y", 0.5)), 0.5), start, tps),
    }
    raw_layers = clip.get("_nested_parent_transforms")
    layers: list[dict[str, Any]] = []
    if isinstance(raw_layers, list):
        layers = [item for item in raw_layers if isinstance(item, dict)]
    if not layers:
        parent = clip.get("_nested_parent_transform")
        if isinstance(parent, dict):
            layers = [{"transform": parent}]
    if not layers:
        return child_exprs

    # Layers are stored from outermost to innermost. Apply the innermost
    # parent first so position offsets are rotated/scaled in the same order as
    # static `combine_transforms` composition.
    result = child_exprs
    layer_count = len(layers)
    for layer_index in range(layer_count - 1, -1, -1):
        layer = layers[layer_index]
        parent = layer.get("transform") if isinstance(layer.get("transform"), dict) else layer
        parent_position = parent.get("position") if isinstance(parent.get("position"), dict) else {}
        prefix = "nested.parent.transform" if layer_count == 1 else f"nested.parent.{layer_index}.transform"
        parent_scale = _keyframe_expr(
            clip, (f"{prefix}.scale",), _num(parent.get("scale", 1.0), 1.0), start, tps,
        )
        parent_rotation = _keyframe_expr(
            clip, (f"{prefix}.rotation",), _num(parent.get("rotation", 0.0), 0.0), start, tps,
        )
        parent_opacity = _keyframe_expr(
            clip, (f"{prefix}.opacity",), _num(parent.get("opacity", 1.0), 1.0), start, tps, time_variable="T",
        )
        parent_x = _keyframe_expr(
            clip, (f"{prefix}.position.x",), _num(parent_position.get("x", parent.get("position_x", 0.5)), 0.5), start, tps,
        )
        parent_y = _keyframe_expr(
            clip, (f"{prefix}.position.y",), _num(parent_position.get("y", parent.get("position_y", 0.5)), 0.5), start, tps,
        )
        child_dx = f"(({result['position_x']})-0.5)*({parent_scale})"
        child_dy = f"(({result['position_y']})-0.5)*({parent_scale})"
        angle = f"(({parent_rotation})*PI/180)"
        result = {
            "scale": f"({parent_scale})*({result['scale']})",
            "rotation": f"({parent_rotation})+({result['rotation']})",
            "opacity": f"clip(({parent_opacity})*({result['opacity']}),0,1)",
            "position_x": f"({parent_x})+({child_dx})*cos({angle})-({child_dy})*sin({angle})",
            "position_y": f"({parent_y})+({child_dx})*sin({angle})+({child_dy})*cos({angle})",
            "anchor_x": result["anchor_x"],
            "anchor_y": result["anchor_y"],
        }
    return result


def _video_overlay_position(transform: dict[str, str], width: int, height: int) -> tuple[str, str]:
    """Return overlay coordinates that keep the authored anchor on position.

    Video layers are normalized to the output canvas before the transform
    chain. That makes the pre-rotation dimensions deterministic and lets the
    overlay expression compensate for FFmpeg's rotate filter expanding its
    bounding box. The subtitle compositor intentionally keeps its existing
    full-canvas rotation contract.
    """
    position_x = transform["position_x"]
    position_y = transform["position_y"]
    anchor_x = transform["anchor_x"]
    anchor_y = transform["anchor_y"]
    if transform["rotation"] == "0.00000000":
        return (
            f"({position_x})*W-w*({anchor_x})",
            f"({position_y})*H-h*({anchor_y})",
        )
    angle = f"(({transform['rotation']})*PI/180)"
    scaled_width = f"max(2,{width}*({transform['scale']}))"
    scaled_height = f"max(2,{height}*({transform['scale']}))"
    rotated_width = f"(abs(({scaled_width})*cos({angle}))+abs(({scaled_height})*sin({angle})))"
    rotated_height = f"(abs(({scaled_width})*sin({angle}))+abs(({scaled_height})*cos({angle})))"
    delta_x = f"(({anchor_x})-0.5)*({scaled_width})"
    delta_y = f"(({anchor_y})-0.5)*({scaled_height})"
    anchor_output_x = f"(({rotated_width})/2+({delta_x})*cos({angle})-({delta_y})*sin({angle}))"
    anchor_output_y = f"(({rotated_height})/2+({delta_x})*sin({angle})+({delta_y})*cos({angle}))"
    return (
        f"({position_x})*W-({anchor_output_x})",
        f"({position_y})*H-({anchor_output_y})",
    )


def _speed_curve_segments(clip: dict[str, Any], source_span_tick: int, tps: int) -> list[tuple[float, float, float, float]]:
    """Normalize a source-relative speed curve into time/remap segments.

    A curve keyframe uses ``at_tick`` relative to the trimmed source span and
    ``speed`` as the instantaneous playback rate. Missing endpoints inherit
    the clip's constant ``speed``. Linear interpolation is integrated exactly
    in the generated setpts expression; unsupported interpolation names fall
    back to a constant segment and are reported by the caller.
    """
    curve = clip.get("speed_curve")
    if isinstance(curve, list):
        raw_keyframes = curve
    elif isinstance(curve, dict):
        raw_keyframes = curve.get("keyframes", [])
    else:
        return []
    if not isinstance(raw_keyframes, list) or len(raw_keyframes) < 1 or source_span_tick <= 0:
        return []
    base_speed = max(0.01, _num(clip.get("speed", 1.0), 1.0))
    points: list[tuple[int, float, str]] = []
    for item in raw_keyframes:
        if not isinstance(item, dict):
            continue
        try:
            at_tick = max(0, min(source_span_tick, int(item.get("at_tick", 0))))
            speed = max(0.01, float(item.get("speed", item.get("value", base_speed))))
        except (TypeError, ValueError):
            continue
        points.append((at_tick, speed, str(item.get("interpolation", "linear")).lower()))
    if not points:
        return []
    points.sort(key=lambda item: item[0])
    deduped: list[tuple[int, float, str]] = []
    for point in points:
        if deduped and deduped[-1][0] == point[0]:
            deduped[-1] = point
        else:
            deduped.append(point)
    if deduped[0][0] > 0:
        deduped.insert(0, (0, base_speed, "hold"))
    if deduped[-1][0] < source_span_tick:
        deduped.append((source_span_tick, deduped[-1][1], "hold"))
    segments: list[tuple[float, float, float, float]] = []
    for left, right in zip(deduped, deduped[1:]):
        if right[0] <= left[0]:
            continue
        start = left[0] / float(tps)
        end = right[0] / float(tps)
        right_speed = right[1] if left[2] in {"linear", "ease_in", "ease_out", "ease_in_out", "bezier"} else left[1]
        segments.append((start, end, left[1], right_speed))
    return segments


def _reverse_speed_curve_segments(segments: list[tuple[float, float, float, float]]) -> list[tuple[float, float, float, float]]:
    """Map source-relative speed segments into the reversed clip clock.

    ``reverse`` reverses decoded frame order before the generated ``setpts``
    expression runs.  Reflecting each segment around the source span and
    swapping its endpoint speeds keeps each speed attached to its authored
    source position, instead of applying the forward ramp to the newly
    reversed frames.
    """
    if not segments:
        return []
    total = max(0.0, float(segments[-1][1]))
    reflected = [
        (max(0.0, total - end), max(0.0, total - start), right_speed, left_speed)
        for start, end, left_speed, right_speed in reversed(segments)
        if end > start
    ]
    reflected.sort(key=lambda item: item[0])
    return reflected


def _speed_curve_audio_parts(segments: list[tuple[float, float, float, float]]) -> list[tuple[float, float, float]]:
    """Approximate a varying speed curve with short constant-tempo audio parts.

    FFmpeg's ``atempo`` takes one scalar tempo per filter instance. Splitting
    each varying curve segment into bounded pieces keeps audio close to the
    same integrated duration as the video remap while remaining fully local
    and deterministic. Constant segments stay exact.
    """
    parts: list[tuple[float, float, float]] = []
    for start, end, left_speed, right_speed in segments:
        span = max(0.0, end - start)
        if span <= 1e-9:
            continue
        subdivisions = 1 if abs(right_speed - left_speed) < 1e-8 else max(2, min(16, int(math.ceil(span * 8.0))))
        for index in range(subdivisions):
            part_start = start + span * index / subdivisions
            part_end = start + span * (index + 1) / subdivisions
            part_left_speed = left_speed + (right_speed - left_speed) * index / subdivisions
            part_right_speed = left_speed + (right_speed - left_speed) * (index + 1) / subdivisions
            # Match each part's analytic duration rather than its midpoint
            # speed.  Audio still uses constant-tempo windows, but their
            # cumulative boundaries share the video's integrated clock.
            if abs(part_right_speed - part_left_speed) < 1e-8:
                speed = part_left_speed
            else:
                speed = (part_right_speed - part_left_speed) / math.log(part_right_speed / part_left_speed)
            parts.append((part_start, part_end, max(0.01, speed)))
    return parts


def _tempo_chain(speed: float) -> str:
    """Return an atempo chain that supports speeds outside FFmpeg's 0.5..2 range."""
    remaining = max(0.01, float(speed))
    tempo: list[str] = []
    while remaining > 2.0:
        tempo.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        tempo.append("atempo=0.5")
        remaining /= 0.5
    tempo.append(f"atempo={remaining:.8f}")
    return ",".join(tempo)


def speed_curve_duration_seconds(clip: dict[str, Any], source_span_tick: int, tps: int) -> float | None:
    segments = _speed_curve_segments(clip, source_span_tick, tps)
    if not segments:
        return None
    duration = 0.0
    for start, end, speed_left, speed_right in segments:
        span = max(0.0, end - start)
        if abs(speed_right - speed_left) < 1e-8:
            duration += span / max(0.01, speed_left)
        else:
            duration += span / (speed_right - speed_left) * math.log(max(0.01, speed_right) / max(0.01, speed_left))
    return max(0.001, duration)


def _speed_curve_elapsed_seconds(segments: list[tuple[float, float, float, float]], source_seconds: float) -> float:
    """Integrate a normalized speed curve from its source origin.

    ``segments`` use source seconds and instantaneous playback speeds.  The
    integral is also used by nested sequence flattening so a child sequence's
    source clock can be mapped onto the parent's final clock without falling
    back to one constant speed for the entire nested clip.
    """
    if not segments:
        return 0.0
    target = max(0.0, float(source_seconds))
    elapsed = 0.0
    for start, end, speed_left, speed_right in segments:
        if target <= start:
            break
        x = min(target, end)
        span = max(0.0, end - start)
        if x <= start or span <= 1e-12:
            continue
        local = x - start
        if abs(speed_right - speed_left) < 1e-8:
            elapsed += local / max(0.01, speed_left)
        else:
            delta = speed_right - speed_left
            speed_at_x = speed_left + delta * (local / span)
            elapsed += span / delta * math.log(max(0.01, speed_at_x) / max(0.01, speed_left))
        if target <= end:
            break
    return max(0.0, elapsed)


def _speed_curve_source_seconds_at_elapsed(segments: list[tuple[float, float, float, float]], elapsed_seconds: float) -> float:
    """Invert :func:`_speed_curve_elapsed_seconds` for a monotone curve."""
    if not segments:
        return 0.0
    remaining = max(0.0, float(elapsed_seconds))
    for start, end, speed_left, speed_right in segments:
        span = max(0.0, end - start)
        if span <= 1e-12:
            continue
        if abs(speed_right - speed_left) < 1e-8:
            segment_elapsed = span / max(0.01, speed_left)
        else:
            segment_elapsed = span / (speed_right - speed_left) * math.log(
                max(0.01, speed_right) / max(0.01, speed_left)
            )
        if remaining > segment_elapsed + 1e-10:
            remaining -= segment_elapsed
            continue
        if abs(speed_right - speed_left) < 1e-8:
            return start + remaining * max(0.01, speed_left)
        delta = speed_right - speed_left
        speed_at_x = max(0.01, speed_left) * math.exp(delta * remaining / span)
        return start + span * (speed_at_x - speed_left) / delta
    return segments[-1][1]


def _speed_curve_setpts(segments: list[tuple[float, float, float, float]], timeline_start: float) -> str:
    total = 0.0
    segment_outputs: list[tuple[float, float, float, float, float]] = []
    for start, end, speed_left, speed_right in segments:
        span = max(0.0, end - start)
        if abs(speed_right - speed_left) < 1e-8:
            output_span = span / max(0.01, speed_left)
        else:
            output_span = span / (speed_right - speed_left) * math.log(max(0.01, speed_right) / max(0.01, speed_left))
        segment_outputs.append((start, end, speed_left, speed_right, total))
        total += output_span
    # trim keeps input timestamps.  Use the first retained frame as the
    # origin so a non-zero source_in_tick cannot skip the beginning of the
    # speed curve or produce an empty clip.
    source_clock = "((PTS-STARTPTS)*TB)"
    expression = f"({timeline_start + total:.8f})/TB"
    for start, end, speed_left, speed_right, output_start in reversed(segment_outputs):
        span = max(1e-9, end - start)
        if abs(speed_right - speed_left) < 1e-8:
            mapped = f"({timeline_start + output_start:.8f}+({source_clock}-{start:.8f})/{speed_left:.8f})/TB"
        else:
            delta = speed_right - speed_left
            speed_at_t = f"({speed_left:.8f}+{delta:.8f}*(({source_clock}-{start:.8f})/{span:.8f}))"
            mapped = f"({timeline_start + output_start:.8f}+{span:.8f}/{delta:.8f}*log(({speed_at_t})/{speed_left:.8f}))/TB"
        expression = f"if(lt({source_clock},{end:.8f}),{mapped},{expression})"
    return f"setpts={_expr_arg(expression)}"


def _insert_audio_freeze(
    filters: list[str],
    audio_chain: list[str],
    prefix: str,
    content_duration: float,
    freeze_at: float,
    freeze_duration: float,
) -> list[str]:
    """Insert sample-bounded silence before clip audio effects/automation.

    The timeline is quantized to 48 kHz once, then split by sample index.
    Padding/trim on the decoded input absorbs codec/atempo tail rounding and
    keeps the insertion at the same clip-local time for mono/stereo assets.
    """
    sample_rate = 48000
    content_samples = max(1, int(round(content_duration * sample_rate)))
    at_samples = max(0, min(content_samples, int(round(freeze_at * sample_rate))))
    hold_samples = max(1, int(round(freeze_duration * sample_rate)))
    base = f"{prefix}base"
    silence = f"{prefix}silence"
    frozen = f"{prefix}out"
    filters.append(
        ",".join(audio_chain)
        + f",aformat=sample_fmts=fltp:sample_rates={sample_rate}:channel_layouts=stereo,"
        f"apad=whole_len={content_samples},atrim=end_sample={content_samples},asetpts=N/SR/TB[{base}]"
    )
    filters.append(
        f"anullsrc=r={sample_rate}:cl=stereo,atrim=end_sample={hold_samples},asetpts=N/SR/TB[{silence}]"
    )
    if at_samples == 0:
        parts = [silence, base]
    elif at_samples == content_samples:
        parts = [base, silence]
    else:
        pre_input, post_input = f"{prefix}prein", f"{prefix}postin"
        pre, post = f"{prefix}pre", f"{prefix}post"
        filters.append(f"[{base}]asplit=2[{pre_input}][{post_input}]")
        filters.append(f"[{pre_input}]atrim=end_sample={at_samples},asetpts=N/SR/TB[{pre}]")
        filters.append(f"[{post_input}]atrim=start_sample={at_samples},asetpts=N/SR/TB[{post}]")
        parts = [pre, silence, post]
    filters.append(
        "".join(f"[{part}]" for part in parts)
        + f"concat=n={len(parts)}:v=0:a=1,asetpts=N/SR/TB[{frozen}]"
    )
    # The first item must name a filter as well as its input label; joining a
    # bare label with commas would introduce an empty FFmpeg filter.
    return [f"[{frozen}]anull"]


def _effect_keyframe_tracks(effect: dict[str, Any], parameters: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized parameter keyframe tracks for one effect.

    Effects keep their own keyframe namespace so an Agent can animate a
    filter without colliding with clip transform/audio tracks.  Both the
    explicit top-level ``effect.keyframes`` form and the convenient
    ``parameters.keyframes`` form are accepted; aliases such as
    ``effect.brightness`` and ``parameters.brightness`` are normalized to
    ``brightness`` before the shared keyframe evaluator runs.
    """
    raw_tracks = effect.get("keyframes")
    if not isinstance(raw_tracks, list):
        raw_tracks = parameters.get("keyframes") if isinstance(parameters.get("keyframes"), list) else []
    effect_name = str(effect.get("type", "")).lower().replace("-", "_")
    prefixes = ("effect.", "parameters.", f"{effect_name}.") if effect_name else ("effect.", "parameters.")
    tracks: list[dict[str, Any]] = []
    for item in raw_tracks:
        if not isinstance(item, dict):
            continue
        property_name = str(item.get("property", "")).strip().lower().replace("-", "_")
        for prefix in prefixes:
            if property_name.startswith(prefix):
                property_name = property_name[len(prefix):]
                break
        if not property_name:
            continue
        tracks.append({**item, "property": property_name})
    return tracks


def _effect_has_keyframe(effect: dict[str, Any], parameters: dict[str, Any], aliases: tuple[str, ...]) -> bool:
    names = {str(alias).lower().replace("-", "_") for alias in aliases}
    return any(str(item.get("property", "")) in names for item in _effect_keyframe_tracks(effect, parameters))


def _effect_keyframe_expr(
    effect: dict[str, Any],
    parameters: dict[str, Any],
    aliases: tuple[str, ...],
    default: float,
    clip_start: float,
    tps: int,
) -> str:
    tracks = _effect_keyframe_tracks(effect, parameters)
    if not tracks:
        return f"{default:.8f}"
    return _keyframe_expr(
        {"keyframes": tracks},
        tuple(str(alias).lower().replace("-", "_") for alias in aliases),
        default,
        clip_start,
        tps,
        time_variable="t",
    )


def _effect_filters(
    effects: Any,
    warnings: list[dict[str, Any]],
    clip_id: str,
    *,
    root: Path | None = None,
    clip: dict[str, Any] | None = None,
    clip_start: float = 0.0,
    tps: int = 90000,
) -> list[str]:
    filters: list[str] = []
    clip_value = clip if isinstance(clip, dict) else {}
    for effect in effects or []:
        if isinstance(effect, dict) and effect.get("enabled", True) is False:
            continue
        if isinstance(effect, str):
            effect_type, parameters = effect, {}
            effect_value: dict[str, Any] = {"type": effect_type}
        elif isinstance(effect, dict):
            effect_type = str(effect.get("type", ""))
            parameters = effect.get("parameters") if isinstance(effect.get("parameters"), dict) else effect
            effect_value = effect
        else:
            continue
        name = effect_type.lower().replace("-", "_")
        effect_tracks = _effect_keyframe_tracks(effect_value, parameters)

        def expression(aliases: tuple[str, ...], default: float) -> str:
            return _effect_keyframe_expr(effect_value, parameters, aliases, default, clip_start, tps)

        def has_track(aliases: tuple[str, ...]) -> bool:
            return _effect_has_keyframe(effect_value, parameters, aliases)

        def warn_unsupported_tracks() -> None:
            if effect_tracks:
                warnings.append({
                    "code": "RENDER_FEATURE_APPROXIMATE",
                    "clip_id": clip_id,
                    "feature": f"effect_keyframes:{effect_type}",
                    "message": "当前效果滤镜不支持逐帧参数表达式，使用静态参数值",
                })

        def invalid_parameter(message: str) -> None:
            warnings.append({
                "code": "EFFECT_PARAMETER_INVALID",
                "clip_id": clip_id,
                "feature": f"effect:{effect_type}",
                "message": message,
            })

        if name in {"lut", "lut3d", "cube", "look"}:
            raw_lut_path = parameters.get("path", parameters.get("file", parameters.get("lut")))
            lut_id = parameters.get("lut_id")
            if lut_id is not None and str(lut_id).strip():
                if root is None:
                    warnings.append({"code": "LUT_ID_CONTEXT_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": "lut_id 引用需要项目根目录上下文"})
                    continue
                from .lut_library import resolve_lut_path

                resolved_lut = resolve_lut_path(root, str(lut_id).strip())
                if resolved_lut is None:
                    warnings.append({"code": "LUT_ID_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": f"LUT 库中不存在: {lut_id}"})
                    continue
                raw_lut_path = resolved_lut[0]
            if not raw_lut_path:
                warnings.append({"code": "LUT_FILE_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": "LUT 效果没有提供 path/file"})
                continue
            raw_lut_text = str(raw_lut_path)
            if raw_lut_text.lower().startswith("file://"):
                raw_lut_text = raw_lut_text[7:]
            lut_path = Path(raw_lut_text)
            if not lut_path.is_absolute() and root is not None:
                lut_path = root / lut_path
            if not lut_path.exists() or not lut_path.is_file():
                warnings.append({"code": "LUT_FILE_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": f"LUT 文件不存在: {lut_path}"})
                continue
            intensity = _num(parameters.get("intensity", 1.0), 1.0)
            if not math.isfinite(intensity) or intensity < 0.0 or intensity > 1.0:
                warnings.append({"code": "EFFECT_PARAMETER_INVALID", "clip_id": clip_id, "feature": "lut3d", "message": "LUT intensity 必须位于 0..1，已跳过该效果"})
                continue
            # A zero-strength LUT is an exact no-op.  Static intermediate
            # strengths are materialized as a deterministic project-local CUBE
            # so the regular FFmpeg lut3d filter remains single-input and can
            # still be used by subtitle, adjustment, and nested clip chains.
            if intensity <= 1e-9:
                if effect_tracks:
                    warn_unsupported_tracks()
                continue
            if intensity < 1.0 - 1e-9:
                if effect_tracks:
                    warn_unsupported_tracks()
                if root is None:
                    warnings.append({"code": "LUT_INTENSITY_CONTEXT_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": "LUT intensity 派生缓存需要项目根目录上下文，已跳过该效果"})
                    continue
                try:
                    from .lut_library import prepare_lut_intensity

                    lut_path = prepare_lut_intensity(root, lut_path, intensity)
                except AppError as exc:
                    warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "lut_intensity", "message": str(exc)})
                    continue
                warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "lut_intensity", "message": "已由本地 .cube identity 混合表执行静态 LUT 强度；逐帧强度仍使用静态值"})
            interpolation = str(parameters.get("interpolation", parameters.get("interp", "tetrahedral"))).lower()
            if interpolation not in {"nearest", "trilinear", "tetrahedral", "pyramid", "prism"}:
                warnings.append({"code": "LUT_INTERPOLATION_INVALID", "clip_id": clip_id, "feature": "lut3d", "message": f"LUT interpolation 无效，已回退 tetrahedral: {interpolation}"})
                interpolation = "tetrahedral"
            if effect_tracks:
                warn_unsupported_tracks()
            filters.append(f"lut3d=file='{_quoted(str(lut_path))}':interp={interpolation}")
        elif name in {"grayscale", "black_white", "blackandwhite"}:
            filters.append("hue=s=0")
        elif name == "sepia":
            filters.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131")
        elif name in {"blur", "gaussian_blur", "gblur"}:
            filters.append(f"gblur=sigma={max(0.1, _num(parameters.get('radius', parameters.get('sigma', 4)), 4)):.4f}")
        elif name in {"avgblur", "average_blur"}:
            if effect_tracks:
                warn_unsupported_tracks()
            size_x = max(1, min(1024, int(round(_num(parameters.get("size_x", parameters.get("sizeX", 2)), 2)))))
            size_y = max(0, min(1024, int(round(_num(parameters.get("size_y", parameters.get("sizeY", 2)), 2)))))
            planes = max(0, min(15, int(round(_num(parameters.get("planes", 15), 15)))))
            filters.append(f"avgblur=sizeX={size_x}:sizeY={size_y}:planes={planes}")
        elif name in {"box_blur", "boxblur"}:
            radius = max(1.0, _num(parameters.get("radius", 4), 4))
            power = max(1.0, min(4.0, _num(parameters.get("power", 1), 1)))
            filters.append(f"boxblur=luma_radius={radius:.4f}:luma_power={power:.4f}")
        elif name == "smartblur":
            if effect_tracks:
                warn_unsupported_tracks()
            radius = max(0.1, min(5.0, _num(parameters.get("radius", parameters.get("luma_radius", 1)), 1)))
            strength = max(-1.0, min(1.0, _num(parameters.get("strength", parameters.get("luma_strength", 1)), 1)))
            threshold = max(-30, min(30, int(round(_num(parameters.get("threshold", parameters.get("luma_threshold", 0)), 0)))))
            filters.append(f"smartblur=lr={radius:.4f}:ls={strength:.4f}:lt={threshold}")
        elif name in {"sharpen", "unsharp"}:
            filters.append(f"unsharp=5:5:{_num(parameters.get('amount', 1), 1):.4f}:5:5:0")
        elif name in {"brightness", "contrast", "saturation", "color"}:
            brightness = _num(parameters.get("brightness", parameters.get("amount", 0)), 0)
            contrast = _num(parameters.get("contrast", 1), 1)
            saturation = _num(parameters.get("saturation", 1), 1)
            dynamic_aliases = {
                "brightness": ("brightness", "amount", "value"),
                "contrast": ("contrast", "amount", "value"),
                "saturation": ("saturation", "amount", "value"),
            }
            if name == "brightness":
                brightness = expression(dynamic_aliases[name], brightness)
            elif name == "contrast":
                contrast = expression(dynamic_aliases[name], contrast)
            elif name == "saturation":
                saturation = expression(dynamic_aliases[name], saturation)
            else:
                brightness = expression(("brightness",), brightness)
                contrast = expression(("contrast",), contrast)
                saturation = expression(("saturation",), saturation)
            if effect_tracks:
                supported = any(has_track(aliases) for aliases in dynamic_aliases.values())
                if supported:
                    filters.append(
                        f"eq=brightness={_expr_arg(str(brightness))}:contrast={_expr_arg(str(contrast))}:"
                        f"saturation={_expr_arg(str(saturation))}:eval=frame"
                    )
                else:
                    warn_unsupported_tracks()
                    filters.append(f"eq=brightness={_num(brightness, 0):.6f}:contrast={_num(contrast, 1):.6f}:saturation={_num(saturation, 1):.6f}")
            else:
                filters.append(f"eq=brightness={_num(brightness, 0):.6f}:contrast={_num(contrast, 1):.6f}:saturation={_num(saturation, 1):.6f}")
        elif name in {"hue", "hue_rotate"}:
            hue_value = _num(parameters.get("degrees", parameters.get("angle", 0)), 0)
            hue_aliases = ("degrees", "angle", "hue", "value")
            if has_track(hue_aliases):
                filters.append(f"hue=h={_expr_arg(expression(hue_aliases, hue_value))}")
            else:
                if effect_tracks:
                    warn_unsupported_tracks()
                filters.append(f"hue=h={hue_value:.6f}")
        elif name in {"hsl", "hsl_adjust"}:
            hue_value = max(-360.0, min(360.0, _num(parameters.get("hue", parameters.get("degrees", 0)), 0)))
            saturation_value = max(0.0, min(4.0, _num(parameters.get("saturation", 1), 1)))
            lightness_value = max(-1.0, min(1.0, _num(parameters.get("lightness", parameters.get("brightness", 0)), 0)))
            hue_aliases = ("hue", "degrees", "angle", "value")
            saturation_aliases = ("saturation", "value")
            lightness_aliases = ("lightness", "brightness", "value")
            if effect_tracks and any(has_track(aliases) for aliases in (hue_aliases, saturation_aliases, lightness_aliases)):
                hue_expr = expression(hue_aliases, hue_value)
                saturation_expr = expression(saturation_aliases, saturation_value)
                lightness_expr = expression(lightness_aliases, lightness_value)
                filters.append(
                    f"hue=h={_expr_arg(str(hue_expr))}:s={_expr_arg(str(saturation_expr))}:"
                    f"b={_expr_arg(str(lightness_expr))}"
                )
            else:
                if effect_tracks:
                    warn_unsupported_tracks()
                filters.append(f"hue=h={hue_value:.6f}:s={saturation_value:.6f}:b={lightness_value:.6f}")
        elif name in {"gamma", "gamma_adjust"}:
            gamma_value = max(0.1, min(10.0, _num(parameters.get("gamma", parameters.get("amount", 1)), 1)))
            gamma_aliases = ("gamma", "amount", "value")
            if has_track(gamma_aliases):
                filters.append(f"eq=gamma={_expr_arg(expression(gamma_aliases, gamma_value))}:eval=frame")
            else:
                if effect_tracks:
                    warn_unsupported_tracks()
                filters.append(f"eq=gamma={gamma_value:.6f}")
        elif name in {"color_temperature", "temperature", "warmth"}:
            kelvin = max(1000.0, min(40000.0, _num(parameters.get("kelvin", 6500), 6500)))
            delta = max(-1.0, min(1.0, (kelvin - 6500.0) / 6500.0))
            filters.append(f"colorbalance=rs={-delta * 0.30:.6f}:gs={-delta * 0.05:.6f}:bs={delta * 0.30:.6f}")
        elif name in {"color_balance", "colorbalance"}:
            red = max(-1.0, min(1.0, _num(parameters.get("red", parameters.get("rs", 0)), 0)))
            green = max(-1.0, min(1.0, _num(parameters.get("green", parameters.get("gs", 0)), 0)))
            blue = max(-1.0, min(1.0, _num(parameters.get("blue", parameters.get("bs", 0)), 0)))
            filters.append(f"colorbalance=rs={red:.6f}:gs={green:.6f}:bs={blue:.6f}")
        elif name in {"color_wheel", "three_way_color", "three_way_wheel"}:
            if effect_tracks:
                warn_unsupported_tracks()
            shadows = [max(-1.0, min(1.0, _num(parameters.get(f"shadows_{channel}", 0), 0))) for channel in ("red", "green", "blue")]
            midtones = [max(-1.0, min(1.0, _num(parameters.get(f"midtones_{channel}", 0), 0))) for channel in ("red", "green", "blue")]
            highlights = [max(-1.0, min(1.0, _num(parameters.get(f"highlights_{channel}", 0), 0))) for channel in ("red", "green", "blue")]
            preserve_raw = parameters.get("preserve_luma", parameters.get("pl", False))
            if isinstance(preserve_raw, bool):
                preserve = preserve_raw
            else:
                preserve = str(preserve_raw).strip().lower() in {"1", "true", "yes", "on", "lum"}
            filters.append(
                "colorbalance="
                f"rs={shadows[0]:.6f}:gs={shadows[1]:.6f}:bs={shadows[2]:.6f}:"
                f"rm={midtones[0]:.6f}:gm={midtones[1]:.6f}:bm={midtones[2]:.6f}:"
                f"rh={highlights[0]:.6f}:gh={highlights[1]:.6f}:bh={highlights[2]:.6f}:pl={int(preserve)}"
            )
        elif name == "exposure":
            if effect_tracks:
                warn_unsupported_tracks()
            exposure = max(-3.0, min(3.0, _num(parameters.get("amount", parameters.get("exposure", 0)), 0)))
            black = max(-1.0, min(1.0, _num(parameters.get("black", 0), 0)))
            filters.append(f"exposure=exposure={exposure:.6f}:black={black:.6f}")
        elif name in {"color_levels", "levels", "colorlevels"}:
            if effect_tracks:
                warn_unsupported_tracks()
            input_black = max(-1.0, min(1.0, _num(parameters.get("input_black", parameters.get("rimin", 0)), 0)))
            input_white = max(-1.0, min(1.0, _num(parameters.get("input_white", parameters.get("rimax", 1)), 1)))
            output_black = max(0.0, min(1.0, _num(parameters.get("output_black", parameters.get("romin", 0)), 0)))
            output_white = max(0.0, min(1.0, _num(parameters.get("output_white", parameters.get("romax", 1)), 1)))
            preserve = str(parameters.get("preserve", "none")).strip().lower()
            if preserve in {"false", "0", "none", "off", ""}:
                preserve = "none"
            elif preserve in {"true", "1", "lum", "max", "avg", "sum", "nrm", "pwr"}:
                preserve = "lum" if preserve in {"true", "1"} else preserve
            else:
                invalid_parameter(f"color_levels preserve 无效: {preserve}")
                preserve = "none"
            filters.append(
                "colorlevels="
                f"rimin={input_black:.6f}:gimin={input_black:.6f}:bimin={input_black:.6f}:"
                f"rimax={input_white:.6f}:gimax={input_white:.6f}:bimax={input_white:.6f}:"
                f"romin={output_black:.6f}:gomin={output_black:.6f}:bomin={output_black:.6f}:"
                f"romax={output_white:.6f}:gomax={output_white:.6f}:bomax={output_white:.6f}:preserve={preserve}"
            )
        elif name in {"curves", "curve"}:
            if effect_tracks:
                warn_unsupported_tracks()
            curve_spec = str(parameters.get("all", parameters.get("master", "0/0 1/1"))).strip()
            tokens = curve_spec.split()
            valid = bool(tokens) and all(
                len(token.split("/")) == 2
                and all(0.0 <= _num(part, -1.0) <= 1.0 for part in token.split("/"))
                and re.fullmatch(r"[0-9eE+./-]+", token) is not None
                for token in tokens
            )
            if not valid:
                invalid_parameter("curves all/master 必须是由 0..1 范围 x/y 点组成的空格分隔字符串")
            else:
                filters.append(f"curves=all={_expr_arg(curve_spec)}")
        elif name in {"rgb_curves", "rgb_curve", "channel_curves"}:
            if effect_tracks:
                warn_unsupported_tracks()

            def valid_curve(value: str) -> bool:
                tokens = value.split()
                return bool(tokens) and all(
                    len(token.split("/")) == 2
                    and all(0.0 <= _num(part, -1.0) <= 1.0 for part in token.split("/"))
                    and re.fullmatch(r"[0-9eE+./-]+", token) is not None
                    for token in tokens
                )

            curve_specs: list[tuple[str, str]] = []
            curve_invalid = False
            for parameter_name, option_name in (
                ("all", "all"),
                ("red", "red"),
                ("green", "green"),
                ("blue", "blue"),
            ):
                if parameter_name not in parameters:
                    continue
                raw_curve = str(parameters.get(parameter_name, "")).strip()
                if not raw_curve:
                    continue
                if not valid_curve(raw_curve):
                    invalid_parameter(f"rgb_curves {parameter_name} 必须是由 0..1 范围 x/y 点组成的空格分隔字符串")
                    curve_invalid = True
                    continue
                curve_specs.append((option_name, raw_curve))
            if curve_specs and not curve_invalid:
                filters.append("curves=" + ":".join(f"{option}={_expr_arg(value)}" for option, value in curve_specs))
        elif name in {"color_contrast", "colorcontrast"}:
            if effect_tracks:
                warn_unsupported_tracks()
            red = max(-1.0, min(1.0, _num(parameters.get("red", parameters.get("rc", 0)), 0)))
            green = max(-1.0, min(1.0, _num(parameters.get("green", parameters.get("gm", 0)), 0)))
            blue = max(-1.0, min(1.0, _num(parameters.get("blue", parameters.get("by", 0)), 0)))
            red_weight = max(0.0, min(1.0, _num(parameters.get("red_weight", parameters.get("rcw", 0)), 0)))
            green_weight = max(0.0, min(1.0, _num(parameters.get("green_weight", parameters.get("gmw", 0)), 0)))
            blue_weight = max(0.0, min(1.0, _num(parameters.get("blue_weight", parameters.get("byw", 0)), 0)))
            preserve = max(0.0, min(1.0, _num(parameters.get("preserve_luma", parameters.get("pl", 0)), 0)))
            filters.append(f"colorcontrast=rc={red:.6f}:gm={green:.6f}:by={blue:.6f}:rcw={red_weight:.6f}:gmw={green_weight:.6f}:byw={blue_weight:.6f}:pl={preserve:.6f}")
        elif name == "vignette":
            angle = _num(parameters.get("angle", 0.785398), 0.785398)
            angle_aliases = ("angle", "value")
            if has_track(angle_aliases):
                filters.append(f"vignette=angle={_expr_arg(expression(angle_aliases, angle))}:eval=frame")
            else:
                if effect_tracks:
                    warn_unsupported_tracks()
                filters.append(f"vignette=angle={angle:.6f}")
        elif name in {"noise", "film_grain"}:
            if effect_tracks:
                warn_unsupported_tracks()
            filters.append(f"noise=alls={max(1, int(_num(parameters.get('amount', 8), 8)))}:allf=t+u")
        elif name in {"invert", "negative", "negate"}:
            filters.append("negate")
        elif name in {"edge", "edges", "edgedetect"}:
            low = max(0.0, min(1.0, _num(parameters.get("low", 0.1), 0.1)))
            high = max(low, min(1.0, _num(parameters.get("high", 0.4), 0.4)))
            filters.append(f"edgedetect=low={low:.6f}:high={high:.6f}")
        elif name in {"deband", "debanding"}:
            threshold = max(0.001, min(0.5, _num(parameters.get("threshold", 0.02), 0.02)))
            radius = max(1, min(64, int(_num(parameters.get("range", 16), 16))))
            filters.append(f"deband=1thr={threshold:.6f}:2thr={threshold:.6f}:3thr={threshold:.6f}:4thr={threshold:.6f}:range={radius}")
        elif name == "deflicker":
            if effect_tracks:
                warn_unsupported_tracks()
            size = max(2, min(129, int(round(_num(parameters.get("size", 5), 5)))))
            mode = str(parameters.get("mode", "am")).strip().lower()
            if mode not in {"am", "gm", "hm", "qm", "cm", "pm", "median"}:
                invalid_parameter(f"deflicker mode 无效: {mode}")
                mode = "am"
            filters.append(f"deflicker=size={size}:mode={mode}")
        elif name == "dctdnoiz":
            if effect_tracks:
                warn_unsupported_tracks()
            sigma = max(0.0, min(999.0, _num(parameters.get("sigma", 0), 0)))
            overlap = max(-1, min(15, int(round(_num(parameters.get("overlap", -1), -1)))))
            block_bits = parameters.get("block_bits")
            if block_bits is None and parameters.get("block_size") is not None:
                block_size = max(8, min(16, int(round(_num(parameters.get("block_size"), 8)))))
                block_bits = 4 if block_size >= 16 else 3
            block_bits = max(3, min(4, int(round(_num(block_bits, 3)))))
            filters.append(f"dctdnoiz=sigma={sigma:.6f}:overlap={overlap}:n={block_bits}")
        elif name in {"frame_interpolation", "minterpolate", "optical_flow", "smooth_slow_motion", "slow_motion"}:
            if effect_tracks:
                warn_unsupported_tracks()
            fps = max(1.0, min(240.0, _num(parameters.get("fps", 60.0), 60.0)))
            mi_mode = str(parameters.get("mi_mode", "mci")).strip().lower()
            if mi_mode not in {"dup", "blend", "mci"}:
                invalid_parameter(f"frame_interpolation mi_mode 无效: {mi_mode}")
                mi_mode = "mci"
            mc_mode = str(parameters.get("mc_mode", "obmc")).strip().lower()
            if mc_mode not in {"obmc", "aobmc"}:
                invalid_parameter(f"frame_interpolation mc_mode 无效: {mc_mode}")
                mc_mode = "obmc"
            me_mode = str(parameters.get("me_mode", "bilat")).strip().lower()
            if me_mode not in {"bidir", "bilat"}:
                invalid_parameter(f"frame_interpolation me_mode 无效: {me_mode}")
                me_mode = "bilat"
            me = str(parameters.get("me", parameters.get("me_method", "epzs"))).strip().lower()
            if me not in {"esa", "tss", "tdls", "ntss", "fss", "ds", "hexbs", "epzs", "umh"}:
                invalid_parameter(f"frame_interpolation me 无效: {me}")
                me = "epzs"
            mb_size = max(4, min(16, int(round(_num(parameters.get("mb_size", 16), 16)))))
            search_param = max(4, min(512, int(round(_num(parameters.get("search_param", 32), 32)))))
            vsbmc_raw = parameters.get("vsbmc", False)
            vsbmc = int(vsbmc_raw) if isinstance(vsbmc_raw, bool) else int(_num(vsbmc_raw, 0) >= 0.5)
            scd = str(parameters.get("scd", "fdiff")).strip().lower()
            if scd not in {"none", "fdiff"}:
                invalid_parameter(f"frame_interpolation scd 无效: {scd}")
                scd = "fdiff"
            scd_threshold = max(0.0, min(100.0, _num(parameters.get("scd_threshold", 10.0), 10.0)))
            filters.append(
                f"minterpolate=fps={fps:.6f}:mi_mode={mi_mode}:mc_mode={mc_mode}:me_mode={me_mode}:"
                f"me={me}:mb_size={mb_size}:search_param={search_param}:vsbmc={vsbmc}:scd={scd}:scd_threshold={scd_threshold:.6f}"
            )
        elif name == "hqdn3d":
            if effect_tracks:
                warn_unsupported_tracks()
            luma_spatial = max(0.0, min(30.0, _num(parameters.get("luma_spatial", parameters.get("ls", 4)), 4)))
            chroma_spatial = max(0.0, min(30.0, _num(parameters.get("chroma_spatial", parameters.get("cs", 3)), 3)))
            luma_temporal = max(0.0, min(30.0, _num(parameters.get("luma_temporal", parameters.get("lt", 6)), 6)))
            chroma_temporal = max(0.0, min(30.0, _num(parameters.get("chroma_temporal", parameters.get("ct", 4.5)), 4.5)))
            filters.append(f"hqdn3d={luma_spatial:.4f}:{chroma_spatial:.4f}:{luma_temporal:.4f}:{chroma_temporal:.4f}")
        elif name in {"deshake", "stabilize"}:
            radius = max(1, min(128, int(_num(parameters.get("radius", 16), 16))))
            filters.append(f"deshake=rx={radius}:ry={radius}")
        elif name in {"histeq", "histogram_equalize"}:
            filters.append("histeq")
        elif name in {"gradfun", "gradient_smooth"}:
            filters.append(f"gradfun=thr={max(0.1, min(64.0, _num(parameters.get('threshold', 1.2), 1.2))):.4f}:radius={max(1, min(32, int(_num(parameters.get('radius', 8), 8))))}")
        elif name in {"posterize", "posterization"}:
            levels = max(2, min(256, int(_num(parameters.get("levels", 8), 8))))
            step = max(1, round(255 / (levels - 1)))
            filters.append(f"lutrgb=r='floor(val/{step})*{step}':g='floor(val/{step})*{step}':b='floor(val/{step})*{step}'")
        elif name == "solarize":
            if effect_tracks:
                warn_unsupported_tracks()
            threshold = max(0, min(255, int(round(_num(parameters.get("threshold", 128), 128)))))
            expression = f"if(gt(val,{threshold}),255-val,val)"
            filters.append(f"lutrgb=r={_expr_arg(expression)}:g={_expr_arg(expression)}:b={_expr_arg(expression)}")
        elif name == "threshold":
            if effect_tracks:
                warn_unsupported_tracks()
            threshold = max(0, min(255, int(round(_num(parameters.get("value", parameters.get("threshold", 128)), 128)))))
            expression = f"if(gte(val,{threshold}),255,0)"
            filters.append(f"lutyuv=y={_expr_arg(expression)}")
        elif name == "tmix":
            if effect_tracks:
                warn_unsupported_tracks()
            frames = max(1, min(1024, int(round(_num(parameters.get("frames", 3), 3)))))
            parts = [f"tmix=frames={frames}"]
            if "scale" in parameters:
                parts.append(f"scale={max(0.0, min(32767.0, _num(parameters.get('scale'), 0))):.6f}")
            filters.append(":".join(parts))
        elif name == "tblend":
            if effect_tracks:
                warn_unsupported_tracks()
            mode = str(parameters.get("mode", "average")).strip().lower()
            allowed_modes = {"normal", "addition", "addition128", "and", "average", "burn", "darken", "difference", "difference128", "divide", "dodge", "exclusion", "extremity", "freeze", "glow", "grainextract", "hardlight", "hardmix", "heat", "lighten", "linearlight", "multiply", "multiply128", "negation", "or", "overlay", "phoenix", "pinlight", "reflect", "screen", "softdifference", "softlight", "stain", "subtract", "vividlight", "xor", "geometric", "harmonic", "bleach", "interpolate", "hardoverlay"}
            if mode not in allowed_modes:
                invalid_parameter(f"tblend mode 无效: {mode}")
                mode = "average"
            filters.append(f"tblend=all_mode={mode}")
        elif name in {"lens_correction", "lenscorrection"}:
            if effect_tracks:
                warn_unsupported_tracks()
            k1 = max(-1.0, min(1.0, _num(parameters.get("k1", 0), 0)))
            k2 = max(-1.0, min(1.0, _num(parameters.get("k2", 0), 0)))
            cx = max(0.0, min(1.0, _num(parameters.get("cx", 0.5), 0.5)))
            cy = max(0.0, min(1.0, _num(parameters.get("cy", 0.5), 0.5)))
            filters.append(f"lenscorrection=k1={k1:.6f}:k2={k2:.6f}:cx={cx:.6f}:cy={cy:.6f}")
        elif name in {"draw_box", "drawbox", "rectangle"}:
            if effect_tracks:
                warn_unsupported_tracks()
            x = max(0.0, min(1.0, _num(parameters.get("x", 0.05), 0.05)))
            y = max(0.0, min(1.0, _num(parameters.get("y", 0.05), 0.05)))
            width = max(0.0, min(1.0, _num(parameters.get("width", 0.9), 0.9)))
            height = max(0.0, min(1.0, _num(parameters.get("height", 0.9), 0.9)))
            color = str(parameters.get("color", "white@0.8"))
            if not re.fullmatch(r"[A-Za-z0-9#@._+\-]+", color):
                invalid_parameter("draw_box color 只能包含 FFmpeg 颜色 token 字符")
                color = "white@0.8"
            thickness = max(1, min(256, int(round(_num(parameters.get("thickness", parameters.get("t", 4)), 4)))))
            filters.append(f"drawbox=x=iw*{x:.6f}:y=ih*{y:.6f}:w=iw*{width:.6f}:h=ih*{height:.6f}:color={_quoted(color)}:t={thickness}")
        elif name in {"chroma_key", "chromakey", "green_screen"}:
            color = str(parameters.get("color", "0x00ff00"))
            similarity = max(0.0, min(1.0, _num(parameters.get("similarity", 0.1), 0.1)))
            blend = max(0.0, min(1.0, _num(parameters.get("blend", 0), 0)))
            filters.append(f"colorkey={_quoted(color)}:{similarity:.6f}:{blend:.6f}")
        elif name in {"flip", "horizontal_flip", "hflip"}:
            if effect_tracks:
                warn_unsupported_tracks()
            filters.append("hflip")
        elif name in {"vertical_flip", "vflip"}:
            if effect_tracks:
                warn_unsupported_tracks()
            filters.append("vflip")
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": f"effect:{effect_type}", "message": "当前 FFmpeg 后端没有安全映射"})
    return filters


def _subtitle_filter(
    root: Path,
    subtitle: Any,
    warnings: list[dict[str, Any]],
    clip_id: str,
    clip_start: float = 0.0,
    clip_duration: float = 0.0,
    *,
    timeline_window: bool = False,
    rotation_supported: bool = False,
    assets: dict[str, dict[str, Any]] | None = None,
) -> str | None:
    if not isinstance(subtitle, dict):
        return None
    if subtitle.get("asset_uri"):
        path = resolve_local_path(root, subtitle["asset_uri"], field="subtitle.asset_uri")
        if path.exists():
            if subtitle.get("animation") or isinstance(subtitle.get("style"), dict) and subtitle["style"].get("animation"):
                warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "subtitle_asset_animation", "message": "外部字幕文件的文字动画未执行"})
            return f"subtitles=filename='{_quoted(str(path))}'"
        warnings.append({"code": "SUBTITLE_ASSET_MISSING", "clip_id": clip_id, "message": f"字幕文件不存在: {path}"})
        return None
    if subtitle.get("text") is None:
        return None
    style = subtitle.get("style") if isinstance(subtitle.get("style"), dict) else {}
    source_subtitle_text = str(subtitle.get("text"))
    subtitle_text = source_subtitle_text
    font_size = max(1, int(_num(style.get("fontsize", 52), 52)))
    resolved_font_path = _subtitle_font_path(root, style, assets)
    font_metrics = _load_subtitle_font_metrics(resolved_font_path, font_size)
    subtitle_text = _wrap_subtitle_text(subtitle_text, style, font_size, warnings, clip_id, font_metrics)
    parts = [f"drawtext=text='{_drawtext_arg(subtitle_text)}'", f"fontcolor={_quoted(style.get('fontcolor', 'white'))}", f"fontsize={font_size}"]
    if timeline_window:
        parts.append(f"enable={_expr_arg(f'between(t,{clip_start:.6f},{clip_start + max(0.001, clip_duration):.6f})')}")
    if resolved_font_path is not None:
        parts.append(f"fontfile='{_quoted(str(resolved_font_path))}'")
    integer_options = {
        "line_spacing": ("line_spacing", -2000, 2000),
        "borderw": ("borderw", 0, 100),
        "shadowx": ("shadowx", -2000, 2000),
        "shadowy": ("shadowy", -2000, 2000),
        "boxw": ("boxw", 0, 10000),
        "boxh": ("boxh", 0, 10000),
        "tabsize": ("tabsize", 0, 256),
    }
    for style_key, (drawtext_key, low, high) in integer_options.items():
        if style_key not in style:
            continue
        number = int(round(_clamp(style.get(style_key), low, high, 0)))
        parts.append(f"{drawtext_key}={number}")
    for style_key, drawtext_key in (("bordercolor", "bordercolor"), ("shadowcolor", "shadowcolor")):
        if style_key in style:
            parts.append(f"{drawtext_key}={_quoted(style.get(style_key))}")
    text_align = style.get("text_align", style.get("align"))
    if text_align is not None:
        alignment_tokens = [token.strip().lower() for token in re.split(r"[+|, ]+", str(text_align)) if token.strip()]
        allowed_alignment = {"left", "right", "center", "top", "bottom", "middle", "l", "r", "c", "t", "b", "m"}
        if alignment_tokens and all(token in allowed_alignment for token in alignment_tokens):
            parts.append(f"text_align={'+'.join(alignment_tokens)}")
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "subtitle_text_align", "message": "字幕 text_align 包含当前 drawtext 不支持的方向"})
    if "boxborderw" in style or "box_padding" in style:
        box_border = int(round(_clamp(style.get("boxborderw", style.get("box_padding", 12)), 0, 1000, 12)))
    else:
        box_border = 12
    if style.get("text_shaping") is not None:
        parts.append(f"text_shaping={'1' if bool(style.get('text_shaping')) else '0'}")
    if style.get("fix_bounds") is not None:
        parts.append(f"fix_bounds={'1' if bool(style.get('fix_bounds')) else '0'}")
    if style.get("expansion") is not None:
        expansion = str(style.get("expansion")).lower()
        if expansion in {"none", "normal", "strftime"}:
            parts.append(f"expansion={expansion}")
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "subtitle_expansion", "message": "字幕 expansion 必须是 none、normal 或 strftime"})
    base_x = str(style.get("x", "(w-text_w)/2"))
    base_y = str(style.get("y", "h-text_h-120"))
    word_timing = subtitle.get("word_timing")
    if word_timing:
        entries: list[tuple[str, float, float, int]] = []
        tick_base = max(1, int(_num(subtitle.get("ticks_per_second", 90000), 90000)))
        resolved_words: dict[int, tuple[int, int]] = {}
        if isinstance(word_timing, list):
            try:
                resolved_words = {
                    id(item): (start, end)
                    for item, start, end in word_ranges(source_subtitle_text, [item for item in word_timing if isinstance(item, dict)])
                }
            except ValueError as exc:
                raise AppError("SUBTITLE_WORD_TIMING_TEXT_MISMATCH", str(exc), exit_code=2, path=f"clips[{clip_id}].subtitle.word_timing") from exc
            for word_index, item in enumerate(word_timing):
                if not isinstance(item, dict):
                    continue
                word = str(item.get("text", item.get("word", "")))
                start_value = item.get("start", item.get("start_seconds"))
                end_value = item.get("end", item.get("end_seconds"))
                if start_value is None and item.get("start_tick") is not None:
                    start_value = _num(item.get("start_tick"), 0) / tick_base
                if end_value is None and item.get("end_tick") is not None:
                    end_value = _num(item.get("end_tick"), 0) / tick_base
                try:
                    start_value = float(start_value)
                    end_value = float(end_value)
                except (TypeError, ValueError):
                    continue
                if word and 0 <= start_value < end_value:
                    entries.append((word, start_value, end_value, word_index))
        if not entries:
            warnings.append({"code": "SUBTITLE_WORD_TIMING_INVALID", "clip_id": clip_id, "message": "word_timing 没有可执行的正时间范围，已回退为整句字幕"})
        else:
            base_parts = list(parts)
            if not any(part.startswith("x=") for part in base_parts):
                base_parts.append(f"x={base_x}")
            if not any(part.startswith("y=") for part in base_parts):
                base_parts.append(f"y={base_y}")
            if style.get("box", True):
                base_parts.extend(["box=1", f"boxcolor={_quoted(style.get('boxcolor', 'black@0.45'))}", f"boxborderw={box_border}"])
            word_filters = [":".join(base_parts)]
            prefix_text = ""
            highlight_color = _quoted(style.get("active_color", style.get("highlight_color", "yellow")))
            for word, start_value, end_value, word_index in entries:
                word_parts = [f"drawtext=text='{_drawtext_arg(word)}'", f"fontcolor={highlight_color}", f"fontsize={font_size}"]
                if resolved_font_path is not None:
                    word_parts.append(f"fontfile='{_quoted(str(resolved_font_path))}'")
                original_item = word_timing[word_index] if isinstance(word_timing, list) and word_index < len(word_timing) else None
                source_span = resolved_words.get(id(original_item)) if isinstance(original_item, dict) else None
                prefix = source_subtitle_text[:source_span[0]] if source_span else prefix_text
                prefix_width = _subtitle_text_width(font_metrics, prefix, font_size)
                word_parts.extend([
                    f"x={_expr_arg(f'({base_x})+({prefix_width:.6f})')}",
                    f"y={base_y}",
                    f"enable={_expr_arg(f'gte(t,{clip_start + start_value:.6f})*lt(t,{clip_start + end_value:.6f})')}",
                ])
                word_filters.append(":".join(word_parts))
                prefix_text = source_subtitle_text[:source_span[1]] if source_span else prefix_text + word + " "
            return ",".join(word_filters)
    animation = subtitle.get("animation") if isinstance(subtitle.get("animation"), dict) else style.get("animation") if isinstance(style.get("animation"), dict) else {}
    animation_type = str(animation.get("type", "")).lower().replace("-", "_")
    if animation_type:
        animation_duration = max(0.001, _num(animation.get("duration", min(0.3, max(0.05, clip_duration / 4 or 0.3))), 0.3))
        delay = max(0.0, _num(animation.get("delay", 0.0), 0.0))
        start_expr = f"({clip_start:.6f}+{delay:.6f})"
        end_expr = f"({clip_start:.6f}+{delay + animation_duration:.6f})"
        progress = f"clip((t-{start_expr})/{animation_duration:.6f},0,1)"
        if animation_type in {"fade_in", "fade"}:
            parts.append(f"alpha={_expr_arg(f'if(lt(t,{start_expr}),0,{progress})')}")
        elif animation_type == "fade_out":
            fade_start = clip_start + max(0.0, clip_duration - animation_duration)
            parts.append(f"alpha={_expr_arg(f'if(gt(t,{fade_start:.6f}),clip(({clip_start + clip_duration:.6f}-t)/{animation_duration:.6f},0,1),1)')}")
        elif animation_type in {"slide_up", "slide_down", "slide_left", "slide_right"}:
            distance = max(0.0, _num(animation.get("distance", 80), 80))
            if animation_type == "slide_up":
                y_expr = f"({base_y})+((1-({progress}))*{distance:.4f})"
                parts.append(f"y={_expr_arg(y_expr)}")
            elif animation_type == "slide_down":
                y_expr = f"({base_y})-((1-({progress}))*{distance:.4f})"
                parts.append(f"y={_expr_arg(y_expr)}")
            elif animation_type == "slide_left":
                x_expr = f"({base_x})+((1-({progress}))*{distance:.4f})"
                parts.append(f"x={_expr_arg(x_expr)}")
            else:
                x_expr = f"({base_x})-((1-({progress}))*{distance:.4f})"
                parts.append(f"x={_expr_arg(x_expr)}")
        elif animation_type in {"typewriter", "typing"}:
            chars = [item[2] for item in graphemes(subtitle_text) if item[2] != "\n"]
            if not chars:
                return None
            char_step = animation_duration / max(1, len(chars))
            char_filters: list[str] = []
            prefix_text = ""
            for index, char in enumerate(chars):
                char_parts = [f"drawtext=text='{_drawtext_arg(char)}'", *parts[1:]]
                char_parts = [part for part in char_parts if not part.startswith("enable=")]
                prefix_width = _subtitle_text_width(font_metrics, prefix_text, font_size)
                x_expr = f"({base_x})+({prefix_width:.6f})"
                char_parts.append(f"x={_expr_arg(x_expr)}")
                char_parts.append(f"y={base_y}")
                enable_expr = f"gte(t,{clip_start + delay + index * char_step:.6f})"
                if timeline_window:
                    enable_expr = f"({enable_expr})*lt(t,{clip_start + max(0.001, clip_duration):.6f})"
                char_parts.append(f"enable={_expr_arg(enable_expr)}")
                if style.get("box", True):
                    char_parts.extend(["box=1", f"boxcolor={_quoted(style.get('boxcolor', 'black@0.45'))}", f"boxborderw={box_border}"])
                char_filters.append(":".join(char_parts))
                prefix_text += char
            return ",".join(char_filters)
        elif animation_type == "pop":
            distance = max(0.0, _num(animation.get("distance", 40), 40))
            parts.append(f"alpha={_expr_arg(f'if(lt(t,{start_expr}),0,{progress})')}")
            parts.append(f"y={_expr_arg(f'({base_y})+((1-({progress}))*{distance:.4f})')}")
        elif animation_type == "bounce":
            distance = max(0.0, _num(animation.get("distance", 36), 36))
            bounce_expr = f"({base_y})-abs(sin((t-{start_expr})*PI*2))*{distance:.4f}*({progress})"
            parts.append(f"y={_expr_arg(bounce_expr)}")
        elif animation_type == "rotate":
            parts.append(f"alpha={_expr_arg(f'if(lt(t,{start_expr}),0,{progress})')}")
            if not rotation_supported:
                warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "subtitle_animation:rotate", "message": "片段内字幕仍使用淡入近似；独立字幕轨道支持透明文字层旋转"})
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": f"subtitle_animation:{animation_type}", "message": "未知字幕动画类型"})
    if not any(part.startswith("x=") for part in parts):
        parts.append(f"x={base_x}")
    if not any(part.startswith("y=") for part in parts):
        parts.append(f"y={base_y}")
    if style.get("box", True):
        parts.extend(["box=1", f"boxcolor={_quoted(style.get('boxcolor', 'black@0.45'))}", f"boxborderw={box_border}"])
    return ":".join(parts)


def _flatten_sequence_tracks(project: dict[str, Any], sequence: dict[str, Any], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten nested sequence clips into renderable asset clips.

    Nested sequences remain first-class in the project model, while FFmpeg
    receives a single filter graph. Full-range nested clips are exact in time;
    cropped ranges are mapped proportionally. Static parent transforms,
    effects and blend settings are flattened into child clips. Direct parent
    transform keyframes are projected onto the final sequence clock so an
    animation keeps one phase across adjacent child clips and multiple parent
    layers compose in one expression; reverse interpolation and multiple masks
    in different coordinate spaces remain explicit approximation warnings.
    """
    sequences = {str(item.get("id")): item for item in project.get("sequences", []) if item.get("id")}
    collected: dict[tuple[str, str], dict[str, Any]] = {}

    def transform_values(raw: Any) -> dict[str, float]:
        value = raw if isinstance(raw, dict) else {}
        position = value.get("position") if isinstance(value.get("position"), dict) else {}
        anchor = value.get("anchor") if isinstance(value.get("anchor"), dict) else {}
        return {
            "x": _num(position.get("x", value.get("position_x", 0.5)), 0.5),
            "y": _num(position.get("y", value.get("position_y", 0.5)), 0.5),
            "scale": _num(value.get("scale", 1.0), 1.0),
            "rotation": _num(value.get("rotation", 0.0), 0.0),
            "opacity": _num(value.get("opacity", 1.0), 1.0),
            "anchor_x": _num(anchor.get("x", value.get("anchor_x", 0.5)), 0.5),
            "anchor_y": _num(anchor.get("y", value.get("anchor_y", 0.5)), 0.5),
        }

    def combine_transforms(parent: Any, child: Any) -> dict[str, Any] | None:
        if not isinstance(parent, dict) and not isinstance(child, dict):
            return None
        outer = transform_values(parent)
        inner = transform_values(child)
        offset_x = (inner["x"] - 0.5) * outer["scale"]
        offset_y = (inner["y"] - 0.5) * outer["scale"]
        angle = math.radians(outer["rotation"])
        rotated_x = offset_x * math.cos(angle) - offset_y * math.sin(angle)
        rotated_y = offset_x * math.sin(angle) + offset_y * math.cos(angle)
        return {
            "position": {
                "x": outer["x"] + rotated_x,
                "y": outer["y"] + rotated_y,
            },
            "scale": outer["scale"] * inner["scale"],
            "rotation": outer["rotation"] + inner["rotation"],
            "opacity": max(0.0, min(1.0, outer["opacity"] * inner["opacity"])),
            # Anchor is a leaf-layer placement reference. Parent pivot
            # composition remains explicit in the capability limitations.
            "anchor": {"x": inner["anchor_x"], "y": inner["anchor_y"]},
        }

    def transform_keyframe_tracks(clip: dict[str, Any]) -> list[dict[str, Any]]:
        supported = {
            "transform.position.x", "position.x", "position_x",
            "transform.position.y", "position.y", "position_y",
            "transform.scale", "scale", "transform.rotation", "rotation",
            "transform.opacity", "opacity", "transform.anchor.x", "anchor.x", "anchor_x",
            "transform.anchor.y", "anchor.y", "anchor_y",
        }
        return [
            copy.deepcopy(item)
            for item in clip.get("keyframes", [])
            if isinstance(item, dict) and str(item.get("property", "")) in supported and isinstance(item.get("keyframes"), list)
        ]

    def context_for(parent: dict[str, Any], clip: dict[str, Any]) -> dict[str, Any]:
        clip_transform = clip.get("transform") if isinstance(clip.get("transform"), dict) else None
        clip_effects = clip.get("effects") if isinstance(clip.get("effects"), list) else []
        clip_mask = clip.get("mask") if isinstance(clip.get("mask"), dict) else None
        clip_blend = clip.get("blend") if isinstance(clip.get("blend"), dict) else None
        clip_transform_tracks = transform_keyframe_tracks(clip)
        inherited_layers = parent.get("dynamic_layers") if isinstance(parent.get("dynamic_layers"), list) else []
        parent_transform = parent.get("transform") if isinstance(parent.get("transform"), dict) else None
        parent_anchor = parent_transform.get("anchor") if isinstance(parent_transform, dict) and isinstance(parent_transform.get("anchor"), dict) else {}
        parent_anchor_x = _num(parent_anchor.get("x", parent_transform.get("anchor_x", 0.5) if isinstance(parent_transform, dict) else 0.5), 0.5)
        parent_anchor_y = _num(parent_anchor.get("y", parent_transform.get("anchor_y", 0.5) if isinstance(parent_transform, dict) else 0.5), 0.5)
        if abs(parent_anchor_x - 0.5) > 1e-9 or abs(parent_anchor_y - 0.5) > 1e-9:
            warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "nested_sequence_parent_anchor", "message": "嵌套序列父级 anchor 目前按叶片放置参考点近似，父级枢轴不会改变子层旋转中心"})
        if not inherited_layers and parent.get("dynamic_transform") and isinstance(parent.get("transform"), dict):
            inherited_layers = [{"transform": copy.deepcopy(parent["transform"]), "tracks": copy.deepcopy(parent.get("transform_keyframes", [])), "clock": "global"}]
        has_clip_transform = isinstance(clip_transform, dict) and bool(clip_transform)
        dynamic_transform = bool(inherited_layers or clip_transform_tracks)
        if dynamic_transform:
            dynamic_layers = copy.deepcopy(inherited_layers)
            if has_clip_transform or clip_transform_tracks:
                dynamic_layers.append({"transform": copy.deepcopy(clip_transform) if isinstance(clip_transform, dict) else {}, "tracks": clip_transform_tracks, "clock": "local"})
            combined_transform = copy.deepcopy(clip_transform) if isinstance(clip_transform, dict) else {}
        else:
            combined_transform = combine_transforms(parent.get("transform"), clip_transform)
            dynamic_layers = []
        inherited_masks = parent.get("masks") if isinstance(parent.get("masks"), list) else []
        if not inherited_masks and isinstance(parent.get("mask"), dict):
            inherited_masks = [parent.get("mask")]
        masks = [*copy.deepcopy(inherited_masks)]
        if clip_mask is not None:
            masks.append(copy.deepcopy(clip_mask))
        if len(masks) > 1:
            warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "nested_sequence_multiple_masks", "message": "嵌套序列父子 mask 将按顺序合成 alpha，坐标空间差异保留近似边界"})
        if parent.get("blend") is not None and clip_blend is not None:
            warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "nested_sequence_multiple_blends", "message": "嵌套序列父子同时设置 blend 时采用内层 blend"})
        return {
            "transform": combined_transform,
            "dynamic_transform": dynamic_transform,
            "dynamic_layers": dynamic_layers,
            "transform_keyframes": clip_transform_tracks if dynamic_transform else [],
            "keyframe_duration_tick": max(1, int(clip.get("duration_tick", 1))),
            "effects": [*parent.get("effects", []), *copy.deepcopy(clip_effects)],
            "masks": masks,
            "mask": copy.deepcopy(masks[-1]) if masks else None,
            "blend": copy.deepcopy(clip_blend if clip_blend is not None else parent.get("blend")),
        }

    def apply_context(clip: dict[str, Any], context: dict[str, Any]) -> None:
        dynamic_layers = context.get("dynamic_layers") if isinstance(context.get("dynamic_layers"), list) else []
        if context.get("dynamic_transform") and dynamic_layers:
            clip["_nested_parent_transforms"] = copy.deepcopy(dynamic_layers)
            if len(dynamic_layers) == 1 and isinstance(dynamic_layers[0], dict):
                layer_transform = dynamic_layers[0].get("transform") if isinstance(dynamic_layers[0].get("transform"), dict) else dynamic_layers[0]
                clip["_nested_parent_transform"] = copy.deepcopy(layer_transform)
            child_duration = max(1, int(clip.get("duration_tick", 1)))
            inherited_tracks: list[dict[str, Any]] = []
            layer_count = len(dynamic_layers)
            for layer_index, layer in enumerate(dynamic_layers):
                tracks = layer.get("tracks", []) if isinstance(layer, dict) else []
                prefix = "nested.parent.transform" if layer_count == 1 else f"nested.parent.{layer_index}.transform"
                for track in tracks:
                    property_name = str(track.get("property", ""))
                    if property_name.startswith("transform."):
                        property_name = f"{prefix}.{property_name[len('transform.') :]}"
                    elif property_name in {"position.x", "position.y", "position_x", "position_y", "scale", "rotation", "opacity", "anchor.x", "anchor.y", "anchor_x", "anchor_y"}:
                        property_name = f"{prefix}.{property_name}"
                    else:
                        continue
                    mapped_track = {**copy.deepcopy(track), "property": property_name, "keyframes": []}
                    for keyframe in track.get("keyframes", []):
                        if not isinstance(keyframe, dict):
                            continue
                        mapped = copy.deepcopy(keyframe)
                        raw_at = _num(keyframe.get("at_tick", 0), 0)
                        if context.get("keyframes_are_global"):
                            # Keep values before the child start. The shared
                            # evaluator uses them to calculate the parent's
                            # interpolated value at this child boundary instead
                            # of resetting every child to the first keyframe.
                            mapped["at_tick"] = int(round(raw_at - _num(clip.get("timeline_start_tick", 0), 0)))
                        else:
                            parent_duration = max(1, int(context.get("keyframe_duration_tick", 1)))
                            mapped["at_tick"] = int(round(raw_at / parent_duration * child_duration))
                        mapped_track["keyframes"].append(mapped)
                    if mapped_track["keyframes"]:
                        inherited_tracks.append(mapped_track)
            if inherited_tracks:
                clip["keyframes"] = [*copy.deepcopy(clip.get("keyframes", [])), *inherited_tracks]
        elif context.get("transform") is not None:
            clip["transform"] = combine_transforms(context.get("transform"), clip.get("transform"))
        inherited_effects = context.get("effects") if isinstance(context.get("effects"), list) else []
        if inherited_effects:
            child_effects = clip.get("effects") if isinstance(clip.get("effects"), list) else []
            clip["effects"] = [*copy.deepcopy(inherited_effects), *copy.deepcopy(child_effects)]
        inherited_masks = context.get("masks") if isinstance(context.get("masks"), list) else []
        if inherited_masks:
            if isinstance(clip.get("mask"), dict):
                warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "nested_sequence_multiple_masks", "message": "嵌套序列父子 mask 将按顺序合成 alpha，坐标空间差异保留近似边界"})
            clip["_nested_parent_masks"] = copy.deepcopy(inherited_masks)
        if context.get("blend") is not None and not isinstance(clip.get("blend"), dict):
            clip["blend"] = copy.deepcopy(context["blend"])

    def visit(
        current: dict[str, Any],
        origin_tick: int,
        scale: float,
        source_window: tuple[int, int],
        prefix: str,
        stack: tuple[str, ...],
        inherited: dict[str, Any] | None = None,
        reverse_time: bool = False,
        time_mapper: Callable[[float], float] | None = None,
    ) -> None:
        current_id = str(current.get("id"))
        if current_id in stack:
            raise AppError("SEQUENCE_CYCLE", "嵌套序列存在循环引用，拒绝渲染", exit_code=2, path="sequences")
        next_stack = stack + (current_id,)
        window_start, window_end = source_window

        def current_to_final(tick: float) -> float:
            if time_mapper is not None:
                return float(time_mapper(float(tick)))
            if reverse_time:
                return float(origin_tick + (window_end - tick) * scale)
            return float(origin_tick + (tick - window_start) * scale)

        for track in sorted(current.get("tracks", []), key=lambda item: int(item.get("order", 0))):
            if track.get("muted"):
                continue
            kind = str(track.get("kind", "video"))
            virtual_id = f"{prefix}{track.get('id', 'track')}"
            key = (kind, virtual_id)
            output_track = collected.setdefault(
                key,
                {
                    "id": virtual_id,
                    "kind": kind,
                    "order": int(track.get("order", 0)),
                    "muted": False,
                    "locked": False,
                    "overlap_policy": track.get("overlap_policy"),
                    "role": track.get("role"),
                    "duck_under_voice": track.get("duck_under_voice"),
                    "audio": copy.deepcopy(track.get("audio")) if isinstance(track.get("audio"), dict) else {},
                    "clips": [],
                },
            )
            for clip in sorted(track.get("clips", []), key=lambda item: int(item.get("timeline_start_tick", 0))):
                clip_start = int(clip.get("timeline_start_tick", 0))
                clip_end = clip_start + int(clip.get("duration_tick", 0))
                overlap_start = max(clip_start, window_start)
                overlap_end = min(clip_end, window_end)
                if overlap_end <= overlap_start:
                    continue
                mapped_left = current_to_final(overlap_start)
                mapped_right = current_to_final(overlap_end)
                mapped_start = int(round(min(mapped_left, mapped_right)))
                mapped_duration = max(1, int(round(abs(mapped_right - mapped_left))))
                if clip.get("sequence_id"):
                    child = sequences.get(str(clip.get("sequence_id")))
                    if child is None:
                        raise AppError("SEQUENCE_REFERENCE_MISSING", f"找不到嵌套序列: {clip.get('sequence_id')}", exit_code=2, path=f"clip[{clip.get('id')}].sequence_id")
                    source_base = int(clip.get("source_in_tick", 0))
                    source_limit = int(clip.get("source_out_tick", source_base + int(child.get("duration_tick", 1))))
                    source_limit = max(source_base + 1, source_limit)
                    effective_reverse = bool(reverse_time) ^ bool(clip.get("reverse"))
                    parent_elapsed_start = max(0, overlap_start - clip_start)
                    parent_elapsed_end = max(parent_elapsed_start, overlap_end - clip_start)
                    source_span_tick = max(1, source_limit - source_base)
                    speed_segments = _speed_curve_segments(clip, source_span_tick, int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000)))
                    curve_duration_seconds = speed_curve_duration_seconds(
                        clip,
                        source_span_tick,
                        int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000)),
                    )
                    nested_speed = max(0.01, _num(clip.get("speed", 1.0), 1.0))
                    curve_scale = None
                    if speed_segments and curve_duration_seconds is not None:
                        tps_local = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000))
                        curve_total_ticks = max(1e-9, curve_duration_seconds * tps_local)
                        curve_scale = max(1e-9, (clip_end - clip_start) / curve_total_ticks)

                        def source_at_parent_elapsed(elapsed_tick: float) -> int:
                            curve_elapsed = max(0.0, min(curve_duration_seconds, elapsed_tick / curve_scale / tps_local))
                            source_seconds = _speed_curve_source_seconds_at_elapsed(speed_segments, curve_elapsed)
                            return source_base + int(round(source_seconds * tps_local))

                        if effective_reverse:
                            child_source_in = source_at_parent_elapsed(curve_total_ticks * curve_scale - parent_elapsed_end)
                            child_source_out = source_at_parent_elapsed(curve_total_ticks * curve_scale - parent_elapsed_start)
                        else:
                            child_source_in = source_at_parent_elapsed(parent_elapsed_start)
                            child_source_out = source_at_parent_elapsed(parent_elapsed_end)

                        def child_to_final(child_tick: float) -> float:
                            source_offset = max(0.0, min(float(source_span_tick), float(child_tick - source_base)))
                            curve_elapsed = _speed_curve_elapsed_seconds(speed_segments, source_offset / tps_local)
                            parent_elapsed = curve_elapsed * tps_local * curve_scale
                            parent_time = clip_end - parent_elapsed if effective_reverse else clip_start + parent_elapsed
                            return current_to_final(parent_time)

                        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "nested_sequence_speed_curve_piecewise", "message": "嵌套序列 speed_curve 使用本地解析积分映射源时间边界；叶片片段内部按区间平均速度渲染，曲线断点和累计时长保持一致"})
                    else:
                        if effective_reverse:
                            child_source_in = source_limit - int(round(parent_elapsed_end * nested_speed))
                            child_source_out = source_limit - int(round(parent_elapsed_start * nested_speed))
                        else:
                            child_source_in = source_base + int(round(parent_elapsed_start * nested_speed))
                            child_source_out = source_base + int(round(parent_elapsed_end * nested_speed))

                        def child_to_final(child_tick: float) -> float:
                            source_offset = max(0.0, min(float(source_span_tick), float(child_tick - source_base)))
                            parent_elapsed = source_offset / nested_speed
                            parent_time = clip_end - parent_elapsed if effective_reverse else clip_start + parent_elapsed
                            return current_to_final(parent_time)

                    child_source_in = max(source_base, min(source_limit - 1, child_source_in))
                    child_source_out = max(child_source_in + 1, min(source_limit, child_source_out))
                    parent_context = context_for(inherited or {"transform": None, "effects": [], "masks": [], "mask": None, "blend": None}, clip)
                    if parent_context.get("dynamic_transform"):
                        # Parent keyframes live in the current sequence clock.
                        # Convert each newly-created local layer once to the
                        # final timeline clock before visiting children;
                        # inherited layers are already global and must not be
                        # remapped at every nesting level.
                        global_layers: list[dict[str, Any]] = []
                        for layer in parent_context.get("dynamic_layers", []):
                            mapped_layer = copy.deepcopy(layer)
                            if str(mapped_layer.get("clock", "local")) == "local":
                                global_tracks: list[dict[str, Any]] = []
                                for track_value in mapped_layer.get("tracks", []):
                                    mapped_track = copy.deepcopy(track_value)
                                    mapped_track["keyframes"] = []
                                    for keyframe in track_value.get("keyframes", []):
                                        if not isinstance(keyframe, dict):
                                            continue
                                        mapped = copy.deepcopy(keyframe)
                                        local_at = _num(keyframe.get("at_tick", 0), 0)
                                        if effective_reverse:
                                            local_at = int(clip.get("duration_tick", 1)) - local_at
                                            _reverse_keyframe_controls(mapped)
                                        if time_mapper is not None:
                                            mapped["at_tick"] = int(round(current_to_final(clip_start + local_at)))
                                        else:
                                            mapped["at_tick"] = int(round(
                                                origin_tick + ((clip_start + local_at - window_start) * scale)
                                            ))
                                        mapped_track["keyframes"].append(mapped)
                                    if mapped_track["keyframes"]:
                                        global_tracks.append(mapped_track)
                                mapped_layer["tracks"] = global_tracks
                                mapped_layer["clock"] = "global"
                            global_layers.append(mapped_layer)
                        parent_context["dynamic_layers"] = global_layers
                        parent_context["keyframes_are_global"] = True
                    child_windows: list[tuple[int, int]] = [(child_source_in, child_source_out)]
                    if speed_segments:
                        tps_local = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000))
                        split_windows: list[tuple[int, int]] = []
                        for segment_start, segment_end, _, _ in speed_segments:
                            segment_source_start = source_base + int(round(segment_start * tps_local))
                            segment_source_end = source_base + int(round(segment_end * tps_local))
                            part_start = max(child_source_in, segment_source_start)
                            part_end = min(child_source_out, segment_source_end)
                            if part_end > part_start:
                                split_windows.append((part_start, part_end))
                        if split_windows:
                            child_windows = split_windows
                    for child_window in child_windows:
                        visit(
                            child,
                            0,
                            1.0,
                            child_window,
                            f"{prefix}{clip.get('id')}.",
                            next_stack,
                            parent_context,
                            effective_reverse,
                            child_to_final,
                        )
                    continue
                child_clip = copy.deepcopy(clip)
                child_clip["id"] = f"{prefix}{clip.get('id', 'clip')}"
                child_clip["timeline_start_tick"] = mapped_start
                child_clip["duration_tick"] = mapped_duration
                # A nested sequence reverse (or speed/time remap) changes the
                # leaf clip's local clock as well as its source frames. Map
                # every authored keyframe through the same clock function so
                # transform/crop/mask/audio automation follows the visual
                # content. Bezier easing is reversed analytically when the
                # parent timeline runs backwards; a nonlinear speed curve
                # still has a documented piecewise interpolation boundary.
                original_keyframe_tracks = child_clip.get("keyframes")
                if isinstance(original_keyframe_tracks, list):
                    mapped_keyframe_tracks: list[dict[str, Any]] = []
                    for track_value in original_keyframe_tracks:
                        if not isinstance(track_value, dict) or not isinstance(track_value.get("keyframes"), list):
                            mapped_keyframe_tracks.append(track_value)
                            continue
                        mapped_track = copy.deepcopy(track_value)
                        mapped_track["keyframes"] = []
                        for keyframe_value in track_value.get("keyframes", []):
                            if not isinstance(keyframe_value, dict):
                                continue
                            mapped_keyframe = copy.deepcopy(keyframe_value)
                            local_at = _num(keyframe_value.get("at_tick", 0), 0.0)
                            final_at = current_to_final(clip_start + local_at)
                            mapped_keyframe["at_tick"] = int(round(final_at - mapped_start))
                            if reverse_time:
                                _reverse_keyframe_controls(mapped_keyframe)
                            mapped_track["keyframes"].append(mapped_keyframe)
                        mapped_keyframe_tracks.append(mapped_track)
                    child_clip["keyframes"] = mapped_keyframe_tracks
                # `scale` is the child-timeline to final-timeline ratio. A
                # nested sequence that plays at 2x therefore needs its leaf
                # clips to render at 1/scale so FFmpeg emits the mapped
                # duration instead of the original child duration.
                effective_leaf_scale = scale
                if time_mapper is not None:
                    effective_leaf_scale = abs(mapped_right - mapped_left) / max(1.0, float(overlap_end - overlap_start))
                if abs(effective_leaf_scale - 1.0) > 1e-9:
                    child_speed = max(0.01, _num(child_clip.get("speed", 1.0), 1.0))
                    child_clip["speed"] = child_speed / max(1e-9, effective_leaf_scale)
                if reverse_time or overlap_start != clip_start or overlap_end != clip_end:
                    source_in = int(child_clip.get("source_in_tick", 0))
                    source_out = int(child_clip.get("source_out_tick", source_in + max(1, int(child_clip.get("duration_tick", 1)))))
                    source_span = max(1, source_out - source_in)
                    clip_span = max(1, clip_end - clip_start)
                    left_ratio = max(0.0, min(1.0, (overlap_start - clip_start) / clip_span))
                    right_ratio = max(left_ratio, min(1.0, (overlap_end - clip_start) / clip_span))
                    # The chronological source subrange is trimmed first;
                    # the leaf's reverse flag then presents that range in
                    # reverse order. Using source_out as the anchor here
                    # would select frames beyond a partially clipped nested
                    # window.
                    child_clip["source_in_tick"] = source_in + int(round(source_span * left_ratio))
                    child_clip["source_out_tick"] = max(
                        child_clip["source_in_tick"] + 1,
                        source_in + int(round(source_span * right_ratio)),
                    )
                    if reverse_time:
                        child_clip["reverse"] = not bool(child_clip.get("reverse"))
                if inherited:
                    apply_context(child_clip, inherited)
                if any(existing.get("id") == child_clip["id"] for existing in output_track["clips"]):
                    base_id = child_clip["id"]
                    part_index = 2
                    while any(existing.get("id") == f"{base_id}.part{part_index}" for existing in output_track["clips"]):
                        part_index += 1
                    child_clip["id"] = f"{base_id}.part{part_index}"
                output_track["clips"].append(child_clip)

    visit(sequence, 0, 1.0, (0, int(sequence.get("duration_tick", 1))), "", (), {"transform": None, "effects": [], "masks": [], "mask": None, "blend": None})
    return list(collected.values())


def _build_subtitle_layer(
    root: Path,
    overlay: dict[str, Any],
    subtitle_index: int,
    filters: list[str],
    warnings: list[dict[str, Any]],
    *,
    width: int,
    height: int,
    fps_value: str,
    duration: float,
    tps: int,
) -> dict[str, Any]:
    """Compile one independent text clip into a reusable transparent layer.

    The returned spec deliberately matches the video compositor's contract.
    Keeping text and media layers in the same queue makes ``track.order`` a
    deterministic z-order for mixed video/title timelines, while the text
    raster remains transparent outside its authored timeline window.
    """
    animation = overlay.get("animation") if isinstance(overlay.get("animation"), dict) else {}
    clip_value = overlay.get("clip") if isinstance(overlay.get("clip"), dict) else {}
    clip_id = str(overlay.get("clip_id"))
    clip_start = float(overlay.get("start", 0.0))
    clip_duration = max(0.001, float(overlay.get("duration", 0.001)))
    transform = _transform_exprs(clip_value, clip_start, tps)
    canvas_label = f"subtitlecanvas{subtitle_index}"
    layer_label = f"subtitlelayer{subtitle_index}"
    filters.append(f"color=c=black@0.0:s={width}x{height}:r={fps_value}:d={duration:.6f},format=rgba[{canvas_label}]")
    filters.append(f"[{canvas_label}]{overlay['filter']}[{layer_label}]")

    if transform["scale"] != "1.00000000":
        scale_w = _expr_arg(f"max(2,iw*({transform['scale']}))")
        scale_h = _expr_arg(f"max(2,ih*({transform['scale']}))")
        scaled_label = f"subtitle_scaled{subtitle_index}"
        filters.append(f"[{layer_label}]scale=w={scale_w}:h={scale_h}:eval=frame,format=rgba[{scaled_label}]")
        layer_label = scaled_label

    rotation_expression = transform["rotation"]
    if overlay.get("animation_type") == "rotate":
        animation_start = clip_start + max(0.0, _num(animation.get("delay", 0.0), 0.0))
        animation_duration = max(0.001, _num(animation.get("duration", 0.3), 0.3))
        from_degrees = _num(animation.get("from_degrees", animation.get("from", -90.0)), -90.0)
        to_degrees = _num(animation.get("to_degrees", animation.get("to", animation.get("angle", 0.0))), 0.0)
        progress = f"clip((t-{animation_start:.6f})/{animation_duration:.6f},0,1)"
        animation_angle = f"({from_degrees:.6f}+({to_degrees - from_degrees:.6f})*{progress})"
        rotation_expression = f"({transform['rotation']})+({animation_angle})"
    if rotation_expression != "0.00000000":
        rotated_label = f"subtitle_rotated{subtitle_index}"
        rotation_radians = _expr_arg(f"({rotation_expression})*PI/180")
        filters.append(f"[{layer_label}]rotate={rotation_radians}:fillcolor=black@0.0:ow=iw:oh=ih,format=rgba[{rotated_label}]")
        layer_label = rotated_label

    effect_filters = _effect_filters(
        clip_value.get("effects"),
        warnings,
        clip_id,
        root=root,
        clip=clip_value,
        clip_start=clip_start,
        tps=tps,
    )
    if effect_filters:
        effect_label = f"subtitle_effects{subtitle_index}"
        filters.append(f"[{layer_label}]" + ",".join(effect_filters) + f",format=rgba[{effect_label}]")
        layer_label = effect_label

    if transform["opacity"] != "1.00000000":
        opacity_label = f"subtitle_opacity{subtitle_index}"
        alpha_expr = f"alpha(X,Y)*clip(({transform['opacity']}),0,1)"
        filters.append(f"[{layer_label}]format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)},format=rgba[{opacity_label}]")
        layer_label = opacity_label

    mask_values: list[dict[str, Any]] = []
    inherited_masks = clip_value.get("_nested_parent_masks")
    if isinstance(inherited_masks, list):
        mask_values.extend(item for item in inherited_masks if isinstance(item, dict))
    if isinstance(clip_value.get("mask"), dict):
        mask_values.append(clip_value["mask"])
    for mask_index, mask_value in enumerate(mask_values):
        mask_filter = _mask_filter(mask_value, warnings, clip_id, clip=clip_value, clip_start=clip_start, tps=tps)
        if mask_filter:
            masked_label = f"subtitle_mask{subtitle_index}_{mask_index}"
            filters.append(f"[{layer_label}]format=rgba,{mask_filter}[{masked_label}]")
            layer_label = masked_label

    incoming = clip_value.get("transition_in") if isinstance(clip_value.get("transition_in"), dict) else {}
    outgoing = clip_value.get("transition_out") if isinstance(clip_value.get("transition_out"), dict) else {}
    transition_opacity = "1.00000000"
    wipe_alpha = "1.00000000"
    position_x_expr = f"({transform['position_x']})*W-w*({transform['anchor_x']})"
    position_y_expr = f"({transform['position_y']})*H-h*({transform['anchor_y']})"
    unsupported_transitions: list[str] = []

    def _spatial_transition(raw_type: str, config: dict[str, Any]) -> tuple[str, str] | None:
        normalized = raw_type.lower().replace("-", "_")
        aliases = {
            "slideleft": ("slide", "left"),
            "slideright": ("slide", "right"),
            "slideup": ("slide", "up"),
            "slidedown": ("slide", "down"),
            "wipeleft": ("wipe", "left"),
            "wiperight": ("wipe", "right"),
            "wipeup": ("wipe", "up"),
            "wipedown": ("wipe", "down"),
        }
        if normalized in aliases:
            return aliases[normalized]
        if normalized not in {"slide", "slide_in", "slide_out", "wipe", "wipe_in", "wipe_out"}:
            return None
        direction = str(config.get("direction", "left")).lower().replace("-", "_")
        direction = {"top": "up", "bottom": "down"}.get(direction, direction)
        if direction not in {"left", "right", "up", "down"}:
            direction = "left"
        return ("wipe" if normalized.startswith("wipe") else "slide", direction)

    def _slide_offset(direction: str) -> str:
        distance = "(W+w)" if direction in {"left", "right"} else "(H+h)"
        sign = "-" if direction in {"left", "up"} else "+"
        return f"{sign}{distance}"

    def _wipe_visibility(direction: str, progress: str, *, entering: bool) -> str:
        if direction == "left":
            condition = f"lt(X,W*({progress}))" if entering else f"gt(X,W*(1-({progress})))"
        elif direction == "right":
            condition = f"gt(X,W*(1-({progress})))" if entering else f"lt(X,W*({progress}))"
        elif direction == "up":
            condition = f"gt(Y,H*(1-({progress})))" if entering else f"lt(Y,H*({progress}))"
        else:
            condition = f"lt(Y,H*({progress}))" if entering else f"gt(Y,H*(1-({progress})))"
        return f"if({condition},1,0)"

    def _apply_spatial(config: dict[str, Any], raw_type: str, *, entering: bool) -> bool:
        nonlocal position_x_expr, position_y_expr, wipe_alpha
        spatial = _spatial_transition(raw_type, config)
        if spatial is None:
            return False
        spatial_type, direction = spatial
        transition_duration = max(0.001, _num(config.get("duration", 0.25), 0.25))
        time_variable = "T" if spatial_type == "wipe" else "t"
        if entering:
            progress = f"clip(({time_variable}-{clip_start:.6f})/{transition_duration:.6f},0,1)"
        else:
            transition_start = clip_start + max(0.0, clip_duration - transition_duration)
            progress = f"clip(({time_variable}-{transition_start:.6f})/{transition_duration:.6f},0,1)"
        if spatial_type == "slide":
            offset = _slide_offset(direction)
            if entering:
                position_x_expr = f"({position_x_expr})+((1-({progress}))*({offset if direction in {'left', 'right'} else '0'}))"
                position_y_expr = f"({position_y_expr})+((1-({progress}))*({offset if direction in {'up', 'down'} else '0'}))"
            else:
                position_x_expr = f"({position_x_expr})+(({progress})*({offset if direction in {'left', 'right'} else '0'}))"
                position_y_expr = f"({position_y_expr})+(({progress})*({offset if direction in {'up', 'down'} else '0'}))"
        else:
            wipe_alpha = f"({wipe_alpha})*({_wipe_visibility(direction, progress, entering=entering)})"
        return True

    incoming_type = str(incoming.get("type", "")).lower().replace("-", "_")
    if incoming_type:
        if incoming_type in {"fade", "fade_in", "dissolve", "crossfade"}:
            transition_duration = max(0.001, _num(incoming.get("duration", 0.25), 0.25))
            transition_expr = f"if(lt(T,{clip_start:.6f}),0,clip((T-{clip_start:.6f})/{transition_duration:.6f},0,1))"
            transition_opacity = f"({transition_opacity})*({transition_expr})"
        elif not _apply_spatial(incoming, incoming_type, entering=True):
            unsupported_transitions.append(f"transition_in:{incoming_type}")
    outgoing_type = str(outgoing.get("type", "")).lower().replace("-", "_")
    if outgoing_type:
        if outgoing_type in {"fade", "fade_out", "dissolve", "crossfade"}:
            transition_duration = max(0.001, _num(outgoing.get("duration", 0.25), 0.25))
            fade_start = clip_start + max(0.0, clip_duration - transition_duration)
            fade_end = clip_start + clip_duration
            transition_expr = f"if(gt(T,{fade_start:.6f}),clip(({fade_end:.6f}-T)/{transition_duration:.6f},0,1),1)"
            transition_opacity = f"({transition_opacity})*({transition_expr})"
        elif not _apply_spatial(outgoing, outgoing_type, entering=False):
            unsupported_transitions.append(f"transition_out:{outgoing_type}")
    if transition_opacity != "1.00000000" or wipe_alpha != "1.00000000":
        transition_label = f"subtitle_transition_opacity{subtitle_index}"
        alpha_expr = f"alpha(X,Y)*clip(({transition_opacity}),0,1)*clip(({wipe_alpha}),0,1)"
        filters.append(f"[{layer_label}]format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)},format=rgba[{transition_label}]")
        layer_label = transition_label
    if unsupported_transitions:
        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "subtitle_transition", "message": f"独立文字层已执行 fade/dissolve alpha、slide/wipe 空间转场；以下转场仍保留基础文字时间窗: {','.join(unsupported_transitions)}"})
    return {
        "label": layer_label,
        "position": f"x={_expr_arg(position_x_expr)}:y={_expr_arg(position_y_expr)}",
        "track_id": overlay.get("track_id"),
        "track_order": int(overlay.get("track_order", 0)),
        "layer_order": subtitle_index,
        "clip_id": clip_id,
        "keyframes": copy.deepcopy(clip_value.get("keyframes", [])),
        "start": clip_start,
        "duration": clip_duration,
        "blend": clip_value.get("blend"),
        "kind": "subtitle",
    }


def build_filter_graph(root: Path, project: dict[str, Any], sequence: dict[str, Any]) -> tuple[list[str], str, list[dict[str, Any]], list[dict[str, Any]]]:
    settings = project["settings"]
    tps = int(settings["timebase"]["ticks_per_second"])
    width = int(settings["canvas"]["width"])
    height = int(settings["canvas"]["height"])
    fps = settings["timebase"].get("display_fps", {"num": 30, "den": 1})
    fps_value = f"{fps['num']}/{fps['den']}"
    frame_duration = max(1e-6, float(fps.get("den", 1)) / max(1.0, float(fps.get("num", 30))))
    duration = max(_sec(int(sequence.get("duration_tick", 1)), tps), 1 / max(1, int(fps["num"])))
    raw_output = settings.get("output") if isinstance(settings.get("output"), dict) else {}
    raw_video_output = raw_output.get("video") if isinstance(raw_output.get("video"), dict) else {}
    transparent_canvas = str(raw_video_output.get("pixel_format", "")).lower() in ALPHA_OUTPUT_PIXEL_FORMATS
    color_tone_map = str((settings.get("color") or {}).get("tone_map", (settings.get("color") or {}).get("tone_mapping", "none"))).lower() if isinstance(settings.get("color"), dict) else "none"
    assets = asset_map(project)
    inputs: list[str] = []
    filters: list[str] = []
    video_labels: list[str] = []
    video_positions: list[str] = []
    video_specs: list[dict[str, Any]] = []
    audio_labels: list[str] = []
    voice_audio_labels: list[str] = []
    music_audio_labels: list[str] = []
    other_audio_labels: list[str] = []
    ducking_requested = False
    input_meta: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    subtitle_overlays: list[dict[str, Any]] = []
    adjustment_layers: list[tuple[str, list[Any], float, float]] = []
    raw_adjustments = settings.get("adjustments")
    if isinstance(raw_adjustments, list):
        for adjustment_index, raw_layer in enumerate(raw_adjustments):
            layer_id = f"adjustment_{adjustment_index}"
            if isinstance(raw_layer, str):
                adjustment_layers.append((layer_id, [raw_layer], 0.0, duration))
                continue
            if not isinstance(raw_layer, dict) or raw_layer.get("enabled", True) is False:
                continue
            if isinstance(raw_layer.get("effects"), list):
                effects = list(raw_layer["effects"])
            elif raw_layer.get("type"):
                effects = [raw_layer]
            else:
                effects = []
            if effects:
                start_tick = max(0, _tick(raw_layer.get("start_tick"), 0))
                duration_tick = _tick(raw_layer.get("duration_tick"), 0)
                start = min(duration, _sec(start_tick, tps))
                end = duration if duration_tick <= 0 else min(duration, start + _sec(duration_tick, tps))
                adjustment_layers.append((str(raw_layer.get("id", layer_id)), effects, start, end))
    has_adjustments = bool(adjustment_layers)
    index = 0
    render_tracks = _flatten_sequence_tracks(project, sequence, warnings)
    audio_track_controls = {
        str(track.get("id")): track.get("audio") if isinstance(track.get("audio"), dict) else {}
        for track in render_tracks
        if track.get("kind") == "audio"
    }
    solo_audio_tracks = {
        track_id
        for track_id, controls in audio_track_controls.items()
        if bool(controls.get("solo", False))
    }
    for track in sorted(render_tracks, key=lambda item: int(item.get("order", 0))):
        track_audio = track.get("audio") if isinstance(track.get("audio"), dict) else {}
        track_id = str(track.get("id"))
        if track.get("kind") == "audio" and solo_audio_tracks and track_id not in solo_audio_tracks:
            continue
        if track.get("muted") or bool(track_audio.get("muted", False) or track_audio.get("mute", False)):
            continue
        for clip in sorted(track.get("clips", []), key=lambda item: int(item.get("timeline_start_tick", 0))):
            asset = assets.get(clip.get("asset_id"))
            if track.get("kind") == "subtitle":
                subtitle = clip.get("subtitle") if isinstance(clip.get("subtitle"), dict) else None
                if subtitle is None and asset and asset.get("kind") == "subtitle":
                    subtitle = {"asset_uri": asset.get("uri")}
                if subtitle is None:
                    warnings.append({"code": "SUBTITLE_TRACK_EMPTY", "clip_id": clip.get("id"), "feature": "subtitle_track", "message": "独立字幕轨道片段缺少内联 subtitle 或 subtitle 资产"})
                    continue
                clip_start = _sec(int(clip.get("timeline_start_tick", 0)), tps)
                clip_duration = max(0.001, _sec(int(clip.get("duration_tick", 1)), tps))
                subtitle_filter = _subtitle_filter(
                    root,
                    subtitle,
                    warnings,
                    str(clip.get("id")),
                    clip_start,
                    clip_duration,
                    timeline_window=True,
                    rotation_supported=True,
                    assets=assets,
                )
                if subtitle_filter:
                    animation = subtitle.get("animation") if isinstance(subtitle.get("animation"), dict) else subtitle.get("style", {}).get("animation") if isinstance(subtitle.get("style"), dict) and isinstance(subtitle.get("style", {}).get("animation"), dict) else {}
                    animation_type = str(animation.get("type", "")).lower().replace("-", "_")
                    subtitle_overlays.append({
                        "clip_id": str(clip.get("id")),
                        "track_id": str(track.get("id")),
                        "track_order": int(track.get("order", 0)),
                        "clip": copy.deepcopy(clip),
                        "filter": subtitle_filter,
                        "start": clip_start,
                        "duration": clip_duration,
                        "animation_type": animation_type,
                        "animation": animation,
                    })
                continue
            if not asset:
                continue
            for keyframe_track in clip.get("keyframes", []):
                for keyframe in keyframe_track.get("keyframes", []):
                    if keyframe.get("interpolation") == "bezier" and not isinstance(keyframe.get("control_points"), list):
                        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "bezier_keyframe", "message": "Bezier 关键帧未提供控制点，使用默认三次曲线控制点"})
            uri = Path(str(asset["uri"]))
            if not uri.is_absolute():
                uri = root / uri
            if not uri.exists():
                raise AppError("ASSET_FILE_MISSING", f"渲染输入不存在: {uri}", exit_code=3, path=str(uri))
            kind = asset.get("kind", "video")
            if kind in {"video", "image"} and track.get("kind") == "video":
                if kind == "image":
                    inputs.extend(["-loop", "1", "-i", str(uri)])
                else:
                    inputs.extend(["-i", str(uri)])
                src_in = _sec(int(clip.get("source_in_tick", 0)), tps)
                src_out = _sec(int(clip.get("source_out_tick", clip.get("duration_tick", 1))), tps)
                start = _sec(int(clip.get("timeline_start_tick", 0)), tps)
                label = f"v{index}"
                speed = _num(clip.get("speed", 1.0), 1.0)
                if speed <= 0:
                    raise AppError("SPEED_INVALID", "speed 必须大于 0", exit_code=2, path=f"clips[{clip.get('id')}].speed")
                source_span_tick = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
                speed_segments = _speed_curve_segments(clip, source_span_tick, tps)
                curve_duration = speed_curve_duration_seconds(clip, source_span_tick, tps)
                if speed_segments:
                    mapped_speed_segments = _reverse_speed_curve_segments(speed_segments) if bool(clip.get("reverse")) else speed_segments
                    setpts = _speed_curve_setpts(mapped_speed_segments, start)
                else:
                    setpts = f"setpts=(PTS-STARTPTS)/{speed:.8f}+{start:.6f}/TB" if abs(speed - 1.0) > 1e-9 else f"setpts=PTS-STARTPTS+{start:.6f}/TB"
                transforms = _transform_exprs(clip, start, tps)
                chain = [f"[{index}:v]trim=start={src_in:.6f}:end={src_out:.6f}"]
                if bool(clip.get("reverse")):
                    chain.append("reverse")
                chain.append(setpts)
                if kind == "video" and color_tone_map not in {"", "none"}:
                    chain.extend(_tone_map_filters(settings, warnings, str(clip.get("id")), transparent=transparent_canvas))
                crop = clip.get("crop") if isinstance(clip.get("crop"), dict) else {}
                crop_fit = str(crop.get("fit", crop.get("mode", "fit"))).lower()
                source_probe = asset.get("probe", {}).get("video", {}) if isinstance(asset.get("probe"), dict) else {}
                source_width = max(0, int(_num(source_probe.get("width", 0), 0)))
                source_height = max(0, int(_num(source_probe.get("height", 0), 0)))
                dynamic_crop_rendered = False
                if crop:
                    crop_unit = str(crop.get("unit", "pixels")).lower()
                    normalized_crop = crop_unit in {"normalized", "relative"}
                    default_width = 1.0 if normalized_crop else source_width
                    default_height = 1.0 if normalized_crop else source_height
                    raw_width = _num(crop.get("width", crop.get("w", default_width)), default_width)
                    raw_height = _num(crop.get("height", crop.get("h", default_height)), default_height)
                    raw_x = _num(crop.get("x", 0), 0)
                    raw_y = _num(crop.get("y", 0), 0)
                    dynamic_x = _crop_has_keyframe(clip, crop, ("crop.x", "x"))
                    dynamic_y = _crop_has_keyframe(clip, crop, ("crop.y", "y"))
                    dynamic_width = _crop_has_keyframe(clip, crop, ("crop.width", "crop.w", "width", "w"))
                    dynamic_height = _crop_has_keyframe(clip, crop, ("crop.height", "crop.h", "height", "h"))
                    if crop_unit in {"normalized", "relative"} and source_width and source_height:
                        crop_width = int(round(raw_width * source_width))
                        crop_height = int(round(raw_height * source_height))
                        crop_x = int(round(raw_x * source_width))
                        crop_y = int(round(raw_y * source_height))
                    else:
                        crop_width = int(round(raw_width))
                        crop_height = int(round(raw_height))
                        crop_x = int(round(raw_x))
                        crop_y = int(round(raw_y))
                    crop_x = max(0, crop_x)
                    crop_y = max(0, crop_y)
                    if source_width:
                        crop_x = min(crop_x, max(0, source_width - 2))
                        crop_width = min(crop_width, source_width if dynamic_x else max(2, source_width - crop_x))
                    if source_height:
                        crop_y = min(crop_y, max(0, source_height - 2))
                        crop_height = min(crop_height, source_height if dynamic_y else max(2, source_height - crop_y))
                    crop_width = max(2, crop_width)
                    crop_height = max(2, crop_height)
                    if (dynamic_width or dynamic_height) and source_width and source_height:
                        chain.extend(_dynamic_crop_filters(clip, crop, width, height, source_width, source_height, start, tps))
                        dynamic_crop_rendered = True
                    elif crop_width >= 2 and crop_height >= 2:
                        if dynamic_x or dynamic_y:
                            x_expression = _crop_keyframe_expr(clip, crop, ("crop.x", "x"), raw_x, start, tps)
                            y_expression = _crop_keyframe_expr(clip, crop, ("crop.y", "y"), raw_y, start, tps)
                            if crop_unit in {"normalized", "relative"}:
                                x_expression = f"({x_expression})*iw"
                                y_expression = f"({y_expression})*ih"
                            # FFmpeg crop accepts per-frame x/y expressions, but
                            # its output dimensions must stay fixed.  Clamp the
                            # animated origin so every frame remains in bounds.
                            x_expression = f"max(0,min(iw-out_w,({x_expression})))"
                            y_expression = f"max(0,min(ih-out_h,({y_expression})))"
                            chain.append(f"crop={crop_width}:{crop_height}:x={_expr_arg(x_expression)}:y={_expr_arg(y_expression)}")
                        else:
                            chain.append(f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y}")
                if not dynamic_crop_rendered:
                    if crop_fit == "fill":
                        chain.extend([f"scale={width}:{height}:force_original_aspect_ratio=increase", f"crop={width}:{height}:(iw-ow)/2:(ih-oh)/2", "setsar=1"])
                    elif crop_fit == "stretch":
                        chain.extend([f"scale={width}:{height}", "setsar=1"])
                    else:
                        chain.extend([f"scale={width}:{height}:force_original_aspect_ratio=decrease", f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black", "setsar=1"])
                clip_content_duration = max(
                    0.001,
                    curve_duration if curve_duration is not None else (src_out - src_in) / max(speed, 1e-9),
                )
                freeze = clip.get("freeze") if isinstance(clip.get("freeze"), dict) else None
                freeze_extra = 0.0
                if freeze:
                    freeze_extra = max(0.0, _sec(int(freeze.get("duration_tick", 0)), tps))
                    if freeze_extra > 0:
                        # A freeze is an insertion in the already time-mapped
                        # video stream.  Split after trim/speed/crop so the
                        # requested `at_tick` refers to the clip timeline,
                        # including speed curves and reverse playback.  The
                        # hold branch keeps one decoded frame and tpad clones
                        # it for the requested duration; the other branches
                        # retain their original order and are concatenated
                        # back onto the clip's absolute timeline.
                        requested_at = _sec(int(freeze.get("at_tick", int(round(clip_content_duration * tps)))), tps)
                        freeze_at = max(0.0, min(clip_content_duration, requested_at))
                        base_start = start
                        base_end = start + clip_content_duration
                        hold_start = max(base_start, base_start + freeze_at - frame_duration)
                        hold_end = min(base_end, hold_start + (frame_duration * 2.0))
                        freeze_prefix = f"freeze{index}"
                        hold_input = f"{freeze_prefix}holdin"
                        hold_output = f"{freeze_prefix}hold"
                        post_input = f"{freeze_prefix}postin"
                        post_output = f"{freeze_prefix}post"
                        pre_input = f"{freeze_prefix}prein"
                        pre_output = f"{freeze_prefix}pre"
                        # Keep a pre/post branch only when it contains at
                        # least one frame.  This also handles freeze-at-zero,
                        # freeze-at-end, and clips shorter than two frames.
                        if freeze_at <= frame_duration or clip_content_duration <= (2.0 * frame_duration):
                            filters.append(
                                ",".join(chain)
                                + f",split=2[{hold_input}][{post_input}]"
                            )
                            filters.append(
                                f"[{hold_input}]trim=start={base_start:.6f}:end={hold_end:.6f},"
                                f"select='eq(n,0)',setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={freeze_extra:.6f}[{hold_output}]"
                            )
                            filters.append(
                                f"[{post_input}]trim=start={base_start + freeze_at:.6f}:end={base_end:.6f},"
                                f"setpts=PTS-STARTPTS[{post_output}]"
                            )
                            chain = [
                                f"[{hold_output}][{post_output}]concat=n=2:v=1:a=0,"
                                f"setpts=PTS-STARTPTS+{start:.6f}/TB"
                            ]
                        elif freeze_at >= clip_content_duration - frame_duration:
                            filters.append(
                                ",".join(chain)
                                + f",split=2[{pre_input}][{hold_input}]"
                            )
                            filters.append(
                                f"[{pre_input}]trim=start={base_start:.6f}:end={base_start + freeze_at:.6f},"
                                f"setpts=PTS-STARTPTS[{pre_output}]"
                            )
                            filters.append(
                                f"[{hold_input}]trim=start={hold_start:.6f}:end={base_end:.6f},"
                                f"select='eq(n,0)',setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={freeze_extra:.6f}[{hold_output}]"
                            )
                            chain = [
                                f"[{pre_output}][{hold_output}]concat=n=2:v=1:a=0,"
                                f"setpts=PTS-STARTPTS+{start:.6f}/TB"
                            ]
                        else:
                            filters.append(
                                ",".join(chain)
                                + f",split=3[{pre_input}][{hold_input}][{post_input}]"
                            )
                            filters.append(
                                f"[{pre_input}]trim=start={base_start:.6f}:end={base_start + freeze_at:.6f},"
                                f"setpts=PTS-STARTPTS[{pre_output}]"
                            )
                            filters.append(
                                f"[{hold_input}]trim=start={hold_start:.6f}:end={hold_end:.6f},"
                                f"select='eq(n,0)',setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={freeze_extra:.6f}[{hold_output}]"
                            )
                            filters.append(
                                f"[{post_input}]trim=start={base_start + freeze_at:.6f}:end={base_end:.6f},"
                                f"setpts=PTS-STARTPTS[{post_output}]"
                            )
                            chain = [
                                f"[{pre_output}][{hold_output}][{post_output}]concat=n=3:v=1:a=0,"
                                f"setpts=PTS-STARTPTS+{start:.6f}/TB"
                            ]
                if transforms["scale"] != "1.00000000":
                    scale_expr = _expr_arg(f"max(2,iw*({transforms['scale']}))")
                    height_expr = _expr_arg(f"max(2,ih*({transforms['scale']}))")
                    chain.append(f"scale=w={scale_expr}:h={height_expr}:eval=frame")
                if transforms["rotation"] != "0.00000000":
                    rotation_expr = _expr_arg("(" + transforms["rotation"] + ")*PI/180")
                    chain.append(f"rotate={rotation_expr}:fillcolor=black@0")
                if transforms["opacity"] != "1.00000000":
                    alpha_expr = f"alpha(X,Y)*clip(({transforms['opacity']}),0,1)"
                    chain.extend(["format=gbrap", f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)}", "format=rgba"])
                chain.extend(
                    _effect_filters(
                        clip.get("effects"),
                        warnings,
                        str(clip.get("id")),
                        root=root,
                        clip=clip,
                        clip_start=start,
                        tps=tps,
                    )
                )
                if speed_segments and curve_duration is not None and abs(curve_duration - (src_out - src_in) / max(speed, 1e-9)) > 1e-6:
                    speed = max(0.01, (src_out - src_in) / max(1e-9, curve_duration))
                subtitle = _subtitle_filter(root, clip.get("subtitle"), warnings, str(clip.get("id")), start, max(0.001, curve_duration if curve_duration is not None else (src_out - src_in) / max(speed, 1e-9)), assets=assets)
                if subtitle:
                    chain.append(subtitle)
                mask_values: list[dict[str, Any]] = []
                inherited_masks = clip.get("_nested_parent_masks")
                if isinstance(inherited_masks, list):
                    mask_values.extend(item for item in inherited_masks if isinstance(item, dict))
                if isinstance(clip.get("mask"), dict):
                    mask_values.append(clip["mask"])
                for mask_value in mask_values:
                    mask_filter = _mask_filter(
                        mask_value,
                        warnings,
                        str(clip.get("id")),
                        clip=clip,
                        clip_start=start,
                        tps=tps,
                    )
                    if mask_filter:
                        chain.append("format=rgba")
                        chain.append(mask_filter)
                incoming = clip.get("transition_in") if isinstance(clip.get("transition_in"), dict) else {}
                outgoing = clip.get("transition_out") if isinstance(clip.get("transition_out"), dict) else {}
                if str(incoming.get("type", "")).lower() in {"fade", "fade_in", "dissolve"}:
                    chain.append(f"fade=t=in:st=0:d={max(0.001, _num(incoming.get('duration', 0.25), 0.25)):.6f}")
                if str(outgoing.get("type", "")).lower() in {"fade", "fade_out", "dissolve"}:
                    fade_duration = max(0.001, _num(outgoing.get("duration", 0.25), 0.25))
                    chain.append(f"fade=t=out:st={max(0.0, clip_content_duration + freeze_extra-fade_duration):.6f}:d={fade_duration:.6f}")
                filters.append(",".join(chain) + f"[{label}]")
                video_labels.append(label)
                overlay_x, overlay_y = _video_overlay_position(transforms, width, height)
                position_x_expr = _expr_arg(overlay_x)
                position_y_expr = _expr_arg(overlay_y)
                position = f"x={position_x_expr}:y={position_y_expr}"
                video_positions.append(position)
                video_specs.append({
                    "label": label,
                    "position": position,
                    "track_id": track.get("id"),
                    "track_order": int(track.get("order", 0)),
                    "layer_order": len(video_specs),
                    "clip_id": clip.get("id"),
                    "keyframes": copy.deepcopy(clip.get("keyframes", [])),
                    "start": start,
                    "duration": max(0.001, clip_content_duration + freeze_extra),
                    "incoming": incoming,
                    "outgoing": outgoing,
                    "blend": clip.get("blend"),
                })
                input_meta.append({"asset_id": asset["id"], "clip_id": clip.get("id"), "input": index, "kind": "video", "source_in_tick": int(clip.get("source_in_tick", 0)), "source_out_tick": int(clip.get("source_out_tick", 0))})
                index += 1
            elif kind in {"video", "audio"} and track.get("kind") == "audio":
                if not asset.get("probe", {}).get("audio", {}).get("codec"):
                    warnings.append({"code": "AUDIO_STREAM_MISSING", "clip_id": clip.get("id"), "message": "音频轨道引用的素材没有音频流，已跳过"})
                    continue
                inputs.extend(["-i", str(uri)])
                src_in = _sec(int(clip.get("source_in_tick", 0)), tps)
                src_out = _sec(int(clip.get("source_out_tick", clip.get("duration_tick", 1))), tps)
                start_ms = int(round(_sec(int(clip.get("timeline_start_tick", 0)), tps) * 1000))
                label = f"a{index}"
                speed = _num(clip.get("speed", 1.0), 1.0)
                if speed <= 0:
                    raise AppError("SPEED_INVALID", "speed 必须大于 0", exit_code=2, path=f"clips[{clip.get('id')}].speed")
                source_span_tick = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
                speed_segments = _speed_curve_segments(clip, source_span_tick, tps)
                curve_duration = speed_curve_duration_seconds(clip, source_span_tick, tps)
                if speed_segments:
                    audio_parts = _speed_curve_audio_parts(speed_segments)
                    split_labels = [f"asplit{index}_{part_index}" for part_index in range(len(audio_parts))]
                    filters.append(
                        f"[{index}:a]atrim=start={src_in:.6f}:end={src_out:.6f},asetpts=PTS-STARTPTS,aresample=48000,"
                        f"asplit={len(split_labels)}" + "".join(f"[{label}]" for label in split_labels)
                    )
                    part_labels: list[str] = []
                    previous_end_sample = 0
                    for part_index, (part_start, part_end, part_speed) in enumerate(audio_parts):
                        part_label = f"aspeed{index}_{part_index}"
                        part_labels.append(part_label)
                        part_end_sample = int(round(_speed_curve_elapsed_seconds(speed_segments, part_end) * 48000))
                        part_samples = max(1, part_end_sample - previous_end_sample)
                        previous_end_sample = part_end_sample
                        filters.append(
                            f"[{split_labels[part_index]}]atrim=start={part_start:.6f}:end={part_end:.6f},"
                            f"asetpts=PTS-STARTPTS,{_tempo_chain(part_speed)},apad=whole_len={part_samples},"
                            f"atrim=end_sample={part_samples},asetpts=N/SR/TB[{part_label}]"
                        )
                    speed_label = f"aspeed{index}"
                    concat_chain = "".join(f"[{label}]" for label in part_labels) + f"concat=n={len(part_labels)}:v=0:a=1"
                    if bool(clip.get("reverse")):
                        concat_chain += ",areverse"
                    filters.append(f"{concat_chain}[{speed_label}]")
                    audio_chain = [f"[{speed_label}]aresample=48000"]
                    warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "audio_speed_curve_piecewise", "message": "音频速度曲线按固定短段 atempo 近似，累计时长与视频曲线对齐；仍可能有段间相位边界"})
                else:
                    audio_chain = [f"[{index}:a]atrim=start={src_in:.6f}:end={src_out:.6f}", "asetpts=PTS-STARTPTS", "aresample=48000"]
                    if bool(clip.get("reverse")):
                        audio_chain.append("areverse")
                    if abs(speed - 1.0) > 1e-9:
                        audio_chain.append(_tempo_chain(speed))
                audio_settings = clip.get("audio") if isinstance(clip.get("audio"), dict) else {}
                freeze = clip.get("freeze") if isinstance(clip.get("freeze"), dict) else None
                freeze_audio_mode = str(freeze.get("audio_mode", "silence")).lower() if freeze else "silence"
                freeze_duration = max(0.0, _sec(int(freeze.get("duration_tick", 0)), tps)) if freeze else 0.0
                content_duration = max(
                    0.001,
                    curve_duration if curve_duration is not None else (src_out - src_in) / max(speed, 1e-9),
                )
                audio_keyframe_time = "t"
                if freeze_duration > 0 and freeze_audio_mode == "silence":
                    freeze_at = max(0.0, min(content_duration, _sec(int(freeze.get("at_tick", int(round(content_duration * tps)))), tps)))
                    audio_chain = _insert_audio_freeze(filters, audio_chain, f"afreeze{index}", content_duration, freeze_at, freeze_duration)
                    # Audio automation is authored against the pre-freeze
                    # clip clock. During the inserted silence, hold the value
                    # at the freeze point; after it, subtract the insertion
                    # so later keyframes keep their authored positions.
                    audio_keyframe_time = (
                        f"if(lt(t,{freeze_at:.8f}),t,"
                        f"if(lt(t,{freeze_at + freeze_duration:.8f}),{freeze_at:.8f},"
                        f"t-{freeze_duration:.8f}))"
                    )
                elif freeze_duration > 0:
                    audio_chain.append(f"apad=pad_dur={freeze_duration:.6f}")
                volume = _num(audio_settings.get("volume", clip.get("volume", 1.0)), 1.0)
                volume_expr = _keyframe_expr(clip, ("audio.volume", "volume"), volume, 0.0, tps, time_variable=audio_keyframe_time)
                if volume_expr != f"{volume:.8f}" or abs(volume - 1.0) > 1e-9:
                    audio_chain.append(f"volume=volume={_expr_arg(volume_expr)}:eval=frame")
                if audio_settings.get("noise_reduction") or audio_settings.get("denoise"):
                    reduction = _num(audio_settings.get("noise_reduction", audio_settings.get("denoise", -25)), -25)
                    audio_chain.append(f"afftdn=nf={reduction:.2f}")
                if audio_settings.get("compressor"):
                    compressor = audio_settings.get("compressor") if isinstance(audio_settings.get("compressor"), dict) else {}
                    audio_chain.append(
                        "acompressor="
                        f"threshold={_num(compressor.get('threshold', 0.125), 0.125):.6f}:"
                        f"ratio={max(1.0, _num(compressor.get('ratio', 2.0), 2.0)):.6f}:"
                        f"attack={max(0.01, _num(compressor.get('attack', 20), 20)):.3f}:"
                        f"release={max(1.0, _num(compressor.get('release', 250), 250)):.3f}"
                    )
                equalizer = audio_settings.get("equalizer", audio_settings.get("eq"))
                if isinstance(equalizer, dict):
                    frequency = max(20.0, min(20000.0, _num(equalizer.get("frequency", equalizer.get("f", 1000)), 1000)))
                    gain = max(-24.0, min(24.0, _num(equalizer.get("gain", equalizer.get("g", 0)), 0)))
                    bandwidth = max(0.05, min(10.0, _num(equalizer.get("width", equalizer.get("w", 1)), 1)))
                    audio_chain.append(f"equalizer=f={frequency:.3f}:t=q:w={bandwidth:.4f}:g={gain:.4f}")
                if audio_settings.get("highpass"):
                    audio_chain.append(f"highpass=f={max(20.0, min(20000.0, _num(audio_settings.get('highpass'), 80))):.3f}")
                if audio_settings.get("lowpass"):
                    audio_chain.append(f"lowpass=f={max(20.0, min(20000.0, _num(audio_settings.get('lowpass'), 16000))):.3f}")
                if audio_settings.get("dialogue_enhance") or audio_settings.get("voice_enhance"):
                    audio_chain.append("dialoguenhance")
                pitch = audio_settings.get("pitch_semitones")
                if pitch is not None and abs(_num(pitch, 0)) > 1e-6:
                    semitones = max(-24.0, min(24.0, _num(pitch, 0)))
                    audio_chain.append(f"rubberband=pitch={2 ** (semitones / 12.0):.8f}")
                reverb = audio_settings.get("reverb")
                if isinstance(reverb, dict):
                    in_gain = max(0.0, min(1.0, _num(reverb.get("in_gain", 0.8), 0.8)))
                    out_gain = max(0.0, min(1.0, _num(reverb.get("out_gain", 0.9), 0.9)))
                    delays = str(reverb.get("delays", "60|90"))
                    decays = str(reverb.get("decays", "0.25|0.15"))
                    audio_chain.append(f"aecho={in_gain:.4f}:{out_gain:.4f}:{delays}:{decays}")
                loudnorm = audio_settings.get("loudnorm")
                if isinstance(loudnorm, dict):
                    integrated = _num(loudnorm.get("i", loudnorm.get("integrated", -16)), -16)
                    true_peak = _num(loudnorm.get("tp", loudnorm.get("true_peak", -1.5)), -1.5)
                    loudness_range = _num(loudnorm.get("lra", 11), 11)
                    audio_chain.append(f"loudnorm=I={integrated:.3f}:TP={true_peak:.3f}:LRA={max(1.0, loudness_range):.3f}")
                pan = audio_settings.get("pan")
                raw_pan_expression = False
                if isinstance(pan, str) and pan.strip():
                    try:
                        float(pan)
                    except (TypeError, ValueError):
                        raw_pan_expression = True
                if raw_pan_expression:
                    audio_chain.append(f"pan={pan.strip()}")
                else:
                    # Numeric pan is normalized to -1 (left) .. +1 (right).
                    # Normalize every source to stereo, then apply a frame-
                    # evaluated balance expression. This duplicates mono
                    # sources but preserves independent left/right channels
                    # for stereo assets instead of collapsing them to mono.
                    raw_pan = pan if pan is not None else clip.get("pan", 0.0)
                    try:
                        pan_value = float(raw_pan)
                    except (TypeError, ValueError):
                        pan_value = 0.0
                    pan_tracks = [
                        item for item in clip.get("keyframes", [])
                        if isinstance(item, dict) and str(item.get("property", "")) in {"audio.pan", "pan"}
                    ]
                    if pan_tracks or abs(pan_value) > 1e-9:
                        pan_expr = _keyframe_expr(clip, ("audio.pan", "pan"), pan_value, 0.0, tps, time_variable=audio_keyframe_time)
                        pan_expr = f"clip(({pan_expr}),-1,1)"
                        left_expr = f"val(0)*(1-max(({pan_expr}),0))"
                        right_expr = f"val(1)*(1+min(({pan_expr}),0))"
                        audio_chain.extend([
                            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
                            f"aeval=exprs={_expr_arg(left_expr + '|' + right_expr)}:c=stereo",
                            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
                        ])
                track_volume_raw = track_audio.get("volume")
                if track_volume_raw is not None:
                    track_volume = max(0.0, min(4.0, _num(track_volume_raw, 1.0)))
                    if abs(track_volume - 1.0) > 1e-9:
                        audio_chain.append(f"volume=volume={track_volume:.6f}")
                track_pan_raw = track_audio.get("pan")
                if track_pan_raw is not None:
                    try:
                        track_pan_value = float(track_pan_raw)
                    except (TypeError, ValueError):
                        track_pan_value = math.nan
                    if isinstance(track_pan_raw, bool) or not math.isfinite(track_pan_value) or not -1.0 <= track_pan_value <= 1.0:
                        warnings.append({"code": "AUDIO_TRACK_PAN_INVALID", "clip_id": clip.get("id"), "track_id": track_id, "feature": "track_audio.pan", "message": "音频轨道 pan 必须是 -1..1 的有限数字，已忽略"})
                    elif abs(track_pan_value) > 1e-9:
                        track_pan_expr = f"clip({track_pan_value:.8f},-1,1)"
                        left_expr = f"val(0)*(1-max(({track_pan_expr}),0))"
                        right_expr = f"val(1)*(1+min(({track_pan_expr}),0))"
                        audio_chain.extend([
                            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
                            f"aeval=exprs={_expr_arg(left_expr + '|' + right_expr)}:c=stereo",
                            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
                        ])
                fade_in = audio_settings.get("fade_in")
                if fade_in:
                    audio_chain.append(f"afade=t=in:st=0:d={max(0.001, _num(fade_in, 0.25)):.6f}")
                fade_out = audio_settings.get("fade_out")
                if fade_out:
                    fade_duration = max(0.001, _num(fade_out, 0.25))
                    clip_seconds = content_duration + freeze_duration
                    audio_chain.append(f"afade=t=out:st={max(0.0, clip_seconds-fade_duration):.6f}:d={fade_duration:.6f}")
                audio_chain.append(f"adelay={start_ms}|{start_ms}")
                filters.append(",".join(audio_chain) + f"[{label}]")
                audio_labels.append(label)
                role = str(audio_settings.get("role", track_audio.get("role", track.get("role", "other")))).lower()
                if role in {"voice", "dialogue", "narration", "speech"}:
                    voice_audio_labels.append(label)
                elif role in {"music", "bgm", "background"}:
                    music_audio_labels.append(label)
                    if audio_settings.get("duck_under_voice") or isinstance(audio_settings.get("ducking"), dict) or track_audio.get("duck_under_voice") or track.get("duck_under_voice"):
                        ducking_requested = True
                else:
                    other_audio_labels.append(label)
                input_meta.append({"asset_id": asset["id"], "clip_id": clip.get("id"), "track_id": track_id, "input": index, "kind": "audio", "source_in_tick": int(clip.get("source_in_tick", 0)), "source_out_tick": int(clip.get("source_out_tick", 0))})
                index += 1
    if not video_labels and not subtitle_overlays:
        raise AppError("VIDEO_TRACK_EMPTY", "没有可渲染的视频片段或独立文字轨道", exit_code=2, path="sequences[].tracks")
    base_filter = f"color=c=black@0.0:s={width}x{height}:r={fps_value}:d={duration:.6f},format=rgba" if transparent_canvas else f"color=c=black:s={width}x{height}:r={fps_value}:d={duration:.6f}"
    filters.append(f"{base_filter}[base]")
    subtitle_specs = [
        _build_subtitle_layer(
            root,
            overlay,
            subtitle_index,
            filters,
            warnings,
            width=width,
            height=height,
            fps_value=fps_value,
            duration=duration,
            tps=tps,
        )
        for subtitle_index, overlay in enumerate(subtitle_overlays)
    ]
    final_specs: list[dict[str, Any]] = []
    by_track: dict[str, list[dict[str, Any]]] = {}
    for spec in video_specs:
        by_track.setdefault(str(spec.get("track_id")), []).append(spec)
    complex_types = (XFADE_TRANSITIONS - {"fade"}) | {"crossfade", "dissolve", "wipe", "slide"}
    for track_specs in by_track.values():
        track_specs.sort(key=lambda item: (float(item["start"]), str(item.get("clip_id"))))
        index = 0
        while index < len(track_specs):
            current_spec = track_specs[index]
            next_spec = track_specs[index + 1] if index + 1 < len(track_specs) else None
            incoming_transition = next_spec.get("incoming") if next_spec and isinstance(next_spec.get("incoming"), dict) else {}
            outgoing_transition = current_spec.get("outgoing") if isinstance(current_spec.get("outgoing"), dict) else {}
            transition = incoming_transition if str(incoming_transition.get("type", "")) else outgoing_transition
            transition_type = str(transition.get("type", "")).lower()
            if next_spec and transition_type in complex_types:
                transition_duration = max(0.001, _num(transition.get("duration", 0.25), 0.25))
                expected_start = float(current_spec["start"]) + float(current_spec["duration"]) - transition_duration
                frame_tolerance = max(1.0 / max(1, int(fps["num"])), 0.01)
                overlap_handles = abs(float(next_spec["start"]) - expected_start) <= frame_tolerance
                contiguous = abs(float(next_spec["start"]) - (float(current_spec["start"]) + float(current_spec["duration"]))) <= frame_tolerance
                auto_handle = bool(transition.get("auto_handle", False)) or str(transition.get("handle_policy", "")).lower() == "auto"
                if transition_duration < float(current_spec["duration"]) and transition_duration < float(next_spec["duration"]) and (overlap_handles or (auto_handle and contiguous)):
                    left_trim = f"tr{len(final_specs)}a"
                    right_trim = f"tr{len(final_specs)}b"
                    output_label = f"transition{len(final_specs)}"
                    filters.append(f"[{current_spec['label']}]trim=start={float(current_spec['start']):.6f}:end={float(current_spec['start']) + float(current_spec['duration']):.6f},setpts=PTS-STARTPTS[{left_trim}]")
                    filters.append(f"[{next_spec['label']}]trim=start={float(next_spec['start']):.6f}:end={float(next_spec['start']) + float(next_spec['duration']):.6f},setpts=PTS-STARTPTS[{right_trim}]")
                    direction = str(transition.get("direction", "left")).lower()
                    transition_name = {"crossfade": "fade", "dissolve": "fade"}.get(transition_type, transition_type)
                    if transition_type == "wipe":
                        transition_name = {"left": "wipeleft", "right": "wiperight", "up": "wipeup", "down": "wipedown"}.get(direction, "wipeleft")
                    elif transition_type == "slide":
                        transition_name = {"left": "slideleft", "right": "slideright", "up": "slideup", "down": "slidedown"}.get(direction, "slideright")
                    if transition_name not in XFADE_TRANSITIONS:
                        transition_name = "fade"
                    preserve_contiguous_duration = auto_handle and contiguous and not overlap_handles
                    tail_padding = f",tpad=stop_mode=clone:stop_duration={transition_duration:.6f}" if preserve_contiguous_duration else ""
                    filters.append(f"[{left_trim}][{right_trim}]xfade=transition={transition_name}:duration={transition_duration:.6f}:offset={float(current_spec['duration']) - transition_duration:.6f}{tail_padding},setpts=PTS-STARTPTS+{float(current_spec['start']):.6f}/TB[{output_label}]")
                    if preserve_contiguous_duration:
                        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": next_spec.get("clip_id"), "feature": "complex_transition_auto_handle", "message": "相邻片段没有重叠句柄，已用本地 xfade 并保持原时间线长度；转场尾部使用最后一帧填充"})
                    final_specs.append({"label": output_label, "position": current_spec["position"], "track_id": current_spec.get("track_id"), "track_order": current_spec.get("track_order", 0), "layer_order": current_spec.get("layer_order", len(final_specs)), "clip_id": f"{current_spec.get('clip_id')}+{next_spec.get('clip_id')}", "start": current_spec["start"], "duration": float(current_spec["duration"]) + float(next_spec["duration"]) if preserve_contiguous_duration else float(current_spec["duration"]) + float(next_spec["duration"]) - transition_duration})
                    index += 2
                    continue
                warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": next_spec.get("clip_id"), "feature": "complex_transition", "message": "复杂转场要求相邻片段有匹配的重叠时间句柄，当前已保留但未执行"})
            elif transition_type in complex_types:
                warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": current_spec.get("clip_id"), "feature": "complex_transition", "message": "没有可配对的相邻片段，复杂转场未执行"})
            final_specs.append(current_spec)
            index += 1
    final_specs.extend(subtitle_specs)
    # Video transitions are resolved per track above; this final ordering is
    # the shared z-order for media and independent text layers.
    final_specs.sort(key=lambda item: (int(item.get("track_order", 0)), float(item.get("start", 0.0)), int(item.get("layer_order", 0))))
    current = "base"
    for pos, spec in enumerate(final_specs):
        target = "vout" if pos == len(final_specs) - 1 and not has_adjustments else f"vo{pos}"
        blend = spec.get("blend") if isinstance(spec.get("blend"), dict) else {}
        blend_mode = str(blend.get("mode", "normal")).lower().replace("-", "_")
        if blend_mode in {"normal", "source_over", ""}:
            opacity = _clamp(blend.get("opacity", 1.0), 0.0, 1.0, 1.0)
            blend_opacity_expr = _keyframe_expr(
                {"keyframes": spec.get("keyframes", [])}, ("blend.opacity", "blend_opacity"),
                opacity, float(spec.get("start", 0.0)), tps, time_variable="T",
            )
            source_label = spec['label']
            if blend_opacity_expr != "1.00000000":
                source_label = f"normalopacity{pos}"
                alpha_expr = f"alpha(X,Y)*clip(({blend_opacity_expr}),0,1)"
                filters.append(f"[{spec['label']}]format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)},format=rgba[{source_label}]")
            filters.append(f"[{current}][{source_label}]overlay={spec['position']}:eof_action=pass:format=auto[{target}]")
        elif blend_mode in {"addition", "addition128", "and", "average", "burn", "darken", "difference", "divide", "dodge", "exclusion", "freeze", "glow", "hardlight", "hard_mix", "lighten", "multiply", "negation", "or", "phoenix", "pinlight", "reflect", "screen", "softlight", "subtract", "vivid", "xor"}:
            # FFmpeg's blend filter requires two same-sized frames and has no
            # notion of the clip's timeline position or alpha coverage.  Build
            # a transparent, positioned canvas first, then use its alpha as a
            # masked merge so pixels outside the layer remain untouched.  This
            # keeps multiply/screen/etc. consistent with source-over behavior.
            opacity = _clamp(blend.get("opacity", 1.0), 0.0, 1.0, 1.0)
            ffmpeg_mode = {"hard_mix": "hardmix", "vivid": "vividlight"}.get(blend_mode, blend_mode)
            layer_prefix = "subtitle_" if spec.get("kind") == "subtitle" else ""
            blend_index = int(spec.get("layer_order", pos)) if spec.get("kind") == "subtitle" else pos
            blend_canvas = f"{layer_prefix}blendcanvas{blend_index}"
            blend_source = f"{layer_prefix}blendsource{blend_index}"
            blend_layer = f"{layer_prefix}blendlayer{blend_index}"
            blend_base = f"{layer_prefix}blendbase{blend_index}"
            blend_under = f"{layer_prefix}blendunder{blend_index}"
            blend_result = f"{layer_prefix}blendresult{blend_index}"
            blend_alpha = f"{layer_prefix}blendalpha{blend_index}"
            blend_color_layer = f"{layer_prefix}blendcolor{blend_index}"
            blend_mask_layer = f"{layer_prefix}blendmask{blend_index}"
            filters.append(f"color=c=black@0.0:s={width}x{height}:r={fps_value}:d={duration:.6f},format=rgba[{blend_canvas}]")
            filters.append(f"[{spec['label']}]format=rgba[{blend_source}]")
            filters.append(f"[{blend_canvas}][{blend_source}]overlay={spec['position']}:eof_action=pass:format=auto,format=rgba[{blend_layer}]")
            blend_opacity_expr = _keyframe_expr(
                {"keyframes": spec.get("keyframes", [])},
                ("blend.opacity", "blend_opacity"),
                opacity,
                float(spec.get("start", 0.0)),
                tps,
                time_variable="T",
            )
            dynamic_blend_opacity = any(
                isinstance(item, dict) and str(item.get("property", "")) in {"blend.opacity", "blend_opacity"}
                for item in spec.get("keyframes", [])
            )
            if dynamic_blend_opacity:
                alpha_expr = f"alpha(X,Y)*clip(({blend_opacity_expr}),0,1)"
                filters.append(f"[{blend_layer}]format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)},format=rgba[{blend_layer}o]")
                blend_layer = f"{blend_layer}o"
            elif opacity < 1.0:
                filters.append(f"[{blend_layer}]colorchannelmixer=aa={opacity:.6f}[{blend_layer}o]")
                blend_layer = f"{blend_layer}o"
            # Keep independent pixel-format negotiations for the blend math
            # and alpha mask; otherwise FFmpeg may negotiate the shared stream
            # to a non-alpha format before alphaextract sees it.
            filters.append(f"[{blend_layer}]split=2[{blend_color_layer}][{blend_mask_layer}]")
            filters.append(f"[{current}]split=2[{blend_base}][{blend_under}]")
            filters.append(f"[{blend_base}]format=gbrp[{blend_base}r]")
            filters.append(f"[{blend_under}]format=gbrp[{blend_under}r]")
            filters.append(f"[{blend_color_layer}]format=gbrp[{blend_color_layer}r]")
            filters.append(f"[{blend_base}r][{blend_color_layer}r]blend=all_mode={ffmpeg_mode}:all_opacity=1[{blend_result}]")
            # All three maskedmerge inputs must share the RGB plane format.
            # A gray alpha plane alone would otherwise negotiate the entire
            # merge to grayscale and discard the composite's color channels.
            filters.append(f"[{blend_mask_layer}]format=rgba,alphaextract,format=gbrp[{blend_alpha}]")
            filters.append(f"[{blend_under}r][{blend_result}][{blend_alpha}]maskedmerge[{target}]")
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": spec.get("clip_id"), "feature": f"blend:{blend_mode}", "message": "当前 FFmpeg 后端不支持该混合模式，已回退 source-over"})
            filters.append(f"[{current}][{spec['label']}]overlay={spec['position']}:eof_action=pass:format=auto[{target}]")
        current = target
    if has_adjustments:
        for adjustment_index, (adjustment_id, effects, adjustment_start, adjustment_end) in enumerate(adjustment_layers):
            effect_clip = {"id": adjustment_id, "effects": effects}
            effect_filters = _effect_filters(
                effects,
                warnings,
                adjustment_id,
                root=root,
                clip=effect_clip,
                clip_start=0.0,
                tps=tps,
            )
            if not effect_filters:
                continue
            target = f"adjusted{adjustment_index}"
            if adjustment_start <= 1e-9 and adjustment_end >= duration - 1e-9:
                filters.append(f"[{current}]" + ",".join(effect_filters) + f"[{target}]")
                current = target
                continue
            segment_labels: list[str] = []
            if adjustment_start > 1e-9:
                pre = f"adjustment{adjustment_index}pre"
                filters.append(f"[{current}]trim=start=0:end={adjustment_start:.6f},setpts=PTS-STARTPTS,format=rgba[{pre}]")
                segment_labels.append(pre)
            mid_input = f"adjustment{adjustment_index}midin"
            mid = f"adjustment{adjustment_index}mid"
            filters.append(f"[{current}]trim=start={adjustment_start:.6f}:end={adjustment_end:.6f},setpts=PTS-STARTPTS,format=rgba[{mid_input}]")
            filters.append(f"[{mid_input}]" + ",".join(effect_filters) + f",format=rgba[{mid}]")
            segment_labels.append(mid)
            if adjustment_end < duration - 1e-9:
                post = f"adjustment{adjustment_index}post"
                filters.append(f"[{current}]trim=start={adjustment_end:.6f}:end={duration:.6f},setpts=PTS-STARTPTS,format=rgba[{post}]")
                segment_labels.append(post)
            filters.append("".join(f"[{label}]" for label in segment_labels) + f"concat=n={len(segment_labels)}:v=1:a=0,format=rgba,setpts=PTS-STARTPTS[{target}]")
            current = target
        adjusted_output = "vout"
        filters.append(f"[{current}]" + ("format=rgba," if transparent_canvas else "") + f"null[{adjusted_output}]")
        current = adjusted_output

    if audio_labels:
        mix_labels = list(audio_labels)
        if ducking_requested and voice_audio_labels and music_audio_labels:
            voice_bus = "voicebus"
            filters.append(f"{''.join(f'[{item}]' for item in voice_audio_labels)}amix=inputs={len(voice_audio_labels)}:duration=longest:dropout_transition=0,aresample=48000[{voice_bus}]")
            ducked_labels: list[str] = []
            for duck_index, label in enumerate(music_audio_labels):
                ducked = f"duck{duck_index}"
                filters.append(f"[{label}][{voice_bus}]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300:makeup=1[{ducked}]")
                ducked_labels.append(ducked)
            mix_labels = voice_audio_labels + ducked_labels + other_audio_labels
            warnings.append({"code": "AUDIO_DUCKING_APPLIED", "message": "已使用本地 FFmpeg sidechaincompress 对背景音乐做旁白闪避"})
        filters.append(f"{''.join(f'[{item}]' for item in mix_labels)}amix=inputs={len(mix_labels)}:duration=longest:dropout_transition=0,aresample=48000[aout]")
    else:
        filters.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={duration:.6f}[aout]")
    return inputs, ";".join(filters), input_meta, warnings


def render_project(
    root: Path,
    project: dict[str, Any],
    sequence: dict[str, Any],
    output: Path,
    *,
    dry_run: bool = False,
    render_settings: dict[str, Any] | None = None,
    profile: str | None = None,
    cancel_file: Path | None = None,
    progress_callback: Callable[[str, str, float | None, str], None] | None = None,
    resume_of: str | None = None,
) -> dict[str, Any]:
    effective_project = project
    if render_settings is not None:
        effective_project = dict(project)
        effective_project["settings"] = render_settings
    encoder = output_settings(effective_project["settings"])
    inputs, graph, input_meta, warnings = build_filter_graph(root, effective_project, sequence)
    fingerprints = render_fingerprints(project, sequence, effective_project["settings"], root)
    output.parent.mkdir(parents=True, exist_ok=True)
    operation_id = new_id("render")
    temp_dir = root / "renders" / ".tmp" / operation_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_output = temp_dir / output.name
    progress_file = temp_dir / "ffmpeg-progress.log"
    container = encoder["container"]
    video_encoder = encoder["video"]
    audio_encoder = encoder["audio"]
    args = [
        ffmpeg_path(), "-hide_banner", "-y", "-loglevel", "error",
        "-progress", str(progress_file),
        *inputs, "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
        "-t", f"{max(int(sequence.get('duration_tick', 1)), 1) / int(project['settings']['timebase']['ticks_per_second']):.6f}",
        "-c:v", str(video_encoder["codec"]),
    ]
    if str(video_encoder.get("codec")) in {"libx264", "libx265"}:
        args.extend(["-preset", str(video_encoder.get("preset", "medium"))])
    if video_encoder.get("bitrate"):
        args.extend(["-b:v", str(video_encoder["bitrate"])])
    else:
        args.extend(["-crf", str(video_encoder.get("crf", 18))])
    if str(video_encoder.get("codec")) in {"libvpx-vp9", "libvpx"} and not video_encoder.get("bitrate"):
        args.extend(["-b:v", "0"])
    args.extend(["-pix_fmt", str(video_encoder.get("pixel_format", "yuv420p"))])
    args.extend(_output_color_args(effective_project["settings"]))
    args.extend(["-c:a", str(audio_encoder["codec"])])
    if str(audio_encoder.get("codec")) not in {"pcm_s16le", "pcm_s24le", "pcm_s32le"}:
        args.extend(["-b:a", str(audio_encoder.get("bitrate", "192k"))])
    if container == "mp4":
        args.extend(["-movflags", "+faststart"])
    args.extend(["-f", OUTPUT_CONTAINERS[container], str(temp_output)])
    plan = {"operation_id": operation_id, "command": args, "filter_complex": graph, "inputs": input_meta, "output": str(output), "encoder": encoder, "warnings": warnings, **fingerprints, "resume_of": resume_of}
    if dry_run:
        if progress_callback:
            progress_callback(operation_id, "planned", 0.0, "渲染计划已生成")
        return {"status": "planned", "plan": plan}
    if progress_callback:
        progress_callback(operation_id, "render_started", 0.0, "FFmpeg 渲染开始")
    progress_stop = threading.Event()
    expected_seconds = max(0.001, int(sequence.get("duration_tick", 1)) / int(effective_project["settings"]["timebase"]["ticks_per_second"]))

    def watch_progress() -> None:
        last_percent = -1.0
        while not progress_stop.is_set():
            try:
                raw = progress_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                raw = ""
            values: dict[str, str] = {}
            for line in raw.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
            if values.get("out_time_ms"):
                try:
                    percent = max(0.0, min(100.0, float(values["out_time_ms"]) / 1_000_000.0 / expected_seconds * 100.0))
                except (TypeError, ValueError):
                    percent = None
                if percent is not None and percent - last_percent >= 1.0:
                    last_percent = percent
                    if progress_callback:
                        try:
                            progress_callback(operation_id, "render_progress", round(percent, 2), "FFmpeg 渲染进行中")
                        except Exception:
                            pass
            if values.get("progress") == "end" and progress_callback:
                try:
                    progress_callback(operation_id, "render_progress", 100.0, "FFmpeg 已完成编码")
                except Exception:
                    pass
            progress_stop.wait(0.2)

    progress_thread = threading.Thread(target=watch_progress, name="ai-ad-editor-render-progress", daemon=True)
    progress_thread.start()
    try:
        if cancel_file is not None and cancel_file.exists():
            raise AppError("CANCELLED", "任务在启动前已被取消", exit_code=8, path=str(cancel_file), retryable=False)
        result = run_process(args, timeout=3600, cwd=root, cancel_file=cancel_file)
        if result.returncode != 0:
            raise AppError("RENDER_FAILED", "FFmpeg 渲染失败", exit_code=6, retryable=True, cause=result.stderr[-6000:])
        if not temp_output.exists() or temp_output.stat().st_size == 0:
            raise AppError("RENDER_EMPTY", "FFmpeg 未生成有效输出", exit_code=6)
        inspected = probe_media(temp_output)
        quality = check_output(temp_output, effective_project["settings"], _sec(_tick(sequence.get("duration_tick"), 1), int(effective_project["settings"]["timebase"]["ticks_per_second"])), run_expensive=False)
        if not quality["ok"]:
            raise AppError("RENDER_QUALITY_FAILED", "输出未通过结构质量检查", exit_code=6, cause=str(quality["errors"]))
        os.replace(temp_output, output)
        manifest = {
            "manifest_version": "0.1.0",
            "operation_id": operation_id,
            "project_id": project["project"]["id"],
            "sequence_id": sequence["id"],
            "output": str(output),
            "sha256": sha256_file(output),
            "probe": inspected,
            "command": args,
            "inputs": input_meta,
            "profile": profile,
            "settings": effective_project["settings"],
            "warnings": warnings,
            "quality": quality,
            **fingerprints,
            "resume_of": resume_of,
        }
        manifest_path = output.with_suffix(output.suffix + ".manifest.json")
        atomic_write_json(manifest_path, manifest)
        if progress_callback:
            progress_callback(operation_id, "artifact_written", 100.0, "渲染产物和 manifest 已写入")
            progress_callback(operation_id, "completed", 100.0, "渲染完成")
        return {"status": "succeeded", "operation_id": operation_id, "path": str(output), "manifest": str(manifest_path), "profile": profile, "settings": effective_project["settings"], "probe": inspected, "warnings": warnings + quality.get("warnings", []), "quality": quality, **fingerprints, "resume_of": resume_of}
    except AppError as exc:
        # Make the persisted operation discoverable from the CLI error envelope so
        # callers can invoke `render --resume <operation_id>` without scanning files.
        exc.operation_id = operation_id
        if progress_callback:
            progress_callback(operation_id, "cancelled" if exc.code == "CANCELLED" else "failed", None, "渲染已取消" if exc.code == "CANCELLED" else "渲染失败")
        atomic_write_json(
            root / "operations" / f"{operation_id}.json",
            {
                "operation_id": operation_id,
                "command": "render",
                "status": "cancelled" if exc.code == "CANCELLED" else "failed",
                "output": str(output),
                "profile": profile,
                "project_id": project["project"]["id"],
                "sequence_id": sequence["id"],
                "settings": effective_project["settings"],
                "error": exc.as_dict(),
                "plan": plan,
                **fingerprints,
                "resume_of": resume_of,
                "created_at": now_iso(),
            },
        )
        raise
    finally:
        progress_stop.set()
        progress_thread.join(timeout=2)
        try:
            for child in temp_dir.glob("*"):
                child.unlink(missing_ok=True)
            temp_dir.rmdir()
            temp_dir.parent.rmdir() if not any(temp_dir.parent.iterdir()) else None
        except OSError:
            pass

