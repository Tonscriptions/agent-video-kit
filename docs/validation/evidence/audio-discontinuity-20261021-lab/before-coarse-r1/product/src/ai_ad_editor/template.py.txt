from __future__ import annotations

import copy
import re
from typing import Any

from .errors import argument_error
from .project import asset_map, find_sequence, find_track
from .utils import new_id


PLACEHOLDER = re.compile(r"^\{\{([A-Za-z0-9_.:-]+)\}\}$")
INLINE_PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_.:-]+)\}\}")
COLOR_VALUE = re.compile(r"^(?:#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?|rgba?\([^()]+\)|[A-Za-z][A-Za-z0-9_-]*)$")
VARIABLE_TYPES = {"any", "string", "number", "integer", "boolean", "asset", "color", "enum"}
TEMPLATE_CLIP_FIELDS = ("asset_id", "sequence_id", "timeline_start_tick", "duration_tick", "source_in_tick", "source_out_tick", "speed", "speed_curve", "reverse", "freeze", "crop", "transform", "keyframes", "effects", "transition_in", "transition_out", "subtitle", "generator", "audio", "blend", "mask")


def substitute(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        match = PLACEHOLDER.fullmatch(value)
        if match:
            key = match.group(1)
            if key not in variables:
                raise KeyError(key)
            return copy.deepcopy(variables[key])

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                raise KeyError(key)
            replacement = variables[key]
            if isinstance(replacement, (dict, list, tuple, set)):
                raise ValueError(f"变量 {key} 不能作为字符串内嵌值")
            return str(replacement)

        return INLINE_PLACEHOLDER.sub(replace, value)
    if isinstance(value, list):
        return [substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, variables) for key, item in value.items()}
    return value


def validate_variables(template: dict[str, Any], variables: dict[str, Any]) -> list[str]:
    declarations = template.get("variables", [])
    if declarations is None:
        declarations = []
    if not isinstance(declarations, list):
        raise ValueError("模板 variables 必须是数组")
    missing: list[str] = []
    seen: set[str] = set()
    for declaration in declarations:
        if not isinstance(declaration, dict):
            raise ValueError("模板变量声明必须是对象")
        name = declaration.get("name")
        if not isinstance(name, str) or not name or not re.fullmatch(r"[A-Za-z0-9_.:-]+", name):
            raise ValueError("模板变量 name 必须匹配 [A-Za-z0-9_.:-]+")
        if name in seen:
            raise ValueError(f"模板变量重复声明: {name}")
        seen.add(name)
        declared_type = str(declaration.get("type", "any")).lower()
        if declared_type not in VARIABLE_TYPES:
            raise ValueError(f"模板变量 {name} 的 type 不支持: {declared_type}")
        if declaration.get("required", False) and name not in variables and "default" not in declaration:
            missing.append(str(name))
        if name not in variables and "default" in declaration:
            candidate = declaration["default"]
        elif name in variables:
            candidate = variables[name]
        else:
            continue
        if not _value_matches(candidate, declaration):
            raise ValueError(f"模板变量 {name} 不符合 type={declared_type} 的约束")
    return missing


def _value_matches(value: Any, declaration: dict[str, Any]) -> bool:
    declared_type = str(declaration.get("type", "any")).lower()
    if declared_type == "any":
        return True
    if declared_type in {"string", "asset", "color", "enum"} and not isinstance(value, str):
        return False
    if declared_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return False
    if declared_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return False
    if declared_type == "boolean" and not isinstance(value, bool):
        return False
    if declared_type == "color" and not COLOR_VALUE.fullmatch(value):
        return False
    if declared_type == "enum":
        allowed = declaration.get("values", declaration.get("choices", declaration.get("enum")))
        if not isinstance(allowed, list) or value not in allowed:
            return False
    if declared_type in {"number", "integer"}:
        if "min" in declaration and value < declaration["min"]:
            return False
        if "max" in declaration and value > declaration["max"]:
            return False
    if declared_type in {"string", "asset", "color", "enum"}:
        if "min_length" in declaration and len(value) < int(declaration["min_length"]):
            return False
        if "max_length" in declaration and len(value) > int(declaration["max_length"]):
            return False
    return True


