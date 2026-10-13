from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_editor.media_docs import auto_generate_doc


def _make_file(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b"fake")
    return p


def test_auto_generate_doc_video_returns_keyframes(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_file(tmp_path, "clip.mp4")

    mock_meta = {
        "ok": True,
        "duration_seconds": 45.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "aspect_ratio": "16:9",
        "color_space": "yuv420p",
        "has_audio": True,
    }
    mock_thumbs = {
        "ok": True,
        "thumbnails": [str(tmp_path / f"thumb_{i}.jpg") for i in range(5)],
    }

    with patch("mcp_editor.media_docs.analyze_video_metadata", return_value=mock_meta), \
         patch("mcp_editor.media_docs.generate_thumbnails", return_value=mock_thumbs):
        result = auto_generate_doc(str(p))

    assert result["ok"] is True
    assert result["type"] == "video"
    assert len(result["keyframe_paths"]) == 5
    assert result["prefilled"]["technical"]["resolution"] == "1920x1080"
    assert result["prefilled"]["technical"]["fps"] == 30.0
    assert "shot_spatial" in result["remaining_sections"]


def test_auto_generate_doc_audio_returns_structure(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_file(tmp_path, "track.mp3")

    mock_meta = {
        "ok": True,
        "duration_seconds": 202.0,
        "sample_rate": 44100,
        "bit_depth": 16,
        "channels": "stereo",
    }
    mock_beats = {
        "ok": True,
        "tempo": 94.3,
        "beat_times": [0.5, 1.1, 1.7, 2.3],
    }

    with patch("mcp_editor.media_docs.analyze_audio_metadata", return_value=mock_meta), \
         patch("mcp_editor.media_docs.analyze_beats", return_value=mock_beats):
        result = auto_generate_doc(str(p))

    assert result["ok"] is True
    assert result["type"] == "audio"
    assert result["prefilled"]["technical"]["bpm"] == 94.3
    assert result["prefilled"]["technical"]["channels"] == "stereo"
    assert len(result["prefilled"]["structure"]["sections"]) == 1
    assert len(result["prefilled"]["edit_utility"]["sync_opportunities"]) == 4


def test_auto_generate_doc_image_returns_path(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    p = _make_file(tmp_path, "photo.jpg")

    mock_img = MagicMock()
    mock_img.size = (4000, 2667)
    mock_img.mode = "RGB"
    mock_img.__enter__ = MagicMock(return_value=mock_img)
    mock_img.__exit__ = MagicMock(return_value=False)

    with patch("mcp_editor.media_docs.Image.open", return_value=mock_img):
        result = auto_generate_doc(str(p))

    assert result["ok"] is True
    assert result["type"] == "image"
    assert result["prefilled"]["technical"]["color_space"] == "RGB"
    assert result["prefilled"]["identity"]["resolution"] == "4000x2667"
    assert str(p) in result["keyframe_paths"]


def test_auto_generate_doc_unsupported_extension_raises(tmp_path):
    p = _make_file(tmp_path, "data.csv")
    with pytest.raises(ValueError, match="Unsupported file extension"):
        auto_generate_doc(str(p))


def test_auto_generate_doc_file_not_found_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        auto_generate_doc(str(tmp_path / "nonexistent.mp4"))
