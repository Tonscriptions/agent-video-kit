---
name: video-cut-timeline
description: Compose an Agent Project timeline with local clips, tracks, transitions, keyframes, masks, speed curves, nested sequences, captions, and audio automation.
---

# Timeline Composition

Use `media matting` with a registered RVM adapter to create a local soft-alpha
human cutout; read the [matting contract](../../docs/specs/本地RVM人物视频抠像与透明素材契约_v0.1_2026-10-16.md).
Its QTRLE/ARGB MOV is an ordinary video asset. Apply it to a video track with
higher `order` than the background. `--audio-track-id` explicitly creates a
matching audio clip; preserved embedded MOV audio alone does not mix itself
into the sequence. Keep both source/model rights dependencies. Final transparent
delivery uses the existing WebM/VPX `yuva420p` output, with a decoder that supports
WebM alpha for visual checks. Review initial-frame defects and held-object loss;
pipeline verification does not establish broad human matting quality.

Native model tracking is described in the [YOLO contract](../../docs/specs/本地YOLO检测与多目标跟踪契约_v0.1_2026-10-15.md).
Review `media track --all-objects` before binding an ID to text or reframing a
direct clip. Preserve the applied clip's `rights_dependencies` entries with
model registration SHA-256; they participate in publish gates. Label binding
without source references uses normalized source coordinates. For current
crop/fit/fill/stretch, transform, mirror and source-time mapping, supply both
`--source-track-id` and `--source-clip-id`; see the [canvas binding contract](../../docs/specs/本地跟踪绑定坐标空间与渲染重算契约_v0.1_2026-10-15.md).
This saves source-clock observations and recompiles them for the render canvas.
Optional `--rotation-mode source` follows layer rotation, not object pose.
Live bindings own their generated transform keys; set `tracking_binding` to null
with update_clip to detach while retaining saved preview keys. Nested parents,
mask/occlusion visibility, VFR and nonlinear warps remain review boundaries. Do not delete
dependencies or warnings to make a project pass a release gate.

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
canvas; `animation.type=rotate` rotates the text layer itself; clip transform/keyframes, masks, blend modes, fade/dissolve alpha transitions, and basic slide/wipe spatial transitions apply to the independent layer. Complex transition handles still need explicit local support. Register local
font assets through `style.font_asset_id` or provide an existing local
`style.fontfile`. Use `word_timing.start_char` when repeated words need an
unambiguous highlight anchor; source text mismatches are rejected before save.
