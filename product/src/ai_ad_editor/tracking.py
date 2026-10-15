from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .errors import AppError, dependency_error
from .media import ffmpeg_path, probe_media
from .utils import run_process, sha256_file


OBJECT_TRACKING_PROTOCOL = "agent-video-object-tracking-v1"
OBJECT_TRACKING_ENGINE = "command-json-tracking-v1"
OBJECT_TRACKING_OUTPUT_CONTRACT = "tracking_frames_v1"


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


def _tracking_runner_command(executable: Path) -> list[str]:
    """Build an argv-only command for a registered local tracking runner."""
    suffix = executable.suffix.lower()
    if suffix in {".cmd", ".bat", ".ps1", ".psm1", ".vbs", ".wsf", ".sh", ".bash", ".zsh"}:
        raise AppError("MODEL_EXECUTABLE_UNSAFE", "command-json-tracking-v1 不允许 shell/script wrapper", exit_code=10, path=str(executable))
    if suffix == ".py":
        return [sys.executable, str(executable)]
    return [str(executable)]


def _tracking_frame_error(message: str, *, index: int, path: str) -> AppError:
    return AppError("TRACKING_RUNNER_OUTPUT_INVALID", f"第 {index} 个跟踪帧无效: {message}", exit_code=6, path=path)


