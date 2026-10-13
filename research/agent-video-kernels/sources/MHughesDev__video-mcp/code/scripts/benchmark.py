#!/usr/bin/env python3
"""Benchmark suite for mcp-editor pure-Python hot paths.

Measures performance of filter building, manifest serialisation,
beat-sync planning, and timeline construction.  No FFmpeg or real
media required.

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --json      # machine-readable output
    python scripts/benchmark.py --runs 200  # increase sample count
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable


# ── Benchmark harness ─────────────────────────────────────────────────────────


def bench(label: str, fn: Callable[[], Any], runs: int = 100) -> dict[str, Any]:
    # Warm-up
    for _ in range(max(1, runs // 10)):
        fn()

    t0 = time.perf_counter()
    for _ in range(runs):
        fn()
    elapsed = time.perf_counter() - t0

    per_call_us = (elapsed / runs) * 1_000_000
    return {
        "label": label,
        "runs": runs,
        "total_s": round(elapsed, 4),
        "per_call_us": round(per_call_us, 2),
    }


def print_result(result: dict[str, Any]) -> None:
    print(f"  {result['label']:<50}  {result['per_call_us']:>8.1f} µs/call  ({result['runs']} runs)")


# ── Benchmark targets ─────────────────────────────────────────────────────────


def _build_filter_benchmarks(runs: int) -> list[dict[str, Any]]:
    from mcp_editor.effects import build_clip_vf, build_clip_af
    from mcp_editor.schemas import ClipEffect, Platform, TimelineClip

    clip_plain = TimelineClip(source="/tmp/a.mp4", start=0, duration=4.0)
    clip_all_effects = TimelineClip(
        source="/tmp/a.mp4",
        start=0,
        duration=4.0,
        effects=[
            ClipEffect(effect_type="speed_ramp", params={"speed": 1.5}),
            ClipEffect(effect_type="zoom_punch", params={"zoom": 1.2}),
            ClipEffect(effect_type="reframe", params={"x_pct": 0.05, "y_pct": 0.0, "crop_pct": 0.9}),
            ClipEffect(effect_type="grade", params={"contrast": 1.05, "saturation": 0.85, "vignette": 0.2}),
        ],
    )

    return [
        bench("build_clip_vf  (no effects)", lambda: build_clip_vf(clip_plain, Platform.widescreen), runs),
        bench("build_clip_vf  (4 effects)", lambda: build_clip_vf(clip_all_effects, Platform.widescreen), runs),
        bench("build_clip_af  (speed_ramp)", lambda: build_clip_af(clip_all_effects), runs),
    ]


def _build_schema_benchmarks(runs: int) -> list[dict[str, Any]]:
    from mcp_editor.schemas import (
        ProjectManifest, Platform, TimelinePlan, TimelineClip,
        RenderManifest, deterministic_project_id,
    )

    clips = [TimelineClip(source=f"/tmp/clip{i}.mp4", start=0, duration=4.0) for i in range(10)]
    plan = TimelinePlan(project_id="bench", platform=Platform.widescreen, clips=clips)
    manifest = ProjectManifest(name="bench", timelines={"16:9": plan})

    return [
        bench("deterministic_project_id", lambda: deterministic_project_id("my-project", "data/input"), runs),
        bench("ProjectManifest.model_dump_json (10 clips)", lambda: manifest.model_dump_json(), runs),
        bench("ProjectManifest.model_validate (10 clips)",
              lambda: ProjectManifest.model_validate(manifest.model_dump()), runs),
    ]


def _build_beat_benchmarks(runs: int) -> list[dict[str, Any]]:
    from mcp_editor.beat_sync import suggest_cut_points

    beat_times = [i * 0.5 for i in range(120)]  # 60 seconds of beats at 120 BPM

    return [
        bench("suggest_cut_points (medium, 30s)", lambda: suggest_cut_points(
            beat_times=beat_times, target_duration=30, style="medium", tempo=120.0,
        ), runs),
        bench("suggest_cut_points (trailer, 60s)", lambda: suggest_cut_points(
            beat_times=beat_times, target_duration=60, style="trailer", tempo=120.0,
        ), runs),
    ]


def _build_timeline_benchmarks(runs: int) -> list[dict[str, Any]]:
    from mcp_editor.timeline import make_simple_timeline_plan, validate_timeline, timeline_duration

    asset_paths = [f"/tmp/clip{i}.mp4" for i in range(20)]

    def make_and_validate():
        plan = make_simple_timeline_plan("bench", asset_paths, target_duration=60)
        return validate_timeline(plan)

    return [
        bench("make_simple_timeline_plan (20 clips, 60s)", lambda: make_simple_timeline_plan(
            "bench", asset_paths, target_duration=60,
        ), runs),
        bench("validate_timeline (20 clips)", make_and_validate, runs),
    ]


def _build_grading_benchmarks(runs: int) -> list[dict[str, Any]]:
    from mcp_editor.grading import build_grade_vf, list_grading_presets
    from mcp_editor.schemas import ClipEffect

    effect_full = ClipEffect(
        effect_type="grade",
        params={"lut_path": "/data/luts/film.cube", "contrast": 1.05, "saturation": 0.85, "gamma": 1.0, "vignette": 0.3},
    )
    effect_eq_only = ClipEffect(
        effect_type="grade",
        params={"contrast": 1.1, "saturation": 0.9},
    )

    return [
        bench("build_grade_vf (lut + eq + vignette)", lambda: build_grade_vf(effect_full), runs),
        bench("build_grade_vf (eq only)", lambda: build_grade_vf(effect_eq_only), runs),
        bench("list_grading_presets", list_grading_presets, runs),
    ]


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="mcp-editor benchmark suite")
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    groups = {
        "Filter building (effects.py)": _build_filter_benchmarks(args.runs),
        "Schema serialisation (schemas.py)": _build_schema_benchmarks(args.runs),
        "Beat sync planning (beat_sync.py)": _build_beat_benchmarks(args.runs),
        "Timeline construction (timeline.py)": _build_timeline_benchmarks(args.runs),
        "Color grading (grading.py)": _build_grading_benchmarks(args.runs),
    }

    if args.as_json:
        all_results = [r for results in groups.values() for r in results]
        print(json.dumps(all_results, indent=2))
        return

    print(f"\nmcp-editor benchmark — {args.runs} runs per target\n")
    for group_name, results in groups.items():
        print(f"{group_name}")
        for r in results:
            print_result(r)
        print()


if __name__ == "__main__":
    main()
