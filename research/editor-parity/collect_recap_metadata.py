"""Read GitHub metadata and freeze only Concat's requested skill as research data."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent / "run-concat-recap"
REPOSITORIES = ["jub0t/concat", "zenstory-ai/video-recap-skills"]


def read_json(path):
    request = urllib.request.Request("https://api.github.com/" + path,
                                     headers={"User-Agent": "Codex-video-research"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def collect(repository):
    metadata = read_json("repos/" + repository)
    commit = read_json("repos/" + repository + "/commits/" + metadata["default_branch"])
    return {"repository": repository, "stars": metadata["stargazers_count"],
            "license": metadata.get("license"), "source_commit": commit["sha"],
            "url": metadata["html_url"], "checked_at_utc": datetime.now(timezone.utc).isoformat()}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(collect, REPOSITORIES))
    (ROOT / "github-metadata.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    concat = next(item for item in records if item["repository"] == "jub0t/concat")
    content = read_json("repos/jub0t/concat/contents/.claude/skills/run-concat/SKILL.md?ref=" + concat["source_commit"])
    (ROOT / "run-concat.upstream.SKILL.md").write_bytes(base64.b64decode(content["content"]))
    for record in records:
        print(json.dumps({key: record[key] for key in ["repository", "stars", "source_commit"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
