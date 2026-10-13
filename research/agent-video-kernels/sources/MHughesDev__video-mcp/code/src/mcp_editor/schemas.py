from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Platform(str, Enum):
    widescreen = "16:9"
    vertical = "9:16"
    square = "1:1"


PLATFORM_DIMENSIONS: dict[Platform, tuple[int, int]] = {
    Platform.widescreen: (1920, 1080),
    Platform.vertical: (1080, 1920),
    Platform.square: (1080, 1080),
}


class MediaStream(BaseModel):
    index: int
    codec_type: str
    codec_name: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    r_frame_rate: str | None = None


class MediaProbe(BaseModel):
    path: str
    exists: bool
    ok: bool
    duration: float | None = None
    format_name: str | None = None
    bit_rate: int | None = None
    streams: list[MediaStream] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    suggested_fix: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @property
    def has_video(self) -> bool:
        return any(stream.codec_type == "video" for stream in self.streams)

    @property
    def has_audio(self) -> bool:
        return any(stream.codec_type == "audio" for stream in self.streams)


class ClipEffect(BaseModel):
    effect_type: str
    params: dict[str, Any] = Field(default_factory=dict)


class TimelineClip(BaseModel):
    clip_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    source: str
    start: float = 0
    duration: float
    label: str | None = None
    effects: list[ClipEffect] = Field(default_factory=list)


class TimelineTransition(BaseModel):
    transition_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    from_clip_id: str
    to_clip_id: str
    transition_type: str = "crossfade"
    duration: float = 0.5


class EditPlanClip(BaseModel):
    source: str
    start: float = 0
    duration: float
    beat_time: float | None = None
    label: str | None = None


class BeatEditPlan(BaseModel):
    project_id: str
    platform: Platform = Platform.widescreen
    style: str = "medium"
    target_duration: float
    music_path: str | None = None
    tempo: float | None = None
    cut_points: list[float] = Field(default_factory=list)
    clips: list[EditPlanClip] = Field(default_factory=list)


class TimelinePlan(BaseModel):
    project_id: str
    platform: Platform = Platform.widescreen
    clips: list[TimelineClip]
    transitions: list[TimelineTransition] = Field(default_factory=list)
    music_path: str | None = None
    target_duration: float | None = None
    otio_path: str | None = None


class RenderedOutput(BaseModel):
    platform: Platform
    path: str
    ok: bool
    validation: dict[str, Any] = Field(default_factory=dict)
    render_manifest_path: str | None = None


class RenderCommand(BaseModel):
    stage: str
    command: list[str]
    output_path: str | None = None


class RenderManifest(BaseModel):
    project_id: str
    platform: Platform
    render_profile: str = "preview"
    output_path: str
    work_dir: str
    expected_duration: float
    dimensions: tuple[int, int]
    commands: list[RenderCommand] = Field(default_factory=list)
    segment_paths: list[str] = Field(default_factory=list)
    concat_file: str | None = None
    dry_run: bool = False
    timing: list[dict[str, Any]] = Field(default_factory=list)


class ProjectManifest(BaseModel):
    project_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    name: str
    prompt: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    input_dir: str = "data/input"
    music_path: str | None = None
    platforms: list[Platform] = Field(default_factory=lambda: [Platform.widescreen])
    assets: list[MediaProbe] = Field(default_factory=list)
    timelines: dict[str, TimelinePlan] = Field(default_factory=dict)
    edit_plans: dict[str, BeatEditPlan] = Field(default_factory=dict)
    outputs: dict[str, RenderedOutput] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Reference library
# ---------------------------------------------------------------------------

class ReferenceType(str, Enum):
    video = "video"
    image = "image"
    audio = "audio"


class ReferenceAsset(BaseModel):
    ref_id: str
    path: str
    type: ReferenceType
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    added_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    doc_path: str | None = None


