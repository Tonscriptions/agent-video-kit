"""Read public GitHub metadata and source text; never install candidate code."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent


def get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "AI-ad-companion-skill-research", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def search(query):
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": 30})
    try:
        data = json.loads(get(url))
        return {"query": query, "total_count": data["total_count"], "url": url,
            "items": [{key: item.get(key) for key in ["full_name", "html_url", "description", "stargazers_count", "fork", "default_branch", "size"]} for item in data["items"]]}
    except Exception as exc:
        return {"query": query, "error": str(exc)}


def metadata(repository):
    try:
        data = json.loads(get(f"https://api.github.com/repos/{repository}"))
        return {"repository": data["full_name"], "requested_repository": repository,
            "url": data["html_url"], "stars": data["stargazers_count"], "fork": data["fork"],
            "parent": (data.get("parent") or {}).get("full_name"), "archived": data["archived"],
            "branch": data["default_branch"], "license": data.get("license"), "size_kib": data["size"],
            "pushed_at": data["pushed_at"], "description": data.get("description"),
            "checked_at_utc": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        return {"requested_repository": repository, "error": str(exc)}


def snapshot(item):
    repository = item["repository"]
    directory = ROOT / "sources" / repository.replace("/", "__")
    index_path = directory / "source-snapshot.json"
    if index_path.exists():
        return json.loads(index_path.read_text(encoding="utf-8"))
    url = f"https://codeload.github.com/{repository}/zip/{item['branch']}"
    payload = get(url)
    code = directory / "code"
    code.mkdir(parents=True, exist_ok=True)
    files = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        commit = archive.comment.decode("ascii", errors="replace")
        for member in archive.infolist():
            parts = member.filename.split("/")[1:]
            if member.is_dir() or not parts or any(part in {"node_modules", "vendor", ".git", ".venv", "target"} for part in parts):
                continue
            relative = Path(*parts)
            if relative.name in {"package-lock.json", "pnpm-lock.yaml", "uv.lock"}:
                continue
            if relative.suffix.lower() not in {".md", ".py", ".ts", ".js", ".mjs", ".json", ".toml", ".yml", ".yaml", ".txt", ".ps1", ".rs"} and not relative.name.upper().startswith(("LICENSE", "NOTICE")):
                continue
            data = archive.read(member)
            try:
                data.decode("utf-8-sig")
            except UnicodeError:
                continue
            target = code / relative
            if not target.resolve().is_relative_to(code.resolve()):
                raise ValueError(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files.append(relative.as_posix())
    skills = [file for file in files if Path(file).name.upper() == "SKILL.MD"]
    record = {"repository": repository, "source_commit": commit, "archive_url": url,
        "archive_bytes_read": len(payload), "archive_sha256": hashlib.sha256(payload).hexdigest(),
        "text_files": len(files), "skill_files": skills, "files": files, "code_directory": str(code),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(), "execution": "None: source-text inspection only."}
    index_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main():
    mode, *arguments = sys.argv[1:]
    if mode == "search":
        queries = ["jianying skill in:name,description,readme", '"pyJianYingDraft" "SKILL.md" in:readme', '"concat-cli" in:readme']
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(search, queries))
        (ROOT / "github-repository-search.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for record in results:
            print(json.dumps(record, ensure_ascii=False), flush=True)
        rate = json.loads(get("https://api.github.com/rate_limit"))
        print(json.dumps({"rate": rate["resources"]}, ensure_ascii=False))
    elif mode == "metadata":
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(metadata, arguments))
        results.sort(key=lambda item: item.get("stars", -1), reverse=True)
        (ROOT / "repository-metadata.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for record in results:
            print(json.dumps({key: record.get(key) for key in ["repository", "stars", "fork", "parent", "size_kib", "license", "error"]}, ensure_ascii=False), flush=True)
    elif mode == "sources":
        data = json.loads((ROOT / "repository-metadata.json").read_text(encoding="utf-8"))
        selected = [item for item in data if item.get("repository") in arguments]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(snapshot, item): item["repository"] for item in selected}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    print(json.dumps({key: result.get(key) for key in ["repository", "source_commit", "archive_bytes_read", "text_files", "skill_files"]}, ensure_ascii=False), flush=True)
                except Exception as exc:
                    print(json.dumps({"repository": futures[future], "error": str(exc)}, ensure_ascii=False), flush=True)
    else:
        raise ValueError(mode)


if __name__ == "__main__":
    main()
