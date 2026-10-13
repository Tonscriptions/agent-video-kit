from mcp_editor.render import plan_render_timeline, render_manifest_summary, render_timeline
from mcp_editor.schemas import Platform, RenderManifest, TimelineClip, TimelinePlan


def timeline_with_missing_source():
    return TimelinePlan(
        project_id="demo",
        platform=Platform.vertical,
        clips=[
            TimelineClip(source="missing-a.mp4", start=1, duration=2, label="A"),
            TimelineClip(source="missing-b.mp4", start=0, duration=3, label="B"),
        ],
    )


def test_plan_render_timeline_dry_plan_does_not_probe_sources():
    plan = timeline_with_missing_source()

    manifest = plan_render_timeline(plan, render_profile="standard", validate_sources=False)

    assert manifest.platform == Platform.vertical
    assert manifest.dimensions == (1080, 1920)
    assert manifest.expected_duration == 5
    assert len(manifest.commands) == 3
    assert manifest.commands[0].stage == "render_segment_1"
    assert "-crf" in manifest.commands[0].command
    assert "23" in manifest.commands[0].command


def test_render_timeline_dry_run_returns_manifest_without_ffmpeg(monkeypatch, tmp_path):
    plan = timeline_with_missing_source()
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))

    result = render_timeline(plan, render_profile="preview", dry_run=True)

    assert isinstance(result, RenderManifest)
    assert result.dry_run is True
    assert result.output_path.endswith("demo_9x16.mp4")


def test_render_manifest_summary_is_agent_readable():
    manifest = plan_render_timeline(timeline_with_missing_source(), validate_sources=False)
    manifest.dry_run = True

    summary = render_manifest_summary(manifest)

    assert summary["ok"] is True
    assert summary["dry_run"] is True
    assert summary["command_count"] == 3
    assert summary["commands"][0]["stage"] == "render_segment_1"


def test_unknown_render_profile_is_rejected():
    try:
        plan_render_timeline(timeline_with_missing_source(), render_profile="cinema", validate_sources=False)
    except ValueError as exc:
        assert "unknown render_profile" in str(exc)
    else:
        raise AssertionError("expected ValueError")
