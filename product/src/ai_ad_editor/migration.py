from __future__ import annotations

import copy
import re
from typing import Any

from . import ENGINE_ID, SCHEMA_VERSION, VERSION
from .errors import AppError


# 0.0.0 denotes this project's prototype tick-based shape. Unknown external
# formats must go through an explicit converter instead of being guessed here.
SUPPORTED_SOURCE_VERSIONS = {"0.0.0", SCHEMA_VERSION}


def migrate_project_payload(
    project: dict[str, Any],
    *,
    timestamp: str,
    asset_metadata: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Transform a known schema without I/O, generated IDs or input mutation.

    The caller provides the timestamp and any missing local asset metadata.
    Existing IDs, references, timing, extension fields and rights remain intact.
    Structural/semantic validation is required before committing the result.
    """
    if not isinstance(project, dict):
        raise AppError("MIGRATION_PROJECT_INVALID", "待迁移项目必须是 JSON 对象", exit_code=2)
    source_version = project.get("schema_version")
    if not isinstance(source_version, str) or source_version not in SUPPORTED_SOURCE_VERSIONS:
        raise AppError("SCHEMA_VERSION_UNSUPPORTED", "迁移仅支持本项目 schema 0.0.0 和 0.1.0；未知格式须使用显式转换器", exit_code=2, path="schema_version")
    candidate = copy.deepcopy(project)
    changes: list[str] = []

    def object_value(container: dict[str, Any], key: str, path: str) -> dict[str, Any]:
        value = container.get(key)
        if not isinstance(value, dict):
            raise AppError("MIGRATION_FIELD_INVALID", f"{path} 必须是对象", exit_code=2, path=path)
        return value

    def array_value(container: dict[str, Any], key: str, path: str) -> list[Any]:
        value = container.get(key)
        if not isinstance(value, list):
            raise AppError("MIGRATION_FIELD_INVALID", f"{path} 必须是数组", exit_code=2, path=path)
        return value

    def fill(container: dict[str, Any], defaults: dict[str, Any], path: str) -> None:
        for key, value in defaults.items():
            field_path = f"{path}.{key}" if path else key
            if key not in container:
                container[key] = copy.deepcopy(value)
                changes.append(f"add:{field_path}")
            elif isinstance(value, dict):
                fill(object_value(container, key, field_path), value, field_path)

    project_meta = object_value(candidate, "project", "project")
    settings = object_value(candidate, "settings", "settings")
    object_value(settings, "timebase", "settings.timebase")
    object_value(settings, "canvas", "settings.canvas")
    assets = array_value(candidate, "assets", "assets")
    sequences = array_value(candidate, "sequences", "sequences")
    fill(project_meta, {"creator": "ai-ad-editor", "source_revision": "migrated"}, "project")
    fill(settings, {
        "color": {"primaries": "bt709", "transfer": "bt709", "matrix": "bt709", "range": "limited"},
        "audio": {"sample_rate": 48_000, "channels": 2},
    }, "settings")
    # Do not infer an encoder for a partial user-defined output policy.
    if "output" not in settings:
        fill(settings, {"output": {"container": "mp4", "video": {"codec": "libx264", "preset": "medium", "crf": 18, "pixel_format": "yuv420p"}, "audio": {"codec": "aac", "bitrate": "192k"}}}, "settings")
    for index, asset in enumerate(assets):
        path = f"assets[{index}]"
        if not isinstance(asset, dict) or not isinstance(asset.get("id"), str):
            raise AppError("MIGRATION_ASSET_INVALID", "迁移资产必须保留稳定 ID", exit_code=2, path=path)
        supplied = (asset_metadata or {}).get(asset["id"], {})
        if not asset.get("sha256"):
            if not supplied.get("sha256"):
                raise AppError("MIGRATION_ASSET_HASH_MISSING", "资产缺少已核验的本地 sha256", exit_code=3, path=f"{path}.sha256")
            asset["sha256"] = supplied["sha256"]
            changes.append(f"add:{path}.sha256")
        elif isinstance(asset["sha256"], str) and re.fullmatch(r"[A-Fa-f0-9]{64}", asset["sha256"]):
            asset["sha256"] = f"sha256:{asset['sha256']}"
            changes.append(f"normalize:{path}.sha256")
        if "probe" not in asset and isinstance(supplied.get("probe"), dict):
            fill(asset, {"probe": supplied["probe"]}, path)
        fill(asset, {"rights_ref": asset["id"]}, path)
    for sequence_index, sequence in enumerate(sequences):
        path = f"sequences[{sequence_index}]"
        if not isinstance(sequence, dict):
            raise AppError("MIGRATION_SEQUENCE_INVALID", "序列必须是对象", exit_code=2, path=path)
        fill(sequence, {"markers": []}, path)
        for track_index, track in enumerate(array_value(sequence, "tracks", f"{path}.tracks")):
            track_path = f"{path}.tracks[{track_index}]"
            if not isinstance(track, dict):
                raise AppError("MIGRATION_TRACK_INVALID", "轨道必须是对象", exit_code=2, path=track_path)
            fill(track, {"muted": False, "locked": False}, track_path)
            array_value(track, "clips", f"{track_path}.clips")
    fill(candidate, {"templates": [], "outputs": [], "provenance": {}}, "")
    provenance = object_value(candidate, "provenance", "provenance")
    fill(provenance, {"cli_version": VERSION, "engine_version": ENGINE_ID, "model_versions": [], "input_hashes": [], "change_log": []}, "provenance")
    array_value(provenance, "change_log", "provenance.change_log")
    if source_version != SCHEMA_VERSION:
        candidate["schema_version"] = SCHEMA_VERSION
        changes.append(f"version:{source_version}->{SCHEMA_VERSION}")
    if changes:
        fill(provenance, {"migrations": []}, "provenance")
        migration_entry = {"from": source_version, "to": SCHEMA_VERSION, "at": timestamp, "changes": list(changes)}
        array_value(provenance, "migrations", "provenance.migrations").append(copy.deepcopy(migration_entry))
        provenance["change_log"].append({"command": "project.migrate", **migration_entry})
        project_meta["updated_at"] = timestamp
    return candidate, {
        "report_version": "0.1.0",
        "source_version": source_version,
        "target_version": SCHEMA_VERSION,
        "changed": bool(changes),
        "changes": changes,
        "asset_count": len(assets),
        "sequence_count": len(sequences),
    }
