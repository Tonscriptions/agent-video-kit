---
name: video-cut-template-library
description: Build and apply local advertising templates, or save and reuse edited clip groups across projects, with media indexing, rights and variable validation, and batch rendering.
---

An explicit vector title can start with `motion stroke-source`, followed by
the existing offline `motion html-render` pipeline. Read the
[stroke contract](../../docs/specs/离线逐笔描线动效契约_v0.1_2026-10-18.md)
for plan fields and quotas; `ink_color` is the only runtime parameter.
The source ZIP preserves the authored plan and both MIT notices. Rebuild to
a new asset/version rather than replacing it. The overall source stays
unverified/internal until its authored content rights are separately reviewed.

# Local Templates

For repeatable template text QA, run `motion html-quality` under the
[all-frame layout/font contract](../../docs/specs/HTML文字布局与字体覆盖核验契约_v0.1_2026-10-18.md).
Use `html-render --layout-check strict` to save a mandatory gate in the new
recipe; omitted mode inherits on rebuild and package import. Preserve
[failed/repaired evidence](../../docs/validation/HTML文字布局与字体覆盖实测_2026-10-18.md),
including missing glyphs, fallback, fully outside text and unknown geometry.

For an existing HTML title card, use the [local template controls contract](../../docs/specs/离线HTML模板控件与覆盖恢复契约_v0.1_2026-10-18.md).
`motion html-controls --source-asset-id <id> --frame-index <n>` draws one frame
twice and reports root CSS variables, direct text and images. Preserve CSS
units in `html-render --overrides <local.json>`; image changes reference local
registered asset IDs. From an existing output, omitted changes inherit and
`null` removes only that change. Keep the new recipe, image rights closure,
failure/cleanup reports and [actual rebuild evidence](../../docs/validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md).
A sampled catalog does not establish full animation, typography or layout quality.

For editable browser motion, read the [offline HTML motion contract](../../docs/specs/离线HTML动效与可编辑源码契约_v0.1_2026-10-18.md).
`motion html-source` freezes listed code and registered images/fonts.
`html-render --from-asset-id` rebuilds preserved typed parameters to a new
asset version. Carry source/resource references through packages/fragments;
recipient projects register their own existing local toolchain. The template
does not authorize downloads or upgrade template/media rights.

Edited groups may contain [presentation windows](../../docs/specs/片段输出窗口裁切与波纹编辑契约_v0.1_2026-10-18.md).
Preserve original source ranges, author start/duration and window offsets when
saving or applying; do not normalize them to the visible clip duration. The
native group path preserves these clocks across projects. Keep current context,
rights and supported-operation gates when continuing to edit an inserted group.

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
