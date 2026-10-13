from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .beat_sync import analyze_beats as analyze_beats_impl
from .effects import apply_motion_effects as apply_motion_effects_impl
from .grading import apply_grading_preset as apply_grading_preset_impl
from .logging import get_project_log_summary
from .grading import apply_lut as apply_lut_impl
from .grading import inspect_lut as inspect_lut_impl
from .grading import list_grading_presets as list_grading_presets_impl
from .grading import list_luts as list_luts_impl
from .grading import render_with_grade as render_with_grade_impl
from .effects import apply_reframe as apply_reframe_impl
from .effects import apply_smash_cut as apply_smash_cut_impl
from .effects import apply_speed_ramp as apply_speed_ramp_impl
from .effects import apply_zoom_punch as apply_zoom_punch_impl
from .effects import remove_clip_effect as remove_clip_effect_impl
from .beat_sync import apply_edit_plan as apply_edit_plan_impl
from .beat_sync import plan_beat_synced_edit as plan_beat_synced_edit_impl
from .beat_sync import suggest_cut_points as suggest_cut_points_impl
from .diagnostics import failed_tool_result
from .inspection import analyze_audio_metadata as analyze_audio_metadata_impl
from .inspection import analyze_video_metadata as analyze_video_metadata_impl
from .inspection import detect_scenes as detect_scenes_impl
from .inspection import generate_thumbnails as generate_thumbnails_impl
from .inspection import inspect_project as inspect_project_impl
from .inspection import scan_project_assets as scan_project_assets_impl
from .media import probe_media as probe_media_impl
from .media import scan_assets as scan_assets_impl
from .projects import load_manifest, save_manifest
from .render import plan_render_timeline as plan_render_timeline_impl
from .render import render_manifest_summary
from .schemas import Platform
from .timeline_ops import add_clip_to_project
from .timeline_ops import add_transition_to_project
from .timeline_ops import export_timeline_for_project
from .timeline_ops import move_clip_in_project
from .timeline_ops import split_clip_in_project
from .timeline_ops import trim_clip_in_project
from .timeline_ops import validate_timeline_for_project
from .validation import validate_audio as validate_audio_impl
from .validation import validate_delivery_package as validate_delivery_package_impl
from .validation import validate_platform_outputs as validate_platform_outputs_impl
from .validation import validate_render as validate_render_impl
from .workflow import (
    build_timeline_for_project,
    create_project as create_project_impl,
    edit_video_from_prompt as edit_video_from_prompt_impl,
    get_workflow_status as get_workflow_status_impl,
    render_all_variants as render_all_variants_impl,
    render_and_validate_project,
    render_platform_variant as render_platform_variant_impl,
)
from .sourcing import download_asset as download_asset_impl
from .references import (
    add_reference as add_reference_impl,
    list_references as list_references_impl,
    get_reference as get_reference_impl,
    remove_reference as remove_reference_impl,
)
from .media_docs import (
    create_media_doc as create_media_doc_impl,
    get_media_doc as get_media_doc_impl,
    list_media_docs as list_media_docs_impl,
    auto_generate_doc as auto_generate_doc_impl,
)

app = FastMCP(
    "mcp-editor",
    instructions=(
        "Local-first video editing MCP server. Tools inspect existing media, "
        "build simple OTIO timelines, render via FFmpeg, and validate outputs."
    ),
)


def _platforms(values: list[str] | None) -> list[Platform]:
    if not values:
        return [Platform.widescreen]
    return [Platform(value) for value in values]


def _error(exc: Exception) -> dict[str, object]:
    return failed_tool_result(exc)


@app.tool()
def scan_assets(input_dir: str = "data/input") -> dict[str, object]:
    """Scan a directory for local video assets and return FFprobe metadata."""
    try:
        assets = scan_assets_impl(input_dir, include_audio=False)
        return {"ok": True, "input_dir": str(Path(input_dir)), "assets": [asset.model_dump() for asset in assets]}
    except Exception as exc:
        return _error(exc)


