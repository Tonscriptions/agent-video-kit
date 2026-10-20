---
name: video-cut-quality
description: Review local encoded masks, explicit selected/clear checkpoints, color scopes, render manifests, and quality evidence for Agent video delivery.
---

# Local Quality

<!-- V76-HSL -->
For selective HSL review, read the
[encoded-RGB HSL contract](../../docs/specs/八色分区HSL与关键帧契约_v0.1_2026-10-20.md)
and [independent colorsys evidence and performance gap](../../docs/validation/八色分区HSL与离线发行实测_2026-10-20.md).
Check original-hue band weights, gray preservation, exact key-stage input
alpha, kernel hashes, author time and independently decoded RGB/PCM/PTS.
The synthetic four-case RGB maximum is 1/255; it does not establish natural
color quality or proprietary parity. The 1080p single-thread probe needs
21-27 seconds per frame and fails real-time targets. Static PNG review does
not establish continuous playback, listening, HDR or skin-tone acceptance.
<!-- /V76-HSL -->

For [spatial/keying parameter animation](../../docs/specs/空间滤镜与抠像参数关键帧契约_v0.1_2026-10-20.md),
read the [native static-frame oracles, retained failures and installed checks](../../docs/validation/空间滤镜与抠像关键帧实测_2026-10-20.md).
Compare every displayed frame against explicitly evaluated static native options
at the same author time. Blur and geometry can change alpha. RGB color keying
must multiply native key coverage by the alpha entering that key stage, with
8-bit rounding. Test clear, partial and opaque input, static and dynamic keys,
and stacked instances; native colorkey alone overwrites input alpha. Inspect
`colorkey-alpha-coverage` and the independent root compositor budget.
Use a separate source-over reference and lossless media for pixel assertions.
Verify original PCM and encoded PTS independently. Native algorithm agreement,
synthetic images and static contact sheets do not accept natural keying quality,
despill, HDR, continuous playback or full CapCut parity.

For [retimed external blend animation](../../docs/specs/外部混合动画与完整输出变速契约_v0.1_2026-10-20.md),
read the [independent RGB, alpha, PCM and native installation checks](../../docs/validation/外部混合动画变速与静音修复实测_2026-10-20.md).
Compare every displayed frame with independently mapped author parameters and
source frame identities. Check alpha separately and compare the full background
PCM when retiming a silent layer. Generated silence must reach tempo filters
as floating point; native u8 silence can introduce a fixed offset. Isolated
ancestor retimes use the already rasterized child frame order. Preserve all
failed references and original thresholds. Static PNG inspection and synthetic
arithmetic cannot accept continuous playback, listening or natural quality.

For [LUT strength automation](../../docs/specs/LUT强度关键帧契约_v0.1_2026-10-20.md),
read the [independent native pixel checks and failures](../../docs/validation/LUT强度关键帧与中性调色修复实测_2026-10-20.md).
Check a non-gray neutral LUT at static strengths, every decoded frame against
an independent RGB oracle, and exact alpha separately. CFR source timestamps
must match the oracle; millisecond-rounded 12fps Matroska is not the same input
clock as exact NUT. Compare lossless outputs; MP4 and GIF are review previews.
Account for one-code rounding per 8-bit mix stage. Inspect actual source hashes,
author-clock mapping, global native command budgets and corrupt-cache errors.
Static frame inspection cannot accept natural footage, HDR, long-video
performance, continuous motion/audio review or full CapCut color science.

For [native multi-frame contact sheets](../../docs/specs/透明视频多帧联系表与实际时间锚点契约_v0.1_2026-10-20.md),
read the [measured native/installed checks](../../docs/validation/透明视频多帧联系表与Alpha核验实测_2026-10-20.md).
Compare selected PNGs against independently decoded source frames, and compare
each checker/light/dark/alpha panel using its actual PTS and pixel hashes.
Keep request time, packet candidates and decoded time distinct. Preview is
8-bit and sampled; static inspection does not accept HDR, natural skin,
continuous motion, audio listening or full CapCut quality. Never promote
`quality_accepted: false` based on contact-sheet generation alone.

For face edits use the [face contract](../../docs/specs/离线人脸锚点与局部修饰契约_v0.1_2026-10-20.md)
and [video checks and failures](../../docs/validation/离线人脸锚点与局部修饰实测_2026-10-20.md).
Check neutral decoded RGBA, unchanged original alpha, pixels outside the
declared support, every PTS, every original audio stream's PCM and saved-recipe
replay. Review missing-face and cut behavior separately from geometry IDs.
Raw heatmap confidence is not accuracy. Static NASA-photo pans establish a
controlled video contract only; they do not accept natural motion, skin detail,
occlusion, transparent face boundaries, identity or CapCut beauty quality.

