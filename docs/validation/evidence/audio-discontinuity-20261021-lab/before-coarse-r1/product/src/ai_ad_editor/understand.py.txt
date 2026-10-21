from __future__ import annotations

import re
import math
import subprocess
from array import array
from pathlib import Path
from typing import Any

from .media import ffmpeg_path, probe_media
from .utils import run_process


SCENE_RE = re.compile(r"pts_time:([0-9.]+)")
SILENCE_START_RE = re.compile(r"silence_start: ([0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end: ([0-9.]+)")


def detect_beats(path: Path, *, sample_rate: int = 22_050) -> dict[str, Any]:
    """Estimate rhythmic anchors from local PCM energy without a network/model call."""
    try:
        completed = subprocess.run(
            [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-"],
            capture_output=True,
            timeout=600,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "anchors": [], "bpm": None, "error": str(exc), "sample_rate": sample_rate}
    if completed.returncode != 0 or not completed.stdout:
        return {"status": "no_audio", "anchors": [], "bpm": None, "sample_rate": sample_rate}
    samples = array("h")
    samples.frombytes(completed.stdout[: len(completed.stdout) - (len(completed.stdout) % 2)])
    if not samples:
        return {"status": "no_audio", "anchors": [], "bpm": None, "sample_rate": sample_rate}
    window = 1024
    hop = 512
    energy: list[float] = []
    for start in range(0, max(1, len(samples) - window + 1), hop):
        chunk = samples[start : start + window]
        if not chunk:
            continue
        energy.append(math.sqrt(sum(float(value) * float(value) for value in chunk) / len(chunk)))
    if len(energy) < 4 or max(energy, default=0.0) <= 1.0:
        return {"status": "insufficient_signal", "anchors": [], "bpm": None, "sample_rate": sample_rate}
    ordered = sorted(energy)
    median = ordered[len(ordered) // 2]
    mean = sum(energy) / len(energy)
    deviation = math.sqrt(sum((value - mean) ** 2 for value in energy) / len(energy))
    threshold = max(median * 1.35, mean + deviation * 0.75)
    min_gap = max(1, int(round(0.25 * sample_rate / hop)))
    peaks: list[int] = []
    for index in range(1, len(energy) - 1):
        if energy[index] < threshold or energy[index] < energy[index - 1] or energy[index] < energy[index + 1]:
            continue
        if peaks and index - peaks[-1] < min_gap:
            if energy[index] > energy[peaks[-1]]:
                peaks[-1] = index
            continue
        peaks.append(index)
    anchors = [round(index * hop / sample_rate, 3) for index in peaks]
    intervals = [anchors[index] - anchors[index - 1] for index in range(1, len(anchors)) if anchors[index] > anchors[index - 1]]
    bpm = None
    if intervals:
        interval = sorted(intervals)[len(intervals) // 2]
        if interval > 0:
            candidate = 60.0 / interval
            while candidate < 60.0:
                candidate *= 2
            while candidate > 180.0:
                candidate /= 2
            bpm = round(candidate, 2)
    return {"status": "ok" if anchors else "no_peaks", "anchors": anchors, "bpm": bpm, "threshold": round(threshold, 3), "sample_rate": sample_rate}


def understand_media(path: Path, *, scene_threshold: float = 0.4, silence_db: float = -35.0, include_beats: bool = False) -> dict[str, Any]:
    probe = probe_media(path)
    duration = float(probe.get("duration_seconds", 0.0))
    scene_result = run_process(
        [ffmpeg_path(), "-hide_banner", "-nostats", "-i", str(path), "-vf", f"select=gt(scene\\,{scene_threshold}),showinfo", "-an", "-f", "null", "-"],
        timeout=600,
    )
    scene_points = sorted({round(float(value), 3) for value in SCENE_RE.findall(scene_result.stderr) if float(value) > 0 and float(value) < duration})
    silence_result = run_process(
        [ffmpeg_path(), "-hide_banner", "-nostats", "-i", str(path), "-af", f"silencedetect=noise={silence_db}dB:d=0.25", "-f", "null", "-"],
        timeout=600,
    )
    silence_starts = [float(value) for value in SILENCE_START_RE.findall(silence_result.stderr)]
    silence_ends = [float(value) for value in SILENCE_END_RE.findall(silence_result.stderr)]
    boundaries = [0.0, *scene_points, duration]
    segments = []
    for start, end in zip(boundaries, boundaries[1:]):
        if end - start >= 0.15:
            segments.append({"start_seconds": start, "end_seconds": end, "duration_seconds": round(end - start, 3), "reason": "scene_boundary" if start else "start"})
    result = {
        "analysis_version": "0.1.0",
        "source": str(path),
        "source_sha256": None,
        "probe": probe,
        "engine": "ffmpeg-local",
        "scenes": scene_points,
        "segments": segments,
        "silence": {"starts": silence_starts, "ends": silence_ends, "noise_db": silence_db},
        "transcription": {"status": "not_requested", "provider": None},
        "beat_anchors": detect_beats(path) if include_beats else {"status": "not_requested", "anchors": [], "bpm": None},
        "network": "disabled",
    }
    return result
