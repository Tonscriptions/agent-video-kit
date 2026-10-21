"""Explicit offline SoulX registration and synthesis; no model discovery/downloads."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .media import ffmpeg_path, probe_media
from .policy import resolve_local_path
from .project import asset_map
from .utils import atomic_write_json, atomic_write_text, assert_id, now_iso, run_process, sha256_bytes, sha256_file


TTS_VERSION = "0.1.0"
SOULX_ENGINE = "soulx-podcast-local-v1"
SOULX_PROTOCOL = "agent-video-soulx-tts-v1"
S3_TOKENIZER_SHA256 = "d43342aa12163a80bf07bffb94c9de2e120a8df2f9917cd2f642e7f4219c6f71"
SAMPLE_RATES = {8000, 16000, 22050, 24000, 32000, 44100, 48000}


def tts_registry(project: dict[str, Any]) -> dict[str, Any]:
    value = project.get("extensions", {}).get("local_tts", {})
    if not isinstance(value, dict) or not isinstance(value.get("adapters", []), list) or not isinstance(value.get("voices", []), list):
        raise AppError("TTS_REGISTRY_INVALID", "extensions.local_tts 必须包含 adapters/voices 数组", exit_code=2)
    return value


def registry_item(project: dict[str, Any], kind: str, item_id: str) -> dict[str, Any]:
    key = "adapter_id" if kind == "adapters" else "voice_id"
    for item in tts_registry(project).get(kind, []):
        if isinstance(item, dict) and item.get(key) == item_id:
            return item
    raise AppError("TTS_REGISTRATION_NOT_FOUND", f"找不到本地 TTS {key}: {item_id}", exit_code=3, path=key)


def add_registration(project: dict[str, Any], kind: str, value: dict[str, Any]) -> None:
    registry = project.setdefault("extensions", {}).setdefault("local_tts", {"schema_version": TTS_VERSION, "adapters": [], "voices": []})
    key = "adapter_id" if kind == "adapters" else "voice_id"
    if any(item.get(key) == value[key] for item in registry.get(kind, [])):
        raise AppError("TTS_REGISTRATION_EXISTS", f"TTS 登记已存在: {value[key]}", exit_code=2, path=key)
    registry.setdefault(kind, []).append(value)
    registry["updated_at"] = now_iso()


def local_path(root: Path, value: str | Path, field: str, *, directory: bool = False) -> Path:
    path = resolve_local_path(root, value, field=field)
    if str(path).startswith("\\\\") or not (path.is_dir() if directory else path.is_file()):
        raise AppError("TTS_LOCAL_PATH_INVALID", f"需要存在的本地{'目录' if directory else '文件'}: {path}", exit_code=10, path=field)
    return path


def validate_text(text: str, *, reference: bool = False) -> str:
    if not isinstance(text, str) or not text.strip():
        raise argument_error("配音文本/参考逐字稿不能为空", "prompt_text" if reference else "text")
    if len(text) > (20000 if reference else 2000):
        raise argument_error("配音文本最多 2000 字符；参考逐字稿最多 20000 字符", "text")
    if any(ord(c) < 32 and c not in "\r\n\t" for c in text):
        raise argument_error("配音文本不能包含 NUL 或其他控制字符", "text")
    # Reference transcripts must retain original wording and script exactly.
    return text if reference else text.strip()


def validate_output(sample_rate: int, channels: int, output: Path) -> None:
    if sample_rate not in SAMPLE_RATES or channels not in {1, 2}:
        raise argument_error("不支持的配音采样率或声道", "sample_rate/channels")
    if output.suffix.lower() != ".wav":
        raise argument_error("本地配音输出必须为 WAV", "output")
    if output.exists():
        raise argument_error("配音输出已存在，请使用新路径", "output")


def _file_entry(path: Path, role: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AppError("TTS_ARTIFACT_INVALID", "模型组件必须为现有普通文件", exit_code=10, path=str(path))
    return {"path": str(path.resolve()), "role": role, "bytes": path.stat().st_size, "sha256": f"sha256:{sha256_file(path)}"}


def _manifest_hash(entries: list[dict[str, Any]]) -> str:
    return "sha256:" + sha256_bytes(json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _rights(item_id: str, kind: str, digest: str, *, evidence: Path, license_spdx: str, creator: str, status: str, uses: list[str], parents: list[str]) -> dict[str, Any]:
    if status not in {"unverified", "verified", "restricted"}:
        raise argument_error("不支持的登记核验状态", "verification_status")
    return {"asset_id": item_id, "kind": kind, "sha256": digest, "source_url": f"local://tts/{item_id}", "source_version": TTS_VERSION, "retrieved_at": now_iso(), "creator": creator, "license_spdx": license_spdx, "license_url": "", "attribution": "", "permitted_uses": list(dict.fromkeys(uses or ["internal"])), "permitted_channels": [], "restrictions": [], "derived_from": parents, "evidence": str(evidence), "verification_status": status, "verified_by": "explicit-local-registration" if status == "verified" else "", "takedown_status": "clear", "notes": "Local evidence supplied explicitly; code licensing does not imply model/voice commercial authorization"}


def prepare_adapter(root: Path, *, adapter_id: str, python_executable: str, source_root: str, package_root: str, model_path: str, tokenizer_path: str, evidence: str, license_spdx: str, creator: str, status: str, uses: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    assert_id(adapter_id, "adapter_id")
    python = local_path(root, python_executable, "python_executable")
    if python.suffix.lower() != ".exe" or "python" not in python.stem.lower():
        raise argument_error("SoulX 需要显式原生 Python .exe", "python_executable")
    source = local_path(root, source_root, "source_root", directory=True)
    packages = local_path(root, package_root, "package_root", directory=True)
    model = local_path(root, model_path, "model_path", directory=True)
    tokenizer = local_path(root, tokenizer_path, "tokenizer_path")
    proof = local_path(root, evidence, "evidence")
    required = ["config.json", "soulxpodcast_config.json", "model.safetensors.index.json", "flow.pt", "hift.pt", "campplus.onnx", "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "special_tokens_map.json", "added_tokens.json", "generation_config.json"]
    try:
        index = json.loads((model / "model.safetensors.index.json").read_text(encoding="utf-8-sig"))
        shards = sorted(set(index["weight_map"].values()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AppError("TTS_MODEL_INCOMPLETE", "需要完整 BF16 safetensors 索引及分片，不会回退 GGUF", exit_code=10, path=str(model)) from exc
    if not shards or any(not isinstance(name, str) or Path(name).name != name or not name.endswith(".safetensors") for name in shards):
        raise argument_error("模型索引包含无效分片路径", "model_path")
    required.extend(shards)
    for name in required:
        if not (model / name).is_file():
            raise AppError("TTS_MODEL_INCOMPLETE", f"缺少本地模型组件: {name}", exit_code=10, path=str(model / name))
    for relative in ["soulxpodcast/utils/parser.py", "soulxpodcast/utils/infer_utils.py", "soulxpodcast/models/soulxpodcast.py", "LICENSE"]:
        if not (source / relative).is_file():
            raise AppError("TTS_SOURCE_INCOMPLETE", f"缺少本地推理源码: {relative}", exit_code=10)
    if not (packages / "s3tokenizer" / "__init__.py").is_file():
        raise AppError("TTS_SOURCE_INCOMPLETE", "本地依赖缺少 s3tokenizer", exit_code=10)
    entries = [_file_entry(python, "python"), _file_entry(proof, "evidence"), _file_entry(tokenizer, "speech-tokenizer")]
    if entries[-1]["sha256"] != f"sha256:{S3_TOKENIZER_SHA256}":
        raise AppError("TTS_TOKENIZER_HASH_MISMATCH", "SoulX v2 语音 tokenizer 与受支持版本不符", exit_code=10, path=str(tokenizer))
    entries.extend(_file_entry(model / name, "model") for name in sorted(set(required)))
    entries.extend(_file_entry(path, "source") for path in sorted((source / "soulxpodcast").rglob("*.py")))
    entries.append(_file_entry(source / "LICENSE", "source-license"))
    entries.extend(_file_entry(path, "s3tokenizer-source") for path in sorted((packages / "s3tokenizer").rglob("*.py")))
    stamp, digest = now_iso(), _manifest_hash(entries)
    record = {"adapter_id": adapter_id, "engine": SOULX_ENGINE, "python_executable": str(python), "source_root": str(source), "package_root": str(packages), "model_path": str(model), "tokenizer_path": str(tokenizer), "artifacts": entries, "sha256": digest, "rights_ref": f"tts_adapter_{adapter_id}", "network": "disabled", "registered_at": stamp, "precision": "llm-bf16-flow-fp16", "device": "cuda", "llm_engine": "hf", "protocol": SOULX_PROTOCOL}
    rights = _rights(record["rights_ref"], "tts-model-adapter", digest, evidence=proof, license_spdx=license_spdx, creator=creator, status=status, uses=uses, parents=[])
    return record, rights


def verify_adapter(adapter: dict[str, Any]) -> dict[str, Any]:
    findings = []
    entries = adapter.get("artifacts", [])
    if not entries or adapter.get("engine") != SOULX_ENGINE or adapter.get("sha256") != _manifest_hash(entries):
        findings.append({"code": "TTS_ADAPTER_MANIFEST_INVALID"})
    for item in entries:
        path = Path(str(item.get("path", "")))
        try:
            if not path.is_file() or path.is_symlink():
                findings.append({"code": "TTS_ARTIFACT_MISSING", "path": str(path)})
            elif path.stat().st_size != item.get("bytes") or f"sha256:{sha256_file(path)}" != item.get("sha256"):
                findings.append({"code": "TTS_ARTIFACT_HASH_MISMATCH", "path": str(path)})
        except OSError as exc:
            findings.append({"code": "TTS_ARTIFACT_UNREADABLE", "path": str(path), "message": str(exc)})
    # Prevent a changed path field from bypassing an otherwise intact manifest.
    paths = {(entry.get("role"), entry.get("path")) for entry in entries}
    for key, role in [("python_executable", "python"), ("tokenizer_path", "speech-tokenizer")]:
        if (role, adapter.get(key)) not in paths:
            findings.append({"code": "TTS_ADAPTER_PATH_MISMATCH", "field": key})
    for key, role, relative in [("model_path", "model", "config.json"), ("source_root", "source", "soulxpodcast/utils/infer_utils.py"), ("package_root", "s3tokenizer-source", "s3tokenizer/__init__.py")]:
        expected_path = str((Path(str(adapter.get(key, ""))) / relative).resolve())
        if (role, expected_path) not in paths:
            findings.append({"code": "TTS_ADAPTER_PATH_MISMATCH", "field": key})
    return {"ok": not findings, "findings": findings, "checked_files": len(entries), "network": "disabled"}


def prepare_voice(root: Path, project: dict[str, Any], *, voice_id: str, asset_id: str, prompt_text: str, evidence: str, license_spdx: str, creator: str, status: str, uses: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    assert_id(voice_id, "voice_id")
    prompt = validate_text(prompt_text, reference=True)
    asset = asset_map(project).get(asset_id)
    if not asset or asset.get("kind") != "audio":
        raise argument_error("参考声必须为已登记的本地 audio 资产", "asset_id")
    audio = local_path(root, asset.get("uri", ""), "asset_id")
    proof = local_path(root, evidence, "evidence")
    actual = f"sha256:{sha256_file(audio)}"
    if actual != asset.get("sha256"):
        raise AppError("TTS_REFERENCE_HASH_MISMATCH", "参考声资产已变化，请先重新登记", exit_code=10)
    probe = probe_media(audio)
    duration = float(probe.get("duration_seconds") or 0)
    if not probe.get("audio", {}).get("codec") or not math.isfinite(duration) or not 1 <= duration <= 60:
        raise argument_error("参考声必须是 1–60 秒的可读单人音频；推荐 5–15 秒", "asset_id")
    record = {"voice_id": voice_id, "asset_id": asset_id, "reference_rights_ref": str(asset.get("rights_ref") or asset_id), "audio_sha256": actual, "prompt_text": prompt, "prompt_text_sha256": f"sha256:{sha256_bytes(prompt.encode('utf-8'))}", "evidence": str(proof), "evidence_sha256": f"sha256:{sha256_file(proof)}", "rights_ref": f"tts_voice_{voice_id}", "registered_at": now_iso(), "duration_seconds": duration}
    record["sha256"] = "sha256:" + sha256_bytes((record["audio_sha256"] + record["prompt_text_sha256"] + record["evidence_sha256"]).encode("ascii"))
    return record, _rights(record["rights_ref"], "tts-voice", record["sha256"], evidence=proof, license_spdx=license_spdx, creator=creator, status=status, uses=uses, parents=[record["reference_rights_ref"]])


def verify_voice(root: Path, project: dict[str, Any], voice: dict[str, Any]) -> dict[str, Any]:
    findings = []
    audio = None
    asset = asset_map(project).get(voice.get("asset_id"))
    if not asset or asset.get("kind") != "audio":
        findings.append({"code": "TTS_REFERENCE_ASSET_MISSING"})
    else:
        try:
            audio = local_path(root, asset.get("uri", ""), "asset_id")
            actual = f"sha256:{sha256_file(audio)}"
            if actual != voice.get("audio_sha256") or actual != asset.get("sha256") or str(asset.get("rights_ref") or asset.get("id")) != voice.get("reference_rights_ref"):
                findings.append({"code": "TTS_REFERENCE_HASH_MISMATCH"})
        except (AppError, OSError) as exc:
            findings.append({"code": "TTS_REFERENCE_INVALID", "message": str(exc)})
    if f"sha256:{sha256_bytes(str(voice.get('prompt_text', '')).encode('utf-8'))}" != voice.get("prompt_text_sha256"):
        findings.append({"code": "TTS_TRANSCRIPT_HASH_MISMATCH"})
    proof = Path(str(voice.get("evidence", "")))
    if not proof.is_file() or f"sha256:{sha256_file(proof)}" != voice.get("evidence_sha256"):
        findings.append({"code": "TTS_VOICE_EVIDENCE_CHANGED"})
    expected = "sha256:" + sha256_bytes((str(voice.get("audio_sha256")) + str(voice.get("prompt_text_sha256")) + str(voice.get("evidence_sha256"))).encode("ascii"))
    if expected != voice.get("sha256"):
        findings.append({"code": "TTS_VOICE_MANIFEST_INVALID"})
    return {"ok": not findings, "findings": findings, "audio": str(audio) if audio else None}


def require_verified_inputs(root: Path, project: dict[str, Any], adapter: dict[str, Any], voice: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    model_check, voice_check = verify_adapter(adapter), verify_voice(root, project, voice)
    if not model_check["ok"] or not voice_check["ok"]:
        raise AppError("TTS_INPUT_INTEGRITY_FAILED", "模型、参考声、逐字稿或证据已变化，拒绝推理", exit_code=10, cause=json.dumps({"adapter": model_check, "voice": voice_check}, ensure_ascii=False))
    return model_check, voice_check


def synthesize_soulx(root: Path, text: str, output: Path, *, adapter: dict[str, Any], voice: dict[str, Any], audio: Path, operation_id: str, sample_rate: int, channels: int, seed: int, timeout: int = 900) -> dict[str, Any]:
    text = validate_text(text)
    validate_output(sample_rate, channels, output)
    cache = root / "cache" / "tts" / operation_id
    cache.mkdir(parents=True, exist_ok=False)
    raw, request_file, response_file = cache / "raw.wav", cache / "request.json", cache / "response.json"
    request = {"protocol": SOULX_PROTOCOL, "network": "disabled", "adapter": adapter, "reference_audio": str(audio), "reference_sha256": voice["audio_sha256"], "prompt_text": voice["prompt_text"], "text": text, "seed": seed, "raw_output": str(raw), "response": str(response_file), "runtime_root": str(cache / "runtime")}
    atomic_write_json(request_file, request)
    staging = output.with_name(f".{output.stem}.{operation_id}.wav")
    try:
        worker_path = Path(__file__).with_name("soulx_worker.py")
        worker_sha256 = f"sha256:{sha256_file(worker_path)}"
        completed = run_process([adapter["python_executable"], "-I", "-B", "-X", "utf8", str(worker_path), str(request_file)], cwd=cache, timeout=timeout)
        atomic_write_text(cache / "worker.log", (completed.stdout or "") + "\n" + (completed.stderr or ""))
        try:
            response = json.loads(response_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AppError("TTS_WORKER_FAILED", "本地 SoulX 未返回有效响应", exit_code=6, cause=(completed.stderr or completed.stdout)[-3000:]) from exc
        if completed.returncode != 0 or response.get("protocol") != SOULX_PROTOCOL or response.get("status") != "succeeded" or response.get("blocked_network_events") != [] or response.get("network") != "disabled" or response.get("raw_output") != str(raw) or not raw.is_file():
            raise AppError("TTS_WORKER_FAILED", "本地 SoulX 推理失败；不会调用其他引擎或在线服务", exit_code=6, cause=json.dumps(response, ensure_ascii=False)[-4000:])
        if response.get("raw_sha256") != f"sha256:{sha256_file(raw)}":
            raise AppError("TTS_OUTPUT_INVALID", "SoulX 原始音频哈希与 worker 响应不一致", exit_code=6)
        source_probe = probe_media(raw)
        if source_probe.get("audio", {}).get("sample_rate") != 24000 or source_probe.get("audio", {}).get("channels") != 1 or float(source_probe.get("duration_seconds") or 0) <= 0:
            raise AppError("TTS_OUTPUT_INVALID", "SoulX 原始音频必须为 24 kHz 单声道且非空", exit_code=6)
        output.parent.mkdir(parents=True, exist_ok=True)
        normalized = run_process([ffmpeg_path(), "-v", "error", "-nostdin", "-y", "-i", str(raw), "-vn", "-ar", str(sample_rate), "-ac", str(channels), "-c:a", "pcm_s16le", str(staging)], timeout=120)
        if normalized.returncode:
            raise AppError("TTS_OUTPUT_INVALID", "SoulX WAV 母带转换失败", exit_code=6, cause=normalized.stderr[-2000:])
        probe = probe_media(staging)
        if probe.get("audio", {}).get("sample_rate") != sample_rate or probe.get("audio", {}).get("channels") != channels or float(probe.get("duration_seconds") or 0) <= 0:
            raise AppError("TTS_OUTPUT_INVALID", "SoulX 最终音频参数或时长无效", exit_code=6)
        if output.exists():
            raise argument_error("配音输出已在推理期间出现，拒绝覆盖", "output")
        os.replace(staging, output)
        return {"engine": SOULX_ENGINE, "adapter_id": adapter["adapter_id"], "voice_id": voice["voice_id"], "text_sha256": f"sha256:{sha256_bytes(text.encode('utf-8'))}", "text_chars": len(text), "seed": seed, "sample_rate": sample_rate, "channels": channels, "output": str(output), "probe": probe, "model_sha256": adapter["sha256"], "reference_sha256": voice["audio_sha256"], "worker_sha256": worker_sha256, "worker": response, "worker_log": str(cache / "worker.log"), "raw_output": str(raw), "natural_duration": True, "network": "disabled"}
    finally:
        staging.unlink(missing_ok=True)
