---
name: davinci-autoedit-agent
description: End-to-end, approval-gated video editing workflow for arbitrary user-selected video, audio, and optional image media. Use when Codex must scan footage, review and classify material, develop a topic into a script, optionally generate TTS, create an edit blueprint, or build and audit a DaVinci Resolve timeline without assuming a genre, drive, date, camera, platform, or API provider.
---

# DaVinci AutoEdit Agent

Run a source-safe workflow from media intake to an audited edit. Use the
bundled `viral-video-writer` for scripts and `davinci-resolve-editor` for
Resolve operations.

## Opening Message

Start by telling the user:

> I can inspect your chosen media, build a review and tag map, develop the
> story and script, optionally prepare TTS, create a shot-by-shot edit
> blueprint, and then build and audit a DaVinci Resolve timeline. I will show
> you each creative artifact for approval before writing it or using it in the
> next stage. Your source files remain unchanged.

Then collect only missing information:

1. Media path or paths. Accept any accessible video/audio directory or file.
2. Topic, purpose, audience, platform, target duration, aspect ratio, and
   language. Do not impose a subject.
3. Ask: "Do you have your own pacing rules, editing practices, references, or
   non-negotiables?" If yes, record them. If no, offer the best-practice
   profile in `references/editorial-best-practices.md`.
4. Ask whether narration/TTS is wanted. Do not assume it.
5. Ask whether Resolve timeline construction is wanted or only a blueprint.

Summarize the brief in chat and obtain approval before writing `project-brief.json`.

## Approval Contract

Read-only inspection does not require repeated confirmation. Before creating
or replacing an artifact, show a concise preview, list the intended path, and
ask for explicit approval.

Use these gates:

1. Project brief
2. Scan scope and exclusions
3. Material review and taxonomy
4. Story direction and script
5. TTS plan, only when enabled
6. Edit blueprint
7. Resolve project/timeline write
8. Color, audio, render, or source-derivative operations
9. Pickup-shot and missing-material report

Approval for one gate does not authorize later gates. Never overwrite a
previous approved artifact; create a versioned file unless replacement was
explicitly requested.

## Configuration

Before API-backed work, run:

```bash
python scripts/check_setup.py
```

If an API is missing, ask whether the user wants to configure it.

- If yes, read `references/configuration.md`, explain the minimum variables,
  help create `.env`, test connectivity without printing secrets, and ask
  before the first billable request.
- If no LLM API, continue with Codex-native visual inspection where available,
  or produce a manual review worksheet.
- If no TTS API or the user declines configuration, set `tts.enabled=false`
  and remove TTS from the plan. Do not keep asking.
- If Resolve MCP is absent, offer blueprint-only delivery or the documented
  Resolve Python fallback.

All endpoints, keys, models, voices, reference audio, media roots, music
libraries, LUTs, and output paths are user configuration. Never ship private
defaults.

## Workflow

### 1. Create The Run Folder

After brief approval, create:

```text
workspace/runs/<project-slug>/
  project-brief.json
  scan/
  review/
  script/
  tts/
  blueprint/
  resolve/
```

### 2. Scan Media

Preview the paths and extension policy, then run:

```bash
python scripts/scan_media.py --input "<path>" --output "<run>/scan"
```

Pass `--input` repeatedly for multiple roots. Accept common video, audio, and
image formats. Use FFprobe metadata when available. Do not filter by date or
camera unless the user requests it.

Review `media-manifest.json` and confirm:

- file counts and total duration by media type
- unreadable or missing files
- source groups/cameras inferred only as provisional labels
- duplicate candidates
- explicit exclusions

Obtain approval before analysis derivatives such as extracted frames.

After approval, a provider-neutral fixed-interval extractor is available:

```bash
python scripts/extract_frames.py --manifest "<run>/scan/media-manifest.json" --output "<run>/review/frames"
```

### 3. Analyze And Review

For video, sample enough frames to represent scene changes and long takes.
For audio, inspect duration, channels, loudness when tooling supports it, and
transcribe only with permission. Treat images as selectable visual assets.

When the user approved an API-backed batch, run:

```bash
python scripts/analyze_frames.py --frames-index "<run>/review/frames/frames-index.json" --output "<run>/review/frame-analysis.jsonl" --topic "<user topic>"
```

Use evidence-based labels: scene, people, action, dialogue, emotion, quality,
continuity, source group, narrative use, and visible text. Never reject an
entire camera family because derivative files or early samples look weak.

Produce a review preview with:

- chronological inventory
- strongest moments and why
- weak/duplicate/technical-risk material
- camera/source counts and usable-duration estimates
- possible story beats
- unanswered factual questions

After approval, write `review/material-review.json` and `.md`.

### 4. Write The Story

Invoke `viral-video-writer`. Give it the approved brief and material review,
not imagined footage. Present:

- one core idea
- 2-3 story structures
- intended emotional curve
- narration policy
- five title/hook options when relevant

