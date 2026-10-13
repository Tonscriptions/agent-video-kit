from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from .media import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, classify_path, probe_media
from .utils import atomic_write_json, new_id, now_iso, sha256_file


LIBRARY_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | {".srt", ".vtt", ".ass", ".ssa", ".ttf", ".otf", ".ttc"}


def _kind(path: Path, probe: dict[str, Any] | None) -> str:
    if path.suffix.lower() in {".srt", ".vtt", ".ass", ".ssa"}:
        return "subtitle"
    if path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
        return "font"
    return classify_path(path, probe)


def index_directory(source_root: Path, output: Path, *, max_files: int = 5000, license_spdx: str = "LicenseRef-UNVERIFIED", verification_status: str = "unverified") -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    files = [path for path in source_root.rglob("*") if path.is_file() and path.suffix.lower() in LIBRARY_EXTENSIONS]
    files.sort(key=lambda path: str(path).lower())
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for path in files[: max(0, int(max_files))]:
        try:
            probe = probe_media(path) if path.suffix.lower() in (VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS) else None
            digest = sha256_file(path)
            records.append({
                "id": f"lib_{digest[:24]}",
                "name": path.name,
                "kind": _kind(path, probe),
                "uri": str(path),
                "relative_uri": str(path.relative_to(source_root)).replace("\\", "/"),
                "sha256": f"sha256:{digest}",
                "bytes": path.stat().st_size,
                "probe": probe or {},
                "rights": {"license_spdx": license_spdx, "verification_status": verification_status, "permitted_uses": ["internal"]},
                "indexed_at": now_iso(),
            })
        except Exception as exc:
            errors.append({"path": str(path), "code": "INDEX_FAILED", "message": str(exc)})
    catalog = {
        "catalog_version": "0.1.0",
        "catalog_id": new_id("catalog"),
        "root": str(source_root),
        "created_at": now_iso(),
        "indexed_count": len(records),
        "skipped_count": max(0, len(files) - len(records)),
        "records": records,
        "errors": errors,
        "network": "disabled",
    }
    atomic_write_json(output, catalog)
    return catalog


def search_catalog(catalog: dict[str, Any], *, query: str = "", kind: str | None = None, verification_status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    query = query.strip().lower()
    results: list[dict[str, Any]] = []
    for record in catalog.get("records", []):
        if kind and record.get("kind") != kind:
            continue
        if verification_status and record.get("rights", {}).get("verification_status") != verification_status:
            continue
        # Search semantic catalog fields only. Absolute paths often contain the
        # product/runtime directory name and must not create accidental hits.
        haystack = " ".join(str(record.get(field, "")) for field in ("name", "relative_uri", "kind")).lower()
        if query and not (query in haystack or fnmatch.fnmatch(record.get("name", "").lower(), query)):
            continue
        results.append(record)
        if len(results) >= max(1, int(limit)):
            break
    return results
