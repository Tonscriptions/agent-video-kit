---
name: video-cut-agent-editor
description: "Drive the local Agent-first advertising video editor CLI for project setup, timeline composition, edited clip-group reuse, local TTS, templates, validation, rights checks, conversion, and FFmpeg rendering."
---

<!-- V90-MULTICAM-AFFINE-CLOCK -->
When capabilities advertise media.multicam_clock / multicam-affine-clock-v1, use media multicam --clock-model affine explicitly for bounded device clock-rate calibration. Default offset stays constant-delay mode.
Inspect source = offset_seconds + source_per_reference * reference, matched anchors, ambiguity, residuals, observed interval and asset SHA bindings. Do not fabricate a successful model or fall back silently after rejected calibration.
Use --dry-run first when applying a switch plan. Keep source rates and inverse coverage; trim leaves real gaps, stretch changes sync and warns. Observed-interval extrapolation requires --allow-clock-extrapolation and retains its warning. Author master audio explicitly.
The analysis prefix is bounded to 600 seconds, with 3–31 anchors, 4–60 second windows and at most 20000 ppm (default 5000). It does not implement nonlinear/discontinuous drift or acoustic-room quality acceptance.
Read the [affine clock contract](../../docs/specs/多机位仿射时钟与漂移校准_v0.1_2026-10-21.md) and [independent native/isolated report](../../docs/validation/多机位仿射时钟与浮点音频实测_2026-10-21.md).
Scalar render source normalization is floating point before author selection; do not introduce intermediate s16 quantization. Preserve native leading gaps and keep async resampling drift correction disabled.
The 590-second synthetic event interval and three short output windows are not complete long-form, natural/HDR/RSS, listening or full CapCut parity acceptance. Native frame-coverage identity is not identical event counters at differing camera sample phases.
<!-- /V90-MULTICAM-AFFINE-CLOCK -->

<!-- V89-OFFLINE-MEDIA-PROFILE -->
<!-- OFFLINE-MEDIA-PROFILE-LAB-20261021 -->
Use the complete media-analysis-v1 eight-wheel bundle for the current product. Run its copied native installer with the separately reviewed manifest SHA; launch the installed CLI with native Python -I -S -B and run.py.
Read the [offline media profile contract](../../docs/specs/离线媒体运行时与NumPy交付_v0.1_2026-10-21.md) and [fresh native/installed evidence](../../docs/validation/八轮离线媒体运行时实测_2026-10-21.md).
The official pinned NumPy2.4.2 cp313 Windows x64 wheel and original notices are verified locally. The fresh eight-wheel install does not copy host NumPy and does not create a virtual environment, download at runtime or change global site-packages. Existing native Python/pip and FFmpeg are prerequisites.
Older core-v1/font-text-v1 bundles remain accepted only for products whose declared dependencies fit those profiles. Current products declaring NumPy require media-analysis-v1. Missing or changed sources must fail before building the product wheel.
This acceptance covers the stated pinned platform and synthetic media. A general dependency resolver, other ABIs, full model distribution, natural/HDR/long-form/RSS/playback/listening and complete CapCut parity are separate acceptance work.

<!-- /OFFLINE-MEDIA-PROFILE-LAB-20261021 -->
<!-- /V89-OFFLINE-MEDIA-PROFILE -->


<!-- V88-NATIVE-AUDIO-SOURCE-ORIGIN -->
<!-- NATIVE-AUDIO-SOURCE-ORIGIN-LAB-20261021 -->
When media.source_audio_clock advertises demux-relative-first-audio-pts-v1, retain source-leading silence before selecting, reversing or retiming audio. Keep the master audio track explicit.
The native PCM acceptance uses demux-relative input timestamps with aresample first_pts=0 before source selection. Async clock-drift correction is disabled. Zero-origin audio and equal nonzero container/audio origins must not gain false silence.
Read the [source audio clock contract](../../docs/specs/原生音频起点与作者采样时钟_v0.1_2026-10-21.md) and [actual native/isolated evidence](../../docs/validation/原生音频起点与同步实测_2026-10-21.md).
The real two-case sample covers container origins 0/5 seconds and audio starts 1/6 seconds, each a one-second relative gap. Source-normalized audio and offset-applied camera cuts are checked separately. R3 input/output frame and silence controls do not establish listening, pitch or stereo-phase quality.
Compressed-codec priming, negative timestamps/edit lists, internal timestamp discontinuities, nonlinear/discontinuous device drift, natural recordings, long-form/RSS, continuous playback and listening still need acceptance.
The current media-analysis-v1 profile ships eight pinned offline wheels, including NumPy 2.4.2. Earlier font-text-v1 experiments used an explicit local NumPy copy; those historical receipts do not establish the current profile. Verify the current bundle manifest, native-operation audit and module origins before use.

