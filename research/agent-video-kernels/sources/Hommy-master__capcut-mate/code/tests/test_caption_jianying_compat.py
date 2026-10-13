"""验证字幕素材导出结构对齐剪映官方草稿，便于二次编辑。"""

from __future__ import annotations

import json
import math

from src.pyJianYingDraft import ScriptFile, TrackType, FontType
from src.service.add_captions import add_caption_to_draft


def _add_material(**kwargs):
    script = ScriptFile(width=1920, height=1080, fps=30, maintrack_adsorb=False)
    script.add_track(TrackType.text, "caption_track")
    caption = {"start": 0, "end": 3_000_000, "text": "第一行字幕"}
    caption.update(kwargs.pop("caption_extra", {}) or {})
    call_kwargs = {"alignment": 1, "font_size": 15}
    call_kwargs.update(kwargs)
    _, text_id, _ = add_caption_to_draft(
        script,
        "caption_track",
        caption=caption,
        **call_kwargs,
    )
    material = next(item for item in script.materials.texts if item["id"] == text_id)
    track = list(script.tracks.values())[0]
    segment = track.segments[0]
    return script, material, segment


def test_caption_material_matches_jianying_schema():
    script, material, segment = _add_material()
    content = json.loads(material["content"])
    style = content["styles"][0]

    assert material["type"] == "text"
    assert material["text_color"] == "#FFFFFF"
    assert material["font_size"] == 15
    assert material["font_resource_id"] == ""
    assert material["fonts"] == []
    assert material["words"] == {"end_time": [], "start_time": [], "text": []}
    assert "caption_template_info" in material
    assert style["range"] == [0, 5]
    assert style["font"] == {"id": "", "path": "D:"}
    assert material["font_path"] == "D:"
    assert "alpha" not in style["fill"]
    assert "bold" not in style
    assert "strokes" not in style

    seg_json = segment.export_json()
    assert seg_json["enable_adjust"] is False
    assert seg_json["enable_lut"] is False
    assert len(seg_json["extra_material_refs"]) >= 1
    assert len(script.materials.animations) == 1
    anim = script.materials.animations[0].export_json()
    assert anim["type"] == "sticker_animation"
    assert anim["animations"] == []
    assert anim["id"] == seg_json["extra_material_refs"][0]


def test_caption_custom_font_writes_fonts_array_and_resource_id():
    _, material, _ = _add_material(
        font="三极宋黑体超粗",
        font_size=12,
        caption_extra={"text": "第二行字幕"},
    )
    content = json.loads(material["content"])
    style = content["styles"][0]
    expected_id = FontType.三极宋黑体超粗.value.resource_id

    assert material["type"] == "text"
    assert material["font_size"] == 12
    assert material["font_resource_id"] == expected_id
    assert len(material["fonts"]) == 1
    assert material["fonts"][0]["resource_id"] == expected_id
    assert material["fonts"][0]["title"] == "三极宋黑体超粗"
    assert style["font"]["id"] == expected_id
    assert style["font"]["path"] == "D:"
    assert material["font_path"] == "D:"
    assert material["fonts"][0]["path"] == "D:"
    assert style["size"] == 12
    assert style["range"] == [0, 5]
    """demo1-2: UI Y=500 → transform.y ≈ 500/1080。"""
    _, _, segment = _add_material(transform_y=500)
    clip = segment.export_json()["clip"]
    assert math.isclose(clip["transform"]["y"], 500 / 1080, rel_tol=1e-9)
    assert clip["transform"]["x"] == 0
