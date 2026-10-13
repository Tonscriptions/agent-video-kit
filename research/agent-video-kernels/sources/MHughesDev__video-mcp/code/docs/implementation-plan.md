# Long-Term Implementation Plan

This plan defines the intended build sequence for `mcp-editor`: a headless, local-first MCP video editing server that turns existing footage, music, LUTs, and assets into validated rendered videos plus OpenTimelineIO timelines.

## Long-Term Completion Status

Overall long-term application completion: **81%**

This percentage is an engineering estimate of how much of the intended long-term product is implemented, tested, documented, and usable. It is not a calendar estimate.

Current state: **Full editing pipeline implemented; remaining gaps are golden-media integration tests, GitHub release packaging, and benchmark CI integration.**

| Area | Status | Completion |
| --- | --- | ---: |
| Repository scaffold and package setup | Implemented | 100% |
| Local MCP server connection | Implemented | 80% |
| Structured errors and workflow callbacks | Implemented | 80% |
| Media scanning and probing | Phase 2 inspection tools implemented | 60% |
| Project manifest model | Deterministic IDs, POSIX paths, timing fields | 70% |
| Timeline and OTIO export | Phase 3 edit operations implemented | 60% |
| Beat analysis | MVP implemented with planner integration | 35% |
| Beat-synced edit planning | Deterministic Phase 4 planner implemented | 35% |
| FFmpeg render engine | Retry with backoff, per-command timing, dry-run planning | 60% |
| Effects engine | Phase 6: speed_ramp, zoom_punch, smash_cut, reframe, motion_effects, remove_clip_effect | 65% |
| LUT grading system | Phase 7: list_luts, inspect_lut, apply_lut, apply_grading_preset, render_with_grade, 6 built-in presets | 70% |
| Self-validation gate | Phase 8: FPS/resolution/black/silence/freeze checks, validate_audio, validate_platform_outputs, validate_delivery_package | 85% |
| End-to-end prompt workflow | Phase 9: full 9-step pipeline, prompt inference, grading integration, get_workflow_status | 80% |
| Integration tests with real media | 19 end-to-end integration tests with monkeypatched FFmpeg; golden media fixtures not yet added | 55% |
| GitHub publishing and release readiness | v0.8.0 version, CHANGELOG.md, mcp-editor-bench entry point; PyPI publish script not yet added | 30% |
| Hardening and scale | Logging, retry, deterministic IDs, timing, POSIX paths, benchmark suite, tools doc complete | 75% |

Update this section whenever a major phase lands. Keep the percentage conservative: only count behavior that is implemented, tested, and documented enough for another coding agent to use.

## Phase 1: Foundation And Contracts

Define the core project contracts before building editing tools.

- Define the project manifest format for input footage, music, target platforms, style presets, output requirements, and validation requirements.
- Define the internal timeline model for clips, tracks, cuts, transitions, effects, audio regions, and platform variants.
- Define MCP tool conventions for input schemas, output schemas, error format, file path rules, dry-run behavior, and validation metadata.
- Add basic test infrastructure for manifest parsing, timeline models, fixture media, and integration tests.

Goal: stable internal data contracts before editing logic begins.

## Phase 2: Media Inspection Layer

Build tools that let an agent understand source footage before editing.

Initial MCP tools:

- `scan_project_assets`
- `probe_media`
- `analyze_video_metadata`
- `analyze_audio_metadata`
- `detect_scenes`
- `generate_thumbnails`
- `inspect_project`

Core capabilities:

- Use FFprobe and FFmpeg for media metadata.
- Detect duration, FPS, resolution, codecs, and audio streams.
- Identify broken or unsupported files.
- Generate lightweight project manifests.
- Store analysis results in `data/projects/`.

Goal: the agent can inspect footage reliably before making edit decisions.

## Phase 3: Timeline And OTIO Core

Build the non-rendering edit model.

Initial MCP tools:

- `create_project`
- `create_timeline`
- `add_clip`
- `trim_clip`
- `split_clip`
- `move_clip`
- `add_transition`
- `export_otio`
- `validate_timeline`

Core capabilities:

- Build OpenTimelineIO timelines.
- Represent frame-accurate edit decisions.
- Export `.otio` files.
- Validate missing media, invalid ranges, overlapping clips, and bad durations.

