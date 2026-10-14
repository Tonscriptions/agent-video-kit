from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
import copy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from .policy import assert_local_project_reference

from .media import classify_path, probe_media
from .project import TICKS_PER_SECOND, create_project, save_project
from .rights import add_record, load_ledger, save_ledger
from .utils import atomic_write_json, new_id, now_iso, safe_filename, sha256_file


def report_item(capability: str, status: str, source: str, target: str | None = None, detail: str = "") -> dict[str, Any]:
    return {"capability": capability, "status": status, "source": source, "target": target, "detail": detail}


def _path_from_uri(value: str, base: Path | None = None) -> Path:
    """Resolve an OTIO/MLT local reference without changing the policy gate.

    OTIO permits relative ``target_url`` values.  They are relative to the
    interchange file, whereas the project runtime resolves paths from the
    project root.  Resolve that distinction before handing the value to the
    common local-only policy.
    """
    text = str(value)
    parsed = urlsplit(text)
    if base is not None and not parsed.scheme and not Path(text).expanduser().is_absolute():
        return (base / Path(text)).expanduser().resolve()
    return assert_local_project_reference(text, field="media_reference.target_url")


def _otio_rational_time(tick: int, tps: int) -> dict[str, Any]:
    """Represent project ticks exactly in an OTIO RationalTime."""
    return {"OTIO_SCHEMA": "RationalTime.1", "value": int(tick), "rate": int(tps)}


def _otio_time_range(start_tick: int, duration_tick: int, tps: int) -> dict[str, Any]:
    return {
        "OTIO_SCHEMA": "TimeRange.1",
        "start_time": _otio_rational_time(start_tick, tps),
        "duration": _otio_rational_time(max(1, duration_tick), tps),
    }


def _otio_ticks(value: Any, tps: int, default: int = 0) -> int:
    """Convert an OTIO RationalTime object to the project tick timebase."""
    if not isinstance(value, dict):
        return default
    try:
        raw_value = float(value.get("value", 0))
        rate = max(float(value.get("rate", 1)), 1e-9)
        return int(round(raw_value / rate * tps))
    except (TypeError, ValueError):
        return default


