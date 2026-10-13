from __future__ import annotations

from pathlib import Path

import pytest

from mcp_editor.projects import save_manifest
from mcp_editor.schemas import (
    MediaProbe,
    MediaStream,
    Platform,
    ProjectManifest,
    RenderedOutput,
    TimelineClip,
    TimelinePlan,
)
from mcp_editor.workflow import _infer_grade, _infer_style, get_workflow_status


# ── Style inference ───────────────────────────────────────────────────────────


class TestInferStyle:
    def test_trailer_keyword(self):
        assert _infer_style("make me an epic trailer") == "trailer"

    def test_social_keyword(self):
        assert _infer_style("create an instagram reel") == "social"

    def test_documentary_keyword(self):
        assert _infer_style("slow documentary style") == "documentary"

    def test_fast_keyword(self):
        assert _infer_style("fast energetic cuts") == "fast"

    def test_slo_mo_keyword(self):
        assert _infer_style("slow-mo highlight reel") == "slow"

    def test_no_match_returns_medium(self):
        assert _infer_style("edit my video please") == "medium"

    def test_case_insensitive(self):
        assert _infer_style("EPIC TRAILER") == "trailer"


# ── Grade inference ────────────────────────────────────────────────────��──────


class TestInferGrade:
    def test_cinematic_keyword(self):
        assert _infer_grade("cinematic colour grade") == "cinematic"

    def test_vivid_keyword(self):
        assert _infer_grade("make the colours vibrant") == "vivid"

    def test_bw_keyword(self):
        assert _infer_grade("black and white film look") == "bw"

    def test_warm_keyword(self):
        assert _infer_grade("golden sunset feel") == "warm"

    def test_cool_keyword(self):
        assert _infer_grade("cold winter blue tones") == "cool"

    def test_flat_keyword(self):
        assert _infer_grade("flat log grade") == "flat"

    def test_no_match_returns_none(self):
        assert _infer_grade("just edit the video") is None

    def test_case_insensitive(self):
        assert _infer_grade("CINEMATIC LOOK") == "cinematic"


# ── get_workflow_status ────────��──────────────────────────────────────────────


def _make_manifest(tmp_path: Path, **kwargs) -> ProjectManifest:
    m = ProjectManifest(name="test", platforms=[Platform.widescreen], **kwargs)
    save_manifest(m)
    return m


class TestGetWorkflowStatus:
    def test_fresh_project_no_assets(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        m = _make_manifest(tmp_path)
        result = get_workflow_status(m.project_id)
        assert result["stages"]["project_created"] is True
        assert result["stages"]["assets_scanned"] is False
        assert result["next_step"] == "scan_project_assets"

    def test_project_with_assets_no_timeline(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        asset = MediaProbe(path="/tmp/clip.mp4", exists=True, ok=True, streams=[
            MediaStream(index=0, codec_type="video", width=1920, height=1080)
        ])
        m = _make_manifest(tmp_path, assets=[asset])
        result = get_workflow_status(m.project_id)
        assert result["stages"]["assets_scanned"] is True
        assert result["stages"]["timelines_built"] is False
        assert result["next_step"] == "create_timeline"

    def test_project_with_timeline_no_render(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        asset = MediaProbe(path="/tmp/clip.mp4", exists=True, ok=True, streams=[
            MediaStream(index=0, codec_type="video", width=1920, height=1080)
        ])
        otio_path = tmp_path / "timeline.otio"
        otio_path.write_text("{}", encoding="utf-8")
        clip = TimelineClip(source="/tmp/clip.mp4", start=0, duration=4.0)
        plan = TimelinePlan(
            project_id="x", platform=Platform.widescreen, clips=[clip],
            otio_path=str(otio_path),
        )
        m = _make_manifest(tmp_path, assets=[asset], timelines={"16:9": plan})
        result = get_workflow_status(m.project_id)
        assert result["stages"]["timelines_built"] is True
        assert result["stages"]["otio_exported"] is True
        assert result["stages"]["rendered"] is False
        assert result["next_step"] == "render_all_variants"

    def test_fully_complete_project(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        asset = MediaProbe(path="/tmp/clip.mp4", exists=True, ok=True, streams=[
            MediaStream(index=0, codec_type="video", width=1920, height=1080)
        ])
        otio_path = tmp_path / "timeline.otio"
        otio_path.write_text("{}", encoding="utf-8")
        clip = TimelineClip(source="/tmp/clip.mp4", start=0, duration=4.0)
        plan = TimelinePlan(
            project_id="x", platform=Platform.widescreen, clips=[clip],
            otio_path=str(otio_path),
        )
        rendered = RenderedOutput(platform=Platform.widescreen, path="/tmp/out.mp4", ok=True)
        m = _make_manifest(
            tmp_path,
            assets=[asset],
            timelines={"16:9": plan},
            outputs={"16:9": rendered},
        )
        result = get_workflow_status(m.project_id)
        assert result["stages"]["rendered"] is True
        assert result["stages"]["all_platforms_rendered"] is True
        assert result["stages"]["outputs_valid"] is True
        assert result["ok"] is True
        assert result["next_step"] is None

    def test_failed_output_flagged(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        rendered = RenderedOutput(platform=Platform.widescreen, path="/tmp/bad.mp4", ok=False)
        m = _make_manifest(tmp_path, outputs={"16:9": rendered})
        result = get_workflow_status(m.project_id)
        assert result["stages"]["outputs_valid"] is False

    def test_returns_summary_fields(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        m = _make_manifest(tmp_path)
        result = get_workflow_status(m.project_id)
        assert "project_name" in result
        assert "platforms" in result
        assert "asset_count" in result
        assert "timeline_count" in result
        assert "output_count" in result
        assert "stages" in result
