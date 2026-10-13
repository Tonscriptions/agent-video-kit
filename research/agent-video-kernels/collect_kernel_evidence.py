"""Read public repository metadata and source archives; never run candidate software."""
from __future__ import annotations

import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
REPOSITORIES = [
    "GuanYixuan/pyJianYingDraft", "GuanYixuan/pyCapCut", "sun-guannan/VectCutAPI",
    "Hommy-master/capcut-mate", "AiPersonacademy/capcut-mcp", "renezander030/capcut-cli",
    "MHughesDev/video-mcp", "AH64-dll/OpenEdit", "craftled/openklip",
    "Mas-inx/lumen-ai-video-editor", "x777/frontstage", "jub0t/Concat",
    "ishan-parihar/openscript", "rdh073/verbreel-engine", "PlbKin190/video-editor-mcp",
    "PlbKin190/video-atelier-mcp", "browser-use/video-use",
]
EXTENSIONS = {".md", ".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".yaml", ".yml", ".toml", ".rs", ".txt", ".cs"}


def request(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AI-ad-agent-kernel-research", "Accept": "application/vnd.github+json" if "api.github.com" in url else "*/*"})
    with urllib.request.urlopen(req, timeout=40) as response:
        return response.read()


def metadata(repository):
    try:
        data = json.loads(request(f"https://api.github.com/repos/{repository}"))
        return {
            "requested_repository": repository, "repository": data["full_name"],
            "url": data["html_url"], "stars": data["stargazers_count"], "fork": data["fork"],
            "archived": data["archived"], "default_branch": data["default_branch"],
            "description": data.get("description"), "license": data.get("license"),
            "pushed_at": data["pushed_at"], "created_at": data["created_at"], "size_kib": data["size"],
            "metadata_api": data["url"], "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {"requested_repository": repository, "error": str(exc)}


def source_snapshot(record):
    repository = record["repository"]
    branch = record["default_branch"]
    destination = ROOT / "sources" / repository.replace("/", "__")
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_path = destination / "source-snapshot.json"
    if snapshot_path.exists():
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    url = f"https://codeload.github.com/{repository}/zip/{branch}"
    print(f"Reading source archive: {repository}", flush=True)
    payload = request(url)
    extracted = destination / "code"
    extracted.mkdir(exist_ok=True)
    files = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        comment = archive.comment.decode("utf-8", errors="replace")
        commit = comment if len(comment) == 40 and all(c in "0123456789abcdef" for c in comment) else None
        for member in archive.infolist():
            if member.is_dir():
                continue
            relative = Path(*member.filename.split("/")[1:])
            if not relative.parts or any(part in {"node_modules", ".git", "vendor", ".venv"} for part in relative.parts):
                continue
            if relative.name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock"}:
                continue
            if relative.suffix.lower() not in EXTENSIONS and not relative.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                continue
            target = extracted / relative
            if not target.resolve().is_relative_to(extracted.resolve()):
                raise ValueError(f"Unsafe archive path: {member.filename}")
            content = archive.read(member)
            try:
                content.decode("utf-8-sig")
            except UnicodeError:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            files.append(relative.as_posix())
    result = {
        "repository": repository, "branch": branch, "source_commit": commit,
        "archive_url": url, "archive_sha256": hashlib.sha256(payload).hexdigest(), "archive_bytes_read": len(payload),
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(), "code_directory": str(extracted),
        "text_file_count": len(files), "files": files,
        "execution": "None: source inspection only; no installation, rendering, Docker, WSL or browser tabs.",
    }
    snapshot_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["metadata", "sources"])
    parser.add_argument("repositories", nargs="*")
    args = parser.parse_args()
    if args.mode == "metadata":
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(metadata, REPOSITORIES))
        records.sort(key=lambda item: item.get("stars", -1), reverse=True)
        (ROOT / "repository-metadata.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for record in records:
            print(json.dumps({key: record.get(key) for key in ["repository", "stars", "license", "size_kib", "pushed_at", "error"]}, ensure_ascii=False), flush=True)
    else:
        records = json.loads((ROOT / "repository-metadata.json").read_text(encoding="utf-8"))
        selected = [record for record in records if record.get("repository") in args.repositories]
        if len(selected) != len(set(args.repositories)):
            raise ValueError("Some requested repositories have no successful metadata record.")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(source_snapshot, record): record["repository"] for record in selected}
            for future in concurrent.futures.as_completed(futures):
                repo = futures[future]
                try:
                    result = future.result()
                    print(json.dumps({"repository": repo, "commit": result["source_commit"], "bytes": result["archive_bytes_read"], "text_files": result["text_file_count"]}, ensure_ascii=False), flush=True)
                except Exception as exc:
                    print(json.dumps({"repository": repo, "error": str(exc)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
