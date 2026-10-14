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
python -X utf8 -m ai_ad_editor rights list --project .\work\demo
python -X utf8 -m ai_ad_editor rights history --project .\work\demo --asset-id asset_001
python -X utf8 -m ai_ad_editor rights export --project .\work\demo --target commercial_ad --output .\work\demo\exports\release.json
```

The policy rejects remote source/evidence URLs at ingest. A missing,
restricted, disputed, expired or takedown record blocks publish. Keep source
files and license evidence inside the project or a local, versioned asset
library so another Agent can reproduce the decision offline. Amendments use
`rights update --reason ...`; the ledger retains immutable revisions and audit
events. Recovering a disputed, expired, takedown or blocked record requires
`--reopen` and new local evidence. `rights export` writes a deterministic
release manifest and returns exit code 7 when the gate fails.
