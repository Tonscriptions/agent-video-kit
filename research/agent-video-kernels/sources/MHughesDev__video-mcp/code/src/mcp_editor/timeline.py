from __future__ import annotations

from pathlib import Path
from typing import Any

import opentimelineio as otio

from .projects import project_dir
from .schemas import Platform, TimelineClip, TimelinePlan, TimelineTransition, as_path


def make_simple_timeline_plan(
    project_id: str,
    asset_paths: list[str],
    platform: Platform = Platform.widescreen,
    target_duration: float | None = 30,
    default_clip_duration: float = 4,
    music_path: str | None = None,
) -> TimelinePlan:
    clips: list[TimelineClip] = []
    remaining = target_duration

    for asset in asset_paths:
        if remaining is not None and remaining <= 0:
            break
        duration = default_clip_duration if remaining is None else min(default_clip_duration, remaining)
        clips.append(TimelineClip(source=str(as_path(asset)), start=0, duration=duration))
        if remaining is not None:
            remaining -= duration

    return TimelinePlan(
        project_id=project_id,
        platform=platform,
        clips=clips,
        music_path=str(as_path(music_path)) if music_path else None,
        target_duration=target_duration,
    )


def timeline_duration(plan: TimelinePlan) -> float:
    return sum(clip.duration for clip in plan.clips)


def find_clip_index(plan: TimelinePlan, clip_id: str | None = None, index: int | None = None) -> int:
    if index is not None:
        if index < 0 or index >= len(plan.clips):
            raise ValueError(f"clip index out of range: {index}")
        return index

    if clip_id is None:
        raise ValueError("clip_id or index is required")

    for position, clip in enumerate(plan.clips):
        if clip.clip_id == clip_id:
            return position
    raise ValueError(f"clip not found: {clip_id}")


def add_clip(
    plan: TimelinePlan,
    source: str | Path,
    start: float = 0,
    duration: float = 4,
    label: str | None = None,
    index: int | None = None,
) -> TimelinePlan:
    if start < 0:
        raise ValueError("clip start must be >= 0")
    if duration <= 0:
        raise ValueError("clip duration must be > 0")
    if index is not None and (index < 0 or index > len(plan.clips)):
        raise ValueError(f"clip insert index out of range: {index}")

    clip = TimelineClip(source=str(as_path(source)), start=start, duration=duration, label=label)
    if index is None:
        plan.clips.append(clip)
    else:
        plan.clips.insert(index, clip)
    return plan


def trim_clip(
    plan: TimelinePlan,
    clip_id: str | None = None,
    index: int | None = None,
    start: float | None = None,
    duration: float | None = None,
) -> TimelinePlan:
    clip = plan.clips[find_clip_index(plan, clip_id=clip_id, index=index)]
    if start is not None:
        if start < 0:
            raise ValueError("clip start must be >= 0")
        clip.start = start
    if duration is not None:
        if duration <= 0:
            raise ValueError("clip duration must be > 0")
        clip.duration = duration
    return plan


def split_clip(
    plan: TimelinePlan,
    split_at: float,
    clip_id: str | None = None,
    index: int | None = None,
) -> TimelinePlan:
    clip_index = find_clip_index(plan, clip_id=clip_id, index=index)
    clip = plan.clips[clip_index]
    if split_at <= 0 or split_at >= clip.duration:
        raise ValueError("split_at must be greater than 0 and less than clip duration")

    first = clip.model_copy(update={"duration": split_at})
    second = TimelineClip(
        source=clip.source,
        start=clip.start + split_at,
        duration=clip.duration - split_at,
        label=f"{clip.label or clip.clip_id} part 2",
    )
    plan.clips[clip_index : clip_index + 1] = [first, second]
    return plan


def move_clip(plan: TimelinePlan, from_index: int, to_index: int) -> TimelinePlan:
    if from_index < 0 or from_index >= len(plan.clips):
        raise ValueError(f"from_index out of range: {from_index}")
    if to_index < 0 or to_index >= len(plan.clips):
        raise ValueError(f"to_index out of range: {to_index}")
    clip = plan.clips.pop(from_index)
    plan.clips.insert(to_index, clip)
    return plan


def add_transition(
    plan: TimelinePlan,
    from_clip_id: str,
    to_clip_id: str,
    transition_type: str = "crossfade",
    duration: float = 0.5,
) -> TimelinePlan:
    if duration <= 0:
        raise ValueError("transition duration must be > 0")
    from_index = find_clip_index(plan, clip_id=from_clip_id)
    to_index = find_clip_index(plan, clip_id=to_clip_id)
    if to_index != from_index + 1:
        raise ValueError("transitions must connect adjacent clips")

    transition = TimelineTransition(
        from_clip_id=from_clip_id,
        to_clip_id=to_clip_id,
        transition_type=transition_type,
        duration=duration,
    )
    plan.transitions = [
        existing
        for existing in plan.transitions
        if not (existing.from_clip_id == from_clip_id and existing.to_clip_id == to_clip_id)
    ]
    plan.transitions.append(transition)
    return plan


