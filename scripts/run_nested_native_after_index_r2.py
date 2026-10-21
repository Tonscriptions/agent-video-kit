"""Bind a published index baseline and run one frozen complete nested-clock suite."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
INDEX = MAIN / 'product/.runtime/reverse-index-lab-20261021'
REL = 'docs/validation/evidence/nested-native-clock-20261021-lab'
INDEX_REL = 'docs/validation/evidence/native-frame-index-20261021-lab'
REPORT = 'docs/validation/嵌套原生VFR时钟独立实验_2026-10-21.md'
CONTRACT = 'docs/specs/嵌套原生VFR时钟契约_实验_v0.1_2026-10-21.md'
MODIFIED = {'product/src/ai_ad_editor/' + name + '.py' for name in ('render', 'reverse_video_clock', 'capabilities')}
MODIFIED.add('product/tests/test_cli.py')
ADDED = {'product/tests/test_nested_native_clock.py'}
SCRIPTS = ('run_nested_native_after_index_r2.py', 'run_frozen_regression.py',
           'run_with_regression_fixtures.py', 'materialize_regression_fixtures.py',
           'run_nested_native_regressions.py', 'smoke_nested_native_clock.py',
           'verify_nested_native_clock_install.py', 'finalize_nested_native_clock_lab.py',
           'prepare_nested_native_skills.py', 'run_nested_native_regressions_r2.py',
           'audit_nested_contract_refresh.py', 'run_nested_contract_controls.py')


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.writing')
    with temporary.open('w', encoding='utf8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(60):
        try:
            os.replace(temporary, path)
            return
        except OSError as error:
            if getattr(error, 'winerror', None) not in {5, 32, 33} or attempt == 59:
                raise
            time.sleep(min(.05 * (attempt + 1), .25))


def git(*args):
    result = subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args],
                            cwd=MAIN, capture_output=True, timeout=1200)
    assert result.returncode == 0, result.stderr.decode('utf8', 'replace')
    return result.stdout


def source_gate():
    current = frozen()
    base = ROOT / REL
    audit = read(base / 'audit-r2.json')
    assert audit['status'] == 'passed-standalone-audit' and audit['targeted_methods'] == 277
    assert len(current) == 255 and audit['frozen_inputs'] == current
    for name, digest in audit['documents'].items():
        assert sha(ROOT / name) == digest, name
    for name, row in audit['media'].items():
        assert sha(ROOT / name) == row['sha256'], name
    for name, digest in read(base / 'installed-r1/verification.json')['resource_hashes'].items():
        assert sha(ROOT / 'product/src/ai_ad_editor' / name) == digest, name
    related = read(base / 'related-r2.json')
    assert related['status'] == 'passed-related-regressions' and related['distinct_methods'] == 277
    assert related['frozen_before'] == related['frozen_after'] == current
    skills = read(base / 'skills-draft-r1.json')
    assert skills['status'] == 'passed-four-unregistered-skill-drafts' and skills['skill_count'] == 4
    for row in skills['results']:
        assert sha(ROOT / 'skills' / row['skill'] / 'SKILL.md') == row['draft_sha256']
        assert sha(ROOT / row['main_parent_snapshot']) == row['main_parent_sha256']
    previous = read(base / 'foundation-r1.json')['source_inputs']
    assert len(previous) == 254 and set(current) - set(previous) == ADDED
    assert {name for name in previous if previous[name] != current[name]} == MODIFIED
    fixture = read(base / 'external-fixtures-r1.json')
    assert fixture['status'] == 'passed' and len(fixture['fixtures']) == 8
    for row in fixture['fixtures']:
        assert sha(ROOT / row['path']) == row['sha256']
    scripts = {name: sha(ROOT / 'scripts' / name) for name in SCRIPTS}
    return current, previous, scripts


def docs_status(message):
    base = ROOT / REL
    snapshot = base / 'before-full-documents-r2.json'
    if not snapshot.exists():
        audit = read(base / 'audit-r2.json')
        directory = base / 'before-full-documents-r2'
        directory.mkdir()
        rows = {}
        for name, digest in audit['documents'].items():
            source = ROOT / name
            assert sha(source) == digest
            target = directory / source.name
            target.write_bytes(source.read_bytes())
            rows[name] = {'sha256': digest, 'snapshot': target.relative_to(ROOT).as_posix()}
        save(snapshot, {'status': 'preserved', 'documents': rows, 'audit_sha256': sha(base / 'audit-r2.json')})
    marker = 'NATIVE-NESTED-FULL-R2'
    for name in ('README.md', REPORT, CONTRACT):
        path = ROOT / name
        value = path.read_text('utf8')
        for before, after in (
                ('尚未完整回归或合入 main。', '完整回归状态见最新记录；尚未合入 main。'),
                ('尚未执行该版本完整回归、尚未合入 main。', '专项阶段未执行完整回归；当前完整回归状态见最新记录，尚未合入 main。'),
                ('未运行该版本完整套件、未合入 main、未推送此实验', '专项阶段未运行完整套件；最新完整回归状态见文首，尚未合入或推送此实验'),
                ('此版本完整回归、合入和推送仍未执行。', '完整回归状态见最新记录；此实验尚未合入或推送。')):
            value = value.replace(before, after)
        block = '<!-- ' + marker + ' -->\n' + message + '\n<!-- /' + marker + ' -->'
        pattern = re.escape('<!-- ' + marker + ' -->') + '.*?' + re.escape('<!-- /' + marker + ' -->')
        if re.search(pattern, value, re.S):
            value = re.sub(pattern, lambda _: block, value, flags=re.S)
        else:
            at = value.index('\n')
            value = value[:at] + '\n\n' + block + '\n' + value[at:]
        path.write_text(value.rstrip() + '\n', encoding='utf8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--upstream-publication', type=Path)
    parser.add_argument('--html-runtime', type=Path)
    parser.add_argument('--rubberband', type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    work = args.work.resolve()
    assert sys.platform == 'win32' and work.is_relative_to(ROOT / 'product/.runtime') and not work.exists()
    work.mkdir(parents=True)
    state = {'status': 'checking-source', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
             'suite_launched': False, 'expected_methods': 1957, 'main_integrated': False}
    def checkpoint():
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(work / 'run.json', state)
    try:
        current, previous, scripts = source_gate()
        state.update(status='passed-source-preflight-awaiting-published-index', frozen_inputs=current,
                     upstream_inputs=previous, verification_scripts=scripts)
        checkpoint()
        if args.preflight_only:
            return
        assert args.upstream_publication and args.html_runtime and args.rubberband
        publication = args.upstream_publication.resolve(strict=True)
        assert publication.is_relative_to(INDEX / 'product/.runtime') and publication.name == 'run.json'
        upstream = read(publication)
        assert upstream['status'] == 'published' and upstream['full_methods'] == 1925
        commit = upstream['commit']
        assert upstream['remote_main'] == commit and upstream['main_clean']
        full_previous = read(INDEX / INDEX_REL / 'full-r1.json')
        assert full_previous['status'] == 'passed' and full_previous['terminal_ok']
        assert full_previous['methods'] == 1925 and full_previous['skipped'] == 0
        assert full_previous['frozen_before'] == full_previous['frozen_after'] == previous
        assert full_previous['external_fixture_count'] == 8 and full_previous['external_fixtures_equal']
        assert full_previous['verification_scripts_equal'] and full_previous['external_fixture_manifest_unchanged']
        assert git('branch', '--show-current').decode().strip() == 'main'
        assert git('remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git('rev-parse', 'HEAD').decode().strip() == commit
        assert git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
        assert not git('status', '--porcelain', '-z')
        spec = importlib.util.spec_from_file_location('nested_index_published_freeze', MAIN / 'scripts/run_frozen_regression.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.frozen() == previous and frozen() == current
        assert sha(MAIN / INDEX_REL / 'full-r1.json') == sha(INDEX / INDEX_REL / 'full-r1.json')
        base = ROOT / REL
        save(base / 'published-index-alignment-r2.json', {
            'status': 'passed', 'published_commit': commit, 'remote_main': commit,
            'upstream_inputs': previous, 'candidate_inputs': current,
            'modified_existing_inputs': sorted(MODIFIED), 'added_inputs': sorted(ADDED),
            'main_clean_before_suite': True, 'upstream_full_sha256': sha(INDEX / INDEX_REL / 'full-r1.json'),
            'publication_record_sha256': sha(publication), 'generator_sha256': sha(__file__)})
        output = base / 'full-r2.json'
        assert not output.exists()
        docs_status('已绑定帧索引发布提交 `' + commit[:12] + '`，启动此版本的 **1957 方法**完整原生回归；尚未标记通过、合入或发布。')
        command = [sys.executable, '-E', '-B', '-X', 'utf8', str(ROOT / 'scripts/run_with_regression_fixtures.py'),
                   '--fixture-manifest', str(base / 'external-fixtures-r1.json'), '--output', str(output),
                   '--html-runtime', str(args.html_runtime.resolve(strict=True)),
                   '--rubberband', str(args.rubberband.resolve(strict=True))]
        state.update(status='running-complete-native-suite', suite_launched=True,
                     published_index_commit=commit, command=command)
        checkpoint()
        with (base / 'full-r2.launcher.log').open('xb') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        item = read(output)
        assert result.returncode == 0 and item['status'] == 'passed' and item['terminal_ok']
        assert item['methods'] == 1957 and item['skipped'] == 0
        assert item['frozen_before'] == item['frozen_after'] == frozen() == current
        assert item['external_fixture_count'] == 8 and item['external_fixtures_equal']
        assert item['verification_scripts_equal'] and item['external_fixture_manifest_unchanged']
        assert all(sha(ROOT / 'scripts' / name) == digest for name, digest in scripts.items())
        docs_status('完整原生回归 **1957 方法、' + format(item['suite_seconds'], '.3f')
                    + ' 秒、0 跳过**；255 产品输入及 8 外部夹具不变。尚未合入 main 或推送此实验。')
        state.update(status='passed-complete-suite-awaiting-reviewed-integration', methods=1957,
                     full_sha256=sha(output), suite_seconds=item['suite_seconds'])
    except BaseException as error:
        state.update(status='failed', error={'type': type(error).__name__, 'message': str(error)})
        if state['suite_launched']:
            docs_status('完整回归或收据校验未通过；保留实际日志，尚未合入或发布此实验。')
        raise
    finally:
        checkpoint()
        print(json.dumps({k: state.get(k) for k in ('status', 'suite_launched', 'methods', 'error')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
