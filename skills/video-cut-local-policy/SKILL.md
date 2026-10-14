---
name: video-cut-local-policy
description: Audit and enforce the local-only runtime policy for Agent video projects. Reject remote media, cloud providers, online downloads, and network endpoints before execution.
---

# Local Policy

Use the local `ai-ad-editor` CLI as the only execution surface:

```powershell
python -X utf8 -m ai_ad_editor policy audit --project .\work\demo
python -X utf8 -m ai_ad_editor doctor --project .\work\demo
```

Only project-relative paths, existing local absolute paths, `local://`, and
`file://` references are allowed. Never download media, models, fonts, npm
packages, or plugins. Do not call cloud APIs, webhooks, GUI automation, or
virtualization. A failed audit is a hard stop; preserve its JSON envelope as
the evidence for the Agent caller.
