"""Local audio extraction primitives used by the Agent CLI.

The first primitive intentionally stays below source separation: it extracts
the first local audio stream without reusing a video decoder or contacting a
remote service.  The CLI registers the result as a derived project asset so
Agents can route it to a timeline while retaining hash and rights evidence.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .media import ffmpeg_path, probe_media
from .utils import run_process, sha256_file


AUDIO_EXTRACT_VERSION = "0.1.0"
_SUPPORTED_SAMPLE_RATES = {8_000, 16_000, 22_050, 24_000, 32_000, 44_100, 48_000, 96_000}


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def inspect_audio_source(source: Path) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("音频提取输入必须是存在的本地文件", str(source))
    probe = probe_media(source)
    audio = probe.get("audio") if isinstance(probe.get("audio"), dict) else {}
    if not audio.get("codec"):
        raise AppError("AUDIO_STREAM_MISSING", f"输入没有可提取的音频流: {source}", exit_code=2, path=str(source))
    return probe


def extract_audio(
    source: Path,
    output: Path,
    *,
    sample_rate: int | None = None,
    channels: int | None = None,
) -> dict[str, Any]:
    """Extract the first audio stream to a project-local lossless WAV file."""
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    probe = inspect_audio_source(source)
    if output.suffix.lower() != ".wav":
        raise argument_error("本地音频提取输出必须使用 .wav，以保留确定性的 PCM 结果", str(output))
    if sample_rate is not None:
        try:
            sample_rate = int(sample_rate)
        except (TypeError, ValueError) as exc:
            raise argument_error("sample_rate 必须是整数", "sample_rate") from exc
        if sample_rate not in _SUPPORTED_SAMPLE_RATES:
            raise argument_error(f"sample_rate 必须是 {sorted(_SUPPORTED_SAMPLE_RATES)} 之一", "sample_rate")
    if channels is not None:
        try:
            channels = int(channels)
        except (TypeError, ValueError) as exc:
            raise argument_error("channels 必须是整数", "channels") from exc
        if channels not in {1, 2}:
            raise argument_error("channels 只支持 1 或 2", "channels")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise argument_error("音频提取输出已存在，为避免覆盖请指定新的 --output", str(output))
    command = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
        "-dn",
    ]
    if sample_rate is not None:
        command.extend(["-ar", str(sample_rate)])
    if channels is not None:
        command.extend(["-ac", str(channels)])
    command.extend(["-c:a", "pcm_s16le", str(output)])
    result = run_process(command, timeout=600)
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        try:
            output.unlink()
        except FileNotFoundError:
            pass
        raise AppError(
            "AUDIO_EXTRACT_FAILED",
            f"本地 FFmpeg 音频提取失败: {source}",
            exit_code=6,
            retryable=True,
            path=str(source),
            cause=(result.stderr or result.stdout)[-4000:],
        )
    output_probe = probe_media(output)
    output_audio = output_probe.get("audio") if isinstance(output_probe.get("audio"), dict) else {}
    if not output_audio.get("codec"):
        raise AppError("AUDIO_EXTRACT_INVALID", "提取输出没有可读音频流", exit_code=6, path=str(output))
    return {
        "version": AUDIO_EXTRACT_VERSION,
        "engine": "ffmpeg-local-audio-extract-v1",
        "network": "disabled",
        "source": str(source),
        "source_sha256": f"sha256:{sha256_file(source)}",
        "output": str(output),
        "output_sha256": f"sha256:{sha256_file(output)}",
        "input_probe": probe,
        "output_probe": output_probe,
        "duration_seconds": round(_finite(output_probe.get("duration_seconds")), 6),
        "sample_rate": output_audio.get("sample_rate"),
        "channels": output_audio.get("channels"),
        "warnings": [],
    }