<!-- /NATIVE-AUDIO-SOURCE-ORIGIN-LAB-20261021 -->
<!-- /V88-NATIVE-AUDIO-SOURCE-ORIGIN -->


<!-- V87-MULTICAM-NATIVE-STREAM-COVERAGE -->
<!-- MULTICAM-NATIVE-STREAM-COVERAGE-LAB-20261021 -->
For multicam_source_coverage 0.3.0, use actual native-video coverage, independently of the longer container/audio duration. Review native bounds before authoring camera switches.
Native coverage uses first PTS, last PTS plus known duration, native time_base and the renderer's demux-origin rounding; retain the exact rational boundaries from the report. Container duration alone cannot establish video coverage.
Default shortfall policy rejects. Explicit trim leaves gaps at original reference positions; stretch clamps to the real first native frame, changes event timing and must retain its warning. Completely disjoint coverage rejects under every policy.
Dry-run reads existing verified native indices without writing caches, reports, snapshots or authored files. A hit reports zero source-frame probes but still reads hashes. Corrupt indices or changed source SHA reject; do not silently repair them or convert integrity errors into successful audio-only analysis.
Read the [native coverage contract](../../docs/specs/多机位原生帧覆盖与只读索引契约_v0.1_2026-10-21.md) and [fresh native/isolated evidence](../../docs/validation/多机位原生视频覆盖实测_2026-10-21.md).
The base seven-wheel installer does not ship NumPy. This experiment explicitly copies the existing local NumPy 2.4.2 distribution with RECORD hashes and licenses; it is not automatic dependency installation.
Unknown-EOF audio-analysis controls include simulated video state. Native PCM source-leading gaps and nonzero container origins use the separately advertised source_audio_clock contract. Compressed priming/edit lists, nonlinear/discontinuous clock drift, natural multicamera quality, HDR, long-form/RSS, continuous playback and listening remain separate acceptance work.

<!-- /MULTICAM-NATIVE-STREAM-COVERAGE-LAB-20261021 -->
<!-- /V87-MULTICAM-NATIVE-STREAM-COVERAGE -->


<!-- V86-MULTICAM-SOURCE-COVERAGE -->
<!-- MULTICAM-SOURCE-COVERAGE-LAB-20261021 -->
Use the advertised source_shortfall policy when building media multicam plans; preserve the requested master duration and explicit audio tracks.
When multicam_source_coverage is advertised, coverage shortfall defaults to reject. Explicit --source-shortfall trim intersects source coverage and leaves gaps; stretch clamps or slows and warns that event sync changes.
Completely disjoint coverage, locked apply targets and sub-tick segments reject. Dry-run performs audio analysis but writes no report or authored project.
Read the [coverage contract](../../docs/specs/多机位源覆盖与显式缺口策略_v0.1_2026-10-21.md) and [real native/isolated evidence](../../docs/validation/多机位源覆盖与原速同步实测_2026-10-21.md).
NumPy is an explicit local dependency; the base seven-wheel bundle does not contain it. The isolated experiment copies the existing 2.4.2 distribution, without runtime installation or download.
Container duration does not establish per-stream video EOF. Offset confidence, tick rounding and natural multicamera quality require separate review.

<!-- /MULTICAM-SOURCE-COVERAGE-LAB-20261021 -->
<!-- /V86-MULTICAM-SOURCE-COVERAGE -->


<!-- V85-NATIVE-EMPTY-WINDOW -->
A valid source selection wholly before native video begins or after its known EOF can have no video frames. Preserve the authored window and underlying layers. Author audio explicitly on an audio track; video placement alone does not extract sound.
Read the [empty-window contract](../../docs/specs/原生视频空区间契约_v0.1_2026-10-21.md) and [actual independent evidence](../../docs/validation/原生空视频选区与显式音频保留实测_2026-10-21.md).
Zero selected-frame raster budget is not zero decoding or process RSS.
<!-- /V85-NATIVE-EMPTY-WINDOW -->


<!-- V84-NESTED-NATIVE-CLOCK -->
When capabilities expose `nested_native_video_clock`, registered native video leaves preserve original PTS/duration through composed author clocks.
Use existing authored clips, source ticks, speed curves and reverse fields. Preserve native frame holds and real video EOF.
Virtual inline surfaces retain child CFR; general nested VFR effect combinations still need separate acceptance.
Keep the editable parent/child author graph and original source ranges. Report the advertised native-leaf scope when explaining the render plan.
Read the [native nested-clock contract](../../docs/specs/嵌套原生VFR时钟契约_v0.1_2026-10-21.md) and [actual native/isolated evidence](../../docs/validation/嵌套原生VFR时钟与多层速度曲线实测_2026-10-21.md).
Verified index hits skip full-source frame scans only; source/runtime hashes and final decode/encode remain. Existing expression, memory and disk limits apply.
The 32 new native interval oracles are part of 277 related methods. These proofs do not establish full CapCut parity, natural/HDR quality, audio quality, long-duration latency or total RSS.
Wholly empty native-video selections follow the validated empty-interval contract; preserve the original window and explicit audio track. Unknown EOF and corrupt indexes still reject.
<!-- /V84-NESTED-NATIVE-CLOCK -->


