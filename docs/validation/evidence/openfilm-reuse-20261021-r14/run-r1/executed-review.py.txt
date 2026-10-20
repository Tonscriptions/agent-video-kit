"""Pinned OpenFilm reuse review; native source tests, no install or browser."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import urllib.request
import zipfile

COMMIT = "53156ac5818d8bad3f2c356043b376b3eebd95ba"
ZIP_SHA = "c106830d98d75080f2aba64ad41cb7d95bee606a48c0cd4d913bf3166cbdb192"
ORIGINAL_TESTS = (
    "packages/openfilm/studio/server/fcpxml.test.mjs",
    "packages/openfilm/studio/server/diagnostics.test.mjs",
    "packages/openfilm/src/problems.test.mjs",
    "apps/desktop/src/pi-config.test.mjs",
)
CANDIDATES = (
    "packages/openfilm/studio/server/nle.mjs",
    "packages/openfilm/studio/server/fcpxml.mjs",
    "apps/desktop/src/pi-config.mjs",
    "packages/openfilm/studio/server/diagnostics.mjs",
    "packages/openfilm/src/look.mjs",
    "packages/openfilm/studio/server/preview-cache.mjs",
    "packages/openfilm/studio/server/exports.mjs",
)


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--capture", action="store_true", help="read-only GitHub API metadata")
    a = p.parse_args()
    root = a.project_root.resolve()
    evidence = a.output.resolve()
    assert not evidence.exists(), "Use a fresh evidence directory"
    assert evidence.is_relative_to(root), "Evidence must remain in this E-drive project"
    scratch = root / "product/.runtime/openfilm-r14-source" / evidence.name
    assert not scratch.exists()
    evidence.mkdir(parents=True)
    scratch.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location("frozen_runner", root / "scripts/run_frozen_regression.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frozen_before = module.frozen()
    record = {
        "status": "running", "scope": "research-only; no product feature acceptance",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "upstream_commit": COMMIT, "script_sha256": sha(Path(__file__).read_bytes()),
        "native_windows": os.name == "nt", "virtualization": False,
        "dependencies_installed": False, "browser_started": False,
        "cloud_provider_or_model_called": False, "new_skills_installed": 0,
        "new_product_tests": 0, "new_rendered_media": 0, "calls": [],
        "frozen_before": frozen_before,
    }
    (evidence / "executed-review.py.txt").write_bytes(Path(__file__).read_bytes())
    try:
        if a.capture:
            record["api"] = {}
            for key, path in (("repository", ""), ("commit", "/commits/main"), ("latest-release", "/releases/latest")):
                url = "https://api.github.com/repos/openfilm/openfilm" + path
                request = urllib.request.Request(url, headers={"User-Agent": "agent-video-kit-source-review", "Accept": "application/vnd.github+json"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = response.read(4 << 20)
                    meta = {"url": url, "final_url": response.url, "http_date": response.headers.get("Date"),
                            "etag": response.headers.get("ETag"), "sha256": sha(data),
                            "received_at_utc": datetime.now(timezone.utc).isoformat()}
                (evidence / (key + ".json")).write_bytes(data)
                record["api"][key] = meta
            commit = json.loads((evidence / "commit.json").read_bytes())
            assert commit["sha"] == COMMIT, "Upstream changed: review the new revision instead"
        archive = root / "sources/upstream/openfilm-024-20261021-r13/repo.zip"
        raw = archive.read_bytes()
        assert sha(raw) == "sha256:" + ZIP_SHA
        record["archive"] = {"path": archive.relative_to(root).as_posix(), "bytes": len(raw), "sha256": sha(raw)}
        files = {}
        with zipfile.ZipFile(archive) as z:
            assert sum(x.file_size for x in z.infolist()) < 64 << 20
            for entry in z.infolist():
                if entry.is_dir():
                    continue
                name = PurePosixPath(entry.filename)
                assert not name.is_absolute() and ".." not in name.parts
                assert name.parts[0] == "openfilm-" + COMMIT
                assert (entry.external_attr >> 16) & 0o170000 != 0o120000
                rel = PurePosixPath(*name.parts[1:]).as_posix()
                assert rel not in files
                data = z.read(entry)
                files[rel] = data
                target = scratch / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        record["source_files"] = len(files)
        write(evidence / "source-tree.json", {n: {"bytes": len(d), "sha256": sha(d)} for n, d in sorted(files.items())})
        for n in ("LICENSE", "THIRD_PARTY_NOTICES.md", "TRADEMARK.md"):
            (evidence / (n + ".txt")).write_bytes(files[n])
        record["modules"] = {n: {"lines": len(files[n].splitlines()), "bytes": len(files[n]), "sha256": sha(files[n])} for n in CANDIDATES}
        # Static import closure only: records why these pure pieces do not need Studio, Electron or browser packages.
        closures = {}
        for entry in CANDIDATES[:4]:
            queue, local, external = [entry], set(), set()
            while queue:
                name = queue.pop()
                if name in local:
                    continue
                local.add(name)
                imports = re.findall(r"^import\s+.*?\sfrom\s+['\"]([^'\"]+)", files[name].decode(), re.M)
                for item in imports:
                    if item.startswith("."):
                        resolved = os.path.normpath(str(PurePosixPath(name).parent / item)).replace("\\", "/")
                        assert resolved in files, resolved
                        queue.append(resolved)
                    else:
                        external.add(item)
            closures[entry] = {"local": sorted(local), "external": sorted(external)}
        record["static_import_closures"] = closures
        node = shutil.which("node")
        assert node
        temp = scratch / "native-temp"
        temp.mkdir()
        env = dict(os.environ, TEMP=str(temp), TMP=str(temp), OPENFILM_HOME=str(scratch / "home"))

        def run(label, args):
            command = [node, *args]
            result = subprocess.run(command, cwd=scratch, env=env, capture_output=True, timeout=120)
            (evidence / (label + ".stdout.txt")).write_bytes(result.stdout)
            (evidence / (label + ".stderr.txt")).write_bytes(result.stderr)
            call = {"label": label, "command": command, "cwd": str(scratch), "exit_code": result.returncode,
                    "stdout_sha256": sha(result.stdout), "stderr_sha256": sha(result.stderr)}
            record["calls"].append(call)
            assert result.returncode == 0, (label, result.stderr.decode(errors="replace")[-1000:])
            return result.stdout.decode("utf8")

        record["node_version"] = run("node-version", ["--version"]).strip()
        originals = run("original-tests", ["--test", "--test-concurrency=1", "--test-reporter=tap", *ORIGINAL_TESTS])
        record["original_tests"] = {"files": {n: sha(files[n]) for n in ORIGINAL_TESTS},
                                     "summary": {k: int(v) for k, v in re.findall(r"^# (tests|pass|fail|cancelled|skipped|todo) (\d+)$", originals, re.M)}}
        export_name = "packages/openfilm/studio/server/exports.test.mjs"
        rows = files[export_name].decode().splitlines(True)
        ranges = [(421, 433), (435, 451), (453, 481)]
        imports = """import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { allocateLanes, containMotion, fadeKeyframes, frameSpan, nleRate, planNleTimeline, xmemlDocument } from './packages/openfilm/studio/server/nle.mjs';
