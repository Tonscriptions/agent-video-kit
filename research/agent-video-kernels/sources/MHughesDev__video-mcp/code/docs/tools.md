# MCP Tool Reference

This is the first MVP tool surface for `mcp-editor`. The server is intentionally deterministic: agents provide creative direction, and this server performs local media operations, timeline export, rendering, and validation.

## Failure Contract

Every MCP tool should return a structured failure instead of an opaque exception:

```json
{
  "ok": false,
  "error": {
    "code": "missing_dependency",
    "message": "ffmpeg was not found on PATH.",
    "suggested_fix": "Install FFmpeg and make sure both ffmpeg and ffprobe are available on PATH.",
    "details": {
      "binary": "ffmpeg"
    }
  }
}
```

Long-running workflow tools may also return callback-style events:

```json
{
  "ok": false,
  "events": [
    {"stage": "create_project", "status": "completed"},
    {"stage": "create_timeline", "status": "started"},
    {"stage": "workflow", "status": "failed"}
  ],
  "error": {
    "code": "no_video_assets",
    "message": "No usable video assets were found in data/input."
  }
}
```

Common error codes:

- `missing_dependency`: `ffmpeg` or `ffprobe` is not installed or not on `PATH`.
- `media_not_found`: a requested media file does not exist.
- `project_not_found`: a requested project manifest does not exist.
- `no_video_assets`: no usable source footage was found.
- `command_failed`: FFmpeg or FFprobe returned a non-zero exit code. Details include command, return code, stdout, and stderr.
- `invalid_probe_output`: FFprobe did not return parseable JSON.
- `invalid_request`: the tool arguments are invalid.
- `internal_error`: unexpected server-side failure.

## `scan_assets`

Scan a local input directory for video assets and return FFprobe metadata.

Parameters:

- `input_dir`: directory to scan. Defaults to `data/input`.

Returns:

- `ok`
- `input_dir`
- `assets`

## `scan_project_assets`

Scan a local project asset directory and return aggregate counts plus per-file probe diagnostics.

Parameters:

- `input_dir`: directory to scan. Defaults to `data/input`.
- `include_audio`: whether to include standalone audio assets. Defaults to `true`.

Returns:

- `ok`
- `input_dir`
- `exists`
- `supported_extensions`
- `summary`
- `assets`

## `probe_media`

Probe one media file with FFprobe.

Parameters:

- `path`: local media file path.

Returns:

- `path`
- `exists`
- `ok`
- `duration`
- `format_name`
- `bit_rate`
- `streams`
- `error`

## `analyze_video_metadata`

Return video-focused metadata for one media file.

Parameters:

- `path`: local media file path.

Returns:

- `ok`
- `path`
- `duration`
- `format_name`
- `bit_rate`
- `width`
- `height`
- `aspect_ratio`
- `fps`
- `codec_name`
- `has_audio`
- `stream_count`
- `probe`

## `analyze_audio_metadata`

Return audio-focused metadata for one media file.

Parameters:

- `path`: local media file path.

Returns:

- `ok`
- `path`
- `duration`
- `format_name`
- `bit_rate`
- `codec_name`
- `has_video`
- `stream_count`
- `probe`

## `detect_scenes`

Detect likely scene-cut timestamps with FFmpeg scene scoring.

Parameters:

- `path`: local video file path.
- `threshold`: FFmpeg scene threshold. Defaults to `0.35`.
- `min_scene_gap`: minimum seconds between reported scene changes. Defaults to `0.5`.

Returns:

- `ok`
- `path`
- `threshold`
- `min_scene_gap`
- `scene_count`
- `scene_times`

## `generate_thumbnails`

Generate representative thumbnails for a video file.

Parameters:

- `path`: local video file path.
- `output_directory`: optional thumbnail output directory.
- `count`: requested thumbnail count. Defaults to `5`.

Returns:

- `ok`
- `path`
- `output_directory`
- `count`
- `timestamps`
- `thumbnails`

## `inspect_project`

Inspect a saved project manifest, including assets, timelines, outputs, and aggregate state.

Parameters:

- `project_id`: existing project ID.

Returns:

- `ok`
- `project_id`
- `name`
- `prompt`
- `input_dir`
- `music_path`
- `platforms`
- `summary`
- `assets`
- `timelines`
- `outputs`

## `create_project`

Create a project manifest from local assets.

Parameters:

