from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from . import ENGINE_ID, SCHEMA_VERSION, VERSION
from .errors import AppError, argument_error
from .utils import atomic_write_json, load_json, new_id, now_iso, project_root


TICKS_PER_SECOND = 90_000


def project_file(root: Path) -> Path:
    return root / "project.json"


def ledger_file(root: Path) -> Path:
    return root / "rights-ledger.json"


def lock_file(root: Path) -> Path:
    return root / "project.lock.json"


def history_dir(root: Path) -> Path:
    """Return the project-local immutable snapshot directory."""
    return root / "history"


def initial_project(name: str, project_id: str | None = None) -> dict[str, Any]:
    stamp = now_iso()
    pid = project_id or new_id("proj")
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "id": pid,
            "name": name,
            "created_at": stamp,
            "updated_at": stamp,
            "creator": "ai-ad-editor",
            "source_revision": "local",
        },
        "settings": {
            "timebase": {"ticks_per_second": TICKS_PER_SECOND, "display_fps": {"num": 30, "den": 1}},
            "canvas": {"width": 1080, "height": 1920, "pixel_aspect": {"num": 1, "den": 1}},
            "color": {"primaries": "bt709", "transfer": "bt709", "matrix": "bt709", "range": "limited"},
            "audio": {"sample_rate": 48_000, "channels": 2},
            "output": {"container": "mp4", "video": {"codec": "libx264", "preset": "medium", "crf": 18, "pixel_format": "yuv420p"}, "audio": {"codec": "aac", "bitrate": "192k"}},
        },
        "assets": [],
        "sequences": [
            {
                "id": "seq_main",
                "name": "Main",
                "duration_tick": 1,
                "tracks": [
                    {"id": "track_video_1", "kind": "video", "order": 0, "muted": False, "locked": False, "clips": []},
                    {"id": "track_audio_1", "kind": "audio", "order": 0, "muted": False, "locked": False, "clips": []},
                ],
                "markers": [],
            }
        ],
        "templates": [],
        "outputs": [],
        "provenance": {
            "cli_version": VERSION,
            "engine_version": ENGINE_ID,
            "model_versions": [],
            "input_hashes": [],
            "change_log": [],
        },
    }


def initial_ledger() -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "updated_at": now_iso(),
        "records": [],
        "policy": {"default_target": "commercial_ad", "unverified_publish": False},
    }


def create_project(root_value: str | Path, name: str | None = None, project_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    root = project_root(root_value)
    if root.exists() and any(root.iterdir()):
        raise AppError("PROJECT_EXISTS", f"项目目录非空，拒绝覆盖: {root}", exit_code=2, path=str(root))
    root.mkdir(parents=True, exist_ok=True)
    for directory in ("assets", "renders", "operations", "validation", "exports", "cache", "history"):
        (root / directory).mkdir(exist_ok=True)
    project = initial_project(name or root.name, project_id)
    atomic_write_json(project_file(root), project)
    atomic_write_json(ledger_file(root), initial_ledger())
    atomic_write_json(
        lock_file(root),
        {
            "lock_version": "0.1.0",
            "created_at": now_iso(),
            "cli_version": VERSION,
            "schema_version": SCHEMA_VERSION,
            "engine": {"id": ENGINE_ID, "version": "pending-doctor"},
            "platform": "windows-native",
            "network": "disabled-by-default",
            "upstream_runtime": "none",
        },
    )
    return root, project


def load_project(value: str | Path) -> tuple[Path, dict[str, Any]]:
    root = project_root(value)
    return root, load_json(project_file(root))


def save_project(root: Path, project: dict[str, Any]) -> None:
    project.setdefault("provenance", {}).setdefault("change_log", [])
    project["project"]["updated_at"] = now_iso()
    atomic_write_json(project_file(root), project)


def create_snapshot(root: Path, project: dict[str, Any], *, label: str = "manual") -> dict[str, Any]:
    """Persist a self-contained project/rights snapshot before a mutation.

    Snapshots are append-only JSON records. They are deliberately local and
    human-readable so an Agent can inspect or restore a prior edit state.
    """
    snapshot_id = new_id("snap")
    ledger = load_json(ledger_file(root)) if ledger_file(root).exists() else initial_ledger()
    lock = load_json(lock_file(root)) if lock_file(root).exists() else {}
    payload = {
        "snapshot_version": "0.1.0",
        "snapshot_id": snapshot_id,
        "created_at": now_iso(),
        "label": label,
        "project_id": project.get("project", {}).get("id"),
        "project": copy.deepcopy(project),
        "rights_ledger": copy.deepcopy(ledger),
        "lock": copy.deepcopy(lock),
    }
    path = history_dir(root) / f"{snapshot_id}.json"
    atomic_write_json(path, payload)
    return {"snapshot_id": snapshot_id, "path": str(path), "label": label, "created_at": payload["created_at"]}


def load_snapshot(root: Path, snapshot_id: str) -> dict[str, Any]:
    path = history_dir(root) / f"{snapshot_id}.json"
    return load_json(path)


def restore_snapshot(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Restore a validated snapshot's project files atomically."""
    project = payload.get("project")
    ledger = payload.get("rights_ledger")
    if not isinstance(project, dict) or not isinstance(ledger, dict):
        raise AppError("SNAPSHOT_INVALID", "快照缺少 project 或 rights_ledger", exit_code=2)
    atomic_write_json(project_file(root), project)
    atomic_write_json(ledger_file(root), ledger)
    if isinstance(payload.get("lock"), dict):
        atomic_write_json(lock_file(root), payload["lock"])
    return {"project": str(project_file(root)), "ledger": str(ledger_file(root)), "project_id": project.get("project", {}).get("id")}


def find_sequence(project: dict[str, Any], sequence_id: str | None = None) -> dict[str, Any]:
    sequences = project.get("sequences", [])
    if not sequences:
        raise AppError("SEQUENCE_MISSING", "项目没有序列", exit_code=2, path="sequences")
    wanted = sequence_id or sequences[0].get("id")
    for sequence in sequences:
        if sequence.get("id") == wanted:
            return sequence
    raise AppError("SEQUENCE_NOT_FOUND", f"找不到序列: {wanted}", exit_code=2, path="sequences")


def find_track(sequence: dict[str, Any], track_id: str | None = None, kind: str | None = None) -> dict[str, Any]:
    tracks = sequence.get("tracks", [])
    for track in tracks:
        if track_id and track.get("id") == track_id:
            return track
        if not track_id and kind and track.get("kind") == kind and not track.get("locked", False):
            return track
    descriptor = track_id or kind or "<default>"
    raise AppError("TRACK_NOT_FOUND", f"找不到轨道: {descriptor}", exit_code=2, path="sequences[].tracks")


def asset_map(project: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(asset.get("id")): asset for asset in project.get("assets", []) if asset.get("id")}


def clone_project(project: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(project)

