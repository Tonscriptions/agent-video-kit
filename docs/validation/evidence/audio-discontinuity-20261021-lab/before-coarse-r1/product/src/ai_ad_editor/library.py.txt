from __future__ import annotations

import fnmatch
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .captions import parse_caption_file
from .media import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, classify_path, ffmpeg_path, probe_media
from .utils import atomic_write_json, new_id, now_iso, sha256_bytes, sha256_file


LIBRARY_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | {".srt", ".vtt", ".ass", ".ssa", ".ttf", ".otf", ".ttc"}
LIBRARY_VERSION = "0.3.0"
SEMANTIC_INDEX_VERSION = "0.2.0"
INDEX_SIGNATURE_VERSION = "0.1.0"
VISUAL_HASH_VERSION = "ahash-v1"
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


def _file_signature(path: Path) -> dict[str, Any]:
    """Return the local stat signature used by incremental catalog refreshes.

    The signature deliberately contains no machine-specific absolute path.  An
    incremental refresh is valid only when the relative path, byte size and
    nanosecond mtime are unchanged.  A caller that needs stronger guarantees can
    omit ``--incremental`` and force a full content hash/probe pass.
    """
    stat = path.stat()
    return {
        "version": INDEX_SIGNATURE_VERSION,
        "bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _visual_hash(path: Path, *, at_seconds: float = 0.0, size: int = 16) -> str:
    """Compute a deterministic local average hash through FFmpeg rawvideo.

    This is intentionally a candidate-similarity signal, not content
    understanding.  A small grayscale frame is enough to catch resized or
    lightly re-encoded copies while avoiding Pillow/OpenCV/model dependencies.
    """
    if size < 4 or size > 64:
        raise ValueError("visual hash size must be between 4 and 64")
    completed = subprocess.run(
        [
            ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, float(at_seconds)):.3f}",
            "-i", str(path), "-frames:v", "1", "-vf",
            f"scale={size}:{size}:force_original_aspect_ratio=decrease,pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=black,format=gray",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
        timeout=60,
    )
    expected = size * size
    if completed.returncode != 0 or len(completed.stdout) < expected:
        message = completed.stderr.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(f"FFmpeg visual hash failed: {message}")
    pixels = completed.stdout[:expected]
    mean = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= mean)
    return f"{value:0{(expected + 3) // 4}x}"


def _visual_hash_bundle(path: Path, kind: str, probe: dict[str, Any], *, size: int = 16) -> dict[str, Any] | None:
    if kind not in {"video", "image"}:
        return None
    duration = max(0.0, float(probe.get("duration_seconds", 0.0) or 0.0))
    if kind == "image" or duration <= 1.0:
        sample_times = [0.0]
    else:
        sample_times = [0.0, round(duration / 2.0, 3), round(max(0.0, duration - 0.1), 3)]
    samples = []
    for at_seconds in sorted(set(sample_times)):
        samples.append({"at_seconds": at_seconds, "hash": _visual_hash(path, at_seconds=at_seconds, size=size)})
    return {"version": VISUAL_HASH_VERSION, "size": size, "source": "ffmpeg-local", "samples": samples}


def _reusable_record(
    previous_by_relative: dict[str, dict[str, Any]],
    relative_uri: str,
    path: Path,
    sidecar_signature: dict[str, Any] | None,
    *,
    require_visual_hash: bool = False,
) -> dict[str, Any] | None:
    previous = previous_by_relative.get(relative_uri.casefold())
    if not isinstance(previous, dict):
        return None
    signature = previous.get("index_signature")
    if not isinstance(signature, dict) or signature.get("file") != _file_signature(path):
        return None
    previous_sidecar = signature.get("sidecar")
    if previous_sidecar != sidecar_signature:
        return None
    if require_visual_hash:
        semantic = previous.get("semantic") if isinstance(previous.get("semantic"), dict) else {}
        if not isinstance(semantic.get("visual_hash"), dict):
            return None
    return previous