- `name`: project name.
- `input_dir`: asset directory. Defaults to `data/input`.
- `music_path`: optional music file.
- `platforms`: optional list of `16:9`, `9:16`, or `1:1`.
- `prompt`: optional natural language request to store in the manifest.

Returns:

- `ok`
- `manifest`
- `manifest_path`

## `analyze_beats`

Analyze music tempo and beat timestamps with `librosa`.

Parameters:

- `music_path`: local music file path.

Returns:

- `ok`
- `path`
- `sample_rate`
- `tempo`
- `beat_count`
- `beat_times`
- `error`

## `suggest_cut_points`

Suggest timeline cut points from beat times, tempo, target duration, and pacing style.

Parameters:

- `beat_times`: optional list of beat timestamps in seconds.
- `target_duration`: target edit duration in seconds. Defaults to `30`.
- `style`: pacing style. Supported presets include `fast`, `social`, `trailer`, `medium`, `documentary`, and `slow`.
- `tempo`: optional BPM fallback when beat times are unavailable.

Returns:

- `ok`
- `style`
- `target_duration`
- `beat_multiplier`
- `cut_count`
- `cut_points`

## `plan_beat_synced_edit`

Create and save a deterministic beat-synced edit plan for a project.

Parameters:

- `project_id`: existing project ID.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.
- `target_duration`: target edit duration in seconds. Defaults to `30`.
- `style`: pacing style. Defaults to `medium`.
- `beat_times`: optional beat timestamps. If omitted and the project has music, the server analyzes the music.
- `tempo`: optional BPM fallback.

Returns:

- `ok`
- `project_id`
- `platform`
- `edit_plan`
- `manifest_path`

## `apply_edit_plan`

Apply a saved beat edit plan to a project timeline and export OTIO.

Parameters:

- `project_id`: existing project ID.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.

Returns:

- `ok`
- `project_id`
- `platform`
- `timeline`
- `validation`
- `otio_path`
- `manifest_path`

## `create_timeline`

Create a simple sequential OTIO timeline for a project.

Parameters:

- `project_id`: existing project ID.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.
- `target_duration`: requested timeline duration in seconds. Defaults to `30`.

Returns:

- `ok`
- `project_id`
- `timeline`
- `manifest_path`

## `add_clip`

Add a clip to a project timeline and refresh the OTIO export.

Parameters:

- `project_id`: existing project ID.
- `source`: local media file path.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.
- `start`: source start time in seconds. Defaults to `0`.
- `duration`: timeline clip duration in seconds. Defaults to `4`.
- `label`: optional clip label.
- `index`: optional insertion index. Appends when omitted.

Returns:

- `ok`
- `project_id`
- `platform`
- `timeline`
- `validation`
- `otio_path`
- `manifest_path`

## `trim_clip`

Trim a clip by `clip_id` or zero-based `index` and refresh the OTIO export.

Parameters:

- `project_id`: existing project ID.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.
- `clip_id`: optional clip ID.
- `index`: optional clip index.
- `start`: optional new source start time in seconds.
- `duration`: optional new duration in seconds.

Returns the same shape as `add_clip`.

## `split_clip`

Split a clip into two timeline clips and refresh the OTIO export.

Parameters:

- `project_id`: existing project ID.
- `split_at`: split point in seconds relative to the clip start.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.
- `clip_id`: optional clip ID.
- `index`: optional clip index.

Returns the same shape as `add_clip`.

## `move_clip`

Move a clip within a timeline and refresh the OTIO export.

Parameters:

- `project_id`: existing project ID.
- `from_index`: zero-based source index.
- `to_index`: zero-based destination index.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.

Returns the same shape as `add_clip`.

## `add_transition`

Add or replace a transition between adjacent clips and refresh the OTIO export.

Parameters:

- `project_id`: existing project ID.
- `from_clip_id`: previous adjacent clip ID.
- `to_clip_id`: next adjacent clip ID.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.
- `transition_type`: transition label. Defaults to `crossfade`.
- `duration`: transition duration in seconds. Defaults to `0.5`.

Returns the same shape as `add_clip`.

## `export_timeline`

Export the current project timeline to OTIO.

Parameters:

- `project_id`: existing project ID.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.

Returns:

- `ok`
- `project_id`
- `platform`
- `timeline`
- `validation`
- `otio_path`
- `manifest_path`

## `validate_timeline`

Validate a project timeline without rendering it.

Parameters:

- `project_id`: existing project ID.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.

Returns:

- `ok`
- `project_id`
- `platform`
- `validation`
- `timeline`

