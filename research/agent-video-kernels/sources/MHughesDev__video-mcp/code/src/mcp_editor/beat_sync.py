from __future__ import annotations

from pathlib import Path
from typing import Any

import librosa

from .diagnostics import McpEditorError, no_video_assets
from .diagnostics import media_not_found
from .projects import load_manifest, save_manifest
from .schemas import BeatEditPlan, EditPlanClip, Platform, ProjectManifest, TimelinePlan, as_path
from .timeline import export_otio, validate_timeline


def analyze_beats(music_path: str | Path) -> dict[str, object]:
    path = as_path(music_path)
    if not path.exists():
        issue = media_not_found(str(path))
        return {"ok": False, "path": str(path), "error": issue.model_dump()}

    y, sr = librosa.load(str(path), sr=None, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    return {
        "ok": True,
        "path": str(path),
        "sample_rate": sr,
        "tempo": float(tempo[0] if hasattr(tempo, "__len__") else tempo),
        "beat_count": int(len(beat_times)),
        "beat_times": [float(time) for time in beat_times],
    }


STYLE_BEAT_MULTIPLIERS: dict[str, int] = {
    "fast": 1,
    "social": 1,
    "trailer": 2,
    "medium": 2,
    "documentary": 4,
    "slow": 4,
}


def _fallback_cut_points(target_duration: float, interval: float) -> list[float]:
    points: list[float] = [0.0]
    cursor = interval
    while cursor < target_duration:
        points.append(round(cursor, 3))
        cursor += interval
    if points[-1] < target_duration:
        points.append(round(target_duration, 3))
    return points


def suggest_cut_points(
    beat_times: list[float] | None = None,
    target_duration: float = 30,
    style: str = "medium",
    tempo: float | None = None,
) -> dict[str, Any]:
    if target_duration <= 0:
        raise ValueError("target_duration must be > 0")

    multiplier = STYLE_BEAT_MULTIPLIERS.get(style, STYLE_BEAT_MULTIPLIERS["medium"])
    usable_beats = sorted(float(beat) for beat in (beat_times or []) if 0 <= float(beat) <= target_duration)

    if usable_beats:
        if usable_beats[0] > 0:
            usable_beats.insert(0, 0.0)
        selected = usable_beats[::multiplier]
        if selected[-1] < target_duration:
            selected.append(float(target_duration))
    else:
        bpm = tempo or 120
        beat_interval = 60.0 / bpm
        selected = _fallback_cut_points(target_duration, beat_interval * multiplier)

    cut_points: list[float] = []
    for point in selected:
        rounded = round(min(max(point, 0), target_duration), 3)
        if not cut_points or rounded > cut_points[-1]:
            cut_points.append(rounded)

    return {
        "ok": True,
        "style": style,
        "target_duration": target_duration,
        "beat_multiplier": multiplier,
        "cut_count": max(0, len(cut_points) - 1),
        "cut_points": cut_points,
    }


def _usable_video_assets(manifest: ProjectManifest) -> list[str]:
    return [asset.path for asset in manifest.assets if asset.ok and asset.has_video]


def plan_beat_synced_edit_for_manifest(
    manifest: ProjectManifest,
    platform: Platform = Platform.widescreen,
    target_duration: float = 30,
    style: str = "medium",
    beat_times: list[float] | None = None,
    tempo: float | None = None,
) -> BeatEditPlan:
    assets = _usable_video_assets(manifest)
    if not assets:
        raise McpEditorError(no_video_assets(manifest.input_dir))

    beat_report: dict[str, Any] | None = None
    if beat_times is None and manifest.music_path:
        beat_report = analyze_beats(manifest.music_path)
        if beat_report.get("ok"):
            beat_times = [float(value) for value in beat_report.get("beat_times", [])]
            tempo = float(beat_report["tempo"])

    cut_report = suggest_cut_points(
        beat_times=beat_times,
        target_duration=target_duration,
        style=style,
        tempo=tempo,
    )
    cut_points = [float(value) for value in cut_report["cut_points"]]
    clips: list[EditPlanClip] = []

    for index, (start, end) in enumerate(zip(cut_points, cut_points[1:])):
        duration = round(end - start, 3)
        if duration <= 0:
            continue
        source = assets[index % len(assets)]
        clips.append(
            EditPlanClip(
                source=source,
                start=0,
                duration=duration,
                beat_time=start,
                label=f"{style}-{index + 1:03d}",
            )
        )

    return BeatEditPlan(
        project_id=manifest.project_id,
        platform=platform,
        style=style,
        target_duration=target_duration,
        music_path=manifest.music_path,
        tempo=tempo if tempo is not None else (float(beat_report["tempo"]) if beat_report and beat_report.get("ok") else None),
        cut_points=cut_points,
        clips=clips,
    )


def plan_beat_synced_edit(
    project_id: str,
    platform: Platform = Platform.widescreen,
    target_duration: float = 30,
    style: str = "medium",
    beat_times: list[float] | None = None,
    tempo: float | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    edit_plan = plan_beat_synced_edit_for_manifest(
        manifest=manifest,
        platform=platform,
        target_duration=target_duration,
        style=style,
        beat_times=beat_times,
        tempo=tempo,
    )
    manifest.edit_plans[platform.value] = edit_plan
    manifest_path = save_manifest(manifest)
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "edit_plan": edit_plan.model_dump(),
        "manifest_path": str(manifest_path),
    }


def apply_edit_plan(project_id: str, platform: Platform = Platform.widescreen) -> dict[str, Any]:
    manifest = load_manifest(project_id)
    edit_plan = manifest.edit_plans.get(platform.value)
    if edit_plan is None:
        edit_plan = plan_beat_synced_edit_for_manifest(manifest=manifest, platform=platform)
        manifest.edit_plans[platform.value] = edit_plan

    timeline = TimelinePlan(
        project_id=manifest.project_id,
        platform=platform,
        clips=[
            {
                "source": clip.source,
                "start": clip.start,
                "duration": clip.duration,
                "label": clip.label,
            }
            for clip in edit_plan.clips
        ],
        music_path=edit_plan.music_path,
        target_duration=edit_plan.target_duration,
    )
    otio_path = export_otio(timeline)
    timeline.otio_path = str(otio_path)
    manifest.timelines[platform.value] = timeline
    manifest_path = save_manifest(manifest)
    validation = validate_timeline(timeline)

    return {
        "ok": validation["ok"],
        "project_id": project_id,
        "platform": platform.value,
        "timeline": timeline.model_dump(),
        "validation": validation,
        "otio_path": str(otio_path),
        "manifest_path": str(manifest_path),
    }