@app.tool()
def scan_project_assets(input_dir: str = "data/input", include_audio: bool = True) -> dict[str, object]:
    """Scan project assets with aggregate media counts and probe diagnostics."""
    try:
        return scan_project_assets_impl(input_dir=input_dir, include_audio=include_audio)
    except Exception as exc:
        return _error(exc)


@app.tool()
def probe_media(path: str) -> dict[str, object]:
    """Probe one media file with FFprobe."""
    try:
        probe = probe_media_impl(path)
        return probe.model_dump()
    except Exception as exc:
        return _error(exc)


@app.tool()
def analyze_video_metadata(path: str) -> dict[str, object]:
    """Return video-focused metadata for one media file."""
    try:
        return analyze_video_metadata_impl(path)
    except Exception as exc:
        return _error(exc)


@app.tool()
def analyze_audio_metadata(path: str) -> dict[str, object]:
    """Return audio-focused metadata for one media file."""
    try:
        return analyze_audio_metadata_impl(path)
    except Exception as exc:
        return _error(exc)


@app.tool()
def detect_scenes(path: str, threshold: float = 0.35, min_scene_gap: float = 0.5) -> dict[str, object]:
    """Detect likely scene-cut timestamps with FFmpeg scene scoring."""
    try:
        return detect_scenes_impl(path, threshold=threshold, min_scene_gap=min_scene_gap)
    except Exception as exc:
        return _error(exc)


@app.tool()
def generate_thumbnails(path: str, output_directory: str | None = None, count: int = 5) -> dict[str, object]:
    """Generate representative thumbnails for a video file."""
    try:
        return generate_thumbnails_impl(path, output_directory=output_directory, count=count)
    except Exception as exc:
        return _error(exc)


@app.tool()
def inspect_project(project_id: str) -> dict[str, object]:
    """Inspect a saved project manifest, timelines, outputs, and asset state."""
    try:
        return inspect_project_impl(project_id)
    except Exception as exc:
        return _error(exc)


@app.tool()
def create_project(
    name: str,
    input_dir: str = "data/input",
    music_path: str | None = None,
    platforms: list[str] | None = None,
    prompt: str | None = None,
) -> dict[str, object]:
    """Create a project manifest from local assets."""
    try:
        manifest = create_project_impl(
            name=name,
            input_dir=input_dir,
            music_path=music_path,
            platforms=_platforms(platforms),
            prompt=prompt,
        )
        return {"ok": True, "manifest": manifest.model_dump(), "manifest_path": str(save_manifest(manifest))}
    except Exception as exc:
        return _error(exc)


@app.tool()
def analyze_beats(music_path: str) -> dict[str, object]:
    """Analyze music tempo and beat timestamps with librosa."""
    try:
        return analyze_beats_impl(music_path)
    except Exception as exc:
        return _error(exc)


