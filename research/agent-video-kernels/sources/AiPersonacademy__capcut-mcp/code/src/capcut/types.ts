export interface TimeRange {
  start: number; // in microseconds (1 second = 1,000,000 us)
  duration: number; // in microseconds
}

export interface ClipTransform {
  scale: {
    x: number;
    y: number;
  };
  rotation: number;
  transform: {
    x: number; // normalized coordinate [-1.0, 1.0]
    y: number; // normalized coordinate [-1.0, 1.0]
  };
  flip: {
    vertical: boolean;
    horizontal: boolean;
  };
  alpha: number; // 0.0 to 1.0
}

export interface CanvasConfig {
  ratio: string; // '9:16', '16:9', '1:1', 'original', etc.
  width: number;
  height: number;
  background?: string | null;
}

export interface VideoMaterial {
  id: string;
  unique_id?: string;
  type: 'video' | 'photo';
  duration: number; // in microseconds
  path: string;
  width: number;
  height: number;
  has_audio: boolean;
  material_name?: string;
  category_name?: string;
  category_id?: string;
  crop?: {
    upper_left_x: number;
    upper_left_y: number;
    upper_right_x: number;
    upper_right_y: number;
    lower_left_x: number;
    lower_left_y: number;
    lower_right_x: number;
    lower_right_y: number;
  };
  crop_scale?: number;
  crop_ratio?: string;
  [key: string]: unknown;
}

export interface AudioMaterial {
  id: string;
  unique_id?: string;
  type: 'extract_music' | 'music' | 'sound_effect' | 'record';
  name: string;
  duration: number; // in microseconds
  path: string;
  category_name?: string;
  [key: string]: unknown;
}

export interface TextMaterialStyle {
  fill?: {
    content?: {
      render_type?: string;
      solid?: {
        color?: number[]; // [r, g, b] in 0..1
      };
    };
  };
  font?: {
    path?: string;
    id?: string;
  };
  strokes?: Array<{
    content?: {
      render_type?: string;
      solid?: {
        color?: number[];
      };
    };
    width?: number;
    mode?: number;
  }>;
  size?: number;
  useLetterColor?: boolean;
  range?: [number, number];
}

export interface TextMaterial {
  id: string;
  name?: string;
  type: 'text';
  content: string; // JSON string with { text: string, styles?: TextMaterialStyle[] }
  font_size?: number;
  text_color?: string; // hex color e.g. '#ffffffff'
  border_color?: string;
  border_width?: number;
  alignment?: number; // 0=left, 1=center, 2=right
  global_alpha?: number;
  words?: {
    start_time: number[];
    end_time: number[];
    text: string[];
  };
  [key: string]: unknown;
}

export interface DraftMaterials {
  videos: VideoMaterial[];
  audios: AudioMaterial[];
  texts: TextMaterial[];
  effects?: unknown[];
  stickers?: unknown[];
  transitions?: unknown[];
  speeds?: SpeedMaterial[];
  canvases?: unknown[];
  text_templates?: unknown[];
  audio_fades?: AudioFadeMaterial[];
  [key: string]: unknown;
}

export interface DraftSegment {
  id: string;
  material_id: string;
  source_timerange: TimeRange | null;
  target_timerange: TimeRange;
  render_timerange?: TimeRange;
  desc?: string;
  state?: number;
  speed: number;
  volume: number;
  clip?: ClipTransform | null;
  extra_material_refs?: string[];
  visible?: boolean;
  [key: string]: unknown;
}

export type TrackType = 'video' | 'audio' | 'text' | 'effect' | 'sticker' | 'filter';

export interface DraftTrack {
  id: string;
  type: TrackType;
  segments: DraftSegment[];
  flag?: number;
  attribute?: number;
  name?: string;
  is_default_name?: boolean;
}

export interface DraftContent {
  id: string;
  version?: number;
  new_version?: string;
  name?: string;
  duration: number; // in microseconds
  create_time?: number;
  update_time?: number;
  fps: number;
  canvas_config: CanvasConfig;
  tracks: DraftTrack[];
  materials: DraftMaterials;
  [key: string]: unknown;
}

export interface DraftMaterialMeta {
  id: string;
  file_Path: string;
  duration: number;
  extra_info?: string;
  metetype: 'video' | 'photo' | 'music' | 'none';
  width: number;
  height: number;
  create_time?: number;
  import_time?: number;
  roughcut_time_range?: TimeRange;
  sub_time_range?: TimeRange;
  type?: number;
}

export interface DraftMetaInfo {
  draft_id: string;
  draft_name: string;
  draft_fold_path: string;
  draft_root_path?: string;
  draft_cover?: string;
  tm_duration: number;
  tm_draft_create?: number;
  tm_draft_modified?: number;
  draft_materials?: Array<{
    type: number;
    value: DraftMaterialMeta[];
  }>;
  [key: string]: unknown;
}

export interface RootDraftStoreItem {
  draft_id: string;
  draft_name: string;
  draft_fold_path: string;
  draft_json_file: string;
  draft_cover: string;
  tm_duration: number; // in microseconds
  tm_draft_create: number;
  tm_draft_modified: number;
  tm_draft_removed?: number;
  draft_root_path?: string;
  [key: string]: unknown;
}

