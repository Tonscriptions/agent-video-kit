"""Integration tests for the full edit workflow.

These tests run the complete pipeline end-to-end using monkeypatched
FFmpeg/ffprobe binaries so no real media is required.  They verify that
the workflow correctly wires together: project creation → timeline build →
grading → render → OTIO export → validation.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import subprocess

import pytest

from mcp_editor.projects import save_manifest, load_manifest
from mcp_editor.schemas import (
    MediaProbe,
    MediaStream,
    Platform,
    ProjectManifest,
    TimelineClip,
    TimelinePlan,
)
from mcp_editor.workflow import (
    build_timeline_for_project,
    create_project,
    edit_video_from_prompt,
    get_workflow_status,
    render_and_validate_project,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """Set up a minimal workspace with a fake video asset."""
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    input_dir = tmp_path / "data" / "input"
    input_dir.mkdir(parents=True)
    fake_video = input_dir / "clip.mp4"
    fake_video.write_bytes(b"\x00" * 1024)  # non-empty placeholder
    return tmp_path, str(input_dir)


def _good_probe(path: str | Path) -> MediaProbe:
    return MediaProbe(
        path=str(path),
        exists=True,
        ok=True,
        duration=10.0,
        streams=[
            MediaStream(index=0, codec_type="video", width=1920, height=1080, r_frame_rate="30/1"),
            MediaStream(index=1, codec_type="audio", codec_name="aac"),
        ],
    )


def _patch_ffmpeg(monkeypatch, workspace_root: Path):
    """Patch FFmpeg/ffprobe so the pipeline runs without real binaries."""
    monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
    monkeypatch.setattr("mcp_editor.render.probe_media", _good_probe)
    monkeypatch.setattr("mcp_editor.validation.probe_media", _good_probe)
    monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (False, "no ffmpeg"))
    # require_binary is imported directly into render.py so patch it there
    monkeypatch.setattr("mcp_editor.render.require_binary", lambda b: b)

    def fake_execute(manifest):
        out = Path(manifest.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00" * 512)
        timing = [{"stage": c.stage, "attempt": 1, "elapsed_s": 0.0, "ok": True} for c in manifest.commands]
        return out, timing

    monkeypatch.setattr("mcp_editor.render.execute_render_manifest", fake_execute)


# ── create_project ────────────────────────────────────────────────────────────


class TestCreateProject:
    def test_creates_manifest_on_disk(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("my-film", input_dir=input_dir)
        assert (root / "data" / "projects" / m.project_id / "manifest.json").exists()

    def test_scans_assets(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("my-film", input_dir=input_dir)
        assert len(m.assets) == 1

    def test_deterministic_id_same_on_rerun(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m1 = create_project("stable-name", input_dir=input_dir)
        m2 = create_project("stable-name", input_dir=input_dir)
        assert m1.project_id == m2.project_id

    def test_different_name_different_id(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m1 = create_project("alpha", input_dir=input_dir)
        m2 = create_project("beta", input_dir=input_dir)
        assert m1.project_id != m2.project_id


# ── build_timeline_for_project ────────────────────────────────────────────────


class TestBuildTimeline:
    def test_creates_otio_file(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("film", input_dir=input_dir)
        m = build_timeline_for_project(m, Platform.widescreen, target_duration=8.0)
        otio_path = m.timelines["16:9"].otio_path
        assert otio_path is not None
        assert Path(otio_path).exists()

    def test_timeline_has_clips(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("film", input_dir=input_dir)
        m = build_timeline_for_project(m, Platform.widescreen, target_duration=8.0)
        assert len(m.timelines["16:9"].clips) > 0

    def test_otio_path_stored_in_manifest(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("film", input_dir=input_dir)
        m = build_timeline_for_project(m, Platform.widescreen)
        reloaded = load_manifest(m.project_id)
        assert reloaded.timelines["16:9"].otio_path is not None


# ── render_and_validate_project ───────────────────────────────────────────────


class TestRenderAndValidate:
    def test_dry_run_produces_output_entry(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("film", input_dir=input_dir)
        m = build_timeline_for_project(m, Platform.widescreen)
        m = render_and_validate_project(m, Platform.widescreen, dry_run=True)
        assert "16:9" in m.outputs
        assert m.outputs["16:9"].validation["dry_run"] is True

    def test_live_render_creates_output_entry(self, workspace, monkeypatch):
        root, input_dir = workspace
        _patch_ffmpeg(monkeypatch, root)
        m = create_project("film", input_dir=input_dir)
        m = build_timeline_for_project(m, Platform.widescreen)
        m = render_and_validate_project(m, Platform.widescreen, dry_run=False)
        assert "16:9" in m.outputs

    def test_output_persisted_to_manifest(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("film", input_dir=input_dir)
        m = build_timeline_for_project(m, Platform.widescreen)
        m = render_and_validate_project(m, Platform.widescreen, dry_run=True)
        reloaded = load_manifest(m.project_id)
        assert "16:9" in reloaded.outputs


# ── get_workflow_status ───────────────────────────────────────────────────────


class TestWorkflowStatusIntegration:
    def test_fresh_project_shows_scan_next(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("film", input_dir=input_dir)
        status = get_workflow_status(m.project_id)
        assert status["stages"]["project_created"] is True
        assert status["stages"]["assets_scanned"] is True  # scan happened in create_project
        assert status["stages"]["timelines_built"] is False

    def test_after_timeline_build_shows_render_next(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("film", input_dir=input_dir)
        m = build_timeline_for_project(m, Platform.widescreen)
        status = get_workflow_status(m.project_id)
        assert status["stages"]["timelines_built"] is True
        assert status["stages"]["otio_exported"] is True
        assert status["next_step"] == "render_all_variants"

    def test_after_dry_render_shows_complete(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        m = create_project("film", input_dir=input_dir)
        m = build_timeline_for_project(m, Platform.widescreen)
        m = render_and_validate_project(m, Platform.widescreen, dry_run=True)
        status = get_workflow_status(m.project_id)
        assert status["stages"]["rendered"] is True


# ── edit_video_from_prompt end-to-end ─────────────────────────────────────────


class TestEditVideoFromPromptIntegration:
    def test_dry_run_completes_without_error(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        result = edit_video_from_prompt(
            prompt="cinematic trailer edit",
            project_name="integration-test",
            input_dir=input_dir,
            platforms=[Platform.widescreen],
            target_duration=8.0,
            dry_run=True,
        )
        assert result["ok"] is True
        assert result["inferred_grade"] == "cinematic"
        assert result["inferred_style"] == "trailer"

    def test_inferred_grade_applied_to_clips(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        result = edit_video_from_prompt(
            prompt="warm golden sunset mood",
            project_name="grade-test",
            input_dir=input_dir,
            platforms=[Platform.widescreen],
            target_duration=8.0,
            dry_run=True,
        )
        assert result["inferred_grade"] == "warm"
        manifest = load_manifest(result["project_id"])
        plan = manifest.timelines["16:9"]
        graded = [c for c in plan.clips if any(e.effect_type == "grade" for e in c.effects)]
        assert len(graded) == len(plan.clips)

    def test_events_trace_contains_key_stages(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        result = edit_video_from_prompt(
            prompt="quick social reel",
            project_name="events-test",
            input_dir=input_dir,
            platforms=[Platform.widescreen],
            target_duration=8.0,
            dry_run=True,
        )
        stages = {e["stage"] for e in result["events"]}
        assert "create_project" in stages
        assert "create_timeline" in stages
        assert "render_project" in stages

    def test_no_prompt_grade_match_skips_grading(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        result = edit_video_from_prompt(
            prompt="edit my clips",
            project_name="no-grade-test",
            input_dir=input_dir,
            platforms=[Platform.widescreen],
            target_duration=8.0,
            dry_run=True,
        )
        assert result["inferred_grade"] is None
        manifest = load_manifest(result["project_id"])
        plan = manifest.timelines["16:9"]
        graded = [c for c in plan.clips if any(e.effect_type == "grade" for e in c.effects)]
        assert len(graded) == 0

    def test_explicit_style_override(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        result = edit_video_from_prompt(
            prompt="edit my video",
            project_name="style-override",
            input_dir=input_dir,
            style="fast",
            grade="vivid",
            platforms=[Platform.widescreen],
            target_duration=8.0,
            dry_run=True,
        )
        assert result["inferred_style"] == "fast"
        assert result["inferred_grade"] == "vivid"

    def test_multi_platform_produces_all_timelines(self, workspace, monkeypatch):
        root, input_dir = workspace
        monkeypatch.setattr("mcp_editor.media.probe_media", _good_probe)
        result = edit_video_from_prompt(
            prompt="social reel",
            project_name="multi-platform",
            input_dir=input_dir,
            platforms=[Platform.widescreen, Platform.vertical],
            target_duration=8.0,
            dry_run=True,
        )
        assert "16:9" in result["timelines"]
        assert "9:16" in result["timelines"]