For explicit previous generated conditions, read the
[context contract](../../docs/specs/VACE前窗生成上下文与连续输出契约_v0.1_2026-10-20.md)
and [paired execution evidence and open gates](../../docs/validation/VACE前窗生成上下文实测_2026-10-20.md).
Check actual emitted-prefix identities, scene resets, no prefix replacement,
bounded context and controller/model trace equality. Generated conditions are
not truth. Compare none/previous using identical source and sampling; preserve
the existing 30 dB controlled gate and independent temporal error. Prefix
stability, callback tests or precise original pixels cannot accept natural
structure, long-video consistency or full CapCut quality.

For a native pipeline failure, review the
[diagnostic contract](../../docs/specs/本地模型管道诊断与有界留证契约_v0.1_2026-10-20.md)
and bind `diagnostics show` to the returned manifest SHA. A bounded, redacted
worker JSON error may contain the useful reason even when stderr is empty.
`first_failure_roles` records observation, while cleanup exits are separate;
Broken pipe alone cannot identify a model root cause. Keep original errors when
evidence is unavailable. Do not rate background quality from an error package;
use the [actual media and installed evidence](../../docs/validation/本地模型管道诊断与回收前留证实测_2026-10-20.md)
and retain failed quality gates independently of operational tests.

For video outpainting, follow the [canvas extension contract](../../docs/specs/本地视频扩图与原画面保护契约_v0.1_2026-10-19.md).
Compare the lossless MOV's complete original rectangle, including partial alpha,
against the normalized source; check generated alpha, every PTS and full PCM.
Score only the generated region against any independently held controlled truth.
Keep failed quality gates even when protected pixels pass. Inspect geometry and
the packaged recipe. GIF/MP4 previews, protocol workers and one synthetic scene
cannot establish natural background quality or full CapCut equivalence.

For native loader faults retain the Windows worker PID, report ID, exception
module and code alongside the original failed command. A later `pread` delivery
is scoped evidence, not proof of a permanently resolved native root cause.
Validate the six-file/three-component read report independently of GPU admission.

For hardware delivery, use the [hardware verification contract](../../docs/specs/硬件编解码探测与显式回退契约_v0.1_2026-10-19.md).
Read `acceleration` in the manifest and its `renders/diagnostics/acceleration_*` report.
Check forced hardware frames, CPU-equal probe PTS/pixels, NV12/P010 transport versus
actual encoded bit depth, decoded color tags, final frame/sample clocks and every fallback.
Completed command logs are full decoded text; cancellation/timeout tails are partial.
Four matching frames and a 10-bit file do not accept whole-source quality or internal
10-bit compositing precision. Required axes must never silently become CPU.

For [compound holds](../../docs/specs/复合片段定格与完整音画时钟契约_v0.1_2026-10-18.md),
check every source-frame identity, transition blend, held/resumed frame and
stereo sample. Child captions and animation pause; parent animation continues.
Use an unencoded RGBA child reference for complex glyphs, with an independent
hold index and 8-bit opacity formula; a second YUV round trip adds unrelated
error. Preserve the failed encoded reference and the unchanged RGB threshold.
Distinguish lossless native-graph alpha/PCM precision from supported CLI
VP9/WebM delivery. Decode VP9 alpha explicitly with libvpx-vp9; Opus is not a
sample-equality oracle. V51's 10-fps/4.01-second root failed the old MP4 AV
gate at a 90-ms tail difference. That historical failure is retained. Review
[all executed cases and their limits](../../docs/validation/复合片段定格与完整音画时钟实测_2026-10-18.md).

For final transparent delivery, use the
[alpha and stream-end contract](../../docs/specs/透明视频交付与音画端点契约_v0.1_2026-10-18.md).
VP9 CRF=0 without a bitrate override explicitly selects lossless YUV/alpha;
the separate original 8-bit alpha plane avoids color-conversion rounding.
This is not lossless RGB/RGBA. VP8 and nonzero-CRF/bitrate alpha remain lossy.
Tagged VPX inputs select a local libvpx decoder and straight RGBA before
compositing. Check reimported footage over light and dark controls as well
as exact alpha. Keep measured lossy errors visible in
[the real delivery/installed-package record](../../docs/validation/透明视频交付与音画端点实测_2026-10-18.md).
Bind independent quality check/golden capture with --sequence-id when author
duration is known; omitted sequence keeps strict unknown-duration behaviour.
Retain raw stream-duration/start/end deltas, expected CFR/sample quantization
and remaining error. The 80-ms default is unchanged; positive/negative audio
offsets and a common timestamp shift must still fail. Missing stream timing
is unverified, not a container-duration substitute. AAC/Opus decode padding
and same-version repeat equality do not prove original PCM fidelity.