def export_agent_project(root: Path, project: dict[str, Any], output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    exported = copy.deepcopy(project)
    for asset in exported.get("assets", []):
        uri = Path(str(asset.get("uri", "")))
        if not uri.is_absolute():
            uri = root / uri
        if uri.exists():
            asset["uri"] = str(uri)
    exported.setdefault("provenance", {}).setdefault("change_log", []).append({"command": "convert.export", "at": now_iso(), "source_project": str(root)})
    atomic_write_json(output, exported)
    report = {
        "report_version": "0.1.0",
        "direction": "export",
        "source_format": "agent-project/0.1.0",
        "target_format": "agent-project/0.1.0",
        "created_at": now_iso(),
        "items": [report_item("project-model", "Exact", "Agent Project JSON", "Agent Project JSON")],
        "warnings": [],
        "failures": [],
    }
    report_path = output.with_suffix(output.suffix + ".conversion-report.json")
    atomic_write_json(report_path, report)
    return {"output": str(output), "report": str(report_path), "report_data": report}


def _asset_uri(root: Path, asset: dict[str, Any]) -> Path:
    uri = Path(str(asset.get("uri", "")))
    return uri if uri.is_absolute() else root / uri


def _export_otio(root: Path, project: dict[str, Any], output: Path) -> dict[str, Any]:
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    assets = {str(asset.get("id")): asset for asset in project.get("assets", [])}
    tracks: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = [report_item("project-model", "Mapped", "Agent Project JSON", "OpenTimelineIO JSON", "使用标准 Stack/Track/Gap/Clip 节点；完整本地片段保存在 ai_ad_editor metadata")]
    sequence = project.get("sequences", [{}])[0]
    for track in sorted(sequence.get("tracks", []), key=lambda item: int(item.get("order", 0))):
        kind = "Audio" if track.get("kind") == "audio" else "Video"
        track_metadata = {
            "track_id": track.get("id"),
            "track_kind": track.get("kind", "video"),
            "track_order": int(track.get("order", 0)),
        }
        otio_track: dict[str, Any] = {
            "OTIO_SCHEMA": "Track.1",
            "name": track.get("id", "track"),
            "kind": kind,
            "children": [],
            "metadata": {"ai_ad_editor": track_metadata},
        }
        cursor_tick = 0
        for clip in sorted(track.get("clips", []), key=lambda item: int(item.get("timeline_start_tick", 0))):
            asset = assets.get(str(clip.get("asset_id")))
            duration_tick = max(1, int(clip.get("duration_tick", 1)))
            timeline_start_tick = max(0, int(clip.get("timeline_start_tick", 0)))
            if timeline_start_tick > cursor_tick:
                otio_track["children"].append({
                    "OTIO_SCHEMA": "Gap.1",
                    "name": f"gap_{cursor_tick}_{timeline_start_tick}",
                    "source_range": _otio_time_range(0, timeline_start_tick - cursor_tick, tps),
                })
            elif timeline_start_tick < cursor_tick:
                items.append(report_item("timeline-overlap", "Approximate", str(clip.get("id")), otio_track["name"], "OTIO Track 是顺序容器；重叠片段保留 timeline_start_tick metadata，外部编辑器可能按顺序压平"))
            source_in_tick = max(0, int(clip.get("source_in_tick", 0)))
            local_metadata: dict[str, Any] = {
                "timeline_start_tick": timeline_start_tick,
                "duration_tick": duration_tick,
                "asset_id": asset.get("id") if asset else clip.get("asset_id"),
                "track_id": track.get("id"),
                "track_order": int(track.get("order", 0)),
                "clip": copy.deepcopy(clip),
            }
            child: dict[str, Any] = {
                "OTIO_SCHEMA": "Clip.2",
                "name": clip.get("id", "clip"),
                "source_range": _otio_time_range(source_in_tick, duration_tick, tps),
                "metadata": {"ai_ad_editor": local_metadata},
            }
            if asset:
                media_path = _asset_uri(root, asset)
                if media_path.exists():
                    child["media_reference"] = {"OTIO_SCHEMA": "ExternalReference.1", "target_url": media_path.resolve().as_uri()}
                else:
                    items.append(report_item("media-reference", "Failed", str(media_path), child["name"], "本地媒体文件不存在，保留 OTIO 引用但目标无法独立渲染"))
                    child["media_reference"] = {"OTIO_SCHEMA": "MissingReference.1", "name": media_path.name}
            elif isinstance(clip.get("generator"), dict) and str(clip["generator"].get("type", "")).lower() == "text" and isinstance(clip.get("subtitle"), dict):
                child["media_reference"] = {"OTIO_SCHEMA": "GeneratorReference.1", "generator_kind": "Text"}
                items.append(report_item("text-generator", "Mapped", str(clip.get("id")), child["name"], "文字生成器保留为 GeneratorReference，并在 ai_ad_editor metadata 保存完整片段"))
            else:
                items.append(report_item("media-reference", "Failed", str(clip.get("asset_id")), child["name"], "片段没有可导出的本地资产或受支持的文字生成器"))
                cursor_tick = max(cursor_tick, timeline_start_tick + duration_tick)
                continue
            feature_fields = [field for field in ("effects", "keyframes", "transition_in", "transition_out", "subtitle", "audio", "mask", "blend", "transform") if clip.get(field)]
            if feature_fields:
                items.append(report_item("clip-features", "Mapped", str(clip.get("id")), child["name"], f"完整字段保存在 metadata.ai_ad_editor.clip；外部 OTIO 播放器只保证基础媒体时间范围，字段: {','.join(feature_fields)}"))
            otio_track["children"].append(child)
            cursor_tick = max(cursor_tick, timeline_start_tick + duration_tick)
        tracks.append(otio_track)
    payload = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": project.get("project", {}).get("name", "Agent Project"),
        "metadata": {"ai_ad_editor": {"schema_version": project.get("schema_version"), "ticks_per_second": tps, "duration_tick": int(sequence.get("duration_tick", 1))}},
        "tracks": {"OTIO_SCHEMA": "Stack.1", "name": "tracks", "children": tracks},
    }
    atomic_write_json(output, payload)
    report = {"report_version": "0.1.0", "direction": "export", "source_format": "agent-project/0.1.0", "target_format": "opentimelineio-json", "created_at": now_iso(), "items": items, "warnings": [item for item in items if item["status"] in {"Approximate", "Unsupported"}], "failures": [item for item in items if item["status"] == "Failed"]}
    report_path = output.with_suffix(output.suffix + ".conversion-report.json")
    atomic_write_json(report_path, report)
    return {"output": str(output), "report": str(report_path), "report_data": report}


