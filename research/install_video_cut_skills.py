"""Stage and validate prefixed Skills; register them with register-video-cut-skills.ps1."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

import yaml

PROJECT = Path(__file__).resolve().parents[1]
CODEX_ROOT = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
LIBRARY = PROJECT / "skills"
SYSTEM = CODEX_ROOT / "skills" / ".system"
sys.path.insert(0, str(SYSTEM / "skill-installer" / "scripts"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


installer = load_module("video_cut_installer", SYSTEM / "skill-installer" / "scripts" / "install-skill-from-github.py")
validator = load_module("video_cut_validator", SYSTEM / "skill-creator" / "scripts" / "quick_validate.py")

OPENMONTAGE = [
    "ai-video-gen", "avatar-video", "create-video", "ffmpeg",
    "hyperframes-animation", "hyperframes-cli", "hyperframes-core", "hyperframes-creative",
    "hyperframes-media", "hyperframes-registry", "hyperframes", "media-use", "music-to-video",
    "remotion-to-hyperframes", "video-download", "video-edit", "video-toolkit", "video-translate",
    "video-understand", "website-to-video",
]
MARKETING = [
    "engineering/demo-video/skills/demo-video",
    "marketing-skill/skills/ad-creative",
    "marketing-skill/skills/campaign-analytics",
    "marketing-skill/skills/marketing-demand-acquisition",
    "marketing-skill/skills/paid-ads",
    "marketing-skill/video-content-strategist/skills/video-content-strategist",
]
REMOTION = [
    "remotion-best-practices", "remotion-captions", "remotion-create", "remotion-docs",
    "remotion-interactivity", "remotion-maps", "remotion-markup", "remotion-multimedia",
    "remotion-render", "remotion-saas", "remotion-studio", "remotion-upgrade",
]
SOURCES = [
    ("calesthio/OpenMontage", [f".agents/skills/{name}" for name in OPENMONTAGE]),
    ("alirezarezvani/claude-skills", MARKETING),
    ("remotion-dev/skills", [f"skills/{name}" for name in REMOTION]),
    ("luoluoluo22/jianying-editor-skill", ["."]),
]
ALIASES = {name: "video-cut-" + name for name in OPENMONTAGE + REMOTION + [Path(p).name for p in MARKETING] + ["jianying-editor"]}
TEXT_EXTENSIONS = {".md", ".py", ".mjs", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml", ".html", ".sh", ".ps1", ".toml", ".txt"}
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---(?:\n|$)", re.S)


class QuotedDumper(yaml.SafeDumper):
    pass


def quoted_string(dumper, value):
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style='"')


QuotedDumper.add_representer(str, quoted_string)


def dump_yaml(value, *, quoted=False):
    return yaml.dump(value, Dumper=QuotedDumper if quoted else yaml.SafeDumper, allow_unicode=True, sort_keys=False, width=110)


def mapped_text(text: str, source_file: Path) -> str:
    """Rename invocation tokens and only paths that resolve to sibling Skill folders."""
    for old, new in sorted(ALIASES.items(), key=lambda p: -len(p[0])):
        text = re.sub(r"\$" + re.escape(old) + r"(?![\w-])", lambda m: "$" + new, text)
        text = re.sub(r"(?<![\w:/])/" + re.escape(old) + r"(?![\w/.-])", lambda m: "/" + new, text)
        # Bare skill references, excluding the actual executable / package names.
        if old not in {"ffmpeg", "hyperframes", "remotion"}:
            text = text.replace("`" + old + "`", "`" + new + "`")
        # Explicit discovery paths (never repository URLs or framework imports).
        text = re.sub(r"((?:\.agents|\.agent|\.trae|\.claude|\.codex)/skills/)" + re.escape(old) + r"(?=/|\b)", lambda m: m.group(1) + new, text)
        # Markdown/code paths crossing out of a skill into another selected skill.
        pattern = re.compile(r"(?P<parents>(?:\.\./)+)" + re.escape(old) + r"(?=/)")

        def cross_skill(match):
            original_target = (source_file.parent / (match.group(0))).resolve()
            if (original_target / "SKILL.md").is_file():
                return match.group("parents") + new
            return match.group(0)

        text = pattern.sub(cross_skill, text)
    if "jianying-editor-skill" in str(source_file) and source_file.suffix in {".py", ".md"}:
        text = text.replace('"jianying-editor"', '"video-cut-jianying-editor"')
        text = text.replace("'jianying-editor'", "'video-cut-jianying-editor'")
        text = text.replace("skills/jianying-editor/", "skills/video-cut-jianying-editor/")
        text = text.replace("skills\\jianying-editor\\", "skills\\video-cut-jianying-editor\\")
        text = re.sub(r"skills([\\/])jianying-editor(?![\w-])", r"skills\1video-cut-jianying-editor", text)
    return text


def local_notes(record, old_name: str) -> str:
    name = ALIASES[old_name]
    extra = ""
    if old_name == "hyperframes":
        extra = """