For [boundary-model research](../../docs/specs/字词边界模型对照核验契约_v0.1_2026-10-18.md),
inspect [all signed sample errors and raw Chinese anomalies](../../docs/validation/开源字词边界模型对照实测_2026-10-18.md).
Qwen, the supplied-text Whisper-DTW baseline and new CTC holdout all failed
the unchanged maximum-error gate. Authored trimmed word blocks are not manual
phonetic labels. Keep zero-duration/overlap predictions before any upstream
interpolation. Distinguish three real model workers/six new forwards from
zero-forward import/meta probes and historical V49 results. The two final
charts check 458 frame PTS and 243835 original PCM samples; they are research
measurement visuals. Only two middle screenshots received readability review;
there was no continuous playback or listening. Preserve the unreadable first
font attempt and the separately licensed readable font. During V50 research,
product source remained at V49 and its 1135-method full regression was not rerun.

For [offline CTC word alignment](../../docs/specs/离线CTC字词强制对齐契约_v0.1_2026-10-18.md),
check original codepoint coverage, explicit OOV/script decisions, model/input/
implementation hashes, source sample anchors and every retained convolution
cell across windows. Distinguish actual worker forwards from mock protocol
tests and idempotent replays. Check word-highlight source indices separately
from acoustic boundary errors. Authored word-block intervals are not phonetic
labels; retain a failed predeclared 2/30-second gate without relaxing it.
The English fixture measured a 258.1875 ms maximum error and failed that gate.
The existing renderer mixes 16 kHz input at 48 kHz: check against an explicitly
resampled source and retain the failed direct-rate expectation separately.
Keep [actual runs, original media and failures](../../docs/validation/离线CTC字词强制对齐实测_2026-10-18.md).
High posterior does not validate the supplied transcript; forced wrong text,
singing, overlapping speakers and broad natural quality require independent
review. Never publish private Chinese reference voices based on test success.

Use `doctor` and `schema show` to inspect the bundled validation contract,
under the [offline schema contract](../../docs/specs/离线发行与随包Schema契约_v0.1_2026-10-18.md).
Missing executors/resources and changed schema bytes must fail; semantic
checks alone do not establish Schema acceptance. Inspect the declared
`project.created_at` field and preserve leap-second limits. See the
[release validation evidence](../../docs/validation/离线发行与随包Schema实测_2026-10-18.md)
for independent source frame/PCM checks, actual rollback cases and the
separate static/playback/listening boundaries.
Font/text installers use the seven-wheel `font-text-v1` profile with Pillow;
verify actual font ingestion under the isolated launcher, not host imports.

For [HTML text layout and font coverage](../../docs/specs/HTML文字布局与字体覆盖核验契约_v0.1_2026-10-18.md),
review every CFR frame and the independent reverse redraw. Separate partial
clipping, completely outside text and unsupported geometry. Check actual CDP
fonts against source file hashes and cmap coverage, keeping system fallback,
unknown formats and variation sequences unverified. Use the explicit strict
render gate when required; keep [negative and repaired cases](../../docs/validation/HTML文字布局与字体覆盖实测_2026-10-18.md).
Mapping coverage and DOM rectangles do not prove ink, shaping or aesthetics.

For [HTML template controls](../../docs/specs/离线HTML模板控件与覆盖恢复契约_v0.1_2026-10-18.md),
separate a twice-drawn sample catalog from all-frame encoded evidence. Check
CSS units, literal multiline words, registered replacement image pixels,
new image rights, inherited/null-reset recipes and package/fragment rebuilds.
Missing selectors must fail and reap every browser child. Keep
[actual failures and pixel checks](../../docs/validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md);
neither control discovery nor pixel equality accepts glyph coverage, layout
aesthetics, continuous playback or complete CapCut quality.

For [FGT research](../../docs/specs/开源时序修复候选核验契约_v0.1_2026-10-18.md),
keep [the measured synthetic and natural findings](../../docs/validation/开源FGT时序修复候选实测_2026-10-18.md)
separate. The declared PSNR and known-motion residual gates passed on one
authored two-surface sequence. Independent integer scoring, decoded RGBA,
every PTS and natural PCM were checked. Four static natural frames still
show residue/patches; no hidden-background truth, dense anatomy labels,
continuous playback or listening acceptance exists. The two workers and
their RAFT/LAFC/FGT forward counts are not product CLI calls or regression
methods. This research does not close capability #56 or CapCut parity.