def _export_kdenlive_xml(root: Path, project: dict[str, Any], output: Path) -> dict[str, Any]:
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    fps = project["settings"]["timebase"].get("display_fps", {"num": 30, "den": 1})
    fps_num = max(1, int(fps.get("num", 30)))
    fps_den = max(1, int(fps.get("den", 1)))
    profile = f"atsc_1080p_{fps_num}"
    assets = {str(asset.get("id")): asset for asset in project.get("assets", [])}
    root_element = ET.Element("mlt", {"version": "7.0", "profile": profile})
    ET.SubElement(root_element, "profile", {
        "description": "Agent Video Kit",
        "frame_rate_num": str(fps_num),
        "frame_rate_den": str(fps_den),
        "width": str(int(project["settings"].get("canvas", {}).get("width", 1080))),
        "height": str(int(project["settings"].get("canvas", {}).get("height", 1920))),
    })
    producers: list[tuple[str, dict[str, Any]]] = []
    items: list[dict[str, Any]] = [report_item("project-model", "Approximate", "Agent Project JSON", "Kdenlive MLT XML", "导出本地 producer 与顺序 playlist；复杂效果需在转换报告中复核")]
    sequence = project.get("sequences", [{}])[0]
    playlists: list[str] = []
    producer_index = 0
    for track_index, track in enumerate(sorted(sequence.get("tracks", []), key=lambda item: int(item.get("order", 0)))):
        playlist_id = f"playlist{track_index}"
        playlists.append(playlist_id)
        playlist = ET.SubElement(root_element, "playlist", {"id": playlist_id})
        ET.SubElement(playlist, "property", {"name": "ai_ad_editor_track_kind"}).text = str(track.get("kind", "video"))
        ET.SubElement(playlist, "property", {"name": "ai_ad_editor_track_id"}).text = str(track.get("id", playlist_id))
        ET.SubElement(playlist, "property", {"name": "ai_ad_editor_track_order"}).text = str(int(track.get("order", track_index)))
        cursor_frame = 0
        for clip in sorted(track.get("clips", []), key=lambda item: int(item.get("timeline_start_tick", 0))):
            asset = assets.get(str(clip.get("asset_id")))
            if not asset:
                items.append(report_item("media-reference", "Failed", str(clip.get("asset_id")), None, "片段没有可导出的本地资产"))
                continue
            producer_id = f"producer{producer_index}"
            producer_index += 1
            media_path = _asset_uri(root, asset).resolve()
            producer = ET.SubElement(root_element, "producer", {"id": producer_id})
            ET.SubElement(producer, "property", {"name": "resource"}).text = str(media_path)
            duration_tick = max(1, int(clip.get("duration_tick", 1)))
            source_in_tick = max(0, int(clip.get("source_in_tick", 0)))
            duration_frames = max(1, round(duration_tick / tps * fps_num / fps_den))
            in_frame = max(0, round(source_in_tick / tps * fps_num / fps_den))
            timeline_start_tick = max(0, int(clip.get("timeline_start_tick", 0)))
            timeline_frame = max(0, round(timeline_start_tick / tps * fps_num / fps_den))
            if timeline_frame > cursor_frame:
                ET.SubElement(playlist, "blank", {"length": str(timeline_frame - cursor_frame)})
            elif timeline_frame < cursor_frame:
                items.append(report_item("timeline-overlap", "Approximate", str(clip.get("id")), playlist_id, "MLT playlist 是顺序容器；重叠片段保留 metadata，外部项目可能压平层级"))
            entry = ET.SubElement(playlist, "entry", {"producer": producer_id, "in": str(in_frame), "out": str(in_frame + duration_frames - 1)})
            ET.SubElement(entry, "property", {"name": "ai_ad_editor_clip_id"}).text = str(clip.get("id", producer_id))
            ET.SubElement(entry, "property", {"name": "ai_ad_editor_timeline_start_tick"}).text = str(timeline_start_tick)
            ET.SubElement(entry, "property", {"name": "ai_ad_editor_duration_tick"}).text = str(duration_tick)
            ET.SubElement(entry, "property", {"name": "ai_ad_editor_clip_json"}).text = json.dumps(clip, ensure_ascii=False, separators=(",", ":"))
            cursor_frame = max(cursor_frame, timeline_frame + duration_frames)
            if any(clip.get(field) for field in ("effects", "keyframes", "transition_in", "transition_out", "subtitle", "audio")):
                items.append(report_item("clip-features", "Mapped", str(clip.get("id")), producer_id, "完整片段字段写入 ai_ad_editor_clip_json；MLT 基础播放器不执行这些字段"))
    tractor = ET.SubElement(root_element, "tractor", {"id": "tractor0"})
    multitrack = ET.SubElement(tractor, "multitrack")
    for playlist_id in playlists:
        ET.SubElement(multitrack, "track", {"producer": playlist_id})
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root_element, space="  ")
    ET.ElementTree(root_element).write(output, encoding="utf-8", xml_declaration=True)
    report = {"report_version": "0.1.0", "direction": "export", "source_format": "agent-project/0.1.0", "target_format": "kdenlive-mlt-xml", "created_at": now_iso(), "items": items, "warnings": [item for item in items if item["status"] in {"Approximate", "Unsupported"}], "failures": [item for item in items if item["status"] == "Failed"]}
    report_path = output.with_suffix(output.suffix + ".conversion-report.json")
    atomic_write_json(report_path, report)
    return {"output": str(output), "report": str(report_path), "report_data": report}


