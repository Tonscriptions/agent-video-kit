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


def check_project_rights(project: dict[str, Any], ledger: dict[str, Any], target: str = "commercial_ad", *, strict: bool = True) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    records = {str(item.get("asset_id")): item for item in active_records(ledger)}
    for asset in project.get("assets", []):
        aid = str(asset.get("id"))
        ref = str(asset.get("rights_ref", ""))
        record = records.get(ref) or records.get(aid)
        if not record:
            failures.append({"asset_id": aid, "code": "RIGHTS_RECORD_MISSING", "message": "没有对应 Rights Ledger 记录"})
            continue
        status = record.get("verification_status", "unverified")
        def report(item: dict[str, Any]) -> None:
            (failures if strict else warnings).append(item)
        if status in BLOCKED_STATUSES:
            report({"asset_id": aid, "rights_ref": ref, "record_version": _record_version(record), "status": status, "code": "RIGHTS_STATUS_BLOCKED", "message": f"状态 {status} 不允许发布"})
        if record.get("takedown_status") in {"notice", "blocked"}:
            report({"asset_id": aid, "rights_ref": ref, "code": "RIGHTS_TAKEDOWN_BLOCKED", "message": f"撤下状态 {record.get('takedown_status')} 不允许发布"})
        permitted = set(record.get("permitted_uses", []))
        if target and target not in permitted and "all" not in permitted:
            report({"asset_id": aid, "rights_ref": ref, "code": "RIGHTS_USE_NOT_PERMITTED", "message": f"记录未允许目标用途: {target}"})
        channels = set(record.get("permitted_channels", []) or [])
        if target and channels and target not in channels and "all" not in channels:
            report({"asset_id": aid, "rights_ref": ref, "code": "RIGHTS_CHANNEL_NOT_PERMITTED", "message": f"记录未允许目标渠道: {target}"})
        expiry = _expiry_failed(record)
        if expiry:
            report({"asset_id": aid, "rights_ref": ref, **expiry})
        if not record.get("source_url") or not record.get("license_spdx") or not _has_evidence(record):
            report({"asset_id": aid, "rights_ref": ref, "code": "RIGHTS_EVIDENCE_INCOMPLETE", "message": "来源、许可证或证据字段缺失"})
    return {"ok": not failures, "target": target, "checked": len(project.get("assets", [])), "failures": failures, "warnings": warnings}


def release_manifest(project: dict[str, Any], ledger: dict[str, Any], target: str = "commercial_ad") -> dict[str, Any]:
    """Build a deterministic local release manifest for downstream publishing."""
    rights_check = check_project_rights(project, ledger, target, strict=True)
    records = {str(item.get("asset_id")): item for item in active_records(ledger)}
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
    }
    digest = sha256_bytes(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {**manifest, "manifest_sha256": f"sha256:{digest}"}


def require_publishable(result: dict[str, Any]) -> None:
    if not result.get("ok"):
        first = result.get("failures", [{}])[0]
        raise rights_error(first.get("message", "Rights Ledger 阻断发布"), first.get("asset_id"), "补充授权证据或使用允许目标用途的资产")