For [encoded mask edits](../../docs/specs/本地蒙版笔刷与关键帧修正契约_v0.1_2026-10-18.md),
check the actual lossless RGBA round trip, every PTS, operation range and
independent authored shape coverage. Unchanged frames preserve decoded alpha;
output RGB is white and carries no audio. Check selected target extremities
and clear preserved objects before and after, then inspect the separately
grown repair mask. A hand-authored correction can satisfy the supplied points
while missing other anatomy. Keep selection, model consumption, texture,
flicker, sound and semantic acceptance as separate conclusions. Rebuild the
embedded plan after a project-package import to verify editability.

For the [coherent reference research contract](../../docs/specs/空间与时序一致参考选择研究契约_v0.1_2026-10-18.md),
keep the [actual failed evaluation](../../docs/validation/空间与时序一致参考选择实测_2026-10-18.md)
separate from product acceptance. The v3 candidate failed four of twelve
overlapping scored regions and made no strict MSE gains on the three new
fixtures. A post-hoc motion-compensated diagnostic cannot replace the declared
gate. Preserve original input, failed candidates, exact-alpha controls and
truth before occlusion; no natural pixels are authorized for publication.
The 41 research checks overlap earlier runs and must not be added to V41's
975 product methods. No continuous-playback or natural-quality acceptance.

For browser motion, read the [offline HTML motion contract](../../docs/specs/离线HTML动效与可编辑源码契约_v0.1_2026-10-18.md).
Require the actual `motion html-render` report: input PNG hashes, two fresh
context orders for every frame, fixed toolchain and native Job cleanup.
Check decoded alpha and timeline composition separately. Equal hashes do not
establish typography, natural quality, HDR, cross browser consistency,
continuous playback or sound review.

For [source edits](../../docs/specs/真实源范围外扩与关联Slip契约_v0.1_2026-10-18.md),
check both physical source bounds and actual decoded frame identities/PCM.
Slip preserves author fields; extension reauthors fades/effects and may
renormalize nested curves. Compare against an explicit new author, not an
unchanged old-output slice. Retain normalization warnings and post-slip
transition-handle failures. Separate CLI worker calls from process startups.

For [professional range edits](../../docs/specs/范围编辑插入覆盖与滚滑剪口契约_v0.1_2026-10-18.md),
compare insertion/overwrite and lift/extract against explicit original ranges,
and roll/slide against the full original left/middle/right authors. Check linked
PCM cut points, moving file cues, unchanged middle-body processing and parent
child buses separately. Use a real animation/caption negative control so an
unapplied fixture cannot pass. Root/track processing is evaluated after edits;
a slice of an old final mix is valid only for the fixture's processing scope.
Inspect short-handle rejection and actual project bytes after failed batches.
Same-product reference equality does not accept its original retiming quality.

Review [output-window cuts](../../docs/specs/片段输出窗口裁切与波纹编辑契约_v0.1_2026-10-18.md)
against the corresponding ranges of the complete original render. Compare RGB
and lossless PCM separately, including held frames/silence, file cue clocks,
nested buses and opaque contain bars over a lower track. Inspect window offset,
author duration, selected display frames/samples and recursive work budget in
sequence-inline-surface evidence. This proves selection of that authored result;
it does not accept the original model, speed audio quality or continuous viewing.

For [real source handles](../../docs/specs/真实源句柄转场与可逆编辑契约_v0.1_2026-10-17.md),
inspect the `source-transition-plan` manifest node and real decoded source
frame identities around the cut. Check window math, unchanged duration,
multi-cut chains, source bounds and removal restoration. Compare PCM against
an independently mixed envelope; AAC/GIF are preview copies. Inspect the
actual black/white dip at the authored cut, including odd frame windows.
Passing a catalog render checks execution, not an independent inside-window
reference for every wipe/slide, natural quality, HDR or listening acceptance.
For [nested transitions](../../docs/specs/嵌套转场合成与作者时钟契约_v0.1_2026-10-18.md),
use high-contrast frame identities to catch one-frame shifts hidden by RGB
rounding tolerances. Check the completed child picture against independent
parent time math; a fixed child renderer is a compatibility reference, not an
independent oracle for each wipe/slide algorithm. Compare original-source PCM
and envelopes on the continuous child clock, keeping raw-sample reversal
distinct from envelope evaluation. Constant/curved atempo and registered R3
duration checks do not prove pitch, phase or listening quality. Preserve
`inline_sequence_path` warnings. The combined surface/projection admission
quota is not a process RSS limit; internal surfaces are not intermediate files.

