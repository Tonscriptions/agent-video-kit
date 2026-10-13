from __future__ import annotations

from typing import Any

from .projects import load_manifest, save_manifest
from .schemas import ClipEffect, Platform, TimelineClip, TimelinePlan
from .timeline import find_clip_index


SUPPORTED_EFFECTS = {"speed_ramp", "zoom_punch", "reframe", "motion_blur", "grade"}

EXTENDED_TRANSITION_TYPES = {"crossfade", "whip_pan", "flash_cut", "glitch_cut", "fade_to_black"}


def build_clip_vf(clip: TimelineClip, platform: Platform) -> str:
    """Build the full FFmpeg -vf filter chain for a clip, including effects and platform scaling."""
    from .schemas import PLATFORM_DIMENSIONS

    width, height = PLATFORM_DIMENSIONS[platform]
    platform_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
    )

    parts: list[str] = []
    for effect in clip.effects:
        if effect.effect_type == "reframe":
            x_pct = float(effect.params.get("x_pct", 0.0))
            y_pct = float(effect.params.get("y_pct", 0.0))
            crop_pct = max(0.5, min(float(effect.params.get("crop_pct", 0.9)), 1.0))
            # Crop a crop_pct-sized window, shifted by x_pct/y_pct from center.
            parts.append(
                f"crop=iw*{crop_pct}:ih*{crop_pct}:"
                f"iw*(1-{crop_pct})/2+iw*{x_pct}:"
                f"ih*(1-{crop_pct})/2+ih*{y_pct}"
            )
        elif effect.effect_type == "zoom_punch":
            zoom = max(1.01, min(float(effect.params.get("zoom", 1.2)), 3.0))
            # Scale up by zoom, then crop back to the original frame dimensions.
            parts.append(
                f"scale=iw*{zoom}:ih*{zoom},"
                f"crop=iw/{zoom}:ih/{zoom}:"
                f"iw*(1-1/{zoom})/2:ih*(1-1/{zoom})/2"
            )
        elif effect.effect_type == "speed_ramp":
            speed = max(0.1, float(effect.params.get("speed", 1.0)))
            parts.append(f"setpts=PTS/{speed}")
        elif effect.effect_type == "motion_blur":
            parts.append("tblend=all_mode=average")

    # Grade effect is applied after geometric transforms but before platform scaling.
    for effect in clip.effects:
        if effect.effect_type == "grade":
            from .grading import build_grade_vf
            grade_filters = build_grade_vf(effect)
            if grade_filters:
                parts.append(grade_filters)

    parts.append(platform_filter)
    return ",".join(parts)


def build_clip_af(clip: TimelineClip) -> list[str]:
    """Return the audio filter chain for a clip (empty unless speed_ramp present)."""
    for effect in clip.effects:
        if effect.effect_type == "speed_ramp":
            speed = max(0.1, float(effect.params.get("speed", 1.0)))
            # atempo is limited to [0.5, 2.0]; chain multiple filters for extremes.
            filters: list[str] = []
            remaining = speed
            while remaining > 2.0:
                filters.append("atempo=2.0")
                remaining /= 2.0
            while remaining < 0.5:
                filters.append("atempo=0.5")
                remaining /= 0.5
            if abs(remaining - 1.0) > 0.001:
                filters.append(f"atempo={remaining:.4f}")
            return filters
    return []


def source_read_duration(clip: TimelineClip) -> float:
    """How much source material to read for a clip, accounting for speed ramp."""
    for effect in clip.effects:
        if effect.effect_type == "speed_ramp":
            speed = max(0.1, float(effect.params.get("speed", 1.0)))
            return clip.duration * speed
    return clip.duration


def _upsert_effect(clip: TimelineClip, effect_type: str, params: dict[str, Any]) -> None:
    for existing in clip.effects:
        if existing.effect_type == effect_type:
            existing.params.update(params)
            return
    clip.effects.append(ClipEffect(effect_type=effect_type, params=params))


def _remove_effect(clip: TimelineClip, effect_type: str) -> bool:
    before = len(clip.effects)
    clip.effects = [e for e in clip.effects if e.effect_type != effect_type]
    return len(clip.effects) < before


def _clip_summary(clip: TimelineClip) -> dict[str, Any]:
    return {
        "clip_id": clip.clip_id,
        "source": clip.source,
        "start": clip.start,
        "duration": clip.duration,
        "label": clip.label,
        "effects": [e.model_dump() for e in clip.effects],
    }


# ── MCP implementation functions ─────────────────────────────────────────────


def apply_speed_ramp(
    project_id: str,
    platform: Platform,
    speed: float,
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    if speed <= 0:
        raise ValueError("speed must be > 0")
    manifest = load_manifest(project_id)
    plan: TimelinePlan = manifest.timelines.get(platform.value)  # type: ignore[arg-type]
    if plan is None:
        raise ValueError(f"no timeline for platform {platform.value!r}; create one first")
    i = find_clip_index(plan, clip_id=clip_id, index=index)
    _upsert_effect(plan.clips[i], "speed_ramp", {"speed": speed})
    save_manifest(manifest)
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "effect": "speed_ramp",
        "speed": speed,
        "clip": _clip_summary(plan.clips[i]),
    }


