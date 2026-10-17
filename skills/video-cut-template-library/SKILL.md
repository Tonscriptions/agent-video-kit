---
name: video-cut-template-library
description: Build and apply local advertising templates, or save and reuse edited clip groups across projects, with media indexing, rights and variable validation, and batch rendering.
---

# Local Templates

To reuse an already edited intro, CTA or caption group, use the
[local fragment library](../../docs/specs/可复用片段组库与跨项目插入契约_v0.1_2026-10-18.md).
`fragment save` takes an immutable ID/version and an optional clip selection;
`fragment list --query` searches names/tags, and `inspect` hashes resources.
`fragment apply --dry-run` plans an independently editable nested instance.
Review expanded linked clips, native canvas, LUT/font/caption closure and
rights. Versions do not auto-update existing instances or transfer new rights
from their source. This is edited-content reuse; use JSON template variables
and batch commands below when parameterized variants are required.

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
