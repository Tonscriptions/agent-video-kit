from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import references_dir
from .media import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from .schemas import ReferenceAsset, ReferenceType, ReferencesManifest, posix_path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tiff", ".bmp"}

MANIFEST_FILENAME = "references.json"


def references_manifest_path() -> Path:
    return references_dir() / MANIFEST_FILENAME


def load_references_manifest() -> ReferencesManifest:
    path = references_manifest_path()
    if not path.exists():
        return ReferencesManifest()
    return ReferencesManifest.model_validate_json(path.read_text())


def save_references_manifest(manifest: ReferencesManifest) -> None:
    path = references_manifest_path()
    path.write_text(manifest.model_dump_json(indent=2))


def _ref_id_for(media_path: str) -> str:
    return hashlib.sha1(media_path.encode()).hexdigest()[:12]


def _infer_type(path: Path) -> ReferenceType:
    ext = path.suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return ReferenceType.video
    if ext in AUDIO_EXTENSIONS:
        return ReferenceType.audio
    return ReferenceType.image


def add_reference(path: str, tags: list[str], notes: str) -> dict:
    media_path = Path(path).expanduser().resolve()
    if not media_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ppath = posix_path(media_path)
    ref_id = _ref_id_for(ppath)
    ref_type = _infer_type(media_path)

    manifest = load_references_manifest()
    existing_ids = {r.ref_id for r in manifest.references}
    if ref_id in existing_ids:
        return {
            "ok": True,
            "ref_id": ref_id,
            "path": ppath,
            "type": ref_type.value,
            "tags": tags,
            "note": "already_exists",
        }

    asset = ReferenceAsset(
        ref_id=ref_id,
        path=ppath,
        type=ref_type,
        tags=tags,
        notes=notes,
    )
    manifest.references.append(asset)
    save_references_manifest(manifest)

    return {
        "ok": True,
        "ref_id": ref_id,
        "path": ppath,
        "type": ref_type.value,
        "tags": tags,
    }


def list_references(tags: list[str]) -> dict:
    manifest = load_references_manifest()
    results = manifest.references

    if tags:
        tag_set = set(tags)
        results = [r for r in results if tag_set.issubset(set(r.tags))]

    return {
        "ok": True,
        "references": [r.model_dump() for r in results],
        "count": len(results),
    }


def get_reference(ref_id: str) -> dict:
    manifest = load_references_manifest()
    for ref in manifest.references:
        if ref.ref_id == ref_id:
            return {"ok": True, "reference": ref.model_dump()}
    raise KeyError(f"Reference not found: {ref_id}")


def remove_reference(ref_id: str) -> dict:
    manifest = load_references_manifest()
    original_count = len(manifest.references)
    target = next((r for r in manifest.references if r.ref_id == ref_id), None)
    if target is None:
        raise KeyError(f"Reference not found: {ref_id}")

    if target.doc_path:
        doc = Path(target.doc_path)
        if doc.exists():
            doc.unlink()
        meta = doc.with_suffix(".meta.json") if doc.suffix == ".md" else Path(str(doc) + ".meta.json")
        if meta.exists():
            meta.unlink()

    manifest.references = [r for r in manifest.references if r.ref_id != ref_id]
    save_references_manifest(manifest)

    return {"ok": True, "ref_id": ref_id, "removed": original_count - len(manifest.references)}
