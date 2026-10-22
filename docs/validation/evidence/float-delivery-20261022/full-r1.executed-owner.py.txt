"""Run the final 300-input suite after the already live 292-input suite ends."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import float_delivery_bundle as bundle

ROOT, MAIN, REL, WORK = bundle.ROOT, bundle.MAIN, bundle.REL, bundle.WORK
read, save, sha, verify = bundle.read, bundle.save, bundle.sha, bundle.verify


def read_state(path):
    for attempt in range(12):
        try:
            return read(path)
        except (OSError, ValueError):
            if attempt == 11:
                raise
            time.sleep(.025)


def main():
    work = WORK / 'complete-r1'
    output = ROOT / REL / 'full-r1.json'
    assert not work.exists() and not output.exists()
    work.mkdir(parents=True)
    state = {'status': 'checking-final-source-bundle', 'pid': os.getpid(),
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'expected_methods': 2355,
        'suite_launched': False, 'published': False, 'native_windows': True, 'network': False,
        'virtualization': False, 'intermediate_V95_V96_full_suites_claimed_passed': False}

    def checkpoint():
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(work / 'run.json', state)

    checkpoint()
    try:
        prepared = bundle.audit()
        before = prepared['frozen_inputs']
        scripts = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / 'scripts').glob('*.py'))}
        deps = prepared['dependency_artifact_inputs']
        state.update(status='waiting-for-actual-V94-full2299-before-final300-suite', frozen_inputs=before,
            verification_scripts=scripts, dependency_artifact_inputs=deps,
            preparation_receipt_sha256=sha(ROOT / REL / 'prepared-r1.json'))
        checkpoint()
        parent_root = ROOT.parent / 'float-stream-lab-20261022'
        parent_owner_path = parent_root / 'product/.runtime/float-stream-20261022/complete-r2/run.json'
        while True:
            parent_owner = read_state(parent_owner_path)
            if parent_owner['status'] == 'passed-complete-native-suite-not-published':
                break
            assert parent_owner['status'] in ('checking', 'waiting-for-actual-parent-publication-and-isolated-install',
                'running-complete-native-suite'), parent_owner.get('error', parent_owner['status'])
            time.sleep(5)
        parent_full_path = parent_root / 'docs/validation/evidence/float-stream-20261022-lab/full-r2.json'
        parent_full = read(parent_full_path)
        first = read(ROOT / prepared['components'][0]['gate'])
        assert parent_owner['methods'] == 2299 and parent_owner['full_receipt_sha256'] == sha(parent_full_path)
        assert parent_full['status'] == 'passed' and parent_full['terminal_ok'] and parent_full['methods'] == 2299 and parent_full['skipped'] == 0
        assert parent_full['frozen_before'] == parent_full['frozen_after'] == first['source_inputs']
        assert parent_full['external_fixtures_equal'] and parent_full['verification_scripts_equal']
        verify(ROOT, before)
        verify(ROOT, scripts)
        verify(ROOT, deps)
        assert bundle.audit() == prepared
        commit = bundle.git('rev-parse', 'HEAD').decode().strip()
        assert commit == prepared['published_parent_commit'] == parent_owner['published_parent_commit']
        assert bundle.git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
        assert bundle.git('branch', '--show-current').decode().strip() == 'main'
        assert not bundle.git('status', '--porcelain', '-z'), 'Preserve unexpected main edits'
        verify(MAIN, prepared['published_parent_inputs'])
        fixture_path = ROOT / REL / 'external-fixtures-r1.json'
        fixtures = prepared['external_fixtures']
        for row in fixtures:
            assert sha(ROOT / row['path']) == row['sha256'] and (ROOT / row['path']).stat().st_size == row['bytes']
            assert parent_full['external_fixtures_expected'][row['path']]['sha256'] == row['sha256']
        save(fixture_path, {'status': 'passed', 'fixtures': fixtures, 'copied_from_frozen_parent_manifest': True,
            'no_materialization': True, 'published_parent_commit': commit})
        # Keep the two actual snapshots distinct: 292 was tested but not separately published.
        save(ROOT / REL / 'tested-predecessor-full-r1.json', parent_full)
        save(ROOT / REL / 'tested-predecessor-owner-r1.json', parent_owner)
        lineage_path = ROOT / REL / 'parent-binding-r1.json'
        save(lineage_path, {'status': 'passed-published-V93-R16-and-tested292-lineage',
            'published_parent_commit': commit, 'published_parent_frozen': prepared['published_parent_inputs'],
            'tested_predecessor_frozen': first['source_inputs'], 'tested_predecessor_methods': 2299,
            'tested_predecessor_full_sha256': sha(parent_full_path), 'tested_predecessor_owner_sha256': sha(parent_owner_path),
            'final_frozen': before, 'changed_product_paths': prepared['changed_product_paths'],
            'added_product_paths': prepared['added_product_paths'], 'separate_V95_V96_full_suites_executed': False})
        env = dict(os.environ)
        env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES', None)
        discovery = ('import sys,unittest;sys.path.insert(0,sys.argv[1]);'
            'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
            'print(unittest.defaultTestLoader.discover(sys.argv[2]).countTestCases())')
        result = subprocess.run([sys.executable, '-E', '-B', '-X', 'utf8', '-c', discovery,
            str(ROOT / 'product/src'), str(ROOT / 'product/tests')], cwd=ROOT, env=env, capture_output=True, check=True)
        state.update(discovery_stdout=result.stdout.decode('utf8', 'replace'), discovery_stderr=result.stderr.decode('utf8', 'replace'))
        assert int(state['discovery_stdout'].strip()) == 2355
        paths = [ROOT / REL / name for name in ('prepared-r1.json', 'tested-predecessor-full-r1.json',
            'tested-predecessor-owner-r1.json', 'parent-binding-r1.json', 'external-fixtures-r1.json')]
        bound = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
        command = list(map(str, [sys.executable, '-E', '-B', '-X', 'utf8', ROOT / 'scripts/run_with_regression_fixtures.py',
            '--fixture-manifest', fixture_path, '--output', output,
            '--html-runtime', MAIN / 'product/.runtime/html-motion-runtime-20261018-e2.json',
            '--rubberband', MAIN / 'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe']))
        state.update(status='running-complete-native-suite', suite_launched=True, published_parent_commit=commit,
            bound_evidence=bound, command=command)
        checkpoint()
        with (ROOT / REL / 'full-r1.launcher.log').open('xb') as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
        full = read(output)
        state['suite_exit_code'] = result.returncode
        assert result.returncode == 0 and full['status'] == 'passed' and full['terminal_ok']
        assert full['methods'] == 2355 and full['skipped'] == 0 and full['frozen_before'] == full['frozen_after'] == before
        assert full['external_fixture_count'] == 8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged']
        assert full['verification_scripts_equal']
        verify(ROOT, before)
        verify(ROOT, scripts)
        verify(ROOT, deps)
        verify(ROOT, bound)
        state.update(status='passed-complete-native-suite-not-published', methods=2355, suite_seconds=full['suite_seconds'],
            full_receipt_sha256=sha(output), frozen_equal=True, dependencies_equal=True, verification_scripts_equal=True)
    except BaseException as exc:
        state.update(status='failed-preserved', error=repr(exc))
        raise
    finally:
        (ROOT / REL / 'full-r1.executed-owner.py.txt').write_bytes(Path(__file__).read_bytes())
        checkpoint()
        print(json.dumps({k: state.get(k) for k in ('status', 'suite_launched', 'methods', 'error')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
