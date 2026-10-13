from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_editor.sourcing import (
    _destination_dir,
    _is_direct_file_url,
    download_asset,
)


def test_destination_dir_input(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    d = _destination_dir("input")
    assert d.exists()
    assert d.name == "input"


def test_destination_dir_music(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    d = _destination_dir("music")
    assert d.name == "music"


def test_destination_dir_references(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    d = _destination_dir("references")
    assert d.name == "references"


def test_destination_dir_invalid_raises():
    with pytest.raises(ValueError, match="Invalid destination"):
        _destination_dir("nowhere")


def test_is_direct_file_url_mp4():
    assert _is_direct_file_url("https://example.com/video.mp4") is True


def test_is_direct_file_url_mp3():
    assert _is_direct_file_url("https://example.com/audio.mp3") is True


def test_is_direct_file_url_jpg():
    assert _is_direct_file_url("https://example.com/photo.jpg") is True


def test_is_direct_file_url_youtube_not_direct():
    assert _is_direct_file_url("https://www.youtube.com/watch?v=abc123") is False


def test_is_direct_file_url_with_query_params():
    assert _is_direct_file_url("https://cdn.example.com/clip.mp4?token=xyz") is True


def test_download_direct_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"Content-Type": "video/mp4"}
    mock_response.iter_content = MagicMock(return_value=[b"fake_video_data"])
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("mcp_editor.sourcing.requests.get", return_value=mock_response):
        result = download_asset(
            url="https://example.com/clip.mp4",
            destination="input",
            filename="clip",
        )

    assert result["ok"] is True
    assert result["destination"] == "input"
    assert Path(result["path"]).exists()


def test_download_ytdlp_calls_subprocess(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))

    dest = tmp_path / "data" / "input"
    dest.mkdir(parents=True, exist_ok=True)
    fake_output = dest / "myvideo.mp4"
    fake_output.write_bytes(b"fake")

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("mcp_editor.sourcing.subprocess.run", return_value=mock_result) as mock_run:
        result = download_asset(
            url="https://www.youtube.com/watch?v=abc123",
            destination="input",
            filename="myvideo",
        )

    assert mock_run.called
    cmd = mock_run.call_args[0][0]
    assert "yt-dlp" in cmd
    assert result["ok"] is True


def test_download_asset_invalid_destination_returns_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    with pytest.raises(ValueError):
        download_asset(url="https://example.com/x.mp4", destination="bad")
