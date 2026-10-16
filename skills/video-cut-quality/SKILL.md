---
name: video-cut-quality
description: Review local encoded masks, explicit selected/clear checkpoints, color scopes, render manifests, and quality evidence for Agent video delivery.
---

# Local Quality

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
