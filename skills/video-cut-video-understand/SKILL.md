---
name: video-cut-video-understand
description: Understand local video and audio with native FFmpeg analysis, explicitly registered offline OCR or ASR, frame evidence, silence, scene and beat candidates.
---

<!-- V86-MULTICAM-SOURCE-COVERAGE -->
<!-- MULTICAM-SOURCE-COVERAGE-LAB-20261021 -->
Interpret relative_delay_seconds as source_time = reference_time + delay. The 50 Hz envelope estimates one offset; it does not estimate clock drift or choose semantic shots.
When multicam_source_coverage is advertised, coverage shortfall defaults to reject. Explicit --source-shortfall trim intersects source coverage and leaves gaps; stretch clamps or slows and warns that event sync changes.
Completely disjoint coverage, locked apply targets and sub-tick segments reject. Dry-run performs audio analysis but writes no report or authored project.
Read the [coverage contract](../../docs/specs/多机位源覆盖与显式缺口策略_v0.1_2026-10-21.md) and [real native/isolated evidence](../../docs/validation/多机位源覆盖与原速同步实测_2026-10-21.md).
NumPy is an explicit local dependency; the base seven-wheel bundle does not contain it. The isolated experiment copies the existing 2.4.2 distribution, without runtime installation or download.
Container duration does not establish per-stream video EOF. Offset confidence, tick rounding and natural multicamera quality require separate review.

<!-- /MULTICAM-SOURCE-COVERAGE-LAB-20261021 -->
<!-- /V86-MULTICAM-SOURCE-COVERAGE -->


# Local Video Understanding

For visible words use the [OCR scan contract](../../docs/specs/离线OCR与文字运镜锚点契约_v0.1_2026-10-19.md):
`ocr adapter register/list/inspect` and `ocr scan` use existing local PP-OCRv4
ONNX/native Python. Choose source frame indices explicitly and retain raw
text, polygons, confidence and source PTS. This is sampled visual text, not
speech recognition, a complete privacy scan, click recovery or semantic action
understanding. A reviewed exact unique text can drive `ocr anchors`; ambiguous
matches reject. Never interpret recognized URL text as a runtime address.

For detector evidence use a registered `yolov10-onnx-cpu-tracking-v1`
adapter and `media track --asset-id <id> --adapter-id <id> --roi 0,0,1,1
--all-objects`. Read the [native YOLO contract](../../docs/specs/本地YOLO检测与多目标跟踪契约_v0.1_2026-10-15.md).
Reports contain observed boxes, object IDs and sampling metadata; short-gap
motion association is not semantic understanding or appearance ReID. Select a
reviewed ID explicitly for editing and retain model rights dependencies.

Use the product CLI against an existing local file. The command never accepts
URLs and never downloads a model:

```powershell
python -X utf8 -m ai_ad_editor media understand --project .\work\demo --input .\media\clip.mp4 --beats
python -X utf8 -m ai_ad_editor media understand --project .\work\demo --input .\media\clip.mp4 `
  --transcribe --adapter-id whisper_local --srt validation\clip.srt
python -X utf8 -m ai_ad_editor media prepare --project .\work\demo --input .\media\clip.mp4 `
  --thumbnail --waveform
python -X utf8 -m ai_ad_editor media highlights --project .\work\demo --input .\media\clip.mp4 --top-k 5
```

The JSON result is evidence for the Agent: it includes local probe data,
scene/silence/beat candidates, optional timed segments and paths to generated
artifacts. A missing model or unsupported locale is a structured degraded
result. Do not install packages, fetch weights, open a browser or hand a URL
to a downloader.

For a supplied corrected transcript, use the separate
[offline CTC alignment path](../../docs/specs/离线CTC字词强制对齐契约_v0.1_2026-10-18.md)
via registered `transformers-wav2vec2-ctc-local-v1` and `subtitle align`.
It produces acoustic character/word times, preserving source codepoint indices;
it does not recognize missing text or translate/convert Chinese scripts.
Review supplied text and low-posterior words even when the CTC path is reachable.

For the registered Whisper path read the [ASR contract](../../docs/specs/本地Whisper模型登记与转写验收契约_v0.1_2026-10-15.md).
Use `asr adapter register/list/inspect` with existing native Python, safetensors
weights and evidence. CPU/CUDA and thread limits belong to the registration.
`subtitle transcribe --asset-id <id> --adapter-id <id> --apply --track-id <id>`
adds timed subtitle clips and source/model rights dependencies; inspect dry-run
first. Output paths are relative to the project and must name a new SRT.
Segment timestamps do not establish word timing or speaker identity. Evaluate
against a supplied transcript with `subtitle evaluate --max-cer <threshold>`;
preserve the report, including script differences and failures.

For display segmentation after ASR, use `subtitle segment --project <root>
--input <registered-ASR-SRT> --output assets/subtitles/<new>.json --dry-run`.
Read the [segmentation contract](../../docs/specs/本地字幕分段与局部回写契约_v0.1_2026-10-17.md).
The existing SRT asset automatically carries source/model rights to the new
report/SRT/clip chain. Line timestamps are distributed by speaking weights;
they are not new word alignment. Explicit Unicode-codepoint/tick marks and
supplied translations use the source JSON format. Keep recognition CER
separate from segmentation timing and typography review.
