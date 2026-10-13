# Connecting mcp-editor to AI Coding Agents

`mcp-editor` runs as a local MCP server. The recommended connection mode is **stdio** — it works with Claude Desktop, Claude Code, Cursor, and any other MCP-compatible client.

---

## Install

From the repository root:

```bash
uv venv --python 3.11 .venv
uv pip install -e ".[dev]"
```

FFmpeg must also be on `PATH` — see [README.md](../README.md) for install instructions.

Verify everything is ready:

```bash
./scripts/verify.sh
```

---

## Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "mcp-editor": {
      "command": "/absolute/path/to/video-mcp/.venv/bin/mcp-editor",
      "args": ["--transport", "stdio"],
      "env": {
        "MCP_EDITOR_ROOT": "/absolute/path/to/video-mcp"
      }
    }
  }
}
```

**Windows:**

```json
{
  "mcpServers": {
    "mcp-editor": {
      "command": "C:\\path\\to\\video-mcp\\.venv\\Scripts\\mcp-editor.exe",
      "args": ["--transport", "stdio"],
      "env": {
        "MCP_EDITOR_ROOT": "C:\\path\\to\\video-mcp"
      }
    }
  }
}
```

---

## Cursor

Create or edit `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "mcp-editor": {
      "command": "/absolute/path/to/video-mcp/.venv/bin/mcp-editor",
      "args": ["--transport", "stdio"],
      "env": {
        "MCP_EDITOR_ROOT": "/absolute/path/to/video-mcp"
      }
    }
  }
}
```

---

## Claude Code (CLI)

Add to your project's `.claude/settings.json`:

```json
{
  "mcpServers": {
    "mcp-editor": {
      "command": "/absolute/path/to/video-mcp/.venv/bin/mcp-editor",
      "args": ["--transport", "stdio"],
      "env": {
        "MCP_EDITOR_ROOT": "/absolute/path/to/video-mcp"
      }
    }
  }
}
```

Or use the global settings at `~/.claude/settings.json` to make it available in every project.

---

## If the console script isn't on PATH

Use Python directly:

```json
{
  "command": "/absolute/path/to/video-mcp/.venv/bin/python",
  "args": ["-m", "mcp_editor.server", "--transport", "stdio"]
}
```

---

## HTTP mode

For clients that support streamable HTTP:

```bash
mcp-editor --transport streamable-http --host 127.0.0.1 --port 8000
```

The MCP endpoint is:

```
http://127.0.0.1:8000/mcp
```

---

## MCP_EDITOR_ROOT

This environment variable tells the server where to find `data/`. If not set, the server walks up from the current working directory looking for a folder that contains both `data/` and `pyproject.toml`.

Set it to the absolute path of your cloned `video-mcp` directory and it will always resolve correctly regardless of where your agent's working directory is.

---

## Trying it out quickly

Once connected, ask your agent:

> "Scan my footage in data/input and tell me what you find."

The agent will call `scan_project_assets` and return metadata for every video file it finds.

To run the full pipeline:

> "Make a 30-second cinematic edit from the footage in data/input using the music in data/music. Render a 16:9 preview and validate the output."

The agent will call `edit_video_from_prompt` and walk through all 9 pipeline steps.
