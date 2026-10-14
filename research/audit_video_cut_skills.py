"""Check namespace, metadata, registrations, bundled links and Python bootstrap paths."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote

import yaml

PROJECT = Path(__file__).resolve().parents[1]
manifest_path = PROJECT / "video-cut-install-manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
validator_path = Path(manifest["codex_skills_directory"]) / ".system" / "skill-creator" / "scripts" / "quick_validate.py"
spec = importlib.util.spec_from_file_location("validator", validator_path)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

failures, unresolved, verified, adapted_python = [], [], [], []
for entry in manifest["skills"]:
    root = Path(entry["canonical_directory"])
    md = root / "SKILL.md"
    valid, message = validator.validate_skill(root)
    if not valid:
        failures.append({"name": entry["name"], "check": "skill_validator", "reason": message})
    header = yaml.safe_load(md.read_text(encoding="utf-8").split("---", 2)[1])
    if header["name"] != root.name or not root.name.startswith("video-cut-"):
        failures.append({"name": root.name, "check": "namespace"})
    registration = Path(entry["registration_directory"])
    registered = registration.is_dir() and os.path.samefile(md, registration / "SKILL.md")
    if manifest["status"] == "registered" and not registered:
        failures.append({"name": root.name, "check": "junction_registration"})
    ui_path = root / "agents" / "openai.yaml"
    interface = {}
    if ui_path.exists():
        ui = yaml.safe_load(ui_path.read_text(encoding="utf-8"))
        interface = ui.get("interface", {}) if isinstance(ui, dict) else {}
        invocation = entry.get("invocation", f"${entry['name']}")
        if not interface.get("display_name"):
            failures.append({"name": root.name, "check": "invocation_metadata"})
        if invocation not in str(interface.get("default_prompt", "")):
            failures.append({"name": root.name, "check": "invocation_metadata"})
    elif entry.get("source_kind") not in {"local-only-skill", "local-product-skill"}:
        failures.append({"name": root.name, "check": "invocation_metadata_missing"})
    # Check all Markdown resources, including the router's bundled references.
    for resource in root.rglob("*.md"):
        text = resource.read_text(encoding="utf-8")
        # Keep fenced code links out of the check: most illustrate future output paths.
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        for link in re.findall(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)", prose):
            target = link.strip().split(" ", 1)[0].strip("<>")
            if re.match(r"^[a-zA-Z][a-zA-Z\d+.-]*:", target) or target.startswith(("#", "/")):
                continue
            target = unquote(target.split("#", 1)[0])
            if not target or any(c in target for c in "<>*"):
                continue
            linked_path = resource.parent / target
            if not linked_path.exists():
                unresolved.append({"name": root.name, "file": resource.relative_to(root).as_posix(), "target": target})
    # Compile modified Python text without executing it or creating pyc files.
    # Local product Skills may be generated in-place and therefore omit the
    # upstream `adapted_files` inventory. Treat that optional field as empty;
    # the SKILL.md, registration, metadata, and link checks above still apply.
    for rel in entry.get("adapted_files", []):
        if rel.endswith(".py"):
            path = root / rel
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
                adapted_python.append(str(path))
            except (SyntaxError, UnicodeError) as exc:
                failures.append({"name": root.name, "check": "adapted_python_syntax", "reason": str(exc)})
    entry["skill_md_sha256"] = hashlib.sha256(md.read_bytes()).hexdigest()
    verified.append({"name": root.name, "skill_valid": valid, "registration_same_file": registered})

report = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(), "skill_count": len(verified),
    "failures": failures, "unresolved_markdown_links": unresolved, "skills": verified,
    "adapted_python_files_compiled": len(adapted_python),
    "scope": "Local file/metadata/registration checks; local-only production Skills; no rendering, model/API calls, browser, Docker or WSL execution.",
}
(PROJECT / "research" / "video-cut-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"skills": len(verified), "failures": failures, "unresolved_links": unresolved, "adapted_python_files_compiled": len(adapted_python)}, ensure_ascii=False, indent=2))
sys.exit(1 if failures else 0)
