"""Publish the frozen R16 research after recovered V93, before another full suite."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import release_openfilm_r16 as original

ROOT, MAIN, REL = original.ROOT, original.MAIN, original.REL
WORK = ROOT / 'product/.runtime/openfilm-r16-release/serialized-owner-r2'
PARENT = MAIN / 'product/.runtime/float-timeline-lab-20261022'
SCRIPT = 'scripts/recover_openfilm_r16_release.py'
sha, read, save = original.sha, original.read, original.save


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def documents(destination):
    names = original.documents(destination)
    path = destination / 'README.md'
    text = path.read_text('utf8')
    row = ('| R16-06 | 恢复后的独立发布 | 原等待队列因前序暂存字节断言停止；保留失败记录，绑定已发布 V93 的 288 个产品输入，研究发布不改产品且不重复计测试 | '
        '[恢复核验](docs/validation/evidence/openfilm-reuse-20261022-r16/release-recovery-r1.json) |\n')
    marker = '<!-- /R16-OPENFILM-025-REUSE -->'
    assert marker in text and 'R16-06' not in text
    path.write_text(text.replace('\n' + marker, row + '\n' + marker, 1), encoding='utf8', newline='\n')
    index = 'docs/README.md'
    text = (MAIN / index).read_text('utf8')
    title, rest = text.split('\n', 1)
    note = ('\n\n<!-- R16-RESEARCH-INDEX -->\nOpenFilm v0.2.5 的 13 类拆用取舍、规划工时、上游 45 通过/1 条件跳过及边界见 '
        '[R16 复核](OpenFilm_0.2.5可拆模块与复用成本评估_2026-10-22.md)。该研究没有新增产品功能或模型结果。\n<!-- /R16-RESEARCH-INDEX -->\n')
    target = destination / index
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(title + note + rest, encoding='utf8', newline='\n')
    return [*names, index]


def update_progress(state):
    path = MAIN / 'product/.runtime/agent-video-kit-progress-20261021.json'
    old = path.read_bytes()
    data = json.loads(old)
    backup = WORK / 'private-progress-before.json'
    backup.write_bytes(old)
    data['main'].update(commit=state['commit'], remote_main=state['remote_main'], clean=True,
        latest_documentation_update='V93 actual full2280/installed163 retained; R16 OpenFilm 0.2.5 scoped research45pass1skip published; no new product feature')
    data.setdefault('openfilm_r16', {}).update(status='published-R16-research', commit=state['commit'],
        remote_main=state['remote_main'], report=str(MAIN / original.REPORT), upstream_passed=45,
        upstream_skipped=1, new_product_features=0, new_media=0, publication_record=str(WORK / 'run.json'))
    data.update(updated_at_utc=datetime.now(timezone.utc).isoformat(), previous_progress_snapshot=str(backup), goal_status='active')
    assert path.read_bytes() == old, 'Concurrent private progress change'
    save(path, data)


def main():
    WORK.mkdir(parents=True, exist_ok=False)
    state = {'status': 'checking-frozen-research-after-recovered-V93', 'pid': os.getpid(),
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'generator_sha256': sha(Path(__file__)),
        'force_push': False, 'published': False, 'main_changed': False}

    def checkpoint():
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(WORK / 'run.json', state)

    checkpoint()
    try:
        old_manifest = ROOT / REL / 'release-manifest-r2.json'
        manifest = read(old_manifest)
        assert len(manifest['files']) == 45 and manifest['generator_sha256'] == sha(Path(original.__file__))
        for name, digest in manifest['files'].items():
            assert sha(ROOT / name) == digest, name
        research = original.source_gate()
        assert all(research[name] == digest for name, digest in manifest['files'].items()
            if name != (REL / 'readme-preview-r2.json').as_posix())
        parent = read(PARENT / 'product/.runtime/float-timeline-20261022/release-chain-r3/run.json')
        publication = read(PARENT / 'product/.runtime/float-timeline-20261022/publication-r3/run.json')
        assert parent['status'] == 'published-V93-with-actual-full2280-and-installed163'
        assert publication['status'] == 'published' and publication['main_clean'] and not publication['force_push']
        commit = parent['commit']
        assert commit == parent['remote_main'] == publication['commit'] == publication['remote_main']
        full = read(MAIN / 'docs/validation/evidence/float-timeline-20261022-lab/full-r2.json')
        assert full['status'] == 'passed' and full['terminal_ok'] and full['methods'] == 2280 and full['skipped'] == 0
        product = load(MAIN / 'scripts/run_frozen_regression.py', 'r16_recovery_product')
        inputs = product.frozen()
        assert inputs == full['frozen_before'] == full['frozen_after'] and len(inputs) == 288
        helper = load(MAIN / 'scripts/native_index_release_tools.py', 'r16_recovery_git')
        git = helper.git
        assert git(MAIN, 'branch', '--show-current').decode().strip() == 'main'
        assert git(MAIN, 'remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN, 'rev-parse', 'HEAD').decode().strip() == commit
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
        assert not git(MAIN, 'status', '--porcelain', '-z'), 'Preserve unexpected main changes'
        failure = ROOT / 'product/.runtime/openfilm-r16-release/serialized-owner-r1/run.json'
        assert read(failure)['status'] == 'failed-preserved' and not read(failure)['main_changed']
        assert not (ROOT / REL / 'failed-owner-r1.json').exists()
        shutil.copyfile(failure, ROOT / REL / 'failed-owner-r1.json')
        save(ROOT / REL / 'release-recovery-r1.json', {
            'status': 'passed-frozen-research-and-actual-published-V93-parent-checks',
            'original_release_manifest_sha256': sha(old_manifest), 'original_frozen_research_files': 45,
            'failed_owner_sha256': sha(ROOT / REL / 'failed-owner-r1.json'),
            'original_research_product_inputs': 282, 'publication_product_inputs': inputs,
            'published_parent_commit': commit, 'parent_full_methods': 2280, 'parent_installed_methods': 163,
            'actual_upstream_tests': {'passed': 45, 'skipped': 1, 'failed': 0}, 'new_product_features': 0,
            'new_test_executions': 0, 'new_media': 0, 'force_push': False,
            'schedule_change': 'publish research between recovered V93 and a new V94 full-suite owner',
            'generator_sha256': sha(Path(__file__)), 'published_claimed': False})
        rows = dict(manifest['files'])
        for name in [str(REL / 'release-manifest-r2.json'), str(REL / 'failed-owner-r1.json'),
                str(REL / 'release-recovery-r1.json'), SCRIPT]:
            rows[Path(name).as_posix()] = sha(ROOT / name)
        manifest_name = (REL / 'release-manifest-r3.json').as_posix()
        save(ROOT / manifest_name, {'status': 'ready-frozen-research-after-recovered-V93', 'files': rows,
            'base_commit': commit, 'old_manifest_sha256': sha(old_manifest), 'generator_sha256': sha(Path(__file__)),
            'actual_upstream_tests': manifest['actual_upstream_tests'], 'new_product_features': 0, 'force_push': False})
        rows[manifest_name] = sha(ROOT / manifest_name)
        preview = WORK / 'readme-preview'
        preview.mkdir()
        names = documents(preview)
        references = original.links(preview, names)
        stage = WORK / 'native-staging'
        stage.mkdir()
        for name in set(rows) | set(names):
            source = preview / name if name in names else ROOT / name
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        expected = {**rows, **{n: sha(stage / n) for n in names}}
        git(stage, 'init', '--quiet', '--initial-branch=main')
        git(stage, 'config', 'core.longpaths', 'true')
        pathspec = WORK / 'paths.nul'
        pathspec.write_bytes(b'\0'.join(n.encode('utf8') for n in sorted(expected)) + b'\0')
        git(stage, 'add', '--force', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
        helper.MAIN = stage
        compared = helper.staged_rows(expected)
        git(stage, 'diff', '--cached', '--check')
        helper.MAIN = MAIN
        preflight_name = (REL / 'staging-preflight-r3.json').as_posix()
        save(ROOT / preflight_name, {'status': 'passed-private-native-staging-original-bytes-and-document-links',
            'compared_blobs': len(compared), 'verified_links': len(references), 'files': expected,
            'main_changed': False, 'product_inputs_unchanged': product.frozen() == inputs,
            'generator_sha256': sha(Path(__file__))})
        rows[preflight_name] = sha(ROOT / preflight_name)
        state.update(status='publishing-verified-R16-research', parent_commit=commit, product_frozen_count=288)
        checkpoint()
        assert product.frozen() == inputs and git(MAIN, 'rev-parse', 'HEAD').decode().strip() == commit
        for name, digest in rows.items():
            target = MAIN / name
            assert not target.exists(), ('Unexpected existing research destination', name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
            assert sha(target) == digest
        names = documents(MAIN)
        references = original.links(MAIN, names)
        rows.update({n: sha(MAIN / n) for n in names})
        actual = {p.decode('utf8') for p in git(MAIN, 'diff', '--name-only', '-z').split(b'\0') if p}
        actual |= {p.decode('utf8') for p in git(MAIN, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p}
        assert actual <= set(rows), sorted(actual - set(rows))
        pathspec.write_bytes(b'\0'.join(n.encode('utf8') for n in sorted(rows)) + b'\0')
        git(MAIN, 'add', '--force', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
        compared = helper.staged_rows({**rows, **inputs})
        git(MAIN, 'diff', '--cached', '--check')
        assert not git(MAIN, 'diff', '--name-only') and product.frozen() == inputs
        receipt_name = (REL / 'publication-r3.json').as_posix()
        save(MAIN / receipt_name, {'status': 'passed-staged-research-publication-audit', 'parent_commit': commit,
            'upstream_head': 'af5756a88d362bdcd71dc870a0e02590420e6944', 'actual_upstream_tests': manifest['actual_upstream_tests'],
            'new_product_features': 0, 'new_media': 0, 'new_test_executions': 0, 'force_push': False,
            'verified_links': len(references), 'product_inputs_unchanged': product.frozen() == inputs,
            'product_inputs': inputs, 'staged_blobs': compared, 'original_manifest_sha256': sha(old_manifest)})
        git(MAIN, 'add', '--force', '--', receipt_name)
        helper.staged_rows({receipt_name: sha(MAIN / receipt_name)})
        git(MAIN, 'diff', '--cached', '--check')
        git(MAIN, 'commit', '--quiet', '-m', 'docs: evaluate OpenFilm 0.2.5 reuse and preserve scoped test evidence')
        published = git(MAIN, 'rev-parse', 'HEAD').decode().strip()
        assert git(MAIN, 'rev-parse', 'HEAD^').decode().strip() == commit
        state.update(status='committed-awaiting-ordinary-push', commit=published, main_changed=True)
        checkpoint()
        git(MAIN, 'push', 'origin', 'main')
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == published
        assert not git(MAIN, 'status', '--porcelain', '-z') and product.frozen() == inputs
        state.update(status='published-R16-research', published=True, remote_main=published,
            verified_links=len(references), compared_blobs=len(compared) + 1)
        checkpoint()
        try:
            update_progress(state)
        except Exception as exc:
            state['private_progress_update_error'] = repr(exc)
    except BaseException as exc:
        state.update(status='failed-preserved', error=repr(exc))
        raise
    finally:
        checkpoint()
        print(json.dumps({k: state.get(k) for k in ('status', 'commit', 'remote_main', 'error')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
