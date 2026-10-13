from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .errors import AppError, argument_error


ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request_fingerprint(command: str, args: Any) -> str:
    """Create a stable fingerprint for a project-bound CLI request.

    Request IDs, output formatting and progress transport are presentation details;
    input paths and file contents remain part of the fingerprint so reusing a key
    with a changed edit plan is rejected instead of silently replaying stale work.
    """
    values = dict(vars(args)) if hasattr(args, "__dict__") else dict(args)
    for field in ("request_id", "format", "progress", "idempotency_key", "dry_run"):
        values.pop(field, None)
    for field in ("project", "input", "output", "variables", "report"):
        value = values.get(field)
        if not isinstance(value, str) or not value:
            continue
        candidate = Path(value).expanduser().resolve()
        values[field] = str(candidate)
        if candidate.is_file():
            try:
                values[field + "_sha256"] = sha256_file(candidate)
            except OSError:
                values[field + "_unreadable"] = True
    payload = json.dumps({"command": command, "request": values}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def idempotency_record_path(root: Path, command: str, key: str) -> Path:
    digest = sha256_bytes(f"{command}\n{key}".encode("utf-8"))
    return root / "operations" / "idempotency" / f"{digest}.json"


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise AppError("FILE_NOT_FOUND", f"文件不存在: {path}", exit_code=3, path=str(path)) from exc
    except json.JSONDecodeError as exc:
        raise AppError("JSON_INVALID", f"JSON 无法解析: {path}: {exc}", exit_code=2, path=str(path)) from exc
    if not isinstance(value, dict):
        raise AppError("JSON_OBJECT_REQUIRED", "顶层 JSON 必须是对象", exit_code=2, path=str(path))
    return value


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False)


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_write_text(path: Path, value: str) -> None:
    """Write UTF-8 text through a same-directory temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_replace(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)


def project_root(path: str | Path) -> Path:
    root = Path(path).expanduser().resolve()
    if root.suffix.lower() == ".json" and root.name.lower() == "project.json":
        root = root.parent
    return root


def ensure_inside(root: Path, candidate: Path, *, allow_external: bool = False) -> Path:
    root = root.resolve()
    candidate = candidate.expanduser().resolve()
    if allow_external:
        return candidate
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise argument_error(f"路径越过项目根目录: {candidate}", str(candidate)) from exc
    return candidate


def safe_filename(name: str) -> str:
    name = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name).strip("._")
    return cleaned or "asset.bin"


def executable(name: str) -> str | None:
    return shutil.which(name)


def run_process(
    args: Iterable[str],
    *,
    timeout: float | None = None,
    cwd: Path | None = None,
    cancel_file: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = list(args)
    if cancel_file is not None and cancel_file.exists():
        raise AppError("CANCELLED", "任务在启动前已被取消", exit_code=8, path=str(cancel_file), retryable=False)
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        result: dict[str, str] = {}

        def collect() -> None:
            stdout, stderr = process.communicate()
            result["stdout"] = stdout or ""
            result["stderr"] = stderr or ""

        reader = threading.Thread(target=collect, name="ai-ad-editor-process-reader", daemon=True)
        reader.start()
        started = time.monotonic()

        def stop_process() -> None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            reader.join(timeout=5)

        while reader.is_alive():
            if cancel_file is not None and cancel_file.exists():
                stop_process()
                raise AppError("CANCELLED", "任务已取消，临时产物将被清理", exit_code=8, path=str(cancel_file), retryable=False, cause=result.get("stderr", "")[-2000:])
            if timeout is not None and time.monotonic() - started > timeout:
                stop_process()
                raise AppError("PROCESS_TIMEOUT", f"子进程超时: {command[0]}", exit_code=6, retryable=True, cause=result.get("stderr", "")[-2000:])
            reader.join(timeout=0.1)
        return subprocess.CompletedProcess(command, process.returncode, result.get("stdout", ""), result.get("stderr", ""))
    except OSError as exc:
        raise AppError("PROCESS_START_FAILED", f"无法启动子进程: {command[0]}", exit_code=10, cause=str(exc)) from exc


def assert_id(value: str, path: str) -> None:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise argument_error("ID 不符合规范", path)
