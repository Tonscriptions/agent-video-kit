from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error, dependency_error
from .media import ffmpeg_path
from .captions import write_srt_file
from .utils import run_process, sha256_file


def _decode_audio(path: Path, sample_rate: int = 16_000) -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise dependency_error("本地转写需要 numpy", "安装本地依赖后重试") from exc
    try:
        result = subprocess.run(
            [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"],
            capture_output=True,
            timeout=1800,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AppError("LOCAL_ASR_AUDIO_FAILED", "本地转写音频解码失败", exit_code=6, retryable=True, cause=str(exc)) from exc
    if result.returncode != 0 or not result.stdout:
        raise AppError("LOCAL_ASR_AUDIO_FAILED", "FFmpeg 无法解码本地音频", exit_code=3, cause=result.stderr[-2000:])
    return np.frombuffer(result.stdout, dtype=np.float32)


def _as_float(value: Any, default: float = 0.0) -> float:
    """Convert scalar tensors and numpy values without making either required."""
    try:
        if hasattr(value, "item"):
            value = value.item()
        return float(value)
    except (TypeError, ValueError):
        return default


def _segment_text(processor: Any, tokens: Any) -> str:
    if tokens is None:
        return ""
    try:
        if hasattr(tokens, "detach"):
            tokens = tokens.detach().cpu()
        decoded = processor.batch_decode([tokens], skip_special_tokens=True)
        return decoded[0].strip() if decoded else ""
    except Exception:
        return ""


def _extract_segments(processor: Any, generated: Any) -> list[dict[str, Any]]:
    """Normalize Transformers Whisper segment output for the project schema."""
    raw = generated.get("segments") if isinstance(generated, dict) else getattr(generated, "segments", None)
    if not raw:
        return []
    # Transformers returns one segment list per batch item.
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        batches = [raw]
    else:
        batches = raw
    first_batch = batches[0] if batches else []
    segments: list[dict[str, Any]] = []
    for item in first_batch:
        if not isinstance(item, dict):
            continue
        start = _as_float(item.get("start"))
        end = _as_float(item.get("end"), start)
        text = _segment_text(processor, item.get("tokens"))
        if not text:
            result = item.get("result")
            sequence = result.get("sequences") if isinstance(result, dict) else getattr(result, "sequences", None)
            if sequence is not None:
                text = _segment_text(processor, sequence[0] if getattr(sequence, "ndim", 1) > 1 else sequence)
        if end <= start and not text:
            continue
        segments.append({"start": round(start, 3), "end": round(max(start, end), 3), "text": text})
    return segments


def transcribe_local(path: Path, *, model_path: str | Path | None, language: str | None = None) -> dict[str, Any]:
    if not model_path:
        raise argument_error("启用本地转写时必须提供 --model-path；不会自动下载模型", "--model-path")
    model = Path(model_path).expanduser().resolve()
    if not model.exists() or not model.is_dir():
        raise AppError("LOCAL_ASR_MODEL_MISSING", f"本地 ASR 模型目录不存在: {model}", exit_code=10, path=str(model), hint="准备离线模型目录后重试；运行时不会联网下载")
    try:
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    except ImportError as exc:
        raise dependency_error("本地转写需要 transformers 和 torch", "安装本地依赖后重试") from exc
    audio = _decode_audio(path)
    # Override inherited environment values so an Agent cannot accidentally turn
    # an offline project into a model download request.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        processor = AutoProcessor.from_pretrained(str(model), local_files_only=True)
        speech_model = AutoModelForSpeechSeq2Seq.from_pretrained(str(model), local_files_only=True, torch_dtype=torch.float32)
    except Exception as exc:
        raise AppError("LOCAL_ASR_MODEL_LOAD_FAILED", "本地 ASR 模型加载失败", exit_code=10, path=str(model), cause=str(exc), hint="模型必须完整保存在本地，且与 transformers 兼容") from exc
    speech_model.to("cpu")
    inputs = processor(audio, sampling_rate=16_000, return_tensors="pt")
    generate_kwargs: dict[str, Any] = {"return_timestamps": True}
    if language:
        generate_kwargs["language"] = language
        generate_kwargs["task"] = "transcribe"
    try:
        with torch.no_grad():
            try:
                generated = speech_model.generate(
                    **inputs,
                    **generate_kwargs,
                    return_segments=True,
                    return_dict_in_generate=True,
                )
            except TypeError:
                # Older Transformers releases may not expose return_segments.
                generated = speech_model.generate(**inputs, **generate_kwargs)
    except Exception as exc:
        raise AppError("LOCAL_ASR_FAILED", "本地 ASR 推理失败", exit_code=6, retryable=True, cause=str(exc)) from exc
    segments = _extract_segments(processor, generated)
    sequences = generated.get("sequences") if isinstance(generated, dict) else getattr(generated, "sequences", generated)
    try:
        decoded = processor.batch_decode(sequences, skip_special_tokens=True)
    except Exception as exc:
        raise AppError("LOCAL_ASR_FAILED", "本地 ASR 文本解码失败", exit_code=6, retryable=True, cause=str(exc)) from exc
    text = decoded[0].strip() if decoded else ""
    if segments:
        # Keep segment text authoritative when the model returned timestamp chunks.
        text = " ".join(item["text"] for item in segments if item.get("text")).strip() or text
    return {
        "status": "ok",
        "provider": "transformers-local",
        "model_path": str(model),
        "language": language,
        "text": text,
        "segments": segments,
        "timed": bool(segments),
        "network": "disabled",
    }


_WHISPER_LANGUAGE_RE = re.compile(r"^(?:auto|[A-Za-z]{2,8}(?:-[A-Za-z]{2,8})?)$")


def _escape_ffmpeg_filter_value(value: str) -> str:
    """Escape a local path for an FFmpeg filter option.

    FFmpeg filter arguments use ``:`` as a separator, which is also present
    in Windows drive letters.  Keeping this escaping in one small function
    prevents model and destination paths from being interpolated unsafely into
    the filter graph.
    """
    escaped = str(value).replace("\\", "/")
    for character in ("\\", ":", ",", "[", "]", "'", "="):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def ffmpeg_whisper_available() -> bool:
    """Return whether the configured local FFmpeg exposes ``whisper``."""
    try:
        result = run_process([ffmpeg_path(), "-hide_banner", "-filters"], timeout=30)
    except AppError:
        return False
    if result.returncode != 0:
        return False
    return any(re.search(r"\bwhisper\b", line) for line in (result.stdout + "\n" + result.stderr).splitlines())


def transcribe_local_ffmpeg_whisper(
    path: Path,
    *,
    model_path: str | Path | None,
    output_srt: Path,
    language: str | None = None,
    use_gpu: bool = False,
) -> dict[str, Any]:
    """Run FFmpeg's bundled whisper.cpp filter against an explicit local model.

    The model is never downloaded.  FFmpeg writes an SRT sidecar through the
    filter's ``destination`` option, while its audio output is discarded.  A
    native FFmpeg whisper build therefore works without Python ML packages and
    still produces the same timestamped segment shape as the Transformers
    adapter.
    """
    raw_source = str(path).strip()
    if raw_source.lower().startswith(("http://", "https://")):
        raise argument_error("本地 FFmpeg Whisper 不接受远程输入", "input")
    source = Path(raw_source).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise AppError("LOCAL_ASR_AUDIO_MISSING", f"本地 ASR 输入不存在: {source}", exit_code=3, path=str(source))
    if not model_path:
        raise argument_error("ffmpeg-whisper 引擎必须提供本地模型文件", "model_path")
    model = Path(model_path).expanduser().resolve()
    if not model.exists() or not model.is_file() or model.stat().st_size <= 0:
        raise AppError("LOCAL_ASR_MODEL_MISSING", f"本地 Whisper 模型文件不存在或为空: {model}", exit_code=10, path=str(model), hint="准备离线 whisper.cpp 模型文件；运行时不会联网下载")
    if not ffmpeg_whisper_available():
        raise AppError("LOCAL_ASR_WHISPER_UNAVAILABLE", "当前本地 FFmpeg 未提供 whisper 滤镜", exit_code=10, hint="运行 ffmpeg -filters 检查 whisper；或改用 transformers 本地模型适配器")
    language_value = str(language or "auto").strip()
    if not _WHISPER_LANGUAGE_RE.fullmatch(language_value):
        raise argument_error("language 只能是 auto 或 ASCII 语言代码", "language")
    destination = Path(output_srt).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    model_value = _escape_ffmpeg_filter_value(str(model))
    destination_value = _escape_ffmpeg_filter_value(str(destination))
    filter_spec = (
        f"whisper=model={model_value}:language={language_value}:"
        f"use_gpu={'true' if use_gpu else 'false'}:destination={destination_value}:format=srt"
    )
    try:
        result = run_process(
            [
                ffmpeg_path(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-af",
                filter_spec,
                "-f",
                "null",
                "-",
            ],
            timeout=3600,
        )
    except AppError:
        destination.unlink(missing_ok=True)
        raise
    if result.returncode != 0 or not destination.exists() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise AppError(
            "LOCAL_ASR_WHISPER_FAILED",
            "FFmpeg whisper 本地转写失败",
            exit_code=6,
            retryable=True,
            path=str(destination),
            cause=(result.stderr or result.stdout)[-4000:],
            hint="检查 whisper.cpp 模型格式、音频流和 FFmpeg 构建；不会自动下载模型",
        )
    try:
        from .captions import parse_caption_file, validate_cues

        cues = parse_caption_file(destination)
    except AppError as exc:
        destination.unlink(missing_ok=True)
        raise AppError(
            "LOCAL_ASR_TIMESTAMPS_INVALID",
            "FFmpeg whisper 生成的 SRT 无法解析",
            exit_code=6,
            path=str(destination),
            cause=str(exc),
        ) from exc
    validation = validate_cues(cues)
    if not validation["ok"]:
        destination.unlink(missing_ok=True)
        raise AppError("LOCAL_ASR_TIMESTAMPS_INVALID", "FFmpeg whisper 生成的 SRT 时间轴无效", exit_code=6, path=str(destination), cause=str(validation["errors"]))
    return {
        "status": "ok" if cues else "empty",
        "provider": "ffmpeg-whisper-local",
        "engine": "ffmpeg-whisper-local",
        "model_path": str(model),
        "model_sha256": f"sha256:{sha256_file(model)}",
        "language": language_value,
        "text": " ".join(str(item.get("text", "")).strip() for item in cues).strip(),
        "segments": cues,
        "timed": bool(cues),
        "srt": str(destination),
        "network": "disabled",
        "use_gpu": bool(use_gpu),
    }


def write_srt(transcription: dict[str, Any], path: Path) -> None:
    segments = transcription.get("segments") or []
    if not segments:
        raise AppError("LOCAL_ASR_TIMESTAMPS_MISSING", "当前本地模型没有可写入 SRT 的时间戳", exit_code=4, path=str(path))
    lines: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        lines.append({"index": index, "start": start, "end": end, "text": str(segment.get("text", "")).strip()})
    write_srt_file(path, lines)
