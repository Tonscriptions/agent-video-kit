from __future__ import annotations

import re
import time
from pathlib import Path

from .beat_sync import analyze_beats
from .beat_sync import apply_edit_plan as apply_beat_edit_plan
from .beat_sync import plan_beat_synced_edit
from .diagnostics import McpEditorError, WorkflowError, event, exception_issue, no_video_assets
from .grading import GRADING_PRESETS, apply_grading_preset
from .logging import ProjectLogger
from .media import scan_assets
from .projects import load_manifest, save_manifest, slugify
from .render import render_manifest_summary, render_timeline
from .schemas import Platform, ProjectManifest, RenderManifest, RenderedOutput, deterministic_project_id
from .timeline import export_otio, make_simple_timeline_plan
from .validation import validate_delivery_package, validate_render


# ── Prompt-to-style inference ─────────────────────────────────────────────────

_STYLE_KEYWORDS: dict[str, list[str]] = {
    "trailer": ["trailer", "epic", "hype", "intense", "action"],
    "social": ["social", "reel", "short", "tiktok", "instagram", "story"],
    "documentary": ["documentary", "doc", "slow", "chill", "calm", "ambient"],
    "fast": ["fast", "quick", "rapid", "energetic", "punchy"],
    "slow": ["slow motion", "slo-mo", "slomo", "slow-mo"],
}

_GRADE_KEYWORDS: dict[str, list[str]] = {
    "cinematic": ["cinematic", "film", "movie", "dramatic", "muted"],
    "vivid": ["vivid", "vibrant", "colorful", "colourful", "bright", "pop"],
    "flat": ["flat", "log", "neutral", "graded later"],
    "bw": ["black and white", "b&w", "monochrome", "noir", "grayscale"],
    "warm": ["warm", "golden", "sunset", "summer", "golden hour"],
    "cool": ["cool", "cold", "blue", "winter", "desaturated"],
}


def _infer_style(prompt: str) -> str:
    lower = prompt.lower()
    # Check longer (more specific) keywords first to avoid false positives.
    scored: list[tuple[int, str]] = []
    for style, keywords in _STYLE_KEYWORDS.items():
        match = next((kw for kw in sorted(keywords, key=len, reverse=True) if kw in lower), None)
        if match:
            scored.append((len(match), style))
    if scored:
        return max(scored)[1]
    return "medium"


def _infer_grade(prompt: str) -> str | None:
    lower = prompt.lower()
    scored: list[tuple[int, str]] = []
    for preset, keywords in _GRADE_KEYWORDS.items():
        match = next((kw for kw in sorted(keywords, key=len, reverse=True) if kw in lower), None)
        if match:
            scored.append((len(match), preset))
    if scored:
        return max(scored)[1]
    return None


# ── Core project/timeline helpers ─────────────────────────────────────────────


def create_project(
    name: str,
    input_dir: str = "data/input",
    music_path: str | None = None,
    platforms: list[Platform] | None = None,
    prompt: str | None = None,
) -> ProjectManifest:
    slug = slugify(name)
    project_id = deterministic_project_id(slug, input_dir)
    manifest = ProjectManifest(
        project_id=project_id,
        name=slug,
        input_dir=input_dir,
        music_path=music_path,
        platforms=platforms or [Platform.widescreen],
        prompt=prompt,
        assets=scan_assets(input_dir, include_audio=False),
    )
    logger = ProjectLogger(project_id)
    logger.info("create_project", "Project created", name=slug, input_dir=input_dir, asset_count=len(manifest.assets))
    save_manifest(manifest)
    return manifest


def build_timeline_for_project(
    manifest: ProjectManifest,
    platform: Platform,
    target_duration: float = 30,
) -> ProjectManifest:
    video_assets = [asset.path for asset in manifest.assets if asset.ok and asset.has_video]
    if not video_assets:
        raise McpEditorError(no_video_assets(manifest.input_dir))

    plan = make_simple_timeline_plan(
        project_id=manifest.project_id,
        asset_paths=video_assets,
        platform=platform,
        target_duration=target_duration,
        music_path=manifest.music_path,
    )
    otio_path = export_otio(plan)
    plan.otio_path = str(otio_path)
    manifest.timelines[platform.value] = plan
    save_manifest(manifest)
    return manifest


