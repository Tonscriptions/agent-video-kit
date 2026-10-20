---
name: video-cut-timeline
description: Compose an Agent Project timeline with local clips, tracks, transitions, keyframes, masks, speed curves, nested sequences, captions, and audio automation.
---

<!-- V81-CURVE-CLOCK -->
For fractional frame rates, cut-ins or moving presentation windows, read the
[video clock contract](../../docs/specs/片段有理数时间基与CFR边界契约_v0.1_2026-10-21.md) and
[combined evidence and retained failures](../../docs/validation/有理数视频时钟与曲线候选合并实测_2026-10-21.md).
Keep requested source-in ticks and original VFR PTS; do not replace the source
clock with its first decoded frame or average FPS. Use public trim/split to
create presentation windows, and explicitly set master duration when needed.
Window cuts sample complete author CFR output on ceil/ceil boundaries; their
phase may retain the last complete frame to the author end. Ordinary short
sources are not padded. Decode references with `-fps_mode passthrough` and
check every frame identity, alpha, PCM and PTS. Respect the reported rational
denominator limit and unaccepted VFR reverse/source-in-plus-reverse cases.
Bounded SHA buffers do not establish OS OOM resilience or natural quality.
<!-- /V81-CURVE-CLOCK -->






<!-- V80-CURVES -->
RGB curves now accept fixed-topology point animation: `all.1.y`, `red.1.x`, `green.1.y`, `blue.1.y` using normal numeric effect keyframes. Inspect the 0.9.0 local catalog first. Keep the original point strings and author keyframes in the project; never persist or edit generated sendcmd files. `curves.master` remains an alias for all, not a post-master curve. Explicit RGB or an animated RGB channel forks the static all curve; other channels inherit animated all. Six-decimal x positions must occupy strictly increasing 8-bit bins; do not sort or drop points to force rendering. Point count is fixed (1–256); temporal easing is separate from native natural-cubic color interpolation. Known CFR-01: fractional FPS with non-frame-aligned clip boundaries can lose trailing coverage even without curves; verify actual visibility and do not claim that scenario accepted or silently snap author time. Use complete author clocks for trims, reverse/nesting and interval layers; respect shared command/sample/byte/target quotas. Check actual frame RGB/alpha, PCM/PTS and package/fragment rebuilds. Do not claim HDR, natural quality, real-time preview or CapCut algorithm equivalence.

[RGB point contract](../../docs/specs/RGB曲线控制点动画契约_v0.1_2026-10-21.md) · [native/isolated validation and failures](../../docs/validation/RGB曲线控制点动画离线实测_2026-10-21.md)
<!-- /V80-CURVES -->

<!-- V79-COMPONENTS -->
For declared editable HTML fields, read the
[component contract](../../docs/specs/HTML组件字段与逐片段取值契约_v0.1_2026-10-21.md) and
[native/isolated pixels, transfers, media and failures](../../docs/validation/HTML组件字段与逐片段参数离线实测_2026-10-21.md).
`motion html-fields --source-asset-id S` or `--from-asset-id A` returns typed
JSON Schema without drawing. Keep stable field IDs across display-name edits.
Pass local `--component-values` to html-render/controls/quality; null resets one
field, `--reset-components` clears component values then applies this patch.
Empty text, zero and false remain explicit values. Definitions and per-output
values are separate snapshots; preserve both on package/fragment transfer.
Images use `{ "asset_id": "registered_image" }` from the original source
closure with SHA and strict rights checks. No arbitrary image paths or URLs.
Boolean overrides run after each author frame; reset restores page animation.
The 128-change/64-KiB budget includes ordinary and component overrides.
`html-render --from-asset-id A --replace-clip-id C` changes only the matching
unlocked clip asset reference, preserving author timing and processing.
Render new immutable versions. Validate actual pixels and cleanup; this does
not accept arbitrary web pages, natural quality or full CapCut parity.
<!-- /V79-COMPONENTS -->

For existing local audio plus corrected text, the
[CTC alignment contract](../../docs/specs/离线CTC字词强制对齐契约_v0.1_2026-10-18.md)
defines `subtitle align --apply --track-id <subtitle> --font-asset-id <font>`.
Generated word times use the source sample clock and exact original character
indices; `--timeline-start-tick` shifts application without altering acoustic
samples. Font/text/model/source rights remain separate. Forced alignment
does not automatically author Chinese strokes or make the transcript correct.

For generated subtitle pieces, read the
[segmentation contract](../../docs/specs/本地字幕分段与局部回写契约_v0.1_2026-10-17.md).
`subtitle segment --apply --track-id <id>` creates ordinary inline text clips,
with source line/part references and explicit generated-SRT rights dependencies.
Use `--timeline-start-tick` for an integer placement offset and
`--replace-track` only when replacing that track is intended. Locked tracks,
overlaps, stale correction hashes and zero-duration quantization reject the
whole operation. Preserve those dependency fields during later edits.

# Timeline Composition

