from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
import copy
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from .media import classify_path, probe_media
from .project import TICKS_PER_SECOND, create_project, save_project
from .rights import add_record, load_ledger, save_ledger
from .utils import atomic_write_json, new_id, now_iso, safe_filename, sha256_file


def report_item(capability: str, status: str, source: str, target: str | None = None, detail: str = "") -> dict[str, Any]:
    return {"capability": capability, "status": status, "source": source, "target": target, "detail": detail}


def _path_from_uri(value: str) -> Path:
    parsed = urlparse(value)
    if parsed.scheme.lower() == "file":
        path = url2pathname(unquote(parsed.path))
        if parsed.netloc:
            path = f"\\\\{parsed.netloc}{path}"
        return Path(path)
    return Path(value.replace("file://", ""))


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
    fps = project["settings"]["timebase"].get("display_fps", {"num": 30, "den": 1})
    assets = {str(asset.get("id")): asset for asset in project.get("assets", [])}
    tracks: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = [report_item("project-model", "Mapped", "Agent Project JSON", "OpenTimelineIO JSON", "轨道和本地媒体引用映射；高级效果保留在 metadata")]
    sequence = project.get("sequences", [{}])[0]
    for track in sorted(sequence.get("tracks", []), key=lambda item: int(item.get("order", 0))):
        kind = "Audio" if track.get("kind") == "audio" else "Video"
        otio_track: dict[str, Any] = {"OTIO_SCHEMA": "Track.1", "name": track.get("id", "track"), "kind": kind, "children": []}
        for clip in sorted(track.get("clips", []), key=lambda item: int(item.get("timeline_start_tick", 0))):
            asset = assets.get(str(clip.get("asset_id")))
            if not asset:
                items.append(report_item("media-reference", "Failed", str(clip.get("asset_id")), None, "片段没有可导出的本地资产"))
                continue
            media_path = _asset_uri(root, asset)
            duration_tick = max(1, int(clip.get("duration_tick", 1)))
            source_in_tick = max(0, int(clip.get("source_in_tick", 0)))
            child: dict[str, Any] = {
                "OTIO_SCHEMA": "Clip.2",
                "name": clip.get("id", "clip"),
                "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": media_path.resolve().as_uri()},
                "source_range": {
                    "OTIO_SCHEMA": "TimeRange.1",
                    "start_time": {"OTIO_SCHEMA": "RationalTime.1", "value": source_in_tick / tps, "rate": 1},
                    "duration": {"OTIO_SCHEMA": "RationalTime.1", "value": duration_tick / tps, "rate": 1},
                },
                "metadata": {"ai_ad_editor": {"timeline_start_tick": int(clip.get("timeline_start_tick", 0)), "asset_id": asset.get("id")}},
            }
            if any(clip.get(field) for field in ("effects", "keyframes", "transition_in", "transition_out", "subtitle", "audio")):
                child["metadata"]["ai_ad_editor"]["unsupported_features"] = [field for field in ("effects", "keyframes", "transition_in", "transition_out", "subtitle", "audio") if clip.get(field)]
                items.append(report_item("clip-features", "Approximate", str(clip.get("id")), child["name"], "高级效果写入 metadata，OTIO 基础导出不执行这些效果"))
            otio_track["children"].append(child)
        tracks.append(otio_track)
    payload = {"OTIO_SCHEMA": "Timeline.1", "name": project.get("project", {}).get("name", "Agent Project"), "metadata": {"ai_ad_editor": {"schema_version": project.get("schema_version")}}, "tracks": tracks}
    atomic_write_json(output, payload)
    report = {"report_version": "0.1.0", "direction": "export", "source_format": "agent-project/0.1.0", "target_format": "opentimelineio-json", "created_at": now_iso(), "items": items, "warnings": [item for item in items if item["status"] in {"Approximate", "Unsupported"}], "failures": [item for item in items if item["status"] == "Failed"]}
    report_path = output.with_suffix(output.suffix + ".conversion-report.json")
    atomic_write_json(report_path, report)
    return {"output": str(output), "report": str(report_path), "report_data": report}


