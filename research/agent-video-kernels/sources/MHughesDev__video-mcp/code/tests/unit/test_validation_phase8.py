from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_editor.schemas import (
    MediaProbe,
    MediaStream,
    Platform,
    ProjectManifest,
    RenderedOutput,
    TimelinePlan,
    TimelineClip,
)
from mcp_editor.validation import (
    _check_fps,
    validate_audio,
    validate_delivery_package,
    validate_platform_outputs,
    validate_render,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _good_probe(platform: Platform = Platform.widescreen, has_audio: bool = True) -> MediaProbe:
    w, h = {Platform.widescreen: (1920, 1080), Platform.vertical: (1080, 1920), Platform.square: (1080, 1080)}[platform]
    streams = [MediaStream(index=0, codec_type="video", width=w, height=h, r_frame_rate="30/1")]
    if has_audio:
        streams.append(MediaStream(index=1, codec_type="audio", codec_name="aac"))
    return MediaProbe(path="out.mp4", exists=True, ok=True, duration=10.0, streams=streams)


def _no_ffmpeg_result():
    """Return value from _run_ffmpeg_null when ffmpeg is absent."""
    return (False, "ffmpeg not found")


# ── _check_fps ────────────────────────────────────────────────────────────────


class TestCheckFps:
    def test_exact_match(self):
        assert _check_fps("30/1", 30.0) is True

    def test_within_tolerance(self):
        assert _check_fps("2997/100", 30.0, tolerance=1.0) is True

    def test_outside_tolerance(self):
        assert _check_fps("24/1", 30.0, tolerance=1.0) is False

    def test_none_returns_false(self):
        assert _check_fps(None) is False

    def test_bad_string_returns_false(self):
        assert _check_fps("not/valid") is False

    def test_zero_denominator_returns_false(self):
        assert _check_fps("30/0") is False


# ── validate_render ───────────────────────────────────────────────────────────


class TestValidateRender:
    def _patch(self, monkeypatch, probe, ffmpeg_ok=False):
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: probe)
        monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (ffmpeg_ok, ""))

    def test_good_file_passes_core_checks(self, monkeypatch):
        self._patch(monkeypatch, _good_probe())
        result = validate_render("out.mp4", Platform.widescreen, expected_duration=10.0)
        assert result["checks"]["exists"] is True
        assert result["checks"]["probe_ok"] is True
        assert result["checks"]["has_video"] is True
        assert result["checks"]["resolution_matches"] is True
        assert result["checks"]["fps_correct"] is True
        assert result["checks"]["duration_close"] is True

    def test_wrong_resolution_fails(self, monkeypatch):
        probe = _good_probe(Platform.vertical)  # 1080x1920
        self._patch(monkeypatch, probe)
        result = validate_render("out.mp4", Platform.widescreen)
        assert result["checks"]["resolution_matches"] is False
        assert result["ok"] is False

    def test_wrong_fps_fails(self, monkeypatch):
        probe = MediaProbe(
            path="out.mp4", exists=True, ok=True, duration=10.0,
            streams=[MediaStream(index=0, codec_type="video", width=1920, height=1080, r_frame_rate="24/1")]
        )
        self._patch(monkeypatch, probe)
        result = validate_render("out.mp4", Platform.widescreen, expected_fps=30.0)
        assert result["checks"]["fps_correct"] is False

    def test_duration_mismatch_fails(self, monkeypatch):
        self._patch(monkeypatch, _good_probe())
        result = validate_render("out.mp4", Platform.widescreen, expected_duration=30.0)
        assert result["checks"]["duration_close"] is False

    def test_ffmpeg_skipped_when_unavailable(self, monkeypatch):
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe())
        monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (False, "ffmpeg not found"))
        result = validate_render("out.mp4", Platform.widescreen)
        assert result["advanced"]["black_check"]["skipped"] is True
        assert result["advanced"]["silence_check"]["skipped"] is True
        assert result["advanced"]["freeze_check"]["skipped"] is True
        # skipped checks should not block ok
        assert "not_black" not in result["checks"]

    def test_black_video_fails_when_ffmpeg_available(self, monkeypatch):
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe())
        # Simulate blackdetect reporting full duration as black
        monkeypatch.setattr(
            "mcp_editor.validation._run_ffmpeg_null",
            lambda args: (True, "black_start:0.0 black_end:5.0 black_duration:5.0"),
        )
        result = validate_render("out.mp4", Platform.widescreen, check_silent=False, check_frozen=False)
        assert result["checks"]["not_black"] is False

    def test_missing_file_fails(self, monkeypatch):
        probe = MediaProbe(path="missing.mp4", exists=False, ok=False, error="file not found")
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: probe)
        result = validate_render("missing.mp4", Platform.widescreen)
        assert result["ok"] is False
        assert result["checks"]["exists"] is False


# ── validate_audio ────────────────────────────────────────────────────────────


class TestValidateAudio:
    def test_good_audio_passes(self, monkeypatch):
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe())
        monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (False, "ffmpeg not found"))
        result = validate_audio("out.mp4", expected_duration=10.0)
        assert result["checks"]["has_audio"] is True
        assert result["checks"]["audio_stream_valid"] is True
        assert result["checks"]["duration_close"] is True

    def test_no_audio_fails(self, monkeypatch):
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe(has_audio=False))
        result = validate_audio("out.mp4")
        assert result["checks"]["has_audio"] is False
        assert result["ok"] is False

    def test_silent_audio_fails_when_ffmpeg_available(self, monkeypatch):
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe())
        monkeypatch.setattr(
            "mcp_editor.validation._run_ffmpeg_null",
            lambda args: (True, "silence_start:0.0\nsilence_end:5.0 | silence_duration:5.0"),
        )
        result = validate_audio("out.mp4")
        assert result["checks"]["not_silent"] is False

    def test_returns_codec_name(self, monkeypatch):
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe())
        monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (False, ""))
        result = validate_audio("out.mp4")
        assert result["codec"] == "aac"