def export_external(root: Path, project: dict[str, Any], output: Path, target_format: str) -> dict[str, Any]:
    if target_format == "agent-json":
        return export_agent_project(root, project, output)
    if target_format == "otio":
        return _export_otio(root, project, output)
    if target_format == "kdenlive-xml":
        return _export_kdenlive_xml(root, project, output)
    raise ValueError(f"不支持的导出格式: {target_format}")


def _asset_from_local(path: Path, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    probe = probe_media(path)
    asset_id = new_id("asset")
    destination = root / "assets" / f"{asset_id}_{safe_filename(path.name)}"
    shutil.copy2(path, destination)
    digest = sha256_file(destination)
    kind = classify_path(path, probe)
    asset = {"id": asset_id, "kind": kind, "uri": str(destination.relative_to(root)).replace("\\", "/"), "sha256": f"sha256:{digest}", "probe": probe, "rights_ref": asset_id, "source": {"source_url": f"local://{path}", "retrieved_at": now_iso(), "original_name": path.name}}
    rights = {"asset_id": asset_id, "kind": kind, "sha256": f"sha256:{digest}", "source_url": f"local://{path}", "source_version": "import", "retrieved_at": now_iso(), "creator": "unknown", "license_spdx": "LicenseRef-UNVERIFIED", "license_url": "", "attribution": "", "permitted_uses": ["internal"], "restrictions": [], "evidence": "", "verification_status": "unverified", "verified_by": "", "takedown_status": "clear", "notes": "Imported through local converter; verify before publish"}
    return asset, rights


def _import_otio(source: Path, destination: Path, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    root, project = create_project(destination, name=payload.get("name") or source.stem)
    ledger = {"schema_version": "0.1.0", "updated_at": now_iso(), "records": [], "policy": {}}
    sequence = project["sequences"][0]
    import_tps = int(project["settings"]["timebase"]["ticks_per_second"])
    report_items: list[dict[str, Any]] = [report_item("project-model", "Mapped", "OpenTimelineIO", "Agent Project JSON", "标准 Stack/Track/Gap/Clip 以及 ai_ad_editor metadata 已映射到本地时间线")]
    asset_by_uri: dict[str, dict[str, Any]] = {}
    raw_tracks = payload.get("tracks")
    if isinstance(raw_tracks, dict):
        raw_tracks = raw_tracks.get("children", [])
    if not isinstance(raw_tracks, list) or not raw_tracks:
        raw_tracks = payload.get("children", [])

    def track_for(otio_track: dict[str, Any], track_index: int) -> dict[str, Any]:
        metadata = otio_track.get("metadata") if isinstance(otio_track.get("metadata"), dict) else {}
        local = metadata.get("ai_ad_editor") if isinstance(metadata.get("ai_ad_editor"), dict) else {}
        raw_kind = str(local.get("track_kind", otio_track.get("kind", "video"))).lower()
        kind = "audio" if raw_kind == "audio" else "subtitle" if raw_kind == "subtitle" else "video"
        requested_id = str(local.get("track_id") or otio_track.get("name") or f"track_{kind}_{track_index + 1}")
        try:
            order = int(local.get("track_order", track_index))
        except (TypeError, ValueError):
            order = track_index
        for existing in sequence["tracks"]:
            if existing.get("id") == requested_id:
                return existing
        candidates = [item for item in sequence["tracks"] if item.get("kind") == kind and not item.get("clips")]
        if candidates and requested_id.startswith("track_"):
            track = candidates[0]
            track["id"] = requested_id
            track["order"] = order
            return track
        track = {"id": requested_id, "kind": kind, "order": order, "muted": False, "locked": False, "clips": []}
        sequence["tracks"].append(track)
        return track

    for track_index, otio_track in enumerate(raw_tracks if isinstance(raw_tracks, list) else []):
        if not isinstance(otio_track, dict):
            continue
        if otio_track.get("OTIO_SCHEMA", "").startswith("Stack."):
            nested_tracks = otio_track.get("children", [])
            for nested_index, nested in enumerate(nested_tracks if isinstance(nested_tracks, list) else []):
                if isinstance(nested, dict):
                    raw_tracks.append(nested)
            continue
        children = otio_track.get("children", []) if isinstance(otio_track.get("children"), list) else []
        track = track_for(otio_track, track_index)
        current_tick = 0
        for child_index, child in enumerate(children):
            if not isinstance(child, dict):
                continue
            schema = str(child.get("OTIO_SCHEMA", ""))
            if schema.startswith("Gap."):
                gap_range = child.get("source_range") if isinstance(child.get("source_range"), dict) else {}
                current_tick += _otio_ticks(gap_range.get("duration"), import_tps, 0)
                continue
            if not schema.startswith("Clip.") and child.get("media_reference") is None:
                report_items.append(report_item("timeline-item", "Unsupported", str(child.get("name", child_index)), track.get("id"), "仅支持 OTIO Clip 或带媒体引用的节点"))
                continue
            ref = child.get("media_reference") or {}
            uri = ref.get("target_url") or child.get("target_url")
            metadata = child.get("metadata") if isinstance(child.get("metadata"), dict) else {}
            local_metadata = metadata.get("ai_ad_editor") if isinstance(metadata.get("ai_ad_editor"), dict) else {}
            preserved_clip = local_metadata.get("clip") if isinstance(local_metadata.get("clip"), dict) else {}
            asset: dict[str, Any] | None = None
            if uri:
                path = _path_from_uri(str(uri), source.parent)
                if not path.exists():
                    report_items.append(report_item("media-reference", "Failed", str(uri), child.get("name"), "本地文件不存在"))
                    continue
                key = str(path.resolve())
                if key not in asset_by_uri:
                    asset, rights = _asset_from_local(path, root)
                    project["assets"].append(asset)
                    add_record(ledger, rights)
                    asset_by_uri[key] = asset
                asset = asset_by_uri[key]
            elif str(ref.get("OTIO_SCHEMA", "")).startswith("GeneratorReference.") and preserved_clip.get("generator"):
                report_items.append(report_item("text-generator", "Mapped", str(child.get("name")), track.get("id"), "GeneratorReference 通过 ai_ad_editor metadata 恢复为本地文字片段"))
            else:
                report_items.append(report_item("media-reference", "Unsupported", str(child.get("name", child_index)), track.get("id"), "缺少本地 target_url 或可恢复的本地生成器"))
                continue
            source_range = child.get("source_range") if isinstance(child.get("source_range"), dict) else {}
            duration_tick = _otio_ticks(source_range.get("duration"), import_tps, 0)
            source_in_tick = _otio_ticks(source_range.get("start_time"), import_tps, 0)
            if not duration_tick and asset:
                duration_tick = max(1, int(asset.get("probe", {}).get("duration_tick", TICKS_PER_SECOND)))
            duration_tick = max(1, duration_tick)
            timeline_start = max(current_tick, _otio_ticks(local_metadata.get("timeline_start"), import_tps, current_tick))
            if local_metadata.get("timeline_start_tick") is not None:
                try:
                    timeline_start = max(0, int(local_metadata["timeline_start_tick"]))
                except (TypeError, ValueError):
                    pass
            if preserved_clip:
                clip = copy.deepcopy(preserved_clip)
                clip["id"] = str(clip.get("id") or child.get("name") or new_id("clip"))
                clip["timeline_start_tick"] = timeline_start
                clip["duration_tick"] = max(1, int(clip.get("duration_tick", duration_tick)))
                clip["source_in_tick"] = max(0, int(clip.get("source_in_tick", source_in_tick)))
                clip["source_out_tick"] = max(clip["source_in_tick"] + 1, int(clip.get("source_out_tick", clip["source_in_tick"] + clip["duration_tick"])))
            else:
                clip = {"id": str(child.get("name") or new_id("clip")), "timeline_start_tick": timeline_start, "duration_tick": duration_tick, "source_in_tick": source_in_tick, "source_out_tick": source_in_tick + duration_tick}
            if asset:
                clip["asset_id"] = asset["id"]
            else:
                clip.pop("asset_id", None)
            track.setdefault("clips", []).append(clip)
            current_tick = max(current_tick, timeline_start + int(clip.get("duration_tick", duration_tick)))
            sequence["duration_tick"] = max(sequence["duration_tick"], current_tick)
    save_project(root, project)
    save_ledger(root, ledger)
    return root, project, report_items


def _import_kdenlive_xml(source: Path, destination: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    root, project = create_project(destination, name=source.stem)
    ledger = {"schema_version": "0.1.0", "updated_at": now_iso(), "records": [], "policy": {}}
    report_items: list[dict[str, Any]] = [report_item("project-model", "Mapped", "Kdenlive MLT XML", "Agent Project JSON", "读取 playlist/blank/entry 时间轴、profile 帧率和本地 producer")]
    tree = ET.parse(source)
    root_element = tree.getroot()
    profile = root_element.find("./profile")
    try:
        fps_num = max(1, int(profile.get("frame_rate_num", "30") if profile is not None else "30"))
        fps_den = max(1, int(profile.get("frame_rate_den", "1") if profile is not None else "1"))
    except (TypeError, ValueError):
        fps_num, fps_den = 30, 1
        report_items.append(report_item("timebase", "Approximate", "Kdenlive MLT XML", "Agent Project JSON", "profile 帧率无效，回退 30/1"))
    producers: dict[str, Path] = {}
    for producer in root_element.findall("./producer"):
        resource = producer.find("property[@name='resource']")
        if resource is not None and resource.text:
            path = _path_from_uri(resource.text, source.parent)
            if path.exists():
                producers[producer.get("id", new_id("producer"))] = path
    sequence = project["sequences"][0]
    asset_by_path: dict[str, dict[str, Any]] = {}
    track_by_id: dict[str, dict[str, Any]] = {}
    def target_track(playlist: ET.Element, playlist_index: int) -> dict[str, Any]:
        raw_kind = (playlist.findtext("property[@name='ai_ad_editor_track_kind']") or "video").lower()
        kind = "audio" if raw_kind == "audio" else "subtitle" if raw_kind == "subtitle" else "video"
        track_id = playlist.findtext("property[@name='ai_ad_editor_track_id']") or playlist.get("id") or f"track_{kind}_{playlist_index + 1}"
        try:
            order = int(playlist.findtext("property[@name='ai_ad_editor_track_order']") or playlist_index)
        except (TypeError, ValueError):
            order = playlist_index
        if track_id in track_by_id:
            return track_by_id[track_id]
        for candidate in sequence["tracks"]:
            if candidate.get("kind") == kind and not candidate.get("clips") and track_id.startswith("track_"):
                candidate["id"] = track_id
                candidate["order"] = order
                track_by_id[track_id] = candidate
                return candidate
        track = {"id": track_id, "kind": kind, "order": order, "muted": False, "locked": False, "clips": []}
        sequence["tracks"].append(track)
        track_by_id[track_id] = track
        return track

    for playlist_index, playlist in enumerate(root_element.findall("./playlist")):
        track = target_track(playlist, playlist_index)
        cursor_frame = 0
        for child in list(playlist):
            if child.tag == "blank":
                try:
                    cursor_frame += max(0, int(child.get("length", "0")))
                except (TypeError, ValueError):
                    report_items.append(report_item("timeline-gap", "Approximate", playlist.get("id", "playlist"), track.get("id"), "MLT blank 长度无效，忽略该空隙"))
                continue
            if child.tag != "entry":
                continue
            producer_id = child.get("producer")
            path = producers.get(producer_id or "")
            if not path:
                report_items.append(report_item("media-reference", "Unsupported", str(producer_id), track.get("id"), "producer 未能解析为本地文件"))
                continue
            path_key = str(path.resolve())
            asset = asset_by_path.get(path_key)
            if asset is None:
                asset, rights = _asset_from_local(path, root)
                project["assets"].append(asset)
                add_record(ledger, rights)
                asset_by_path[path_key] = asset
            try:
                source_in_frame = max(0, int(child.get("in", "0")))
                source_out_frame = max(source_in_frame, int(child.get("out", str(source_in_frame))))
            except (TypeError, ValueError):
                source_in_frame, source_out_frame = 0, 0
                report_items.append(report_item("timebase", "Approximate", str(producer_id), track.get("id"), "entry 的 in/out 帧无效，使用 0"))
            duration_frames = max(1, source_out_frame - source_in_frame + 1)
            source_in_tick = int(round(source_in_frame * fps_den / fps_num * TICKS_PER_SECOND))
            duration_tick = int(round(duration_frames * fps_den / fps_num * TICKS_PER_SECOND))
            duration_tick = max(1, duration_tick)
            timeline_text = child.findtext("property[@name='ai_ad_editor_timeline_start_tick']")
            duration_text = child.findtext("property[@name='ai_ad_editor_duration_tick']")
            try:
                timeline_start = max(0, int(timeline_text)) if timeline_text is not None else int(round(cursor_frame * fps_den / fps_num * TICKS_PER_SECOND))
            except (TypeError, ValueError):
                timeline_start = int(round(cursor_frame * fps_den / fps_num * TICKS_PER_SECOND))
            try:
                duration_tick = max(1, int(duration_text)) if duration_text is not None else duration_tick
            except (TypeError, ValueError):
                pass
            clip_json = child.findtext("property[@name='ai_ad_editor_clip_json']")
            clip: dict[str, Any]
            if clip_json:
                try:
                    clip = json.loads(clip_json)
                except (TypeError, ValueError):
                    clip = {}
                    report_items.append(report_item("clip-metadata", "Approximate", str(producer_id), track.get("id"), "ai_ad_editor_clip_json 无法解析，使用基础片段"))
            else:
                clip = {}
            if not isinstance(clip, dict):
                clip = {}
            clip["id"] = str(child.findtext("property[@name='ai_ad_editor_clip_id']") or clip.get("id") or new_id("clip"))
            clip["asset_id"] = asset["id"]
            clip["timeline_start_tick"] = timeline_start
            clip["duration_tick"] = duration_tick
            clip["source_in_tick"] = max(0, int(clip.get("source_in_tick", source_in_tick)))
            clip["source_out_tick"] = max(clip["source_in_tick"] + 1, int(clip.get("source_out_tick", clip["source_in_tick"] + duration_tick)))
            track["clips"].append(clip)
            cursor_frame = max(cursor_frame, int(round((timeline_start / TICKS_PER_SECOND) * fps_num / fps_den)) + duration_frames)
            sequence["duration_tick"] = max(sequence["duration_tick"], timeline_start + duration_tick)
    project["sequences"][0]["duration_tick"] = max(sequence.get("duration_tick", 1), 1)
    save_project(root, project)
    save_ledger(root, ledger)
    return root, project, report_items


def import_external(source: Path, destination: Path) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    if source.suffix.lower() in {".json", ".otio"}:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        if payload.get("schema_version") == "0.1.0":
            root, project = create_project(destination, name=payload.get("project", {}).get("name") or source.stem)
            report_items = [report_item("project-model", "Exact", str(source), "Agent Project JSON")]
            ledger = {"schema_version": "0.1.0", "updated_at": now_iso(), "records": [], "policy": {}}
            for asset in payload.get("assets", []):
                original = Path(str(asset.get("uri", "")))
                if not original.is_absolute():
                    original = source.parent / original
                if original.exists():
                    copied = root / "assets" / f"{asset.get('id', new_id('asset'))}_{safe_filename(original.name)}"
                    shutil.copy2(original, copied)
                    asset["uri"] = str(copied.relative_to(root)).replace("\\", "/")
                    asset["sha256"] = f"sha256:{sha256_file(copied)}"
                    record = {"asset_id": asset.get("rights_ref") or asset.get("id"), "kind": asset.get("kind", "video"), "sha256": asset["sha256"], "source_url": asset.get("source", {}).get("source_url", f"local://{original}"), "source_version": "import", "retrieved_at": now_iso(), "creator": "unknown", "license_spdx": "LicenseRef-UNVERIFIED", "license_url": "", "attribution": "", "permitted_uses": ["internal"], "restrictions": [], "evidence": "", "verification_status": "unverified", "verified_by": "", "takedown_status": "clear", "notes": "Imported project asset; verify before publish"}
                    add_record(ledger, record)
                else:
                    report_items.append(report_item("asset", "Failed", str(original), asset.get("id"), "资产文件不存在，已保留项目引用"))
            project = payload
            save_project(root, project)
            save_ledger(root, ledger)
            report = {"report_version": "0.1.0", "direction": "import", "source_format": "agent-project/0.1.0", "target_format": "agent-project/0.1.0", "created_at": now_iso(), "items": report_items, "warnings": [item for item in report_items if item["status"] in {"Approximate", "Unsupported"}], "failures": [item for item in report_items if item["status"] == "Failed"]}
            report_path = root / "validation" / f"conversion_{new_id('report')}.json"
            atomic_write_json(report_path, report)
            return {"root": str(root), "project": str(root / "project.json"), "report": str(report_path), "report_data": report}
        root, _, items = _import_otio(source, destination, payload)
    elif source.suffix.lower() in {".xml", ".kdenlive"}:
        root, _, items = _import_kdenlive_xml(source, destination)
    else:
        raise ValueError(f"不支持的外部格式: {source.suffix}")
    report = {"report_version": "0.1.0", "direction": "import", "source_format": source.suffix.lower().lstrip("."), "target_format": "agent-project/0.1.0", "created_at": now_iso(), "items": items, "warnings": [item for item in items if item["status"] in {"Approximate", "Unsupported"}], "failures": [item for item in items if item["status"] == "Failed"]}
    report_path = root / "validation" / f"conversion_{new_id('report')}.json"
    atomic_write_json(report_path, report)
    return {"root": str(root), "project": str(root / "project.json"), "report": str(report_path), "report_data": report}