<!-- V83-NATIVE-INDEX -->
When capabilities advertise `native_video_frame_index`, ordinary native reverse reuses verified source PTS/duration arrays.
`source_index_decode_calls=0` skips full-source frame scans; source/runtime SHA reads, audio, final video decoding and encoding still apply.
Use `cache list --project P --kind native-video-index` before explicit `cache prune --project P --kind native-video-index --key KEY --dry-run`.
Current authored references are protected; keep corrupt indexes for diagnosis until explicit cleanup. Do not edit derived arrays.
Read the [index contract](../../docs/specs/原生帧索引缓存契约_v0.1_2026-10-21.md) and [actual native/isolated evidence](../../docs/validation/原生帧索引缓存与倒放复用实测_2026-10-21.md).
The 256-entry limit, V82 disk reservation and unaccepted long-duration, peak RSS, natural/HDR quality, nested VFR and full CapCut parity limits still apply.
<!-- /V83-NATIVE-INDEX -->


<!-- V82-REVERSE-CHUNKS -->
For ordinary native-video reverse, read the [V82 chunk/clock contract](../../docs/specs/原生分块倒放缓存契约_v0.1_2026-10-21.md)
and [actual native/isolated evidence](../../docs/validation/原生分块倒放与离线缓存实测_2026-10-21.md). Preserve original VFR display intervals
and fractional source bounds. Normal `render`/`preview` automatically prepare FFV1 native-format
chunks when the shared selected-frame estimate exceeds 256 MiB. Cache 25 Hz is a frame
counter; source intervals are reapplied. Chunk decode counters exclude the full-source
index probe. When capabilities expose native_video_frame_index, verified index hits skip that probe;
source/runtime SHA reads remain. Raster estimates are not process RSS guarantees.
Inspect cache plans and final revalidation in render manifests. The conservative 128 GiB disk
reservation can reject about 20 s of 4K/25 Hz even for compressible content; see the contract.
General nested VFR, long-duration performance, reverse audio, natural/HDR quality and full CapCut parity remain unaccepted.
<!-- /V82-REVERSE-CHUNKS -->

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
denominator limit. Ordinary native reverse follows V82; general nested VFR remains unaccepted.
Bounded SHA buffers do not establish OS OOM resilience or natural quality.
<!-- /V81-CURVE-CLOCK -->






<!-- V80-CURVES -->
RGB curves now accept fixed-topology point animation: `all.1.y`, `red.1.x`, `green.1.y`, `blue.1.y` using normal numeric effect keyframes. Inspect the 0.9.0 local catalog first. Keep the original point strings and author keyframes in the project; never persist or edit generated sendcmd files. `curves.master` remains an alias for all, not a post-master curve. Explicit RGB or an animated RGB channel forks the static all curve; other channels inherit animated all. Six-decimal x positions must occupy strictly increasing 8-bit bins; do not sort or drop points to force rendering. Point count is fixed (1–256); temporal easing is separate from native natural-cubic color interpolation. CFR-01 is covered by the V81 rational-clock contract; preserve author ticks and verify actual display boundaries. Use complete author clocks for trims, reverse/nesting and interval layers; respect shared command/sample/byte/target quotas. Check actual frame RGB/alpha, PCM/PTS and package/fragment rebuilds. Do not claim HDR, natural quality, real-time preview or CapCut algorithm equivalence.

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

# Video Cut Agent Editor

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
For eight-band selective HSL, read the
[HSL author contract](../../docs/specs/八色分区HSL与关键帧契约_v0.1_2026-10-20.md)
and [native/installed evidence and CPU limits](../../docs/validation/八色分区HSL与离线发行实测_2026-10-20.md).
Use catalog 0.8.0 `selective_hsl` for 24 band controls plus final intensity.
Its 25 expression channels are discovered separately from the existing 34
native-command channels. Selection uses original hue, preserves gray and
input alpha, and operates on encoded 8-bit RGB. Native geq is very slow at
1080p in the retained single-thread probe; do not promise real-time previews.
<!-- /V76-HSL -->