# ── validate_platform_outputs ─────────────────────────────────────────────────


class TestValidatePlatformOutputs:
    def _make_manifest(self, tmp_path) -> ProjectManifest:
        clip = TimelineClip(source=str(tmp_path / "clip.mp4"), start=0, duration=10.0)
        plan = TimelinePlan(project_id="proj1", platform=Platform.widescreen, clips=[clip], target_duration=10.0)
        rendered = RenderedOutput(platform=Platform.widescreen, path=str(tmp_path / "out.mp4"), ok=True)
        return ProjectManifest(
            project_id="proj1",
            name="Test",
            timelines={"16:9": plan},
            outputs={"16:9": rendered},
        )

    def test_no_outputs_returns_error(self, monkeypatch):
        manifest = ProjectManifest(project_id="proj1", name="Test")
        monkeypatch.setattr("mcp_editor.validation.load_manifest", lambda pid: manifest)
        result = validate_platform_outputs("proj1")
        assert result["ok"] is False
        assert "no rendered outputs" in result["error"]

    def test_validates_each_output(self, monkeypatch, tmp_path):
        manifest = self._make_manifest(tmp_path)
        monkeypatch.setattr("mcp_editor.validation.load_manifest", lambda pid: manifest)
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe())
        monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (False, ""))
        result = validate_platform_outputs("proj1")
        assert "16:9" in result["results"]
        assert result["platforms_checked"] == 1

    def test_failed_output_propagates(self, monkeypatch, tmp_path):
        manifest = self._make_manifest(tmp_path)
        monkeypatch.setattr("mcp_editor.validation.load_manifest", lambda pid: manifest)
        bad_probe = MediaProbe(path="out.mp4", exists=False, ok=False)
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: bad_probe)
        result = validate_platform_outputs("proj1")
        assert result["ok"] is False


# ── validate_delivery_package ─────────────────────────────────────────────────


class TestValidateDeliveryPackage:
    def _make_manifest(self, tmp_path, with_otio=False) -> ProjectManifest:
        otio_path = str(tmp_path / "timeline.otio") if with_otio else None
        if with_otio:
            (tmp_path / "timeline.otio").write_text("{}", encoding="utf-8")
        clip = TimelineClip(source=str(tmp_path / "clip.mp4"), start=0, duration=10.0)
        plan = TimelinePlan(
            project_id="proj1", platform=Platform.widescreen, clips=[clip],
            target_duration=10.0, otio_path=otio_path,
        )
        from mcp_editor.schemas import MediaProbe as MP, MediaStream as MS
        asset = MP(path=str(tmp_path / "clip.mp4"), exists=True, ok=True, streams=[
            MS(index=0, codec_type="video", width=1920, height=1080)
        ])
        rendered = RenderedOutput(platform=Platform.widescreen, path=str(tmp_path / "out.mp4"), ok=True)
        return ProjectManifest(
            project_id="proj1",
            name="Test Delivery",
            platforms=[Platform.widescreen],
            timelines={"16:9": plan},
            outputs={"16:9": rendered},
            assets=[asset],
        )

    def test_no_outputs_fails_delivery(self, monkeypatch):
        manifest = ProjectManifest(project_id="proj1", name="Test", platforms=[Platform.widescreen])
        monkeypatch.setattr("mcp_editor.validation.load_manifest", lambda pid: manifest)
        result = validate_delivery_package("proj1")
        assert result["ok"] is False
        codes = [i["code"] for i in result["issues"]]
        assert "no_outputs" in codes
        assert "missing_platform_outputs" in codes

    def test_missing_otio_flagged(self, monkeypatch, tmp_path):
        manifest = self._make_manifest(tmp_path, with_otio=False)
        monkeypatch.setattr("mcp_editor.validation.load_manifest", lambda pid: manifest)
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe())
        monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (False, ""))
        result = validate_delivery_package("proj1")
        codes = [i["code"] for i in result["issues"]]
        assert "missing_otio_export" in codes

    def test_full_valid_package_passes(self, monkeypatch, tmp_path):
        manifest = self._make_manifest(tmp_path, with_otio=True)
        monkeypatch.setattr("mcp_editor.validation.load_manifest", lambda pid: manifest)
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe())
        monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (False, ""))
        result = validate_delivery_package("proj1")
        assert result["ok"] is True
        assert result["issues"] == []
        assert result["outputs_count"] == 1

    def test_summary_fields_present(self, monkeypatch, tmp_path):
        manifest = self._make_manifest(tmp_path, with_otio=True)
        monkeypatch.setattr("mcp_editor.validation.load_manifest", lambda pid: manifest)
        monkeypatch.setattr("mcp_editor.validation.probe_media", lambda p: _good_probe())
        monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (False, ""))
        result = validate_delivery_package("proj1")
        assert "project_name" in result
        assert "platforms" in result
        assert "timelines_count" in result
        assert "checks" in result