## `plan_render`

Plan FFmpeg render commands for a project timeline without executing them. This is useful for agent dry-runs, debugging, and environments where FFmpeg is not installed yet.

Parameters:

- `project_id`: existing project ID.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.
- `render_profile`: `preview`, `standard`, or `high`. Defaults to `preview`.

Returns:

- `ok`
- `project_id`
- `platform`
- `render_profile`
- `dry_run`
- `output_path`
- `work_dir`
- `expected_duration`
- `dimensions`
- `command_count`
- `commands`
- `segment_paths`
- `concat_file`

## `render_project`

Render a project timeline with FFmpeg and validate the output.

Parameters:

- `project_id`: existing project ID.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.
- `render_profile`: `preview`, `standard`, or `high`. Defaults to `preview`.
- `dry_run`: when `true`, writes and returns a render manifest without executing FFmpeg.

Returns:

- `ok`
- `project_id`
- `output`
- `manifest_path`

## `render_platform_variant`

Render or dry-run one platform variant for a project.

Parameters:

- `project_id`: existing project ID.
- `platform`: `16:9`, `9:16`, or `1:1`.
- `render_profile`: `preview`, `standard`, or `high`. Defaults to `preview`.
- `dry_run`: when `true`, writes and returns a render manifest without executing FFmpeg.

Returns the same shape as `render_project`.

## `render_all_variants`

Render or dry-run all requested platform variants for a project.

Parameters:

- `project_id`: existing project ID.
- `platforms`: optional list of `16:9`, `9:16`, or `1:1`. Defaults to the platforms saved in the project manifest.
- `render_profile`: `preview`, `standard`, or `high`. Defaults to `preview`.
- `dry_run`: when `true`, writes and returns render manifests without executing FFmpeg.

Returns:

- `ok`
- `project_id`
- `platforms`
- `outputs`
- `manifest_path`

## `validate_output`

Validate a rendered video file.

Parameters:

- `path`: rendered video path.
- `platform`: `16:9`, `9:16`, or `1:1`. Defaults to `16:9`.
- `expected_duration`: optional expected duration in seconds.

Returns:

- `ok`
- `path`
- `platform`
- `checks`
- `duration`
- `error`

## `edit_video_from_prompt`

Run the MVP end-to-end edit workflow from a natural language request.

Parameters:

- `prompt`: natural language editing request.
- `project_name`: optional project name. Defaults to `mvp-edit`.
- `input_dir`: asset directory. Defaults to `data/input`.
- `music_path`: optional music file for beat analysis.
- `platforms`: optional list of `16:9`, `9:16`, or `1:1`.
- `target_duration`: requested timeline duration in seconds. Defaults to `30`.
- `render`: whether to render outputs. Defaults to `true`.
- `render_profile`: `preview`, `standard`, or `high`. Defaults to `preview`.
- `dry_run`: when `true`, plans render commands without executing FFmpeg.

Additional parameters (Phase 9):

- `style`: explicit pacing style override (`trailer`, `social`, `documentary`, `fast`, `slow`, `medium`). Inferred from prompt keywords when omitted.
- `grade`: explicit grading preset override (`cinematic`, `vivid`, `flat`, `bw`, `warm`, `cool`). Inferred from prompt keywords when omitted.

Workflow (Phase 9 — full pipeline):

1. Scan assets and create project manifest.
2. Probe footage metadata (best-effort, never fatal).
3. Analyze music beats if `music_path` provided.
4. Build beat-synced or simple timeline per platform.
5. Apply grading preset inferred or specified.
6. Render platform variants.
7. Export OTIO timelines.
8. Run `validate_delivery_package` full gate.
9. Return delivery manifest with events trace.

Returns:

- `ok`
- `project_id`, `project_name`, `manifest_path`
- `inferred_style`, `inferred_grade`
- `footage_analyzed` — count of probed clips
- `events` — per-stage trace with status and details
- `beat_report`
- `timelines` — platform → OTIO path
- `outputs` — platform → rendered output
- `delivery` — delivery validation summary

---

## Phase 6: Effects Engine

### `apply_speed_ramp`

Apply a playback speed multiplier to a clip. `speed > 1` plays faster (shorter output); `speed < 1` plays slower (longer output). Adjusts source read duration and chains `atempo` audio filters correctly.

Parameters: `project_id`, `speed`, `platform` (default `16:9`), `clip_id` or `index`.

### `apply_zoom_punch`

