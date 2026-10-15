from __future__ import annotations

"""Local Rights Ledger and publish gate.

The ledger is deliberately append-only at the record level.  A correction,
license change, dispute or takedown creates a new revision and preserves the
previous evidence and audit event so an Agent can explain why a release was
allowed or blocked.
"""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import AppError, rights_error
from .policy import require_local_reference
from .project import ledger_file
from .utils import atomic_write_json, load_json, new_id, now_iso, sha256_bytes


LEDGER_VERSION = "0.2.0"
VALID_STATUSES = {"unverified", "verified", "restricted", "disputed", "expired", "takedown", "blocked"}
BLOCKED_STATUSES = {"unverified", "disputed", "expired", "takedown", "blocked"}
RECOVERABLE_STATUSES = {"disputed", "expired", "takedown", "blocked"}
VALID_TAKEDOWN_STATUSES = {"clear", "notice", "blocked"}
DISPOSITION_ACTIONS = {"replace", "delete", "retain"}
DISPOSITION_STATUSES = {"proposed", "approved", "cancelled"}
_DISPOSITION_TRANSITIONS = {
    "proposed": {"proposed", "approved", "cancelled"},
    "approved": {"approved", "cancelled"},
    "cancelled": set(),
}

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "unverified": {"unverified", "verified", "restricted", "disputed", "blocked"},
    "verified": {"verified", "restricted", "expired", "takedown", "blocked"},
    "restricted": {"restricted", "verified", "expired", "takedown", "blocked"},
    "disputed": {"disputed", "verified", "restricted", "blocked"},
    "expired": {"expired", "verified", "restricted", "blocked"},
    "takedown": {"takedown", "verified", "restricted", "blocked"},
    "blocked": {"blocked", "verified", "restricted"},
}
_PATCHABLE_FIELDS = {
    "kind",
    "sha256",
    "source_url",
    "source_version",
    "retrieved_at",
    "creator",
    "license_spdx",
    "license_url",
    "attribution",
    "permitted_uses",
    "permitted_channels",
    "restrictions",
    "derived_from",
    "evidence",
    "verification_status",
    "verified_by",
    "takedown_status",
    "expires_at",
    "notes",
}


def _normalize_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    ledger.setdefault("records", [])
    ledger.setdefault("events", [])
    ledger.setdefault("decisions", [])
    ledger.setdefault("policy", {})
    ledger["schema_version"] = LEDGER_VERSION
    return ledger


def load_ledger(root: Path) -> dict[str, Any]:
    if not ledger_file(root).exists():
        return _normalize_ledger({"schema_version": LEDGER_VERSION, "updated_at": now_iso(), "records": [], "events": [], "policy": {}})
    return _normalize_ledger(load_json(ledger_file(root)))


def save_ledger(root: Path, ledger: dict[str, Any]) -> None:
    _normalize_ledger(ledger)
    ledger["updated_at"] = now_iso()
    atomic_write_json(ledger_file(root), ledger)


def _record_version(record: dict[str, Any]) -> int:
    try:
        return int(record.get("record_version", 1))
    except (TypeError, ValueError):
        return 1


def _is_active(record: dict[str, Any]) -> bool:
    return record.get("active", True) is not False and not record.get("superseded_by")


