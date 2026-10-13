"""Read public GitHub metadata and skill files; never install or execute repositories."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
REPOSITORIES = [
    "calesthio/OpenMontage",
    "coreyhaines31/marketingskills",
    "heygen-com/hyperframes",
    "sickn33/antigravity-awesome-skills",
    "alirezarezvani/claude-skills",
    "Vincentwei1021/video-shotcraft",
    "remotion-dev/skills",
    "browser-use/video-use",
    "luoluoluo22/jianying-editor-skill",
    "Agentchengfeng/chengfeng-videocut-skills",
    "FireRedTeam/FireRed-OpenStoryline",
    "irinabuht12-oss/marketing-skills",
    "ericosiu/ai-marketing-skills",
    "aaron-he-zhu/aaron-marketing-skills",
    "zubair-trabzada/ai-marketing-claude",
    "znyupup/ai-video-editing-skill",
    "digitalsamba/claude-code-video-toolkit",
    "robonuggets/hyperframes-helper",
    "leosssvip-dot/remotion-ad-video-skill",
    "isYangs/jianying-editor-skill",
    "liuluhaixiu/DaVinci-AutoEdit-Agent",
    "nopefallacy/vertical-video-editing-skills",
    "DotanVG/video-director-skill",
    "ivangfalco/ads-skills",
    "SamurAIGPT/Generative-Media-Skills",
    "appergb/ClipSkills",
    "liyupi/ai-promo-video-maker",
    "kangarooking/promo-creator-skills",
    "rendleyhq/video-editing-skill",
    "Killusions/open-video-use",
    "Rajbharti06/Ultimate-Video-Editing-Skills",
    "iart-ai/ad-video-skills",
    "riffkit/skills",
    "xsourabhsharma/remotion-marketing-video-skill",
    "ALBEDO-TABAI/video-expert-analyzer",
]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "AI-ad-skills-research",
        "Accept": "application/vnd.github+json" if "api.github.com" in url else "text/plain",
    })
    with urllib.request.urlopen(req, timeout=35) as response:
        return response.read()


def metadata(repo: str) -> dict:
    try:
        data = json.loads(get(f"https://api.github.com/repos/{repo}"))
        return {
            "requested_repository": repo,
            "repository": data["full_name"],
            "stars": data["stargazers_count"],
            "fork": data["fork"],
            "archived": data["archived"],
            "description": data.get("description"),
            "default_branch": data["default_branch"],
            "license": data.get("license"),
            "pushed_at": data["pushed_at"],
            "url": data["html_url"],
            "api_url": data["url"],
            "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {"requested_repository": repo, "error": str(exc)}


def inspect(repo: dict) -> dict:
    name = repo["repository"]
    branch = repo["default_branch"]
    destination = ROOT / "sources" / name.replace("/", "__")
    destination.mkdir(parents=True, exist_ok=True)
    result = {"repository": name, "branch": branch}
    try:
        tree = json.loads(get(f"https://api.github.com/repos/{name}/git/trees/{urllib.parse.quote(branch, safe='')}?recursive=1"))
        result["tree_sha"] = tree.get("sha")
        result["tree_truncated"] = tree.get("truncated", False)
        result["skill_paths"] = [n["path"] for n in tree.get("tree", []) if n["type"] == "blob" and n["path"].endswith("SKILL.md")]
        result["license_paths"] = [n["path"] for n in tree.get("tree", []) if n["type"] == "blob" and n["path"].rsplit("/", 1)[-1].lower() in {"license", "license.md", "license.txt", "copying"}][:15]
        result["readme_paths"] = [n["path"] for n in tree.get("tree", []) if n["type"] == "blob" and "/" not in n["path"] and n["path"].lower().startswith("readme")]
    except Exception as exc:
        result["tree_error"] = str(exc)
    ref = branch
    for path in result.get("readme_paths", ["README.md"])[:2]:
        try:
            body = get(f"https://raw.githubusercontent.com/{name}/{ref}/{urllib.parse.quote(path, safe='/')}")
            (destination / path).write_bytes(body)
        except Exception as exc:
            result.setdefault("readme_errors", {})[path] = str(exc)
    return result


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "metadata"
    if mode == "metadata":
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            entries = list(pool.map(metadata, REPOSITORIES))
        entries.sort(key=lambda x: x.get("stars", -1), reverse=True)
        snapshot = {"scope": "Public GitHub repositories discovered by topic search; not an exhaustive global ranking.", "repositories": entries}
        (ROOT / "github-repository-snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        for repo in entries:
            print(json.dumps({k: repo.get(k) for k in ["repository", "stars", "license", "fork", "archived", "error"]}, ensure_ascii=True))
    elif mode == "inspect":
        snapshot = json.loads((ROOT / "github-repository-snapshot.json").read_text(encoding="utf-8"))
        requested = set(sys.argv[2:])
        repositories = [r for r in snapshot["repositories"] if "repository" in r and (not requested or r["repository"] in requested)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            inspections = list(pool.map(inspect, repositories))
        existing_path = ROOT / "skill-file-inspections.json"
        existing = json.loads(existing_path.read_text(encoding="utf-8")) if existing_path.exists() else []
        merged = {row["repository"]: row for row in existing + inspections}
        existing_path.write_text(json.dumps(list(merged.values()), ensure_ascii=False, indent=2), encoding="utf-8")
        for row in inspections:
            print(json.dumps({"repository": row["repository"], "count": len(row.get("skill_paths", [])), "skills": row.get("skill_paths", [])[:25], "tree_error": row.get("tree_error"), "truncated": row.get("tree_truncated")}, ensure_ascii=True))
    else:
        raise SystemExit(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
