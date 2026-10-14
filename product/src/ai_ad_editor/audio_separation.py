"""Deterministic local audio stem approximations.

The built-in adapter exposes a transparent mid/side split.  It is useful for
rough center-channel vocal reduction and ambience extraction, but it is not an
AI source-separation model.  Model-backed adapters must be registered and
audited separately before they can be added to this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .audio_tools import inspect_audio_source
from .errors import AppError, argument_error
from .media import ffmpeg_path, probe_media
from .utils import run_process, sha256_file


AUDIO_SEPARATION_VERSION = "0.1.0"
AUDIO_SEPARATION_ENGINE = "ffmpeg-local-mid-side-v1"


def separate_mid_side(
    source: Path,
    center_output: Path,
    side_output: Path,
    *,
    sample_rate: int | None = None,
) -> dict[str, Any]:
    """Write center and side stems from the first local audio stream.

    ``center`` is a mono mid signal and ``side`` is a stereo difference signal.
    Converting to stereo first keeps mono and multichannel inputs deterministic
    while making the residual bleed and phase sensitivity explicit to Agents.
    """
    source = source.expanduser().resolve()
    center_output = center_output.expanduser().resolve()
    side_output = side_output.expanduser().resolve()
    input_probe = inspect_audio_source(source)
    if center_output == side_output:
        raise argument_error("center 和 side 输出必须是不同文件", "output")
    if center_output.suffix.lower() != ".wav" or side_output.suffix.lower() != ".wav":
        raise argument_error("本地音频分离输出必须使用 .wav", "output")
    if sample_rate is not None:
        try:
            sample_rate = int(sample_rate)
        except (TypeError, ValueError) as exc:
            raise argument_error("sample_rate 必须是整数", "sample_rate") from exc
        if sample_rate not in {8_000, 16_000, 22_050, 24_000, 32_000, 44_100, 48_000, 96_000}:
            raise argument_error("sample_rate 不在本地音频白名单内", "sample_rate")
    if center_output.exists() or side_output.exists():
        raise argument_error("音频分离输出已存在，为避免覆盖请指定新的输出路径", "output")
    center_output.parent.mkdir(parents=True, exist_ok=True)
    side_output.parent.mkdir(parents=True, exist_ok=True)
    filter_graph = (
        "[0:a:0]aformat=channel_layouts=stereo,asplit=2[center_in][side_in];"
        "[center_in]pan=mono|c0=0.5*c0+0.5*c1[center];"
        "[side_in]pan=stereo|c0=0.5*c0-0.5*c1|c1=0.5*c1-0.5*c0[side]"
    )
    command = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        filter_graph,
        "-map",
        "[center]",
        "-c:a",
        "pcm_s16le",
    ]
    if sample_rate is not None:
        command.extend(["-ar", str(sample_rate)])
    command.extend([str(center_output), "-map", "[side]", "-c:a", "pcm_s16le"])
    if sample_rate is not None:
        command.extend(["-ar", str(sample_rate)])
    command.append(str(side_output))
    result = run_process(command, timeout=900)
    if result.returncode != 0 or not center_output.exists() or not side_output.exists() or center_output.stat().st_size == 0 or side_output.stat().st_size == 0:
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError(
            "AUDIO_SEPARATION_FAILED",
            "本地 FFmpeg mid/side 音频分离失败",
            exit_code=6,
            retryable=True,
            path=str(source),
            cause=(result.stderr or result.stdout)[-4000:],
        )
    center_probe = probe_media(center_output)
    side_probe = probe_media(side_output)
    if not center_probe.get("audio", {}).get("codec") or not side_probe.get("audio", {}).get("codec"):
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError("AUDIO_SEPARATION_INVALID", "音频分离输出缺少可读音频流", exit_code=6, path=str(center_output))
    return {
        "version": AUDIO_SEPARATION_VERSION,
        "engine": AUDIO_SEPARATION_ENGINE,
        "network": "disabled",
        "method": "mid-side",
        "source": str(source),
        "source_sha256": f"sha256:{sha256_file(source)}",
        "input_probe": input_probe,
        "stems": {
            "center": {"output": str(center_output), "sha256": f"sha256:{sha256_file(center_output)}", "probe": center_probe},
            "side": {"output": str(side_output), "sha256": f"sha256:{sha256_file(side_output)}", "probe": side_probe},
        },
        "warnings": [
            {
                "code": "AUDIO_SEPARATION_APPROXIMATE",
                "message": "mid/side 只利用声道相位，不能替代 Demucs、UVR 或其他本地 AI 源分离模型；中心声泄漏和相位伪影需要人工复核",
            }
        ],
    }