For animated blur, lens distortion, RGB color keying and color contrast, read the
[spatial/keying contract](../../docs/specs/空间滤镜与抠像参数关键帧契约_v0.1_2026-10-20.md)
and [native/installed pixel verification](../../docs/validation/空间滤镜与抠像关键帧实测_2026-10-20.md).
Catalog 0.7.0 exposes 14 additional channels, 34 native numeric channels across
10 families. Apply ordinary effect tracks with compose `update_clip`.
Blur radius drives both axes and can change alpha. Key color, plane selection
and sampling enums stay static. Color keying uses RGB distance; it does not
perform semantic matting or despill. Static and dynamic key coverage multiply
the alpha entering that key stage; inspect `colorkey-alpha-coverage` metadata
and the separate 1,024-node root budget. Check original author ticks, native command
support, decoded pixels and full PCM separately from natural visual quality.

For retiming animated external blends, read the
[blend-clock contract](../../docs/specs/外部混合动画与完整输出变速契约_v0.1_2026-10-20.md)
and [native/installed verification](../../docs/validation/外部混合动画变速与静音修复实测_2026-10-20.md).
Existing `timeline edit` retime and compose `retime_clip` retain the external
blend as editable `blend.opacity_animation`, outside the child picture graph.
Keep its author points and relative maps through trims and transfers. New top
level blend-opacity keys override the saved curve. Inspect actual alpha-only
commands, recursive budgets, decoded pixels and background PCM. An isolated
ancestor transforms rasterized child frames; it does not continuously resample
the child's already rendered opacity. Full CapCut parity remains unaccepted.

For local multi-frame inspection use `media contact-sheet` with a new project-local
output directory and explicit anchors or bounded automatic sampling. Read the
[contact-sheet contract](../../docs/specs/透明视频多帧联系表与实际时间锚点契约_v0.1_2026-10-20.md)
and [native/installed evidence](../../docs/validation/透明视频多帧联系表与Alpha核验实测_2026-10-20.md).
Report actual decoded PTS separately from requested time. Explicit anchors select
the first available frame at or after the request; automatic count is an upper
bound. Inspect checker/light/dark/alpha panels and preserve the manifest. This
read-only inspection does not accept natural quality or modify the timeline.

For local face anchors and retouch read the
[face contract](../../docs/specs/离线人脸锚点与局部修饰契约_v0.1_2026-10-20.md)
and [real execution and limits](../../docs/validation/离线人脸锚点与局部修饰实测_2026-10-20.md).
Use `face scan` with an explicitly registered CPU adapter. Use `face retouch`
with a reviewed report, explicit face selection and chosen controls to create
a new lossless asset. The source remains an explicit input; recipe replay
does not rescan or fetch weights. Neutral defaults, project transactions,
source/model rights and separate visual quality review remain applicable.

For duplicate serial deliverables, use opt-in `queue run --reuse-identical`
under the [batch reuse contract](../../docs/specs/同批次相同渲染结果复用契约_v0.1_2026-10-20.md).
Read the [actual checks and limitations](../../docs/validation/OpenFilm同批次结果复用实测_2026-10-20.md).
Inspect source provenance and actual encoded/reused success counts. Different
content or settings must not share an output, and copying never proves a new
encoder, model or device execution. New targets and explicit dependencies are
required; there is no persistent cache.

For explicit generated overlap conditioning, read the
[VACE context contract](../../docs/specs/VACE前窗生成上下文与连续输出契约_v0.1_2026-10-20.md)
and [current verification and failures](../../docs/validation/VACE前窗生成上下文实测_2026-10-20.md).
`media inpaint|outpaint --temporal-context previous` requires positive overlap;
default/`none` preserves independent windows. Previous uses actual emitted
selected pixels as known conditions, clears at cuts and never overwrites the
emitted prefix. It is generated context, not ground truth or whole-video
attention. Register a fresh adapter after implementation changes. Saved sampling
metadata does not trigger inference when importing or reusing rendered clips.

For generated canvas extension, read the [outpainting contract](../../docs/specs/本地视频扩图与原画面保护契约_v0.1_2026-10-19.md).
Use `media outpaint` with explicit target width/height and a registered local
LaMa/VACE adapter; optional integer offsets preserve the entire normalized
original. Review its dry-run geometry and budget before execution. The generated
asset retains an editable, validated recipe through project packages. Original
pixel/audio protection and generated-region quality require separate evidence.

For optional native hardware encoding/decoding, read the [hardware contract](../../docs/specs/硬件编解码探测与显式回退契约_v0.1_2026-10-19.md).
Use `render --hardware-encode prefer|require --hardware-encoder auto|nvenc|qsv|amf|mf`
and `--hardware-decode prefer|require --hardware-decoder auto|cuda|d3d11va`.
Encoding needs an explicit `--video-bitrate`; default off preserves the software path.
A compiled encoder list is not availability: inspect actual probes, chosen backends,
all attempts and the final format/color gate. Do not assert a speedup or full parity.