def render_and_validate_project(
    manifest: ProjectManifest,
    platform: Platform,
    render_profile: str = "preview",
    dry_run: bool = False,
) -> ProjectManifest:
    logger = ProjectLogger(manifest.project_id)
    plan = manifest.timelines.get(platform.value)
    if plan is None:
        manifest = build_timeline_for_project(manifest, platform)
        plan = manifest.timelines[platform.value]

    t0 = time.monotonic()
    output = render_timeline(plan, render_profile=render_profile, dry_run=dry_run)
    elapsed = time.monotonic() - t0

    if isinstance(output, RenderManifest):
        manifest.outputs[platform.value] = RenderedOutput(
            platform=platform,
            path=output.output_path,
            ok=True,
            validation={
                "ok": True,
                "dry_run": True,
                "render_manifest": render_manifest_summary(output),
            },
        )
        logger.timed("render", f"Dry-run render planned for {platform.value}", elapsed, dry_run=True)
        save_manifest(manifest)
        return manifest

    expected_duration = sum(clip.duration for clip in plan.clips)
    validation = validate_render(output, platform, expected_duration=expected_duration)
    ok = bool(validation["ok"])
    manifest.outputs[platform.value] = RenderedOutput(
        platform=platform,
        path=str(output),
        ok=ok,
        validation=validation,
    )
    if ok:
        logger.timed("render", f"Render completed for {platform.value}", elapsed, output=str(output))
    else:
        logger.warning("render", f"Render validation failed for {platform.value}", checks=validation.get("checks"))
    save_manifest(manifest)
    return manifest


def render_platform_variant(
    project_id: str,
    platform: Platform,
    render_profile: str = "preview",
    dry_run: bool = False,
) -> dict[str, object]:
    manifest = load_manifest(project_id)
    manifest = render_and_validate_project(manifest, platform, render_profile=render_profile, dry_run=dry_run)
    output = manifest.outputs[platform.value]
    return {
        "ok": output.ok,
        "project_id": project_id,
        "platform": platform.value,
        "output": output.model_dump(),
        "manifest_path": str(save_manifest(manifest)),
    }


def render_all_variants(
    project_id: str,
    platforms: list[Platform] | None = None,
    render_profile: str = "preview",
    dry_run: bool = False,
) -> dict[str, object]:
    manifest = load_manifest(project_id)
    selected_platforms = platforms or manifest.platforms
    results: dict[str, object] = {}

    for platform in selected_platforms:
        manifest = render_and_validate_project(manifest, platform, render_profile=render_profile, dry_run=dry_run)
        results[platform.value] = manifest.outputs[platform.value].model_dump()

    return {
        "ok": all(bool(output["ok"]) for output in results.values()),
        "project_id": project_id,
        "platforms": [platform.value for platform in selected_platforms],
        "outputs": results,
        "manifest_path": str(save_manifest(manifest)),
    }


# ── Workflow status ────────────────────────────────────────────────────────────


