---
name: video-cut-project-ops
description: Operate local Agent Projects with snapshots, migration, relinking, persistent render queues, cancellation, and deterministic replay.
---

# Project Operations

For optional GPU queues/resume, follow the [hardware policy](../../docs/specs/硬件编解码探测与显式回退契约_v0.1_2026-10-19.md).
Queue fields are `hardware_encode`, `hardware_decode`, `hardware_encoder`,
`hardware_decoder`, `hardware_probe_mib` and explicit `video_bitrate`.
Resume retains the original fingerprinted settings and reruns availability probes;
never reuse a previous machine/driver's success. Failed/cancelled command reports
remain under `renders/diagnostics`, outside authoring-metadata rollback.

For [compound freeze projects](../../docs/specs/复合片段定格与完整音画时钟契约_v0.1_2026-10-18.md),
package the authored child sequences, media and fonts. Render-only virtual
surfaces are graph pads, not generated files or rights entries. Verify native
package restoration and an actual isolated installed CLI render against the
development bytes, as scoped in the
[installation and rebuild evidence](../../docs/validation/复合片段定格与完整音画时钟实测_2026-10-18.md).
The shared estimated quota charges complete child and frozen surfaces;
loop/reverse buffers and total process RSS still require separate acceptance.

For installing outside the source checkout, use the new-target, hash-bound
wheel-only installer described by the
[offline release contract](../../docs/specs/离线发行与随包Schema契约_v0.1_2026-10-18.md).
Keep existing installations intact; cancellation/failure cleans only owned
staging. The generated launcher isolates host/user dependency sites, and
`schema export` writes a new file. Consult the
[real installation and project-package round trip](../../docs/validation/离线发行与随包Schema实测_2026-10-18.md)
for current platform and external-tool limits.

The [source edit actions](../../docs/specs/真实源范围外扩与关联Slip契约_v0.1_2026-10-18.md)
share timeline snapshots, canonical plan hashes, idempotency and batch rollback.
Reusing a key must not slip the source twice. A failure in any linked member
or later batch step retains original project bytes. Review source and native
retiming changes before applying; these actions preserve asset rights records.

The [range edit actions](../../docs/specs/范围编辑插入覆盖与滚滑剪口契约_v0.1_2026-10-18.md)
share the existing timeline transaction, snapshot and idempotency path.
Preview is read-only; bind `base_project_sha256` when applying, and replay the
same accepted request/key even though its original digest is now stale.
`compose` can batch a range `linked_edit` with later commands; a late error
must retain the exact original project. Review new/removed IDs and detached
transition declarations in the full plan. A completed range edit does not
authorize new source downloads or publication of unverified assets.

For the [fragment library](../../docs/specs/可复用片段组库与跨项目插入契约_v0.1_2026-10-18.md),
save versions under a local library; apply uses the project lock, a
before-fragment-apply snapshot, metadata transaction and normal idempotency.
Bind a reviewed plan with `--expected-project-sha256` and
`--expected-fragment-sha256`. A new instance owns fresh resource and ID
namespaces. Ordinary handler failures remove copied resources; process death
can leave unreferenced files after metadata recovery. Preserve and inspect
those files before cleanup. A library version does not overwrite an earlier
version or automatically propagate source-rights changes to existing copies.

For [source-handle transitions](../../docs/specs/真实源句柄转场与可逆编辑契约_v0.1_2026-10-17.md),
`timeline transition` uses the existing project lock, metadata transaction and
`before-source-transition` snapshot. Its `project_sha256` binds the optional
expected hash; replay the same idempotency request without reapplying it.
Remove the declaration to restore source ranges; no clip restoration journal
is needed. Native JSON/package preserve it; external formats report
`sequence.source_transitions` as Unsupported and strict export rejects.
For [transitioned nested sources](../../docs/specs/嵌套转场合成与作者时钟契约_v0.1_2026-10-18.md),
keep author declarations and references in snapshots/native packages. Internal
video surfaces exist only in the detached render graph; do not register,
relink, package or add rights entries for synthetic surface IDs. Original
media and model dependencies still gate publication. Child warnings propagate
with `inline_sequence_path`. Queue render/dry-run use the existing sampling
quota plus recursive surface/projection charges and preserve explicit
`SEQUENCE_INLINE_BUDGET_EXCEEDED` errors. This is not a total RAM guarantee.

For [linked edits](../../docs/specs/关联片段与主轨联动规划契约_v0.1_2026-10-17.md),
dry-run is read-only. Formal `timeline edit` makes a before-timeline-edit
snapshot and records its plan in the existing metadata transaction. Supply
the plan's `base_project_sha256` through `--expected-project-sha256` to reject
stale authorship; reuse an idempotency key only for the same request. A replay
returns the original result even after its accepted edit changed the project.
`compose` can batch `linked_edit`; invalid intermediate models and late failures
roll back. Native JSON/package preserve editing flags, sync locks, links and
cue offsets. OTIO/Kdenlive/plain drafts report these semantics as Unsupported;
metadata retention does not establish execution in another editor.

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
