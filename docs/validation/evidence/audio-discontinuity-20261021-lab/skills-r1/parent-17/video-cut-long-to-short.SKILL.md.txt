---
name: video-cut-long-to-short
description: Turn a local talk, interview, lesson or recording into editable short clips using supplied or reviewed transcripts, preserved context, source ranges and local captions. Use for 长转短, 切片, 高光 and 拆条.
---

# Local long video to shorts

Use the local Agent Video Kit CLI and the
[workflow contract](../../docs/specs/OpenFilm三套本地创作Skill适配与实片核验契约_v0.1_2026-10-19.md).
Select moments that stand alone while preserving what the speaker meant.
Retain conditions, negations, referents and the question needed to understand
an answer. Do not join separate remarks into a new claim. Follow the requested
audience, length, number of clips and required/excluded moments.

Start with a local recording and reviewed transcript. If it needs transcription,
follow the [local understanding instructions](../video-cut-video-understand/SKILL.md)
to use an explicitly registered offline ASR adapter. `media highlights` and
silence/scene/beat reports propose candidates; they do not choose semantically
valid or compelling passages. A detector object ID does not identify the speaker.
Use supplied text/times when available and label their origin.

For each selected passage, save source integer tick ranges, the complete
original words, first line, selection reason and uncertain names/numbers.
Inspect neighboring speech; put cuts in pauses without clipping words. Current
ASR segment times, weighted subtitle segmentation and CTC word alignment have
different meanings and quality limits. Consult the
[actual word-timing failures](../../docs/validation/开源字词边界模型对照实测_2026-10-18.md)
before promising precise automatic word boundaries.

Create a separate sequence/project per deliverable as appropriate. Add explicit
video and audio clips with identical source ranges and shared `link_id`; placing
a video on a visual track alone does not carry its embedded speech. Use
`timeline compose`/`edit --dry-run`, inspect the retained ranges and output
duration, then apply. Follow the
[timeline instructions](../video-cut-timeline/SKILL.md) for linked edits,
portrait reframing and source clocks. Review the subject throughout every
retained interval, especially occlusion and speaker changes.

Use `subtitle segment` for readable display chunks, with a registered font and
source rights dependencies; `--apply --track-id` places them on the caption
track. Generated line times are not new acoustic observations. Keep supplied
text exact; correct recognition separately. Inspect caption size and platform
safe areas in actual output frames.

Render each clip, run quality/policy/rights checks and inspect actual picture
and sound. Keep all negations/conditions and needed context in the final media.
Technical sample equality does not establish semantic quality or listening
acceptance. Return each clip's length, opening, why selected, source intervals
and remaining uncertainties. Retain unverified voice/model rights and any
commercial gate refusal; an internal render is not a publish authorization.

Adapted from OpenFilm's fixed `7a64d1f` long-to-short workflow; retain the
[MIT notice](../../product/src/ai_ad_editor/OPENFILM_LICENSE.txt). This workflow
does not supply a new semantic selection, diarization or speech-alignment model.
