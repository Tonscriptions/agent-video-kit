"""Serialize the full native suite behind the actually published V96 parent."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
PARENT = ROOT.parent/'float-standard-render-lab-20261022'
REL = ROOT/'docs/validation/evidence/float-preview-20261022-lab'


def read(path):
    for attempt in range(12):
        try:
            return json.loads(path.read_bytes())
        except (OSError, ValueError):
            if attempt == 11: raise
            time.sleep(.025)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def verify(base, entries):
    assert all(sha(base/name) == digest for name, digest in entries.items())


def git(*args):
    return subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args], cwd=MAIN,
        capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout


def main():
    work = ROOT/'product/.runtime/float-preview-20261022/complete-r1'; output = REL/'full-r1.json'
    assert not work.exists() and not output.exists(); work.mkdir(parents=True)
    state = {'status': 'checking', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
        'expected_methods': 2355, 'suite_launched': False, 'published': False,
        'native_windows': True, 'network': False, 'virtualization': False}
    def checkpoint(): save(work/'run.json', state)
    checkpoint()
    try:
        before = frozen(); assert len(before) == 300
        foundation = read(REL/'foundation-r1.json'); parent_inputs = foundation['parent_frozen_inputs']
        assert len(parent_inputs) == 298
        changed = {'product/src/ai_ad_editor/preview.py', 'product/src/ai_ad_editor/capabilities.py'}
        added = {'product/src/ai_ad_editor/float_preview.py', 'product/tests/test_float_preview.py'}
        assert {k for k in parent_inputs if before[k] != parent_inputs[k]} == changed
        assert set(before)-set(parent_inputs) == added
        deps = foundation['dependency_artifact_inputs']; assert len(deps) == 9; verify(ROOT, deps)
        scripts = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT/'scripts').glob('*.py'))}
        state.update(status='waiting-for-actual-V96-publication-and-isolated-install', frozen_inputs=before,
                     verification_scripts=scripts, dependency_artifact_inputs=deps); checkpoint()
        owner_path = PARENT/'product/.runtime/float-standard-20261022/release-chain-r1/run.json'
        while True:
            parent = read(owner_path); assert 'failed' not in parent['status'], parent
            installed_path = REL/'installed-r1/verification.json'
            installed = read(installed_path) if installed_path.exists() else {}
            assert 'failed' not in installed.get('status', ''), installed.get('error')
            if (parent['status'] == 'published-V96-with-actual-full2337-and-installed220' and
                installed.get('status') == 'passed-fresh-eight-wheel-180-resources-real-previews-and-260-methods'):
                break
            time.sleep(5)
        verify(ROOT, before); verify(ROOT, scripts); verify(ROOT, deps)
        assert installed['frozen_before'] == installed['frozen_after'] == before
        assert installed['isolated_methods']['methods'] == 260 and installed['isolated_methods']['skipped'] == 0
        assert len(installed['resource_hashes']) == 180
        native = read(REL/'native-r2/verification.json')
        assert native['status'] == 'passed' and native['methods'] == 57 and native['frozen_after'] == before and not native['skipped']
        for name in ('media-r1', 'media-installed-r1'):
            media = read(REL/name/'verification.json')
            assert media['status'] == 'passed-public-CLI-original-edited-and-native-float-previews'
            assert media['frozen_before'] == media['frozen_after'] == before
            assert media['actual_public_render_CLI_processes'] == 2 and media['actual_public_preview_CLI_processes'] == 3
            assert all(c['ok'] for c in media['checks'])
        parent_full_path = MAIN/'docs/validation/evidence/float-standard-20261022-lab/full-r1.json'
        parent_full = read(parent_full_path)
        assert parent_full['status'] == 'passed' and parent_full['terminal_ok'] and parent_full['methods'] == 2337 and parent_full['skipped'] == 0
        assert parent_full['frozen_before'] == parent_full['frozen_after'] == parent_inputs
        commit = git('rev-parse', 'HEAD').decode().strip()
        assert commit == parent['commit'] == parent['remote_main']
        assert git('branch', '--show-current').decode().strip() == 'main'
        assert git('remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
        assert not git('status', '--porcelain', '-z'), 'Preserve unexpected main edits'
        spec = importlib.util.spec_from_file_location('published_preview_parent', MAIN/'scripts/run_frozen_regression.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        assert module.frozen() == parent_inputs
        fixtures = foundation['external_fixtures']; assert len(fixtures) == 8
        for row in fixtures:
            assert sha(ROOT/row['path']) == row['sha256'] and (ROOT/row['path']).stat().st_size == row['bytes']
            assert parent_full['external_fixtures_expected'][row['path']]['sha256'] == row['sha256']
        fixture_path = REL/'external-fixtures-r1.json'
        save(fixture_path, {'status': 'passed', 'fixtures': fixtures, 'copied_from_frozen_parent_manifest': True,
                           'no_materialization': True, 'published_parent_commit': commit})
        lineage = REL/'parent-binding-r1.json'
        save(lineage, {'status': 'passed-published-V96-parent-binding', 'published_parent_commit': commit,
            'published_parent_frozen': parent_inputs, 'frozen_after': before, 'changed_parent_inputs': sorted(changed),
            'parent_full_methods': 2337, 'parent_full_sha256': sha(parent_full_path), 'parent_release_owner_sha256': sha(owner_path)})
        env = dict(os.environ); env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES', None)
        discovery = 'import sys,unittest;sys.path.insert(0,sys.argv[1]);from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();print(unittest.defaultTestLoader.discover(sys.argv[2]).countTestCases())'
        count = subprocess.run([sys.executable, '-E', '-B', '-X', 'utf8', '-c', discovery, str(ROOT/'product/src'), str(ROOT/'product/tests')],
            cwd=ROOT, env=env, capture_output=True, check=True)
        state.update(discovery_stdout=count.stdout.decode('utf8', 'replace'), discovery_stderr=count.stderr.decode('utf8', 'replace'))
        assert int(state['discovery_stdout'].strip()) == 2355
        evidence = [REL/name for name in ('foundation-r1.json', 'native-r2/verification.json', 'installed-r1/verification.json',
            'media-r1/verification.json', 'media-installed-r1/verification.json', 'static-review-r1.json', 'black-precision-review-r1.json')]+[fixture_path, lineage]
        bound = {p.relative_to(ROOT).as_posix(): sha(p) for p in evidence}
        command = list(map(str, [sys.executable, '-E', '-B', '-X', 'utf8', ROOT/'scripts/run_with_regression_fixtures.py',
            '--fixture-manifest', fixture_path, '--output', output,
            '--html-runtime', MAIN/'product/.runtime/html-motion-runtime-20261018-e2.json',
            '--rubberband', MAIN/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe']))
        state.update(status='running-complete-native-suite', suite_launched=True, published_parent_commit=commit, bound_evidence=bound, command=command); checkpoint()
        with (REL/'full-r1.launcher.log').open('xb') as log:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        full = read(output); state['suite_exit_code'] = result.returncode
        assert result.returncode == 0 and full['status'] == 'passed' and full['terminal_ok'] and full['methods'] == 2355 and full['skipped'] == 0
        assert full['frozen_before'] == full['frozen_after'] == before == frozen()
        assert full['external_fixture_count'] == 8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        verify(ROOT, scripts); verify(ROOT, deps); verify(ROOT, bound)
        state.update(status='passed-complete-native-suite-not-published', methods=2355, suite_seconds=full['suite_seconds'], full_receipt_sha256=sha(output))
    except BaseException as exc:
        state.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat(); checkpoint()
        (REL/'full-r1.executed-owner.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k: state.get(k) for k in ['status', 'suite_launched', 'methods', 'error']}), flush=True)


if __name__ == '__main__':
    main()