<!-- V78-TIMELINE-PREVIEW -->
For author timeline frames/ranges read the
[preview and content-cache contract](../../docs/specs/时间线帧区间预览与内容缓存契约_v0.1_2026-10-20.md)
and [native/isolated checks, media and retained failures](../../docs/validation/时间线帧区间预览与离线发行实测_2026-10-20.md).
Use `preview frame --frame N` or `preview range --start-frame S --end-frame E`
with `--project`; ranges are half-open output display frames. Compile the full
author graph before trimming; compare lossless BGRA/float-PCM NUT with the
complete graph. MP4/GIF are lossy opaque viewing copies. Transparent reference
requires transparent author output. Export with `--output <new project dir>`
to retain a result beyond `preview cache-prune`; omitted output is evictable.
Cache hits verify complete source/runtime/output content and do not execute
a new graph, encoder or model. Corruption rejects; explicit prune rebuilds.
`--dry-run`, project-local cancel markers, bounded space admission and current
asset-reference protection apply. Software preview decodes cumulatively from
author start. It does not accept realtime playback, natural quality or delivery.
<!-- /V78-TIMELINE-PREVIEW -->

<!-- V77-NATIVE-HSL -->
For catalog 0.8.1 selective HSL, read the
[native kernel and bounded DAG contract](../../docs/specs/八色HSL原生像素内核与表达式DAG契约_v0.1_2026-10-20.md)
and [native/installed outputs, full CLI timing and retained failures](../../docs/validation/八色HSL原生提速与离线发行实测_2026-10-20.md).
`AI_AD_EDITOR_HSL_BACKEND=auto|native|expression` defaults to a verified bundled
Windows amd64 frei0r DLL. Auto falls back for an absent platform module or
missing FFmpeg filter; integrity errors reject. Explicit native requires it.
Retain original author tracks on transfer; rebuild the immutable DAG at the
destination. Its 25 channels remain separate from the 34 command channels.
Check backend, program and DLL/source hashes, decoded pixels, alpha, PCM and
PTS. Native processing uses up to three shared background workers plus the
caller. Separate null-output filter throughput from complete CLI encoding
and interactive-preview acceptance. Older V76 geq timings below are historical.
<!-- /V77-NATIVE-HSL -->

<!-- V76-HSL -->
Historical V76 implementation and evidence (superseded execution backend):
For eight-band HSL tracks, read the
[25-channel HSL contract](../../docs/specs/八色分区HSL与关键帧契约_v0.1_2026-10-20.md)
and [clock, transfer and pixel checks](../../docs/validation/八色分区HSL与离线发行实测_2026-10-20.md).
Use `selective_hsl` with flat `<band>_hue`, `_saturation`, `_lightness`
parameters and ordinary author tracks; intensity mixes the final RGB result.
Keep original ticks through trims and transfers. This expression backend
shares 1,024 executed instances and two million state samples with native
commands; static neutral or zero-intensity bypass consumes none. Each kernel
is capped at 64 KiB, with 16 MiB across the root graph. Unknown channels reject.
<!-- /V76-HSL -->

For animated `blur`, `lens_correction`, `chroma_key` and `color_contrast`, read the
[14-channel contract](../../docs/specs/空间滤镜与抠像参数关键帧契约_v0.1_2026-10-20.md)
and [actual frame, clock and transfer checks](../../docs/validation/空间滤镜与抠像关键帧实测_2026-10-20.md).
Use effect-local author ticks and six supported interpolation modes. Radius
sets both Gaussian axes; similarity must be at least 0.00001. Keep the key color,
planes, lens sampling and fill tokens static. Static and dynamic RGB keys
multiply key-stage input alpha by native key coverage with 8-bit rounding.
They share a separate 1,024-node root budget and unique compositor labels.
Saved effects remain editable
through trim/split, relative retiming, packages and clip groups. Confirm the
installed runtime's actual commands before encoding; do not silently substitute
static parameters when a declared numeric channel cannot execute.

For external blend-opacity retiming, read the
[independent clock contract](../../docs/specs/外部混合动画与完整输出变速契约_v0.1_2026-10-20.md)
and [actual pixels, audio and transfer evidence](../../docs/validation/外部混合动画变速与静音修复实测_2026-10-20.md).
Relative speed, curve, reverse and freeze keep original opacity points in
`blend.opacity_animation`; maps run from the current complete output to the
original author ticks. At most 4096 points, 16 maps and 1 MiB are allowed.
Trims keep author phase. To replace the curve, author top-level `blend.opacity`
or `blend_opacity` keys; the next retime starts a fresh model from those keys.
Keep blending outside the child picture graph and apply original alpha once.
Direct tracking/transition endpoint restrictions still apply.