Goal: produce valid timelines before producing rendered video.

## Phase 4: Beat Sync And Edit Planning

Add automated cut planning from music and footage analysis.

Initial MCP tools:

- `analyze_beats`
- `analyze_music_energy`
- `suggest_cut_points`
- `plan_beat_synced_edit`
- `apply_edit_plan`

Core capabilities:

- Use `librosa` for beat and tempo detection.
- Detect downbeats and energy peaks.
- Generate cut grids.
- Match clip lengths to beat intervals.
- Support pacing styles such as slow, medium, fast, trailer, social, and documentary.

Goal: the agent can create a coherent beat-synced rough cut.

## Phase 5: FFmpeg Render Engine

Turn timelines into actual video.

Initial MCP tools:

- `render_timeline`
- `render_preview`
- `render_platform_variant`
- `render_all_variants`

Core capabilities:

- Convert timeline operations into FFmpeg commands.
- Render 16:9, 9:16, and 1:1 outputs.
- Handle scaling, cropping, padding, and audio mixing.
- Support render profiles such as preview, standard, and high.
- Write render manifests and logs.

Goal: produce finished video files from validated timelines.

## Phase 6: Effects Engine

Add reusable visual effects and edit grammar.

Initial MCP tools:

- `apply_speed_ramp`
- `apply_zoom_punch`
- `apply_smash_cut`
- `apply_transition`
- `apply_reframe`
- `apply_motion_effects`

Core capabilities:

- Compose FFmpeg filter graphs.
- Support speed ramps, punch zooms, whip or glitch transitions, crossfades, freeze frames, motion crops, and social-platform reframing.

Goal: move from basic assembly to stylized editing.

## Phase 7: Color Grading And LUTs

Add deterministic grading.

Initial MCP tools:

- `list_luts`
- `inspect_lut`
- `apply_lut`
- `apply_grading_preset`
- `render_with_grade`

Core capabilities:

- Load `.cube` LUTs from `data/luts/`.
- Apply LUTs through FFmpeg.
- Support brightness, contrast, saturation, gamma, and vignette controls.
- Store grade choices in timeline and project manifests.
- Validate missing or incompatible LUTs.

Goal: make grading part of the reproducible edit pipeline.

## Phase 8: Self-Validation Gate

Prevent silent bad exports.

Initial MCP tools:

- `validate_render`
- `validate_audio`
- `validate_platform_outputs`
- `validate_delivery_package`

Validation checks:

- File exists and is playable.
- Duration matches the expected timeline.
- Resolution matches the platform target.
- FPS is correct.
- Audio exists unless intentionally muted.
- Output is not fully black.
- Output does not contain unexpected silence.
- Output does not contain frozen-frame failures.
- OTIO export exists.
- Manifest matches rendered outputs.

Goal: every final delivery passes automated quality checks before being reported as complete.

## Phase 9: End-To-End Agent Workflow

Create the full autonomous editing pipeline.

Primary MCP tool:

- `edit_video_from_prompt`

Workflow:

1. Scan assets.
2. Analyze footage.
3. Analyze music.
4. Build edit plan.
5. Create timeline.
6. Apply effects and grading.
7. Render variants.
8. Export OTIO.
9. Validate outputs.
10. Return delivery manifest.

Goal: a coding agent can call one tool with a natural language editing request and receive final video outputs plus OTIO.

## Phase 10: Hardening And Scale

Make the system durable for real use.

Add:

- Better logging.
- Structured render reports.
- Retry behavior.
- Partial render caching.
- Deterministic project IDs.
- Large-file handling.
- Cross-platform path handling.
- Golden media integration tests.
- Benchmark suite.
- Failure recovery.
- Documentation for every MCP tool.

Goal: move from prototype to reliable local production system.

## Recommended Build Order

1. Manifest model.
2. Media probe tools.
3. Timeline model.
4. OTIO export.
5. Basic render.
6. Beat detection.
7. Beat-synced edit planner.
8. Platform variants.
9. Effects.
10. LUT grading.
11. Validation gate.
12. One-shot `edit_video_from_prompt` orchestration.

## Guiding Principle

Build the deterministic editing engine first, then expose it through MCP tools. The natural-language layer should remain outside the server, with the calling agent making creative decisions and the server executing them precisely.
