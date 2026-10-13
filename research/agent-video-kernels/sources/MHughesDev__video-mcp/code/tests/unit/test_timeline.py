from pathlib import Path

from mcp_editor.schemas import Platform, TimelinePlan
from mcp_editor.timeline import (
    add_clip,
    add_transition,
    export_otio,
    make_simple_timeline_plan,
    move_clip,
    split_clip,
    timeline_duration,
    trim_clip,
    validate_timeline,
)


def test_make_simple_timeline_plan_limits_target_duration(tmp_path):
    clip_a = tmp_path / "a.mp4"
    clip_b = tmp_path / "b.mp4"
    clip_a.write_bytes(b"")
    clip_b.write_bytes(b"")

    plan = make_simple_timeline_plan(
        project_id="demo",
        asset_paths=[str(clip_a), str(clip_b)],
        platform=Platform.square,
        target_duration=6,
        default_clip_duration=4,
    )

    assert [clip.duration for clip in plan.clips] == [4, 2]
    assert plan.platform == Platform.square


def test_export_otio_writes_file(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"")
    plan = make_simple_timeline_plan(
        project_id="demo",
        asset_paths=[str(clip)],
        target_duration=4,
    )
    output = export_otio(plan, tmp_path / "timeline.otio")

    assert output.exists()
    assert "clip-1" in output.read_text(encoding="utf-8")


def test_timeline_edit_operations_update_clip_order_and_duration(tmp_path):
    clip_a = tmp_path / "a.mp4"
    clip_b = tmp_path / "b.mp4"
    clip_a.write_bytes(b"")
    clip_b.write_bytes(b"")
    plan = TimelinePlan(project_id="demo", platform=Platform.widescreen, clips=[])

    add_clip(plan, clip_a, duration=5, label="A")
    add_clip(plan, clip_b, duration=3, label="B")
    trim_clip(plan, index=0, start=1, duration=4)
    split_clip(plan, index=0, split_at=2)
    move_clip(plan, from_index=2, to_index=0)

    assert [clip.label for clip in plan.clips] == ["B", "A", "A part 2"]
    assert timeline_duration(plan) == 7


def test_add_transition_and_export_otio(tmp_path):
    clip_a = tmp_path / "a.mp4"
    clip_b = tmp_path / "b.mp4"
    clip_a.write_bytes(b"")
    clip_b.write_bytes(b"")
    plan = make_simple_timeline_plan("demo", [str(clip_a), str(clip_b)], target_duration=8)

    add_transition(
        plan,
        from_clip_id=plan.clips[0].clip_id,
        to_clip_id=plan.clips[1].clip_id,
        transition_type="crossfade",
        duration=0.5,
    )
    validation = validate_timeline(plan)
    output = export_otio(plan, tmp_path / "timeline.otio")

    assert validation["ok"] is True
    assert validation["transition_count"] == 1
    assert "crossfade" in output.read_text(encoding="utf-8")


def test_validate_timeline_reports_issues_and_warnings(tmp_path):
    missing = tmp_path / "missing.mp4"
    plan = TimelinePlan(project_id="demo", clips=[])
    add_clip(plan, missing, duration=2)
    plan.clips[0].duration = -1

    validation = validate_timeline(plan)

    assert validation["ok"] is False
    assert any(issue["code"] == "non_positive_clip_duration" for issue in validation["issues"])
    assert any(warning["code"] == "missing_media" for warning in validation["warnings"])
