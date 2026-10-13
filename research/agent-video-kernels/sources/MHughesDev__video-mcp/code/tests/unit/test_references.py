from __future__ import annotations

from pathlib import Path

import pytest

from mcp_editor.references import (
    add_reference,
    get_reference,
    list_references,
    load_references_manifest,
    remove_reference,
)


def _make_video(tmp_path: Path, name: str = "clip.mp4") -> Path:
    p = tmp_path / "data" / "input" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"fake")
    return p


def _make_audio(tmp_path: Path, name: str = "track.mp3") -> Path:
    p = tmp_path / "data" / "music" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"fake")
    return p


def _make_image(tmp_path: Path, name: str = "ref.jpg") -> Path:
    p = tmp_path / "data" / "references" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"fake")
    return p


def test_load_manifest_creates_empty_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    manifest = load_references_manifest()
    assert manifest.references == []


def test_add_reference_returns_ref_id(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_video(tmp_path)
    result = add_reference(str(p), tags=["color"], notes="great grade")
    assert result["ok"] is True
    assert len(result["ref_id"]) == 12


def test_add_reference_persists_to_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_video(tmp_path)
    add_reference(str(p), tags=[], notes="")
    manifest = load_references_manifest()
    assert len(manifest.references) == 1


def test_add_reference_infers_type_video(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_video(tmp_path)
    result = add_reference(str(p), tags=[], notes="")
    assert result["type"] == "video"


def test_add_reference_infers_type_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_audio(tmp_path)
    result = add_reference(str(p), tags=[], notes="")
    assert result["type"] == "audio"


def test_add_reference_infers_type_image(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_image(tmp_path)
    result = add_reference(str(p), tags=[], notes="")
    assert result["type"] == "image"


def test_add_reference_file_not_found_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        add_reference("/nonexistent/clip.mp4", tags=[], notes="")


def test_add_reference_duplicate_returns_already_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_video(tmp_path)
    add_reference(str(p), tags=[], notes="")
    result = add_reference(str(p), tags=[], notes="")
    assert result.get("note") == "already_exists"
    manifest = load_references_manifest()
    assert len(manifest.references) == 1


def test_list_references_returns_all(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    add_reference(str(_make_video(tmp_path, "a.mp4")), tags=["x"], notes="")
    add_reference(str(_make_audio(tmp_path, "b.mp3")), tags=["y"], notes="")
    result = list_references(tags=[])
    assert result["count"] == 2


def test_list_references_filters_by_single_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    add_reference(str(_make_video(tmp_path, "a.mp4")), tags=["color"], notes="")
    add_reference(str(_make_audio(tmp_path, "b.mp3")), tags=["pacing"], notes="")
    result = list_references(tags=["color"])
    assert result["count"] == 1


def test_list_references_filters_by_multiple_tags_and(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    add_reference(str(_make_video(tmp_path, "a.mp4")), tags=["color", "golden-hour"], notes="")
    add_reference(str(_make_audio(tmp_path, "b.mp3")), tags=["color"], notes="")
    result = list_references(tags=["color", "golden-hour"])
    assert result["count"] == 1


def test_list_references_empty_when_no_match(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    add_reference(str(_make_video(tmp_path)), tags=["color"], notes="")
    result = list_references(tags=["nonexistent"])
    assert result["count"] == 0


def test_get_reference_found(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_video(tmp_path)
    added = add_reference(str(p), tags=[], notes="")
    result = get_reference(added["ref_id"])
    assert result["ok"] is True
    assert result["reference"]["ref_id"] == added["ref_id"]


def test_get_reference_not_found_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    with pytest.raises(KeyError):
        get_reference("doesnotexist")


def test_remove_reference_removes_from_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_video(tmp_path)
    added = add_reference(str(p), tags=[], notes="")
    remove_reference(added["ref_id"])
    manifest = load_references_manifest()
    assert len(manifest.references) == 0


def test_remove_reference_deletes_doc_if_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_video(tmp_path)
    added = add_reference(str(p), tags=[], notes="")

    doc_path = tmp_path / "ref_doc.md"
    doc_path.write_text("hello")
    manifest = load_references_manifest()
    manifest.references[0].doc_path = str(doc_path)
    from mcp_editor.references import save_references_manifest
    save_references_manifest(manifest)

    remove_reference(added["ref_id"])
    assert not doc_path.exists()


def test_remove_reference_not_found_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    with pytest.raises(KeyError):
        remove_reference("doesnotexist")
