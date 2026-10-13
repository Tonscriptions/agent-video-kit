from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from mcp_editor.grading import (
    GRADING_PRESETS,
    _eq_filter,
    _parse_cube_header,
    _vignette_filter,
    build_grade_vf,
    list_grading_presets,
)
from mcp_editor.schemas import ClipEffect


class TestEqFilter:
    def test_neutral_grade_skips_brightness(self):
        f = _eq_filter(brightness=0.0, contrast=1.0, saturation=1.0, gamma=1.0)
        assert "brightness" not in f

    def test_nonzero_brightness_included(self):
        f = _eq_filter(brightness=0.1, contrast=1.0, saturation=1.0, gamma=1.0)
        assert "brightness=0.1000" in f

    def test_contains_contrast_saturation_gamma(self):
        f = _eq_filter(brightness=0.0, contrast=1.1, saturation=0.8, gamma=1.05)
        assert "contrast=1.1000" in f
        assert "saturation=0.8000" in f
        assert "gamma=1.0500" in f

    def test_starts_with_eq(self):
        f = _eq_filter(0.0, 1.0, 1.0, 1.0)
        assert f.startswith("eq=")


class TestVignetteFilter:
    def test_returns_vignette_filter(self):
        f = _vignette_filter(0.5)
        assert f.startswith("vignette=angle=")

    def test_zero_strength_gives_zero_angle(self):
        f = _vignette_filter(0.0)
        assert "angle=0.0000" in f

    def test_full_strength_gives_pi_over_2(self):
        f = _vignette_filter(1.0)
        assert "angle=1.5708" in f


class TestBuildGradeVf:
    def test_empty_params_returns_empty_string(self):
        effect = ClipEffect(effect_type="grade", params={})
        assert build_grade_vf(effect) == ""

    def test_lut_path_adds_lut3d(self):
        effect = ClipEffect(effect_type="grade", params={"lut_path": "/data/luts/film.cube"})
        vf = build_grade_vf(effect)
        assert "lut3d=" in vf

    def test_contrast_adds_eq(self):
        effect = ClipEffect(effect_type="grade", params={"contrast": 1.1})
        vf = build_grade_vf(effect)
        assert "eq=" in vf

    def test_vignette_adds_vignette_filter(self):
        effect = ClipEffect(effect_type="grade", params={"vignette": 0.3})
        vf = build_grade_vf(effect)
        assert "vignette=" in vf

    def test_all_params_combined(self):
        effect = ClipEffect(
            effect_type="grade",
            params={
                "lut_path": "/luts/grade.cube",
                "contrast": 1.05,
                "saturation": 0.85,
                "gamma": 1.05,
                "vignette": 0.3,
            },
        )
        vf = build_grade_vf(effect)
        assert "lut3d=" in vf
        assert "eq=" in vf
        assert "vignette=" in vf
        # Order: LUT → eq → vignette
        assert vf.index("lut3d") < vf.index("eq=") < vf.index("vignette=")


class TestParseCubeHeader:
    def _write_cube(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "test.cube"
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p

    def test_parses_3d_size(self, tmp_path):
        cube = self._write_cube(
            tmp_path,
            """\
            TITLE "Test LUT"
            LUT_3D_SIZE 17
            0.0 0.0 0.0
            """,
        )
        meta = _parse_cube_header(cube)
        assert meta["size"] == 17
        assert meta["lut_type"] == "3D"
        assert meta["title"] == "Test LUT"

    def test_parses_1d_size(self, tmp_path):
        cube = self._write_cube(
            tmp_path,
            """\
            LUT_1D_SIZE 256
            0.0 0.0 0.0
            """,
        )
        meta = _parse_cube_header(cube)
        assert meta["size"] == 256
        assert meta["lut_type"] == "1D"

    def test_parses_domain(self, tmp_path):
        cube = self._write_cube(
            tmp_path,
            """\
            LUT_3D_SIZE 4
            DOMAIN_MIN 0.0 0.0 0.0
            DOMAIN_MAX 1.0 1.0 1.0
            0.0 0.0 0.0
            """,
        )
        meta = _parse_cube_header(cube)
        assert meta["domain_min"] == [0.0, 0.0, 0.0]
        assert meta["domain_max"] == [1.0, 1.0, 1.0]

    def test_counts_data_lines(self, tmp_path):
        lines = "\n".join(f"0.{i} 0.{i} 0.{i}" for i in range(5))
        cube = self._write_cube(tmp_path, f"LUT_3D_SIZE 2\n{lines}\n")
        meta = _parse_cube_header(cube)
        assert meta["data_lines"] == 5

    def test_no_size_returns_none(self, tmp_path):
        cube = self._write_cube(tmp_path, "# no size header\n0.0 0.0 0.0\n")
        meta = _parse_cube_header(cube)
        assert meta["size"] is None


class TestListGradingPresets:
    def test_returns_ok(self):
        result = list_grading_presets()
        assert result["ok"] is True

    def test_contains_all_presets(self):
        result = list_grading_presets()
        assert set(result["presets"]) == set(GRADING_PRESETS)

    def test_each_preset_has_description_and_params(self):
        result = list_grading_presets()
        for name, data in result["presets"].items():
            assert "description" in data
            assert "params" in data

    def test_count_matches(self):
        result = list_grading_presets()
        assert result["count"] == len(GRADING_PRESETS)


class TestBuildClipVfWithGrade:
    """Verify grade effect is threaded through effects.build_clip_vf."""

    def test_grade_with_contrast_adds_eq_to_vf(self):
        from mcp_editor.effects import build_clip_vf
        from mcp_editor.schemas import Platform, TimelineClip

        clip = TimelineClip(
            source="/tmp/dummy.mp4",
            start=0,
            duration=4.0,
            effects=[ClipEffect(effect_type="grade", params={"contrast": 1.1, "saturation": 0.9, "gamma": 1.0})],
        )
        vf = build_clip_vf(clip, Platform.widescreen)
        assert "eq=" in vf
        # Grade filter must appear before the final platform scale/crop
        assert vf.index("eq=") < vf.index("scale=1920")
