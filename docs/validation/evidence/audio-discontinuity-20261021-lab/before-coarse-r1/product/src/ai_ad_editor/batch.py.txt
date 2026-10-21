from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .project import find_sequence, load_project, save_project
from .render import render_project
from .template import apply_template_operations, instantiate
from .utils import atomic_write_json, new_id, now_iso, safe_filename
from .validator import validate_project


def _apply_template(root: Path, project: dict[str, Any], template: dict[str, Any], variables: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    resolved = instantiate(template, variables)
    operations = resolved.get("operations") or resolved.get("changes") or []
    if not isinstance(operations, list):
        raise argument_error("模板 operations/changes 必须是数组")
    applied = apply_template_operations(project, operations, resolved.get("sequence_id"))
    snapshot_variables = resolved.get("template_snapshot", {}).get("variables", variables)
    project.setdefault("templates", []).append({"id": template.get("id") or new_id("template"), "version": template.get("version", "0.0.0"), "variables": [{"name": key, "value": value} for key, value in snapshot_variables.items()], "assets": sorted({item.get("clip", {}).get("asset_id") for item in applied if isinstance(item.get("clip"), dict) and item.get("clip", {}).get("asset_id")})})
    return resolved, applied


def _load_variants(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise argument_error(f"批量变量文件无法读取: {exc}", str(path)) from exc
    if isinstance(payload, dict) and isinstance(payload.get("variants"), list):
        values = payload["variants"]
    elif isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        values = [{"id": "default", "variables": payload}]
    else:
        raise argument_error("批量变量必须是对象、数组或 {variants: []}", str(path))
    variants: list[dict[str, Any]] = []
    for index, item in enumerate(values):
        if not isinstance(item, dict):
            raise argument_error(f"批量变量第 {index} 项必须是对象", str(path))
        variables = item.get("variables", item)
        if not isinstance(variables, dict):
            raise argument_error(f"批量变量第 {index} 项 variables 必须是对象", str(path))
        variants.append({"id": item.get("id") or f"variant-{index + 1:03d}", "variables": variables})
    if not variants:
        raise argument_error("批量变量不能为空", str(path))
    return variants


def run_template_batch(base_root: Path, template: dict[str, Any], variants: list[dict[str, Any]], output_root: Path, *, publish: bool = False, continue_on_error: bool = False) -> dict[str, Any]:
    base_root = base_root.resolve()
    output_root = output_root.resolve()
    try:
        output_root.relative_to(base_root)
    except ValueError as exc:
        raise argument_error("批量输出目录必须位于项目目录内", str(output_root)) from exc
    if output_root == base_root:
        raise argument_error("批量输出目录不能等于基础项目目录", str(output_root))
    if output_root.exists() and any(output_root.iterdir()):
        raise argument_error("批量输出目录必须不存在或为空", str(output_root))
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for index, variant in enumerate(variants):
        variant_id = safe_filename(str(variant.get("id") or f"variant-{index + 1:03d}"))
        variant_root = output_root / variant_id
        item: dict[str, Any] = {"id": variant_id, "status": "failed", "path": str(variant_root), "errors": [], "warnings": []}
        try:
            excluded = ["renders", "operations", "validation", "exports", "cache"]
            try:
                excluded.append(output_root.relative_to(base_root).parts[0])
            except (ValueError, IndexError):
                pass
            shutil.copytree(base_root, variant_root, ignore=shutil.ignore_patterns(*sorted(set(excluded))))
            for directory in ("renders", "operations", "validation", "exports", "cache"):
                (variant_root / directory).mkdir(exist_ok=True)
            _, project = load_project(variant_root)
            resolved, applied = _apply_template(variant_root, project, template, dict(variant["variables"]))
            validation = validate_project(variant_root, project, strict_rights=publish, target="commercial_ad")
            if not validation["ok"]:
                raise AppError("BATCH_PROJECT_INVALID", "批量变体未通过项目或权利校验", exit_code=7 if publish else 2, cause=json.dumps(validation, ensure_ascii=False))
            save_project(variant_root, project)
            result: dict[str, Any] = {"variant_id": variant_id, "project": str(variant_root / "project.json"), "template_snapshot": resolved.get("template_snapshot"), "applied": applied, "validation": validation}
            if publish or template.get("render", True):
                sequence = find_sequence(project, resolved.get("sequence_id"))
                output = variant_root / "renders" / f"{variant_id}.mp4"
                rendered = render_project(variant_root, project, sequence, output, dry_run=False)
                result["render"] = rendered
                project.setdefault("outputs", []).append({"id": new_id("output"), "path": str(output), "container": "mp4", "video": {"codec": "h264"}, "audio": {"codec": "aac"}, "target_platform": "generic"})
                save_project(variant_root, project)
            item.update({"status": "succeeded", "data": result, "warnings": validation.get("warnings", [])})
        except Exception as exc:
            item["errors"] = [{"code": getattr(exc, "code", "BATCH_VARIANT_FAILED"), "message": str(exc)}]
        results.append(item)
        if item["status"] != "succeeded" and not continue_on_error:
            break
    succeeded = sum(1 for item in results if item["status"] == "succeeded")
    return {"batch_version": "0.1.0", "created_at": now_iso(), "requested": len(variants), "completed": len(results), "succeeded": succeeded, "failed": len(results) - succeeded, "output_root": str(output_root), "variants": results}
