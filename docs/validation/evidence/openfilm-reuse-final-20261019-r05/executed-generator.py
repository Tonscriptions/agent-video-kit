"""Read-only R05 fixed-source check; dependency-free upstream tests, no GUI or providers."""
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
from audit_openfilm_refresh import contents

ROOT = Path(__file__).resolve().parents[1]
def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def run(refresh, output):
    output.mkdir(parents=True, exist_ok=False); (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    r = json.loads(refresh.read_bytes()); source = Path(r['unpacked_source']).resolve(strict=True); before = frozen()
    assert r['head'] == '7a64d1feacdb59fb631694af7501a4ca570254ca'
    assert r['old_file_count'] == 713 and r['new_file_count'] == 727
    archive = Path(r['source_archive']); assert sha(archive) == r['source_archive_sha256']
    actual = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()}
    assert actual == r['head_hashes']
    prefix = 'packages/openfilm/'
    unchanged_core = [p for p in r['fixed_hashes'] if p.startswith((prefix+'src/', prefix+'studio/server/'))]
    assert unchanged_core and all(r['fixed_hashes'][p] == actual[p] for p in unchanged_core)
    assert all(not p.startswith((prefix+'src/', prefix+'studio/server/')) for p in r['added'])
    old = contents(Path(r['fixed_archive']).read_bytes())
    assert old['LICENSE'] == (source/'LICENSE').read_bytes() == (ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()
    selected = [prefix+'studio/server/fcpxml.test.mjs', prefix+'studio/server/film-subtitle.test.mjs',
        prefix+'studio/server/subtitle-segments.test.mjs', prefix+'src/overrides.test.mjs',
        prefix+'studio/ui/src/lib/template-controls.test.ts',
        'apps/desktop/src/window-lifecycle.test.mjs', 'apps/desktop/src/page-presentation.test.mjs',
        prefix+'studio/ui/src/lib/context-length.test.ts']
    command = ['D:/Program Files/nodejs/node.exe', '--experimental-strip-types', '--test', '--test-concurrency=1',
               '--test-reporter=tap', *[str(source/p) for p in selected]]
    env = dict(os.environ); env.update(TEMP=str(output), TMP=str(output), TMPDIR=str(output))
    started = time.monotonic(); done = subprocess.run(command, cwd=source, env=env, capture_output=True, timeout=120)
    (output/'upstream-selected.stdout.log').write_bytes(done.stdout); (output/'upstream-selected.stderr.log').write_bytes(done.stderr)
    text = done.stdout.decode('utf-8', 'replace'); totals = {}
    for key in ('tests', 'pass', 'fail', 'skipped'):
        match = re.search(r'^# '+key+r' (\d+)\s*$', text, re.M); totals[key] = int(match[1]) if match else None
    assert done.returncode == 0 and totals['fail'] == 0 and totals['skipped'] == 1, (done.returncode, totals, done.stderr)
    assert totals['tests'] == totals['pass']+totals['skipped']
    assert actual == {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()}
    assert frozen() == before
    changed = [x['path'] for x in r['changed']]
    groups = {'desktop': sum(p.startswith('apps/desktop/') for p in changed+r['added']),
              'studio_ui': sum(p.startswith(prefix+'studio/ui/') for p in changed+r['added']),
              'other': sum(not p.startswith(('apps/desktop/', prefix+'studio/ui/')) for p in changed+r['added'])}
    record = {'status': 'passed_scoped_research', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'generator_sha256': sha(Path(__file__)), 'refresh_receipt_sha256': sha(refresh), 'head': r['head'],
        'stars': r['stars'], 'forks': r['forks'], 'version': r['version'], 'source_files': 727,
        'source_before': actual, 'source_after': actual, 'core_files_unchanged': unchanged_core,
        'all_changes_by_scope': groups, 'license_original_bytes_preserved': True,
        'selected_test_files': selected, 'command': command, 'exit_code': done.returncode, 'totals': totals,
        'test_seconds': time.monotonic()-started, 'stdout_sha256': sha(output/'upstream-selected.stdout.log'),
        'stderr_sha256': sha(output/'upstream-selected.stderr.log'), 'frozen_before': before, 'frozen_after': frozen(),
        'browser_invocations': 0, 'gui_started': False, 'dependencies_installed': False, 'providers_called': False,
        'runtime_updated': False, 'model_forwards': 0, 'virtualization': False,
        'window_checks': 'upstream EventEmitter/VM mocks, no real browser window or memory reclamation acceptance',
        'skip': 'optional local Final Cut Pro DTD unavailable; not waived or counted as passed',
        'scope': 'New main is primarily desktop chat/settings/lifecycle. Existing CLI/render/server core unchanged. No new local AI/video kernel adopted.'}
    save(output/'verification.json', record)
    print(json.dumps({k: record[k] for k in ('status', 'head', 'source_files', 'all_changes_by_scope', 'totals')}))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--refresh', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); run(a.refresh.resolve(), a.output.resolve())
