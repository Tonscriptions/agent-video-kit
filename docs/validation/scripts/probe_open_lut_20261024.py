"""Small community CUBE feasibility probe through the registered installed Skill.

Requires research_lut_sources_20261024.py --transport git-ssh to have captured notices.
Does not install a look library or modify the frozen application release.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/validation/evidence/lut-research-20261024-r1/probe"
MEDIA = ROOT / "docs/assets/lut-research-20261024-r1"
PROJECT = ROOT / "local/agent-ffmpeg/lut-research-20261024-r1/project"
PREFIX = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
          "C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1"]
REPO = "stripedpurple/color-grading-luts"
COMMIT = "9757e8b5147693cab49c3fd674bf23dbe28d6c8e"
UPSTREAM_PATH = "Avant Garde/Striped Purple - Amber Haze.cube"


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    resume = sys.argv[1:] == ["--finish-existing"]
    if not resume and (EVIDENCE.exists() or MEDIA.exists() or PROJECT.exists()):
        raise SystemExit("Preserve existing probe evidence; use a new run directory.")
    EVIDENCE.mkdir(parents=True, exist_ok=resume)
    MEDIA.mkdir(parents=True, exist_ok=resume)
    commands = json.loads((EVIDENCE / "commands.json").read_bytes()) if resume else []

    def run(label: str, argv: list, cli: bool = False) -> object:
        proc = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=180,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        (EVIDENCE / (label + ".stdout.txt")).write_bytes(proc.stdout)
        (EVIDENCE / (label + ".stderr.txt")).write_bytes(proc.stderr)
        row = {"label": label, "argv": list(map(str, argv)), "exit_code": proc.returncode}
        commands.append(row)
        save(EVIDENCE / "commands.json", commands)
        if proc.returncode:
            raise RuntimeError(label + ": " + proc.stdout.decode("utf-8", "replace")[-2000:] + proc.stderr.decode("utf-8", "replace")[-2000:])
        if cli:
            response = json.loads(proc.stdout)
            assert response["ok"] and response["status"] == "succeeded", response
            row.update({"status": response["status"], "warnings": response.get("warnings"), "errors": response.get("errors")})
            save(EVIDENCE / "commands.json", commands)
            return response
        return proc.stdout

    def call(label: str, args: list) -> dict:
        return run(label, PREFIX + args, True)

    if resume:
        # Resume only post-render verification. Preserve all original CLI logs,
        # project edits, the published render and the first failed assertion.
        finish(run, commands)
        return
    for label, args in [("version", ["version"]), ("doctor", ["doctor"]),
                        ("capabilities", ["capabilities"]), ("schema", ["schema", "show"]),
                        ("lut-effect", ["effects", "inspect", "--name", "lut3d"])]:
        call(label, args)
    notices = EVIDENCE.parent / "stripedpurple--color-grading-luts"
    snapshot = ROOT / "sources/lut-research-20261024/stripedpurple--color-grading-luts"
    tree = json.loads((notices / "tree.json").read_bytes())
    entry = next(x for x in tree["tree"] if x["path"] == UPSTREAM_PATH)
    cube = run("read-community-cube", ["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
                                      "-C", snapshot, "show", COMMIT + ":" + UPSTREAM_PATH])
    assert hashlib.sha1(b"blob " + str(len(cube)).encode() + b"\0" + cube).hexdigest() == entry["sha"]
    sample = ROOT / "sources/lut-research-20261024/samples/striped-purple-amber-haze.cube"
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_bytes(cube)
    shutil.copyfile(notices / "LICENSE", sample.with_name("LICENSE"))
    (MEDIA / "LICENSE.txt").write_text(
        "The synthetic FFmpeg test pattern and this probe's composition are dedicated to CC0-1.0.\n"
        "The applied Amber Haze LUT is by Striped Purple/Nixua, MIT.\n"
        "Source: https://github.com/stripedpurple/color-grading-luts\n"
        "Commit: " + COMMIT + "\n\n" + (notices / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8")
    source = MEDIA / "original.mp4"
    run("make-synthetic-input", ["ffmpeg", "-hide_banner", "-nostdin", "-f", "lavfi", "-i",
        "testsrc2=size=320x180:rate=12:duration=3", "-an", "-c:v", "libx264", "-crf", "16",
        "-pix_fmt", "yuv420p", source])
    call("project-init", ["project", "init", PROJECT, "--name", "Community LUT feasibility / synthetic silent"])
    project_json = PROJECT / "project.json"
    project = json.loads(project_json.read_bytes())
    project["settings"]["canvas"].update({"width": 320, "height": 180})
    project["settings"]["timebase"]["display_fps"] = {"num": 12, "den": 1}
    save(project_json, project)
    ingested = call("ingest", ["media", "ingest", "--project", PROJECT, "--input", source,
        "--license-spdx", "CC0-1.0", "--license-url", MEDIA / "LICENSE.txt", "--evidence", MEDIA / "LICENSE.txt",
        "--creator", "Agent Video Kit contributors", "--verification-status", "verified", "--permitted-use", "commercial_ad"])
    registered = call("lut-register", ["lut", "register", "--project", PROJECT, "--input", sample,
        "--lut-id", "lut_community_amber_haze", "--name", "Striped Purple / Amber Haze / research sample",
        "--license-spdx", "MIT", "--license-url", notices / "LICENSE", "--evidence", notices / "LICENSE",
        "--creator", "Striped Purple / Nixua", "--verification-status", "verified", "--permitted-use", "commercial_ad"])
    save(EVIDENCE / "community-sample.json", {"repository": REPO, "commit": COMMIT, "path": UPSTREAM_PATH,
        "git_blob_sha1_verified": entry["sha"], "sha256": digest(sample), "license": "MIT",
        "source_url": "https://github.com/" + REPO + "/blob/" + COMMIT + "/" + UPSTREAM_PATH,
        "input_color_domain": "upstream unspecified; encoded RGB engineering probe, not colorimetric acceptance"})
    edits = {"sequence_id": "seq_main", "operations": [{"op": "append_clip", "track_id": "track_video_1",
        "asset_id": ingested["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 270000,
        "duration_tick": 270000, "effects": [{"type": "lut3d", "parameters": {
            "lut_id": "lut_community_amber_haze", "intensity": 0.65, "interpolation": "tetrahedral"}}]}]}
    save(EVIDENCE / "changes.json", edits)
    call("compose", ["timeline", "compose", "--project", PROJECT, "--input", EVIDENCE / "changes.json"])
    call("validate", ["validate", "--project", PROJECT])
    call("rights", ["rights", "check", "--project", PROJECT])
    rendered = PROJECT / "renders/amber-haze-065.mp4"
    call("render", ["render", "--project", PROJECT, "--output", rendered, "--publish"])
    call("quality", ["quality", "check", "--project", PROJECT, "--input", rendered, "--width", 320, "--height", 180])
    edited = MEDIA / "edited.mp4"
    shutil.copyfile(rendered, edited)
    finish(run, commands)


def finish(run, commands: list) -> None:
    source = MEDIA / "original.mp4"
    edited = MEDIA / "edited.mp4"
    project_json = PROJECT / "project.json"
    run("decode", ["ffmpeg", "-hide_banner", "-v", "error", "-i", edited, "-f", "null", "-"])
    probe = json.loads(run("probe", ["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", edited]))
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert video["width"] == 320 and video["height"] == 180 and int(video["nb_read_frames"]) == 36
    assert video["avg_frame_rate"] == "12/1"
    pcm = run("silence-pcm", ["ffmpeg", "-v", "error", "-i", edited, "-map", "0:a:0", "-ac", "1", "-f", "f32le", "-"])
    peak = max(abs(value[0]) for value in struct.iter_unpack("<f", pcm))
    assert peak == 0.0, peak
    raw_inputs = []
    for label, video_path in [("original", source), ("edited", edited)]:
        pixels = run("pixels-" + label, ["ffmpeg", "-v", "error", "-i", video_path, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        raw_inputs.append(pixels)
    assert len(raw_inputs[0]) == len(raw_inputs[1]) == 320 * 180 * 3
    mean_delta = sum(abs(a - b) for a, b in zip(*raw_inputs)) / len(raw_inputs[0])
    assert mean_delta > 2, mean_delta
    graph = "[0:v][1:v]hstack=inputs=2,fps=6,split[a][b];[a]palettegen[p];[b][p]paletteuse"
    run("comparison-gif", ["ffmpeg", "-hide_banner", "-nostdin", "-i", source, "-i", edited,
                           "-filter_complex", graph, "-an", MEDIA / "comparison.gif"])
    run("comparison-still", ["ffmpeg", "-hide_banner", "-nostdin", "-i", source, "-i", edited,
        "-filter_complex", "[0:v][1:v]hstack=inputs=2", "-frames:v", "1", MEDIA / "comparison.png"])
    save(EVIDENCE / "project.snapshot.json", json.loads(project_json.read_bytes()))
    report = {"status": "passed", "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "one MIT community CUBE, installed release via registered Skill, 0.65 static intensity",
        "new_product_features": 0, "new_model_inferences": 0, "bundled_library_installed": False,
        "hald_conversion_tested": False, "natural_material_or_brand_match_accepted": False,
        "native_windows": True, "virtual_environments_created": 0,
        "audio": "no authored audio clips; renderer emits silent AAC", "decoded_audio_peak": peak,
        "render_warnings": json.loads((EVIDENCE / "render.stdout.txt").read_bytes())["warnings"],
        "continuous_playback_review": False, "human_listening": False, "frame_still_review": "pending",
        "video": {"width": 320, "height": 180, "fps": "12/1", "frames": 36, "seconds": 3},
        "first_frame_mean_absolute_rgb_delta_0_255": round(mean_delta, 6),
        "cli_commands": sum(command["argv"][0] == "powershell.exe" for command in commands),
        "media": [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": digest(p)}
                  for p in sorted(MEDIA.iterdir()) if p.is_file()]}
    save(EVIDENCE / "verification.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
