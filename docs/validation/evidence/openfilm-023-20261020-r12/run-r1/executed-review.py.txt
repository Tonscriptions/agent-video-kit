"""Offline comparison of pinned OpenFilm 0.2.2/0.2.3 and original pure tests.

No upstream CLI, browser, server, provider, package installation or model runs.
Acquisition happens separately; all scratch data stays on E. Never overwrites
an earlier execution receipt, including failed executions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import zipfile

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
OLD = '695f4a887a97258d45ffe5715eadf537b6d2579b'
NEW = '284f8bd3d6850ceaa773043e2ecb90e13640f547'
ARCHIVES = {
    OLD: ('openfilm-022-20261020-r11', '2786c4b06d90f112aba12c013ee7aaa3d8bf75f14b40d59e86e36f2a917c300e'),
    NEW: ('openfilm-023-20261020-r12', '5ee1665981831493dd776d2f667da728e0521812c9748e946c99b442ed708e57'),
}
SELECTED = (
    'src/look.mjs', 'src/render.mjs', 'src/rate.mjs', 'src/film-doc.mjs',
    'src/problems.mjs', 'studio/server/exports.mjs',
    'studio/server/preview-cache.mjs', 'studio/server/fcpxml.mjs',
    'studio/server/nle.mjs', 'studio/server/diagnostics.mjs',
    'studio/server/derived.mjs', 'studio/ui/src/lib/component-props.ts',
    'studio/ui/src/lib/template-controls.ts', 'studio/ui/src/editor/steps.ts',
)
TESTS = (
    'src/film-doc.test.mjs', 'src/rate.test.mjs',
    'studio/ui/src/lib/component-props.test.ts',
    'studio/ui/src/lib/template-controls.test.ts',
    'studio/ui/src/editor/steps.test.ts',
)


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def archive(commit):
    folder, expected = ARCHIVES[commit]
    path = ROOT / 'sources/upstream' / folder / 'repo.zip'
    data = path.read_bytes()
    assert sha(data) == 'sha256:' + expected
    files = {}
    with zipfile.ZipFile(path) as z:
        assert sum(x.file_size for x in z.infolist()) < 64 * 1024 * 1024
        for entry in z.infolist():
            if entry.is_dir():
                continue
            parts = PurePosixPath(entry.filename)
            assert not parts.is_absolute() and '..' not in parts.parts
            assert parts.parts[0] == 'openfilm-' + commit
            assert (entry.external_attr >> 16) & 0o170000 != 0o120000
            name = PurePosixPath(*parts.parts[1:]).as_posix()
            assert name not in files
            files[name] = z.read(entry)
    return files, {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(data), 'sha256': sha(data)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'docs/validation/evidence') and not output.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / 'product/.runtime/openfilm-r12-pure' / output.parent.name
    scratch.mkdir(parents=True, exist_ok=False)
    before = frozen()
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'script_sha256': sha(Path(__file__).read_bytes()), 'old_commit': OLD, 'new_commit': NEW,
              'frozen_before': before, 'network_calls': 0, 'dependencies_installed': False,
              'upstream_cli_executed': False, 'upstream_browser_executed': False,
              'upstream_provider_executed': False, 'new_model_inference': 0,
              'virtualization': False, 'full_capcut_parity': False, 'calls': []}
    (output.parent / 'executed-review.py.txt').write_bytes(Path(__file__).read_bytes())
    try:
        old, old_meta = archive(OLD)
        new, new_meta = archive(NEW)
        record['archives'] = {'old': old_meta, 'new': new_meta}
        added = sorted(new.keys() - old.keys())
        removed = sorted(old.keys() - new.keys())
        modified = sorted(n for n in old.keys() & new.keys() if old[n] != new[n])
        unchanged = sorted(n for n in old.keys() & new.keys() if old[n] == new[n])
        record['tree'] = {'old_files': len(old), 'new_files': len(new),
                          'unchanged_count': len(unchanged), 'added': added,
                          'removed': removed, 'modified': modified}
        manifest = {n: {'bytes': len(data), 'sha256': sha(data)} for n, data in sorted(new.items())}
        write(output.parent / 'new-tree.json', manifest)
        difference = []
        for n in added + modified + removed:
            try:
                difference.extend(difflib.unified_diff(old.get(n, b'').decode().splitlines(True),
                                                     new.get(n, b'').decode().splitlines(True),
                                                     fromfile='old/' + n, tofile='new/' + n))
            except UnicodeDecodeError:
                difference.append('Binary changed: ' + n + '\n')
        (output.parent / 'source.diff').write_text(''.join(difference), encoding='utf8', newline='\n')
        assert old['LICENSE'] == new['LICENSE']
        record['license_sha256'] = sha(new['LICENSE'])
        (output.parent / 'LICENSE.txt').write_bytes(new['LICENSE'])
        record['selected_modules'] = {
            n: {'old_sha256': sha(old['packages/openfilm/' + n]) if 'packages/openfilm/' + n in old else None,
                'new_sha256': sha(new['packages/openfilm/' + n]),
                'unchanged': old.get('packages/openfilm/' + n) == new['packages/openfilm/' + n]}
            for n in SELECTED}
        record['groups'] = {}
        for prefix in ('packages/openfilm/skills/', 'packages/openfilm/studio/server/providers/'):
            a = {n: sha(data) for n, data in old.items() if n.startswith(prefix)}
            b = {n: sha(data) for n, data in new.items() if n.startswith(prefix)}
            record['groups'][prefix] = {'old_files': len(a), 'new_files': len(b),
                                       'unchanged': sorted(n for n in a.keys() & b.keys() if a[n] == b[n]),
                                       'changed': sorted(n for n in a.keys() | b.keys() if a.get(n) != b.get(n))}
        record['versions'] = {n: json.loads(new[n])['version'] for n in
                              ('packages/openfilm/package.json', 'apps/desktop/package.json')}
        record['workflow_count'] = len([n for n in new if n.startswith('packages/openfilm/skills/') and n.endswith('/SKILL.md')])
        # Preserve original paths/bytes, including package.json module metadata.
        # This is a source extraction, not an installed upstream workspace.
        for name, data in new.items():
            target = scratch / 'source' / name
            assert target.resolve().is_relative_to(scratch)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        node = shutil.which('node')
        assert node is not None
        record['node'] = {'path': node, 'sha256': sha(Path(node).read_bytes()),
                          'version': subprocess.run([node, '--version'], capture_output=True, check=True, timeout=15).stdout.decode().strip()}
        env = dict(os.environ)
        env.pop('NODE_OPTIONS', None)
        env.pop('NODE_PATH', None)
        temp = scratch / 'temp'
        temp.mkdir()
        env.update(TEMP=str(temp), TMP=str(temp))
        passed = 0
        for i, name in enumerate(TESTS, 1):
            # The inspected dependency closure contains only local pure functions
            # and node:test/assert. No test runner child processes are needed.
            path = scratch / 'source/packages/openfilm' / name
            argv = [node, '--experimental-strip-types', '--disallow-code-generation-from-strings', str(path)]
            result = subprocess.run(argv, cwd=scratch, env=env, capture_output=True, timeout=45)
            for stream in ('stdout', 'stderr'):
                (output.parent / f'test-{i}.{stream}.log').write_bytes(getattr(result, stream))
            text = result.stdout.decode('utf8', errors='replace')
            counts = {key: int(value) for key, value in re.findall(r'^# (tests|pass|fail|skipped|cancelled) (\d+)\s*$', text, re.M)}
            call = {'test': name, 'test_source_sha256': sha(new['packages/openfilm/' + name]),
                    'argv': argv, 'exit_code': result.returncode, 'counts': counts,
                    'stdout_sha256': sha(result.stdout), 'stderr_sha256': sha(result.stderr)}
            record['calls'].append(call)
            assert result.returncode == 0, name
            assert counts.get('tests', 0) > 0 and counts.get('fail') == counts.get('skipped') == counts.get('cancelled') == 0
            assert counts['pass'] == counts['tests']
            passed += counts['pass']
        record.update(original_upstream_test_methods=passed, original_test_files=len(TESTS),
                      installed_new_skills=0, product_test_methods_executed=0,
                      status='passed_research_only')
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        after = frozen()
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=after, frozen_equal=before == after)
        write(output, record)
    assert record['frozen_equal']
    print(json.dumps({'status': record['status'], 'tree': {k: (len(v) if isinstance(v, list) else v) for k,v in record['tree'].items()},
                      'test_methods': passed, 'frozen_inputs': len(before), 'frozen_equal': True}))


if __name__ == '__main__':
    main()
