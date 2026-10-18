---
name: video-cut-agent-editor
description: "Drive the local Agent-first advertising video editor CLI for project setup, timeline composition, edited clip-group reuse, local TTS, templates, validation, rights checks, conversion, and FFmpeg rendering."
---

# Video Cut Agent Editor

For automatic duration following after relative speed/curve/reverse/freeze,
read the [complete output retime contract](../../docs/specs/完整作者输出变速与磁吸联动契约_v0.1_2026-10-18.md).
Use `timeline edit` action `retime`, or compose `retime_clip`, with a transform
of the current complete visible output. Original author graphs remain editable
child sequences. Main clips ripple; linked intersections share the host clock.
Background music defaults to unchanged-speed ripple, with explicit
`sync_content: retime` for common retiming. Review all partial spans, absolute
markers, root bus points and the dry-run hash. Existing absolute source setters
retain their meaning. Animated blend and direct tracking/transition endpoints
reject. Native tempo timing does not prove natural quality; see the
[actual outputs and failed references](../../docs/validation/完整作者输出变速与磁吸联动实测_2026-10-19.md).

For persistent main-track magnet editing, read the
[mode and sync-split contract](../../docs/specs/主轨磁吸模式与跨剪口同步拆分契约_v0.1_2026-10-18.md).
Use `timeline edit` action `magnet` with an explicit boolean `enabled`.
In enabled sequences, main shift/append/remove/trim plans keep the main track
gapless; nearest-cut ties choose the earlier original boundary. Differently
displaced sync spans use complete-author presentation windows; shared side
links receive matching cut regions and fresh IDs. Ordinary reorder can opt
in with `sync_span_policy: split`. Review dry-run changes and expected hash
before applying. Partial magnetic fragment saving expands the full sequence.
Relative speed/curve/freeze duration following uses the planner above. All GUI
gestures and natural quality remain open; invalid geometry rejects atomically.
The [real outputs, failures and installed replay](../../docs/validation/主轨磁吸模式与跨剪口同步拆分实测_2026-10-18.md)
keeps independent source references separate from same-renderer author graphs.

For named audio buses, read the
[routing contract](../../docs/specs/命名音频总线发送返回与侧链契约_v0.1_2026-10-18.md).
Set `sequence.audio_routing` through compose `update_sequence`; review
outputs, pre/post sends, automation and named sidechains. Bus solo preserves
an unpruned detector context; mute silences pre-fader taps too. Routed children
finish their complete audio before ancestor time maps. Fragment saving expands
the full routed sequence. Render, then run `policy audit`; retain the
[actual PCM/media and installation evidence](../../docs/validation/命名音频总线发送返回与侧链实测_2026-10-18.md).
Stereo routing does not establish natural mixing or spatial audio quality.

For a whole-clip main-track permutation, read the
[magnetic reorder contract](../../docs/specs/主轨磁吸重排与关联附着契约_v0.1_2026-10-18.md).
Use `timeline edit` with `action: reorder`, selected main `clip_ids`, and an
explicit `before_clip_id` (null means the end). Original selection order is
retained and the whole main track packs from zero. Review every displaced
shot's links, sync/rider attachments and collision lanes before hash-bound
application. Broken transitions reject unless `drop_broken` is explicit;
different-delta sync spans reject unless `sync_span_policy: split` is selected.
Markers stay absolute.
The [frame/PCM and installation record](../../docs/validation/主轨磁吸重排与关联附着实测_2026-10-18.md)
distinguishes independent source truth from same-renderer author blocks.
Persistent mode uses this action through the planner above; GUI snapping remains open.

For transparent output or a root ending between display frames, read the
[delivery clock/alpha contract](../../docs/specs/透明视频交付与音画端点契约_v0.1_2026-10-18.md).
Use WebM/libvpx-vp9/yuva420p with CRF=0 and no bitrate override for lossless
YUV/alpha; RGB 4:2:0 remains lossy. Tagged VP8/VP9 input selects libvpx locally.
Use quality check/golden capture --sequence-id to bind authored duration and
retain raw deltas plus the quantified frame/sample tail. Unknown duration
gets no guessed exemption. See the
[actual exports, rejected offsets and native install](../../docs/validation/透明视频交付与音画端点实测_2026-10-18.md).

For a detached native installation, read the
[offline release contract](../../docs/specs/离线发行与随包Schema契约_v0.1_2026-10-18.md).
Use the reviewed manifest hash and a new target with the bundled installer;
the generated launcher uses the installed dependency site and local caches.
For font/text rendering use a `font-text-v1` bundle with seven pinned wheels,
including Pillow; the historical six-wheel `core-v1` bundle lacks that dependency.
`schema show/export` supplies the exact contract. Missing schema/executor or
invalid `project.created_at` is an error. See the
[actual install/edit/package checks](../../docs/validation/离线发行与随包Schema实测_2026-10-18.md)
before treating the same-machine result as portability evidence.
The [CTC install and quality record](../../docs/validation/离线CTC字词强制对齐实测_2026-10-18.md)
keeps the actual font failure and failed acoustic precision gate.