For [subtitle segmentation](../../docs/specs/本地字幕分段与局部回写契约_v0.1_2026-10-17.md),
check source character coverage, displayed punctuation, line-bound clocks,
shared translation spans, number/unit protection and correction SHA-256.
Distinguish supplied synthetic onsets from actual ASR timestamps and forced
alignment. A reference made with the same renderer verifies text/timing
adaptation; it does not independently accept font rasterization or language
quality. New transcript rights remain unverified until explicitly reviewed.

For [linked edits](../../docs/specs/关联片段与主轨联动规划契约_v0.1_2026-10-17.md),
review common `short_tick`, selected/deleted IDs, locked tracks, long beds,
collision-lane audio processing, source-reference rebinding and accumulated
sequence-file subtitle offsets. Compare actual encoded output with explicit
expected intervals and cue timing. A manual timeline rendered by the same
renderer checks edit semantics, not an independent raster algorithm. Use
lossless PCM for sample checks and treat AAC/GIF as display copies. Upstream
planner comparisons, product tests and real media are separate evidence;
none accepts natural quality, listening or complete Jianying parity by count.

For nested sequences, review the actual isolated composite against the
[sequence canvas contract](../../docs/specs/嵌套序列隔离合成契约_v0.1_2026-10-17.md).
Check overlap opacity, root occlusion order, parent pivot, post-transform mask,
transparent blend coverage, child animation and half-open gaps separately.
`sequence-composite` manifest nodes describe the compiled graph and do not
establish pixel accuracy. Retain old failed outputs and compare all decoded
frames to an independent reference. Fixed 8-bit RGB fixture checks do not
accept HDR, natural quality, group audio, nested freeze or full editor parity.

For [independent sequence rasters](../../docs/specs/独立序列画布与父级投影契约_v0.1_2026-10-17.md),
check native child crop/anchor, parent position/mask, fill-then-rotate visibility,
local glyph layout and multilevel projection. Selected-sequence quality defaults
to its effective canvas; use the actual output profile for a temporary override.
Keep standalone-child glyph projection separate from independent text shaping,
and baseline compatibility controls separate from independent spatial oracles.
Odd internal RGBA does not prove a valid final 4:2:0 or 4:2:2 encode.

For explicit [sequence area sampling](../../docs/specs/序列面积采样与工作栅格预算契约_v0.1_2026-10-17.md),
pass matching `--sequence-sampling` and `--sequence-memory-mib` to quality
check/golden when render used temporary overrides. Keep default-bilinear
compatibility separate from an independent source-cell area reference. Inspect
high-frequency means, fractional crop and soft alpha. Source-axis box checks
do not accept exact rotated footprints, linear-light/HDR or leaf resampling.
The projection quota is not a measured or guaranteed process RSS ceiling.

Before inpainting or accepting segmentation, review the actual encoded mask:

```powershell
python -X utf8 -m ai_ad_editor quality mask --project .\work\demo --asset-id selected_mask --channel alpha --expectations .\work\demo\validation\mask-expectations.json --report validation/mask-review.json
```

Follow the [mask review contract](../../docs/specs/本地蒙版逐帧核验与检查点契约_v0.1_2026-10-16.md)
for the strict local JSON format. Add `selected` points on the target's limbs
and `clear` points on nearby objects that must remain. Check zero-based output
frames and normalized output coordinates against the actual mask clock. The
default threshold selects values strictly above 127. Opaque black/white masks
need explicit `--channel luma`; static images are one frame and reject `--fps`.
Inspect per-frame area, half-open extent and explicit scene boundaries. Raw
neighboring-frame IoU has no motion compensation; area/edge flags request review.
`--budget-mib` bounds decoded gray storage, excluding total RAM and FFmpeg.

Exit 2 preserves a failed checkpoint report. Keep it when a model correction
still misses the target; do not weaken assertions to produce a pass. Without
expectations, a successful structural report has `expectations_checked=false`.
Even all checkpoints passing leaves `semantic_quality_accepted=false`. This
command reviews the supplied asset; it does not apply inpainting mask growth,
infer object identity, prove full extent, or accept reconstruction quality.

For mask-driven tracking, supply `--mask-expectations` to the tracking/binding/
reframe command when those checks should gate the edit; a prior standalone
review is not an implicit gate. See the [mask tracking contract](../../docs/specs/本地分割蒙版轨迹与锚定契约_v0.1_2026-10-16.md).
Check the encoded bbox clock and final rendered label separately. Inspect
transparent-label padding as well as its position: a center metric can pass
while an opaque border damages the composition. Keep an exceeded pixel
threshold and failed semantic checks visible, even when project/render succeeds.

