from mcp_editor.schemas import MediaProbe, MediaStream, Platform
from mcp_editor.validation import validate_render


def test_validate_render_accepts_matching_probe(monkeypatch):
    def fake_probe(path):
        return MediaProbe(
            path=str(path),
            exists=True,
            ok=True,
            duration=10,
            streams=[
                MediaStream(index=0, codec_type="video", width=1920, height=1080, r_frame_rate="30/1"),
                MediaStream(index=1, codec_type="audio"),
            ],
        )

    monkeypatch.setattr("mcp_editor.validation.probe_media", fake_probe)
    monkeypatch.setattr("mcp_editor.validation._run_ffmpeg_null", lambda args: (False, "ffmpeg not found"))

    result = validate_render("out.mp4", Platform.widescreen, expected_duration=10)

    assert result["ok"] is True
    assert result["checks"]["resolution_matches"] is True