class ReferencesManifest(BaseModel):
    references: list[ReferenceAsset] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Media comprehension documents — shared enums
# ---------------------------------------------------------------------------

class TemperatureValue(str, Enum):
    warm = "warm"
    neutral = "neutral"
    cool = "cool"


class ContrastValue(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class SaturationValue(str, Enum):
    desaturated = "desaturated"
    muted = "muted"
    natural = "natural"
    vivid = "vivid"


class IntensityValue(str, Enum):
    quiet = "quiet"
    moderate = "moderate"
    intense = "intense"
    overwhelming = "overwhelming"


class TonalKey(str, Enum):
    high_key = "high_key"
    balanced = "balanced"
    low_key = "low_key"


# ---------------------------------------------------------------------------
# VideoDoc
# ---------------------------------------------------------------------------

class VideoIdentity(BaseModel):
    file: str
    duration: str
    source: str | None = None
    captured: str | None = None


class VideoTechnical(BaseModel):
    resolution: str
    aspect_ratio: str
    fps: float
    color_space: str | None = None
    dynamic_range: str = "SDR"
    stabilized: bool | None = None
    has_audio: bool = False


class ShotScale(str, Enum):
    extreme_wide = "extreme_wide"
    wide = "wide"
    medium_wide = "medium_wide"
    medium = "medium"
    medium_close = "medium_close"
    close = "close"
    extreme_close = "extreme_close"
    macro = "macro"


class CameraAngle(str, Enum):
    eye_level = "eye_level"
    high = "high"
    low = "low"
    birds_eye = "birds_eye"
    worms_eye = "worms_eye"
    dutch = "dutch"


class CameraMovement(str, Enum):
    static = "static"
    pan = "pan"
    tilt = "tilt"
    dolly = "dolly"
    zoom = "zoom"
    handheld = "handheld"
    gimbal = "gimbal"
    aerial = "aerial"


class VideoShotSpatial(BaseModel):
    scale: ShotScale | None = None
    angle: CameraAngle | None = None
    depth_of_field: str | None = None
    composition: str = ""


class VideoShotMovement(BaseModel):
    camera: CameraMovement | None = None
    subject_motion: str | None = None
    overall_pace: str | None = None
    energy_arc: str = ""


class VideoColor(BaseModel):
    palette: list[str] = Field(default_factory=list)
    temperature: TemperatureValue | None = None
    contrast: ContrastValue | None = None
    saturation: SaturationValue | None = None
    tonal_key: TonalKey | None = None
    grade_character: str | None = None


class VideoLighting(BaseModel):
    source: str | None = None
    quality: str | None = None
    direction: str | None = None
    time_of_day: str | None = None
    shadow_character: str | None = None


class VideoContent(BaseModel):
    primary_subject: str = ""
    secondary: list[str] = Field(default_factory=list)
    setting: str = ""
    action: str = ""
    human_presence: str | None = None
    emotion_displayed: str | None = None


class VideoEmbeddedAudio(BaseModel):
    ambient: str | None = None
    dialogue: str | None = None
    music: str | None = None
    audio_quality: str | None = None
    silence_at: list[str] = Field(default_factory=list)


class TemporalSegment(BaseModel):
    start: str
    end: str
    description: str


class VideoTemporalMap(BaseModel):
    segments: list[TemporalSegment] = Field(default_factory=list)
    natural_cutpoints: list[str] = Field(default_factory=list)
    energy_arc: str = ""


class VideoEmotionalRegister(BaseModel):
    primary_emotion: str = ""
    secondary: list[str] = Field(default_factory=list)
    intensity: IntensityValue | None = None
    viewer_effect: str = ""


class VideoNarrativeRole(BaseModel):
    best_as: list[str] = Field(default_factory=list)
    narrative_weight: str | None = None
    standalone: bool | None = None


class VideoCreativeUtility(BaseModel):
    pairs_with: str = ""
    conflicts_with: str | None = None
    grade_notes: str | None = None
    edit_notes: str | None = None
    avoid: str | None = None


class VideoDoc(BaseModel):
    identity: VideoIdentity
    technical: VideoTechnical
    shot_spatial: VideoShotSpatial = Field(default_factory=VideoShotSpatial)
    shot_movement: VideoShotMovement = Field(default_factory=VideoShotMovement)
    color: VideoColor = Field(default_factory=VideoColor)
    lighting: VideoLighting = Field(default_factory=VideoLighting)
    content: VideoContent = Field(default_factory=VideoContent)
    embedded_audio: VideoEmbeddedAudio = Field(default_factory=VideoEmbeddedAudio)
    temporal_map: VideoTemporalMap = Field(default_factory=VideoTemporalMap)
    emotional_register: VideoEmotionalRegister = Field(default_factory=VideoEmotionalRegister)
    narrative_role: VideoNarrativeRole = Field(default_factory=VideoNarrativeRole)
    creative_utility: VideoCreativeUtility = Field(default_factory=VideoCreativeUtility)


# ---------------------------------------------------------------------------
# ImageDoc
# ---------------------------------------------------------------------------

class FramingRule(str, Enum):
    thirds = "thirds"
    centered = "centered"
    golden_ratio = "golden_ratio"
    diagonal = "diagonal"
    symmetrical = "symmetrical"
    unconventional = "unconventional"


class Perspective(str, Enum):
    eye_level = "eye_level"
    high = "high"
    low = "low"
    aerial = "aerial"
    worms_eye = "worms_eye"


class ImageIdentity(BaseModel):
    file: str
    resolution: str
    aspect_ratio: str
    source: str | None = None


class ImageTechnical(BaseModel):
    color_space: str | None = None
    dynamic_range: str | None = None
    sharpness: str | None = None
    grain: str | None = None


class DepthLayers(BaseModel):
    foreground: str | None = None
    midground: str | None = None
    background: str | None = None


class ImageComposition(BaseModel):
    rule: FramingRule | None = None
    subject_position: str = ""
    depth_layers: DepthLayers = Field(default_factory=DepthLayers)
    negative_space: str | None = None
    leading_lines: str | None = None
    perspective: Perspective | None = None
    depth_of_field: str | None = None


class ImageColor(BaseModel):
    palette: list[str] = Field(default_factory=list)
    temperature: TemperatureValue | None = None
    contrast: ContrastValue | None = None
    saturation: SaturationValue | None = None
    tonal_key: TonalKey | None = None
    color_relationships: str | None = None


class ImageLighting(BaseModel):
    source: str | None = None
    quality: str | None = None
    direction: str | None = None
    shadows: str | None = None
    highlights: str | None = None


class ImageContent(BaseModel):
    primary_subject: str = ""
    secondary_elements: list[str] = Field(default_factory=list)
    setting: str = ""
    human_presence: str | None = None
    emotion_displayed: str | None = None
    moment: str = ""


class ImageAesthetic(BaseModel):
    genre: str | None = None
    era_feel: str | None = None
    processing: str | None = None
    texture_character: str | None = None


class ImageEmotionalRegister(BaseModel):
    primary_mood: str = ""
    secondary_moods: list[str] = Field(default_factory=list)
    intensity: IntensityValue | None = None
    what_it_communicates: str = ""


class ImageCreativeUtility(BaseModel):
    use_as: list[str] = Field(default_factory=list)
    grade_inspiration: str | None = None
    pairs_with_video: str | None = None
    reference_notes: str | None = None


class ImageDoc(BaseModel):
    identity: ImageIdentity
    technical: ImageTechnical = Field(default_factory=ImageTechnical)
    composition: ImageComposition = Field(default_factory=ImageComposition)
    color: ImageColor = Field(default_factory=ImageColor)
    lighting: ImageLighting = Field(default_factory=ImageLighting)
    content: ImageContent = Field(default_factory=ImageContent)
    aesthetic: ImageAesthetic = Field(default_factory=ImageAesthetic)
    emotional_register: ImageEmotionalRegister = Field(default_factory=ImageEmotionalRegister)
    creative_utility: ImageCreativeUtility = Field(default_factory=ImageCreativeUtility)


# ---------------------------------------------------------------------------
# AudioDoc
# ---------------------------------------------------------------------------

class AudioType(str, Enum):
    music = "music"
    ambient = "ambient"
    sfx = "sfx"
    voiceover = "voiceover"
    field_recording = "field_recording"
    mixed = "mixed"


class AudioIdentity(BaseModel):
    file: str
    duration: str
    type: AudioType = AudioType.music
    source: str | None = None
    artist_title: str | None = None


class AudioTechnical(BaseModel):
    sample_rate: int | None = None
    bit_depth: int | None = None
    channels: str | None = None
    bpm: float | None = None
    key: str | None = None
    time_signature: str | None = None


class AudioSection(BaseModel):
    name: str
    start: str
    end: str
    description: str = ""


class AudioStructure(BaseModel):
    sections: list[AudioSection] = Field(default_factory=list)


class AudioSonicCharacter(BaseModel):
    primary_sources: list[str] = Field(default_factory=list)
    texture: str | None = None
    frequency_profile: str | None = None
    dynamic_range: str | None = None
    stereo_field: str | None = None
    vocal_presence: str | None = None


class EnergyMoment(BaseModel):
    timestamp: str
    description: str = ""


class AudioEnergyProfile(BaseModel):
    overall_energy: str | None = None
    energy_arc: str = ""
    peak_moments: list[EnergyMoment] = Field(default_factory=list)
    quiet_moments: list[EnergyMoment] = Field(default_factory=list)
    tension_points: list[EnergyMoment] = Field(default_factory=list)


class AudioEmotionalRegister(BaseModel):
    primary_mood: str = ""
    secondary_moods: list[str] = Field(default_factory=list)
    emotional_arc: str = ""
    intensity: IntensityValue | None = None
    cultural_context: str | None = None


class AudioEditUtility(BaseModel):
    natural_cutpoints: list[str] = Field(default_factory=list)
    loop_points: list[str] = Field(default_factory=list)
    recommended_clip_in: str | None = None
    recommended_clip_out: str | None = None
    works_as: str | None = None
    pacing_suggestion: str | None = None
    sync_opportunities: list[str] = Field(default_factory=list)


class AudioCreativeUtility(BaseModel):
    pairs_with_visual: str = ""
    avoid_pairing_with: str | None = None
    reference_context: str | None = None
    notes: str | None = None


class AudioDoc(BaseModel):
    identity: AudioIdentity
    technical: AudioTechnical = Field(default_factory=AudioTechnical)
    structure: AudioStructure = Field(default_factory=AudioStructure)
    sonic_character: AudioSonicCharacter = Field(default_factory=AudioSonicCharacter)
    energy_profile: AudioEnergyProfile = Field(default_factory=AudioEnergyProfile)
    emotional_register: AudioEmotionalRegister = Field(default_factory=AudioEmotionalRegister)
    edit_utility: AudioEditUtility = Field(default_factory=AudioEditUtility)
    creative_utility: AudioCreativeUtility = Field(default_factory=AudioCreativeUtility)


def as_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def posix_path(value: str | Path) -> str:
    """Return a POSIX forward-slash path string for cross-platform manifest storage."""
    return Path(value).as_posix()


def deterministic_project_id(name: str, input_dir: str) -> str:
    """Return a stable 12-char hex ID derived from project name and input directory.

    Calling create_project twice with the same name + input_dir returns the same ID,
    preventing duplicate project directories on re-runs.
    """
    key = f"{name.strip().lower()}::{Path(input_dir).as_posix().lower()}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]
