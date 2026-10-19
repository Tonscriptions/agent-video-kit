"""Review fixed OpenFilm 0.2.1 reuse candidates without running its CLI or GUI."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
HEAD = "f6a65ae54fa1c10ec482eeb84dc9ffa6ef33c4d8"
NODE = "D:/Program Files/nodejs/node.exe"

GUARD = r"""import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import tls from 'node:tls';
import cp from 'node:child_process';
import { appendFileSync } from 'node:fs';
import { syncBuiltinESMExports } from 'node:module';
const deny = (what) => (...args) => {
  appendFileSync(process.env.AVK_R07_GUARD_LOG, JSON.stringify({ denied: what }) + '\n');
  throw new Error('R07 source-review guard: ' + what);
};
globalThis.fetch = deny('fetch');
for (const [label, mod, names] of [
  ['http', http, ['request', 'get', 'createServer']],
  ['https', https, ['request', 'get', 'createServer']],
  ['net', net, ['connect', 'createConnection', 'createServer']],
  ['tls', tls, ['connect', 'createServer']],
  ['child_process', cp, ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']],
]) for (const name of names) mod[name] = deny(label + '.' + name);
syncBuiltinESMExports();
"""

FIXTURES = r"""import assert from 'node:assert/strict';
import { mkdirSync, readFileSync, statSync, utimesSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
const [source, scratch] = process.argv.slice(2);
const load = (name) => import(pathToFileURL(join(source, name)).href);
const rows = await load('studio/server/track-layout.mjs');
const enc = await load('src/encoders.mjs');
const doctor = await load('src/doctor.mjs');
const problems = await load('src/problems.mjs');
const diag = await load('studio/server/diagnostics.mjs');
const cover = await load('studio/server/cover.mjs');
const cache = await load('studio/server/preview-cache.mjs');
const passed = [];
const check = (id, fn) => { fn(); passed.push(id); };
check('F01-row-labels', () => assert.deepEqual(rows.rowBadges(['mg','video','mg','audio','video','audio']), ['P2','V2','P1','A1','V1','A2']));
check('F02-video-audio-only', () => assert.equal(rows.trackKind({clips:[{src:'a.mp4',sound:true}]}), 'audio'));
check('F03-one-ms-tolerance-and-immutable-input', () => {
  const blocks = [{id:'a',startMs:0,endMs:1000},{id:'b',startMs:999,endMs:2000}];
  const before = structuredClone(blocks);
  assert.deepEqual(rows.layerBlocks(blocks).map(r => r.map(c => c.id)), [['a','b']]);
  assert.deepEqual(blocks, before);
  assert.equal(rows.layerBlocks([blocks[0], {...blocks[1], startMs:998}]).length, 2);
});
check('F04-encoder-options-only', () => {
  const a = enc.hardwareOptions('hevc_nvenc', 8000000, {gop:59.94});
  assert.equal(a[a.indexOf('-g')+1], '60');
  assert.equal(a[a.indexOf('-tag:v')+1], 'hvc1');
  assert.equal(enc.proresOptions('prores_ks', true).pix, 'format=yuva444p10le');
});
check('F05-decoder-policy-only', () => {
  assert.deepEqual(enc.decoderCandidates('win32'), [['-hwaccel','d3d11va'],['-hwaccel','cuda']]);
  assert.deepEqual(enc.decoderCandidates('linux', []), [['-hwaccel','cuda']]);
});
check('F06-color-metadata-only', () => {
  assert.deepEqual(enc.h264ColorTags({color_primaries:'bt709',color_transfer:'iec61966-2-1',color_space:'bt709',color_range:'tv'}),
    ['-bsf:v','h264_metadata=colour_primaries=1:transfer_characteristics=13:matrix_coefficients=1:video_full_range_flag=0']);
  assert.deepEqual(enc.h264ColorTags({color_transfer:'constructor'}), []);
});
check('F07-agent-names-without-env-values', () => {
  const a = doctor.agentHints({CODEX_SANDBOX:'fixture-private-value', PATH:'x'});
  assert.deepEqual(a.agents, ['Codex']);
  assert.ok(!JSON.stringify(a).includes('fixture-private-value'));
});
check('F08-renderer-and-report-helpers-only', () => {
  assert.equal(doctor.softwareRenderer('ANGLE SwiftShader'), true);
  assert.equal(doctor.softwareRenderer('NVIDIA RTX'), false);
  assert.match(doctor.formatReport([{label:'ffmpeg',text:'missing',problem:'configure local path'}]), /configure local path/);
});
check('F09-fixture-redaction', () => {
  assert.ok(!problems.redact('Bearer abcdefghijklmnop ana@example.com').includes('abcdefghijklmnop'));
  assert.ok(!problems.redact('Bearer abcdefghijklmnop ana@example.com').includes('ana@example.com'));
});
check('F10-turn-payload-omission', () => {
  const raw = JSON.stringify({kind:'prompt',t:1,agent:'fixture',text:'fixture-private-words'})+'\n'+
    JSON.stringify({kind:'update',t:2,update:{sessionUpdate:'tool_call',toolCallId:'a',name:'exec_command',rawInput:{cmd:'fixture-private-command'}}});
  const out = diag.turnLogForFile(raw, false);
  assert.ok(!out.includes('fixture-private-'));
  assert.ok(out.includes('exec_command'));
});
check('F11-cover-header-recognition-not-decoding', () => {
  assert.equal(cover.pictureType(Buffer.from('89504e470d0a1a0a', 'hex')), 'png');
  assert.equal(cover.pictureType(Buffer.from('plain text')), null);
});
mkdirSync(scratch, {recursive:true});
writeFileSync(join(scratch, 'film.html'), '<section><iframe src="a.html"></iframe></section>');
writeFileSync(join(scratch, 'a.html'), '<body>AAAA</body>');
const key = () => cache.previewKey(scratch, 0, 1, 30, 540);
check('F12-preview-key-parameters', () => {
  assert.equal(key(), key());
  assert.notEqual(key(), cache.previewKey(scratch, 0, 2, 30, 540));
  assert.notEqual(key(), cache.previewKey(scratch, 0, 1, 30, 720));
});
check('F13-normal-file-change-invalidates', () => {
  const before = key();
  const at = statSync(join(scratch, 'a.html')).mtimeMs;
  writeFileSync(join(scratch, 'a.html'), '<body>LONGER CONTENT</body>');
  utimesSync(join(scratch, 'a.html'), new Date(at+2000), new Date(at+2000));
  assert.notEqual(key(), before);
});
// A negative suitability check, deliberately retained separately from passing cases.
const p = join(scratch, 'a.html');
const fixedTime = new Date(1700000000000);
writeFileSync(p, '<body>AAAA</body>'); utimesSync(p, fixedTime, fixedTime);
const hash = () => createHash('sha256').update(readFileSync(p)).digest('hex');
const beforeKey = key(), beforeHash = hash();
writeFileSync(p, '<body>BBBB</body>'); utimesSync(p, fixedTime, fixedTime);
const afterKey = key(), afterHash = hash();
assert.notEqual(beforeHash, afterHash);
assert.equal(beforeKey, afterKey);
console.log(JSON.stringify({status:'completed_scoped_pure_fixtures',passed,passed_count:passed.length,
  negative_suitability_checks:[{id:'N01-same-size-restored-mtime',expected_for_avk:'content change invalidates cache',
    actual:'same key despite different SHA-256',accepted_for_direct_avk_reuse:false,beforeKey,afterKey,beforeHash,afterHash}],
  actual_media_rendered:false,hardware_probe_executed:false,doctor_executed:false}));
"""


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def run(refresh, output):
    r = json.loads(refresh.read_bytes())
    if r["head"] != HEAD or r["version"] != "0.2.1" or r["new_file_count"] != 749:
        raise ValueError("This review requires its fixed 0.2.1 snapshot")
    source = Path(r["unpacked_source"]).resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    (output / "executed-generator.py").write_bytes(Path(__file__).read_bytes())
    before = frozen()
    tree = lambda: {p.relative_to(source).as_posix(): sha(p) for p in source.rglob("*") if p.is_file()}
    if tree() != r["head_hashes"] or sha(Path(r["source_archive"])) != r["source_archive_sha256"]:
        raise ValueError("Source bytes differ from the acquisition receipt")
    scratch = ROOT / "product/.runtime" / output.name
    scratch.mkdir(parents=True, exist_ok=False)
    for directory in ("temp", "home", "library", "app-logs"):
        (scratch / directory).mkdir()
    env = dict(os.environ, TEMP=str(scratch / "temp"), TMP=str(scratch / "temp"),
               OPENFILM_HOME=str(scratch / "home"), OPENFILM_LIBRARY=str(scratch / "library"),
               OPENFILM_APP_LOGS=str(scratch / "app-logs"), AVK_R07_GUARD_LOG=str(output / "denied.jsonl"))
    selected = ["src/film-doc.test.mjs", "studio/server/fcpxml.test.mjs",
                "studio/server/film-subtitle.test.mjs", "studio/server/subtitle-segments.test.mjs",
                "src/overrides.test.mjs", "studio/ui/src/lib/template-controls.test.ts",
                "src/problems.test.mjs", "studio/server/diagnostics.test.mjs"]
    guard = output / "no-runtime-io.mjs"
    guard.write_text(GUARD, encoding="utf-8", newline="\n")
    probe = output / "pure-fixtures.mjs"
    probe.write_text(FIXTURES, encoding="utf-8", newline="\n")
    record = dict(status="running", head=HEAD, frozen_before=before, refresh_sha256=sha(refresh),
                  generator_sha256=sha(Path(__file__)), source_before=r["head_hashes"],
                  upstream_cli_started=False, browser_started=False, dependencies_installed=False,
                  product_adopted=False, product_full_regression_repeated=False, neural_forwards=0,
                  virtualization=False, guard_sha256=sha(guard), fixtures_sha256=sha(probe))
    started = time.monotonic()
    save(output / "verification.json", record)
    try:
        command = [NODE, "--experimental-strip-types", "--import", guard.as_uri(),
                   "--experimental-test-isolation=none", "--test", "--test-concurrency=1",
                   "--test-reporter=tap", *[str(source / "packages/openfilm" / p) for p in selected]]
        p = subprocess.run(command, cwd=source, env=env, capture_output=True, timeout=120)
        (output / "upstream-selected.stdout.log").write_bytes(p.stdout)
        (output / "upstream-selected.stderr.log").write_bytes(p.stderr)
        text = p.stdout.decode("utf-8", "replace")
        totals = {key: int(m[1]) if (m := re.search(r"^# " + key + r" (\d+)\s*$", text, re.M)) else None
                  for key in ("tests", "pass", "fail", "skipped")}
        record.update(command=command, upstream_exit_code=p.returncode, totals=totals, selected_test_files=selected)
        if p.returncode or totals["fail"] != 0 or totals["skipped"] != 1:
            raise ValueError("Selected original tests failed or skip count changed: " + str(totals))
        qcommand = [NODE, "--import", guard.as_uri(), str(probe), str(source / "packages/openfilm"), str(scratch / "project")]
        q = subprocess.run(qcommand, cwd=source, env=env, capture_output=True, timeout=30)
        (output / "fixtures.stdout.log").write_bytes(q.stdout)
        (output / "fixtures.stderr.log").write_bytes(q.stderr)
        record.update(fixtures_command=qcommand, fixtures_exit_code=q.returncode)
        if q.returncode:
            raise ValueError("Pure fixture failed: " + q.stderr.decode("utf-8", "replace"))
        fixture_result = json.loads(q.stdout)
        save(output / "fixtures.json", fixture_result)
        if fixture_result["passed_count"] != 13 or (output / "denied.jsonl").exists():
            raise ValueError("Unexpected fixture count or runtime I/O attempted")
        if (source / "LICENSE").read_bytes() != (ROOT / "product/src/ai_ad_editor/OPENFILM_LICENSE.txt").read_bytes():
            raise ValueError("MIT notice changed")
        stable = {}
        for name, prefix in (("skills", "packages/openfilm/skills/"), ("providers", "packages/openfilm/studio/server/providers/")):
            old = {k: v for k, v in r["fixed_hashes"].items() if k.startswith(prefix)}
            new = {k: v for k, v in r["head_hashes"].items() if k.startswith(prefix)}
            stable[name] = {"files": len(new), "all_bytes_unchanged": old == new}
        record.update(status="completed_scoped_r07_review_with_cache_limitation", fixtures=fixture_result,
                      stable_groups=stable, license_original_bytes_preserved=True,
                      native_node_version=subprocess.check_output([NODE, "--version"], env=env, text=True).strip(),
                      engine_scope="Node 22.14 runs selected checks only; repository/doctor ask for >=22.18 while package still declares >=22.2",
                      skip="Optional local Final Cut Pro 1.10 DTD absent; no target NLE import tested")
    except BaseException as exc:
        record.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
        raise
    finally:
        after = frozen()
        record.update(frozen_after=after, frozen_equal=before == after, source_after=tree(),
                      source_equal=tree() == r["head_hashes"], seconds=time.monotonic() - started,
                      checked_at_utc=datetime.now(timezone.utc).isoformat())
        record["evidence_sha256"] = {p.name: sha(p) for p in output.iterdir() if p.is_file() and p.name != "verification.json"}
        save(output / "verification.json", record)
    if not record["frozen_equal"] or not record["source_equal"]:
        raise ValueError("Source or product inputs changed during the review")
    print(json.dumps({k: record[k] for k in ("status", "totals", "stable_groups", "native_node_version", "frozen_equal", "source_equal")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.refresh.resolve(), args.output.resolve())