For all-frame HTML text checks, use `motion html-quality` under the
[layout/font contract](../../docs/specs/HTML文字布局与字体覆盖核验契约_v0.1_2026-10-18.md).
Pass `html-render --layout-check strict` when those checks must gate encoding;
saved strict recipes inherit and rerun the gate on rebuild. Inspect actual
source fonts, fallback, late-frame bounds and unsupported regions in
[the validation record](../../docs/validation/HTML文字布局与字体覆盖实测_2026-10-18.md).
Nonzero glyph mapping does not accept shaping or visual quality.

For CSS/text/image changes to an existing HTML asset, use
`motion html-controls` and `html-render --overrides` under the
[template controls contract](../../docs/specs/离线HTML模板控件与覆盖恢复契约_v0.1_2026-10-18.md).
Inspect a real frame first, keep numeric CSS units and registered image IDs,
then render a new version. A `null` patch restores the page's own frame values;
other saved changes inherit. Preserve source/override image rights and
[the package/fragment rebuild boundary](../../docs/validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md).

For local correction of an encoded mask, use `media mask-edit` with the
[bound geometry plan](../../docs/specs/本地蒙版笔刷与关键帧修正契约_v0.1_2026-10-18.md).
Preview with `--dry-run`, create a new mask asset, check it with `quality mask`,
then explicitly supply it to repair or mask tracking. `--edits-from-asset`
rebuilds the saved authored plan after packaging. This does not run automatic
tracking or establish natural object-removal quality.

For linked source slip and genuine local source extension, read the
[source edit contract](../../docs/specs/真实源范围外扩与关联Slip契约_v0.1_2026-10-18.md).
Use `timeline edit` actions `slip` / `extend_source`; inspect `source_changes`
and the full before/after diff. Source slip keeps timeline/automation data;
extension reauthors native processing. Preserve nested curve normalization
warnings and input bounds. Roll/slide accept explicit `handle_policy: source`.

For insert/overwrite/lift/extract/roll/slide, read the
[range edit contract](../../docs/specs/范围编辑插入覆盖与滚滑剪口契约_v0.1_2026-10-18.md).
Use `timeline edit --input <request.json> --dry-run`; incoming clips have
group-relative positions and must reference registered local assets. Inspect
the complete created/removed/modified clip diff, linked/sync/rider closure,
cut pairs and sequence duration before binding the project hash. Roll and
slide default to retained full-author handles; the source policy above uses
finite real inputs. Preserve explicit shortfall, lock, binding, transition
and audio-bus errors. Compose can batch these requests as `linked_edit`.

For source-preserving split, trim and interval ripple operations, use the
[presentation window contract](../../docs/specs/片段输出窗口裁切与波纹编辑契约_v0.1_2026-10-18.md).
The visible clip range is separate from its full author source/animation clock.
Native rendering computes the full clip before selecting its output; external
formats report this authoring feature unsupported. Keep the explicit operation
gates for tracking, smart-cut/reframe, transitions and partial-take speed/reverse.

Use this skill when the requested edit should be represented as a reproducible local Agent Project rather than a GUI project. The implementation lives in `product/` in this project.

For editable HTML/SVG/Canvas titles, read the [offline HTML motion contract](../../docs/specs/离线HTML动效与可编辑源码契约_v0.1_2026-10-18.md).
Use `motion html-register` with explicit existing native toolchain paths, then
`html-source`, `html-inspect`, and `html-render --dry-run`. Bind formal rendering
with its project hash; optional `--apply --track-id` inserts a normal alpha video.
`--from-asset-id` rebuilds preserved source and typed parameters to a new asset
version. Keep original image/font rights, frame-order and Job cleanup reports.
No downloads, live-site capture, embedded video/iframes or WebGL are enabled.

For cross-project reuse of edited clips, read the
[fragment library contract](../../docs/specs/可复用片段组库与跨项目插入契约_v0.1_2026-10-18.md).
Use `fragment save/apply --project <root> --library <local-dir> --input
<request.json> --dry-run`. Inspect expanded link/transition/binding selection,
resource bytes, rights and ID maps; bind formal execution with both expected
project/fragment hashes. The result remains an editable nested group with
original author clocks. Keep context/track/collision errors and publication
gates. `fragment inspect` verifies files; `list --query` only searches metadata.

For reversible cut transitions, read the [real source-handle contract](../../docs/specs/真实源句柄转场与可逆编辑契约_v0.1_2026-10-17.md).
Use `timeline transition --input <request.json> --dry-run` with add/resize/remove.
The plan's `project_sha256` can bind formal application. Inspect actual source
head/tail ticks and frozen linked audio pairs. Clips, cut and sequence length
stay authored; short handles reject rather than clone a frame. The first
version requires direct local video endpoints, exact frame/tick grids and
constant leaf speed; endpoint containers/curves/freeze/tracking/blend reject.
For using a transitioned child in a parent, read the
[nested transition contract](../../docs/specs/嵌套转场合成与作者时钟契约_v0.1_2026-10-18.md).
Parent trim/reverse/constant speed/curves operate on the completed native
child surface in the same FFmpeg graph. Keep original-source audio, scoped
`inline_sequence_path` warnings and the combined projection/surface quota.
Ancestor freeze follows complete-child picture/audio holds in V51; parent
animation continues. Preserve the remaining endpoint and inline-R3 errors.

