"""Registered native Whisper inference. Weights and Python are explicit inputs."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .captions import validate_cues
from .errors import AppError, argument_error
from .media import ffmpeg_path, probe_media
from .policy import resolve_local_path
from .utils import atomic_write_json, assert_id, new_id, now_iso, run_process, sha256_bytes, sha256_file

ASR_ENGINE = "transformers-whisper-local-v1"
ASR_PROTOCOL = "agent-video-whisper-asr-v1"
ASR_VERSION = "0.1.0"


def asr_registry(project: dict[str, Any]) -> dict[str, Any]:
    value = project.get("extensions", {}).get("local_asr", {})
    if not isinstance(value, dict) or not isinstance(value.get("adapters", []), list) or any(not isinstance(x, dict) for x in value.get("adapters", [])):
        raise AppError("ASR_REGISTRY_INVALID", "extensions.local_asr.adapters 必须为对象数组", exit_code=2)
    return value


def registry_item(project: dict[str, Any], adapter_id: str) -> dict[str, Any]:
    for item in asr_registry(project).get("adapters", []):
        if item.get("adapter_id") == adapter_id:
            return item
    raise AppError("ASR_REGISTRATION_NOT_FOUND", f"找不到本地 ASR 模型: {adapter_id}", exit_code=3)


def _local(root: Path, value: str | Path, field: str, *, directory: bool = False) -> Path:
    path = resolve_local_path(root, value, field=field)
    if str(path).startswith("\\\\") or not (path.is_dir() if directory else path.is_file()):
        raise AppError("ASR_LOCAL_PATH_INVALID", "需要现有本地路径", exit_code=10, path=field)
    return path


def _model_files(model: Path) -> list[Path]:
    required = {"config.json", "preprocessor_config.json", "tokenizer_config.json", "tokenizer.json", "generation_config.json", "vocab.json", "merges.txt"}
    for name in sorted(required):
        if not (model / name).is_file():
            raise AppError("ASR_MODEL_INCOMPLETE", f"缺少模型组件: {name}", exit_code=10)
    try:
        for name in ("config.json", "tokenizer_config.json", "preprocessor_config.json", "generation_config.json"):
            config = json.loads((model / name).read_text(encoding="utf-8"))
            if not isinstance(config, dict) or config.get("auto_map") or config.get("custom_pipelines"):
                raise ValueError("Custom model code is unsupported")
            if name == "config.json" and config.get("model_type") != "whisper":
                raise ValueError("Only Whisper safetensors models are supported")
        index = model / "model.safetensors.index.json"
        if index.is_file():
            values = json.loads(index.read_text(encoding="utf-8"))["weight_map"].values()
            weights = set(values)
            if not weights:
                raise ValueError("Empty weight map")
        else:
            weights = {"model.safetensors"}
        for name in weights:
            path = model / name
            if Path(name).is_absolute() or ".." in Path(name).parts or path.suffix != ".safetensors" or not path.resolve().is_relative_to(model) or not path.is_file() or not path.stat().st_size:
                raise ValueError(f"Missing or invalid local safetensors shard: {name}")
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
        raise AppError("ASR_MODEL_INVALID", "Whisper 模型配置或权重不完整，禁止自定义代码", exit_code=10, cause=str(exc)) from exc
    files = sorted(p for p in model.rglob("*") if p.is_file() and p.suffix in {".json", ".txt", ".safetensors"})
    if any(p.suffix == ".py" for p in model.rglob("*")) or any(p.is_symlink() or not p.resolve().is_relative_to(model) for p in files):
        raise AppError("ASR_MODEL_INVALID", "模型目录不能包含代码或指向目录外的组件", exit_code=10)
    return files


def _entry(path: Path, role: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AppError("ASR_ARTIFACT_INVALID", "ASR 组件必须为本地普通文件", exit_code=10)
    return {"path": str(path.resolve()), "role": role, "bytes": path.stat().st_size, "sha256": "sha256:" + sha256_file(path)}


def manifest_hash(record: dict[str, Any]) -> str:
    fields = {key: record.get(key) for key in ("adapter_id", "engine", "protocol", "python_executable", "model_path", "device", "threads", "artifacts")}
    return "sha256:" + sha256_bytes(json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def prepare_adapter(root: Path, *, adapter_id: str, python_executable: str, model_path: str, device: str, threads: int, evidence: str, license_spdx: str, creator: str, status: str, uses: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    assert_id(adapter_id, "adapter_id")
    if device not in {"cpu", "cuda"} or not 1 <= threads <= 32 or status not in {"unverified", "verified", "restricted"}:
        raise argument_error("ASR device 只能为 cpu/cuda，threads 必须为 1–32", "device/threads")
    python = _local(root, python_executable, "python_executable")
    model, proof = _local(root, model_path, "model_path", directory=True), _local(root, evidence, "evidence")
    if python.suffix.lower() != ".exe":
        raise argument_error("ASR 仅支持显式原生 Windows Python .exe", "python_executable")
    entries = [_entry(python, "python"), _entry(proof, "evidence")]
    entries.extend(_entry(p, "model") for p in _model_files(model))
    record = {"adapter_id": adapter_id, "engine": ASR_ENGINE, "protocol": ASR_PROTOCOL, "python_executable": str(python), "model_path": str(model), "device": device, "threads": threads, "artifacts": entries, "rights_ref": f"asr_adapter_{adapter_id}", "registered_at": now_iso(), "network": "disabled"}
    record["sha256"] = manifest_hash(record)
    rights = {"asset_id": record["rights_ref"], "kind": "asr-model-adapter", "sha256": record["sha256"], "source_url": f"local://asr/{adapter_id}", "source_version": ASR_VERSION, "retrieved_at": now_iso(), "creator": creator, "license_spdx": license_spdx, "license_url": "", "attribution": "", "permitted_uses": list(dict.fromkeys(uses or ["internal"])), "permitted_channels": [], "restrictions": [], "derived_from": [], "evidence": str(proof), "verification_status": status, "verified_by": "explicit-local-registration" if status == "verified" else "", "takedown_status": "clear", "notes": "Explicit offline ASR evidence; model and source rights need separate review"}
    return record, rights


def verify_adapter(record: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    entries = record.get("artifacts", [])
    if not isinstance(entries, list) or not entries or record.get("sha256") != manifest_hash(record) or record.get("engine") != ASR_ENGINE or record.get("protocol") != ASR_PROTOCOL or record.get("rights_ref") != f"asr_adapter_{record.get('adapter_id')}" or record.get("network") != "disabled" or record.get("device") not in {"cpu", "cuda"} or type(record.get("threads")) is not int or not 1 <= record["threads"] <= 32:
        return {"ok": False, "findings": [{"code": "ASR_MANIFEST_INVALID"}], "checked_files": 0}
    try:
        model = Path(record["model_path"])
        expected = {(str(p.resolve()), "model") for p in _model_files(model)}
        expected.add((record["python_executable"], "python"))
        actual = {(item["path"], item["role"]) for item in entries}
        if not expected.issubset(actual) or len(actual) != len(entries) or len(actual - expected) != 1 or next(iter(actual - expected))[1] != "evidence":
            findings.append({"code": "ASR_MANIFEST_INVENTORY_CHANGED"})
        for item in entries:
            path = Path(item["path"])
            if path.is_symlink() or not path.is_file() or path.stat().st_size != item["bytes"] or "sha256:" + sha256_file(path) != item["sha256"]:
                findings.append({"code": "ASR_ARTIFACT_HASH_MISMATCH", "path": str(path)})
    except (AppError, OSError, KeyError, TypeError, ValueError) as exc:
        findings.append({"code": "ASR_ARTIFACT_INVALID", "message": str(exc)})
    return {"ok": not findings, "findings": findings, "checked_files": len(entries), "network": "disabled"}


def checked_transcription(value: Any, duration: float) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("status") != "ok" or value.get("network") != "disabled" or not isinstance(value.get("segments"), list) or not value["segments"] or not isinstance(value.get("warnings", []), list) or not math.isfinite(duration) or duration <= 0:
        raise AppError("ASR_RESULT_INVALID", "本地 ASR 未返回有效时码字幕", exit_code=6)
    previous_end = 0.0
    for cue in value["segments"]:
        try:
            if not isinstance(cue, dict) or isinstance(cue.get("start"), bool) or isinstance(cue.get("end"), bool):
                raise ValueError("Invalid cue shape")
            start, end = float(cue["start"]), float(cue["end"])
            if not isinstance(cue.get("text"), str) or not cue["text"].strip() or not all(math.isfinite(x) for x in (start, end)) or start < previous_end - 1e-6 or start < 0 or end <= start or end > duration + 0.04:
                raise ValueError("Empty, non-finite, overlapping or out-of-range cue")
            # Whisper timestamps use a 20ms grid; only the final rounding tail
            # may be clipped to the independently probed duration.
            if end > duration:
                cue["end"] = duration
                value.setdefault("warnings", []).append("ASR_TIMESTAMP_END_CLAMPED")
            previous_end = min(end, duration)
        except (TypeError, ValueError, KeyError) as exc:
            raise AppError("ASR_RESULT_INVALID", "本地 ASR 字幕文本或时码无效", exit_code=6, cause=str(exc)) from exc
    report = validate_cues(value["segments"], duration=duration)
    if not report["ok"]:
        raise AppError("ASR_RESULT_INVALID", "本地 ASR 时码校验失败", exit_code=6)
    value["text"] = " ".join(cue["text"].strip() for cue in value["segments"])
    value["timed"] = True
    return value


def transcribe_registered(root: Path, source: Path, *, adapter: dict[str, Any], language: str | None) -> dict[str, Any]:
    source = _local(root, source, "input")
    verification = verify_adapter(adapter)
    if not verification["ok"]:
        raise AppError("ASR_INTEGRITY_FAILED", "登记的 ASR 模型或执行器已改变", exit_code=10, cause=json.dumps(verification, ensure_ascii=False))
    probe = probe_media(source)
    duration = float(probe.get("duration_seconds") or 0)
    if not probe.get("audio", {}).get("codec") or not math.isfinite(duration) or duration <= 0:
        raise argument_error("ASR 输入必须包含有效音频", "input")
    source_hash = "sha256:" + sha256_file(source)
    job = root / "cache" / "asr" / new_id("run")
    job.mkdir(parents=True, exist_ok=False)
    pcm, response = job / "input.wav", job / "response.json"
    decoded = run_process([ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(source), "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(pcm)], timeout=1800)
    if decoded.returncode:
        raise AppError("ASR_AUDIO_DECODE_FAILED", "本地 ASR 音频准备失败", exit_code=6, cause=decoded.stderr[-1500:])
    worker = Path(__file__).with_name("whisper_worker.py")
    request_path = job / "request.json"
    request = {"protocol": ASR_PROTOCOL, "network": "disabled", "adapter": adapter, "input": str(pcm), "input_sha256": "sha256:" + sha256_file(pcm), "source_sha256": source_hash, "language": language, "response": str(response), "runtime_root": str(job / "runtime")}
    atomic_write_json(request_path, request)
    result = run_process([adapter["python_executable"], "-I", "-B", "-X", "utf8", str(worker), str(request_path)], timeout=3600)
    try:
        payload = json.loads(response.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AppError("ASR_WORKER_FAILED", "离线 ASR worker 未返回有效结果", exit_code=6, cause=result.stderr[-2000:]) from exc
    if result.returncode or not isinstance(payload, dict) or payload.get("protocol") != ASR_PROTOCOL or payload.get("status") != "succeeded" or payload.get("network") != "disabled" or payload.get("blocked_network_events") != [] or payload.get("input_sha256") != request["input_sha256"] or payload.get("source_sha256") != source_hash or payload.get("adapter_sha256") != adapter["sha256"]:
        raise AppError("ASR_WORKER_FAILED", "离线 ASR 协议、完整性或推理失败", exit_code=6, cause=json.dumps(payload, ensure_ascii=False)[-3500:])
    if "sha256:" + sha256_file(source) != source_hash or not verify_adapter(adapter)["ok"]:
        raise AppError("ASR_INTEGRITY_FAILED", "转写过程中模型或源素材发生变化", exit_code=10)
    transcription = checked_transcription(payload.get("transcription"), duration)
    transcription.update({"engine": ASR_ENGINE, "adapter_id": adapter["adapter_id"], "model_sha256": adapter["sha256"], "source_sha256": source_hash, "worker_sha256": "sha256:" + sha256_file(worker), "worker": {key: value for key, value in payload.items() if key != "transcription"}, "review_required": True})
    return transcription
