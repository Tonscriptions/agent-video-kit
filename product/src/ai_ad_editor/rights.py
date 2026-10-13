from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import AppError, rights_error
from .project import ledger_file
from .utils import atomic_write_json, load_json, now_iso


VALID_STATUSES = {"unverified", "verified", "restricted", "disputed", "expired", "takedown", "blocked"}
BLOCKED_STATUSES = {"unverified", "disputed", "expired", "takedown", "blocked"}


def load_ledger(root: Path) -> dict[str, Any]:
    if not ledger_file(root).exists():
        return {"schema_version": "0.1.0", "updated_at": now_iso(), "records": [], "policy": {}}
    ledger = load_json(ledger_file(root))
    ledger.setdefault("records", [])
    return ledger


def save_ledger(root: Path, ledger: dict[str, Any]) -> None:
    ledger["updated_at"] = now_iso()
    atomic_write_json(ledger_file(root), ledger)


def record_for(ledger: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    for record in ledger.get("records", []):
        if record.get("asset_id") == asset_id:
            return record
    return None


def add_record(ledger: dict[str, Any], record: dict[str, Any]) -> None:
    status = record.get("verification_status", "unverified")
    if status not in VALID_STATUSES:
        raise AppError("RIGHTS_STATUS_INVALID", f"不支持的权利状态: {status}", exit_code=2, path="verification_status")
    existing = record_for(ledger, str(record.get("asset_id")))
    if existing:
        raise AppError("RIGHTS_RECORD_EXISTS", f"Rights Ledger 已存在资产记录: {record.get('asset_id')}", exit_code=2)
    ledger.setdefault("records", []).append(record)


def check_project_rights(project: dict[str, Any], ledger: dict[str, Any], target: str = "commercial_ad", *, strict: bool = True) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    records = {str(item.get("asset_id")): item for item in ledger.get("records", [])}
    for asset in project.get("assets", []):
        aid = str(asset.get("id"))
        ref = str(asset.get("rights_ref", ""))
        record = records.get(ref) or records.get(aid)
        if not record:
            failures.append({"asset_id": aid, "code": "RIGHTS_RECORD_MISSING", "message": "没有对应 Rights Ledger 记录"})
            continue
        status = record.get("verification_status", "unverified")
        permitted = set(record.get("permitted_uses", []))
        if status in BLOCKED_STATUSES:
            item = {"asset_id": aid, "rights_ref": ref, "status": status, "code": "RIGHTS_STATUS_BLOCKED", "message": f"状态 {status} 不允许发布"}
            if strict:
                failures.append(item)
            else:
                warnings.append(item)
        if target and target not in permitted and "all" not in permitted:
            item = {"asset_id": aid, "rights_ref": ref, "code": "RIGHTS_USE_NOT_PERMITTED", "message": f"记录未允许目标用途: {target}"}
            if strict:
                failures.append(item)
            else:
                warnings.append(item)
        if not record.get("source_url") or not record.get("license_spdx") or not record.get("evidence"):
            item = {"asset_id": aid, "rights_ref": ref, "code": "RIGHTS_EVIDENCE_INCOMPLETE", "message": "来源、许可证或证据字段缺失"}
            if strict:
                failures.append(item)
            else:
                warnings.append(item)
    return {"ok": not failures, "target": target, "checked": len(project.get("assets", [])), "failures": failures, "warnings": warnings}


def require_publishable(result: dict[str, Any]) -> None:
    if not result.get("ok"):
        first = result.get("failures", [{}])[0]
        raise rights_error(first.get("message", "Rights Ledger 阻断发布"), first.get("asset_id"), "补充授权证据或使用允许目标用途的资产")
