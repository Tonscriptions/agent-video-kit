---
name: video-cut-rights-ledger
description: Register local media, templates, fonts, audio, LUTs, and model artifacts with a reproducible Rights Ledger and enforce publish gates.
---

# Rights Ledger

Every asset used by a publishable project needs a local source reference,
content hash, SPDX or explicit license reference, permitted target use and
evidence. Keep `verification_status=unverified` until the local evidence is
reviewed. Run the gate before rendering a release:

```powershell
python -X utf8 -m ai_ad_editor rights check --project .\work\demo --target commercial_ad
python -X utf8 -m ai_ad_editor validate --project .\work\demo --strict-rights
```

The policy rejects remote source/evidence URLs at ingest. A missing,
restricted, disputed, expired or takedown record blocks publish. Keep source
files and license evidence inside the project or a local, versioned asset
library so another Agent can reproduce the decision offline.
