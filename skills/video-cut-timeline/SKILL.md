---
name: video-cut-timeline
description: Compose an Agent Project timeline with local clips, tracks, transitions, keyframes, masks, speed curves, nested sequences, captions, and audio automation.
---

For generated subtitle pieces, read the
[segmentation contract](../../docs/specs/本地字幕分段与局部回写契约_v0.1_2026-10-17.md).
`subtitle segment --apply --track-id <id>` creates ordinary inline text clips,
with source line/part references and explicit generated-SRT rights dependencies.
Use `--timeline-start-tick` for an integer placement offset and
`--replace-track` only when replacing that track is intended. Locked tracks,
overlaps, stale correction hashes and zero-duration quantization reject the
whole operation. Preserve those dependency fields during later edits.

# Timeline Composition

Use the [range edit contract](../../docs/specs/范围编辑插入覆盖与滚滑剪口契约_v0.1_2026-10-18.md)
for insert/overwrite with complete incoming clips, lift/extract with explicit
tracks, roll with a continuous left/right pair, and slide with a middle clip.
Input positions are group-relative; a declared group duration preserves holes
and its blank tail. Linked IDs expand across audio; sync and linkage follow
the operation-specific closure in the contract. Keep split source/curve/
animation fields unchanged and use presentation windows. Roll/slide need
retained author handles and complete linked pairs/triples. Slide moves the
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
`sequence-inline-budget`, including child warnings. Ancestor freeze and
container/curved/frozen/tracked/blended cut endpoints remain rejected.

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
These whole-clip actions do not extend source edges or implement full magnetic
main-track rearrangement. The range actions above cover insert/overwrite and
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
Named audio send/return, independent child FPS/color/SAR, nested freeze,
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
voice or music input. Named send/return, feedback and spatial routing remain open.

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
