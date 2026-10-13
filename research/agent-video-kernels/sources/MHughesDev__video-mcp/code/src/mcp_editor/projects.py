from __future__ import annotations

import json
import re
from pathlib import Path

from .config import projects_dir
from .diagnostics import project_not_found
from .schemas import ProjectManifest


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "project"


def project_dir(project_id: str, create: bool = True) -> Path:
    path = projects_dir() / project_id
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def manifest_path(project_id: str, create_parent: bool = True) -> Path:
    return project_dir(project_id, create=create_parent) / "manifest.json"


def save_manifest(manifest: ProjectManifest) -> Path:
    path = manifest_path(manifest.project_id)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_manifest(project_id: str) -> ProjectManifest:
    path = manifest_path(project_id, create_parent=False)
    if not path.exists():
        raise project_not_found(project_id, str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectManifest.model_validate(data)