import { fcpxmlDocument } from './packages/openfilm/studio/server/fcpxml.mjs';
const scratch = new URL('./native-temp/', import.meta.url).pathname;
"""
        bodies = "\n".join("".join(rows[start - 1:end]) for start, end in ranges)
        extracted = (imports + bodies).encode()
        (scratch / "extracted-planner.test.mjs").write_bytes(extracted)
        (evidence / "executed-planner.test.mjs.txt").write_bytes(extracted)
        pure = run("extracted-planner-tests", ["--test", "--test-reporter=tap", "extracted-planner.test.mjs"])
        record["extracted_planner_tests"] = {"source": export_name, "source_sha256": sha(files[export_name]),
                                            "line_ranges": ranges, "bodies_modified": False, "harness_sha256": sha(extracted),
                                            "summary": {k: int(v) for k, v in re.findall(r"^# (tests|pass|fail|cancelled|skipped|todo) (\d+)$", pure, re.M)}}
        probe = Path(__file__).with_name("probe_openfilm_r14.mjs")
        shutil.copyfile(probe, scratch / "probe.mjs")
        (evidence / "executed-probe.mjs.txt").write_bytes(probe.read_bytes())
        observations = run("boundary-observations", ["probe.mjs"])
        record["boundary_observations"] = json.loads(observations)
        record["frozen_after"] = module.frozen()
        assert frozen_before == record["frozen_after"], "Product changed during this research"
        record["frozen_count"] = len(frozen_before)
        record["status"] = "passed_research_only"
    except Exception as error:
        record["status"] = "failed"
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write(evidence / "verification.json", record)


if __name__ == "__main__":
    main()
