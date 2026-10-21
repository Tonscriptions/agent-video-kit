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
python -X utf8 -m ai_ad_editor rights batch-update --project .\work\demo --input .\work\rights-updates.json
python -X utf8 -m ai_ad_editor rights impact --project .\work\demo --asset-id asset_001
python -X utf8 -m ai_ad_editor rights retract --project .\work\demo --asset-id asset_001 --reason "license notice"
python -X utf8 -m ai_ad_editor rights decide --project .\work\demo --asset-id asset_001 --action replace --replacement-asset-id asset_002 --status proposed --reason "license replacement"
python -X utf8 -m ai_ad_editor rights decide --project .\work\demo --asset-id asset_001 --action replace --replacement-asset-id asset_002 --status approved --supersedes-decision-id rightsdecision_... --reason "replacement approved"
python -X utf8 -m ai_ad_editor rights apply --project .\work\demo --decision-id rightsdecision_...
```

The policy rejects remote source/evidence URLs at ingest. A missing,
restricted, disputed, expired or takedown record blocks publish. Keep source
files and license evidence inside the project or a local, versioned asset
library so another Agent can reproduce the decision offline. Amendments use
`rights update --reason ...`; the ledger retains immutable revisions and audit
events. Template and `derived_from` dependencies are checked recursively, and
batch updates preflight all changes before one snapshot is committed.
Recovering a disputed, expired, takedown or blocked record requires `--reopen`
and new local evidence. `rights retract` blocks new publishing and
`rights impact` reports historical artifacts without deleting them.
`rights decide` appends a non-destructive historical `replace`, `delete` or
`retain` decision with its affected artifacts. Use `proposed` while an Agent
is preparing the change, then supersede the current decision with `approved`
or `cancelled` by passing `--supersedes-decision-id`. An approved replace or
delete blocks later releases until it is explicitly cancelled or the asset is
removed from the project dependency closure; the command never deletes or
rewrites historical media. Approved replacements are checked against the
replacement asset's local Rights Ledger record and dependencies first.
`rights apply` is the explicit mutation step for an approved replace/delete:
it snapshots the project, updates or removes current timeline references,
removes the retired asset from the editable project graph, validates the
result, and records an apply event. Historical export JSON and media files
remain untouched; a failed validation leaves the project files unchanged.
`rights export` writes a deterministic release manifest and returns exit code 7
when the gate fails.
