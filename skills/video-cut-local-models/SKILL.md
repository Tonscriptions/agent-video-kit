---
name: video-cut-local-models
description: Run registered offline Whisper transcription, SoulX speech, HDemucs vocal separation, YOLO tracking and RVM human video matting with existing local models and native Python.
---

# Local Models

For human video cutouts, read the [native RVM contract](../../docs/specs/本地RVM人物视频抠像与透明素材契约_v0.1_2026-10-16.md).
Register `media adapter register --engine rvm-onnx-cpu-matting-v1` with
an existing self-contained FP32 `.onnx`, native `--executable <Python.exe>`
and local `--evidence`. numpy/onnx/onnxruntime must already exist in that Python.
Registration records six artifact hashes, CPU threads and an optional
`--downsample-ratio`; it never loads or downloads weights. Inspect integrity,
ingest the video and use `media matting --asset-id <source> --adapter-id <id>
--derived-asset-id <new-id> --max-edge 1280 --dry-run`. The default output is
`assets/derived/<new-id>.mov`, lossless QTRLE/ARGB with soft straight alpha.
The worker recycles four states per frame and multiplies existing input alpha.
Encoded RGBA must decode to the exact worker byte hash before registration.

Optional `--apply --track-id <video-track>` applies the cutout; add
`--audio-track-id <audio-track>` to hear preserved audio in the timeline.
Without that flag audio remains embedded in the MOV and is not auto-mixed.
Use higher video track order for foreground and lower order for a background.
Range, rational `--fps`, `--max-edge`, `--max-frames`, timeout and cancellation
are explicit; CFR resampling and partial final-frame extension are reported.
HDR must first be explicitly tone mapped. Keep `MATTING_MODEL_REVIEW_REQUIRED`:
this human model can lose held objects, edges and initial-frame detail; it is
not general-object segmentation. Model/source rights both gate publication.
Weights and native Python remain external to project packages.

For model-backed vocal/accompaniment separation, read the [native HDemucs contract](../../docs/specs/本地HDemucs人声伴奏分离契约_v0.1_2026-10-16.md).
Register `audio adapter register --engine torchaudio-hdemucs-local-v1` with
an existing compatible `.pt/.pth` state dictionary, `--executable <Python.exe>`,
local `--evidence`, and explicit `--device cpu` or `cuda`. Torch/TorchAudio/numpy
must already exist in that Python. Inspect integrity, then use `audio separate
--asset-id <source> --adapter-id <id> --vocals-asset-id <new-id>
--accompaniment-asset-id <new-id> --dry-run`. Optional `--apply --track-id
<audio-track> --stem vocals|accompaniment` selects one output for the timeline.
The model runs at 44.1 kHz stereo; segmented overlap/add preserves all samples.
Accompaniment is input minus predicted vocals. Float WAV peaks can exceed 1;
retain the model-review warning and check leakage, seams and listening quality.
Both stem rights depend on source and model. The legacy `demucs-local-v1`
metadata engine is separate and remains unavailable for inference.

For native object detection and tracking, read the [YOLO contract](../../docs/specs/本地YOLO检测与多目标跟踪契约_v0.1_2026-10-15.md).
Register `media adapter register --engine yolov10-onnx-cpu-tracking-v1`
with an existing self-contained COCO-80 YOLOv10 ONNX, native Python `.exe`
and local `--evidence`. The Python must already contain numpy/Pillow/onnx/
onnxruntime. Explicit CPU settings, model/Python/evidence/implementation hashes
and class filters belong to the registration; there is no install or GPU fallback.
Inspect the adapter, then use `media track --adapter-id <id> --roi 0,0,1,1
--all-objects` to review IDs before selecting `--object-id` for editing.
Native tracking uses motion/IoU association without appearance ReID. Preserve
missing-observation, resampled-clock and identity-review warnings. Applying
requires `--asset-id` and retains model rights on the target clip. Registration
metadata is restored/packaged; external weights and Python remain explicit inputs.

For labels on an edited source clip, pass `--source-track-id` and
`--source-clip-id` to `media track-bind`. The saved source-clock observations
are projected through crop, layer transforms, mirror and source-time changes
again at render time; inference is not rerun. Read the [canvas binding contract](../../docs/specs/本地跟踪绑定坐标空间与渲染重算契约_v0.1_2026-10-15.md).
Plaintext/OTIO/MLT export bakes this relationship and must report the loss.

Models are inputs, never dependencies that the CLI fetches. Put a model in a
project or approved local model directory, record its version, SHA-256 and
license in the project provenance/Rights Ledger, then pass the absolute path.

For reproducible Whisper transcription, read the [registered ASR contract](../../docs/specs/本地Whisper模型登记与转写验收契约_v0.1_2026-10-15.md).
Register an existing complete safetensors model, native Python and local evidence
with `asr adapter register --device cpu --threads 4 --dry-run`. Register formally
after reviewing the plan; use `asr adapter inspect` to check integrity. An isolated
Python must already contain Torch/Transformers; registration does not install them.
CUDA is an explicit registration choice and has no automatic CPU fallback.

```powershell
python -X utf8 -m ai_ad_editor media understand --project .\work\demo `
  --input .\media\clip.mp4 --transcribe --adapter-id whisper_local
python -X utf8 -m ai_ad_editor subtitle transcribe --project .\work\demo `
  --asset-id source_audio --adapter-id whisper_local --language zh `
  --output assets\subtitles\speech.srt --track-id captions --apply --dry-run
```

Registered inference verifies model/Python/evidence hashes, blocks Python network
calls and preserves long-form input. Keep the segment timing and review warning;
this is not word alignment or diarization. Generated subtitle rights depend on
both source and registered model. The legacy `--model-path` gate remains available
but does not acquire the registered worker's integrity/isolation guarantees.
Use `subtitle evaluate` against an independent transcript for CER evidence;
default normalization preserves simplified/traditional script differences.

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
