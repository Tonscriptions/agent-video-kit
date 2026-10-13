# CapCut Desktop MCP Server & Agent Skills 🎬

[![CI](https://github.com/AiPersonacademy/capcut-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/AiPersonacademy/capcut-mcp/actions/workflows/ci.yml)
[![GitHub Stars](https://img.shields.io/github/stars/AiPersonacademy/capcut-mcp?style=social)](https://github.com/AiPersonacademy/capcut-mcp)
[![GitHub Forks](https://img.shields.io/github/forks/AiPersonacademy/capcut-mcp?style=social)](https://github.com/AiPersonacademy/capcut-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js Version](https://img.shields.io/badge/node-%3E%3D18.0.0-brightgreen)](https://nodejs.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-1.6.1-blue)](https://modelcontextprotocol.io/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8-blue)](https://www.typescriptlang.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> **Enterprise-grade Model Context Protocol (MCP) server & Agent Skills for CapCut Desktop & JianYing Pro (剪映)**.  
> Programmatic video editing, multi-track timeline construction, Quad Ease keyframing, and viral typography for **Claude Desktop**, **Cursor AI**, **Google Antigravity**, **Cline**, and **Windsurf**.

---

## 📑 Table of Contents

- [Why CapCut MCP?](#-why-capcut-mcp)
- [Architecture & Direct AST Engine](#-architecture--direct-ast-engine)
- [Key Features](#-key-features)
- [Quick Start](#-quick-start)
- [Client Configuration](#-client-configuration)
  - [Claude Desktop](#claude-desktop)
  - [Cursor AI](#cursor-ai)
  - [Google Antigravity](#google-antigravity)
  - [Windsurf & Cline](#windsurf--cline)
- [MCP Tools Reference (24 Atomic Tools)](#-mcp-tools-reference-24-atomic-tools)
- [Viral Typography Engine](#-viral-typography-engine)
- [AI Agent Skills & Editorial Playbooks](#-ai-agent-skills--editorial-playbooks)
- [Testing & Quality Assurance](#-testing--quality-assurance)
- [Contributing](#-contributing)
- [License](#-license)

---

## 💡 Why CapCut MCP?

Traditional AI video editing attempts rely on brittle GUI automation: simulating mouse clicks, keystrokes, and window focusing that fail when UI elements shift or screen resolutions vary.

**CapCut MCP takes an entirely different approach:**
- **Direct AST Manipulation**: It reads and writes directly to CapCut's native `draft_content.json` Abstract Syntax Tree (AST).
- **Instant & Deterministic**: Timelines, multi-track sequences, cuts, speed ramps, and keyframes apply in milliseconds without opening the GUI.
- **Cross-Platform**: Works natively with both **CapCut Global** and **JianYing Pro (剪映)** on Windows and macOS.
- **Zero Window Focus**: Edits run cleanly in the background while you continue working.

---

## 📐 Architecture & Direct AST Engine

```
User Prompt (e.g. "Cut dead air, add viral captions, punch zoom on keywords")
                                │
                                ▼
         AI Agent (Claude Desktop / Cursor / Antigravity)
                                │
                                ▼ (Model Context Protocol JSON-RPC)
                        capcut-mcp-server
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
CapCut Path Resolver     Media Probe (FFprobe)    Draft Manager
(CapCut Global / JianYing)                              │
                                                        ▼
                                                  Draft Builder
                                             (Native AST Generator)
                                                        │
                                                        ▼
                                          CapCut Project Directory
                                         (%LOCALAPPDATA%/CapCut/...)
                                                        │
                                                        ▼
                                       Native CapCut Project Ready
```

1. **`paths.ts`**: Dynamically detects CapCut Global or JianYing Pro directories without hardcoded user paths.
2. **`draft-builder.ts`**: Pure deterministic constructor for clips, keyframes, transitions, text materials, and multi-track audio.
3. **`draft-manager.ts`**: High-level timeline orchestrator providing safe atomic file writes and project registration.
4. **`preview-renderer.ts`**: Generates headless proxy MP4 previews via FFmpeg without launching the CapCut application.

---

## ✨ Key Features

- 🎬 **24 Atomic Video Editing Tools**: Complete programmatic control over projects, multi-track timelines, transformations, speed scaling, audio fades, subtitles, and keyframes.
- ⚡ **Multi-Track Orchestration**: Base A-roll, overlay B-roll layers, background music with audio ducking (-12dB), sound effects, and text caption tracks.
- 🔥 **Viral Typography Engine**: Built-in support for high-retention short-form styles (Style 6 Glow Pop, Style 7 Hero Typography, -1.0 metric tracking, ambient drop shadows, and scale pop animations).
- 📈 **Mathematical Keyframing & Easing**: Quad Ease Out curves, kinetic punch-in zooms, smooth opacity transitions, and position pans.
- 🎯 **Synchronized Subtitles**: Parse and import standard SRT files directly into formatted native CapCut text layers.
- 🖼️ **Fast Headless Previews**: Render fast proxy preview MP4s using FFmpeg without opening the CapCut GUI.
- 🤖 **Production Agent Skills Included**: Battle-tested prompt playbooks and references in `skills/capcut/` covering Walter Murch's Rule of Six, B-roll sourcing, and Quad Easing.

---

## 🚀 Quick Start

### 1. Global Installation (Recommended)

```bash
# Run directly via npx
npx capcut-mcp-server

# Or install globally via npm
npm install -g capcut-mcp-server
```

### 2. Run from Source

```bash
git clone https://github.com/AiPersonacademy/capcut-mcp.git
cd capcut-mcp
npm install
npm run build
npm test
npm start
```

---

## 🔌 Client Configuration

### Claude Desktop

Add this configuration to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "capcut": {
      "command": "npx",
      "args": ["-y", "capcut-mcp-server"]
    }
  }
}
```

*Config file locations:*
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

---

### Cursor AI

Add to your `.cursor/mcp.json` or global MCP settings:

```json
{
  "mcpServers": {
    "capcut": {
      "command": "npx",
      "args": ["-y", "capcut-mcp-server"]
    }
  }
}
```

---

### Google Antigravity

Add to your `mcp_config.json`:

```json
{
  "mcpServers": {
    "capcut": {
      "command": "node",
      "args": ["<ABSOLUTE_PATH_TO_CAPCUT_MCP>/dist/src/index.js"]
    }
  }
}
```

---

### Windsurf & Cline

Configure the stdio command:

```json
{
  "mcpServers": {
    "capcut": {
      "command": "npx",
      "args": ["-y", "capcut-mcp-server"]
    }
  }
}
```

---

## 🛠️ MCP Tools Reference (24 Atomic Tools)

| Tool Name | Category | Description | Key Parameters |
|:---|:---|:---|:---|
| `capcut_list_projects` | Projects | Lists all local CapCut projects with duration, resolution, and track counts | *None* |
| `capcut_get_project` | Projects | Fetches the full timeline structure, tracks, media materials, and duration | `project_name_or_id` |
| `capcut_create_project` | Projects | Creates a new project draft with custom canvas dimensions (e.g. 1080x1920) | `name`, `width`, `height`, `ratio`, `fps` |
| `capcut_duplicate_project` | Projects | Duplicates an existing project draft under a new name | `source_project_name_or_id`, `new_project_name` |
| `capcut_delete_project` | Projects | Safely deletes a project folder from CapCut storage | `project_name_or_id` |
| `capcut_open_app` | Projects | Launches CapCut Desktop or opens project directory in Explorer | `project_name_or_id` |
| `capcut_add_video_clip` | Timeline | Inserts or appends a video clip onto any track index | `project_name_or_id`, `file_path`, `track_index`, `start_time` |
| `capcut_add_audio_clip` | Audio | Adds background music or voiceover with volume control | `project_name_or_id`, `file_path`, `track_index`, `volume` |
| `capcut_add_sound_effect` | Audio | Inserts SFX (whooshes, pops, risers, impacts) at exact timestamps | `project_name_or_id`, `file_path`, `start_time` |
| `capcut_add_audio_fade` | Audio | Applies smooth fade-in and fade-out volume curves | `project_name_or_id`, `track_index`, `clip_index`, `fade_in`, `fade_out` |
| `capcut_trim_clip` | Editing | Trims in/out source points and target duration of an existing clip | `project_name_or_id`, `track_index`, `clip_index`, `source_start`, `source_duration` |
| `capcut_split_clip` | Editing | Splits a clip at an exact timeline timestamp | `project_name_or_id`, `track_index`, `clip_index`, `split_timestamp` |
| `capcut_remove_clip` | Editing | Removes a specific clip from a timeline track | `project_name_or_id`, `track_index`, `clip_index` |
| `capcut_set_clip_transform` | Transform | Adjusts 2D position `(x, y)`, scale multiplier, and rotation degrees | `project_name_or_id`, `track_index`, `clip_index`, `x`, `y`, `scale`, `rotation` |
| `capcut_set_clip_speed` | Transform | Modifies speed multiplier (0.1x to 100.0x) with pitch preservation | `project_name_or_id`, `track_index`, `clip_index`, `speed`, `change_pitch` |
| `capcut_add_keyframe` | Animation | Adds keyframe animation for scale, position, or opacity | `project_name_or_id`, `track_index`, `clip_index`, `property`, `time_offset`, `value` |
| `capcut_add_transition` | Transitions | Adds native video transitions (dissolve, push, zoom, wipe) | `project_name_or_id`, `track_index`, `clip_index`, `transition_type`, `duration` |
| `capcut_add_text` | Text | Injects static text, titles, or lower thirds | `project_name_or_id`, `text`, `start_time`, `duration`, `font_size`, `color` |
| `capcut_add_subtitles` | Text | Parses and imports complete SRT subtitle files into text tracks | `project_name_or_id`, `srt_content`, `font_size`, `color` |
| `capcut_add_viral_caption` | Text | Adds viral dynamic caption with accent words and hover-pop animations | `project_name_or_id`, `text`, `power_words`, `accent_color`, `font_family` |
| `capcut_add_sticker` | Graphics | Places graphic stickers or overlays on the timeline | `project_name_or_id`, `sticker_id`, `start_time`, `duration` |
| `capcut_create_video_bridge` | Sequencing | Creates a multi-track sequenced project with video plates & audio ducking | `project_name`, `video_plate_path`, `audio_tracks`, `subtitles_srt_path` |
| `capcut_get_media_info` | Utilities | Probes video/audio resolution, duration, codecs, and framerate | `file_path` |
| `capcut_generate_preview` | Utilities | Generates a fast proxy preview MP4 via headless FFmpeg | `project_name_or_id`, `output_path`, `resolution` |

---

## 🎨 Viral Typography Engine

Short-form retention depends on visual stimulation and dynamic typography. CapCut MCP comes with pre-calibrated viral styles accessible via `capcut_add_viral_caption`:

### Style 6: Glow Pop
- **Font**: Montserrat ExtraBold / Impact
- **Primary Color**: High-saturation electric yellow (`#FFE600`) or lime (`#00FF66`)
- **Stroke**: Heavy black outline (`#000000`, width `12-16`)
- **Drop Shadow**: Ambient soft blur
- **Pop Motion**: Scale burst (1.15x -> 1.0x) over 120ms at word boundary

### Style 7: Hero Typography
- **Character Spacing**: `-1.0` metric tracking (tight, cinematic feel)
- **Casing**: Uppercase
- **Shadow Offset**: `(26, 26)` with 85% opacity
- **Color Accent**: Single focal word highlighted in cyan (`#00E5FF`) or electric magenta (`#FF0055`)

---

## 🤖 AI Agent Skills & Editorial Playbooks

This repository includes a dedicated Agent Skill located at [`skills/capcut/SKILL.md`](skills/capcut/SKILL.md).

When connected to an AI agent, the agent can autonomously follow the **Autonomous Editing Playbook**:
1. **Probe**: Inspect raw files with `capcut_get_media_info`.
2. **Scaffold**: Create the project canvas with `capcut_create_project`.
3. **Assemble A-Roll**: Place primary speech clips on Track 0 with `capcut_add_video_clip`.
4. **Synchronize Subtitles**: Inject timed captions with `capcut_add_subtitles` or kinetic titles with `capcut_add_viral_caption`.
5. **Overlay B-Roll**: Insert relevant visual cutaways on Track 1 with punch-in zoom keyframes.
6. **Sound Design**: Add background music (ducked to -12dB) with `capcut_add_audio_clip` and impact transients with `capcut_add_sound_effect`.
7. **Review**: Generate an instant proxy preview with `capcut_generate_preview` or open CapCut Desktop with `capcut_open_app`.

For comprehensive editorial reference manuals, see:
- [CapCut Master Manual](skills/capcut/references/capcut_master_manual.md)
- [B-Roll Production Manual](skills/capcut/references/broll_production_manual.md)

---

## 🧪 Testing & Quality Assurance

The test suite validates timeline calculations, AST segment generation, track collisions, speed scaling, and SRT subtitle ingestion:

```bash
npm test
```

```
▶ CapCut MCP Server - Comprehensive Suite
  ✔ SrtParser parses standard SRT format accurately (3.0ms)
  ✔ DraftManager creates a 9:16 project and registers in root meta (46.1ms)
  ✔ MediaProbe and addVideoClip with synthetic video (219.5ms)
  ✔ DraftManager adds audio clip (133.6ms)
  ✔ DraftManager sets clip transform (24.3ms)
  ✔ DraftManager trims existing clip (16.4ms)
  ✔ DraftManager adds transition to clip (27.2ms)
  ✔ DraftManager adds keyframe to clip (16.5ms)
  ✔ DraftManager adds sticker to project (25.0ms)
  ✔ DraftManager renders fast proxy preview via ffmpeg (409.5ms)
  ✔ DraftManager adds text overlays to a project (19.8ms)
  ✔ DraftManager adds synchronized subtitles from SRT (22.8ms)
  ✔ DraftManager splits an existing clip accurately (25.2ms)
  ✔ DraftManager sets clip speed and preserves pitch (26.8ms)
  ✔ DraftManager adds audio fade-in and fade-out (25.1ms)
  ✔ DraftManager adds viral caption with Aeovisuals styling (23.4ms)
  ✔ DraftManager creates video bridge draft (203.1ms)
  ✔ DraftManager adds transient sound effect (96.8ms)
  ✔ DraftManager duplicates a project (22.3ms)
  ✔ DraftManager deletes a project safely (13.1ms)
✔ CapCut MCP Server - Comprehensive Suite (2805ms)
ℹ tests 21 | pass 21 | fail 0
```

---

## 🤝 Contributing

Contributions are warmly welcomed! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on development workflow, code style, and PR submissions.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.