For reviewed text-box camera focus, follow the [OCR anchor contract](../../docs/specs/离线OCR与文字运镜锚点契约_v0.1_2026-10-19.md).
`ocr anchors --report <registered-report> --clip-id <id> --query <exact-text>
--frame-index <source-index> --apply --dry-run` plans editable
`transform.position.x/y` and `transform.scale` keys. Inspect the source frame,
hold and full-view return before applying. It preserves source/audio spans
and adds source/model rights dependencies. Same-sized forward 1x clips without
existing camera/crop/effects are supported; nested, retimed or transformed
inputs reject instead of guessing coordinates. Locked tracks cannot be edited.

For numeric color effect animation, read the
[color automation contract](../../docs/specs/逐帧调色参数自动化契约_v0.1_2026-10-19.md).
Existing compose `update_clip.patch.effects` accepts effect keyframe tracks;
catalog 0.7.0 retains the original 19 channels of temperature, balance, nine-wheel,
exposure and levels. Top-level effect keyframes take precedence over parameter
keyframes. Preserve author ticks through windows, curves, reverse and compound
holds. Independent text, groups and interval adjustments use the same bounded
native command compiler; interval clocks reset at their first retained frame.
Unsupported dynamic channels reject; booleans, curve strings and unlisted
filters remain outside this contract. Check per-target hashes and the shared
recursive budget in the manifest. Do not repair a corrupt derived command
cache by overwriting it. Kelvin keeps the existing shadow-RGB approximation.
The [actual media, encoding diagnosis and installed replay](../../docs/validation/逐帧调色参数自动化实测_2026-10-19.md)
compare independently authored parameters on the same pinned FFmpeg delivery
boundary; they do not establish physical white balance or CapCut color science.

For `lut3d` / `lut` / `cube` / `look`, use the numeric channel
`intensity` with ordinary effect keyframes, using the
[LUT strength contract](../../docs/specs/LUT强度关键帧契约_v0.1_2026-10-20.md).
Dynamic strength mixes the original and native LUT result in 8-bit encoded
RGB; alpha is preserved. Paths/IDs/interpolation enums stay static. Constant
and nonlinear nested ancestors retain the effect's author clock; trimmed or
split clips retain animation phase. Interval adjustments use their local clock
and explicitly split the composed surface. Inspect LUT SHA, unique blend
target and shared commands/budgets in the render manifest. Static partial
CUBE strength uses versioned red-fastest identity tables; damaged old/new
cache files are not overwritten. See the
[real pixels, portable edits and failures](../../docs/validation/LUT强度关键帧与中性调色修复实测_2026-10-20.md).
This does not accept HDR, linear-light mixing or all vendor LUT dialects.

For relative retiming of the current complete visible output, read the
[complete output retime contract](../../docs/specs/完整作者输出变速与磁吸联动契约_v0.1_2026-10-18.md).
Use `timeline edit` action `retime` with `clip_ids`, `transform` and optional
`options` / `sync_content`; compose `retime_clip` joins an atomic batch.
Speed/curve/reverse/freeze runs after original windows, animation and buses.
Main durations ripple; intersecting links share the complete host clock.
Continuous unlinked BGM defaults to unchanged-speed ripple; explicit
`sync_content: retime` warps its intersecting body. Review the editable child
sequences and before/body/after spans. External blend animation uses the
independent clock above; tracking and direct transition endpoints reject.
Root markers and bus points stay absolute.
Nested native audio preserves hold knots and merges adjacent equal tempos;
its terminal source end differs from the legacy constant file path's head
selection. Keep natural quality separate from the
[actual frames, PCM and failure evidence](../../docs/validation/完整作者输出变速与磁吸联动实测_2026-10-19.md).

For persistent main-track editing, read the
[magnetic mode contract](../../docs/specs/主轨磁吸模式与跨剪口同步拆分契约_v0.1_2026-10-18.md).
`timeline edit` with `{action: "magnet", enabled: true}` packs existing gaps
and persists `sequence.editing.magnetic`; existing main overlaps reject.
Main `shift` chooses the nearest original cut of the remaining main track,
with earlier ties. Compose main append/remove/slide/trim uses the mode planner;
trim cannot also request a separate placement. Review the full hash-bound plan.
The mode defaults sync on only when sync was not explicitly configured.
Reorder `sync_span_policy: split` partitions differently displaced sync spans
after the complete author graph, keeping source/curve/freeze/audio clocks.
Magnetic mode defaults to split; ordinary mode defaults to reject. Direct
main links keep their explicit host. Linked side cohorts share cut regions
and fresh later link IDs. Locked members, transition endpoints and tracking
references reject automatic splitting. Keep detector/nonlinear lane protections.
Saving a partial magnetic fragment expands the full sequence and reports it.
Absolute author speed/curve/freeze setters must still satisfy the main invariant;
use the relative retime planner above for automatic following. GUI gestures remain open. Markers and sequence
automation stay absolute. Read the
[actual media, fragment failure and installed checks](../../docs/validation/主轨磁吸模式与跨剪口同步拆分实测_2026-10-18.md).

