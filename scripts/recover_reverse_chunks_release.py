"""Recover the owned V82 staged candidate after a documented whitespace failure."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from publish_curve_clock import sha, git, staged_rows

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
BASE = '5c77f58149252df1f1bbbdf0c7bd652b3b6235cd'
REL = 'docs/validation/evidence/vfr-reverse-chunks-release-20261021-r1'
FULL_REL = 'docs/validation/evidence/vfr-reverse-chunks-20261021-v82'
REPORT = 'docs/validation/原生倒放缓存发布前字节审查修复_2026-10-21.md'
OLD_WORK = ROOT / 'product/.runtime/reverse-chunks-20261021-v82/publication-r2'
LICENSES = tuple('docs/assets/vfr-reverse-20261021-lab/' + name + '/LICENSE.txt'
                 for name in ('installed-r1', 'native-r1', 'native-r2', 'native-r3'))


def read(path):
    return json.loads(path.read_bytes())


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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    assert work.is_relative_to(ROOT / 'product/.runtime') and not work.exists()
    work.mkdir(parents=True)
    state = {'status': 'checking-owned-staged-candidate', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
             'force_push': False, 'calls': [], 'base_commit': BASE}
    def checkpoint():
        save(work / 'run.json', state)
    try:
        checkpoint()
        original = read(OLD_WORK / 'run.json')
        assert original['status'] == 'failed' and original['base_commit'] == BASE
        assert original['error']['type'] == 'CalledProcessError' and '--check' in original['error']['message']
        observation = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
            "Get-CimInstance Win32_Process -Filter 'ProcessId=11072' | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, check=True, timeout=30)
        assert not observation.stdout.decode('utf-8-sig').strip(), 'Original publisher remains live'
        assert git(MAIN, 'branch', '--show-current').decode().strip() == 'main'
        assert git(MAIN, 'rev-parse', 'HEAD').decode().strip() == BASE
        assert git(MAIN, 'remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == BASE
        expected_stage = {name.decode('utf8') for name in (OLD_WORK / 'stage-paths.nul').read_bytes().split(b'\0') if name}
        staged = {name.decode('utf8') for name in git(MAIN, 'diff', '--cached', '--name-only', '-z').split(b'\0') if name}
        assert staged == expected_stage
        assert not git(MAIN, 'diff', '--name-only')
        assert not git(MAIN, 'ls-files', '--others', '--exclude-standard', '-z')
        for name, digest in original['reviewed_final'].items():
            assert sha(MAIN / name) == digest, name
        spec = importlib.util.spec_from_file_location('v82_recovery_freeze', MAIN / 'scripts/run_frozen_regression.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        frozen = module.frozen()
        full = read(MAIN / FULL_REL / 'full-r2.json')
        assert len(frozen) == 249 and frozen == original['frozen_inputs'] == full['frozen_before'] == full['frozen_after']
        assert full['status'] == 'passed' and full['terminal_ok'] and full['methods'] == 1888 and full['skipped'] == 0
        assert full['external_fixture_count'] == 8 and full['external_fixtures_equal'] and full['verification_scripts_equal']
        for name, row in full['external_fixtures_expected'].items():
            assert sha(MAIN / name) == row['sha256'], name
        result = subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
                                 'diff', '--cached', '--check'], cwd=MAIN, capture_output=True)
        failure = result.stdout + result.stderr
        errors = failure.decode('utf8').splitlines()
        reported = {line.split(':', 1)[0] for line in errors if ': trailing whitespace.' in line or ': new blank line at EOF.' in line}
        assert result.returncode == 2 and reported == {*LICENSES, 'scripts/finalize_reverse_chunks.py'}, reported
        for name in LICENSES:
            data = (MAIN / name).read_bytes()
            assert data.endswith(b'\r\n') and data.count(b'\n') == 1 and not data[:-2].endswith((b' ', b'\t'))
        proof = MAIN / REL
        assert not proof.exists()
        proof.mkdir(parents=True)
        (proof / 'before-staged-check.log').write_bytes(failure)
        shutil.copyfile(OLD_WORK / 'run.json', proof / 'publication-r2-failure.json')
        prior=ROOT/'product/.runtime/reverse-chunks-20261021-v82/publication-r3'
        shutil.copyfile(prior/'run.json',proof/'publication-r3-guard-failure.json')
        shutil.copyfile(prior/'partial-main/proof/executed-recovery.py.txt',proof/'before-recovery-row-guard-fix.py.txt')
        shutil.copyfile(Path(__file__), proof / 'executed-recovery.py.txt')
        before_tree = git(MAIN, 'write-tree').decode().strip()
        before_generator = (MAIN / 'scripts/finalize_reverse_chunks.py').read_bytes()
        (proof / 'before-finalize_reverse_chunks.py.txt').write_bytes(before_generator)
        after_generator = before_generator.rstrip(b'\r\n') + b'\n'
        assert before_generator != after_generator
        assert ast.dump(ast.parse(before_generator.decode('utf8'))) == ast.dump(ast.parse(after_generator.decode('utf8')))
        (MAIN / 'scripts/finalize_reverse_chunks.py').write_bytes(after_generator)
        attributes = (MAIN / '.gitattributes').read_text('utf8')
        write(MAIN / '.gitattributes', attributes + '\n# V82 retained historical CRLF license bytes.\n'
              + '\n'.join(name + ' whitespace=cr-at-eol' for name in LICENSES)
              + '\n' + REL + '/** -text -whitespace\n'
              + 'scripts/recover_reverse_chunks_release.py -text whitespace=cr-at-eol\n')
        write(MAIN / REPORT, '''# 原生倒放缓存发布前字节审查修复（2026-10-21）

本记录绑定 V82 的 1888 项完整回归（0 跳过）及 249 个产品输入。发布前 Git 暂存检查发现 4 份历史 CC0 说明的 CRLF 识别问题和发布脚本末尾空行，原发布器在提交前退出。

| 编号 | 实际处理 | 证据与边界 |
|---|---|---|
| V82-R01 | 保留检查失败和旧发布器终态 | [原始诊断](evidence/vfr-reverse-chunks-release-20261021-r1/before-staged-check.log) · [原发布器失败](evidence/vfr-reverse-chunks-release-20261021-r1/publication-r2-failure.json) |
| V82-R02 | 保留 4 份历史文件原字节，只为对应路径识别 CRLF | 文件不是新增尾部空格；不重写历史许可证或媒体证据。 |
| V82-R03 | 只去除发布脚本末尾额外空行，AST 不变 | [原脚本留档](evidence/vfr-reverse-chunks-release-20261021-r1/before-finalize_reverse_chunks.py.txt) · [实际恢复脚本](evidence/vfr-reverse-chunks-release-20261021-r1/executed-recovery.py.txt) |
| V82-R04 | 复核完整套件、外部夹具、17 个 Skills 和暂存字节 | [完整回归](evidence/vfr-reverse-chunks-20261021-v82/full-r2.json) · [恢复审查](evidence/vfr-reverse-chunks-release-20261021-r1/recovery-main-r1.json) · [暂存审查](evidence/vfr-reverse-chunks-release-20261021-r1/staged-r1.json) |

首次恢复脚本因使用不存在的 README 末行编号而在提交前停止；其[终态](evidence/vfr-reverse-chunks-release-20261021-r1/publication-r3-guard-failure.json)和[旧脚本](evidence/vfr-reverse-chunks-release-20261021-r1/before-recovery-row-guard-fix.py.txt)保留。对应自有格式/文档改动已留档后恢复到原始暂存快照，再执行本轮审查。

恢复流程不重新运行或修改产品测试。249 个产品输入与完整回归、真实原生媒体和隔离安装所绑定的版本一致；所有暂存对象与工作区以 64 KiB 缓冲逐字节比较，继续使用普通 main 推送。历史复制收据描述首次复制时的快照；本记录另行绑定脚本结尾格式调整后的发布候选。最终状态以恢复发布器终态和远端提交一致性为准。
''')
        readme = MAIN / 'README.md'
        text = readme.read_text('utf8')
        lines = text.splitlines()
        positions = [n for n, line in enumerate(lines) if line.startswith('| V82-07 |')]
        assert len(positions) == 1
        lines.insert(positions[0] + 1, '| V82-08 | 发布前暂存检查与恢复 | 保留 CRLF/脚本 EOF 检查失败；4 份历史 CC0 原字节保留，脚本只修整结尾且 AST 不变；249 产品输入不变 | [恢复审查](' + REPORT + ') |')
        write(readme, '\n'.join(lines))
        existing_report = MAIN / 'docs/validation/原生分块倒放与离线缓存实测_2026-10-21.md'
        write(existing_report, existing_report.read_text('utf8') + '\n发布前暂存检查及其恢复另见[字节审查修复](原生倒放缓存发布前字节审查修复_2026-10-21.md)，保留首次失败和原脚本快照。\n')
        index = MAIN / 'docs/README.md'
        write(index, index.read_text('utf8') + '\n[V82 发布前字节审查修复](validation/原生倒放缓存发布前字节审查修复_2026-10-21.md)：保留暂存检查失败、历史 CRLF 字节和脚本 EOF 格式桥接。\n')
        destination_script = MAIN / 'scripts/recover_reverse_chunks_release.py'
        assert not destination_script.exists()
        shutil.copyfile(Path(__file__), destination_script)
        skills = read(MAIN / FULL_REL / 'skills-r2.json')
        assert skills['skill_count'] == len(skills['results']) == 17
        for row in skills['results']:
            assert row['validator_exit_code'] == 0 and row['installed_directory_resolves_to_repo']
            assert sha(MAIN / 'skills' / row['skill'] / 'SKILL.md') == row['sha256']
            assert (Path('C:/Users/carzy/.codex/skills') / row['skill']).resolve() == (MAIN / 'skills' / row['skill']).resolve()
        assert module.frozen() == frozen
        save(proof / 'recovery-main-r1.json', {
            'status': 'passed-owned-candidate-and-format-bridge', 'base_commit': BASE,
            'before_staged_tree': before_tree, 'original_staged_files': len(expected_stage),
            'reviewed_copy_files_verified': len(original['reviewed_final']), 'frozen_inputs': frozen,
            'full_methods': 1888, 'full_skipped': 0, 'full_sha256': sha(MAIN / FULL_REL / 'full-r2.json'),
            'external_fixtures': 8, 'skills': 17,
            'unchanged_historical_licenses': {name: sha(MAIN / name) for name in LICENSES},
            'generator_EOF_only_bridge': {'before_sha256': sha(proof / 'before-finalize_reverse_chunks.py.txt'),
                'after_sha256': sha(MAIN / 'scripts/finalize_reverse_chunks.py'), 'AST_equal': True},
            'recovery_generator_sha256': sha(Path(__file__))})
        changed = {p.decode('utf8') for p in git(MAIN, 'diff', '--name-only', '-z').split(b'\0') if p}
        changed |= {p.decode('utf8') for p in git(MAIN, 'diff', '--cached', '--name-only', '-z').split(b'\0') if p}
        changed |= {p.decode('utf8') for p in git(MAIN, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p}
        added = {p.relative_to(MAIN).as_posix() for p in proof.rglob('*') if p.is_file()} | {REPORT, 'scripts/recover_reverse_chunks_release.py'}
        assert changed == expected_stage | added
        paths = work / 'stage-paths.nul'
        paths.write_bytes(b'\0'.join(name.encode('utf8') for name in sorted(changed)) + b'\0')
        git(MAIN, 'add', '--pathspec-from-file=' + str(paths), '--pathspec-file-nul')
        git(MAIN, 'add', '--renormalize', '--pathspec-from-file=' + str(paths), '--pathspec-file-nul')
        assert not git(MAIN, 'diff', '--name-only')
        git(MAIN, 'diff', '--cached', '--check')
        state.update(status='checking-all-staged-bytes', changed_files=len(changed), frozen_inputs=frozen)
        checkpoint()
        rows = staged_rows({**{name: sha(MAIN / name) for name in changed}, **frozen})
        receipt = proof / 'staged-r1.json'
        save(receipt, {'status': 'passed', 'base_commit': BASE, 'changed_files': len(changed),
             'frozen_files': 249, 'compared_blobs': len(rows), 'files': rows,
             'all_staged_bytes_equal_workspace': True, 'all_frozen_bytes_equal_staged': True,
             'stream_buffer_bytes': 65536, 'diff_check': 'passed',
             'full_sha256': sha(MAIN / FULL_REL / 'full-r2.json'), 'generator_sha256': sha(Path(__file__))})
        git(MAIN, 'add', '--', receipt.relative_to(MAIN).as_posix())
        staged_rows({receipt.relative_to(MAIN).as_posix(): sha(receipt)})
        for path in (MAIN / REPORT,):
            for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)', path.read_text('utf8')):
                target = (path.parent / token.split('#', 1)[0]).resolve()
                assert target.is_relative_to(MAIN) and target.is_file(), token
        assert module.frozen() == frozen and not git(MAIN, 'diff', '--name-only')
        git(MAIN, 'diff', '--cached', '--check')
        state.update(status='passed-staged-byte-audit', staged_files=len(changed) + 1)
        checkpoint()
        git(MAIN, 'commit', '--quiet', '-m', 'feat: preserve native reverse intervals with lossless frame chunks')
        commit = git(MAIN, 'rev-parse', 'HEAD').decode().strip()
        assert git(MAIN, 'rev-parse', 'HEAD^').decode().strip() == BASE
        state.update(status='committed-awaiting-ordinary-push', commit=commit)
        checkpoint()
        git(MAIN, 'push', 'origin', 'main')
        remote = git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
        assert remote == commit and not git(MAIN, 'status', '--porcelain', '-z') and module.frozen() == frozen
        state.update(status='published', remote_main=remote, main_clean=True, full_methods=1888,
                     full_seconds=full['suite_seconds'], full_sha256=sha(MAIN / FULL_REL / 'full-r2.json'))
    except BaseException as error:
        state.update(status='failed', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        checkpoint()
        print(json.dumps({k: state.get(k) for k in ('status', 'commit', 'remote_main', 'error')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
