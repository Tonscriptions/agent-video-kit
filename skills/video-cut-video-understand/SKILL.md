---
name: video-cut-video-understand
description: Understand local video and audio with native FFmpeg analysis, optional explicitly registered offline ASR, frame evidence, silence, scene and beat candidates.
---

# Local Video Understanding

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
