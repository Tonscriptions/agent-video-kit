from mcp_editor.projects import save_manifest
from mcp_editor.schemas import Platform, ProjectManifest
from mcp_editor.timeline_ops import (
    add_clip_to_project,
    add_transition_to_project,
    export_timeline_for_project,
    move_clip_in_project,
    split_clip_in_project,
    trim_clip_in_project,
    validate_timeline_for_project,
)


def test_project_timeline_operations_persist_manifest_and_otio(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(workspace))
    source_a = tmp_path / "a.mp4"
    source_b = tmp_path / "b.mp4"
    source_a.write_bytes(b"")
    source_b.write_bytes(b"")
    manifest = ProjectManifest(name="demo")
    save_manifest(manifest)

    result = add_clip_to_project(manifest.project_id, Platform.widescreen, str(source_a), duration=4, label="A")
    result = add_clip_to_project(manifest.project_id, Platform.widescreen, str(source_b), duration=4, label="B")
    clip_ids = [clip["clip_id"] for clip in result["timeline"]["clips"]]

    trim_result = trim_clip_in_project(manifest.project_id, Platform.widescreen, clip_id=clip_ids[0], duration=3)
    split_result = split_clip_in_project(manifest.project_id, Platform.widescreen, clip_id=clip_ids[0], split_at=1)
    move_result = move_clip_in_project(manifest.project_id, Platform.widescreen, from_index=2, to_index=0)
    moved_ids = [clip["clip_id"] for clip in move_result["timeline"]["clips"]]
    transition_result = add_transition_to_project(
        manifest.project_id,
        Platform.widescreen,
        from_clip_id=moved_ids[0],
        to_clip_id=moved_ids[1],
        duration=0.25,
    )
    export_result = export_timeline_for_project(manifest.project_id, Platform.widescreen)
    validation_result = validate_timeline_for_project(manifest.project_id, Platform.widescreen)

    assert trim_result["timeline"]["clips"][0]["duration"] == 3
    assert len(split_result["timeline"]["clips"]) == 3
    assert transition_result["validation"]["transition_count"] == 1
    assert export_result["otio_path"].endswith(".otio")
    assert validation_result["ok"] is True
