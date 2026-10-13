# video-editor-mcp

A local ffmpeg editing workbench over MCP. Give Claude Code tools to inspect media, make explicit edits, render a JSON timeline, and measure the result: a real editing bench, not a black box. The server needs no API key. Its only media engines are ffmpeg and ffprobe.

> **Looking for the full editing room?** [video-atelier-mcp](https://github.com/PlbKin190/video-atelier-mcp)
> adds a Svelte editor UI, a timeline, captions, SAM2 screen replacement and multi-format export.
> It is source-available under PolyForm Noncommercial.
>
> This repository is the minimal, permissive half: nine ffmpeg tools, Apache 2.0, no UI, no HTTP
> port, no Python. Take it when you want something small enough to read end to end before you
> point it at your own media.

## Quickstart: two commands

From the repository root, with Docker and Compose v2 installed:

```sh
docker compose build
docker compose run --rm mcp
```

The second command starts an MCP stdio server, not an interactive shell. It waits for protocol messages; press Ctrl-C to stop it before connecting your client. No port is exposed. A named `media` volume is initialized automatically and persists after container removal.

The image uses `node:22-bookworm-slim` with Debian's `ffmpeg` package (including ffprobe) and DejaVu fonts. This provides a conventional glibc runtime, libx264 and drawtext support without a separate media download. Docker necessarily uses container-internal absolute mount/build locations; no host-specific path is embedded in the repository or accepted from an MCP client.

## Generate samples

No binary media is committed. Generate test patterns, a color gradient, tones, silence and a raster badge directly into the same Docker volume:

```sh
docker compose run --rm --no-deps -T --entrypoint sh mcp scripts/make-samples.sh
```

The sample script overwrites its own known sample names. Editing tools never overwrite output files. The supplied `voice-placeholder.wav` is a tone, not speech, and `music.wav` is a low tone, not a musical work. They exercise the two-track mix without third-party recordings. Substitute your own authorized voice and music for a listening demonstration.

For native development with ffmpeg installed, `sh scripts/make-samples.sh` writes to the local `workspace` directory instead. That directory is **not** the Docker named volume.

## Connect Claude Code

From this repository directory:

```sh
claude mcp add --transport stdio video-editor -- docker compose run --rm --no-deps -T mcp
```

Alternatively merge `examples/claude_code_mcp.json` into your project `.mcp.json`. Do not do both. Run Claude Code from the repository root so Compose selects the same project and volume. `-T` disables the pseudo-terminal; stdout is reserved for MCP, while diagnostics go to stderr. Approve only the editing requests you intend to execute.

## Nine tools

All paths below are workspace-relative names, for example `shot-one.mp4`, never `workspace/shot-one.mp4`. Output parents must already exist; outputs must end in `.mp4` and must not exist.

| Tool | Parameters | Behavior |
|---|---|---|
| `probe` | `input` | Duration; all track types/codecs; video dimensions/FPS; audio sample rate/channels |
| `trim` | `input`, `output`, `start`, `duration`, `mode=auto` | `auto` tries stream copy then encoding; `copy` refuses fallback; `accurate` encodes |
| `concat` | `inputs[]`, `output`, `frame={}` | Sequential whole clips; normalizes geometry/FPS/audio and re-encodes |
| `transform` | `input`, `output`, `frame` | Resize, rectangle crop, crop-to-fill or letterbox |
| `overlay` | `input`, `output`, `overlay`, `start=0`, `frame={}` | Text or raster image; optional source trim start; window relative to trimmed video |
| `audio_mix` | `input`, `output`, `music`, optional `voice`, `voiceVolume=1`, `normalize=true`, `targetLufs=-16` | Mix beneath existing audio or a replacement voice track; preserve video stream |
| `render` | `composition`, `output` | Render JSON ordered shots and optional global music to H.264/AAC MP4 |
| `qa` | `input`, `expectedDuration`, optional `expectedWidth`, `expectedHeight`, `expectedFps`; thresholds below | Actual duration, black/silence intervals, LUFS, geometry and FPS checks |
| `health` | none | ffmpeg/ffprobe versions, encoder names, workspace free bytes and limits |

Nested values:

- `frame`: `ratio` = `16:9` (1280×720), `9:16` (720×1280), or `1:1` (720×720); `fit=pad` or `crop`; `fps=30` (1–60). Paired `width`/`height` override the ratio; even values 16–1920. Optional `crop={width,height,x,y}` runs before sizing.
- Text overlay: `{kind:"text",text,fontSize:48,color:"white",x:40,y:40,start:0,end}`. Colors: white, black, yellow, red. Image overlay: `{kind:"image",source,width:160,x:40,y:40,start:0,end}`. At most eight overlays per shot; windows must fit the shot.
- Audio track: `{source,start:0,volume:1,fadeIn:0,fadeOut:0}`. Gains range from 0 to 2; fades are seconds. Short audio is padded with silence, not looped. A replacement voice's `volume` supersedes `voiceVolume`.
- Composition: `{frame,shots:[{source,start:0,duration,overlays:[],audio?,sourceVolume:1}],music?,normalize:true,targetLufs:-16}`. Overlays use shot-local time. `audio` replaces source audio; absent source audio becomes silence. Music spans the final timeline.
- QA defaults: `durationTolerance=0.15`, `targetLufs=-16`, `lufsTolerance=2`, `blackMinDuration=0.1`, `silenceMinDuration=0.5`, `silenceDb=-40`. Missing audio fails audio checks; unmeasurable loudness is `null`, never a fabricated value. Analysis errors fail the operation.

Times are seconds. Strict schemas reject unknown properties and raw ffmpeg arguments. See [architecture and composition diagrams](docs/architecture.md) and [the example JSON](examples/composition.json).

## Two-minute demonstration

After generating the samples and connecting Claude Code, ask:

1. “Check the video editor health and inspect `shot-one.mp4`.” → `health`, `probe`.
2. “Trim its first two seconds into `short.mp4`, using stream copy if possible.” → `trim`.
3. “Make `short.mp4` vertical 9:16, crop-to-fill, into `vertical.mp4`.” → `transform`.
4. “Add `Local editing` at x=40, y=100 from 0 to 2 seconds in `vertical.mp4`, keeping a 9:16 frame; output `titled.mp4`.” → `overlay`.
5. “Use `voice-placeholder.wav` as replacement voice and mix `music.wav` underneath it at volume 0.3, with 0.5-second fade-in and 1-second fade-out. Use `titled.mp4`, output `mixed.mp4`, normalize to -16 LUFS.” → `audio_mix`. The placeholders are tones; actual speech requires your own recording.
6. “Read `examples/composition.json` from this project and pass its JSON object to `render`, output `vertical-demo.mp4`.” → `render`. The client reads the project file; the server accepts the object, not a JSON path. This produces eight seconds of 9:16 video with titles, a timed badge, replacement audio and background audio.
7. “Check `vertical-demo.mp4` against 8 seconds, 720×1280, 30 FPS and -16 LUFS. Explain every failed check.” → `qa`.

Allow extra time on slow hardware. Use new output names when repeating. Inspect and listen to the result: QA is a measurement aid, not an aesthetic judgment.

An automated MCP demonstration (Node 22 on the host) uses the same sample volume:

```sh
npm install
npm run demo
```

It renders `demo.mp4` and prints QA results. To copy that result out without a host bind mount:

```sh
docker compose run --rm --no-deps -T --entrypoint cat mcp workspace/demo.mp4 > demo.mp4
```

## Configuration

`.env.example` lists every application setting. Copy it to `.env` to change Compose limits. For native runs Node does not automatically load it: use `node --env-file=.env dist/src/index.js` after building.

| Variable | Default | Meaning |
|---|---:|---|
| `WORKSPACE_DIR` | `workspace` | Relative workspace; Compose intentionally fixes this to its mounted directory |
| `MAX_RENDER_SECONDS` | 300 | Maximum whole-video edit/QA and composition duration |
| `MAX_FILE_BYTES` | 536870912 | Maximum individual input/output file size |
| `EXEC_TIMEOUT_MS` | 180000 | Whole-call deadline shared across copies and subprocesses |
| `MAX_COMPOSITION_SHOTS` | 32 | Maximum shot/concat count |
| `FFMPEG_THREADS` | 2 | Decoder, filter and video encoder thread budget |

## Security

- One workspace; no absolute client paths, traversal, hidden names, protocols or symbolic links. Names use ASCII letters, digits, underscore, dash, dot and directory separators. Parents must exist. Hard-linked inputs are rejected.
- Input snapshots in private job directories; no client names in filter graphs. Fixed, explicitly selected demuxers and file-only protocol access prevent playlist/protocol indirection. Inputs supported: MP4/MOV/M4A, MKV/WebM, WAV, MP3, FLAC, PNG and JPEG. Some container variants may be refused.
- Fixed ffmpeg/ffprobe binaries invoked with `execFile`, arrays, no shell, no raw flags. Text uses `textfile` and `expansion=none`, so quotes, colons, backslashes and percent expressions remain data.
- Duration, file-size, deadline, shot and thread limits. One request at a time; concurrent calls receive a busy error. Timeout uses SIGKILL. Output-size polling kills excessive writers; final size/probe checks reject truncation before publication.
- Atomic, no-overwrite output publication; temporary directories removed on normal completion/failure. Generic client errors; detailed diagnostics only on server stderr.
- Non-root container; no network; read-only root; dropped capabilities; no new privileges; memory, CPU and PID limits.

Do not allow untrusted local processes to mutate the mounted workspace concurrently. Component checks and `O_NOFOLLOW` do not make pathname operations race-free against a hostile same-user filesystem writer. A dedicated volume under operator control is part of the security model. Keep media parsers and the container patched. See [architecture](docs/architecture.md).

## Limits and operation

H.264/AAC MP4 outputs only; cuts only; no remote storage, content generation, transitions, background job service or database. `concat` and `render` encode intermediate shots then encode the concatenation: simple to inspect, but uses temporary disk and incurs generation loss. Budget workspace capacity for all inputs, snapshots, intermediates and final outputs; the per-file limit is not a volume quota. Host/container crash can leave `.job-*` directories; remove these only with the service stopped. Never mount credentials or unrelated documents into the media volume.

Stream-copy trim is keyframe-aligned and may be refused by duration verification. Use `accurate` for frame-level edits. Whole-video editing and QA reject sources longer than the duration limit; `probe` only inspects bounded file metadata. Inputs above 4096 pixels on either video axis are rejected for editing. No automatic text wrapping; unusual scripts may need additional fonts. Audio mix uses fixed gains, not dynamic ducking; normalization is single-pass and QA should confirm delivery loudness. Black/silence detectors can flag intentional content. Optional geometry/FPS expectations should be supplied for meaningful checks.

The image includes third-party media packages with their own licenses; the application license does not replace those obligations. Review distribution and codec-patent requirements for your use. Dependency versions are pinned directly, but transitive dependencies and base/OS packages are not yet locked: generate and commit a reviewed lockfile and pin image digests for release reproducibility.

## Development and verification

```sh
npm install
npm run build
npm test
```

`npm run dev` starts native stdio. Tests use Node's test runner through tsx. Guard tests need no ffmpeg. Execution tests run synthetic rendering and process timeout checks when ffmpeg is available (otherwise skipped). Confirm drawtext/libx264/AAC availability on native installations. Build and tests must be run on the release host; source review alone is not execution evidence.

## License

Copyright 2026 Christian Verbrugge. Application code: [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) and [CONTRIBUTING.md](CONTRIBUTING.md).
