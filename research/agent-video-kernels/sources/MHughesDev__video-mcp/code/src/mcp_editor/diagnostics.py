from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DiagnosticIssue:
    code: str
    message: str
    suggested_fix: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
        if self.suggested_fix:
            payload["suggested_fix"] = self.suggested_fix
        return payload


class McpEditorError(Exception):
    def __init__(self, issue: DiagnosticIssue):
        super().__init__(issue.message)
        self.issue = issue


class WorkflowError(McpEditorError):
    def __init__(self, issue: DiagnosticIssue, events: list[dict[str, Any]]):
        super().__init__(issue)
        self.events = events


def missing_dependency(binary: str) -> McpEditorError:
    return McpEditorError(
        DiagnosticIssue(
            code="missing_dependency",
            message=f"{binary} was not found on PATH.",
            suggested_fix=(
                "Install FFmpeg and make sure both ffmpeg and ffprobe are available on PATH. "
                "Windows: winget install Gyan.FFmpeg. macOS: brew install ffmpeg. "
                "Ubuntu/Debian: sudo apt install ffmpeg."
            ),
            details={"binary": binary},
        )
    )


def media_not_found(path: str) -> DiagnosticIssue:
    return DiagnosticIssue(
        code="media_not_found",
        message=f"Media file was not found: {path}",
        suggested_fix="Check the path, or place the source file under data/input or data/music.",
        details={"path": path},
    )


def no_video_assets(input_dir: str) -> DiagnosticIssue:
    return DiagnosticIssue(
        code="no_video_assets",
        message=f"No usable video assets were found in {input_dir}.",
        suggested_fix="Add .mp4, .mov, .mkv, .webm, .avi, or .m4v footage to the input directory.",
        details={"input_dir": input_dir},
    )


def project_not_found(project_id: str, path: str) -> McpEditorError:
    return McpEditorError(
        DiagnosticIssue(
            code="project_not_found",
            message=f"Project manifest was not found for project_id: {project_id}",
            suggested_fix="Call create_project first, or pass an existing project_id from data/projects.",
            details={"project_id": project_id, "manifest_path": path},
        )
    )


def command_failed(stage: str, cmd: list[str], exc: subprocess.CalledProcessError) -> McpEditorError:
    return McpEditorError(
        DiagnosticIssue(
            code="command_failed",
            message=f"External command failed during {stage}.",
            suggested_fix="Inspect stderr, fix the media/dependency issue, and retry the same tool call.",
            details={
                "stage": stage,
                "returncode": exc.returncode,
                "command": cmd,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            },
        )
    )


def exception_issue(exc: Exception) -> DiagnosticIssue:
    if isinstance(exc, McpEditorError):
        return exc.issue
    if isinstance(exc, FileNotFoundError):
        return DiagnosticIssue(
            code="file_not_found",
            message=str(exc),
            suggested_fix="Verify the file path exists and is readable from the MCP server process.",
            details={"exception_type": exc.__class__.__name__},
        )
    if isinstance(exc, ValueError):
        return DiagnosticIssue(
            code="invalid_request",
            message=str(exc),
            suggested_fix="Check the tool arguments and retry with valid platform, project, or timeline values.",
            details={"exception_type": exc.__class__.__name__},
        )
    return DiagnosticIssue(
        code="internal_error",
        message=str(exc) or exc.__class__.__name__,
        suggested_fix="Check server logs and retry. If this repeats, file a bug with the returned details.",
        details={"exception_type": exc.__class__.__name__},
    )


def failed_tool_result(exc: Exception, stage: str | None = None) -> dict[str, Any]:
    issue = exception_issue(exc)
    events = getattr(exc, "events", None)
    payload: dict[str, Any] = {
        "ok": False,
        "error": issue.model_dump(),
    }
    if stage:
        payload["stage"] = stage
    if events:
        payload["events"] = events
    return payload


def event(stage: str, status: str, **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"stage": stage, "status": status}
    if details:
        payload["details"] = details
    return payload
