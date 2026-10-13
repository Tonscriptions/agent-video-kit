"""Download the four selected repositories using Codex's skill installer helper."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
INSTALLER_DIR = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / ".system" / "skill-installer" / "scripts"
sys.path.insert(0, str(INSTALLER_DIR))
spec = importlib.util.spec_from_file_location("codex_skill_installer", INSTALLER_DIR / "install-skill-from-github.py")
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)
socket.setdefaulttimeout(45)

REPOS = {
    "openmontage": (2, "calesthio/OpenMontage"),
    "marketing": (8, "alirezarezvani/claude-skills"),
    "remotion": (10, "remotion-dev/skills"),
    "jianying": (12, "luoluoluo22/jianying-editor-skill"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("key", choices=REPOS)
    args = parser.parse_args()
    rank, repository = REPOS[args.key]
    owner, repo = repository.split("/")
    destination = PROJECT / "sources" / f"{owner}__{repo}"
    destination.mkdir(parents=True, exist_ok=True)
    record_path = destination / "download.json"
    if record_path.exists():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if (Path(record["source_root"]) / "SKILL.md").is_file() or any(Path(record["source_root"]).rglob("SKILL.md")):
            print(json.dumps({"status": "already_downloaded", **record}, ensure_ascii=False), flush=True)
            return
    print(f"Downloading {repository} (main) using the Codex installer helper", flush=True)
    source_root = Path(installer._download_repo_zip(owner, repo, "main", str(destination)))
    archive = destination / "repo.zip"
    # GitHub puts the exact source commit ID into its ZIP comment.
    with zipfile.ZipFile(archive) as zf:
        comment = zf.comment.decode("utf-8", errors="replace")
    commit = comment if len(comment) == 40 and all(c in "0123456789abcdef" for c in comment) else None
    record = {
        "rank_in_saved_report": rank,
        "repository": repository,
        "repository_url": f"https://github.com/{repository}",
        "requested_ref": "main",
        "commit_from_github_zip_comment": commit,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source_root),
        "archive_path": str(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": hashlib.file_digest(archive.open("rb"), "sha256").hexdigest(),
        "skill_file_count": sum(1 for _ in source_root.rglob("SKILL.md")),
        "download_method": "Codex skill-installer _download_repo_zip (codeload HTTPS)",
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "downloaded", **record}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
