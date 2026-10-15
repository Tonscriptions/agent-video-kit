"""Deterministic local audio stem approximations.

The built-in adapter exposes a transparent mid/side split.  It is useful for
rough center-channel vocal reduction and ambience extraction, but it is not an
AI source-separation model.  Model-backed adapters must be registered and
audited separately before they can be added to this module.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .audio_tools import inspect_audio_source
from .errors import AppError, argument_error
from .media import ffmpeg_path, probe_media
from .utils import run_process, sha256_file


AUDIO_SEPARATION_VERSION = "0.1.0"
AUDIO_SEPARATION_ENGINE = "ffmpeg-local-mid-side-v1"
AUDIO_SEPARATION_COMMAND_PROTOCOL = "agent-video-audio-separation-v1"
SUPPORTED_AUDIO_SAMPLE_RATES = {8_000, 16_000, 22_050, 24_000, 32_000, 44_100, 48_000, 96_000}


def _validate_sample_rate(sample_rate: int | None) -> int | None:
    if sample_rate is None:
        return None
    try:
        normalized = int(sample_rate)
    except (TypeError, ValueError) as exc:
        raise argument_error("sample_rate 必须是整数", "sample_rate") from exc
    if normalized not in SUPPORTED_AUDIO_SAMPLE_RATES:
        raise argument_error("sample_rate 不在本地音频白名单内", "sample_rate")
    return normalized


def _runner_command(executable: Path) -> list[str]:
    """Build a non-shell command for a registered local runner.

    Python runners are useful for reproducible adapter shims on Windows, where
    a ``.py`` file is not itself an executable.  Native executables are
    launched directly.  Batch files are intentionally rejected: invoking a
    shell would make the local-only policy and argument boundary ambiguous.
    """
    suffix = executable.suffix.lower()
    if suffix in {".cmd", ".bat"}:
        raise AppError(
            "AUDIO_SEPARATION_RUNNER_UNSAFE",
            "command-json-v1 不允许通过 .cmd/.bat shell runner 执行",
            exit_code=10,
            path=str(executable),
        )
    if suffix == ".py":
        return [sys.executable, str(executable)]
    return [str(executable)]


def separate_command_json(
    source: Path,
    center_output: Path,
    side_output: Path,
    *,
    adapter_id: str,
    model_path: Path,
    executable: Path,
    sample_rate: int | None = None,
    timeout: float = 1800.0,
) -> dict[str, Any]:
    """Run a registered local adapter using the strict JSON stem protocol.

    The runner receives one JSON object on stdin and must return one JSON
    object on stdout.  It must write exactly the requested center and side WAV
    paths; arbitrary alternate outputs are rejected so that the Agent can
    audit the generated assets.  The executable and model are already hash
    verified by the CLI before this function is called.
    """
    source = source.expanduser().resolve()
    center_output = center_output.expanduser().resolve()
    side_output = side_output.expanduser().resolve()
    model_path = model_path.expanduser().resolve()
    executable = executable.expanduser().resolve()
    sample_rate = _validate_sample_rate(sample_rate)
    if not source.is_file():
        raise AppError("AUDIO_SEPARATION_SOURCE_MISSING", f"本地音频源不存在: {source}", exit_code=3, path=str(source))
    if not model_path.exists():
        raise AppError("MODEL_PATH_MISSING", f"本地模型路径不存在: {model_path}", exit_code=10, path=str(model_path))
    if not executable.is_file():
        raise AppError("MODEL_EXECUTABLE_MISSING", f"本地适配器 executable 不存在: {executable}", exit_code=10, path=str(executable))
    if center_output == side_output:
        raise argument_error("center 和 side 输出必须是不同文件", "output")
    if center_output.exists() or side_output.exists():
        raise argument_error("音频分离输出已存在，为避免覆盖请指定新的输出路径", "output")
    center_output.parent.mkdir(parents=True, exist_ok=True)
    side_output.parent.mkdir(parents=True, exist_ok=True)
    request = {
        "protocol": AUDIO_SEPARATION_COMMAND_PROTOCOL,
        "adapter_id": str(adapter_id),
        "engine": "command-json-v1",
        "network": "disabled",
        "source": {"path": str(source), "sha256": f"sha256:{sha256_file(source)}"},
        "model": {"path": str(model_path)},
        "outputs": {"center": str(center_output), "side": str(side_output)},
        "sample_rate": sample_rate,
    }
    command = _runner_command(executable)
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(request, ensure_ascii=False) + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(source.parent),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError("AUDIO_SEPARATION_RUNNER_TIMEOUT", "command-json-v1 本地 runner 超时", exit_code=6, retryable=True, path=str(executable), cause=str(exc)) from exc
    except OSError as exc:
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError("AUDIO_SEPARATION_RUNNER_START_FAILED", "无法启动 command-json-v1 本地 runner", exit_code=10, path=str(executable), cause=str(exc)) from exc
    if completed.returncode != 0:
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError(
            "AUDIO_SEPARATION_RUNNER_FAILED",
            "command-json-v1 本地 runner 返回失败",
            exit_code=6,
            retryable=True,
            path=str(executable),
            cause=(completed.stderr or completed.stdout)[-4000:],
        )
    if len(completed.stdout) > 1_000_000:
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError("AUDIO_SEPARATION_PROTOCOL_INVALID", "command-json-v1 runner stdout 超过协议大小限制", exit_code=10, path=str(executable))
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError("AUDIO_SEPARATION_PROTOCOL_INVALID", "command-json-v1 runner stdout 不是单个 JSON 对象", exit_code=10, path=str(executable), cause=completed.stdout[-2000:]) from exc
    if not isinstance(response, dict) or response.get("protocol") != AUDIO_SEPARATION_COMMAND_PROTOCOL or response.get("status") != "ok":
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError("AUDIO_SEPARATION_PROTOCOL_INVALID", "command-json-v1 runner 返回的 protocol/status 无效", exit_code=10, path=str(executable), cause=json.dumps(response, ensure_ascii=False)[:4000])
    returned = response.get("stems") if isinstance(response.get("stems"), dict) else {}
    for stem, expected in (("center", center_output), ("side", side_output)):
        returned_path = returned.get(stem)
        if not returned_path or Path(str(returned_path)).expanduser().resolve() != expected:
            center_output.unlink(missing_ok=True)
            side_output.unlink(missing_ok=True)
            raise AppError("AUDIO_SEPARATION_PROTOCOL_INVALID", f"runner 未返回约定的 {stem} 输出路径", exit_code=10, path=str(executable))
    if not center_output.is_file() or not side_output.is_file() or center_output.stat().st_size == 0 or side_output.stat().st_size == 0:
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError("AUDIO_SEPARATION_OUTPUT_INVALID", "command-json-v1 runner 没有生成非空 center/side 输出", exit_code=6, retryable=True, path=str(executable))
    try:
        center_probe = probe_media(center_output)
        side_probe = probe_media(side_output)
    except AppError as exc:
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError("AUDIO_SEPARATION_OUTPUT_INVALID", "command-json-v1 输出无法通过本地媒体探测", exit_code=6, retryable=True, path=str(center_output), cause=json.dumps(exc.as_dict(), ensure_ascii=False)) from exc
    if not center_probe.get("audio", {}).get("codec") or not side_probe.get("audio", {}).get("codec"):
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise AppError("AUDIO_SEPARATION_OUTPUT_INVALID", "command-json-v1 输出缺少可读音频流", exit_code=6, path=str(center_output))
    return {
        "version": AUDIO_SEPARATION_VERSION,
        "engine": "command-json-v1",
        "protocol": AUDIO_SEPARATION_COMMAND_PROTOCOL,
        "network": "disabled",
        "method": "command-json",
        "adapter_id": str(adapter_id),
        "source": str(source),
        "source_sha256": f"sha256:{sha256_file(source)}",
        "runner": str(executable),
        "model": str(model_path),
        "stems": {
            "center": {"output": str(center_output), "sha256": f"sha256:{sha256_file(center_output)}", "probe": center_probe},
            "side": {"output": str(side_output), "sha256": f"sha256:{sha256_file(side_output)}", "probe": side_probe},
        },
        "runner_response": response,
        "warnings": [
            {
                "code": "AUDIO_SEPARATION_LOCAL_RUNNER_REVIEW",
                "message": "command-json-v1 已通过本地协议生成 center/side；分离质量、模型许可和输出内容仍需按项目 golden 与 Rights Ledger 复核",
            }
        ],
    }


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
    sample_rate = _validate_sample_rate(sample_rate)
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
