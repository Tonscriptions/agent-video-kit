"""Opt-in native SoulX smoke: explicit existing artifacts only, no downloads."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "python-executable", "source-root", "package-root", "model-path", "tokenizer-path", "model-evidence", "reference-audio", "prompt-input", "voice-evidence"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--text", default="让每一次创作，都变得更加简单。")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "product" / "src"))
    from ai_ad_editor.cli import main as cli
    from ai_ad_editor.media import ffmpeg_path
    from ai_ad_editor.utils import atomic_write_json, run_process
    root = Path(args.project).resolve()
    if root.exists():
        parser.error("smoke project must not exist; never overwrite or restart an existing run")
    calls = []

    def invoke(*argv: str, expected: int = 0) -> dict:
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            code = cli(list(argv))
        result = json.loads(capture.getvalue())
        calls.append({"command": result["command"], "exit_code": code, "result": result})
        if root.exists():
            atomic_write_json(root / "validation" / "soulx-smoke.json", {"calls": calls})
        print(json.dumps({"command": result["command"], "exit_code": code, "status": result["status"]}, ensure_ascii=False), flush=True)
        if code != expected:
            raise RuntimeError(json.dumps(result, ensure_ascii=False))
        return result

    invoke("project", "init", str(root))
    project = json.loads((root / "project.json").read_text(encoding="utf-8"))
    track = next(track for track in project["sequences"][0]["tracks"] if track["kind"] == "audio")
    source = invoke("media", "ingest", "--project", str(root), "--input", args.reference_audio)
    adapter_options = ["--project", str(root), "--adapter-id", "soulx_local", "--python-executable", args.python_executable, "--source-root", args.source_root, "--package-root", args.package_root, "--model-path", args.model_path, "--tokenizer-path", args.tokenizer_path, "--evidence", args.model_evidence]
    invoke("tts", "adapter", "register", *adapter_options, "--dry-run")
    invoke("tts", "adapter", "register", *adapter_options)
    invoke("tts", "voice", "register", "--project", str(root), "--voice-id", "cv_s4", "--asset-id", source["data"]["asset"]["id"], "--prompt-input", args.prompt_input, "--evidence", args.voice_evidence)
    synth = ["tts", "synthesize", "--project", str(root), "--adapter-id", "soulx_local", "--voice-id", "cv_s4", "--text", args.text, "--asset-id", "soulx_chinese_voice", "--apply", "--track-id", track["id"], "--channels", "1"]
    invoke(*synth, "--dry-run")
    generated = invoke(*synth)
    # A render fixture needs a visual track; the product does not export audio-only
    # projects as a video. Use a synthetic local plate, not third-party media.
    duration = float(generated["data"]["probe"]["duration_seconds"])
    plate = root / "cache" / "soulx-smoke-plate.mp4"
    encoded = run_process([ffmpeg_path(), "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i", f"color=c=0x25394f:s=320x180:r=24:d={duration + 0.1}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(plate)], timeout=120)
    if encoded.returncode:
        raise RuntimeError(encoded.stderr)
    visual = invoke("media", "ingest", "--project", str(root), "--input", str(plate))
    visual_track = next(item for item in project["sequences"][0]["tracks"] if item["kind"] == "video")
    plan = root / "cache" / "soulx-smoke-timeline.json"
    atomic_write_json(plan, {"operations": [{"op": "append_clip", "track_id": visual_track["id"], "asset_id": visual["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": round(duration * project["settings"]["timebase"]["ticks_per_second"])}]})
    invoke("timeline", "compose", "--project", str(root), "--input", str(plan))
    output = root / "renders" / "soulx-chinese.mp4"
    invoke("render", "--project", str(root), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
    invoke("quality", "check", "--project", str(root), "--input", str(output), "--width", "320", "--height", "180", "--require-audio")
    invoke("validate", "--project", str(root))
    invoke("policy", "audit", "--project", str(root))
    invoke("rights", "check", "--project", str(root), expected=7)
    print(json.dumps({"project": str(root), "audio": generated["data"]["output"], "duration_seconds": generated["data"]["probe"]["duration_seconds"], "worker": generated["data"].get("worker")}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