For real supplied-text word/character timing, read the
[offline CTC contract](../../docs/specs/离线CTC字词强制对齐契约_v0.1_2026-10-18.md).
Use registered `transformers-wav2vec2-ctc-local-v1` with `subtitle align`,
an explicit local transcript and new JSON output. Character/whitespace units,
case mapping, SRT source windows, local font/track application and model rights
remain explicit. OOV fails without script conversion. Keep review warnings;
forced alignment is separate from Whisper transcription and subtitle splitting.

For readable subtitle segments or local piece corrections, read the
[subtitle segmentation contract](../../docs/specs/本地字幕分段与局部回写契约_v0.1_2026-10-17.md).
Use `subtitle segment --project <root> --input <caption-or-ASR-report-or-source.json>
--output assets/subtitles/<new>.json --dry-run`; native local Node >=22.2 is
required. Add `--apply --track-id <subtitle-track>` and optionally
`--mode bilingual` for explicitly supplied translations. Inspect source ranges,
estimated timing, shared translation groups and reading-limit warnings.
Corrections bind the raw input SHA-256 and the original line/part; public
indexes are Unicode codepoints. New text starts with unverified rights.
This neither recognizes speech nor translates it; preserve source/model
dependencies through `--source-asset-id` or the registered ASR subtitle asset.

For whole-clip linked editing, read the [linked editing contract](../../docs/specs/关联片段与主轨联动规划契约_v0.1_2026-10-17.md).
Use `timeline edit --project <path> --input <request.json> --dry-run` for
link/unlink/remove/close_gap/close_gaps/shift. Inspect selected IDs, locked
members, common `short_tick`, collision lanes and subtitle cue offsets. Apply
by omitting dry-run; pass `--expected-project-sha256` from the plan when needed.
Sync takes precedence over main-track linkage; `track.sync_lock=false` opts
other tracks out. Whole-clip movement preserves source clocks and animation;
Use the range actions above for insert/overwrite and retained-author cuts.
Source extension uses the explicit actions above; full main-track magnetism
and arbitrary nested-curve old-body preservation remain separate work.
Preserve explicit audio-bus relocation and binding-reference errors.

For Chinese voiceovers, read the [local SoulX contract](../../docs/specs/本地SoulX中文配音与声线登记契约_v0.1_2026-10-15.md).
Register explicit existing Python/source/package/model/tokenizer paths with
`tts adapter register`; ingest the authorized single-speaker reference and use
`tts voice register` with its exact transcript and local evidence. Inspect both
registrations, then run `tts synthesize --adapter-id <id> --voice-id <id> --text
<Chinese-text> --asset-id <new-id> --output assets/tts/<new-name>.wav --dry-run`.
Run formally after reviewing the plan. Optional `--apply --track-id <audio-track>`
uses the actual WAV duration. Generated WAVs are registered assets with rights
dependencies and remain unverified until reviewed. Preserve `TTS_REVIEW_REQUIRED`;
this is a CUDA/HF/BF16 single-voice path, with no downloads, CPU/GGUF fallback or
online service. No adapter keeps the English/ASCII flite behavior described below.

## Runtime boundary

For independent nested raster dimensions, read the
[sequence canvas contract](../../docs/specs/独立序列画布与父级投影契约_v0.1_2026-10-17.md).
Sequence canvas is optional width/height; null inherits effective project
dimensions. Compose with `add_sequence.canvas` or `update_sequence.patch`.
Parent crop/fit/anchor projects the complete native child; text/bindings remain
in child coordinates. Render/quality/queue selection uses that sequence's
default canvas, while explicit output dimensions affect only the selected root.
Keep internal odd rasters distinct from final encoder alignment requirements.
This does not add independent child FPS, color space or HDR acceptance.

For reduced sequence layers, read the [area sampling contract](../../docs/specs/序列面积采样与工作栅格预算契约_v0.1_2026-10-17.md).
Use `render --sequence-sampling area` explicitly; omitted settings retain
bilinear behavior. `--sequence-memory-mib` controls the projection admission
quota (default 1024 MiB), not whole-process RSS. A quota error occurs before
render allocation; inspect its node breakdown before changing sizes or budget.
Area uses a source-axis box, not exact rotated-pixel geometry or HDR filtering.

For text-controlled masked video windows, read the [local VACE contract](../../docs/specs/本地VACE联合视频编辑契约_v0.1_2026-10-16.md).
Register existing fixed Wan VACE Diffusers weights/Python/evidence with
`media adapter register --engine diffusers-wan-vace-local-v1 --device cuda`.
Use `media inpaint` with source/mask asset IDs and a descriptive `--prompt`;
review `--window-frames`, `--window-overlap`, seed, steps, token budget and
explicit scene cuts in dry-run before execution. No prompt is expanded or
silently truncated. Text GPU/CPU weight budgets are explicit; video generation
releases the encoder first. Native read locks protect reused digests within
each command. Review generated texture, object identity and overlap boundaries;
joint windows do not prove broad video quality or full Jianying parity.
Use explicit `--flow-shift` (0.1..32; default 3) and `--model-input-scale`
(1/2/4; default 1) when the edit needs sampling calibration. Dry-run reports
the scaled array budget; execution reports actual model input shapes and
scheduler configuration. Input scaling follows the base `--model-max-edge`
ROI and preserves output dimensions. It can increase resource use and worsen
quality, so keep the requested settings visible in the delivery evidence.
Source, mask and model rights continue to gate publication.

