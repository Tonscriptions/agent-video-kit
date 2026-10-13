import crypto from 'crypto';
import {
  DraftContent,
  DraftMetaInfo,
  DraftTrack,
  DraftSegment,
  VideoMaterial,
  AudioMaterial,
  TextMaterial,
  CanvasConfig,
  ClipTransform,
  TimeRange,
  TransitionMaterial,
  VideoKeyframe,
  AudioFadeMaterial,
  SpeedMaterial
} from './types.js';

export class DraftBuilder {
  /**
   * Generates a standard uppercase UUID formatted for CapCut.
   */
  public static generateId(): string {
    return crypto.randomUUID().toUpperCase();
  }

  /**
   * Generates an MD5-like 32-character hex ID.
   */
  public static generateHexId(): string {
    return crypto.randomBytes(16).toString('hex');
  }

  /**
   * Builds an empty base draft_content.json object.
   */
  public static createEmptyDraftContent(
    draftId: string,
    name: string,
    canvas: CanvasConfig,
    fps = 30.0
  ): DraftContent {
    const now = Date.now() * 1000; // microseconds timestamp

    return {
      id: draftId,
      version: 360000,
      new_version: '185.0.0',
      name,
      duration: 0,
      create_time: now,
      update_time: now,
      fps,
      is_drop_frame_timecode: false,
      color_space: 0,
      config: {
        adjust_max_index: 1,
        attachment_info: [],
        combination_max_index: 1,
        export_range: null,
        extract_audio_last_index: 1,
        lyrics_recognition_id: '',
        lyrics_sync: true,
        lyrics_taskinfo: [],
        maintrack_adsorb: true,
        material_save_mode: 0,
        original_sound_last_index: 1,
        record_audio_last_index: 1,
        sticker_max_index: 1,
        subtitle_recognition_id: '',
        subtitle_sync: true,
        subtitle_taskinfo: [],
        video_mute: false,
        zoom_info_params: null
      },
      canvas_config: canvas,
      tracks: [
        this.createTrack('video')
      ],
      group_container: null,
      materials: {
        flowers: [],
        videos: [],
        tail_leaders: [],
        audios: [],
        images: [],
        texts: [],
        effects: [],
        stickers: [],
        canvases: [],
        transitions: [],
        audio_effects: [],
        audio_fades: [],
        beats: [],
        material_animations: [],
        placeholders: [],
        placeholder_infos: [],
        speeds: [],
        common_mask: [],
        chromas: [],
        text_templates: [],
        realtime_denoises: [],
        audio_pannings: [],
        audio_pitch_shifts: [],
        video_trackings: [],
        hsl: [],
        drafts: [],
        color_curves: [],
        hsl_curves: [],
        primary_color_wheels: [],
        log_color_wheels: [],
        video_effects: [],
        ai_text_effects: [],
        audio_balances: [],
        handwrites: [],
        manual_deformations: [],
        manual_beautys: [],
        plugin_effects: [],
        sound_channel_mappings: [],
        green_screens: [],
        shapes: [],
        material_colors: [],
        digital_humans: [],
        digital_human_model_dressing: [],
        smart_crops: [],
        ai_translates: [],
        audio_track_indexes: [],
        loudnesses: [],
        vocal_beautifys: [],
        vocal_separations: [],
        smart_relights: [],
        time_marks: [],
        multi_language_refs: [],
        video_shadows: [],
        video_strokes: [],
        video_radius: []
      },
      keyframes: {
        adjusts: [],
        audios: [],
        effects: [],
        filters: [],
        handwrites: [],
        stickers: [],
        texts: [],
        videos: []
      },
      keyframe_graph_list: [],
      platform: {
        os: 'windows',
        os_version: '10.0.26200',
        app_id: 359289,
        app_version: '9.4.0',
        app_source: 'cc',
        device_id: this.generateHexId(),
        hard_disk_id: '',
        mac_address: this.generateHexId()
      },
      last_modified_platform: {
        os: 'windows',
        app_version: '9.4.0'
      },
      mutable_config: null,
      cover: '',
      retouch_cover: '',
      extra_info: null,
      relationships: [],
      mixed_track_mode_on: false,
      render_index_track_mode_on: false,
      free_render_index_mode_on: false,
      static_cover_image_path: '',
      source: 'default',
      time_marks: null,
      path: '',
      lyrics_effects: null,
      uneven_animation_template_info: null,
      draft_type: '',
      smart_ads_info: null,
      function_assistant_info: null
    };
  }