For transparent resampling, compare identical alpha/visible RGB with different
hidden RGB, and white layers over white with authored dark styles disabled.
Use a dark-background positive control to prove the layer is present. Ordinary
scale, affine sampling and alpha dynamic crop use float premultiplied RGB;
fixed-raster inline/independent text paints separate coverage/color components
and already produces straight alpha. External subtitle files retain their
separate native raster path. See the
[alpha contract](../../docs/specs/透明素材重采样与文字Alpha契约_v0.2_2026-10-16.md).
Inspect final encoded edges and label centers separately. Other effect warps,
linear-light color, performance and segmentation keep separate review gates.

For joint masked video editing, review the [VACE contract](../../docs/specs/本地VACE联合视频编辑契约_v0.1_2026-10-16.md).
Check the exact window plan/hash, scene boundaries, tail padding, seed sequence,
overlap frame count, `conditioning=masked-rgb-127-before-and-after-resize`,
untruncated token counts and text encoder release before generation. Inspect
parent/worker `artifact_verification`: complete byte hashes are reused only
while native read locks deny writes/deletion. Counters describe verification,
not model reconstruction quality or a cross-command checksum cache.

Check requested `flow_shift` and `model_input_scale` against model execution,
and actual `window_input_shapes` against model-call count and peak raster.
The input multiplier follows base ROI padding, scales model area quadratically,
and leaves output geometry fixed. Compare the scaled array estimate separately
from CUDA peaks and total process memory. A higher multiplier or step count
is a sampling choice whose reconstruction quality needs evidence.

For `--repair-blend harmonic`, inspect `metrics.blend`: nonempty frame count,
selected-pixel bound, iteration limits, finite residual/target ratio <=1,
clipping, correction magnitude, elapsed time and the at-most-16 samples.
Check `base_state_peak_bytes` separately from solver-owned arrays; their
combined estimate excludes model/Torch/total RAM and VRAM. The source RGB
inside the mask does not enter correction; optional final feathering can
still mix it back. Compare against matching direct settings, preserve the
true mask denominator, and review generated structure, texture and temporal
seams independently of a reduced color bias. See the
[harmonic contract](../../docs/specs/本地修复区域色差融合契约_v0.1_2026-10-16.md).

Compare all decoded frames for original alpha and outside-mask RGB. For
controlled truth, report masked error using the exact expanded mask, context
and inference settings. Different mask growth changes the score denominator.
Review first/last frames and both sides of every overlap/cut; e.g. 32 frames
with a 17/4 plan overlap at 13–16 and 26–29. Sampled-frame inspection does not
establish continuous temporal quality. Retain seams, color bias, texture,
residual objects, generated-content and commercial-rights limitations.

For masked video repair, review the [LaMa contract](../../docs/specs/本地LaMa区域修复与对象移除契约_v0.1_2026-10-16.md).
Check `outside_mask_changed_pixels=0`, matching input/output alpha hashes and
exact decoded MOV RGBA. Independently compare source/output pixels using the
same display/range/CFR clock and expanded mask. Empty-mask frames must pass
unchanged. These checks prove preservation, not repaired-background accuracy.
When a known unoccluded reference exists, measure masked reconstruction error
and consecutive error changes; retain the fixture scope. Review texture seams,
remaining object edges, movement, occlusion and flicker in natural footage.
Keep model/source/mask rights gating separate from render-quality success.

For nested speed curves, use a source video with encoded frame identities and
an independently authored clock oracle. Compare every output frame, including
fractional curve-segment cuts and reverse combinations. See the
[nested time contract](../../docs/specs/嵌套序列解析时间映射契约_v0.1_2026-10-16.md).
The current fixture gate is <=1 CFR source frame; it does not accept arbitrary
VFR timestamps. Measure keyframe geometry in its original child clock, and
audio pulse timing separately. Pulse-envelope checks exclude explicit boundary
neighborhoods and do not establish seamless phase, lip sync or listening quality.

For [nested frame endpoint coverage](../../docs/specs/嵌套视频帧区间与结束时钟契约_v0.1_2026-10-17.md),
grade every final sample against the authored half-open visible interval,
including both leading and trailing gaps. Visibility allows zero mismatches;
the separate source identity gate remains <=1 registered CFR frame. Include
partial source frames, very short trims, one-tick offsets, fractional source
and output rates, and two trimmed reverse ancestors. Check actual EOF traces
and frame_sampling metadata, not just a correct total MP4 frame count. Retain
the original V24 failed tail when publishing a V25 recheck. Variant PCM equality
accepts preservation only; it does not prove seamless audio or listening quality.

For [speed easing](../../docs/specs/速度曲线Easing与Bezier契约_v0.1_2026-10-16.md),
compare independently integrated authored curves, encoded source frames and
original keyframe geometry. Read the raw and normalized clock error bounds
separately; 250 us applies before duration normalization and outer composition.
Do not count a certificate alone as proof of final encoded timing or audio quality.