Use the [named audio routing contract](../../docs/specs/命名音频总线发送返回与侧链契约_v0.1_2026-10-18.md)
for `update_sequence.patch.audio_routing` (null restores legacy tree mixing).
Track rows reference local video/audio tracks; output defaults to master,
null disables only direct output, and sends address local buses. Pre/post
taps surround volume/pan/fades after tone processing. Automation uses the
sequence clock; a shortened sequence must contain all retained author points.
Bus solo isolates paths with the complete sidechain detector context. Child
routing precedes ancestor trim/reverse/speed/freeze/windows. Routed fragment
selection expands and is reported. Automatic relocation cannot split named
detectors or tone state. Review the [actual samples and failures](../../docs/validation/命名音频总线发送返回与侧链实测_2026-10-18.md)
and run `policy audit` after rendering. No feedback/plugin host/surround is implied.

For whole-main-track ordering, use the
[magnetic reorder contract](../../docs/specs/主轨磁吸重排与关联附着契约_v0.1_2026-10-18.md).
`timeline edit` action `reorder` takes main `clip_ids` and a mandatory
`before_clip_id` (null appends). Stable selected clips become one block, and
all main clips pack from zero without changing their author payload. Links
on displaced shots follow too; differently displaced sync spans reject by
default in ordinary mode or use explicit `sync_span_policy: split` above.
Inspect the plan's moves/anchored IDs,
lane changes, subtitle offsets, references and transitions before applying.
Keep `transition_policy: preserve` unless removing broken declarations or
legacy fields is intended. See the
[actual frame/sample and package checks](../../docs/validation/主轨磁吸重排与关联附着实测_2026-10-18.md).
This explicit action is also used by persistent mode; it does not define screen snaps.

For a [compound freeze](../../docs/specs/复合片段定格与完整音画时钟契约_v0.1_2026-10-18.md),
apply the existing compose `freeze_frame` to the `sequence_id` container. The
whole child picture, captions, animation and audio bus finish before the
container source window/speed/reverse/freeze. Its own spatial animation keeps
running; an outer container retimes that complete result. `silence` inserts a
silent bus interval; `continue` plays original audio then pads its tail.
Non-frame holds report quantization. File-only R3 cannot consume an inline
retimed bus. Source-transition endpoints retain their own restrictions; an
ancestor may freeze a legal transition mid-blend. Keep internal surface IDs
out of author assets and preserve original rights. See the
[actual frame/sample checks](../../docs/validation/复合片段定格与完整音画时钟实测_2026-10-18.md)
for same-renderer glyph references versus independent clocks and alpha.

For explicit vector lettering, use `motion stroke-source --project <path>
--input <local-plan.json> --asset-id <new-source>`, then `motion html-render`
to encode/apply it on an ordinary video track. The
[stroke contract](../../docs/specs/离线逐笔描线动效契约_v0.1_2026-10-18.md)
defines character times, bounded absolute polylines and a hex ink color.
Keep the editable source and its original plan. This path generates no glyphs,
Chinese stroke order or speech alignment; Canvas ink is outside DOM text checks.

For HTML/SVG/Canvas overlay assets, read the [offline HTML motion contract](../../docs/specs/离线HTML动效与可编辑源码契约_v0.1_2026-10-18.md).
The FFV1/BGRA output of `motion html-source/html-render` uses ordinary timeline
edits. Preserve `html_motion.source_asset_id` and the source's image/font
references in packages and fragments. Rebuild parameters to a new asset
version; keep the editable ZIP and review any changes to existing clip uses.

Use the [source edit contract](../../docs/specs/真实源范围外扩与关联Slip契约_v0.1_2026-10-18.md)
for `timeline edit` slip/extend_source and explicit source handles on roll/slide.
Positive source deltas stay physical-forward even on reversed clips. Linked
source members are checked atomically; sync/rider movement is separate.
Inspect reanchored keyframes/freeze, edge reprocessing and nested normalization.
Legacy compose `slip_clip` defaults to one clip and accepts `linked: true`.

Use the [range edit contract](../../docs/specs/范围编辑插入覆盖与滚滑剪口契约_v0.1_2026-10-18.md)
for insert/overwrite with complete incoming clips, lift/extract with explicit
tracks, roll with a continuous left/right pair, and slide with a middle clip.
Input positions are group-relative; a declared group duration preserves holes
and its blank tail. Linked IDs expand across audio; sync and linkage follow
the operation-specific closure in the contract. Keep split source/curve/
animation fields unchanged and use presentation windows. Roll/slide need
retained author handles by default and complete linked pairs/triples; explicit
source policy can reauthor finite real handles. Slide moves the
whole middle body; it is not source-content slip. Markers remain absolute.

Use the [presentation cut contract](../../docs/specs/片段输出窗口裁切与波纹编辑契约_v0.1_2026-10-18.md)
for compose split_clip/trim_clip/ripple_insert/ripple_delete. These preserve the
complete authored source, curve, keyframes, freeze and clip audio processing in
presentation_window; source_in/out describe the full author input. Trim ranges
are relative to the current visible window; set timeline_start_tick to move the
result. Presets accept visible-local ticks and store author ticks. Speed/curve,
reverse and freeze commands require a full take; smart-cut/reframe/tracking on
windows reject. Remove affected real-handle or legacy cross-clip transitions
first. Markers stay absolute; full main-track magnet/linkage rules are separate.
Review frame/sample selections and repeated author-graph cost in render metadata.

