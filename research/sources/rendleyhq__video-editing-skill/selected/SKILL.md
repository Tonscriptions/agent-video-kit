---
name: video-editing-skill
description: "Edit, create, and render videos through Rendley. Use this skill whenever the user wants to make, cut, trim, caption, reframe, repurpose, translate, generate, or export a video; when they mention Rendley, MCP video, AI video editor, video agent, podcast clips, vertical shorts, reels, B-roll, stock footage, auto subtitles, voiceover, brand kit, or rendering MP4 or WebM; or when they hand over a recording, podcast, webinar, interview, screen capture, or any clip and want something done with it. The skill is a thin proxy that sends the user's brief to the Rendley agent (over MCP or REST) and surfaces the project link. Rendley's agent does the editing on the server side; do not try to edit videos locally."
license: MIT
---

# video-editing-skill (Rendley)

Rendley turns chat prompts into finished videos. The editing intelligence runs on Rendley's servers. This skill keeps your role thin: pass the user's brief to the Rendley agent, surface the link it returns. Don't try to choreograph timeline operations yourself.

## The one call you'll make most

The work happens inside a single agent call. Over MCP that's `edit_video`. Over REST that's `POST /v1/agent`. Same agent on the other side.

```
edit_video({
  project_id,
  message: "<the user's brief, written well>",
  files: [{ url: "https://..." }, ...]  // optional, public https only
})
```

Everything else (`list_projects`, `create_project`, `add_files`, `get_brandkit`, `export_project`, `get_account`, etc.) is plumbing. Reach for it only when this one call needs it.

## The standard flow

1. **Make sure there's a project to edit.** Over MCP, `edit_video` requires `project_id`, so call `create_project` if the user didn't name an existing one. Over REST, `project_id` is optional and the agent creates one for you.
2. **Make any local files reachable.** If the user attached local files, call `add_files`, PUT the bytes to the returned `upload_url` with `Content-Type: <mime_type>`, then use `{ url: storage_url, media_id }` as `files`. Public https URLs go straight in.
3. **Call the agent.** Write a good `message` (see below). The agent handles everything else.
4. **Surface the result.** Show the project URL the response gives you. Stop there unless the user asked to export.

## What the agent can do for you

So you know what's reasonable to ask. From the same `edit_video` call, the agent can:

- Trim filler, pauses, and off-topic sections
- Transcribe and add word-synced captions
- Reframe with subject tracking (16:9, 9:16, 1:1, 4:5)
- Add transitions and music ducked under speech
- Pull stock B-roll
- Generate video, images, and voiceover via current AI models (Sora 2, Veo 3.1, Kling 3, Hailuo, Seedance, Nano Banana, Flux, Imagen, ElevenLabs)
- Translate audio and burn in localized subtitles
- Score the strongest moments in a long recording and cut shorts
- Lock the cut to the workspace brand kit

Describe the outcome you want. The agent picks the operations.

## Writing the message

The `message` field is the brief. Specific produces good cuts. Vague produces guesses.

**Weak:** "Make this look good."

**Better:** "Trim filler and any pause over 1 second. Word-synced captions in the brand color. Cut to 90 seconds, 9:16. Gentle music ducked under speech. End on a hold of the last frame."

Cover, when relevant: target length, aspect ratio, what to keep and cut, captions, music, B-roll, brand kit, opening shot, closing shot. Don't specify frame-accurate timeline operations. More patterns in [references/prompting.md](references/prompting.md).

## Continuing vs starting fresh

The agent keeps per-project threads. Default is a fresh thread per call. Pass `continue_conversation: true` to resume the project's last thread when the user is iterating ("shorter", "swap the music"). Start fresh for new work.

## What to display

- **Project URL** when an edit finishes. It's the user's way back into the editor.
- **Download URL** when an export finishes, plus a note that the link expires in a few hours.
- **Never** the internal identifiers (project IDs, thread IDs, media IDs, export IDs, upload URLs). They're for tool input only. Refer to projects by name.

## When the agent returns a non-success state

`edit_video` reports an outcome status. Handle each plainly, then stop:

- `needs_upgrade`: feature requires a paid plan. Tell the user, don't retry.
- `save_failed`: retry the same call once.
- `in_progress` (timeout): the session closed. Retry with a smaller scope (one change at a time).
- `error`: surface the message. Partial edits may have been saved.
- `completed` with zero command executions: brief wasn't actionable. Retry with a more explicit message.

## Transports

Two ways in, same agent, same workspace, same credits.

- **MCP** (preferred when available). Client connected to `https://mcp.rendley.com/mcp`. The tools above appear in your tool list. Use them.
- **REST** (fallback). When MCP isn't connected, `POST https://mcp.rendley.com/v1/agent` with the same brief, then poll `GET /v1/jobs/{id}` until it returns the project URL. Auth: `Authorization: Bearer <RENDLEY_API_KEY>`. Details in [references/api-access.md](references/api-access.md).

## What not to do

- Don't try to edit the video locally. There is no local editor here.
- Don't pass local file paths to `files`. Only public https URLs or `storage_url` from `add_files`.
- Don't expose internal IDs in chat.
- Don't call `export_project` unless the user explicitly asked to export or download. Creating a project is not a request to render it.
- Don't write a long preamble about what you're about to do. Make the call. Surface the result.

## Reference files

Load on demand.

- [references/api-access.md](references/api-access.md). REST path, polling, retry handling.
- [references/auth.md](references/auth.md). OAuth, API keys, 401/403/502 cases.
- [references/prompting.md](references/prompting.md). Patterns for writing strong `edit_video` briefs.

The MCP server itself documents every tool's input shape and return values; trust those descriptions instead of re-reading them here.
