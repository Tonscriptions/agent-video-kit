"""Capture public upstream metadata and license/readme evidence; no media download.

Native Python stdlib only. This research helper does not install or execute upstream code.
"""
from __future__ import annotations

import concurrent.futures
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.parse

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/validation/evidence/lut-research-20261024-r1"
REPOS = [
    "t3mujinpack/t3mujinpack",
    "andreavolpato/spektrafilm",
    "shenmintao/V-Log-Alchemy",
    "cedeber/hald-clut",
    "NatronGitHub/clut",
    "stripedpurple/color-grading-luts",
    "sguyader/FilmSim",
    "ChristophWurst/haldclut",
    "frogbf/Film-Luts",
    "slaycamera/luts",
]
ASSET_SUFFIXES = {".cube", ".3dl", ".csp", ".dat", ".png", ".tif", ".tiff", ".dtstyle", ".pp3"}
TRANSPORT = "https"


def get(url: str) -> bytes:
    # curl.exe uses native Windows networking; urllib connections were reset on
    # this host. Arguments are passed as an array, with no shell or credentials.
    response = subprocess.run([
        "curl.exe", "--fail", "--silent", "--show-error", "--location",
        "--connect-timeout", "10", "--max-time", "45", "--retry", "1",
        "--user-agent", "agent-video-kit-lut-research/1.0",
        "--header", "Accept: application/vnd.github+json" if "api.github.com" in url else "Accept: */*",
        url,
    ], capture_output=True, check=False)
    if response.returncode:
        raise RuntimeError(response.stderr.decode("utf-8", errors="replace"))
    return response.stdout


def capture(repo: str) -> dict:
    target = OUT / repo.replace("/", "--")
    target.mkdir(parents=True, exist_ok=True)
    api = "https://api.github.com/repos/" + repo
    def cached(name: str, url: str) -> bytes:
        path = target / name
        if path.exists():
            return path.read_bytes()
        data = get(url)
        path.write_bytes(data)
        return data

    metadata_bytes = cached("repository.json", api)
    metadata = json.loads(metadata_bytes)
    (target / "repository.json").write_bytes(metadata_bytes)
    commit_bytes = cached("commit.json", api + "/commits/" + urllib.parse.quote(metadata["default_branch"], safe=""))
    commit = json.loads(commit_bytes)
    (target / "commit.json").write_bytes(commit_bytes)
    sha = commit["sha"]
    tree_bytes = cached("tree.json", api + "/git/trees/" + sha + "?recursive=1")
    tree = json.loads(tree_bytes)
    (target / "tree.json").write_bytes(tree_bytes)
    files = [entry for entry in tree["tree"] if entry["type"] == "blob"]
    notices = [entry for entry in files if "/" not in entry["path"] and (
        entry["path"].lower().startswith(("readme", "license", "copying", "notice"))
        or entry["path"] == "SPEKTRAFILM_LICENSE.txt"
    )]
    evidence = []
    snapshot = ROOT / "sources/lut-research-20261024" / repo.replace("/", "--")
    if TRANSPORT == "git-ssh" and not (snapshot / ".git").exists():
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "git", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
            "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
            "git@github.com:" + repo + ".git", str(snapshot),
        ], capture_output=True, check=True, timeout=90)
    for entry in notices:
        path = entry["path"]
        url = "https://raw.githubusercontent.com/" + repo + "/" + sha + "/" + urllib.parse.quote(path)
        if TRANSPORT == "git-ssh":
            content = subprocess.run([
                "git", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
                "-C", str(snapshot), "show", sha + ":" + path,
            ], capture_output=True, check=True, timeout=60).stdout
        else:
            content = cached(path, url)
        blob_id = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if blob_id != entry["sha"]:
            raise ValueError("Notice bytes do not match pinned upstream Git blob: " + path)
        (target / path).write_bytes(content)
        evidence.append({"path": path, "url": url, "sha256": hashlib.sha256(content).hexdigest()})
    counts: dict[str, int] = {}
    assets = []
    for entry in files:
        suffix = Path(entry["path"]).suffix.lower()
        if suffix in ASSET_SUFFIXES:
            counts[suffix] = counts.get(suffix, 0) + 1
            assets.append({"path": entry["path"], "bytes": entry.get("size"), "git_blob": entry["sha"]})
    result = {
        "repository": repo,
        "url": metadata["html_url"],
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stars": metadata["stargazers_count"],
        "default_branch": metadata["default_branch"],
        "commit": sha,
        "commit_date": commit["commit"]["committer"]["date"],
        "github_detected_license": (metadata.get("license") or {}).get("spdx_id"),
        "tree_truncated": tree.get("truncated"),
        "extension_counts_not_unique_looks": counts,
        "notice_evidence": evidence,
        "notice_transport": TRANSPORT,
        "candidate_files_not_all_looks": assets,
    }
    (target / "capture.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    global TRANSPORT
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=("https", "git-ssh"), default="https")
    args = parser.parse_args()
    TRANSPORT = args.transport
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    # Git mutations stay sequential; independent read-only HTTPS fetches may overlap.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1 if TRANSPORT == "git-ssh" else 4) as executor:
        tasks = {executor.submit(capture, repo): repo for repo in REPOS}
        for task in concurrent.futures.as_completed(tasks):
            try:
                result = task.result()
                results.append(result)
                print(json.dumps({key: result[key] for key in ("repository", "stars", "commit", "github_detected_license", "extension_counts_not_unique_looks")}, ensure_ascii=False), flush=True)
            except Exception as error:
                result = {"repository": tasks[task], "error": str(error)}
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
    results.sort(key=lambda item: item.get("stars", -1), reverse=True)
    (OUT / "upstreams.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