def _export_kdenlive_xml(root: Path, project: dict[str, Any], output: Path) -> dict[str, Any]:
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    fps = project["settings"]["timebase"].get("display_fps", {"num": 30, "den": 1})
    profile = f"atsc_1080p_{int(fps.get('num', 30))}"
    assets = {str(asset.get("id")): asset for asset in project.get("assets", [])}
    root_element = ET.Element("mlt", {"version": "7.0", "profile": profile})
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
            duration_frames = max(1, round(duration_tick / tps * int(fps.get("num", 30)) / int(fps.get("den", 1))))
            in_frame = max(0, round(source_in_tick / tps * int(fps.get("num", 30)) / int(fps.get("den", 1))))
            ET.SubElement(playlist, "entry", {"producer": producer_id, "in": str(in_frame), "out": str(in_frame + duration_frames - 1)})
            if any(clip.get(field) for field in ("effects", "keyframes", "transition_in", "transition_out", "subtitle", "audio")):
                items.append(report_item("clip-features", "Approximate", str(clip.get("id")), producer_id, "复杂片段属性未转换为 MLT filter/transition"))
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
    report_items: list[dict[str, Any]] = [report_item("project-model", "Mapped", "OpenTimelineIO", "Agent Project JSON", "OTIO fields are mapped into the local model")]
    asset_by_uri: dict[str, dict[str, Any]] = {}
    track_index = 0
    for otio_track in payload.get("tracks", []) or payload.get("children", []):
        if not isinstance(otio_track, dict):
            continue
        children = otio_track.get("children", [])
        kind = "audio" if str(otio_track.get("kind", "")).lower() == "audio" else "video"
        track = sequence["tracks"][0 if kind == "video" else 1]
        current_tick = 0
        for child in children:
            if not isinstance(child, dict):
                continue
            ref = child.get("media_reference") or {}
            uri = ref.get("target_url") or child.get("target_url")
            if not uri:
                report_items.append(report_item("media-reference", "Unsupported", "OTIO clip", None, "缺少本地 target_url"))
                continue
            path = _path_from_uri(str(uri))
            if not path.exists():
                report_items.append(report_item("media-reference", "Failed", str(uri), None, "本地文件不存在"))
                continue
            key = str(path.resolve())
            if key not in asset_by_uri:
                asset, rights = _asset_from_local(path, root)
                project["assets"].append(asset)
                add_record(ledger, rights)
                asset_by_uri[key] = asset
            asset = asset_by_uri[key]
            source_range = child.get("source_range") if isinstance(child.get("source_range"), dict) else {}
            duration_value = source_range.get("duration", {}).get("value") if isinstance(source_range.get("duration"), dict) else None
            duration_rate = source_range.get("duration", {}).get("rate", 1) if isinstance(source_range.get("duration"), dict) else 1
            start_value = source_range.get("start_time", {}).get("value") if isinstance(source_range.get("start_time"), dict) else 0
            start_rate = source_range.get("start_time", {}).get("rate", duration_rate) if isinstance(source_range.get("start_time"), dict) else duration_rate
            try:
                duration_seconds = float(duration_value) / max(float(duration_rate), 1e-9) if duration_value is not None else float(asset["probe"].get("duration_seconds", 1))
                source_in_seconds = float(start_value or 0) / max(float(start_rate or 1), 1e-9)
            except (TypeError, ValueError):
                duration_seconds = float(asset["probe"].get("duration_seconds", 1))
                source_in_seconds = 0.0
            duration_tick = max(1, int(round(duration_seconds * TICKS_PER_SECOND)))
            source_in_tick = max(0, int(round(source_in_seconds * TICKS_PER_SECOND)))
            metadata = child.get("metadata") if isinstance(child.get("metadata"), dict) else {}
            local_metadata = metadata.get("ai_ad_editor") if isinstance(metadata.get("ai_ad_editor"), dict) else {}
            timeline_start = local_metadata.get("timeline_start_tick", current_tick)
            try:
                timeline_start = max(0, int(timeline_start))
            except (TypeError, ValueError):
                timeline_start = current_tick
            clip = {"id": new_id("clip"), "asset_id": asset["id"], "timeline_start_tick": timeline_start, "duration_tick": duration_tick, "source_in_tick": source_in_tick, "source_out_tick": source_in_tick + duration_tick}
            track.setdefault("clips", []).append(clip)
            current_tick = max(current_tick, timeline_start + duration_tick)
            sequence["duration_tick"] = max(sequence["duration_tick"], current_tick)
    save_project(root, project)
    save_ledger(root, ledger)
    return root, project, report_items


def _import_kdenlive_xml(source: Path, destination: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    root, project = create_project(destination, name=source.stem)
    ledger = {"schema_version": "0.1.0", "updated_at": now_iso(), "records": [], "policy": {}}
    report_items: list[dict[str, Any]] = [report_item("project-model", "Approximate", "Kdenlive MLT XML", "Agent Project JSON", "仅导入可定位的本地 producer 与顺序片段")]
    tree = ET.parse(source)
    producers: dict[str, Path] = {}
    for producer in tree.findall(".//producer"):
        resource = producer.find("property[@name='resource']")
        if resource is not None and resource.text:
            path = Path(resource.text)
            if path.exists():
                producers[producer.get("id", new_id("producer"))] = path
    track = project["sequences"][0]["tracks"][0]
    current = 0
    for entry in tree.findall(".//playlist/entry"):
        producer_id = entry.get("producer")
        path = producers.get(producer_id or "")
        if not path:
            report_items.append(report_item("media-reference", "Unsupported", str(producer_id), None, "producer 未能解析为本地文件"))
            continue
        asset, rights = _asset_from_local(path, root)
        project["assets"].append(asset)
        add_record(ledger, rights)
        duration = max(int(asset["probe"].get("duration_tick", TICKS_PER_SECOND)), 1)
        track["clips"].append({"id": new_id("clip"), "asset_id": asset["id"], "timeline_start_tick": current, "duration_tick": duration, "source_in_tick": 0, "source_out_tick": duration})
        current += duration
    project["sequences"][0]["duration_tick"] = max(current, 1)
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
