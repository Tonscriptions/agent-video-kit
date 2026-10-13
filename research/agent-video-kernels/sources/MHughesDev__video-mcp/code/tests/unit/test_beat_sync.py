from mcp_editor.beat_sync import apply_edit_plan, plan_beat_synced_edit, suggest_cut_points
from mcp_editor.projects import load_manifest, save_manifest
from mcp_editor.schemas import MediaProbe, MediaStream, Platform, ProjectManifest
from mcp_editor.workflow import edit_video_from_prompt


def video_probe(path):
    return MediaProbe(
        path=str(path),
        exists=True,
        ok=True,
        duration=30,
        streams=[
            MediaStream(index=0, codec_type="video", codec_name="h264", width=1920, height=1080),
            MediaStream(index=1, codec_type="audio", codec_name="aac"),
        ],
    )


def test_suggest_cut_points_uses_style_multiplier():
    result = suggest_cut_points(
        beat_times=[0, 0.5, 1.0, 1.5, 2.0],
        target_duration=2,
        style="medium",
    )

    assert result["ok"] is True
    assert result["beat_multiplier"] == 2
    assert result["cut_points"] == [0.0, 1.0, 2.0]


def test_suggest_cut_points_falls_back_to_tempo():
    result = suggest_cut_points(
        beat_times=[],
        target_duration=2,
        style="fast",
        tempo=120,
    )

    assert result["cut_points"] == [0.0, 0.5, 1.0, 1.5, 2.0]


def test_plan_and_apply_beat_synced_edit(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(workspace))
    source_a = tmp_path / "a.mp4"
    source_b = tmp_path / "b.mp4"
    source_a.write_bytes(b"")
    source_b.write_bytes(b"")
    manifest = ProjectManifest(
        name="demo",
        assets=[video_probe(source_a), video_probe(source_b)],
    )
    save_manifest(manifest)

    plan_result = plan_beat_synced_edit(
        project_id=manifest.project_id,
        platform=Platform.widescreen,
        target_duration=4,
        style="medium",
        beat_times=[0, 1, 2, 3, 4],
    )
    apply_result = apply_edit_plan(manifest.project_id, Platform.widescreen)
    saved = load_manifest(manifest.project_id)

    assert plan_result["ok"] is True
    assert len(plan_result["edit_plan"]["clips"]) == 2
    assert apply_result["ok"] is True
    assert apply_result["validation"]["duration"] == 4
    assert saved.timelines[Platform.widescreen.value].otio_path.endswith(".otio")


def test_plan_beat_synced_edit_reports_no_video_assets(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(workspace))
    manifest = ProjectManifest(name="empty")
    save_manifest(manifest)

    try:
        plan_beat_synced_edit(project_id=manifest.project_id)
    except Exception as exc:
        assert exc.issue.code == "no_video_assets"
    else:
        raise AssertionError("expected no_video_assets")


def test_edit_video_from_prompt_uses_beat_plan_when_music_exists(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(workspace))
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"")
    monkeypatch.setattr("mcp_editor.workflow.scan_assets", lambda input_dir, include_audio=False: [video_probe(source)])
    monkeypatch.setattr(
        "mcp_editor.workflow.analyze_beats",
        lambda music_path: {
            "ok": True,
            "path": str(music_path),
            "tempo": 120.0,
            "beat_count": 5,
            "beat_times": [0, 1, 2, 3, 4],
        },
    )

    result = edit_video_from_prompt(
        prompt="cut to the beat",
        input_dir=str(tmp_path),
        music_path=str(tmp_path / "track.mp3"),
        target_duration=4,
        render=False,
    )

    assert result["ok"] is True
    assert any(item["stage"] == "plan_beat_synced_edit" for item in result["events"])
    assert any(item["stage"] == "apply_edit_plan" for item in result["events"])
    assert result["timelines"][Platform.widescreen.value].endswith(".otio")
