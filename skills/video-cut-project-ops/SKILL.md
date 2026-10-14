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

Snapshots, operations, queue state and reports stay in the project. Retry a
failed or cancelled job explicitly after inspecting its report. Never start a
daemon, database, container, remote worker or cloud artifact service.
