"""Offline byte comparison and original pure tests for pinned OpenFilm 0.2.4.

No installation, Studio, SDK, provider, browser, player instance, or render run.
The acquisition receipt pins source bytes; choose a fresh --output each time.
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
OLD = '284f8bd3d6850ceaa773043e2ecb90e13640f547'
NEW = '53156ac5818d8bad3f2c356043b376b3eebd95ba'
ARCHIVES = {
    OLD: ('openfilm-023-20261020-r12', '5ee1665981831493dd776d2f667da728e0521812c9748e946c99b442ed708e57'),
    NEW: ('openfilm-024-20261021-r13', 'c106830d98d75080f2aba64ad41cb7d95bee606a48c0cd4d913bf3166cbdb192'),
}
SELECTED = (
    'packages/openfilm/src/look.mjs', 'packages/openfilm/src/render.mjs',
    'packages/openfilm/src/rate.mjs', 'packages/openfilm/src/film-doc.mjs',
    'packages/openfilm/src/problems.mjs', 'packages/openfilm/studio/server/exports.mjs',
    'packages/openfilm/studio/server/preview-cache.mjs', 'packages/openfilm/studio/server/fcpxml.mjs',
    'packages/openfilm/studio/server/nle.mjs', 'packages/openfilm/studio/server/diagnostics.mjs',
    'packages/openfilm/studio/server/derived.mjs', 'packages/openfilm/studio/ui/src/lib/component-props.ts',
    'packages/openfilm/studio/ui/src/lib/template-controls.ts', 'packages/openfilm/studio/ui/src/editor/steps.ts',
    'packages/openfilm/studio/ui/src/editor/player.ts', 'apps/desktop/src/pi-config.mjs',
)
TESTS = (
    'packages/openfilm/src/film-doc.test.mjs', 'packages/openfilm/src/rate.test.mjs',
    'packages/openfilm/studio/ui/src/lib/component-props.test.ts',
    'packages/openfilm/studio/ui/src/lib/template-controls.test.ts',
    'packages/openfilm/studio/ui/src/editor/steps.test.ts',
    'packages/openfilm/studio/ui/src/editor/player.test.ts',
    'apps/desktop/src/pi-config.test.mjs',
)


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def archive(commit):
    folder, digest = ARCHIVES[commit]
    path = ROOT / 'sources/upstream' / folder / 'repo.zip'
    data = path.read_bytes()
    assert sha(data) == 'sha256:' + digest
    files = {}
    with zipfile.ZipFile(path) as z:
        assert sum(x.file_size for x in z.infolist()) < 64 << 20
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
    assert not output.parent.exists(), 'Choose a completely new evidence directory'
    scratch = ROOT / 'product/.runtime/openfilm-r13-pure' / output.parent.name
    assert not scratch.exists()
    output.parent.mkdir(parents=True)
    scratch.mkdir(parents=True)
    before = frozen()
    record = {'status': 'running', 'old_commit': OLD, 'new_commit': NEW,
              'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'script_sha256': sha(Path(__file__).read_bytes()), 'frozen_before': before,
              'network_calls': 0, 'dependencies_installed': False, 'upstream_cli_executed': False,
              'browser_or_player_instance_executed': False, 'provider_or_agent_sdk_executed': False,
              'virtualization': False, 'new_product_methods_executed': 0, 'new_model_inference': 0,
              'new_skills_installed': 0, 'full_capcut_parity': False, 'calls': []}
    (output.parent / 'executed-review.py.txt').write_bytes(Path(__file__).read_bytes())
    try:
        old, old_meta = archive(OLD)
        new, new_meta = archive(NEW)
        record['archives'] = {'old': old_meta, 'new': new_meta}
        tree = {key: sorted(value) for key, value in {
            'added': new.keys() - old.keys(), 'removed': old.keys() - new.keys(),
            'modified': {n for n in old.keys() & new.keys() if old[n] != new[n]},
            'unchanged': {n for n in old.keys() & new.keys() if old[n] == new[n]},
        }.items()}
        record['tree'] = {'old_files': len(old), 'new_files': len(new), **tree}
        write(output.parent / 'new-tree.json', {n: {'bytes': len(data), 'sha256': sha(data)} for n, data in sorted(new.items())})
        differences = []
        for name in tree['added'] + tree['modified'] + tree['removed']:
            try:
                differences.extend(difflib.unified_diff(old.get(name, b'').decode().splitlines(True),
                                                      new.get(name, b'').decode().splitlines(True),
                                                      fromfile='old/' + name, tofile='new/' + name))
            except UnicodeDecodeError:
                differences.append('Binary changed: ' + name + '\n')
        (output.parent / 'source.diff').write_text(''.join(differences), encoding='utf8', newline='\n')
        legal = ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'TRADEMARK.md', 'packages/openfilm/LICENSE',
                 'packages/openfilm/THIRD_PARTY_NOTICES.md', 'packages/openfilm/TRADEMARK.md', 'packages/shared/LICENSE')
        record['legal'] = {}
        for name in legal:
            assert new[name] == old[name], name
            target = output.parent / 'legal' / (name + '.txt')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(new[name])
            record['legal'][name] = {'sha256': sha(new[name]), 'unchanged': True}
        record['selected_modules'] = {}
        for name in SELECTED:
            record['selected_modules'][name] = {'old_sha256': sha(old[name]), 'new_sha256': sha(new[name]),
                                              'unchanged': old[name] == new[name]}
            for label, files in (('old', old), ('new', new)):
                target = output.parent / 'selected' / label / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(files[name])
        record['groups'] = {}
        for prefix in ('packages/openfilm/skills/', 'packages/openfilm/studio/server/providers/'):
            a = {n: sha(v) for n, v in old.items() if n.startswith(prefix)}
            b = {n: sha(v) for n, v in new.items() if n.startswith(prefix)}
            record['groups'][prefix] = {'old_files': len(a), 'new_files': len(b),
                                       'unchanged': sum(a.get(n) == v for n, v in b.items()),
                                       'changed': sorted(n for n in a.keys() | b.keys() if a.get(n) != b.get(n))}
        record['workflow_count'] = sum(n.startswith('packages/openfilm/skills/') and n.endswith('/SKILL.md') for n in new)
        record['versions'] = {n: json.loads(new[n])['version'] for n in
                              ('packages/openfilm/package.json', 'apps/desktop/package.json', 'packages/shared/package.json')}
        record['existing_local_upstream_modules'] = {}
        for local in sorted((ROOT / 'product/src/ai_ad_editor').glob('openfilm_*.mjs')):
            data = local.read_bytes()
            record['existing_local_upstream_modules'][local.relative_to(ROOT).as_posix()] = {
                'sha256': sha(data), 'bytes': len(data),
                'exact_matches': [n for n, value in new.items() if value == data]}
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
        for index, name in enumerate(TESTS, 1):
            path = scratch / 'source' / name
            argv = [node, '--experimental-strip-types', '--disallow-code-generation-from-strings', str(path)]
            result = subprocess.run(argv, cwd=scratch, env=env, capture_output=True, timeout=45)
            for stream in ('stdout', 'stderr'):
                (output.parent / f'test-{index}.{stream}.log').write_bytes(getattr(result, stream))
            text = result.stdout.decode('utf8', errors='replace')
            counts = {k: int(v) for k, v in re.findall(r'^# (tests|pass|fail|skipped|cancelled) (\d+)\s*$', text, re.M)}
            record['calls'].append({'test': name, 'test_source_sha256': sha(new[name]), 'argv': argv,
                                    'exit_code': result.returncode, 'counts': counts,
                                    'stdout_sha256': sha(result.stdout), 'stderr_sha256': sha(result.stderr)})
            assert result.returncode == 0, name
            assert counts.get('tests', 0) > 0 and counts.get('fail') == counts.get('skipped') == counts.get('cancelled') == 0
            assert counts['pass'] == counts['tests']
            passed += counts['pass']
        record.update(status='passed_research_only', original_upstream_test_methods=passed, original_test_files=len(TESTS))
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        after = frozen()
        record.update(frozen_after=after, frozen_equal=before == after,
                      finished_at_utc=datetime.now(timezone.utc).isoformat())
        write(output, record)
    assert record['frozen_equal']
    print(json.dumps({'status': record['status'], 'tree': {k: len(v) if isinstance(v, list) else v for k, v in record['tree'].items()},
                      'test_methods': passed, 'frozen_inputs': len(before), 'frozen_equal': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
