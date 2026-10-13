# mcp-editor

A headless, local-first MCP video editing server for AI coding agents.

You give it footage, music, and LUTs. An AI agent calls its tools to inspect media, cut a timeline, apply effects and color grades, render platform variants, and validate the delivery package — all on your own machine, no cloud dependency.

> **Version 0.8.0** — 44 MCP tools, full pipeline implemented.

---

## What it does

```
footage + music + LUTs
        │
        ▼
   mcp-editor (local MCP server)
        │
        ├── scan & probe footage
        ├── analyze music beats
        ├── build beat-synced timeline
        ├── apply effects (speed ramp, zoom punch, reframe, …)
        ├── apply color grade (LUT or preset)
        ├── render 16:9 / 9:16 / 1:1 via FFmpeg
        ├── export OpenTimelineIO (.otio)
        └── validate delivery package
        │
        ▼
  rendered .mp4 files + .otio timeline + delivery report
```

The agent drives creative decisions. The server executes them deterministically.

---

## Requirements

| Dependency | Install |
|---|---|
| Python 3.11+ | [python.org](https://www.python.org/downloads/) |
| FFmpeg + FFprobe | see below |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Git | [git-scm.com](https://git-scm.com/) |

**Install FFmpeg:**

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows
winget install Gyan.FFmpeg
```

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/MHughesDev/video-mcp.git
cd video-mcp
uv venv --python 3.11 .venv
uv pip install -e ".[dev]"

# 2. Verify everything is wired up
./scripts/verify.sh

# 3. Drop footage into data/input/ and (optionally) music into data/music/
cp my-clips/*.mp4 data/input/
cp my-track.mp3 data/music/

# 4. Start the server
mcp-editor --transport stdio
```

From your agent, call `edit_video_from_prompt` to run the full pipeline in one shot:

```json
{
  "tool": "edit_video_from_prompt",
  "arguments": {
    "prompt": "cinematic highlight reel, golden warm tones",
    "project_name": "my-edit",
    "input_dir": "data/input",
    "music_path": "data/music/my-track.mp3",
    "platforms": ["16:9", "9:16"],
    "target_duration": 30,
    "dry_run": true
  }
}
```

Set `dry_run: false` to execute real FFmpeg renders.

---

## Connect to your AI agent

### Claude Desktop / Claude Code

Add to `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`):

```json
{
  "mcpServers": {
    "mcp-editor": {
      "command": "/path/to/video-mcp/.venv/bin/mcp-editor",
      "args": ["--transport", "stdio"],
      "env": {
        "MCP_EDITOR_ROOT": "/path/to/video-mcp"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "mcp-editor": {
      "command": "/path/to/video-mcp/.venv/bin/mcp-editor",
      "args": ["--transport", "stdio"],
      "env": {
        "MCP_EDITOR_ROOT": "/path/to/video-mcp"
      }
    }
  }
}
```

**Windows** — use the `.exe` path from `.venv\Scripts\`:

```json
{
  "command": "C:\\path\\to\\video-mcp\\.venv\\Scripts\\mcp-editor.exe"
}
```

### HTTP mode (any MCP client)

```bash
mcp-editor --transport streamable-http --host 127.0.0.1 --port 8000
# endpoint: http://127.0.0.1:8000/mcp
```

See [docs/custom-mcp-server.md](docs/custom-mcp-server.md) for more client configuration examples.

---

## Data layout

```
data/
├── input/      ← drop your footage here (.mp4 .mov .mkv .webm .avi .m4v)
├── music/      ← music tracks for beat analysis
├── luts/       ← .cube LUT files for color grading
├── output/     ← rendered .mp4 files land here
└── projects/   ← manifests, OTIO files, logs (auto-managed)
```

---

## Tool reference (44 tools)

### Media inspection
| Tool | What it does |
|---|---|
| `scan_assets` | Scan a directory for video assets |
| `scan_project_assets` | Scan with aggregate counts and diagnostics |
| `probe_media` | FFprobe metadata for one file |
| `analyze_video_metadata` | Video-focused metadata (codec, FPS, resolution) |
| `analyze_audio_metadata` | Audio-focused metadata (codec, channels, sample rate) |
| `detect_scenes` | Scene-cut timestamps via FFmpeg scene scoring |
| `generate_thumbnails` | Extract representative thumbnail frames |
| `inspect_project` | Full project state: assets, timelines, outputs |

### Project & timeline
| Tool | What it does |
|---|---|
| `create_project` | Create a project manifest from local assets |
| `create_timeline` | Build a simple sequential OTIO timeline |
| `add_clip` | Add a clip to a timeline |
| `trim_clip` | Trim a clip's in/out points |
| `split_clip` | Split a clip into two |
| `move_clip` | Reorder clips |
| `add_transition` | Add a crossfade or transition between adjacent clips |
| `export_timeline` | Export timeline to `.otio` |
| `validate_timeline` | Check for missing media, invalid ranges, bad durations |

### Beat sync & edit planning
| Tool | What it does |
|---|---|
| `analyze_beats` | Detect tempo and beat timestamps with librosa |
| `suggest_cut_points` | Generate cut grid from beats + pacing style |
| `plan_beat_synced_edit` | Create a deterministic beat-synced edit plan |
| `apply_edit_plan` | Apply a saved beat plan to a timeline |

### Effects
| Tool | What it does |
|---|---|
| `apply_speed_ramp` | Speed up or slow down a clip |
| `apply_zoom_punch` | Punch zoom into a clip |
| `apply_smash_cut` | Remove transition for a hard cut |
| `apply_reframe` | Crop-reframe for social platform framing |
| `apply_motion_effects` | Apply multiple effects to a clip in one call |
| `remove_clip_effect` | Remove a named effect from a clip |

### Color grading
| Tool | What it does |
|---|---|
| `list_luts` | List `.cube` LUT files in `data/luts/` |
| `inspect_lut` | Parse LUT metadata (size, type, domain) |
| `apply_lut` | Apply a `.cube` LUT to clips |
| `list_grading_presets` | List built-in presets |
| `apply_grading_preset` | Apply a preset: `cinematic` `vivid` `flat` `bw` `warm` `cool` |
| `render_with_grade` | Render with grades baked into FFmpeg filter chain |

### Rendering
| Tool | What it does |
|---|---|
| `plan_render` | Plan FFmpeg commands without executing (dry-run) |
| `render_project` | Render one platform variant |
| `render_platform_variant` | Same as above, explicit platform parameter |
| `render_all_variants` | Render all declared platform variants |

### Validation
| Tool | What it does |
|---|---|
| `validate_output` | Check resolution, FPS, black frames, silence, freezes |
| `validate_audio` | Audio codec, duration, and silence check |
| `validate_platform_outputs` | Validate all rendered outputs in a project |
| `validate_delivery_package` | Full gate: renders + OTIO + manifest completeness |

### Workflow & observability
| Tool | What it does |
|---|---|
| `edit_video_from_prompt` | Full 9-step pipeline from a natural language prompt |
| `get_workflow_status` | Pipeline checklist: what's done, what's next |
| `get_project_logs` | Structured log records with error/warning counts |

Full parameter documentation: [docs/tools.md](docs/tools.md)

---

## Pacing styles

Used by `suggest_cut_points`, `plan_beat_synced_edit`, and inferred by `edit_video_from_prompt`:

| Style | Description |
|---|---|
| `trailer` | Dense cuts on every beat, high energy |
| `social` | Short-form pacing for reels |
| `fast` | Quick cuts, energetic |
| `medium` | Balanced default |
| `slow` / `documentary` | Longer clips, breathing room |

## Built-in color presets

| Preset | Look |
|---|---|
| `cinematic` | Muted tones, lifted blacks |
| `vivid` | Punchy colours, high contrast |
| `flat` | Low contrast, log-style |
| `bw` | Black and white |
| `warm` | Golden-hour tones |
| `cool` | Blue-tinted, desaturated |

---

## Running tests

```bash
# Unit tests
python -m pytest tests/unit/

# Integration tests (no real FFmpeg needed)
python -m pytest tests/integration/

# Full suite
python -m pytest tests/

# Benchmark (pure-Python hot paths)
python scripts/benchmark.py
```

---

## Architecture

The server is intentionally split:

- **Agent** — supplies creative intent, calls tools, interprets results
- **mcp-editor** — executes deterministically: probe, plan, render, validate

There is no LLM inside the server. Prompts are stored in the project manifest for reproducibility, but the calling agent is responsible for all creative decisions.

See [docs/architecture.md](docs/architecture.md) for design rationale and [docs/tools.md](docs/tools.md) for the full tool reference.

---

## Contributing

See [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md).

## License

See [LICENSE](LICENSE).