def get_workflow_status(project_id: str) -> dict[str, object]:
    """Return a pipeline-stage checklist for a project."""
    manifest = load_manifest(project_id)

    stages: dict[str, bool] = {
        "project_created": True,
        "assets_scanned": len(manifest.assets) > 0,
        "timelines_built": len(manifest.timelines) > 0,
        "otio_exported": all(
            bool(plan.otio_path) and Path(plan.otio_path).exists()
            for plan in manifest.timelines.values()
        ),
        "rendered": len(manifest.outputs) > 0,
        "all_platforms_rendered": all(p.value in manifest.outputs for p in manifest.platforms),
        "outputs_valid": all(output.ok for output in manifest.outputs.values()),
    }

    next_step: str | None = None
    if not stages["assets_scanned"]:
        next_step = "scan_project_assets"
    elif not stages["timelines_built"]:
        next_step = "create_timeline"
    elif not stages["otio_exported"]:
        next_step = "export_timeline"
    elif not stages["rendered"]:
        next_step = "render_all_variants"
    elif not stages["all_platforms_rendered"]:
        next_step = "render_all_variants (missing platforms)"
    elif not stages["outputs_valid"]:
        next_step = "validate_delivery_package (review failures)"

    return {
        "ok": all(stages.values()),
        "project_id": project_id,
        "project_name": manifest.name,
        "platforms": [p.value for p in manifest.platforms],
        "stages": stages,
        "next_step": next_step,
        "asset_count": len(manifest.assets),
        "timeline_count": len(manifest.timelines),
        "output_count": len(manifest.outputs),
        "timelines": {k: v.otio_path for k, v in manifest.timelines.items()},
        "outputs": {k: {"path": v.path, "ok": v.ok} for k, v in manifest.outputs.items()},
    }


# ── One-shot orchestrator ─────────────────────────────────────────────────────


