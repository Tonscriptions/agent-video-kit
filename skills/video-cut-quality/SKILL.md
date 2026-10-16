---
name: video-cut-quality
description: Produce local quality reports, color scopes, render manifests, and machine-readable evidence for Agent video delivery.
---

# Local Quality

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
