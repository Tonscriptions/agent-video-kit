---
name: video-cut-reference-remake
description: Rebuild a local reference video's cuts, layout and motion as an editable Agent Project using original replacement assets. Use for reference remakes, style or pacing matches, 复刻 and 做同款.
---

# Local reference remake

Use the existing Agent Video Kit CLI in `product/`. Read the
[workflow contract](../../docs/specs/OpenFilm三套本地创作Skill适配与实片核验契约_v0.1_2026-10-19.md)
and the [local capability mapping](../../docs/OpenFilm创作流程本地适配设计_2026-10-19.md)
when choosing which steps can be automated. The user may want identical content
or only its pacing, structure and motion; preserve their requested degree of
similarity and use supplied original assets.

Keep the local reference under a reference directory. Ingest production material
explicitly; do not insert the reference itself to conceal an incomplete rebuild.
`media understand --beats` and `media prepare --thumbnail --at-seconds` provide
cut, beat and frame evidence. They do not identify every word, camera movement
or semantic scene. Author a table of source/target integer ticks for cuts,
titles, motion extrema and sound hits, with the declared duration mapping.

Build editable clips through `timeline compose`/`timeline edit`, then use
`motion list/inspect/apply` or explicit clip keyframes. Numeric position is
normalized to the output canvas; keep source crop and complete author clocks.
Read the [timeline instructions](../video-cut-timeline/SKILL.md) for transforms,
compound clips and retiming. The motion catalog uses IDs such as `pan_right`;
its ease curve is part of the motion, not an assumed linear interpolation.
Local HTML scenes may supply titles or overlays through `motion html-*`.

Video and its sound require explicit clips on the respective video/audio
tracks; use a shared `link_id` and matching source ranges when they must move
together. A silent preview does not prove the source sound survived. Review the
dry-run, retain the plan, then render and inspect the actual encoded frames and
audio. Use simultaneous reference/result frames and explicit cut/motion errors.
Different content cannot be evaluated by a single full-frame equality score.

Keep original production assets, font notices, editable project and render
evidence. `quality check`, `policy audit` and `rights check` cover technical
and publication gates; they do not prove a convincing remake. State the
remaining visual differences, changed content and any unreviewed playback or
listening. Use existing registered local models when needed; upstream online
generation commands are not a substitute for a missing local capability.

Adapted from OpenFilm's fixed `7a64d1f` replicate workflow. Preserve the
[MIT notice](../../product/src/ai_ad_editor/OPENFILM_LICENSE.txt); assets and
models have their own rights. A controlled card-motion demonstration does not
establish automatic scene understanding or arbitrary frame-for-frame fidelity.