def active_records(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the current revision for every asset, sorted by asset ID."""
    latest: dict[str, dict[str, Any]] = {}
    for record in ledger.get("records", []):
        aid = str(record.get("asset_id", ""))
        if not aid or not _is_active(record):
            continue
        previous = latest.get(aid)
        if previous is None or (_record_version(record), str(record.get("recorded_at", ""))) > (_record_version(previous), str(previous.get("recorded_at", ""))):
            latest[aid] = record
    return [latest[aid] for aid in sorted(latest)]


def record_for(ledger: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    for record in active_records(ledger):
        if str(record.get("asset_id")) == str(asset_id):
            return record
    return None


def record_history(ledger: dict[str, Any], asset_id: str) -> list[dict[str, Any]]:
    records = [record for record in ledger.get("records", []) if str(record.get("asset_id")) == str(asset_id)]
    return sorted(records, key=lambda item: (_record_version(item), str(item.get("recorded_at", ""))))


def _validate_reference(value: Any, field: str) -> None:
    if isinstance(value, str):
        if value:
            require_local_reference(value, field=field)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_reference(item, f"{field}[{index}]")
        return
    if isinstance(value, dict):
        for key in ("path", "uri", "url", "reference"):
            if value.get(key):
                require_local_reference(value[key], field=f"{field}.{key}")
        return
    if value is not None:
        raise AppError("RIGHTS_REFERENCE_INVALID", f"权利证据引用必须是本地字符串、列表或对象: {field}", exit_code=2, path=field)


def _validate_record_shape(record: dict[str, Any], *, partial: bool = False) -> None:
    if not partial and not record.get("asset_id"):
        raise AppError("RIGHTS_ASSET_ID_REQUIRED", "Rights Ledger 记录必须包含 asset_id", exit_code=2, path="asset_id")
    status = record.get("verification_status")
    if status is not None and status not in VALID_STATUSES:
        raise AppError("RIGHTS_STATUS_INVALID", f"不支持的权利状态: {status}", exit_code=2, path="verification_status")
    takedown = record.get("takedown_status")
    if takedown is not None and takedown not in VALID_TAKEDOWN_STATUSES:
        raise AppError("RIGHTS_TAKEDOWN_STATUS_INVALID", f"不支持的撤下状态: {takedown}", exit_code=2, path="takedown_status")
    for field in ("source_url", "license_url", "evidence"):
        if field in record:
            _validate_reference(record.get(field), field)
    for field in ("permitted_uses", "permitted_channels", "restrictions"):
        if field in record and record[field] is not None and not isinstance(record[field], list):
            raise AppError("RIGHTS_FIELD_INVALID", f"字段必须是数组: {field}", exit_code=2, path=field)


def add_record(ledger: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    _normalize_ledger(ledger)
    _validate_record_shape(record)
    status = record.get("verification_status", "unverified")
    if record_for(ledger, str(record.get("asset_id"))):
        raise AppError("RIGHTS_RECORD_EXISTS", f"Rights Ledger 已存在资产记录: {record.get('asset_id')}", exit_code=2)
    record.setdefault("record_id", new_id("rights"))
    record.setdefault("record_version", 1)
    record.setdefault("active", True)
    record.setdefault("recorded_at", now_iso())
    record.setdefault("takedown_status", "clear")
    record.setdefault("permitted_channels", [])
    record.setdefault("restrictions", [])
    record.setdefault("permitted_uses", [])
    record["verification_status"] = status
    ledger.setdefault("records", []).append(record)
    ledger.setdefault("events", []).append({"event_id": new_id("rightsevent"), "event": "created", "asset_id": record["asset_id"], "record_id": record["record_id"], "record_version": record["record_version"], "at": record["recorded_at"], "actor": record.get("verified_by") or "ai-ad-editor"})
    return record


def _has_evidence(record: dict[str, Any]) -> bool:
    evidence = record.get("evidence")
    if isinstance(evidence, str):
        return bool(evidence.strip())
    return bool(evidence)


def revise_record(
    ledger: dict[str, Any],
    asset_id: str,
    patch: dict[str, Any],
    *,
    reason: str,
    actor: str = "ai-ad-editor",
    reopen: bool = False,
) -> dict[str, Any]:
    """Create an immutable next revision and an audit event."""
    _normalize_ledger(ledger)
    if not reason.strip():
        raise AppError("RIGHTS_REASON_REQUIRED", "Rights Ledger 修订必须提供 reason", exit_code=2, path="reason")
    if not isinstance(patch, dict) or not patch:
        raise AppError("RIGHTS_PATCH_REQUIRED", "Rights Ledger 修订至少需要一个字段", exit_code=2, path="patch")
    unknown = sorted(set(patch) - _PATCHABLE_FIELDS)
    if unknown:
        raise AppError("RIGHTS_PATCH_FIELD_INVALID", f"不允许修订字段: {', '.join(unknown)}", exit_code=2, path="patch")
    current = record_for(ledger, str(asset_id))
    if not current:
        raise AppError("RIGHTS_RECORD_MISSING", f"找不到 Rights Ledger 记录: {asset_id}", exit_code=3, path="asset_id")
    next_record = copy.deepcopy(current)
    next_record.update(copy.deepcopy(patch))
    next_status = next_record.get("verification_status", "unverified")
    current_status = current.get("verification_status", "unverified")
    if next_status not in _ALLOWED_TRANSITIONS.get(current_status, {current_status}):
        raise AppError("RIGHTS_TRANSITION_INVALID", f"不允许状态从 {current_status} 变为 {next_status}", exit_code=2, path="verification_status")
    if current_status in RECOVERABLE_STATUSES and next_status in {"verified", "restricted"}:
        if not reopen:
            raise AppError("RIGHTS_REOPEN_REQUIRED", "从争议、过期、撤下或阻断状态恢复必须显式提供 --reopen", exit_code=2, path="reopen")
        if "evidence" not in patch or not _has_evidence(next_record) or patch.get("evidence") == current.get("evidence"):
            raise AppError("RIGHTS_RECOVERY_EVIDENCE_REQUIRED", "恢复状态必须提供新的本地证据", exit_code=2, path="evidence")
    if next_status in {"takedown", "disputed", "blocked"} and "takedown_status" not in patch:
        next_record["takedown_status"] = "notice" if next_status in {"takedown", "disputed"} else "blocked"
    if next_status in {"verified", "restricted"} and current_status in RECOVERABLE_STATUSES and "takedown_status" not in patch:
        next_record["takedown_status"] = "clear"
    _validate_record_shape(next_record)
    previous_id = current.get("record_id")
    next_record["record_id"] = new_id("rights")
    next_record["record_version"] = _record_version(current) + 1
    next_record["recorded_at"] = now_iso()
    next_record["active"] = True
    next_record["supersedes"] = previous_id
    next_record.pop("superseded_by", None)
    current["active"] = False
    current["superseded_by"] = next_record["record_id"]
    ledger["records"].append(next_record)
    event = {"event_id": new_id("rightsevent"), "event": "revised", "asset_id": asset_id, "record_id": next_record["record_id"], "previous_record_id": previous_id, "record_version": next_record["record_version"], "from_status": current_status, "to_status": next_status, "reason": reason, "actor": actor, "at": next_record["recorded_at"], "reopen": reopen}
    ledger["events"].append(event)
    return {"previous": current, "record": next_record, "event": event}


def _expiry_failed(record: dict[str, Any]) -> dict[str, Any] | None:
    value = record.get("expires_at")
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
    except ValueError:
        return {"code": "RIGHTS_EXPIRY_INVALID", "message": f"expires_at 不是有效时间: {value}"}
    if stamp <= datetime.now(timezone.utc):
        return {"code": "RIGHTS_AUTH_EXPIRED", "message": f"授权已过期: {value}"}
    return None


def _walk_scalar_paths(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        result: list[tuple[str, Any]] = []
        for key, child in value.items():
            result.extend(_walk_scalar_paths(child, f"{path}.{key}"))
        return result
    if isinstance(value, list):
        result = []
        for index, child in enumerate(value):
            result.extend(_walk_scalar_paths(child, f"{path}[{index}]"))
        return result
    return [(path, value)]


def impacted_artifacts(root: Path, asset_id: str) -> list[dict[str, Any]]:
    """Find local JSON/JSONL artifacts that still reference an asset.

    This is an offline impact report for retract/replace workflows.  It does
    not delete or rewrite historical renders, so an Agent can decide whether a
    published artifact needs human review.
    """
    root = root.resolve()
    result: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in {".json", ".jsonl"} or path.name == "rights-ledger.json":
            continue
        try:
            if path.suffix.casefold() == ".jsonl":
                payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                payloads = [json.loads(path.read_text(encoding="utf-8"))]
        except (OSError, UnicodeError, ValueError):
            continue
        matches: list[str] = []
        for payload in payloads:
            matches.extend(field for field, value in _walk_scalar_paths(payload) if str(value) == str(asset_id))
        if matches:
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                relative = str(path)
            parts = set(Path(relative).parts)
            kind = next((name for name in ("exports", "renders", "operations", "validation", "history") if name in parts), "project")
            result.append({"path": relative, "kind": kind, "fields": sorted(set(matches))})
    return result


def _record_dependencies(record: dict[str, Any]) -> list[str]:
    value = record.get("derived_from", [])
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def _required_records(project: dict[str, Any], ledger: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    records = {str(item.get("asset_id")): item for item in active_records(ledger) if item.get("asset_id")}
    roots: list[dict[str, Any]] = []
    for asset in project.get("assets", []):
        roots.append({"asset_id": str(asset.get("id")), "rights_ref": str(asset.get("rights_ref", "")), "asset_hash": asset.get("sha256"), "context": "project_asset"})
    for sequence in project.get('sequences', []):
        for track in sequence.get('tracks', []):
            for clip in track.get('clips', []):
                dependencies = clip.get('rights_dependencies', [])
                for dependency in dependencies if isinstance(dependencies, list) else [None]:
                    ref = dependency.get('rights_ref') if isinstance(dependency, dict) else ''
                    roots.append({'asset_id':str(ref or ''), 'rights_ref':str(ref or ''), 'asset_hash':dependency.get('sha256') if isinstance(dependency, dict) else None, 'context':f"clip:{sequence.get('id')}:{clip.get('id')}"})
    for template in project.get("templates", []):
        template_id = str(template.get("id", "<template>"))
        dependencies = template.get("assets", [])
        if isinstance(dependencies, str):
            dependencies = [dependencies]
        if isinstance(dependencies, list):
            for dependency in dependencies:
                roots.append({"asset_id": str(dependency), "rights_ref": str(dependency), "asset_hash": None, "context": f"template:{template_id}"})
        declared = template.get("dependencies", [])
        if isinstance(declared, list):
            for dependency in declared:
                if isinstance(dependency, dict):
                    dependency_id = dependency.get("asset_id") or dependency.get("rights_ref")
                else:
                    dependency_id = dependency
                if dependency_id:
                    roots.append({"asset_id": str(dependency_id), "rights_ref": str(dependency_id), "asset_hash": None, "context": f"template:{template_id}"})
    required: dict[str, dict[str, Any]] = {}
    missing: list[dict[str, Any]] = []
    hash_mismatches: list[dict[str, Any]] = []
    queue = list(roots)
    seen_context: set[tuple[str, str]] = set()
    while queue:
        item = queue.pop(0)
        aid = str(item.get("rights_ref") or item.get("asset_id"))
        context = str(item.get("context", "project_asset"))
        key = (aid, context)
        if key in seen_context:
            continue
        seen_context.add(key)
        record = records.get(aid) or records.get(str(item.get("asset_id")))
        if not record:
            missing.append({"asset_id": aid, "context": context, "code": "RIGHTS_TEMPLATE_DEPENDENCY_MISSING" if context.startswith("template:") else "RIGHTS_RECORD_MISSING", "message": "没有对应 Rights Ledger 记录"})
            continue
        record_id = str(record.get("asset_id"))
        required.setdefault(record_id, record)
        asset_hash = item.get("asset_hash")
        if asset_hash and record.get("sha256") and str(asset_hash) != str(record.get("sha256")):
            hash_mismatches.append({"asset_id": str(item.get("asset_id")), "rights_ref": aid, "context": context, "code": "RIGHTS_HASH_MISMATCH", "message": "项目资产哈希与 Rights Ledger 快照不一致"})
        for parent in _record_dependencies(record):
            queue.append({"asset_id": parent, "rights_ref": parent, "asset_hash": None, "context": f"derived_from:{record_id}"})
    return required, missing, hash_mismatches


def _check_record(record: dict[str, Any], aid: str, target: str, *, strict: bool, failures: list[dict[str, Any]], warnings: list[dict[str, Any]], context: str = "project_asset") -> None:
    def report(item: dict[str, Any]) -> None:
        item.setdefault("asset_id", aid)
        item.setdefault("rights_ref", str(record.get("asset_id", aid)))
        item.setdefault("record_version", _record_version(record))
        item.setdefault("context", context)
        (failures if strict else warnings).append(item)
    status = record.get("verification_status", "unverified")
    if status in BLOCKED_STATUSES:
        report({"status": status, "code": "RIGHTS_STATUS_BLOCKED", "message": f"状态 {status} 不允许发布"})
    if record.get("takedown_status") in {"notice", "blocked"}:
        report({"code": "RIGHTS_TAKEDOWN_BLOCKED", "message": f"撤下状态 {record.get('takedown_status')} 不允许发布"})
    permitted = set(record.get("permitted_uses", []))
    if target and target not in permitted and "all" not in permitted:
        report({"code": "RIGHTS_USE_NOT_PERMITTED", "message": f"记录未允许目标用途: {target}"})
    channels = set(record.get("permitted_channels", []) or [])
    if target and channels and target not in channels and "all" not in channels:
        report({"code": "RIGHTS_CHANNEL_NOT_PERMITTED", "message": f"记录未允许目标渠道: {target}"})
    expiry = _expiry_failed(record)
    if expiry:
        report(expiry)
    if not record.get("source_url") or not record.get("license_spdx") or not _has_evidence(record):
        report({"code": "RIGHTS_EVIDENCE_INCOMPLETE", "message": "来源、许可证或证据字段缺失"})


def disposition_decisions(ledger: dict[str, Any], asset_id: str | None = None) -> list[dict[str, Any]]:
    decisions = [item for item in ledger.get("decisions", []) if isinstance(item, dict) and (asset_id is None or str(item.get("asset_id")) == str(asset_id))]
    return sorted(decisions, key=lambda item: (str(item.get("created_at", "")), str(item.get("decision_id", ""))))


def effective_disposition_decisions(ledger: dict[str, Any], asset_id: str | None = None) -> list[dict[str, Any]]:
    decisions = disposition_decisions(ledger)
    superseded = {str(item["supersedes"]) for item in decisions if item.get("supersedes")}
    return [item for item in decisions if str(item.get("decision_id")) not in superseded and (asset_id is None or str(item.get("asset_id")) == str(asset_id))]


def _project_asset_reference_paths(project: dict[str, Any], asset_id: str) -> list[str]:
    paths: list[str] = []

    def walk(value: Any, path: str, *, in_provenance: bool = False) -> None:
        if in_provenance:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if key in {"asset_id", "rights_ref"} and str(child) == str(asset_id):
                    paths.append(child_path)
                else:
                    walk(child, child_path, in_provenance=path == "provenance" or in_provenance)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]", in_provenance=in_provenance)

    walk(project, "")
    return sorted(set(paths))


def apply_disposition_to_project(project: dict[str, Any], ledger: dict[str, Any], decision_id: str) -> dict[str, Any]:
    """Apply one approved replace/delete decision to the editable project graph.

    This changes only current project references and leaves historical exports and
    media files untouched.  The caller must snapshot before committing the result.
    """
    decision = next((item for item in effective_disposition_decisions(ledger) if str(item.get("decision_id")) == str(decision_id)), None)
    if not decision:
        raise AppError("RIGHTS_DISPOSITION_MISSING", f"找不到当前有效历史处置决策: {decision_id}", exit_code=3, path="decision_id")
    if decision.get("status") != "approved":
        raise AppError("RIGHTS_DISPOSITION_NOT_APPROVED", "只有 approved 历史处置决策可以 apply", exit_code=2, path="decision_id")
    action = str(decision.get("action"))
    if action not in {"replace", "delete"}:
        raise AppError("RIGHTS_DISPOSITION_APPLY_UNSUPPORTED", "retain 决策不需要 apply；replace/delete 才能修改项目", exit_code=2, path="action")
    old_id = str(decision.get("asset_id"))
    replacement_id = str(decision.get("replacement_asset_id")) if decision.get("replacement_asset_id") else None
    assets = project.get("assets", [])
    old_asset = next((item for item in assets if str(item.get("id")) == old_id), None)
    if not old_asset:
        raise AppError("RIGHTS_PROJECT_ASSET_MISSING", f"项目中找不到待处置资产: {old_id}", exit_code=3, path="asset_id")
    replacement = None
    if action == "replace":
        replacement = next((item for item in assets if str(item.get("id")) == replacement_id), None)
        if not replacement:
            raise AppError("RIGHTS_REPLACEMENT_PROJECT_ASSET_MISSING", f"替代资产没有加入当前项目: {replacement_id}", exit_code=3, path="replacement_asset_id")
    changed_clips: list[dict[str, Any]] = []
    removed_clips: list[dict[str, Any]] = []
    for sequence in project.get("sequences", []):
        for track in sequence.get("tracks", []):
            clips = track.get("clips", [])
            kept: list[dict[str, Any]] = []
            for clip in clips:
                if str(clip.get("asset_id")) != old_id:
                    kept.append(clip)
                    continue
                if action == "replace":
                    source_out = int(clip.get("source_out_tick", 0) or 0)
                    replacement_duration = int((replacement or {}).get("probe", {}).get("duration_tick", 0) or 0)
                    if replacement_duration and source_out > replacement_duration:
                        raise AppError("RIGHTS_REPLACEMENT_DURATION_SHORT", "替代资产时长不足以覆盖现有片段 source_out_tick", exit_code=2, path=f"sequences[{sequence.get('id')}].tracks[{track.get('id')}].clips[{clip.get('id')}].source_out_tick")
                    updated = copy.deepcopy(clip)
                    updated["asset_id"] = replacement_id
                    kept.append(updated)
                    changed_clips.append({"sequence_id": sequence.get("id"), "track_id": track.get("id"), "clip_id": clip.get("id"), "from_asset_id": old_id, "to_asset_id": replacement_id})
                else:
                    removed_clips.append({"sequence_id": sequence.get("id"), "track_id": track.get("id"), "clip_id": clip.get("id"), "asset_id": old_id})
            track["clips"] = kept
        sequence["duration_tick"] = max(1, max((int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0)) for track in sequence.get("tracks", []) for clip in track.get("clips", [])), default=0))

    def rewrite(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: (replacement_id if key in {"asset_id", "rights_ref"} and str(child) == old_id and action == "replace" else rewrite(child)) for key, child in value.items()}
        if isinstance(value, list):
            return [rewrite(child) for child in value]
        return value

    if action == "replace":
        for key in ("templates", "outputs"):
            if key in project:
                project[key] = rewrite(project[key])
    else:
        for template in project.get("templates", []):
            if isinstance(template.get("assets"), list):
                template["assets"] = [item for item in template["assets"] if str(item) != old_id]
            if isinstance(template.get("dependencies"), list):
                template["dependencies"] = [item for item in template["dependencies"] if str(item.get("asset_id") if isinstance(item, dict) else item) != old_id]
    project["assets"] = [item for item in assets if str(item.get("id")) != old_id]
    remaining = _project_asset_reference_paths(project, old_id)
    if remaining:
        raise AppError("RIGHTS_DISPOSITION_REFERENCES_REMAIN", "项目仍有未处理的处置资产引用", exit_code=2, path="project", cause=json.dumps(remaining, ensure_ascii=False))
    return {"decision": copy.deepcopy(decision), "action": action, "asset_id": old_id, "replacement_asset_id": replacement_id, "changed_clips": changed_clips, "removed_clips": removed_clips, "removed_project_asset": old_id, "remaining_references": []}


def create_disposition_decision(
    ledger: dict[str, Any],
    asset_id: str,
    *,
    action: str,
    status: str,
    reason: str,
    actor: str = "ai-ad-editor",
    target: str = "commercial_ad",
    replacement_asset_id: str | None = None,
    impacted: list[dict[str, Any]] | None = None,
    supersedes_decision_id: str | None = None,
    project: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a non-destructive historical replace/delete decision.

    The decision never removes media or rewrites historical manifests.  An
    approved replace/delete decision blocks new release use of the affected
    asset until that decision is explicitly cancelled or the asset is removed
    from the project's rights dependency closure.
    """
    _normalize_ledger(ledger)
    if action not in DISPOSITION_ACTIONS:
        raise AppError("RIGHTS_DISPOSITION_ACTION_INVALID", f"不支持的历史处置动作: {action}", exit_code=2, path="action")
    if status not in DISPOSITION_STATUSES:
        raise AppError("RIGHTS_DISPOSITION_STATUS_INVALID", f"不支持的历史处置状态: {status}", exit_code=2, path="status")
    if not str(reason).strip():
        raise AppError("RIGHTS_REASON_REQUIRED", "历史处置决策必须提供 reason", exit_code=2, path="reason")
    current = record_for(ledger, str(asset_id))
    if not current:
        raise AppError("RIGHTS_RECORD_MISSING", f"找不到 Rights Ledger 记录: {asset_id}", exit_code=3, path="asset_id")
    previous = None
    if supersedes_decision_id:
        previous = next((item for item in disposition_decisions(ledger) if item.get("decision_id") == supersedes_decision_id), None)
        if not previous:
            raise AppError("RIGHTS_DISPOSITION_MISSING", f"找不到历史处置决策: {supersedes_decision_id}", exit_code=3, path="supersedes_decision_id")
        if not any(item.get("decision_id") == supersedes_decision_id for item in effective_disposition_decisions(ledger)):
            raise AppError("RIGHTS_DISPOSITION_STALE", "历史处置决策已有后续修订，请使用当前有效 decision_id", exit_code=2, path="supersedes_decision_id")
        expected = (str(asset_id), action, target, str(replacement_asset_id) if replacement_asset_id else None)
        actual = (str(previous.get("asset_id")), previous.get("action"), previous.get("target"), previous.get("replacement_asset_id"))
        if actual != expected:
            raise AppError("RIGHTS_DISPOSITION_SCOPE_MISMATCH", "决策修订必须保留原资产、动作、目标渠道和替代资产", exit_code=2, path="supersedes_decision_id")
        if status not in _DISPOSITION_TRANSITIONS.get(str(previous.get("status")), set()):
            raise AppError("RIGHTS_DISPOSITION_TRANSITION_INVALID", f"不允许的决策状态转换: {previous.get('status')} -> {status}", exit_code=2, path="status")
    elif status == "cancelled":
        raise AppError("RIGHTS_DISPOSITION_PREDECESSOR_REQUIRED", "撤销必须通过 supersedes_decision_id 指定当前有效决策", exit_code=2, path="supersedes_decision_id")
    if action == "replace":
        if not replacement_asset_id:
            raise AppError("RIGHTS_REPLACEMENT_REQUIRED", "replace 决策必须提供 replacement_asset_id", exit_code=2, path="replacement_asset_id")
        if str(replacement_asset_id) == str(asset_id):
            raise AppError("RIGHTS_REPLACEMENT_SAME_ASSET", "replacement_asset_id 不能与原资产相同", exit_code=2, path="replacement_asset_id")
        replacement = record_for(ledger, str(replacement_asset_id))
        if not replacement:
            raise AppError("RIGHTS_REPLACEMENT_RECORD_MISSING", f"找不到替代资产 Rights Ledger 记录: {replacement_asset_id}", exit_code=3, path="replacement_asset_id")
        if status == "approved":
            replacement_asset = next((item for item in (project or {}).get("assets", []) if str(item.get("id")) == str(replacement_asset_id)), {"id": str(replacement_asset_id)})
            replacement_check = check_project_rights({"assets": [replacement_asset]}, ledger, target, strict=True)
            if not replacement_check["ok"]:
                raise AppError("RIGHTS_REPLACEMENT_NOT_PUBLISHABLE", "替代资产或其依赖未通过目标渠道权利门禁", exit_code=7, path="replacement_asset_id", cause=json.dumps(replacement_check["failures"], ensure_ascii=False))
    elif replacement_asset_id:
        raise AppError("RIGHTS_REPLACEMENT_UNEXPECTED", "delete/retain 决策不能提供 replacement_asset_id", exit_code=2, path="replacement_asset_id")
    decision = {
        "decision_id": new_id("rightsdecision"),
        "supersedes": supersedes_decision_id,
        "asset_id": str(asset_id),
        "action": action,
        "status": status,
        "replacement_asset_id": str(replacement_asset_id) if replacement_asset_id else None,
        "target": target,
        "reason": str(reason),
        "actor": actor,
        "affected_artifacts": copy.deepcopy(previous.get("affected_artifacts", []) if previous else impacted or []),
        "created_at": now_iso(),
    }
    ledger["decisions"].append(decision)
    ledger["events"].append({"event_id": new_id("rightsevent"), "event": "disposition_decision", "asset_id": str(asset_id), "decision_id": decision["decision_id"], "supersedes": supersedes_decision_id, "action": action, "status": status, "replacement_asset_id": decision["replacement_asset_id"], "reason": str(reason), "actor": actor, "at": decision["created_at"]})
    return decision


def check_project_rights(project: dict[str, Any], ledger: dict[str, Any], target: str = "commercial_ad", *, strict: bool = True) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    required, missing, hash_mismatches = _required_records(project, ledger)
    failures.extend(missing)
    failures.extend(hash_mismatches)
    for record in required.values():
        context = "derived_dependency" if record.get("asset_id") not in {str(asset.get("id")) for asset in project.get("assets", [])} else "project_asset"
        _check_record(record, str(record.get("asset_id")), target, strict=strict, failures=failures, warnings=warnings, context=context)
    required_ids = {str(item) for item in required}
    for decision in effective_disposition_decisions(ledger):
        if str(decision.get("asset_id")) not in required_ids or decision.get("target") not in {None, "", target, "all"}:
            continue
        if decision.get("status") == "approved" and decision.get("action") in {"replace", "delete"}:
            failures.append({"code": "RIGHTS_DISPOSITION_BLOCKED", "message": f"资产已有已批准的历史处置决策: {decision.get('action')}", "asset_id": str(decision.get("asset_id")), "decision_id": decision.get("decision_id"), "replacement_asset_id": decision.get("replacement_asset_id"), "context": "historical_disposition"})
        elif decision.get("status") == "proposed" and decision.get("action") in {"replace", "delete"}:
            warnings.append({"code": "RIGHTS_DISPOSITION_PROPOSED", "message": f"资产存在待处理历史处置决策: {decision.get('action')}", "asset_id": str(decision.get("asset_id")), "decision_id": decision.get("decision_id"), "replacement_asset_id": decision.get("replacement_asset_id"), "context": "historical_disposition"})
    return {"ok": not failures, "target": target, "checked": len(project.get("assets", [])), "required_records": len(required), "failures": failures, "warnings": warnings, "disposition_decisions": disposition_decisions(ledger), "effective_disposition_decisions": effective_disposition_decisions(ledger)}


def release_manifest(project: dict[str, Any], ledger: dict[str, Any], target: str = "commercial_ad") -> dict[str, Any]:
    """Build a deterministic local release manifest for downstream publishing."""
    rights_check = check_project_rights(project, ledger, target, strict=True)
    records = {str(item.get("asset_id")): item for item in active_records(ledger)}
    required_records, _missing, _hash_mismatches = _required_records(project, ledger)
    assets: list[dict[str, Any]] = []
    for asset in project.get("assets", []):
        aid = str(asset.get("id"))
        record = records.get(str(asset.get("rights_ref", ""))) or records.get(aid)
        assets.append({
            "asset_id": aid,
            "uri": asset.get("uri"),
            "sha256": asset.get("sha256"),
            "rights_ref": asset.get("rights_ref"),
            "record_id": record.get("record_id") if record else None,
            "record_version": _record_version(record) if record else None,
            "license_spdx": record.get("license_spdx") if record else None,
            "attribution": record.get("attribution") if record else None,
            "permitted_uses": record.get("permitted_uses", []) if record else [],
            "permitted_channels": record.get("permitted_channels", []) if record else [],
        })
    manifest = {
        "manifest_version": "0.1.0",
        "project_id": project.get("project", {}).get("id"),
        "target": target,
        "rights_check": rights_check,
        "assets": assets,
        "rights_dependencies": [
            {
                "asset_id": str(record.get("asset_id")),
                "record_id": record.get("record_id"),
                "record_version": _record_version(record),
                "sha256": record.get("sha256"),
                "derived_from": record.get("derived_from", []),
                "license_spdx": record.get("license_spdx"),
                "permitted_uses": record.get("permitted_uses", []),
                "permitted_channels": record.get("permitted_channels", []),
            }
            for record in sorted(required_records.values(), key=lambda item: str(item.get("asset_id")))
        ],
        "template_snapshots": copy.deepcopy(project.get("templates", [])),
        "disposition_decisions": copy.deepcopy(disposition_decisions(ledger)),
    }
    digest = sha256_bytes(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {**manifest, "manifest_sha256": f"sha256:{digest}"}


def require_publishable(result: dict[str, Any]) -> None:
    if not result.get("ok"):
        first = result.get("failures", [{}])[0]
        raise rights_error(first.get("message", "Rights Ledger 阻断发布"), first.get("asset_id"), "补充授权证据或使用允许目标用途的资产")