Use [saved fragments](../../docs/specs/可复用片段组库与跨项目插入契约_v0.1_2026-10-18.md)
for editable cross-project groups. Insertion creates one container on an
unlocked video track; its source range selects the saved group's original
author clock. Do not zero child clip ticks or external subtitle cue times.
Review all automatically included link/transition/binding dependencies and
fresh ID maps before applying. Tick/FPS/color/audio context mismatches,
overlaps and partial ducking-bus selections reject; independent source canvas
and original transition endpoint limits remain in force.

Use [real source transitions](../../docs/specs/真实源句柄转场与可逆编辑契约_v0.1_2026-10-17.md)
for add/resize/remove across an exact same-track cut. The declaration lives in
`sequence.source_transitions`; compose batches `{op: "source_transition",
transition: <request>}`. Authored clips, original keyframe/subtitle clocks and
sequence length stay put. The renderer extends source windows on a detached
copy, supports nonintersecting cut chains, and multiplies separate linked-audio
envelopes. Review `audio=none` when intentionally omitting linkage. Locked audio,
source shortfall and stale/deleted cut references reject. Native black/white
dips reach that color at the original cut; legacy auto_handle still reports
its tail-clone approximation. Endpoint exclusions remain in that contract.
For parent use of a transitioned child, read the
[nested transition contract](../../docs/specs/嵌套转场合成与作者时钟契约_v0.1_2026-10-18.md).
Add declarations with `--sequence-id <child>`. The complete transparent child
is composed before ancestor trimming, reversal, constant/curved retiming and
spatial projection. Do not move transition starts to a parent's trim window.
Audio retains original source leaves and buses; reverse envelopes use the
continuous child author clock. Inspect `sequence-inline-surface` and
`sequence-inline-budget`, including child warnings. Ancestor freeze is now
handled by the compound-freeze path above. Container/curved/frozen/tracked/
blended cut endpoints retain the source-transition contract's restrictions.

Use the [linked edit planner](../../docs/specs/关联片段与主轨联动规划契约_v0.1_2026-10-17.md)
for link/unlink/remove/close_gap/close_gaps/shift on whole clips. Configure
`sequence.editing` (main_track_id/sync/linkage/linked), per-track `sync_lock`
and clip `link_id`. Inspect `timeline edit --dry-run` before applying; a
`compose` operation `{op: "linked_edit", edit: <request>}` joins one transaction.
The intermediate project must be valid before that operation. Linked locked
members reject the whole selection. Sync uses common available room and
reports `short_tick`; linkage follows riders while multi-cut beds stay anchored.
Collision lanes preserve processing; effect/ducking audio buses cannot be
automatically relocated. Keep file-subtitle offsets and tracking references.
These older whole-clip actions do not extend source edges; use the explicit
reorder action above for insertion-style ordering. The range actions cover insert/overwrite and
roll/slide within retained authors. Markers retain absolute sequence ticks.

Nested sequence clips now render as isolated transparent canvases; see the
[sequence compositing contract](../../docs/specs/嵌套序列隔离合成契约_v0.1_2026-10-17.md).
Composite the children first. Parent crop, canvas TRS/anchor, opacity, effects,
mask and fade then act on that result once. Keep the parent on its intended
root track: a child's high track order cannot escape that slot. Container
animation uses its containing sequence's authored clock. Do not pre-multiply
parent opacity into each child, flatten parent masks, or bake a lossy child
video to simulate a group. Inspect `sequence-composite` manifest inputs.
Use optional sequence `canvas: {width, height}` for an independent pixel raster;
see the [sequence canvas contract](../../docs/specs/独立序列画布与父级投影契约_v0.1_2026-10-17.md).
Omitted or null canvas inherits the effective project/output dimensions, not
the immediate parent. `add_sequence` accepts canvas; `update_sequence.patch`
accepts canvas/name/duration_tick/markers/editing, and null clears the canvas override.
Container crop pixels and cropped anchors belong to the native child; position
and the post-transform mask belong to its parent. Child text and tracking
bindings compile locally before projection. Selected-sequence export defaults
to that raster; profile/width/height override only the selected root for that
render. Odd internal rasters are valid; final 4:2:0 requires even width/height,
and 4:2:2 requires even width. Explicit child rasters survive parent overrides.
Independent child FPS/color/SAR,
standalone slide/wipe, linear-light/HDR and broad performance remain acceptance
boundaries; preserve existing audio and quality warnings. Native bilinear
sampling is not a promise of high-frequency minification quality.
An explicit `settings.sequence_sampling.method: area` selects a premultiplied
source-axis box for sequence containers, including same-canvas shrink; see the
[sampling and quota contract](../../docs/specs/序列面积采样与工作栅格预算契约_v0.1_2026-10-17.md).
Leaf sampling remains separate. General rotation is not exact rotated-pixel
integration. Inspect `sequence-projection-budget` and preserve a resource
rejection instead of silently shrinking, dropping frames or raising the budget.

