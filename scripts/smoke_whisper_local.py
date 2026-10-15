"""Opt-in native Whisper evidence using caller-supplied existing local files."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "product" / "src"))
from ai_ad_editor.cli import main as cli_main
from ai_ad_editor.utils import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--python-executable", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--reference", action="append", required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--font", default=None, help="Optional existing local Chinese font; never fetched")
    parser.add_argument("--language", default="zh")
    args = parser.parse_args()
    root = Path(args.project).resolve()
    if root.exists() or len(args.input) != len(args.reference):
        parser.error("Use a new project and one --reference per --input")
    checks = []

    def invoke(*argv: str, expected: int = 0) -> dict:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli_main(list(argv))
        value = json.loads(output.getvalue())
        checks.append({"command": value.get("command"), "exit_code": code, "status": value.get("status")})
        print(json.dumps(checks[-1], ensure_ascii=False), flush=True)
        if code != expected:
            raise RuntimeError(output.getvalue())
        return value

    invoke("project", "init", str(root))
    adapter = ["asr", "adapter", "register", "--project", str(root), "--adapter-id", "whisper_local", "--python-executable", args.python_executable, "--model-path", args.model_path, "--device", args.device, "--threads", str(args.threads), "--evidence", args.evidence]
    invoke(*adapter, "--dry-run")
    registration = invoke(*adapter)
    invoke("asr", "adapter", "inspect", "--project", str(root), "--adapter-id", "whisper_local")
    plan = root / "cache" / "subtitle-track.json"
    atomic_write_json(plan, {"operations": [{"op": "add_track", "track_id": "track_asr", "kind": "subtitle", "order": 10}]})
    invoke("timeline", "compose", "--project", str(root), "--input", str(plan))
    font_id = None
    if args.font:
        font_id = invoke("media", "ingest", "--project", str(root), "--input", str(Path(args.font).resolve()))["data"]["asset"]["id"]
    cases = []
    offset = 0.0
    for index, (audio, reference) in enumerate(zip(args.input, args.reference)):
        ingested = invoke("media", "ingest", "--project", str(root), "--input", str(Path(audio).resolve()))
        asset = ingested["data"]["asset"]
        project = json.loads((root / "project.json").read_text(encoding="utf-8"))
        audio_track = next(track for track in project["sequences"][0]["tracks"] if track["kind"] == "audio")
        tps = int(project["settings"]["timebase"]["ticks_per_second"])
        atomic_write_json(plan, {"operations": [{"op": "append_clip", "track_id": audio_track["id"], "asset_id": asset["id"], "source_in_tick": 0, "source_out_tick": round(float(asset["probe"]["duration_seconds"]) * tps), "timeline_start_tick": round(offset * tps)}]})
        invoke("timeline", "compose", "--project", str(root), "--input", str(plan))
        options = ["subtitle", "transcribe", "--project", str(root), "--asset-id", asset["id"], "--adapter-id", "whisper_local", "--language", args.language, "--output", f"assets/subtitles/case-{index}.srt", "--apply", "--track-id", "track_asr", "--timeline-start-seconds", str(offset)]
        if font_id:
            options.extend(["--font-asset-id", font_id])
        invoke(*options, "--dry-run")
        result = invoke(*options)
        evaluation = invoke("subtitle", "evaluate", "--project", str(root), "--input", result["data"]["output"], "--reference", str(Path(reference).resolve()), "--report", f"validation/case-{index}-cer.json")
        transcription = result["data"]["transcription"]
        cases.append({"input": str(Path(audio).resolve()), "reference": str(Path(reference).resolve()), "transcription": transcription, "evaluation": evaluation["data"]["result"], "validation": result["data"]["validation"], "output": result["data"]["output"]})
        offset += float(asset["probe"]["duration_seconds"]) + 1
    output = root / "renders" / "whisper-subtitles.mp4"
    invoke("render", "--project", str(root), "--output", str(output), "--profile", "custom", "--width", "640", "--height", "360")
    invoke("quality", "check", "--project", str(root), "--input", str(output), "--width", "640", "--height", "360", "--require-audio")
    invoke("validate", "--project", str(root))
    invoke("policy", "audit", "--project", str(root))
    invoke("rights", "check", "--project", str(root), expected=7)
    report = {"scope": "explicit local Mandarin Whisper smoke, not broad acceptance", "checks": checks, "adapter": registration["data"]["adapter"], "cases": cases, "render": str(output), "network": "disabled"}
    atomic_write_json(root / "validation" / "whisper-smoke.json", report)
    print(json.dumps({"project": str(root), "case_cer": [x["evaluation"]["cer"] for x in cases]}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
