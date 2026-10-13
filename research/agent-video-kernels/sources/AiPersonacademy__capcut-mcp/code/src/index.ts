#!/usr/bin/env node

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { DraftManager } from './capcut/draft-manager.js';
import { MediaProbe } from './capcut/media.js';
import { AppLauncher } from './capcut/app-launcher.js';
import { CapCutPathResolver } from './capcut/paths.js';

const server = new McpServer({
  name: 'capcut-mcp-server',
  version: '1.0.0'
});

// ==========================================
// TOOLS: Project Management
// ==========================================

server.tool(
  'capcut_list_projects',
  'Lists all CapCut video projects on this computer, including duration, resolution, track counts, and lock status.',
  {},
  async () => {
    try {
      const projects = await DraftManager.listProjects();
      return {
        content: [{ type: 'text', text: JSON.stringify(projects, null, 2) }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to list projects: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_get_project',
  'Fetches the complete timeline structure, tracks, media materials, and duration of a CapCut project.',
  {
    project_name_or_id: z.string().describe('The name of the project folder or the UUID draft ID.')
  },
  async ({ project_name_or_id }) => {
    try {
      const details = await DraftManager.getProject(project_name_or_id);
      return {
        content: [{ type: 'text', text: JSON.stringify(details, null, 2) }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to get project '${project_name_or_id}': ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_create_project',
  'Creates a brand new CapCut project draft with canvas resolution and frame rate, registered directly into CapCut Desktop.',
  {
    name: z.string().describe('Project name (alphanumeric, spaces, underscores).'),
    ratio: z.enum(['9:16', '16:9', '1:1', '4:3', 'original']).default('9:16').describe('Aspect ratio: 9:16 (TikTok/Reels/Shorts), 16:9 (YouTube), 1:1 (Square).'),
    width: z.number().optional().describe('Custom canvas width in pixels (e.g. 1080).'),
    height: z.number().optional().describe('Custom canvas height in pixels (e.g. 1920).'),
    fps: z.number().default(30.0).describe('Frame rate (typically 30 or 60).')
  },
  async ({ name, ratio, width, height, fps }) => {
    try {
      const result = await DraftManager.createProject({ name, ratio, width, height, fps });
      return {
        content: [{
          type: 'text',
          text: `Project '${name}' successfully created!\n\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to create project: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_duplicate_project',
  'Duplicates an existing CapCut project to a new draft with fresh IDs (ideal for creating variations or backups).',
  {
    source_project: z.string().describe('Name or UUID of the project to copy from.'),
    new_name: z.string().describe('Name for the cloned project.')
  },
  async ({ source_project, new_name }) => {
    try {
      const result = await DraftManager.duplicateProject(source_project, new_name);
      return {
        content: [{
          type: 'text',
          text: `Successfully duplicated '${source_project}' into '${new_name}'!\n\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to duplicate project: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_delete_project',
  'Deletes a CapCut project folder and unregisters it from CapCut. Requires explicit confirmation.',
  {
    project_name_or_id: z.string().describe('Name or UUID of the project to delete.'),
    confirm: z.boolean().describe('Must be set to true to confirm deletion.')
  },
  async ({ project_name_or_id, confirm }) => {
    try {
      const result = await DraftManager.deleteProject(project_name_or_id, confirm);
      return {
        content: [{
          type: 'text',
          text: `Successfully deleted project '${project_name_or_id}' from ${result.deletedPath}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to delete project: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

// ==========================================
// TOOLS: Media & Timeline Sequencing
// ==========================================

server.tool(
  'capcut_add_video_clip',
  'Adds a video or image file to a CapCut video track. Media metadata (duration, resolution) is automatically probed.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    file_path: z.string().describe('Absolute path to the video or image file on disk.'),
    track_index: z.number().default(0).describe('Track index (0 = main track, 1+ = overlay / PIP tracks).'),
    start_time_seconds: z.union([z.number(), z.literal('auto_append')]).default('auto_append').describe("Start time on timeline in seconds, or 'auto_append' to append sequentially."),
    duration_seconds: z.number().optional().describe('Clip duration in seconds. Defaults to full media length (or 3s for images).'),
    source_start_seconds: z.number().default(0).describe('Starting in-point within the source file in seconds.'),
    scale: z.number().optional().describe('Scale multiplier (1.0 = 100%).'),
    x: z.number().optional().describe('Horizontal position offset normalized [-1.0 to 1.0]. 0.0 is center.'),
    y: z.number().optional().describe('Vertical position offset normalized [-1.0 to 1.0]. 0.0 is center.'),
    rotation: z.number().optional().describe('Rotation in degrees.'),
    opacity: z.number().min(0).max(1).optional().describe('Opacity/alpha from 0.0 to 1.0.')
  },
  async ({ project_name_or_id, file_path, track_index, start_time_seconds, duration_seconds, source_start_seconds, scale, x, y, rotation, opacity }) => {
    try {
      const result = await DraftManager.addVideoClip({
        projectNameOrId: project_name_or_id,
        filePath: file_path,
        trackIndex: track_index,
        startTimeSeconds: start_time_seconds,
        durationSeconds: duration_seconds,
        sourceStartSeconds: source_start_seconds,
        scale,
        x,
        y,
        rotation,
        opacity
      });
      return {
        content: [{
          type: 'text',
          text: `Added video clip to track ${track_index}!\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add video clip: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_add_audio_clip',
  'Adds background music, sound effects, or voiceover audio to an audio track.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    file_path: z.string().describe('Absolute path to audio file on disk (.mp3, .wav, .m4a, etc.).'),
    track_index: z.number().default(0).describe('Audio track index (0 = main audio, 1+ = secondary audio).'),
    start_time_seconds: z.union([z.number(), z.literal('auto_append')]).default('auto_append').describe("Start time on timeline in seconds, or 'auto_append' to append sequentially."),
    duration_seconds: z.number().optional().describe('Duration in seconds. Defaults to entire audio file length.'),
    source_start_seconds: z.number().default(0).describe('In-point offset within the source audio file.'),
    volume: z.number().default(1.0).describe('Audio volume multiplier (1.0 = 100%, 0.5 = 50%, 2.0 = 200%).')
  },
  async ({ project_name_or_id, file_path, track_index, start_time_seconds, duration_seconds, source_start_seconds, volume }) => {
    try {
      const result = await DraftManager.addAudioClip({
        projectNameOrId: project_name_or_id,
        filePath: file_path,
        trackIndex: track_index,
        startTimeSeconds: start_time_seconds,
        durationSeconds: duration_seconds,
        sourceStartSeconds: source_start_seconds,
        volume
      });
      return {
        content: [{
          type: 'text',
          text: `Added audio clip to track ${track_index}!\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add audio clip: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_add_text',
  'Adds a customizable title, lower-third, or text overlay to a text track.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    text: z.string().describe('Text content to display.'),
    track_index: z.number().default(0).describe('Text track index.'),
    start_time_seconds: z.union([z.number(), z.literal('auto_append')]).default('auto_append').describe("Start time in seconds, or 'auto_append'."),
    duration_seconds: z.number().default(3.0).describe('Duration in seconds (default 3s).'),
    font_size: z.number().default(14.0).describe('Font size (e.g. 12, 14, 18).'),
    text_color: z.string().default('#ffffffff').describe('Hex color with alpha (default #ffffffff white).'),
    border_color: z.string().default('#000000ff').describe('Stroke/outline color (default #000000ff black).'),
    border_width: z.number().default(0.08).describe('Outline border width (0.0 to 0.2).'),
    alignment: z.enum(['left', 'center', 'right']).default('center').describe('Text alignment.'),
    x: z.number().default(0.0).describe('Horizontal position [-1.0 to 1.0]. 0 = center.'),
    y: z.number().default(-0.65).describe('Vertical position [-1.0 to 1.0]. Negative is lower third.')
  },
  async ({ project_name_or_id, text, track_index, start_time_seconds, duration_seconds, font_size, text_color, border_color, border_width, alignment, x, y }) => {
    try {
      const result = await DraftManager.addText({
        projectNameOrId: project_name_or_id,
        text,
        trackIndex: track_index,
        startTimeSeconds: start_time_seconds,
        durationSeconds: duration_seconds,
        fontSize: font_size,
        textColor: text_color,
        borderColor: border_color,
        borderWidth: border_width,
        alignment,
        x,
        y
      });
      return {
        content: [{
          type: 'text',
          text: `Added text overlay '${text}'!\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add text: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_add_subtitles',
  'Batch adds synchronized subtitles / captions from an array of items, an SRT file path, or raw SRT string.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    srt_file_path: z.string().optional().describe('Absolute path to a .srt subtitle file on disk.'),
    srt_content: z.string().optional().describe('Raw SRT format text string.'),
    subtitles: z.array(z.object({
      startTimeSeconds: z.number().describe('Start timestamp in seconds.'),
      endTimeSeconds: z.number().describe('End timestamp in seconds.'),
      text: z.string().describe('Subtitle text.')
    })).optional().describe('Structured list of subtitle cues.'),
    font_size: z.number().default(10.0).describe('Subtitle font size.'),
    text_color: z.string().default('#ffffffff').describe('Subtitle font color.'),
    border_color: z.string().default('#000000ff').describe('Subtitle border outline color.'),
    border_width: z.number().default(0.08).describe('Subtitle border outline width.'),
    y: z.number().default(-0.72).describe('Vertical position [-1.0 to 1.0]. -0.72 is ideal lower-third position.')
  },
  async ({ project_name_or_id, srt_file_path, srt_content, subtitles, font_size, text_color, border_color, border_width, y }) => {
    try {
      const result = await DraftManager.addSubtitles({
        projectNameOrId: project_name_or_id,
        srtFilePath: srt_file_path,
        srtContent: srt_content,
        subtitles,
        fontSize: font_size,
        textColor: text_color,
        borderColor: border_color,
        borderWidth: border_width,
        y
      });
      return {
        content: [{
          type: 'text',
          text: `Successfully added ${result.addedCount} subtitles to project!\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add subtitles: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

// ==========================================
// TOOLS: Timeline Editing
// ==========================================

server.tool(
  'capcut_trim_clip',
  "Adjusts the timeline start time or duration of an existing segment by its segment ID.",
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    segment_id: z.string().describe('UUID of the segment to trim.'),
    new_start_seconds: z.number().optional().describe('New start time in seconds.'),
    new_duration_seconds: z.number().optional().describe('New duration in seconds.')
  },
  async ({ project_name_or_id, segment_id, new_start_seconds, new_duration_seconds }) => {
    try {
      const result = await DraftManager.trimClip(project_name_or_id, segment_id, new_start_seconds, new_duration_seconds);
      return {
        content: [{ type: 'text', text: `Trimmed clip successfully:\n${JSON.stringify(result, null, 2)}` }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to trim clip: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_remove_clip',
  'Deletes a specific segment from a project track by its segment ID.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    segment_id: z.string().describe('UUID of the segment to delete.')
  },
  async ({ project_name_or_id, segment_id }) => {
    try {
      await DraftManager.removeClip(project_name_or_id, segment_id);
      return {
        content: [{ type: 'text', text: `Successfully removed segment '${segment_id}' from project.` }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to remove clip: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_set_clip_transform',
  'Adjusts scale, rotation, translation position (x, y), or opacity of an existing clip.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    segment_id: z.string().describe('UUID of the segment.'),
    scale: z.number().optional().describe('Scale factor (1.0 = 100%).'),
    rotation: z.number().optional().describe('Rotation in degrees.'),
    x: z.number().optional().describe('Horizontal position [-1.0 to 1.0].'),
    y: z.number().optional().describe('Vertical position [-1.0 to 1.0].'),
    alpha: z.number().min(0).max(1).optional().describe('Opacity from 0.0 to 1.0.')
  },
  async ({ project_name_or_id, segment_id, scale, rotation, x, y, alpha }) => {
    try {
      const result = await DraftManager.setClipTransform(project_name_or_id, segment_id, {
        scale,
        rotation,
        x,
        y,
        alpha
      });
      return {
        content: [{ type: 'text', text: `Updated transform for segment:\n${JSON.stringify(result, null, 2)}` }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to set transform: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

// ==========================================
// TOOLS: Utilities & App Integration
// ==========================================

server.tool(
  'capcut_get_media_info',
  'Inspects video or audio file technical parameters (duration, width, height, fps, codec) using ffprobe.',
  {
    file_path: z.string().describe('Absolute path to video, image, or audio file.')
  },
  async ({ file_path }) => {
    try {
      const info = await MediaProbe.probeFile(file_path);
      return {
        content: [{ type: 'text', text: JSON.stringify(info, null, 2) }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to probe media: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_open_app',
  'Launches CapCut Desktop on Windows or opens the project folder in Windows Explorer.',
  {
    project_name_or_id: z.string().optional().describe('If specified, opens this specific project folder in Windows Explorer. Otherwise launches CapCut application.')
  },
  async ({ project_name_or_id }) => {
    try {
      if (project_name_or_id) {
        const result = await AppLauncher.openProjectFolder(project_name_or_id);
        return {
          content: [{ type: 'text', text: `Opened project directory in Explorer: ${result.path}` }]
        };
      } else {
        const result = await AppLauncher.launchCapCut();
        return {
          content: [{ type: 'text', text: result.message }]
        };
      }
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to open CapCut: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_add_transition',
  'Adds a transition effect (e.g. Dissolve, Fade to Black, Fade to White, Zoom In) between clips on a video track.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    segment_id: z.string().describe('UUID of the video segment to attach the transition to.'),
    transition_name: z.enum(['Dissolve', 'Fade to Black', 'Fade to White', 'Slide Left', 'Zoom In']).default('Dissolve').describe('Name of the transition effect.'),
    duration_seconds: z.number().default(0.5).describe('Transition duration in seconds (default 0.5s).')
  },
  async ({ project_name_or_id, segment_id, transition_name, duration_seconds }) => {
    try {
      const result = await DraftManager.addTransition({
        projectNameOrId: project_name_or_id,
        segmentId: segment_id,
        transitionName: transition_name,
        durationSeconds: duration_seconds
      });
      return {
        content: [{ type: 'text', text: `Added transition '${transition_name}' to segment:\n${JSON.stringify(result, null, 2)}` }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add transition: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_add_keyframe',
  'Adds an animation keyframe for scale, rotation, translation (x, y), or opacity to a video segment.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    segment_id: z.string().describe('UUID of the video segment.'),
    property: z.enum(['scale', 'x', 'y', 'rotation', 'alpha']).describe('Property to animate.'),
    time_offset_seconds: z.number().describe('Time offset from segment start in seconds (e.g. 0.0 for start, 1.5 for mid-clip).'),
    value: z.number().describe('Value at keyframe (e.g. scale 1.2, x 0.1, alpha 0.5).')
  },
  async ({ project_name_or_id, segment_id, property, time_offset_seconds, value }) => {
    try {
      const result = await DraftManager.addKeyframe({
        projectNameOrId: project_name_or_id,
        segmentId: segment_id,
        property,
        timeOffsetSeconds: time_offset_seconds,
        value
      });
      return {
        content: [{ type: 'text', text: `Added keyframe to segment:\n${JSON.stringify(result, null, 2)}` }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add keyframe: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_add_sticker',
  'Adds an animated sticker or graphic element to the project timeline.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    sticker_name: z.string().describe('Name/tag of the sticker.'),
    track_index: z.number().default(0).describe('Sticker track index.'),
    start_time_seconds: z.union([z.number(), z.literal('auto_append')]).default('auto_append').describe("Start time on timeline in seconds, or 'auto_append'."),
    duration_seconds: z.number().default(3.0).describe('Duration in seconds.'),
    x: z.number().default(0.0).describe('Horizontal position [-1.0 to 1.0].'),
    y: z.number().default(0.0).describe('Vertical position [-1.0 to 1.0].'),
    scale: z.number().default(1.0).describe('Scale multiplier.')
  },
  async ({ project_name_or_id, sticker_name, track_index, start_time_seconds, duration_seconds, x, y, scale }) => {
    try {
      const result = await DraftManager.addSticker({
        projectNameOrId: project_name_or_id,
        stickerName: sticker_name,
        trackIndex: track_index,
        startTimeSeconds: start_time_seconds,
        durationSeconds: duration_seconds,
        x,
        y,
        scale
      });
      return {
        content: [{ type: 'text', text: `Added sticker '${sticker_name}':\n${JSON.stringify(result, null, 2)}` }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add sticker: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_generate_preview',
  'Renders a fast proxy preview video (.mp4) of a CapCut project using ffmpeg without needing to export from the GUI.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    output_path: z.string().optional().describe('Optional custom destination path for the rendered mp4.'),
    width: z.number().optional().describe('Custom render width (defaults to project canvas width).'),
    height: z.number().optional().describe('Custom render height (defaults to project canvas height).'),
    fps: z.number().optional().describe('Render framerate (defaults to project fps, e.g. 30).')
  },
  async ({ project_name_or_id, output_path, width, height, fps }) => {
    try {
      const result = await DraftManager.generatePreview({
        projectNameOrId: project_name_or_id,
        outputPath: output_path,
        width,
        height,
        fps
      });
      return {
        content: [{
          type: 'text',
          text: `Preview rendered successfully!\nFile: ${result.outputPath}\nDuration: ${result.durationSeconds}s`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to render preview: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_split_clip',
  'Splits a video, audio, or text clip into two linked segments at an exact timeline timestamp (the timeline razor / blade tool). Essential for cutting out pauses, pacing edits, or inserting B-roll.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    segment_id: z.string().describe('UUID of the segment to split.'),
    split_time_seconds: z.number().describe('Timeline timestamp in seconds where the razor cut should occur.')
  },
  async ({ project_name_or_id, segment_id, split_time_seconds }) => {
    try {
      const result = await DraftManager.splitClip({
        projectNameOrId: project_name_or_id,
        segmentId: segment_id,
        splitTimeSeconds: split_time_seconds
      });
      return {
        content: [{
          type: 'text',
          text: `Split segment successfully at ${split_time_seconds}s!\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to split clip: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_set_clip_speed',
  'Sets playback speed multiplier (e.g. 0.5x slow-mo, 1.25x talking head, 2.0x time-lapse) with optional pitch preservation so voices do not sound like chipmunks.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    segment_id: z.string().describe('UUID of the video or audio segment.'),
    speed: z.number().min(0.01).max(100).describe('Speed multiplier (e.g. 0.5 for half speed, 1.2 for faster speech, 2.0 for double speed).'),
    preserve_pitch: z.boolean().default(true).describe('If true, preserves original audio pitch when altering speed.')
  },
  async ({ project_name_or_id, segment_id, speed, preserve_pitch }) => {
    try {
      const result = await DraftManager.setClipSpeed({
        projectNameOrId: project_name_or_id,
        segmentId: segment_id,
        speed,
        preservePitch: preserve_pitch
      });
      return {
        content: [{
          type: 'text',
          text: `Updated speed for segment:\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to set speed: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_add_audio_fade',
  'Adds smooth volume fade-in and/or fade-out envelopes to an audio track segment, eliminating abrupt audio cutoffs in background music or dialogue.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    segment_id: z.string().describe('UUID of the audio segment.'),
    fade_in_seconds: z.number().default(0).describe('Fade-in duration in seconds (e.g. 1.5).'),
    fade_out_seconds: z.number().default(0).describe('Fade-out duration in seconds (e.g. 2.0).')
  },
  async ({ project_name_or_id, segment_id, fade_in_seconds, fade_out_seconds }) => {
    try {
      const result = await DraftManager.addAudioFade({
        projectNameOrId: project_name_or_id,
        segmentId: segment_id,
        fadeInSeconds: fade_in_seconds,
        fadeOutSeconds: fade_out_seconds
      });
      return {
        content: [{
          type: 'text',
          text: `Added audio fade envelopes:\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add audio fade: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_add_viral_caption',
  'Injects Aeovisuals-calibrated viral typography with -1.0 metric kerning, 26/26 diffuse ambient shadow, custom font, power word scaling/color contrast, and optional Quad Ease hover-up pop keyframes.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    text: z.string().describe('The caption text content.'),
    power_words: z.array(z.string()).optional().describe('Specific keywords to emphasize with 1.4x scale and power accent color (e.g. ["10 MILLION", "MONEY"]).'),
    font_family: z.enum(['Montserrat', 'Poppins', 'Helvetica', 'Arial']).default('Montserrat').describe('Font superfamily (Montserrat/Poppins recommended for viral videos).'),
    accent_color: z.string().default('#FF1E27').describe('Hex accent color for power words (default #FF1E27 Crimson, or #FFD700 Gold).'),
    enable_hover_pop: z.boolean().default(true).describe('If true, automatically keyframes a 5-frame snappy hover-up pop from floor to baseline with opacity fade.'),
    track_index: z.number().default(0).describe('Text track index.'),
    start_time_seconds: z.union([z.number(), z.literal('auto_append')]).default('auto_append').describe("Start time in seconds or 'auto_append'."),
    duration_seconds: z.number().default(2.5).describe('Display duration in seconds.'),
    font_size: z.number().default(14.0).describe('Base font size.'),
    x: z.number().default(0.0).describe('Horizontal offset [-1.0 to 1.0]. 0.0 is center.'),
    y: z.number().default(-0.65).describe('Vertical offset [-1.0 to 1.0]. Default -0.65 (standard lower-third).')
  },
  async ({ project_name_or_id, text, power_words, font_family, accent_color, enable_hover_pop, track_index, start_time_seconds, duration_seconds, font_size, x, y }) => {
    try {
      const result = await DraftManager.addViralCaption({
        projectNameOrId: project_name_or_id,
        text,
        powerWords: power_words,
        fontFamily: font_family,
        accentColor: accent_color,
        enableHoverPop: enable_hover_pop,
        trackIndex: track_index,
        startTimeSeconds: start_time_seconds,
        durationSeconds: duration_seconds,
        fontSize: font_size,
        x,
        y
      });
      return {
        content: [{
          type: 'text',
          text: `Added viral caption '${text}' with Aeovisuals styling!\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add viral caption: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_create_video_bridge',
  'Orchestrates the Direct Video Track Bridge: creates a CapCut draft around a pre-rendered 60 FPS master video plate (Remotion/WebGL), separates multi-track audio, and auto-imports subtitles into editable tracks.',
  {
    project_name: z.string().describe('Target project name.'),
    video_plate_path: z.string().describe('Absolute file path to pre-rendered master video plate (.mp4).'),
    audio_tracks: z.array(z.object({
      filePath: z.string().describe('Absolute path to audio track file.'),
      volume: z.number().default(1.0).describe('Volume level (1.0 = 100%).'),
      trackIndex: z.number().default(0).describe('Audio track index (0=voice, 1=BGM, 2=SFX).')
    })).optional().describe('Audio tracks to inject.'),
    subtitles_srt_path: z.string().optional().describe('Optional SRT file path to import as editable subtitles.'),
    ratio: z.enum(['9:16', '16:9', '1:1', 'original']).default('9:16').describe('Canvas aspect ratio.'),
    fps: z.number().default(60.0).describe('Canvas frame rate (default 60fps for high-end motion).')
  },
  async ({ project_name, video_plate_path, audio_tracks, subtitles_srt_path, ratio, fps }) => {
    try {
      const result = await DraftManager.createVideoBridge({
        projectName: project_name,
        videoPlatePath: video_plate_path,
        audioTracks: audio_tracks,
        subtitlesSrtPath: subtitles_srt_path,
        ratio,
        fps
      });
      return {
        content: [{
          type: 'text',
          text: `Video bridge draft '${project_name}' created successfully!\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to create video bridge: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

server.tool(
  'capcut_add_sound_effect',
  'Drops a transient sound effect (whoosh, pop, click, riser impact) at an exact timeline timestamp, aligned with visual keyframes or text pops.',
  {
    project_name_or_id: z.string().describe('Target project name or ID.'),
    sfx_file_path: z.string().describe('Absolute path to sound effect audio file (.wav, .mp3).'),
    timestamp_seconds: z.number().describe('Timeline timestamp in seconds where the SFX should trigger.'),
    volume: z.number().default(0.7).describe('SFX volume multiplier (default 0.7).'),
    track_index: z.number().default(1).describe('Audio track index for SFX (default track 1).')
  },
  async ({ project_name_or_id, sfx_file_path, timestamp_seconds, volume, track_index }) => {
    try {
      const result = await DraftManager.addSoundEffect({
        projectNameOrId: project_name_or_id,
        sfxFilePath: sfx_file_path,
        timestampSeconds: timestamp_seconds,
        volume,
        trackIndex: track_index
      });
      return {
        content: [{
          type: 'text',
          text: `Added sound effect at ${timestamp_seconds}s:\n${JSON.stringify(result, null, 2)}`
        }]
      };
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Failed to add sound effect: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true
      };
    }
  }
);

// ==========================================
// RESOURCES
// ==========================================

server.resource(
  'capcut-projects-list',
  'capcut://projects',
  async () => {
    const projects = await DraftManager.listProjects();
    return {
      contents: [{
        uri: 'capcut://projects',
        text: JSON.stringify(projects, null, 2),
        mimeType: 'application/json'
      }]
    };
  }
);

// ==========================================
// PROMPTS
// ==========================================

server.prompt(
  'create_social_short',
  {
    topic: z.string().describe('The topic or subject of the video'),
    video_files: z.string().describe('Comma-separated list of video clips to include'),
    bgm_file: z.string().optional().describe('Optional path to background music')
  },
  ({ topic, video_files, bgm_file }) => ({
    messages: [{
      role: 'user',
      content: {
        type: 'text',
        text: `Please assemble a vertical 9:16 CapCut project for topic: "${topic}".\n` +
          `Video files: ${video_files}\n` +
          (bgm_file ? `Background music: ${bgm_file}\n` : '') +
          `1. Call capcut_create_project with ratio="9:16" (1080x1920).\n` +
          `2. Add each video clip sequentially using capcut_add_video_clip with start_time_seconds="auto_append".\n` +
          (bgm_file ? `3. Add background music using capcut_add_audio_clip with volume=0.3.\n` : '') +
          `4. Add hook title text in the first 3 seconds using capcut_add_text.\n` +
          `5. Report the total duration and project status.`
      }
    }]
  })
);

// ==========================================
// START SERVER
// ==========================================

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('CapCut MCP Server connected and listening on stdio.');
}

main().catch((err) => {
  console.error('Fatal error in CapCut MCP Server:', err);
  process.exit(1);
});
