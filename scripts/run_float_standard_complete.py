"""Serialize the complete 2337-method suite behind published V95 and R16."""
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
REL = ROOT/'docs/validation/evidence/float-standard-20261022-lab'
PARENT = ROOT.parent/'float-render-lab-20261022'
RESEARCH = ROOT.parent/'openfilm-reuse-lab-20261022-r16'


def read(path):
    for attempt in range(12):
        try:
            return json.loads(path.read_bytes())
        except (OSError, ValueError):
            if attempt == 11:
                raise
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
    work = ROOT/'product/.runtime/float-standard-20261022/complete-r1'
    output = REL/'full-r1.json'
    assert not work.exists() and not output.exists()
    work.mkdir(parents=True)
    record = {'status': 'checking', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
              'expected_methods': 2337, 'suite_launched': False, 'published': False,
              'native_windows': True, 'network': False, 'virtualization': False}
    def checkpoint():
        save(work/'run.json', record)
    checkpoint()
    try:
        before = frozen(); assert len(before) == 298
        foundation = read(REL/'foundation-r1.json'); parent_inputs = foundation['parent_frozen_inputs']
        assert len(parent_inputs) == 296 and not set(parent_inputs)-set(before)
        expected_changed = {'docs/specs/agent-project.schema.json', *('product/src/ai_ad_editor/'+n for n in
            ['agent-project.schema.json', 'capabilities.py', 'float_stream.py', 'float_timeline.py', 'render.py', 'schema_contract.py', 'validator.py'])}
        assert {k for k in parent_inputs if before[k] != parent_inputs[k]} == expected_changed
        assert set(before)-set(parent_inputs) == {'product/src/ai_ad_editor/float_standard_render.py', 'product/tests/test_float_standard_render.py'}
        deps = foundation['dependency_artifact_inputs']; assert len(deps) == 9; verify(ROOT, deps)
        scripts = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT/'scripts').glob('*.py'))}
        record.update(status='waiting-for-actual-V95-R16-publication-and-isolated-install', frozen_inputs=before,
                      verification_scripts=scripts, dependency_artifact_inputs=deps)
        checkpoint()
        parent_owner = PARENT/'product/.runtime/float-render-20261022/release-chain-r1/run.json'
        research_owner = RESEARCH/'product/.runtime/openfilm-r16-release/serialized-owner-r1/run.json'
        while True:
            parent, research = read(parent_owner), read(research_owner)
            assert 'failed' not in parent['status'], parent
            assert 'failed' not in research['status'], research
            installed_path = REL/'installed-r1/verification.json'
            installed = read(installed_path) if installed_path.exists() else {}
            assert 'failed' not in installed.get('status', ''), installed.get('error')
            if (parent['status'] == 'published-V95-with-actual-full2320-and-installed203' and
                    research['status'] == 'published-R16-research' and
                    installed.get('status') == 'passed-fresh-eight-wheel-179-resources-real-CLI-media-and-220-methods'):
                break
            time.sleep(5)
        verify(ROOT, before); verify(ROOT, scripts); verify(ROOT, deps)
        assert installed['frozen_before'] == installed['frozen_after'] == before
        assert installed['isolated_methods']['methods'] == 220 and installed['isolated_methods']['skipped'] == 0
        assert len(installed['resource_hashes']) == 179
        terminal = read(REL/'standard-r5/verification.json')
        assert terminal['status'] == 'passed' and terminal['methods'] == 17 and terminal['frozen_after'] == before
        for name in ('media-r4', 'media-installed-r1'):
            media = read(REL/name/'verification.json')
            assert media['status'] == 'passed-public-CLI-original-and-edited-native-float-media'
            assert media['frozen_before'] == media['frozen_after'] == before and media['actual_public_render_CLI_processes'] == 2
            assert all(c['ok'] for c in media['checks'])
        parent_full = read(MAIN/'docs/validation/evidence/float-render-20261022-lab/full-r1.json')
        assert parent_full['status'] == 'passed' and parent_full['terminal_ok'] and parent_full['methods'] == 2320 and parent_full['skipped'] == 0
        assert parent_full['frozen_before'] == parent_full['frozen_after'] == parent_inputs
        commit = git('rev-parse', 'HEAD').decode().strip()
        assert commit == research['commit'] == research['remote_main']
        assert git('rev-parse', 'HEAD^').decode().strip() == parent['commit'] == research['parent_commit']
        assert git('branch', '--show-current').decode().strip() == 'main'
        assert git('remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
        assert not git('status', '--porcelain', '-z'), 'Preserve unexpected main edits'
        spec = importlib.util.spec_from_file_location('published_standard_parent', MAIN/'scripts/run_frozen_regression.py')
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
        save(lineage, {'status': 'passed-published-V95-plus-R16-parent-binding', 'published_parent_commit': commit,
            'published_product_parent_commit': parent['commit'], 'published_parent_frozen': parent_inputs,
            'frozen_after': before, 'changed_parent_inputs': sorted(expected_changed), 'parent_full_methods': 2320,
            'parent_full_sha256': sha(MAIN/'docs/validation/evidence/float-render-20261022-lab/full-r1.json'),
            'research_owner_sha256': sha(research_owner), 'parent_release_owner_sha256': sha(parent_owner)})
        env = dict(os.environ); env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES', None)
        discovery = 'import sys,unittest;sys.path.insert(0,sys.argv[1]);from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();print(unittest.defaultTestLoader.discover(sys.argv[2]).countTestCases())'
        count = subprocess.run([sys.executable, '-E', '-B', '-X', 'utf8', '-c', discovery, str(ROOT/'product/src'), str(ROOT/'product/tests')], cwd=ROOT, env=env, capture_output=True, check=True)
        record.update(discovery_stdout=count.stdout.decode('utf8', 'replace'), discovery_stderr=count.stderr.decode('utf8', 'replace'))
        assert int(record['discovery_stdout'].strip()) == 2337
        inputs = [REL/name for name in ('foundation-r1.json', 'standard-r5/verification.json', 'installed-r1/verification.json',
                  'media-r4/verification.json', 'media-installed-r1/verification.json')]+[fixture_path, lineage]
        bound = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
        command = list(map(str, [sys.executable, '-E', '-B', '-X', 'utf8', ROOT/'scripts/run_with_regression_fixtures.py',
            '--fixture-manifest', fixture_path, '--output', output,
            '--html-runtime', MAIN/'product/.runtime/html-motion-runtime-20261018-e2.json',
            '--rubberband', MAIN/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe']))
        record.update(status='running-complete-native-suite', suite_launched=True, published_parent_commit=commit, bound_evidence=bound, command=command)
        checkpoint()
        with (REL/'full-r1.launcher.log').open('xb') as log:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        full = read(output); record['suite_exit_code'] = result.returncode
        assert result.returncode == 0 and full['status'] == 'passed' and full['terminal_ok'] and full['methods'] == 2337 and full['skipped'] == 0
        assert full['frozen_before'] == full['frozen_after'] == before == frozen()
        assert full['external_fixture_count'] == 8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        verify(ROOT, scripts); verify(ROOT, deps); verify(ROOT, bound)
        record.update(status='passed-complete-native-suite-not-published', methods=2337, suite_seconds=full['suite_seconds'], full_receipt_sha256=sha(output))
    except BaseException as exc:
        record.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        record['updated_at_utc'] = datetime.now(timezone.utc).isoformat(); checkpoint()
        (REL/'full-r1.executed-owner.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k: record.get(k) for k in ['status', 'suite_launched', 'methods', 'error']}), flush=True)


if __name__ == '__main__':
    main()
