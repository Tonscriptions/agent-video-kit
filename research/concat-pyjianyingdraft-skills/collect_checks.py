"""Collect release facts and a small integration snapshot without running it."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
from collect_skill_companions import ROOT, get, metadata, snapshot


records_path = ROOT / "repository-metadata.json"
records = json.loads(records_path.read_text(encoding="utf-8"))
if not any(item.get("repository") == "isYangs/jianying-editor-skill" for item in records):
    records.append(metadata("isYangs/jianying-editor-skill"))
    records.sort(key=lambda item: item.get("stars", -1), reverse=True)
    records_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
is_yangs = next(item for item in records if item.get("requested_repository") == "isYangs/jianying-editor-skill")
print(json.dumps({"isYangs_metadata": is_yangs}, ensure_ascii=False), flush=True)
if "repository" in is_yangs:
    source = snapshot(is_yangs)
    print(json.dumps({"repository": source["repository"], "skills": source["skill_files"]}, ensure_ascii=False), flush=True)

checks = {"checked_at_utc": datetime.now(timezone.utc).isoformat()}
for repository in ["jub0t/concat", "GuanYixuan/pyJianYingDraft"]:
    try:
        data = json.loads(get(f"https://api.github.com/repos/{repository}/releases/latest"))
        checks[repository] = {"tag": data["tag_name"], "name": data["name"], "published_at": data["published_at"],
            "url": data["html_url"], "prerelease": data["prerelease"],
            "windows_assets": [{"name": item["name"], "size": item["size"]} for item in data["assets"] if "windows" in item["name"].lower() or item["name"].lower().endswith((".msi", ".exe"))]}
    except Exception as exc:
        checks[repository] = {"error": str(exc)}
try:
    pypi = json.loads(get("https://pypi.org/pypi/pyJianYingDraft/json"))
    checks["pypi"] = {key: pypi["info"].get(key) for key in ["name", "version", "requires_python", "requires_dist", "license"]}
except Exception as exc:
    checks["pypi"] = {"error": str(exc)}
(ROOT / "release-checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(checks, ensure_ascii=False), flush=True)

tree = json.loads((ROOT / "agentbox-tree.json").read_text(encoding="utf-8"))
revision = tree["sha"]
directory = ROOT / "sources" / "DreamLab-AI__agentbox"
directory.mkdir(parents=True, exist_ok=True)
for path in ["concatcontainer/README.md", "concatcontainer/Dockerfile", "docker-compose.concat.yml"]:
    contents = json.loads(get(f"https://api.github.com/repos/DreamLab-AI/agentbox/contents/{path}?ref={revision}"))
    payload = base64.b64decode(contents["content"])
    target = directory / "code" / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
skill_paths = [item["path"] for item in tree.get("tree", []) if item["type"] == "blob" and Path(item["path"]).name.upper() == "SKILL.MD"]
record = {"repository": "DreamLab-AI/agentbox", "source_commit": revision,
    "mode": "selected source files", "files": ["concatcontainer/README.md", "concatcontainer/Dockerfile", "docker-compose.concat.yml"],
    "skill_files": skill_paths, "concat_named_skill_files": [path for path in skill_paths if "concat" in path.lower()],
    "tree_truncated": tree.get("truncated"), "execution": "None: no containers or candidate code executed."}
(directory / "selected-source-snapshot.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"agentbox_skill_count": len(skill_paths), "concat_named_skills": record["concat_named_skill_files"]}, ensure_ascii=False), flush=True)