For removing a selected object, use the [local LaMa contract](../../docs/specs/本地LaMa区域修复与对象移除契约_v0.1_2026-10-16.md).
Register existing TorchScript/Python/evidence with explicit CPU/CUDA and inspect.
Ingest an alpha or black/white mask, or derive a binary alpha mask using SAM2.
Run `media inpaint --asset-id <video> --mask-asset-id <mask> --adapter-id <id>
--derived-asset-id <new-id> --dry-run`; review mask clock, geometry, growth,
feather and ROI limits. Opaque masks need `--mask-channel luma`. Formal execution
can use `--apply --track-id <video-track> --audio-track-id <audio-track>`.
Source, mask and model rights gate the result. Review texture and temporal
flicker; this is framewise repair and does not prove full video/generative parity.

For an explicit boundary color correction after either repair engine, use
`--repair-blend harmonic`; default `direct` retains the existing composition.
Read the [harmonic contract](../../docs/specs/本地修复区域色差融合契约_v0.1_2026-10-16.md)
for solver options, selection-dependent admission and failure behavior.
Review its convergence report and natural texture/motion separately; the
mode can reduce a color patch while leaving object traces or flicker.

For selected objects or a person with a held product, use the
[local SAM2 contract](../../docs/specs/本地SAM2对象分割与提示修正契约_v0.1_2026-10-16.md).
Register existing video safetensors/Python/evidence with explicit CPU or CUDA,
then pass a local `--prompts` JSON to `media matting`. Review output-frame
coordinates, positive/negative points, boxes, selected IDs and explicit resets.
A face click can select only a face; inspect before accepting a whole-person
cutout. Binary/probability segmentation does not establish hair or matte quality.

To drive labels or portrait reframing from its registered video mask, use
`media track-bind` or `media reframe --mask-asset-id <mask>` with the source
asset, without ROI/adapter/object-ID options. Read the [mask tracking contract](../../docs/specs/本地分割蒙版轨迹与锚定契约_v0.1_2026-10-16.md).
Review the mask clock and optional `--mask-expectations` in dry-run; explicit
source-clip references enable render-time canvas recompilation. This measures
the supplied bbox and retains source/mask/model rights. Segmentation mistakes
and failed final label-pixel checks remain quality failures.

For transparent human cutouts use the [local RVM contract](../../docs/specs/本地RVM人物视频抠像与透明素材契约_v0.1_2026-10-16.md).
Register existing FP32 ONNX, native Python and evidence with `media adapter
register --engine rvm-onnx-cpu-matting-v1`; inspect, then run `media matting
--asset-id <ingested-video> --adapter-id <id> --derived-asset-id <new-id>
--max-edge 1280 --dry-run`. Formal execution registers a QTRLE/ARGB MOV with
source/model rights and exact RGBA encode/decode hash evidence. Add `--apply
--track-id <video-track>` and optionally `--audio-track-id <audio-track>` for
explicit synchronized audio. Existing clip overlap needs `--replace-track`.
Put the foreground on a higher-order video layer than its background.
This is CPU-only, recurrent human matting with no downloads/provider fallback.
Keep model-review and CFR-clock warnings; first-frame edges, hair, movement,
occlusion and held objects need visual review, and HDR requires prior tone map.

For actual vocal separation, use the [native HDemucs contract](../../docs/specs/本地HDemucs人声伴奏分离契约_v0.1_2026-10-16.md).
Register existing compatible weights, native Python and evidence with
`audio adapter register --engine torchaudio-hdemucs-local-v1 --device cpu|cuda`.
Inspect, then run `audio separate --asset-id <source> --adapter-id <id>
--vocals-asset-id <new-id> --accompaniment-asset-id <new-id> --dry-run`.
Add `--apply --track-id <audio-track> --stem vocals|accompaniment` when needed.
The outputs are float WAVs with source/model rights dependencies, exact sample
coverage and residual accompaniment. Review leakage, seam artifacts, peaks and
licensing before delivery; this engine does not download or silently fall back.

For model-backed object tracking use the [native YOLO contract](../../docs/specs/本地YOLO检测与多目标跟踪契约_v0.1_2026-10-15.md).
`media adapter register --engine yolov10-onnx-cpu-tracking-v1` takes an
existing `.onnx`, `--executable <native-Python.exe>` and local evidence.
Inspect registration and review `media track --all-objects` before selecting
an object for `media track-bind` or `media reframe`. Use ingested assets for
application. Motion-only IDs, source-clock resampling and missing observations
require review. Add `--source-track-id` and `--source-clip-id` for a persistent
[canvas binding](../../docs/specs/本地跟踪绑定坐标空间与渲染重算契约_v0.1_2026-10-15.md): current source crop, transform, mirror and source clock are compiled again
for the output canvas. Optional `--rotation-mode source` follows layer rotation.
Keep source hash, observations and model rights. Nested parents, mask/occlusion,
VFR, nonlinear warps and broad visual quality still require further work.
Dense crop graphs are passed through hash-checked local files when Windows
command length requires it. Never lower trajectory sampling to hide a render error.

