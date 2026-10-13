"""Freeze public Kdenlive harness text and license without running upstream code."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent / "open-only" / "sources" / "HKUDS__CLI-Anything"
PREFIX = "kdenlive/agent-harness/"
REPOSITORY = "HKUDS/CLI-Anything"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Codex-video-research"})
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read()


def save_text(path, data):
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe source path")
    destination = ROOT / "code" / Path(*relative.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    commit = json.loads(fetch(f"https://api.github.com/repos/{REPOSITORY}/commits/main"))["sha"]
    archive = fetch(f"https://codeload.github.com/{REPOSITORY}/zip/{commit}")
    files = []
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        for entry in bundle.infolist():
            if entry.is_dir():
                continue
            path = PurePosixPath(*PurePosixPath(entry.filename).parts[1:]).as_posix()
            if not (path.startswith(PREFIX) or path in {"LICENSE", "README.md"}):
                continue
            if Path(path).suffix.lower() not in {".md", ".py", ".toml", ".json", ".txt", ".yaml", ".yml"} and Path(path).name != "LICENSE":
                continue
            files.append(save_text(path, bundle.read(entry)))
    metadata = {"repository": REPOSITORY, "source_commit": commit,
                "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "scope": "Kdenlive harness plus root README/LICENSE; text-only, no upstream code executed",
                "files": sorted(files, key=lambda item: item["path"]),
                "skill_files": [item["path"] for item in files if Path(item["path"]).name == "SKILL.md"]}
    (ROOT / "source-metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: metadata[key] for key in {"repository", "source_commit", "skill_files"}}, ensure_ascii=False))
    print(f"Fetched {len(files)} text files; {sum(item['bytes'] for item in files)} bytes")


if __name__ == "__main__":
    main()
