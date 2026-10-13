# Architecture

`mcp-editor` is a headless, local-first MCP video editing server. It accepts existing footage, audio, LUTs, and project assets, then exposes the full editing workflow as structured MCP tools for an external AI coding agent. The server does not contain its own creative-director LLM; the calling agent supplies intent and invokes deterministic tools.

## Upstream References Reviewed

- `upstream/montage-ai/AGENTS.md`
- `upstream/montage-ai/README.md`
- `upstream/mcp-video/README.md`

## What We Are Keeping From montage-ai

Montage AI is a local-first post-production assistant that polishes existing footage through beat and scene analysis, edit planning, FFmpeg rendering, and timeline output. We will keep these concepts as references, not copy code in this setup phase.

1. Beat sync pipeline

   Keep the idea of analyzing music tempo, beat times, energy, and onset peaks so edits can land on musically meaningful boundaries. The initial `mcp-editor` implementation will live under `src/beat_sync/` and can draw from montage-ai's `audio_analysis.py` patterns while using our own package boundaries and tests.

2. OTIO export

   Keep OpenTimelineIO as the interchange timeline model for final delivery to Premiere Pro, DaVinci Resolve, and other NLEs. The OTIO construction work belongs in `src/timeline/`, using montage-ai's `export/otio_builder.py` and `timeline_exporter.py` as references.

3. Style template system

   Keep the idea of named style presets that influence pacing, cut density, transitions, reframing, and grading choices. In this project, style templates should be data that the external agent can choose or override, not prompts for an internal LLM.

4. FFmpeg render chain

   Keep the FFmpeg-first rendering model, centralized FFmpeg argument construction, encoder-awareness, and progressive segment rendering concepts. This maps primarily to `src/effects/`, `src/grading/`, `src/timeline/`, and future render orchestration inside `src/mcp_server/`.

## What We Are Not Keeping

1. Docker-only workflow

   montage-ai's quick start and deployment path are Docker-centered. `mcp-editor` is being built for a self-hosted local machine with native Python, native FFmpeg, and local data directories. Docker may be added later as packaging, but it is not the foundation.

2. Internal LLM-as-creative-director pattern

   montage-ai routes a user prompt through an internal creative director before constructing edits. `mcp-editor` will not embed that role. The calling coding agent is the creative decision maker and uses MCP tools to inspect media, plan edits, apply operations, render, and validate results.

3. Web UI and human review loop

   montage-ai includes CLI and web workflows. `mcp-editor` has no UI. mcp-video's release checkpoint idea is useful as a guardrail reference, but this project targets autonomous validation before delivery rather than asking a human to review release artifacts.

4. Broad platform concerns before core editing

   We are not carrying over Kubernetes deployment, Redis/job infrastructure, web templates, or Docker resource tuning into the initial architecture.

## What We Are Adding New

1. MCP server layer

   `src/mcp_server/` will expose all operations as MCP tools with typed inputs, structured results, clear error messages, and discoverable capabilities. mcp-video's documented tool categories are a useful reference for tool shape and guardrails, especially around media inspection, editing, effects, analysis, and validation.

2. VFX effects engine

   `src/effects/` will own reusable FFmpeg filter chains for speed ramps, zoom punches, smash cuts, transitions, layout transforms, and platform-specific reframing effects.

3. LUT grading system

   `src/grading/` will load `.cube` LUTs from `data/luts/`, apply grading presets, and provide deterministic FFmpeg grading chains. It should support both explicit user-selected LUTs and style-driven defaults.

4. Self-validation gate

   `src/validation/` will inspect rendered outputs before delivery. Validation should check media existence, duration, codecs, dimensions, audio presence/levels, black frames, frozen frames, timeline/export consistency, platform format requirements, and OTIO availability.

5. Multi-platform output contract

   The render pipeline must produce variants such as 9:16, 16:9, and 1:1 from the same project manifest and timeline plan, with each output validated independently.

## Target Directory Mapping

| mcp-editor module | montage-ai reference | Purpose |
| --- | --- | --- |
| `src/mcp_server/` | `api.py`, `cli.py`, `worker.py`; mcp-video MCP surface | MCP server startup, tool registration, orchestration boundaries, structured responses |
| `src/timeline/` | `export/otio_builder.py`, `timeline_exporter.py`, `editor.py`, `core/montage_builder.py` | OTIO timeline model, edit operations, project manifests, NLE interchange |
| `src/effects/` | `ffmpeg_config.py`, `ffmpeg_utils.py`, `ffmpeg_tools.py`, `segment_writer.py`, `auto_reframe.py` | FFmpeg filter graphs, render chains, reframing, transitions, speed and motion effects |
| `src/grading/` | `cgpu_jobs/lut_generator.py`, style JSON files, FFmpeg filter patterns | LUT loading, grading presets, color transform chains |
| `src/beat_sync/` | `audio_analysis.py`, `audio_analysis_gpu.py`, `clip_scoring.py`, `scene_analysis.py` | Tempo and beat detection, energy analysis, cut-to-beat planning |
| `src/validation/` | `preview_generator.py`, `video_metadata.py`, render pipeline checks; mcp-video preflight and release checkpoints | Post-render validation, media metadata checks, timeline/output consistency gates |
| `src/tools/` | mcp-video documented tool categories | Individual MCP tool definitions and schemas |
| `data/input/` | `data/input/` | Raw footage and source assets |
| `data/music/` | `data/music/` | Music tracks for beat sync |
| `data/luts/` | `data/luts/` | Local `.cube` LUT files |
| `data/output/` | `data/output/` | Rendered videos and validation reports |
| `data/projects/` | Montage output manifests and timeline exports | Per-project manifests, OTIO files, and derived edit plans |

## Initial Build Boundary

This scaffold intentionally stops before implementing MCP tools or porting montage-ai code. The next phase should define the project manifest format, timeline primitives, and the first small MCP inspection tools before adding render operations.
