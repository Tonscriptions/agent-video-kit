---
name: video-cut-video-understand
description: Understand local video and audio with native FFmpeg analysis, optional explicitly registered offline ASR, frame evidence, silence, scene and beat candidates.
---

# Local Video Understanding

Use the product CLI against an existing local file. The command never accepts
URLs and never downloads a model:

```powershell
python -X utf8 -m ai_ad_editor media understand --project .\work\demo --input .\media\clip.mp4 --beats
python -X utf8 -m ai_ad_editor media understand --project .\work\demo --input .\media\clip.mp4 `
  --transcribe --model-path E:\models\asr-local --srt validation\clip.srt
python -X utf8 -m ai_ad_editor media prepare --project .\work\demo --input .\media\clip.mp4 `
  --thumbnail --waveform
python -X utf8 -m ai_ad_editor media highlights --project .\work\demo --input .\media\clip.mp4 --top-k 5
```

The JSON result is evidence for the Agent: it includes local probe data,
scene/silence/beat candidates, optional timed segments and paths to generated
artifacts. A missing model or unsupported locale is a structured degraded
result. Do not install packages, fetch weights, open a browser or hand a URL
to a downloader.