def instantiate(template: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(variables, dict):
        raise ValueError("模板变量必须是对象")
    resolved_variables = copy.deepcopy(variables)
    missing = validate_variables(template, resolved_variables)
    if missing:
        raise ValueError(f"模板缺少必填变量: {', '.join(missing)}")
    for declaration in template.get("variables", []) or []:
        name = declaration.get("name")
        if name not in resolved_variables and "default" in declaration:
            resolved_variables[name] = copy.deepcopy(declaration["default"])
    resolved = substitute(copy.deepcopy(template), resolved_variables)
    resolved["template_snapshot"] = {"id": template.get("id"), "version": template.get("version"), "variables": copy.deepcopy(resolved_variables)}
    return resolved


def _template_clip(change: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    for field in ("source_in_tick", "source_out_tick"):
        if field not in change:
            raise argument_error(f"模板 append_clip 缺少字段: {field}", field)
    asset_id = change.get("asset_id")
    nested_sequence_id = change.get("nested_sequence_id") or change.get("child_sequence_id")
    generator = change.get("generator")
    text_generator = isinstance(generator, dict) and str(generator.get("type", "")).lower() == "text" and isinstance(change.get("subtitle"), dict)
    if not asset_id and not nested_sequence_id and not text_generator:
        raise argument_error("模板 append_clip 必须提供 asset_id、nested_sequence_id 或有效的 text generator")
    source_in = int(change["source_in_tick"])
    source_out = int(change["source_out_tick"])
    duration = int(change.get("duration_tick", source_out - source_in))
    if duration <= 0 or source_out <= source_in:
        raise argument_error("模板片段 source/duration 时间范围无效")
    start = change.get("timeline_start_tick")
    if start is None:
        start = max((int(item.get("timeline_start_tick", 0)) + int(item.get("duration_tick", 0)) for item in track.get("clips", [])), default=0)
    clip = {"id": change.get("id") or new_id("clip"), "timeline_start_tick": int(start), "duration_tick": duration, "source_in_tick": source_in, "source_out_tick": source_out}
    if asset_id:
        clip["asset_id"] = asset_id
    if nested_sequence_id:
        clip["sequence_id"] = nested_sequence_id
    if text_generator:
        clip["generator"] = copy.deepcopy(generator)
    for field in TEMPLATE_CLIP_FIELDS:
        if field in change:
            clip[field] = copy.deepcopy(change[field])
    return clip


def _template_find_clip(sequence: dict[str, Any], clip_id: str, track_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if not clip_id:
        raise argument_error("模板操作必须提供 clip_id", "clip_id")
    tracks = sequence.get("tracks", [])
    if track_id:
        tracks = [track for track in tracks if track.get("id") == track_id]
    for track in tracks:
        for clip in track.get("clips", []):
            if clip.get("id") == clip_id:
                return track, clip
    raise argument_error(f"模板找不到片段: {clip_id}", "clip_id")


def _template_recompute_duration(sequence: dict[str, Any]) -> None:
    end = max((int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0)) for track in sequence.get("tracks", []) for clip in track.get("clips", [])), default=0)
    sequence["duration_tick"] = max(1, end)


def _template_add_track(sequence: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    track_id = str(change.get("track_id") or change.get("id") or new_id("track"))
    if any(track.get("id") == track_id for track in sequence.get("tracks", [])):
        raise argument_error(f"模板轨道 ID 已存在: {track_id}", "track_id")
    kind = str(change.get("kind") or change.get("track_kind") or "video")
    if kind not in {"video", "audio", "subtitle", "data"}:
        raise argument_error(f"模板轨道 kind 无效: {kind}", "kind")
    track = {"id": track_id, "kind": kind, "order": int(change.get("order", max((int(item.get("order", 0)) for item in sequence.get("tracks", [])), default=-1) + 1)), "muted": bool(change.get("muted", False)), "locked": bool(change.get("locked", False)), "clips": []}
    if "overlap_policy" in change:
        track["overlap_policy"] = change["overlap_policy"]
    sequence.setdefault("tracks", []).append(track)
    return track


def apply_template_operations(project: dict[str, Any], operations: list[dict[str, Any]], sequence_id: str | None = None) -> list[dict[str, Any]]:
    """Apply the safe, local subset of Agent Project operations used by templates."""
    if not isinstance(operations, list):
        raise argument_error("模板 operations/changes 必须是数组")
    root_sequence = find_sequence(project, sequence_id)
    assets = asset_map(project)
    applied: list[dict[str, Any]] = []
    for change in operations:
        if not isinstance(change, dict):
            raise argument_error("模板操作必须是对象")
        operation = str(change.get("op", "append_clip"))
        target_sequence = find_sequence(project, change.get("sequence_id") or root_sequence["id"])
        if operation == "append_clip":
            track = find_track(target_sequence, change.get("track_id"), change.get("track_kind", "video"))
            clip = _template_clip(change, track)
            if clip.get("asset_id") and str(clip["asset_id"]) not in assets:
                raise argument_error(f"模板引用的资产不存在: {clip['asset_id']}", "asset_id")
            if any(existing.get("id") == clip["id"] for existing in track.get("clips", [])):
                raise argument_error(f"模板片段 ID 已存在: {clip['id']}", "id")
            track.setdefault("clips", []).append(clip)
            target_sequence["duration_tick"] = max(int(target_sequence.get("duration_tick", 1)), clip["timeline_start_tick"] + clip["duration_tick"])
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation in {"update_clip", "replace_clip"}:
            track, clip = _template_find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            patch = copy.deepcopy(change.get("patch")) if isinstance(change.get("patch"), dict) else {}
            for field in TEMPLATE_CLIP_FIELDS:
                if field in change:
                    patch[field] = copy.deepcopy(change[field])
            if "asset_id" in patch and str(patch["asset_id"]) not in assets:
                raise argument_error(f"模板引用的资产不存在: {patch['asset_id']}", "asset_id")
            for field in TEMPLATE_CLIP_FIELDS:
                if field in patch:
                    clip[field] = patch[field]
            if int(clip.get("duration_tick", 0)) <= 0 or int(clip.get("source_out_tick", 0)) <= int(clip.get("source_in_tick", 0)):
                raise argument_error("模板 update_clip 生成了无效的片段时间范围", "patch")
            _template_recompute_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "remove_clip":
            track, clip = _template_find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            track["clips"] = [item for item in track.get("clips", []) if item is not clip]
            _template_recompute_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip_id": clip["id"]})
        elif operation == "add_track":
            track = _template_add_track(target_sequence, change)
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "track": track})
        elif operation == "update_track":
            track = find_track(target_sequence, change.get("track_id"), None)
            patch = change.get("patch") if isinstance(change.get("patch"), dict) else change
            for field in ("muted", "locked", "order", "overlap_policy"):
                if field in patch:
                    track[field] = patch[field]
            applied.append({"op": operation, "track_id": track["id"], "track": track})
        elif operation == "remove_track":
            track_id = str(change.get("track_id") or change.get("id") or "")
            track = find_track(target_sequence, track_id, None)
            if track.get("locked"):
                raise argument_error(f"模板轨道已锁定，不能删除: {track_id}", "track_id")
            if track.get("clips") and not bool(change.get("force", False)):
                raise argument_error("模板删除含片段轨道需要 force=true", "force")
            target_sequence["tracks"] = [item for item in target_sequence.get("tracks", []) if item is not track]
            _template_recompute_duration(target_sequence)
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "track_id": track_id})
        elif operation == "add_marker":
            marker = {"id": change.get("id") or new_id("marker"), "at_tick": int(change.get("at_tick", 0)), "label": str(change.get("label", ""))}
            if marker["at_tick"] < 0:
                raise argument_error("模板标记 at_tick 不能为负", "at_tick")
            if any(item.get("id") == marker["id"] for item in target_sequence.get("markers", [])):
                raise argument_error(f"模板标记 ID 已存在: {marker['id']}", "id")
            target_sequence.setdefault("markers", []).append(marker)
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "marker": marker})
        elif operation == "remove_marker":
            marker_id = str(change.get("marker_id") or change.get("id") or "")
            markers = target_sequence.get("markers", [])
            retained = [item for item in markers if item.get("id") != marker_id]
            if len(retained) == len(markers):
                raise argument_error(f"模板找不到标记: {marker_id}", "marker_id")
            target_sequence["markers"] = retained
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "marker_id": marker_id})
        else:
            raise argument_error(f"模板暂不支持操作: {operation}", "op")
    return applied