def track_command_json(
    source: Path,
    roi: str | dict[str, Any] | list[float] | tuple[float, ...],
    *,
    adapter_id: str,
    model_path: str | Path,
    executable: str | Path,
    model_sha256: str | None = None,
    executable_sha256: str | None = None,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    step_frames: int = 4,
    max_width: int = 640,
    max_samples: int = 600,
    ticks_per_second: int = 90_000,
    timeout: int = 1800,
) -> dict[str, Any]:
    """Run a registered local visual model through the strict JSON protocol.

    The runner receives one JSON request on stdin and must return one JSON
    object on stdout.  No shell is involved, and only normalized bounding
    boxes are accepted back into the project timeline.
    """
    if not source.exists() or not source.is_file():
        raise AppError("TRACK_SOURCE_MISSING", f"跟踪输入不存在: {source}", exit_code=3, path=str(source))
    model = Path(model_path).expanduser().resolve()
    runner = Path(executable).expanduser().resolve()
    if not model.exists():
        raise AppError("MODEL_PATH_MISSING", f"本地视觉模型不存在: {model}", exit_code=10, path=str(model))
    if not runner.exists() or not runner.is_file():
        raise AppError("MODEL_EXECUTABLE_MISSING", f"本地视觉适配器 executable 不存在: {runner}", exit_code=10, path=str(runner))
    roi_values = _parse_roi(roi)
    try:
        start_seconds = float(start_seconds)
        end_seconds = None if end_seconds is None else float(end_seconds)
    except (TypeError, ValueError) as exc:
        raise AppError("TRACK_RANGE_INVALID", "跟踪时间范围必须是数字", exit_code=2, path="range") from exc
    if not math.isfinite(start_seconds) or start_seconds < 0:
        raise AppError("TRACK_RANGE_INVALID", "start_seconds 必须是非负有限数字", exit_code=2, path="start_seconds")
    if end_seconds is not None and (not math.isfinite(end_seconds) or end_seconds <= start_seconds):
        raise AppError("TRACK_RANGE_INVALID", "end_seconds 必须大于 start_seconds", exit_code=2, path="end_seconds")
    step_frames = max(1, int(step_frames))
    max_width = max(160, min(4096, int(max_width)))
    max_samples = max(1, min(20_000, int(max_samples)))
    ticks_per_second = max(1, int(ticks_per_second))
    source_sha256 = f"sha256:{sha256_file(source)}"
    if not model_sha256:
        if model.is_file():
            model_sha256 = f"sha256:{sha256_file(model)}"
        else:
            raise AppError("MODEL_HASH_REQUIRED", "视觉 runner 需要已登记的模型目录哈希", exit_code=10, path=str(model))
    if not executable_sha256:
        executable_sha256 = f"sha256:{sha256_file(runner)}"
    request = {
        "protocol": OBJECT_TRACKING_PROTOCOL,
        "status": "request",
        "adapter_id": str(adapter_id),
        "engine": OBJECT_TRACKING_ENGINE,
        "network": "disabled",
        "source": {"path": str(source), "sha256": source_sha256},
        "model": {"path": str(model), "sha256": model_sha256},
        "runner": {"path": str(runner), "sha256": executable_sha256},
        "roi": {"x": roi_values[0], "y": roi_values[1], "width": roi_values[2], "height": roi_values[3]},
        "range": {"start_seconds": start_seconds, "end_seconds": end_seconds, "step_frames": step_frames},
        "limits": {"max_width": max_width, "max_samples": max_samples},
        "ticks_per_second": ticks_per_second,
        "output_contract": OBJECT_TRACKING_OUTPUT_CONTRACT,
    }
    try:
        completed = subprocess.run(
            _tracking_runner_command(runner),
            input=json.dumps(request, ensure_ascii=False) + "\n",
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=max(1, int(timeout)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError("TRACKING_RUNNER_TIMEOUT", "本地视觉 runner 超时", exit_code=6, retryable=True, path=str(runner), cause=str(exc)) from exc
    except OSError as exc:
        raise AppError("TRACKING_RUNNER_START_FAILED", f"无法启动本地视觉 runner: {runner}", exit_code=10, path=str(runner), cause=str(exc)) from exc
    if completed.returncode != 0:
        raise AppError("TRACKING_RUNNER_FAILED", "本地视觉 runner 返回失败", exit_code=6, path=str(runner), cause=completed.stderr[-3000:])
    stdout = completed.stdout or ""
    if len(stdout.encode("utf-8", errors="replace")) > 10 * 1024 * 1024:
        raise AppError("TRACKING_RUNNER_OUTPUT_TOO_LARGE", "本地视觉 runner 输出超过 10 MiB 限制", exit_code=6, path=str(runner))
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AppError("TRACKING_RUNNER_OUTPUT_INVALID", "本地视觉 runner stdout 不是有效 JSON", exit_code=6, path=str(runner), cause=str(exc)) from exc
    if not isinstance(response, dict):
        raise AppError("TRACKING_RUNNER_OUTPUT_INVALID", "本地视觉 runner 响应必须是对象", exit_code=6, path=str(runner))
    if response.get("protocol") != OBJECT_TRACKING_PROTOCOL:
        raise AppError("TRACKING_RUNNER_PROTOCOL_MISMATCH", "本地视觉 runner protocol 不匹配", exit_code=6, path="protocol")
    if response.get("status") != "ok":
        raise AppError("TRACKING_RUNNER_FAILED", "本地视觉 runner 未返回 status=ok", exit_code=6, path="status", cause=json.dumps(response, ensure_ascii=False)[:3000])
    raw_frames = response.get("frames")
    if not isinstance(raw_frames, list) or not raw_frames:
        raise AppError("TRACKING_RUNNER_OUTPUT_INVALID", "本地视觉 runner 必须返回非空 frames 数组", exit_code=6, path="frames")
    if len(raw_frames) > max_samples:
        raise AppError("TRACKING_RUNNER_OUTPUT_INVALID", "本地视觉 runner 返回帧数超过 max_samples", exit_code=6, path="frames")
    positions: list[dict[str, Any]] = []
    previous_tick = -1
    for index, raw in enumerate(raw_frames):
        if not isinstance(raw, dict):
            raise _tracking_frame_error("必须是对象", index=index, path=f"frames[{index}]")
        try:
            at_seconds = float(raw.get("at_seconds"))
            if not math.isfinite(at_seconds):
                raise ValueError("at_seconds")
            raw_tick = raw.get("at_tick")
            at_tick = int(round((at_seconds - start_seconds) * ticks_per_second)) if raw_tick is None else int(raw_tick)
            values = [float(raw.get(key)) for key in ("x", "y", "width", "height", "confidence")]
            if not all(math.isfinite(value) for value in values):
                raise ValueError("non-finite")
            x, y, width, height, confidence = values
        except (TypeError, ValueError) as exc:
            raise _tracking_frame_error("坐标、时间和 confidence 必须是有限数字", index=index, path=f"frames[{index}]") from exc
        if at_seconds < start_seconds - 1e-6 or (end_seconds is not None and at_seconds > end_seconds + 1e-6):
            raise _tracking_frame_error("at_seconds 超出请求范围", index=index, path=f"frames[{index}].at_seconds")
        if at_tick < 0 or at_tick < previous_tick:
            raise _tracking_frame_error("at_tick 必须非负且单调递增", index=index, path=f"frames[{index}].at_tick")
        if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0 or not 0.0 < width <= 1.0 or not 0.0 < height <= 1.0:
            raise _tracking_frame_error("x/y/width/height 必须位于归一化范围", index=index, path=f"frames[{index}]")
        if not 0.0 <= confidence <= 1.0:
            raise _tracking_frame_error("confidence 必须位于 0..1", index=index, path=f"frames[{index}].confidence")
        previous_tick = at_tick
        positions.append({
            "at_seconds": round(at_seconds, 6),
            "at_tick": at_tick,
            "x": round(x, 6),
            "y": round(y, 6),
            "width": round(width, 6),
            "height": round(height, 6),
            "confidence": round(confidence, 6),
        })
    response_range = response.get("range") if isinstance(response.get("range"), dict) else {}
    return {
        "engine": OBJECT_TRACKING_ENGINE,
        "method": "command-json",
        "protocol": OBJECT_TRACKING_PROTOCOL,
        "output_contract": OBJECT_TRACKING_OUTPUT_CONTRACT,
        "adapter_id": str(adapter_id),
        "model_path": str(model),
        "model_sha256": model_sha256,
        "executable": str(runner),
        "executable_sha256": executable_sha256,
        "source": str(source),
        "source_sha256": source_sha256,
        "range": {
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "step_frames": step_frames,
            "max_samples": max_samples,
            "runner": response_range,
        },
        "ticks_per_second": ticks_per_second,
        "roi": {"x": roi_values[0], "y": roi_values[1], "width": roi_values[2], "height": roi_values[3]},
        "frames": positions,
        "keyframes": [
            {"property": "transform.position.x", "keyframes": [{"at_tick": item["at_tick"], "value": item["x"], "interpolation": "linear"} for item in positions]},
            {"property": "transform.position.y", "keyframes": [{"at_tick": item["at_tick"], "value": item["y"], "interpolation": "linear"} for item in positions]},
        ],
        "runner": {"status": response.get("status"), "engine": response.get("engine"), "metadata": response.get("metadata", {}) if isinstance(response.get("metadata"), dict) else {}},
        "warnings": ["external_local_runner_requires_quality_review", "runner_output_validated_by_agent"],
    }


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


def build_reframe_plan(
    frames: list[dict[str, Any]],
    *,
    source_aspect: float,
    target_aspect: float,
    margin: float = 0.12,
    fit: str = "fill",
) -> dict[str, Any]:
    """Convert local tracking positions into a target-aspect crop animation.

    The crop window keeps the largest legal source rectangle with the requested
    output aspect and follows the tracked subject center.  The subject bbox is
    checked against that window; when it cannot fit without breaking the target
    aspect, the plan remains deterministic and reports a clipping warning for
    Agent review instead of inventing a zoom or an out-of-bounds crop.
    """
    try:
        source_aspect = float(source_aspect)
        target_aspect = float(target_aspect)
        margin = float(margin)
    except (TypeError, ValueError) as exc:
        raise AppError("REFRAME_PARAMETER_INVALID", "自动重构图参数必须是数字", exit_code=2, path="target_aspect") from exc
    if source_aspect <= 0 or target_aspect <= 0:
        raise AppError("REFRAME_ASPECT_INVALID", "源画幅和目标画幅必须大于 0", exit_code=2, path="target_aspect")
    if margin < 0 or margin > 0.75:
        raise AppError("REFRAME_MARGIN_INVALID", "自动重构图 margin 必须位于 0..0.75", exit_code=2, path="margin")
    fit = str(fit or "fill").lower()
    if fit not in {"fit", "fill", "stretch"}:
        raise AppError("REFRAME_FIT_INVALID", "自动重构图 fit 只支持 fit、fill、stretch", exit_code=2, path="fit")
    ordered = [item for item in frames if isinstance(item, dict)]
    if not ordered:
        raise AppError("REFRAME_TRACK_EMPTY", "自动重构图需要至少一个跟踪帧", exit_code=2, path="frames")
    ratio = target_aspect / source_aspect
    if ratio <= 1.0:
        base_width, base_height = ratio, 1.0
    else:
        base_width, base_height = 1.0, 1.0 / ratio
    warnings: list[str] = []
    x_values: list[dict[str, Any]] = []
    y_values: list[dict[str, Any]] = []
    width_values: list[dict[str, Any]] = []
    height_values: list[dict[str, Any]] = []
    clipped_frames = 0
    for item in ordered:
        try:
            at_tick = max(0, int(item.get("at_tick", 0)))
            center_x = min(1.0, max(0.0, float(item.get("x", 0.5))))
            center_y = min(1.0, max(0.0, float(item.get("y", 0.5))))
            subject_width = max(0.0, float(item.get("width", 0.0))) * (1.0 + 2.0 * margin)
            subject_height = max(0.0, float(item.get("height", 0.0))) * (1.0 + 2.0 * margin)
        except (TypeError, ValueError):
            continue
        if subject_width > base_width + 1e-6 or subject_height > base_height + 1e-6:
            clipped_frames += 1
        crop_x = min(max(0.0, center_x - base_width / 2.0), 1.0 - base_width)
        crop_y = min(max(0.0, center_y - base_height / 2.0), 1.0 - base_height)
        x_values.append({"at_tick": at_tick, "value": round(crop_x, 6), "interpolation": "linear"})
        y_values.append({"at_tick": at_tick, "value": round(crop_y, 6), "interpolation": "linear"})
        width_values.append({"at_tick": at_tick, "value": round(base_width, 6), "interpolation": "linear"})
        height_values.append({"at_tick": at_tick, "value": round(base_height, 6), "interpolation": "linear"})
    if not x_values:
        raise AppError("REFRAME_TRACK_EMPTY", "自动重构图没有可用的跟踪帧", exit_code=2, path="frames")
    if clipped_frames:
        warnings.append("tracked_subject_exceeds_target_crop_window")
    if any(float(item.get("confidence", 1.0)) < 0.35 for item in ordered):
        warnings.append("low_tracking_confidence_requires_review")
    warnings.append("local_template_tracking_can_drift_on_occlusion_scale_change_or_scene_cut")
    return {
        "engine": "local-reframe-from-template-track-v1",
        "source_aspect": round(source_aspect, 8),
        "target_aspect": round(target_aspect, 8),
        "margin": round(margin, 6),
        "fit": fit,
        "crop": {"unit": "normalized", "x": x_values[0]["value"], "y": y_values[0]["value"], "width": round(base_width, 6), "height": round(base_height, 6), "fit": fit},
        "keyframes": [
            {"property": "crop.x", "keyframes": x_values},
            {"property": "crop.y", "keyframes": y_values},
            {"property": "crop.width", "keyframes": width_values},
            {"property": "crop.height", "keyframes": height_values},
        ],
        "frames": len(x_values),
        "clipped_frame_count": clipped_frames,
        "warnings": warnings,
    }
