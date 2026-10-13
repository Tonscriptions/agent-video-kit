from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_editor.media_docs import (
    create_media_doc,
    doc_path_for,
    get_media_doc,
    list_media_docs,
    load_doc,
    meta_path_for,
    render_doc,
    save_doc,
)
from mcp_editor.schemas import (
    AudioDoc,
    AudioIdentity,
    AudioSection,
    AudioStructure,
    CameraMovement,
    ContrastValue,
    ImageDoc,
    ImageIdentity,
    IntensityValue,
    ShotScale,
    TemperatureValue,
    VideoColor,
    VideoContent,
    VideoDoc,
    VideoEmotionalRegister,
    VideoIdentity,
    VideoLighting,
    VideoNarrativeRole,
    VideoShotMovement,
    VideoShotSpatial,
    VideoTechnical,
)


def _make_video_doc() -> VideoDoc:
    return VideoDoc(
        identity=VideoIdentity(file="clip.mp4", duration="0:45"),
        technical=VideoTechnical(
            resolution="1920x1080",
            aspect_ratio="16:9",
            fps=30.0,
            has_audio=True,
        ),
        shot_spatial=VideoShotSpatial(scale=ShotScale.wide, composition="Subject left of frame"),
        shot_movement=VideoShotMovement(camera=CameraMovement.static, overall_pace="slow"),
        color=VideoColor(palette=["warm orange", "deep blue"], temperature=TemperatureValue.warm, contrast=ContrastValue.high),
        lighting=VideoLighting(source="natural", quality="soft", time_of_day="golden_hour"),
        content=VideoContent(primary_subject="person walking", setting="beach", action="walking away"),
        emotional_register=VideoEmotionalRegister(primary_emotion="melancholic", intensity=IntensityValue.moderate),
        narrative_role=VideoNarrativeRole(best_as=["outro"]),
    )


from mcp_editor.schemas import (
    AudioCreativeUtility,
    AudioEditUtility,
    AudioEnergyProfile,
    AudioEmotionalRegister,
    AudioSonicCharacter,
    DepthLayers,
    FramingRule,
    ImageAesthetic,
    ImageColor,
    ImageComposition,
    ImageContent,
    ImageCreativeUtility,
    ImageEmotionalRegister,
    ImageLighting,
    ImageTechnical,
    SaturationValue,
)


def _make_image_doc() -> ImageDoc:
    return ImageDoc(
        identity=ImageIdentity(file="photo.jpg", resolution="4000x2667", aspect_ratio="3:2"),
        technical=ImageTechnical(color_space="RGB", sharpness="sharp"),
        composition=ImageComposition(
            rule=FramingRule.thirds,
            subject_position="upper left",
            depth_layers=DepthLayers(foreground="grass", midground="path", background="sky"),
        ),
        color=ImageColor(palette=["green", "blue"], saturation=SaturationValue.natural),
        lighting=ImageLighting(source="natural", quality="soft"),
        content=ImageContent(primary_subject="landscape", setting="countryside", moment="sunrise"),
        aesthetic=ImageAesthetic(genre="landscape", era_feel="contemporary"),
        emotional_register=ImageEmotionalRegister(primary_mood="peaceful", what_it_communicates="serenity"),
        creative_utility=ImageCreativeUtility(use_as=["color_reference"]),
    )


def _make_audio_doc() -> AudioDoc:
    return AudioDoc(
        identity=AudioIdentity(file="track.mp3", duration="3:22"),
        structure=AudioStructure(sections=[
            AudioSection(name="intro", start="0:00", end="0:08", description="quiet open"),
        ]),
        sonic_character=AudioSonicCharacter(primary_sources=["piano", "bass"], texture="sparse"),
        energy_profile=AudioEnergyProfile(overall_energy="medium", energy_arc="builds gradually"),
        emotional_register=AudioEmotionalRegister(primary_mood="nostalgic", emotional_arc="calm to hopeful"),
        edit_utility=AudioEditUtility(works_as="background", natural_cutpoints=["1:30", "2:45"]),
        creative_utility=AudioCreativeUtility(pairs_with_visual="slow landscape footage"),
    )


