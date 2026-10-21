from __future__ import annotations

"""Deterministic local multi-camera audio sync and switch planning.

The module deliberately stops at an auditable synchronization primitive.  It
does not claim speaker identification, visual shot selection, or semantic
director decisions.  Audio is decoded locally with FFmpeg, reduced to a small
energy envelope, and aligned with a bounded normalized cross-correlation.
"""

import math
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error, dependency_error
from .media import ffmpeg_path, probe_media
from .utils import new_id, sha256_file


MULTICAM_SYNC_VERSION = "0.5.0"
FEATURE_RATE_HZ = 50


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        converted = float(value)
    except (TypeError, ValueError):
        return default
    return converted if math.isfinite(converted) else default


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on local runtime
        raise dependency_error("多机位音频同步需要本地 numpy", "安装本地 numpy；不会自动联网安装") from exc
    return np


def _video_coverage(path: Path, digest: str, *, project_root: Path | None = None) -> dict[str, Any]:
    """Use the renderer's native display clock, without populating a dry-run cache."""
    from .reverse_video_clock import _nearest, probe_frames
    if project_root is None:
        pts, durations, stream, format_info = probe_frames(path)
        index = {'status': 'direct-probe', 'source_index_decode_calls': 1}
        if f"sha256:{sha256_file(path)}" != digest:
            raise AppError('MULTICAM_SOURCE_CHANGED', '多机位视频分析期间源文件发生变化', exit_code=6, path=str(path))
    else:
        from .native_video_index import IndexContext
        pts, durations, stream, format_info, index = IndexContext(project_root, persist=False).acquire(path, digest, probe_frames)
    if not pts or len(pts) != len(durations) or durations[-1] <= 0:
        raise AppError('MULTICAM_VIDEO_COVERAGE_UNKNOWN', '多机位视频末帧没有可验证的显示时长', exit_code=2, path=str(path))
    try:
        native = Fraction(stream['time_base'])
        origin_text = format_info.get('start_time', '0')
        origin = _nearest(Fraction('0' if origin_text in (None, '', 'N/A') else origin_text) / native)
        first = (pts[0] - origin) * native
        final = (pts[-1] + durations[-1] - origin) * native
        left = max(Fraction(0), first)
        if native <= 0 or final <= left:
            raise ValueError('No positive native video range after the demux origin')
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise AppError('MULTICAM_VIDEO_COVERAGE_UNKNOWN', '多机位视频时间基或覆盖区间无效', exit_code=2, path=str(path), cause=str(exc)) from exc
    return {'protocol': 'native-video-first-last-intervals-v1', 'status': 'known',
        'start_seconds': float(left), 'end_seconds': float(final),
        'start_seconds_rational': str(left), 'end_seconds_rational': str(final),
        'native_time_base': str(native), 'demux_origin_native_pts': origin,
        'first_native_pts': pts[0], 'last_native_pts': pts[-1], 'last_duration_native': durations[-1],
        'frame_count': len(pts), 'source_sha256': digest, 'native_index': index,
        'internal_display_intervals': 'hold_to_next_pts_as_renderer', 'cache_writes': False}


