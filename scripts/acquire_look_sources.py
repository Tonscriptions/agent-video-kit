"""Acquire only pinned open look data via native Git; never execute upstream code."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/validation/evidence/lut-research-20261024-r1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--git', default=shutil.which('git'), help='Existing native Git executable; modern Git is required for partial clones')
    args = parser.parse_args()
    if not args.git:
        raise RuntimeError('An existing native Git executable is required')
    captures = []
    for repo, suffix, prefix in [
        ("t3mujinpack--t3mujinpack", ".png", "haldcluts/"),
        ("stripedpurple--color-grading-luts", ".cube", ""),
    ]:
        metadata = json.loads((EVIDENCE / repo / "capture.json").read_bytes())
        snapshot = ROOT / "sources/lut-research-20261024" / repo
        if not (snapshot / ".git").is_dir():
            raise RuntimeError("Missing pinned Git snapshot: " + str(snapshot))
        selected = [x for x in metadata["candidate_files_not_all_looks"]
                    if x["path"].startswith(prefix) and x["path"].lower().endswith(suffix)]
        command = [args.git, "-c", "core.autocrlf=false", "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-C", str(snapshot),
                   "restore", "--source", metadata["commit"], "--worktree", "--", *[x["path"] for x in selected]]
        subprocess.run(command, check=True, timeout=600)
        rows = []
        for entry in selected:
            path = snapshot / entry["path"]
            data = path.read_bytes()
            actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if actual != entry["git_blob"]:
                raise RuntimeError("Pinned Git blob mismatch: " + str(path))
            rows.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(data).hexdigest(),
                         "bytes": len(data), "upstream_path": entry["path"], "git_blob": actual})
        captures.append({"repository": metadata["repository"], "commit": metadata["commit"], "files": rows})
        print(json.dumps({"repository": metadata["repository"], "files": len(rows), "bytes": sum(r["bytes"] for r in rows)}), flush=True)
    output = ROOT / "sources/lut-research-20261024/look-sources.json"
    output.write_text(json.dumps(captures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
