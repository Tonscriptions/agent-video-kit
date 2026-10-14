---
name: video-cut-quality
description: Produce local quality reports, color scopes, render manifests, and machine-readable evidence for Agent video delivery.
---

# Local Quality

Run structural and media gates after rendering:

```powershell
python -X utf8 -m ai_ad_editor quality check --project .\work\demo --input .\work\demo\renders\ad.mp4 --require-audio --expensive
python -X utf8 -m ai_ad_editor quality scopes --project .\work\demo --input .\work\demo\renders\ad.mp4 --at-seconds 1.25
```

The scope command writes waveform, vectorscope and histogram PNGs plus a
hash-linked JSON report. Treat them as review evidence; they do not invent an
automatic color grade. Preserve the report, render manifest, probe output and
Rights result with the delivery artifact.