After the user chooses a direction, draft the full script. Show it in chat and
write only after approval.

### 5. Decide TTS

If narration is disabled, skip this stage and design around dialogue, natural
sound, music, captions, or silence.

If enabled, confirm provider, endpoint, model, voice/reference audio, language,
segmenting, pronunciation, and output directory. Preview `tts-plan.json`
before any request. Generate only after approval:

```bash
python scripts/generate_tts.py --script "<approved.json>" --output "<run>/tts"
```

Audit every output for duration, clipping, empty files, pronunciation, and
segment order. Never bundle or publish a user's voice samples.

### 6. Build The Blueprint

Create a source-grounded JSON blueprint following
`references/blueprint-schema.md`. Every clip must identify source path,
source in/out, timeline in/out, purpose, audio policy, and confidence.

Apply the user's editing practice. If none was supplied, use
`references/editorial-best-practices.md`.

Audit before presenting:

- target duration and pacing
- source range within media duration
- no accidental adjacent repetition across section boundaries
- meaningful source/camera diversity where available
- dialogue/narration synchronization
- still-image duration handling
- music and LUT authorization

Write the blueprint only after approval.

Validate it before Resolve:

```bash
python scripts/validate_blueprint.py "<run>/blueprint/edit-blueprint.json"
```

### 7. Build In Resolve

Invoke `davinci-resolve-editor`. Confirm Resolve is open and the current
project/timeline identity. Prefer the registered MCP tools; configured files
alone do not prove MCP availability.

Before writing, state the exact new project/timeline name and affected tracks.
Create a new project or duplicated timeline for every substantial revision.
Do not modify user audio, grades, BGM, or existing tracks without approval.

When MCP is unavailable but the official Python API is configured, use:

```bash
python scripts/build_resolve_timeline.py "<run>/blueprint/edit-blueprint.json"
```

### 8. Audit Delivery

Read back the final Resolve state. Verify:

- actual project and timeline names
- expected item counts by track
- timeline frame origin
- gaps/overlaps and one-frame boundary errors
- source paths and source range bounds
- source/camera ratios and zero-use available groups
- adjacent repeated source
- LUT write and readback, when authorized
- audio writes actually succeeded, when authorized
- report belongs to the currently delivered timeline

A failed build report is not a delivery. Save the report under `resolve/` and
summarize unresolved manual work honestly.

### 9. Recommend Pickup Shots

After the edit audit, compare three sources of truth:

1. The approved script, including every factual, emotional, and explanatory
   beat it asks the viewer to understand.
2. The finished timeline, including the actual image and sound covering each
   beat.
3. The complete reviewed media inventory, so an unused existing shot is not
   incorrectly labeled as missing.

Identify all necessary but absent material. A shot is necessary when its
absence causes at least one of these problems:

- a script claim has no visual or audible evidence
- a person, object, place, process, or result is introduced without orientation
- an action cannot be understood because setup, key step, reaction, or outcome
  is missing
- continuity, geography, chronology, or screen direction becomes confusing
- dialogue/narration is covered by visibly unrelated filler
- a transition conceals a structural gap rather than serving the story
- a required product, safety, legal, tutorial, or factual detail is not shown
- the ending lacks the promised payoff or proof

Do not call every aesthetic opportunity "necessary." Separate the report into:

- `P0 Required`: the cut is misleading, unclear, unsupported, or incomplete
  without it
- `P1 Strongly Recommended`: comprehension or emotional payoff is materially
  weaker without it
- `P2 Optional Enhancement`: texture, polish, rhythm, or alternate coverage

For each recommendation include:

- related script paragraph/line and finished timeline timecode
- exact missing information or story function
- evidence that no adequate existing source covers it
- concrete subject, action, framing, camera movement, duration, orientation,
  location, time-of-day, sound, and continuity requirements
- whether original participants/location/props are required
- safe and practical capture notes
- an alternative using existing media, graphics, text, archival material,
  voiceover rewrite, or script deletion when reshooting is impossible
- expected editorial placement and what it replaces

Use `references/pickup-shot-report.md`. Preview the findings in chat and obtain
approval before writing:

```text
review/pickup-shot-report.md
review/pickup-shot-report.json
```

If nothing necessary is missing, say so explicitly and list only genuinely
useful optional enhancements. Never invent continuity details merely to make a
pickup request sound precise.

## Source Safety

- Treat original media as immutable.
- Write derivatives only under the approved run folder or staging directory.
- Stop and inspect running FFmpeg/Python processes after interruptions.
- Never delete original tracks after a partial audio bake.
- Never expose API keys, private endpoints, personal paths, or voice samples.

## References

- Configuration: `references/configuration.md`
- Best-practice edit profile: `references/editorial-best-practices.md`
- Blueprint schema: `references/blueprint-schema.md`
- Failure lessons and audits: `references/resolve-pitfalls.md`
- Pickup-shot report: `references/pickup-shot-report.md`
