import subprocess

from mcp_editor.diagnostics import command_failed, failed_tool_result, missing_dependency
from mcp_editor.media import probe_media
from mcp_editor.server import edit_video_from_prompt


def test_missing_dependency_tool_error_is_structured():
    result = failed_tool_result(missing_dependency("ffmpeg"))

    assert result["ok"] is False
    assert result["error"]["code"] == "missing_dependency"
    assert "suggested_fix" in result["error"]


def test_command_failed_preserves_stderr():
    exc = subprocess.CalledProcessError(
        returncode=1,
        cmd=["ffmpeg", "-bad"],
        output="out",
        stderr="specific ffmpeg failure",
    )

    result = failed_tool_result(command_failed("render_segment_1", ["ffmpeg", "-bad"], exc))

    assert result["error"]["code"] == "command_failed"
    assert result["error"]["details"]["stderr"] == "specific ffmpeg failure"
    assert result["error"]["details"]["stage"] == "render_segment_1"


def test_probe_media_missing_file_reports_path(tmp_path):
    missing = tmp_path / "missing.mp4"

    result = probe_media(missing)

    assert result.ok is False
    assert result.error_code == "media_not_found"
    assert str(missing.resolve()) in result.error


def test_workflow_failure_includes_events(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    input_dir = workspace / "data" / "input"
    input_dir.mkdir(parents=True)
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(workspace))

    result = edit_video_from_prompt(
        prompt="make a short edit",
        input_dir=str(input_dir),
        render=False,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "no_video_assets"
    assert any(event["stage"] == "create_project" for event in result["events"])
