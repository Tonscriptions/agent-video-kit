"""Versioned local motion preset catalog for Agent timeline planning.

The renderer stores motion as ordinary project keyframes.  This module only
describes the safe, deterministic preset vocabulary that an Agent can inspect
before creating those keyframes; it never downloads templates or calls a
remote registry.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


MOTION_PRESET_CATALOG_VERSION = "0.1.0"


def _parameter(
    kind: str,
    default: Any,
    *,
    minimum: float | int | None = None,
    maximum: float | int | None = None,
    description: str = "",
) -> dict[str, Any]:
    value: dict[str, Any] = {"type": kind, "default": default}
    if minimum is not None:
        value["minimum"] = minimum
    if maximum is not None:
        value["maximum"] = maximum
    if description:
        value["description"] = description
    return value


def _preset(
    preset_id: str,
    *,
    aliases: tuple[str, ...] = (),
    category: str,
    description: str,
    properties: tuple[str, ...],
    parameters: dict[str, dict[str, Any]] | None = None,
    limits: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": preset_id,
        "aliases": list(aliases),
        "category": category,
        "description": description,
        "engine": "timeline-keyframes",
        "source": "local-catalog",
        "license": "project-code",
        "properties": list(properties),
        "parameters": parameters or {},
        "limits": list(limits),
    }


_MOTION_PRESETS: tuple[dict[str, Any], ...] = (
    _preset(
        "zoom_in",
        aliases=("push_in",),
        category="scale",
        description="在片段区间内平滑放大画面。",
        properties=("transform.scale",),
        parameters={"amount": _parameter("number", 0.15, minimum=0.0, maximum=1.0, description="相对缩放增量")},
    ),
    _preset(
        "zoom_out",
        aliases=("pull_out",),
        category="scale",
        description="从放大状态平滑回到原始缩放。",
        properties=("transform.scale",),
        parameters={"amount": _parameter("number", 0.15, minimum=0.0, maximum=1.0, description="相对缩放增量")},
    ),
    _preset(
        "pan_left",
        aliases=("slide_left",),
        category="position",
        description="沿 X 轴从右向左平移。",
        properties=("transform.position.x",),
        parameters={"amount": _parameter("number", 0.15, minimum=0.0, maximum=1.0, description="归一化位移范围")},
    ),
    _preset(
        "pan_right",
        aliases=("slide_right",),
        category="position",
        description="沿 X 轴从左向右平移。",
        properties=("transform.position.x",),
        parameters={"amount": _parameter("number", 0.15, minimum=0.0, maximum=1.0, description="归一化位移范围")},
    ),
    _preset(
        "pan_up",
        aliases=("slide_up",),
        category="position",
        description="沿 Y 轴从下向上平移。",
        properties=("transform.position.y",),
        parameters={"amount": _parameter("number", 0.15, minimum=0.0, maximum=1.0, description="归一化位移范围")},
    ),
    _preset(
        "pan_down",
        aliases=("slide_down",),
        category="position",
        description="沿 Y 轴从上向下平移。",
        properties=("transform.position.y",),
        parameters={"amount": _parameter("number", 0.15, minimum=0.0, maximum=1.0, description="归一化位移范围")},
    ),
    _preset(
        "ken_burns",
        aliases=("kenburns",),
        category="compound",
        description="同时平移和缩放的照片式镜头运动。",
        properties=("transform.scale", "transform.position.x", "transform.position.y"),
        parameters={"amount": _parameter("number", 0.15, minimum=0.0, maximum=1.0, description="缩放及位移强度")},
    ),
    _preset(
        "rotate_in",
        aliases=("rotate_left",),
        category="rotation",
        description="从指定角度平滑旋转回零度。",
        properties=("transform.rotation",),
        parameters={"degrees": _parameter("number", 8.0, minimum=-360.0, maximum=360.0, description="起始旋转角度")},
    ),
    _preset(
        "rotate_out",
        aliases=("rotate_right",),
        category="rotation",
        description="从零度平滑旋转到指定角度。",
        properties=("transform.rotation",),
        parameters={"degrees": _parameter("number", 8.0, minimum=-360.0, maximum=360.0, description="结束旋转角度")},
    ),
    _preset(
        "fade_in",
        aliases=("opacity_in",),
        category="opacity",
        description="在片段区间内从透明渐入。",
        properties=("transform.opacity",),
        limits=("opacity_is_composited_as_a_transform_keyframe",),
    ),
    _preset(
        "fade_out",
        aliases=("opacity_out",),
        category="opacity",
        description="在片段区间内渐出到透明。",
        properties=("transform.opacity",),
        limits=("opacity_is_composited_as_a_transform_keyframe",),
    ),
    _preset(
        "shake",
        category="position",
        description="生成交替位置点的轻微抖动。",
        properties=("transform.position.x",),
        parameters={
            "amount": _parameter("number", 0.15, minimum=0.0, maximum=1.0, description="抖动范围"),
            "points": _parameter("integer", 8, minimum=2, maximum=64, description="关键帧点数"),
        },
        limits=("uses_deterministic_linear_keyframes",),
    ),
)


_ALIASES = {
    alias: item["id"]
    for item in _MOTION_PRESETS
    for alias in [item["id"], *item["aliases"]]
}


def _canonical_name(value: str) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def motion_preset_catalog() -> dict[str, Any]:
    """Return a defensive copy of the local motion preset catalog."""
    presets = deepcopy(list(_MOTION_PRESETS))
    return {
        "catalog_version": MOTION_PRESET_CATALOG_VERSION,
        "source": "local-catalog",
        "engine": "timeline-keyframes",
        "network": "disabled",
        "count": len(presets),
        "presets": presets,
    }


def list_motion_presets(query: str | None = None) -> list[dict[str, Any]]:
    normalized = _canonical_name(query) if query else ""
    values: list[dict[str, Any]] = []
    for item in _MOTION_PRESETS:
        if normalized:
            haystack = " ".join([item["id"], *item["aliases"], item["category"], item["description"]]).lower()
            if normalized not in haystack:
                continue
        values.append(deepcopy(item))
    return values


def get_motion_preset(name: str) -> dict[str, Any] | None:
    canonical = _ALIASES.get(_canonical_name(name))
    if canonical is None:
        return None
    for item in _MOTION_PRESETS:
        if item["id"] == canonical:
            return deepcopy(item)
    return None


def canonical_motion_preset(name: str) -> str | None:
    """Return the stable project-facing preset id for a user-facing alias."""
    return _ALIASES.get(_canonical_name(name))

