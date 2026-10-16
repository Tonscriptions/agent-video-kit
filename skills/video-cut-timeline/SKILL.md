---
name: video-cut-timeline
description: Compose an Agent Project timeline with local clips, tracks, transitions, keyframes, masks, speed curves, nested sequences, captions, and audio automation.
---

# Timeline Composition

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
Unconfigured projects retain the legacy atempo boundary. A unity-tempo positive
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
