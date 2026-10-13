"""Fetch selected public source files only, without executing repository code."""
import base64
import hashlib
import json
from pathlib import Path

from collect_kernel_evidence import ROOT, metadata, request


def selected_source(repository, selected_paths):
    record = next(item for item in records if item.get("repository") == repository)
    branch = record["default_branch"]
    tree = json.loads(request(f"https://api.github.com/repos/{repository}/git/trees/{branch}?recursive=1"))
    commit = tree["sha"]
    directory = ROOT / "sources" / repository.replace("/", "__")
    code = directory / "code"
    code.mkdir(parents=True, exist_ok=True)
    files = []
    available = {item["path"] for item in tree["tree"] if item["type"] == "blob"}
    (directory / "tree-paths.json").write_text(json.dumps(sorted(available), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if repository == "AH64-dll/OpenEdit":
        selected_paths += sorted(path for path in available if path.endswith(".py") and ("mcp" in path.lower() or path.endswith("/server.py")))[:4]
    selected_paths = list(dict.fromkeys(selected_paths))
    for path in selected_paths:
        if path not in available:
            print(f"Missing {repository}/{path}", flush=True)
            continue
        content = json.loads(request(f"https://api.github.com/repos/{repository}/contents/{path}?ref={commit}"))
        payload = base64.b64decode(content["content"])
        target = code / path
        if not target.resolve().is_relative_to(code.resolve()):
            raise ValueError(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        files.append({"path": path, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})
    result = {"repository": repository, "branch": branch, "source_commit": commit,
              "mode": "selected source files", "files": files,
              "tree_paths": sorted(available), "execution": "None: read-only source inspection."}
    (directory / "selected-source-snapshot.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"repository": repository, "commit": commit, "selected_files": len(files)}, ensure_ascii=False), flush=True)


records_path = ROOT / "repository-metadata.json"
records = json.loads(records_path.read_text(encoding="utf-8"))
if not any(item.get("repository") == "Monet-AI-Editor/Monet" for item in records):
    records.append(metadata("Monet-AI-Editor/Monet"))
    records.sort(key=lambda item: item.get("stars", -1), reverse=True)
    records_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

selected_source("AH64-dll/OpenEdit", ["README.md", "INSTALL.md", "pyproject.toml",
    "open_edit/mcp/server.py", "src/open_edit/mcp/server.py", "docs/agent-configure.md"])
selected_source("Monet-AI-Editor/Monet", ["README.md", "package.json", "LICENSE"])

record = next(item for item in records if item.get("repository") == "Monet-AI-Editor/Monet")
print(json.dumps({key: record.get(key) for key in ["repository", "stars", "license"]}, ensure_ascii=False))
