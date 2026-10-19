"""Bind R07 acquisition, selected native checks and the current reuse report."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import re
from urllib.parse import unquote

from audit_openfilm_refresh import contents, digest
from run_frozen_regression import frozen
from sync_openfilm_r07_documents import ROOT, REPORT, EVIDENCE, ACQUIRE


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return digest(path.read_bytes())


def need(value, message):
    if not value:
        raise ValueError(message)


def run(output):
    need(not output.exists(), "Use a fresh delivery receipt")
    before = frozen()
    a = ROOT / "docs" / ACQUIRE
    b = ROOT / "docs" / EVIDENCE
    r, v = read(a / "verification.json"), read(b / "verification.json")
    full_path = ROOT / "docs/validation/evidence/audio-source-context-20261019-v64/full-r1.json"
    full = read(full_path)
    need(full["terminal_ok"] and full["frozen_after"] == before == v["frozen_before"] == v["frozen_after"], "Product changed")
    need(v["frozen_equal"] and v["source_equal"] and len(before) == 196, "Source scope differs")
    need(v["status"] == "completed_scoped_r07_review_with_cache_limitation", "Completed selected checks required")
    need(v["totals"] == {"tests": 76, "pass": 75, "fail": 0, "skipped": 1}, "Test scope changed")
    need(v["fixtures"]["passed_count"] == 13 and not v["fixtures"]["negative_suitability_checks"][0]["accepted_for_direct_avk_reuse"], "Negative suitability check concealed")
    need(not (b / "denied.jsonl").exists(), "Runtime I/O was attempted")
    need(sha(ROOT / "scripts/audit_openfilm_r07.py") == sha(b / "executed-generator.py") == v["generator_sha256"], "Executed checker differs")
    for name, expected in v["evidence_sha256"].items():
        need(sha(b / name) == expected, "Changed evidence: " + name)
    for folder in (b.with_name("openfilm-reuse-20261019-r07"), b.with_name("openfilm-reuse-20261019-r07-r2")):
        failed = read(folder / "verification.json")
        need(failed["status"] == "failed" and failed["frozen_equal"], "Original development failure missing")
        for name, expected in failed["evidence_sha256"].items():
            need(sha(folder / name) == expected, "Changed original failure evidence")
    archive = (ROOT / r["source_archive"]).resolve()
    need(sha(archive) == r["source_archive_sha256"], "Archive changed")
    old, new = contents((ROOT / r["fixed_archive"]).read_bytes()), contents(archive.read_bytes())
    need({p: digest(raw) for p, raw in new.items()} == r["head_hashes"], "Source inventory differs")
    need(len(new) == 749 and len(old) == 731 and len(r["changed"]) == 179 and len(r["added"]) == 37 and len(r["removed"]) == 19, "Delta changed")
    need(all(p.startswith(".changeset/") for p in r["removed"]), "Removed functional file")
    need(new["LICENSE"] == (ROOT / "product/src/ai_ad_editor/OPENFILM_LICENSE.txt").read_bytes(), "License differs")
    for item in r["changed"]:
        if item.get("binary"):
            continue
        name = item["path"]
        patch = "".join(difflib.unified_diff(old[name].decode("utf-8").splitlines(True), new[name].decode("utf-8").splitlines(True), fromfile="fixed/" + name, tofile="head/" + name))
        need((a / item["patch"]).read_bytes() == patch.encode("utf-8"), "Patch differs: " + name)
    need(read(a / "commit.json")["sha"] == r["head"], "API head differs")
    repo = read(a / "repository.json")
    need(repo["stargazers_count"] == r["stars"] == 1142 and repo["forks_count"] == r["forks"] == 117, "API snapshot differs")
    for request in read(a / "requests.json"):
        if "error" in request:
            continue
        target = archive if "/zipball/" in request["url"] else a / ("commit.json" if "/commits/" in request["url"] else "repository.json")
        need(sha(target) == request["sha256"], "Request payload differs")
    documents = ["README.md", "docs/README.md", "docs/构建进度总表_2026-10-16.md",
                 "docs/OpenFilm当前复用决策_2026-10-18.md", "docs/validation/README功能核验与实测演示_2026-10-16.md", "docs/" + REPORT]
    links = upstream_links = 0
    for name in documents:
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        need("R07" in text, "Current review absent from " + name)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', text):
            target = raw.strip("<>").split("#", 1)[0]
            prefix = f"https://github.com/openfilm/openfilm/blob/{r['head']}/"
            if target.startswith(prefix):
                rel = unquote(target[len(prefix):])
                need(rel in new or any(p.startswith(rel + "/") for p in new), "Missing fixed upstream source: " + rel)
                upstream_links += 1
            if not target or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            need((path.parent / unquote(target)).resolve().exists(), "Broken link: " + name + " -> " + target)
            links += 1
    need("| R07 |" in (ROOT / "README.md").read_text(encoding="utf-8"), "README numbered row absent")
    need(frozen() == before, "Product changed during audit")
    files = {}
    for folder in [a, b, b.with_name("openfilm-reuse-20261019-r07"), b.with_name("openfilm-reuse-20261019-r07-r2"), archive.parent]:
        for path in folder.rglob("*"):
            if path.is_file() and path != output:
                files[path.relative_to(ROOT).as_posix()] = {"sha256": sha(path), "bytes": path.stat().st_size}
    for name in [*documents, ".gitattributes", "scripts/audit_openfilm_r07.py", "scripts/sync_openfilm_r07_documents.py", "scripts/audit_openfilm_r07_delivery.py"]:
        path = ROOT / name
        files[name] = {"sha256": sha(path), "bytes": path.stat().st_size}
    record = dict(status="passed_scoped_r07_delivery_with_cache_negative_retained", checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  upstream_head=r["head"], source_files=749, selected_original_tests=v["totals"], independent_pure_fixtures=13,
                  negative_cache_suitability_accepted=False, product_inputs_unchanged=196, product_regression_repeated=False,
                  baseline_completed_product_regression_sha256=sha(full_path), frozen_before=before, frozen_after=frozen(), frozen_equal=True,
                  doc_links_checked=links, fixed_upstream_links_checked=upstream_links, documents=documents, files=files,
                  new_media=False, hardware_or_model_execution=False, full_capcut_parity=False)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: record[k] for k in ("status", "doc_links_checked", "fixed_upstream_links_checked", "product_inputs_unchanged")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output.resolve())