For local speech recognition use the [registered Whisper contract](../../docs/specs/本地Whisper模型登记与转写验收契约_v0.1_2026-10-15.md).
`asr adapter register/list/inspect` records existing native Python, complete
safetensors weights, explicit CPU/CUDA and local evidence. Pass `--adapter-id`
to `media understand --transcribe` or `subtitle transcribe`; the latter can apply
source/model-dependent subtitle assets to an existing subtitle track. Use new
project-relative SRT paths and inspect dry-run before applying. `subtitle evaluate`
compares to a supplied reference and emits CER, including Chinese script differences.
Local `.ttf/.otf/.ttc` fonts can be ingested and selected with `--font-asset-id`;
their readability does not establish publication rights.

- Use native Windows Python and the installed `ffmpeg.exe`/`ffprobe.exe` only.
- Set `PYTHONPATH` to the absolute `product/src` directory and invoke `python -m ai_ad_editor`; the repository wrapper also pins TEMP/TMP and Python/model caches to `product/.runtime/` on E drive.
- Keep the default network policy disabled. Do not call GUI automation, HTTP services, or any other closed/online provider.
- Do not start Docker, WSL, containers, or virtual machines. The `doctor` command only reports whether those executables are on PATH.
- Every publishable asset needs a Rights Ledger record with an allowed target use and evidence. Never use a template or `--yes` to bypass this gate.

## Workflow

1. Run `doctor` and fail clearly if FFmpeg/FFprobe is unavailable. Then read `capabilities` and choose only features whose status and limits fit the requested plan; `degraded` and `local_adapter_only` entries must remain visible in the response.
2. Create or inspect a project with `project init`/`project inspect`. For a known legacy Agent Project (`0.0.0`), run `project migrate` first; it hashes/probes only local assets, creates a `before-migrate` snapshot, validates the candidate, and writes a migration report. Unknown or higher schema versions must go through an explicit converter.
3. Ingest local files with `media ingest`; retain the returned asset ID and never invent a media hash. Use `media track --asset-id <id> --roi x,y,w,h` for explainable local template tracking; inspect confidence and drift warnings, and pass `--clip-id` only when the Agent wants a `before-track-apply` snapshot plus position keyframes written back. For an aspect-ratio change, run `media reframe --asset-id <id> --roi x,y,w,h --clip-id <clip> --track-id <track> --dry-run`, inspect target crop, clipping count, and confidence warnings, then use `--apply` to create a `before-reframe` snapshot and write `crop.x/y/width/height` keyframes. Reframe currently accepts direct constant-speed forward clips only and uses a deterministic local template track; nested sequences, reverse, and `speed_curve` require baking or an explicit local adapter. For spoken footage, use `media smart-cut --project <path> --track-id <video-track> --clip-id <video-clip> --dry-run` to inspect a local FFmpeg `silencedetect` plan; add one `--linked-track-id` and matching `--linked-clip-id` per audio clip to keep explicit A/V IDs aligned. When the Agent has a project-local SRT, VTT, ASS, SSA, or TTML, add `--transcript <path> --remove-phrase <phrase>` (repeat the option for more phrases) to remove whole matching caption cues; review `plan.semantic`, `SMART_CUT_SEMANTIC_CUE_GRANULARITY`, and `SMART_CUT_PHRASE_NOT_FOUND` before using `--apply`. The operation creates a `before-smart-cut` snapshot, preserves keyframe boundaries, writes deterministic `.smartN` pieces and validates the project. It accepts direct constant-speed media clips only and rejects nested sequences, `speed_curve`, and freeze clips; silence is amplitude evidence and transcript matching is explicit lexical cue matching, so neither path claims word-level timing, filler-word semantics, or language understanding. For multi-camera footage, run `media multicam --project <path> --source-asset-id <wide> --source-asset-id <close> --reference-asset-id <wide> --switch-seconds 4 --track-id <video-track> --dry-run` first; inspect each `offsets[].relative_delay_seconds`, `score`, overlap evidence, and warnings, then use a project-local `--switch-plan` JSON or fixed `--switch-seconds` with `--apply` only after review. This is local FFmpeg PCM envelope cross-correlation for timing assistance and does not claim visual auto-directing, speaker identification, or semantic shot selection; read the [multicam contract](../../docs/specs/本地多机位同步与切换契约_v0.1_2026-10-15.md). For audio extraction, run `audio extract --project <path> --asset-id <video> --derived-asset-id <audio> --track-id <audio-track> --apply` only after a `--dry-run`; the command writes the first local audio stream to a lossless PCM WAV derived asset, creates `before-audio-extract`, inherits Rights Ledger evidence, and can append an audio clip. It does not claim vocal/background separation; inspect the [audio extraction contract](../../docs/specs/本地音频提取与派生资产契约_v0.1_2026-10-15.md). For a transparent stem approximation, run `audio separate --project <path> --asset-id <video> --center-asset-id <center> --side-asset-id <side> --track-id <audio-track> --stem center --apply` only after a `--dry-run`; this uses local FFmpeg `aformat`/`pan` to write center mono and side stereo WAV assets, creates `before-audio-separate`, inherits Rights Ledger evidence, and appends only the selected stem. Preserve the `AUDIO_SEPARATION_APPROXIMATE` warning: mid/side is phase-based and does not equal Demucs/UVR or other model separation. Read the [mid/side separation contract](../../docs/specs/本地音频mid-side与源分离适配器边界契约_v0.1_2026-10-15.md). For camera shake, run `media stabilize --project <path> --asset-id <id> --dry-run` first, then apply only after checking the local `libvidstab` dependency and parameters; the command runs `vidstabdetect` followed by `vidstabtransform`, creates a `before-stabilize` snapshot, registers a project derived asset with inherited parent rights, and writes a hash/probe report. It does not rewrite the timeline or claim subject-aware stabilization; review crop, black edges, scene cuts, rolling-shutter artifacts, and CPU cost before publishing. Read the [stabilization contract](../../docs/specs/本地视频防抖与稳定化派生素材契约_v0.1_2026-10-15.md) for parameter bounds and failure codes.
For an offline audio adapter, register existing local artifacts with `audio adapter register --dry-run`, then inspect the formal registration before separation. Registration never downloads or infers. `ffmpeg-local-mid-side-v1`, restricted `command-json-v1` and native `torchaudio-hdemucs-local-v1` are executable. Command-json requires exact center/side WAVs and rejects shell wrappers; native HDemucs emits vocals/accompaniment. Legacy `demucs-local-v1`, UVR, Open-Unmix and ONNX-specific engines without runners still return `AUDIO_SEPARATION_ADAPTER_UNAVAILABLE`. Preserve review warnings and model/source rights dependencies. Read the [audio registry contract](../../docs/specs/本地模型适配器注册与音频分离门禁契约_v0.1_2026-10-15.md).
 3b. For a registered local visual tracker, run `media adapter register --project <path> --adapter-id <id> --engine command-json-tracking-v1 --model-path <existing-local-path> --executable <existing-local-py-or-native-runner> --license-spdx <license> --evidence <local-evidence> --dry-run` first. Register formally only after checking the model and executable hashes, then use `media adapter list/inspect` to confirm `verification.ok`. Pass `--adapter-id <id>` to `media track`, `media track-bind`, or `media reframe`; the CLI sends one `agent-video-object-tracking-v1` JSON request, validates protocol/status, frame count, range, monotonic ticks, normalized bbox and confidence, and emits `TRACKING_EXTERNAL_REVIEW`. Shell wrappers, network access, unknown engines and hash changes are rejected. Read the [visual tracking adapter contract](../../docs/specs/本地视觉模型适配器与对象跟踪协议契约_v0.1_2026-10-15.md) and retain a local golden review; this protocol does not claim occlusion recovery, multi-object identity, pose or segmentation quality.