def edit_video_from_prompt(
    prompt: str,
    project_name: str = "mvp-edit",
    input_dir: str = "data/input",
    music_path: str | None = None,
    platforms: list[Platform] | None = None,
    target_duration: float = 30,
    style: str | None = None,
    grade: str | None = None,
    render: bool = True,
    render_profile: str = "preview",
    dry_run: bool = False,
) -> dict[str, object]:
    """
    Full autonomous edit pipeline:
    1. Scan assets
    2. Probe footage
    3. Analyze music (if provided)
    4. Build beat-synced or simple edit plan
    5. Apply grading preset
    6. Render variants
    7. Export OTIO
    8. Validate delivery
    9. Return delivery manifest
    """
    selected_platforms = platforms or [Platform.widescreen]
    inferred_style = style or _infer_style(prompt)
    inferred_grade = grade or _infer_grade(prompt)
    events: list[dict[str, object]] = []

    events.append(event(
        "workflow_start", "started",
        prompt=prompt,
        platforms=[p.value for p in selected_platforms],
        inferred_style=inferred_style,
        inferred_grade=inferred_grade,
    ))

    try:
        # Step 1: Scan assets and create project
        events.append(event("create_project", "started", input_dir=input_dir))
        manifest = create_project(
            name=project_name,
            input_dir=input_dir,
            music_path=music_path,
            platforms=selected_platforms,
            prompt=prompt,
        )
        video_assets = [a for a in manifest.assets if a.ok and a.has_video]
        events.append(event(
            "create_project", "completed",
            project_id=manifest.project_id,
            asset_count=len(manifest.assets),
            usable_video_count=len(video_assets),
        ))

        # Step 2: Best-effort footage probe (logged, never fatal)
        footage_summaries: list[dict[str, object]] = []
        for asset in video_assets[:10]:  # cap at 10 to avoid blocking on large libraries
            vs = next((s for s in asset.streams if s.codec_type == "video"), None)
            footage_summaries.append({
                "path": asset.path,
                "duration": asset.duration,
                "resolution": f"{vs.width}x{vs.height}" if vs else None,
                "fps": vs.r_frame_rate if vs else None,
            })
        events.append(event("analyze_footage", "completed", clip_count=len(footage_summaries)))

        # Step 3: Analyze music
        beat_report: dict[str, object] | None = None
        if music_path:
            events.append(event("analyze_beats", "started", music_path=music_path))
            beat_report = analyze_beats(music_path)
            events.append(event(
                "analyze_beats",
                "completed" if beat_report.get("ok") else "failed",
                beat_count=beat_report.get("beat_count"),
                tempo=beat_report.get("tempo"),
                error=beat_report.get("error"),
            ))

        # Steps 4–5: Build timeline + export OTIO per platform
        for platform in selected_platforms:
            if beat_report and beat_report.get("ok"):
                events.append(event("plan_beat_synced_edit", "started", platform=platform.value))
                plan_result = plan_beat_synced_edit(
                    project_id=manifest.project_id,
                    platform=platform,
                    target_duration=target_duration,
                    style=inferred_style,
                    beat_times=[float(v) for v in beat_report.get("beat_times", [])],
                    tempo=float(beat_report["tempo"]),
                )
                events.append(event(
                    "plan_beat_synced_edit", "completed",
                    platform=platform.value,
                    clip_count=len(plan_result["edit_plan"]["clips"]),
                ))
                events.append(event("apply_edit_plan", "started", platform=platform.value))
                apply_result = apply_beat_edit_plan(project_id=manifest.project_id, platform=platform)
                manifest = load_manifest(manifest.project_id)
                events.append(event(
                    "apply_edit_plan",
                    "completed" if apply_result.get("ok") else "failed",
                    platform=platform.value,
                    otio_path=apply_result.get("otio_path"),
                ))
            else:
                events.append(event("create_timeline", "started", platform=platform.value))
                manifest = build_timeline_for_project(manifest, platform, target_duration=target_duration)
                events.append(event(
                    "create_timeline", "completed",
                    platform=platform.value,
                    clip_count=len(manifest.timelines[platform.value].clips),
                    otio_path=manifest.timelines[platform.value].otio_path,
                ))

            # Step 5: Apply grading preset if inferred or requested
            if inferred_grade and inferred_grade in GRADING_PRESETS:
                events.append(event("apply_grade", "started", platform=platform.value, preset=inferred_grade))
                grade_result = apply_grading_preset(
                    project_id=manifest.project_id,
                    platform=platform,
                    preset=inferred_grade,
                )
                manifest = load_manifest(manifest.project_id)
                events.append(event(
                    "apply_grade",
                    "completed" if grade_result.get("ok") else "skipped",
                    platform=platform.value,
                    preset=inferred_grade,
                    clips_affected=grade_result.get("clips_affected", 0),
                ))

            # Step 6: Render
            if render:
                events.append(event("render_project", "started", platform=platform.value))
                manifest = render_and_validate_project(
                    manifest, platform, render_profile=render_profile, dry_run=dry_run,
                )
                output = manifest.outputs[platform.value]
                events.append(event(
                    "render_project",
                    "completed" if output.ok else "failed",
                    platform=platform.value,
                    output_path=output.path,
                ))

        # Steps 7–9: OTIO already exported above; run delivery validation
        delivery: dict[str, object] = {"skipped": True}
        if render and not dry_run:
            events.append(event("validate_delivery", "started"))
            try:
                delivery = validate_delivery_package(manifest.project_id)
                events.append(event(
                    "validate_delivery",
                    "completed" if delivery.get("ok") else "failed",
                    issues_count=len(delivery.get("issues", [])),
                ))
            except Exception as val_exc:
                events.append(event("validate_delivery", "failed", error=str(val_exc)))
                delivery = {"skipped": False, "ok": False, "error": str(val_exc)}

        overall_ok = (
            all(output.ok for output in manifest.outputs.values())
            if render
            else True
        )
        events.append(event("workflow_end", "completed" if overall_ok else "failed"))

        return {
            "ok": overall_ok,
            "project_id": manifest.project_id,
            "project_name": manifest.name,
            "manifest_path": str(save_manifest(manifest)),
            "inferred_style": inferred_style,
            "inferred_grade": inferred_grade,
            "footage_analyzed": len(footage_summaries),
            "beat_report": beat_report,
            "timelines": {key: plan.otio_path for key, plan in manifest.timelines.items()},
            "outputs": {key: output.model_dump() for key, output in manifest.outputs.items()},
            "delivery": delivery,
            "events": events,
        }

    except Exception as exc:
        events.append(event("workflow", "failed", error=exception_issue(exc).model_dump()))
        raise WorkflowError(exception_issue(exc), events) from exc
