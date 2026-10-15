---
name: video-cut-local-models
description: Run explicitly registered offline models for ASR, SoulX Chinese speech and local visual analysis without downloads, cloud APIs, or hidden network access.
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
  --text "Local voice only" --output assets\tts\voice.wav
```

For Chinese speech, use the dedicated `soulx-podcast-local-v1` integration.
Read the [SoulX contract](../../docs/specs/本地SoulX中文配音与声线登记契约_v0.1_2026-10-15.md)
before registration. `tts adapter register` requires an existing native Python
`.exe`, source/package/model directories, the pinned local speech tokenizer,
and a local evidence file. It hashes full BF16 model components and inference
sources; it never installs packages or downloads weights. Use `--dry-run` first.

Ingest the authorized single-speaker reference as an audio asset, then register
it with `tts voice register --voice-id <id> --asset-id <id> --prompt-input
<exact-UTF8-transcript> --evidence <local-source-and-authorization-file>`.
Preserve the transcript verbatim. Licensing a code repository does not grant
commercial rights to weights, reference voices, text or generated speech.

```powershell
python -X utf8 -m ai_ad_editor tts adapter inspect --project .\work\demo --adapter-id soulx_local
python -X utf8 -m ai_ad_editor tts voice inspect --project .\work\demo --voice-id narrator
python -X utf8 -m ai_ad_editor tts synthesize --project .\work\demo `
  --adapter-id soulx_local --voice-id narrator --text '让创作更加简单。' `
  --asset-id narration_01 --output assets\tts\narration_01.wav `
  --channels 1 --apply --track-id track_audio_1 --dry-run
```

Review both integrity checks before running without `--dry-run`. This engine
requires CUDA/full BF16 weights and uses isolated native Python. It blocks Python
network calls and overrides the tokenizer downloader with the registered file.
There is no CPU/GGUF/online fallback. Retain natural duration and the
`TTS_REVIEW_REQUIRED` warning; check pronunciation, truncation and voice identity.
Every generated WAV becomes an audio asset with model/voice/source rights
dependencies. New outputs default to `unverified/internal` and cannot publish.
Registries live in `extensions.local_tts` and follow project snapshots/restore.

If a local model is missing, report a structured degraded result. Do not
replace it with a hosted service or an automatic package/model download.
