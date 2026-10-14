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
