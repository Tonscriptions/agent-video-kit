---
name: video-cut-quality
description: Produce local quality reports, color scopes, render manifests, and machine-readable evidence for Agent video delivery.
---

# Local Quality

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