Use a registered SAM2 adapter with local `--prompts` for multiple selected
objects, boxes, positive/negative points and future-frame corrections; read
the [SAM2 contract](../../docs/specs/本地SAM2对象分割与提示修正契约_v0.1_2026-10-16.md).
Prompt frame numbers and normalized coordinates refer to the processed output,
including range trim and CFR resampling. Explicit scene reset requires fresh
prompts. Its MOV layers and explicit audio application use the same timeline
semantics below. Review object scope and motion; probabilities are not a matte.

Use `media matting` with a registered RVM adapter to create a local soft-alpha
human cutout; read the [matting contract](../../docs/specs/本地RVM人物视频抠像与透明素材契约_v0.1_2026-10-16.md).
Its QTRLE/ARGB MOV is an ordinary video asset. Apply it to a video track with
higher `order` than the background. `--audio-track-id` explicitly creates a
matching audio clip; preserved embedded MOV audio alone does not mix itself
into the sequence. Keep both source/model rights dependencies. Final transparent
delivery uses the existing WebM/VPX `yuva420p` output, with a decoder that supports
WebM alpha for visual checks. Review initial-frame defects and held-object loss;
pipeline verification does not establish broad human matting quality.

Native model tracking is described in the [YOLO contract](../../docs/specs/本地YOLO检测与多目标跟踪契约_v0.1_2026-10-15.md).

An already registered selected video mask can drive the same three tracking,
binding and reframe commands through `--mask-asset-id`, replacing ROI/adapter
selection; see the [mask tracking contract](../../docs/specs/本地分割蒙版轨迹与锚定契约_v0.1_2026-10-16.md).
Keep source/mask time correspondence explicit. Selected/clear expectations can
gate application, and failures preserve diagnostics while rolling back edits.
Retain source and mask/model rights dependencies on the target clip.

Review `media track --all-objects` before binding an ID to text or reframing a
direct clip. Preserve the applied clip's `rights_dependencies` entries with
model registration SHA-256; they participate in publish gates. Label binding
without source references uses normalized source coordinates. For current
crop/fit/fill/stretch, transform, mirror and source-time mapping, supply both
`--source-track-id` and `--source-clip-id`; see the [canvas binding contract](../../docs/specs/本地跟踪绑定坐标空间与渲染重算契约_v0.1_2026-10-15.md).
This saves source-clock observations and recompiles them for the render canvas.

Alpha-media ordinary scale, affine rotation and dynamic-size crop interpolate
premultiplied RGB, then return straight RGBA. Fixed-raster inline/independent
text builds straight RGBA from opaque component coverage and authored colors.
See the [alpha contract](../../docs/specs/透明素材重采样与文字Alpha契约_v0.2_2026-10-16.md).
Alpha fit bars are transparent; opaque dynamic-fit bars stay black. Position/
anchor clocks are unchanged. Review encoded output; other effect warps, linear
light, total memory and broad natural quality require separate acceptance.
Optional `--rotation-mode source` follows layer rotation, not object pose.
Live bindings own their generated transform keys; set `tracking_binding` to null
with update_clip to detach while retaining saved preview keys. Nested parents,
mask/occlusion visibility, VFR and nonlinear warps remain review boundaries. Do not delete
dependencies or warnings to make a project pass a release gate.

