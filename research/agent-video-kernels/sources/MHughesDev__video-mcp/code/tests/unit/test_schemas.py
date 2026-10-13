from mcp_editor.schemas import PLATFORM_DIMENSIONS, Platform, ProjectManifest


def test_project_manifest_defaults_to_widescreen():
    manifest = ProjectManifest(name="demo")

    assert manifest.platforms == [Platform.widescreen]
    assert manifest.project_id


def test_platform_dimensions_cover_mvp_targets():
    assert PLATFORM_DIMENSIONS[Platform.widescreen] == (1920, 1080)
    assert PLATFORM_DIMENSIONS[Platform.vertical] == (1080, 1920)
    assert PLATFORM_DIMENSIONS[Platform.square] == (1080, 1080)