For opt-in R3 real source handles, read the
[audio source context contract](../../docs/specs/离线音频真实源上下文与精确选区契约_v0.1_2026-10-19.md).
Author `settings.audio_stretch.source_context_ms` as an integer 0..1000,
default 0. This reads adjacent physical source samples, stretches the extended
window and crops the original authored interval before reverse. Inspect the
manifest's actual bounds/map/crop and `AUDIO_STRETCH_SOURCE_CONTEXT` warning.
Short-tone pitch gains do not accept stereo phase, transients or natural sound.

For local visible-text editing use the [OCR contract](../../docs/specs/离线OCR与文字运镜锚点契约_v0.1_2026-10-19.md):
`ocr adapter register/list/inspect`, `ocr scan` and `ocr anchors`. Register
existing PP-OCRv4 ONNX/native Python with local evidence, review raw source
frame text/polygons, then apply a unique exact target as editable camera keys
with a full-view return. Dry-run does not execute the model or write a report.
No runtime install/download is offered. OCR confidence, a sampled box or a
successful render does not establish semantic UI actions, complete privacy,
natural-scene accuracy or full CapCut equivalence.

For animated color parameters, read the
[numeric automation contract](../../docs/specs/逐帧调色参数自动化契约_v0.1_2026-10-19.md).
Use catalog 0.7.0 `effects list/inspect` and existing compose `update_clip`
effects: 19 numeric channels of temperature, balance, three-way wheel,
exposure and levels execute on actual CFR samples. Retain complete author
graphs in package transfers; the target rebuilds content-addressed command
files with globally unique filter targets. Unknown dynamic properties,
unavailable native runtime options, corrupt caches and cumulative graph
budgets reject explicitly. Inspect `effect-automation` and its root budget.
Interval adjustment clocks and six-decimal serialization are explicit limits;
Kelvin still uses the existing shadow-RGB mapping. Review the
[real outputs, original failures and native installation](../../docs/validation/逐帧调色参数自动化实测_2026-10-19.md).
Same-FFmpeg static references require the same declared composite/encoding
boundary; this does not accept HDR, physical white balance or CapCut parity.

For animated LUT strength, follow the
[LUT contract](../../docs/specs/LUT强度关键帧契约_v0.1_2026-10-20.md)
and [native/installed evidence](../../docs/validation/LUT强度关键帧与中性调色修复实测_2026-10-20.md).
`intensity` is retained from catalog 0.6.0; all four LUT aliases accept its
0..1 author-tick keyframes and six interpolation types. Dynamic mixing uses
local lut3d plus independently addressed blend RGB opacity commands, preserving
alpha. Check the source LUT hash, CFR sampling and recursive budget. Static
partial strength still requires a complete CUBE, with corrected red-fastest
identity tables and a new cache version. Never hide cache-corruption errors.
Package export materializes referenced local paths/registered IDs as hashed
paths, keeps keyframes and original LUT bytes, and rejects missing/changed
registered resources before creating a ZIP. Review encoding and color-space
limits separately from authoring/portability tests.

