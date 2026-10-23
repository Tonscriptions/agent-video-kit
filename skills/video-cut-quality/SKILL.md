---
name: video-cut-quality
description: Review local encoded masks, explicit selected/clear checkpoints, color scopes, render manifests, and quality evidence for Agent video delivery.
---

# Video Cut / quality

Current release: `v0.1.0-alpha.1`. Source of truth: [bilingual release manual](../../docs/releases/v0.1.0-alpha.1/USAGE.md)
and [Skill catalog](../../docs/releases/v0.1.0-alpha.1/SKILLS.md).

Validate the authored project and Rights Ledger before publication. Run `quality check` on the actual
encoded output; use `quality scopes` and `quality golden` when requested. Inspect source/output frames and manifests.
Distinguish automatic decode/pixel/PCM checks, static visual review, continuous playback and human listening.
A successful encode or a passed test count does not establish natural quality or complete CapCut parity.
For Float32 work inspect the declared color signal, renderer protocol and independent reference evidence.

## Execution boundaries

- Native local execution only. No Docker, WSL, containers, runtime downloads, cloud providers or telemetry.
- Use existing Python/FFmpeg and explicit local model paths; missing dependencies must produce a truthful refusal.
- Output paths are absolute and inside the owned project. Preserve existing outputs and failure evidence.
- Run dry plans where supported; author audio explicitly. Video placement alone does not create an audio track.
- Inspect actual `ok`, `status`, `errors`, exit code and artifact paths. Preserve warnings and conversion losses.
- `--publish` performs local rights gating; it does not upload media.

## Renderer choice

Default render/preview uses the existing FFmpeg graph. Explicit `settings.pixel_pipeline.engine = "float32-native-v1"`
uses the advertised Float32 path for its supported subset. Declare source/working/delivery color signals using
the current schema and [Float32 contracts](../../docs/Agent浮点帧包CLI使用与验收边界_2026-10-22.md).
Do not silently change pipeline or substitute unsupported effects. Native `surface export` is a separate
frame-bundle interchange command. Float transition/runtime experiments beyond released V112 are not this release.

## References

- [First-release cases and real responses](../../docs/releases/v0.1.0-alpha.1/CASES.md)
- [Release gates and known limitations](../../docs/releases/v0.1.0-alpha.1/RELEASE.md)
- [Complete schema](../../docs/specs/agent-project.schema.json)
- [Historical routing and evidence](references/pre-release-routing.md), only for its dated capability scope.
