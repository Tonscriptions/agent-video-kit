"""Recover the reviewed V93 index after Git normalized the CRLF manifest."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import publish_float_timeline as original
from float_timeline_release_docs import ROOT, MAIN, REL, REPORT, CONTRACT, LATEST_DOCS, local_links, write
from run_frozen_regression import frozen, sha

git = original.git
WORK = ROOT / 'product/.runtime/float-timeline-20261022'
EVIDENCE = REL + '/publication-recovery-r1'
NOTE = 'docs/validation/浮点宿主发布字节核验恢复_2026-10-22.md'
SCRIPT = 'scripts/recover_float_timeline_publication.py'


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2))


def utc():
    return datetime.now(timezone.utc).isoformat()


def paths(raw):
    return {row.decode('utf8') for row in raw.split(b'\0') if row}


def update_progress(state, full, installed, skills):
    path = MAIN / 'product/.runtime/agent-video-kit-progress-20261021.json'
    old = path.read_bytes()
    data = json.loads(old)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = WORK / ('progress-before-recovered-V93-' + stamp + '.json')
    backup.write_bytes(old)
    data['main'].update(branch='main', version='V93', commit=state['commit'], remote_main=state['remote_main'],
        product_commit=state['commit'], clean=True, full_methods=2280, suite_seconds=full['suite_seconds'],
        skipped=0, frozen_inputs=288, full_receipt=str(MAIN / REL / 'full-r2.json'),
        publication_record=str(WORK / 'publication-r3/run.json'), skills=17,
        verified_document_links=state['verified_links'], staged_blob_comparisons=state['compared_blobs'],
        skill_links=skills['local_links_checked'], readme_and_numbered_actual_media_updated=True,
        latest_documentation_update='V93 actual full2280/installed163; recovered exact CRLF manifest staging; library host only, full parity incomplete')
    data.setdefault('float_timeline_lab', {}).update(status='published-V93-library-host-default-render-not-integrated',
        published=True, published_commit=state['commit'], remote_main=state['remote_main'], full_suite_started=True,
        full_suite_passed=True, full_methods=2280, full_seconds=full['suite_seconds'], installed_status=installed['status'],
        installed_methods=163, publication_record=str(WORK / 'publication-r3/run.json'),
        release_chain_status='published', public_main_readme_updated=True, main_untouched=False,
        publication_recovery_record=str(MAIN / EVIDENCE / 'verification.json'))
    data.update(updated_at_utc=utc(), goal_status='active', previous_progress_snapshot=str(backup),
        current_goal_turn_classification='progress: actual full2280/installed163 published after exact-byte index recovery; complete CapCut parity unfinished')
    assert path.read_bytes() == old, 'Concurrent private progress change'
    temporary = path.with_name('progress-recovered-V93-' + stamp + '.tmp')
    save(temporary, data)
    os.replace(temporary, path)


def main():
    work = WORK / 'publication-r3'
    release = WORK / 'release-chain-r3'
    assert not work.exists() and not release.exists()
    work.mkdir(parents=True)
    release.mkdir()
    state = {'status': 'checking-preserved-index-failure', 'pid': os.getpid(), 'started_at_utc': utc(),
        'force_push': False, 'main_integrated': True, 'generator_sha256': sha(Path(__file__))}

    def checkpoint():
        state['updated_at_utc'] = utc()
        save(work / 'run.json', state)
        save(release / 'run.json', {**state, 'status': ('published-V93-with-actual-full2280-and-installed163'
            if state['status'] == 'published' else state['status'])})

    checkpoint()
    try:
        failure = read(WORK / 'publication-r2/run.json')
        assert failure['status'] == 'failed-preserved' and failure['main_integrated']
        assert failure['error'] == {'type': 'AssertionError', 'message': 'video-cut-install-manifest.json'}
        audit, full = original.source_gate(True)
        current, parent = audit['frozen_inputs'], audit['published_parent']
        assert frozen() == current and len(current) == 288
        spec = importlib.util.spec_from_file_location('v93_recovered_main_inputs', MAIN / 'scripts/run_frozen_regression.py')
        main_inputs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_inputs)
        assert main_inputs.frozen() == current
        assert git(MAIN, 'branch', '--show-current').decode().strip() == 'main'
        assert git(MAIN, 'rev-parse', 'HEAD').decode().strip() == parent
        assert git(MAIN, 'remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == parent
        for name, digest in failure['source_files'].items():
            assert sha(ROOT / name) == sha(MAIN / name) == digest, name
        manifest = MAIN / 'video-cut-install-manifest.json'
        local = manifest.read_bytes()
        staged = git(MAIN, 'show', ':video-cut-install-manifest.json')
        assert len(local) == 56818 and len(staged) == 55878 and local.count(b'\r\n') == 940
        assert local.replace(b'\r\n', b'\n') == staged and b'\r\n' not in staged
        generated = {REL + '/' + name for name in ('skills-release-r2.json', 'release-main-r2.json',
            'publication-copy-r2.json', 'staged-release-r2.json')}
        allowed = set(failure['source_files']) | generated | set(LATEST_DOCS) | {'.gitattributes', 'video-cut-install-manifest.json'}
        changed = paths(git(MAIN, 'diff', 'HEAD', '--name-only', '-z'))
        changed |= paths(git(MAIN, 'ls-files', '--others', '--exclude-standard', '-z'))
        assert changed <= allowed, sorted(changed - allowed)
        source = ROOT / EVIDENCE
        source.mkdir(parents=True, exist_ok=False)
        for rel, label in [('publication-r2/run.json', 'failed-publication.json'),
                ('release-chain-r2/run.json', 'failed-release-owner.json'),
                ('release-chain-r2/publish-reviewed-V93.log', 'failed-publisher.log')]:
            shutil.copyfile(WORK / rel, source / label)
        note = f'''# 浮点宿主发布字节核验恢复

V93 的真实完整回归为 **2,280 方法 /{full['suite_seconds']:.3f} 秒 /0 跳过**，新安装测试为 163 方法。恢复没有修改 288 个已测产品输入，也没有新增或重复计算功能测试。

| 编号 | 实际检查 | 结果 |
|---|---|---|
| PUB93-01 | 原发布失败 | 安装清单工作区 56,818 字节，暂存区 55,878 字节；940 处 CRLF 被 Git 文本属性规范化为 LF，独立还原后两者完全相同 |
| PUB93-02 | 修复范围 | 为该清单设置 `-text whitespace=cr-at-eol`，保留原工作区字节；产品、原始媒体与既有测试收据不变 |
| PUB93-03 | 恢复门槛 | 重新核验实际完整终态、163 项安装终态、17 个 Skill 正文、原始复制清单、当前分支及远端父提交；逐项比对所有待发文件和 288 产品输入的暂存 blob |
| PUB93-04 | 发布方式 | 普通 commit/push；实际提交、远端和干净状态保存在拥有进程的终态，不能以提交前收据代替推送成功 |

[原失败与恢复核验](evidence/float-timeline-20261022-lab/publication-recovery-r1/verification.json) · [原完整回归](evidence/float-timeline-20261022-lab/full-r2.json)。本轮依旧只交付库层作者时钟宿主；默认渲染、所有效果及完整剪映等价未完成。
'''
        write(ROOT / NOTE, note)
        save(source / 'verification.json', {'status': 'passed-explained-original-index-normalization-failure',
            'at_utc': utc(), 'failed_publisher_sha256': sha(source / 'failed-publication.json'),
            'failure_log_sha256': sha(source / 'failed-publisher.log'), 'worktree_bytes': len(local),
            'original_staged_bytes': len(staged), 'CRLF_count': 940, 'lf_normalization_explains_entire_difference': True,
            'worktree_sha256': 'sha256:' + hashlib.sha256(local).hexdigest(),
            'old_staged_sha256': 'sha256:' + hashlib.sha256(staged).hexdigest(),
            'product_inputs': current, 'full_methods': 2280, 'installed_methods': 163, 'new_test_methods': 0,
            'original_full_receipt_sha256': sha(ROOT / REL / 'full-r2.json'),
            'generator_sha256': sha(Path(__file__)), 'published_claimed': False})
        reviewed = original.source_files(current, audit['parent_frozen_inputs'])
        reviewed[NOTE] = sha(ROOT / NOTE)
        for name, digest in reviewed.items():
            target = MAIN / name
            if name not in failure['source_files']:
                assert not target.exists(), ('Unexpected new destination', name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or sha(target) != digest:
                shutil.copyfile(ROOT / name, target)
            assert sha(target) == digest
        readme = MAIN / 'README.md'
        text = readme.read_text('utf8')
        marker = '<!-- /V93-AUTHOR-CLOCK-FLOAT-HOST -->'
        assert marker in text and 'V93-11' not in text
        row = '| V93-11 | 发布字节核验恢复 | 原完整 2280 项与安装 163 项结果保持不变；保留 CRLF 规范化失败，逐字节核验后普通提交，不新增功能测试计数 | [恢复说明](' + NOTE + ') |\n'
        table_end = next(line for line in text.splitlines() if line.startswith('| V93-10 |'))
        write(readme, text.replace(table_end + '\n', table_end + '\n' + row, 1))
        attrs = MAIN / '.gitattributes'
        write(attrs, attrs.read_text('utf8') + '\n# V93 publication recovery preserves the reviewed CRLF manifest.\n'
            'video-cut-install-manifest.json -text whitespace=cr-at-eol\n' + SCRIPT + ' -text\n')
        skills = read(MAIN / REL / 'skills-release-r2.json')
        mapping = read(manifest)
        assert len(mapping['skills']) == len(skills['results']) == 17
        for entry in mapping['skills']:
            result = next(v for v in skills['results'] if v['skill'] == entry['name'])
            assert sha(MAIN / 'skills' / entry['name'] / 'SKILL.md') == result['sha256'] == 'sha256:' + entry['skill_md_sha256']
        assert manifest.read_bytes() == local
        names = [*LATEST_DOCS, REPORT, CONTRACT, NOTE, *('skills/' + v['name'] + '/SKILL.md' for v in mapping['skills'])]
        links = local_links(MAIN, names)
        expected_names = set(reviewed) | set(names) | {'.gitattributes', 'video-cut-install-manifest.json'}
        expected_names |= {n for n in generated if (MAIN / n).is_file()}
        changes = paths(git(MAIN, 'diff', 'HEAD', '--name-only', '-z')) | paths(git(MAIN, 'ls-files', '--others', '--exclude-standard', '-z'))
        assert changes <= expected_names, sorted(changes - expected_names)
        expected = {n: sha(MAIN / n) for n in expected_names}
        pathspec = work / 'paths.nul'
        pathspec.write_bytes(b'\0'.join(n.encode('utf8') for n in sorted(expected)) + b'\0')
        state.update(status='restaging-reviewed-exact-bytes', base_commit=parent, frozen_inputs=current,
            source_files=reviewed, verified_links=len(links)); checkpoint()
        git(MAIN, 'add', '--force', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
        git(MAIN, 'add', '--renormalize', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
        rows = original.staged_rows({**expected, **current})
        assert not git(MAIN, 'diff', '--name-only')
        git(MAIN, 'diff', '--cached', '--check')
        receipt = REL + '/staged-release-r3.json'
        save(MAIN / receipt, {'status': 'passed-exact-source-and-raw-manifest-index-recovery',
            'base_commit': parent, 'compared_blobs': len(rows), 'files': rows, 'frozen_files': 288,
            'full_methods': 2280, 'installed_methods': 163, 'new_test_methods': 0, 'verified_links': len(links),
            'all_staged_bytes_equal_workspace': True, 'force_push': False,
            'recovery_receipt_sha256': sha(MAIN / EVIDENCE / 'verification.json')})
        git(MAIN, 'add', '--force', '--', receipt)
        original.staged_rows({receipt: sha(MAIN / receipt)})
        git(MAIN, 'diff', '--cached', '--check')
        assert frozen() == main_inputs.frozen() == current and not git(MAIN, 'diff', '--name-only')
        original.source_gate(True)
        git(MAIN, 'commit', '--quiet', '-m', 'feat: add author-clock float host with exact-byte publication audit')
        commit = git(MAIN, 'rev-parse', 'HEAD').decode().strip()
        assert git(MAIN, 'rev-parse', 'HEAD^').decode().strip() == parent
        state.update(status='committed-awaiting-ordinary-push', commit=commit, compared_blobs=len(rows) + 1); checkpoint()
        git(MAIN, 'push', 'origin', 'main')
        remote = git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
        assert remote == commit and not git(MAIN, 'status', '--porcelain', '-z') and frozen() == main_inputs.frozen() == current
        state.update(status='published', remote_main=remote, main_clean=True, full_methods=2280, isolated_methods=163)
        checkpoint()
        try:
            update_progress(state, full, original.installed_gate(), skills)
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