For automatic duration following after relative speed/curve/reverse/freeze,
read the [complete output retime contract](../../docs/specs/完整作者输出变速与磁吸联动契约_v0.1_2026-10-18.md).
Use `timeline edit` action `retime`, or compose `retime_clip`, with a transform
of the current complete visible output. Original author graphs remain editable
child sequences. Main clips ripple; linked intersections share the host clock.
Background music defaults to unchanged-speed ripple, with explicit
`sync_content: retime` for common retiming. Review all partial spans, absolute
markers, root bus points and the dry-run hash. Existing absolute source setters
retain their meaning. Direct tracking/transition endpoints reject. External
blend animation uses the independent clock contract above. Native tempo timing
does not prove natural quality; see the
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
For the current product use the eight-wheel `media-analysis-v1` bundle with
Pillow and NumPy. The seven-wheel `font-text-v1` and six-wheel `core-v1` profiles
reproduce dependency-compatible historical products only.
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
4. Use `media understand` for local scene/silence/beat candidates. Add `--transcribe --model-path <existing-local-transformers-model>` only when an offline model has been registered; the command never downloads a model. Add `--srt <project-relative-path>` only when timed segments are returned. Use `media prepare` to make local proxies, thumbnails, and waveforms, and `media highlights` to write a hash-linked deterministic candidate report. For `media highlights`, run `--asset-id <id> --beats --top-k <n>` without `--apply` first, review the hash-linked report, then add `--apply --track-id <video-track>` only for a registered local video asset. Use `--replace-track` explicitly before clearing existing clips; preserve `HIGHLIGHTS_HEURISTIC` and `HIGHLIGHTS_REVIEW_REQUIRED`, and inspect semantic continuity, A/V sync, and transitions before publishing. Read the [highlights rough-cut contract](../../docs/specs/本地高光候选与自动粗剪时间线契约_v0.1_2026-10-15.md). Use `ad plan --input <brief.json>` to turn a local advertising brief into timed Hook/Problem/Benefit/Proof/Offer/CTA phases and marker operations before selecting assets. Use `subtitle validate`/`subtitle normalize` for SRT, VTT, ASS, SSA, and local TTML/DFXP before publishing captions; TTML external entities and unsupported timing expressions are rejected. Use `tts synthesize --project <path> --text <ASCII/English text> --output <project WAV>` for the local FFmpeg flite voice baseline; inspect `doctor.data.checks.local_features.flite_tts` first and surface the `TTS_LOCALE_UNSUPPORTED` response for non-ASCII text instead of retrying through a network provider. Before writing an effect into a plan, call `effects list` or `effects inspect --name <id-or-alias>`; use the returned backend, parameter limits, and `keyframable` flag. The current catalog has 45 local FFmpeg effects, including HSL, RGB curves, three-way color wheel mappings, and `frame_interpolation` backed by local `minterpolate`; native filters that remain static-only must keep any keyframe approximation warning visible, and motion-compensation CPU cost or scene-change artifacts must be quality-checked. For reusable color looks, run `lut register/list/inspect` to copy a local `.cube/.3dl/.csp/.dat` into the project, record SHA-256 and Rights Ledger evidence, then reference it as `{"type":"lut3d","parameters":{"lut_id":"lut_warm"}}`; a changed registered file is rejected by validation. Add `"intensity": 0.5` for a static partial-strength `.cube` look; the renderer writes a source-hash keyed identity-mixed LUT under the project `cache/luts/` directory, while `intensity=0` skips the LUT exactly. Static partial `.3dl/.csp/.dat` strength remains unsupported; dynamic `intensity` keyframes use the bounded native RGB pixel mixer described above, subject to the local FFmpeg parser and 8-bit limits. Before selecting a camera move, call `motion list` or `motion inspect --name <id-or-alias>`; the v0.1.0 local catalog contains 12 deterministic presets and bounded `amount`/`degrees`/`points` parameters. Use `motion apply --project <path> --clip-id <id> --preset <name>` to write ordinary transform keyframes to an existing clip; the command creates a `before-motion-apply` snapshot, records an operation, supports `--start-tick/--end-tick`, and supports `--dry-run`. `push_in`, `slide_*`, `rotate_left/right`, and `opacity_*` are compatibility aliases; use the returned canonical ID and preserve any catalog limits in the Agent response. Use `timeline compose` for explicit clip/track/marker changes and reusable motion presets, including split/ripple/slip/slide/speed/reverse/freeze operations; clip transforms accept normalized `transform.anchor.x/y` (or `anchor_x/anchor_y`, default `0.5`) and matching keyframes so an Agent can place a chosen layer corner or edge on a motion path; video-layer rotation compensates the expanded FFmpeg bounds to keep the anchor; independent text canvases still rotate around their canvas center, and nested parent pivots remain an explicit approximation warning; speed curves, nested sequences, static path/polygon masks, basic-shape mask.* keyframes, and normalized alpha feather are available with their reported approximation limits; clip changes may include validated rectangle/circle/ellipse `mask` objects and local FFmpeg `blend` modes. Adjacent clips may use `auto_handle: true` on a complex transition to invoke local xfade without manual overlap handles; the renderer preserves the authored duration with a visible tail-padding approximation warning. Use `template apply` or `template batch` only with a versioned local template and variable snapshot. Use `library index --root <local-dir> --output <catalog.json>` to build the v0.3.0 deterministic catalog, optionally pass `--previous <catalog.json> --incremental` to reuse stat-unchanged records and `--visual-hash` to add local FFmpeg `ahash-v1` samples; then use `library search --catalog <catalog.json>` for filename/relative-path/CJK-token/same-stem subtitle discovery and duration/dimensions/audio-stream filters, `library duplicates --catalog <catalog.json>` for exact SHA-256 duplicate groups, and `library similar --catalog <catalog.json>` for review-only visual candidates. The catalog declares `semantic.source=deterministic-local` and `vector_index=false`: do not describe this as VLM, OCR, embedding, person or object understanding, and never use visual candidates as a rights or publish decision. Feed selected records through Rights Ledger before publishing. Run `policy audit --project <path>` before a publish plan. For project-bound writes, pass a stable `--idempotency-key` when the caller may retry.