4. Use `media understand` for local scene/silence/beat candidates. Add `--transcribe --model-path <existing-local-transformers-model>` only when an offline model has been registered; the command never downloads a model. Add `--srt <project-relative-path>` only when timed segments are returned. Use `media prepare` to make local proxies, thumbnails, and waveforms, and `media highlights` to write a hash-linked deterministic candidate report. For `media highlights`, run `--asset-id <id> --beats --top-k <n>` without `--apply` first, review the hash-linked report, then add `--apply --track-id <video-track>` only for a registered local video asset. Use `--replace-track` explicitly before clearing existing clips; preserve `HIGHLIGHTS_HEURISTIC` and `HIGHLIGHTS_REVIEW_REQUIRED`, and inspect semantic continuity, A/V sync, and transitions before publishing. Read the [highlights rough-cut contract](../../docs/specs/本地高光候选与自动粗剪时间线契约_v0.1_2026-10-15.md). Use `ad plan --input <brief.json>` to turn a local advertising brief into timed Hook/Problem/Benefit/Proof/Offer/CTA phases and marker operations before selecting assets. Use `subtitle validate`/`subtitle normalize` for SRT, VTT, ASS, SSA, and local TTML/DFXP before publishing captions; TTML external entities and unsupported timing expressions are rejected. Use `tts synthesize --project <path> --text <ASCII/English text> --output <project WAV>` for the local FFmpeg flite voice baseline; inspect `doctor.data.checks.local_features.flite_tts` first and surface the `TTS_LOCALE_UNSUPPORTED` response for non-ASCII text instead of retrying through a network provider. Before writing an effect into a plan, call `effects list` or `effects inspect --name <id-or-alias>`; use the returned backend, parameter limits, and `keyframable` flag. The current catalog has 45 local FFmpeg effects, including HSL, RGB curves, three-way color wheel mappings, and `frame_interpolation` backed by local `minterpolate`; native filters that remain static-only must keep any keyframe approximation warning visible, and motion-compensation CPU cost or scene-change artifacts must be quality-checked. For reusable color looks, run `lut register/list/inspect` to copy a local `.cube/.3dl/.csp/.dat` into the project, record SHA-256 and Rights Ledger evidence, then reference it as `{"type":"lut3d","parameters":{"lut_id":"lut_warm"}}`; a changed registered file is rejected by validation. Add `"intensity": 0.5` for a static partial-strength `.cube` look; the renderer writes a source-hash keyed identity-mixed LUT under the project `cache/luts/` directory, while `intensity=0` skips the LUT exactly. `.3dl/.csp/.dat` partial strength and intensity keyframes remain explicit degraded cases. Before selecting a camera move, call `motion list` or `motion inspect --name <id-or-alias>`; the v0.1.0 local catalog contains 12 deterministic presets and bounded `amount`/`degrees`/`points` parameters. Use `motion apply --project <path> --clip-id <id> --preset <name>` to write ordinary transform keyframes to an existing clip; the command creates a `before-motion-apply` snapshot, records an operation, supports `--start-tick/--end-tick`, and supports `--dry-run`. `push_in`, `slide_*`, `rotate_left/right`, and `opacity_*` are compatibility aliases; use the returned canonical ID and preserve any catalog limits in the Agent response. Use `timeline compose` for explicit clip/track/marker changes and reusable motion presets, including split/ripple/slip/slide/speed/reverse/freeze operations; clip transforms accept normalized `transform.anchor.x/y` (or `anchor_x/anchor_y`, default `0.5`) and matching keyframes so an Agent can place a chosen layer corner or edge on a motion path; video-layer rotation compensates the expanded FFmpeg bounds to keep the anchor; independent text canvases still rotate around their canvas center, and nested parent pivots remain an explicit approximation warning; speed curves, nested sequences, static path/polygon masks, basic-shape mask.* keyframes, and normalized alpha feather are available with their reported approximation limits; clip changes may include validated rectangle/circle/ellipse `mask` objects and local FFmpeg `blend` modes. Adjacent clips may use `auto_handle: true` on a complex transition to invoke local xfade without manual overlap handles; the renderer preserves the authored duration with a visible tail-padding approximation warning. Use `template apply` or `template batch` only with a versioned local template and variable snapshot. Use `library index --root <local-dir> --output <catalog.json>` to build the v0.3.0 deterministic catalog, optionally pass `--previous <catalog.json> --incremental` to reuse stat-unchanged records and `--visual-hash` to add local FFmpeg `ahash-v1` samples; then use `library search --catalog <catalog.json>` for filename/relative-path/CJK-token/same-stem subtitle discovery and duration/dimensions/audio-stream filters, `library duplicates --catalog <catalog.json>` for exact SHA-256 duplicate groups, and `library similar --catalog <catalog.json>` for review-only visual candidates. The catalog declares `semantic.source=deterministic-local` and `vector_index=false`: do not describe this as VLM, OCR, embedding, person or object understanding, and never use visual candidates as a rights or publish decision. Feed selected records through Rights Ledger before publishing. Run `policy audit --project <path>` before a publish plan. For project-bound writes, pass a stable `--idempotency-key` when the caller may retry.

