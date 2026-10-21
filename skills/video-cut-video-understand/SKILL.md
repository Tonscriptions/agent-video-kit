---
name: video-cut-video-understand
description: Understand local video and audio with native FFmpeg analysis, explicitly registered offline OCR or ASR, frame evidence, silence, scene and beat candidates.
---

<!-- V89-OFFLINE-MEDIA-PROFILE -->
<!-- OFFLINE-MEDIA-PROFILE-LAB-20261021 -->
Multicam analysis can use NumPy from the actual offline bundle. Development-time source acquisition, offline build/install, model registration and media inference are separate steps; analysis must not download missing dependencies or model weights.
Read the [offline media profile contract](../../docs/specs/离线媒体运行时与NumPy交付_v0.1_2026-10-21.md) and [fresh native/installed evidence](../../docs/validation/八轮离线媒体运行时实测_2026-10-21.md).
The official pinned NumPy2.4.2 cp313 Windows x64 wheel and original notices are verified locally. The fresh eight-wheel install does not copy host NumPy and does not create a virtual environment, download at runtime or change global site-packages. Existing native Python/pip and FFmpeg are prerequisites.
Older core-v1/font-text-v1 bundles remain accepted only for products whose declared dependencies fit those profiles. Current products declaring NumPy require media-analysis-v1. Missing or changed sources must fail before building the product wheel.
This acceptance covers the stated pinned platform and synthetic media. A general dependency resolver, other ABIs, full model distribution, natural/HDR/long-form/RSS/playback/listening and complete CapCut parity are separate acceptance work.

<!-- /OFFLINE-MEDIA-PROFILE-LAB-20261021 -->
<!-- /V89-OFFLINE-MEDIA-PROFILE -->


<!-- V88-NATIVE-AUDIO-SOURCE-ORIGIN -->
<!-- NATIVE-AUDIO-SOURCE-ORIGIN-LAB-20261021 -->
For multicam 0.4.0, source_time = reference_time + relative_delay_seconds includes the native audio start. The score uses overlap Pearson correlation without the unmatched first-difference boundary; it is not a probability, drift estimate or semantic shot decision.
The native PCM acceptance uses demux-relative input timestamps with aresample first_pts=0 before source selection. Async clock-drift correction is disabled. Zero-origin audio and equal nonzero container/audio origins must not gain false silence.
Read the [source audio clock contract](../../docs/specs/原生音频起点与作者采样时钟_v0.1_2026-10-21.md) and [actual native/isolated evidence](../../docs/validation/原生音频起点与同步实测_2026-10-21.md).
The real two-case sample covers container origins 0/5 seconds and audio starts 1/6 seconds, each a one-second relative gap. Source-normalized audio and offset-applied camera cuts are checked separately. R3 input/output frame and silence controls do not establish listening, pitch or stereo-phase quality.
Compressed-codec priming, negative timestamps/edit lists, internal timestamp discontinuities, device drift, natural recordings, long-form/RSS, continuous playback and listening still need acceptance.
The current media-analysis-v1 profile ships eight pinned offline wheels, including NumPy 2.4.2. Earlier font-text-v1 experiments used an explicit local NumPy copy; those historical receipts do not establish the current profile. Verify the current bundle manifest, native-operation audit and module origins before use.

<!-- /NATIVE-AUDIO-SOURCE-ORIGIN-LAB-20261021 -->
<!-- /V88-NATIVE-AUDIO-SOURCE-ORIGIN -->


<!-- V87-MULTICAM-NATIVE-STREAM-COVERAGE -->
<!-- MULTICAM-NATIVE-STREAM-COVERAGE-LAB-20261021 -->
Audio-offset analysis and native-video coverage are separate. Audio-only analysis may return valid delays with unknown video-coverage diagnostics; authoring a switch to that camera must refuse unknown coverage.
Native coverage uses first PTS, last PTS plus known duration, native time_base and the renderer's demux-origin rounding; retain the exact rational boundaries from the report. Container duration alone cannot establish video coverage.
Default shortfall policy rejects. Explicit trim leaves gaps at original reference positions; stretch clamps to the real first native frame, changes event timing and must retain its warning. Completely disjoint coverage rejects under every policy.
Dry-run reads existing verified native indices without writing caches, reports, snapshots or authored files. A hit reports zero source-frame probes but still reads hashes. Corrupt indices or changed source SHA reject; do not silently repair them or convert integrity errors into successful audio-only analysis.
Read the [native coverage contract](../../docs/specs/多机位原生帧覆盖与只读索引契约_v0.1_2026-10-21.md) and [fresh native/isolated evidence](../../docs/validation/多机位原生视频覆盖实测_2026-10-21.md).
The base seven-wheel installer does not ship NumPy. This experiment explicitly copies the existing local NumPy 2.4.2 distribution with RECORD hashes and licenses; it is not automatic dependency installation.
Unknown-EOF audio-analysis controls include simulated video state. Native PCM source-leading gaps and nonzero container origins use the separately advertised source_audio_clock contract. Compressed priming/edit lists, clock drift, natural multicamera quality, HDR, long-form/RSS, continuous playback and listening remain separate acceptance work.

<!-- /MULTICAM-NATIVE-STREAM-COVERAGE-LAB-20261021 -->
<!-- /V87-MULTICAM-NATIVE-STREAM-COVERAGE -->


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