4.1. For a registered multi-object visual runner, use `media track --adapter-id <id> --object-id <object-id>` when one trajectory will be applied, or `--all-objects` for a report-only identity review. Never combine `--all-objects` with `--clip-id`. `media track-bind` and `media reframe` require `--object-id` for the v2 engine so multiple trajectories cannot be written into one text layer or crop window. Preserve `TRACK_OBJECT_SELECTION_REQUIRED`, `TRACK_OBJECT_NOT_FOUND`, `TRACK_OBJECT_SELECTION_UNSUPPORTED`, and `TRACKING_MULTI_OBJECT_REVIEW`; review identity continuity through occlusion/crossing, then apply only after the usual before snapshot and project validation. Read the [multi-object tracking contract](../../docs/specs/本地多目标视觉跟踪与对象选择协议契约_v0.1_2026-10-15.md).
4a. For a music montage, use `media beat-cut --project <path> (--audio-asset-id <id>|--input <local-file>) --source-asset-id <video-id> --track-id <video-track> --dry-run`, review the local energy-anchor plan, then add `--apply`. Existing target overlaps are rejected unless `--replace-track` is explicit. Read the [beat-cut contract](../../docs/specs/本地节拍卡点与混剪时间线契约_v0.1_2026-10-15.md) and preserve `BEAT_NO_ANCHORS`, `BEAT_SOURCE_REUSED`, and `BEAT_SOURCE_SLOWED` warnings.
4b. For automatic captions, use `subtitle transcribe --project <path> (--asset-id <registered-audio-or-video>|--input <local-file>) --model-path <local-model> --dry-run` first. Choose `--transcribe-engine transformers` for a local model directory or `--transcribe-engine ffmpeg-whisper` for a local whisper.cpp model file; inspect `doctor.data.checks.local_features.ffmpeg_whisper_asr` before the native path. Add `--apply --track-id <subtitle-track>` only after review; application requires a registered source asset so the generated subtitle asset inherits Rights Ledger evidence, creates `before-subtitle-transcribe`, validates the project, and records the operation. Preserve `LOCAL_ASR_WHISPER_UNAVAILABLE`, `LOCAL_ASR_WHISPER_FAILED`, `SUBTITLE_APPLY_SOURCE_ASSET_REQUIRED`, and `SUBTITLE_TRANSCRIBE_TRACK_OVERLAP` errors. Read the [local AI and subtitle contract](../../docs/specs/本地AI适配器与字幕流水线规范_v0.1_2026-10-13.md).
4c. To make a text, sticker, or effect layer follow a locally tracked subject, use `media track-bind --project <path> (--asset-id <id>|--input <local-file>) --roi x,y,w,h [--adapter-id <id>] --target-clip-id <clip> --target-track-id <track> --dry-run` first. Review the source/model hashes, confidence frames, target duration mapping, offsets, and `scale-mode`; add `--apply` only after review. `--apply` creates `before-track-bind`, writes `transform.position.x/y` and optional ROI-relative `transform.scale` keyframes, validates the project, and records a report, provenance entry, and operation. Preserve `TRACK_BIND_TARGET_AUDIO`, `TRACK_BIND_NESTED_UNSUPPORTED`, `TRACK_BIND_EMPTY`, and `TRACK_BIND_APPLY_INVALID`; the source-clock normalization and template/external-runner quality warnings are mandatory review evidence. Read the [tracking bind contract](../../docs/specs/本地跟踪绑定与对象锚定契约_v0.1_2026-10-15.md).
5. Run `validate`; the project validator includes the local Agent Project JSON Schema executor when `jsonschema` is installed and reports its engine. For a release or ad publish also run `rights check`, render with `--publish`, and finish with `quality check --require-audio` (add `--expensive` for black-frame/loudness scans). Use `quality scopes --project <path> --input <project-media> --at-seconds <seconds>` when an Agent or reviewer needs local waveform/vectorscope/histogram PNG evidence; read the [scope contract](../../docs/specs/本地色彩Scope审查契约_v0.1_2026-10-14.md) and treat these images as review artifacts rather than automatic color grading. Render may declare `--container mp4|webm|mkv`, local video/audio codecs, CRF or bitrates; preserve the resulting encoder settings in the manifest. For multiple output variants, write a project-local queue JSON and use `queue enqueue`, `queue list/inspect`, then `queue run`; the queue defaults to a sequential local FFmpeg runner, while `queue run --workers N --continue-on-error` enables bounded local concurrency for distinct output paths. Failed/cancelled jobs require explicit `--job-id` retry, duplicate concurrent outputs are rejected, and `queue cancel` uses a project-local marker. Read the [queue contract](../../docs/specs/本地渲染队列与任务状态契约_v0.1_2026-10-14.md) before relying on state transitions.
6. Use `convert import/export` only through its conversion report. Export can target `agent-json`, `package`, `otio`, `kdenlive-xml`, or `jianying-draft-json`. Use `package` for portable projects with copied local assets and a hash manifest. For a readable local draft, import automatically detects `materials/tracks/canvas_config`; export with `--target-format jianying-draft-json` writes a plaintext file, a conversion report, and a redacted source-project sidecar. Add `--strict` only for this draft adapter when every `Approximate/Baked/Unsupported/Failed` must reject the conversion before publishing the target; do not retry a strict rejection without surfacing the loss report. Text layout and Bezier remain approximate, private resources are never downloaded, encrypted drafts are rejected, and imported media/fonts have unverified rights. Video sound becomes an explicit linked audio track; unmodified sound folds back on export, while independent volume/mute edits stay separate to avoid extra mixing. Treat `Failed` and `summary.status=partial` as failure even when a partial project exists. No conversion result proves compatibility with a commercial Jianying version or visual parity. Read the [plaintext draft contract](../../docs/specs/本地明文草稿双向适配器契约_v0.1_2026-10-15.md).
7. Inspect the render manifest and probe the output before reporting success. If the renderer warns that keyframes, effects, transitions, or transforms are preserved but not executed, report that limitation. If a render is cancelled or fails, retain the returned `operation_id`; retry with `render --resume <operation_id>` only after the CLI accepts the unchanged project and asset fingerprints. This is a validated rebuild from the recorded plan, not a partial-frame checkpoint.

