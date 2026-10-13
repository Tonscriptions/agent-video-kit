from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .media import ffmpeg_path, probe_media
from .utils import atomic_write_text, ensure_inside, run_process, sha256_bytes


_VOICE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SAMPLE_RATES = {8_000, 16_000, 22_050, 24_000, 32_000, 44_100, 48_000}


def _validate_text(text: str) -> str:
    if not isinstance(text, str):
        raise argument_error("TTS 文本必须是字符串", "text")
    normalized = text.replace("\x00", "").strip()
    if not normalized:
        raise argument_error("TTS 文本不能为空", "text")
    if len(normalized) > 20_000:
        raise argument_error("TTS 文本最多 20,000 个字符", "text")
    # FFmpeg's bundled flite build is an English voice engine.  Rejecting
    # non-ASCII input before spawning it also avoids a native flite crash seen
    # with unsupported UTF-8 text on Windows.
    if not normalized.isascii():
        raise AppError(
            "TTS_LOCALE_UNSUPPORTED",
            "当前 FFmpeg flite 适配器只支持 ASCII/英文文本；中文和其他非 ASCII 文本请接入显式本地多语言模型适配器",
            exit_code=2,
            path="text",
            hint="保留 network=disabled；不要让 CLI 自动下载模型",
        )
    if any(ord(char) < 32 and char not in "\r\n\t" for char in normalized):
        raise argument_error("TTS 文本包含不支持的控制字符", "text")
    return normalized


def _validate_voice(voice: str) -> str:
    value = str(voice or "").strip()
    if not _VOICE_RE.fullmatch(value):
        raise argument_error("TTS voice 只能包含 ASCII 字母、数字、下划线或短横线", "voice")
    return value


def synthesize_local_tts(
    root: Path,
    text: str,
    output: Path,
    *,
    operation_id: str,
    voice: str = "kal",
    sample_rate: int = 48_000,
    channels: int = 2,
) -> dict[str, Any]:
    """Synthesize an English voice locally through FFmpeg's bundled flite filter.

    The adapter deliberately writes the text to a project-local temporary file
    and runs FFmpeg with the project as its working directory.  This avoids
    filter-graph quoting problems with Windows absolute paths and keeps all
    intermediate files inside the project runtime boundary.
    """
    root = root.resolve()
    output = ensure_inside(root, output)
    text = _validate_text(text)
    voice = _validate_voice(voice)
    try:
        sample_rate = int(sample_rate)
    except (TypeError, ValueError) as exc:
        raise argument_error("TTS sample rate 必须是整数", "sample_rate") from exc
    if sample_rate not in _SAMPLE_RATES:
        raise argument_error(f"TTS sample rate 必须是 {_SAMPLE_RATES} 之一", "sample_rate")
    try:
        channels = int(channels)
    except (TypeError, ValueError) as exc:
        raise argument_error("TTS channels 必须是整数", "channels") from exc
    if channels not in {1, 2}:
        raise argument_error("TTS channels 只支持 1 或 2", "channels")
    if output.suffix.lower() != ".wav":
        raise argument_error("本地 flite TTS 输出必须使用 .wav", str(output))

    text_file = root / "cache" / "tts" / f"{operation_id}.txt"
    atomic_write_text(text_file, text + "\n")
    relative_text_file = text_file.relative_to(root).as_posix()
    filter_input = f"flite=textfile={relative_text_file}:voice={voice}"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run_process(
            [
                ffmpeg_path(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                filter_input,
                "-ar",
                str(sample_rate),
                "-ac",
                str(channels),
                "-c:a",
                "pcm_s16le",
                str(output),
            ],
            cwd=root,
            timeout=600,
        )
    finally:
        try:
            text_file.unlink()
        except FileNotFoundError:
            pass
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        try:
            output.unlink()
        except FileNotFoundError:
            pass
        raise AppError(
            "TTS_SYNTHESIS_FAILED",
            f"FFmpeg flite TTS 生成失败: {output}",
            exit_code=6,
            retryable=True,
            path=str(output),
            cause=(result.stderr or result.stdout)[-4000:],
            hint="运行 ffmpeg -filters 检查是否包含 flite，并使用本地支持的 voice",
        )
    probe = probe_media(output)
    if not probe.get("audio", {}).get("codec"):
        try:
            output.unlink()
        except FileNotFoundError:
            pass
        raise AppError("TTS_OUTPUT_INVALID", "TTS 输出没有可读音频流", exit_code=6, path=str(output))
    return {
        "engine": "ffmpeg-flite-local",
        "voice": voice,
        "text_sha256": f"sha256:{sha256_bytes(text.encode('utf-8'))}",
        "text_chars": len(text),
        "sample_rate": sample_rate,
        "channels": channels,
        "output": str(output),
        "probe": probe,
    }


def flite_available() -> bool:
    """Return whether the current native FFmpeg exposes the flite filter."""
    try:
        result = run_process([ffmpeg_path(), "-hide_banner", "-filters"], timeout=30)
    except AppError:
        return False
    if result.returncode != 0:
        return False
    return any(re.search(r"\bflite\b", line) for line in (result.stdout + "\n" + result.stderr).splitlines())
