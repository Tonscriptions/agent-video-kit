from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import data_dir


def _log_dir(project_id: str) -> Path:
    path = data_dir() / "projects" / project_id / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log_path(project_id: str, session_id: str) -> Path:
    return _log_dir(project_id) / f"{session_id}.jsonl"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectLogger:
    """Append-only structured JSON logger for a single project run."""

    def __init__(self, project_id: str, session_id: str | None = None):
        self.project_id = project_id
        self.session_id = session_id or f"{int(time.time() * 1000)}"
        self._path: Path | None = None

    def _ensure_path(self) -> Path:
        if self._path is None:
            self._path = _log_path(self.project_id, self.session_id)
        return self._path

    def _write(self, record: dict[str, Any]) -> None:
        try:
            path = self._ensure_path()
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except OSError:
            pass  # logging must never crash the server

    def info(self, stage: str, message: str, **extra: Any) -> None:
        self._write({"ts": _ts(), "level": "info", "stage": stage, "message": message, **extra})

    def warning(self, stage: str, message: str, **extra: Any) -> None:
        self._write({"ts": _ts(), "level": "warning", "stage": stage, "message": message, **extra})

    def error(self, stage: str, message: str, **extra: Any) -> None:
        self._write({"ts": _ts(), "level": "error", "stage": stage, "message": message, **extra})

    def timed(self, stage: str, message: str, elapsed: float, **extra: Any) -> None:
        self._write({"ts": _ts(), "level": "info", "stage": stage, "message": message, "elapsed_s": round(elapsed, 3), **extra})

    @property
    def log_path(self) -> str:
        return str(self._ensure_path())


def read_project_logs(project_id: str) -> list[dict[str, Any]]:
    """Return all log records for a project across all sessions, newest first."""
    log_dir = data_dir() / "projects" / project_id / "logs"
    if not log_dir.exists():
        return []
    records: list[dict[str, Any]] = []
    for log_file in sorted(log_dir.glob("*.jsonl"), reverse=True):
        try:
            for line in log_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def get_project_log_summary(project_id: str) -> dict[str, Any]:
    """Return a summary of recent log records for a project."""
    records = read_project_logs(project_id)
    errors = [r for r in records if r.get("level") == "error"]
    warnings = [r for r in records if r.get("level") == "warning"]
    log_dir = data_dir() / "projects" / project_id / "logs"
    session_files = sorted(log_dir.glob("*.jsonl"), reverse=True) if log_dir.exists() else []
    return {
        "ok": True,
        "project_id": project_id,
        "total_records": len(records),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "session_count": len(session_files),
        "recent_errors": errors[:5],
        "recent_records": records[:20],
    }
