---
name: video-cut-screen-demo
description: Edit a local screen recording into a product demo with explicit action anchors, editable zooms, clear results, captions and honest timing. Use for 录屏演示, 产品教程 and 操作视频.
---

# Local screen demo

Use actual recorded product actions and results with the
[workflow contract](../../docs/specs/OpenFilm三套本地创作Skill适配与实片核验契约_v0.1_2026-10-19.md).
Work from the supplied local recording and its intended viewer/task. Existing
recordings are sufficient; do not silently substitute a redrawn interface or
an output that the real product did not produce. A controlled test page must
be described as a test page.

Inspect source frames with `media prepare --thumbnail --at-seconds` and locate
the action and resulting state. Keep an action table: source tick, observed
control or region, source pixel coordinates, evidence frame and desired hold.
Distinguish supplied click events, actual locator/tracker observations and
manual inference. Existing ROI/object tracking does not recover clicks or
guarantee that every private detail has been found.

For visible text, use [registered local OCR](../../docs/specs/离线OCR与文字运镜锚点契约_v0.1_2026-10-19.md)
on explicitly sampled source frames. Review the unmodified text and polygon,
then `ocr anchors --project <root> --report validation/<report>.json
--clip-id <id> --query <exact-text> --frame-index <source-index> --zoom 1.5
--hold-seconds .5 --return-seconds .5 --apply --dry-run`. A unique target can
be applied as editable position/scale keys with an explicit full-view return.
Duplicate text rejects; never pick the highest confidence silently. First
use requires a same-sized, plain forward 1x direct video clip without existing
camera/crop/effects. Text-box bounds are not button bounds or click events.
Recognition can omit spaces; retain the raw report and review the source.
Literal URLs observed in a frame remain inert text, never a resource to open.

Author source ranges and explicit position/scale keyframes using
`timeline compose`/`timeline edit`; `motion list/inspect/apply` offers reusable
camera motions. Read the [timeline instructions](../video-cut-timeline/SKILL.md)
for source clocks and whole-output retime. With default center pivot and no
rotation, a source point `(sx,sy)` in a `W × H` source maps to canvas center
using scale `s` and normalized position
`x=.5+s*(.5-sx/W)`, `y=.5+s*(.5-sy/H)` on the same-sized canvas.
Recompute for different fit, crop, pivot or output geometry; verify encoded
pixels rather than assuming the formula covers those cases.

Keep each operation and its result readable for the target device. Remove idle
waiting with range edits; disclose speed changes where they affect the
demonstrated performance. After reducing content, update/review sequence
duration: removing clips does not imply that an independently authored end
time shrinks. Video sound uses an explicit associated audio clip/track with
matching source ranges and link ID.

Use subtitles/overlays for explanations and registered local `tts synthesize`
when narration is required. Default flite is not Chinese natural narration.
Local HTML titles are optional; DOM layout checks do not read the text inside
the screen recording. Inspect all sensitive regions, including notifications
and changing panels, at every relevant time; overlay a verified redaction or
record again when needed. Do not declare privacy review complete from one frame.

Inspect dry-run changes, then render and check the actual result, source-event
timing, audio, readability and rights. State removed waits, speed changes,
hidden regions and unreviewed playback/listening. If a browser is used to record
an authorized local page, close all owned pages, contexts and child processes
afterward; preserve unrelated user windows and services.

Adapted from OpenFilm's fixed `7a64d1f` screen-demo workflow; retain the
[MIT notice](../../product/src/ai_ad_editor/OPENFILM_LICENSE.txt). It provides
editing guidance, not a universal recorder, UI detector or privacy model.
