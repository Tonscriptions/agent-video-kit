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
independent text first converts the drawn raster to straight alpha. See the
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
