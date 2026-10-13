"""Read public metadata and text snapshots; never execute repository code."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent / "open-only"
ROOT.mkdir(parents=True, exist_ok=True)
REPOSITORIES = {
    "matrodrigs/shotcut-mcp": True,
    "dcc-mcp/dcc-mcp-kdenlive": True,
    "AMMIROSOH/Kdenlive-mcp": True,
    "mltframework/shotcut": False,
    "KDE/kdenlive": False,
    "HKUDS/CLI-Anything": False,
    "heygen-com/hyperframes": False,
    "Mas-inx/lumen-ai-video-editor": False,
    "jub0t/concat": False,
}
TEXT_SUFFIXES = {".md", ".mdx", ".py", ".toml", ".json", ".yaml", ".yml", ".ts", ".js", ".rst", ".txt"}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Codex-video-research", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read()


def collect(repository, snapshot):
    result = {"repository": repository, "checked_at_utc": datetime.now(timezone.utc).isoformat()}
    branch = "main"
    try:
        meta = json.loads(fetch("https://api.github.com/repos/" + repository))
        branch = meta["default_branch"]
        result.update(stars=meta["stargazers_count"], branch=branch, license=meta.get("license"), pushed_at=meta["pushed_at"], url=meta["html_url"])
    except Exception as error:
        result["metadata_error"] = str(error)
    if snapshot:
        try:
            archive = fetch("https://codeload.github.com/" + repository + "/zip/refs/heads/" + branch)
            target = ROOT / "sources" / repository.replace("/", "__")
            target.mkdir(parents=True, exist_ok=True)
            archive_path = target / "source.zip"
            archive_path.write_bytes(archive)
            skill_files, count = [], 0
            with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
                result["source_commit"] = zipped.comment.decode("ascii", errors="replace")
                for member in zipped.infolist():
                    parts = PurePosixPath(member.filename).parts[1:]
                    if not parts or member.is_dir() or ".." in parts:
                        continue
                    if any(part in {"node_modules", ".git", "vendor"} for part in parts):
                        continue
                    relative = PurePosixPath(*parts)
                    if relative.suffix not in TEXT_SUFFIXES and relative.name not in {"LICENSE", "COPYING", "NOTICE"}:
                        continue
                    if member.file_size > 1_500_000 or relative.name.endswith("lock.json") or relative.name == "pnpm-lock.yaml":
                        continue
                    data = zipped.read(member)
                    data.decode("utf-8")
                    destination = target / "code" / Path(*parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
                    count += 1
                    if relative.name == "SKILL.md":
                        skill_files.append(relative.as_posix())
            result.update(text_file_count=count, skill_files=skill_files, archive_sha256=hashlib.sha256(archive).hexdigest(), archive_bytes=len(archive))
        except Exception as error:
            result["snapshot_error"] = str(error)
    return result


results = []
with ThreadPoolExecutor(max_workers=4) as pool:
    tasks = {pool.submit(collect, repo, snapshot): repo for repo, snapshot in REPOSITORIES.items()}
    for task in as_completed(tasks):
        result = task.result()
        results.append(result)
        print(json.dumps({key: value for key, value in result.items() if key in {"repository", "stars", "source_commit", "skill_files", "metadata_error", "snapshot_error", "text_file_count"}}, ensure_ascii=False), flush=True)
results.sort(key=lambda item: item.get("stars", -1), reverse=True)
(ROOT / "repository-metadata.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
