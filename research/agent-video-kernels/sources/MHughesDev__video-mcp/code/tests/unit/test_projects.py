from mcp_editor.diagnostics import McpEditorError
from mcp_editor.projects import load_manifest


def test_load_manifest_missing_project_has_stable_code():
    try:
        load_manifest("definitely-missing")
    except McpEditorError as exc:
        assert exc.issue.code == "project_not_found"
        assert exc.issue.details["project_id"] == "definitely-missing"
    else:
        raise AssertionError("expected McpEditorError")
