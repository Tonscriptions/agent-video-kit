from __future__ import annotations

import fnmatch
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .captions import parse_caption_file
from .media import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, classify_path, probe_media
from .utils import atomic_write_json, new_id, now_iso, sha256_bytes, sha256_file


LIBRARY_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | {".srt", ".vtt", ".ass", ".ssa", ".ttf", ".otf", ".ttc"}
LIBRARY_VERSION = "0.2.0"
SEMANTIC_INDEX_VERSION = "0.1.0"
_TOKEN_RE = re.compile(r"[0-9A-Za-z_]+|[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_WHITESPACE_RE = re.compile(r"\s+")


def _kind(path: Path, probe: dict[str, Any] | None) -> str:
    if path.suffix.lower() in {".srt", ".vtt", ".ass", ".ssa"}:
        return "subtitle"
    if path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
        return "font"
    return classify_path(path, probe)


def _normalize_text(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", str(value or "")).casefold()).strip()


def _tokens(value: Any) -> list[str]:
    """Return stable ASCII/CJK tokens without network or model dependencies.

    Latin words remain whole tokens. CJK characters are also emitted one by one
    so a query can find a Chinese term inside a filename or subtitle sentence.
    The full normalized text is retained separately for phrase matching.
    """
    normalized = _normalize_text(value)
    return sorted(set(_TOKEN_RE.findall(normalized)))


def _subtitle_text(path: Path) -> str:
    try:
        cues = parse_caption_file(path)
    except Exception:
        return ""
    return " ".join(str(cue.get("text", "")).strip() for cue in cues if str(cue.get("text", "")).strip())


def _subtitle_key(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root)
    return str(relative.with_suffix("")).replace("\\", "/").casefold()


def _media_facets(kind: str, probe: dict[str, Any], *, subtitle_text: str = "") -> dict[str, Any]:
    video = probe.get("video", {}) if isinstance(probe, dict) else {}
    streams = probe.get("streams", []) if isinstance(probe, dict) else []
    has_video = kind in {"video", "image"} or any(item.get("codec_type") == "video" for item in streams if isinstance(item, dict))
    has_audio = kind == "audio" or any(item.get("codec_type") == "audio" for item in streams if isinstance(item, dict))
    return {
        "kind": kind,
        "duration_seconds": round(float(probe.get("duration_seconds", 0.0) or 0.0), 3),
        "width": int(video.get("width", 0) or 0),
        "height": int(video.get("height", 0) or 0),
        "fps": str(video.get("fps") or ""),
        "has_video": bool(has_video),
        "has_audio": bool(has_audio),
        "format": str(probe.get("format") or ""),
        "subtitle_text": subtitle_text[:16000],
    }


def _semantic_record(*, name: str, relative_uri: str, kind: str, probe: dict[str, Any], subtitle_text: str = "") -> dict[str, Any]:
    text = " ".join(part for part in (name, relative_uri, kind, subtitle_text) if part)
    return {
        "version": SEMANTIC_INDEX_VERSION,
        "source": "deterministic-local",
        "text": _normalize_text(text)[:20000],
        "tokens": _tokens(text),
        "facets": _media_facets(kind, probe, subtitle_text=subtitle_text),
        "model": None,
    }


def index_directory(source_root: Path, output: Path, *, max_files: int = 5000, license_spdx: str = "LicenseRef-UNVERIFIED", verification_status: str = "unverified") -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    files = [path for path in source_root.rglob("*") if path.is_file() and path.suffix.lower() in LIBRARY_EXTENSIONS]
    files.sort(key=lambda path: str(path).lower())
    subtitle_by_key = {
        _subtitle_key(path, source_root): _subtitle_text(path)
        for path in files
        if path.suffix.lower() in {".srt", ".vtt", ".ass", ".ssa"}
    }
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for path in files[: max(0, int(max_files))]:
        try:
            probe = probe_media(path) if path.suffix.lower() in (VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | {".srt", ".vtt", ".ass", ".ssa"}) else {}
            kind = _kind(path, probe)
            relative_uri = str(path.relative_to(source_root)).replace("\\", "/")
            sidecar_text = subtitle_by_key.get(_subtitle_key(path, source_root), "") if kind in {"video", "audio", "image"} else _subtitle_text(path)
            digest = sha256_file(path)
            records.append({
                "id": f"lib_{digest[:16]}_{sha256_bytes(relative_uri.encode('utf-8'))[:8]}",
                "name": path.name,
                "kind": kind,
                "uri": str(path),
                "relative_uri": relative_uri,
                "sha256": f"sha256:{digest}",
                "bytes": path.stat().st_size,
                "probe": probe,
                "semantic": _semantic_record(name=path.name, relative_uri=relative_uri, kind=kind, probe=probe, subtitle_text=sidecar_text),
                "rights": {"license_spdx": license_spdx, "verification_status": verification_status, "permitted_uses": ["internal"]},
                "indexed_at": now_iso(),
            })
        except Exception as exc:
            errors.append({"path": str(path), "code": "INDEX_FAILED", "message": str(exc)})
    catalog = {
        "catalog_version": LIBRARY_VERSION,
        "semantic_index_version": SEMANTIC_INDEX_VERSION,
        "catalog_id": new_id("catalog"),
        "root": str(source_root),
        "created_at": now_iso(),
        "indexed_count": len(records),
        "skipped_count": max(0, len(files) - len(records)),
        "records": records,
        "errors": errors,
        "duplicate_groups": len(duplicate_groups({"records": records})),
        "network": "disabled",
        "semantic_search": {"source": "deterministic-local", "model": None, "vector_index": False},
    }
    atomic_write_json(output, catalog)
    return catalog


def search_catalog(
    catalog: dict[str, Any],
    *,
    query: str = "",
    kind: str | None = None,
    verification_status: str | None = None,
    min_duration: float | None = None,
    max_duration: float | None = None,
    min_width: int | None = None,
    min_height: int | None = None,
    has_audio: bool | None = None,
    duplicate_only: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = _normalize_text(query)
    query_tokens = _tokens(query)
    records = [record for record in catalog.get("records", []) if isinstance(record, dict)]
    digest_counts = Counter(str(record.get("sha256", "")) for record in records)
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for record in catalog.get("records", []):
        if not isinstance(record, dict):
            continue
        if kind and record.get("kind") != kind:
            continue
        if verification_status and record.get("rights", {}).get("verification_status") != verification_status:
            continue
        facets = record.get("semantic", {}).get("facets", {}) if isinstance(record.get("semantic"), dict) else {}
        duration = float(facets.get("duration_seconds", record.get("probe", {}).get("duration_seconds", 0.0)) or 0.0)
        width = int(facets.get("width", record.get("probe", {}).get("video", {}).get("width", 0)) or 0)
        height = int(facets.get("height", record.get("probe", {}).get("video", {}).get("height", 0)) or 0)
        record_has_audio = bool(facets.get("has_audio"))
        if min_duration is not None and duration < float(min_duration):
            continue
        if max_duration is not None and duration > float(max_duration):
            continue
        if min_width is not None and width < int(min_width):
            continue
        if min_height is not None and height < int(min_height):
            continue
        if has_audio is not None and record_has_audio != has_audio:
            continue
        if duplicate_only and digest_counts.get(str(record.get("sha256", "")), 0) < 2:
            continue
        semantic = record.get("semantic", {}) if isinstance(record.get("semantic"), dict) else {}
        haystack = _normalize_text(semantic.get("text") or " ".join(str(record.get(field, "")) for field in ("name", "relative_uri", "kind")))
        tokens = set(semantic.get("tokens", [])) or set(_tokens(haystack))
        if query:
            if not (query in haystack or fnmatch.fnmatch(_normalize_text(record.get("name", "")), query) or all(term in tokens or term in haystack for term in query_tokens)):
                continue
        score = 0.0
        if query:
            if query == _normalize_text(record.get("name", "")):
                score += 12.0
            if query in _normalize_text(record.get("name", "")):
                score += 6.0
            if query in haystack:
                score += 4.0
            score += sum(3.0 if term in tokens else 1.0 for term in query_tokens)
        ranked.append((score, _normalize_text(record.get("relative_uri", record.get("name", ""))), record))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [record for _, _, record in ranked[: max(1, int(limit))]]


def duplicate_groups(catalog: dict[str, Any], *, include_unique: bool = False) -> list[dict[str, Any]]:
    """Group exact byte-identical assets by content hash."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in catalog.get("records", []):
        if not isinstance(record, dict):
            continue
        digest = str(record.get("sha256", ""))
        if digest:
            groups[digest].append(record)
    result: list[dict[str, Any]] = []
    for digest, records in groups.items():
        if len(records) < 2 and not include_unique:
            continue
        result.append({
            "sha256": digest,
            "count": len(records),
            "bytes": max(int(record.get("bytes", 0) or 0) for record in records),
            "record_ids": [str(record.get("id", "")) for record in records],
            "relative_uris": [str(record.get("relative_uri", "")) for record in records],
        })
    result.sort(key=lambda item: (-int(item["count"]), item["sha256"]))
    return result