@app.tool()
def suggest_cut_points(
    beat_times: list[float] | None = None,
    target_duration: float = 30,
    style: str = "medium",
    tempo: float | None = None,
) -> dict[str, object]:
    """Suggest timeline cut points from beat times, tempo, target duration, and pacing style."""
    try:
        return suggest_cut_points_impl(
            beat_times=beat_times,
            target_duration=target_duration,
            style=style,
            tempo=tempo,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def plan_beat_synced_edit(
    project_id: str,
    platform: str = "16:9",
    target_duration: float = 30,
    style: str = "medium",
    beat_times: list[float] | None = None,
    tempo: float | None = None,
) -> dict[str, object]:
    """Create and save a deterministic beat-synced edit plan for a project."""
    try:
        return plan_beat_synced_edit_impl(
            project_id=project_id,
            platform=Platform(platform),
            target_duration=target_duration,
            style=style,
            beat_times=beat_times,
            tempo=tempo,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def apply_edit_plan(project_id: str, platform: str = "16:9") -> dict[str, object]:
    """Apply a saved beat edit plan to a project timeline and export OTIO."""
    try:
        return apply_edit_plan_impl(project_id=project_id, platform=Platform(platform))
    except Exception as exc:
        return _error(exc)


@app.tool()
def create_timeline(project_id: str, platform: str = "16:9", target_duration: float = 30) -> dict[str, object]:
    """Create a simple sequential OTIO timeline for a project."""
    try:
        manifest = load_manifest(project_id)
        manifest = build_timeline_for_project(manifest, Platform(platform), target_duration=target_duration)
        plan = manifest.timelines[platform]
        return {"ok": True, "project_id": project_id, "timeline": plan.model_dump(), "manifest_path": str(save_manifest(manifest))}
    except Exception as exc:
        return _error(exc)


@app.tool()
def add_clip(
    project_id: str,
    source: str,
    platform: str = "16:9",
    start: float = 0,
    duration: float = 4,
    label: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    """Add a clip to a project timeline and refresh the OTIO export."""
    try:
        return add_clip_to_project(
            project_id=project_id,
            platform=Platform(platform),
            source=source,
            start=start,
            duration=duration,
            label=label,
            index=index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def trim_clip(
    project_id: str,
    platform: str = "16:9",
    clip_id: str | None = None,
    index: int | None = None,
    start: float | None = None,
    duration: float | None = None,
) -> dict[str, object]:
    """Trim a clip by clip_id or index and refresh the OTIO export."""
    try:
        return trim_clip_in_project(
            project_id=project_id,
            platform=Platform(platform),
            clip_id=clip_id,
            index=index,
            start=start,
            duration=duration,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def split_clip(
    project_id: str,
    split_at: float,
    platform: str = "16:9",
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    """Split a clip into two timeline clips and refresh the OTIO export."""
    try:
        return split_clip_in_project(
            project_id=project_id,
            platform=Platform(platform),
            split_at=split_at,
            clip_id=clip_id,
            index=index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def move_clip(project_id: str, from_index: int, to_index: int, platform: str = "16:9") -> dict[str, object]:
    """Move a clip within a project timeline and refresh the OTIO export."""
    try:
        return move_clip_in_project(
            project_id=project_id,
            platform=Platform(platform),
            from_index=from_index,
            to_index=to_index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def add_transition(
    project_id: str,
    from_clip_id: str,
    to_clip_id: str,
    platform: str = "16:9",
    transition_type: str = "crossfade",
    duration: float = 0.5,
) -> dict[str, object]:
    """Add a transition between adjacent timeline clips and refresh the OTIO export."""
    try:
        return add_transition_to_project(
            project_id=project_id,
            platform=Platform(platform),
            from_clip_id=from_clip_id,
            to_clip_id=to_clip_id,
            transition_type=transition_type,
            duration=duration,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def export_timeline(project_id: str, platform: str = "16:9") -> dict[str, object]:
    """Export the current project timeline to OTIO."""
    try:
        return export_timeline_for_project(project_id=project_id, platform=Platform(platform))
    except Exception as exc:
        return _error(exc)


@app.tool()
def validate_timeline(project_id: str, platform: str = "16:9") -> dict[str, object]:
    """Validate a project timeline without rendering it."""
    try:
        return validate_timeline_for_project(project_id=project_id, platform=Platform(platform))
    except Exception as exc:
        return _error(exc)


@app.tool()
def plan_render(project_id: str, platform: str = "16:9", render_profile: str = "preview") -> dict[str, object]:
    """Plan FFmpeg render commands for a project timeline without executing them."""
    try:
        manifest = load_manifest(project_id)
        plan = manifest.timelines.get(platform)
        if plan is None:
            manifest = build_timeline_for_project(manifest, Platform(platform))
            plan = manifest.timelines[platform]
        render_manifest = plan_render_timeline_impl(plan, render_profile=render_profile, validate_sources=False)
        render_manifest.dry_run = True
        return render_manifest_summary(render_manifest)
    except Exception as exc:
        return _error(exc)


@app.tool()
def render_project(
    project_id: str,
    platform: str = "16:9",
    render_profile: str = "preview",
    dry_run: bool = False,
) -> dict[str, object]:
    """Render or dry-run one project timeline with FFmpeg and validate the output."""
    try:
        return render_platform_variant_impl(
            project_id=project_id,
            platform=Platform(platform),
            render_profile=render_profile,
            dry_run=dry_run,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def render_platform_variant(
    project_id: str,
    platform: str,
    render_profile: str = "preview",
    dry_run: bool = False,
) -> dict[str, object]:
    """Render or dry-run one platform variant for a project."""
    try:
        return render_platform_variant_impl(
            project_id=project_id,
            platform=Platform(platform),
            render_profile=render_profile,
            dry_run=dry_run,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def render_all_variants(
    project_id: str,
    platforms: list[str] | None = None,
    render_profile: str = "preview",
    dry_run: bool = False,
) -> dict[str, object]:
    """Render or dry-run all requested platform variants for a project."""
    try:
        return render_all_variants_impl(
            project_id=project_id,
            platforms=_platforms(platforms) if platforms else None,
            render_profile=render_profile,
            dry_run=dry_run,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def validate_output(
    path: str,
    platform: str = "16:9",
    expected_duration: float | None = None,
    expected_fps: float = 30.0,
    check_black: bool = True,
    check_silent: bool = True,
    check_frozen: bool = True,
) -> dict[str, object]:
    """Validate a rendered video file with comprehensive checks (resolution, FPS, black frames, silence, freezes)."""
    try:
        return validate_render_impl(
            path,
            Platform(platform),
            expected_duration=expected_duration,
            expected_fps=expected_fps,
            check_black=check_black,
            check_silent=check_silent,
            check_frozen=check_frozen,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def validate_audio(path: str, expected_duration: float | None = None) -> dict[str, object]:
    """Validate the audio track of a rendered file (existence, codec, silence detection)."""
    try:
        return validate_audio_impl(path, expected_duration=expected_duration)
    except Exception as exc:
        return _error(exc)


@app.tool()
def validate_platform_outputs(project_id: str) -> dict[str, object]:
    """Validate all rendered platform outputs for a project against their expected specs."""
    try:
        return validate_platform_outputs_impl(project_id)
    except Exception as exc:
        return _error(exc)


@app.tool()
def validate_delivery_package(project_id: str) -> dict[str, object]:
    """Full delivery gate: validate renders, OTIO exports, and manifest completeness."""
    try:
        return validate_delivery_package_impl(project_id)
    except Exception as exc:
        return _error(exc)


@app.tool()
def edit_video_from_prompt(
    prompt: str,
    project_name: str = "mvp-edit",
    input_dir: str = "data/input",
    music_path: str | None = None,
    platforms: list[str] | None = None,
    target_duration: float = 30,
    style: str | None = None,
    grade: str | None = None,
    render: bool = True,
    render_profile: str = "preview",
    dry_run: bool = False,
) -> dict[str, object]:
    """
    Full autonomous edit pipeline from a natural language prompt.
    Infers pacing style and grading preset from prompt keywords.
    Steps: scan → probe footage → analyze music → build edit plan →
    apply grade → render variants → export OTIO → validate delivery.
    """
    try:
        return edit_video_from_prompt_impl(
            prompt=prompt,
            project_name=project_name,
            input_dir=input_dir,
            music_path=music_path,
            platforms=_platforms(platforms),
            target_duration=target_duration,
            style=style,
            grade=grade,
            render=render,
            render_profile=render_profile,
            dry_run=dry_run,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def get_project_logs(project_id: str) -> dict[str, object]:
    """Return structured log records for a project (errors, warnings, render timings)."""
    try:
        return get_project_log_summary(project_id)
    except Exception as exc:
        return _error(exc)


@app.tool()
def get_workflow_status(project_id: str) -> dict[str, object]:
    """Return a pipeline-stage checklist showing what's done and what's next for a project."""
    try:
        return get_workflow_status_impl(project_id)
    except Exception as exc:
        return _error(exc)


@app.tool()
def apply_speed_ramp(
    project_id: str,
    speed: float,
    platform: str = "16:9",
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    """Apply a speed ramp to a clip. speed > 1 is faster, speed < 1 is slower."""
    try:
        return apply_speed_ramp_impl(
            project_id=project_id,
            platform=Platform(platform),
            speed=speed,
            clip_id=clip_id,
            index=index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def apply_zoom_punch(
    project_id: str,
    zoom: float = 1.2,
    platform: str = "16:9",
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    """Apply a punch zoom to a clip. zoom is a scale multiplier > 1.0 (e.g. 1.2 = 20% in)."""
    try:
        return apply_zoom_punch_impl(
            project_id=project_id,
            platform=Platform(platform),
            zoom=zoom,
            clip_id=clip_id,
            index=index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def apply_smash_cut(
    project_id: str,
    from_clip_id: str,
    to_clip_id: str,
    platform: str = "16:9",
) -> dict[str, object]:
    """Remove any transition between two adjacent clips, making it a hard cut."""
    try:
        return apply_smash_cut_impl(
            project_id=project_id,
            platform=Platform(platform),
            from_clip_id=from_clip_id,
            to_clip_id=to_clip_id,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def apply_reframe(
    project_id: str,
    x_pct: float = 0.0,
    y_pct: float = 0.0,
    crop_pct: float = 0.9,
    platform: str = "16:9",
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    """Reframe a clip by cropping with a center offset. x_pct/y_pct shift the crop window."""
    try:
        return apply_reframe_impl(
            project_id=project_id,
            platform=Platform(platform),
            x_pct=x_pct,
            y_pct=y_pct,
            crop_pct=crop_pct,
            clip_id=clip_id,
            index=index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def apply_motion_effects(
    project_id: str,
    effects: list[dict],
    platform: str = "16:9",
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    """Apply multiple effects to a single clip in one call. Each effect needs effect_type and params."""
    try:
        return apply_motion_effects_impl(
            project_id=project_id,
            platform=Platform(platform),
            effects=effects,
            clip_id=clip_id,
            index=index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def remove_clip_effect(
    project_id: str,
    effect_type: str,
    platform: str = "16:9",
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    """Remove a specific effect from a clip by effect_type."""
    try:
        return remove_clip_effect_impl(
            project_id=project_id,
            platform=Platform(platform),
            effect_type=effect_type,
            clip_id=clip_id,
            index=index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def list_luts() -> dict[str, object]:
    """List all .cube LUT files available in data/luts/."""
    try:
        return list_luts_impl()
    except Exception as exc:
        return _error(exc)


@app.tool()
def inspect_lut(name_or_path: str) -> dict[str, object]:
    """Inspect a .cube LUT file and return its metadata (size, type, domain)."""
    try:
        return inspect_lut_impl(name_or_path)
    except Exception as exc:
        return _error(exc)


@app.tool()
def apply_lut(
    project_id: str,
    lut_name: str,
    platform: str = "16:9",
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    """Apply a .cube LUT grade to a clip (or all clips if no clip_id/index given)."""
    try:
        return apply_lut_impl(
            project_id=project_id,
            platform=Platform(platform),
            lut_name=lut_name,
            clip_id=clip_id,
            index=index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def list_grading_presets() -> dict[str, object]:
    """List built-in grading presets (cinematic, vivid, flat, bw, warm, cool)."""
    try:
        return list_grading_presets_impl()
    except Exception as exc:
        return _error(exc)


@app.tool()
def apply_grading_preset(
    project_id: str,
    preset: str,
    platform: str = "16:9",
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, object]:
    """Apply a named grading preset to a clip or all clips in a timeline."""
    try:
        return apply_grading_preset_impl(
            project_id=project_id,
            platform=Platform(platform),
            preset=preset,
            clip_id=clip_id,
            index=index,
        )
    except Exception as exc:
        return _error(exc)


@app.tool()
def render_with_grade(
    project_id: str,
    platform: str = "16:9",
    render_profile: str = "preview",
    dry_run: bool = False,
) -> dict[str, object]:
    """Render a timeline with all grading effects baked into the FFmpeg filter chain."""
    try:
        return render_with_grade_impl(
            project_id=project_id,
            platform=Platform(platform),
            render_profile=render_profile,
            dry_run=dry_run,
        )
    except Exception as exc:
        return _error(exc)


# ---------------------------------------------------------------------------
# Asset sourcing
# ---------------------------------------------------------------------------

@app.tool()
def download_asset(
    url: str,
    destination: str,
    filename: str | None = None,
) -> dict[str, object]:
    """Download a media file from a URL into the workspace.
    destination must be one of: input, music, references.
    Handles YouTube, Vimeo, SoundCloud, and 1000+ sites via yt-dlp,
    plus direct file URLs (mp4, mp3, jpg, png, etc.) via HTTP.
    filename is optional — inferred from the URL if omitted."""
    try:
        return download_asset_impl(url=url, destination=destination, filename=filename)
    except Exception as exc:
        return _error(exc)


# ---------------------------------------------------------------------------
# Reference library
# ---------------------------------------------------------------------------

@app.tool()
def add_reference(
    path: str,
    tags: list[str] | None = None,
    notes: str = "",
) -> dict[str, object]:
    """Add a media file to the reference/inspiration library.
    Does not add it to any timeline — it is kept separate as a research asset.
    tags are free-form strings used for filtering."""
    try:
        return add_reference_impl(path=path, tags=tags or [], notes=notes)
    except Exception as exc:
        return _error(exc)


@app.tool()
def list_references(tags: list[str] | None = None) -> dict[str, object]:
    """List all reference assets, optionally filtered by tags.
    Passing multiple tags requires ALL of them to match (AND filter)."""
    try:
        return list_references_impl(tags=tags or [])
    except Exception as exc:
        return _error(exc)


@app.tool()
def get_reference(ref_id: str) -> dict[str, object]:
    """Get a single reference asset by its ref_id."""
    try:
        return get_reference_impl(ref_id=ref_id)
    except Exception as exc:
        return _error(exc)


@app.tool()
def remove_reference(ref_id: str) -> dict[str, object]:
    """Remove a reference from the library.
    Deletes the companion .md doc if present. Does not delete the media file itself."""
    try:
        return remove_reference_impl(ref_id=ref_id)
    except Exception as exc:
        return _error(exc)


# ---------------------------------------------------------------------------
# Media comprehension documents
# ---------------------------------------------------------------------------

@app.tool()
def create_media_doc(path: str, doc_data: dict) -> dict[str, object]:
    """Create or update a comprehension document for a media file.
    doc_data must match the schema for the file type (VideoDoc / ImageDoc / AudioDoc).
    Writes a human-readable .md sidecar and a machine-readable .meta.json sidecar.
    Use auto_generate_doc first to get pre-filled technical fields."""
    try:
        return create_media_doc_impl(media_path=path, doc_data=doc_data)
    except Exception as exc:
        return _error(exc)


@app.tool()
def get_media_doc(path: str) -> dict[str, object]:
    """Read the comprehension document for a media file.
    Returns the full structured doc and paths to the .md and .meta.json files."""
    try:
        return get_media_doc_impl(media_path=path)
    except Exception as exc:
        return _error(exc)


@app.tool()
def list_media_docs(directory: str = "data/input") -> dict[str, object]:
    """List all media files in a directory that have comprehension documents."""
    try:
        return list_media_docs_impl(directory=directory)
    except Exception as exc:
        return _error(exc)


@app.tool()
def auto_generate_doc(path: str) -> dict[str, object]:
    """Auto-generate a partial comprehension document for a media file.
    Extracts all technically derivable fields (resolution, fps, bpm, etc.)
    and returns keyframe image paths for video/image files so the calling
    agent can visually analyze them.
    Workflow: call this → analyze keyframes → call create_media_doc with complete doc_data."""
    try:
        return auto_generate_doc_impl(media_path=path)
    except Exception as exc:
        return _error(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the mcp-editor MCP server.")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.transport == "stdio":
        app.run("stdio")
        return

    app.settings.host = args.host
    app.settings.port = args.port
    app.run(args.transport)


if __name__ == "__main__":
    main()
