---
name: video-cut-timeline
description: Compose an Agent Project timeline with local clips, tracks, transitions, keyframes, masks, speed curves, nested sequences, captions, and audio automation.
---

# Timeline Composition

Write a project-relative JSON change set and apply it with:

```powershell
python -X utf8 -m ai_ad_editor timeline compose --project .\work\demo --input .\changes\shot.json
```

Use integer ticks from the project timebase. Prefer explicit clip IDs,
source in/out points, track IDs and keyframe properties. The command creates
a before-mutation snapshot and validates references, time ranges, transitions,
mask geometry and nested sequence cycles before saving. Unsupported or
approximate effects must remain visible in the response and render manifest.

For titles and captions that must exist independently of a source video, add a
`kind=subtitle` track and append a clip with `generator: {"type": "text"}` and
`subtitle.text/style`. The local renderer draws this layer on a transparent
canvas; `animation.type=rotate` rotates the text layer itself; clip transform/keyframes, masks, blend modes, and fade/dissolve alpha transitions apply to the independent layer. Slide/wipe transitions still need explicit spatial-handle support. Register local
font assets through `style.font_asset_id` or provide an existing local
`style.fontfile`. Use `word_timing.start_char` when repeated words need an
unambiguous highlight anchor; source text mismatches are rejected before save.