Nested variable-speed clips retain an analytic source-clock composition for
video and authored keyframes; read the [nested clock contract](../../docs/specs/嵌套序列解析时间映射契约_v0.1_2026-10-16.md).
Keep each reverse attached to its own container, and keep leaf curves in their
original source domain after trimming. Render manifests record the composed
maps and explicit source CFR normalization. Audio still uses atempo windows
with integrated 48 kHz boundaries, so retain its phase/continuous-tempo warning.
Use the [speed easing contract](../../docs/specs/速度曲线Easing与Bezier契约_v0.1_2026-10-16.md)
for ease_in/out/in_out and two/four-value Bezier handles. Keep the authored
source-domain curve; never replace easing with its endpoint chord. Bezier
handles must be finite, x handles in 0..1 and the entire speed curve positive.
Inspect SPEED_CURVE_COMPILED certificates: 250 us is an unnormalized per-curve
clock bound, not a composed output guarantee. Segment/expression budget failures
must remain errors; audio is still windowed. Endpoint speed floor 0.01 remains.
For [nested frame coverage](../../docs/specs/嵌套视频帧区间与结束时钟契约_v0.1_2026-10-17.md),
source CFR frames cover half-open intervals: retain both partial endpoint
frames with exact rational frame bounds. The native EOF event maps through
the authored source endpoint after the expected source count. Inspect
`nested_time_mapping.frame_sampling`, then check the encoded source identities
and every visible output sample. Keep real leading/trailing timeline gaps;
the final global frame interval must not reveal early or leak past the end.
A subframe trim can retain one source frame or have no final output sample.
The EOF mapping does not pad a genuinely short input or relax publish duration.
Freeze, parent pivots and group coordinate spaces keep separate acceptance
boundaries. Nested captions use the original authoring clock; see the
[caption clock contract](../../docs/specs/嵌套字幕与文字动画时钟契约_v0.1_2026-10-16.md).
Inline word/animation offsets are clip-local; custom x/y t is author-sequence
time. Leaf media reverse does not independently reverse inline overlay cues.
External SRT/ASS defaults to author-sequence timestamps; choose
`subtitle.asset_time_base=clip` for clip-relative files. Supply a local font
asset and verify its actual family; libass fontsize uses ASS units. Captions
on frozen intervals, file animation and inline rotate retain explicit limits.
Dynamic-size inline alpha animation remains approximate; prefer an independent
title track for that combination. For word colors, read the
[native paragraph contract](../../docs/specs/逐字高亮原生排版与颜色选择契约_v0.1_2026-10-16.md).
Fixed-raster highlights select between two identical full-paragraph paints;
native FFmpeg/font metrics position the selection. Repeated words and line
spans preserve source ranges. Use literal text and a local font; bidi, split
graphemes/internal shaping clusters and stateful position expressions are
rejected during render planning. Dynamic-size inline highlights retain the
whole sentence and explicitly suppress highlighting; use an independent title.
Fixed-raster style colors use the [coverage/color contract](../../docs/specs/文字颜色透明度与独立覆盖率契约_v0.1_2026-10-16.md).
Box, shadow, border and fill retain separate opaque glyph coverage, then apply
each authored color alpha once in that order. Active word color replaces the
normal paragraph paint, including its opacity. Color alpha, supported fade
opacity and layer opacity multiply. Review `text_paint` fingerprints and actual
encoded controls; working color is 8-bit encoded RGB, with integer rounding.
Random colors are rejected; dynamic-raster inline colors retain an explicit
approximation. External ASS, linear-light/HDR, dynamic-raster combinations and
overlapping lines still need separate acceptance. A render intentionally records outputs
and provenance; compare authored timeline/assets/settings and Rights Ledger
when checking that generated internal clocks were not persisted.

For [combined animations and native typing](../../docs/specs/文字动画高亮组合与原生打字机契约_v0.1_2026-10-17.md),
apply fixed-raster word timing together with fade, slide, pop, bounce or typing;
rotate needs an independent text layer. Typing paints whole native prefixes on
the complete paragraph's fixed origin/baselines, with one complete box. Source
whitespace consumes steps; LF does not. Existing local fonts and an FFmpeg build
with drawtext runtime `text` commands are required. Inspect `text_layout.typing`
and actual encoded glyphs; exit zero alone cannot establish command execution.
Command files are immutable content-addressed streams; planning a later plain
or differently styled version must preserve earlier plan/manifest hashes.
The CFR command schedule uses compiled ancestral author time, including reverse.
Keep 512-grapheme/128-line/16384-command/4 MiB budgets and planning rejections for
bidi, stateful positions and undersized boxes. Dynamic-size inline typing keeps
an explicit approximation; its combination with highlighting is suppressed.
General VFR, frozen clocks, shaping, HDR and long-project performance remain open.

Write a project-relative JSON change set and apply it with:

```powershell
python -X utf8 -m ai_ad_editor timeline compose --project .\work\demo --input .\changes\shot.json
```

Use integer ticks from the project timebase. Prefer explicit clip IDs,
source in/out points, track IDs and keyframe properties. The command creates
a before-mutation snapshot and validates references, time ranges, transitions,
mask geometry and nested sequence cycles before saving. Unsupported or
approximate effects must remain visible in the response and render manifest.

For titles and captions that must exist independently of a source video, add a
`kind=subtitle` track and append a clip with `generator: {"type": "text"}` and
`subtitle.text/style`. The local renderer draws this layer on a transparent
canvas; `animation.type=rotate` rotates the text layer itself; clip transform/keyframes, masks, blend modes, fade/dissolve alpha transitions, and basic slide/wipe spatial transitions apply to the independent layer. Complex transition handles still need explicit local support. Register local
font assets through `style.font_asset_id` or provide an existing local
`style.fontfile`. Use `word_timing.start_char` when repeated words need an
unambiguous highlight anchor; source text mismatches are rejected before save.


For [offline audio stretching](../../docs/specs/离线音频伸缩与PCM输出契约_v0.1_2026-10-17.md),
use only an explicitly pinned local R3 executable, native dependencies and license.
Planning must not decode audio. Check actual source/output sample counts and
channels, not padding or container duration alone. Compare encoded float PCM
with the derived artifact; use MKV pcm_s24le/pcm_s32le/pcm_f32le for precision.
Inspect whole-clip time maps and engine stderr. R3 must receive interior anchors;
0 -> 0 can trigger a native NaN warning. Keep full endpoints in the manifest.
The raw WAV PEAK timestamp is normalized without altering PCM bytes; repeated
renders must preserve existing cache bytes and reject tampering. Keep automatic
quality, pitch, local transient timing and listening conclusions separate. A
4 ms clip stretched to 250 ms can be audible but still fail pitch preservation.
Unconfigured projects use the default native atempo path and its explicit limits. A unity-tempo positive
control passing on both versions is not evidence of a historical failure.