The OpenMontage snapshot does not bundle every workflow named in the upstream router. For a
custom HTML video, load `$video-cut-hyperframes-core`, `$video-cut-hyperframes-creative`, and
`$video-cut-hyperframes-animation`. For a product demo, use `$video-cut-demo-video` or
`$video-cut-remotion-create`; for a music montage use `$video-cut-music-to-video`; for footage
cuts use `$video-cut-video-edit` or `$video-cut-jianying-editor`. The absent upstream workflows
are optional references, not locally registered Skills. Do not follow the upstream blanket
"install all workflows" command as part of loading this local router.
"""
    elif old_name == "video-toolkit":
        extra = """
This upstream Skill describes a separate `claude-code-video-toolkit` runtime and declares
macOS/Linux support. That external runtime was not installed here. Its fixed
`~/.openclaw/workspace/` paths are upstream examples, not paths on this machine. Keep this
Skill as a workflow reference until a native Windows implementation is configured. For
local editing/rendering use `$video-cut-video-edit`, `$video-cut-remotion-best-practices`,
or `$video-cut-jianying-editor` instead.
"""
    elif old_name == "jianying-editor":
        extra = f"""
The installed Python helpers locate the prefixed Skill via the global Codex discovery folder.
For a copied business script, initialize it in native PowerShell with:

```powershell
$env:JY_SKILL_ROOT = '{LIBRARY / name}'
```

Then follow `rules/setup.md`. Put new edit scripts in the user's project under `AI广告剪辑`,
not inside this reusable Skill. A usable JianYing installation, FFmpeg and the Python packages
in `requirements.txt` are separate runtime dependencies.
"""
    elif old_name == "demo-video":
        extra = "\nOn this machine output `build.ps1` with native Windows commands instead of the upstream `build.sh` example.\n"
    return f"""# Local installation rules

Source: [{record['repository']}]({record['repository_url']}); source commit
`{record['commit_from_github_zip_comment']}`. Original Skill: `{old_name}`.
Local invocation: `${name}`.

Apply these installation rules to the upstream examples in this package:

- Work in `{PROJECT}` or a task subdirectory below it. Keep new project content there.
- Use native Windows PowerShell, Python, Node.js and FFmpeg. Never launch local Docker,
  WSL, containers or another virtualization environment. Translate Bash-only commands
  into native Windows commands; do not run Unix installers on this machine.
- After browser work, close every unused tab to release memory.
- Use the locally registered `video-cut-` names for cross-Skill calls. Executable names,
  npm packages, API identifiers and engine flags keep their upstream names.
- Framework Skill refresh/install examples must preserve this namespace. Do not let a
  framework command replace these adapted packages or register unprefixed duplicates.
  The original repository snapshots remain in `AI广告剪辑/sources/` for review and updates.
- These packages install instructions and bundled resources. Before running a workflow,
  check its actual runtime dependencies and configured provider tools/credentials.

