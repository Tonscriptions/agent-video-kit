---
name: video-cut-template-library
description: Build and apply versioned local advertising templates with deterministic media indexing, variable validation, and batch rendering.
---

# Local Templates

Index only a local directory and keep each template JSON, media file, font,
LUT and license record under local control:

```powershell
python -X utf8 -m ai_ad_editor library index --root E:\library\ads --output .\work\library.json
python -X utf8 -m ai_ad_editor library search --catalog .\work\library.json --query "hook product"
python -X utf8 -m ai_ad_editor template apply --project .\work\demo --input .\templates\ad.json --variables .\templates\vars.json
```

Use `template batch` for deterministic variants. Validate all variables and
Rights Ledger records before rendering. Do not fetch stock media, fonts,
templates, or remote references during instantiation.