def _extract_envelope(path: Path, *, sample_rate: int, max_seconds: float, project_root: Path | None = None) -> tuple[Any, dict[str, Any]]:
    """Decode a bounded local audio prefix and return a normalized envelope."""
    np = _numpy()
    if sample_rate < 1000 or sample_rate > 96_000:
        raise argument_error("sample_rate 必须位于 1000..96000", "sample_rate")
    if max_seconds <= 0 or max_seconds > 600:
        raise argument_error("analysis_seconds 必须位于 0..600", "analysis_seconds")
    probe = probe_media(path)
    digest = f"sha256:{sha256_file(path)}"
    audio = probe.get("audio") if isinstance(probe.get("audio"), dict) else {}
    if not audio.get("codec"):
        raise AppError("MULTICAM_AUDIO_MISSING", f"机位素材没有音频流: {path}", exit_code=2, path=str(path))
    try:
        completed = subprocess.run(
            [
                ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-t", f"{max_seconds:.3f}",
                "-i", str(path), "-vn", "-af", f"aresample={sample_rate}:first_pts=0",
                "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-",
            ],
            capture_output=True,
            timeout=max(60.0, max_seconds * 4.0),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AppError("MULTICAM_AUDIO_EXTRACT_FAILED", f"多机位音频抽取失败: {path}", exit_code=6, retryable=True, path=str(path), cause=str(exc)) from exc
    if completed.returncode != 0 or not completed.stdout:
        raise AppError(
            "MULTICAM_AUDIO_EXTRACT_FAILED",
            f"多机位音频抽取失败: {path}",
            exit_code=6,
            retryable=True,
            path=str(path),
            cause=(completed.stderr or b"")[-4000:].decode("utf-8", errors="replace"),
        )
    raw = completed.stdout[: len(completed.stdout) - (len(completed.stdout) % 2)]
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if samples.size < max(32, sample_rate // 4):
        raise AppError("MULTICAM_AUDIO_SIGNAL_SHORT", f"机位音频有效信号过短: {path}", exit_code=2, path=str(path))
    samples /= 32768.0
    hop = max(1, int(round(sample_rate / FEATURE_RATE_HZ)))
    frame_count = samples.size // hop
    samples = samples[: frame_count * hop]
    envelope = np.sqrt(np.mean(samples.reshape(frame_count, hop) ** 2, axis=1))
    # Log compression and first difference reduce gain/room-tone differences.
    envelope = np.log1p(envelope * 100.0)
    envelope = np.diff(envelope, prepend=envelope[:1])
    envelope -= np.mean(envelope)
    scale = float(np.std(envelope))
    if not math.isfinite(scale) or scale <= 1e-7:
        raise AppError("MULTICAM_AUDIO_SIGNAL_FLAT", f"机位音频没有足够可对齐的变化: {path}", exit_code=2, path=str(path))
    envelope = envelope / scale
    try:
        coverage = _video_coverage(path, digest, project_root=project_root)
    except AppError as exc:
        if exc.code != 'MULTICAM_VIDEO_COVERAGE_UNKNOWN':
            raise
        # Audio-only analysis is still useful; authoring requires known bounds below.
        # Integrity failures never enter this branch or become successful fallbacks.
        coverage = {'protocol': 'native-video-first-last-intervals-v1', 'status': 'unknown',
            'error': {'code': exc.code, 'message': str(exc)}, 'cache_writes': False}
    if f"sha256:{sha256_file(path)}" != digest:
        raise AppError('MULTICAM_SOURCE_CHANGED', '多机位音视频分析期间源文件发生变化', exit_code=6, path=str(path))
    return envelope.astype(np.float32), {
        "path": str(path),
        "sha256": digest,
        "duration_seconds": round(float(probe.get("duration_seconds", 0.0)), 6),
        "video_coverage": coverage,
        "audio_source_clock": "demux-relative-first-audio-pts-v1",
        "audio_origin_filter": f"aresample={sample_rate}:first_pts=0",
        "sample_rate": sample_rate,
        "feature_rate_hz": FEATURE_RATE_HZ,
        "feature_count": int(envelope.size),
    }


def _overlap(ref: Any, candidate: Any, lag: int) -> tuple[Any, Any]:
    """Return reference/candidate slices for numpy correlate's lag convention."""
    ref_len = int(ref.size)
    candidate_len = int(candidate.size)
    if lag >= 0:
        length = min(ref_len - lag, candidate_len)
        return ref[lag : lag + max(0, length)], candidate[: max(0, length)]
    offset = -lag
    length = min(ref_len, candidate_len - offset)
    return ref[: max(0, length)], candidate[offset : offset + max(0, length)]


def estimate_audio_offset(reference: Any, candidate: Any, *, max_offset_seconds: float) -> dict[str, Any]:
    """Estimate candidate delay relative to reference using bounded correlation."""
    np = _numpy()
    if reference.size == 0 or candidate.size == 0:
        raise argument_error("多机位音频特征不能为空", "sources")
    max_offset = max(0.0, min(float(max_offset_seconds), 300.0))
    max_lag = int(round(max_offset * FEATURE_RATE_HZ))
    # Leading source silence changes each whole-prefix mean and variance. Rank
    # and report Pearson correlation on the actual common event window, rather
    # than letting a different prefix dilute confidence or bias the chosen lag.
    reference = np.asarray(reference, dtype=np.float64)
    candidate = np.asarray(candidate, dtype=np.float64)
    correlation = np.correlate(reference, candidate, mode="full")
    lags = np.arange(-int(candidate.size) + 1, int(reference.size), dtype=np.int64)
    mask = np.abs(lags) <= max_lag
    if not bool(np.any(mask)):
        raise argument_error("max_offset_seconds 没有有效搜索范围", "max_offset_seconds")
    masked_indices = np.flatnonzero(mask)
    def prefix(values):
        return np.concatenate((np.zeros(1,dtype=np.float64),np.cumsum(values,dtype=np.float64)))
    ref_sum,ref_square=prefix(reference),prefix(reference*reference)
    candidate_sum,candidate_square=prefix(candidate),prefix(candidate*candidate)
    ranked=[]
    for index in masked_indices:
        index=int(index);lag=int(lags[index]);left=max(0,lag);right=max(0,-lag)
        count=min(int(reference.size)-left,int(candidate.size)-right)
        if count<FEATURE_RATE_HZ:
            continue
        # Features are first differences. At the first common sample, one
        # source may have real preceding silence while the other has no prior
        # sample. That artificial boundary has no comparable history.
        cross=float(correlation[index]-reference[left]*candidate[right])
        left+=1;right+=1;scoring_count=count-1
        a=float(ref_sum[left+scoring_count]-ref_sum[left]);b=float(candidate_sum[right+scoring_count]-candidate_sum[right])
        aa=max(0.,float(ref_square[left+scoring_count]-ref_square[left])-a*a/scoring_count)
        bb=max(0.,float(candidate_square[right+scoring_count]-candidate_square[right])-b*b/scoring_count)
        denominator=math.sqrt(aa*bb)
        score=float((cross-a*b/scoring_count)/denominator) if denominator>1e-9 else 0.
        ranked.append((max(-1.,min(1.,score)),count,-abs(lag),lag))
    # Reject tiny overlaps, which can create a falsely perfect edge match.
    if not ranked:
        raise AppError("MULTICAM_OVERLAP_TOO_SHORT", "多机位音频重叠不足以估计偏移", exit_code=2, path="sources")
    score,overlap_count,_,lag=max(ranked)
    # A positive delay means the candidate's matching event occurs later than
    # the reference.  The correction applied to a timeline is its negative.
    delay_seconds = -lag / FEATURE_RATE_HZ
    return {
        "relative_delay_seconds": round(delay_seconds, 6),
        "correction_seconds": round(-delay_seconds, 6),
        "lag_frames": lag,
        "score": round(max(-1.0, min(1.0, score)), 6),
        "overlap_seconds": round(overlap_count / FEATURE_RATE_HZ, 6),
        "score_contract": "overlap_pearson_excluding_first_difference_boundary_v1",
        "status": "ok" if score >= 0.35 else "low_confidence",
    }


def synchronize_multicam_sources(
    sources: list[dict[str, Any]],
    *,
    reference_asset_id: str | None = None,
    sample_rate: int = 8000,
    analysis_seconds: float = 120.0,
    max_offset_seconds: float = 30.0,
    clock_model: str = "offset",
    max_drift_ppm: float = 5000.0,
    drift_window_seconds: float = 12.0,
    drift_anchors: int = 9,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Analyze a set of local project assets and return auditable offsets."""
    if len(sources) < 2:
        raise argument_error("多机位同步至少需要两个源素材", "source_asset_id")
    if clock_model not in {"offset", "affine"}:
        raise argument_error("clock_model 必须为 offset 或 affine", "clock_model")
    if clock_model == "affine":
        from .multicam_clock import validate_affine_options
        validate_affine_options(max_offset_seconds=max_offset_seconds, max_drift_ppm=max_drift_ppm,
                                window_seconds=drift_window_seconds, anchor_count=drift_anchors)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(sources):
        if not isinstance(item, dict):
            raise argument_error("多机位源素材必须是对象", f"sources[{index}]")
        asset_id = str(item.get("asset_id", "")).strip()
        path = Path(str(item.get("path", ""))).expanduser().resolve()
        if not asset_id or asset_id in seen:
            raise argument_error("多机位源素材 ID 必须唯一", f"sources[{index}].asset_id")
        if not path.exists() or not path.is_file():
            raise AppError("MULTICAM_SOURCE_MISSING", f"多机位源素材不存在: {path}", exit_code=3, path=str(path))
        seen.add(asset_id)
        normalized.append({"asset_id": asset_id, "path": path})
    reference_id = reference_asset_id or str(normalized[0]["asset_id"])
    if reference_id not in seen:
        raise argument_error("reference_asset_id 必须属于 source_asset_id", "reference_asset_id")
    reference_item = next(item for item in normalized if item["asset_id"] == reference_id)
    reference_feature, reference_evidence = _extract_envelope(reference_item["path"], sample_rate=sample_rate, max_seconds=analysis_seconds, project_root=project_root)
    offsets: list[dict[str, Any]] = []
    for item in normalized:
        if item["asset_id"] == reference_id:
            evidence = {**reference_evidence, "asset_id": reference_id}
            offsets.append({"asset_id": reference_id, "reference_asset_id": reference_id, "relative_delay_seconds": 0.0, "correction_seconds": 0.0, "lag_frames": 0, "score": 1.0, "overlap_seconds": round(reference_feature.size / FEATURE_RATE_HZ, 6), "status": "reference", "evidence": evidence})
            continue
        candidate_feature, candidate_evidence = _extract_envelope(item["path"], sample_rate=sample_rate, max_seconds=analysis_seconds, project_root=project_root)
        if clock_model == "affine":
            from .multicam_clock import estimate_affine_clock, seal_clock
            model = estimate_affine_clock(reference_feature, candidate_feature,
                max_offset_seconds=max_offset_seconds, max_drift_ppm=max_drift_ppm,
                window_seconds=drift_window_seconds, anchor_count=drift_anchors)
            model = seal_clock({**model, "source_asset_id": item["asset_id"], "reference_asset_id": reference_id,
                                "source_sha256": candidate_evidence["sha256"], "reference_sha256": reference_evidence["sha256"]})
            delay = model["offset_seconds"]
            bounds = model["valid_reference_range"]
            alignment = {"relative_delay_seconds": delay, "correction_seconds": round(-delay, 9),
                "lag_frames": int(round(-delay * FEATURE_RATE_HZ)),
                "score": min(row["score"] for row in model["anchors"] if row["accepted"]),
                "overlap_seconds": round(bounds["end_seconds"] - bounds["start_seconds"], 9),
                "score_contract": "affine-window-pearson-v1", "status": "ok", "clock_model": model}
        else:
            alignment = estimate_audio_offset(reference_feature, candidate_feature, max_offset_seconds=max_offset_seconds)
        offsets.append({"asset_id": item["asset_id"], "reference_asset_id": reference_id, **alignment, "evidence": {**candidate_evidence, "asset_id": item["asset_id"]}})
    return {
        "sync_version": MULTICAM_SYNC_VERSION,
        "engine": "ffmpeg-local-audio-envelope-affine-v1" if clock_model == "affine" else "ffmpeg-local-audio-envelope-xcorr-v1",
        "network": "disabled",
        "reference_asset_id": reference_id,
        "parameters": {
            "sample_rate": int(sample_rate),
            "feature_rate_hz": FEATURE_RATE_HZ,
            "analysis_seconds": round(float(analysis_seconds), 6),
            "max_offset_seconds": round(float(max_offset_seconds), 6),
            "clock_model": clock_model,
            "max_drift_ppm": max_drift_ppm,
            "drift_window_seconds": drift_window_seconds,
            "drift_anchors": drift_anchors,
        },
        "sources": [{"asset_id": item["asset_id"], "path": str(item["path"])} for item in normalized],
        "offsets": offsets,
        "warnings": [
            {"code": "MULTICAM_LOW_CONFIDENCE", "message": f"机位 {item['asset_id']} 音频偏移相关性较低，请复核波形或拍板点", "asset_id": item["asset_id"], "score": item.get("score")}
            for item in offsets if item.get("status") == "low_confidence"
        ] + [
            {'code': 'MULTICAM_VIDEO_COVERAGE_UNKNOWN', 'message': f"机位 {item['asset_id']} 的视频覆盖未知；保留音频同步分析，不能生成该机位切换段", 'asset_id': item['asset_id']}
            for item in offsets if item['evidence']['video_coverage'].get('status') == 'unknown'
        ],
    }


def build_switch_segments(
    sync: dict[str, Any],
    *,
    switch_seconds: float | None = None,
    switch_plan: list[dict[str, Any]] | None = None,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    timeline_start_seconds: float = 0.0,
    source_shortfall: str = "reject",
    allow_clock_extrapolation: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build source-bounded angle clips from a fixed cadence or explicit plan."""
    if source_shortfall not in {"reject", "trim", "stretch"}:
        raise argument_error("source_shortfall 必须为 reject、trim 或 stretch", "source_shortfall")
    if not isinstance(allow_clock_extrapolation, bool):
        raise argument_error("allow_clock_extrapolation 必须为 bool", "allow_clock_extrapolation")
    offsets = {str(item.get("asset_id")): item for item in sync.get("offsets", []) if isinstance(item, dict)}
    sources = [str(item.get("asset_id")) for item in sync.get("sources", []) if isinstance(item, dict)]
    if not sources:
        raise argument_error("同步结果缺少源素材", "sync.sources")
    reference_id = str(sync.get("reference_asset_id", sources[0]))
    reference_duration = _finite(offsets.get(reference_id, {}).get("evidence", {}).get("duration_seconds"), 0.0)
    start = _finite(start_seconds, 0.0)
    end = reference_duration if end_seconds is None else _finite(end_seconds, reference_duration)
    if start < 0 or end <= start:
        raise argument_error("start_seconds/end_seconds 必须形成正的时间范围", "start_seconds")
    warnings: list[dict[str, Any]] = []
    if switch_plan is not None:
        raw_segments = switch_plan
        if not isinstance(raw_segments, list) or not raw_segments:
            raise argument_error("switch_plan 必须是非空数组", "switch_plan")
    elif switch_seconds is not None:
        cadence = _finite(switch_seconds, 0.0)
        if cadence <= 0:
            raise argument_error("switch_seconds 必须大于 0", "switch_seconds")
        raw_segments = []
        cursor = start
        index = 0
        while cursor < end - 1e-9:
            raw_segments.append({"start_seconds": cursor, "end_seconds": min(end, cursor + cadence), "camera_asset_id": sources[index % len(sources)]})
            cursor += cadence
            index += 1
    else:
        return [], [{"code": "MULTICAM_SWITCH_PLAN_MISSING", "message": "只执行同步分析；未提供 switch_seconds 或 switch_plan，未生成时间线切换"}]
    segments: list[dict[str, Any]] = []
    cursor = start
    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            raise argument_error("切换段必须是对象", f"switch_plan[{index}]")
        left = _finite(raw.get("start_seconds"), cursor)
        right = _finite(raw.get("end_seconds"), 0.0)
        asset_id = str(raw.get("camera_asset_id") or raw.get("asset_id") or "").strip()
        if not asset_id and raw.get("camera_index") is not None:
            try:
                asset_id = sources[int(raw["camera_index"])]
            except (IndexError, TypeError, ValueError) as exc:
                raise argument_error("camera_index 不在 source_asset_id 范围内", f"switch_plan[{index}].camera_index") from exc
        if asset_id not in offsets:
            raise argument_error("切换段引用了未知 camera_asset_id", f"switch_plan[{index}].camera_asset_id")
        if left < start - 1e-6 or right > end + 1e-6 or right <= left:
            raise argument_error("切换段必须位于 start_seconds/end_seconds 范围内且时长为正", f"switch_plan[{index}]")
        if index and left < cursor - 1e-6:
            raise argument_error("switch_plan 的切换段不能重叠", f"switch_plan[{index}]")
        alignment = offsets[asset_id]
        relative_delay = _finite(alignment.get("relative_delay_seconds"), 0.0)
        from .multicam_clock import clock_for_alignment
        clock = clock_for_alignment(sync, alignment, asset_id)
        clock_rate = 1.0
        if clock is not None:
            clock_rate, relative_delay, observed_start, observed_end = clock
        evidence = alignment.get("evidence", {})
        native_coverage = evidence.get('video_coverage')
        if native_coverage is None:
            if sync.get('sync_version') not in (None, '', '0.1.0', '0.2.0'):
                raise AppError('MULTICAM_VIDEO_COVERAGE_UNKNOWN', f'机位 {asset_id} 缺少原生视频覆盖证据', exit_code=2)
            source_left = 0.0
            source_duration = _finite(evidence.get('duration_seconds'), 0.0)
            warnings.append({'code': 'MULTICAM_LEGACY_CONTAINER_COVERAGE', 'message': f'机位 {asset_id} 为旧同步结果，只具备容器覆盖证据', 'asset_id': asset_id})
        else:
            try:
                if isinstance(native_coverage['start_seconds'], bool) or isinstance(native_coverage['end_seconds'], bool):
                    raise ValueError('boolean video bounds are invalid')
                source_left = float(native_coverage['start_seconds'])
                source_duration = float(native_coverage['end_seconds'])
                if not math.isfinite(source_left) or not math.isfinite(source_duration) or source_left < 0 or source_duration <= source_left:
                    raise ValueError('invalid video bounds')
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise AppError('MULTICAM_VIDEO_COVERAGE_UNKNOWN', f'机位 {asset_id} 原生视频覆盖证据无效', exit_code=2) from exc
        requested_left, requested_right = left, right
        covered_left = max(left, (source_left - relative_delay) / clock_rate)
        covered_right = min(right, (source_duration - relative_delay) / clock_rate)
        if covered_right <= covered_left:
            raise AppError("MULTICAM_SOURCE_RANGE_EMPTY", f"机位 {asset_id} 无法覆盖切换段", exit_code=2, path=f"switch_plan[{index}]")
        shortfall = left * clock_rate + relative_delay < source_left - 1e-9 or right * clock_rate + relative_delay > source_duration + 1e-9
        coverage = "complete"
        if shortfall and source_shortfall == "reject":
            raise AppError("MULTICAM_SOURCE_SHORTFALL", f"机位 {asset_id} 未完整覆盖切换段；请缩小选区，或显式选择 --source-shortfall trim|stretch", exit_code=2, path=f"switch_plan[{index}]")
        if shortfall and source_shortfall == "trim":
            left, right = covered_left, covered_right
            coverage = "trimmed"
            warnings.append({"code": "MULTICAM_SOURCE_TRIMMED", "message": f"机位 {asset_id} 仅保留有覆盖的校准同步区间，缺失部分留空", "asset_id": asset_id,
                             "requested_start_seconds": round(requested_left, 6), "requested_end_seconds": round(requested_right, 6),
                             "covered_start_seconds": round(left, 6), "covered_end_seconds": round(right, 6)})
        elif shortfall:
            coverage = "stretched"
            warnings.append({"code": "MULTICAM_SOURCE_CLOCK_CHANGED", "message": f"机位 {asset_id} 显式填充缺失覆盖；钳制或慢放将改变与参考机位的事件同步", "asset_id": asset_id})
        if clock is not None and (left < observed_start - 1e-9 or right > observed_end + 1e-9):
            if not allow_clock_extrapolation:
                raise AppError("MULTICAM_CLOCK_EXTRAPOLATION", "切换段超出被观察的时钟校准范围；扩展分析范围或显式允许外推", exit_code=2, path=f"switch_plan[{index}]")
            warnings.append({"code": "MULTICAM_CLOCK_EXTRAPOLATION", "asset_id": asset_id,
                "message": "显式允许在观测范围外外推机位时钟，需独立核验事件同步",
                "observed_start_seconds": observed_start, "observed_end_seconds": observed_end,
                "requested_start_seconds": left, "requested_end_seconds": right,
                "before_seconds": max(0., observed_start - left), "after_seconds": max(0., right - observed_end)})
        source_start = left * clock_rate + relative_delay
        if source_start < source_left - 1e-9:
            warnings.append({"code": "MULTICAM_SOURCE_CLAMPED", "message": f"机位 {asset_id} 的源起点早于视频覆盖起点，已钳制", "asset_id": asset_id, "seconds": round(source_start, 6), 'video_start_seconds': source_left})
            source_start = source_left
        source_start = max(source_left, source_start)
        available = max(0.0, source_duration - source_start)
        requested = right - left
        if available <= 0:
            raise AppError("MULTICAM_SOURCE_RANGE_EMPTY", f"机位 {asset_id} 无法覆盖切换段", exit_code=2, path=f"switch_plan[{index}]")
        source_span = min(requested * clock_rate, available)
        speed = source_span / requested
        if speed < clock_rate * 0.999999:
            warnings.append({"code": "MULTICAM_SOURCE_SLOWED", "message": f"机位 {asset_id} 可用源范围不足，使用 speed={speed:.6f} 填满切换段", "asset_id": asset_id, "speed": round(speed, 6)})
        segments.append({
            "index": index,
            "camera_asset_id": asset_id,
            "source_shortfall": source_shortfall,
            "source_coverage": coverage,
            "coverage_basis": 'native-video-first-last-intervals-v1' if native_coverage is not None else 'legacy-container-duration',
            "video_coverage_start_seconds": source_left,
            "video_coverage_end_seconds": source_duration,
            "requested_start_seconds": round(requested_left, 6),
            "requested_end_seconds": round(requested_right, 6),
            "start_seconds": round(left, 6),
            "end_seconds": round(right, 6),
            "timeline_start_seconds": round(timeline_start_seconds + left - start, 6),
            "duration_seconds": round(requested, 6),
            "source_in_seconds": round(source_start, 6),
            "source_out_seconds": round(source_start + source_span, 6),
            "speed": round(speed, 12),
            "source_clock": "affine" if clock is not None else "offset",
            "source_per_reference": clock_rate,
            "clock_calibration_sha256": alignment["clock_model"]["calibration_sha256"] if clock is not None else None,
        })
        cursor = requested_right
    if segments and cursor < end - 1e-6:
        warnings.append({"code": "MULTICAM_SWITCH_GAP", "message": "切换计划没有覆盖完整分析区间", "start_seconds": round(cursor, 6), "end_seconds": round(end, 6)})
    return segments, warnings


def new_multicam_clip_id(index: int) -> str:
    return new_id(f"multicam{index}")
