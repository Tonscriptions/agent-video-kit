# Changelog

All notable changes to `mcp-editor` are documented here.

## [0.8.0] — 2026-05-31

### Added — Phase 10: Hardening & Scale
- `logging.py`: `ProjectLogger` writes append-only JSON lines to `data/projects/{id}/logs/`; never raises on `OSError`
- `get_project_logs` MCP tool: returns structured log summary with error/warning counts and last 20 records
- Retry with backoff in render pipeline: `_run_command` retries FFmpeg up to 2× with 1 s / 2 s delays on transient failures
- Per-command timing records in `execute_render_manifest`; `RenderManifest.timing` field serialised to JSON
- `deterministic_project_id()` in `schemas.py`: stable 12-char hex from SHA-256(name + input\_dir) — re-running the same project reuses the same directory
- `posix_path()` helper: normalises manifest paths to POSIX forward slashes for cross-platform portability
- `scripts/benchmark.py`: pure-Python benchmark suite covering filter building, schema serialisation, beat planning, timeline construction, and grading

### Added — Phase 9: End-to-End Agent Workflow
- `edit_video_from_prompt` upgraded to full 9-step pipeline: scan → probe → analyze music → build edit plan → apply grade → render → OTIO → validate delivery → return manifest
- Prompt-driven keyword inference for pacing style and grading preset (longest-match wins)
- `style` and `grade` explicit override parameters on `edit_video_from_prompt`
- `get_workflow_status` MCP tool: pipeline-stage checklist with `next_step` hint

### Added — Phase 8: Self-Validation Gate
- `validate_output` extended: `fps_correct`, `not_black` (blackdetect), `not_silent` (silencedetect), `not_frozen` (freezedetect) checks; all FFmpeg advanced checks skip gracefully when binary is unavailable
- `validate_audio` MCP tool: codec, duration, and silence checks for audio tracks
- `validate_platform_outputs` MCP tool: validates all rendered outputs in a project manifest
- `validate_delivery_package` MCP tool: full delivery gate — renders, OTIO exports, manifest completeness

### Added — Phase 7: Color Grading & LUTs
- `grading.py` module with `list_luts`, `inspect_lut`, `apply_lut`, `apply_grading_preset`, `render_with_grade`, `list_grading_presets`, `build_grade_vf`
- Six built-in grading presets: `cinematic`, `vivid`, `flat`, `bw`, `warm`, `cool`
- Grade stored as `ClipEffect(effect_type="grade")` and composed into the FFmpeg `-vf` chain via `effects.build_clip_vf`

### Added — Phase 6: Effects Engine
- `effects.py` module: `build_clip_vf`, `build_clip_af`, `source_read_duration`
- Six MCP tools: `apply_speed_ramp`, `apply_zoom_punch`, `apply_smash_cut`, `apply_reframe`, `apply_motion_effects`, `remove_clip_effect`
- `ClipEffect` schema model added to `TimelineClip`
- Render pipeline updated to apply per-clip effect filters and correct source read duration

## [0.1.0] — initial scaffold

- Repository scaffold, Python environment, local MCP server connection
- Media scanning and probing (FFprobe)
- Timeline editing and OTIO export
- Beat-sync planning with librosa
- FFmpeg render engine with profiles and dry-run
- Structured error diagnostics and workflow callbacks
