---
name: video-cut-local-models
description: Run registered offline speech, transcription, separation, tracking, matting, prompted segmentation, masked repair and joint video window editing with existing local models and native Python.
---

# Local Models

For prompted joint video editing, read the [VACE contract](../../docs/specs/本地VACE联合视频编辑契约_v0.1_2026-10-16.md).
Register an existing complete Wan2.1-VACE-1.3B Diffusers safetensors bundle with
`media adapter register --engine diffusers-wan-vace-local-v1 --device cuda`,
native Python and local evidence. Explicit text weight budgets default to
`--text-gpu-budget-mib 7168 --text-cpu-budget-mib 8192`; the encoder is released
before video generation. This path uses BF16 with declared FP32 stability
modules and FP32 VAE, without runtime installation or model downloads.

Use `media inpaint --asset-id <video> --mask-asset-id <mask> --adapter-id <id>
--derived-asset-id <new-id> --prompt <description-of-result> --window-frames 17
--window-overlap 4 --inference-steps 30 --dry-run`. Preserve prompt text;
token overflow fails without truncation or expansion. Seeds, negative prompt,
guidance, conditioning and prompt token budget are explicit. Repeated
`--scene-cut-frame` uses zero-based frames after source range/CFR conversion.
For controlled sampling, `--flow-shift` accepts finite 0.1..32 (default 3);
`--model-input-scale` accepts 1/2/4 (default 1). Scaling follows the base ROI
limit/padding from `--model-max-edge`, then returns to the original output canvas.
Inspect the scaled owned-array budget and actual window input shapes. This
budget excludes Torch/model/VRAM and cannot guarantee freedom from CUDA OOM.
Larger inputs or more steps require evidence for the chosen footage. LaMa
rejects both options.

Both repair engines accept `--repair-blend harmonic` for explicit spatial
boundary color correction; `direct` remains the default. Read the
[harmonic contract](../../docs/specs/本地修复区域色差融合契约_v0.1_2026-10-16.md)
when using it. Optional `--blend-max-iterations` (1..10000, default 2000) and
`--blend-tolerance` (0..0.01 excluding 0, default 1e-6) require harmonic.
Dry-run cannot know decoded selection size: execution checks the actual
selection budget before each model call. Empty frames bypass weights; a full
canvas selection has no fixed boundary and fails. Nonconvergence also fails,
without silent fallback. Inspect the `blend` report and keep
`REPAIR_HARMONIZE_REVIEW_REQUIRED`; spatial correction does not reconstruct
object geometry or temporal consistency. Re-register adapters whose bound
implementation hashes changed instead of editing their saved digests.

Joint windows and overlap blending do not establish global video attention
or consistent identity. Tail padding is cropped before delivery.

The worker erases selected RGB to 127 before/after resizing. Original alpha and
RGB outside the expanded mask remain exact. Model digest reuse is scoped to
native read handles that deny writes/deletion; each new command verifies again.
Review texture, object traces, window seams and natural motion; keep
`VACE_MODEL_REVIEW_REQUIRED`. Use the same audio/application/rights pipeline
as LaMa below. Array limits exclude model, Torch and total process RAM/VRAM;
real hardware, quality and commercial rights require independent evidence.

For object removal or local region repair, read the
[LaMa contract](../../docs/specs/本地LaMa区域修复与对象移除契约_v0.1_2026-10-16.md).
Register `media adapter register --engine torchscript-lama-local-v1` using an
existing TorchScript `.pt`, native Python, local evidence and explicit CPU/CUDA.
Inspect before `media inpaint --asset-id <source-video> --mask-asset-id
<registered-image-or-video> --adapter-id <id> --derived-asset-id <new-id>
--dry-run`. White/high alpha selects repair; use `--mask-channel luma` for
an opaque black/white mask. SAM2 binary MOV outputs can supply the alpha mask.

Mask time starts at its own display origin plus `--mask-start-seconds`; it
must cover the rounded output duration. Default geometry mismatch is rejected;
`--mask-resize nearest` allows explicit matching-aspect scaling. Review this
clock when source range, frame rate, crop or size has changed. `--mask-grow`,
`--mask-feather`, `--context-pixels` and `--model-max-edge` control region and
context. Empty frames bypass the model. Repair preserves original alpha and
RGB outside the expanded region. ROI resizing and padding are reported.

Formal execution produces a lossless MOV with audio, hashes and source/mask/model
rights dependencies. Apply with video and explicit audio tracks as below.
Preserve `INPAINT_MODEL_REVIEW_REQUIRED`: LaMa runs framewise and can invent
texture, leave traces or flicker. It does not establish temporal reconstruction
or text-prompt generative fill. Compare against independent truth where available.

For a person plus held product, or other selected video objects, read the
[SAM2 prompt contract](../../docs/specs/本地SAM2对象分割与提示修正契约_v0.1_2026-10-16.md).
Register `media adapter register --engine transformers-sam2-video-local-v1`
with an existing complete video safetensors directory, native Python, evidence
and explicit `--device cpu|cuda`. Inspect before execution. Run `media matting
--asset-id <video> --adapter-id <id> --derived-asset-id <new-id> --prompts
<local-json> --dry-run`; points/boxes use normalized output coordinates and
zero-based frames after range/CFR conversion. Choose multiple positive points
or a box when a face click selects only the face. Negative points exclude areas.

Optional repeated `--object-id` selects objects for union. Later-frame prompts
correct future output; `reset` starts a new scene and requires fresh prompts
for active objects. Inspect the canonical prompt hash, device and reset count. Review object extent
at prompt/reset boundaries: the same points can select a smaller part on another
frame. Add a bounding box when scope is ambiguous and inspect the new result.
Default binary masks differ from `--mask-mode probability`: sigmoid logits
are segmentation confidence, not physical transparency or reconstructed hair.
Both modes keep source RGB and multiply existing alpha. The 512 MiB session
tensor limit excludes model/process memory. No runtime download or device fallback.
MOV, audio application, rights and transparent delivery follow the RVM pipeline.

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