4.1. For a registered multi-object visual runner, use `media track --adapter-id <id> --object-id <object-id>` when one trajectory will be applied, or `--all-objects` for a report-only identity review. Never combine `--all-objects` with `--clip-id`. `media track-bind` and `media reframe` require `--object-id` for the v2 engine so multiple trajectories cannot be written into one text layer or crop window. Preserve `TRACK_OBJECT_SELECTION_REQUIRED`, `TRACK_OBJECT_NOT_FOUND`, `TRACK_OBJECT_SELECTION_UNSUPPORTED`, and `TRACKING_MULTI_OBJECT_REVIEW`; review identity continuity through occlusion/crossing, then apply only after the usual before snapshot and project validation. Read the [multi-object tracking contract](../../docs/specs/本地多目标视觉跟踪与对象选择协议契约_v0.1_2026-10-15.md).
4a. For a music montage, use `media beat-cut --project <path> (--audio-asset-id <id>|--input <local-file>) --source-asset-id <video-id> --track-id <video-track> --dry-run`, review the local energy-anchor plan, then add `--apply`. Existing target overlaps are rejected unless `--replace-track` is explicit. Read the [beat-cut contract](../../docs/specs/本地节拍卡点与混剪时间线契约_v0.1_2026-10-15.md) and preserve `BEAT_NO_ANCHORS`, `BEAT_SOURCE_REUSED`, and `BEAT_SOURCE_SLOWED` warnings.
4b. For automatic captions, use `subtitle transcribe --project <path> (--asset-id <registered-audio-or-video>|--input <local-file>) --model-path <local-model> --dry-run` first. Choose `--transcribe-engine transformers` for a local model directory or `--transcribe-engine ffmpeg-whisper` for a local whisper.cpp model file; inspect `doctor.data.checks.local_features.ffmpeg_whisper_asr` before the native path. Add `--apply --track-id <subtitle-track>` only after review; application requires a registered source asset so the generated subtitle asset inherits Rights Ledger evidence, creates `before-subtitle-transcribe`, validates the project, and records the operation. Preserve `LOCAL_ASR_WHISPER_UNAVAILABLE`, `LOCAL_ASR_WHISPER_FAILED`, `SUBTITLE_APPLY_SOURCE_ASSET_REQUIRED`, and `SUBTITLE_TRANSCRIBE_TRACK_OVERLAP` errors. Read the [local AI and subtitle contract](../../docs/specs/本地AI适配器与字幕流水线规范_v0.1_2026-10-13.md).
4c. To make a text, sticker, or effect layer follow a locally tracked subject, use `media track-bind --project <path> (--asset-id <id>|--input <local-file>) --roi x,y,w,h [--adapter-id <id>] --target-clip-id <clip> --target-track-id <track> --dry-run` first. Review the source/model hashes, confidence frames, target duration mapping, offsets, and `scale-mode`; add `--apply` only after review. `--apply` creates `before-track-bind`, writes `transform.position.x/y` and optional ROI-relative `transform.scale` keyframes, validates the project, and records a report, provenance entry, and operation. Preserve `TRACK_BIND_TARGET_AUDIO`, `TRACK_BIND_NESTED_UNSUPPORTED`, `TRACK_BIND_EMPTY`, and `TRACK_BIND_APPLY_INVALID`; the source-clock normalization and template/external-runner quality warnings are mandatory review evidence. Read the [tracking bind contract](../../docs/specs/本地跟踪绑定与对象锚定契约_v0.1_2026-10-15.md).
5. Run `validate`; the project validator includes the local Agent Project JSON Schema executor when `jsonschema` is installed and reports its engine. For a release or ad publish also run `rights check`, render with `--publish`, and finish with `quality check --require-audio` (add `--expensive` for black-frame/loudness scans). Use `quality scopes --project <path> --input <project-media> --at-seconds <seconds>` when an Agent or reviewer needs local waveform/vectorscope/histogram PNG evidence; read the [scope contract](../../docs/specs/本地色彩Scope审查契约_v0.1_2026-10-14.md) and treat these images as review artifacts rather than automatic color grading. Render may declare `--container mp4|webm|mkv`, local video/audio codecs, CRF or bitrates; preserve the resulting encoder settings in the manifest. For multiple output variants, write a project-local queue JSON and use `queue enqueue`, `queue list/inspect`, then `queue run`; the queue defaults to a sequential local FFmpeg runner, while `queue run --workers N --continue-on-error` enables bounded local concurrency for distinct output paths. Failed/cancelled jobs require explicit `--job-id` retry, duplicate concurrent outputs are rejected, and `queue cancel` uses a project-local marker. Read the [queue contract](../../docs/specs/本地渲染队列与任务状态契约_v0.1_2026-10-14.md) before relying on state transitions.
6. Use `convert import/export` only through its conversion report. Export can target `agent-json`, `package`, `otio`, `kdenlive-xml`, or `jianying-draft-json`. Use `package` for portable projects with copied local assets and a hash manifest. For a readable local draft, import automatically detects `materials/tracks/canvas_config`; export with `--target-format jianying-draft-json` writes a plaintext file, a conversion report, and a redacted source-project sidecar. Add `--strict` only for this draft adapter when every `Approximate/Baked/Unsupported/Failed` must reject the conversion before publishing the target; do not retry a strict rejection without surfacing the loss report. Text layout and Bezier remain approximate, private resources are never downloaded, encrypted drafts are rejected, and imported media/fonts have unverified rights. Video sound becomes an explicit linked audio track; unmodified sound folds back on export, while independent volume/mute edits stay separate to avoid extra mixing. Treat `Failed` and `summary.status=partial` as failure even when a partial project exists. No conversion result proves compatibility with a commercial Jianying version or visual parity. Read the [plaintext draft contract](../../docs/specs/本地明文草稿双向适配器契约_v0.1_2026-10-15.md).
7. Inspect the render manifest and probe the output before reporting success. If the renderer warns that keyframes, effects, transitions, or transforms are preserved but not executed, report that limitation. If a render is cancelled or fails, retain the returned `operation_id`; retry with `render --resume <operation_id>` only after the CLI accepts the unchanged project and asset fingerprints. This is a validated rebuild from the recorded plan, not a partial-frame checkpoint.

Agent calls should consume the JSON envelope and exit code. Keep a project-relative change set in a file so the operation is reviewable and repeatable. Read [the CLI contract](../../docs/specs/AgentCLI契约_v0.1_2026-10-13.md), [the local AI adapter specification](../../docs/specs/本地AI适配器与字幕流水线规范_v0.1_2026-10-13.md), [the object tracking specification](../../docs/specs/本地对象跟踪与关键帧规范_v0.1_2026-10-13.md), [the visual tracking adapter contract](../../docs/specs/本地视觉模型适配器与对象跟踪协议契约_v0.1_2026-10-15.md), [the tracking bind contract](../../docs/specs/本地跟踪绑定与对象锚定契约_v0.1_2026-10-15.md), and [the P0 usage guide](../../docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md) when a request needs exact fields or failure handling.
