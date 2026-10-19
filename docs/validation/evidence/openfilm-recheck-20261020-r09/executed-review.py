"""Recheck the fixed OpenFilm tree and exercise selected pure declarations only.

Network access obtains public source metadata; the extracted Node fixtures may
not start network connections, upstream commands, providers or browsers.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/openfilm-refresh-20261020-r08'
OUT = ROOT / 'docs/validation/evidence/openfilm-recheck-20261020-r09'
WORK = ROOT / 'product/.runtime/openfilm-recheck-20261020-r09'
FIXED = '71922644da5d6b67db2cc796d4e057f98999944f'


def sha_bytes(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf8', newline='\n')


def declaration(raw, name):
    begin = raw.index(('export function ' + name + '(').encode())
    end = raw.index(b'\n}', begin) + 2
    return raw[begin:end]


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    WORK.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, OUT / 'executed-review.py')
    before = frozen()
    requests = []

    def fetch(label, url):
        request = urllib.request.Request(url, headers={
            'User-Agent': 'agent-video-kit-openfilm-source-recheck',
            'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=40) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            assert len(raw) <= 2 * 1024 * 1024
            requests.append({'url': url, 'status': response.status,
                             'sha256': sha_bytes(raw), 'bytes': len(raw),
                             'received_at_utc': datetime.now(timezone.utc).isoformat()})
        (OUT / (label + '.json')).write_bytes(raw)
        save(OUT / 'requests.json', requests)
        return json.loads(raw)

    api = 'https://api.github.com/repos/openfilm/openfilm'
    repository = fetch('repository', api)
    commit = fetch('commit', api + '/commits/' + repository['default_branch'])
    # New source must receive a new full acquisition/review, never silently reuse
    # an old tree while calling it the latest one.
    assert commit['sha'] == FIXED, 'Upstream changed: acquire/review a fresh archive'
    acquired = json.loads((BASE / 'verification.json').read_bytes())
    assert acquired['head'] == FIXED
    source = Path(acquired['unpacked_source']).resolve(strict=True)
    archive = ROOT / acquired['source_archive']
    assert sha_bytes(archive.read_bytes()) == acquired['source_archive_sha256']
    actual = {p.relative_to(source).as_posix(): sha_bytes(p.read_bytes())
              for p in sorted(source.rglob('*')) if p.is_file()}
    assert actual == acquired['head_hashes'], 'Source tree changed'
    license_equal = ((source / 'LICENSE').read_bytes() ==
                     (ROOT / 'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes())
    assert license_equal
    package = source / 'packages/openfilm'
    modules = {}
    for name in ('src/render.mjs', 'src/look.mjs', 'src/problems.mjs',
                 'studio/server/exports.mjs', 'studio/server/preview-cache.mjs',
                 'studio/server/fcpxml.mjs', 'studio/server/nle.mjs',
                 'studio/server/diagnostics.mjs'):
        path = package / name
        text = path.read_text(encoding='utf8')
        modules[name] = {'sha256': sha_bytes(path.read_bytes()), 'bytes': path.stat().st_size,
                         'imports': [line for line in text.splitlines() if line.startswith('import ')]}

    render = (package / 'src/render.mjs').read_bytes()
    cache = (package / 'studio/server/preview-cache.mjs').read_bytes()
    exports = (package / 'studio/server/exports.mjs').read_bytes()
    constants = []
    for name, raw in [('WORKER_MEMORY', render), ('RESERVE', render),
                      ('FRAMES_PER_WORKER', render), ('MAX_WORKERS', render),
                      ('SOUNDS', cache), ('MOST_FILES', cache), ('VERSION', cache)]:
        constants.append(re.search(rb'^const ' + name.encode() + rb' = .+;$', raw, re.M)[0])
    functions = [declaration(render, 'defaultWorkers'), declaration(cache, 'projectPrint'),
                 declaration(cache, 'previewKey')]
    key_begin = exports.index(b'        const { preset, label, ...rest }')
    key_end = exports.index(b'\n', exports.index(b'const same =', key_begin))
    key_statements = exports[key_begin:key_end]
    extraction = b'\n\n'.join(constants + functions + [key_statements]) + b'\n'
    (OUT / 'original-declarations.mjs.txt').write_bytes(extraction)

    guard = OUT / 'no-runtime-io.mjs'
    original_guard = (ROOT / 'docs/validation/evidence/openfilm-reuse-20261020-r08-r3/no-runtime-io.mjs').read_text(encoding='utf8')
    guard.write_text(original_guard.replace('AVK_R08_GUARD_LOG', 'AVK_R09_GUARD_LOG')
                     .replace('R08 source-review', 'R09 source-review'), encoding='utf8', newline='\n')
    fixture = OUT / 'selected-declarations.mjs'
    imports = b"""import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readdirSync, statSync, readFileSync, writeFileSync, mkdirSync, utimesSync } from 'node:fs';
import { extname, join } from 'node:path';
const FILM_FILE = 'film.html';
"""
    wrapper = b'function askKey(ask) {\n' + key_statements + b'\nreturn same;\n}\n'
    cases = b"""
