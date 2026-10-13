import subprocess

from mcp_editor.inspection import (
    analyze_audio_metadata,
    analyze_video_metadata,
    detect_scenes,
    generate_thumbnails,
    inspect_project,
    scan_project_assets,
)
from mcp_editor.projects import load_manifest, save_manifest
from mcp_editor.schemas import MediaProbe, MediaStream, ProjectManifest


def video_probe(path="clip.mp4"):
    return MediaProbe(
        path=path,
        exists=True,
        ok=True,
        duration=12,
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        bit_rate=1000,
        streams=[
            MediaStream(
                index=0,
                codec_type="video",
                codec_name="h264",
                width=1920,
                height=1080,
                r_frame_rate="30000/1001",
            ),
            MediaStream(index=1, codec_type="audio", codec_name="aac"),
        ],
    )


def test_analyze_video_metadata_summarizes_primary_video(monkeypatch):
    monkeypatch.setattr("mcp_editor.inspection.probe_media", lambda path: video_probe(str(path)))

    result = analyze_video_metadata("clip.mp4")

    assert result["ok"] is True
    assert result["width"] == 1920
    assert result["height"] == 1080
    assert result["aspect_ratio"] == "16:9"
    assert round(result["fps"], 3) == 29.97
    assert result["has_audio"] is True


def test_analyze_audio_metadata_reports_no_audio(monkeypatch):
    probe = MediaProbe(
        path="silent.mp4",
        exists=True,
        ok=True,
        streams=[MediaStream(index=0, codec_type="video", width=1920, height=1080)],
    )
    monkeypatch.setattr("mcp_editor.inspection.probe_media", lambda path: probe)

    result = analyze_audio_metadata("silent.mp4")

    assert result["ok"] is False
    assert result["error"]["code"] == "no_audio_stream"


def test_scan_project_assets_returns_summary(monkeypatch):
    monkeypatch.setattr("mcp_editor.inspection.scan_assets", lambda root, include_audio=True: [video_probe("clip.mp4")])

    result = scan_project_assets("data/input")

    assert result["ok"] is True
    assert result["summary"]["asset_count"] == 1
    assert result["summary"]["video_count"] == 1


def test_detect_scenes_parses_ffmpeg_showinfo(monkeypatch):
    monkeypatch.setattr("mcp_editor.inspection.probe_media", lambda path: video_probe(str(path)))
    monkeypatch.setattr("mcp_editor.inspection.require_binary", lambda name: name)

    def fake_run(cmd, capture_output, text, check):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="",
            stderr="showinfo pts_time:0.10\nshowinfo pts_time:0.40\nshowinfo pts_time:1.10\n",
        )

    monkeypatch.setattr("mcp_editor.inspection.subprocess.run", fake_run)

    result = detect_scenes("clip.mp4", min_scene_gap=0.5)

    assert result["ok"] is True
    assert result["scene_times"] == [0.1, 1.1]


def test_generate_thumbnails_returns_created_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("mcp_editor.inspection.probe_media", lambda path: video_probe(str(path)))
    monkeypatch.setattr("mcp_editor.inspection.require_binary", lambda name: name)

    def fake_run(cmd, capture_output, text, check):
        output_path = cmd[-1]
        with open(output_path, "wb") as file:
            file.write(b"jpg")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("mcp_editor.inspection.subprocess.run", fake_run)

    result = generate_thumbnails("clip.mp4", output_directory=tmp_path, count=2)

    assert result["ok"] is True
    assert result["count"] == 2
    assert len(result["thumbnails"]) == 2


def test_inspect_project_summarizes_manifest(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(workspace))
    manifest = ProjectManifest(name="demo", assets=[video_probe("clip.mp4")])
    save_manifest(manifest)

    result = inspect_project(manifest.project_id)

    assert result["ok"] is True
    assert result["summary"]["usable_video_count"] == 1


def test_load_manifest_missing_does_not_create_project_dir(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(workspace))

    try:
        load_manifest("missing")
    except Exception:
        pass

    assert not (workspace / "data" / "projects" / "missing").exists()