For [nested captions](../../docs/specs/嵌套字幕与文字动画时钟契约_v0.1_2026-10-16.md),
check encoded active words, typing prefixes, opacity and rotation against an
independent original authoring clock. Include reverse half-open boundaries,
trim offsets and final visibility windows. Check source-frame identity and
external SRT/ASS time base separately from cue pixels; specify a local font.
Calibrate encoded opacity against actual blank and opaque CLI controls;
coverage-weighted moments avoid a sparse threshold bias on fading glyphs.
Keep raw failed checks. Freeze intervals, dynamic-raster inline color alpha, VFR,
continuous playback and listening still require separate acceptance.

For [word colors](../../docs/specs/逐字高亮原生排版与颜色选择契约_v0.1_2026-10-16.md),
compare the encoded full paragraph with an actual untimed CLI control. White
and yellow preserve R/G: lossless 4:4:4 controls can detect shifted/repainted
glyphs within a 3-level RGB/YUV round-trip allowance. Check word identity and
time separately through the blue-channel change, including repeated words,
line breaks and centered text. Same-color activation must not thicken glyphs;
an active transparent color must replace, rather than cover, opaque base text.
Inspect text_layout engine/font fingerprints in the manifest. Native metrics
do not accept general shaping, automatic wrapping, dynamic-raster color alpha or a
suppressed dynamic-raster highlight. Preserve explicit rejection/warnings.

For [text color/opacity](../../docs/specs/文字颜色透明度与独立覆盖率契约_v0.1_2026-10-16.md),
measure the actual blank and opaque component controls and apply independent
source-over truth. A native semi-transparent drawtext output is not a color
truth control. Check solid colors, antialiasing coverage and box/shadow/border/
fill overlaps, then color alpha times fade/layer opacity. Inspect encoded RGB
over dark and light backgrounds; the current public fixture gate is 6 levels,
including the opaque-control and RGB/YUV quantization. Check decoded audio
invariance separately. Retain old failed outputs and raw color/alpha evidence;
do not infer linear-light/HDR, ASS, very low-alpha precision or broad typography
quality from this controlled encoded-RGB acceptance.

For [animation/highlight composition and typing](../../docs/specs/文字动画高亮组合与原生打字机契约_v0.1_2026-10-17.md),
compare actual untimed animated controls with white/yellow R/G geometry, then
grade word identity separately. Check revealed prefixes against independently
authored native prefix runs and a full-paragraph control: center, kerning,
multiline baselines, wrapping, whitespace delays, one box, border/shadow updates,
literal command delimiters, reverse/Bezier clocks and fractional CFR. Inspect
every actual component target and `text_layout.typing` state/command-file hashes.
Recheck earlier command-file hashes after planning later controls/variants;
correct existing pixels alone cannot establish deterministic replay integrity.
Long filter instance names can lose native commands while FFmpeg still exits 0;
encoded glyph checks are required. Retain old CLI and development failures with
their frozen sources; separate full-suite, subset and media counts. A declared
leading timeline gap may be black; preserve the black gate's failure and grade
the exact authored interval explicitly, without treating all black frames as OK.
R/G geometry does not accept arbitrary color combinations or general shaping.

Run structural and media gates after rendering:

```powershell
python -X utf8 -m ai_ad_editor quality check --project .\work\demo --input .\work\demo\renders\ad.mp4 --require-audio --expensive
python -X utf8 -m ai_ad_editor quality scopes --project .\work\demo --input .\work\demo\renders\ad.mp4 --at-seconds 1.25
python -X utf8 -m ai_ad_editor quality golden --project .\work\demo --input .\work\demo\renders\ad.mp4 --mode capture --require-audio --expensive
python -X utf8 -m ai_ad_editor quality golden --project .\work\demo --input .\work\demo\renders\ad.mp4 --mode verify --require-audio --expensive
```

The scope command writes waveform, vectorscope and histogram PNGs plus a
hash-linked JSON report. Treat them as review evidence; they do not invent an
automatic color grade. Preserve the report, render manifest, probe output and
Rights result with the delivery artifact.

Use `quality golden --mode capture` only after the same quality gate passes. It
writes a project-local `validation/golden-quality.json` containing the local
media hash, settings hash, quality constraints and stable metrics. Re-run
`--mode verify` with the same local settings to detect hash, settings or metric
drift. The manifest proves reproducibility for the captured local FFmpeg build;
it does not prove cross-device visual equivalence or replace manual subtitle
review.

