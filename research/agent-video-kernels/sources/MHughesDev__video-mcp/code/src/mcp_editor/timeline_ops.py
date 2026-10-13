from __future__ import annotations

from typing import Any

from .projects import load_manifest, save_manifest
from .schemas import Platform, ProjectManifest, TimelinePlan
from .timeline import (
    add_clip,
    add_transition,
    export_otio,
    move_clip,
    split_clip,
    trim_clip,
    validate_timeline,
)


def _platform_key(platform: Platform) -> str:
    return platform.value


def get_or_create_timeline(manifest: ProjectManifest, platform: Platform) -> TimelinePlan:
    key = _platform_key(platform)
    if key not in manifest.timelines:
        manifest.timelines[key] = TimelinePlan(project_id=manifest.project_id, platform=platform, clips=[])
    return manifest.timelines[key]


def persist_timeline(manifest: ProjectManifest, plan: TimelinePlan) -> dict[str, Any]:
    otio_path = export_otio(plan)
    plan.otio_path = str(otio_path)
    manifest.timelines[_platform_key(plan.platform)] = plan
    manifest_path = save_manifest(manifest)
    validation = validate_timeline(plan)
    return {
        "ok": validation["ok"],
        "project_id": manifest.project_id,
        "platform": plan.platform.value,
        "timeline": plan.model_dump(),
        "validation": validation,
        "otio_path": str(otio_path),
        "manifest_path": str(manifest_path),
    }


def add_clip_to_project(
    project_id: str,
    platform: Platform,
    source: str,
    start: float = 0,
    duration: float = 4,
    label: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    plan = get_or_create_timeline(manifest, platform)
    add_clip(plan, source=source, start=start, duration=duration, label=label, index=index)
    return persist_timeline(manifest, plan)


def trim_clip_in_project(
    project_id: str,
    platform: Platform,
    clip_id: str | None = None,
    index: int | None = None,
    start: float | None = None,
    duration: float | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    plan = get_or_create_timeline(manifest, platform)
    trim_clip(plan, clip_id=clip_id, index=index, start=start, duration=duration)
    return persist_timeline(manifest, plan)


def split_clip_in_project(
    project_id: str,
    platform: Platform,
    split_at: float,
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    plan = get_or_create_timeline(manifest, platform)
    split_clip(plan, split_at=split_at, clip_id=clip_id, index=index)
    return persist_timeline(manifest, plan)


def move_clip_in_project(project_id: str, platform: Platform, from_index: int, to_index: int) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    plan = get_or_create_timeline(manifest, platform)
    move_clip(plan, from_index=from_index, to_index=to_index)
    return persist_timeline(manifest, plan)


def add_transition_to_project(
    project_id: str,
    platform: Platform,
    from_clip_id: str,
    to_clip_id: str,
    transition_type: str = "crossfade",
    duration: float = 0.5,
) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    plan = get_or_create_timeline(manifest, platform)
    add_transition(
        plan,
        from_clip_id=from_clip_id,
        to_clip_id=to_clip_id,
        transition_type=transition_type,
        duration=duration,
    )
    return persist_timeline(manifest, plan)


def export_timeline_for_project(project_id: str, platform: Platform) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    plan = get_or_create_timeline(manifest, platform)
    return persist_timeline(manifest, plan)


def validate_timeline_for_project(project_id: str, platform: Platform) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    plan = get_or_create_timeline(manifest, platform)
    validation = validate_timeline(plan)
    return {
        "ok": validation["ok"],
        "project_id": manifest.project_id,
        "platform": platform.value,
        "validation": validation,
        "timeline": plan.model_dump(),
    }