export interface RootMetaInfo {
  all_draft_store: RootDraftStoreItem[];
  draft_ids?: number;
  root_path?: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  path: string;
  durationSeconds: number;
  durationFormatted: string;
  resolution: string;
  ratio: string;
  fps: number;
  tracksCount: number;
  videoTracksCount: number;
  audioTracksCount: number;
  textTracksCount: number;
  isLocked: boolean;
  createTime?: string;
  modifiedTime?: string;
}

export interface CreateProjectOptions {
  name: string;
  ratio?: '9:16' | '16:9' | '1:1' | '4:3' | 'original';
  width?: number;
  height?: number;
  fps?: number;
}

export interface AddVideoClipOptions {
  projectNameOrId: string;
  filePath: string;
  trackIndex?: number;
  startTimeSeconds?: number | 'auto_append';
  durationSeconds?: number;
  sourceStartSeconds?: number;
  scale?: number;
  x?: number; // normalized -1.0 to 1.0
  y?: number; // normalized -1.0 to 1.0
  rotation?: number;
  opacity?: number; // 0.0 to 1.0
}

export interface AddAudioClipOptions {
  projectNameOrId: string;
  filePath: string;
  trackIndex?: number;
  startTimeSeconds?: number | 'auto_append';
  durationSeconds?: number;
  sourceStartSeconds?: number;
  volume?: number; // 1.0 = 100%
}

export interface AddTextOptions {
  projectNameOrId: string;
  text: string;
  trackIndex?: number;
  startTimeSeconds?: number | 'auto_append';
  durationSeconds?: number;
  fontSize?: number;
  textColor?: string; // hex or '#ffffffff'
  borderColor?: string;
  borderWidth?: number;
  alignment?: 'left' | 'center' | 'right';
  x?: number;
  y?: number;
}

export interface SubtitleItem {
  startTimeSeconds: number;
  endTimeSeconds: number;
  text: string;
}

export interface AddSubtitlesOptions {
  projectNameOrId: string;
  subtitles?: SubtitleItem[];
  srtContent?: string;
  srtFilePath?: string;
  fontSize?: number;
  textColor?: string;
  borderColor?: string;
  borderWidth?: number;
  y?: number;
}

export interface TransitionMaterial {
  id: string;
  name: string;
  type: 'transition';
  category_name: string;
  category_id?: string;
  duration: number; // in microseconds
  path?: string;
  effect_id: string;
  resource_id: string;
  is_overlap?: boolean;
  [key: string]: unknown;
}

export interface VideoKeyframe {
  id: string;
  property_type: string;
  time_offset: number; // in microseconds
  values: number[];
  [key: string]: unknown;
}

export interface AddTransitionOptions {
  projectNameOrId: string;
  segmentId: string;
  transitionName?: 'Dissolve' | 'Fade to Black' | 'Fade to White' | 'Slide Left' | 'Zoom In' | string;
  durationSeconds?: number;
}

export interface AddKeyframeOptions {
  projectNameOrId: string;
  segmentId: string;
  property: 'scale' | 'x' | 'y' | 'rotation' | 'alpha';
  timeOffsetSeconds: number;
  value: number;
}

export interface AddStickerOptions {
  projectNameOrId: string;
  stickerName: string;
  trackIndex?: number;
  startTimeSeconds?: number | 'auto_append';
  durationSeconds?: number;
  x?: number;
  y?: number;
  scale?: number;
}

export interface GeneratePreviewOptions {
  projectNameOrId: string;
  outputPath?: string;
  width?: number;
  height?: number;
  fps?: number;
}

export interface AudioFadeMaterial {
  id: string;
  type: 'audio_fade';
  fade_type: number; // 0 = standard
  fade_in_duration: number; // microseconds
  fade_out_duration: number; // microseconds
  [key: string]: unknown;
}

export interface SpeedMaterial {
  id: string;
  type: 'speed';
  mode: number;
  speed: number;
  curve_speed?: unknown | null;
  [key: string]: unknown;
}

export interface SplitClipOptions {
  projectNameOrId: string;
  segmentId: string;
  splitTimeSeconds: number;
}

export interface SetClipSpeedOptions {
  projectNameOrId: string;
  segmentId: string;
  speed: number;
  preservePitch?: boolean;
}

export interface AddAudioFadeOptions {
  projectNameOrId: string;
  segmentId: string;
  fadeInSeconds?: number;
  fadeOutSeconds?: number;
}

export interface AddViralCaptionOptions {
  projectNameOrId: string;
  text: string;
  powerWords?: string[];
  fontFamily?: 'Montserrat' | 'Poppins' | 'Helvetica' | 'Arial' | string;
  accentColor?: string; // e.g. '#FF1E27', '#FFD700'
  enableHoverPop?: boolean;
  trackIndex?: number;
  startTimeSeconds?: number | 'auto_append';
  durationSeconds?: number;
  fontSize?: number;
  x?: number;
  y?: number;
}

export interface CreateVideoBridgeOptions {
  projectName: string;
  videoPlatePath: string;
  audioTracks?: Array<{
    filePath: string;
    volume?: number;
    trackIndex?: number;
  }>;
  subtitlesSrtPath?: string;
  ratio?: '9:16' | '16:9' | '1:1' | 'original';
  fps?: number;
}

export interface AddSoundEffectOptions {
  projectNameOrId: string;
  sfxFilePath: string;
  timestampSeconds: number;
  volume?: number;
  trackIndex?: number;
}


