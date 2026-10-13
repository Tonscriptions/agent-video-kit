from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from .config import data_dir
from .projects import load_manifest, save_manifest
from .schemas import ClipEffect, Platform, TimelineClip, TimelinePlan
from .timeline import find_clip_index


# ── LUT directory ─────────────────────────────────────────────────────────────


def luts_dir() -> Path:
    path = data_dir() / "luts"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── Built-in grading presets ──────────────────────────────────────────────────


GRADING_PRESETS: dict[str, dict[str, Any]] = {
    "cinematic": {
        "description": "Muted tones, lifted blacks, slight blue shadows",
        "brightness": 0.0,
        "contrast": 1.05,
        "saturation": 0.85,
        "gamma": 1.05,
        "vignette": 0.3,
    },
    "vivid": {
        "description": "Punchy colours, deep blacks, high contrast",
        "brightness": 0.02,
        "contrast": 1.15,
        "saturation": 1.3,
        "gamma": 0.95,
        "vignette": 0.0,
    },
    "flat": {
        "description": "Log-style low contrast, useful before further grading",
        "brightness": 0.05,
        "contrast": 0.8,
        "saturation": 0.7,
        "gamma": 1.1,
        "vignette": 0.0,
    },
    "bw": {
        "description": "Black and white conversion",
        "brightness": 0.0,
        "contrast": 1.0,
        "saturation": 0.0,
        "gamma": 1.0,
        "vignette": 0.0,
    },
    "warm": {
        "description": "Warm golden-hour look",
        "brightness": 0.03,
        "contrast": 1.05,
        "saturation": 1.1,
        "gamma": 1.0,
        "vignette": 0.15,
    },
    "cool": {
        "description": "Cool desaturated blue-tinted look",
        "brightness": -0.02,
        "contrast": 1.0,
        "saturation": 0.9,
        "gamma": 1.05,
        "vignette": 0.0,
    },
}


# ── .cube LUT parsing ─────────────────────────────────────────────────────────


def _parse_cube_header(path: Path) -> dict[str, Any]:
    """Parse a .cube file header and return metadata without loading all data."""
    size: int | None = None
    title: str | None = None
    lut_type = "3D"
    domain_min = [0.0, 0.0, 0.0]
    domain_max = [1.0, 1.0, 1.0]
    data_lines = 0

    with path.open(encoding="utf-8", errors="replace") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            upper = line.upper()
            if upper.startswith("LUT_3D_SIZE"):
                try:
                    size = int(line.split()[-1])
                    lut_type = "3D"
                except ValueError:
                    pass
            elif upper.startswith("LUT_1D_SIZE"):
                try:
                    size = int(line.split()[-1])
                    lut_type = "1D"
                except ValueError:
                    pass
            elif upper.startswith("TITLE"):
                title = line[5:].strip().strip('"')
            elif upper.startswith("DOMAIN_MIN"):
                try:
                    domain_min = [float(v) for v in line.split()[1:4]]
                except ValueError:
                    pass
            elif upper.startswith("DOMAIN_MAX"):
                try:
                    domain_max = [float(v) for v in line.split()[1:4]]
                except ValueError:
                    pass
            else:
                # Count data rows (three floats per line)
                parts = line.split()
                if len(parts) == 3:
                    try:
                        float(parts[0])
                        data_lines += 1
                    except ValueError:
                        pass

    return {
        "lut_type": lut_type,
        "size": size,
        "title": title,
        "domain_min": domain_min,
        "domain_max": domain_max,
        "data_lines": data_lines,
    }


# ── FFmpeg filter builders ────────────────────────────────────────────────────


def _eq_filter(brightness: float, contrast: float, saturation: float, gamma: float) -> str:
    """Build an FFmpeg eq filter string."""
    parts = [f"contrast={contrast:.4f}", f"saturation={saturation:.4f}", f"gamma={gamma:.4f}"]
    if brightness != 0.0:
        parts.append(f"brightness={brightness:.4f}")
    return "eq=" + ":".join(parts)


def _vignette_filter(strength: float) -> str:
    """Build an FFmpeg vignette filter. strength 0–1."""
    angle = strength * 1.5708  # map 0-1 → 0-π/2
    return f"vignette=angle={angle:.4f}"


def build_grade_vf(effect: ClipEffect) -> str:
    """Return a comma-joined FFmpeg filter string for a grading ClipEffect."""
    p = effect.params
    filters: list[str] = []

    lut_path = p.get("lut_path")
    if lut_path:
        safe = str(lut_path).replace("\\", "/").replace(":", "\\:")
        filters.append(f"lut3d='{safe}'")

    brightness = float(p.get("brightness", 0.0))
    contrast = float(p.get("contrast", 1.0))
    saturation = float(p.get("saturation", 1.0))
    gamma = float(p.get("gamma", 1.0))
    if any([brightness != 0, contrast != 1, saturation != 1, gamma != 1]):
        filters.append(_eq_filter(brightness, contrast, saturation, gamma))

    vignette = float(p.get("vignette", 0.0))
    if vignette > 0:
        filters.append(_vignette_filter(vignette))

    return ",".join(filters)


# ── effects.py integration ────────────────────────────────────────────────────


