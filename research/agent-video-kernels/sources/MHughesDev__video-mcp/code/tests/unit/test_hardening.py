from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mcp_editor.logging import ProjectLogger, get_project_log_summary, read_project_logs
from mcp_editor.schemas import deterministic_project_id, posix_path, RenderManifest, Platform
from mcp_editor.render import _run_command, RENDER_PROFILES


# ── posix_path ────────────────────────────────────────────────────────────────


class TestPosixPath:
    def test_forward_slashes(self):
        result = posix_path("/data/projects/abc/out.mp4")
        assert "\\" not in result

    def test_windows_path_normalised(self):
        result = posix_path(Path("C:/Users/test/out.mp4"))
        assert "\\" not in result

    def test_relative_path(self):
        result = posix_path("data/output/file.mp4")
        assert result == "data/output/file.mp4"


# ── deterministic_project_id ──────────────────────────────────────────────────


class TestDeterministicProjectId:
    def test_same_inputs_same_id(self):
        a = deterministic_project_id("my-project", "data/input")
        b = deterministic_project_id("my-project", "data/input")
        assert a == b

    def test_different_name_different_id(self):
        a = deterministic_project_id("project-a", "data/input")
        b = deterministic_project_id("project-b", "data/input")
        assert a != b

    def test_different_input_dir_different_id(self):
        a = deterministic_project_id("my-project", "data/input")
        b = deterministic_project_id("my-project", "data/other")
        assert a != b

    def test_returns_12_chars(self):
        pid = deterministic_project_id("test", "data/input")
        assert len(pid) == 12

    def test_returns_hex(self):
        pid = deterministic_project_id("test", "data/input")
        assert all(c in "0123456789abcdef" for c in pid)

    def test_case_insensitive(self):
        a = deterministic_project_id("My Project", "data/input")
        b = deterministic_project_id("my project", "data/input")
        assert a == b


# ── ProjectLogger ─────────────────────────────────────────────────────────────


class TestProjectLogger:
    def test_writes_info_record(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        logger = ProjectLogger("proj1", session_id="test-session")
        logger.info("render", "Segment done", segment=1)
        records = read_project_logs("proj1")
        assert len(records) == 1
        assert records[0]["level"] == "info"
        assert records[0]["stage"] == "render"
        assert records[0]["segment"] == 1

    def test_writes_warning_record(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        logger = ProjectLogger("proj1", session_id="s1")
        logger.warning("validate", "Resolution mismatch")
        records = read_project_logs("proj1")
        assert records[0]["level"] == "warning"

    def test_writes_error_record(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        logger = ProjectLogger("proj1", session_id="s1")
        logger.error("render", "FFmpeg crashed", code=1)
        records = read_project_logs("proj1")
        assert records[0]["level"] == "error"
        assert records[0]["code"] == 1

    def test_timed_record_has_elapsed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        logger = ProjectLogger("proj1", session_id="s1")
        logger.timed("render", "Render done", elapsed=3.14)
        records = read_project_logs("proj1")
        assert records[0]["elapsed_s"] == 3.14

    def test_multiple_records_appended(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        logger = ProjectLogger("proj1", session_id="s1")
        logger.info("a", "first")
        logger.info("b", "second")
        logger.info("c", "third")
        records = read_project_logs("proj1")
        assert len(records) == 3

    def test_log_never_crashes_on_bad_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        logger = ProjectLogger("proj1", session_id="s1")
        # Force an OSError by making the log path a directory
        log_path = tmp_path / "data" / "projects" / "proj1" / "logs" / "s1.jsonl"
        log_path.mkdir(parents=True, exist_ok=True)
        # Should not raise
        logger.info("test", "this should be swallowed silently")


class TestGetProjectLogSummary:
    def test_no_logs_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        result = get_project_log_summary("proj-no-logs")
        assert result["ok"] is True
        assert result["total_records"] == 0

    def test_counts_errors_and_warnings(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        logger = ProjectLogger("proj1", session_id="s1")
        logger.info("a", "info")
        logger.warning("b", "warn")
        logger.error("c", "err1")
        logger.error("d", "err2")
        result = get_project_log_summary("proj1")
        assert result["error_count"] == 2
        assert result["warning_count"] == 1
        assert result["total_records"] == 4

    def test_recent_records_capped_at_20(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
        logger = ProjectLogger("proj1", session_id="s1")
        for i in range(30):
            logger.info("stage", f"msg {i}")
        result = get_project_log_summary("proj1")
        assert len(result["recent_records"]) == 20
        assert result["total_records"] == 30


# ── _run_command retry behaviour ──────────────────────────────────────────────


class TestRunCommandRetry:
    def test_succeeds_on_first_attempt(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            return result

        monkeypatch.setattr(subprocess, "run", fake_run)
        record = _run_command("test_stage", ["echo", "hi"], max_retries=2)
        assert record["ok"] is True
        assert record["attempt"] == 1
        assert len(calls) == 1

    def test_retries_on_failure_then_succeeds(self, monkeypatch):
        attempt_count = [0]

        def fake_run(cmd, **kwargs):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise subprocess.CalledProcessError(1, cmd, output=b"", stderr=b"transient")
            result = MagicMock()
            result.returncode = 0
            return result

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr("mcp_editor.render.time.sleep", lambda s: None)
        record = _run_command("stage", ["ffmpeg", "-y"], max_retries=2)
        assert record["ok"] is True
        assert record["attempt"] == 3

    def test_raises_after_all_retries_exhausted(self, monkeypatch):
        from mcp_editor.diagnostics import McpEditorError

        def fake_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd, output=b"", stderr=b"always fails")

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr("mcp_editor.render.time.sleep", lambda s: None)
        with pytest.raises(McpEditorError):
            _run_command("stage", ["ffmpeg"], max_retries=2)

    def test_zero_retries_fails_immediately(self, monkeypatch):
        from mcp_editor.diagnostics import McpEditorError

        def fake_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd, output=b"", stderr=b"fail")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(McpEditorError):
            _run_command("stage", ["ffmpeg"], max_retries=0)


# ── RenderManifest timing field ───────────────────────────────────────────────


class TestRenderManifestTiming:
    def test_timing_defaults_to_empty(self):
        m = RenderManifest(
            project_id="p1",
            platform=Platform.widescreen,
            output_path="/tmp/out.mp4",
            work_dir="/tmp/work",
            expected_duration=10.0,
            dimensions=(1920, 1080),
        )
        assert m.timing == []

    def test_timing_serialises_to_json(self):
        m = RenderManifest(
            project_id="p1",
            platform=Platform.widescreen,
            output_path="/tmp/out.mp4",
            work_dir="/tmp/work",
            expected_duration=10.0,
            dimensions=(1920, 1080),
            timing=[{"stage": "render_segment_1", "elapsed_s": 1.23, "ok": True}],
        )
        data = json.loads(m.model_dump_json())
        assert data["timing"][0]["elapsed_s"] == 1.23
