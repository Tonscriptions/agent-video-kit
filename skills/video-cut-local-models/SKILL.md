---
name: video-cut-local-models
description: Run explicitly registered offline models for ASR and future local visual analysis without downloads, cloud APIs, or hidden network access.
---

# Local Models

Models are inputs, never dependencies that the CLI fetches. Put a model in a
project or approved local model directory, record its version, SHA-256 and
license in the project provenance/Rights Ledger, then pass the absolute path.

For transcription use the local gate:

```powershell
python -X utf8 -m ai_ad_editor media understand --project .\work\demo `
  --input .\media\clip.mp4 --transcribe --model-path E:\models\whisper-local
```

For the baseline English voice, use the native FFmpeg `flite` adapter:

```powershell
python -X utf8 -m ai_ad_editor tts synthesize --project .\work\demo `
  --text "Local voice only" --output .\work\demo\assets\voice.wav
```

If a local model is missing, report a structured degraded result. Do not
replace it with a hosted service or an automatic package/model download.