Agent calls should consume the JSON envelope and exit code. Keep a project-relative change set in a file so the operation is reviewable and repeatable. Read [the CLI contract](../../docs/specs/AgentCLI契约_v0.1_2026-10-13.md), [the local AI adapter specification](../../docs/specs/本地AI适配器与字幕流水线规范_v0.1_2026-10-13.md), [the object tracking specification](../../docs/specs/本地对象跟踪与关键帧规范_v0.1_2026-10-13.md), [the visual tracking adapter contract](../../docs/specs/本地视觉模型适配器与对象跟踪协议契约_v0.1_2026-10-15.md), [the tracking bind contract](../../docs/specs/本地跟踪绑定与对象锚定契约_v0.1_2026-10-15.md), and [the P0 usage guide](../../docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md) when a request needs exact fields or failure handling.

For explicit local HTML motion, use the [subframe shutter contract](../../docs/specs/HTML子帧快门采样与预乘透明合成契约_v0.1_2026-10-20.md).
`motion html-render --shutter-samples 4 --shutter-fraction 1` redraws each sample;
default samples=1 and fraction=0 retain the original frame path. Declare each
internal cut with `--shutter-cut-tick <source-tick>`; use `--shutter-clear-cuts`
when explicitly replacing an inherited recipe. Samples are 1..16, fraction 0..1;
strict layout includes every subframe and all redraw passes count toward the
work budget. The saved recipe survives package and edited-fragment reuse.
Read the [actual pixels and failures](../../docs/validation/HTML子帧快门与透明混合实测_2026-10-20.md).
This is premultiplied encoded-sRGB 8-bit compositing. It does not add motion
blur to arbitrary source footage or accept HDR, natural-motion quality, hidden
Canvas text layout, undeclared scene cuts or complete CapCut parity.


### Native source audio intervals

Discover `native_audio_source_clock` with `capabilities` before using this path.
The protocol is `native-decoded-audio-interval-clock-v1`. It keeps the original
asset ID, URI, source SHA and authored ranges. Native decoded PTS/sample counts
place hard gaps as silence and let later decoded frames overwrite overlaps.
Continuous sources retain their original input; discontinuous sources use a
hash-bound derived native-rate float PCM cache. Soft async drift compensation
stays disabled. Coarse PTS has per-measurement rounding uncertainty; its already
lost subtick clock jumps cannot be reconstructed. Exact native sample timebases
retain a real one-sample gap.

Apply this source clock before scalar/reverse/curve/nested selection, offline R3
input and multicam envelopes. R3 may use audio EOF silence within verified native
video coverage, and must reject invented handles beyond actual source coverage.
Preserve structured clock/cache errors; do not silently retry with a legacy clock.

Use `cache list --project PROJECT --kind native-audio-clock` and explicit
`cache prune --project PROJECT --kind native-audio-clock`. Inventory is not byte
integrity validation. Registered source assets protect matching cache entries;
do not delete protected files manually or present a cache hit as new inference.
The frame/index/PCM/directory bounds do not prove peak RSS or long-file latency.

See [source clock contract](../../docs/specs/源音频内部时钟与硬缺口缓存_实验_v0.1_2026-10-21.md)
and [actual source/MP4/GIF and failure evidence](../../docs/validation/源音频硬缺口与重叠缓存独立实验_2026-10-21.md).
Synthetic sample equality does not establish natural listening, arbitrary codec
changes, HDR, long-form reliability or full CapCut parity.

Require capability/protocol discovery before requesting this cache kind. Keep an explicit source master audio track; source interval normalization does not infer device drift or editorial camera choices.