def index_directory(
    source_root: Path,
    output: Path,
    *,
    max_files: int = 5000,
    license_spdx: str = "LicenseRef-UNVERIFIED",
    verification_status: str = "unverified",
    previous_catalog: dict[str, Any] | None = None,
    incremental: bool = False,
    include_visual_hash: bool = False,
) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve()
    files = [path for path in source_root.rglob("*") if path.is_file() and path.suffix.lower() in LIBRARY_EXTENSIONS]
    files.sort(key=lambda path: str(path).lower())
    subtitle_by_key: dict[str, dict[str, Any]] = {}
    for path in files:
        if path.suffix.lower() not in {".srt", ".vtt", ".ass", ".ssa"}:
            continue
        try:
            subtitle_by_key[_subtitle_key(path, source_root)] = {"text": _subtitle_text(path), "signature": _file_signature(path)}
        except OSError:
            subtitle_by_key[_subtitle_key(path, source_root)] = {"text": "", "signature": None}
    previous_by_relative = {
        str(record.get("relative_uri", "")).casefold(): record
        for record in (previous_catalog or {}).get("records", [])
        if isinstance(record, dict) and record.get("relative_uri")
    }
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    reused_count = 0
    reindexed_count = 0
    visual_hash_count = 0
    for path in files[: max(0, int(max_files))]:
        try:
            relative_uri = str(path.relative_to(source_root)).replace("\\", "/")
            suffix = path.suffix.lower()
            sidecar = subtitle_by_key.get(_subtitle_key(path, source_root)) if suffix in (VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS) else None
            sidecar_text = str(sidecar.get("text", "")) if isinstance(sidecar, dict) else ""
            sidecar_signature = sidecar.get("signature") if isinstance(sidecar, dict) else None
            reusable = _reusable_record(
                previous_by_relative,
                relative_uri,
                path,
                sidecar_signature,
                require_visual_hash=include_visual_hash and suffix in (VIDEO_EXTENSIONS | IMAGE_EXTENSIONS),
            ) if incremental else None
            if reusable is not None:
                record = dict(reusable)
                record["uri"] = str(path)
                record["relative_uri"] = relative_uri
                record["rights"] = {"license_spdx": license_spdx, "verification_status": verification_status, "permitted_uses": ["internal"]}
                records.append(record)
                reused_count += 1
                if isinstance(record.get("semantic"), dict) and record["semantic"].get("visual_hash"):
                    visual_hash_count += 1
                continue
            probe = probe_media(path) if suffix in (VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | {".srt", ".vtt", ".ass", ".ssa"}) else {}
            kind = _kind(path, probe)
            if kind == "subtitle":
                sidecar_text = _subtitle_text(path)
            digest = sha256_file(path)
            semantic = _semantic_record(name=path.name, relative_uri=relative_uri, kind=kind, probe=probe, subtitle_text=sidecar_text)
            if include_visual_hash:
                try:
                    visual = _visual_hash_bundle(path, kind, probe)
                    if visual:
                        semantic["visual_hash"] = visual
                        visual_hash_count += 1
                except Exception as exc:
                    warnings.append({"path": str(path), "code": "VISUAL_HASH_FAILED", "message": str(exc)})
            records.append({
                "id": f"lib_{digest[:16]}_{sha256_bytes(relative_uri.encode('utf-8'))[:8]}",
                "name": path.name,
                "kind": kind,
                "uri": str(path),
                "relative_uri": relative_uri,
                "sha256": f"sha256:{digest}",
                "bytes": path.stat().st_size,
                "probe": probe,
                "semantic": semantic,
                "rights": {"license_spdx": license_spdx, "verification_status": verification_status, "permitted_uses": ["internal"]},
                "index_signature": {"file": _file_signature(path), "sidecar": sidecar_signature},
                "indexed_at": now_iso(),
            })
            reindexed_count += 1
        except Exception as exc:
            errors.append({"path": str(path), "code": "INDEX_FAILED", "message": str(exc)})
    removed_count = 0
    if incremental:
        indexed_keys = {str(record.get("relative_uri", "")).casefold() for record in records}
        removed_count = sum(1 for key in previous_by_relative if key not in indexed_keys)
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
        "warnings": warnings,
        "duplicate_groups": len(duplicate_groups({"records": records})),
        "network": "disabled",
        "semantic_search": {"source": "deterministic-local", "model": None, "vector_index": False, "visual_hash": include_visual_hash or visual_hash_count > 0},
        "index_refresh": {
            "mode": "incremental" if incremental else "full",
            "signature_version": INDEX_SIGNATURE_VERSION,
            "previous_catalog_id": (previous_catalog or {}).get("catalog_id") if incremental else None,
            "reused_count": reused_count,
            "reindexed_count": reindexed_count,
            "removed_count": removed_count,
            "visual_hash_count": visual_hash_count,
        },
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


def _hash_distance(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except (TypeError, ValueError):
        return 10**9


def visual_similarity_groups(catalog: dict[str, Any], *, max_distance: int = 12) -> list[dict[str, Any]]:
    """Return candidate groups from optional FFmpeg average-hash samples.

    Similarity is deliberately conservative in its naming: matching one sample
    can indicate a reused opening frame, a still image in a video, or a resized
    transcode.  The result is a review queue and never a rights or publish
    decision.
    """
    threshold = max(0, int(max_distance))
    candidates: list[dict[str, Any]] = []
    for record in catalog.get("records", []):
        if not isinstance(record, dict):
            continue
        semantic = record.get("semantic") if isinstance(record.get("semantic"), dict) else {}
        visual = semantic.get("visual_hash") if isinstance(semantic, dict) else None
        samples = visual.get("samples", []) if isinstance(visual, dict) else []
        hashes = [str(sample.get("hash", "")) for sample in samples if isinstance(sample, dict) and sample.get("hash")]
        if hashes:
            candidates.append({"record": record, "hashes": hashes})
    if len(candidates) < 2:
        return []
    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    pair_distances: dict[tuple[int, int], int] = {}
    for left in range(len(candidates)):
        for right in range(left + 1, len(candidates)):
            distance = min(_hash_distance(first, second) for first in candidates[left]["hashes"] for second in candidates[right]["hashes"])
            if distance <= threshold:
                pair_distances[(left, right)] = distance
                union(left, right)
    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(candidates)):
        grouped[find(index)].append(index)
    result: list[dict[str, Any]] = []
    for indices in grouped.values():
        if len(indices) < 2:
            continue
        distances = [distance for (left, right), distance in pair_distances.items() if left in indices and right in indices]
        records = [candidates[index]["record"] for index in indices]
        records.sort(key=lambda item: _normalize_text(item.get("relative_uri", item.get("name", ""))))
        result.append({
            "method": VISUAL_HASH_VERSION,
            "max_distance": threshold,
            "distance": min(distances) if distances else None,
            "count": len(records),
            "record_ids": [str(record.get("id", "")) for record in records],
            "relative_uris": [str(record.get("relative_uri", "")) for record in records],
        })
    result.sort(key=lambda item: (-int(item["count"]), str(item["relative_uris"])))
    return result