def apply_zoom_punch(
    project_id: str,
    platform: Platform,
    zoom: float = 1.2,
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    if zoom <= 1.0:
        raise ValueError("zoom must be > 1.0 to punch in")
    if zoom > 3.0:
        raise ValueError("zoom must be <= 3.0")
    manifest = load_manifest(project_id)
    plan: TimelinePlan = manifest.timelines.get(platform.value)  # type: ignore[arg-type]
    if plan is None:
        raise ValueError(f"no timeline for platform {platform.value!r}; create one first")
    i = find_clip_index(plan, clip_id=clip_id, index=index)
    _upsert_effect(plan.clips[i], "zoom_punch", {"zoom": zoom})
    save_manifest(manifest)
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "effect": "zoom_punch",
        "zoom": zoom,
        "clip": _clip_summary(plan.clips[i]),
    }


def apply_smash_cut(
    project_id: str,
    platform: Platform,
    from_clip_id: str,
    to_clip_id: str,
) -> dict[str, Any]:
    """Remove any transition between two adjacent clips, making it a hard cut."""
    manifest = load_manifest(project_id)
    plan: TimelinePlan = manifest.timelines.get(platform.value)  # type: ignore[arg-type]
    if plan is None:
        raise ValueError(f"no timeline for platform {platform.value!r}; create one first")
    before = len(plan.transitions)
    plan.transitions = [
        t
        for t in plan.transitions
        if not (t.from_clip_id == from_clip_id and t.to_clip_id == to_clip_id)
    ]
    removed = before - len(plan.transitions)
    save_manifest(manifest)
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "effect": "smash_cut",
        "from_clip_id": from_clip_id,
        "to_clip_id": to_clip_id,
        "transitions_removed": removed,
    }


def apply_reframe(
    project_id: str,
    platform: Platform,
    x_pct: float = 0.0,
    y_pct: float = 0.0,
    crop_pct: float = 0.9,
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    """Reframe a clip by cropping with a center offset."""
    if not (0.5 <= crop_pct <= 1.0):
        raise ValueError("crop_pct must be between 0.5 and 1.0")
    max_offset = (1.0 - crop_pct) / 2.0
    if abs(x_pct) > max_offset or abs(y_pct) > max_offset:
        raise ValueError(
            f"x_pct/y_pct offsets must be within ±{max_offset:.2f} for crop_pct={crop_pct}"
        )
    manifest = load_manifest(project_id)
    plan: TimelinePlan = manifest.timelines.get(platform.value)  # type: ignore[arg-type]
    if plan is None:
        raise ValueError(f"no timeline for platform {platform.value!r}; create one first")
    i = find_clip_index(plan, clip_id=clip_id, index=index)
    _upsert_effect(plan.clips[i], "reframe", {"x_pct": x_pct, "y_pct": y_pct, "crop_pct": crop_pct})
    save_manifest(manifest)
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "effect": "reframe",
        "x_pct": x_pct,
        "y_pct": y_pct,
        "crop_pct": crop_pct,
        "clip": _clip_summary(plan.clips[i]),
    }


def apply_motion_effects(
    project_id: str,
    platform: Platform,
    effects: list[dict[str, Any]],
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    """Apply a batch of named effects to a single clip."""
    manifest = load_manifest(project_id)
    plan: TimelinePlan = manifest.timelines.get(platform.value)  # type: ignore[arg-type]
    if plan is None:
        raise ValueError(f"no timeline for platform {platform.value!r}; create one first")
    i = find_clip_index(plan, clip_id=clip_id, index=index)
    clip = plan.clips[i]
    applied: list[str] = []
    for entry in effects:
        effect_type = entry.get("effect_type", "")
        if effect_type not in SUPPORTED_EFFECTS:
            raise ValueError(f"unsupported effect_type: {effect_type!r}; choose from {sorted(SUPPORTED_EFFECTS)}")
        params = {k: v for k, v in entry.items() if k != "effect_type"}
        _upsert_effect(clip, effect_type, params)
        applied.append(effect_type)
    save_manifest(manifest)
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "effects_applied": applied,
        "clip": _clip_summary(clip),
    }


def remove_clip_effect(
    project_id: str,
    platform: Platform,
    effect_type: str,
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    """Remove one effect type from a clip."""
    manifest = load_manifest(project_id)
    plan: TimelinePlan = manifest.timelines.get(platform.value)  # type: ignore[arg-type]
    if plan is None:
        raise ValueError(f"no timeline for platform {platform.value!r}; create one first")
    i = find_clip_index(plan, clip_id=clip_id, index=index)
    removed = _remove_effect(plan.clips[i], effect_type)
    save_manifest(manifest)
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "effect_removed": effect_type if removed else None,
        "clip": _clip_summary(plan.clips[i]),
    }
