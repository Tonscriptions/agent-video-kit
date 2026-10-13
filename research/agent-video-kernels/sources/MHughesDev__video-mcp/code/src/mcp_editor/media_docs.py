from __future__ import annotations

import json
from pathlib import Path
from typing import Union

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]

from .inspection import analyze_audio_metadata, analyze_video_metadata, generate_thumbnails
from .beat_sync import analyze_beats
from .media import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from .schemas import (
    AudioDoc,
    AudioIdentity,
    AudioTechnical,
    AudioSection,
    AudioStructure,
    ImageDoc,
    ImageIdentity,
    ImageTechnical,
    VideoDoc,
    VideoIdentity,
    VideoTechnical,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tiff", ".bmp"}

AnyDoc = Union[VideoDoc, ImageDoc, AudioDoc]

DOC_SUFFIX = ".md"
META_SUFFIX = ".meta.json"

_DOC_TYPE_KEY = "__doc_type__"


def doc_path_for(media_path: str | Path) -> Path:
    return Path(str(media_path) + DOC_SUFFIX)


def meta_path_for(media_path: str | Path) -> Path:
    return Path(str(media_path) + META_SUFFIX)


# ---------------------------------------------------------------------------
# Markdown renderers
# ---------------------------------------------------------------------------

def _field(label: str, value: object) -> str:
    if value is None or value == "" or value == []:
        return ""
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return f"**{label}:** {value}\n"


def _section(title: str, lines: list[str]) -> str:
    body = "".join(l for l in lines if l)
    if not body.strip():
        return ""
    return f"\n## {title}\n\n{body}"


def _render_video_doc(doc: VideoDoc) -> str:
    parts: list[str] = [f"# {doc.identity.file}\n"]

    parts.append(_section("IDENTITY", [
        _field("file", doc.identity.file),
        _field("duration", doc.identity.duration),
        _field("source", doc.identity.source),
        _field("captured", doc.identity.captured),
    ]))

    parts.append(_section("TECHNICAL", [
        _field("resolution", doc.technical.resolution),
        _field("aspect_ratio", doc.technical.aspect_ratio),
        _field("fps", doc.technical.fps),
        _field("color_space", doc.technical.color_space),
        _field("dynamic_range", doc.technical.dynamic_range),
        _field("stabilized", doc.technical.stabilized),
        _field("has_audio", doc.technical.has_audio),
    ]))

    parts.append(_section("SHOT — SPATIAL", [
        _field("scale", doc.shot_spatial.scale.value if doc.shot_spatial.scale else None),
        _field("angle", doc.shot_spatial.angle.value if doc.shot_spatial.angle else None),
        _field("depth_of_field", doc.shot_spatial.depth_of_field),
        _field("composition", doc.shot_spatial.composition),
    ]))

    parts.append(_section("SHOT — MOVEMENT", [
        _field("camera", doc.shot_movement.camera.value if doc.shot_movement.camera else None),
        _field("subject_motion", doc.shot_movement.subject_motion),
        _field("overall_pace", doc.shot_movement.overall_pace),
        _field("energy_arc", doc.shot_movement.energy_arc),
    ]))

    parts.append(_section("COLOR", [
        _field("palette", doc.color.palette),
        _field("temperature", doc.color.temperature.value if doc.color.temperature else None),
        _field("contrast", doc.color.contrast.value if doc.color.contrast else None),
        _field("saturation", doc.color.saturation.value if doc.color.saturation else None),
        _field("tonal_key", doc.color.tonal_key.value if doc.color.tonal_key else None),
        _field("grade_character", doc.color.grade_character),
    ]))

    parts.append(_section("LIGHTING", [
        _field("source", doc.lighting.source),
        _field("quality", doc.lighting.quality),
        _field("direction", doc.lighting.direction),
        _field("time_of_day", doc.lighting.time_of_day),
        _field("shadow_character", doc.lighting.shadow_character),
    ]))

    parts.append(_section("CONTENT", [
        _field("primary_subject", doc.content.primary_subject),
        _field("secondary", doc.content.secondary),
        _field("setting", doc.content.setting),
        _field("action", doc.content.action),
        _field("human_presence", doc.content.human_presence),
        _field("emotion_displayed", doc.content.emotion_displayed),
    ]))

    parts.append(_section("EMBEDDED AUDIO", [
        _field("ambient", doc.embedded_audio.ambient),
        _field("dialogue", doc.embedded_audio.dialogue),
        _field("music", doc.embedded_audio.music),
        _field("audio_quality", doc.embedded_audio.audio_quality),
        _field("silence_at", doc.embedded_audio.silence_at),
    ]))

    if doc.temporal_map.segments:
        seg_lines = ["".join(
            f"- `[{s.start}–{s.end}]` {s.description}\n" for s in doc.temporal_map.segments
        )]
        if doc.temporal_map.natural_cutpoints:
            seg_lines.append(_field("natural_cutpoints", doc.temporal_map.natural_cutpoints))
        if doc.temporal_map.energy_arc:
            seg_lines.append(_field("energy_arc", doc.temporal_map.energy_arc))
        parts.append(_section("TEMPORAL MAP", seg_lines))
    elif doc.temporal_map.energy_arc or doc.temporal_map.natural_cutpoints:
        parts.append(_section("TEMPORAL MAP", [
            _field("natural_cutpoints", doc.temporal_map.natural_cutpoints),
            _field("energy_arc", doc.temporal_map.energy_arc),
        ]))

    parts.append(_section("EMOTIONAL REGISTER", [
        _field("primary_emotion", doc.emotional_register.primary_emotion),
        _field("secondary", doc.emotional_register.secondary),
        _field("intensity", doc.emotional_register.intensity.value if doc.emotional_register.intensity else None),
        _field("viewer_effect", doc.emotional_register.viewer_effect),
    ]))

    parts.append(_section("NARRATIVE ROLE", [
        _field("best_as", doc.narrative_role.best_as),
        _field("narrative_weight", doc.narrative_role.narrative_weight),
        _field("standalone", doc.narrative_role.standalone),
    ]))

    parts.append(_section("CREATIVE UTILITY", [
        _field("pairs_with", doc.creative_utility.pairs_with),
        _field("conflicts_with", doc.creative_utility.conflicts_with),
        _field("grade_notes", doc.creative_utility.grade_notes),
        _field("edit_notes", doc.creative_utility.edit_notes),
        _field("avoid", doc.creative_utility.avoid),
    ]))

    return "".join(parts)


def _render_image_doc(doc: ImageDoc) -> str:
    parts: list[str] = [f"# {doc.identity.file}\n"]

    parts.append(_section("IDENTITY", [
        _field("file", doc.identity.file),
        _field("resolution", doc.identity.resolution),
        _field("aspect_ratio", doc.identity.aspect_ratio),
        _field("source", doc.identity.source),
    ]))

    parts.append(_section("TECHNICAL", [
        _field("color_space", doc.technical.color_space),
        _field("dynamic_range", doc.technical.dynamic_range),
        _field("sharpness", doc.technical.sharpness),
        _field("grain", doc.technical.grain),
    ]))

    parts.append(_section("COMPOSITION", [
        _field("rule", doc.composition.rule.value if doc.composition.rule else None),
        _field("subject_position", doc.composition.subject_position),
        _field("foreground", doc.composition.depth_layers.foreground),
        _field("midground", doc.composition.depth_layers.midground),
        _field("background", doc.composition.depth_layers.background),
        _field("negative_space", doc.composition.negative_space),
        _field("leading_lines", doc.composition.leading_lines),
        _field("perspective", doc.composition.perspective.value if doc.composition.perspective else None),
        _field("depth_of_field", doc.composition.depth_of_field),
    ]))

    parts.append(_section("COLOR", [
        _field("palette", doc.color.palette),
        _field("temperature", doc.color.temperature.value if doc.color.temperature else None),
        _field("contrast", doc.color.contrast.value if doc.color.contrast else None),
        _field("saturation", doc.color.saturation.value if doc.color.saturation else None),
        _field("tonal_key", doc.color.tonal_key.value if doc.color.tonal_key else None),
        _field("color_relationships", doc.color.color_relationships),
    ]))

    parts.append(_section("LIGHTING", [
        _field("source", doc.lighting.source),
        _field("quality", doc.lighting.quality),
        _field("direction", doc.lighting.direction),
        _field("shadows", doc.lighting.shadows),
        _field("highlights", doc.lighting.highlights),
    ]))

    parts.append(_section("CONTENT", [
        _field("primary_subject", doc.content.primary_subject),
        _field("secondary_elements", doc.content.secondary_elements),
        _field("setting", doc.content.setting),
        _field("human_presence", doc.content.human_presence),
        _field("emotion_displayed", doc.content.emotion_displayed),
        _field("moment", doc.content.moment),
    ]))

    parts.append(_section("AESTHETIC", [
        _field("genre", doc.aesthetic.genre),
        _field("era_feel", doc.aesthetic.era_feel),
        _field("processing", doc.aesthetic.processing),
        _field("texture_character", doc.aesthetic.texture_character),
    ]))

    parts.append(_section("EMOTIONAL REGISTER", [
        _field("primary_mood", doc.emotional_register.primary_mood),
        _field("secondary_moods", doc.emotional_register.secondary_moods),
        _field("intensity", doc.emotional_register.intensity.value if doc.emotional_register.intensity else None),
        _field("what_it_communicates", doc.emotional_register.what_it_communicates),
    ]))

    parts.append(_section("CREATIVE UTILITY", [
        _field("use_as", doc.creative_utility.use_as),
        _field("grade_inspiration", doc.creative_utility.grade_inspiration),
        _field("pairs_with_video", doc.creative_utility.pairs_with_video),
        _field("reference_notes", doc.creative_utility.reference_notes),
    ]))

    return "".join(parts)


def _render_audio_doc(doc: AudioDoc) -> str:
    parts: list[str] = [f"# {doc.identity.file}\n"]

    parts.append(_section("IDENTITY", [
        _field("file", doc.identity.file),
        _field("duration", doc.identity.duration),
        _field("type", doc.identity.type.value),
        _field("source", doc.identity.source),
        _field("artist_title", doc.identity.artist_title),
    ]))

    parts.append(_section("TECHNICAL", [
        _field("sample_rate", doc.technical.sample_rate),
        _field("bit_depth", doc.technical.bit_depth),
        _field("channels", doc.technical.channels),
        _field("bpm", doc.technical.bpm),
        _field("key", doc.technical.key),
        _field("time_signature", doc.technical.time_signature),
    ]))

    if doc.structure.sections:
        rows = ["| Section | Start | End | Description |\n", "|---|---|---|---|\n"]
        for s in doc.structure.sections:
            rows.append(f"| {s.name} | {s.start} | {s.end} | {s.description} |\n")
        parts.append(_section("STRUCTURE", rows))

    parts.append(_section("SONIC CHARACTER", [
        _field("primary_sources", doc.sonic_character.primary_sources),
        _field("texture", doc.sonic_character.texture),
        _field("frequency_profile", doc.sonic_character.frequency_profile),
        _field("dynamic_range", doc.sonic_character.dynamic_range),
        _field("stereo_field", doc.sonic_character.stereo_field),
        _field("vocal_presence", doc.sonic_character.vocal_presence),
    ]))

    energy_lines: list[str] = [
        _field("overall_energy", doc.energy_profile.overall_energy),
        _field("energy_arc", doc.energy_profile.energy_arc),
    ]
    if doc.energy_profile.peak_moments:
        energy_lines.append("**peak_moments:**\n")
        for m in doc.energy_profile.peak_moments:
            energy_lines.append(f"- `{m.timestamp}` {m.description}\n")
    if doc.energy_profile.quiet_moments:
        energy_lines.append("**quiet_moments:**\n")
        for m in doc.energy_profile.quiet_moments:
            energy_lines.append(f"- `{m.timestamp}` {m.description}\n")
    if doc.energy_profile.tension_points:
        energy_lines.append("**tension_points:**\n")
        for m in doc.energy_profile.tension_points:
            energy_lines.append(f"- `{m.timestamp}` {m.description}\n")
    parts.append(_section("ENERGY PROFILE", energy_lines))

    parts.append(_section("EMOTIONAL REGISTER", [
        _field("primary_mood", doc.emotional_register.primary_mood),
        _field("secondary_moods", doc.emotional_register.secondary_moods),
        _field("emotional_arc", doc.emotional_register.emotional_arc),
        _field("intensity", doc.emotional_register.intensity.value if doc.emotional_register.intensity else None),
        _field("cultural_context", doc.emotional_register.cultural_context),
    ]))

    parts.append(_section("EDIT UTILITY", [
        _field("natural_cutpoints", doc.edit_utility.natural_cutpoints),
        _field("loop_points", doc.edit_utility.loop_points),
        _field("recommended_clip_in", doc.edit_utility.recommended_clip_in),
        _field("recommended_clip_out", doc.edit_utility.recommended_clip_out),
        _field("works_as", doc.edit_utility.works_as),
        _field("pacing_suggestion", doc.edit_utility.pacing_suggestion),
        _field("sync_opportunities", doc.edit_utility.sync_opportunities),
    ]))

    parts.append(_section("CREATIVE UTILITY", [
        _field("pairs_with_visual", doc.creative_utility.pairs_with_visual),
        _field("avoid_pairing_with", doc.creative_utility.avoid_pairing_with),
        _field("reference_context", doc.creative_utility.reference_context),
        _field("notes", doc.creative_utility.notes),
    ]))

    return "".join(parts)


def render_doc(doc: AnyDoc) -> str:
    if isinstance(doc, VideoDoc):
        return _render_video_doc(doc)
    if isinstance(doc, ImageDoc):
        return _render_image_doc(doc)
    if isinstance(doc, AudioDoc):
        return _render_audio_doc(doc)
    raise TypeError(f"Unknown doc type: {type(doc)}")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_doc(doc: AnyDoc, media_path: str | Path) -> None:
    md_path = doc_path_for(media_path)
    meta_path = meta_path_for(media_path)

    md_path.write_text(render_doc(doc))

    raw = json.loads(doc.model_dump_json())
    raw[_DOC_TYPE_KEY] = type(doc).__name__
    meta_path.write_text(json.dumps(raw, indent=2))


def load_doc(media_path: str | Path) -> AnyDoc | None:
    meta_path = meta_path_for(media_path)
    if not meta_path.exists():
        return None

    raw = json.loads(meta_path.read_text())
    doc_type = raw.pop(_DOC_TYPE_KEY, None)

    if doc_type == "VideoDoc" or "shot_spatial" in raw:
        return VideoDoc.model_validate(raw)
    if doc_type == "ImageDoc" or "composition" in raw:
        return ImageDoc.model_validate(raw)
    if doc_type == "AudioDoc" or "structure" in raw:
        return AudioDoc.model_validate(raw)

    raise ValueError(f"Cannot determine doc type from {meta_path}")


def _infer_doc_type_from_extension(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return "VideoDoc"
    if ext in AUDIO_EXTENSIONS:
        return "AudioDoc"
    return "ImageDoc"


# ---------------------------------------------------------------------------
# MCP-level operations
# ---------------------------------------------------------------------------

def create_media_doc(media_path: str, doc_data: dict) -> dict:
    path = Path(media_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Media file not found: {media_path}")

    doc_type = _infer_doc_type_from_extension(path)

    if doc_type == "VideoDoc":
        doc: AnyDoc = VideoDoc.model_validate(doc_data)
    elif doc_type == "AudioDoc":
        doc = AudioDoc.model_validate(doc_data)
    else:
        doc = ImageDoc.model_validate(doc_data)

    save_doc(doc, path)

    return {
        "ok": True,
        "doc_type": doc_type,
        "doc_path": doc_path_for(path).as_posix(),
        "meta_path": meta_path_for(path).as_posix(),
    }


def get_media_doc(media_path: str) -> dict:
    path = Path(media_path).expanduser().resolve()
    doc = load_doc(path)
    if doc is None:
        raise FileNotFoundError(f"No comprehension document found for: {media_path}")

    return {
        "ok": True,
        "doc": json.loads(doc.model_dump_json()),
        "doc_type": type(doc).__name__,
        "doc_path": doc_path_for(path).as_posix(),
        "meta_path": meta_path_for(path).as_posix(),
    }


def list_media_docs(directory: str) -> dict:
    root = Path(directory).expanduser().resolve()
    if not root.exists():
        return {"ok": True, "docs": [], "count": 0}

    results = []
    for meta_file in sorted(root.rglob(f"*{META_SUFFIX}")):
        media_file = Path(str(meta_file)[: -len(META_SUFFIX)])
        if not media_file.exists():
            continue
        raw = json.loads(meta_file.read_text())
        doc_type = raw.get(_DOC_TYPE_KEY, "unknown")
        results.append({
            "media_path": media_file.as_posix(),
            "doc_path": doc_path_for(media_file).as_posix(),
            "doc_type": doc_type,
        })

    return {"ok": True, "docs": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Phase D — Auto-generation
# ---------------------------------------------------------------------------

def _seconds_to_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def auto_generate_doc(media_path: str) -> dict:
    path = Path(media_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {media_path}")

    ext = path.suffix.lower()

    if ext in VIDEO_EXTENSIONS:
        return _auto_generate_video(path)
    if ext in AUDIO_EXTENSIONS:
        return _auto_generate_audio(path)
    if ext in IMAGE_EXTENSIONS:
        return _auto_generate_image(path)

    raise ValueError(f"Unsupported file extension '{ext}' for auto-generation")


def _auto_generate_video(path: Path) -> dict:
    meta = analyze_video_metadata(str(path))
    thumb = generate_thumbnails(str(path), count=5)

    duration_s = meta.get("duration_seconds") or 0
    width = meta.get("width") or 0
    height = meta.get("height") or 0
    fps = meta.get("fps") or 0.0

    prefilled = {
        "identity": {
            "file": path.name,
            "duration": _seconds_to_timestamp(duration_s),
            "source": None,
            "captured": None,
        },
        "technical": {
            "resolution": f"{width}x{height}" if width and height else "unknown",
            "aspect_ratio": meta.get("aspect_ratio") or "unknown",
            "fps": fps,
            "color_space": meta.get("color_space"),
            "dynamic_range": "SDR",
            "stabilized": None,
            "has_audio": meta.get("has_audio", False),
        },
    }

    keyframe_paths = []
    if thumb.get("ok") and thumb.get("thumbnails"):
        keyframe_paths = thumb["thumbnails"]

    return {
        "ok": True,
        "type": "video",
        "prefilled": prefilled,
        "keyframe_paths": keyframe_paths,
        "remaining_sections": [
            "shot_spatial", "shot_movement", "color", "lighting",
            "content", "embedded_audio", "temporal_map",
            "emotional_register", "narrative_role", "creative_utility",
        ],
        "instructions": (
            "Analyze the keyframe images to fill the remaining sections, "
            "then call create_media_doc with the complete doc_data."
        ),
    }


def _auto_generate_audio(path: Path) -> dict:
    meta = analyze_audio_metadata(str(path))
    beats = analyze_beats(str(path))

    duration_s = meta.get("duration_seconds") or 0
    bpm = beats.get("tempo") if beats.get("ok") else None

    sections = []
    if duration_s:
        sections = [{"name": "full", "start": "0:00", "end": _seconds_to_timestamp(duration_s), "description": ""}]

    prefilled = {
        "identity": {
            "file": path.name,
            "duration": _seconds_to_timestamp(duration_s),
            "type": "music",
            "source": None,
            "artist_title": None,
        },
        "technical": {
            "sample_rate": meta.get("sample_rate"),
            "bit_depth": meta.get("bit_depth"),
            "channels": meta.get("channels"),
            "bpm": round(bpm, 1) if bpm else None,
            "key": None,
            "time_signature": None,
        },
        "structure": {"sections": sections},
        "edit_utility": {
            "sync_opportunities": [
                _seconds_to_timestamp(t) for t in (beats.get("beat_times") or [])[:20]
            ],
        },
    }

    return {
        "ok": True,
        "type": "audio",
        "prefilled": prefilled,
        "keyframe_paths": [],
        "remaining_sections": [
            "sonic_character", "energy_profile", "emotional_register", "creative_utility",
            "edit_utility (natural_cutpoints, loop_points, works_as, pacing_suggestion)",
            "structure (refine section names and descriptions)",
        ],
        "instructions": (
            "Listen to the audio to fill the remaining sections, "
            "then call create_media_doc with the complete doc_data."
        ),
    }


def _auto_generate_image(path: Path) -> dict:
    try:
        if Image is None:
            raise ImportError("Pillow not installed")
        with Image.open(path) as img:
            width, height = img.size
            color_space = img.mode
    except Exception:
        width, height, color_space = 0, 0, None

    from fractions import Fraction
    aspect = ""
    if width and height:
        r = Fraction(width, height).limit_denominator(20)
        aspect = f"{r.numerator}:{r.denominator}"

    prefilled = {
        "identity": {
            "file": path.name,
            "resolution": f"{width}x{height}" if width and height else "unknown",
            "aspect_ratio": aspect or "unknown",
            "source": None,
        },
        "technical": {
            "color_space": color_space,
            "dynamic_range": None,
            "sharpness": None,
            "grain": None,
        },
    }

    return {
        "ok": True,
        "type": "image",
        "prefilled": prefilled,
        "keyframe_paths": [str(path)],
        "remaining_sections": [
            "composition", "color", "lighting", "content",
            "aesthetic", "emotional_register", "creative_utility",
        ],
        "instructions": (
            "Analyze the image to fill the remaining sections, "
            "then call create_media_doc with the complete doc_data."
        ),
    }
