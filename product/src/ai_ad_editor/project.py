from __future__ import annotations

import copy
import os
import time
from contextlib import contextmanager
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


def write_lock_file(root: Path) -> Path:
    """Return the native process lock used to serialize project mutations."""
    return root / "operations" / "project-write.lock"


@contextmanager
def _native_byte_lock(path: Path, *, timeout: float, error_code: str, message: str):
    """Acquire one byte of a local file with a bounded non-blocking retry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    started = time.monotonic()
    acquired = False
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (OSError, BlockingIOError):
                if timeout <= 0 or time.monotonic() - started >= timeout:
                    raise AppError(error_code, message, exit_code=6, path=str(path), retryable=True)
                time.sleep(min(0.05, max(0.01, timeout / 10)))
        yield {"path": str(path), "acquired": True}
    finally:
        if acquired:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
        else:
            handle.close()


def cancel_lock_file(root: Path) -> Path:
    """Return the short-lived lock for cancellation marker arbitration."""
    return root / "operations" / "queue-cancel.lock"


@contextmanager
def project_write_lock(root_value: str | Path, *, timeout: float = 0.0):
    """Serialize project-bound mutations with a native file lock.

    The lock is advisory at the operating-system level and is held for the
    complete CLI operation, including its read-modify-write phase.  Windows
    uses ``msvcrt.locking``; POSIX is supported for deterministic unit tests and
    future portability.  A zero timeout fails immediately so an Agent can
    retry from the structured ``PROJECT_WRITE_LOCKED`` response.
    """
    root = project_root(root_value)
    if not project_file(root).exists():
        # Let the command handler return its normal project-not-found/schema
        # error without creating an operations directory as a side effect.
        yield {"path": str(write_lock_file(root)), "root": str(root), "acquired": False}
        return
    path = write_lock_file(root)
    with _native_byte_lock(path, timeout=timeout, error_code="PROJECT_WRITE_LOCKED", message=f"项目正在被另一个本地操作写入: {root}") as info:
        yield {"path": info["path"], "root": str(root), "acquired": True}


@contextmanager
def queue_cancel_lock(root_value: str | Path, *, timeout: float = 1.0):
    """Serialize short cancellation marker/state transitions.

    This lock is deliberately separate from the project write lock so a cancel
    request can arbitrate with queue start/finalization without waiting for the
    render itself to finish.
    """
    root = project_root(root_value)
    path = cancel_lock_file(root)
    with _native_byte_lock(path, timeout=timeout, error_code="QUEUE_CANCEL_CHANNEL_BUSY", message=f"队列取消通道正在处理另一个请求: {root}") as info:
        yield {"path": info["path"], "root": str(root), "acquired": True}


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
        "schema_version": "0.2.0",
        "updated_at": now_iso(),
        "records": [],
        "events": [],
        "decisions": [],
        "policy": {"default_target": "commercial_ad", "unverified_publish": False},
    }


def create_project(root_value: str | Path, name: str | None = None, project_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    root = project_root(root_value)
    if root.exists() and any(root.iterdir()):
        raise AppError("PROJECT_EXISTS", f"项目目录非空，拒绝覆盖: {root}", exit_code=2, path=str(root))
    root.mkdir(parents=True, exist_ok=True)
    for directory in ("assets", "renders", "operations", "validation", "exports", "cache", "history"):
        (root / directory).mkdir(exist_ok=True)
    write_lock_file(root).write_bytes(b"0")
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

