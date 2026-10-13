from __future__ import annotations

import pytest

from mcp_editor.effects import (
    SUPPORTED_EFFECTS,
    build_clip_af,
    build_clip_vf,
    source_read_duration,
)
from mcp_editor.schemas import ClipEffect, Platform, TimelineClip


def _clip(effects: list[ClipEffect] | None = None) -> TimelineClip:
    return TimelineClip(source="/tmp/dummy.mp4", start=0, duration=4.0, effects=effects or [])


class TestBuildClipVf:
    def test_no_effects_returns_platform_filter(self):
        vf = build_clip_vf(_clip(), Platform.widescreen)
        assert "scale=1920:1080" in vf
        assert "crop=1920:1080" in vf
        assert "setsar=1" in vf

    def test_vertical_platform(self):
        vf = build_clip_vf(_clip(), Platform.vertical)
        assert "scale=1080:1920" in vf

    def test_speed_ramp_inserts_setpts(self):
        clip = _clip([ClipEffect(effect_type="speed_ramp", params={"speed": 2.0})])
        vf = build_clip_vf(clip, Platform.widescreen)
        assert "setpts=PTS/2.0" in vf

    def test_zoom_punch_inserts_scale_and_crop(self):
        clip = _clip([ClipEffect(effect_type="zoom_punch", params={"zoom": 1.5})])
        vf = build_clip_vf(clip, Platform.widescreen)
        assert "scale=iw*1.5:ih*1.5" in vf
        assert "crop=" in vf

    def test_reframe_inserts_crop(self):
        clip = _clip([ClipEffect(effect_type="reframe", params={"x_pct": 0.0, "y_pct": 0.0, "crop_pct": 0.9})])
        vf = build_clip_vf(clip, Platform.widescreen)
        assert "crop=iw*0.9:ih*0.9" in vf

    def test_motion_blur_inserts_tblend(self):
        clip = _clip([ClipEffect(effect_type="motion_blur", params={})])
        vf = build_clip_vf(clip, Platform.widescreen)
        assert "tblend=all_mode=average" in vf

    def test_effects_appear_before_platform_filter(self):
        clip = _clip([ClipEffect(effect_type="speed_ramp", params={"speed": 2.0})])
        vf = build_clip_vf(clip, Platform.widescreen)
        speed_pos = vf.index("setpts")
        scale_pos = vf.index("scale=1920")
        assert speed_pos < scale_pos


class TestBuildClipAf:
    def test_no_effects_returns_empty(self):
        assert build_clip_af(_clip()) == []

    def test_speed_1_returns_empty(self):
        clip = _clip([ClipEffect(effect_type="speed_ramp", params={"speed": 1.0})])
        assert build_clip_af(clip) == []

    def test_speed_2_returns_atempo_2(self):
        clip = _clip([ClipEffect(effect_type="speed_ramp", params={"speed": 2.0})])
        af = build_clip_af(clip)
        assert len(af) == 1
        assert af[0].startswith("atempo=2.0")

    def test_speed_4_chains_atempo(self):
        clip = _clip([ClipEffect(effect_type="speed_ramp", params={"speed": 4.0})])
        af = build_clip_af(clip)
        assert len(af) == 2
        assert all(f.startswith("atempo=2.0") for f in af)

    def test_speed_half_returns_atempo_half(self):
        clip = _clip([ClipEffect(effect_type="speed_ramp", params={"speed": 0.5})])
        assert build_clip_af(clip) == ["atempo=0.5000"]

    def test_non_speed_effect_no_af(self):
        clip = _clip([ClipEffect(effect_type="zoom_punch", params={"zoom": 1.2})])
        assert build_clip_af(clip) == []


class TestSourceReadDuration:
    def test_no_effect_returns_clip_duration(self):
        assert source_read_duration(_clip()) == 4.0

    def test_speed_2_doubles_read_duration(self):
        clip = _clip([ClipEffect(effect_type="speed_ramp", params={"speed": 2.0})])
        assert source_read_duration(clip) == pytest.approx(8.0)

    def test_speed_half_halves_read_duration(self):
        clip = _clip([ClipEffect(effect_type="speed_ramp", params={"speed": 0.5})])
        assert source_read_duration(clip) == pytest.approx(2.0)

    def test_zoom_punch_does_not_affect_duration(self):
        clip = _clip([ClipEffect(effect_type="zoom_punch", params={"zoom": 1.5})])
        assert source_read_duration(clip) == 4.0


class TestSupportedEffects:
    def test_expected_effects_present(self):
        assert {"speed_ramp", "zoom_punch", "reframe", "motion_blur", "grade"} == SUPPORTED_EFFECTS