{extra.strip()}
"""


def adapt_jianying_bootstrap(destination: Path):
    global_candidate = 'os.path.join(os.environ.get("CODEX_HOME", os.path.join(os.path.expanduser("~"), ".codex")), "skills", "video-cut-jianying-editor")'
    canonical_candidate = repr(str(destination))
    for rel in ["scripts/utils/skill_path.py", "examples/_bootstrap.py"]:
        path = destination / rel
        text = path.read_text(encoding="utf-8")
        # Both upstream candidate builders define cwd just before assembling candidate lists.
        if global_candidate not in text:
            if rel.startswith("scripts"):
                text = text.replace("return parents + editor_paths", f"return [{global_candidate}, {canonical_candidate}] + parents + editor_paths")
            else:
                text = text.replace("    return [\n", f"    return [\n        {global_candidate},\n        {canonical_candidate},\n", 1)
        path.write_text(text, encoding="utf-8", newline="\n")
    # Make copied initialization examples find the global prefixed registration too.
    for rel in ["SKILL.md", "rules/setup.md"]:
        path = destination / rel
        text = path.read_text(encoding="utf-8")
        text = text.replace(f"    {global_candidate},\n", "").replace(f"    {canonical_candidate},\n", "")
        text = text.replace("skill_candidates = [\n    env_root,\n", f"skill_candidates = [\n    env_root,\n    {global_candidate},\n    {canonical_candidate},\n", 1)
        text = text.replace("skill_root = next((p for p in [\n    env_root,\n", f"skill_root = next((p for p in [\n    env_root,\n    {global_candidate},\n    {canonical_candidate},\n", 1)
        text = text.replace('"skills/jianying-editor"', '"skills/video-cut-jianying-editor"')
        path.write_text(text, encoding="utf-8", newline="\n")


def stage_skill(record, relative: str):
    source_root = Path(record["source_root"])
    source = source_root / relative
    installer._validate_relative_path(relative)
    installer._validate_skill(str(source), str(source_root))
    original_md = (source / "SKILL.md").read_text(encoding="utf-8")
    front = FRONTMATTER.match(original_md)
    if not front:
        raise ValueError(f"No valid frontmatter: {source}")
    metadata = yaml.safe_load(front.group(1))
    old_name = metadata["name"]
    name = ALIASES[old_name]
    installer._validate_skill_name(name)
    destination = LIBRARY / name
    if destination.exists() or (CODEX_ROOT / "skills" / name).exists():
        raise FileExistsError(f"Existing Skill will not be overwritten: {name}")
    installer._copy_skill(str(source), str(destination))
    changed = []
    for path in destination.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        revised = mapped_text(text, source / path.relative_to(destination))
        if revised != text:
            path.write_text(revised, encoding="utf-8", newline="\n")
            changed.append(path.relative_to(destination).as_posix())

    # Keep upstream metadata, moving non-Codex frontmatter fields under metadata.
    adapted_md = (destination / "SKILL.md").read_text(encoding="utf-8")
    match = FRONTMATTER.match(adapted_md)
    header = yaml.safe_load(match.group(1))
    header["name"] = name
    extra_keys = set(header) - {"name", "description", "license", "allowed-tools", "metadata"}
    header.setdefault("metadata", {})
    if extra_keys:
        header["metadata"]["upstream_fields"] = {key: header.pop(key) for key in sorted(extra_keys)}
    # Description angle brackets are disallowed by Codex's skill validator.
    header["description"] = header["description"].replace("<", "(").replace(">", ")").strip()
    header["metadata"]["video_cut_source"] = {
        "repository": record["repository"], "commit": record["commit_from_github_zip_comment"],
        "path": relative, "original_name": old_name,
    }
    openclaw = header["metadata"].get("openclaw", {})
    if openclaw.get("skillKey") == old_name:
        openclaw["skillKey"] = name
    local = destination / "references" / "local-installation.md"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(local_notes(record, old_name), encoding="utf-8", newline="\n")
    body = adapted_md[match.end():].lstrip("\n")
    body = "Read [local installation rules](references/local-installation.md) before running the upstream workflow.\n\n" + body
    (destination / "SKILL.md").write_text("---\n" + dump_yaml(header) + "---\n\n" + body, encoding="utf-8", newline="\n")
    changed.append("SKILL.md")

    # Preserve existing UI, dependencies and invocation policy; prefix visible skill names.
    ui_files = list(destination.rglob("agents/openai.yaml"))
    root_ui = destination / "agents" / "openai.yaml"
    if root_ui not in ui_files:
        ui_files.append(root_ui)
    for ui in ui_files:
        data = yaml.safe_load(ui.read_text(encoding="utf-8")) if ui.exists() else {}
        data = data or {}
        interface = data.setdefault("interface", {})
        is_root = ui == root_ui
        interface_name = name if is_root else ALIASES.get(ui.parent.parent.name, name)
        interface["display_name"] = interface_name
        if "short_description" not in interface:
            interface["short_description"] = header["description"][:60].rstrip()
        prompt = interface.get("default_prompt", "")
        if "$" + interface_name not in prompt:
            prompt = "$" + interface_name + ": " + (prompt if prompt else "Help with this video or advertising workflow.")
        interface["default_prompt"] = prompt
        ui.parent.mkdir(parents=True, exist_ok=True)
        ui.write_text(dump_yaml(data, quoted=True), encoding="utf-8", newline="\n")
        changed.append(ui.relative_to(destination).as_posix())

    if old_name == "jianying-editor":
        adapt_jianying_bootstrap(destination)
        changed += ["scripts/utils/skill_path.py", "examples/_bootstrap.py", "rules/setup.md"]
    for filename in ["LICENSE", "LICENSE.md", "LICENSE.txt", "NOTICE", "NOTICE.md"]:
        upstream_license = source_root / filename
        if upstream_license.is_file() and not (destination / filename).exists():
            shutil.copy2(upstream_license, destination / filename)
    valid, message = validator.validate_skill(destination)
    if not valid:
        raise ValueError(f"{name}: {message}")
    skill_file = destination / "SKILL.md"
    return {
        "name": name, "invocation": "$" + name, "original_name": old_name,
        "repository": record["repository"], "source_path": relative,
        "source_commit": record["commit_from_github_zip_comment"],
        "canonical_directory": str(destination), "registration_directory": str(CODEX_ROOT / "skills" / name),
        "description": header["description"], "adapted_files": sorted(set(changed)),
        "file_count": sum(1 for path in destination.rglob("*") if path.is_file()),
        "skill_md_sha256": hashlib.sha256(skill_file.read_bytes()).hexdigest(),
        "validation": message,
    }


def main():
    LIBRARY.mkdir(parents=True, exist_ok=True)
    records, installed = [], []
    # Preflight every target before copying, so existing user skills remain intact.
    for repository, paths in SOURCES:
        snapshot = PROJECT / "sources" / repository.replace("/", "__") / "download.json"
        record = json.loads(snapshot.read_text(encoding="utf-8"))
        records.append(record)
        for relative in paths:
            source = Path(record["source_root"]) / relative
            name = yaml.safe_load(FRONTMATTER.match((source / "SKILL.md").read_text(encoding="utf-8")).group(1))["name"]
            for target in [LIBRARY / ALIASES[name], CODEX_ROOT / "skills" / ALIASES[name]]:
                if target.exists():
                    raise FileExistsError(f"Existing destination: {target}")
    for (repository, paths), record in zip(SOURCES, records):
        for relative in paths:
            entry = stage_skill(record, relative)
            installed.append(entry)
            print(f"Validated {entry['name']} ({entry['file_count']} files)", flush=True)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_directory": str(PROJECT), "codex_skills_directory": str(CODEX_ROOT / "skills"),
        "status": "staged_and_validated", "registration_method": "Windows directory junctions",
        "source_repositories": records, "skill_count": len(installed), "skills": installed,
        "selection": "OpenMontage video/media Skills; six relevant advertising/video-planning Skills from claude-skills; all twelve official Remotion Skills; complete JianYing package. Official Remotion replaces duplicate OpenMontage Remotion bundles.",
        "runtime_installation": "Skill instructions/resources only; provider services and video rendering environments have not been installed or exercised.",
    }
    from repair_video_cut_references import repair
    repair(manifest)
    (PROJECT / "video-cut-install-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Prepared and validated {len(installed)} prefixed Skills.", flush=True)


if __name__ == "__main__":
    main()
