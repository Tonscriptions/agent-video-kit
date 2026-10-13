from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error, dependency_error
from .media import ffmpeg_path
from .captions import write_srt_file


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