  /**
   * Builds an empty base draft_meta_info.json object.
   */
  public static createEmptyDraftMeta(
    draftId: string,
    name: string,
    folderPath: string,
    rootPath: string
  ): DraftMetaInfo {
    const nowSec = Math.floor(Date.now() / 1000);
    const nowUs = Date.now() * 1000;

    return {
      cloud_draft_cover: false,
      cloud_draft_sync: false,
      cloud_package_completed_time: '',
      draft_cloud_capcut_purchase_info: '',
      draft_cloud_last_action_download: false,
      draft_cloud_package_type: '',
      draft_cloud_purchase_info: '',
      draft_cloud_template_id: '',
      draft_cloud_tutorial_info: '',
      draft_cloud_videocut_purchase_info: '',
      draft_cover: 'draft_cover.jpg',
      draft_deeplink_url: '',
      draft_enterprise_info: {
        draft_enterprise_extra: '',
        draft_enterprise_id: '',
        draft_enterprise_name: '',
        enterprise_material: []
      },
      draft_fold_path: folderPath.replace(/\\/g, '/'),
      draft_has_unfinished_aigc_video_effect: false,
      draft_id: draftId,
      draft_is_ae_produce: false,
      draft_is_ai_packaging_used: false,
      draft_is_ai_shorts: false,
      draft_is_ai_translate: false,
      draft_is_article_video_draft: false,
      draft_is_cloud_temp_draft: false,
      draft_is_from_deeplink: 'false',
      draft_is_infinite_canvas_draft: false,
      draft_is_invisible: false,
      draft_is_pippit_draft: false,
      draft_is_web_article_video: false,
      draft_materials: [
        { type: 0, value: [] }, // video/image
        { type: 1, value: [] }, // audio
        { type: 2, value: [] }, // stickers
        { type: 3, value: [] }, // text
        { type: 6, value: [] },
        { type: 7, value: [] }
      ],
      draft_materials_copied_info: [],
      draft_name: name,
      draft_need_rename_folder: false,
      draft_new_version: '',
      draft_removable_storage_device: '',
      draft_root_path: rootPath.replace(/\//g, '\\'),
      draft_segment_extra_info: [],
      draft_timeline_materials_size_: 0,
      draft_type: '',
      draft_web_article_video_enter_from: '',
      pippit_avatar_url: '',
      pippit_extra_info: '',
      pippit_id: '',
      pippit_user_name: '',
      tm_draft_cloud_completed: '',
      tm_draft_cloud_entry_id: -1,
      tm_draft_cloud_modified: 0,
      tm_draft_cloud_parent_entry_id: -1,
      tm_draft_cloud_space_id: -1,
      tm_draft_cloud_user_id: -1,
      tm_draft_create: nowUs,
      tm_draft_modified: nowUs,
      tm_draft_removed: 0,
      tm_duration: 0
    };
  }

  /**
   * Creates a new track of given type.
   */
  public static createTrack(type: 'video' | 'audio' | 'text'): DraftTrack {
    return {
      id: this.generateId(),
      type,
      segments: [],
      flag: 0,
      attribute: 0,
      name: '',
      is_default_name: true
    };
  }

  /**
   * Constructs a VideoMaterial entry.
   */
  public static createVideoMaterial(
    materialId: string,
    filePath: string,
    durationUs: number,
    width: number,
    height: number,
    hasAudio: boolean,
    isImage: boolean
  ): VideoMaterial {
    const normPath = filePath.replace(/\\/g, '/');
    const fileName = normPath.split('/').pop() || 'media';

    return {
      id: materialId,
      unique_id: this.generateHexId(),
      type: isImage ? 'photo' : 'video',
      duration: durationUs,
      path: normPath,
      media_path: '',
      local_id: '',
      has_audio: hasAudio,
      reverse_path: '',
      intensifies_path: '',
      reverse_intensifies_path: '',
      intensifies_audio_path: '',
      cartoon_path: '',
      width,
      height,
      category_id: '',
      category_name: 'local',
      material_id: '',
      material_name: fileName,
      material_url: '',
      crop: {
        upper_left_x: 0.0,
        upper_left_y: 0.0,
        upper_right_x: 1.0,
        upper_right_y: 0.0,
        lower_left_x: 0.0,
        lower_left_y: 1.0,
        lower_right_x: 1.0,
        lower_right_y: 1.0
      },
      crop_ratio: 'free',
      audio_fade: null,
      crop_scale: 1.0,
      extra_type_option: 0,
      source: 0,
      source_platform: 0,
      formula_id: '',
      check_flag: 62978047
    };
  }

  /**
   * Constructs an AudioMaterial entry.
   */
  public static createAudioMaterial(
    materialId: string,
    filePath: string,
    durationUs: number
  ): AudioMaterial {
    const normPath = filePath.replace(/\\/g, '/');
    const fileName = normPath.split('/').pop() || 'audio';

    return {
      id: materialId,
      unique_id: this.generateHexId(),
      type: 'extract_music',
      name: fileName,
      duration: durationUs,
      path: normPath,
      category_name: 'local',
      wave_points: [],
      music_id: this.generateId().toLowerCase(),
      app_id: 0,
      text_id: '',
      tone_type: '',
      source_platform: 0,
      check_flag: 1,
      source_from: ''
    };
  }

  /**
   * Constructs a TextMaterial entry with customizable styling.
   */
  public static createTextMaterial(
    materialId: string,
    text: string,
    options: {
      fontSize?: number;
      textColor?: string;
      borderColor?: string;
      borderWidth?: number;
      alignment?: 'left' | 'center' | 'right';
    } = {}
  ): TextMaterial {
    const fontSize = options.fontSize || 12.0;
    const textColor = options.textColor || '#ffffffff';
    const borderColor = options.borderColor || '#000000ff';
    const borderWidth = options.borderWidth ?? 0.08;

    let alignNum = 1; // center
    if (options.alignment === 'left') alignNum = 0;
    if (options.alignment === 'right') alignNum = 2;

    const contentObj = {
      text,
      styles: [
        {
          fill: {
            content: {
              render_type: 'solid',
              solid: {
                color: [1.0, 1.0, 1.0]
              }
            }
          },
          strokes: [
            {
              content: {
                render_type: 'solid',
                solid: {
                  color: [0, 0, 0]
                }
              },
              width: borderWidth,
              mode: 0
            }
          ],
          size: fontSize,
          useLetterColor: true,
          range: [0, text.length]
        }
      ]
    };

    return {
      id: materialId,
      name: this.generateId(),
      type: 'text',
      content: JSON.stringify(contentObj),
      base_content: '',
      font_size: fontSize,
      text_color: textColor,
      text_alpha: 1.0,
      border_color: borderColor,
      border_width: borderWidth,
      border_mode: 0,
      border_alpha: 1.0,
      alignment: alignNum,
      line_feed: 1,
      global_alpha: 1.0,
      typesetting: 0,
      check_flag: 47
    };
  }

  /**
   * Constructs a DraftSegment for a video or image clip.
   */
  public static createVideoSegment(
    materialId: string,
    targetTimerange: TimeRange,
    sourceTimerange: TimeRange,
    transform?: Partial<ClipTransform>
  ): DraftSegment {
    const defaultClip: ClipTransform = {
      scale: { x: transform?.scale?.x ?? 1.0, y: transform?.scale?.y ?? 1.0 },
      rotation: transform?.rotation ?? 0.0,
      transform: { x: transform?.transform?.x ?? 0.0, y: transform?.transform?.y ?? 0.0 },
      flip: { vertical: false, horizontal: false },
      alpha: transform?.alpha ?? 1.0
    };

    return {
      id: this.generateId(),
      material_id: materialId,
      source_timerange: sourceTimerange,
      target_timerange: targetTimerange,
      render_timerange: { start: 0, duration: 0 },
      desc: '',
      state: 0,
      speed: 1.0,
      is_loop: false,
      is_tone_modify: false,
      reverse: false,
      intensifies_audio: false,
      cartoon: false,
      volume: 1.0,
      last_nonzero_volume: 1.0,
      clip: defaultClip,
      uniform_scale: { on: true, value: defaultClip.scale.x },
      extra_material_refs: [],
      render_index: 10000,
      keyframe_refs: [],
      visible: true,
      enable_color_curves: true,
      enable_hsl_curves: true,
      track_render_index: 0
    };
  }

  /**
   * Constructs a DraftSegment for an audio clip.
   */
  public static createAudioSegment(
    materialId: string,
    targetTimerange: TimeRange,
    sourceTimerange: TimeRange,
    volume = 1.0
  ): DraftSegment {
    return {
      id: this.generateId(),
      material_id: materialId,
      source_timerange: sourceTimerange,
      target_timerange: targetTimerange,
      render_timerange: { start: 0, duration: 0 },
      desc: '',
      state: 0,
      speed: 1.0,
      is_loop: false,
      is_tone_modify: false,
      reverse: false,
      intensifies_audio: false,
      cartoon: false,
      volume,
      last_nonzero_volume: 1.0,
      clip: null,
      uniform_scale: null,
      extra_material_refs: [],
      render_index: 0,
      keyframe_refs: [],
      visible: true,
      track_render_index: 10
    };
  }

  /**
   * Constructs a DraftSegment for a text layer or subtitle.
   */
  public static createTextSegment(
    materialId: string,
    targetTimerange: TimeRange,
    x = 0.0,
    y = -0.65 // By default placed lower third for subtitles / captions
  ): DraftSegment {
    const clip: ClipTransform = {
      scale: { x: 1.0, y: 1.0 },
      rotation: 0.0,
      transform: { x, y },
      flip: { vertical: false, horizontal: false },
      alpha: 1.0
    };

    return {
      id: this.generateId(),
      material_id: materialId,
      source_timerange: null,
      target_timerange: targetTimerange,
      render_timerange: { start: 0, duration: 0 },
      desc: '',
      state: 0,
      speed: 1.0,
      is_loop: false,
      is_tone_modify: false,
      reverse: false,
      intensifies_audio: false,
      cartoon: false,
      volume: 1.0,
      last_nonzero_volume: 1.0,
      clip,
      uniform_scale: { on: true, value: 1.0 },
      extra_material_refs: [],
      render_index: 14000,
      keyframe_refs: [],
      visible: true,
      track_render_index: 1
    };
  }

  /**
   * Constructs a TransitionMaterial entry.
   */
  public static createTransitionMaterial(
    materialId: string,
    name: string,
    durationUs = 500_000
  ): TransitionMaterial {
    const effectId = this.generateHexId();
    return {
      id: materialId,
      name,
      type: 'transition',
      category_name: 'basic',
      category_id: '',
      duration: durationUs,
      path: '',
      effect_id: effectId,
      resource_id: effectId,
      is_overlap: false
    };
  }

  /**
   * Constructs a VideoKeyframe entry.
   */
  public static createKeyframe(
    keyframeId: string,
    property: 'scale' | 'x' | 'y' | 'rotation' | 'alpha',
    timeOffsetUs: number,
    value: number
  ): VideoKeyframe {
    const propMap: Record<string, string> = {
      scale: 'KFTypeScaleX',
      x: 'KFTypePositionX',
      y: 'KFTypePositionY',
      rotation: 'KFTypeRotation',
      alpha: 'KFTypeAlpha'
    };

    return {
      id: keyframeId,
      property_type: propMap[property] || 'KFTypeScaleX',
      time_offset: timeOffsetUs,
      values: [value]
    };
  }

  /**
   * Constructs a sticker DraftSegment.
   */
  public static createStickerSegment(
    materialId: string,
    targetTimerange: TimeRange,
    x = 0.0,
    y = 0.0,
    scale = 1.0
  ): DraftSegment {
    const clip: ClipTransform = {
      scale: { x: scale, y: scale },
      rotation: 0.0,
      transform: { x, y },
      flip: { vertical: false, horizontal: false },
      alpha: 1.0
    };

    return {
      id: this.generateId(),
      material_id: materialId,
      source_timerange: null,
      target_timerange: targetTimerange,
      render_timerange: { start: 0, duration: 0 },
      desc: '',
      state: 0,
      speed: 1.0,
      is_loop: false,
      is_tone_modify: false,
      reverse: false,
      intensifies_audio: false,
      cartoon: false,
      volume: 1.0,
      last_nonzero_volume: 1.0,
      clip,
      uniform_scale: { on: true, value: scale },
      extra_material_refs: [],
      render_index: 12000,
      keyframe_refs: [],
      visible: true,
      track_render_index: 2
    };
  }

  /**
   * Constructs an AudioFadeMaterial entry for smooth audio volume ramping.
   */
  public static createAudioFadeMaterial(
    materialId: string,
    fadeInUs: number,
    fadeOutUs: number
  ): AudioFadeMaterial {
    return {
      id: materialId,
      type: 'audio_fade',
      fade_type: 0,
      fade_in_duration: fadeInUs,
      fade_out_duration: fadeOutUs
    };
  }

  /**
   * Constructs a SpeedMaterial entry for clip speed control.
   */
  public static createSpeedMaterial(
    materialId: string,
    speed: number,
    mode = 0
  ): SpeedMaterial {
    return {
      id: materialId,
      type: 'speed',
      mode,
      speed,
      curve_speed: null
    };
  }

  /**
   * Constructs a TextMaterial with Aeovisuals viral typography styling:
   * -1.0 metric tracking, 26/26 diffuse ambient shadow, custom font, and power word highlighting.
   */
  public static createViralCaptionMaterial(
    materialId: string,
    text: string,
    options: {
      fontSize?: number;
      fontFamily?: string;
      accentColor?: string;
      powerWords?: string[];
    } = {}
  ): TextMaterial {
    const baseFontSize = options.fontSize || 14.0;
    const fontFamily = options.fontFamily || 'Montserrat';
    const accentColor = options.accentColor || '#FF1E27';
    const powerWords = (options.powerWords || []).map((w: any) => {
      if (typeof w === 'string') return w.toLowerCase().trim();
      if (w && typeof w.word === 'string') return w.word.toLowerCase().trim();
      return String(w || '').toLowerCase().trim();
    });

    const hexToRgb = (hex: string): [number, number, number] => {
      const clean = hex.replace('#', '');
      const r = parseInt(clean.substring(0, 2), 16) / 255.0 || 1.0;
      const g = parseInt(clean.substring(2, 4), 16) / 255.0 || 0.12;
      const b = parseInt(clean.substring(4, 6), 16) / 255.0 || 0.15;
      return [r, g, b];
    };

    const accentRgb = hexToRgb(accentColor);

    const styles: Array<{
      fill: { content: { render_type: string; solid: { color: number[] } } };
      size: number;
      useLetterColor: boolean;
      range: [number, number];
    }> = [];

    if (powerWords.length > 0) {
      const regex = /\b[\w']+\b/g;
      let match: RegExpExecArray | null;
      let lastIndex = 0;

      while ((match = regex.exec(text)) !== null) {
        const word = match[0];
        const start = match.index;
        const end = start + word.length;

        if (start > lastIndex) {
          styles.push({
            fill: { content: { render_type: 'solid', solid: { color: [1.0, 1.0, 1.0] } } },
            size: baseFontSize,
            useLetterColor: true,
            range: [lastIndex, start]
          });
        }

        const isPower = powerWords.includes(word.toLowerCase());
        styles.push({
          fill: { content: { render_type: 'solid', solid: { color: isPower ? accentRgb : [1.0, 1.0, 1.0] } } },
          size: isPower ? Math.round(baseFontSize * 1.4 * 10) / 10 : baseFontSize,
          useLetterColor: true,
          range: [start, end]
        });

        lastIndex = end;
      }

      if (lastIndex < text.length) {
        styles.push({
          fill: { content: { render_type: 'solid', solid: { color: [1.0, 1.0, 1.0] } } },
          size: baseFontSize,
          useLetterColor: true,
          range: [lastIndex, text.length]
        });
      }
    } else {
      styles.push({
        fill: { content: { render_type: 'solid', solid: { color: [1.0, 1.0, 1.0] } } },
        size: baseFontSize,
        useLetterColor: true,
        range: [0, text.length]
      });
    }

    const contentObj = {
      text,
      styles
    };

    return {
      id: materialId,
      name: this.generateId(),
      type: 'text',
      content: JSON.stringify(contentObj),
      base_content: '',
      font_size: baseFontSize,
      font_title: fontFamily,
      font_name: fontFamily,
      text_color: '#ffffffff',
      text_alpha: 1.0,
      letter_spacing: -1.0,
      has_shadow: true,
      shadow_color: '#000000ff',
      shadow_alpha: 0.26,
      shadow_smoothing: 0.26,
      shadow_distance: 0.0,
      shadow_angle: 0.0,
      border_color: '#000000ff',
      border_width: 0.0,
      border_alpha: 0.0,
      alignment: 1,
      line_feed: 1,
      global_alpha: 1.0,
      typesetting: 0,
      check_flag: 47
    };
  }

  /**
   * Splits a DraftSegment at a target microsecond timestamp into two continuous segments.
   */
  public static splitSegment(
    segment: DraftSegment,
    splitTimeUs: number,
    newSegmentId: string
  ): { firstSegment: DraftSegment; secondSegment: DraftSegment } {
    const startUs = segment.target_timerange.start;
    const totalDurationUs = segment.target_timerange.duration;
    const endUs = startUs + totalDurationUs;

    if (splitTimeUs <= startUs || splitTimeUs >= endUs) {
      throw new Error(`Split timestamp ${splitTimeUs}us must be strictly between start (${startUs}us) and end (${endUs}us).`);
    }

    const firstDurationUs = splitTimeUs - startUs;
    const secondDurationUs = totalDurationUs - firstDurationUs;

    segment.target_timerange.duration = firstDurationUs;

    let secondSourceRange: TimeRange | null = null;
    if (segment.source_timerange) {
      const origSourceStart = segment.source_timerange.start;
      const origSourceDuration = segment.source_timerange.duration;
      const firstSourceDuration = Math.round(firstDurationUs * segment.speed);
      segment.source_timerange.duration = firstSourceDuration;

      const secondSourceStart = origSourceStart + firstSourceDuration;
      const secondSourceDuration = origSourceDuration - firstSourceDuration;
      secondSourceRange = {
        start: secondSourceStart,
        duration: secondSourceDuration
      };
    }

    const secondSegment: DraftSegment = JSON.parse(JSON.stringify(segment));
    secondSegment.id = newSegmentId;
    secondSegment.target_timerange = {
      start: splitTimeUs,
      duration: secondDurationUs
    };
    secondSegment.source_timerange = secondSourceRange;
    secondSegment.keyframe_refs = [];

    return { firstSegment: segment, secondSegment };
  }

  /**
   * Recalculates total project duration from all segments in all tracks.
   */
  public static recalculateDuration(draft: DraftContent): number {
    let maxEndUs = 0;
    for (const track of draft.tracks) {
      for (const seg of track.segments) {
        const endUs = seg.target_timerange.start + seg.target_timerange.duration;
        if (endUs > maxEndUs) {
          maxEndUs = endUs;
        }
      }
    }
    draft.duration = maxEndUs;
    return maxEndUs;
  }
}