Scale a clip up and crop back to frame size for a punch-zoom effect. `zoom` is a multiplier > 1.0 (e.g. `1.2` = 20% in).

Parameters: `project_id`, `zoom` (default `1.2`), `platform`, `clip_id` or `index`.

### `apply_smash_cut`

Remove any transition between two adjacent clips, replacing it with a hard cut.

Parameters: `project_id`, `from_clip_id`, `to_clip_id`, `platform`.

### `apply_reframe`

Crop a clip with a centre offset to reframe the shot for a different platform aspect ratio. `x_pct`/`y_pct` shift the crop window; `crop_pct` controls the crop size (0.5–1.0).

Parameters: `project_id`, `x_pct`, `y_pct`, `crop_pct` (default `0.9`), `platform`, `clip_id` or `index`.

### `apply_motion_effects`

Apply multiple named effects to a single clip in one call. Each entry in `effects` needs `effect_type` plus any effect-specific params.

Supported `effect_type` values: `speed_ramp`, `zoom_punch`, `reframe`, `motion_blur`, `grade`.

Parameters: `project_id`, `effects` (list of dicts), `platform`, `clip_id` or `index`.

### `remove_clip_effect`

Remove one effect type from a clip by name.

Parameters: `project_id`, `effect_type`, `platform`, `clip_id` or `index`.

---

## Phase 7: Color Grading & LUTs

### `list_luts`

Return all `.cube` LUT files found in `data/luts/`.

### `inspect_lut`

Parse a `.cube` file header and return metadata: size, type (1D/3D), domain min/max, title, data line count.

Parameters: `name_or_path` — LUT name (with or without `.cube` extension) or absolute path.

### `apply_lut`

Apply a `.cube` LUT grade to a clip (or all clips if no `clip_id`/`index` given). The LUT is stored as a `grade` effect on the clip and baked in at render time via `lut3d` FFmpeg filter.

Parameters: `project_id`, `lut_name`, `platform`, `clip_id` or `index`.

### `list_grading_presets`

Return all built-in grading presets with their parameters and descriptions.

Built-in presets: `cinematic`, `vivid`, `flat`, `bw`, `warm`, `cool`.

### `apply_grading_preset`

Apply a named grading preset to a clip or all clips. Presets control `contrast`, `saturation`, `gamma`, `brightness`, and `vignette` via the FFmpeg `eq` and `vignette` filters.

Parameters: `project_id`, `preset`, `platform`, `clip_id` or `index`.

### `render_with_grade`

Render a timeline with all grading effects baked into the FFmpeg filter chain. Equivalent to `render_project` but explicitly documents that grades are included.

Parameters: `project_id`, `platform`, `render_profile`, `dry_run`.

---

## Phase 8: Self-Validation Gate

### `validate_output`

Comprehensive validation of a single rendered video file.

Checks: `exists`, `probe_ok`, `has_video`, `resolution_matches`, `fps_correct`, `duration_close`, `not_black` (blackdetect), `not_silent` (silencedetect), `not_frozen` (freezedetect). FFmpeg advanced checks skip gracefully when the binary is unavailable.

Parameters: `path`, `platform`, `expected_duration`, `expected_fps` (default `30.0`), `check_black`, `check_silent`, `check_frozen`.

### `validate_audio`

Audio-focused validation: stream existence, codec, duration accuracy, silence detection.

Parameters: `path`, `expected_duration`.

### `validate_platform_outputs`

Validate all rendered platform outputs in a project manifest against their expected specs.

Parameters: `project_id`.

Returns per-platform `validate_output` results.

### `validate_delivery_package`

Full delivery gate. Checks:

- All declared platforms have rendered outputs.
- OTIO files exist for all timelines.
- Every rendered output passes `validate_output`.
- Manifest has a name and scanned assets.

Parameters: `project_id`.

---

## Phase 9 / 10: Workflow & Observability

### `get_workflow_status`

Return a pipeline-stage checklist for a project showing which stages are complete and what the next recommended action is.

Stages checked: `project_created`, `assets_scanned`, `timelines_built`, `otio_exported`, `rendered`, `all_platforms_rendered`, `outputs_valid`.

Returns `ok`, `stages`, `next_step`, asset/timeline/output counts, and OTIO/output paths.

Parameters: `project_id`.

### `get_project_logs`

Return structured log records for a project across all sessions.

Returns: `total_records`, `error_count`, `warning_count`, `session_count`, `recent_errors` (last 5), `recent_records` (last 20).

Parameters: `project_id`.
