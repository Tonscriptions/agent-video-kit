# mcp-editor — Agent Contract

This file defines how AI coding agents (Claude Code, Cursor, etc.) should work in this repository.

---

## What this repo is

`mcp-editor` is a headless MCP server that exposes video editing as structured tools. The server does not contain a creative-director LLM. **The calling agent makes creative decisions; the server executes them deterministically.**

---

## Repository layout

```
src/mcp_editor/       ← all server source code
  server.py           ← FastMCP app, all 44 @app.tool registrations
  workflow.py         ← edit_video_from_prompt and project lifecycle
  effects.py          ← FFmpeg filter builders for clip effects
  grading.py          ← LUT and grading preset application
  validation.py       ← render quality gate (black/silence/freeze checks)
  logging.py          ← per-project JSON log files
  render.py           ← FFmpeg command planning and execution
  timeline.py         ← OTIO timeline model and clip operations
  timeline_ops.py     ← MCP-level wrappers for timeline edits
  beat_sync.py        ← librosa beat analysis and edit planner
  inspection.py       ← media inspection tools
  media.py            ← FFprobe wrapper
  schemas.py          ← all Pydantic models
  projects.py         ← manifest load/save, project directory helpers
  config.py           ← workspace root resolution

tests/unit/           ← unit tests (no FFmpeg required)
tests/integration/    ← end-to-end tests (FFmpeg monkeypatched)
docs/
  tools.md            ← full tool reference (44 tools)
  architecture.md     ← design decisions
  implementation-plan.md ← phase-by-phase plan and completion status
scripts/
  setup.sh            ← install dependencies
  verify.sh           ← check all requirements
  benchmark.py        ← pure-Python performance benchmarks
data/
  input/              ← drop footage here
  music/              ← music for beat analysis
  luts/               ← .cube LUT files
  output/             ← rendered .mp4 files
  projects/           ← manifests, OTIO, logs (auto-managed)
```

---

## How to add a new MCP tool

1. Write the implementation function in the appropriate module (`effects.py`, `grading.py`, `validation.py`, etc.).
2. Import it in `server.py` and decorate with `@app.tool()`.
3. Write unit tests in `tests/unit/`.
4. Update `docs/tools.md` with the parameter list and return shape.
5. Update the completion table in `docs/implementation-plan.md`.

Keep the tool registration thin — validate inputs, call the impl function, return `_error(exc)` on failure. Business logic belongs in the impl module.

---

## Data contracts

Every tool must return a dict with at least `ok: bool`. On failure, return:

```python
return _error(exc)  # calls failed_tool_result(exc) from diagnostics.py
```

Which produces:

```json
{
  "ok": false,
  "error": {
    "code": "...",
    "message": "...",
    "suggested_fix": "...",
    "details": {}
  }
}
```

Never let an unhandled exception escape a tool handler.

---

## Schema rules

- All Pydantic models live in `schemas.py`.
- `TimelineClip.effects: list[ClipEffect]` — store per-clip effects here; `build_clip_vf()` in `effects.py` composes them into FFmpeg filters at render time.
- `ProjectManifest.project_id` is deterministic: `deterministic_project_id(name, input_dir)` from `schemas.py`. Do not use `uuid4()` for project IDs.
- Store paths in manifests using `posix_path()` (forward slashes on all platforms).

---

## Platform values

Always use the `Platform` enum from `schemas.py`:

| Enum value | String | Dimensions |
|---|---|---|
| `Platform.widescreen` | `"16:9"` | 1920×1080 |
| `Platform.vertical` | `"9:16"` | 1080×1920 |
| `Platform.square` | `"1:1"` | 1080×1080 |

---

## Effect pipeline order

When `build_clip_vf(clip, platform)` builds the FFmpeg `-vf` chain, effects are applied in this order:

1. `reframe` — crop/offset
2. `zoom_punch` — scale up + crop
3. `speed_ramp` — setpts
4. `motion_blur` — tblend
5. `grade` — lut3d + eq + vignette
6. Platform scale/crop (always last)

---

## Testing conventions

- Unit tests: monkeypatch `probe_media`, `_run_ffmpeg_null`, `_run_command`, `execute_render_manifest` to avoid real FFmpeg.
- Integration tests: use `monkeypatch.setenv("MCP_EDITOR_ROOT", str(tmp_path))` for workspace isolation.
- Never write tests that require real media files to exist.
- All tests must pass with `python -m pytest tests/` before committing.

---

## Development branch

Active development happens on `claude/fervent-pascal-VKE17`. Do not push directly to `main` without a PR.

---

## What NOT to do

- Do not embed an LLM or make HTTP calls to external APIs inside any tool.
- Do not create new top-level modules without updating `server.py` imports.
- Do not use `uuid4()` for project IDs (use `deterministic_project_id()`).
- Do not let tool handlers raise exceptions — always return `_error(exc)`.
- Do not skip `docs/tools.md` updates when adding or changing tools.
