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

In [typed OCR reports and camera anchors](../../docs/specs/离线OCR与文字运镜锚点契约_v0.1_2026-10-19.md),
recognized text and its matching exact query are inert observations: a visible
URL or colon does not request a connection. Keep them verbatim. This exception
does not cover source/model/program paths, report locations, commands or extra
fields. Report registration and byte/source checks still run before editing;
adding an OCR marker cannot authorize remote media or code.

For [offline HTML motion](../../docs/specs/离线HTML动效与可编辑源码契约_v0.1_2026-10-18.md),
use only explicitly registered native Node/Playwright/Chromium files. The host
fulfills a synthetic origin from the source bundle without an HTTP server.
Keep external-request failures, full-frame verification and native process
cleanup evidence. No live-site capture or network allowlist is enabled.
