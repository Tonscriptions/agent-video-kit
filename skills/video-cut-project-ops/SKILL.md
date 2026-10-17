---
name: video-cut-project-ops
description: Operate local Agent Projects with snapshots, migration, relinking, persistent render queues, cancellation, and deterministic replay.
---

# Project Operations

Use the project lifecycle and queue as local files:

```powershell
python -X utf8 -m ai_ad_editor project snapshot --project .\work\demo --label before-release
python -X utf8 -m ai_ad_editor queue enqueue --project .\work\demo --input .\queue\variants.json
python -X utf8 -m ai_ad_editor queue run --project .\work\demo --continue-on-error --progress jsonl
python -X utf8 -m ai_ad_editor queue list --project .\work\demo
```

Snapshots, operations, queue state and reports stay in the project. Mutating
CLI commands serialize their complete project read-modify-write phase with
`operations/project-write.lock`; a competing process receives the structured
`PROJECT_WRITE_LOCKED` error and should retry. `queue cancel` stays responsive
while a render holds that lock: it atomically writes the job's `.cancel` marker,
returns `acknowledged=true, confirmed=false`, and the runner later confirms the
terminal state. Retry a failed or cancelled job explicitly after inspecting its
report. Never start a daemon, database, container, remote worker or cloud
artifact service.

Queue jobs selecting an [independent sequence canvas](../../docs/specs/独立序列画布与父级投影契约_v0.1_2026-10-17.md)
default to that sequence's effective width/height. A per-job profile or explicit
dimensions override only the selected root; authored child canvases remain.
Preserve canvas in snapshots and native project/package exchange; external
formats report unsupported child rasters instead of implying full nested parity.

Queue fields `sequence_sampling: area` and `sequence_memory_mib: 1024` are
per-job overrides, matching render/quality flags in the [sampling contract](../../docs/specs/序列面积采样与工作栅格预算契约_v0.1_2026-10-17.md).
They do not edit author settings. Cancelled render resume retains effective
sampling and quota; explicit replacement settings must match its fingerprint.
Projection budget rejection also applies to dry-run; the estimate excludes
decoders, encoders, other effects, threads and simultaneous jobs.