Explicit [real source context](../../docs/specs/离线音频真实源上下文与精确选区契约_v0.1_2026-10-19.md)
is available with `settings.audio_stretch.source_context_ms` (integer 0..1000,
default 0). It uses finite physical source handles, never padding/repetition;
the output crops back to the original authored sample interval before reverse.
Review the actual extended PCM budget and context warning. Source-edge shortage
clamps to actual samples; stale duration/short decoded audio rejects. Adjacent
transients and stereo phase still require review; this is not timeline-neighbour mixing.

The [R3 channel strategy](../../docs/specs/R3声道策略契约_v0.1_2026-10-17.md)
accepts `settings.audio_stretch.channel_mode`: `together` (the compatible
default, with `--centre-focus`) or `apart` (native per-channel fidelity
preference, without that flag). Record the resolved mode and argv in the
manifest. Modes use distinct immutable caches; omitted and explicit together
are equivalent. Apart can degrade phase and mono compatibility. Separated
short-window spectral peaks still do not prove pitch preservation. Never add
outside-selection audio, padding, short-window processing or pitch correction
as an implicit workaround. Mono/stereo controls do not accept 3..8-channel quality.

For [hierarchical audio buses](../../docs/specs/分层音频总线与采样包络契约_v0.1_2026-10-17.md),
use existing clip/container `audio` controls and `audio.volume` / `audio.pan`
keyframes. Clips mix into tracks, track effects run after that sum, and container
effects run after the child sequence sum. Every mix uses floating addition with
normalization disabled; adding a silent input must not attenuate other inputs.
Old multitrack project levels can change. Provide headroom explicitly: float
peaks can exceed 1 and no automatic limiter is inserted.

Mute audio through `clip.audio.mute/muted` or `track.audio.mute/muted` to retain
video. `track.muted` still removes the whole track. Audio-track solo and explicit
music ducking are local to each authored sequence; a parent treats a child bus
as one role. Give the container an explicit role when the parent needs it as a
voice or music input. V55 adds the bounded named sends/returns described above;
feedback and spatial routing remain open.

Place audio on the 48-kHz half-open sample grid using rational ceiling, without
integer-millisecond rounding. Container automation uses its own authored clock:
its reverse changes child content, while an ancestor reverse or trim changes
the inner automation clock. Numeric stereo pan is balance, not equal-power mono
pan. Put fades on clips or containers; track fades have no authored clip window
and emit an unsupported warning. General effect-parameter automation is pending.
Inspect `audio-track-bus`, `sequence-audio-bus`, `sequence-audio-root` and leaf
sample-window nodes in the actual render manifest. Keep gain-clock acceptance
separate from the approximate retimed content and its remaining failures.

The [native tempo context contract](../../docs/specs/分段音频变速上下文契约_v0.1_2026-10-17.md)
warms each default atempo segment with audio contained in the same authored
selection, then selects the original integrated output core. Inspect
`audio_tempo_context` for source/core bounds, cumulative output samples,
`output_selection` and `shortfall_policy=zero-pad-core`. The final non-unity core
selects the actual retimed end; do not substitute its nominal offset for the
unknown native output position. Endpoint context uses float32 and a 64-MiB
estimated PCM preflight limit, not a total RAM guarantee. Unity retains `anull`; an explicitly pinned R3
engine keeps its own whole-clip path. Context reduces controlled interior DC
gaps but does not accept continuous phase, transients, arbitrary pitch or
listening. Preserve the development slow/cropped-tail failures and recheck the
current complete active interval and actual terminal source marker. Arbitrary
or ultra-short input can still be insufficient and require zero padding; an
interior amplitude pass and correct container length do not establish quality.

Use the [HTML shutter contract](../../docs/specs/HTML子帧快门采样与预乘透明合成契约_v0.1_2026-10-20.md)
for optional subframe redraws of an explicit HTML asset. Run `motion html-render`
with `--shutter-samples 1..16`, `--shutter-fraction 0..1`, and sorted unique
`--shutter-cut-tick` source anchors. A cut is in the HTML source tick clock, not
a timeline clip clock; the output frame anchor selects its half-open segment.
Recipes inherit through `--from-asset-id`; clear internal cuts explicitly with
`--shutter-clear-cuts`. Package/fragment reuse retains these parameters.
Keep the [measured clock and Alpha evidence](../../docs/validation/HTML子帧快门与透明混合实测_2026-10-20.md)
separate from aesthetic acceptance. This does not infer scene changes or
synthesize subframes from ordinary video; default or zero exposure keeps the
existing CFR path.