For speech/caption accuracy use `subtitle evaluate --project <path> --input
assets/subtitles/speech.srt --reference validation/reference.txt --report
validation/speech-cer.json --max-cer 0.1`. Choose a task-appropriate threshold;
0.1 is an example. The default NFKC/text normalization removes punctuation and
spacing but never converts Chinese scripts. `--normalization raw` compares decoded
characters directly. A failed threshold returns code 6 and preserves its report.
CER checks transcript text; review subtitle boundaries, script preference and
pronunciation separately. See the [ASR evaluation contract](../../docs/specs/本地Whisper模型登记与转写验收契约_v0.1_2026-10-15.md).


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

For opt-in [real source context](../../docs/specs/离线音频真实源上下文与精确选区契约_v0.1_2026-10-19.md),
compare exact decoded float32 selected samples with a fresh extended-window R3
run, then evaluate pitch and phase separately. Record requested milliseconds,
actual head/tail, edge slopes and output crop. Default 0 stays explicit. The
selected 64 ms apart controls can pass pitch while antiphase still fails;
together can preserve cancellation while missing the right-channel pitch gate.
Do not accept natural quality or listening from synthetic tones or silent GIFs.

For [R3 channel-mode evidence](../../docs/specs/R3声道策略契约_v0.1_2026-10-17.md),
inspect both actual decoded channels. Keep sample-count/presence, known-source
pitch, phase/mono mixing and listening gates separate. Use float PCM for exact
antiphase `max(abs(L+R))` and silent-channel checks; AAC is a listening delivery,
not a bit-exact phase oracle. Apart may separate dominant bands while still
failing pitch and mono compatibility. Preserve these failures and the explicit
`stereo_phase_accepted: false` boundary; do not infer acceptance from automatic
quality CLI success. Link original WAV/video, both actual modes, GIF and hashes
from the numbered README verification row.

For [hierarchical audio buses](../../docs/specs/分层音频总线与采样包络契约_v0.1_2026-10-17.md),
decode lossless float32 MKV and compare every stereo sample with an independently
authored sum/envelope. Test group/track compression against an independently
pre-summed PCM input to native FFmpeg; that proves processing placement, not the
compressor algorithm or perceptual quality. AAC previews are lossy playback
artifacts and must not serve as sample-equality references.

Check additive mixing, silent extra inputs, nested gain, sample fades, one-tick
placement, local solo, audio-only mute, effect tails and multiple detector
branches. Recheck old/new video pixels when changing audio. Inspect manifest
sample windows and `automatic_limiter: false`; super-unit float peaks require
their own delivery/headroom decision. The root sample count uses the declared
duration convention; a correct container length alone proves no content timing.

Keep nonlinear retimer quality separate from the gain clock: compare an
enveloped output with the same retimed plain control times an independent
inverse-clock envelope. Retain old DC amplitude/literal-silence failures and
recheck the current plain control independently. The old R3 ultra-short pitch and apart antiphase failures also
remain open. Publish original WAV/video, old/new lossless files, reference WAV,
actual decoded waveform GIF, complete sample metrics, hashes and raw failures
in the numbered README row; static waveform inspection does not establish
continuous playback, natural-audio quality or listening acceptance.

For [default tempo context](../../docs/specs/分段音频变速上下文契约_v0.1_2026-10-17.md),
compare fixed old/new lossless PCM. Record interior and full active-interval DC
error and literal zero runs separately. Source-context boundaries must stay
inside the selected 48-kHz buffer; loud content outside a cropped parent must
not become warm-up content. Also verify authored silence, silent channels,
exact antiphase cancellation and unity samples. These are distinct controls,
not a general pitch or perceptual gate. Keep development slow/cropped-tail
padding failures visible and verify the current end selection against the
complete authored interval, terminal source marker and trailing silence.
Validate the estimated buffer rejection separately from media/quality runs.
Preserve actual old,
new and original audio, a decoded waveform preview, and the failed tail image
in the numbered README row.

For [HTML subframe shutter checks](../../docs/specs/HTML子帧快门采样与预乘透明合成契约_v0.1_2026-10-20.md),
inspect intended rational times, actual binary64 times, explicit cut segments,
all three fresh-context sample hashes and the original output CFR PTS. Compare
whole decoded RGBA with an independent premultiplied integer reference; opaque
checkerboard MP4s and quantized GIFs are previews. Strict DOM layout must inspect
every actual shutter sample in two fresh orders. Preserve Canvas semantic-text
unverified status. Confirm cancellation after a real encoded frame and owned
process cleanup. The [actual failures and installation proof](../../docs/validation/HTML子帧快门与透明混合实测_2026-10-20.md)
remain separate from natural-motion review, continuous playback and HDR/linear
light quality. Never infer those outcomes from deterministic synthetic pixels.
