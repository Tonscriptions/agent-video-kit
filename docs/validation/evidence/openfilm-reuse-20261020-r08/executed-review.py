"""Bounded source review; never starts upstream CLI, providers or a browser."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/openfilm-refresh-20261020-r08'
OUT = ROOT/'docs/validation/evidence/openfilm-reuse-20261020-r08'

def sha(p): return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')

def main():
    OUT.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, OUT/'executed-review.py')
    acquired = json.loads((BASE/'verification.json').read_bytes())
    assert acquired['head'] == '71922644da5d6b67db2cc796d4e057f98999944f'
    source = Path(acquired['unpacked_source']); before = frozen()
    for name, expected in acquired['head_hashes'].items(): assert sha(source/name) == expected
    groups = {}
    for label, prefix in [('skills', 'skills/'), ('providers', 'packages/openfilm/src/providers/')]:
        old = {n:v for n,v in acquired['fixed_hashes'].items() if n.startswith(prefix)}
        new = {n:v for n,v in acquired['head_hashes'].items() if n.startswith(prefix)}
        groups[label] = {'files_before': len(old), 'files_after': len(new), 'all_bytes_equal': old == new}
    nodes = []
    for name in ('packages/openfilm/src/problems.mjs', 'packages/openfilm/studio/server/diagnostics.mjs'):
        nodes.append({'path': name, 'sha256': sha(source/name), 'unchanged_from_r07': acquired['head_hashes'][name] == acquired['fixed_hashes'][name]})
    guard = OUT/'no-runtime-io.mjs'
    previous = ROOT/'docs/validation/evidence/openfilm-reuse-20261019-r07-r3/no-runtime-io.mjs'
    guard.write_text(previous.read_text(encoding='utf8').replace('AVK_R07_GUARD_LOG', 'AVK_R08_GUARD_LOG').replace('R07 source-review', 'R08 source-review'), encoding='utf8', newline='\n')
    env = dict(os.environ, TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
               AVK_R08_GUARD_LOG=str(OUT/'denied.jsonl'))
    node = 'D:/Program Files/nodejs/node.exe'
    command = [node, '--experimental-test-isolation=none', '--test', '--test-reporter=tap', '--import', guard.as_uri(),
        str(source/'packages/openfilm/studio/server/fcpxml.test.mjs')]
    p = subprocess.run(command, cwd=source, env=env, capture_output=True, timeout=60)
    (OUT/'fcpxml.stdout.log').write_bytes(p.stdout); (OUT/'fcpxml.stderr.log').write_bytes(p.stderr)
    totals = {k:int(re.search(rb'^# '+k.encode()+rb' (\d+)', p.stdout, re.M)[1]) for k in ('tests', 'pass', 'fail', 'skipped')}
    # Execute exactly the two new pure declarations, without importing the
    # browser/encoder render module. This is an extracted helper fixture.
    raw = (source/'packages/openfilm/src/render.mjs').read_text(encoding='utf8')
    constant = re.search(r'^const OUT_OF_MEMORY = .+;$', raw, re.M)[0]
    start = raw.index('export function outOfMemory('); end = raw.index('\n}', start) + 2
    helper = raw[start:end].replace('export function', 'function', 1)
    fixture = OUT/'extracted-oom.mjs'
    fixture.write_text("import assert from 'node:assert/strict';\n" + constant+'\n'+helper+'''
const cases = [
  ['malloc of size 123 failed', 4, /--workers 2/],
  ['cannot allocate memory', 2, /--workers 1/],
  ['out of memory', 1, /out of memory/],
  ['ffmpeg exit 3221225495', 4, /--workers 2/],
];
for (const [message, workers, expected] of cases) {
  const original = new Error(message), result = outOfMemory(original, workers);
  assert.match(result.message, expected); assert.equal(result.cause, original);
}
for (const value of [new Error('unknown encoder'), new Error('exit 3221225477'), 'out of memory', null]) {
  assert.equal(outOfMemory(value, 4), value);
}
console.log(JSON.stringify({cases: 8, scope: 'exact extracted pure helper; no encoder or browser executed'}));
''', encoding='utf8', newline='\n')
    q = subprocess.run([node, '--import', guard.as_uri(), str(fixture)], cwd=OUT, env=env, capture_output=True, timeout=30)
    (OUT/'oom.stdout.log').write_bytes(q.stdout); (OUT/'oom.stderr.log').write_bytes(q.stderr)
    record = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'head': acquired['head'], 'version': acquired['version'],
        'stars': acquired['stars'], 'forks': acquired['forks'], 'community_snapshot_at_utc': acquired['checked_at_utc'],
        'source_files': acquired['new_file_count'], 'all_fixed_source_hashes_checked': True,
        'groups': groups, 'diagnostic_modules': nodes, 'fcpxml_original_tests': totals, 'fcpxml_exit': p.returncode,
        'extracted_oom_exit': q.returncode, 'extracted_oom_cases': 8, 'upstream_full_suite_run': False,
        'browser_started': False, 'upstream_cli_started': False, 'provider_called': False, 'dependencies_installed': False,
        'guard_denied_calls': (OUT/'denied.jsonl').read_text() if (OUT/'denied.jsonl').exists() else '',
        'product_before': before, 'product_after': frozen(), 'license_equal': (source/'LICENSE').read_bytes() == (ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()}
    record['product_unchanged'] = record['product_before'] == record['product_after']
    record['files'] = {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in OUT.iterdir() if p.is_file()}
    save(OUT/'verification.json', record)
    assert p.returncode == 0 and q.returncode == 0 and totals['fail'] == 0
    assert record['guard_denied_calls'] == '' and record['product_unchanged'] and record['license_equal']
    print(json.dumps({k: record[k] for k in ('head','groups','fcpxml_original_tests','extracted_oom_cases','product_unchanged')}, ensure_ascii=False))

if __name__ == '__main__': main()
