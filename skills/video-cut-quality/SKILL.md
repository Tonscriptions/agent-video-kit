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
