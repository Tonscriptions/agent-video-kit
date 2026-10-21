"""Native subprocess entry point; imports only the explicitly registered local SoulX.

The audit guard blocks Python network operations, including the upstream tokenizer
download fallback. This is an offline runtime guard, not an OS security sandbox.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path


PROTOCOL = "agent-video-soulx-tts-v1"
TOKENIZER_SHA256 = "d43342aa12163a80bf07bffb94c9de2e120a8df2f9917cd2f642e7f4219c6f71"


def install_network_guard(events: list[str]) -> None:
    import socket
    # urllib3 probes IPv6 by binding ::1:0 while importing Transformers. Offline
    # inference needs no address family; suppress the probe rather than permit it.
    socket.has_ipv6 = False
    def audit(event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.connect_ex", "socket.bind", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.sendto", "urllib.Request", "http.client.connect"}:
            events.append(event)
            raise RuntimeError(f"TTS_NETWORK_DISABLED: {event}")
    sys.addaudithook(audit)


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return "sha256:" + hashlib.file_digest(handle, "sha256").hexdigest()


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    response_path = Path(request["response"])
    response = {"protocol": PROTOCOL, "status": "failed", "blocked_network_events": [], "network": "disabled"}
    started = time.monotonic()
    try:
        if request.get("protocol") != PROTOCOL or request.get("network") != "disabled":
            raise ValueError("Invalid offline TTS request")
        install_network_guard(response["blocked_network_events"])
        runtime = Path(request["runtime_root"])
        for key, directory in {"TEMP": "temp", "TMP": "temp", "TMPDIR": "temp", "HF_HOME": "hf", "HF_HUB_CACHE": "hf/hub", "TORCH_HOME": "torch", "XDG_CACHE_HOME": "cache"}.items():
            path = runtime / directory
            path.mkdir(parents=True, exist_ok=True)
            os.environ[key] = str(path)
        os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1", "PYTHONUTF8": "1", "TOKENIZERS_PARALLELISM": "false"})
        sys.dont_write_bytecode = True
        adapter = request["adapter"]
        for item in adapter["artifacts"]:
            path = Path(item["path"])
            if path.is_symlink() or path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
                raise ValueError(f"TTS_ARTIFACT_HASH_MISMATCH: {path.name}")
        reference = Path(request["reference_audio"])
        if digest(reference) != request["reference_sha256"]:
            raise ValueError("TTS_REFERENCE_HASH_MISMATCH")
        tokenizer = Path(adapter["tokenizer_path"])
        if digest(tokenizer) != "sha256:" + TOKENIZER_SHA256:
            raise ValueError("TTS_TOKENIZER_HASH_MISMATCH")
        sys.path[:0] = [adapter["package_root"], adapter["source_root"]]
        import torch
        import soundfile as sf
        import s3tokenizer
        import transformers
        import onnxruntime
        if not torch.cuda.is_available():
            raise RuntimeError("TTS_CUDA_UNAVAILABLE: the registered SoulX HF/BF16 engine requires CUDA")

        def local_tokenizer(name: str, download_root: str | None = None) -> str:
            if name != "speech_tokenizer_v2_25hz":
                raise ValueError(f"TTS_TOKENIZER_UNREGISTERED: {name}")
            return str(tokenizer)

        # The public loader otherwise downloads when its own default cache misses.
        s3tokenizer._download = local_tokenizer
        from soulxpodcast.utils.parser import podcast_format_parser
        from soulxpodcast.utils.infer_utils import initiate_model, process_single_input
        script = {"speakers": {"S1": {"prompt_audio": str(reference), "prompt_text": request["prompt_text"]}}, "text": [["S1", request["text"]]]}
        parsed = podcast_format_parser(script)
        with torch.inference_mode():
            model, dataset = initiate_model(int(request["seed"]), adapter["model_path"], "hf", True)
            inputs = process_single_input(dataset, parsed["text"], parsed["prompt_wav"], parsed["prompt_text"], parsed["use_dialect_prompt"], parsed["dialect_prompt_text"])
            result = model.forward_longform(**inputs)
            waves = result.get("generated_wavs", [])
            if not waves:
                raise ValueError("TTS_EMPTY_AUDIO")
            audio = torch.cat(waves, dim=1).detach().float().cpu().squeeze(0).numpy()
        if audio.ndim != 1 or len(audio) < 2400:
            raise ValueError("TTS_INVALID_AUDIO_SHAPE")
        peak = max(abs(float(audio.min())), abs(float(audio.max())))
        rms = float((audio ** 2).mean() ** 0.5)
        if not math.isfinite(peak) or not math.isfinite(rms) or rms <= 1e-7:
            raise ValueError("TTS_NONFINITE_OR_SILENT_AUDIO")
        if response["blocked_network_events"]:
            raise RuntimeError("TTS_NETWORK_ATTEMPT_REJECTED")
        raw = Path(request["raw_output"])
        sf.write(str(raw), audio, 24000, subtype="PCM_16")
        response.update({"status": "succeeded", "raw_output": str(raw), "raw_sha256": digest(raw), "sample_rate": 24000, "channels": 1, "samples": len(audio), "duration_seconds": len(audio) / 24000, "seed": request["seed"], "precision": "llm-bf16-flow-fp16", "llm_engine": "hf", "device": torch.cuda.get_device_name(0), "peak_cuda_bytes": torch.cuda.max_memory_allocated(0), "peak": peak, "rms_dbfs": 20 * math.log10(rms), "versions": {"python": sys.version.split()[0], "torch": torch.__version__, "transformers": transformers.__version__, "onnxruntime": onnxruntime.__version__}, "module_paths": {"torch": str(torch.__file__), "s3tokenizer": str(s3tokenizer.__file__)}})
    except Exception as exc:
        response.update({"error_type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()[-4000:]})
    response["elapsed_seconds"] = round(time.monotonic() - started, 3)
    response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if response["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
