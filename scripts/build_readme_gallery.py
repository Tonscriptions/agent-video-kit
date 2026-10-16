"""Build public, procedural media and exercise the real local CLI for README.

No model downloads or natural/private footage. Research animations either reuse
hash-verified arrays from a recorded run or explicitly rebuild synthetic cases.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_SOURCE_COMMIT = "0c9290c75111abaf847d777d716387bfed40513d"
sys.path.insert(0, str(ROOT / "product/src"))
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.rvm_worker import install_network_guard

NETWORK_EVENTS: list = []
install_network_guard(NETWORK_EVENTS)
configure_local_runtime()

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence
import PIL


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def baseline_sources_match(frozen: dict[str, str], baseline: dict[str, str]) -> str:
    if frozen == baseline:
        return "recorded-raw-sha256"
    # A Windows checkout can normalize LF/CRLF without changing source code.
    # Accept only equality to the fixed, verified commit after this conversion.
    for name in baseline:
        expected = command(["git", "show", ACCEPTED_SOURCE_COMMIT + ":" + name])
        actual = (ROOT / name).read_bytes()
        if actual.replace(b"\r\n", b"\n") != expected.replace(b"\r\n", b"\n"):
            raise AssertionError(f"Product differs from the verified source commit: {name}")
    return "fixed-accepted-commit-with-crlf-lf-normalization"


def command(argv: list[str], *, data: bytes | None = None) -> bytes:
    result = subprocess.run(argv, input=data, capture_output=True, cwd=ROOT, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace") + result.stdout.decode("utf-8", "replace"))
    return result.stdout


def encode(path: Path, frames: np.ndarray, fps: int) -> None:
    n, h, w, channels = frames.shape
    assert channels == 3 and n > 0 and w % 2 == 0 and h % 2 == 0
    command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{w}x{h}", "-r", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264", "-crf", "18",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)], data=frames.tobytes())


def decode(path: Path) -> tuple[np.ndarray, dict]:
    probe = json.loads(command(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)]))
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    raw = command(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
    frames = np.frombuffer(raw, np.uint8).reshape(-1, video["height"], video["width"], 3)
    return frames, probe


def gif(path: Path, frames: np.ndarray, fps: int) -> None:
    assert 1000 % fps == 0 and (1000 // fps) % 10 == 0, "GIF uses 10ms time units"
    images = [Image.fromarray(frame).quantize(colors=128) for frame in frames]
    images[0].save(path, save_all=True, append_images=images[1:], duration=1000 // fps, loop=0, disposal=2, optimize=False)


def font(size: int):
    return ImageFont.load_default(size=size)


def panel_clip(arrays: list[np.ndarray], labels: list[str], footer: str) -> np.ndarray:
    result = []
    for index in range(len(arrays[0])):
        canvas = Image.new("RGB", (192 * len(arrays), 168), "#101722")
        draw = ImageDraw.Draw(canvas)
        for col, (array, label) in enumerate(zip(arrays, labels)):
            draw.text((col * 192 + 6, 5), label, fill="#f3f7ff", font=font(13))
            frame = ImageOps.contain(Image.fromarray(array[index, :, :, :3]), (192, 120))
            canvas.paste(frame, (col * 192 + (192 - frame.width) // 2, 25 + (120 - frame.height) // 2))
        draw.text((6, 149), f"Frame {index:02d} / {len(arrays[0])-1:02d} | {footer}", fill="#aec0d5", font=font(11))
        result.append(np.asarray(canvas))
    return np.stack(result)


def fixture(kind: int) -> np.ndarray:
    result = []
    for index in range(90):
        image = Image.new("RGB", (640, 360), "#102a40" if kind == 0 else "#4a2936")
        draw = ImageDraw.Draw(image)
        for x in range(-40, 680, 40):
            xx = x + index % 40
            draw.line((xx, 0, xx, 360), fill="#25485e" if kind == 0 else "#633f4e")
        for y in range(0, 361, 40):
            draw.line((0, y, 640, y), fill="#25485e" if kind == 0 else "#633f4e")
        cx = 320 + int(50 * np.sin(index / 25))
        if kind == 0:
            draw.rounded_rectangle((cx-57, 100, cx+57, 291), radius=22, fill="#51d6bd", outline="#e1fff0", width=3)
            draw.rounded_rectangle((cx-29, 73, cx+29, 108), radius=8, fill="#c9f7ef")
            draw.line((cx-31, 150, cx+31, 150), fill="#174d52", width=5)
            draw.line((cx-25, 168, cx+25, 168), fill="#174d52", width=3)
        else:
            draw.ellipse((cx-93, 95, cx+93, 281), fill="#f7b95e", outline="#ffedd1", width=3)
            draw.ellipse((cx-48, 140, cx+48, 236), fill="#4a2936")
        draw.text((25, 20), f"PROCEDURAL SOURCE {'A' if kind == 0 else 'B'}", fill="#ffffff", font=font(20))
        draw.text((25, 322), f"LOCAL FIXTURE / 30 FPS / {index:02d}", fill="#bdcddd", font=font(15))
        result.append(np.asarray(image))
    return np.stack(result)


def build(output: Path, work: Path, research_root: Path | None, rebuild: bool) -> None:
    if (work / "project").exists():
        raise ValueError("Use a fresh --work-dir; existing projects are never deleted or reset")
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    baseline_path = ROOT / "docs/validation/evidence/repair-blend-smoke-20261016.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
    frozen = {name: sha(ROOT / name) for name in baseline["implementation_sha256"]}
    source_comparison = baseline_sources_match(frozen, baseline["implementation_sha256"])
    calls = []
    entry = f"import sys;sys.path.insert(0,{str(ROOT / 'product/src')!r});from ai_ad_editor.cli import main;sys.exit(main(sys.argv[1:]))"

    def cli(*args: object) -> dict:
        args = [str(v) for v in args]
        result = json.loads(command([sys.executable, "-I", "-B", "-X", "utf8", "-c", entry, *args]))
        calls.append({"argv": args, "result": result})
        return result

    source_a, source_b = output / "source-a.mp4", output / "source-b.mp4"
    encode(source_a, fixture(0), 30)
    encode(source_b, fixture(1), 30)
    samples = int(5.5 * 48000)
    t = np.arange(samples) / 48000
    envelope = np.minimum(1, t / .2) * np.minimum(1, (5.5 - t) / .3)
    tone = (.055 * np.sin(2*np.pi*220*t) + .025*np.sin(2*np.pi*330*t)) * envelope
    wav = output / "source-audio.wav"
    with wave.open(str(wav), "wb") as handle:
        handle.setnchannels(2); handle.setsampwidth(2); handle.setframerate(48000)
        handle.writeframes(np.repeat((tone*32767).astype("<i2")[:, None], 2, axis=1).tobytes())
    title = Image.new("RGBA", (640, 360))
    draw = ImageDraw.Draw(title)
    draw.rounded_rectangle((14, 6, 626, 60), radius=12, fill=(10, 17, 30, 230))
    draw.text((31, 18), "AGENT VIDEO KIT / ACTUAL CLI RENDER", font=font(22), fill="white")
    draw.rounded_rectangle((14, 298, 626, 352), radius=12, fill=(10, 17, 30, 230))
    draw.text((30, 309), "KEYFRAMES + CROSSFADE + MASK + AUDIO", font=font(20), fill="#79e7cb")
    title_path = output / "title-overlay.png"
    title.save(title_path)
    provenance = output / "fixture-provenance.json"
    save(provenance, {"kind": "procedural-public-development-fixture", "generator": "scripts/build_readme_gallery.py",
                      "generator_sha256": sha(Path(__file__)), "third_party_natural_media": False,
                      "rights": "CC0-1.0 dedication for original fixture graphics and synthesized tones; no font binary redistributed",
                      "label_font": "Pillow built-in load_default (Aileron); raster labels only",
                      "assets": {p.name: sha(p) for p in [source_a, source_b, wav, title_path]},
                      "scope": "functional illustration, not a commercial-advertising quality benchmark"})
    project = work / "project"
    cli("project", "init", project, "--name", "README procedural functional demonstration")
    for asset_id, path in [("source_a", source_a), ("source_b", source_b), ("tone", wav), ("title", title_path)]:
        cli("media", "ingest", "--project", project, "--input", path, "--asset-id", asset_id,
            "--source-url", "local://readme-procedural-fixture", "--license-spdx", "CC0-1.0",
            "--evidence", provenance, "--verification-status", "verified", "--permitted-use", "commercial_ad",
            "--creator", "Agent Video Kit procedural fixture generator")
    operations = [
        {"op": "update_track", "track_id": "track_video_1", "overlap_policy": "allow"},
        {"op": "add_track", "id": "track_overlay", "kind": "video", "order": 2},
        {"op": "add_track", "id": "track_title", "kind": "video", "order": 3},
        {"op": "append_clip", "id": "base_a", "track_id": "track_video_1", "asset_id": "source_a",
         "source_in_tick": 0, "source_out_tick": 270000, "timeline_start_tick": 0,
         "effects": [{"type": "hsl", "hue": 8, "saturation": 1.1}]},
        {"op": "append_clip", "id": "base_b", "track_id": "track_video_1", "asset_id": "source_b",
         "source_in_tick": 0, "source_out_tick": 270000, "timeline_start_tick": 225000,
         "transition_in": {"type": "crossfade", "duration": .5}},
        {"op": "append_clip", "id": "circle", "track_id": "track_overlay", "asset_id": "source_b",
         "source_in_tick": 0, "source_out_tick": 270000, "timeline_start_tick": 67500,
         "mask": {"type": "circle", "cx": .3, "cy": .5, "radius": .23, "feather": .02},
         "transform": {"scale": .62, "position": {"x": .77, "y": .53}},
         "keyframes": [{"property": "mask.cx", "keyframes": [{"at_tick": 0, "value": .3}, {"at_tick": 270000, "value": .7}]}]},
        {"op": "append_clip", "id": "title_clip", "track_id": "track_title", "asset_id": "title",
         "source_in_tick": 0, "source_out_tick": 495000, "timeline_start_tick": 0,
         "keyframes": [{"property": "transform.opacity", "keyframes": [{"at_tick": 0, "value": 0},
             {"at_tick": 27000, "value": 1}, {"at_tick": 468000, "value": 1}, {"at_tick": 495000, "value": 0}]}]},
        {"op": "append_clip", "id": "tone_clip", "track_id": "track_audio_1", "asset_id": "tone",
         "source_in_tick": 0, "source_out_tick": 495000, "timeline_start_tick": 0,
         "audio": {"volume": .8, "fade_in": .15, "fade_out": .3}},
    ]
    for operation in operations:
        for track in operation.get("keyframes", []):
            for keyframe in track["keyframes"]:
                keyframe["interpolation"] = "linear"
    changes = output / "timeline-changes.json"
    save(changes, {"sequence_id": "seq_main", "operations": operations})
    cli("timeline", "compose", "--project", project, "--input", changes)
    cli("motion", "apply", "--project", project, "--clip-id", "base_a", "--preset", "push-in", "--amount", ".12")
    validation = cli("validate", "--project", project, "--strict-rights")
    policy = cli("policy", "audit", "--project", project)
    rendered = project / "renders" / "showcase.mp4"
    render = cli("render", "--project", project, "--publish", "--profile", "custom", "--width", 640, "--height", 360,
                 "--output", rendered)
    quality = cli("quality", "check", "--project", project, "--input", rendered, "--require-audio", "--expensive",
                  "--profile", "custom", "--width", 640, "--height", 360, "--max-av-sync-ms", 80, "--max-true-peak-dbfs", -1)
    assert validation["data"]["ok"] and quality["data"]["ok"]
    assert not render["data"]["warnings"], render["data"]["warnings"]
    shutil.copyfile(rendered, output / "cli-showcase.mp4")
    shutil.copyfile(Path(str(rendered) + ".manifest.json"), output / "cli-showcase.mp4.manifest.json")
    package = output / "cli-showcase.aevpkg.zip"
    cli("convert", "export", "--project", project, "--target-format", "package", "--output", package)
    imported = work / "imported"
    cli("convert", "import", "--input", package, "--output", imported)
    cli("validate", "--project", imported, "--strict-rights")
    frames, probe = decode(output / "cli-showcase.mp4")
    assert frames.shape == (165, 360, 640, 3), frames.shape
    assert any(s["codec_type"] == "audio" for s in probe["streams"])
    gif(output / "cli-showcase.gif", frames[::3], 10)
    contact = Image.new("RGB", (640, 360 * 4))
    for row, index in enumerate([15, 45, 83, 135]):
        contact.paste(Image.fromarray(frames[index]), (0, row * 360))
    contact.save(output / "cli-contact.png")
    research = {}
    if rebuild:
        sys.path.insert(0, str(ROOT / "research/temporal-background"))
        from run_reference_probe import simple_translation, two_surfaces
        research_root = work / "synthetic-research"
        research_root.mkdir()
        research = {"translation": simple_translation(research_root, 1536*1024*1024),
                    "two_surfaces": two_surfaces(research_root, 1536*1024*1024)}
    elif research_root:
        historical_path = ROOT / "docs/validation/evidence/temporal-reference-selection-20261016.json"
        historical = json.loads(historical_path.read_text(encoding="utf-8-sig"))
        for case, key in [("translation", "translation"), ("two-surfaces", "two_surfaces")]:
            npz = research_root / (case + ".npz")
            if sha(npz) != historical[key]["artifact_sha256"]:
                raise AssertionError(f"Unmatched research artifact: {npz}")
        research = {k: historical[k] for k in ["translation", "two_surfaces"]}
    if research_root:
        for case in ["translation", "two-surfaces"]:
            with np.load(research_root / (case + ".npz"), allow_pickle=False) as arrays:
                series = [arrays[k] for k in ["source", "fallback", "previous_output", "output", "truth"]]
                assert np.array_equal(series[0][..., 3], series[3][..., 3])
                assert np.array_equal(series[0][~arrays["selected"]], series[3][~arrays["selected"]])
                panels = panel_clip(series, ["1 INPUT", "2 FALLBACK", "3 PREVIOUS", "4 NEW RESEARCH", "5 TRUTH"], "5 FPS viewing clock / research only")
                encode(output / (case + "-input.mp4"), series[0][..., :3], 5)
                encode(output / (case + "-comparison.mp4"), panels, 5)
                gif(output / (case + "-comparison.gif"), panels, 5)
                Image.fromarray(panels[6]).save(output / (case + "-contact.png"))
                key = case.replace("-", "_")
                research[key] = {"source_npz_sha256": sha(research_root / (case + ".npz")),
                                 "metrics": research[key]["metrics"], "previous_metrics": research[key]["previous_metrics"],
                                 "reused_recorded_output": not rebuild, "original_frame_count": len(series[0]),
                                 "presentation_fps": 5, "product_integrated": False}
    media = {}
    for path in sorted(output.iterdir()):
        if path.suffix == ".mp4":
            decoded, details = decode(path)
            video = next(s for s in details["streams"] if s["codec_type"] == "video")
            media[path.name] = {"frames": len(decoded), "width": video["width"], "height": video["height"],
                                "fps": video["avg_frame_rate"], "seconds": float(video["duration"]),
                                "audio_streams": sum(s["codec_type"] == "audio" for s in details["streams"])}
        elif path.suffix == ".gif":
            with Image.open(path) as handle:
                times = [frame.info["duration"] for frame in ImageSequence.Iterator(handle)]
                media[path.name] = {"frames": len(times), "width": handle.width, "height": handle.height,
                                    "milliseconds": sum(times), "frame_durations_ms": sorted(set(times)), "loop": handle.info.get("loop")}
            if path.name == "cli-showcase.gif":
                assert len(times) == 55 and sum(times) == 5500
            else:
                assert len(times) == 12 and sum(times) == 2400
    assert {name: sha(ROOT / name) for name in frozen} == frozen
    save(output / "verification.json", {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "base_commit": command(["git", "rev-parse", "HEAD"]).decode().strip(),
         "generator_sha256": sha(Path(__file__)), "runtime": {"python": sys.version, "numpy": np.__version__, "pillow": PIL.__version__,
             "ffmpeg": command(["ffmpeg", "-version"]).decode().splitlines()[0], "network_guard_events": NETWORK_EVENTS,
             "network_guard_scope": "generator Python only; CLI subprocesses use production local-path policy; no packet-level or process-tree network audit",
             "virtualization_invoked": False, "browser_invoked": False, "learned_model_runs": 0},
         "cli_calls": calls, "render_warning_count": len(render["data"]["warnings"]), "quality": quality["data"],
         "policy": policy["data"], "media": media, "research": research,
         "baseline_363_source_files_verified": len(frozen), "baseline_363_sources_unchanged": True,
         "baseline_source_comparison": source_comparison, "accepted_source_commit": ACCEPTED_SOURCE_COMMIT,
         "full_regression_rerun": False, "natural_video_quality_accepted": False, "full_jianying_parity_accepted": False,
         "visual_review": "pending; review record is separate", "files": {p.name: {"sha256": sha(p), "bytes": p.stat().st_size}
             for p in sorted(output.iterdir()) if p.is_file() and p.name not in {"verification.json", "manual-review.json"}}})
    print(json.dumps({"output": str(output), "cli_calls": len(calls), "media": media}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--research-root", type=Path)
    group.add_argument("--rebuild-synthetic-research", action="store_true")
    args = parser.parse_args()
    build(args.output_dir.resolve(), args.work_dir.resolve(), args.research_root.resolve() if args.research_root else None, args.rebuild_synthetic_research)