const checks = [];
function check(name, actual, expected) {
  assert.deepEqual(actual, expected, name);
  checks.push({ name, actual, expected, passed: true });
}
const GiB = 2 ** 30;
check('workers-high-memory-capped', defaultWorkers({cores: 8, available: 16 * GiB}, 600), 4);
check('workers-zero-memory-still-one', defaultWorkers({cores: 8, available: 0}, 600), 1);
check('workers-one-core-still-one', defaultWorkers({cores: 1, available: 16 * GiB}, 600), 1);
check('workers-short-job', defaultWorkers({cores: 8, available: 16 * GiB}, 59), 1);
check('workers-frame-budget', defaultWorkers({cores: 8, available: 16 * GiB}, 120), 2);
check('workers-memory-budget', defaultWorkers({cores: 8, available: 5 * GiB}, 600), 2);
const base = { kind: 'video', codec: 'h264', shortEdge: 1080, fps: 30, range: [0, 4] };
check('signature-platform-label-ignored', askKey({...base, preset:'A', label:'a'}) === askKey({...base, preset:'B', label:'b'}), true);
check('signature-object-key-order', askKey(base) === askKey({range:[0,4], fps:30, shortEdge:1080, codec:'h264', kind:'video'}), true);
check('signature-different-custom-names-prevent-reuse', askKey({...base,name:'A'}) === askKey({...base,name:'B'}), false);
check('signature-resolution-separated', askKey(base) === askKey({...base,shortEdge:720}), false);
check('signature-fps-separated', askKey(base) === askKey({...base,fps:24}), false);
check('signature-codec-separated', askKey(base) === askKey({...base,codec:'hevc'}), false);
check('signature-range-separated', askKey(base) === askKey({...base,range:[0,5]}), false);
const root = process.argv[2];
mkdirSync(root, { recursive: true });
writeFileSync(join(root, FILM_FILE), '<section></section>');
const asset = join(root, 'title.html'), fixed = new Date('2026-10-01T00:00:00.000Z');
writeFileSync(asset, '<p>A</p>'); utimesSync(asset, fixed, fixed);
const contentBefore = createHash('sha256').update(readFileSync(asset)).digest('hex');
const printBefore = projectPrint(root), keyBefore = previewKey(root, 0, 4, 30, 360);
writeFileSync(asset, '<p>B</p>'); utimesSync(asset, fixed, fixed);
const contentAfter = createHash('sha256').update(readFileSync(asset)).digest('hex');
check('cache-asset-content-changed', contentBefore !== contentAfter, true);
check('cache-project-fingerprint-stale', printBefore === projectPrint(root), true);
check('cache-preview-key-stale', keyBefore === previewKey(root, 0, 4, 30, 360), true);
console.log(JSON.stringify({ checks, scope: 'isolated original declarations; not full upstream modules, exports or rendering',
  cache: { contentBefore, contentAfter, printBefore, printAfter:projectPrint(root), keyBefore, keyAfter:previewKey(root,0,4,30,360) } }));
"""
    fixture.write_bytes(imports + b'\n'.join(constants + functions) + b'\n' + wrapper + cases)
    env = dict(os.environ, AVK_R09_GUARD_LOG=str(OUT / 'denied.jsonl'),
               TEMP=str(ROOT / 'product/.runtime/temp'), TMP=str(ROOT / 'product/.runtime/temp'))
    node = 'D:/Program Files/nodejs/node.exe'
    command = [node, '--import', guard.as_uri(), str(fixture), str(WORK / 'cache-fixture')]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=30)
    (OUT / 'fixtures.stdout.log').write_bytes(result.stdout)
    (OUT / 'fixtures.stderr.log').write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode('utf8', errors='replace')
    observations = json.loads(result.stdout)
    save(OUT / 'fixture-observations.json', observations)
    assert len(observations['checks']) == 16
    after = frozen()
    full = json.loads((ROOT / 'docs/validation/evidence/pipeline-diagnostics-20261020-v67/full-r2.json').read_bytes())
    release_inputs = full['frozen_after']
    record = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'head': commit['sha'],
        'source_changed_from_r08': False, 'version': acquired['version'],
        'stars': repository['stargazers_count'], 'forks': repository['forks_count'],
        'community_snapshot_at_utc': requests[0]['received_at_utc'],
        'license': repository['license']['spdx_id'], 'license_equal_to_packaged_copy': license_equal,
        'archive': str(archive.relative_to(ROOT)), 'archive_sha256': sha_bytes(archive.read_bytes()),
        'tree_files': len(actual), 'all_tree_bytes_verified': True, 'tree_hashes': actual,
        'reviewed_modules': modules, 'extracted_declarations_sha256': sha_bytes(extraction),
        'extracted_fixture_cases': len(observations['checks']), 'fixture_exit': result.returncode,
        'command': command, 'upstream_full_modules_run': False, 'upstream_original_tests_rerun': False,
        'product_regression_rerun': False, 'dependencies_installed': False,
        'browsers_started': 0, 'provider_calls': 0, 'model_calls': 0, 'new_media_outputs': 0,
        'guard_denied_calls': (OUT / 'denied.jsonl').read_text() if (OUT / 'denied.jsonl').exists() else '',
        'product_before': before, 'product_after': after, 'product_unchanged_during_review': before == after,
        'baseline_product_commit': 'ed09f69539247e90bd009aac2fd9ad2b01eedbb6',
        'preexisting_product_wip_vs_v67': {
            'added': sorted(before.keys() - release_inputs.keys()),
            'removed': sorted(release_inputs.keys() - before.keys()),
            'changed': sorted(p for p in before.keys() & release_inputs.keys() if before[p] != release_inputs[p])},
        'scope': 'source research only; pending V68 product edits are preserved and not accepted by this review',
    }
    record['files'] = {p.name: {'sha256': sha_bytes(p.read_bytes()), 'bytes': p.stat().st_size}
                       for p in sorted(OUT.iterdir()) if p.is_file()}
    save(OUT / 'verification.json', record)
    assert record['product_unchanged_during_review'] and not record['guard_denied_calls']
    print(json.dumps({key: record[key] for key in ('head', 'stars', 'forks', 'tree_files',
          'extracted_fixture_cases', 'product_unchanged_during_review', 'preexisting_product_wip_vs_v67')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