def _upsert_grade(clip: TimelineClip, params: dict[str, Any]) -> None:
    for effect in clip.effects:
        if effect.effect_type == "grade":
            effect.params.update(params)
            return
    clip.effects.append(ClipEffect(effect_type="grade", params=params))


def _clip_summary(clip: TimelineClip) -> dict[str, Any]:
    return {
        "clip_id": clip.clip_id,
        "source": clip.source,
        "start": clip.start,
        "duration": clip.duration,
        "label": clip.label,
        "effects": [e.model_dump() for e in clip.effects],
    }


# ── MCP implementation functions ──────────────────────────────────────────────


def list_luts() -> dict[str, Any]:
    """Return all .cube LUT files found in data/luts/."""
    lut_files = sorted(luts_dir().glob("*.cube"))
    luts = []
    for path in lut_files:
        luts.append(
            {
                "name": path.stem,
                "filename": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return {
        "ok": True,
        "luts_dir": str(luts_dir()),
        "count": len(luts),
        "luts": luts,
    }


def inspect_lut(name_or_path: str) -> dict[str, Any]:
    """Parse and return metadata for a .cube LUT file."""
    candidate = Path(name_or_path)
    if not candidate.is_absolute():
        candidate = luts_dir() / (name_or_path if name_or_path.endswith(".cube") else f"{name_or_path}.cube")

    if not candidate.exists():
        return {
            "ok": False,
            "error": f"LUT file not found: {candidate}",
            "suggested_fix": f"Run list_luts to see available LUTs in {luts_dir()}",
        }

    meta = _parse_cube_header(candidate)
    return {
        "ok": True,
        "name": candidate.stem,
        "filename": candidate.name,
        "path": str(candidate),
        "size_bytes": candidate.stat().st_size,
        **meta,
    }


def apply_lut(
    project_id: str,
    platform: Platform,
    lut_name: str,
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    """Apply a .cube LUT to a clip (or all clips if neither clip_id nor index given)."""
    candidate = luts_dir() / (lut_name if lut_name.endswith(".cube") else f"{lut_name}.cube")
    if not candidate.exists():
        return {
            "ok": False,
            "error": f"LUT file not found: {candidate}",
            "suggested_fix": f"Run list_luts to see available options in {luts_dir()}",
        }

    manifest = load_manifest(project_id)
    plan: TimelinePlan = manifest.timelines.get(platform.value)  # type: ignore[arg-type]
    if plan is None:
        raise ValueError(f"no timeline for platform {platform.value!r}; create one first")

    params = {"lut_path": str(candidate)}
    if clip_id is not None or index is not None:
        i = find_clip_index(plan, clip_id=clip_id, index=index)
        _upsert_grade(plan.clips[i], params)
        affected = [_clip_summary(plan.clips[i])]
    else:
        for clip in plan.clips:
            _upsert_grade(clip, params)
        affected = [_clip_summary(c) for c in plan.clips]

    save_manifest(manifest)
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "lut": lut_name,
        "lut_path": str(candidate),
        "clips_affected": len(affected),
        "clips": affected,
    }


def apply_grading_preset(
    project_id: str,
    platform: Platform,
    preset: str,
    clip_id: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    """Apply a named grading preset to a clip or all clips."""
    if preset not in GRADING_PRESETS:
        return {
            "ok": False,
            "error": f"Unknown preset: {preset!r}",
            "available_presets": list(GRADING_PRESETS),
        }

    manifest = load_manifest(project_id)
    plan: TimelinePlan = manifest.timelines.get(platform.value)  # type: ignore[arg-type]
    if plan is None:
        raise ValueError(f"no timeline for platform {platform.value!r}; create one first")

    params = {k: v for k, v in GRADING_PRESETS[preset].items() if k != "description"}
    if clip_id is not None or index is not None:
        i = find_clip_index(plan, clip_id=clip_id, index=index)
        _upsert_grade(plan.clips[i], params)
        affected = [_clip_summary(plan.clips[i])]
    else:
        for clip in plan.clips:
            _upsert_grade(clip, params)
        affected = [_clip_summary(c) for c in plan.clips]

    save_manifest(manifest)
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "preset": preset,
        "preset_params": params,
        "clips_affected": len(affected),
        "clips": affected,
    }


def render_with_grade(
    project_id: str,
    platform: Platform,
    render_profile: str = "preview",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Render a graded timeline (grades are baked into per-clip FFmpeg filters)."""
    from .render import render_timeline, render_manifest_summary
    from .projects import load_manifest as _load

    manifest = _load(project_id)
    plan: TimelinePlan = manifest.timelines.get(platform.value)  # type: ignore[arg-type]
    if plan is None:
        raise ValueError(f"no timeline for platform {platform.value!r}; create one first")

    result = render_timeline(plan, render_profile=render_profile, dry_run=dry_run)
    if dry_run:
        return render_manifest_summary(result)  # type: ignore[arg-type]
    return {
        "ok": True,
        "project_id": project_id,
        "platform": platform.value,
        "render_profile": render_profile,
        "output_path": str(result),
    }


def list_grading_presets() -> dict[str, Any]:
    """Return all built-in grading presets and their parameters."""
    return {
        "ok": True,
        "count": len(GRADING_PRESETS),
        "presets": {
            name: {"description": meta["description"], "params": {k: v for k, v in meta.items() if k != "description"}}
            for name, meta in GRADING_PRESETS.items()
        },
    }
