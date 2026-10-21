"""Run the frozen native suite with explicitly bound committed media fixtures.

The original runner retains its own source inputs and raw log. This wrapper
additionally hashes all external media/font inputs before and after the run.
It never restores, overwrites or downloads a fixture.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from materialize_regression_fixtures import FIXTURES

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return 'sha256:' + result.hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def observe(rows):
    observed = {}
    for row in rows:
        name = row['path']
        path = ROOT / name
        assert path.resolve(strict=True).is_relative_to(ROOT), name
        assert path.is_file() and not path.is_symlink(), name
        size = path.stat().st_size
        assert 0 < size <= 2 * 1024**3, name
        observed[name] = {'bytes': size, 'sha256': digest(path)}
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--pattern', default='test*.py')
    parser.add_argument('--html-runtime', type=Path)
    parser.add_argument('--rubberband', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    source_output = output.with_name(output.stem + '.source.json')
    log = output.with_suffix('.log')
    source_log = source_output.with_suffix('.log')
    assert output.is_relative_to(ROOT / 'docs'), 'evidence must stay under docs/'
    assert not any(p.exists() for p in (output, source_output, log, source_log)), 'choose fresh evidence paths'
    output.parent.mkdir(parents=True, exist_ok=True)
    runner = ROOT / 'scripts/run_frozen_regression.py'
    materializer = ROOT / 'scripts/materialize_regression_fixtures.py'
    record = {
        'status': 'checking_external_fixtures', 'started_at_utc': utc(),
        'wrapper_sha256': digest(Path(__file__)), 'inner_runner_sha256': digest(runner),
        'fixture_definition_sha256': digest(materializer), 'pattern': args.pattern,
        'native_windows': sys.platform == 'win32', 'virtualization': False,
        'network': False, 'suite_launched': False, 'terminal_ok': False,
        'source_evidence': source_output.relative_to(ROOT).as_posix(),
        'source_log': source_log.relative_to(ROOT).as_posix(),
    }

    def save():
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')

    save()
    rows = None
    manifest = None
    manifest_sha = None
    wrapper_before = record['wrapper_sha256']
    runner_before = record['inner_runner_sha256']
    definition_before = record['fixture_definition_sha256']
    try:
        manifest = args.fixture_manifest.resolve(strict=True)
        assert manifest.is_relative_to(ROOT / 'docs') and manifest.is_file()
        manifest_sha = digest(manifest)
        value = json.loads(manifest.read_text(encoding='utf8'))
        assert value['status'] == 'passed'
        rows = value['fixtures']
        assert len(rows) == len(FIXTURES) and {r['path'] for r in rows} == set(FIXTURES)
        expected = {}
        for row in rows:
            assert type(row['bytes']) is int and 0 < row['bytes'] <= 2 * 1024**3
            assert re.fullmatch(r'sha256:[0-9a-f]{64}', row['sha256'])
            expected[row['path']] = {'bytes': row['bytes'], 'sha256': row['sha256']}
        before = observe(rows)
        record.update(external_fixture_manifest=manifest.relative_to(ROOT).as_posix(),
                      external_fixture_manifest_sha256=manifest_sha,
                      external_fixtures_expected=expected, external_fixtures_before=before,
                      external_fixture_count=len(before))
        assert before == expected, 'external fixture preflight hash/size mismatch'
        command = [sys.executable, '-E', '-B', '-X', 'utf8', str(runner),
                   '--output', str(source_output), '--pattern', args.pattern]
        for option in ('html_runtime', 'rubberband'):
            item = getattr(args, option)
            if item:
                command.extend(['--' + option.replace('_', '-'), str(item.resolve(strict=True))])
        record.update(status='running', suite_launched=True, command=command)
        save()
        result = subprocess.run(command, cwd=ROOT, capture_output=True)
        record['runner_stdout'] = result.stdout.decode('utf8', errors='replace')[-8192:]
        record['runner_stderr'] = result.stderr.decode('utf8', errors='replace')[-8192:]
        record['source_suite_exit_code'] = result.returncode
        if source_output.exists():
            source = json.loads(source_output.read_text(encoding='utf8'))
            for key, item in source.items():
                if key not in ('started_at_utc', 'finished_at_utc', 'command'):
                    record[key] = item
            record['source_started_at_utc'] = source.get('started_at_utc')
            record['source_finished_at_utc'] = source.get('finished_at_utc')
        if source_log.exists():
            shutil.copyfile(source_log, log)
            record['log_sha256'] = digest(log)
            record['raw_source_log_sha256'] = digest(source_log)
        assert result.returncode == 0 and record.get('terminal_ok') and record.get('frozen_equal'), 'source suite failed'
        record['status'] = 'passed'
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
    finally:
        if rows is not None and manifest_sha is not None:
            try:
                after = observe(rows)
                record['external_fixtures_after'] = after
                record['external_fixtures_equal'] = after == record.get('external_fixtures_before') == record.get('external_fixtures_expected')
                record['external_fixture_manifest_unchanged'] = digest(manifest) == manifest_sha
            except BaseException as exc:
                record['external_fixtures_equal'] = False
                record['external_fixture_error'] = {'type': type(exc).__name__, 'message': str(exc)}
        record['verification_scripts_equal'] = (
            digest(Path(__file__)) == wrapper_before and digest(runner) == runner_before
            and digest(materializer) == definition_before)
        if (not record.get('external_fixtures_equal')
                or not record.get('external_fixture_manifest_unchanged')
                or not record['verification_scripts_equal']):
            record['status'] = 'failed'
        record['terminal_ok'] = record['status'] == 'passed'
        if not record['terminal_ok']:
            record['exit_code'] = 1
        record['finished_at_utc'] = utc()
        save()
    print(json.dumps({k: record.get(k) for k in ('status', 'methods', 'skipped', 'suite_launched',
          'frozen_equal', 'external_fixture_count', 'external_fixtures_equal', 'terminal_ok')}))
    return 0 if record['terminal_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