def test_doc_path_for():
    assert doc_path_for("/data/input/clip.mp4") == Path("/data/input/clip.mp4.md")


def test_meta_path_for():
    assert meta_path_for("/data/input/clip.mp4") == Path("/data/input/clip.mp4.meta.json")


def test_render_video_doc_contains_all_sections():
    md = render_doc(_make_video_doc())
    for section in ["IDENTITY", "TECHNICAL", "SHOT", "COLOR", "LIGHTING", "CONTENT"]:
        assert section in md


def test_render_image_doc_contains_all_sections():
    md = render_doc(_make_image_doc())
    for section in ["IDENTITY", "COMPOSITION", "COLOR", "LIGHTING", "CONTENT", "AESTHETIC"]:
        assert section in md


def test_render_audio_doc_contains_all_sections():
    md = render_doc(_make_audio_doc())
    for section in ["IDENTITY", "STRUCTURE", "SONIC CHARACTER", "ENERGY PROFILE", "EDIT UTILITY"]:
        assert section in md


def test_save_doc_writes_md_and_meta_json(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"fake")
    doc = _make_video_doc()
    save_doc(doc, p)
    assert doc_path_for(p).exists()
    assert meta_path_for(p).exists()


def test_load_doc_roundtrip_video(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"fake")
    original = _make_video_doc()
    save_doc(original, p)
    loaded = load_doc(p)
    assert isinstance(loaded, VideoDoc)
    assert loaded.identity.file == "clip.mp4"
    assert loaded.technical.fps == 30.0


def test_load_doc_roundtrip_image(tmp_path):
    p = tmp_path / "photo.jpg"
    p.write_bytes(b"fake")
    original = _make_image_doc()
    save_doc(original, p)
    loaded = load_doc(p)
    assert isinstance(loaded, ImageDoc)
    assert loaded.identity.resolution == "4000x2667"


def test_load_doc_roundtrip_audio(tmp_path):
    p = tmp_path / "track.mp3"
    p.write_bytes(b"fake")
    original = _make_audio_doc()
    save_doc(original, p)
    loaded = load_doc(p)
    assert isinstance(loaded, AudioDoc)
    assert loaded.structure.sections[0].name == "intro"


def test_load_doc_returns_none_when_missing(tmp_path):
    p = tmp_path / "clip.mp4"
    assert load_doc(p) is None


def test_create_media_doc_valid_video(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"fake")
    doc_data = {
        "identity": {"file": "clip.mp4", "duration": "0:30"},
        "technical": {"resolution": "1920x1080", "aspect_ratio": "16:9", "fps": 24.0, "has_audio": False},
    }
    result = create_media_doc(str(p), doc_data)
    assert result["ok"] is True
    assert result["doc_type"] == "VideoDoc"
    assert Path(result["doc_path"]).exists()


def test_create_media_doc_invalid_path_returns_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_media_doc("/nonexistent/clip.mp4", {})


def test_get_media_doc_found(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"fake")
    save_doc(_make_video_doc(), p)
    result = get_media_doc(str(p))
    assert result["ok"] is True
    assert result["doc_type"] == "VideoDoc"
    assert "doc" in result


def test_get_media_doc_not_found_raises(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"fake")
    with pytest.raises(FileNotFoundError):
        get_media_doc(str(p))


def test_list_media_docs_returns_all_with_docs(tmp_path):
    for name in ["a.mp4", "b.mp3"]:
        p = tmp_path / name
        p.write_bytes(b"fake")
        if name.endswith(".mp4"):
            save_doc(_make_video_doc(), p)
        else:
            save_doc(_make_audio_doc(), p)

    result = list_media_docs(str(tmp_path))
    assert result["ok"] is True
    assert result["count"] == 2


def test_list_media_docs_empty_directory(tmp_path):
    result = list_media_docs(str(tmp_path))
    assert result["count"] == 0


def test_list_media_docs_skips_orphan_meta(tmp_path):
    # .meta.json without a corresponding media file should be skipped
    orphan = tmp_path / "ghost.mp4.meta.json"
    orphan.write_text('{"__doc_type__": "VideoDoc"}')
    result = list_media_docs(str(tmp_path))
    assert result["count"] == 0