def validate_timeline(plan: TimelinePlan) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_clip_ids: set[str] = set()

    if not plan.clips:
        issues.append({"code": "empty_timeline", "message": "Timeline has no clips."})

    for index, clip in enumerate(plan.clips):
        if clip.clip_id in seen_clip_ids:
            issues.append({"code": "duplicate_clip_id", "message": f"Duplicate clip_id: {clip.clip_id}", "index": index})
        seen_clip_ids.add(clip.clip_id)
        if clip.start < 0:
            issues.append({"code": "negative_clip_start", "message": "Clip start must be >= 0.", "clip_id": clip.clip_id})
        if clip.duration <= 0:
            issues.append({"code": "non_positive_clip_duration", "message": "Clip duration must be > 0.", "clip_id": clip.clip_id})
        if not Path(clip.source).exists():
            warnings.append({"code": "missing_media", "message": f"Source file does not exist: {clip.source}", "clip_id": clip.clip_id})

    valid_ids = {clip.clip_id for clip in plan.clips}
    for transition in plan.transitions:
        if transition.from_clip_id not in valid_ids or transition.to_clip_id not in valid_ids:
            issues.append(
                {
                    "code": "transition_clip_missing",
                    "message": "Transition references a missing clip.",
                    "transition_id": transition.transition_id,
                }
            )
            continue
        if transition.duration <= 0:
            issues.append(
                {
                    "code": "non_positive_transition_duration",
                    "message": "Transition duration must be > 0.",
                    "transition_id": transition.transition_id,
                }
            )
        from_index = find_clip_index(plan, clip_id=transition.from_clip_id)
        to_index = find_clip_index(plan, clip_id=transition.to_clip_id)
        if to_index != from_index + 1:
            issues.append(
                {
                    "code": "non_adjacent_transition",
                    "message": "Transition clips must be adjacent.",
                    "transition_id": transition.transition_id,
                }
            )
        max_transition = min(plan.clips[from_index].duration, plan.clips[to_index].duration)
        if transition.duration >= max_transition:
            warnings.append(
                {
                    "code": "long_transition",
                    "message": "Transition duration is longer than or equal to one adjacent clip.",
                    "transition_id": transition.transition_id,
                }
            )

    return {
        "ok": not issues,
        "project_id": plan.project_id,
        "platform": plan.platform.value,
        "duration": timeline_duration(plan),
        "clip_count": len(plan.clips),
        "transition_count": len(plan.transitions),
        "issues": issues,
        "warnings": warnings,
    }


def export_otio(plan: TimelinePlan, output_path: str | Path | None = None) -> Path:
    output = Path(output_path) if output_path else project_dir(plan.project_id) / f"timeline_{plan.platform.value.replace(':', 'x')}.otio"
    timeline = otio.schema.Timeline(name=f"{plan.project_id}-{plan.platform.value}")
    track = otio.schema.Track(name="Video 1", kind=otio.schema.TrackKind.Video)
    transitions_by_pair = {(transition.from_clip_id, transition.to_clip_id): transition for transition in plan.transitions}

    cursor = 0.0
    for index, clip in enumerate(plan.clips, start=1):
        source = as_path(clip.source)
        media_ref = otio.schema.ExternalReference(
            target_url=source.as_uri(),
            available_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(0, 30),
                duration=otio.opentime.RationalTime(clip.duration * 30, 30),
            ),
        )
        otio_clip = otio.schema.Clip(name=clip.label or f"clip-{index}", media_reference=media_ref)
        otio_clip.source_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(clip.start * 30, 30),
            duration=otio.opentime.RationalTime(clip.duration * 30, 30),
        )
        otio_clip.metadata["mcp_editor"] = {"timeline_start": cursor}
        track.append(otio_clip)
        cursor += clip.duration

        if index < len(plan.clips):
            next_clip = plan.clips[index]
            transition = transitions_by_pair.get((clip.clip_id, next_clip.clip_id))
            if transition:
                track.append(
                    otio.schema.Transition(
                        name=transition.transition_type,
                        transition_type=otio.schema.TransitionTypes.SMPTE_Dissolve,
                        in_offset=otio.opentime.RationalTime(transition.duration * 15, 30),
                        out_offset=otio.opentime.RationalTime(transition.duration * 15, 30),
                        metadata={"mcp_editor": transition.model_dump()},
                    )
                )

    timeline.tracks.append(track)
    output.parent.mkdir(parents=True, exist_ok=True)
    otio.adapters.write_to_file(timeline, str(output))
    return output
