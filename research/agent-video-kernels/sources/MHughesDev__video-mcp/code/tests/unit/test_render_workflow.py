from mcp_editor.projects import save_manifest
from mcp_editor.schemas import Platform, ProjectManifest, TimelineClip, TimelinePlan
from mcp_editor.workflow import render_all_variants, render_platform_variant


def manifest_with_timelines():
    manifest = ProjectManifest(name="render-demo", platforms=[Platform.widescreen, Platform.square])
    for platform in manifest.platforms:
        manifest.timelines[platform.value] = TimelinePlan(
            project_id=manifest.project_id,
            platform=platform,
            clips=[TimelineClip(source="missing.mp4", duration=2)],
        )
    return manifest


def test_render_platform_variant_dry_run_saves_output_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    manifest = manifest_with_timelines()
    save_manifest(manifest)

    result = render_platform_variant(
        project_id=manifest.project_id,
        platform=Platform.widescreen,
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["output"]["validation"]["dry_run"] is True
    assert result["output"]["validation"]["render_manifest"]["command_count"] == 2


def test_render_all_variants_dry_run_returns_each_platform(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))
    manifest = manifest_with_timelines()
    save_manifest(manifest)

    result = render_all_variants(project_id=manifest.project_id, dry_run=True)

    assert result["ok"] is True
    assert result["platforms"] == ["16:9", "1:1"]
    assert set(result["outputs"]) == {"16:9", "1:1"}
